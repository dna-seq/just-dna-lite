"""Read one module's results across a set of genomes and say what looks wrong.

Three questions, each answered from files a finished run left on disk:

1. **Coverage** — for every authored locus, in how many genomes it was *called and matched*, *restored
   as hom-ref*, *called with a genotype the module never authored*, *called with a different
   reference allele*, or *not observed at all*. The last two are the ones an author acts on: a
   paper's variant that no genome carries, and a locus every genome is called at but none matches
   (missing genotype rows, a strand or allele-orientation mistake, a build mismatch).
2. **Scores** — per genome, the summed authored ``weight`` over matched rows, and across genomes the
   shape of that distribution: constant, one-sided, dominated by one variant, carried by inferred
   rows, or shifted by a genotype every genome shares.
3. **Join health** — how the engine could join the module at all, rows without coordinates,
   ambiguous (expansion) rows, phased rows that can never match, and modules skipped or failed.

Everything here is a reading, not a verdict. The thresholds are heuristics chosen to surface
something worth a look, and every finding says which one fired. A check that could not run is
reported as not assessed, never as passed.

Presence is taken from ``user_vcf_normalized.parquet`` (every call the sample has at the module's
positions) and matches from the run's ``{module}_weights.parquet``, so a position the engine
discarded for a reference-allele disagreement still shows up here as *called with a different ref*.
"""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Literal, Optional

import polars as pl
from pydantic import BaseModel, Field

from just_dna_pipelines.annotation.hf_logic import (
    _lead_join_strategy,
    _normalize_lead_genotype,
    _normalize_vcf_contigs,
    _unmatchable_phased_rows,
)
from just_dna_pipelines.annotation.hf_modules import ModuleInfo, ModuleTable, scan_module_table

# Heuristic thresholds. Each finding names the one that fired, so none of these is hidden policy.
DOMINANT_SHARE = 0.5          # one variant carries more than this share of a genome's |weight|
RESTORED_SHARE = 0.5          # inferred hom-ref rows carry more than this share of |weight|
OUTLIER_FACTOR = 10.0         # authored |weight| more than this many times the module's median |weight|
MIN_SAMPLES_FOR_SHAPE = 3     # distribution-shape findings need at least this many annotated genomes
PREVIEW_LIMIT = 25            # loci named per finding / in the preview table

Status = Literal["called_matched", "restored_hom_ref", "called_unmatched", "called_ref_mismatch", "not_observed"]
STATUSES: tuple[str, ...] = (
    "called_matched",
    "restored_hom_ref",
    "called_unmatched",
    "called_ref_mismatch",
    "not_observed",
)
EVIDENCE_RESTORED = "restored_hom_ref"


class SampleInput(BaseModel):
    """Where one genome's files for this run are."""

    sample_id: str
    normalized_path: Path
    annotated_path: Optional[Path] = None
    skipped_reason: Optional[str] = None
    failed_reason: Optional[str] = None


class SampleScore(BaseModel):
    sample_id: str
    status: Literal["annotated", "skipped", "failed", "no_output"]
    reason: Optional[str] = None
    matched_rows: int = 0
    matched_loci: int = 0
    restored_rows: int = 0
    total_weight: Optional[float] = None
    positive_weight: Optional[float] = None
    negative_weight: Optional[float] = None
    top_variant: Optional[str] = None
    top_genotype: Optional[str] = None
    top_weight: Optional[float] = None
    top_share: Optional[float] = Field(None, description="Top variant's share of this genome's summed |weight|")
    restored_weight_share: Optional[float] = Field(None, description="Share of |weight| carried by inferred hom-ref rows")


class ScoreStats(BaseModel):
    n: int
    mean: Optional[float] = None
    sd: Optional[float] = None
    median: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None


class Finding(BaseModel):
    code: str
    severity: Literal["info", "warning", "problem", "not_assessed"]
    message: str
    loci: list[str] = Field(default_factory=list)
    samples: list[str] = Field(default_factory=list)
    count: Optional[int] = None


class LocusCoverage(BaseModel):
    locus: str
    rsid: Optional[str] = None
    chrom: Optional[str] = None
    start: Optional[int] = None
    ref: Optional[str] = None
    authored_genotypes: list[str]
    called_matched: int
    restored_hom_ref: int
    called_unmatched: int
    called_ref_mismatch: int
    not_observed: int
    observed_unmatched_genotypes: list[str] = Field(default_factory=list)


class ValidationReport(BaseModel):
    module: str
    lead_table: str
    join_strategy: str
    join_reason: str
    lead_rows: int
    loci: int
    rows_without_coordinates: Optional[int] = None
    ambiguous_rows: Optional[int] = Field(None, description="Rows with locus_count > 1 (an rsID placed at several loci); None if the column is absent")
    phased_rows: int = 0
    phased_rows_unmatchable: int = 0
    samples_requested: int
    samples_annotated: int
    coverage_totals: dict[str, int]
    scores: list[SampleScore]
    score_stats: ScoreStats
    findings: list[Finding]
    loci_preview: list[LocusCoverage] = Field(description="The loci most worth a look, worst first")
    coverage_path: Optional[str] = Field(None, description="Parquet with one row per (sample, locus): the full matrix")
    thresholds: dict[str, float]


def _genotype_text(expr: pl.Expr) -> pl.Expr:
    return expr.list.join("/")


def _lead_frame(info: ModuleInfo) -> tuple[pl.LazyFrame, pl.LazyFrame]:
    """``(raw lead, lead with genotype in the engine's representation)``."""
    raw = scan_module_table(info.name, ModuleTable.LEAD, module_info=info)
    return raw, _normalize_lead_genotype(raw)


def _nonempty(name: str) -> pl.Expr:
    """*name* with empty strings read as null, so a blank ID cell cannot become a locus key."""
    col = pl.col(name).cast(pl.String)
    return pl.when(col.str.len_chars() > 0).then(col)


def _position_key() -> pl.Expr:
    return pl.concat_str([pl.col("chrom"), pl.col("start").cast(pl.String)], separator=":")


def _locus_expr(names: set[str], rsid_column: str = "rsid") -> pl.Expr:
    """The key one authored locus is known by: variant_key, else rsid, else chrom:start.

    *rsid_column* names where the module's own rsID sits: ``rsid`` in the lead table, but
    ``rsid_{module}`` in a run's output, where plain ``rsid`` is the VCF's ID cell.
    """
    candidates: list[pl.Expr] = []
    if "variant_key" in names:
        candidates.append(_nonempty("variant_key"))
    if rsid_column in names:
        candidates.append(_nonempty(rsid_column))
    if {"chrom", "start"}.issubset(names):
        candidates.append(_position_key())
    return pl.coalesce(candidates).alias("locus")


def build_loci(lead: pl.DataFrame) -> pl.DataFrame:
    """One row per authored locus: coordinates, module ref, authored genotypes."""
    names = set(lead.columns)
    cols = [c for c in ("rsid", "chrom", "start", "ref") if c in names]
    with_key = lead.with_columns(
        _locus_expr(names),
        _genotype_text(pl.col("genotype")).alias("_gt"),
    )
    agg = [pl.col(c).drop_nulls().first().alias(c) for c in cols]
    agg.append(pl.col("_gt").drop_nulls().unique().sort().alias("authored_genotypes"))
    loci = with_key.group_by("locus", maintain_order=True).agg(agg)
    for c in ("rsid", "chrom", "ref"):
        if c not in loci.columns:
            loci = loci.with_columns(pl.lit(None, dtype=pl.String).alias(c))
    if "start" not in loci.columns:
        loci = loci.with_columns(pl.lit(None, dtype=pl.UInt32).alias("start"))
    return loci


def _presence(normalized: Path, loci: pl.DataFrame, strategy: str) -> pl.DataFrame:
    """The sample's calls at the module's loci: ``locus, sample_ref, sample_genotype``."""
    vcf = _normalize_vcf_contigs(pl.scan_parquet(normalized).select("chrom", "start", "rsid", "ref", "genotype"))
    if strategy == "position":
        keys = loci.filter(pl.col("chrom").is_not_null() & pl.col("start").is_not_null()).select(
            "locus", "chrom", pl.col("start").cast(pl.UInt32)
        )
        hits = vcf.join(keys.lazy(), on=["chrom", "start"], how="inner")
    else:
        keys = loci.filter(pl.col("rsid").is_not_null()).select("locus", "rsid")
        hits = (
            vcf.with_columns(pl.col("rsid").str.split(";").alias("_rs"))
            .explode("_rs", empty_as_null=True)
            .join(keys.lazy(), left_on="_rs", right_on="rsid", how="inner")
        )
    return hits.select(
        "locus",
        pl.col("ref").alias("sample_ref"),
        _genotype_text(pl.col("genotype")).alias("sample_genotype"),
    ).collect()


def _matched(annotated: Path, module: str, loci: pl.DataFrame) -> pl.DataFrame:
    """Matched rows of the run's module parquet: ``locus, matched_genotype, weight, evidence``."""
    lf = pl.scan_parquet(annotated)
    schema = set(lf.collect_schema().names())
    empty = pl.DataFrame(schema={"locus": pl.String, "matched_genotype": pl.String, "weight": pl.Float64, "evidence": pl.String})
    if "module" not in schema:
        return empty
    lf = lf.filter(pl.col("module").is_not_null())
    module_rsid = f"rsid_{module}"
    if "variant_key" in schema or module_rsid in schema:
        lf = lf.with_columns(_locus_expr(schema, rsid_column=module_rsid))
    else:
        # An rsid-joined module with no variant_key: the only trace of which authored row matched is
        # the VCF's own ID cell, which may list several identifiers. Key on the one the module names.
        lf = (
            lf.with_columns(pl.col("rsid").str.split(";").alias("_rs"))
            .explode("_rs", empty_as_null=True)
            .join(loci.lazy().select(pl.col("rsid").alias("_rs"), "locus"), on="_rs", how="inner")
            .drop("_rs")
        )
    return lf.select(
        "locus",
        _genotype_text(pl.col("genotype")).alias("matched_genotype"),
        (pl.col("weight").cast(pl.Float64) if "weight" in schema else pl.lit(None, dtype=pl.Float64)).alias("weight"),
        (pl.col("genotype_evidence") if "genotype_evidence" in schema else pl.lit("called")).alias("evidence"),
    ).collect()


def classify_sample(
    sample: SampleInput, loci: pl.DataFrame, strategy: str, module: str
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """``(coverage rows, matched rows)`` for one annotated genome."""
    if sample.annotated_path is None:
        raise ValueError(f"{sample.sample_id}: no annotated parquet to classify")
    matched = _matched(sample.annotated_path, module, loci)
    presence = _presence(sample.normalized_path, loci, strategy)
    matched_status = (
        matched.group_by("locus")
        .agg(
            (pl.col("evidence") != EVIDENCE_RESTORED).any().alias("_called"),
            pl.col("matched_genotype").first(),
        )
    )
    per_locus_presence = presence.group_by("locus").agg(
        pl.col("sample_ref").first(),
        pl.col("sample_genotype").unique().sort().str.join(",").alias("sample_genotype"),
    )
    cov = (
        loci.select("locus", pl.col("ref").alias("module_ref"))
        .join(matched_status, on="locus", how="left")
        .join(per_locus_presence, on="locus", how="left")
        .with_columns(
            pl.when(pl.col("_called") == True)  # noqa: E712 — tri-state column, null means no match
            .then(pl.lit("called_matched"))
            .when(pl.col("_called") == False)  # noqa: E712
            .then(pl.lit("restored_hom_ref"))
            .when(pl.col("sample_ref").is_not_null() & pl.col("module_ref").is_not_null() & (pl.col("sample_ref") != pl.col("module_ref")))
            .then(pl.lit("called_ref_mismatch"))
            .when(pl.col("sample_ref").is_not_null())
            .then(pl.lit("called_unmatched"))
            .otherwise(pl.lit("not_observed"))
            .alias("status")
        )
        .select(
            pl.lit(sample.sample_id).alias("sample_id"),
            "locus",
            "status",
            "sample_genotype",
            "sample_ref",
            "matched_genotype",
        )
    )
    return cov, matched


def score_sample(sample_id: str, matched: pl.DataFrame) -> SampleScore:
    if matched.is_empty():
        return SampleScore(sample_id=sample_id, status="annotated", total_weight=0.0, positive_weight=0.0, negative_weight=0.0)
    w = matched.with_columns(pl.col("weight").fill_null(0.0), pl.col("weight").fill_null(0.0).abs().alias("_abs"))
    total_abs = float(w["_abs"].sum())
    top = w.sort("_abs", descending=True).row(0, named=True)
    restored = w.filter(pl.col("evidence") == EVIDENCE_RESTORED)
    return SampleScore(
        sample_id=sample_id,
        status="annotated",
        matched_rows=w.height,
        matched_loci=w["locus"].n_unique(),
        restored_rows=restored.height,
        total_weight=round(float(w["weight"].sum()), 6),
        positive_weight=round(float(w.filter(pl.col("weight") > 0)["weight"].sum()), 6),
        negative_weight=round(float(w.filter(pl.col("weight") < 0)["weight"].sum()), 6),
        top_variant=top["locus"],
        top_genotype=top["matched_genotype"],
        top_weight=top["weight"],
        top_share=round(top["_abs"] / total_abs, 4) if total_abs else None,
        restored_weight_share=round(float(restored["_abs"].sum()) / total_abs, 4) if total_abs else None,
    )


def _stats(values: list[float]) -> ScoreStats:
    if not values:
        return ScoreStats(n=0)
    return ScoreStats(
        n=len(values),
        mean=round(statistics.fmean(values), 6),
        sd=round(statistics.pstdev(values), 6) if len(values) > 1 else None,
        median=round(statistics.median(values), 6),
        min=min(values),
        max=max(values),
    )


def _coverage_findings(wide: pl.DataFrame, annotated: int) -> list[Finding]:
    findings: list[Finding] = []
    if annotated == 0:
        return [Finding(code="coverage_not_assessed", severity="not_assessed", message="No genome produced output for this module, so coverage could not be measured.")]

    never = wide.filter(pl.col("not_observed") == annotated)
    if never.height:
        findings.append(Finding(
            code="loci_never_observed",
            severity="warning",
            count=never.height,
            loci=never["locus"].head(PREVIEW_LIMIT).to_list(),
            message=(
                f"{never.height} of {wide.height} loci have no call in any of the {annotated} genomes. In a "
                "variant-only VCF an absent call usually means hom-ref (or no coverage there); if the module "
                "authors no hom-ref row, these loci can never contribute. Decide whether to keep them, author "
                "the reference genotype, or test on genomes that carry them."
            ),
        ))
    unmatched = wide.filter((pl.col("called_matched") + pl.col("restored_hom_ref") == 0) & (pl.col("called_unmatched") > 0))
    if unmatched.height:
        findings.append(Finding(
            code="called_but_never_matched",
            severity="problem",
            count=unmatched.height,
            loci=unmatched["locus"].head(PREVIEW_LIMIT).to_list(),
            message=(
                f"{unmatched.height} loci are called in at least one genome but no genome's genotype matches any "
                "authored genotype. Compare observed_unmatched_genotypes with authored_genotypes in loci_preview: "
                "this is the signature of a missing genotype row, a strand/allele-orientation mistake, or an "
                "effect allele that is really the other one."
            ),
        ))
    ref_mm = wide.filter(pl.col("called_ref_mismatch") > 0)
    if ref_mm.height:
        findings.append(Finding(
            code="reference_allele_mismatch",
            severity="problem",
            count=ref_mm.height,
            loci=ref_mm["locus"].head(PREVIEW_LIMIT).to_list(),
            message=(
                f"{ref_mm.height} loci are called with a reference allele different from the module's `ref`. The "
                "engine discards those rows (it would otherwise report a different variant). Usually a wrong "
                "coordinate, a different indel spelling, or a GRCh37 position in a GRCh38 module."
            ),
        ))
    return findings


def _score_findings(scores: list[SampleScore], lead: pl.DataFrame, shared: pl.DataFrame) -> list[Finding]:
    findings: list[Finding] = []
    annotated = [s for s in scores if s.status == "annotated"]
    zero = [s.sample_id for s in annotated if s.matched_rows == 0]
    if zero:
        findings.append(Finding(
            code="genomes_with_no_matches",
            severity="warning",
            samples=zero,
            count=len(zero),
            message=f"{len(zero)} of {len(annotated)} annotated genomes matched no module row at all.",
        ))

    if "weight" in lead.columns:
        abs_w = lead.select(pl.col("weight").cast(pl.Float64).abs()).to_series().drop_nulls()
        nonzero = abs_w.filter(abs_w > 0)
        if nonzero.len() == 0:
            findings.append(Finding(
                code="all_weights_zero",
                severity="info",
                message="Every authored weight is 0, so there is no score to distribute (normal for a drug-response or purely descriptive module).",
            ))
            return findings
        median = float(nonzero.median())
        outliers = lead.with_columns(_locus_expr(set(lead.columns))).filter(
            pl.col("weight").cast(pl.Float64).abs() > OUTLIER_FACTOR * median
        )
        if outliers.height:
            findings.append(Finding(
                code="weight_outliers",
                severity="warning",
                count=outliers.height,
                loci=outliers["locus"].unique(maintain_order=True).head(PREVIEW_LIMIT).to_list(),
                message=(
                    f"{outliers.height} authored rows have |weight| above {OUTLIER_FACTOR:g}x the module's median "
                    f"non-zero |weight| ({median:.4g}). One such row can decide every genome's score; check its scale "
                    "against the others (a beta pasted where a log-odds belongs, a missing minus sign, a percent)."
                ),
            ))
    else:
        findings.append(Finding(code="scores_not_assessed", severity="not_assessed", message="The lead table has no weight column, so no score distribution exists."))
        return findings

    if len(annotated) < MIN_SAMPLES_FOR_SHAPE:
        findings.append(Finding(
            code="distribution_not_assessed",
            severity="not_assessed",
            message=f"Only {len(annotated)} genome(s) annotated; distribution-shape checks need at least {MIN_SAMPLES_FOR_SHAPE}.",
        ))
        return findings

    totals = [s.total_weight or 0.0 for s in annotated]
    if len(set(totals)) == 1:
        findings.append(Finding(
            code="constant_score",
            severity="problem",
            message=f"Every genome scores exactly {totals[0]:g}. The module cannot tell these genomes apart.",
        ))
    elif all(t > 0 for t in totals) or all(t < 0 for t in totals):
        side = "positive" if totals[0] > 0 else "negative"
        findings.append(Finding(
            code="one_sided_scores",
            severity="warning",
            message=(
                f"All {len(totals)} genomes land on the {side} side (range {min(totals):g} to {max(totals):g}). "
                "Possible for a small set, but often a sign that a common genotype carries weight (see "
                "weight_shared_by_all_genomes) or that signs are inverted."
            ),
        ))

    dominated = [s.sample_id for s in annotated if s.top_share is not None and s.top_share > DOMINANT_SHARE and s.matched_rows >= 3]
    if len(dominated) * 2 > len(annotated):
        tops = sorted({s.top_variant for s in annotated if s.sample_id in dominated and s.top_variant})
        findings.append(Finding(
            code="dominated_by_one_variant",
            severity="warning",
            samples=dominated,
            loci=tops[:PREVIEW_LIMIT],
            count=len(dominated),
            message=(
                f"In {len(dominated)} of {len(annotated)} genomes a single variant carries more than "
                f"{DOMINANT_SHARE:.0%} of the summed |weight|; the score is effectively that one locus."
            ),
        ))

    carried = [s.sample_id for s in annotated if s.restored_weight_share is not None and s.restored_weight_share > RESTORED_SHARE]
    if len(carried) * 2 > len(annotated):
        findings.append(Finding(
            code="score_carried_by_inferred_rows",
            severity="warning",
            samples=carried,
            count=len(carried),
            message=(
                f"In {len(carried)} of {len(annotated)} genomes more than {RESTORED_SHARE:.0%} of |weight| comes from "
                "hom-ref rows restored from the *absence* of a call, not from observed genotypes."
            ),
        ))

    if shared.height:
        findings.append(Finding(
            code="weight_shared_by_all_genomes",
            severity="warning",
            count=shared.height,
            loci=shared["locus"].head(PREVIEW_LIMIT).to_list(),
            message=(
                f"{shared.height} (locus, genotype) rows with non-zero weight match in every annotated genome, "
                f"adding {float(shared['weight'].sum()):g} to each score. A genotype everyone carries shifts the whole "
                "distribution without separating anyone; check whether the risk/benefit allele is the common one."
            ),
        ))
    return findings


def _health_findings(
    strategy: str,
    reason: str,
    no_coords: Optional[int],
    lead_rows: int,
    ambiguous: Optional[int],
    phased: tuple[int, int],
    scores: list[SampleScore],
) -> list[Finding]:
    findings: list[Finding] = []
    if strategy == "unsupported":
        findings.append(Finding(code="module_not_joinable", severity="problem", message=f"The engine cannot join this module to a VCF: {reason}."))
    elif strategy == "rsid":
        findings.append(Finding(
            code="rsid_join_only",
            severity="warning",
            message=(
                "The lead table has no usable coordinates, so the engine joins on rsID + genotype. A VCF with an empty "
                "ID column (most WGS callers' output) matches nothing. Resolve coordinates (enrich) before trusting a run."
            ),
        ))
    if no_coords and strategy == "position":
        findings.append(Finding(
            code="rows_without_coordinates",
            severity="warning",
            count=no_coords,
            message=f"{no_coords} of {lead_rows} lead rows carry no chrom/start; under a position join they can never match.",
        ))
    if ambiguous:
        findings.append(Finding(
            code="ambiguous_positions",
            severity="info",
            count=ambiguous,
            message=f"{ambiguous} rows come from an rsID placed at several loci (locus_count > 1); matches on them render with a 'position ambiguous' caveat and are never restored.",
        ))
    if phased[1]:
        findings.append(Finding(
            code="phased_rows_unmatchable",
            severity="problem",
            count=phased[1],
            message=f"{phased[1]} of {phased[0]} phased genotype rows are held in homolog order rather than sorted order; the VCF side sorts, so they match nothing.",
        ))
    for s in scores:
        if s.status in ("skipped", "failed", "no_output"):
            findings.append(Finding(
                code=f"module_{s.status}",
                severity="problem" if s.status == "failed" else "warning",
                samples=[s.sample_id],
                message=f"{s.sample_id}: {s.reason or 'the run left no output for this module'}",
            ))
    return findings


def _preview(wide: pl.DataFrame) -> list[LocusCoverage]:
    ranked = wide.with_columns(
        (
            pl.col("called_ref_mismatch") * 4
            + ((pl.col("called_matched") + pl.col("restored_hom_ref") == 0) & (pl.col("called_unmatched") > 0)).cast(pl.Int32) * 3
            + pl.col("called_unmatched")
        ).alias("_rank")
    ).sort(["_rank", "not_observed"], descending=True)
    return [
        LocusCoverage(**{k: v for k, v in row.items() if k != "_rank"})
        for row in ranked.head(PREVIEW_LIMIT).iter_rows(named=True)
    ]


def validate_module_run(
    info: ModuleInfo,
    samples: list[SampleInput],
    coverage_out: Optional[Path] = None,
) -> ValidationReport:
    """Coverage, score distribution and join health for one module over the given genomes."""
    raw_lf, lead_lf = _lead_frame(info)
    strategy, reason = _lead_join_strategy(lead_lf)
    phased = _unmatchable_phased_rows(raw_lf)
    lead = lead_lf.collect()
    names = set(lead.columns)
    no_coords = int(lead["chrom"].is_null().sum()) if "chrom" in names else None
    ambiguous = int((lead["locus_count"] > 1).sum()) if "locus_count" in names else None

    loci = build_loci(lead) if "genotype" in names else pl.DataFrame()
    scores: list[SampleScore] = []
    coverage_parts: list[pl.DataFrame] = []
    matched_parts: list[pl.DataFrame] = []
    for sample in samples:
        if sample.failed_reason:
            scores.append(SampleScore(sample_id=sample.sample_id, status="failed", reason=sample.failed_reason))
            continue
        if sample.skipped_reason:
            scores.append(SampleScore(sample_id=sample.sample_id, status="skipped", reason=sample.skipped_reason))
            continue
        if sample.annotated_path is None or not sample.annotated_path.exists() or strategy == "unsupported":
            scores.append(SampleScore(sample_id=sample.sample_id, status="no_output"))
            continue
        cov, matched = classify_sample(sample, loci, strategy, info.name)
        coverage_parts.append(cov)
        matched_parts.append(matched.with_columns(pl.lit(sample.sample_id).alias("sample_id")))
        scores.append(score_sample(sample.sample_id, matched))

    annotated = sum(1 for s in scores if s.status == "annotated")
    coverage = pl.concat(coverage_parts) if coverage_parts else pl.DataFrame(
        schema={"sample_id": pl.String, "locus": pl.String, "status": pl.String, "sample_genotype": pl.String, "sample_ref": pl.String, "matched_genotype": pl.String}
    )
    counts = (
        coverage.group_by("locus").agg([(pl.col("status") == s).sum().cast(pl.Int64).alias(s) for s in STATUSES])
        if not coverage.is_empty()
        else pl.DataFrame(schema={"locus": pl.String, **{s: pl.Int64 for s in STATUSES}})
    )
    unmatched_gts = (
        coverage.filter(pl.col("status") == "called_unmatched")
        .select("locus", pl.col("sample_genotype").str.split(","))
        .explode("sample_genotype", empty_as_null=True)
        .group_by("locus")
        .agg(pl.col("sample_genotype").unique().sort().alias("observed_unmatched_genotypes"))
    )
    wide = (
        loci.join(counts, on="locus", how="left")
        .join(unmatched_gts, on="locus", how="left")
        .with_columns([pl.col(s).fill_null(0) for s in STATUSES])
        .with_columns(pl.col("observed_unmatched_genotypes").fill_null([]))
        if not loci.is_empty()
        else pl.DataFrame()
    )

    shared = pl.DataFrame(schema={"locus": pl.String, "matched_genotype": pl.String, "weight": pl.Float64})
    if matched_parts and annotated >= MIN_SAMPLES_FOR_SHAPE:
        all_matched = pl.concat(matched_parts)
        shared = (
            all_matched.filter(pl.col("weight").fill_null(0.0) != 0)
            .group_by("locus", "matched_genotype")
            .agg(pl.col("sample_id").n_unique().alias("_n"), pl.col("weight").first())
            .filter(pl.col("_n") == annotated)
            .drop("_n")
        )

    findings = (
        _health_findings(strategy, reason, no_coords, lead.height, ambiguous, phased, scores)
        + (_coverage_findings(wide, annotated) if not wide.is_empty() else [])
        + _score_findings(scores, lead, shared)
    )
    if coverage_out is not None and not coverage.is_empty():
        coverage_out.parent.mkdir(parents=True, exist_ok=True)
        coverage.write_parquet(coverage_out)

    return ValidationReport(
        module=info.name,
        lead_table=info.lead_table,
        join_strategy=strategy,
        join_reason=reason,
        lead_rows=lead.height,
        loci=loci.height,
        rows_without_coordinates=no_coords,
        ambiguous_rows=ambiguous,
        phased_rows=phased[0],
        phased_rows_unmatchable=phased[1],
        samples_requested=len(samples),
        samples_annotated=annotated,
        coverage_totals={s: int(coverage.filter(pl.col("status") == s).height) for s in STATUSES},
        scores=scores,
        score_stats=_stats([s.total_weight for s in scores if s.status == "annotated" and s.total_weight is not None]),
        findings=findings,
        loci_preview=_preview(wide) if not wide.is_empty() else [],
        coverage_path=str(coverage_out) if coverage_out is not None and not coverage.is_empty() else None,
        thresholds={
            "dominant_share": DOMINANT_SHARE,
            "restored_share": RESTORED_SHARE,
            "outlier_factor": OUTLIER_FACTOR,
            "min_samples_for_shape": MIN_SAMPLES_FOR_SHAPE,
        },
    )
