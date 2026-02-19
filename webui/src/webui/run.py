"""CLI entry point for running the Reflex app. Reuses reflex run directly."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    """Run reflex in the webui project directory. Never returns (exec)."""
    webui_root = Path(__file__).resolve().parent.parent.parent
    os.chdir(webui_root)
    os.execvp(sys.executable, [sys.executable, "-m", "reflex", "run"] + sys.argv[1:])


if __name__ == "__main__":
    main()
