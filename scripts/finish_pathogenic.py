"""
Resume `pathogenic` from its authored spec: validate → resolve (batched) → compile.

Separate from `pipelines v1-port clinvar --module pathogenic` because that command re-drafts first,
and drafting 305,850 ClinVar records across 4,793 genes is half an hour this does not need to spend
when `data/interim/v1_port/pathogenic/` already holds a complete, correct `variants.csv` +
`studies.csv` + `sources.csv`.

    uv run python scripts/finish_pathogenic.py
"""

import sys
from pathlib import Path

from just_dna_compiler.compiler import compile_module, validate_spec
from just_dna_enricher.enrich import enrich
from just_dna_enricher.locations import resolve_clinvar_reference
from rich.console import Console

from just_dna_pipelines.runtime import load_env
from just_dna_pipelines.v1_port.clinvar_runner import _NO_ENSEMBL

MODULE_DIR = Path("data/interim/v1_port/pathogenic")


def main() -> int:
    load_env()
    console = Console()
    reference = resolve_clinvar_reference()
    if reference is None:
        console.print("[red]no ClinVar snapshot found[/red]")
        return 2

    console.print("validating the authored spec…")
    validation = validate_spec(MODULE_DIR)
    if not validation.valid:
        for error in validation.errors[:10]:
            console.print(f"[red]{error}[/red]")
        return 1
    console.print(f"valid — {validation.stats.get('variant_count', '?')} variants")

    console.print("resolving against the ClinVar snapshot…")
    enrichment = enrich(
        MODULE_DIR, offline=True, ensembl_cache=_NO_ENSEMBL, clinvar_cache=reference,
        use_clinvar=True, use_gnomad=False, download=False,
    )
    console.print(
        f"resolution.csv: {len(enrichment.rows):,} rows, "
        f"{len(enrichment.unresolved):,} unresolved"
    )

    console.print("compiling…")
    result = compile_module(
        MODULE_DIR,
        MODULE_DIR,
        resolve_with_ensembl=True,
        ensembl_cache=None,
        log_files=[MODULE_DIR / "clinvar_panel.log"],
    )
    for warning in result.warnings[:10]:
        console.print(f"[yellow]{warning}[/yellow]")
    for error in result.errors[:10]:
        console.print(f"[red]{error}[/red]")
    if not result.success:
        return 1
    console.print(f"[green]compiled[/green] digest {result.manifest.artifact.digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
