"""``python -m just_dna_lite.dg`` runs Dagster's ``dg`` CLI without its console-script wrapper.

``dagster_dg_cli`` ships no ``__main__``, so ``dg`` is only reachable through ``.venv/bin/dg``
(``dg.exe`` on Windows) — a uv trampoline. Locked-down Windows machines refuse to execute those
(AppLocker, Smart App Control), so the launchers start ``dg`` through this module instead.
"""

from dagster_dg_cli.cli import main

if __name__ == "__main__":
    main()
