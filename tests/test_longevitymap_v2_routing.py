"""Longevity Map 2.0.0 keeps the name `longevitymap` but not Generation I's pathway categories.

The report's longevity section files rows under `LONGEVITY_CATEGORIES` only, so the re-curated module,
whose `category` is the system a locus acts through, must take the generic module section instead.
The categories are read from the committed spec (`data/modules/longevitymap_v2/variants.csv`), not
restated here.
"""

from pathlib import Path

import polars as pl
import pytest

from just_dna_pipelines.annotation.report_logic import LONGEVITY_CATEGORIES, are_longevity_pathways

SPEC = Path(__file__).resolve().parents[1] / "data" / "modules" / "longevitymap_v2"


def test_the_recurated_modules_categories_are_not_pathways() -> None:
    variants = pl.read_csv(SPEC / "variants.csv", infer_schema_length=0)
    categories = set(variants["category"].drop_nulls().to_list())
    assert categories, "the v2 spec names a category on its rows"
    # The premise the routing rests on: none of v2's categories is a Generation I pathway.
    assert categories.isdisjoint(LONGEVITY_CATEGORIES)
    assert are_longevity_pathways(categories) is False


def test_generation_one_categories_are_pathways() -> None:
    assert are_longevity_pathways(set(LONGEVITY_CATEGORIES)) is True
    assert are_longevity_pathways({"other"}) is True


def test_no_category_at_all_keeps_the_pathway_section() -> None:
    assert are_longevity_pathways(set()) is True


@pytest.mark.parametrize("extra", ["heart_vessels", "general_ageing"])
def test_one_category_outside_the_pathways_is_enough_to_leave(extra: str) -> None:
    assert are_longevity_pathways({sorted(LONGEVITY_CATEGORIES)[0], extra}) is False
