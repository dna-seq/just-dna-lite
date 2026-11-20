"""Whether this Linux user has inotify instances left for the dev stack's file watchers.

The kernel caps inotify instances per user (`fs.inotify.max_user_instances`, 128 by default), and
every editor, file manager and agent session holds some. When they run out, `uv run start` gets as
far as Granian's reloader and dies in `watchfiles` with "Too many open files (os error 24)", a
traceback that names neither inotify nor the limit. Measured 2026-11-20: 105 of 128 in use on a
KDE desktop before the stack started.

What the dev stack needs: Granian's reloader opens one instance (watchfiles), the Vite dev server
one (measured: one in the process that listens). Dagster opens none at start; its SQLite event log
adds one per run someone watches in the Dagster UI (watchdog), and its compute logs poll.
`uv run serve` reloads nothing and is not checked.
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

PROC = Path("/proc")
INOTIFY_FD_TARGET = "anon_inode:inotify"
# Granian's reloader and the Vite dev server, plus one run watched in the Dagster UI and one spare.
REQUIRED_FREE = 4
# Below this the stack starts, but other programs open and close watchers all the time: the crash
# above came at a moment when fewer than the 23 free measured just after it were left.
COMFORTABLE_FREE = 32
SUGGESTED_LIMIT = 1024
# Set by `uv run start` once it has checked, so its `webui.run` child does not print it again.
CHECKED_ENV = "JUST_DNA_INOTIFY_CHECKED"


@dataclass(frozen=True)
class InotifyBudget:
    """The user's inotify instances: the limit, how many are held, and by which programs."""

    limit: int
    in_use: int
    holders: tuple[tuple[str, int], ...]

    @property
    def free(self) -> int:
        return self.limit - self.in_use


def _instances_held(pid_dir: Path) -> int:
    """How many inotify instances one process holds; 0 for a process that is gone or not ours."""
    try:
        fds = list((pid_dir / "fd").iterdir())
    except (PermissionError, FileNotFoundError, NotADirectoryError):
        return 0
    held = 0
    for fd in fds:
        try:
            if os.readlink(fd) == INOTIFY_FD_TARGET:
                held += 1
        except OSError:  # the fd closed, or the process exited, between listing and reading
            continue
    return held


def inotify_budget(proc: Path = PROC) -> InotifyBudget | None:
    """Count this user's inotify instances from `proc`; None where there is no Linux inotify."""
    limit_file = proc / "sys" / "fs" / "inotify" / "max_user_instances"
    if not limit_file.is_file():
        return None
    uid = os.getuid()
    by_program: Counter[str] = Counter()
    for pid_dir in proc.iterdir():
        if not pid_dir.name.isdigit():
            continue
        try:
            if pid_dir.stat().st_uid != uid:
                continue
            program = (pid_dir / "comm").read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        held = _instances_held(pid_dir)
        if held:
            by_program[program] += held
    return InotifyBudget(
        limit=int(limit_file.read_text(encoding="utf-8").strip()),
        in_use=sum(by_program.values()),
        holders=tuple(by_program.most_common()),
    )


def _fix(budget: InotifyBudget) -> str:
    top = ", ".join(f"{program} {count}" for program, count in budget.holders[:5])
    return (
        f"  Held by: {top}.\n"
        f"  Raise the limit (needs sudo; the second command keeps it after a reboot):\n"
        f"    sudo sysctl fs.inotify.max_user_instances={SUGGESTED_LIMIT}\n"
        f"    echo 'fs.inotify.max_user_instances={SUGGESTED_LIMIT}' | sudo tee /etc/sysctl.d/60-inotify.conf\n"
        f"  Or close programs that hold many, or run `uv run serve` (no hot reload, no file watchers)."
    )


def inotify_preflight(budget: InotifyBudget | None) -> tuple[str, str]:
    """``(refusal, warning)`` for the dev stack; each is "" when it does not apply."""
    if sys.platform != "linux" or budget is None:
        return "", ""
    numbers = f"{budget.in_use} of {budget.limit} inotify instances (fs.inotify.max_user_instances) are in use"
    if budget.free < REQUIRED_FREE:
        return (
            f"{numbers}; the dev stack's file watchers need {REQUIRED_FREE} free, and without them "
            f"it stops with \"Too many open files (os error 24)\".\n{_fix(budget)}",
            "",
        )
    if budget.free < COMFORTABLE_FREE:
        return "", f"{numbers}; the stack starts, but a few more watchers anywhere will stop hot reload.\n{_fix(budget)}"
    return "", ""
