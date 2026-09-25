"""Whether this machine's JavaScript runtime can run the Reflex dev frontend.

Lives outside ``webui`` so the stack launcher can ask before it starts anything: ``uv run start``
spawns Dagster and prints its banner before the UI child would get far enough to fail.
"""

from __future__ import annotations

from packaging import version
from reflex.utils import js_runtimes
from reflex_base import constants


def node_too_old_for_dev_server() -> str:
    """Why the dev frontend cannot start on this machine's Node.js, or "" if it can.

    Below Reflex's minimum Node, Reflex runs the frontend as ``bun --bun run dev``, i.e. under
    Bun's runtime. react-router 8's ``dev`` then restarts itself with
    ``NODE_OPTIONS=--conditions=development``, which Bun ignores, so the restarted process
    fails the same check and throws "restartWithMergedOptions() was called, but the process
    has already been restarted". Reflex prints only an "out of date" warning before that, and
    the crash that follows names neither Node nor Bun. ``uv run serve`` builds the frontend
    once and never takes that path.
    """
    current = js_runtimes.get_node_version()
    required = version.parse(constants.Node.MIN_VERSION)
    if current is None:
        found = "No Node.js was found on PATH"
    elif current < required:
        found = f"Node.js {current} is installed"
    else:
        return ""
    return (
        f"{found}; the development web UI needs Node.js {required} or newer.\n"
        "  Install the current LTS from https://nodejs.org (Windows: winget install OpenJS.NodeJS.LTS),\n"
        "  open a new terminal, and run `uv run start` again.\n"
        "  Or run `uv run serve` instead, which works on this Node (single port, no hot reload)."
    )
