"""By Trait search matches both names, and age finds the longevity scores."""

from __future__ import annotations

import polars as pl
import pytest
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


def test_curated_synonyms_find_their_concept_on_the_real_catalog() -> None:
    """Concept grouping plus `PRSCatalog.search_terms()`: a curated alias that is no catalog
    name of any score still finds every score of its concept, through the same contains
    filter the search box applies."""
    from just_prs import PRSCatalog
    from just_prs.trait_search import matching_pgs_ids, score_search_terms
    from prs_ui.mixin import TRAIT_GROUP_BY_CONCEPT

    catalog = PRSCatalog()
    scores = catalog.scores(genome_build="GRCh38").collect()
    terms = catalog.search_terms()
    summary, mapping = _trait_summary_frame(scores, TRAIT_GROUP_BY_CONCEPT, terms)
    assert set(summary["trait"]) == set(mapping)
    assert sum(summary["n_models"]) == scores.height

    catalog_only = score_search_terms(scores)
    concept_terms = catalog.curation_tables()["search_terms"]
    aliases = concept_terms.filter(pl.col("term_kind") == "alias").sort("cluster", "term")
    for row in aliases.iter_rows(named=True):
        if matching_pgs_ids(catalog_only, row["term"]):
            continue  # also a catalog name: proves nothing about the curated terms
        concept_ids = set(
            scores.filter(pl.col("cluster") == row["cluster"])["pgs_id"]
        )
        if not concept_ids:
            continue
        found = apply_filter_model(
            summary.lazy(), _trait_filter_searches_both(_contains("trait", row["term"]))
        ).collect()
        found_ids = {pgs_id for trait in found["trait"] for pgs_id in mapping[trait]}
        assert concept_ids <= found_ids
        label = scores.filter(pl.col("cluster") == row["cluster"])["concept_label"][0]
        assert label in set(found["trait"])
        return
    pytest.skip("no curated alias that is absent from catalog names yet")


def test_frames_without_curation_columns_still_group() -> None:
    """Callers that never joined curation (old caches, fixtures) fall back to the mapped term."""
    from prs_ui.mixin import TRAIT_GROUP_BY_CONCEPT

    by_concept, _ = _trait_summary_frame(_catalog_rows(), TRAIT_GROUP_BY_CONCEPT)
    by_ontology, _ = _trait_summary_frame(_catalog_rows(), TRAIT_GROUP_BY_ONTOLOGY)
    assert by_concept["trait"].sort().to_list() == by_ontology["trait"].sort().to_list()
    assert by_concept["n_curated"].sum() == 0
