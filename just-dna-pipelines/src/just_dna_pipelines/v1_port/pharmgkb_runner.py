"""
Orchestration for the pharmgkb module: draft → cross-check → resolve → compile.

Four library calls, in the order the ClinPGx reference example documents. The cross-check
(``enrich_clinpgx``) is the step with no counterpart in the ClinVar path: an ``evidence_level`` is
ClinPGx's own metadata about its own annotation, so a difference means the module is stale rather
than that two experts disagree — which is why it can be checked mechanically and, in strict mode,
refused.
"""

from pathlib import Path
from typing import Optional

from just_dna_compiler.compiler import compile_module, validate_spec
from just_dna_enricher.clinpgx import enrich_clinpgx
from just_dna_enricher.enrich import enrich
from just_dna_enricher.locations import resolve_clinpgx_reference, resolve_ensembl_reference
from pydantic import BaseModel, Field
from rich.console import Console

from just_dna_pipelines.v1_port.pharmgkb import (
    DECLARED_USE,
    MIN_EVIDENCE_LEVEL,
    MODULE_NAME,
    PharmGkbBuild,
    build_pharmgkb_module,
)

DEFAULT_OUT_ROOT = Path("data/interim/v1_port")


class PharmGkbResult(BaseModel):
    """Outcome of building the pharmgkb module end to end."""

    build: PharmGkbBuild
    valid: bool = False
    evidence_conflicts: int = 0
    resolved_rows: int = 0
    unresolved_rows: int = 0
    compiled: bool = False
    digest: Optional[str] = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def build_and_compile_pharmgkb(
    *,
    out_root: Path = DEFAULT_OUT_ROOT,
    snapshot: Optional[Path] = None,
    min_evidence_level: str = MIN_EVIDENCE_LEVEL,
    declared_use: str = DECLARED_USE,
    do_enrich: bool = True,
    do_compile: bool = True,
    offline: bool = False,
    console: Optional[Console] = None,
) -> PharmGkbResult:
    """Build ``out_root/pharmgkb/`` and take it through resolution and compilation."""
    reference = Path(snapshot) if snapshot is not None else resolve_clinpgx_reference()
    out_dir = out_root / MODULE_NAME

    if console:
        console.print(f"[cyan]{MODULE_NAME}[/cyan]: drafting from ClinPGx…")
    build = build_pharmgkb_module(
        out_dir,
        snapshot=reference,
        min_evidence_level=min_evidence_level,
        declared_use=declared_use,
    )
    result = PharmGkbResult(build=build, warnings=list(build.warnings))

    validation = validate_spec(out_dir)
    result.valid = validation.valid
    result.errors.extend(validation.errors[:20])
    result.warnings.extend(validation.warnings[:20])
    if not validation.valid:
        return result

    if console:
        console.print(f"[cyan]{MODULE_NAME}[/cyan]: cross-checking evidence levels…")
    check = enrich_clinpgx(
        out_dir, snapshot=reference, declared_use=declared_use, offline=True, download=False
    )
    result.evidence_conflicts = len(check.conflicts)
    result.warnings.extend(check.warnings[:10])
    if check.conflicts:
        result.warnings.append(
            f"{len(check.conflicts)} evidence-level disagreement(s) with ClinPGx — the module is "
            f"stale against the snapshot it was drafted from"
        )

    if do_enrich:
        if console:
            console.print(f"[cyan]{MODULE_NAME}[/cyan]: resolving rsIDs against Ensembl…")
        # Unlike the ClinVar panels, these rows carry only an rsID and no coordinate, so Ensembl is
        # the reference that resolves them. Online by default and only because the module is small
        # (≈150 loci): VRS ids for indels and MNVs need the reference *sequence*, so an offline run
        # leaves them unminted, and `--verify-rsids` needs dbSNP.
        enrichment = enrich(
            out_dir,
            offline=offline,
            ensembl_cache=resolve_ensembl_reference(),
            use_clinvar=True,
            use_gnomad=False,
            download=not offline,
        )
        result.resolved_rows = len(enrichment.rows)
        result.unresolved_rows = len(enrichment.unresolved)
        if enrichment.unresolved:
            result.warnings.append(
                f"{len(enrichment.unresolved)} variant(s) unresolved against the Ensembl cache"
            )

    if do_compile:
        if console:
            console.print(f"[cyan]{MODULE_NAME}[/cyan]: compiling…")
        # `resolve_with_ensembl` is the master switch for resolution, not a choice of reference:
        # with `ensembl_cache=None` and a `resolution.csv` present it takes the injected-table path,
        # which is the 0.5 route. Setting it False compiles every row with `chrom=None`.
        compiled = compile_module(
            out_dir,
            out_dir,
            resolve_with_ensembl=True,
            ensembl_cache=None,
            log_files=[out_dir / "pharmgkb.log"],
        )
        result.compiled = compiled.success
        if compiled.manifest is not None:
            result.digest = compiled.manifest.artifact.digest
        result.errors.extend(compiled.errors[:20])
        result.warnings.extend(compiled.warnings[:20])
    return result
