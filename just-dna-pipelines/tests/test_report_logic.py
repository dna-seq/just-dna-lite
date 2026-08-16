"""Tests for report generation logic (just_dna_pipelines.annotation.report_logic)."""

import polars as pl

from just_dna_pipelines.annotation.report_logic import _annotated_rows


def test_annotated_rows_keeps_weightless_module_matches():
    """Regression: weight-less modules (superhuman, ClinVar gene panels) carry weight=None on
    every variant. The report must not filter on weight or it shows 0 annotated variants even when
    the annotation matched (the v1->v2 superhuman '0 annotated' report bug, 2026-07)."""
    df = pl.DataFrame({
        "rsid": ["rs1", "rs2", "rs3"],
        "genotype": [["G", "G"], ["C", "T"], ["A", "A"]],
        # rs1/rs2 matched the module (module/conclusion/state populated); rs3 is an at-position
        # non-match from the left join (all module columns null).
        "module": ["superhuman", "superhuman", None],
        "conclusion": ["Low odor production", "Malaria resistance", None],
        "state": ["significant", "significant", None],
        "weight": [None, None, None],  # weight-less module
    })
    kept = _annotated_rows(df)
    assert kept.height == 2, kept
    assert set(kept["rsid"].to_list()) == {"rs1", "rs2"}
    # the old, buggy criterion would have dropped everything
    assert df.filter(pl.col("weight").is_not_null()).height == 0


def test_annotated_rows_unchanged_for_weighted_modules():
    """A weighted module (e.g. longevitymap) keeps exactly its matched rows — no regression."""
    df = pl.DataFrame({
        "rsid": ["rs1", "rs2"],
        "module": ["longevitymap", None],   # rs2 = at-position non-match
        "conclusion": ["assoc", None],
        "state": ["risk", None],
        "weight": [1.5, None],
    })
    kept = _annotated_rows(df)
    assert kept["rsid"].to_list() == ["rs1"]
    # for a weighted module this matches the legacy weight-based criterion
    assert kept.height == df.filter(pl.col("weight").is_not_null()).height


import pytest

from just_dna_pipelines.annotation.report_logic import (
    _variant_color,
    _variant_sign,
    _weight_color,
)


@pytest.mark.parametrize(
    "weight, state, expected_sign",
    [
        (1.5, None, 1),           # weighted module: sign from weight
        (-2.0, None, -1),
        (0.0, "protective", 1),   # weight-less protective (superhuman) -> beneficial via state
        (None, "protective", 1),
        (None, "risk", -1),       # weight-less risk (ClinVar gene panels)
        (None, "significant", 0), # 'significant' is not a direction -> neutral
        (None, None, 0),
        (2.0, "risk", 1),         # a real weight wins over state
    ],
)
def test_variant_sign_weight_then_state(weight, state, expected_sign):
    assert _variant_sign(weight, state) == expected_sign


def test_variant_color_protective_is_green_at_zero_weight():
    green = _variant_color(None, "protective")
    red = _variant_color(None, "risk")
    assert green.startswith("rgba(0,") and "160" in green   # protective -> green
    assert red.startswith("rgba(180,")                      # risk -> red
    assert _variant_color(None, "significant") == "transparent"  # no direction
    # a weighted variant still colors by its weight
    assert _variant_color(0.5, None) == _weight_color(0.5)


from just_dna_pipelines.annotation.report_logic import _effective_direction


@pytest.mark.parametrize(
    "weight, state, direction, expected_sign",
    [
        # 0.5 era: direction column empty, benefit derived from state (unchanged behavior)
        (None, "protective", "", 1),
        (None, "protective", None, 1),
        (None, "risk", "", -1),
        # 1.0 era: state dropped, direction is authoritative
        (None, None, "protective", 1),
        (None, None, "risk", -1),
        (None, None, "neutral", 0),
        (None, None, "unknown", 0),
        # populated direction wins over a (transitional) state
        (None, "risk", "protective", 1),
        # a real weight still wins over everything (weighted modules)
        (1.5, None, None, 1),
        (-2.0, "protective", "protective", -1),
    ],
)
def test_variant_sign_prefers_direction_then_state(weight, state, direction, expected_sign):
    assert _variant_sign(weight, state, direction) == expected_sign


def test_effective_direction_bridges_both_schemas():
    # authored direction present -> used verbatim (1.0)
    assert _effective_direction("protective", None, None) == "protective"
    # direction empty -> derived from legacy state (0.5)
    assert _effective_direction("", "protective", None) == "protective"
    assert _effective_direction(None, "risk", None) == "risk"
    # 'significant' + weight sign refinement, via the format's own leaf
    assert _effective_direction("", "significant", 0.7) == "protective"
    assert _effective_direction("", "significant", -0.7) == "risk"


def test_variant_color_direction_only_is_green():
    # a 1.0-style row (state gone, direction set, no weight) still colors green/red
    assert _variant_color(None, None, "protective").startswith("rgba(0,")
    assert _variant_color(None, None, "risk").startswith("rgba(180,")


# --------------------------------------------------------- 0.4 table families in the report

from just_dna_pipelines.annotation.report_logic import (
    _clin_sig_label,
    _evidence_rank,
    _genotype_alleles,
    _genotype_str,
    _zygosity,
)


@pytest.mark.parametrize(
    "genotype, expected_str, expected_zygosity",
    [
        # weights.parquet spells a genotype as a list of alleles
        (["G", "G"], "G/G", "hom"),
        (["C", "T"], "C/T", "het"),
        # the 0.4 families (pharm_variants and friends) carry the authored string. Splitting it
        # character-wise produced "G///G" and read zygosity off the separator.
        ("G/G", "G/G", "hom"),
        ("C/T", "C/T", "het"),
        # single-allele calls on MT/chrY have no zygosity to report
        (["A"], "A", ""),
        ("A", "A", ""),
        (None, "", ""),
    ],
)
def test_genotype_helpers_accept_both_representations(genotype, expected_str, expected_zygosity):
    assert _genotype_str(genotype) == expected_str
    assert _zygosity(genotype) == expected_zygosity


def test_genotype_alleles_drops_empty_fragments():
    """A trailing or doubled separator must not become a phantom allele."""
    assert _genotype_alleles("G//G") == ["G", "G"]
    assert _genotype_alleles("G/") == ["G"]


def test_clin_sig_label_prefers_typed_column_over_booleans():
    """The ClinVar panels set pathogenic=True for both pathogenic and likely_pathogenic.
    Keying the report on the boolean collapses those two calls; clin_sig does not."""
    assert _clin_sig_label({
        "clin_sig": "likely_pathogenic",
        "clinvar": True,
        "pathogenic": True,
        "benign": False,
    }) == "likely pathogenic"
    assert _clin_sig_label({"clin_sig": "pathogenic", "pathogenic": True}) == "pathogenic"
    assert _clin_sig_label({"clin_sig": "uncertain_significance"}) == "uncertain significance"


def test_clin_sig_label_falls_back_to_booleans_when_typed_column_empty():
    assert _clin_sig_label({"clin_sig": None, "pathogenic": True}) == "pathogenic"
    assert _clin_sig_label({"clin_sig": "", "benign": True}) == "benign"
    assert _clin_sig_label({"clinvar": True}) == ""
    assert _clin_sig_label({}) == ""


def test_evidence_rank_orders_clinpgx_tiers_strongest_first():
    levels = ["2B", "1A", "3", "1B", "2A", "4"]
    assert sorted(levels, key=_evidence_rank, reverse=True) == ["1A", "1B", "2A", "2B", "3", "4"]
    # every non-pharmacogenomics module carries an empty level and must not outrank a real one
    assert _evidence_rank("") < _evidence_rank("4")
    assert _evidence_rank(None) < _evidence_rank("4")
    assert _evidence_rank("nonsense") < _evidence_rank("4")
