"""Reference-genotype restoration: report the rows a variant-only callset cannot supply.

A module may author a row whose genotype *is* the reference genotype — `G/G` where `ref` is `G`.
Our `lactose_tolerance` module states exactly that for rs4988235 ("adult-type hypolactasia"), and it
is the most common result worldwide. A variant-only callset emits no record where the sample matches
the reference, so such a row can never match and the reader is told "no variants found" instead of
being told their result.

**Whether a hom-ref row is reachable is a property of the callset, not of the module** — a gVCF
carries the reference block, an array genotypes every probe, a variant-only VCF carries nothing. So
the module cannot mark these rows and must not try; the decision is the annotator's, which is what
this module implements.

The design is `just-prs`'s, which solved the same problem for absent PGS scoring loci
(`just_prs.reference_allele`, `just_prs.prs.RestorationScope`). Three properties are taken directly:

- **Restoration is scoped to a position set the embedder supplies**, never applied blanket-wide.
  `RestorationScope` explicitly admits a custom `(chrom, pos)` set and names just-dna-lite as the
  embedder that would inject one. A module's authored hom-ref sites are that set, and they are tiny
  (2 for `lactose_tolerance`, 193 rows for `longevitymap`).
- **Provenance is a tri-state carried on the row**, never a boolean and never silent.
  `just_prs.reference_allele.RefSource` is `panel | fasta | unresolved`; ours is the `evidence`
  column below.
- **A case that cannot be established stays unestablished** rather than being filled with a plausible
  value — the rule behind that library's refusal to stand a single FASTA base in for an indel's REF.

Where we deliberately diverge from `just-prs`: `compute_prs` fills hom-ref for *every* absent locus
with a known reference allele, with no locality gate. That is sound for a polygenic score, where one
wrong locus among thousands moves the total by a rounding error. It is not sound here, where one
restored row becomes one rendered sentence about a person. **Absence is hom-ref or absence of
coverage, and a variant-only VCF cannot tell them apart** — so we additionally require local evidence
that the callset reached the neighbourhood (`max_flank_bp`), and we label every restored row so the
report can render it as inferred rather than observed.

That flanking test is coarse and is not a callability proof: it shows the caller emitted records near
the site, not that this base was covered at depth. The rigorous answer is the format's
`requires_callable` / `callable_from` (RM6) evaluated against a gVCF's `MIN_DP` with interval
containment, and those columns are unpopulated across our whole corpus. Until they are populated this
is the strongest honest gate available, which is why the evidence column exists and why the report
must never merge the two categories.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Optional

import polars as pl
from just_prs.prs import GenotypeInputMode

# Column names added to an annotated parquet by this module. Held here so the report and the
# manifest agree with the engine on one spelling.
EVIDENCE_COLUMN: str = "genotype_evidence"
FLANK_COLUMN: str = "restored_flank_bp"

#: The row carries a genotype the caller actually emitted.
EVIDENCE_CALLED: str = "called"
#: The row carries the reference genotype, inferred from the absence of any record at the site in a
#: callset that only records differences from the reference.
EVIDENCE_RESTORED: str = "restored_hom_ref"


class CallsetScope(StrEnum):
    """How much of the genome the callset attempted to call.

    This is the gate that ``GenotypeInputMode`` alone cannot supply, and it is the difference
    between a sound inference and a fabricated one. On a **whole-genome** callset, absence at a
    site means the caller looked and found nothing to report. On an **exome or gene panel**, the
    overwhelming majority of the genome was never captured, so absence carries no information at
    all — and the per-site flanking test is actively misleading there, because exonic variants
    cluster densely enough that an uncaptured intronic site a few kb away still has a neighbour.
    """

    WGS = "wgs"
    #: Exome, gene panel, or an array export — absence is uninformative outside the targeted set.
    TARGETED = "targeted"


#: A human WGS callset carries ~4.3–4.7M sites (measured across every sample in this repo). An exome
#: carries ~50–100k and a gene panel far fewer, so this sits ~4x below the WGS floor and ~10x above
#: the exome ceiling — far from either boundary rather than tuned to one file.
MIN_WGS_SITES: int = 1_000_000

#: Fraction of the callset's own span that lies within one ``max_flank_bp`` of some call — i.e. the
#: share of the genome where the per-site flanking test would pass. Deliberately the *same question*
#: that test asks, applied genome-wide, so the two gates are one rule at two scales rather than two
#: unrelated heuristics.
#:
#: Measured at **0.942–0.950** on all four WGS samples in this repo (the shortfall is centromeres and
#: assembly gaps, which no caller reaches), against **0.21** for a synthetic clustered callset of the
#: same order of magnitude in site count. 0.75 sits far from both.
#:
#: A percentile of the gap distribution was tried first and rejected: a callset of dense clusters far
#: apart — 20 calls 50 bp apart every 100 kb — puts 95% of its gaps at 50 bp, so p90 reports it as
#: dense while 79% of the genome is nowhere near a call. Breadth is not fooled by that shape because
#: it weights a gap by its length instead of counting it once.
MIN_WGS_BREADTH: float = 0.75

#: Scaffolds, alt contigs and decoys carry a handful of calls each and would skew the gap
#: distribution, so density is measured on the primary assembly only.
_PRIMARY_CONTIG = r"^(?:\d+|X|Y|MT)$"


@dataclass(frozen=True)
class RestorationContext:
    """Everything restoration needs about *this sample*, computed once for all modules.

    ``called_sites`` is the sample's ``(chrom, start)`` sorted by ``start`` within ``chrom``, which
    is what the flanking test joins against. Building it once matters: it is a 4.3M-row frame on a
    WGS genome and there are twelve modules in a normal run.
    """

    called_sites: pl.DataFrame
    mode: GenotypeInputMode
    scope: CallsetScope
    scope_reason: str
    max_flank_bp: int

    @property
    def enabled(self) -> bool:
        """Both gates must pass, and they answer different questions.

        ``mode`` answers *does this callset omit reference-matching sites* — an ``ALL_SITES`` input
        already carries the reference genotype as a record, so restoring would duplicate a row the
        caller supplied, without the caller's depth behind it.

        ``scope`` answers *does absence mean anything here* — see :class:`CallsetScope`.

        There is deliberately **no configuration flag beside these two**. Whether a hom-ref row can
        be inferred is a fact about the callset, and the callset is in front of us; a default would
        only be a guess at what these two already measure, and a wrong one would either fabricate
        rows on an exome or withhold real results on a genome.
        """
        return self.mode == GenotypeInputMode.VARIANT_ONLY and self.scope == CallsetScope.WGS


def _coverage_breadth(primary: pl.DataFrame, max_flank_bp: int) -> float:
    """Share of the callset's span that lies within one flank of a call.

    Each inter-call gap contributes at most ``2 * max_flank_bp`` — one flank reaching forward from
    the call before it and one reaching back from the call after — so a gap longer than that counts
    only the part a site could actually be restored in. Divided by the span the callset spreads over,
    that is the probability an arbitrary position in this callset passes the per-site flanking test.
    """
    gaps = primary.with_columns(
        pl.col("start").cast(pl.Int64).diff().over("chrom").alias("_gap")
    )
    covered = gaps.select(
        pl.min_horizontal(pl.col("_gap"), pl.lit(2 * max_flank_bp)).sum()
    ).item()
    span = (
        primary.group_by("chrom")
        .agg((pl.col("start").max() - pl.col("start").min()).cast(pl.Int64).alias("_span"))
        .select(pl.col("_span").sum())
        .item()
    )
    if not span:
        return 0.0
    return float(covered or 0) / float(span)


def detect_callset_scope(
    called_sites: pl.DataFrame, max_flank_bp: int
) -> tuple[CallsetScope, str]:
    """Classify a sorted ``(chrom, start)`` frame as whole-genome or targeted, and say why.

    Two signals, both cheap on a frame the caller has already sorted, and both chosen so that WGS and
    a targeted callset sit far from the threshold rather than either side of a tuned one: how many
    sites were called at all, and what share of the span is near a call.

    Returns ``(scope, reason)`` — the reason is logged and carried, because "we did not restore"
    with no explanation is the silent-zero failure this whole area keeps producing.
    """
    primary = called_sites.filter(pl.col("chrom").str.contains(_PRIMARY_CONTIG))
    sites = primary.height
    if sites < MIN_WGS_SITES:
        return CallsetScope.TARGETED, (
            f"only {sites:,} called sites on the primary assembly, below the {MIN_WGS_SITES:,} a "
            "whole-genome callset carries; absence outside a targeted region means nothing was "
            "attempted there, not that the sample matches the reference"
        )

    breadth = _coverage_breadth(primary.sort(["chrom", "start"]), max_flank_bp)
    if breadth < MIN_WGS_BREADTH:
        return CallsetScope.TARGETED, (
            f"only {breadth:.1%} of the callset's span lies within {max_flank_bp:,} bp of a call, "
            f"below the {MIN_WGS_BREADTH:.0%} a whole-genome callset shows; the calls are clustered, "
            "so a site having a nearby neighbour is not evidence that this site was covered"
        )

    return CallsetScope.WGS, (
        f"{sites:,} called sites on the primary assembly, {breadth:.1%} of the span within "
        f"{max_flank_bp:,} bp of a call"
    )


def infer_genotype_input_mode(vcf_lf: pl.LazyFrame) -> GenotypeInputMode:
    """Classify a prepared callset as variant-only or all-sites.

    Mirrors ``just_prs.prs._infer_genotype_input_mode`` — which is private, so it is re-derived here
    rather than imported — reading the two markers a reference-block callset leaves behind: a
    ``<NON_REF>`` symbolic allele, or a ``RefCall`` filter value.

    **Read this on the parquet we are about to annotate, not on the raw VCF.** The two can disagree,
    and when they do the parquet is the one that matters: our own quality filter drops
    ``FILTER=RefCall``, so a genuine gVCF arrives here with its reference blocks already removed and
    is variant-only *as far as annotation is concerned*. Classifying the raw file would return
    ``ALL_SITES``, disable restoration, and leave the reference rows unreportable from either
    direction.
    """
    cols = vcf_lf.collect_schema().names()
    checks: list[pl.Expr] = []
    if "alt" in cols:
        checks.append(
            pl.col("alt").cast(pl.Utf8).str.contains("NON_REF", literal=True).any().alias("non_ref")
        )
    if "filter" in cols:
        checks.append(
            pl.col("filter").cast(pl.Utf8).str.contains("RefCall", literal=True).any().alias("refcall")
        )
    if not checks:
        return GenotypeInputMode.VARIANT_ONLY
    found = vcf_lf.select(checks).collect()
    if any(bool(found[c][0]) for c in found.columns):
        return GenotypeInputMode.ALL_SITES
    return GenotypeInputMode.VARIANT_ONLY


def build_restoration_context(
    vcf_lf: pl.LazyFrame, max_flank_bp: int
) -> RestorationContext:
    """Collect the sample-side inputs restoration needs, once per run.

    The sort is paid once here and reused by both the scope detection and every module's flanking
    test — on a WGS genome that is a 4.3M-row frame and a normal run has twelve modules.
    """
    mode = infer_genotype_input_mode(vcf_lf)
    called_sites = (
        vcf_lf.select("chrom", "start")
        .unique()
        .sort(["chrom", "start"])
        .collect()
    )
    scope, reason = detect_callset_scope(called_sites, max_flank_bp)
    return RestorationContext(
        called_sites=called_sites,
        mode=mode,
        scope=scope,
        scope_reason=reason,
        max_flank_bp=max_flank_bp,
    )


def hom_ref_rows(lead_lf: pl.LazyFrame) -> Optional[pl.LazyFrame]:
    """The module rows whose authored genotype is the reference genotype.

    Returns ``None`` when the lead table cannot express the question — a 0.4 family carries no
    ``ref`` and no coordinates before format 0.6's RM43 fill, so `pharm_variants` is excluded here by
    the schema rather than by a name check.

    A genotype is hom-ref when every allele equals ``ref``. Written over the list rather than as
    ``[ref, ref]`` so a haploid contig (chrY, chrM) is handled by the same expression: a one-element
    genotype equal to ``ref`` is as hom-ref as a two-element one.
    """
    schema = lead_lf.collect_schema()
    names = set(schema.names())
    if not {"chrom", "start", "ref", "genotype"}.issubset(names):
        return None
    if schema["genotype"] != pl.List(pl.String):
        return None

    placed = lead_lf.filter(
        pl.col("chrom").is_not_null()
        & pl.col("start").is_not_null()
        & pl.col("ref").is_not_null()
    )

    # A locus the module spells with two different reference alleles is a locus the module does not
    # agree with itself about, and "which allele is the reference" is the entire question here.
    #
    # This is not hypothetical, and the cause is worth stating precisely because it is *not* a
    # curation error. ClinVar holds two real records at 5:112767222 under one rsID — Variation
    # 428095, the duplication `T -> TA`, and Variation 2583495, the deletion `TA -> T`, both
    # pathogenic. Our panel authors that faithfully and rsid-only: two rows, `T/TA` and `TA/TA`,
    # both meaning the duplication. `resolution.csv` then carries **two rows for that one
    # variant_key**, `locus_index` 0 and 1, and the compiler pairs every authored genotype with
    # every resolved locus — so `TA/TA` also lands against `ref=TA`, where it reads as hom-REF
    # instead of the hom-alt duplication the author wrote.
    #
    # Reading that literally would have restored 2,579 rows into one real genome's `pathogenic`
    # section and 1,183 into `cancer`, every one telling the reader they carry a pathogenic variant
    # they do not have — from a record the caller never emitted. The multi-locus variant_keys are
    # cancer 1,296 / cardio 540 / pathogenic 2,730, which match those hom-ref counts one for one.
    #
    # Ambiguity withholds. Two tests do it, because they see different halves of the same fan-out
    # and only one of them travels on an artifact we can already read.
    #
    # **`locus_count > 1` is the row-level predicate, and it is the complete one** (format 0.6,
    # RM87). It is stamped by the compiler at the expansion itself: `1` on any row that was not
    # expanded, `N` on every member of an `N`-way expansion. So it holds on a single row, with no
    # grouping and no comparison against siblings — which is exactly what the `ref`-spelling test
    # below cannot do.
    #
    # The `ref`-spelling test stays as the **pre-0.6 fallback**, because every module published on
    # HuggingFace today, and every one in `data/interim/v1_port/`, was compiled before the column
    # existed. It is partial by construction: it can only see an expansion whose members disagree
    # about `ref` *at one position*, which is the ClinVar dup/del shape above. A **same-`ref`**
    # expansion is invisible to it and is real — `--keep-par-twin` records a pseudoautosomal locus on
    # X and on Y with identical alleles, and a paralogous rsID can name two positions carrying the
    # same reference base. Measured on a compiled fixture of that shape: two rows, `ref="C"` on both,
    # `locus_count=2` on both, and the grouped test finds one `ref` spelling per position and passes
    # them through. Keep both tests until the last pre-0.6 artifact is gone.
    #
    # No `expanded_keys` gate is needed here, though it is needed by anything that *counts* rows: a
    # module compiled with no `resolution.csv` reads `locus_count=1` when the honest answer is
    # "nothing was checked", but those rows carry no coordinate at all and `placed` has already
    # dropped them.
    ambiguous_sites = (
        placed.group_by("chrom", "start")
        .agg(pl.col("ref").n_unique().alias("_ref_spellings"))
        .filter(pl.col("_ref_spellings") > 1)
        .select("chrom", "start")
    )

    candidates = placed.join(ambiguous_sites, on=["chrom", "start"], how="anti")
    if "locus_count" in names:
        candidates = candidates.filter(pl.col("locus_count").fill_null(1) <= 1)

    return candidates.filter(
        (pl.col("genotype").list.len() > 0)
        & pl.col("genotype").list.eval(pl.element() == pl.element().first()).list.all()
        & (pl.col("genotype").list.first() == pl.col("ref"))
    )


def _absent_sites(candidates: pl.LazyFrame, called: pl.DataFrame) -> pl.LazyFrame:
    """Candidate rows at sites where the callset emitted no record at all.

    A site the caller *did* emit is not restorable: it was seen, and whatever it says there — a
    different variant, a different genotype — is the observation. Restoring on top of it would
    manufacture a second, contradictory genotype for one locus.
    """
    return candidates.join(called.lazy(), on=["chrom", "start"], how="anti")


def _with_flanking_distance(
    candidates: pl.LazyFrame, called: pl.DataFrame, max_flank_bp: int
) -> pl.LazyFrame:
    """Keep candidates whose neighbourhood the callset demonstrably reached, and record how far.

    ``join_asof(strategy="nearest")`` gives the closest called position on the same contig; the
    distance to it is the evidence. A site on a contig the callset never touched gets a null and is
    dropped — which is the case this gate exists for, since a module site in an unsequenced region
    would otherwise be "restored" to hom-ref on no evidence whatsoever.
    """
    if called.is_empty():
        return candidates.head(0)

    nearest = called.rename({"start": "_called_start"}).with_columns(
        pl.col("_called_start").alias("_asof_key")
    )
    return (
        candidates.sort("start")
        .join_asof(
            nearest.lazy().sort("_asof_key"),
            left_on="start",
            right_on="_asof_key",
            by="chrom",
            strategy="nearest",
        )
        .with_columns(
            (pl.col("start").cast(pl.Int64) - pl.col("_called_start").cast(pl.Int64))
            .abs()
            .alias(FLANK_COLUMN)
        )
        .filter(pl.col(FLANK_COLUMN).is_not_null() & (pl.col(FLANK_COLUMN) <= max_flank_bp))
        .drop("_called_start", "_asof_key")
    )


def restored_rows(
    vcf_lf: pl.LazyFrame,
    lead_lf: pl.LazyFrame,
    module_name: str,
    context: RestorationContext,
) -> tuple[Optional[pl.LazyFrame], dict[str, int]]:
    """Synthesise the annotated rows for this module's reachable hom-ref sites.

    Returns ``(rows, stats)``; ``rows`` is ``None`` when the module states no hom-ref row this
    callset could support, so a caller can skip the concat entirely.

    The synthesised frame is built by pouring the module's own values into an **empty slice of the
    real VCF frame** (`vcf_lf.limit(0)`) and concatenating diagonally. That is what guarantees the
    restored rows carry exactly the annotated schema — column set, order and dtypes — rather than a
    hand-maintained copy of it that drifts the first time the VCF reader gains a column.
    """
    stats = {"hom_ref_rows": 0, "absent": 0, "restored": 0}
    if not context.enabled:
        return None, stats

    candidates = hom_ref_rows(lead_lf)
    if candidates is None:
        return None, stats

    stats["hom_ref_rows"] = candidates.select(pl.len()).collect().item()
    if not stats["hom_ref_rows"]:
        return None, stats

    absent = _absent_sites(candidates, context.called_sites)
    stats["absent"] = absent.select(pl.len()).collect().item()
    if not stats["absent"]:
        return None, stats

    eligible = _with_flanking_distance(absent, context.called_sites, context.max_flank_bp).collect()
    stats["restored"] = eligible.height
    if not eligible.height:
        return None, stats

    # The sample-side view of a restored site: the reference genotype the module itself states, at
    # the module's own coordinate. Everything the caller would have supplied (QUAL, DP, FILTER, GT)
    # stays null, because nothing was called — that absence is the honest record.
    vcf_shaped = eligible.select(
        pl.col("chrom"),
        pl.col("start"),
        pl.col("ref"),
        pl.col("genotype"),
    )
    module_side = eligible.drop("chrom", "start", "ref", "genotype")

    empty_vcf = vcf_lf.limit(0).collect()
    sample_rows = pl.concat([empty_vcf, vcf_shaped], how="diagonal_relaxed")

    suffix = f"_{module_name}"
    collisions = set(empty_vcf.columns) & set(module_side.columns)
    module_side = module_side.rename({c: f"{c}{suffix}" for c in collisions})

    # `hstack`, not `concat(how="horizontal")`: the two frames are the same height by construction
    # (both are `eligible` reshaped), and hstack says so and fails loudly if that ever stops being
    # true, where horizontal concat pads with nulls and is mid-deprecation for exactly that reason.
    return (
        sample_rows.hstack(module_side)
        .with_columns(
            pl.lit(EVIDENCE_RESTORED).alias(EVIDENCE_COLUMN),
            pl.col(FLANK_COLUMN).cast(pl.Int64),
        )
        .lazy()
    ), stats
