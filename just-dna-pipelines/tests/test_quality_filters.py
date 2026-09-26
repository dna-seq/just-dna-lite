"""Tests for VCF quality-filter expression building.

Regression coverage for the FILTER "." vs "" mismatch: polars-bio decodes the
VCF missing FILTER sentinel ("." in the spec) as an empty string "". A
``pass_filters`` config of ``["PASS", "."]`` must therefore still keep records
whose FILTER column is "", otherwise GATK HaplotypeCaller-style VCFs (every
record FILTER=".") get filtered down to zero rows.
"""

import polars as pl

from just_dna_pipelines.module_config import (
    QualityFilters,
    _expand_pass_filters,
    build_quality_filter_expr,
    unstated_metric_counts,
)


def test_expand_pass_filters_treats_dot_and_empty_as_equivalent() -> None:
    expanded = set(_expand_pass_filters(["PASS", "."]))
    assert expanded == {"PASS", ".", ""}

    expanded_empty = set(_expand_pass_filters(["PASS", ""]))
    assert expanded_empty == {"PASS", ".", ""}


def test_expand_pass_filters_without_missing_sentinel_unchanged() -> None:
    assert set(_expand_pass_filters(["PASS"])) == {"PASS"}
    assert set(_expand_pass_filters(["PASS", "LowQual"])) == {"PASS", "LowQual"}


def test_filter_keeps_polars_bio_empty_string_filter() -> None:
    """A polars-bio FILTER column of "" must pass when "." is allowed."""
    df = pl.DataFrame(
        {
            "filter": ["", "", "PASS", "LowQual"],
            "DP": [30, 5, 40, 50],
            "qual": [50.0, 50.0, 50.0, 50.0],
        }
    )
    filters = QualityFilters(pass_filters=["PASS", "."], min_depth=10, min_qual=20.0)
    expr = build_quality_filter_expr(filters, df.columns)
    assert expr is not None

    kept = df.filter(expr)
    # Row 0 ("", DP=30) and row 2 (PASS, DP=40) pass; row 1 fails DP; row 3 fails FILTER.
    assert kept.height == 2
    assert kept["filter"].to_list() == ["", "PASS"]


def test_filter_drops_all_when_empty_not_allowed() -> None:
    """Sanity check: without the expansion the empty-string rows would be dropped."""
    df = pl.DataFrame({"filter": ["", "", ""]})
    # Directly exercising the un-expanded membership shows the original bug shape.
    assert df.filter(pl.col("filter").is_in(["PASS", "."])).height == 0
    # The real builder expands the allow-list, so it keeps them.
    filters = QualityFilters(pass_filters=["PASS", "."])
    expr = build_quality_filter_expr(filters, df.columns)
    assert expr is not None
    assert df.filter(expr).height == 3


# --- Unstated metrics: a VCF "." is unknown, not zero -------------------------------------------
#
# The shape below is taken from a real DRAGEN hard-filtered VCF (Livia Zaharia, Zenodo 19487816) at
# RHCE c.307 (rs676785, chr1:25408711): the RH targeted caller emits a PASS gene-conversion call whose
# FORMAT is only GT:GQ:PS, so it states no DP; the small-variant caller's call at the same position
# carries DP=22 and is FILTER=TargetedConflict. DRAGEN's GBA/CYP21A2/CYP2D6 callers state JDP
# instead of DP.


def _dragen_like_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "filter": ["PASS", "TargetedConflict", "PASS", "PASS", "PASS", "PASS", "PASS"],
            "DP": [None, 22, 5, None, None, 40, 40],
            "JDP": [None, None, None, 30, 4, None, None],
            "qual": [38.85, 5.57, 50.0, 60.0, 60.0, None, 10.0],
            "label": [
                "targeted_no_depth",
                "overruled_small_variant",
                "shallow",
                "jdp_deep",
                "jdp_shallow",
                "qual_unstated",
                "low_qual",
            ],
        },
        schema_overrides={"DP": pl.Int32, "JDP": pl.Int32},
    )


def _kept(filters: QualityFilters, df: pl.DataFrame) -> set[str]:
    expr = build_quality_filter_expr(filters, df.columns)
    assert expr is not None
    return set(df.filter(expr)["label"].to_list())


def test_keep_policy_judges_unstated_records_by_filter_alone() -> None:
    filters = QualityFilters(pass_filters=["PASS", "."], min_depth=10, min_qual=20.0)
    assert filters.unstated_metrics == "keep"
    # Kept: the PASS call stating no depth, the JDP=30 call, the PASS call stating no QUAL.
    # Dropped: the caller-filtered TargetedConflict (never resurrected), DP=5, JDP=4 (JDP is read
    # when DP is absent, so the fallback enforces the threshold rather than bypassing it), QUAL=10.
    assert _kept(filters, _dragen_like_frame()) == {"targeted_no_depth", "jdp_deep", "qual_unstated"}


def test_drop_policy_treats_unstated_as_failing() -> None:
    filters = QualityFilters(
        pass_filters=["PASS", "."], min_depth=10, min_qual=20.0, unstated_metrics="drop"
    )
    # JDP still counts as a stated depth under drop; only genuinely unstated records go.
    assert _kept(filters, _dragen_like_frame()) == {"jdp_deep"}


def test_policy_only_differs_on_unstated_rows() -> None:
    """keep and drop agree on every record that states its metrics; they differ exactly on the rest."""
    df = _dragen_like_frame()
    base = dict(pass_filters=["PASS", "."], min_depth=10, min_qual=20.0)
    kept = _kept(QualityFilters(**base), df)
    dropped = _kept(QualityFilters(**base, unstated_metrics="drop"), df)
    unstated = set(
        df.filter(pl.coalesce("DP", "JDP").is_null() | pl.col("qual").is_null())["label"].to_list()
    )
    assert kept - dropped == unstated & kept
    assert dropped <= kept


def test_policy_moves_the_config_hash() -> None:
    """A normalized parquet built under one policy must read as stale under the other."""
    base = dict(pass_filters=["PASS", "."], min_depth=10, min_qual=20.0)
    assert QualityFilters(**base).config_hash() != QualityFilters(**base, unstated_metrics="drop").config_hash()


def test_unstated_metric_counts_reports_what_abstention_kept() -> None:
    df = _dragen_like_frame()
    filters = QualityFilters(pass_filters=["PASS", "."], min_depth=10, min_qual=20.0)
    kept = df.filter(build_quality_filter_expr(filters, df.columns))
    # Derived from the kept rows, not counted by hand: every kept row that states no depth
    # (neither DP nor JDP) or no QUAL survived only because the threshold abstained.
    assert unstated_metric_counts(filters, kept.lazy()) == {
        "kept_depth_unstated": kept.select(pl.coalesce("DP", "JDP").is_null().sum()).item(),
        "kept_qual_unstated": kept.select(pl.col("qual").is_null().sum()).item(),
    }
    assert set(kept.filter(pl.coalesce("DP", "JDP").is_null())["label"].to_list()) == {"targeted_no_depth"}
    assert unstated_metric_counts(
        QualityFilters(**{**filters.model_dump(), "unstated_metrics": "drop"}), kept.lazy()
    ) == {}
