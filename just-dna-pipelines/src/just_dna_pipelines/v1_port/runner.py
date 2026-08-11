"""
Orchestration for the v1 port: fetch → adapt → write spec → validate → **enrich** → compile.

Produces a standalone module directory under ``data/interim/v1_port/<module>/`` containing the
authored spec (module_spec.yaml + variants.csv + studies.csv), the enricher's ``resolution.csv``
(and ``literature.csv``), the compiled artifacts (weights/annotations/studies.parquet +
manifest.json), and a v1_port.log provenance record.

**The 0.5 change is the enrich step.** Compilation used to resolve rsIDs itself
(``compile_module(resolve_with_ensembl=True, ensembl_cache=…)``), which the compiler deprecates and
removes at 1.0: resolution is the enricher's job, the compiler is inject-only, and the artifact of
the handover is ``resolution.csv`` travelling with the module. That is what makes a rebuild offline,
reproducible and independent of whichever cache happens to be on the machine — see
``docs/MODULE_FORMAT_0_5_MIGRATION.md``.
"""

import csv
from pathlib import Path
from typing import Optional

from just_dna_enricher.enrich import enrich
from just_dna_enricher.literature import enrich_literature
from just_dna_enricher.locations import resolve_ensembl_reference
from pydantic import BaseModel, Field

from just_dna_pipelines.module_compiler.compiler import compile_module, validate_spec
from just_dna_pipelines.runtime import load_env
from just_dna_pipelines.v1_port.adapters import run_adapter
from just_dna_pipelines.v1_port.clinvar import DEFAULT_CLINVAR_VCF
from just_dna_pipelines.v1_port.sources import REGISTRY, V1Module, fetch_data_file, fetch_logo
from just_dna_pipelines.v1_port.writer import write_spec_dir

# The Ensembl variations parquet cache (rsid -> GRCh38 position). Resolved from the environment
# (`JUST_DNA_PIPELINES_CACHE_DIR`, see `pipelines ensembl-setup`) with the legacy /data path as the
# fallback, so a machine configured either way finds a complete cache rather than a partial one.
#
# `load_env()` first, and not decoratively: the enricher's resolvers evaluate their default cache
# directory as a *call argument*, before the `load_env()` inside them runs, so the very first
# resolve in a process reads platformdirs and returns None even when the env names a full cache.
# Every later call in that process is fine, which is what makes it easy to miss.
load_env()
DEFAULT_ENSEMBL_CACHE = resolve_ensembl_reference() or Path("/data/just-dna-cache/ensembl_variations")
DEFAULT_OUT_ROOT = Path("data/interim/v1_port")
DEFAULT_DOWNLOAD_CACHE = Path("data/interim/v1_port/_sources")


class PortResult(BaseModel):
    """Outcome of porting one module."""

    name: str
    output_dir: Path
    variant_count: int = 0
    study_count: int = 0
    valid: bool = False
    resolved_rows: int = 0
    unresolved_rows: int = 0
    literature_rows: int = 0
    compiled: bool = False
    digest: Optional[str] = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def port_module(
    module: V1Module,
    *,
    out_root: Path = DEFAULT_OUT_ROOT,
    download_cache: Path = DEFAULT_DOWNLOAD_CACHE,
    do_compile: bool = True,
    ensembl_cache: Optional[Path] = DEFAULT_ENSEMBL_CACHE,
    offline: bool = False,
    do_literature: bool = True,
) -> PortResult:
    """Port a single module end-to-end. Compilation is skipped gracefully if it can't run."""
    out_dir = out_root / module.name
    # Modules with no data file (pathogenic: a genome-wide ClinVar flag) skip the fetch entirely.
    db_path = fetch_data_file(module, download_cache) if module.data_path else None
    cache = ensembl_cache if (ensembl_cache and ensembl_cache.exists()) else None
    spec, variants, studies, warnings = run_adapter(module, db_path, cache)

    # For the data-less pathogenic module, pin the ClinVar release as the provenance source.
    provenance_file = db_path
    if provenance_file is None and DEFAULT_CLINVAR_VCF.exists():
        provenance_file = DEFAULT_CLINVAR_VCF
    write_spec_dir(
        spec, variants, studies, out_dir,
        source_repo=module.repo, source_file=provenance_file, warnings=warnings,
    )

    # Ship the source repo's logo alongside the artifacts — auto-discovered by hf_modules and
    # uploaded by both publish paths. Optional: modules without a source logo (e.g. vo2max) skip it.
    logo = fetch_logo(module, out_dir)
    if logo is not None:
        warnings.append(f"shipped source logo {logo.name}")

    result = PortResult(
        name=module.name, output_dir=out_dir,
        variant_count=len(variants), study_count=len(studies), warnings=list(warnings),
    )

    validation = validate_spec(out_dir)
    result.valid = validation.valid
    result.errors.extend(validation.errors)
    result.warnings.extend(validation.warnings)
    if not validation.valid:
        return result

    # A rebuild must re-resolve: `enrich` treats existing rows as authoritative and merges, so a
    # stale resolution.csv from a previous adapter run would survive an adapter fix unnoticed.
    (out_dir / "resolution.csv").unlink(missing_ok=True)
    cache = ensembl_cache if (ensembl_cache and ensembl_cache.exists()) else None
    if module.needs_ensembl:
        enrichment = enrich(
            out_dir,
            offline=offline,
            ensembl_cache=cache,
            use_clinvar=True,
            use_gnomad=not offline,
            download=not offline,
        )
        result.resolved_rows = len(enrichment.rows)
        result.unresolved_rows = len(enrichment.unresolved)
        if enrichment.unresolved:
            result.warnings.append(
                f"{len(enrichment.unresolved)} variant(s) unresolved "
                f"({', '.join(sorted(enrichment.unresolved)[:8])})"
            )
        if enrichment.stale_rsids:
            result.warnings.append(
                f"{len(enrichment.stale_rsids)} rsID(s) merged or withdrawn in dbSNP"
            )

        pruned = prune_unmatchable_rows(out_dir)
        result.warnings.extend(pruned)
        if pruned:
            # `write_spec_dir` ran before resolution, so the provenance log predates these drops.
            # Append rather than rewrite: the log is what travels with the module.
            with (out_dir / "v1_port.log").open("a", encoding="utf-8") as handle:
                handle.write("post-resolution pruning:\n")
                handle.writelines(f"  - {line}\n" for line in pruned)
            # The pruned rows changed the authored table, so the resolution table has to be
            # rebuilt from it — a resolution row for a variant that is gone is an orphan.
            (out_dir / "resolution.csv").unlink(missing_ok=True)
            enrich(
                out_dir, offline=offline, ensembl_cache=cache,
                use_clinvar=True, use_gnomad=not offline, download=not offline,
            )

    if do_literature and not offline:
        # Online only, and once written the file *is* the pin — later compiles read it offline.
        literature = enrich_literature(out_dir, offline=False)
        result.literature_rows = len(literature.rows)
        if literature.missing:
            result.warnings.append(
                f"{len(literature.missing)} cited PMID(s) PubMed has no record of: "
                f"{', '.join(literature.missing[:8])}"
            )
        if literature.doi_conflicts:
            result.warnings.append(f"{len(literature.doi_conflicts)} DOI conflict(s)")

    if do_compile:
        # Inject-only: the coordinates come from resolution.csv, never from a cache at compile time.
        # `resolve_with_ensembl` is the *master switch for resolution*, not a choice of reference —
        # with `ensembl_cache=None` it takes the injected-table path. Passing False (the intuitive
        # reading of the name) compiles every weight row with `chrom=None`, silently.
        compiled = compile_module(
            out_dir, out_dir,
            resolve_with_ensembl=True,
            ensembl_cache=None,
            log_files=[out_dir / "v1_port.log"],
        )
        result.compiled = compiled.success
        if compiled.manifest is not None:
            result.digest = compiled.manifest.artifact.digest
        result.errors.extend(compiled.errors)
        result.warnings.extend(compiled.warnings)

    return result


def prune_unmatchable_rows(spec_dir: Path) -> list[str]:
    """Drop authored rows the resolved locus cannot host, and orphan studies. Returns the report.

    Two findings the registry's **strict** pre-publish check raises as errors, both of which a
    best-effort local compile lets through:

    * *"allele(s) X are not among the resolved alleles at this locus"* — four longevitymap rows
      (`rs699 A/T` and `T/T` against a locus that is `A/G`, `rs1207362 C/C` against `G/T`,
      `rs2107538 A/A` against `C/T`). These are Generation-I curation reading a paper's strand
      rather than the reference's, and they are **not** a clean reverse-complement away: `rs699`'s
      authored pair mixes one forward-strand allele with one reverse-strand one, so no
      transformation recovers the intended genotype. The row is dropped rather than repaired,
      because a genotype whose alleles are not at the locus can never match a VCF — keeping it only
      fails the publish gate. Every drop is named here and in `v1_port.log`, and repairing them is
      curation against the original papers, not a rewrite this port can make.
    * *"Studies reference variants not in variants.csv"* — study rows for rsIDs the module does not
      weight. Harmless but noisy, and an orphan by the compiler's own definition.
    """
    variants_csv, resolution_csv = spec_dir / "variants.csv", spec_dir / "resolution.csv"
    if not resolution_csv.exists():
        return []

    alleles_at: dict[str, set[str]] = {}
    with resolution_csv.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rsid = (row.get("rsid") or "").strip()
            if not rsid:
                continue
            found = {(row.get("ref") or "").strip()} | {
                a.strip() for a in (row.get("alts") or "").split(",") if a.strip()
            }
            alleles_at.setdefault(rsid, set()).update(found - {""})

    with variants_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    kept: list[dict] = []
    dropped: list[str] = []
    for row in rows:
        rsid = (row.get("rsid") or "").strip()
        locus = alleles_at.get(rsid)
        genotype = {a for a in (row.get("genotype") or "").split("/") if a}
        if rsid and locus and genotype and not genotype <= locus:
            dropped.append(f"{rsid} {row.get('genotype')} (locus has {'/'.join(sorted(locus))})")
            continue
        kept.append(row)

    report: list[str] = []
    if dropped:
        with variants_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(kept)
        report.append(
            f"dropped {len(dropped)} row(s) whose genotype is not among the locus's resolved "
            f"alleles (Gen-I strand/curation mismatch; never matchable): {'; '.join(dropped)}"
        )

    weighted = {(r.get("rsid") or "").strip() for r in kept} - {""}
    studies_csv = spec_dir / "studies.csv"
    with studies_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        study_fields = list(reader.fieldnames or [])
        studies = list(reader)
    linked = [
        s for s in studies
        if not (s.get("rsid") or "").strip() or (s.get("rsid") or "").strip() in weighted
    ]
    if len(linked) != len(studies):
        with studies_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=study_fields)
            writer.writeheader()
            writer.writerows(linked)
        report.append(
            f"dropped {len(studies) - len(linked)} orphan study row(s) citing rsIDs the module "
            f"does not weight"
        )
    return report


#: The variant-backed ports. cardio/cancer/pathogenic are in REGISTRY too but are built by
#: `pipelines v1-port clinvar` on the enricher's ClinVar snapshot — the raw-VCF `gene_panel` adapter
#: they used is superseded (see clinvar_panel.py).
VARIANT_MODULES = (
    "coronary", "thrombophilia", "lipidmetabolism", "vo2max", "longevitymap", "superhuman",
)


def port_all(
    names: Optional[list[str]] = None,
    *,
    out_root: Path = DEFAULT_OUT_ROOT,
    download_cache: Path = DEFAULT_DOWNLOAD_CACHE,
    do_compile: bool = True,
    ensembl_cache: Optional[Path] = DEFAULT_ENSEMBL_CACHE,
    offline: bool = False,
    do_literature: bool = True,
) -> list[PortResult]:
    targets = names or list(VARIANT_MODULES)
    results: list[PortResult] = []
    for name in targets:
        module = REGISTRY[name]
        results.append(port_module(
            module, out_root=out_root, download_cache=download_cache,
            do_compile=do_compile, ensembl_cache=ensembl_cache,
            offline=offline, do_literature=do_literature,
        ))
    return results
