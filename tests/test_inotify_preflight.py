"""`uv run start` checks the user's inotify instances before starting the dev stack's file watchers.

With `fs.inotify.max_user_instances` used up (105 of 128 on 2026-11-20, mostly desktop programs and
agent sessions), the stack died inside Granian's reloader with "Too many open files (os error 24)"
from watchfiles. The launcher now names the limit, who holds the instances and the fix, first.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import sys
from pathlib import Path

import pytest
import typer

from just_dna_lite import cli
from just_dna_lite.inotify import (
    COMFORTABLE_FREE,
    INOTIFY_FD_TARGET,
    REQUIRED_FREE,
    InotifyBudget,
    _instances_held,
    inotify_budget,
    inotify_preflight,
)

linux_only = pytest.mark.skipif(sys.platform != "linux", reason="inotify is Linux-only")


def _fake_proc(root: Path, limit: int, processes: dict[str, tuple[str, list[str]]]) -> Path:
    """A /proc tree: the limit file, and per pid a `comm` and `fd/` symlinks with the given targets."""
    limit_file = root / "sys" / "fs" / "inotify" / "max_user_instances"
    limit_file.parent.mkdir(parents=True)
    limit_file.write_text(f"{limit}\n")
    for pid, (comm, targets) in processes.items():
        fd_dir = root / pid / "fd"
        fd_dir.mkdir(parents=True)
        (root / pid / "comm").write_text(f"{comm}\n", encoding="utf-8")
        for n, target in enumerate(targets):
            (fd_dir / str(n)).symlink_to(target)
    return root


def test_counts_instances_by_program_from_proc(tmp_path: Path) -> None:
    proc = _fake_proc(
        tmp_path,
        limit=128,
        processes={
            "101": ("claude", [INOTIFY_FD_TARGET, INOTIFY_FD_TARGET, "/dev/null"]),
            "102": ("claude", [INOTIFY_FD_TARGET]),
            "103": ("dolphin", [INOTIFY_FD_TARGET, "anon_inode:[eventfd]", "socket:[1]"]),
            "104": ("bäsh ünicode", ["/dev/null"]),
        },
    )
    (proc / "self").mkdir()  # not a pid: skipped
    (proc / "105").mkdir()  # a process that exited mid-scan: no comm, no fd

    budget = inotify_budget(proc)

    assert budget == InotifyBudget(limit=128, in_use=4, holders=(("claude", 3), ("dolphin", 1)))
    assert budget.free == 124


def test_no_inotify_means_no_budget(tmp_path: Path) -> None:
    assert inotify_budget(tmp_path) is None
    assert inotify_preflight(None) == ("", "")


@linux_only
def test_the_real_proc_counts_an_instance_this_process_opens() -> None:
    libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    me = Path("/proc") / str(os.getpid())
    before = _instances_held(me)
    fd = libc.inotify_init1(0)
    assert fd >= 0, os.strerror(ctypes.get_errno())
    try:
        assert _instances_held(me) == before + 1
        budget = inotify_budget()
        assert budget is not None
        assert budget.limit == int(Path("/proc/sys/fs/inotify/max_user_instances").read_text())
        assert budget.in_use >= before + 1
    finally:
        os.close(fd)
    assert _instances_held(me) == before


def _budget(free: int, limit: int = 128) -> InotifyBudget:
    return InotifyBudget(limit=limit, in_use=limit - free, holders=(("claude", 35), ("ChatGPT", 10)))


@linux_only
@pytest.mark.parametrize("free", [-3, 0, REQUIRED_FREE - 1])
def test_too_few_free_refuses_with_the_numbers_holders_and_fix(free: int) -> None:
    refusal, warning = inotify_preflight(_budget(free))
    assert warning == ""
    assert f"{128 - free} of 128" in refusal
    assert "claude 35" in refusal and "ChatGPT 10" in refusal
    assert "sysctl fs.inotify.max_user_instances=" in refusal
    assert "/etc/sysctl.d/" in refusal
    assert "uv run serve" in refusal


@linux_only
@pytest.mark.parametrize("free", [REQUIRED_FREE, COMFORTABLE_FREE - 1])
def test_a_tight_budget_warns_but_starts(free: int) -> None:
    refusal, warning = inotify_preflight(_budget(free))
    assert refusal == ""
    assert f"{128 - free} of 128" in warning and "sysctl" in warning


@linux_only
@pytest.mark.parametrize("free", [COMFORTABLE_FREE, 900])
def test_a_comfortable_budget_says_nothing(free: int) -> None:
    assert inotify_preflight(_budget(free, limit=1024)) == ("", "")


def test_start_refuses_before_spawning_anything(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "node_too_old_for_dev_server", lambda: "")
    monkeypatch.setattr(cli, "inotify_preflight", lambda budget: ("105 of 128 inotify instances", ""))

    def must_not_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("the launcher reached process startup")

    monkeypatch.setattr(cli, "reap_dagster_instance", must_not_run)
    monkeypatch.setattr(cli.subprocess, "Popen", must_not_run)
    with pytest.raises(typer.Exit) as exited:
        cli.start_all()
    assert exited.value.exit_code == 1
