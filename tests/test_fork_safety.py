"""Regression tests for the Polars-after-fork deadlock.

The bug: Polars' Rayon pool is created on the *first Polars operation*, not at import.
A ``fork()`` after that gives the child a pool with no worker threads, so its first
parallel call parks forever — GIL released, so Python signal handlers never run, no
traceback, SIGTERM ignored, SIGKILL only.  Both production server paths used to fork
after importing the app.

These tests pin the mechanism, not just the fix, so the fix cannot be quietly undone.
See ``docs/GRANIAN_POLARS_FORK_DEADLOCK.md``.

Each probe runs in its own interpreter, because ``set_start_method(force=True)`` and the
Rayon pool are both process-global. Fork probes use ``-c``; the spawn probe needs a real
script file, since spawn children re-import ``__main__`` and unpickle their target by
module path — a ``-c`` body has neither.
"""

from __future__ import annotations

import multiprocessing
import os
import subprocess
import sys
import textwrap

import pytest

# A child that inherits a poisoned Rayon pool never returns, so every probe is bounded
# by the parent and the worker is SIGKILLed.  Generous enough for a cold import.
PROBE_BUDGET_SEC = 20

_FORK_PROBE = """
import os, sys, time
import polars as pl

if {warm_parent}:
    pl.DataFrame({{"a": [3, 1, 2]}}).lazy().sort("a").collect()   # materialize Rayon

pid = os.fork()
if pid == 0:
    pl.DataFrame({{"a": list(range(200_000))[::-1]}}).lazy().sort("a").slice(0, 3).collect()
    os._exit(0)

deadline = time.time() + 6
while time.time() < deadline:
    if os.waitpid(pid, os.WNOHANG)[0]:
        print("CHILD_OK")
        sys.exit(0)
    time.sleep(0.1)
os.kill(pid, 9)
print("CHILD_HUNG")
"""


def _run_probe(*, warm_parent: bool, env: dict[str, str] | None = None) -> str:
    """Run the fork probe in a fresh interpreter and return CHILD_OK / CHILD_HUNG."""
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(_FORK_PROBE.format(warm_parent=warm_parent))],
        capture_output=True,
        text=True,
        timeout=PROBE_BUDGET_SEC,
        env={**os.environ, **(env or {})},
        check=False,
    )
    for marker in ("CHILD_OK", "CHILD_HUNG"):
        if marker in result.stdout:
            return marker
    raise AssertionError(f"probe produced no verdict:\nstdout={result.stdout}\nstderr={result.stderr}")


def test_fork_after_polars_op_deadlocks_the_child():
    """The bug itself: a warm Rayon pool plus fork() wedges the child.

    If this ever starts returning CHILD_OK, upstream Polars became fork-safe and the
    workarounds in webui.forksafety can be reconsidered — but do not assume it silently.
    """
    assert _run_probe(warm_parent=True) == "CHILD_HUNG"


def test_fork_before_any_polars_op_is_safe():
    """Importing polars is not enough to poison a fork; using it is.

    This is why the hazard is latent: an app can fork safely for months and detonate the
    day someone adds a Polars call to an import-time code path.
    """
    assert _run_probe(warm_parent=False) == "CHILD_OK"


@pytest.mark.parametrize("max_threads", ["1", "4", "16"])
def test_polars_max_threads_does_not_avoid_the_deadlock(max_threads):
    """Capping Polars threads does **not** fix this, including ``POLARS_MAX_THREADS=1``.

    Worth pinning because it is the intuitive mitigation and it is wrong: even a
    single-worker Rayon pool has that one worker thread lost to the fork, so the child
    still parks.  Anyone reaching for this knob is not protected; only spawn is.
    """
    assert _run_probe(warm_parent=True, env={"POLARS_MAX_THREADS": max_threads}) == "CHILD_HUNG"


# Written to a file rather than passed with ``-c``: spawn children re-import ``__main__``
# and unpickle the callable by module path, so a ``-c`` body has neither an importable
# ``__main__`` nor a resolvable target — the pool would hang.  Exactly the constraint
# ``uv run serve`` satisfies via its ``__main__``-guarded console script.
_COMPUTE_POOL_PROBE = '''
import asyncio, sys
from pathlib import Path


def main():
    import polars as pl
    from webui.compute.pool import run_in_compute, stop_pool
    from webui.compute.tasks import GridSource, read_page

    out = Path(sys.argv[1])
    pl.DataFrame({"a": list(range(50_000))[::-1]}).write_parquet(out)

    # Warm Rayon in the parent: the exact state that wedges a forked child.
    pl.DataFrame({"a": [3, 1, 2]}).lazy().sort("a").collect()

    async def run():
        page = await run_in_compute(
            read_page, GridSource(reader="scan_file", path=str(out)), {}, 0, 3, True, timeout=120
        )
        print("POOL_RESULT", page.row_count, [r["a"] for r in page.rows])
        stop_pool()

    asyncio.run(run())


if __name__ == "__main__":
    main()
'''


def test_compute_pool_works_with_a_warm_parent_rayon_pool(tmp_path):
    """The fix, on the real compute tier: spawned workers are immune to the parent's pool.

    Same parent state that wedges a forked child (``test_fork_after_polars_op_...``), but
    the query runs and returns.  This is the property the whole compute tier rests on.
    """
    script = tmp_path / "probe_compute_pool.py"
    script.write_text(textwrap.dedent(_COMPUTE_POOL_PROBE))

    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path / "data.parquet")],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert "POOL_RESULT 50000 [49999, 49998, 49997]" in result.stdout, (
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )


def test_guards_pin_spawn_and_granian():
    """``serve()``'s preamble must leave spawn as the start method and Granian pinned.

    Run in a subprocess because ``set_start_method(force=True)`` is process-global.
    """
    probe = """
    import multiprocessing, os
    from webui.forksafety import apply_process_model_guards
    guards = apply_process_model_guards()
    print("METHOD", multiprocessing.get_start_method())
    print("GRANIAN", os.environ.get("REFLEX_USE_GRANIAN"))
    print("REPORTED", guards["mp_start_method"])
    """
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(probe)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert "METHOD spawn" in result.stdout, result.stdout + result.stderr
    assert "GRANIAN true" in result.stdout, result.stdout + result.stderr
    assert "REPORTED spawn" in result.stdout, result.stdout + result.stderr


def test_compute_pool_never_uses_a_fork_context():
    """The compute pool must be spawn-based; a fork context would inherit the poison."""
    from webui.compute import pool

    source = (pool._new_pool.__doc__ or "") + str(pool._new_pool.__code__.co_consts)
    assert "spawn" in source, "compute pool must request a spawn context explicitly"

    created = pool._new_pool()
    try:
        assert created._mp_context.get_start_method() == "spawn"
    finally:
        created.shutdown(wait=False, cancel_futures=True)


def test_live_native_pools_detects_rayon():
    """The fork tripwire's detector must actually see Rayon workers appear."""
    probe = """
    from webui.forksafety import live_native_pools
    print("BEFORE", live_native_pools())
    import polars as pl
    pl.DataFrame({"a": [3, 1, 2]}).lazy().sort("a").collect()
    print("AFTER", live_native_pools())
    """
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(probe)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    lines = {line.split(" ", 1)[0]: line for line in result.stdout.splitlines() if " " in line}
    assert "rayon" not in lines.get("BEFORE", ""), lines.get("BEFORE")
    assert "rayon" in lines.get("AFTER", ""), lines.get("AFTER", "") + result.stderr


@pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="thread enumeration reads /proc"
)
def test_fork_tripwire_warns_in_the_child():
    """A fork with live native pools must produce the loud banner, not silence."""
    probe = """
    import os, time
    from webui.forksafety import install_fork_tripwire
    import polars as pl
    install_fork_tripwire()
    pl.DataFrame({"a": [3, 1, 2]}).lazy().sort("a").collect()
    pid = os.fork()
    if pid == 0:
        time.sleep(0.3)
        os._exit(0)
    os.waitpid(pid, 0)
    """
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(probe)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    combined = result.stdout + result.stderr
    assert "FATAL RISK" in combined, combined
    assert "polars/rayon" in combined, combined


def test_default_warning_filters_hide_the_fork_deprecation():
    """Documents *why* this shipped unnoticed, and that unmuting works.

    CPython warns on a multi-threaded fork, but the default filters only surface
    DeprecationWarning from ``__main__``; the fork happens inside multiprocessing or
    gunicorn, so the blanket ignore swallows it.
    """
    import warnings

    from webui.forksafety import unmute_fork_warning

    defaults = [f for f in warnings.filters if f[2] is DeprecationWarning]
    assert any(
        action == "ignore" and module in (None, "")
        for action, _msg, _cat, module, _line in defaults
    ), f"expected a blanket DeprecationWarning ignore in the defaults, got {defaults}"

    with warnings.catch_warnings():
        warnings.resetwarnings()
        unmute_fork_warning()
        assert any(
            action == "always" and getattr(msg, "pattern", "") and "fork" in msg.pattern
            for action, msg, _cat, _mod, _line in warnings.filters
        ), warnings.filters


def test_multiprocessing_default_on_linux_is_the_unsafe_one():
    """Sanity: the platform default really is ``fork`` here, so pinning spawn matters."""
    if sys.platform.startswith("linux"):
        assert multiprocessing.get_all_start_methods()[0] == "fork"
