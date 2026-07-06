"""
CLI for porting Generation-I OakVar modules to the current just-dna-format.

Mounted into the main pipelines CLI as ``pipelines v1-port``. Heavy imports (the compiler's
polars/duckdb stack) are deferred into command bodies, matching the module-compiler CLI idiom, so
``pipelines --help`` stays fast.
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="v1-port",
    help="Port Generation-I OakVar (dna-seq just_* postaggregator) modules to the current format.",
    no_args_is_help=True,
)

console = Console()


@app.command("list")
def v1_list() -> None:
    """List the portable Gen-I modules and their source repos."""
    from just_dna_pipelines.v1_port.sources import REGISTRY

    table = Table(title="Portable Gen-I modules")
    table.add_column("Module", style="cyan")
    table.add_column("Source repo", style="green")
    table.add_column("Data file")
    table.add_column("Adapter", style="magenta")
    for module in REGISTRY.values():
        table.add_row(module.name, f"dna-seq/{module.repo}", module.data_path, module.adapter)
    console.print(table)


@app.command("port")
def v1_port(
    module: Optional[str] = typer.Option(
        None, "--module", "-m", help="Port a single module by name. Omit with --all for every one."
    ),
    all_modules: bool = typer.Option(False, "--all", help="Port every registered module."),
    out_root: Path = typer.Option(
        Path("data/interim/v1_port"), "--out", help="Output root for ported module directories."
    ),
    compile_artifacts: bool = typer.Option(
        True, "--compile/--no-compile", help="Compile parquet artifacts after validating the spec."
    ),
    ensembl_cache: Optional[Path] = typer.Option(
        None, "--ensembl-cache",
        help="Ensembl parquet cache dir. Default: /data/just-dna-cache/ensembl_variations.",
    ),
) -> None:
    """Fetch, convert, validate, and compile Gen-I modules into standalone spec+parquet dirs."""
    from just_dna_pipelines.v1_port.runner import (
        DEFAULT_ENSEMBL_CACHE,
        port_all,
    )
    from just_dna_pipelines.v1_port.sources import REGISTRY

    if not all_modules and module is None:
        console.print("[red]Specify --module <name> or --all.[/red]")
        raise typer.Exit(2)
    if module is not None and module not in REGISTRY:
        console.print(f"[red]Unknown module {module!r}. Known: {', '.join(REGISTRY)}[/red]")
        raise typer.Exit(2)

    names = None if all_modules else [module]
    cache = ensembl_cache or DEFAULT_ENSEMBL_CACHE
    results = port_all(
        names, out_root=out_root, do_compile=compile_artifacts, ensembl_cache=cache,
    )

    table = Table(title="v1 port results")
    for col in ("Module", "Variants", "Studies", "Valid", "Compiled", "Notes"):
        table.add_column(col)
    failures = 0
    for r in results:
        if not r.valid or (compile_artifacts and not r.compiled):
            failures += 1
        note = "; ".join(r.errors[:2]) or ("; ".join(r.warnings[:1]) if r.warnings else "")
        table.add_row(
            r.name, str(r.variant_count), str(r.study_count),
            "[green]yes[/green]" if r.valid else "[red]no[/red]",
            "[green]yes[/green]" if r.compiled else "[yellow]no[/yellow]",
            note,
        )
    console.print(table)
    console.print(f"\nOutput: {out_root}\n")
    if failures:
        console.print(f"[yellow]{failures} module(s) did not fully compile (see notes / GAPS.md).[/yellow]")


@app.command("publish")
def v1_publish(
    module: str = typer.Argument(..., help="Compiled module name under the output root to publish."),
    out_root: Path = typer.Option(
        Path("data/interim/v1_port"), "--out", help="Output root holding the compiled module dir."
    ),
    repo_id: Optional[str] = typer.Option(
        None, "--repo", help="Target HF dataset. Default: first collection source in modules.yaml."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be uploaded without contacting HuggingFace."
    ),
) -> None:
    """Upload a compiled module's artifacts to the HuggingFace annotator collection."""
    from just_dna_pipelines.v1_port.publish import plan_publish, publish_module

    module_dir = out_root / module
    if dry_run:
        plan = plan_publish(module_dir, module, repo_id)
        console.print(f"[bold]Would upload[/bold] to [cyan]{plan.repo_id}[/cyan] at "
                      f"[cyan]{plan.path_in_repo}/[/cyan]:")
        for f in plan.files:
            console.print(f"  • {f}")
        return

    plan = publish_module(module_dir, module, repo_id)
    console.print(
        f"[bold green]✓ Published {module}[/bold green] → "
        f"{plan.repo_id}/{plan.path_in_repo} ({len(plan.files)} files)"
    )
