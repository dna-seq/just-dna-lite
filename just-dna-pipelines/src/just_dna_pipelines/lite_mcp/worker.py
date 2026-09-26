"""The process that runs one annotation job: ``python -m just_dna_pipelines.lite_mcp.worker <job_dir>``.

Samples run one after another in this process (each a Dagster ``execute_in_process``), because a
whole-genome normalization is memory-heavy and two at once is how a laptop starts swapping. Jobs
queue behind each other for the same reason: a worker waits while an earlier job is still running.

Owns ``job.json`` for its lifetime and rewrites it after every state change.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from dagster import DagsterInstance

from just_dna_pipelines.annotation.annotation_runner import (
    AnnotationRequest,
    ensure_dagster_home,
    run_annotation,
)
from just_dna_pipelines.annotation.definitions import defs
from just_dna_pipelines.annotation.resources import (
    ensure_vcf_in_user_input_dir,
    list_default_sample_alias_map,
    resolve_default_sample,
)
from just_dna_pipelines.lite_mcp.catalog import find_sample, list_samples
from just_dna_pipelines.lite_mcp.jobs import (
    JobRecord,
    SampleRun,
    active_jobs,
    cancel_marker,
    job_dir_of,
    read_job_at,
    results_dir,
    save_job,
    utc_now,
)
from just_dna_pipelines.runtime import load_env

POLL_SECONDS = 3.0


class SampleResolutionError(ValueError):
    """The requested sample could not be turned into a VCF in a user input directory."""


def resolve_sample(requested: str, default_user: str) -> tuple[Path, str, dict[str, Any]]:
    """``(placed VCF, user, metadata)`` for a sample id, a VCF path, a public alias, or a bare name."""
    key = requested.strip()
    listing = list_samples()
    exact = next((s for s in listing.samples if s.sample_id == key), None)
    if exact is not None and exact.vcf_path:
        return Path(exact.vcf_path), exact.user, {"sex": exact.sex, "reference_genome": exact.reference_genome}

    candidate = Path(key).expanduser()
    if candidate.is_file():
        return ensure_vcf_in_user_input_dir(candidate.resolve(), default_user, log=None), default_user, {}

    if key.lower() in list_default_sample_alias_map():
        meta = resolve_default_sample(key.lower(), user_name=default_user, log=None)
        return Path(meta["path"]), default_user, meta

    found = find_sample(key)
    if found is not None and found.vcf_path:
        return Path(found.vcf_path), found.user, {"sex": found.sex, "reference_genome": found.reference_genome}
    raise SampleResolutionError(
        f"{requested!r} is not a listed sample id (user/sample), a VCF path, a public-genome alias, or a "
        "unique sample name. Call list_samples."
    )


def snapshot_results(job_directory: Path, partition_key: str, modules_dir: Path, modules: list[str]) -> None:
    """Copy this run's module parquets and manifest into the job, so validating the job later reads
    the bytes this job produced, not whatever a later run of the same sample left in its output dir.
    """
    target = results_dir(job_directory, partition_key)
    target.mkdir(parents=True, exist_ok=True)
    for name in [*(f"{m}_weights.parquet" for m in modules), "manifest.json"]:
        source = modules_dir / name
        if source.exists():
            shutil.copy2(source, target / name)


def _cancelled(job_dir: Path) -> bool:
    return cancel_marker(job_dir).exists()


def _wait_for_turn(record: JobRecord, job_dir: Path) -> bool:
    """Block while an earlier job is running. False when this job was cancelled meanwhile."""
    while True:
        if _cancelled(job_dir):
            return False
        earlier = [j for j in active_jobs() if j.job_id != record.job_id and j.created_at < record.created_at]
        if not earlier:
            return True
        time.sleep(POLL_SECONDS)


def _clean(value: Any) -> Any:
    return None if value in (None, "", "N/A") else value


def run_sample(record: JobRecord, sample: SampleRun, instance: DagsterInstance) -> None:
    sample.status = "preparing"
    sample.started_at = utc_now()
    save_job(record)
    vcf, user, meta = resolve_sample(sample.requested, record.request.user)
    request = AnnotationRequest(
        vcf_path=vcf,
        user_name=user,
        modules=record.request.modules,
        ensembl=record.request.ensembl,
        sex=_clean(meta.get("sex")),
        reference_genome=meta.get("reference_genome") or "GRCh38",
        species=meta.get("species") or "Homo sapiens",
        subject_id=_clean(meta.get("subject_id")),
        reuse_normalized=record.request.reuse_normalized,
        source_tag="mcp",
    )
    sample.sample_id = request.partition_key
    sample.status = "running"
    save_job(record)
    outcome = run_annotation(request, instance, defs, run_id=sample.run_id)
    snapshot_results(job_dir_of(record), request.partition_key, Path(outcome.modules_dir), record.request.modules)
    sample.outcome = outcome
    sample.run_id = outcome.run_id or sample.run_id
    sample.status = "succeeded" if outcome.success else "failed"
    sample.error = outcome.error
    sample.finished_at = utc_now()
    save_job(record)


def main(job_dir: Path) -> int:
    load_env()
    ensure_dagster_home()
    record = read_job_at(job_dir)
    record.pid = os.getpid()
    save_job(record)

    if not _wait_for_turn(record, job_dir):
        record.status = "canceled"
        record.finished_at = utc_now()
        save_job(record)
        return 0

    record.status = "running"
    record.started_at = utc_now()
    save_job(record)
    instance = DagsterInstance.get()

    for sample in record.samples:
        if _cancelled(job_dir):
            sample.status = "canceled"
            continue
        try:
            run_sample(record, sample, instance)
        except SampleResolutionError as exc:
            sample.status = "skipped"
            sample.error = str(exc)
            sample.finished_at = utc_now()
        except Exception as exc:  # one genome failing must not cost the others
            sample.status = "failed"
            sample.error = f"{type(exc).__name__}: {exc}"
            sample.finished_at = utc_now()
            traceback.print_exc()
        save_job(record)

    outcomes = [s.status for s in record.samples]
    if _cancelled(job_dir):
        record.status = "canceled"
    elif all(s == "succeeded" for s in outcomes):
        record.status = "succeeded"
    elif any(s == "succeeded" for s in outcomes):
        record.status = "partial"
    else:
        record.status = "failed"
    record.finished_at = utc_now()
    save_job(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
