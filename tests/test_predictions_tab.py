"""The Predictions tab: its form helpers, its place among the tabs, and that its components build.

The run itself (job, config, scores, report) is tested in just-dna-pipelines/tests/test_predictions.py.
"""

from __future__ import annotations

import pytest
from just_dna_pipelines.predictions.models import PREDICTION_MODELS
from just_dna_pipelines.predictions.run_config import (
    DEFAULT_MAX_VARIANTS,
    MAX_REGION_BP,
    VARIANT_SET_ANNOTATED,
    VARIANT_SET_REGION,
)
from webui.pages.annotate import _right_panel_tab_menu
from webui.pages.predictions import predictions_tab_content
from webui.predictions_state import MAX_VARIANTS_LIMIT, clamp_max_variants, model_option_rows, region_problem
from webui.state import DEFAULT_TAB_ORDER


def test_predictions_is_a_tab_in_the_menu() -> None:
    assert "predictions" in DEFAULT_TAB_ORDER
    assert len(DEFAULT_TAB_ORDER) == len(set(DEFAULT_TAB_ORDER))
    menu = str(_right_panel_tab_menu().render())
    assert "Predictions" in menu


def test_the_tab_builds_and_offers_every_registered_model() -> None:
    rendered = str(predictions_tab_content().render())
    assert "start_prediction_run" in rendered
    rows = model_option_rows()
    assert [r["id"] for r in rows] == list(PREDICTION_MODELS)
    for row, model in zip(rows, PREDICTION_MODELS.values(), strict=True):
        assert row["licence"] == model.licence and row["card_url"] == model.model_card_url


@pytest.mark.parametrize("region", ["7:117,559,000-117,560,000", "chrX:1-10"])
def test_a_readable_region_has_no_problem(region: str) -> None:
    assert region_problem(VARIANT_SET_REGION, region) == ""


@pytest.mark.parametrize("region", ["", "   ", "7", "7:9-1", f"1:1-{MAX_REGION_BP + 1}", "ü:1-2x"])
def test_an_unreadable_region_is_explained(region: str) -> None:
    assert region_problem(VARIANT_SET_REGION, region)


def test_the_region_box_is_ignored_for_the_annotated_set() -> None:
    assert region_problem(VARIANT_SET_ANNOTATED, "not a region") == ""


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("7", 7),
        (7.0, 7),
        ("12.9", 12),
        ("0", 1),
        (str(MAX_VARIANTS_LIMIT + 50), MAX_VARIANTS_LIMIT),
        ("", DEFAULT_MAX_VARIANTS),
        ("-3", DEFAULT_MAX_VARIANTS),
        ("abc", DEFAULT_MAX_VARIANTS),
        ("٣", DEFAULT_MAX_VARIANTS),  # a non-ASCII digit is not a plain number here
    ],
)
def test_the_cap_is_clamped_to_a_sane_integer(typed: str | float, expected: int) -> None:
    assert clamp_max_variants(typed) == expected
