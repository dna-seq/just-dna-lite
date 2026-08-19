"""CLI entry for running annotation + report via Dagster ``execute_in_process``.

Mirrors the web UI path (same jobs and ``ops``-keyed run_config) so runs appear
in the shared Dagster UI when ``DAGSTER_HOME`` matches.
"""

from __future__ import annotations

import difflib
import os
from pathlib import Path
from typing import Annotated, Any, Optional

import typer
from dagster import DagsterInstance
from rich.console import Console

from just_dna_pipelines.annotation.assets import user_vcf_partitions
from just_dna_pipelines.annotation.hf_modules import AnnotationManifest
from just_dna_pipelines.annotation.resources import (
    ensure_vcf_in_user_input_dir,
    get_user_output_dir,
    get_workspace_root,
    list_default_sample_alias_map,
    resolve_default_sample,
)
from just_dna_pipelines.module_config import get_immutable_config
from just_dna_pipelines.runtime import load_env
from just_dna_pipelines.urls import resolve_dagster_web_public_url

console = Console()

DEFAULT_DAGSTER_HOME = "data/interim/dagster"
DEFAULT_USER = "local"


def _ensure_dagster_home() -> Path:
    """Resolve and export ``DAGSTER_HOME`` the same way other pipeline CLIs do."""
    root = get_workspace_root()
    configured = os.getenv("DAGSTER_HOME", DEFAULT_DAGSTER_HOME)
    dagster_home = Path(configured)
    if not dagster_home.is_absolute():
        dagster_home = (root / dagster_home).resolve()
    dagster_home.mkdir(parents=True, exist_ok=True)
    (dagster_home / "logs").mkdir(parents=True, exist_ok=True)
    os.environ["DAGSTER_HOME"] = str(dagster_home)
    return dagster_home


def _sample_name_from_vcf(vcf_path: Path) -> str:
    """Match partition discovery: strip ``.vcf`` / ``.vcf.gz`` from the filename."""
    name = vcf_path.name
    if name.endswith(".vcf.gz"):
        return name[: -len(".vcf.gz")]
    if name.endswith(".vcf"):
        return name[: -len(".vcf")]
    return vcf_path.stem


def _resolve_modules(
    modules: list[str],
    all_modules: bool,
    discovered: list[str],
) -> list[str]:
    """Validate ``-m`` names (or ``--all-modules``) against discovered modules."""
    if all_modules and modules:
        console.print(
            "[red]Error:[/red] pass either --all-modules or -m/--module, not both"
        )
        raise typer.Exit(1)
    if not all_modules and not modules:
        console.print(
            "[red]Error:[/red] specify at least one -m/--module, or pass --all-modules"
        )
        console.print("[dim]Run: uv run pipelines list-modules[/dim]")
        raise typer.Exit(1)

    if all_modules:
        if not discovered:
            console.print("[red]Error:[/red] no annotation modules discovered")
            raise typer.Exit(1)
        return list(discovered)

    discovered_lower = {name.lower(): name for name in discovered}
    resolved: list[str] = []
    unknown: list[str] = []
    for raw in modules:
        key = raw.strip().lower()
        if not key:
            continue
        if key in discovered_lower:
            resolved.append(discovered_lower[key])
            continue
        unknown.append(raw.strip())

    if unknown:
        for name in unknown:
            suggestions = difflib.get_close_matches(
                name.lower(),
                list(discovered_lower.keys()),
                n=3,
                cutoff=0.5,
            )
            hint = (
                f" (did you mean: {', '.join(discovered_lower[s] for s in suggestions)}?)"
                if suggestions
                else ""
            )
            console.print(f"[red]Unknown module:[/red] {name}{hint}")
        console.print("[dim]Run: uv run pipelines list-modules[/dim]")
        raise typer.Exit(1)

    # Preserve order, drop duplicates
    seen: set[str] = set()
    unique: list[str] = []
    for name in resolved:
        if name not in seen:
            seen.add(name)
            unique.append(name)
    return unique


def _default_sample_shortcuts() -> list[str]:
    """Short preferred aliases for help text (first name when available)."""
    shortcuts: list[str] = []
    seen: set[str] = set()
    for sample in get_immutable_config().default_samples:
        label = (sample.label or "").strip().lower()
        if not label:
            continue
        alias = label.split()[0]
        if alias not in seen:
            seen.add(alias)
            shortcuts.append(alias)
    return shortcuts


def _resolve_vcf_target(
    vcf: str,
    user_name: str,
) -> tuple[Path, dict[str, Any]]:
    """Resolve a path or default-sample alias to a placed VCF plus optional metadata."""
    candidate = Path(vcf).expanduser()
    if candidate.exists() and candidate.is_file():
        placed = ensure_vcf_in_user_input_dir(candidate.resolve(), user_name, log=None)
        return placed, {}

    alias_key = vcf.strip().lower()
    alias_map = list_default_sample_alias_map()
    if alias_key in alias_map:
        console.print(
            f"[dim]Resolving default sample alias {vcf!r} "
            f"({alias_map[alias_key].label})…[/dim]"
        )
        meta = resolve_default_sample(alias_key, user_name=user_name, log=None)
        return Path(meta["path"]), meta

    shortcuts = ", ".join(_default_sample_shortcuts()) or "(none configured)"
    suggestions = difflib.get_close_matches(
        alias_key,
        list(alias_map.keys()),
        n=3,
        cutoff=0.5,
    )
    hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
    console.print(
        f"[red]Error:[/red] {vcf!r} is not a VCF path and not a known sample alias.{hint}"
    )
    console.print(
        f"[dim]Pass a .vcf/.vcf.gz path, or a default-sample alias "
        f"({shortcuts}).[/dim]"
    )
    raise typer.Exit(1)


def annotate(
    vcf: Annotated[
        str,
        typer.Argument(
            help=(
                "Path to a .vcf/.vcf.gz file, or a default-sample alias "
                "(e.g. anton, livia)."
            ),
        ),
    ],
    module: Annotated[
        Optional[list[str]],
        typer.Option(
            "--module",
            "-m",
            help="Module name to run (repeatable). See: pipelines list-modules",
        ),
    ] = None,
    all_modules: Annotated[
        bool,
        typer.Option(
            "--all-modules",
            help="Run every discovered annotation module.",
        ),
    ] = False,
    user: Annotated[
        str,
        typer.Option(
            "--user",
            "-u",
            help="User id for input/output paths and the Dagster partition key.",
        ),
    ] = DEFAULT_USER,
    ensembl: Annotated[
        bool,
        typer.Option(
            "--ensembl",
            help="Also run Ensembl DuckDB annotation (annotate_all_job).",
        ),
    ] = False,
    sex: Annotated[
        Optional[str],
        typer.Option(
            "--sex",
            help="Optional sample sex metadata (Female/Male); informational only.",
        ),
    ] = None,
    reference_genome: Annotated[
        Optional[str],
        typer.Option(
            "--reference-genome",
            help=(
                "Reference genome label. Defaults to the sample metadata for "
                "aliases, otherwise GRCh38."
            ),
        ),
    ] = None,
) -> None:
    """Annotate a VCF with selected modules and generate the HTML report via Dagster.

    Uses the same jobs as the web UI (``annotate_and_report_job`` or
    ``annotate_all_job``). With Dagster UI running against the same
    ``DAGSTER_HOME``, the run is visible while this command blocks.

    ``vcf`` may be a filesystem path or a configured default-sample alias such as
    ``anton`` / ``livia`` (from ``modules.yaml`` ``immutable_mode.default_samples``).
    """
    # Discovery (and therefore network I/O) stays inside the command so importing
    # the pipelines CLI does not pay for it on every subcommand.
    from just_dna_pipelines.annotation.definitions import defs
    from just_dna_pipelines.annotation.hf_modules import DISCOVERED_MODULES

    load_env()
    _ensure_dagster_home()

    modules_to_use = _resolve_modules(
        modules=module or [],
        all_modules=all_modules,
        discovered=DISCOVERED_MODULES,
    )

    user_name = user.strip() or DEFAULT_USER
    placed_vcf, sample_meta = _resolve_vcf_target(vcf, user_name)
    sample_name = _sample_name_from_vcf(placed_vcf)
    partition_key = f"{user_name}/{sample_name}"

    resolved_sex = sex if sex is not None else sample_meta.get("sex") or None
    if resolved_sex in ("", "N/A"):
        resolved_sex = None
    resolved_reference = (
        reference_genome
        or sample_meta.get("reference_genome")
        or "GRCh38"
    )
    resolved_species = sample_meta.get("species") or "Homo sapiens"
    subject_id = sample_meta.get("subject_id") or None

    job_name = "annotate_all_job" if ensembl else "annotate_and_report_job"

    normalize_config: dict[str, Any] = {
        "vcf_path": str(placed_vcf),
    }
    if resolved_sex:
        normalize_config["sex"] = resolved_sex

    hf_config: dict[str, Any] = {
        "vcf_path": str(placed_vcf),
        "user_name": user_name,
        "sample_name": sample_name,
        "modules": modules_to_use,
        "species": resolved_species,
        "reference_genome": resolved_reference,
        "sex": resolved_sex,
    }
    if subject_id:
        hf_config["subject_id"] = subject_id

    ops_config: dict[str, Any] = {
        "user_vcf_normalized": {
            "config": normalize_config,
        },
        "user_hf_module_annotations": {
            "config": hf_config,
        },
        "user_longevity_report": {
            "config": {
                "user_name": user_name,
                "sample_name": sample_name,
                "modules": modules_to_use,
            }
        },
    }

    if ensembl:
        ops_config["user_annotated_vcf_duckdb"] = {
            "config": {
                "vcf_path": str(placed_vcf),
                "user_name": user_name,
                "sample_name": sample_name,
            }
        }

    run_config: dict[str, Any] = {"ops": ops_config}

    console.print("\n[bold]Annotation run[/bold]")
    if sample_meta.get("label"):
        console.print(f"  Sample:    {sample_meta['label']}")
    console.print(f"  VCF:       {placed_vcf}")
    console.print(f"  Partition: {partition_key}")
    console.print(f"  Job:       {job_name}")
    console.print(f"  Modules:   {', '.join(modules_to_use)}")
    console.print(f"  Dagster:   {os.environ['DAGSTER_HOME']}")
    console.print(
        f"  UI:        [cyan]{resolve_dagster_web_public_url()}[/cyan] "
        "(start with [cyan]uv run dagster-ui[/cyan] in another terminal)\n"
    )

    instance = DagsterInstance.get()
    existing = instance.get_dynamic_partitions(user_vcf_partitions.name)
    if partition_key not in existing:
        instance.add_dynamic_partitions(user_vcf_partitions.name, [partition_key])
        console.print(f"[dim]Registered partition {partition_key}[/dim]")

    job_def = defs.resolve_job_def(job_name)
    result = job_def.execute_in_process(
        run_config=run_config,
        instance=instance,
        tags={
            "dagster/partition": partition_key,
            "source": "cli",
        },
    )

    if not result.success:
        console.print(
            f"[bold red]Annotation failed[/bold red] (run_id={result.run_id})"
        )
        raise typer.Exit(1)

    sample_out = get_user_output_dir() / partition_key
    modules_dir = sample_out / "modules"
    reports_dir = sample_out / "reports"
    report_files = sorted(reports_dir.glob("*.html")) if reports_dir.exists() else []

    console.print(f"\n[bold green]Annotation complete[/bold green] (run_id={result.run_id})")
    console.print(f"  Modules: {modules_dir}")
    if report_files:
        latest_report = max(report_files, key=lambda path: path.stat().st_mtime)
        console.print(f"  Report:  {latest_report}")
    else:
        console.print(f"  Reports: {reports_dir} (no HTML report found yet)")

    _report_module_outcomes(modules_dir / "manifest.json")
    console.print()


def _report_module_outcomes(manifest_path: Path) -> None:
    """Say what each requested module actually did, reading the run's manifest.

    A module that produced nothing is a result too. The job succeeds when a module is skipped
    (an unsupported lead-table family) or fails on its own, so without this the only trace is an
    absence from the output directory — the user is told "Annotation complete" and left to notice
    that a module they asked for is simply not there.

    Best-effort: a missing or unreadable manifest is not worth failing a completed run over, since
    the annotation outputs themselves are already on disk.
    """
    if not manifest_path.exists():
        return
    manifest = AnnotationManifest.model_validate_json(manifest_path.read_text())
    for name, reason in manifest.skipped_modules.items():
        console.print(f"  [yellow]Skipped[/yellow] {name}: {reason}")
    for name, reason in manifest.failed_modules.items():
        console.print(f"  [red]Failed[/red] {name}: {reason}")
    console.print(f"  Variants annotated: {manifest.total_variants_annotated}")


def annotate_main() -> None:
    """Console-script entry for ``uv run annotate`` (no ``pipelines`` prefix)."""
    typer.run(annotate)
