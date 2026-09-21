"""The enricher's Typer app, or a stub that says why it could not be imported.

Both `pipelines` entry points (`just_dna_lite.cli`, which owns the installed script, and
`just_dna_pipelines.cli`) mount `just-dna-enricher`'s CLI whole under `enrich`, so new enricher
commands surface without wiring. That import is the one place this repo is exposed to the enricher's
optional AlphaGenome Atlas bindings: `just_dna_enricher.cli` imports `alphagenome_check` at module
scope, which imports `atlas_client`, which imports protobuf gencode stamped by the `grpcio-tools`
that generated it (1.83.1, protobuf 7.35). Every deployment of this repo runs an older protobuf
runtime — dagster caps `protobuf<7` — and protobuf refuses a runtime older than its gencode with
`google.protobuf.runtime_version.VersionError`, a bare `Exception` subclass. The enricher's own
guard is `except (ImportError, RuntimeError)` (RM247) and does not catch it, so on enricher 0.7.1
against protobuf 6.33.6 the whole `pipelines` command died at import. Measured 2026-09-21; filed
upstream as S107 in just-dna-format's `CONSUMER_SUGGESTIONS.md`.

This is the sanctioned guarded-optional-import exception to "no try around imports", and it is not
silent: when the real app is unavailable a stub `enrich` group is mounted whose `status` command
prints the captured reason and exits 1, and `ENRICHER_CLI_UNAVAILABLE` carries it for anything else
that wants to say so. The enricher's Python API (`resolver`, `enrich`, `caches`, `clinvar*`,
`clinpgx*`) imports cleanly and is what this repo actually calls; only the Typer app is lost.
"""

from __future__ import annotations

from typing import Optional

import typer
from google.protobuf.runtime_version import VersionError as ProtobufVersionError
from rich.console import Console

try:
    from just_dna_enricher.cli import app as _real_enricher_app

    ENRICHER_CLI_UNAVAILABLE: Optional[str] = None
except (ImportError, RuntimeError, ProtobufVersionError) as _enricher_cli_exc:
    _real_enricher_app = None
    ENRICHER_CLI_UNAVAILABLE = f"{type(_enricher_cli_exc).__name__}: {_enricher_cli_exc}"


def _build_stub() -> typer.Typer:
    stub = typer.Typer(
        name="enrich",
        help=(
            "just-dna-enricher's CLI could not be imported in this environment; "
            "run `status` for the reason."
        ),
        no_args_is_help=True,
    )

    @stub.command("status")
    def status() -> None:
        """Say why the enricher CLI is not mounted, instead of hiding the command group."""
        Console().print(
            "[bold red]✗ just-dna-enricher's CLI is not available in this environment[/bold red]\n"
            f"  {ENRICHER_CLI_UNAVAILABLE}\n"
            "  The enricher's Python API still works; only its command-line app failed to import.\n"
            "  Cache provisioning is available as [bold]pipelines prepare-caches[/bold]."
        )
        raise typer.Exit(1)

    return stub


#: What to mount under `enrich`: the enricher's own app when it imports, else the stub above.
enricher_app: typer.Typer = _real_enricher_app if _real_enricher_app is not None else _build_stub()
