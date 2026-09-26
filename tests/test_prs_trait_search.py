"""By Trait search matches both names, and age finds the longevity scores."""

from __future__ import annotations

import polars as pl
from prs_ui.mixin import TRAIT_GROUP_BY_ONTOLOGY, TRAIT_GROUP_BY_REPORTED
from reflex_mui_datagrid.polars_utils import apply_filter_model

from webui.state import _trait_filter_searches_both, _trait_summary_frame


def _catalog_rows() -> pl.DataFrame:
    """Two longevity scores plus neighbors that look like an age search."""
    return pl.DataFrame(
        {
            "pgs_id": ["PGS000906", "PGS002795", "PGS001915", "PGS009999", "PGS008888"],
            "trait_reported": [
                "Longevity",
                "Longevity (>90th survival percentile)",
                "Age at menarche",
                "Body fat percentage",
                "Neuroimaging measurement",
            ],
            "trait_efo": [
                "life span determination trait",
                "life span determination trait",
                "age at menarche",
                "body fat percentage",
                "neuroimaging measurement",
            ],
            "trait_efo_id": [
                "OBA_VT0005372",
                "OBA_VT0005372",
                "EFO_0004703",
                "EFO_0004339",
                "EFO_0004300",
            ],
            "n_variants": [5, 8, 100, 12, 40],
        }
    )


def _contains(field: str, value: str) -> dict:
    return {
        "items": [{"field": field, "operator": "contains", "value": value}],
        "logicOperator": "and",
    }


def test_ontology_group_is_found_by_the_reported_name() -> None:
    """The mapped label is 'life span determination trait', not Longevity."""
    summary, mapping = _trait_summary_frame(_catalog_rows(), TRAIT_GROUP_BY_ONTOLOGY)
    lifespan = summary.filter(pl.col("trait") == "life span determination trait")
    assert lifespan.height == 1
    assert "longevity" not in lifespan["trait"][0].lower()
    assert "Longevity" in lifespan["trait_reported"][0]
    assert set(mapping["life span determination trait"]) == {"PGS000906", "PGS002795"}

    missed = apply_filter_model(summary.lazy(), _contains("trait", "longevity")).collect()
    assert missed.height == 0

    found = apply_filter_model(
        summary.lazy(),
        _trait_filter_searches_both(_contains("trait", "longevity")),
    ).collect()
    assert found["trait"].to_list() == ["life span determination trait"]


def test_reported_grouping_keeps_the_ontology_name_searchable() -> None:
    summary, mapping = _trait_summary_frame(_catalog_rows(), TRAIT_GROUP_BY_REPORTED)
    assert mapping["Longevity"] == ["PGS000906"]

    found = apply_filter_model(
        summary.lazy(),
        _trait_filter_searches_both(_contains("trait", "life span")),
    ).collect()
    assert set(found["trait"].to_list()) == {
        "Longevity",
        "Longevity (>90th survival percentile)",
    }


def test_age_filter_finds_longevity_without_tagging_imaging() -> None:
    """Longevity is named 'life span', so age is linked on purpose.

    'percentage' still matches because it contains the letters age. 'imaging'
    contains 'aging' only as part of a longer word and stays out.
    """
    summary, _mapping = _trait_summary_frame(_catalog_rows(), TRAIT_GROUP_BY_ONTOLOGY)
    matched = apply_filter_model(
        summary.lazy(),
        _trait_filter_searches_both(_contains("trait", "age")),
    ).collect()
    assert set(matched["trait"].to_list()) == {
        "life span determination trait",
        "age at menarche",
        "body fat percentage",
    }

    ageing = apply_filter_model(
        summary.lazy(),
        _trait_filter_searches_both(_contains("trait", "ageing")),
    ).collect()
    assert ageing["trait"].to_list() == ["life span determination trait"]
