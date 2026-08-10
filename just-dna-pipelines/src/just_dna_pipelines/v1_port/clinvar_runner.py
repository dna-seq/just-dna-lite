"""
Orchestration for the ClinVar modules: gene list → draft → fill → resolve → compile.

The three steps after drafting are deliberately separate library calls rather than one
``compile_module(resolve_with_ensembl=True)``: 0.5 makes resolution the enricher's job and the
compiler inject-only, so this runner produces ``resolution.csv`` from the **same ClinVar snapshot**
the variants were drafted from and then compiles offline. Ensembl is not involved at all — ClinVar
carries the coordinates — which is why these modules build while an Ensembl cache is still syncing.
"""

from pathlib import Path
from typing import Optional

from just_dna_compiler.compiler import compile_module, validate_spec
from just_dna_enricher.enrich import enrich
from just_dna_enricher.locations import resolve_clinvar_reference
from pydantic import BaseModel, Field
from rich.console import Console

from just_dna_pipelines.v1_port.clinvar_panel import (
    MIN_REVIEW_STARS,
    PanelBuild,
    build_clinvar_module,
    panel_genes,
)
from just_dna_pipelines.v1_port.sources import REGISTRY, fetch_data_file, fetch_logo
from just_dna_pipelines.v1_port.symbols import load_symbol_resolver, resolve_panel_genes

DEFAULT_OUT_ROOT = Path("data/interim/v1_port")
DEFAULT_DOWNLOAD_CACHE = Path("data/interim/v1_port/_sources")

#: Ensembl is deliberately unreachable for these builds. ClinVar supplies every coordinate, and
#: pointing the resolver at a cache would let a coordinate arrive from a second source — which would
#: make the compiled bytes depend on which cache happened to be present.
_NO_ENSEMBL = Path("/nonexistent")


class ClinVarModuleResult(BaseModel):
    """Outcome of building one ClinVar module end to end."""

    build: PanelBuild
    valid: bool = False
    resolved_rows: int = 0
    unresolved_rows: int = 0
    compiled: bool = False
    digest: Optional[str] = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def module_gene_list(name: str, download_cache: Path) -> tuple[list[str], dict[str, str], list[str]]:
    """The panel's gene symbols, reconciled to the current NCBI symbols ClinVar publishes.

    ``pathogenic`` has no authored gene list — Gen-I's ``just_pathogenic`` shipped no data at all —
    so its list is derived from the snapshot selection itself (see :func:`panel_genes`).
    """
    if name == "pathogenic":
        reference = resolve_clinvar_reference()
        if reference is None:
            raise FileNotFoundError(
                "no ClinVar snapshot found; provision it with "
                "`just-dna-enricher cache pull --only clinvar`."
            )
        return panel_genes(reference), {}, []

    module = REGISTRY[name]
    gene_file = fetch_data_file(module, download_cache)
    raw = {line.strip() for line in gene_file.read_text().splitlines() if line.strip()}
    wanted, alias_map, unresolved = resolve_panel_genes(raw, load_symbol_resolver())
    return sorted(wanted), alias_map, unresolved


def build_clinvar_modules(
    names: list[str],
    *,
    out_root: Path = DEFAULT_OUT_ROOT,
    download_cache: Path = DEFAULT_DOWNLOAD_CACHE,
    snapshot: Optional[Path] = None,
    min_review_stars: Optional[int] = None,
    do_enrich: bool = True,
    do_compile: bool = True,
    console: Optional[Console] = None,
) -> list[ClinVarModuleResult]:
    """Build each named ClinVar module into ``out_root/<name>/``."""
    stars = MIN_REVIEW_STARS if min_review_stars is None else min_review_stars
    reference = Path(snapshot) if snapshot is not None else resolve_clinvar_reference()
    results: list[ClinVarModuleResult] = []
    for name in names:
        if console:
            console.print(f"[cyan]{name}[/cyan]: resolving gene list…")
        genes, alias_map, unresolved = module_gene_list(name, download_cache)

        if console:
            console.print(f"[cyan]{name}[/cyan]: drafting from ClinVar ({len(genes):,} gene(s))…")
        build = build_clinvar_module(
            name,
            genes,
            out_root / name,
            reference=reference,
            min_review_stars=stars,
            alias_remaps=alias_map,
            unresolved_symbols=unresolved,
        )
        # The Gen-I repo's logo, carried into the module the way the variant-backed ports do.
        if name in REGISTRY:
            fetch_logo(REGISTRY[name], build.output_dir)
        results.append(_finish(build, reference, do_enrich=do_enrich, do_compile=do_compile,
                               console=console))
    return results


def _finish(
    build: PanelBuild,
    reference: Optional[Path],
    *,
    do_enrich: bool,
    do_compile: bool,
    console: Optional[Console],
) -> ClinVarModuleResult:
    result = ClinVarModuleResult(build=build, warnings=list(build.warnings))
    if build.unfilled_placeholders:
        result.errors.append(
            f"{build.unfilled_placeholders} row(s) still carry a genotype placeholder"
        )

    validation = validate_spec(build.output_dir)
    result.valid = validation.valid
    result.errors.extend(validation.errors[:20])
    result.warnings.extend(validation.warnings[:20])
    if not validation.valid:
        return result

    if do_enrich:
        if console:
            console.print(f"[cyan]{build.name}[/cyan]: resolving from the ClinVar snapshot…")
        # One call, whole panel. Until enricher 0.5.2 this had to be sliced into 10k-row batches:
        # the ClinVar reader OR-chained one predicate per allele, which DuckDB could not hash, so
        # cost grew with alleles × rows and `cardio` never finished. 0.5.2 joins a probe table
        # instead — 76,078 rows now resolve in 13 s, and the rate *improves* with size.
        enrichment = enrich(
            build.output_dir,
            offline=True,
            ensembl_cache=_NO_ENSEMBL,
            clinvar_cache=reference,
            use_clinvar=True,
            use_gnomad=False,
            download=False,
        )
        result.resolved_rows = len(enrichment.rows)
        result.unresolved_rows = len(enrichment.unresolved)
        # The `clin_sig` cross-check is tautological for a panel drafted from the snapshot it is
        # checked against, and 0.5.2 detects that from the `panel:` pin and skips it — but only on
        # an established match, so a hand-authored module or one pinned to another release still
        # gets checked. Record which happened; an empty conflict list alone is ambiguous.
        if getattr(enrichment, "clin_sig_not_checked", None):
            result.warnings.append(f"clin_sig not checked: {enrichment.clin_sig_not_checked}")
        elif enrichment.clin_sig_conflicts:
            result.warnings.append(
                f"{len(enrichment.clin_sig_conflicts)} clin_sig conflict(s) against the snapshot"
            )
        if enrichment.unresolved:
            result.warnings.append(
                f"{len(enrichment.unresolved)} variant(s) unresolved against the ClinVar snapshot"
            )

    if do_compile:
        if console:
            console.print(f"[cyan]{build.name}[/cyan]: compiling…")
        # Master switch for resolution, not a choice of reference: with `ensembl_cache=None` and a
        # `resolution.csv` present it takes the injected-table path (no reference, no network).
        compiled = compile_module(
            build.output_dir,
            build.output_dir,
            resolve_with_ensembl=True,
            ensembl_cache=None,
            log_files=[build.output_dir / "clinvar_panel.log"],
        )
        result.compiled = compiled.success
        if compiled.manifest is not None:
            result.digest = compiled.manifest.artifact.digest
        result.errors.extend(compiled.errors[:20])
        result.warnings.extend(compiled.warnings[:20])
    return result
