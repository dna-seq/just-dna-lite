"""Ctrl+C has to be *seen* by the launcher before it can kill anything.

``tests/test_process_shutdown.py`` covers what shutdown does once it starts: snapshot
the tree, ask ``dg`` to drain its IPC pipe, SIGKILL the deaf daemon. These tests cover
the half before that — whether the signal ever reaches the launcher's wait at all.

The hazard: ``import polars`` — dragged in by the pipelines imports at the top of
``just_dna_lite.cli`` — re-installs the process-wide SIGINT handler through
``sigaction`` with ``SA_RESTART``. The kernel then restarts the interrupted
``waitpid`` instead of returning ``EINTR``, CPython never reaches the bytecode loop
where Python-level handlers run, and ``KeyboardInterrupt`` is not raised until the
child exits on its own. Since every child is started with ``start_new_session=True``,
the terminal's SIGINT does not reach them either: Ctrl+C did nothing at all,
indefinitely, with the whole stack still up.

``install_launcher_signal_handlers`` undoes it as a side effect — CPython registers
with ``sa_flags = 0``, which clears ``SA_RESTART`` — so it must run *before* the
launcher blocks in ``wait()``, and a launcher that goes back to a bare wait would be
silently uninterruptible again. Each probe runs in its own interpreter: signal
dispositions are process-global and the hazard only exists once polars is imported.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

# Cold-importing the pipelines stack (polars, duckdb, dagster) dominates every probe.
PROBE_BUDGET_SEC = 180

# Importing the launcher is what pulls polars — and therefore the SA_RESTART handler —
# into the probe process. That is the state the real ``uv run start`` waits in.
_PREAMBLE = """
import os, signal, subprocess, sys, threading, time
from just_dna_lite import cli
from just_dna_lite.process import install_launcher_signal_handlers

def signal_after(delay, sig=signal.SIGINT):
    threading.Timer(delay, lambda: os.kill(os.getpid(), sig)).start()

def spawn_child():
    return subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"], start_new_session=True
    )
"""


def _run_probe(tmp_path: Path, body: str, name: str) -> str:
    """Run a probe in a fresh interpreter and return its stdout."""
    script = tmp_path / f"probe_{name}.py"
    script.write_text(textwrap.dedent(_PREAMBLE) + textwrap.dedent(body))
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        timeout=PROBE_BUDGET_SEC,
        check=False,
    )
    assert "VERDICT" in result.stdout, f"stdout={result.stdout}\nstderr={result.stderr}"
    return result.stdout


def test_polars_import_installs_a_restarting_sigint_handler(tmp_path):
    """The mechanism: polars takes SIGINT and sets ``SA_RESTART`` on it.

    If this ever fails, upstream stopped doing it — good news, but not a reason to
    stop claiming the signals: any dependency can install such a handler at import
    time without saying so.
    """
    probe = """
    import ctypes, signal

    class Sigaction(ctypes.Structure):
        _fields_ = [("handler", ctypes.c_void_p), ("mask", ctypes.c_ubyte * 128),
                    ("flags", ctypes.c_int), ("restorer", ctypes.c_void_p)]

    SA_RESTART = 0x10000000
    libc = ctypes.CDLL(None, use_errno=True)

    def restarting():
        act = Sigaction()
        libc.sigaction(signal.SIGINT, None, ctypes.byref(act))
        return bool(act.flags & SA_RESTART)

    before = restarting()
    import polars  # noqa: F401
    print("VERDICT", before, restarting())
    """
    # Imports polars itself, so it runs without the launcher preamble.
    script = tmp_path / "probe_sa_restart.py"
    script.write_text(textwrap.dedent(probe))
    out = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, timeout=PROBE_BUDGET_SEC, check=False,
    )
    assert "VERDICT False True" in out.stdout, out.stdout + out.stderr


def test_wait_without_claiming_the_signals_sleeps_through_ctrl_c(tmp_path):
    """The bug, reproduced: an unclaimed SIGINT never interrupts the wait.

    Timing is the discriminator, not the exception. The signal arrives at 0.5s and a
    watchdog kills the child at 3s; the KeyboardInterrupt does eventually surface,
    because polars' handler chains to CPython's — but only once ``waitpid`` returns of
    its own accord, which in the real launcher means when Dagster exits by itself.
    """
    probe = """
    child = spawn_child()
    signal_after(0.5)
    threading.Timer(3.0, child.kill).start()

    started = time.monotonic()
    try:
        child.wait()
        verdict = "RETURNED"
    except KeyboardInterrupt:
        verdict = "KEYBOARD_INTERRUPT"
    print("VERDICT", verdict, round(time.monotonic() - started, 2))
    """
    out = _run_probe(tmp_path, probe, "unclaimed_wait")
    _verdict, elapsed = out.split("VERDICT ")[1].split()
    assert float(elapsed) >= 2.5, (
        f"the wait unblocked at {elapsed}s, before the watchdog killed the child at 3s — "
        f"SA_RESTART is no longer in play and this test is now vacuous: {out}"
    )


def test_launcher_handlers_make_the_wait_interruptible_again(tmp_path):
    """The fix: the same SIGINT, same process state, once the launcher claims it.

    This is the property both ``start`` and ``dagster`` rest on — they install the
    handlers and then block in ``proc.wait()``, so the wait must actually break.
    """
    probe = """
    child = spawn_child()

    def _first(_signum, _frame):
        raise KeyboardInterrupt

    def _force(_signum, _frame):
        raise SystemExit(1)

    install_launcher_signal_handlers(_first, _force)
    signal_after(0.5)
    threading.Timer(5.0, child.kill).start()

    started = time.monotonic()
    try:
        child.wait()
        verdict = "RETURNED"
    except KeyboardInterrupt:
        verdict = "KEYBOARD_INTERRUPT"
    elapsed = time.monotonic() - started
    child.kill()
    print("VERDICT", verdict, round(elapsed, 2))
    """
    out = _run_probe(tmp_path, probe, "claimed_wait")
    verdict, elapsed = out.split("VERDICT ")[1].split()
    assert verdict == "KEYBOARD_INTERRUPT", out
    assert float(elapsed) < 2.0, f"took {elapsed}s to notice the signal: {out}"


def test_first_and_second_signals_route_to_graceful_then_force(tmp_path):
    """One Ctrl+C shuts down; the next one force-kills. SIGTERM enters the same path.

    ``kill <launcher>`` must tear the children down too: they live in their own
    sessions, so a launcher that dies without running its shutdown orphans Dagster and
    the web UI, which then keep the ports.
    """
    probe = """
    seen = []
    install_launcher_signal_handlers(
        lambda _s, _f: seen.append("first"),
        lambda _s, _f: seen.append("second"),
    )
    os.kill(os.getpid(), signal.SIGINT)
    time.sleep(0.3)
    os.kill(os.getpid(), signal.SIGTERM)
    time.sleep(0.3)
    print("VERDICT", ",".join(seen))
    """
    out = _run_probe(tmp_path, probe, "escalation")
    assert "VERDICT first,second" in out, out


def test_every_blocking_wait_claims_the_signals_first():
    """Whoever blocks on a child must install the handlers rather than trust KeyboardInterrupt.

    A bare ``proc.wait()`` in this process is uninterruptible (see the tests above), so
    dropping this call would silently restore the original bug. ``start_all`` waits
    inline; ``start_dagster`` waits through ``_run_managed_foreground``.
    """
    from just_dna_lite import cli

    for waiter in ("start_all", "_run_managed_foreground"):
        names = getattr(cli, waiter).__code__.co_names
        assert "install_launcher_signal_handlers" in names, (
            f"{waiter} must claim SIGINT/SIGTERM before it blocks on a child"
        )
    assert "_run_managed_foreground" in cli.start_dagster.__code__.co_names, (
        "start_dagster must keep waiting through _run_managed_foreground"
    )
