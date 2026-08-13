"""Shutdown must kill Dagster-like children that swallow SIGINT/SIGTERM.

The production bug: ``dg dev`` is started with ``start_new_session=True``, so
Ctrl+C hits the launcher, not Dagster.  The launcher then SIGTERMed the session
leader and waited only for that PID.  ``dagster._daemon`` installs
``capture_interrupts()``, which swallows SIGINT/SIGTERM, so it kept heartbeating
after ``dg`` had already exited.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil
import pytest

from just_dna_lite.process import (
    find_dagster_instance_pids,
    find_webui_leftover_pids,
    reap_dagster_instance,
    reap_webui_leftovers,
    shutdown_managed_processes,
    snapshot_process_tree,
)

_unix_only = pytest.mark.skipif(sys.platform == "win32", reason="Unix process-group shutdown")

def _is_live(pid: int) -> bool:
    try:
        return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False

_DEAF_CHILD = """
import signal
import time
signal.signal(signal.SIGINT, signal.SIG_IGN)
signal.signal(signal.SIGTERM, signal.SIG_IGN)
signal.signal(signal.SIGHUP, signal.SIG_IGN)
print("ready", flush=True)
while True:
    time.sleep(0.1)
"""

_LEADER = """
import subprocess
import sys
import time
child = subprocess.Popen(
    [sys.executable, "-c", sys.argv[1], *sys.argv[2:]],
    stdout=subprocess.PIPE,
    text=True,
)
assert child.stdout is not None
assert child.stdout.readline().strip() == "ready"
print(child.pid, flush=True)
time.sleep(120)
"""


def _spawn_leader_with_deaf_child(*child_args: str) -> tuple[subprocess.Popen[str], int]:
    """Start a session-leader whose child ignores SIGINT and SIGTERM."""
    leader = subprocess.Popen(
        [sys.executable, "-c", _LEADER, _DEAF_CHILD, *child_args],
        start_new_session=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert leader.stdout is not None
    line = leader.stdout.readline()
    child_pid = int(line.strip())
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if _is_live(child_pid) and _is_live(leader.pid):
            return leader, child_pid
        time.sleep(0.05)
    raise AssertionError(f"leader={leader.pid} child={child_pid} did not stay alive")


def _buggy_shutdown_leader_only(proc: subprocess.Popen) -> None:
    """The previous launcher shutdown: signal the group, wait for the leader PID."""
    pgid = os.getpgid(proc.pid)
    os.killpg(pgid, signal.SIGTERM)
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        os.killpg(pgid, signal.SIGKILL)
        proc.wait(timeout=1)


@_unix_only
def test_term_only_on_leader_leaves_interrupt_swallowing_child() -> None:
    """Demonstrate the bug: once the leader dies, the deaf child is never SIGKILLed."""
    leader, child_pid = _spawn_leader_with_deaf_child()
    try:
        _buggy_shutdown_leader_only(leader)
        time.sleep(0.3)
        assert leader.poll() is not None, "leader should have died on SIGTERM"
        assert _is_live(child_pid), "deaf child must still be alive under the old shutdown"
    finally:
        for pid in (child_pid, leader.pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        leader.wait(timeout=2)


@_unix_only
def test_shutdown_managed_processes_kills_interrupt_swallowing_child() -> None:
    leader, child_pid = _spawn_leader_with_deaf_child()
    try:
        shutdown_managed_processes([leader], grace_seconds=0.4)
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and (_is_live(child_pid) or _is_live(leader.pid)):
            time.sleep(0.05)
        assert not _is_live(leader.pid)
        assert not _is_live(child_pid)
        assert leader.returncode is not None
    finally:
        for pid in (child_pid, leader.pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        leader.wait(timeout=2)


@_unix_only
def test_reap_dagster_instance_kills_leftover_daemon_like_process(tmp_path: Path) -> None:
    dagster_home = tmp_path / "dagster"
    dagster_home.mkdir()
    leftover = subprocess.Popen(
        [
            sys.executable,
            "-c",
            _DEAF_CHILD,
            "dagster._daemon",
            f"--instance-ref=base_dir: {dagster_home.resolve()}",
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert leftover.stdout is not None
        assert leftover.stdout.readline().strip() == "ready"
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if leftover.pid in find_dagster_instance_pids(dagster_home):
                break
            time.sleep(0.05)
        else:
            raise AssertionError("leftover daemon-like process was not discovered")

        killed = reap_dagster_instance(dagster_home)
        assert leftover.pid in killed
        leftover.wait(timeout=2)
        assert leftover.poll() is not None
        assert leftover.pid not in find_dagster_instance_pids(dagster_home)

        env_leader = subprocess.Popen(
            [sys.executable, "-c", _DEAF_CHILD, "dg", "dev", "-f", "definitions.py"],
            env={**os.environ, "DAGSTER_HOME": str(dagster_home.resolve())},
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert env_leader.stdout is not None
            assert env_leader.stdout.readline().strip() == "ready"
            assert env_leader.pid in find_dagster_instance_pids(dagster_home)
            killed_leader = reap_dagster_instance(dagster_home)
            assert env_leader.pid in killed_leader
            env_leader.wait(timeout=2)
        finally:
            if env_leader.poll() is None:
                env_leader.kill()
                env_leader.wait(timeout=2)
    finally:
        if leftover.poll() is None:
            leftover.kill()
            leftover.wait(timeout=2)


def test_shutdown_reaps_a_simple_child_on_this_os() -> None:
    """Force-kill + wait must work without POSIX-only APIs (Windows included)."""
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        shutdown_managed_processes([proc], grace_seconds=0.2, force=True)
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=2)


def test_shutdown_does_not_kill_unrelated_children() -> None:
    """serve() owns Granian/compute workers; Dagster shutdown must not reap them."""
    sentinel = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    target = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        shutdown_managed_processes([target], grace_seconds=0.2, force=True)
        assert target.poll() is not None
        assert sentinel.poll() is None
    finally:
        for proc in (sentinel, target):
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=2)


@_unix_only
def test_snapshot_process_tree_includes_descendants() -> None:
    leader, child_pid = _spawn_leader_with_deaf_child()
    try:
        tree = snapshot_process_tree(leader.pid)
        assert leader.pid in tree
        assert child_pid in tree
    finally:
        shutdown_managed_processes([leader], grace_seconds=0.2, force=True)


def test_reap_webui_leftovers_kills_this_workspace_ui_only(tmp_path: Path) -> None:
    """Stale Reflex UIs must be reaped by workspace path, not by killing port 8000."""
    workspace = tmp_path / "just-dna-lite"
    other = tmp_path / "other-app"
    router = workspace / "webui" / ".web" / "node_modules" / ".bin" / "react-router"
    router.parent.mkdir(parents=True)
    other.mkdir()

    leftover = subprocess.Popen(
        [sys.executable, "-c", _DEAF_CHILD, str(router), "dev", "--host"],
        cwd=workspace,
        stdout=subprocess.PIPE,
        text=True,
    )
    uv_style = subprocess.Popen(
        [sys.executable, "-c", _DEAF_CHILD, "uv", "run", "--package", "webui", "run"],
        cwd=workspace,
        stdout=subprocess.PIPE,
        text=True,
    )
    foreign = subprocess.Popen(
        [
            sys.executable,
            "-c",
            _DEAF_CHILD,
            str(other / "webui" / ".web" / "node_modules" / ".bin" / "react-router"),
            "dev",
            "--host",
        ],
        cwd=other,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        for proc in (leftover, uv_style, foreign):
            assert proc.stdout is not None
            assert proc.stdout.readline().strip() == "ready"

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            found = set(find_webui_leftover_pids(workspace))
            if leftover.pid in found and uv_style.pid in found:
                break
            time.sleep(0.05)
        else:
            raise AssertionError(
                f"workspace UI leftovers not discovered: {find_webui_leftover_pids(workspace)}"
            )

        assert foreign.pid not in find_webui_leftover_pids(workspace)

        kept = subprocess.Popen(
            [sys.executable, "-c", _DEAF_CHILD, str(router), "dev", "--host"],
            cwd=workspace,
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert kept.stdout is not None
            assert kept.stdout.readline().strip() == "ready"
            assert kept.pid in find_webui_leftover_pids(workspace)
            assert kept.pid not in find_webui_leftover_pids(
                workspace, exclude_pids=[kept.pid]
            )

            killed = reap_webui_leftovers(workspace, exclude_pids=[kept.pid])
            assert leftover.pid in killed
            assert uv_style.pid in killed
            leftover.wait(timeout=2)
            uv_style.wait(timeout=2)
            assert _is_live(kept.pid)
            assert _is_live(foreign.pid)
        finally:
            if kept.poll() is None:
                kept.kill()
                kept.wait(timeout=2)
    finally:
        for proc in (leftover, uv_style, foreign):
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=2)


@_unix_only
def test_shutdown_does_not_kill_webui_started_during_grace(tmp_path: Path) -> None:
    """Dying start must not SIGKILL a takeover start spawned during the grace wait."""
    workspace = tmp_path / "just-dna-lite"
    router = workspace / "webui" / ".web" / "node_modules" / ".bin" / "react-router"
    router.parent.mkdir(parents=True)

    ours = subprocess.Popen(
        [sys.executable, "-c", _DEAF_CHILD, str(router), "dev", "--host"],
        cwd=workspace,
        stdout=subprocess.PIPE,
        text=True,
    )
    newcomer: subprocess.Popen[str] | None = None
    try:
        assert ours.stdout is not None
        assert ours.stdout.readline().strip() == "ready"

        def _shutdown() -> None:
            shutdown_managed_processes(
                [ours],
                workspace_root=workspace,
                grace_seconds=0.8,
                force=False,
            )

        worker = threading.Thread(target=_shutdown)
        worker.start()
        time.sleep(0.3)
        newcomer = subprocess.Popen(
            [sys.executable, "-c", _DEAF_CHILD, str(router), "dev", "--host"],
            cwd=workspace,
            stdout=subprocess.PIPE,
            text=True,
        )
        assert newcomer.stdout is not None
        assert newcomer.stdout.readline().strip() == "ready"
        worker.join(timeout=5)
        assert not worker.is_alive()
        assert ours.poll() is not None
        assert _is_live(newcomer.pid)
    finally:
        if ours.poll() is None:
            ours.kill()
            ours.wait(timeout=2)
        if newcomer is not None and newcomer.poll() is None:
            newcomer.kill()
            newcomer.wait(timeout=2)
