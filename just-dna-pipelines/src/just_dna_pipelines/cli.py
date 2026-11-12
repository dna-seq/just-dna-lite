"""
CLI for just-dna-pipelines.

Provides command-line interface for running annotation pipelines.
"""

from pathlib import Path
from typing import Dict, Optional

import typer
from rich.console import Console
from rich.table import Table

from just_dna_pipelines.annotation.module_cache import (
    clear_hf_module_cache,
    get_app_version,
)
from just_dna_pipelines.module_compiler.cli import app as module_app
from just_dna_pipelines.agents.cli import app as agent_app
from just_dna_pipelines.v1_port.cli import app as v1_port_app
from just_dna_enricher.cli import app as enricher_app
from just_dna_pipelines.runtime import environ_guard

# just-dna-registry calls a bare load_dotenv() at import, which climbs above this checkout; import it
# once under environ_guard so only our own load_env() decides the configuration.
with environ_guard():
    from just_dna_registry.client_cli import app as registry_client_app

app = typer.Typer(
    name="pipelines",
    help="Genomic annotation pipelines for VCF files.",
    no_args_is_help=True,
)
app.add_typer(module_app, name="module")
app.add_typer(agent_app, name="agent")
app.add_typer(v1_port_app, name="v1-port")
# The enricher's own Typer app, mounted whole rather than re-declared: it is the
# authoring tier that produces `resolution.csv` and the 0.5 fact sidecars which
# `pipelines module compile` then consumes with no reference and no network.
# Mounting it means new enricher commands appear here without further wiring; the Ensembl
# snapshot is its `cache pull --only ensembl` / `cache status`.
app.add_typer(enricher_app, name="enrich")
app.add_typer(registry_client_app, name="registry")

console = Console()


@app.command()
def clear_module_cache() -> None:
    """Delete the locally cached HuggingFace annotator-module data.

    Forces the next run to re-download the currently published module versions.
    Use after republishing a module in place (same version); version bumps are
    invalidated automatically on startup.
    """
    removed = clear_hf_module_cache()
    if removed:
        console.print(f"[green]Cleared HF module cache for:[/green] {', '.join(removed)}")
    else:
        console.print("[yellow]No cached HF module repos found — nothing to clear.[/yellow]")
    console.print(f"[dim]Current app version: {get_app_version()}[/dim]")


@app.command()
def list_modules() -> None:
    """
    List all available annotation modules (auto-discovered from configured sources).
    """
    from just_dna_pipelines.annotation.hf_modules import DISCOVERED_MODULES, MODULE_INFOS
    from just_dna_pipelines.module_config import get_module_meta, MODULES_CONFIG

    table = Table(title="Available Annotation Modules")
    table.add_column("Module", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Source", style="dim")

    for module in DISCOVERED_MODULES:
        meta = get_module_meta(module)
        info = MODULE_INFOS.get(module)
        source = info.source_url if info else ""
        table.add_row(module, meta.description or "", source)

    console.print(table)
    console.print(f"\n[dim]Sources: {', '.join(s.url for s in MODULES_CONFIG.sources)}[/dim]")
    console.print("[dim]Select modules with: uv run annotate genome.vcf -m <name> [-m <name> ...][/dim]")


@app.command()
def show_manifest(
    manifest_path: str = typer.Argument(
        ...,
        help="Path to manifest.json file",
    ),
) -> None:
    """
    Display the contents of an annotation manifest file.
    """
    import json

    path = Path(manifest_path)
    if not path.exists():
        console.print(f"[red]Error: Manifest not found: {path}[/red]")
        raise typer.Exit(1)

    with open(path) as f:
        manifest = json.load(f)

    console.print(f"\n[bold]Annotation Manifest[/bold]")
    console.print(f"  User: {manifest['user_name']}")
    console.print(f"  Sample: {manifest['sample_name']}")
    console.print(f"  Source VCF: {manifest['source_vcf']}")
    console.print(f"  Total variants: {manifest['total_variants_annotated']}")

    table = Table(title="Output Files")
    table.add_column("Module", style="cyan")
    table.add_column("Lead table", style="magenta")
    table.add_column("Weights File", style="green")

    for m in manifest["modules"]:
        table.add_row(m["module"], m.get("lead_table", "weights"), m.get("weights_path", "N/A"))

    console.print(table)

    for name, reason in manifest.get("skipped_modules", {}).items():
        console.print(f"[yellow]Skipped[/yellow] {name}: {reason}")
    for name, reason in manifest.get("failed_modules", {}).items():
        console.print(f"[red]Failed[/red] {name}: {reason}")


def main() -> None:
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
