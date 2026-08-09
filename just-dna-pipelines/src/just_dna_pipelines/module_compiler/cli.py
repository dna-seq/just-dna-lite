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


def _unresolved_coordinates(output_dir: Path) -> tuple[int, int]:
    """Return ``(rows without chrom, total rows)`` for a compiled weights table.

    Compilation succeeds with ``chrom=None`` when resolution found nothing, so this is
    the only signal that a module cannot match a VCF.  Returns ``(0, 0)`` when the
    table is unreadable — a reporting aid must never fail the command that produced it.
    """
    import polars as pl

    weights = output_dir / "weights.parquet"
    if not weights.is_file():
        return (0, 0)
    try:
        frame = pl.read_parquet(weights, columns=["chrom"])
    except (OSError, pl.exceptions.PolarsError):
        # Unreadable, or a table shape with no `chrom` (the 0.4+ non-variant tables).
        # Either way there is nothing to report on; never fail the compile over it.
        return (0, 0)
    return (frame["chrom"].null_count(), frame.height)


@app.command("validate")
def module_validate(
    spec_dir: Path = typer.Argument(
        ...,
        help="Path to module spec directory (contains module_spec.yaml + variants.csv).",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Promote best-effort warnings to errors (0.5). Use in CI before publishing.",
    ),
    authority_key: Optional[list[str]] = typer.Option(
        None,
        "--authority-key",
        help="Authority key accepted for authored facts (0.5). Repeatable.",
    ),
) -> None:
    """
    Validate a module spec without producing output.

    Checks YAML structure, CSV row validity, cross-row consistency,
    and weight/state directionality.

    Since just-dna-format 0.4 a spec may lead with a table other than variants.csv
    (pharm_variants.csv, diplotypes.csv, pgs.csv), and 0.5 adds the injected
    resolution.csv plus fact sidecars — all are validated when present.

    Examples:

        uv run pipelines module validate data/module_specs/evals/mthfr_nad/

        uv run pipelines module validate data/module_specs/evals/cyp_panel/ --strict
    """
    from just_dna_pipelines.module_compiler.compiler import validate_spec

    console.print(f"\n[bold]Validating:[/bold] {spec_dir}")
    if strict:
        console.print("[bold]Mode:      [/bold] strict (warnings are errors)")
    console.print()
    result = validate_spec(spec_dir, authority_keys=authority_key or None, strict=strict)

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


@app.command("register")
def module_register(
    spec_dir: Path = typer.Argument(
        ...,
        help="Path to module spec directory (contains module_spec.yaml + variants.csv).",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    resolve: bool = typer.Option(
        True,
        "--resolve/--no-resolve",
        help="Resolve missing rsid/position via Ensembl DuckDB.",
    ),
    ensembl_cache: Optional[Path] = typer.Option(
        None,
        "--ensembl-cache",
        help="Explicit Ensembl parquet cache path.",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
) -> None:
    """
    Compile a DSL spec, register it as a custom module, and refresh discovery.

    This is the one-shot command for agents and scripts: it validates,
    compiles to parquet, adds the local source + display metadata to
    modules.yaml, and refreshes the in-memory module registry.

    Equivalent to clicking "Add" in the web UI.

    Examples:

        uv run pipelines module register data/module_specs/evals/mthfr_nad/

        uv run pipelines module register data/module_specs/my_panel/ --no-resolve
    """
    from just_dna_pipelines.module_registry import register_custom_module

    console.print(f"\n[bold]Registering module from:[/bold] {spec_dir}\n")

    result = register_custom_module(
        spec_dir,
        resolve_with_ensembl=resolve,
        ensembl_cache=ensembl_cache,
    )

    if result.errors:
        console.print("[bold red]Errors:[/bold red]")
        for err in result.errors:
            console.print(f"  [red]\u2717[/red] {err}")
        console.print()

    if result.warnings:
        console.print("[bold yellow]Warnings:[/bold yellow]")
        for warn in result.warnings:
            console.print(f"  [yellow]\u26a0[/yellow] {warn}")
        console.print()

    if result.success:
        table = Table(title="Registration Result")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        for key, val in result.stats.items():
            table.add_row(key, str(val))
        console.print(table)
        console.print(
            f"\n[bold green]\u2713 Module registered and discoverable[/bold green]"
        )
        if result.output_dir:
            console.print(f"  Output: {result.output_dir}\n")
    else:
        console.print(
            f"[bold red]\u2717 Registration failed with {len(result.errors)} error(s)[/bold red]\n"
        )
        raise typer.Exit(1)


@app.command("unregister")
def module_unregister(
    module_name: str = typer.Argument(
        ...,
        help="Machine name of the custom module to remove (e.g. 'mthfr_nad').",
    ),
) -> None:
    """
    Remove a custom module: delete its parquet, update modules.yaml, refresh discovery.

    Equivalent to clicking "Remove" in the web UI.

    Examples:

        uv run pipelines module unregister mthfr_nad
    """
    from just_dna_pipelines.module_registry import unregister_custom_module

    console.print(f"\n[bold]Unregistering module:[/bold] {module_name}\n")

    removed = unregister_custom_module(module_name)
    if removed:
        console.print(f"[bold green]\u2713 Module '{module_name}' removed[/bold green]\n")
    else:
        console.print(f"[bold red]\u2717 Module '{module_name}' not found in custom modules[/bold red]\n")
        raise typer.Exit(1)


@app.command("list-custom")
def module_list_custom() -> None:
    """
    List all custom modules currently compiled on disk.

    Shows module names and their output directories.

    Examples:

        uv run pipelines module list-custom
    """
    from just_dna_pipelines.module_registry import get_custom_module_specs

    specs = get_custom_module_specs()
    if not specs:
        console.print("\n[dim]No custom modules found.[/dim]\n")
        return

    table = Table(title="Custom Modules")
    table.add_column("Module", style="cyan")
    table.add_column("Output Directory", style="green")
    for name, path in specs.items():
        table.add_row(name, str(path))
    console.print(table)
    console.print()


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
        help="Resolve missing rsid/position via the local Ensembl DuckDB (skipped if absent).",
    ),
    ensembl_cache: Optional[Path] = typer.Option(
        None,
        "--ensembl-cache",
        help=(
            "Explicit Ensembl parquet cache path. Default: auto-detect from platform cache. "
            "DEPRECATED — prefer `pipelines enrich enrich` to produce resolution.csv."
        ),
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Promote best-effort warnings to errors (0.5). Use in CI before publishing.",
    ),
    authority_key: Optional[list[str]] = typer.Option(
        None,
        "--authority-key",
        help="Authority key accepted for authored facts (0.5). Repeatable.",
    ),
    compiled_by: Optional[str] = typer.Option(
        None,
        "--compiled-by",
        help="Recorded in the manifest's compilation provenance (0.5).",
    ),
    ensembl_reference: Optional[str] = typer.Option(
        None,
        "--ensembl-reference",
        help="Reference label recorded in the manifest, e.g. 'Ensembl 115 GRCh38' (0.5).",
    ),
    provenance: Optional[Path] = typer.Option(
        None,
        "--provenance",
        help="Provenance file to hash into the manifest (0.5).",
        exists=True,
        dir_okay=False,
    ),
    logo: Optional[Path] = typer.Option(
        None,
        "--logo",
        help="Logo image to carry into the artifact (0.5).",
        exists=True,
        dir_okay=False,
    ),
    log_file: Optional[list[Path]] = typer.Option(
        None,
        "--log-file",
        help="Build log to hash into the manifest (0.5). Repeatable.",
        exists=True,
        dir_okay=False,
    ),
    ba1_threshold: float = typer.Option(
        0.05,
        "--ba1-threshold",
        help="Allele-frequency threshold for the ACMG BA1 stand-alone benign rule (0.5).",
    ),
) -> None:
    """
    Compile a module spec into deployable parquet files.

    Produces weights.parquet, annotations.parquet, and (if studies.csv exists)
    studies.parquet in the output directory.

    Resolution, in order of preference:

    1. **resolution.csv in the spec dir** (0.5, preferred) — the compiler consumes it
       with no reference and no network, and it reproduces the DuckDB path byte for
       byte. Produce it with `pipelines enrich enrich <spec_dir>`.
    2. **Injected Ensembl DuckDB** — the legacy path, kept working. just-dna-compiler
       deprecates it for removal at 1.0, so migrate specs to (1).

    Compilation uses the published inject-only just-dna-compiler: with neither of the
    above it compiles successfully but leaves coordinates unresolved (chrom=None)
    rather than downloading anything.

    Examples:

        uv run pipelines module compile data/module_specs/evals/mthfr_nad/

        uv run pipelines enrich enrich data/module_specs/evals/cyp_panel/
        uv run pipelines module compile data/module_specs/evals/cyp_panel/ --strict

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

    # Which resolution path this run will take, stated up front. A spec with no
    # resolution.csv and no cache still compiles — it just leaves chrom=None, which is
    # easy to miss because nothing fails. See docs/MODULE_FORMAT_0_5_MIGRATION.md.
    has_resolution_csv = (spec_dir / "resolution.csv").is_file()
    if not resolve:
        resolution_path = "none (--no-resolve)"
    elif has_resolution_csv:
        resolution_path = "resolution.csv (injected, no network)"
    elif ensembl_cache is not None:
        resolution_path = f"Ensembl DuckDB at {ensembl_cache} [deprecated, removed at 1.0]"
    else:
        resolution_path = "default Ensembl cache if present, else unresolved (chrom=None)"

    console.print(f"\n[bold]Compiling:[/bold] {spec_dir}")
    console.print(f"[bold]Output:   [/bold] {output}")
    console.print(f"[bold]Resolve:  [/bold] {resolution_path}")
    if strict:
        console.print("[bold]Mode:     [/bold] strict (warnings are errors)")
    console.print()

    result = compile_module(
        spec_dir,
        output,
        compression=compression,
        resolve_with_ensembl=resolve,
        ensembl_cache=ensembl_cache,
        compiled_by=compiled_by,
        ensembl_reference=ensembl_reference,
        log_files=log_file or None,
        provenance_file=provenance,
        logo_file=logo,
        authority_keys=authority_key or None,
        strict=strict,
        ba1_threshold=ba1_threshold,
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

        unresolved, total = _unresolved_coordinates(output)
        if unresolved:
            # Unresolved coordinates are not a compile error, so nothing above fails —
            # which is exactly how a partial Ensembl cache ships a broken module. The
            # usual cause is a cache missing the chromosomes these variants sit on
            # (a complete GRCh38 cache is 25 parquet files, chr1-22/X/Y/MT).
            console.print(
                f"\n[bold yellow]⚠ {unresolved}/{total} weight rows have no chrom[/bold yellow]\n"
                "  They will never match a VCF. Resolve them before publishing:\n"
                f"    uv run pipelines enrich enrich {spec_dir}\n"
                "  then recompile — the resolution.csv it writes needs no reference and no network."
            )
        console.print(f"\n[bold green]✓ Module compiled successfully to {output}[/bold green]\n")
    else:
        console.print(
            f"[bold red]✗ Compilation failed with {len(result.errors)} error(s)[/bold red]\n"
        )
        raise typer.Exit(1)


@app.command("reverse")
def module_reverse(
    parquet_dir: Path = typer.Argument(
        ...,
        help="Directory holding a compiled module (weights.parquet + friends).",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    output: Path = typer.Argument(
        ...,
        help="Directory to write the reconstructed spec into.",
        file_okay=False,
        dir_okay=True,
    ),
    module_name: Optional[str] = typer.Option(None, "--name", help="Override module name."),
    title: Optional[str] = typer.Option(None, "--title", help="Override display title."),
    description: Optional[str] = typer.Option(None, "--description", help="Override description."),
    report_title: Optional[str] = typer.Option(None, "--report-title", help="Override report title."),
    icon: str = typer.Option("database", "--icon", help="Display icon name."),
    color: str = typer.Option("#6435c9", "--color", help="Display colour (hex)."),
    version: Optional[str] = typer.Option(None, "--version", help="Override module version."),
    write_resolution: bool = typer.Option(
        True,
        "--write-resolution/--no-write-resolution",
        help=(
            "Emit resolution.csv alongside the spec (0.5). Keeping it means the spec "
            "recompiles offline and byte-identically; dropping it forces re-enrichment."
        ),
    ),
    genome_build: Optional[str] = typer.Option(
        None,
        "--genome-build",
        help="Genome build recorded in resolution.csv, e.g. GRCh38 (0.5).",
    ),
) -> None:
    """
    Reconstruct an authored spec directory from a compiled module.

    The inverse of ``compile``: reads the parquet tables and writes back
    module_spec.yaml plus the authored CSVs, so a published module can be edited
    and recompiled. Round-trips cleanly for every module published so far.

    With ``--write-resolution`` (the default) the reconstructed spec carries the
    already-resolved coordinates, so recompiling needs neither a reference nor
    network access and reproduces the same artifact digest.

    Examples:

        uv run pipelines module reverse data/output/modules/longevitymap/ \\
            data/module_specs/longevitymap/

        uv run pipelines module reverse data/output/modules/vo2max/ /tmp/vo2max \\
            --no-write-resolution
    """
    from just_dna_compiler.compiler import reverse_module

    console.print(f"\n[bold]Reversing:[/bold] {parquet_dir}")
    console.print(f"[bold]Output:   [/bold] {output}")
    console.print(f"[bold]resolution.csv:[/bold] {'yes' if write_resolution else 'no'}\n")

    spec_dir = reverse_module(
        parquet_dir,
        output,
        module_name=module_name,
        title=title,
        description=description,
        report_title=report_title,
        icon=icon,
        color=color,
        version=version,
        write_resolution=write_resolution,
        genome_build=genome_build,
    )

    written = sorted(p.name for p in Path(spec_dir).iterdir() if p.is_file())
    table = Table(title="Reconstructed Spec")
    table.add_column("File", style="cyan")
    table.add_column("Size", style="green", justify="right")
    for name in written:
        table.add_row(name, f"{(Path(spec_dir) / name).stat().st_size:,} B")
    console.print(table)
    console.print(f"\n[bold green]✓ Spec written to {spec_dir}[/bold green]\n")
