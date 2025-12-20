from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import typer


app = typer.Typer(no_args_is_help=True, add_completion=False)


def _find_workspace_root(start: Path) -> Optional[Path]:
    """Find the workspace root by searching for a pyproject.toml with uv workspace config."""
    for candidate in [start, *start.parents]:
        pyproject = candidate / "pyproject.toml"
        if not pyproject.exists():
            continue
        try:
            text = pyproject.read_text(encoding="utf-8")
        except OSError:
            continue
        if "[tool.uv.workspace]" in text:
            return candidate
    return None


@app.command("start")
def start() -> None:
    """Start the dev stack (currently: Reflex Web UI)."""
    root = _find_workspace_root(Path.cwd())
    if root is None:
        raise typer.BadParameter("Could not find workspace root. Run this from the repo root.")

    webui_dir = root / "webui"
    if not webui_dir.exists():
        raise typer.BadParameter(f"webui folder not found: {webui_dir}")

    # Important: `reflex` is installed in the `webui` workspace member, not necessarily
    # in the workspace-root environment. So we delegate to `uv run` inside `webui/`.
    #
    # Reflex already runs both frontend+backend in dev.
    # We keep Granian optional for now; Reflex defaults are used here.
    raise typer.Exit(subprocess.call(["uv", "run", "reflex", "run"], cwd=str(webui_dir)))


