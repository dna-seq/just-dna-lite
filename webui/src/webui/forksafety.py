"""Process-model guards that keep native thread pools out of forked children.

Polars' Rayon pool, polars-bio's Tokio runtime and DuckDB's background threads are
all created lazily on *first use* and none of them survive ``fork()``.  The child
inherits the pool's latches and mutexes but none of its worker threads, so the
first parallel operation parks forever waiting on a worker that does not exist.
It parks with the GIL released, so Python-level signal handlers never run: the
process stays alive, keeps its listening socket, answers nothing, produces no
traceback, and ignores SIGTERM.  Only SIGKILL clears it.

Reproduction, one interpreter, repeated forks:

===================================================== ==========================
 sequence                                              child ``sort()``
===================================================== ==========================
 ``import polars`` -> fork                             ok
 ``import polars`` -> parent Polars op -> fork         hangs, needs SIGKILL
 ``POLARS_MAX_THREADS=1`` -> parent op -> fork         hangs (the cap does not help)
 spawn instead of fork, warm parent pool               ok
===================================================== ==========================

Both production server paths used to fork after importing the app:
``gunicorn --preload`` (chosen when uvicorn+gunicorn are importable) and Granian,
whose ``MPServer`` forks via ``multiprocessing`` and which Reflex starts *after*
``_compile_app()`` has already run in the same process.

See ``docs/GRANIAN_POLARS_FORK_DEADLOCK.md``.
"""

from __future__ import annotations

import multiprocessing
import os
import re
import sys
import warnings
from pathlib import Path

# Rayon worker threads polars spawns on first use are named ``polars-<n>``.  The
# single ``polars-ooc-clea`` thread appears at import time and is not a signal.
_RAYON_THREAD_RE = re.compile(r"^polars-\d+$")
_TOKIO_THREAD_NAME = "tokio-rt-worker"

_IS_LINUX = sys.platform.startswith("linux")

# Set by the ``before`` fork hook so the ``after_in_child`` hook can report what
# the parent was holding at the moment it forked.
_pools_live_at_fork: tuple[str, ...] = ()


def native_thread_names() -> list[str]:
    """Return this process's OS thread names, or ``[]`` where unavailable.

    Reads ``/proc/self/task/*/comm``.  Python's ``threading`` module cannot see
    these — Rayon and Tokio threads are created by Rust and never registered
    with the interpreter — which is precisely why the hazard is invisible.
    """
    if not _IS_LINUX:
        return []
    names: list[str] = []
    for tid in os.listdir("/proc/self/task"):
        try:
            names.append(Path(f"/proc/self/task/{tid}/comm").read_text().strip())
        except OSError:
            # Thread exited between listdir and read; nothing to report.
            continue
    return names


def live_native_pools() -> tuple[str, ...]:
    """Return names of fork-hostile native thread pools live in this process.

    An empty tuple means forking is currently safe as far as we can tell.  On
    platforms without ``/proc`` we fall back to "is polars imported at all",
    which over-reports rather than staying silent.
    """
    names = native_thread_names()
    if not names:
        return ("polars (imported; thread enumeration unavailable)",) if "polars" in sys.modules else ()

    pools: list[str] = []
    rayon = sum(1 for name in names if _RAYON_THREAD_RE.match(name))
    if rayon:
        pools.append(f"polars/rayon ({rayon} workers)")
    tokio = sum(1 for name in names if name == _TOKIO_THREAD_NAME)
    if tokio:
        pools.append(f"tokio ({tokio} workers)")
    return tuple(pools)


def _before_fork() -> None:
    global _pools_live_at_fork
    _pools_live_at_fork = live_native_pools()


def _after_fork_in_child() -> None:
    """Write a loud banner when we were forked while native pools were live.

    Runs in the freshly forked child.  Uses ``os.write`` on fd 2 rather than
    ``print``/``logging`` because the child's interpreter state right after fork
    is not somewhere to be re-entering buffered I/O or lock-taking code.
    """
    if not _pools_live_at_fork:
        return
    pools = ", ".join(_pools_live_at_fork)
    banner = (
        "\n"
        "================================================================\n"
        "FATAL RISK: this process was fork()ed while native thread pools\n"
        f"were live in the parent: {pools}\n"
        "Those pools have no worker threads here. The next parallel Polars\n"
        "or polars-bio call will park forever, ignore SIGTERM, and produce\n"
        "no traceback. Use a 'spawn' start method instead.\n"
        "See docs/GRANIAN_POLARS_FORK_DEADLOCK.md\n"
        "================================================================\n"
    )
    try:
        os.write(2, banner.encode())
    except OSError:
        pass


def install_fork_tripwire() -> None:
    """Register fork hooks that report a fork-after-native-init as it happens."""
    os.register_at_fork(before=_before_fork, after_in_child=_after_fork_in_child)


def unmute_fork_warning() -> None:
    """Make CPython's own multi-threaded-fork DeprecationWarning visible.

    ``os.fork()`` does warn, but the default filters are
    ``default::DeprecationWarning:__main__`` followed by
    ``ignore::DeprecationWarning``.  The fork happens inside
    ``multiprocessing/popen_fork.py`` or ``gunicorn/arbiter.py``, neither of
    which is ``__main__``, so the warning was silently dropped.
    """
    warnings.filterwarnings("always", category=DeprecationWarning, message=".*fork.*")


def enforce_spawn_start_method() -> str:
    """Force ``spawn`` for every ``multiprocessing`` child and return the method.

    Granian's worker supervisor honours ``multiprocessing.get_start_method()``
    (``granian/server/mp.py``) and already enables connection pickling for the
    socket handoff, so spawn is a supported mode there.  Spawned children are
    fresh interpreters that build their own Rayon/Tokio pools, which also means
    our own compute pool must never use a fork context.
    """
    multiprocessing.set_start_method("spawn", force=True)
    return multiprocessing.get_start_method()


def pin_asgi_server() -> None:
    """Pin Granian as the production ASGI server.

    Reflex picks its prod server with ``should_use_granian()``, a
    ``find_spec`` heuristic: if both ``uvicorn`` and ``gunicorn`` are importable
    it silently prefers ``gunicorn --preload``, which forks after importing the
    app.  Both packages arrive transitively here, so the choice would otherwise
    flip with unrelated dependency changes.  Pin it explicitly.
    """
    os.environ.setdefault("REFLEX_USE_GRANIAN", "true")


def apply_process_model_guards() -> dict[str, str]:
    """Install every guard.  Call before importing reflex, return a log summary."""
    pin_asgi_server()
    unmute_fork_warning()
    install_fork_tripwire()
    start_method = enforce_spawn_start_method()
    return {
        "asgi_server": "granian (pinned)",
        "mp_start_method": start_method,
        "native_pools_live": ", ".join(live_native_pools()) or "none",
    }
