from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Optional

import typer


app = typer.Typer(
    name="just-dna-lite",
    help="Just DNA Lite - Genomic analysis stack",
    no_args_is_help=True,
    add_completion=False
)


def _find_workspace_root(start: Path) -> Optional[Path]:
    """Find the workspace root by searching for a pyproject.toml with uv workspace config."""
    for candidate in [start, *start.parents]:
        pyproject = candidate / "pyproject.toml"
        if not pyproject.exists():
            continue
        text = pyproject.read_text(encoding="utf-8")
        if "[tool.uv.workspace]" in text:
            return candidate
    return None


@app.command("ui")
def start_ui() -> None:
    """Start only the Reflex Web UI."""
    root = _find_workspace_root(Path.cwd())
    if root is None:
        raise typer.BadParameter("Could not find workspace root. Run this from the repo root.")

    webui_dir = root / "webui"
    if not webui_dir.exists():
        raise typer.BadParameter(f"webui folder not found: {webui_dir}")

    print("🚀 Starting Reflex Web UI...")
    # Reflex already runs both frontend+backend in dev.
    subprocess.call(["uv", "run", "reflex", "run"], cwd=str(webui_dir))


@app.command("pipelines")
def start_pipelines() -> None:
    """Start the Prefect server and the GenoBear pipelines."""
    print("🧬 Starting GenoBear Pipelines...")
    subprocess.call(["uv", "run", "pipelines"])


@app.command("start")
def start_all() -> None:
    """Start the full stack: Prefect Server, Pipelines, and Reflex UI."""
    root = _find_workspace_root(Path.cwd())
    if root is None:
        raise typer.BadParameter("Could not find workspace root.")

    print("🏗️  Starting full GenoBear stack...")

    # 1. Start the pipelines (which also handles starting Prefect server)
    pipelines_proc = subprocess.Popen(
        ["uv", "run", "pipelines"],
        preexec_fn=os.setpgrp if hasattr(os, "setpgrp") else None
    )
    
    # Wait a bit for the worker/server to start initializing
    time.sleep(2)

    # 2. Start the UI
    try:
        start_ui()
    finally:
        # Cleanup
        print("\n🛑 Shutting down...")
        pipelines_proc.terminate()


if __name__ == "__main__":
    app()



