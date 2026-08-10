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
        help="Ensembl parquet cache dir. Default: the configured cache (`pipelines ensembl-setup`).",
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Cache-only: no live Ensembl, no gnomAD, no literature pass."
    ),
    literature: bool = typer.Option(
        True, "--literature/--no-literature",
        help="Fill literature.csv from the cited PMIDs (online: PubMed/Crossref).",
    ),
) -> None:
    """Fetch, convert, validate, resolve and compile Gen-I modules into spec+parquet dirs."""
    from just_dna_pipelines.v1_port.runner import (
        DEFAULT_ENSEMBL_CACHE,
        VARIANT_MODULES,
        port_all,
    )

    if not all_modules and module is None:
        console.print("[red]Specify --module <name> or --all.[/red]")
        raise typer.Exit(2)
    if module is not None and module not in VARIANT_MODULES:
        console.print(
            f"[red]Unknown module {module!r}. Known: {', '.join(VARIANT_MODULES)}[/red]\n"
            f"[yellow]cardio/cancer/pathogenic are built by `v1-port clinvar`.[/yellow]"
        )
        raise typer.Exit(2)

    names = None if all_modules else [module]
    cache = ensembl_cache or DEFAULT_ENSEMBL_CACHE
    results = port_all(
        names, out_root=out_root, do_compile=compile_artifacts, ensembl_cache=cache,
        offline=offline, do_literature=literature,
    )

    table = Table(title="v1 port results")
    for col in ("Module", "Variants", "Studies", "Valid", "Resolved", "Lit", "Compiled", "Notes"):
        table.add_column(col)
    failures = 0
    for r in results:
        if not r.valid or (compile_artifacts and not r.compiled):
            failures += 1
        note = "; ".join(r.errors[:2]) or ("; ".join(r.warnings[:1]) if r.warnings else "")
        unresolved = f" (-{r.unresolved_rows})" if r.unresolved_rows else ""
        table.add_row(
            r.name, str(r.variant_count), str(r.study_count),
            "[green]yes[/green]" if r.valid else "[red]no[/red]",
            f"{r.resolved_rows}{unresolved}",
            str(r.literature_rows),
            "[green]yes[/green]" if r.compiled else "[yellow]no[/yellow]",
            note[:60],
        )
    console.print(table)
    console.print(f"\nOutput: {out_root}\n")
    if failures:
        console.print(f"[yellow]{failures} module(s) did not fully compile (see notes / GAPS.md).[/yellow]")


CLINVAR_MODULES = ("cardio", "cancer", "pathogenic")


@app.command("clinvar")
def v1_clinvar(
    module: Optional[str] = typer.Option(
        None, "--module", "-m", help=f"One of {', '.join(CLINVAR_MODULES)}. Omit with --all."
    ),
    all_modules: bool = typer.Option(False, "--all", help="Build every ClinVar module."),
    out_root: Path = typer.Option(
        Path("data/interim/v1_port"), "--out", help="Output root for the built module directories."
    ),
    snapshot: Optional[Path] = typer.Option(
        None, "--snapshot", help="ClinVar parquet snapshot dir. Default: the resolved cache."
    ),
    min_review_stars: int = typer.Option(
        None, "--min-review-stars", help="Review-status floor. Default: the module default (1)."
    ),
    enrich_spec: bool = typer.Option(
        True, "--enrich/--no-enrich", help="Fill resolution.csv from the same ClinVar snapshot."
    ),
    compile_artifacts: bool = typer.Option(
        True, "--compile/--no-compile", help="Compile parquet artifacts from resolution.csv."
    ),
) -> None:
    """Build the ClinVar-backed modules on the 0.5 enricher machinery (snapshot, not raw VCF)."""
    from just_dna_pipelines.v1_port.clinvar_runner import build_clinvar_modules

    if not all_modules and module is None:
        console.print("[red]Specify --module <name> or --all.[/red]")
        raise typer.Exit(2)
    if module is not None and module not in CLINVAR_MODULES:
        console.print(f"[red]Unknown module {module!r}. Known: {', '.join(CLINVAR_MODULES)}[/red]")
        raise typer.Exit(2)

    names = list(CLINVAR_MODULES) if all_modules else [module]
    results = build_clinvar_modules(
        names,
        out_root=out_root,
        snapshot=snapshot,
        min_review_stars=min_review_stars,
        do_enrich=enrich_spec,
        do_compile=compile_artifacts,
        console=console,
    )

    table = Table(title="ClinVar module builds")
    for col in ("Module", "Genes", "Records", "Variants", "Studies", "Resolved", "Compiled"):
        table.add_column(col)
    failures = 0
    for r in results:
        if compile_artifacts and not r.compiled:
            failures += 1
        table.add_row(
            r.build.name,
            f"{r.build.genes_matched}/{r.build.genes_requested}",
            f"{r.build.clinvar_records:,}",
            f"{r.build.variant_rows:,}",
            f"{r.build.study_rows:,}",
            f"{r.resolved_rows:,}" if r.resolved_rows else "[yellow]no[/yellow]",
            "[green]yes[/green]" if r.compiled else "[red]no[/red]",
        )
    console.print(table)
    for r in results:
        for err in r.errors[:5]:
            console.print(f"[red]{r.build.name}: {err}[/red]")
    console.print(f"\nOutput: {out_root}\n")
    if failures:
        raise typer.Exit(1)


@app.command("pharmgkb")
def v1_pharmgkb(
    out_root: Path = typer.Option(
        Path("data/interim/v1_port"), "--out", help="Output root for the built module directory."
    ),
    snapshot: Optional[Path] = typer.Option(
        None, "--snapshot", help="ClinPGx snapshot dir. Default: the resolved cache."
    ),
    min_evidence_level: str = typer.Option(
        None, "--min-evidence-level", help="Evidence floor: 1A|1B|2A|2B|3|4. Default: 2B."
    ),
    enrich_spec: bool = typer.Option(
        True, "--enrich/--no-enrich", help="Fill resolution.csv (rsID → GRCh38 via Ensembl)."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Cache-only resolution; leaves indel/MNV VRS ids unminted."
    ),
    compile_artifacts: bool = typer.Option(
        True, "--compile/--no-compile", help="Compile parquet artifacts from resolution.csv."
    ),
) -> None:
    """Build the pharmacogenomics module from the ClinPGx clinical annotations (Gen-I just_drugs)."""
    from just_dna_pipelines.v1_port.pharmgkb import MIN_EVIDENCE_LEVEL
    from just_dna_pipelines.v1_port.pharmgkb_runner import build_and_compile_pharmgkb

    result = build_and_compile_pharmgkb(
        out_root=out_root,
        snapshot=snapshot,
        min_evidence_level=min_evidence_level or MIN_EVIDENCE_LEVEL,
        do_enrich=enrich_spec,
        do_compile=compile_artifacts,
        offline=offline,
        console=console,
    )

    table = Table(title="pharmgkb build")
    for col in ("Rows", "Annotations", "Drugs", "Genes", "Resolved", "Compiled"):
        table.add_column(col)
    table.add_row(
        f"{result.build.rows:,}",
        f"{result.build.annotations:,}",
        f"{result.build.drugs:,}",
        f"{result.build.genes:,}",
        f"{result.resolved_rows:,}" if result.resolved_rows else "[yellow]no[/yellow]",
        "[green]yes[/green]" if result.compiled else "[red]no[/red]",
    )
    console.print(table)
    for err in result.errors[:10]:
        console.print(f"[red]{err}[/red]")
    for warning in result.warnings[:10]:
        console.print(f"[yellow]{warning}[/yellow]")
    console.print(f"\nOutput: {out_root / 'pharmgkb'}\n")
    if compile_artifacts and not result.compiled:
        raise typer.Exit(1)


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
    # A module HuggingFace discovery cannot see is a refusal with an explanation, not a crash — the
    # message names the registry route instead, so a traceback would only bury it.
    try:
        plan = plan_publish(module_dir, module, repo_id)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from None

    if dry_run:
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
