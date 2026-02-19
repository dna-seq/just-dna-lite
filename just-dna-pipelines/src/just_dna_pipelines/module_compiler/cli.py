"""
CLI commands for the module compiler.

Provides Typer commands for validating and compiling module specs.
Designed to be mounted into the main pipelines CLI via app.add_typer()
or by registering individual commands.
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="module",
    help="Module compiler: validate and build annotation modules from spec files.",
    no_args_is_help=True,
)

console = Console()


@app.command("validate")
def module_validate(
    spec_dir: Path = typer.Argument(
        ...,
        help="Path to module spec directory (contains module_spec.yaml + variants.csv).",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
) -> None:
    """
    Validate a module spec without producing output.

    Checks YAML structure, CSV row validity, cross-row consistency,
    and weight/state directionality.

    Examples:

        uv run pipelines module validate data/module_specs/evals/mthfr_nad/

        uv run pipelines module validate data/module_specs/evals/cyp_panel/
    """
    from just_dna_pipelines.module_compiler.compiler import validate_spec

    console.print(f"\n[bold]Validating:[/bold] {spec_dir}\n")
    result = validate_spec(spec_dir)

    if result.errors:
        console.print("[bold red]Errors:[/bold red]")
        for err in result.errors:
            console.print(f"  [red]✗[/red] {err}")
        console.print()

    if result.warnings:
        console.print("[bold yellow]Warnings:[/bold yellow]")
        for warn in result.warnings:
            console.print(f"  [yellow]⚠[/yellow] {warn}")
        console.print()

    if result.stats:
        table = Table(title="Spec Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        for key, val in result.stats.items():
            table.add_row(key, str(val))
        console.print(table)

    if result.valid:
        console.print("[bold green]✓ Spec is valid[/bold green]\n")
    else:
        console.print(f"[bold red]✗ Validation failed with {len(result.errors)} error(s)[/bold red]\n")
        raise typer.Exit(1)


@app.command("compile")
def module_compile(
    spec_dir: Path = typer.Argument(
        ...,
        help="Path to module spec directory (contains module_spec.yaml + variants.csv).",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Output directory. Default: data/output/modules/<module_name>/",
    ),
    compression: str = typer.Option(
        "zstd",
        "--compression", "-c",
        help="Parquet compression: zstd, snappy, lz4, gzip.",
    ),
    resolve: bool = typer.Option(
        True,
        "--resolve/--no-resolve",
        help="Resolve missing rsid/position via Ensembl DuckDB (auto-downloads if needed).",
    ),
    ensembl_cache: Optional[Path] = typer.Option(
        None,
        "--ensembl-cache",
        help="Explicit Ensembl parquet cache path. Default: auto-detect from platform cache.",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
) -> None:
    """
    Compile a module spec into deployable parquet files.

    Produces weights.parquet, annotations.parquet, and (if studies.csv exists)
    studies.parquet in the output directory.

    By default, resolves missing rsid/position fields via the local Ensembl
    DuckDB (GRCh38). The DuckDB is auto-built from the Ensembl parquet cache;
    if the cache is missing it is downloaded from HuggingFace Hub.

    Examples:

        uv run pipelines module compile data/module_specs/evals/mthfr_nad/

        uv run pipelines module compile data/module_specs/evals/cyp_panel/ \\
            --output data/output/modules/cyp_panel/

        uv run pipelines module compile data/module_specs/evals/cyp_panel/ --no-resolve
    """
    from just_dna_pipelines.module_compiler.compiler import compile_module

    # Determine output dir: load module name from YAML for default path
    if output is None:
        import yaml as _yaml

        yaml_path = spec_dir / "module_spec.yaml"
        if yaml_path.exists():
            raw = _yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            module_name = raw.get("module", {}).get("name", spec_dir.name)
        else:
            module_name = spec_dir.name
        output = Path("data/output/modules") / module_name

    console.print(f"\n[bold]Compiling:[/bold] {spec_dir}")
    console.print(f"[bold]Output:   [/bold] {output}")
    console.print(f"[bold]Resolve:  [/bold] {'yes' if resolve else 'no'}\n")

    result = compile_module(
        spec_dir,
        output,
        compression=compression,
        resolve_with_ensembl=resolve,
        ensembl_cache=ensembl_cache,
    )

    if result.errors:
        console.print("[bold red]Errors:[/bold red]")
        for err in result.errors:
            console.print(f"  [red]✗[/red] {err}")
        console.print()

    if result.warnings:
        console.print("[bold yellow]Warnings:[/bold yellow]")
        for warn in result.warnings:
            console.print(f"  [yellow]⚠[/yellow] {warn}")
        console.print()

    if result.success:
        table = Table(title="Compilation Result")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        for key, val in result.stats.items():
            table.add_row(key, str(val))
        console.print(table)
        console.print(f"\n[bold green]✓ Module compiled successfully to {output}[/bold green]\n")
    else:
        console.print(
            f"[bold red]✗ Compilation failed with {len(result.errors)} error(s)[/bold red]\n"
        )
        raise typer.Exit(1)
