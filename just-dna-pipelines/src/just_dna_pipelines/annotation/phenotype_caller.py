"""Call a compound phenotype from a VCF by reading several sites together.

A phenotype like APOE ε-status or an HFE compound-het finding is not a per-position match: it is a
function of the alleles a sample carries across a small set of *defining* sites, read as a pair of
named haplotypes (a diplotype). The per-position weights engine cannot express that, so a module
authored with ``haplotypes`` + ``diplotypes`` (format 0.7) lands in ``skipped_modules`` there. This
module is the second engine path that handles it.

Scope of this version:

* **Two combiners, both the format's own.** Enumerative (``diplotypes``: each row an allele pair with
  a known phenotype) and score-and-bin (``allele_function.activity_value`` summed over the pair, then
  binned by ``activity_phenotype``). There is no rule language in the module and no evaluator here.
* **Phase is read where the callset states it.** Two sites are read as phased together only when both
  genotypes use ``|`` *and* carry the same non-null ``PS``; everything else is unphased, and an
  unphased double-het that two diplotypes both explain is ``ambiguous`` with ``phase_would_decide``
  set, never resolved by a guess.
* **Diploid.** A site's expected genotype is compared as a two-allele set, and a restored site is
  ``[ref, ref]``. A haploid contig (chrY/chrM, or the hemizygous X of a male G6PD call) therefore
  reads as ``no_match`` rather than a haploid call — out of scope, tracked in PHENOTYPE_CALLS.md.

The result is one :class:`PhenotypeCall` per (module, gene), written to
``{module}_phenotypes.parquet`` and rendered in its own report section. A call is **never** a silent
default: a callset that cannot establish anything is ``not_assessable``, a genotype no diplotype
explains is ``no_match``, and an unobserved site is restored to hom-ref only under the same gates the
weights engine uses (:func:`restoration.restorable_sites`), tri-state on the row.
"""

from __future__ import annotations

import re
import struct
from itertools import combinations_with_replacement
from pathlib import Path
from typing import Literal, Optional

import polars as pl
from eliot import log_message, start_action
from just_dna_format.alleles import parse_symbolic_allele, parsimony_reduce
from pydantic import BaseModel

from just_dna_pipelines.annotation.hf_modules import (
    ModuleInfo,
    ModuleTable,
    scan_module_table,
)
from just_dna_pipelines.annotation.hard_regions import fraction_in_hard_regions
from just_dna_pipelines.annotation.restoration import (
    FLANK_COLUMN,
    RestorationContext,
    restorable_sites,
)

# A `HaplotypeRow.allele` is "bases, or a symbolic/structural allele" (just_dna_format.pgx) — there is
# no separate sv_type/copy_number column on the haplotypes table (those live on allele_function). A
# structural allele is therefore one whose spelling is not plain bases: a symbolic `<DEL>`/`<CN0>`, or
# anything outside the nucleotide alphabet. An SNV VCF cannot confirm it, so a diplotype that needs it
# is reported `not_assessable` rather than `no_match` — the sample may carry it, we just cannot see it.
# v1 has no fixture carrying a structural allele (APOE/HFE are all SNVs); this is the honest gate for
# when one arrives (RhD, a CYP2C19 SV allele).
_BASE_ALLELE = re.compile(r"^[ACGTN]+$", re.IGNORECASE)


def _is_structural_allele(allele: Optional[str]) -> bool:
    if allele is None or allele == "":
        return False
    return not bool(_BASE_ALLELE.match(allele))


Evidence = Literal["called", "restored_hom_ref", "no_call"]
MatchedBy = Literal["position", "rsid", "indel_window"]
Combiner = Literal["diplotypes", "activity"]

# How far from an indel site the caller looks for the same event spelled at another anchor. An indel
# in a repeat has several valid VCF spellings (ABO's A2 c.1061delC is `GGG>GG` at 133255670 in
# Ensembl and `CG>C` at 133255669 left-normalized), and a reference cache can place an rsID one base
# off (rs8176719: Ensembl 133257520 G>GC, dbSNP/gnomAD/DRAGEN 133257521 T>TC). ±10 bp covers both.
INDEL_WINDOW_BP = 10
Status = Literal["called", "ambiguous", "not_assessable", "no_match"]


class SiteEvidence(BaseModel):
    """What the callset says at one of a gene's defining sites."""

    rsid: Optional[str]
    chrom: str
    start: int
    ref: str
    # The sample's alleles at this site (sorted, as the VCF stores a genotype), or None when nothing
    # was observed and nothing could be restored.
    observed: Optional[list[str]]
    evidence: Evidence
    matched_by: Optional[MatchedBy]
    restored_flank_bp: Optional[int]
    # The sample's alleles in homolog order, set only for a phased call (`|` with a non-null PS). The
    # `observed` list is sorted, so it has already lost which allele sits on which chromosome copy.
    phased_alleles: Optional[list[str]] = None
    phase_set: Optional[int] = None


StructuralReading = Literal["copy_present", "both_deleted"]


class StructuralEvidence(BaseModel):
    """What the coverage inside a deletion allele's span says, on a whole-genome callset.

    A small-variant VCF never lists a large deletion, so a missing ``<DEL>`` record says nothing. The
    calls *inside* the span do: reads mapped there mean at least one copy is present, and a span with
    no calls at all on a genome that has calls on both sides of it means both copies are gone.
    ``reading`` is ``None`` when the coverage does not settle it, and ``reason`` then says why.
    """

    haplotype: str
    allele: str
    chrom: str
    start: int
    end: int
    calls_in_span: int
    # The longest stretch of the span with no call, counting from the span's edges.
    largest_gap_bp: int
    hard_region_fraction: Optional[float]
    reading: Optional[StructuralReading]
    reason: str


class Candidate(BaseModel):
    """A diplotype consistent with the observed genotype, and the phenotype it maps to."""

    haplotype_a: str
    haplotype_b: str
    phenotype: Optional[str]
    conclusion: Optional[str]
    direction: Optional[str]
    clin_sig: Optional[str]
    # True when this candidate needs a structural/copy-number allele an SNV VCF cannot confirm.
    not_assessable: bool = False
    # Score-and-bin only: the summed activity value of the pair (None on an enumerative module, and
    # None when either allele's activity value is unstated — then no bin is chosen).
    activity_score: Optional[float] = None


class DrugRow(BaseModel):
    """A pharmacogenomic recommendation attached to a diplotype, grouped by clinical context."""

    drug: str
    response: Optional[str]
    evidence_level: Optional[str]
    recommendation_strength: Optional[str]
    clinical_context: Optional[str]


class PhenotypeCall(BaseModel):
    """The report contract: one call per (module, gene). See docs/PHENOTYPE_CALLS.md."""

    module: str
    gene: str
    status: Status
    # Set only when every consistent diplotype maps to the same phenotype.
    phenotype: Optional[str]
    candidates: list[Candidate]
    sites: list[SiteEvidence]
    # True when the candidates differ only by cis/trans assignment of the same observed alleles —
    # i.e. knowing the phase would settle the call. False when the ambiguity is a no_call site whose
    # genotype (not its phase) would decide.
    phase_would_decide: bool
    # Coverage readings for the gene's deletion alleles (empty when it has none).
    structural_evidence: list[StructuralEvidence] = []
    alleles_considered: list[str]
    alleles_not_assessable: list[str]
    # Haplotypes the module defines that no diplotype row pairs (measured upstream: CYP2C19 *40/*41).
    unpaired_haplotypes: list[str]
    drug_rows: list[DrugRow]
    # The module's own phase-ambiguity warnings from manifest.compilation, passed through verbatim.
    compiler_warnings: list[str]


class GeneDefinition(BaseModel):
    """Everything the caller needs about one gene of a phenotype module."""

    gene: str
    # allele name -> {(chrom, start) -> allele base at that site}. A haplotype carries `ref` at any
    # defining site it does not list (the PharmVar/CPIC unlisted-site convention).
    haplotype_alleles: dict[str, dict[str, str]]
    # (chrom, start) -> {rsid, ref, requires_callable, alleles} for every defining site of this gene;
    # `alleles` is every allele any haplotype carries there, ref included.
    site_meta: dict[str, dict]
    combiner: Combiner = "diplotypes"
    # Enumerative: the diplotype rows, each a dict with haplotype_a/b, phenotype, conclusion,
    # direction, clin_sig, and the drug columns.
    diplotypes: list[dict] = []
    # Score-and-bin: allele -> activity_value (None = unstated), and the activity_phenotype bins with
    # the `unresolved` sentinel row already removed.
    activity_values: dict[str, Optional[float]] = {}
    activity_bins: list[dict] = []
    # Alleles that need a structural/copy-number call an SNV VCF cannot make.
    structural_alleles: set[str]
    # haplotype -> the span a symbolic deletion allele covers: {site, chrom, start, end, allele}.
    # Only `<DEL:length>` alleles have a span a callset can be read against; any other symbolic
    # allele stays not assessable.
    deletion_spans: dict[str, dict] = {}


class PhenotypeDefinition(BaseModel):
    module: str
    genes: dict[str, GeneDefinition]
    compiler_warnings: list[str]


def _site_key(chrom: str, start: int) -> str:
    return f"{chrom}:{start}"


def load_phenotype_definition(module_name: str, info: ModuleInfo) -> PhenotypeDefinition:
    """Read a module's haplotypes + combiner tables into the per-gene structure the caller enumerates.

    The combiner is chosen by which tables the module carries, the same test ``module_kind`` routes
    on: ``diplotypes`` when present (enumerative), else ``allele_function`` + ``activity_phenotype``
    (score-and-bin). The compiler's own phase-ambiguity warnings are surfaced verbatim on every call
    for the module rather than recomputed here.
    """
    haplotypes = scan_module_table(module_name, ModuleTable.HAPLOTYPES, module_info=info).collect()
    combiner: Combiner = "diplotypes" if info.diplotypes_url is not None else "activity"
    if combiner == "diplotypes":
        diplotypes = scan_module_table(module_name, ModuleTable.DIPLOTYPES, module_info=info).collect()
        allele_function = activity_phenotype = None
    else:
        diplotypes = None
        allele_function = scan_module_table(
            module_name, ModuleTable.ALLELE_FUNCTION, module_info=info
        ).collect()
        activity_phenotype = scan_module_table(
            module_name, ModuleTable.ACTIVITY_PHENOTYPE, module_info=info
        ).collect()

    genes: dict[str, GeneDefinition] = {}
    for gene in haplotypes["gene"].unique().drop_nulls().sort().to_list():
        gene_haps = haplotypes.filter(pl.col("gene") == gene)
        haplotype_alleles: dict[str, dict[str, str]] = {}
        site_meta: dict[str, dict] = {}
        structural_alleles: set[str] = set()
        deletion_spans: dict[str, dict] = {}
        for row in gene_haps.iter_rows(named=True):
            name = row["haplotype_name"]
            key = _site_key(row["chrom"], row["start"])
            haplotype_alleles.setdefault(name, {})[key] = row["allele"]
            meta = site_meta.setdefault(
                key,
                {
                    "rsid": row.get("rsid"),
                    "ref": row["ref"],
                    "requires_callable": row.get("requires_callable"),
                    "alleles": {row["ref"]},
                },
            )
            meta["alleles"].add(row["allele"])
            if _is_structural_allele(row["allele"]):
                structural_alleles.add(name)
                symbolic = parse_symbolic_allele(row["allele"])
                if symbolic is not None and symbolic.type == "DEL" and symbolic.length:
                    # VCF's convention for a symbolic deletion: the record sits on the base before
                    # the deleted sequence, which runs for `length` bases after it.
                    deletion_spans[name] = {
                        "site": key,
                        "chrom": row["chrom"],
                        "start": int(row["start"]) + 1,
                        "end": int(row["start"]) + symbolic.length,
                        "allele": row["allele"],
                    }

        if combiner == "diplotypes":
            gene_diplos = (
                diplotypes.filter(pl.col("gene") == gene) if "gene" in diplotypes.columns else diplotypes
            )
            genes[gene] = GeneDefinition(
                gene=gene,
                haplotype_alleles=haplotype_alleles,
                site_meta=site_meta,
                combiner="diplotypes",
                diplotypes=[dict(r) for r in gene_diplos.iter_rows(named=True)],
                structural_alleles=structural_alleles,
                deletion_spans=deletion_spans,
            )
        else:
            functions = allele_function.filter(pl.col("gene") == gene)
            bins = activity_phenotype.filter(pl.col("gene") == gene)
            if "unresolved" in bins.columns:
                bins = bins.filter(~pl.col("unresolved").fill_null(False))
            genes[gene] = GeneDefinition(
                gene=gene,
                haplotype_alleles=haplotype_alleles,
                site_meta=site_meta,
                combiner="activity",
                activity_values={
                    r["allele"]: r.get("activity_value") for r in functions.iter_rows(named=True)
                },
                activity_bins=[dict(r) for r in bins.iter_rows(named=True)],
                structural_alleles=structural_alleles,
                deletion_spans=deletion_spans,
            )

    # The compiler's warnings for these bytes were kept on ModuleInfo at discovery time (the fsspec
    # probe already read and validated the manifest). Reading them from the manifest again here would
    # need the module's path resolved to a filesystem, which `info.path` on a remote module is not.
    return PhenotypeDefinition(
        module=module_name, genes=genes, compiler_warnings=list(info.manifest_compilation_warnings)
    )


_GT_INDEX = re.compile(r"\d+|\.")


def _record_alleles(gt: Optional[str], ref: str, alt: Optional[str]) -> Optional[list[str]]:
    """The alleles a GT names, in the order it names them (homolog order when phased).

    Returns None for a missing call (any ``.`` index), which the caller treats as nothing observed.
    """
    if gt is None:
        return None
    indices = _GT_INDEX.findall(gt)
    if not indices or "." in indices:
        return None
    pool = [ref] + (alt.split(",") if alt else [])
    return [pool[int(i)] for i in indices]


def _is_indel_site(meta: dict) -> bool:
    return any(len(a) != len(meta["ref"]) for a in meta["alleles"] if not _is_structural_allele(a))


def _translate(alleles: list[str], record_ref: str, record_alts: list[str], meta: dict) -> list[str]:
    """Rewrite a record's alleles into the site's spelling, for a record matched in the indel window.

    The record's ref becomes the site's ref, and each record ALT that represents the same event as
    one of the site's non-ref alleles becomes that allele. An ALT that represents none of them is kept
    verbatim — it then matches no haplotype, which is the honest outcome (a different event was seen).
    """
    site_ref = meta["ref"]
    mapping = {record_ref: site_ref}
    for alt in record_alts:
        event = parsimony_reduce([record_ref, alt])
        for allele in meta["alleles"]:
            if allele != site_ref and parsimony_reduce([site_ref, allele]) == event:
                mapping[alt] = allele
    return [mapping.get(a, a) for a in alleles]


def gather_site_evidence(
    vcf_lf: pl.LazyFrame,
    gene_def: GeneDefinition,
    context: RestorationContext,
) -> list[SiteEvidence]:
    """Resolve every defining site of a gene against the callset.

    Match order:

    1. by ``(chrom, start)`` where the record's ``ref`` equals the site's (a record at the same
       position with a different ``ref`` is a different event — an indel anchored on this base, say);
    2. by rsID where the site names one and the VCF carries IDs;
    3. for an **indel** site only, the same event at another anchor within ``INDEL_WINDOW_BP``: the
       record's ``parsimony_reduce`` must equal the site's for one of its non-ref alleles, and exactly
       one record in the window may qualify (two candidates is a refusal, logged, never a pick).
       The record's alleles are rewritten into the site's spelling before any comparison;
    4. otherwise :func:`restoration.restorable_sites` (hom-ref where the callset's coverage supports
       it, honouring ``requires_callable``), and failing that ``no_call``. A site whose window was
       refused is never restored: an event of its shape is right there.

    A record whose GT uses ``|`` and carries a non-null ``PS`` keeps its alleles in homolog order on
    ``phased_alleles`` with the ``phase_set``; everything else is read unphased.
    """
    sites = list(gene_def.site_meta.items())  # [(key, meta), ...]
    vcf_names = vcf_lf.collect_schema().names()
    has_ps = "PS" in vcf_names
    record_cols = ["chrom", "start", "ref", "alt", "GT", "genotype"] + (["PS"] if has_ps else [])
    record_cols = [c for c in record_cols if c in vcf_names]

    site_frame = pl.DataFrame(
        {
            "_key": [k for k, _ in sites],
            "chrom": [k.split(":")[0] for k, _ in sites],
            "start": [int(k.split(":")[1]) for k, _ in sites],
            "rsid": [m["rsid"] for _, m in sites],
            "_site_ref": [m["ref"] for _, m in sites],
            "requires_callable": [m.get("requires_callable") for _, m in sites],
        },
        schema_overrides={"start": pl.UInt32},
    )

    # key -> {"record": dict, "matched_by": ...}
    matched: dict[str, dict] = {}

    # 1. Position match, ref-agreeing. Several records can share a position (an SNV beside an indel
    #    anchored on the same base); prefer the one whose ALTs include an allele the site defines.
    pos = (
        site_frame.lazy()
        .join(vcf_lf.select(record_cols), on=["chrom", "start"], how="inner")
        .filter(pl.col("ref") == pl.col("_site_ref"))
        .select(["_key"] + [c for c in record_cols if c not in ("chrom", "start")])
        .collect()
    )
    for row in pos.sort(["_key", "alt"], nulls_last=True).iter_rows(named=True):
        meta = gene_def.site_meta[row["_key"]]
        relevant = bool(set((row.get("alt") or "").split(",")) & (meta["alleles"] - {meta["ref"]}))
        current = matched.get(row["_key"])
        if current is None or (relevant and not current["relevant"]):
            matched[row["_key"]] = {"record": row, "matched_by": "position", "relevant": relevant}

    # 2. rsID match for sites position did not find, when the site names one and the VCF carries IDs.
    unresolved = site_frame.filter(
        ~pl.col("_key").is_in(list(matched.keys())) & pl.col("rsid").is_not_null()
    )
    if unresolved.height and "rsid" in vcf_names:
        # Cast first: a callset with no IDs at all can carry an all-null `rsid` column typed `Null`,
        # which `str.split` refuses. Casting to Utf8 makes it null-valued Utf8, which splits to null.
        vcf_by_rsid = vcf_lf.with_columns(
            pl.col("rsid").cast(pl.Utf8).str.split(";").alias("_rsid_key")
        ).explode("_rsid_key", empty_as_null=True)
        rs = (
            unresolved.lazy()
            .select("_key", "rsid")
            .join(
                vcf_by_rsid.select(["_rsid_key"] + [c for c in record_cols if c not in ("chrom", "start")]),
                left_on="rsid",
                right_on="_rsid_key",
                how="inner",
            )
            .collect()
        )
        for row in rs.sort("_key").iter_rows(named=True):
            matched.setdefault(row["_key"], {"record": row, "matched_by": "rsid", "relevant": True})

    # 3. Indel window: the same event spelled at another anchor. A site with more than one qualifying
    #    record is refused — and kept out of restoration below: the callset demonstrably carries an
    #    event of this shape here, so reading the site as reference would fabricate a hom-ref.
    window_refused: set[str] = set()
    for key, meta in sites:
        if key in matched or not _is_indel_site(meta):
            continue
        chrom, start = key.split(":")[0], int(key.split(":")[1])
        events = {
            parsimony_reduce([meta["ref"], a]) for a in meta["alleles"] if a != meta["ref"]
        }
        window = (
            vcf_lf.filter(
                (pl.col("chrom") == chrom)
                & pl.col("start").is_between(start - INDEL_WINDOW_BP, start + INDEL_WINDOW_BP)
            )
            .select([c for c in record_cols if c != "chrom"])
            .collect()
        )
        hits = [
            row
            for row in window.iter_rows(named=True)
            if row.get("alt")
            and any(parsimony_reduce([row["ref"], alt]) in events for alt in row["alt"].split(","))
        ]
        if len(hits) == 1:
            matched[key] = {"record": hits[0], "matched_by": "indel_window", "relevant": True}
        elif len(hits) > 1:
            window_refused.add(key)
            log_message(
                message_type="phenotype_caller",
                step="indel_window_not_unique",
                site=key,
                candidates=[f"{chrom}:{h['start']} {h['ref']}>{h['alt']}" for h in hits],
            )

    # 4. Restoration for sites still unresolved. `restorable_sites` returns those whose neighbourhood
    #    the callset demonstrably reached (and honours `requires_callable`); the rest are `no_call`.
    still_absent = site_frame.filter(~pl.col("_key").is_in([*matched.keys(), *window_refused]))
    restored: dict[str, int] = {}
    if still_absent.height:
        eligible = restorable_sites(
            still_absent.lazy().select("_key", "chrom", "start", "requires_callable"),
            context.called_sites,
            context,
        ).collect()
        for row in eligible.iter_rows(named=True):
            restored[row["_key"]] = int(row[FLANK_COLUMN])

    evidence: list[SiteEvidence] = []
    for key, meta in sites:
        base = {
            "rsid": meta["rsid"],
            "chrom": key.split(":")[0],
            "start": int(key.split(":")[1]),
            "ref": meta["ref"],
        }
        if key in matched:
            record = matched[key]["record"]
            ordered = _record_alleles(record.get("GT"), record["ref"], record.get("alt"))
            if ordered is None:
                # No GT to read (a callset without FORMAT) — fall back to the stored genotype list.
                ordered = list(record["genotype"] or [])
            if matched[key]["matched_by"] == "indel_window":
                ordered = _translate(
                    ordered, record["ref"], (record.get("alt") or "").split(","), meta
                )
            if not ordered:
                evidence.append(SiteEvidence(**base, observed=None, evidence="no_call",
                                             matched_by=None, restored_flank_bp=None))
                continue
            phase_set = record.get("PS")
            phased = "|" in (record.get("GT") or "") and phase_set is not None
            evidence.append(
                SiteEvidence(
                    **base,
                    observed=sorted(ordered),
                    evidence="called",
                    matched_by=matched[key]["matched_by"],
                    restored_flank_bp=None,
                    phased_alleles=ordered if phased else None,
                    phase_set=int(phase_set) if phased else None,
                )
            )
        elif key in restored:
            evidence.append(
                SiteEvidence(**base, observed=[meta["ref"], meta["ref"]], evidence="restored_hom_ref",
                             matched_by=None, restored_flank_bp=restored[key])
            )
        else:
            evidence.append(SiteEvidence(**base, observed=None, evidence="no_call",
                                         matched_by=None, restored_flank_bp=None))
    return evidence


def gather_structural_evidence(
    gene_def: GeneDefinition, context: RestorationContext
) -> list[StructuralEvidence]:
    """Read each deletion allele's span against the callset's own call density.

    Only on a callset restoration trusts (variant-only and whole-genome): anywhere else a missing
    call carries no information and every reading is ``None``. On a genome:

    * **copy_present** — calls inside the span and no call-free stretch longer than the restoration
      flank. Reads were placed across the region, so at least one copy is there. A heterozygous
      deletion is invisible to a small-variant caller, so this never tells one copy from two.
    * **both_deleted** — no call inside the span, calls within the flank on both sides of it, and the
      span mostly outside the hard-region mask. The caller covered the neighbourhood and emitted
      nothing across the whole span.
    * otherwise ``None``. A long call-free stretch *inside* an otherwise covered span is the telling
      case: it can be a deletion of part of the span, a span the module anchored imprecisely, or
      reads that could not be placed, and coverage alone cannot say which.
    """
    evidence: list[StructuralEvidence] = []
    for haplotype, span in gene_def.deletion_spans.items():
        chrom, start, end = span["chrom"], span["start"], span["end"]
        fraction = (
            fraction_in_hard_regions(chrom, start, end, context.hard_regions)
            if context.hard_regions is not None
            else None
        )
        base = {"haplotype": haplotype, "allele": span["allele"], "chrom": chrom, "start": start,
                "end": end, "hard_region_fraction": fraction}
        contig = context.called_sites.filter(pl.col("chrom") == chrom)["start"].cast(pl.Int64)
        inside = contig.filter((contig >= start) & (contig <= end)).sort().to_list()
        edges = [start - 1, *inside, end + 1]
        largest_gap = max(b - a - 1 for a, b in zip(edges, edges[1:]))
        base.update(calls_in_span=len(inside), largest_gap_bp=largest_gap)

        if not context.enabled:
            evidence.append(StructuralEvidence(**base, reading=None, reason=(
                "coverage is only read on a whole-genome, variant-only callset; here a missing "
                "call says nothing")))
            continue
        flank = context.max_flank_bp
        if inside and largest_gap <= flank:
            evidence.append(StructuralEvidence(**base, reading="copy_present", reason=(
                f"{len(inside)} calls inside the span, none more than {largest_gap:,} bp apart: "
                "reads were placed across it, so at least one copy is present")))
            continue
        if inside:
            share = largest_gap / (end - start + 1)
            evidence.append(StructuralEvidence(**base, reading=None, reason=(
                f"{largest_gap:,} bp of the span ({share:.0%}) has no calls although the rest does: "
                "a deletion of part of the span, an imprecise span, or reads that could not be "
                "placed, and coverage alone cannot tell which")))
            continue
        if fraction is None or fraction >= 0.5:
            evidence.append(StructuralEvidence(**base, reading=None, reason=(
                "no calls inside the span, but "
                + ("the hard-region mask is unavailable" if fraction is None
                   else f"{fraction:.0%} of it lies in low-mappability or duplicated sequence, "
                        "where a missing call is not evidence of a missing copy"))))
            continue
        before = contig.filter((contig < start) & (contig >= start - flank)).len()
        after = contig.filter((contig > end) & (contig <= end + flank)).len()
        if before and after:
            evidence.append(StructuralEvidence(**base, reading="both_deleted", reason=(
                "no calls inside the span, calls within "
                f"{flank:,} bp on both sides: both copies read as deleted (inferred from coverage)")))
        else:
            evidence.append(StructuralEvidence(**base, reading=None, reason=(
                "no calls inside or near the span, so the neighbourhood itself was not covered")))
    return evidence


def _allele_at(gene_def: GeneDefinition, haplotype: str, key: str) -> Optional[str]:
    """The base a haplotype carries at a site, applying the unlisted-site → ref convention.

    Returns None only when the haplotype is not defined at all (a diplotype naming an undefined
    allele — e.g. an unsynthesised ``*1``), which the caller records rather than guessing.
    """
    alleles = gene_def.haplotype_alleles.get(haplotype)
    if alleles is None:
        return None
    if key in alleles:
        return alleles[key]
    return gene_def.site_meta[key]["ref"]


def _float32(value: float) -> float:
    """Narrow to float32, the precision TABLES.md says bin bounds are compared in."""
    return struct.unpack("f", struct.pack("f", value))[0]


def _bin_activity(score: float, bins: list[dict]) -> Optional[dict]:
    """The ``activity_phenotype`` row a summed activity score falls in, or None.

    Bounds are inclusive and ``None`` is open; where two bins share an endpoint the one with the
    greater ``measure_min`` owns it (TABLES.md). Compared in float32, never with an epsilon.
    """
    value = _float32(score)
    hits = [
        b
        for b in bins
        if (b.get("measure_min") is None or value >= _float32(b["measure_min"]))
        and (b.get("measure_max") is None or value <= _float32(b["measure_max"]))
    ]
    if not hits:
        return None
    return max(hits, key=lambda b: float("-inf") if b.get("measure_min") is None else b["measure_min"])


def _candidate_rows(gene_def: GeneDefinition) -> list[dict]:
    """Every diplotype the module lets the caller consider, as a row carrying its phenotype.

    Enumerative: the ``diplotypes`` rows as authored. Score-and-bin: every unordered pair of alleles
    that both ``haplotypes`` (which says what an allele looks like) and ``allele_function`` (which says
    what it is worth) define, with its summed ``activity_value`` binned — an allele missing from either
    table cannot be scored and is reported as unpaired rather than guessed.
    """
    if gene_def.combiner == "diplotypes":
        return gene_def.diplotypes
    scorable = sorted(set(gene_def.haplotype_alleles) & set(gene_def.activity_values))
    rows: list[dict] = []
    for a, b in combinations_with_replacement(scorable, 2):
        value_a, value_b = gene_def.activity_values[a], gene_def.activity_values[b]
        score = None if value_a is None or value_b is None else value_a + value_b
        bin_row = _bin_activity(score, gene_def.activity_bins) if score is not None else None
        rows.append(
            {
                "haplotype_a": a,
                "haplotype_b": b,
                "activity_score": score,
                "phenotype": bin_row.get("phenotype") if bin_row else None,
                "conclusion": bin_row.get("conclusion") if bin_row else None,
                "direction": bin_row.get("direction") if bin_row else None,
                "clin_sig": bin_row.get("clin_sig") if bin_row else None,
            }
        )
    return rows


def _consistent(
    expected: dict[str, tuple[str, str]],
    evidence_by_key: dict[str, SiteEvidence],
    observed_keys: list[str],
) -> bool:
    """Whether a diplotype's expected alleles explain every observed site.

    Unphased (and restored) sites compare as unordered pairs. Phased sites are grouped by phase set,
    and within one set the diplotype must fit under a *single* orientation — haplotype A on the first
    homolog at every site of the set, or on the second at every site. That is what tells the HFE
    compound heterozygote (trans) from both variants in cis.

    A deletion allele contributes no allele at its site: one deleted copy leaves the site
    hemizygous, which a diploid caller writes as a homozygote, so the pair compares as a *set* of the
    surviving alleles; two deleted copies leave nothing to call, so any observation contradicts them.
    """
    blocks: dict[int, list[str]] = {}
    for key in observed_keys:
        site = evidence_by_key[key]
        pair = expected[key]
        if any(_is_structural_allele(a) for a in pair):
            surviving = {a for a in pair if not _is_structural_allele(a)}
            if surviving != set(site.observed):
                return False
            continue
        if site.phased_alleles is not None and site.phase_set is not None:
            blocks.setdefault(site.phase_set, []).append(key)
        elif sorted(pair) != sorted(site.observed):
            return False
    for keys in blocks.values():
        forward = all(list(expected[k]) == evidence_by_key[k].phased_alleles for k in keys)
        reverse = all(list(expected[k][::-1]) == evidence_by_key[k].phased_alleles for k in keys)
        if not (forward or reverse):
            return False
    return True


def _fits_structural(a: str, b: str, structural: list[StructuralEvidence]) -> bool:
    """Whether a pair agrees with the coverage readings of the gene's deletion alleles."""
    for item in structural:
        homozygous = a == item.haplotype and b == item.haplotype
        if item.reading == "copy_present" and homozygous:
            return False
        if item.reading == "both_deleted" and not homozygous:
            return False
    return True


def call_gene(
    module: str,
    gene_def: GeneDefinition,
    evidence: list[SiteEvidence],
    structural: Optional[list[StructuralEvidence]] = None,
) -> PhenotypeCall:
    """Turn the site evidence into a set of consistent diplotypes and a status.

    A candidate diplotype is *consistent* when its expected genotype equals the observed one at every
    called or restored site (as an unordered pair, or under one orientation per phase set where the
    callset is phased); a no_call site is a wildcard. The phenotype is *called* only when every
    consistent candidate maps to the same phenotype, ``ambiguous`` when they disagree, ``no_match``
    when none is consistent, and ``not_assessable`` when nothing could be observed at all (or the only
    consistent candidates need an allele an SNV VCF cannot confirm).
    """
    structural = structural or []
    evidence_by_key = {_site_key(e.chrom, e.start): e for e in evidence}
    observed_keys = [k for k, e in evidence_by_key.items() if e.evidence != "no_call"]
    decided_structural = [item for item in structural if item.reading is not None]
    no_call_keys = [k for k, e in evidence_by_key.items() if e.evidence == "no_call"]

    considered = sorted(gene_def.haplotype_alleles.keys())
    not_assessable_alleles = sorted(gene_def.structural_alleles)
    paired: set[str] = set()

    kept: list[tuple[dict, dict[str, tuple[str, str]]]] = []  # (row, expected alleles per key)
    for diplo in _candidate_rows(gene_def):
        a, b = diplo["haplotype_a"], diplo["haplotype_b"]
        paired.update({a, b})
        expected: dict[str, tuple[str, str]] = {}
        undefined = False
        for key in gene_def.site_meta:
            allele_a = _allele_at(gene_def, a, key)
            allele_b = _allele_at(gene_def, b, key)
            if allele_a is None or allele_b is None:
                undefined = True
                break
            expected[key] = (allele_a, allele_b)
        if undefined:
            continue
        if _consistent(expected, evidence_by_key, observed_keys) and _fits_structural(
            a, b, decided_structural
        ):
            kept.append((diplo, expected))

    unpaired = sorted(set(gene_def.haplotype_alleles.keys()) - paired)

    candidates: list[Candidate] = []
    for diplo, _ in kept:
        a, b = diplo["haplotype_a"], diplo["haplotype_b"]
        # A pair needing a structural allele stays unconfirmable unless coverage decided exactly it:
        # "both copies deleted" confirms the homozygous deletion, while "a copy is present" cannot
        # tell a heterozygous deletion from none.
        settled_by_coverage = a == b and any(
            item.haplotype == a and item.reading == "both_deleted" for item in decided_structural
        )
        needs_structural = (
            a in gene_def.structural_alleles or b in gene_def.structural_alleles
        ) and not settled_by_coverage
        candidates.append(
            Candidate(
                haplotype_a=diplo["haplotype_a"],
                haplotype_b=diplo["haplotype_b"],
                phenotype=diplo.get("phenotype"),
                conclusion=diplo.get("conclusion"),
                direction=diplo.get("direction"),
                clin_sig=diplo.get("clin_sig"),
                not_assessable=needs_structural,
                activity_score=diplo.get("activity_score"),
            )
        )

    # Status.
    assessable = [c for c in candidates if not c.not_assessable]
    if not observed_keys and not decided_structural:
        # Nothing was seen and nothing could be restored — every candidate is trivially consistent,
        # so there is no call to make. Never fall back to a reference diplotype here.
        status: Status = "not_assessable"
        phenotype = None
    elif not candidates:
        status = "no_match"
        phenotype = None
    elif not assessable:
        # The only consistent diplotypes need a structural allele we cannot confirm from an SNV VCF.
        status = "not_assessable"
        phenotype = None
    else:
        phenotypes = {c.phenotype for c in assessable}
        if len(phenotypes) == 1 and None not in phenotypes:
            status = "called"
            phenotype = next(iter(phenotypes))
        elif len(phenotypes) == 1:
            # Every consistent pair agrees, but on *no* phenotype — a score that falls in no bin, or an
            # allele whose activity value the module leaves unstated. There is nothing to name.
            status = "not_assessable"
            phenotype = None
        else:
            status = "ambiguous"
            phenotype = None

    # phase_would_decide: the ambiguity is pure cis/trans when the consistent candidates agree on the
    # expected genotype at every no_call site (so no missing *call* is what splits them) — the only
    # remaining unknown is which homolog carries which observed allele.
    phase_would_decide = False
    if status == "ambiguous":
        no_call_sigs = {
            tuple(tuple(sorted(expected[k])) for k in no_call_keys) for _, expected in kept
        }
        phase_would_decide = len(no_call_sigs) == 1

    drug_rows = _drug_rows([diplo for diplo, _ in kept])

    # module-level warnings are attached by the caller; per-gene call carries a placeholder filled in
    # by call_phenotype_module so every gene of a module shows the same compiler warnings.
    return PhenotypeCall(
        module=module,
        gene=gene_def.gene,
        status=status,
        phenotype=phenotype,
        candidates=candidates,
        sites=evidence,
        phase_would_decide=phase_would_decide,
        structural_evidence=structural,
        alleles_considered=considered,
        alleles_not_assessable=not_assessable_alleles,
        unpaired_haplotypes=unpaired,
        drug_rows=drug_rows,
        compiler_warnings=[],
    )


def _drug_rows(diplotypes: list[dict]) -> list[DrugRow]:
    """Pharmacogenomic rows from the consistent diplotypes, one per (drug, clinical_context).

    The caller never picks a clinical setting — every distinct (drug, context) is carried so the
    report can render them side by side.
    """
    seen: set[tuple] = set()
    rows: list[DrugRow] = []
    for diplo in diplotypes:
        drug = diplo.get("drug")
        if drug in (None, ""):
            continue
        key = (drug, diplo.get("clinical_context"))
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            DrugRow(
                drug=drug,
                response=diplo.get("response"),
                evidence_level=diplo.get("evidence_level"),
                recommendation_strength=diplo.get("recommendation_strength"),
                clinical_context=diplo.get("clinical_context"),
            )
        )
    return rows


def call_phenotype_module(
    vcf_lf: pl.LazyFrame,
    module_name: str,
    info: ModuleInfo,
    context: RestorationContext,
    output_path: Path,
) -> tuple[Path, int]:
    """Call every gene of a phenotype module and write ``{module}_phenotypes.parquet``.

    Returns ``(path, n_called)`` where ``n_called`` is the number of genes whose status is ``called``.
    """
    with start_action(action_type="call_phenotype_module", module=module_name):
        definition = load_phenotype_definition(module_name, info)
        calls: list[PhenotypeCall] = []
        for gene, gene_def in definition.genes.items():
            evidence = gather_site_evidence(vcf_lf, gene_def, context)
            structural = gather_structural_evidence(gene_def, context)
            call = call_gene(module_name, gene_def, evidence, structural)
            call.compiler_warnings = definition.compiler_warnings
            calls.append(call)

        n_called = sum(1 for c in calls if c.status == "called")
        _write_calls(calls, output_path)
        return output_path, n_called


# The parquet schema is stated explicitly rather than inferred from the rows: polars infers a struct
# dtype per row from a dict, and a module with a `no_match` gene (empty `candidates`) beside a `called`
# one (populated `candidates`), or a `sites` list whose `observed` is null on one row and a list on
# another, gives per-row struct dtypes that will not unify into one column. Stating the schema also
# lets an empty module write typed-empty columns rather than a 0x0 frame.
_CANDIDATE_STRUCT = pl.Struct(
    {
        "haplotype_a": pl.String,
        "haplotype_b": pl.String,
        "phenotype": pl.String,
        "conclusion": pl.String,
        "direction": pl.String,
        "clin_sig": pl.String,
        "not_assessable": pl.Boolean,
        "activity_score": pl.Float64,
    }
)
_SITE_STRUCT = pl.Struct(
    {
        "rsid": pl.String,
        "chrom": pl.String,
        "start": pl.Int64,
        "ref": pl.String,
        "observed": pl.List(pl.String),
        "evidence": pl.String,
        "matched_by": pl.String,
        "restored_flank_bp": pl.Int64,
        "phased_alleles": pl.List(pl.String),
        "phase_set": pl.Int64,
    }
)
_DRUG_STRUCT = pl.Struct(
    {
        "drug": pl.String,
        "response": pl.String,
        "evidence_level": pl.String,
        "recommendation_strength": pl.String,
        "clinical_context": pl.String,
    }
)
_STRUCTURAL_STRUCT = pl.Struct(
    {
        "haplotype": pl.String,
        "allele": pl.String,
        "chrom": pl.String,
        "start": pl.Int64,
        "end": pl.Int64,
        "calls_in_span": pl.Int64,
        "largest_gap_bp": pl.Int64,
        "hard_region_fraction": pl.Float64,
        "reading": pl.String,
        "reason": pl.String,
    }
)
PHENOTYPE_CALL_SCHEMA: dict[str, pl.DataType] = {
    "module": pl.String,
    "gene": pl.String,
    "status": pl.String,
    "phenotype": pl.String,
    "candidates": pl.List(_CANDIDATE_STRUCT),
    "sites": pl.List(_SITE_STRUCT),
    "phase_would_decide": pl.Boolean,
    "structural_evidence": pl.List(_STRUCTURAL_STRUCT),
    "alleles_considered": pl.List(pl.String),
    "alleles_not_assessable": pl.List(pl.String),
    "unpaired_haplotypes": pl.List(pl.String),
    "drug_rows": pl.List(_DRUG_STRUCT),
    "compiler_warnings": pl.List(pl.String),
}


def _write_calls(calls: list[PhenotypeCall], output_path: Path) -> None:
    """One row per gene, with nested list/struct columns for candidates, sites and drug rows.

    An empty module (no genes) still writes a file with the right schema, so a reader never has to
    special-case "the parquet is missing" against "the module found nothing".
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = [c.model_dump() for c in calls]
    frame = pl.DataFrame(records, schema=PHENOTYPE_CALL_SCHEMA)
    frame.write_parquet(output_path)
