"""Process-tree shutdown for the stack launcher.

Dagster's daemon is the process that Ctrl+C has to kill and the one it most
often fails to.  ``dg dev`` starts ``dagster._daemon`` with ``capture_interrupts()``,
which swallows SIGINT and SIGTERM and only exits when ``dg`` writes to a shutdown
pipe.  Our launchers also use ``start_new_session=True``, so the daemon is not in
the shell's foreground process group: Ctrl+C and Ctrl+Z hit the launcher, not
Dagster.  If the launcher then SIGTERMs the session leader and only waits for
that one PID, ``dg`` can die while the daemon keeps heartbeating.

Snapshot every descendant *before* signalling, ask the leader to drain the pipe,
then SIGKILL whatever is still alive — including leftovers that match this
``DAGSTER_HOME``.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Optional

import psutil

SignalHandler = Callable[[int, object], None]

_IS_WINDOWS = sys.platform == "win32"

DAGSTER_CMDLINE_MARKERS: tuple[str, ...] = (
    "dagster._daemon",
    "dagster_webserver",
    "dagster code-server",
    "dagster api grpc",
    "dg dev",
)

# ``dg`` waits up to 60s per child for a clean IPC shutdown.  Users treat that
# as "Ctrl+C does nothing".  Give it a short chance, then SIGKILL the tree.
DEFAULT_GRACE_SECONDS = 2.0


def snapshot_process_tree(pid: int) -> list[int]:
    """Return *pid* and every current descendant.  Empty if *pid* is already gone."""
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return []
    if not _pid_is_live(pid):
        return []
    children = proc.children(recursive=True)
    return [child.pid for child in children if _pid_is_live(child.pid)] + [pid]


def detached_popen_kwargs() -> dict[str, object]:
    """Kwargs so a child is not in the launcher's console/job-control group.

    POSIX: a new session, so Ctrl+C lands on the launcher.  Windows has no
    ``start_new_session``; ``CREATE_NEW_PROCESS_GROUP`` is the equivalent and
    is required for ``CTRL_BREAK_EVENT`` to reach ``dg``.
    """
    if _IS_WINDOWS:
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def signal_pids(pids: Iterable[int], sig: int) -> None:
    """Send *sig* to each pid, ignoring processes that have already exited."""
    my_pid = os.getpid()
    for pid in pids:
        if pid == my_pid:
            continue
        try:
            os.kill(pid, sig)
        except (ProcessLookupError, PermissionError, OSError):
            continue


def force_kill_pids(pids: Iterable[int]) -> None:
    """Uncatchable kill: SIGKILL on POSIX, TerminateProcess on Windows."""
    my_pid = os.getpid()
    for pid in pids:
        if pid == my_pid:
            continue
        try:
            psutil.Process(pid).kill()
        except (psutil.Error, ProcessLookupError, OSError):
            continue


def find_dagster_instance_pids(dagster_home: Path) -> list[int]:
    """PIDs whose command line is a Dagster service for this instance."""
    home = str(dagster_home.resolve())
    my_pid = os.getpid()
    found: list[int] = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        pid = proc.info["pid"]
        if pid == my_pid:
            continue
        if not _pid_is_live(pid):
            continue
        cmdline = " ".join(proc.info.get("cmdline") or [])
        if not any(marker in cmdline for marker in DAGSTER_CMDLINE_MARKERS):
            continue
        if home in cmdline or _process_dagster_home(proc) == home:
            found.append(pid)
    return found


def _process_dagster_home(proc: psutil.Process) -> str:
    """Resolved DAGSTER_HOME from the process environment, or empty."""
    try:
        raw = proc.environ().get("DAGSTER_HOME", "")
    except (psutil.Error, OSError):
        return ""
    if not raw:
        return ""
    return str(Path(raw).resolve())


def reap_dagster_instance(dagster_home: Path) -> list[int]:
    """SIGKILL leftover Dagster services for *dagster_home*.  Returns killed pids."""
    pids = find_dagster_instance_pids(dagster_home)
    if not pids:
        return []
    force_kill_pids(pids)
    _wait_pids_exit(pids, timeout=2.0)
    return [pid for pid in pids if not _pid_is_live(pid)]


def find_webui_leftover_pids(
    workspace_root: Path,
    *,
    exclude_pids: Iterable[int] = (),
) -> list[int]:
    """PIDs for a leftover Reflex UI belonging to this workspace.

    Matches ``uv run --package webui run``, the Reflex ``.venv/bin/run`` backend,
    and ``react-router dev`` under ``webui/.web``.  Port cleanup is off by
    default because 8000/8001 may belong to unrelated tools; this targets only
    this repo's UI tree.
    """
    root = workspace_root.resolve()
    excluded = set(exclude_pids)
    for pid in exclude_pids:
        excluded.update(snapshot_process_tree(pid))
    my_pid = os.getpid()
    excluded.add(my_pid)
    matches: list[int] = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        pid = proc.info["pid"]
        if pid in excluded or not _pid_is_live(pid):
            continue
        cmdline = proc.info.get("cmdline") or []
        if not _is_workspace_webui_process(proc, cmdline, root):
            continue
        matches.append(pid)
    tree = [child for pid in matches for child in snapshot_process_tree(pid)]
    return [pid for pid in _unique(tree) if pid not in excluded]


def reap_webui_leftovers(
    workspace_root: Path,
    *,
    exclude_pids: Iterable[int] = (),
) -> list[int]:
    """SIGKILL leftover Reflex UI processes for this workspace.  Returns killed pids."""
    pids = find_webui_leftover_pids(workspace_root, exclude_pids=exclude_pids)
    if not pids:
        return []
    force_kill_pids(pids)
    _wait_pids_exit(pids, timeout=2.0)
    return [pid for pid in pids if not _pid_is_live(pid)]


def _is_workspace_webui_process(
    proc: psutil.Process,
    cmdline: list[str],
    workspace_root: Path,
) -> bool:
    """True when *proc* is this workspace's Reflex dev UI, not an unrelated listener."""
    joined = " ".join(cmdline)
    router = str(workspace_root / "webui" / ".web" / "node_modules" / ".bin" / "react-router")
    run_script = workspace_root / ".venv" / ("Scripts/run.exe" if _IS_WINDOWS else "bin/run")
    if router in joined or str(run_script) in joined:
        return True
    cwd = _process_cwd(proc)
    root_s = str(workspace_root)
    if cwd != root_s and not cwd.startswith(root_s + os.sep):
        return False
    return _is_uv_package_webui_run(cmdline)


def _is_uv_package_webui_run(cmdline: list[str]) -> bool:
    try:
        pkg_idx = cmdline.index("--package")
    except ValueError:
        return False
    if pkg_idx + 1 >= len(cmdline) or cmdline[pkg_idx + 1] != "webui":
        return False
    return "run" in cmdline[pkg_idx + 2 :]


def _process_cwd(proc: psutil.Process) -> str:
    try:
        return str(Path(proc.cwd()).resolve())
    except (psutil.Error, OSError):
        return ""


def shutdown_managed_processes(
    processes: list[subprocess.Popen],
    *,
    dagster_home: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
    grace_seconds: float = DEFAULT_GRACE_SECONDS,
    force: bool = False,
) -> None:
    """Stop launched children and leftovers that already belonged to this session.

    *force* skips the graceful SIGINT and SIGKILLs the snapshotted tree immediately
    (second Ctrl+C).

    A second ``uv run start`` is last-writer-wins: it reaps this instance on
    *startup*.  The dying instance must not then sweep processes created after
    shutdown began, or it SIGKILLs the new stack.  No pidfile: we snapshot live
    PIDs now and ignore any PID that was not in that set.
    """
    existing = {proc.pid for proc in psutil.process_iter()}
    roots = [proc.pid for proc in processes if proc.pid is not None]
    tree = _unique(pid for root in roots for pid in snapshot_process_tree(root))
    if dagster_home is not None:
        tree = _unique(
            [
                *tree,
                *[
                    pid
                    for pid in find_dagster_instance_pids(dagster_home)
                    if pid in existing
                ],
            ]
        )
    if workspace_root is not None:
        tree = _unique(
            [
                *tree,
                *[
                    pid
                    for pid in find_webui_leftover_pids(workspace_root)
                    if pid in existing
                ],
            ]
        )

    if not tree:
        return

    if not force:
        _interrupt_leaders(processes)
        _wait_pids_exit(tree, timeout=grace_seconds)

    force_kill_pids(tree)
    _reap_popens(processes)
    _wait_pids_exit(tree, timeout=2.0)

    if dagster_home is not None:
        leftovers = [
            pid
            for pid in find_dagster_instance_pids(dagster_home)
            if pid in existing
        ]
        if leftovers:
            force_kill_pids(leftovers)
            _wait_pids_exit(leftovers, timeout=2.0)
    if workspace_root is not None:
        ui_leftovers = [
            pid for pid in find_webui_leftover_pids(workspace_root) if pid in existing
        ]
        if ui_leftovers:
            force_kill_pids(ui_leftovers)
            _wait_pids_exit(ui_leftovers, timeout=2.0)


def install_launcher_signal_handlers(
    on_first: SignalHandler,
    on_second: SignalHandler,
) -> None:
    """Ctrl+C / SIGTERM start a graceful shutdown; a second signal force-kills.

    Ctrl+Z (SIGTSTP) is treated as the first shutdown signal.  The children live
    in their own session, so stopping only the launcher would orphan the daemon.
    ``uv run start`` is also in the foreground group and does not catch SIGTSTP,
    so we SIGCONT that group after ignoring further stops — otherwise ``uv`` stays
    stopped, cannot ``wait()`` on this Python process, and ``dg`` is left zombie.
    """
    state = {"started": False}

    def handler(signum: int, frame: object) -> None:
        if signum == getattr(signal, "SIGTSTP", None):
            _resume_foreground_group()
        if state["started"]:
            on_second(signum, frame)
            return
        state["started"] = True
        on_first(signum, frame)

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
    if hasattr(signal, "SIGTSTP"):
        signal.signal(signal.SIGTSTP, handler)


def _interrupt_leaders(processes: list[subprocess.Popen]) -> None:
    """Ask each session leader to shut down; do not signal the whole group.

    ``killpg(SIGTERM)`` also hits ``dagster._daemon``, whose ``capture_interrupts()``
    handler swallows it.  SIGINT on the leader (``dg``) is what runs the IPC
    shutdown pipe write.
    """
    for proc in processes:
        if proc.poll() is not None or proc.pid is None:
            continue
        try:
            if _IS_WINDOWS:
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.kill(proc.pid, signal.SIGINT)
        except (ProcessLookupError, OSError):
            continue


def _wait_pids_exit(pids: Iterable[int], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    remaining = set(pids)
    while remaining and time.monotonic() < deadline:
        remaining = {pid for pid in remaining if _pid_is_live(pid)}
        if remaining:
            time.sleep(0.05)


def _resume_foreground_group() -> None:
    """Keep ``uv`` from staying stopped after Ctrl+Z.

    SIGTSTP is delivered to the whole foreground group.  This Python process
    can catch it; ``uv`` cannot.  If ``uv`` stays in ``T``, it never reaps us
    and any ``dg`` child we already killed remains a zombie.
    """
    if not hasattr(signal, "SIGTSTP"):
        return
    signal.signal(signal.SIGTSTP, signal.SIG_IGN)
    try:
        os.killpg(os.getpgrp(), signal.SIGCONT)
    except OSError:
        return


def _reap_popens(processes: list[subprocess.Popen]) -> None:
    """Collect exit status for Popen objects we started.

    Only these PIDs.  ``waitpid(-1)`` would also reap Granian workers, uvicorn
    workers, and the compute ``ProcessPoolExecutor`` children that share the
    ``uv run serve`` process — the supervisor then sees ECHILD.
    """
    deadline = time.monotonic() + 2.0
    pending = list(processes)
    while pending and time.monotonic() < deadline:
        still: list[subprocess.Popen] = []
        for proc in pending:
            if proc.poll() is None:
                still.append(proc)
        pending = still
        if pending:
            time.sleep(0.05)


def _pid_is_live(pid: int) -> bool:
    """True when *pid* exists and is not a zombie waiting to be reaped."""
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return False
    try:
        return proc.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def _unique(pids: Iterable[int]) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for pid in pids:
        if pid in seen:
            continue
        seen.add(pid)
        ordered.append(pid)
    return ordered
