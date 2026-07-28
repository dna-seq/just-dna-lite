"""External liveness watchdog for ``uv run serve``.

A wedged ASGI worker is not detectable from inside itself.  When a thread parks in a
native thread pool — Polars' Rayon, polars-bio's Tokio — it holds no GIL and runs no
Python, so signal handlers, timers and self-checks never fire.  The process stays
alive, keeps its listening socket, answers nothing, logs nothing, and ignores SIGTERM.
An outside observer with the ability to SIGKILL is the only thing that helps.

This is a backstop, not the fix.  The fix is not forking a warm interpreter
(``webui.forksafety``) and not running heavy work in the ASGI process
(``webui.compute``).  This exists for the wedge we have not thought of yet.

Liveness is judged by *any* HTTP response, including a 404 or a 500: producing a
response at all proves the worker's event loop is still executing handlers, which is
exactly the property under test.  Only a connection failure or a timeout counts as a
failure, so the probe cannot be fooled by route changes or by an unhealthy dependency.

Env knobs (all optional):

===============================  =======  ======================================
 ``SERVE_HEALTH_WATCHDOG``        ``1``    ``0`` disables; use when debugging a hang
 ``SERVE_HEALTH_TIMEOUT``         ``5``    per-probe HTTP timeout, seconds
 ``SERVE_HEALTH_INTERVAL``        ``5``    seconds between probes once healthy
 ``SERVE_HEALTH_FAIL_LIMIT``      ``2``    consecutive failures before killing
 ``SERVE_HEALTH_STARTUP_GRACE``   ``600``  max seconds to wait for the first response
===============================  =======  ======================================
"""

from __future__ import annotations

import os
import sys
import time
import urllib.error
import urllib.request

PROBE_PATH = "/ping"


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    return float(raw) if raw else default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    return int(raw) if raw else default


def _probe(url: str, timeout: float) -> bool:
    """Return whether the server produced any HTTP response at all."""
    try:
        with urllib.request.urlopen(url, timeout=timeout):  # noqa: S310 - fixed localhost URL
            return True
    except urllib.error.HTTPError:
        # A status code is still a response: the event loop ran our request.
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _kill_tree(pid: int) -> list[int]:
    """SIGKILL *pid* and every descendant.  Returns the pids killed.

    A process tree rather than a process group: ``serve`` deliberately stays in the
    shell's foreground process group so Ctrl+C keeps working, which rules out
    ``killpg``.  SIGKILL rather than SIGTERM because the thread we are trying to stop
    cannot run a signal handler.
    """
    import psutil

    killed: list[int] = []
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return killed

    victims = parent.children(recursive=True) + [parent]
    for victim in victims:
        try:
            victim.kill()
            killed.append(victim.pid)
        except psutil.Error:
            continue
    return killed


def main() -> int:
    """Poll the server until it stops responding, then kill its process tree."""
    if os.getenv("SERVE_HEALTH_WATCHDOG", "1").strip() == "0":
        return 0

    try:
        serve_pid = int(os.environ["SERVE_WATCHDOG_PID"])
        url = os.environ["SERVE_WATCHDOG_URL"]
    except (KeyError, ValueError):
        print("[serve-watchdog] SERVE_WATCHDOG_PID/URL not set; not watching", file=sys.stderr, flush=True)
        return 2

    timeout = _env_float("SERVE_HEALTH_TIMEOUT", 5.0)
    interval = _env_float("SERVE_HEALTH_INTERVAL", 5.0)
    fail_limit = _env_int("SERVE_HEALTH_FAIL_LIMIT", 2)
    startup_grace = _env_float("SERVE_HEALTH_STARTUP_GRACE", 600.0)

    import psutil

    def server_gone() -> bool:
        return not psutil.pid_exists(serve_pid)

    # Startup: a production build compiles the frontend first, which can take minutes.
    deadline = time.time() + startup_grace
    while not _probe(url, timeout):
        if server_gone():
            return 0
        if time.time() > deadline:
            print(
                f"[serve-watchdog] no response from {url} within "
                f"{startup_grace:.0f}s startup grace; giving up watching",
                file=sys.stderr,
                flush=True,
            )
            return 3
        time.sleep(2.0)

    print(f"[serve-watchdog] health OK ({url}); watching pid {serve_pid}", flush=True)

    failures = 0
    while True:
        time.sleep(interval)
        if server_gone():
            return 0
        if _probe(url, timeout):
            failures = 0
            continue

        failures += 1
        print(
            f"[serve-watchdog] probe failed ({failures}/{fail_limit}) for {url}",
            file=sys.stderr,
            flush=True,
        )
        if failures < fail_limit:
            continue

        killed = _kill_tree(serve_pid)
        print(
            "\n"
            "================================================================\n"
            "FATAL: uv run serve became unresponsive\n"
            f"{url} stopped answering for {failures} consecutive probes\n"
            f"({failures * interval:.0f}s). The worker is most likely parked in a\n"
            "native thread pool, which ignores SIGTERM, so it was SIGKILLed.\n"
            f"killed pids: {killed}\n"
            "See docs/GRANIAN_POLARS_FORK_DEADLOCK.md\n"
            "================================================================\n",
            file=sys.stderr,
            flush=True,
        )
        return 137


if __name__ == "__main__":
    sys.exit(main())
