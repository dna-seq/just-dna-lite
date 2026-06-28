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
