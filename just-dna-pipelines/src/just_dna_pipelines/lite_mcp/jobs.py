"""Background annotation jobs that outlive the MCP session that started them.

A job is a directory under ``data/interim/lite_mcp/jobs/{job_id}/`` holding ``job.json`` and the
worker's log. The server writes ``job.json`` once, then spawns a worker process
(``python -m just_dna_pipelines.lite_mcp.worker <job_dir>``) that owns the file until it exits.
Nothing lives in the server's memory, so a stdio server restarted by the next Claude Code or Cursor
session can still report on a job the previous one started, and the Dagster run it produced is in
the shared ``DAGSTER_HOME`` either way.

The worker is a fresh interpreter started with ``sys.executable -m`` — never a fork of this
process, which has already used Polars (see "Process Model & Fork Safety" in AGENTS.md), and never
a console-script wrapper (locked-down Windows refuses to execute those).
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

import psutil
from pydantic import BaseModel, Field

from just_dna_pipelines.annotation.annotation_runner import AnnotationOutcome
from just_dna_pipelines.annotation.resources import get_workspace_root
from just_dna_pipelines.lite_mcp.catalog import lite_mcp_dir, write_json

JobStatus = Literal["queued", "running", "succeeded", "partial", "failed", "canceled"]
SampleStatus = Literal["queued", "preparing", "running", "succeeded", "failed", "canceled", "skipped"]
ACTIVE: frozenset[str] = frozenset({"queued", "running"})
WORKER_MODULE = "just_dna_pipelines.lite_mcp.worker"


class SampleRun(BaseModel):
    requested: str = Field(description="The sample as the caller named it: id, alias, or VCF path")
    sample_id: Optional[str] = None
    status: SampleStatus = "queued"
    run_id: Optional[str] = Field(None, description="Dagster run id, fixed before the run starts")
    outcome: Optional[AnnotationOutcome] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class JobRequest(BaseModel):
    samples: list[str]
    modules: list[str]
    user: str = "local"
    ensembl: bool = False
    reuse_normalized: bool = True


class JobRecord(BaseModel):
    job_id: str
    kind: Literal["annotation"] = "annotation"
    status: JobStatus = "queued"
    request: JobRequest
    samples: list[SampleRun]
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    pid: Optional[int] = None
    error: Optional[str] = None
    log_path: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def jobs_dir() -> Path:
    return lite_mcp_dir() / "jobs"


def job_dir(job_id: str) -> Path:
    if not job_id or "/" in job_id or "\\" in job_id or job_id.startswith("."):
        raise ValueError(f"{job_id!r} is not a job id")
    return jobs_dir() / job_id


def job_file(directory: Path) -> Path:
    return directory / "job.json"


def job_dir_of(record: JobRecord) -> Path:
    return Path(record.log_path).parent


def results_dir(job_directory: Path, partition_key: str) -> Path:
    """A job's own copy of one sample's module outputs (``user__sample``)."""
    return job_directory / "results" / partition_key.replace("/", "__")


def cancel_marker(directory: Path) -> Path:
    return directory / "cancel"


def pid_file(directory: Path) -> Path:
    """Written by the server right after spawning, so a worker that dies at import is still detected."""
    return directory / "worker.pid"


def worker_pid(record: JobRecord) -> Optional[int]:
    if record.pid is not None:
        return record.pid
    path = pid_file(job_dir(record.job_id))
    return int(path.read_text().strip()) if path.exists() else None


def read_job(job_id: str) -> JobRecord:
    path = job_file(job_dir(job_id))
    if not path.exists():
        raise KeyError(f"no job {job_id!r}")
    return JobRecord.model_validate_json(path.read_text(encoding="utf-8"))


def read_job_at(directory: Path) -> JobRecord:
    return JobRecord.model_validate_json(job_file(directory).read_text(encoding="utf-8"))


def save_job(record: JobRecord) -> None:
    write_json(job_file(job_dir(record.job_id)), record.model_dump(mode="json"))


def _pid_alive(pid: Optional[int]) -> bool:
    if pid is None:
        return False
    if not psutil.pid_exists(pid):
        return False
    try:
        return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def reconcile(record: JobRecord) -> JobRecord:
    """Mark a job whose worker died without finishing as failed, rather than running forever."""
    pid = worker_pid(record)
    if record.status in ACTIVE and pid is not None and not _pid_alive(pid):
        record = read_job(record.job_id)  # the worker may have finished between the two reads
        if record.status not in ACTIVE:
            return record
        record.status = "failed"
        record.error = record.error or f"worker process {pid} exited without finishing; see {record.log_path}"
        record.finished_at = record.finished_at or utc_now()
        for sample in record.samples:
            if sample.status in ("queued", "preparing", "running"):
                sample.status = "failed"
                sample.error = sample.error or "worker exited mid-run"
        save_job(record)
    return record


def list_jobs(limit: int = 20) -> list[JobRecord]:
    root = jobs_dir()
    if not root.is_dir():
        return []
    records = [read_job_at(d) for d in root.iterdir() if job_file(d).exists()]
    records.sort(key=lambda r: r.created_at, reverse=True)
    return [reconcile(r) for r in records[:limit]]


def active_jobs() -> list[JobRecord]:
    return [r for r in list_jobs(limit=200) if r.status in ACTIVE]


def _detached_kwargs() -> dict[str, object]:
    """Keep the worker out of the server's process group, so the server exiting does not kill it."""
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def create_job(request: JobRequest) -> JobRecord:
    """Record the job and start its worker. Returns immediately."""
    job_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    directory = job_dir(job_id)
    directory.mkdir(parents=True, exist_ok=False)
    log_path = directory / "worker.log"
    record = JobRecord(
        job_id=job_id,
        request=request,
        samples=[SampleRun(requested=s, run_id=str(uuid.uuid4())) for s in request.samples],
        created_at=utc_now(),
        log_path=str(log_path),
    )
    save_job(record)
    with log_path.open("ab") as log:
        proc = subprocess.Popen(
            [sys.executable, "-m", WORKER_MODULE, str(directory)],
            cwd=str(get_workspace_root()),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            **_detached_kwargs(),
        )
    # job.json belongs to the worker from here on; the pid goes in a file of its own.
    pid_file(directory).write_text(str(proc.pid))
    return record.model_copy(update={"pid": proc.pid})


def cancel_job(job_id: str) -> JobRecord:
    """Ask the worker to stop, then kill it. Returns the record after the fact."""
    record = read_job(job_id)
    if record.status not in ACTIVE:
        return record
    cancel_marker(job_dir(job_id)).touch()
    pid = worker_pid(record)
    if pid is not None and _pid_alive(pid):
        root = psutil.Process(pid)
        tree = [root, *root.children(recursive=True)]
        for proc in tree:
            try:
                proc.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(tree, timeout=5)
        for proc in alive:
            try:
                proc.kill()
            except psutil.NoSuchProcess:
                pass
    record = read_job(job_id)
    record.status = "canceled"
    record.finished_at = utc_now()
    for sample in record.samples:
        if sample.status in ("queued", "preparing", "running"):
            sample.status = "canceled"
    save_job(record)
    return record
