"""Dagster job execution in spawned child processes.

One child per run rather than a pool slot, because a run is minutes long, must be
individually cancellable, and must not be able to take the web server with it when it
OOMs.  The child creates its own ``DagsterInstance`` from the inherited
``DAGSTER_HOME`` — instances and their sqlite handles are not passed across the
process boundary.

This replaces calling ``job_def.execute_in_process(...)`` in the ASGI process, which
ran the whole annotation pipeline (Polars ``sink_parquet``, ``polars_bio.scan_vcf``
with its own Tokio runtime, DuckDB joins) inside the single web worker.
"""

from __future__ import annotations

import asyncio
import multiprocessing
import os
import signal
from dataclasses import dataclass, field
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from typing import Any


@dataclass
class JobResult:
    """Outcome reported back by the child."""

    success: bool
    run_id: str = ""
    error: str = ""


@dataclass
class JobHandle:
    """Parent-side handle on a running job child."""

    token: str
    partition_key: str
    job_name: str
    process: BaseProcess
    _conn: Connection = field(repr=False)

    @property
    def pid(self) -> int | None:
        return self.process.pid

    def alive(self) -> bool:
        return self.process.is_alive()

    def poll(self) -> JobResult | None:
        """Return the child's result if it has reported one, else ``None``.

        Never blocks.  A child that died without reporting (OOM kill, SIGKILL) yields a
        failure result rather than hanging the caller forever.
        """
        if self._conn.poll():
            payload = self._conn.recv()
            return JobResult(**payload)
        if not self.process.is_alive():
            code = self.process.exitcode
            if code == 0:
                return JobResult(success=True)
            return JobResult(
                success=False,
                error=f"job child exited with code {code} without reporting a result",
            )
        return None


_active: dict[str, JobHandle] = {}


async def await_job(handle: JobHandle, poll_interval: float = 1.0) -> JobResult:
    """Wait for a job child to finish without blocking the event loop.

    ``handle.poll()`` never blocks, so the wait is a plain ``asyncio.sleep`` loop: the
    ASGI worker keeps serving requests for the whole minutes-long run.
    """
    while True:
        result = handle.poll()
        if result is not None:
            return result
        await asyncio.sleep(poll_interval)


def _child_execute(
    conn: Connection,
    job_name: str,
    run_config: dict[str, Any],
    partition_key: str,
    partition_def_name: str,
    tags: dict[str, str],
) -> None:
    """Run one Dagster job to completion in this child and report the outcome."""
    from just_dna_pipelines.annotation.definitions import defs
    from just_dna_pipelines.runtime import load_env
    from webui.dagster_env import get_dagster_instance

    load_env()
    result_payload: dict[str, Any]
    try:
        instance = get_dagster_instance()
        job_def = defs.resolve_job_def(job_name)
        if partition_key and partition_def_name:
            existing = instance.get_dynamic_partitions(partition_def_name)
            if partition_key not in existing:
                instance.add_dynamic_partitions(partition_def_name, [partition_key])
        result = job_def.execute_in_process(
            run_config=run_config,
            instance=instance,
            tags={**tags, "dagster/partition": partition_key} if partition_key else tags,
        )
        result_payload = {"success": bool(result.success), "run_id": result.run_id}
    except Exception as exc:  # reported to the parent, which owns the UI message
        result_payload = {"success": False, "error": f"{type(exc).__name__}: {exc}"}

    conn.send(result_payload)
    conn.close()


def submit_job(
    token: str,
    job_name: str,
    run_config: dict[str, Any],
    partition_key: str,
    partition_def_name: str = "",
    tags: dict[str, str] | None = None,
) -> JobHandle:
    """Start *job_name* in a spawned child and return a handle to poll.

    Args:
        token: Caller-chosen id used to cancel or look the job up later.  Dagster
            assigns the real run id inside the child; it comes back via ``poll()``.
        job_name: Name resolvable by ``defs.resolve_job_def``.
        run_config: Dagster run config (the ``"ops"`` key, not ``"assets"``).
        partition_key: Dynamic partition key, or "" for unpartitioned jobs.
        partition_def_name: Name of the dynamic partitions def to register the key in.
        tags: Extra Dagster run tags.  ``source: webui`` is added.
    """
    ctx = multiprocessing.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    process = ctx.Process(
        target=_child_execute,
        args=(
            child_conn,
            job_name,
            run_config,
            partition_key,
            partition_def_name,
            {"source": "webui", **(tags or {})},
        ),
        name=f"dagster-{job_name}-{token[:8]}",
        daemon=False,
    )
    process.start()
    child_conn.close()  # only the child writes; keep the parent end EOF-accurate

    handle = JobHandle(
        token=token,
        partition_key=partition_key,
        job_name=job_name,
        process=process,
        _conn=parent_conn,
    )
    _active[token] = handle
    print(
        f"[compute] job {job_name} started in pid={process.pid} "
        f"(token={token[:8]}, partition={partition_key or '-'})",
        flush=True,
    )
    return handle


def active_jobs() -> dict[str, JobHandle]:
    """Return live handles, pruning any whose child has exited."""
    for token, handle in list(_active.items()):
        if not handle.alive():
            _active.pop(token, None)
    return dict(_active)


def forget_job(token: str) -> None:
    _active.pop(token, None)


def cancel_job(token: str) -> bool:
    """Kill the child running *token*.  Returns whether a live child was killed.

    SIGKILL rather than ``terminate()``: a child parked inside a native thread pool
    never runs a Python signal handler, so SIGTERM would be ignored.
    """
    handle = _active.get(token)
    if handle is None or not handle.alive():
        _active.pop(token, None)
        return False
    pid = handle.pid
    if pid is not None:
        try:
            os.kill(pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
    handle.process.join(timeout=5)
    _active.pop(token, None)
    print(f"[compute] job {handle.job_name} cancelled (pid={pid})", flush=True)
    return True


def kill_all_jobs() -> list[str]:
    """Kill every live job child.  Used on shutdown; returns the tokens killed."""
    return [token for token in active_jobs() if cancel_job(token)]
