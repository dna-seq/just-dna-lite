"""
The pharmacogenomics module (Gen-I ``just_drugs``), rebuilt on the 0.5 ClinPGx surface.

Generation-I shipped ``data/annotation_tab.tsv`` — 1,063 PharmGKB **variant** annotations, one row
per published study finding, with no evidence grading and with "Significance: no" rows mixed in.
There was no schema for drug response, so the module was never migrated (``docs/V1_PARITY.md`` §6,
format ROADMAP item 9).

0.5 supplies both halves: ``pharm_variants.csv`` (``PharmVariantRow``) models a drug-response row
keyed by ``(variant, drug, genotype, phenotype_category, annotation_id)``, and the enricher builds a
ClinPGx snapshot of the **clinical** annotations — PharmGKB's aggregated, evidence-levelled reading
of all the studies behind a variant/drug pair, which is the thing a report should show.

**What this module is.** Every ClinPGx clinical annotation at evidence level 1A/1B/2A/2B that is
keyed to an rsID: the tier PharmGKB describes as having a variant-drug association replicated in
significant studies, with 1A/1B additionally appearing in a prescribing guideline or label. Level 3
(single study / unreplicated, 13,631 rows) and 4 (case reports) are deliberately excluded — Gen-I's
table drew no such line, and drawing it is most of the upgrade.

**Licensing is machine-readable and restrictive.** ClinPGx is CC BY-SA 4.0 *plus* a contractual bar
on sale, so ``licensing.csv`` records ``commercial_use=false`` and the compiler refuses to build
without that declaration. The module is therefore **not sellable**, and says so in the artifact.
"""

import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import polars as pl
import yaml
from just_dna_enricher.clinpgx import load_snapshot
from just_dna_enricher.clinpgx_draft import ClinPgxDraftResult, draft_pharm_variants
from just_dna_enricher.locations import resolve_clinpgx_reference
from just_dna_format.layout import SOURCES_CSV, sidecar_candidates
from pydantic import BaseModel, Field

from just_dna_pipelines.v1_port.sources import display_meta

MODULE_NAME = "pharmgkb"

#: The Gen-I repo this module supersedes. It ships no curated data we read (the rows come
#: from the ClinPGx snapshot), but it does ship the logo the ported module carries.
GEN1_REPO = "just_drugs"

#: Evidence floor. ClinPGx grades 1A > 1B > 2A > 2B > 3 > 4; this keeps the four replicated tiers.
MIN_EVIDENCE_LEVEL = "2B"

#: ClinPGx forbids sale, so the use must be declared before the data is read. Non-commercial is the
#: only declaration that both permits the read and matches what this module is for.
DECLARED_USE = "non_commercial"

#: ClinPGx's own annotation sentence can be long; a conclusion cell that is a page of prose is not
#: readable in a report. Truncated on a sentence boundary, never mid-word, and only when it must be.
MAX_CONCLUSION_CHARS = 600

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


class PharmGkbBuild(BaseModel):
    """What one pharmgkb build produced."""

    output_dir: Path
    rows: int = 0
    annotations: int = 0
    drugs: int = 0
    genes: int = 0
    conclusions_filled: int = 0
    release: str = ""
    warnings: list[str] = Field(default_factory=list)


def _trim(text: str, limit: int = MAX_CONCLUSION_CHARS) -> str:
    """ClinPGx's sentence, cut at a sentence boundary when it exceeds ``limit``.

    Falls back to a word boundary when the *first* sentence is already over the limit — ClinPGx has
    single sentences that long, and a sentence-boundary cut that keeps the whole text is not a cut.
    """
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    kept: list[str] = []
    for sentence in _SENTENCE_END.split(text):
        candidate = " ".join(kept + [sentence])
        if kept and len(candidate) > limit:
            break
        kept.append(sentence)
    joined = " ".join(kept)
    if joined and len(joined) <= limit:
        return joined
    return text[:limit].rsplit(" ", 1)[0] + " …"


def enrich_drafted_rows(spec_dir: Path, snapshot: Path) -> tuple[int, int, int]:
    """Fill ``gene`` and replace the placeholder ``conclusion`` with ClinPGx's own sentence.

    ``draft_pharm_variants`` writes a terse identity line ("ClinPGx 1043880818: C/C and atorvastatin
    — toxicity") because the provider states only what it is willing to assert about identity. The
    snapshot carries the annotation's published text, which is the thing a reader needs, so it is
    transcribed here verbatim (trimmed on a sentence boundary) rather than summarized. ``gene`` comes
    from the same record.

    Returns ``(rows, conclusions_filled, genes_filled)``.

    Note this reads the snapshot **parquet** rather than ``clinpgx.load_snapshot``: that helper
    returns the reduced projection the cross-check needs (id, rsid, genotype, level, category,
    drugs) and drops exactly the two columns wanted here.
    """
    frame = pl.read_parquet(
        snapshot / "data" / "annotations.parquet",
        columns=["annotation_id", "genotype", "gene", "annotation_text"],
    )
    by_key: dict[tuple[str, str], tuple[str, str]] = {}
    for record in frame.iter_rows(named=True):
        key = (
            str(record["annotation_id"] or ""),
            (record["genotype"] or "").strip(),
        )
        by_key.setdefault(key, ((record["gene"] or "").strip(), (record["annotation_text"] or "")))

    pharm_csv = spec_dir / "pharm_variants.csv"
    with pharm_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if "gene" not in fieldnames:
        fieldnames.insert(fieldnames.index("drug"), "gene")

    filled_conclusions = 0
    filled_genes = 0
    for row in rows:
        # The drafted genotype is the canonical sorted form ('C/T'); the snapshot's is the raw
        # ClinPGx spelling ('CT'). Match on both so neither spelling misses.
        genotype = (row.get("genotype") or "").strip()
        annotation_id = row.get("annotation_id") or ""
        found = by_key.get((annotation_id, genotype)) or by_key.get(
            (annotation_id, genotype.replace("/", ""))
        )
        if found is None:
            continue
        gene, text = found
        if text.strip():
            row["conclusion"] = _trim(text)
            filled_conclusions += 1
        if gene and not (row.get("gene") or "").strip():
            row["gene"] = gene
            filled_genes += 1

    with pharm_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows), filled_conclusions, filled_genes


def _module_spec_yaml(release: dict[str, object], row_count: int) -> str:
    # Display metadata is owned by modules.yaml, never by a Python literal — the app and the module
    # must agree on the title a report is headed with.
    meta = display_meta(MODULE_NAME)
    spec: dict[str, object] = {
        "schema_version": "1.0",
        "module": {
            "name": MODULE_NAME,
            "title": meta["title"],
            "description": meta["description"],
            "report_title": meta["report_title"],
            "icon": meta["icon"],
            "color": meta["color"],
            "version": "1.0.0",
        },
        "license": "CC-BY-SA-4.0",
        "genome_build": "GRCh38",
        "authorship": [
            {"who": "just-dna-seq", "role": "created", "kind": ["human", "ai"]},
        ],
    }
    header = (
        f"# Built by `pipelines v1-port pharmgkb` from the ClinPGx snapshot "
        f"{release.get('dataset', '?')}\n"
        f"# ({row_count:,} rows, evidence level >= {MIN_EVIDENCE_LEVEL}). ClinPGx is CC BY-SA 4.0 "
        f"and may not be sold — see licensing.csv.\n"
    )
    return header + yaml.safe_dump(spec, sort_keys=False, allow_unicode=True)


def build_pharmgkb_module(
    out_dir: Path,
    *,
    snapshot: Optional[Path] = None,
    min_evidence_level: str = MIN_EVIDENCE_LEVEL,
    declared_use: str = DECLARED_USE,
) -> PharmGkbBuild:
    """Draft, enrich and record the pharmgkb module into ``out_dir``."""
    reference = Path(snapshot) if snapshot is not None else resolve_clinpgx_reference()
    if reference is None:
        raise FileNotFoundError(
            "no ClinPGx snapshot found. Provision it with `just-dna-enricher cache pull "
            "--only clinpgx --use non-commercial`."
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in ("pharm_variants.csv", "resolution.csv"):
        (out_dir / stale).unlink(missing_ok=True)
    # Cleared through `layout` rather than by name — see `clinvar_panel.build_clinvar_module` for the
    # measured case a literal unlink misses: a `derived/sources.csv` it cannot reach becomes the copy
    # the drafter merges into, so the module keeps the deprecated spelling permanently.
    for stale_path in sidecar_candidates(out_dir, SOURCES_CSV):
        stale_path.unlink(missing_ok=True)

    _records, release = load_snapshot(reference)
    (out_dir / "module_spec.yaml").write_text(_module_spec_yaml(release, 0), encoding="utf-8")

    result: ClinPgxDraftResult = draft_pharm_variants(
        out_dir,
        snapshot=reference,
        min_evidence_level=min_evidence_level,
        declared_use=declared_use,
    )
    rows, filled_conclusions, _filled_genes = enrich_drafted_rows(out_dir, reference)
    (out_dir / "module_spec.yaml").write_text(_module_spec_yaml(release, rows), encoding="utf-8")

    frame = pl.read_csv(out_dir / "pharm_variants.csv", infer_schema_length=0)
    build = PharmGkbBuild(
        output_dir=out_dir,
        rows=rows,
        annotations=frame["annotation_id"].n_unique(),
        drugs=frame["drug"].n_unique(),
        genes=frame["gene"].drop_nulls().n_unique() if "gene" in frame.columns else 0,
        conclusions_filled=filled_conclusions,
        release=str(release.get("dataset") or ""),
        warnings=list(result.warnings),
    )
    _write_log(out_dir, build, release, reference, min_evidence_level, declared_use)
    return build


def _write_log(
    out_dir: Path,
    build: PharmGkbBuild,
    release: dict[str, object],
    snapshot: Path,
    min_evidence_level: str,
    declared_use: str,
) -> None:
    lines = [
        f"module: {MODULE_NAME}",
        "route: just-dna-enricher clinpgx_draft.draft_pharm_variants (0.5 snapshot)",
        "supersedes: dna-seq/just_drugs data/annotation_tab.tsv (PharmGKB variant annotations)",
        f"snapshot: {snapshot}",
        f"clinpgx_release: {release.get('dataset', '?')}",
        f"clinpgx_source_sha256: sha256:{release.get('source_sha256', '?')}",
        f"min_evidence_level: {min_evidence_level}",
        f"declared_use: {declared_use}",
        f"rows: {build.rows}",
        f"clinical_annotations: {build.annotations}",
        f"drugs: {build.drugs}",
        f"genes: {build.genes}",
        f"conclusions_from_source_text: {build.conclusions_filled}",
        f"built_at: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "warnings:",
    ]
    lines += [f"  - {w}" for w in build.warnings] or ["  (none)"]
    (out_dir / "pharmgkb.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
