"""
ClinVar-backed modules on the 0.5 enricher machinery (cardio / cancer / pathogenic).

This replaces the Generation-I re-port route (``v1_port/clinvar.py`` — a raw ClinVar VCF scan that
baked coordinates into ``variants.csv`` and grounded every variant on the single ClinVar resource
paper). The 0.5 route instead drives ``just_dna_enricher.clinvar_draft.draft_gene_panel`` over the
published ClinVar **parquet snapshot**, which changes five things:

1. Variants are authored **by identity** (rsID, or the whole coordinate when an rsID names more than
   one allele at its locus), never by baked coordinate. ``just-dna-enricher enrich`` fills
   ``resolution.csv`` from the same snapshot, so the compile is offline and reproducible.
2. Every row carries a typed ``clin_sig`` from the closed ``VALID_CLIN_SIG`` vocabulary, so the
   module is checkable against the source it was built from (``enrich --verify-clinsig``).
3. A **review-status floor** applies. Gen-I mixed 0★ "no assertion criteria provided" submissions in
   silently; ``MIN_REVIEW_STARS`` states the floor and the panel declaration records it.
4. Grounding is **per variant**, from ClinVar's own literature links, instead of one blanket
   citation of the ClinVar resource paper for every row.
5. ``licensing.csv`` records ClinVar's terms, and ``module_spec.yaml`` carries a ``panel:`` block
   (``GenePanelSpec``) pinning the reference release and the significance predicate.

**The one judgement this module makes.** ``draft_gene_panel`` deliberately leaves ``genotype`` as a
``<<REPLACE>>`` placeholder: ClinVar publishes alleles, and whether carrying one is a carrier state
or an affected one follows from the condition's inheritance mode, which the source does not state.
A genome-wide panel cannot be hand-curated row by row, so :func:`fill_genotypes` expands each stub
into the **two genotypes a diploid caller can emit** for that allele — heterozygous ``ref/alt`` and
homozygous ``alt/alt`` — and says so in the conclusion. That is a transcription of zygosity, not a
claim about its clinical consequence, and it is the same shape the Gen-I modules had (both rows).
"""

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

import duckdb
import yaml
from just_dna_enricher.clinvar import select_by_gene
from just_dna_enricher.clinvar_draft import (
    DEFAULT_CLIN_SIG,
    ClinVarDraftResult,
    draft_gene_panel,
    multi_allelic_rsids,
)
from just_dna_enricher.locations import resolve_clinvar_reference
from just_dna_format.layout import SOURCES_CSV, sidecar_candidates
from pydantic import BaseModel, Field

from just_dna_pipelines.v1_port.sources import display_meta

#: Review-status floor for every ClinVar module here. 1 = "criteria provided, single submitter" —
#: it drops only the 0★ submissions that assert no criteria at all. The enricher's own default is 2
#: ("multiple submitters, no conflicts"), which is the better floor for a *clinical* panel but
#: discards ~72% of ClinVar's pathogenic set; these modules are pathogenicity **flags** whose Gen-I
#: predecessors had no floor at all, so 1 keeps the coverage while removing the un-criteria'd rows.
MIN_REVIEW_STARS = 1

#: Calls a pathogenicity flag is drawn from — Gen-I's ``_is_pathogenic`` rule, typed.
PANEL_CLIN_SIG = DEFAULT_CLIN_SIG  # {"pathogenic", "likely_pathogenic"}

#: ClinVar literature links drafted per variant. Three is the enricher's default and plenty for a
#: flag module; the number dropped is reported rather than silently truncated.
MAX_CITATIONS = 3

#: The placeholder ``draft_gene_panel`` writes into every cell it refuses to decide.
PLACEHOLDER = "<<REPLACE>>"

#: The ClinVar resource paper (Landrum et al., NAR 2018) — the grounding for a variant ClinVar
#: aggregates but links no literature to. Gen-I used it for every row; here it is the fallback only.
CLINVAR_RESOURCE_PMID = "29165669"

#: What `StudyRow.pmid` accepts (``just_dna_format.spec.PMID_PATTERN`` is ``\\b(\\d{1,8})\\b``).
#: The snapshot's citations table needs filtering against it — see :func:`draft_studies`.
_PMID_RE = re.compile(r"^\d{1,8}$")

_GENOTYPE_NOTE = {
    "het": "heterozygous (one copy)",
    "hom": "homozygous (two copies)",
}


class PanelBuild(BaseModel):
    """What one ClinVar module build produced."""

    name: str
    output_dir: Path
    genes_requested: int = 0
    genes_matched: int = 0
    clinvar_records: int = 0
    variant_rows: int = 0
    study_rows: int = 0
    unfilled_placeholders: int = 0
    alias_remaps: dict[str, str] = Field(default_factory=dict)
    unresolved_symbols: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def snapshot_release(reference: Path) -> dict[str, object]:
    """The snapshot's ``release.json`` — the reference identity a ``panel:`` block pins."""
    release_file = reference / "release.json"
    if not release_file.exists():
        return {}
    return json.loads(release_file.read_text(encoding="utf-8"))


def panel_genes(
    reference: Path,
    *,
    clin_sig: frozenset[str] = PANEL_CLIN_SIG,
    min_review_stars: int = MIN_REVIEW_STARS,
) -> list[str]:
    """Every gene the selection touches — the genome-wide ``pathogenic`` module's gene list.

    ``select_by_gene`` filters by an explicit gene set and returns nothing for an empty one, so a
    genome-wide module derives its list from the snapshot itself. That is the same set Gen-I's
    ``pathogenic`` reached (it required a ``GENEINFO`` gene too), only stated instead of implied.
    """
    files = sorted(str(p) for p in (reference / "data").glob("*.parquet"))
    con = duckdb.connect()
    try:
        con.execute(f"CREATE VIEW clinvar AS SELECT * FROM read_parquet({files!r})")
        params: list[object] = sorted(clin_sig)
        clause = f"clin_sig IN ({', '.join('?' for _ in clin_sig)})"
        if min_review_stars:
            clause += " AND review_stars >= ?"
            params.append(min_review_stars)
        rows = con.execute(
            f"SELECT DISTINCT gene FROM clinvar WHERE {clause} AND gene IS NOT NULL ORDER BY gene",
            params,
        ).fetchall()
    finally:
        con.close()
    return [r[0] for r in rows]


def _allele_index(records: Iterable[dict], ambiguous: set[str]) -> dict[tuple, tuple[str, str]]:
    """Map each drafted row's identity to the ``(ref, alt)`` its genotype is written from.

    The identity is the rsID when the draft kept one, else the full coordinate — mirroring
    ``clinvar_draft._identity_cells``, which forces the coordinate for an rsID that names several
    alleles at one locus. Keyed the same way so a filled row is matched to the record it came from.
    """
    index: dict[tuple, tuple[str, str]] = {}
    for record in records:
        ref, alt = (record.get("ref") or "").strip(), (record.get("alt") or "").strip()
        if not (ref and alt):
            continue
        rsid = (record.get("rsid") or "").strip()
        if rsid and rsid not in ambiguous:
            index.setdefault(("rsid", rsid), (ref, alt))
        else:
            key = ("coord", str(record.get("chrom") or ""), str(record.get("start") or ""), ref, alt)
            index.setdefault(key, (ref, alt))
    return index


def _row_key(row: dict) -> Optional[tuple]:
    rsid = (row.get("rsid") or "").strip()
    if rsid:
        return ("rsid", rsid)
    chrom, start = (row.get("chrom") or "").strip(), (row.get("start") or "").strip()
    ref, alts = (row.get("ref") or "").strip(), (row.get("alts") or "").strip()
    if chrom and start and ref and alts:
        return ("coord", chrom, start, ref, alts)
    return None


def fill_genotypes(spec_dir: Path, records: list[dict]) -> tuple[int, int]:
    """Expand each ``<<REPLACE>>`` genotype into the two zygosities a diploid caller can emit.

    Heterozygous ``ref/alt`` and homozygous ``alt/alt``. Only placeholders are touched, so a row the
    provider already decided passes through untouched — which is how the non-diploid contigs are
    handled: since enricher 0.5.2, ``draft_gene_panel`` writes the sole expressible genotype itself
    on the mitochondrial genome and on hemizygous chrY, leaving the stub only where a zygosity
    judgement genuinely remains. It decides chrY **per locus** against the pseudoautosomal regions,
    which is finer than treating the whole contig as hemizygous.

    Returns ``(rows_written, rows_left_unfilled)``. A stub whose alleles cannot be found is left
    exactly as it is — an unfilled placeholder fails the compile loudly, which is the right outcome
    for a row nothing can be written from.
    """
    variants_csv = spec_dir / "variants.csv"
    with variants_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    ambiguous = multi_allelic_rsids(records)
    index = _allele_index(records, ambiguous)

    out_rows: list[dict] = []
    unfilled = 0
    for row in rows:
        if (row.get("genotype") or "").strip() != PLACEHOLDER:
            out_rows.append(row)
            continue
        alleles = index.get(_row_key(row) or ())
        if alleles is None:
            unfilled += 1
            out_rows.append(row)
            continue
        ref, alt = alleles
        base_conclusion = (row.get("conclusion") or "").strip()
        # An unphased genotype is alphabetically sorted (`VariantRow` enforces it) — the pair is a
        # set, so `A/G` and `G/A` would otherwise be two spellings of one call.
        het = "/".join(sorted((ref, alt)))
        for zygosity, genotype in (("het", het), ("hom", f"{alt}/{alt}")):
            filled = dict(row)
            filled["genotype"] = genotype
            filled["conclusion"] = f"{base_conclusion} | genotype: {_GENOTYPE_NOTE[zygosity]}"
            out_rows.append(filled)

    with variants_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)
    return len(out_rows), unfilled


def draft_studies(
    spec_dir: Path,
    reference: Path,
    records: list[dict],
    *,
    max_citations: int = MAX_CITATIONS,
) -> tuple[int, int, list[str]]:
    """Write ``studies.csv`` from ClinVar's own literature links. Returns ``(rows, dropped, notes)``.

    **Why this is here rather than left to the enricher.** ``draft_gene_panel`` drafts study rows
    itself, and on a real panel it raises: the snapshot's citations table carries ClinVar's
    ``var_citations.txt`` verbatim, which mixes 632k PubMedCentral ids and a handful of malformed
    "PubMed" ones (ClinVar Variation 12606 cites ``168335863``, nine digits) in with the real PMIDs,
    and ``StudyRow.pmid`` accepts at most eight — so one bad row in one gene aborts the whole draft
    with an unhandled ``ValidationError``. Reported upstream; here the panel drafts its own studies
    with ``max_citations=0`` on the provider, filtering to ids the model can actually hold.

    A variant ClinVar links no usable literature to is grounded on the ClinVar resource paper — the
    honest citation for an aggregate classification, and what Gen-I used for every row.
    """
    citations_file = reference / "citations" / "citations.parquet"
    ambiguous = multi_allelic_rsids(records)
    wanted = {str(r.get("variation_id") or "") for r in records} - {""}

    links: dict[str, list[str]] = {}
    malformed = 0
    if citations_file.exists() and wanted:
        con = duckdb.connect()
        try:
            con.execute("CREATE TABLE wanted (variation_id VARCHAR)")
            con.executemany("INSERT INTO wanted VALUES (?)", [(v,) for v in sorted(wanted)])
            rows = con.execute(
                "SELECT c.variation_id, c.pmid FROM read_parquet(?) c "
                "JOIN wanted w ON w.variation_id = c.variation_id "
                "ORDER BY c.variation_id, c.pmid",
                [str(citations_file)],
            ).fetchall()
        finally:
            con.close()
        for variation_id, pmid in rows:
            text = (pmid or "").strip()
            if not _PMID_RE.match(text):
                malformed += 1
                continue
            links.setdefault(variation_id, []).append(text)

    study_rows: list[dict] = []
    seen: set[tuple] = set()
    dropped = 0
    grounded_on_resource = 0
    for record in records:
        rsid = (record.get("rsid") or "").strip() or None
        if rsid in ambiguous:
            rsid = None
        identity = (
            {"rsid": rsid, "chrom": "", "start": "", "ref": ""}
            if rsid
            else {
                "rsid": "",
                "chrom": str(record.get("chrom") or ""),
                "start": str(record.get("start") or ""),
                "ref": (record.get("ref") or "").strip(),
            }
        )
        pmids = links.get(str(record.get("variation_id") or ""), [])
        if not pmids:
            pmids = [CLINVAR_RESOURCE_PMID]
            grounded_on_resource += 1
        else:
            dropped += max(0, len(pmids) - max_citations)
        for pmid in pmids[:max_citations] if max_citations else pmids[:1]:
            key = (identity["rsid"], identity["chrom"], identity["start"], pmid)
            if key in seen:
                continue
            seen.add(key)
            study_rows.append({**identity, "pmid": pmid})

    with (spec_dir / "studies.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["rsid", "chrom", "start", "ref", "pmid"])
        writer.writeheader()
        writer.writerows(study_rows)

    notes: list[str] = []
    if malformed:
        notes.append(
            f"{malformed} ClinVar citation id(s) are not PMIDs the format can hold "
            f"(PubMedCentral ids and malformed entries) — dropped"
        )
    if dropped:
        notes.append(f"{dropped} further ClinVar citation(s) beyond --max-citations {max_citations}")
    if grounded_on_resource:
        notes.append(
            f"{grounded_on_resource} variant(s) have no ClinVar literature link and are grounded "
            f"on the ClinVar resource paper (PMID {CLINVAR_RESOURCE_PMID})"
        )
    return len(study_rows), dropped, notes


def _module_spec_yaml(
    name: str, genes: list[str], release: dict[str, object], record_count: int
) -> str:
    """``module_spec.yaml`` for a ClinVar module, including the ``panel:`` declaration.

    ``panel.genes`` is left empty for the genome-wide module — ``GenePanelSpec`` documents empty as
    "no gene filter", which is what ``pathogenic`` is. Listing its 4,793 derived symbols there would
    read as a curated panel it is not.
    """
    meta = display_meta(name)
    genome_wide = name == "pathogenic"
    source_sha = release.get("source_sha256")
    spec: dict[str, object] = {
        "schema_version": "1.0",
        "module": {
            "name": name,
            "title": meta["title"],
            "description": meta["description"],
            "report_title": meta["report_title"],
            "icon": meta["icon"],
            "color": meta["color"],
            "version": "1.0.0",
        },
        # Spelled exactly as the ClinVar SourceRow spells it, so the compiler's licence cross-check
        # sees a matching pair. `CC0-1.0` is the same grant in substance and still trips the check.
        "license": "public-domain",
        "genome_build": "GRCh38",
        "panel": {
            "source": "clinvar",
            "reference": str(release.get("clinvar_file_date") or "unknown"),
            "reference_sha256": f"sha256:{source_sha}" if source_sha else None,
            "genes": [] if genome_wide else sorted(genes),
            "significance": sorted(PANEL_CLIN_SIG),
        },
        "authorship": [
            {"who": "just-dna-seq", "role": "created", "kind": ["human", "ai"]},
        ],
    }
    header = (
        f"# Built by `pipelines v1-port clinvar --module {name}` from the ClinVar snapshot\n"
        f"# release {release.get('clinvar_file_date', '?')} "
        f"({record_count:,} matching records, review_stars >= {MIN_REVIEW_STARS}).\n"
    )
    return header + yaml.safe_dump(spec, sort_keys=False, allow_unicode=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _count_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def build_clinvar_module(
    name: str,
    genes: list[str],
    out_dir: Path,
    *,
    reference: Optional[Path] = None,
    min_review_stars: int = MIN_REVIEW_STARS,
    max_citations: int = MAX_CITATIONS,
    alias_remaps: Optional[dict[str, str]] = None,
    unresolved_symbols: Optional[list[str]] = None,
) -> PanelBuild:
    """Draft, fill and record one ClinVar module into ``out_dir``.

    Leaves the directory holding ``module_spec.yaml`` + ``variants.csv`` + ``studies.csv`` +
    ``licensing.csv`` + a ``clinvar_panel.log`` provenance record. Resolution and compilation are the
    caller's next two steps (``just-dna-enricher enrich --offline`` then ``compile``), kept separate
    so a rebuild does not re-resolve and a re-resolve does not re-draft.
    """
    snapshot = Path(reference) if reference is not None else resolve_clinvar_reference()
    if snapshot is None:
        raise FileNotFoundError(
            "no ClinVar snapshot found. Provision it with `just-dna-enricher cache pull "
            "--only clinvar`, or build one with `just-dna-enricher clinvar build --download`."
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    # A rebuild must not append to the previous run's tables — draft_gene_panel is deliberately
    # additive, so the authored tables are cleared here rather than by it. The parquet artifacts and
    # the superseded raw-VCF route's log go too: leaving them would ship a mixture of two builds.
    for stale in (
        "variants.csv", "studies.csv", "resolution.csv",
        "weights.parquet", "annotations.parquet", "studies.parquet", "manifest.json",
        "v1_port.log",
    ):
        (out_dir / stale).unlink(missing_ok=True)
    # The licence sidecar is cleared through `layout`, not by name, because "the file to delete" now
    # has four legal locations: format 0.6 renamed it `sources.csv` -> `licensing.csv` (RM51), reads
    # both, and tolerates either under `derived/`.
    #
    # A literal `sources.csv` unlink is not equivalent, and the case it misses was measured rather
    # than reasoned about. Seed a module with `derived/sources.csv` — a pre-0.6 build in a split tree
    # — and rebuild: the literal unlink does not reach it, so the drafter's `sidecar_write_path` finds
    # it as the existing copy and **merges into the deprecated spelling**, which the module then keeps
    # for good. That is the spelling 1.0 stops reading, and every publish from such a directory
    # carries a deprecation warning in its manifest. Clearing every candidate makes the rebuild write
    # the preferred name instead. (Both spellings at once is a third state, and `resolve_sidecar`
    # refuses it outright rather than picking a winner — two copies of a fact-hashed, hand-editable
    # table are two claims.)
    for stale_path in sidecar_candidates(out_dir, SOURCES_CSV):
        stale_path.unlink(missing_ok=True)

    records = select_by_gene(
        snapshot, genes, clin_sig=PANEL_CLIN_SIG, min_review_stars=min_review_stars
    )
    release = snapshot_release(snapshot)
    (out_dir / "module_spec.yaml").write_text(
        _module_spec_yaml(name, genes, release, len(records)), encoding="utf-8"
    )

    result: ClinVarDraftResult = draft_gene_panel(
        out_dir,
        genes,
        snapshot=snapshot,
        clin_sig=PANEL_CLIN_SIG,
        min_review_stars=min_review_stars,
        # 0 = the provider drafts no study rows; see draft_studies for why this panel drafts its own.
        max_citations=0,
        offline=True,
    )
    variant_rows, unfilled = fill_genotypes(out_dir, records)
    study_rows, _dropped, study_notes = draft_studies(
        out_dir, snapshot, records, max_citations=max_citations
    )

    build = PanelBuild(
        name=name,
        output_dir=out_dir,
        genes_requested=len(genes),
        genes_matched=len({(r.get("gene") or "") for r in records} - {""}),
        clinvar_records=len(records),
        variant_rows=variant_rows,
        study_rows=study_rows,
        unfilled_placeholders=unfilled,
        alias_remaps=dict(alias_remaps or {}),
        unresolved_symbols=list(unresolved_symbols or []),
        # Three of the draft's warnings are answered by the two steps above and would be stale here:
        # the per-row genotype worklist and its "will not compile" header (fill_genotypes), and the
        # provider's own citation-cap note (draft_studies drafts them instead). What is left is a
        # real finding. `unfilled_placeholders` is the honest report of any stub that survived.
        warnings=[
            w
            for w in result.warnings
            if not w.lstrip().startswith("genotype for ")
            and "unreplaced genotype placeholder" not in w
            and "--max-citations 0" not in w
        ]
        + study_notes,
    )
    _write_log(out_dir, build, release, snapshot)
    return build


def _write_log(out_dir: Path, build: PanelBuild, release: dict[str, object], snapshot: Path) -> None:
    lines = [
        f"module: {build.name}",
        "route: just-dna-enricher clinvar_draft.draft_gene_panel (0.5 snapshot)",
        f"snapshot: {snapshot}",
        f"clinvar_release: {release.get('clinvar_file_date', '?')}",
        f"clinvar_source_sha256: sha256:{release.get('source_sha256', '?')}",
        "citations_source_sha256: sha256:"
        + str((release.get("citations") or {}).get("source_sha256", "?")),
        f"clin_sig: {', '.join(sorted(PANEL_CLIN_SIG))}",
        f"min_review_stars: {MIN_REVIEW_STARS}",
        f"max_citations: {MAX_CITATIONS}",
        f"genes_requested: {build.genes_requested}",
        f"genes_matched: {build.genes_matched}",
        f"clinvar_records: {build.clinvar_records}",
        f"variant_rows: {build.variant_rows}",
        f"study_rows: {build.study_rows}",
        f"unfilled_placeholders: {build.unfilled_placeholders}",
        f"built_at: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
    ]
    if build.alias_remaps:
        lines.append("alias_remaps:")
        lines += [f"  - {old} -> {new}" for old, new in sorted(build.alias_remaps.items())]
    if build.unresolved_symbols:
        lines.append("unresolved_symbols (reported, never guessed):")
        lines += [f"  - {s}" for s in build.unresolved_symbols]
    lines.append("warnings:")
    lines += [f"  - {w}" for w in build.warnings] or ["  (none)"]
    (out_dir / "clinvar_panel.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
