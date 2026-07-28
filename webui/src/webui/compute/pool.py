"""A spawn-context process pool for short, CPU-bound queries.

Every submission carries a wall-clock budget.  A blown budget is not "cancelled" —
you cannot cancel a Rust kernel mid-flight — so the worker is killed and the pool
rebuilt.  That is the only honest way to bound a Polars call.
"""

from __future__ import annotations

import asyncio
import contextlib
import multiprocessing
import os
import signal
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from typing import Any, TypeVar

# Long enough for a whole-genome streaming sort on slow disks, short enough that a
# genuinely wedged child does not hold a pool slot forever.
DEFAULT_TIMEOUT_SEC: float = float(os.getenv("JUST_DNA_COMPUTE_TIMEOUT", "300"))

_T = TypeVar("_T")

_pool: ProcessPoolExecutor | None = None
_pool_lock: asyncio.Lock | None = None


class ComputeTimeout(TimeoutError):
    """A compute task exceeded its wall-clock budget and its worker was killed."""


def _worker_count() -> int:
    configured = os.getenv("JUST_DNA_COMPUTE_WORKERS", "").strip()
    if configured:
        return max(1, int(configured))
    cpus = os.cpu_count() or 2
    return max(1, min(4, cpus // 2))


def _warm_child() -> None:
    """Pre-import the heavy modules so the first user query does not pay for them.

    Spawned children start from a bare interpreter.  Importing polars and the grid
    helpers costs a couple of seconds; doing it in the pool initializer moves that off
    the first sort a user triggers.
    """
    import polars  # noqa: F401
    import reflex_mui_datagrid.polars_utils  # noqa: F401


def _new_pool() -> ProcessPoolExecutor:
    # spawn is mandatory, not a default we are accepting: a fork context would inherit
    # the parent's Rayon/Tokio pools and deadlock on the first parallel call.
    return ProcessPoolExecutor(
        max_workers=_worker_count(),
        mp_context=multiprocessing.get_context("spawn"),
        initializer=_warm_child,
        # Recycle workers so a leaky native allocator cannot grow without bound.
        max_tasks_per_child=200,
    )


def start_pool() -> None:
    """Create the pool if it does not exist yet."""
    global _pool, _pool_lock
    if _pool_lock is None:
        _pool_lock = asyncio.Lock()
    if _pool is None:
        _pool = _new_pool()
        print(
            f"[compute] pool started: {_worker_count()} spawn workers, "
            f"timeout={DEFAULT_TIMEOUT_SEC:.0f}s",
            flush=True,
        )


def stop_pool() -> None:
    """Shut the pool down, killing anything still running."""
    global _pool
    pool, _pool = _pool, None
    if pool is None:
        return
    _kill_workers(pool)
    pool.shutdown(wait=False, cancel_futures=True)
    print("[compute] pool stopped", flush=True)


def _kill_workers(pool: ProcessPoolExecutor) -> list[int]:
    """SIGKILL every worker of *pool* and return the pids killed.

    SIGKILL, not SIGTERM: a worker parked inside a native thread pool never runs a
    Python signal handler, so a polite signal is ignored.
    """
    killed: list[int] = []
    # ``_processes`` is private but it is the only handle on the worker pids, and
    # bounding a runaway native call requires killing the process that owns it.
    for pid in list(getattr(pool, "_processes", {}) or {}):
        with contextlib.suppress(OSError, ProcessLookupError):
            os.kill(pid, signal.SIGKILL)
            killed.append(pid)
    return killed


async def _rebuild_pool() -> None:
    global _pool
    pool, _pool = _pool, None
    if pool is not None:
        killed = _kill_workers(pool)
        pool.shutdown(wait=False, cancel_futures=True)
        print(f"[compute] pool rebuilt after timeout; killed pids={killed}", flush=True)
    start_pool()


async def run_in_compute(
    fn: Callable[..., _T],
    *args: Any,
    timeout: float | None = None,
) -> _T:
    """Run *fn* in a spawned worker and return its result.

    Args:
        fn: A module-level callable.  It and its arguments must be picklable —
            paths, dicts and dataclasses, never LazyFrames or DagsterInstances.
        args: Positional arguments for *fn*.
        timeout: Wall-clock budget in seconds; defaults to ``JUST_DNA_COMPUTE_TIMEOUT``.

    Raises:
        ComputeTimeout: The budget was exceeded.  The worker has been killed and the
            pool rebuilt, so the caller can retry with a cheaper query.
    """
    global _pool_lock
    if _pool_lock is None:
        _pool_lock = asyncio.Lock()
    if _pool is None:
        async with _pool_lock:
            start_pool()

    pool = _pool
    assert pool is not None  # start_pool() above guarantees this
    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(pool, fn, *args)
    budget = DEFAULT_TIMEOUT_SEC if timeout is None else timeout

    try:
        # shield: wait_for cancels its awaitable on timeout, but cancelling the wrapper
        # would not stop the child.  Kill the worker instead, below.
        return await asyncio.wait_for(asyncio.shield(future), timeout=budget)
    except (asyncio.TimeoutError, TimeoutError) as exc:
        # The shielded future outlives this call and will fail with BrokenProcessPool
        # once we kill its worker.  Consume that outcome so asyncio does not log an
        # "exception was never retrieved" traceback for something we caused on purpose.
        future.add_done_callback(lambda done: done.exception() if not done.cancelled() else None)
        async with _pool_lock:
            await _rebuild_pool()
        raise ComputeTimeout(
            f"{getattr(fn, '__name__', fn)} exceeded {budget:.0f}s and was killed"
        ) from exc
