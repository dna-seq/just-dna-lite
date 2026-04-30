"""CLI entry point for running the Reflex app. Reuses reflex run directly."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from just_dna_pipelines.runtime import load_env


def main() -> None:
    """Run reflex in the webui project directory. Never returns (exec).

    Supports ``--immutable`` flag to start in public demo mode
    (equivalent to ``JUST_DNA_IMMUTABLE_MODE=true``).  The flag is
    consumed here and not forwarded to Reflex.
    """
    argv = list(sys.argv[1:])
    if "--immutable" in argv:
        argv.remove("--immutable")
        os.environ["JUST_DNA_IMMUTABLE_MODE"] = "true"

    load_env()
    webui_root = Path(__file__).resolve().parent.parent.parent
    os.chdir(webui_root)
    os.execvp(sys.executable, [sys.executable, "-m", "reflex", "run"] + argv)


if __name__ == "__main__":
    main()
