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
    _effective_clin_sig,
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


def _row_clin_sig_label(row: dict) -> str:
    """What the report shows for a parquet row: the effective tier, rendered.

    `_build_variant` does exactly this pair — `_effective_clin_sig` to settle the tier across the
    format transition, then `_clin_sig_label` to render it — so the tests below exercise the same
    path the report takes rather than a display helper on its own.
    """
    return _clin_sig_label(
        _effective_clin_sig(
            row.get("clin_sig"), row.get("pathogenic"), row.get("benign"), row.get("clinvar")
        )
    )


def test_clin_sig_prefers_typed_column_over_booleans():
    """The ClinVar panels set pathogenic=True for both pathogenic and likely_pathogenic.
    Keying the report on the boolean collapses those two calls; clin_sig does not."""
    assert _row_clin_sig_label({
        "clin_sig": "likely_pathogenic",
        "clinvar": True,
        "pathogenic": True,
        "benign": False,
    }) == "Likely pathogenic"
    assert _row_clin_sig_label({"clin_sig": "pathogenic", "pathogenic": True}) == "Pathogenic"
    assert _row_clin_sig_label({"clin_sig": "uncertain_significance"}) == "Uncertain significance"


def test_clin_sig_falls_back_to_booleans_when_typed_column_empty():
    assert _row_clin_sig_label({"clin_sig": None, "pathogenic": True}) == "Pathogenic"
    assert _row_clin_sig_label({"clin_sig": "", "benign": True}) == "Benign"
    assert _row_clin_sig_label({}) == ""


def test_a_clinvar_record_that_is_neither_pathogenic_nor_benign_is_vus():
    """Not "" — a ClinVar record with both calls false is uncertain significance.

    This is the format's own `clin_sig_from_booleans` leaf rather than a rule of ours, and it is
    the one case where deriving beats reporting nothing: the variant *was* reviewed, and saying so
    is different from saying nothing is known.
    """
    assert _row_clin_sig_label({"clinvar": True}) == "Uncertain significance"
    assert _row_clin_sig_label({"clinvar": True, "pathogenic": False, "benign": False}) == (
        "Uncertain significance"
    )


def test_evidence_rank_orders_clinpgx_tiers_strongest_first():
    levels = ["2B", "1A", "3", "1B", "2A", "4"]
    assert sorted(levels, key=_evidence_rank, reverse=True) == ["1A", "1B", "2A", "2B", "3", "4"]
    # every non-pharmacogenomics module carries an empty level and must not outrank a real one
    assert _evidence_rank("") < _evidence_rank("4")
    assert _evidence_rank(None) < _evidence_rank("4")
    assert _evidence_rank("nonsense") < _evidence_rank("4")


# ============================================================ 0.5 contract: the annotations join

from pathlib import Path

from just_dna_pipelines.annotation.hf_modules import ModuleInfo
from just_dna_pipelines.annotation.report_logic import (
    _annotations_keying,
    _build_variant,
    _effective_clin_sig,
    _genotype_join_key,
    build_report_credits,
    load_annotated_weights,
    load_module_credits,
)

V1_PORT = Path(__file__).resolve().parents[2] / "data" / "interim" / "v1_port"


def _weights_frame() -> pl.DataFrame:
    """Two variants; rs1 is poly-effect (two real annotations), rs2 has one."""
    return pl.DataFrame(
        {
            "rsid": ["rs1", "rs2"],
            "variant_key": ["rs1", "rs2"],
            "genotype": [["A", "G"], ["C", "C"]],
            "phased": [False, False],
            "module": ["m", "m"],
            "weight": [1.0, -1.0],
            "state": ["risk", "protective"],
        }
    )


def _annotations_frame(era: str) -> pl.DataFrame:
    """The same two variants' annotations, spelled the way each artifact generation spells them."""
    base = {
        "rsid": ["rs1", "rs1", "rs2"],
        "gene": ["G1", "G1", "G2"],
        "category": ["lipids", "lipids", "insulin"],
        "phenotype": ["p1", "p2", "p3"],
    }
    if era == "rsid":
        return pl.DataFrame(base)
    base["variant_key"] = ["rs1", "rs1", "rs2"]
    if era == "variant_key":
        return pl.DataFrame(base)
    # 0.6 / RM80: the annotation is keyed by the genotype it applies to
    base["genotype"] = ["A/G", "G/G", "C/C"]
    return pl.DataFrame(base)


@pytest.mark.parametrize("era", ["rsid", "variant_key", "genotype"])
def test_annotations_join_never_inflates_the_variant_count(tmp_path, era):
    """Regression: joining annotations on rsid fanned a poly-effect variant out into one report row
    per annotation. Measured on real data at coronary 81 -> 231 (x2.85), lipidmetabolism x2.73,
    vo2max x2.15 — silently inflating total_variants and every count derived from it."""
    weights_path = tmp_path / "m_weights.parquet"
    _weights_frame().write_parquet(weights_path)
    ann_path = tmp_path / "annotations.parquet"
    _annotations_frame(era).write_parquet(ann_path)

    info = ModuleInfo(
        name="m", repo_id="local", path=str(tmp_path),
        lead_table="weights", lead_url=str(weights_path),
        weights_url=str(weights_path), annotations_url=str(ann_path),
    )

    out = load_annotated_weights(weights_path, "m", info)
    assert out.height == 2, f"{era} keying inflated {2} rows to {out.height}"
    # the annotation actually landed
    assert set(out["gene"].to_list()) == {"G1", "G2"}


def test_annotations_keying_is_detected_from_the_columns_present():
    """Three generations of artifact are in circulation at once, so the key is detected, not assumed."""
    schema = pl.Schema({"genotype": pl.List(pl.String), "variant_key": pl.String})
    assert _annotations_keying(
        ["variant_key", "genotype"], ["variant_key", "genotype", "gene"], schema
    ) == "genotype"
    assert _annotations_keying(
        ["variant_key", "genotype"], ["variant_key", "gene"], schema
    ) == "variant_key"
    assert _annotations_keying(["rsid"], ["rsid", "gene"], schema) == "rsid"
    # a 0.4-family lead table stores the genotype as a string, so it cannot take the genotype key
    str_schema = pl.Schema({"genotype": pl.String, "variant_key": pl.String})
    assert _annotations_keying(
        ["variant_key", "genotype"], ["variant_key", "genotype"], str_schema
    ) == "variant_key"


def test_genotype_join_key_matches_the_compilers_round_trip():
    """The rebuilt key must be the spelling `reverse_module` re-emits: phased keeps authored order,
    unphased is sorted. Ground truth is the compiler's own splitter, not a hardcoded string."""
    from just_dna_compiler.compiler import _split_genotype

    for authored, phased in [("A|G", True), ("G|A", True), ("A/G", False), ("C/C", False), ("A", False)]:
        alleles = _split_genotype(authored)
        assert _genotype_join_key(alleles, phased) == authored, authored

    # phase is not folded away: A|G and G|A stay distinct keys
    assert _genotype_join_key(["A", "G"], True) != _genotype_join_key(["G", "A"], True)
    # unphased is, because the grammar requires the sorted spelling
    assert _genotype_join_key(["G", "A"], False) == _genotype_join_key(["A", "G"], False) == "A/G"


# ============================================================ clin_sig as the primary clinical axis


def test_clin_sig_column_wins_over_the_lossy_booleans():
    """The booleans cannot express `likely_pathogenic`. Our ClinVar panels populate the column AND
    the booleans, so reading the boolean rendered 214,827 likely_pathogenic rows identically to
    402,174 pathogenic ones."""
    assert _effective_clin_sig("likely_pathogenic", True, False, True) == "likely_pathogenic"
    assert _effective_clin_sig("likely_benign", False, True, True) == "likely_benign"


def test_clin_sig_is_derived_when_only_the_legacy_booleans_are_present():
    assert _effective_clin_sig("", True, False, True) == "pathogenic"
    assert _effective_clin_sig(None, False, True, True) == "benign"
    assert _effective_clin_sig(None, False, False, True) == "uncertain_significance"
    # nothing established -> nothing said, rather than a fabricated default
    assert _effective_clin_sig(None, None, None, None) == ""
    assert _effective_clin_sig(None, False, False, False) == ""


# ==================================================== render-if-present: the axes our corpus lacks

import urllib.parse

import jinja2

from just_dna_pipelines.annotation.report_logic import (
    _AUTHORED_AXES,
    TABLE_PREVIEW_ROWS,
    build_module_report_data,
    build_pharmacogenomics_report_data,
    report_filename_stem,
    report_title_for_modules,
)

TEMPLATE_DIR = (
    Path(__file__).resolve().parents[1]
    / "src" / "just_dna_pipelines" / "annotation" / "templates"
)


def _render(**context) -> str:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True
    )
    ctx = {
        "report_title": "Synthetic Report",
        "report_description": "Synthetic report description.",
        # Read from the module rather than restated, so the preview cut-off has one definition
        # across the Python side, the pre-collapsed markup, and the inline JS constant.
        "preview_row_limit": TABLE_PREVIEW_ROWS,
        "user_name": "t", "sample_name": "s", "longevity": None,
        "other_modules": [], "pgx_modules": [], "credits": [],
        "module_provenance": [], "module_exclusions": [],
        "module_display_names": {}, "umami_script_tag": "",
    }
    ctx.update(context)
    return env.get_template("longevity_report.html.j2").render(**ctx)


def _module_data(variants: list[dict]) -> dict:
    return {
        "module_name": "synthetic", "display_name": "Synthetic",
        "variants": variants,
        "summary": {"total_variants": len(variants), "total_positive": 0,
                    "total_negative": 0, "total_weight": 0.0},
    }


def test_report_identity_uses_the_curated_single_module_name():
    assert report_title_for_modules(["longevitymap"]) == "Longevity Variants"
    assert report_filename_stem(["longevitymap"]) == "longevity_variants"
    assert report_title_for_modules(["coronary"]) == "Coronary Artery Disease"
    assert report_filename_stem(["coronary"]) == "coronary_artery"


def test_multi_module_report_identity_is_neutral():
    modules = ["longevitymap", "coronary"]
    assert report_title_for_modules(modules) == "Genomic Annotation Report"
    assert report_filename_stem(modules) == "report"


def test_variant_tables_show_ten_rows_and_offer_open_all_at_the_bottom():
    variants = []
    for index in range(TABLE_PREVIEW_ROWS + 2):
        row = {
            "rsid": f"rs{index}",
            "gene": "GENE",
            "genotype": ["A", "T"],
            "module": "synthetic",
            "weight": 0.5,
            "state": "risk",
        }
        variants.append(_build_variant(row, {}))

    html = _render(other_modules=[_module_data(variants)])

    row_count = TABLE_PREVIEW_ROWS + 2
    assert (
        f"Showing first <strong>{TABLE_PREVIEW_ROWS}</strong> of {row_count} rows" in html
    )
    assert html.count('class="variant-summary preview-overflow"') == 2
    assert ">Open all</button>" in html
    assert "toggleTableRows" in html
    table_start = html.index('<table class="ui variants">')
    table_end = html.index("</table>", table_start)
    toolbar = html.index('<div class="table-toolbar">', table_end)
    assert toolbar > table_end


def test_each_rsid_row_links_four_ai_assistants_with_variant_context():
    row = {
        "rsid": "rs429358",
        "gene": "APOE",
        "genotype": ["C", "T"],
        "module": "synthetic",
        "weight": -0.8,
        "state": "risk",
        "conclusion": "Associated with altered lipid transport.",
    }
    variant = _build_variant(row, {"rs429358": [{"pmid": "123456"}]})

    assert [link["provider"] for link in variant["ai_explain_links"]] == [
        "chatgpt",
        "claude",
        "perplexity",
        "grok",
    ]
    decoded_prompts = [
        urllib.parse.unquote(link["url"].split("q=", maxsplit=1)[1])
        for link in variant["ai_explain_links"]
    ]
    assert len(set(decoded_prompts)) == 1
    prompt = decoded_prompts[0]
    assert "RSID: rs429358" in prompt
    assert "Gene: APOE" in prompt
    assert "My genotype: C/T" in prompt
    assert "Supporting PubMed IDs: 123456" in prompt
    assert "do not diagnose or recommend treatment" in prompt

    html = _render(other_modules=[_module_data([variant])])
    assert "<th>AI explain</th>" in html
    assert html.count('class="ai-explain-link ') == 4
    for provider in ("ChatGPT", "Claude", "Perplexity", "Grok"):
        assert f"Ask {provider} to explain rs429358" in html
    assert 'viewBox="0 0 512 512"' in html
    # The glyphs are defined once and referenced per row. Inlining the paths in every row cost
    # ~5 kB a variant (1 MB on a 206-variant report) for four copies of the same four icons.
    assert html.count("M210.484 312.759L343.465 210.383") == 1
    assert html.count('<use href="#ai-icon-') == 4
    assert "M14.234 10.162 22.977 0" not in html
    assert 'colspan="9"' in html


def test_ai_explain_cell_has_no_external_links_without_an_rsid():
    variant = _build_variant(
        {"rsid": "", "gene": "GENE", "genotype": ["A", "T"], "weight": 0.2},
        {},
    )

    assert variant["ai_explain_links"] == []
    html = _render(other_modules=[_module_data([variant])])
    assert "<th>AI explain</th>" in html
    assert 'class="ai-explain-link ' not in html


def test_a_populated_0_5_axis_reaches_the_html():
    """The test that keeps the deferral honest.

    Every module in our corpus is a Gen-I port authored against 0.2 and mechanically uplifted, so
    these axes are empty everywhere — that is a property of the corpus, not of the format. A newly
    authored module will carry them, and this fails the day the view model or the macro starts
    dropping a populated column, which is the defect this whole pass exists to undo.
    """
    populated = {
        "effect_size": "1.42", "effect_measure": "OR", "effect_allele": "T",
        "stat_significance": "genome_wide", "negatives": "not in East Asian cohorts",
        "trait_efo_id": "EFO:0001645", "flags": "low_coverage",
        "priority": "high", "population": "European", "p_value": "3e-9",
    }
    row = {"rsid": "rs1", "gene": "G", "genotype": ["A", "T"], "module": "m",
           "weight": 0.5, "state": "risk", **populated}
    variant = _build_variant(row, {})

    # the view model carries every one
    for axis, value in populated.items():
        assert variant[axis] == value, axis

    html = _render(other_modules=[_module_data([variant])])
    for axis, value in populated.items():
        assert value in html, f"{axis}={value!r} never reached the rendered report"


def test_an_expanded_locus_is_labelled_in_the_report():
    """`locus_count > 1` is stated to the reader rather than silently rendered as a finding.

    One authored row for an rsID that resolves onto N positions becomes N rows, at most one of which
    is the variant the module is about. Restoration withholds these outright — an unobserved hom-ref
    row at N loci fabricates N results — but a *called* row was really sequenced and really carries
    that genotype, so it is labelled instead of discarded.
    """
    row = {"rsid": "rs1170991098", "gene": "SHOX", "genotype": ["A", "C"], "module": "m",
           "weight": 0.5, "state": "risk", "locus_count": 2, "locus_index": 1}
    variant = _build_variant(row, {})
    assert variant["locus_count"] == 2
    html = _render(other_modules=[_module_data([variant])])
    assert "Position ambiguous" in html
    assert "resolves to 2 positions" in html


@pytest.mark.parametrize("locus_count", [None, 1], ids=["pre_0_6_absent", "not_expanded"])
def test_an_unexpanded_locus_says_nothing(locus_count):
    """`None` is every module we have published; `1` is the ordinary 0.6 row. Neither is a caveat.

    `None` must not be coalesced to `1` and `1` must not read as an ambiguity — a row rendered with
    this caveat when the position is not ambiguous undermines the one case where it is true.
    """
    row = {"rsid": "rs1", "gene": "G", "genotype": ["A", "T"], "module": "m",
           "weight": 0.5, "state": "risk", "locus_count": locus_count}
    variant = _build_variant(row, {})
    html = _render(other_modules=[_module_data([variant])])
    assert "Position ambiguous" not in html


def test_a_declared_weighting_reaches_the_provenance_table():
    """`manifest.weighting` (format 0.6, RM92) is shown verbatim beside the version and digest.

    The report prints a per-module net weight, and `weight` is a bare float with no unit column — so
    before 0.6 the artifact could not say what scale that number is on and a reader had no way to
    interpret it. Free text, rendered as written, never parsed.
    """
    row = {
        "name": "coronary", "display_name": "Coronary", "version": "2.1.0",
        "digest": "sha256:abcdef0123456789", "digest_short": "abcdef012345",
        "lead_table": "weights", "source_url": "hf://x",
        "weighting": "scale: log odds ratio · note: not comparable with other modules",
    }
    html = _render(module_provenance=[row])
    assert "What its weights mean" in html
    assert "scale: log odds ratio" in html
    assert "not comparable with other modules" in html


def test_an_undeclared_weighting_renders_not_stated_rather_than_blank():
    """Absent means the module has not said, which is **not** "these weights are comparable".

    A blank cell reads as "nothing to report here"; every other tri-state column in this table says
    *Not stated* for the same reason, and this one carries the same weight of meaning.
    """
    row = {
        "name": "longevitymap", "display_name": "Longevity Map", "version": "",
        "digest": "", "digest_short": "", "lead_table": "weights", "source_url": "",
        "weighting": "",
    }
    html = _render(module_provenance=[row])
    assert "What its weights mean" in html
    assert "Not stated" in html


def test_an_empty_axis_emits_no_row_rather_than_an_empty_one():
    """The converse. Absent means render nothing, never a fabricated default or a blank row."""
    row = {"rsid": "rs1", "gene": "G", "genotype": ["A", "T"], "module": "m",
           "weight": 0.5, "state": "risk"}
    variant = _build_variant(row, {})
    html = _render(other_modules=[_module_data([variant])])
    for label in ("Effect size", "Effect measure", "Trait (EFO)", "Does not apply to"):
        assert label not in html, f"{label} rendered a row for an absent value"


def test_the_template_renders_direction_not_the_raw_state():
    """Format 1.0 removes `state`; the report must key on the derived direction instead."""
    row = {"rsid": "rs1", "gene": "G", "genotype": ["A", "T"], "module": "m",
           "weight": None, "state": "protective"}
    variant = _build_variant(row, {})
    assert variant["direction"] == "protective"
    html = _render(other_modules=[_module_data([variant])])
    assert "<th>Direction</th>" in html
    assert "<th>State</th>" not in html


def test_clin_sig_tier_is_what_the_report_shows():
    row = {"rsid": "rs1", "genotype": ["A", "T"], "module": "m", "weight": None,
           "clin_sig": "likely_pathogenic", "pathogenic": True, "clinvar": True}
    variant = _build_variant(row, {})
    html = _render(other_modules=[_module_data([variant])])
    assert "Likely pathogenic" in html
    # the old rendering collapsed the tier to a bare "(Pathogenic)"
    assert "Yes (Pathogenic)" not in html


# ============================================== pharmacogenomics: a 0.4-family lead table's report

pytestmark_v1 = pytest.mark.skipif(
    not (V1_PORT / "pharmgkb" / "pharm_variants.parquet").exists(),
    reason="v1_port modules not built (uv run pipelines v1-port pharmgkb)",
)


@pytestmark_v1
def test_pharmacogenomics_report_groups_by_drug_and_ranks_by_evidence(tmp_path):
    """A pharmacogenomics module states no weights, so |weight| ordering leaves it in scan order.
    The unit a reader acts on is the drug, and the ranking axis is the ClinPGx evidence level."""
    src = pl.read_parquet(V1_PORT / "pharmgkb" / "pharm_variants.parquet")
    # stand in for the engine's output: the matched subset, named the way it names outputs
    matched = src.head(200)
    weights_path = tmp_path / "pharmgkb_weights.parquet"
    matched.write_parquet(weights_path)

    info = ModuleInfo(
        name="pharmgkb", repo_id="local", path=str(V1_PORT / "pharmgkb"),
        lead_table="pharm_variants", lead_url=str(weights_path),
        sources_url=str(V1_PORT / "pharmgkb" / "sources.parquet"),
    )
    data = build_pharmacogenomics_report_data(weights_path, "pharmgkb", info)

    assert data["drugs"], "no drug groups built"
    # every matched variant lands in exactly one group
    assert sum(d["total_count"] for d in data["drugs"]) == data["summary"]["total_variants"]
    assert data["summary"]["total_variants"] == matched.height

    # groups are ordered by their strongest evidence, strongest first
    ranks = [_evidence_rank(d["best_evidence"]) for d in data["drugs"]]
    assert ranks == sorted(ranks, reverse=True)
    # and within a group too
    for d in data["drugs"]:
        inner = [_evidence_rank(v["evidence_level"]) for v in d["variants"]]
        assert inner == sorted(inner, reverse=True), d["drug"]

    # the strongest tier present in the source is the one that leads the report
    best_in_source = max(_evidence_rank(x) for x in matched["evidence_level"].to_list())
    assert _evidence_rank(data["drugs"][0]["best_evidence"]) == best_in_source


@pytestmark_v1
def test_pharmacogenomics_variants_survive_the_0_4_genotype_string(tmp_path):
    """pharm_variants keeps the authored genotype string; treating it as characters produced
    'G///G' and read zygosity off the separator."""
    src = pl.read_parquet(V1_PORT / "pharmgkb" / "pharm_variants.parquet").head(50)
    weights_path = tmp_path / "pharmgkb_weights.parquet"
    src.write_parquet(weights_path)
    info = ModuleInfo(name="pharmgkb", repo_id="local", path=str(tmp_path),
                      lead_table="pharm_variants", lead_url=str(weights_path))
    data = build_pharmacogenomics_report_data(weights_path, "pharmgkb", info)

    rendered = [v for d in data["drugs"] for v in d["variants"]]
    authored = src["genotype"].to_list()
    for v in rendered:
        assert "//" not in v["genotype_str"]
        assert v["zygosity"] in ("hom", "het", "")
    # zygosity agrees with the authored string it came from
    by_pair = {(v["rsid"], v["genotype_str"]) for v in rendered}
    for rsid, gt in zip(src["rsid"].to_list(), authored):
        if gt:
            assert (rsid, gt) in by_pair or "|" in gt


@pytestmark_v1
def test_credits_list_only_the_annotation_layer(tmp_path):
    """SCHEMAS.md SourceRow: only the `annotation` layer carries the derivative-work obligation. A
    reference consulted to place a coordinate (Ensembl, layer `resolution`) is recorded for
    provenance without tainting the module's terms, so crediting it would misstate what is owed."""
    info = ModuleInfo(
        name="pharmgkb", repo_id="local", path=str(V1_PORT / "pharmgkb"),
        lead_table="pharm_variants",
        lead_url=str(V1_PORT / "pharmgkb" / "pharm_variants.parquet"),
        sources_url=str(V1_PORT / "pharmgkb" / "sources.parquet"),
    )
    credits = load_module_credits("pharmgkb", info)

    raw = pl.read_parquet(V1_PORT / "pharmgkb" / "sources.parquet")
    expected = set(raw.filter(pl.col("layer") == "annotation")["source"].to_list())
    assert {c["source"] for c in credits} == expected
    # the resolution-layer source is present in the artifact but deliberately not credited
    assert "ensembl" in set(raw["source"].to_list())
    assert "ensembl" not in {c["source"] for c in credits}

    clinpgx = next(c for c in credits if c["source"] == "clinpgx")
    assert clinpgx["license"] == "CC-BY-SA-4.0"
    assert clinpgx["share_alike"] is True
    assert clinpgx["commercial_use"] is False
    assert clinpgx["attribution"]


@pytestmark_v1
def test_credits_are_deduplicated_across_modules_but_keep_who_used_them(tmp_path):
    infos = {
        name: ModuleInfo(
            name=name, repo_id="local", path=str(V1_PORT / "pharmgkb"),
            lead_table="pharm_variants",
            lead_url=str(V1_PORT / "pharmgkb" / "pharm_variants.parquet"),
            sources_url=str(V1_PORT / "pharmgkb" / "sources.parquet"),
        )
        for name in ("a", "b")
    }
    credits = build_report_credits(["a", "b"], infos)
    # two modules on the same upstream release owe one attribution, not two
    assert len(credits) == 1
    assert credits[0]["modules"] == ["a", "b"]


def test_credits_absent_when_the_module_has_no_sources_table(tmp_path):
    """A 0.3 module published before sources.parquet existed must not break the report."""
    info = ModuleInfo(name="old", repo_id="local", path=str(tmp_path),
                      lead_table="weights", lead_url=str(tmp_path / "w.parquet"))
    assert load_module_credits("old", info) == []
    assert build_report_credits(["old"], {"old": info}) == []


def test_weightless_lead_family_does_not_raise_on_the_weight_sum(tmp_path):
    """`annotated.select("weight").sum()` raised ColumnNotFoundError for any lead family with no
    weight column — latent while only longevitymap took that path, live once routing changed."""
    from just_dna_pipelines.annotation.report_logic import build_longevity_report_data

    pl.DataFrame({
        "rsid": ["rs1"], "genotype": ["C/C"], "module": ["m"],
        "gene": ["G"], "category": ["lipids"], "conclusion": ["c"],
    }).write_parquet(tmp_path / "m_weights.parquet")
    info = ModuleInfo(name="m", repo_id="local", path=str(tmp_path),
                      lead_table="pharm_variants", lead_url=str(tmp_path / "m_weights.parquet"))

    data = build_longevity_report_data(tmp_path / "m_weights.parquet", "m", info)
    assert data["summary"]["total_variants"] == 1
    assert data["summary"]["total_weight"] == 0.0


# =============================================== end to end, against a real sample when present

REAL_SAMPLE = Path(
    "/data/just-dna-lite/output/users/anonymous/M8UBMVNLH.hard-filtered/user_vcf_normalized.parquet"
)


@pytest.mark.skipif(
    not REAL_SAMPLE.exists() or not (V1_PORT / "pharmgkb" / "pharm_variants.parquet").exists(),
    reason="real sample or v1_port pharmgkb not present on this machine",
)
def test_pharmgkb_on_a_real_genome_produces_a_drug_keyed_section(tmp_path):
    """The measured end-to-end case: pharmgkb matches 63 rows on this sample, and every one must
    survive into a drug group. Pinned to the engine's own count rather than a literal, so the test
    tracks the module rather than a snapshot of it."""
    from just_dna_pipelines.annotation.hf_logic import annotate_vcf_with_module_weights

    src = V1_PORT / "pharmgkb"
    info = ModuleInfo(
        name="pharmgkb", repo_id="local", path=str(src), lead_table="pharm_variants",
        lead_url=str(src / "pharm_variants.parquet"),
        sources_url=str(src / "sources.parquet"),
    )
    out = tmp_path / "pharmgkb_weights.parquet"
    _, matched, _ = annotate_vcf_with_module_weights(
        pl.scan_parquet(REAL_SAMPLE), "pharmgkb", out, join_on="rsid", module_info=info
    )
    assert matched > 0, "engine matched nothing — the 0.4 genotype join regressed"

    data = build_pharmacogenomics_report_data(out, "pharmgkb", info)
    # nothing is lost between the engine and the report
    assert data["summary"]["total_variants"] == matched
    assert sum(d["total_count"] for d in data["drugs"]) == matched
    # the strongest evidence leads
    assert data["drugs"][0]["best_evidence"] == "1A"
    ranks = [_evidence_rank(d["best_evidence"]) for d in data["drugs"]]
    assert ranks == sorted(ranks, reverse=True)
    # a real PGx result names genes, not just rsids
    assert any(d["genes"] for d in data["drugs"])


# ============================================================================
# Which module bytes produced the report (AnnotationManifest provenance)
# ============================================================================

from just_dna_pipelines.annotation.hf_modules import (
    AnnotationManifest,
    ModuleOutputMapping,
)
from just_dna_pipelines.annotation.report_logic import (
    _module_outputs_from_manifest,
    _read_annotation_manifest,
    build_module_exclusions,
    build_module_provenance,
    generate_longevity_report,
)


def _write_run_manifest(modules_dir: Path, *modules: ModuleOutputMapping) -> None:
    manifest = AnnotationManifest(
        user_name="u", sample_name="s", source_vcf="/x.vcf",
        output_dir=str(modules_dir), modules=list(modules),
    )
    (modules_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2))


def test_the_report_reads_back_the_module_version_that_produced_it(tmp_path):
    """A rendered report must be tie-able to the module bytes behind it.

    The manifest is the only carrier: the parquet next to it says nothing about which version of
    which module wrote it, so a republished module silently changes what a saved report means.
    """
    _write_run_manifest(
        tmp_path,
        ModuleOutputMapping(
            module="coronary", lead_table="weights", version="2.1.0",
            digest="sha256:0123456789abcdef0123456789abcdef",
            source_url="/registered/coronary",
        ),
    )
    outputs = _module_outputs_from_manifest(tmp_path)
    assert outputs["coronary"].version == "2.1.0"

    rows = build_module_provenance(["coronary"], outputs, {})
    assert rows[0]["version"] == "2.1.0"
    assert rows[0]["digest_short"] == "0123456789ab"   # readable prefix of the Merkle root
    assert rows[0]["digest"].startswith("sha256:")     # the full value stays available

    html = _render(module_provenance=rows)
    assert "Modules in this report" in html
    assert "2.1.0" in html
    assert "0123456789ab" in html


def test_an_unstated_version_renders_as_not_stated_rather_than_as_unversioned(tmp_path):
    """`None` means the acquisition path never said, which is not the same as 'no version'.

    An HF-discovered module has no manifest fetched at all, so both fields are genuinely unknown;
    rendering that as a blank or as "v0" would assert something the run cannot support.
    """
    _write_run_manifest(
        tmp_path, ModuleOutputMapping(module="longevitymap", lead_table="weights")
    )
    rows = build_module_provenance(
        ["longevitymap"], _module_outputs_from_manifest(tmp_path), {}
    )
    assert (rows[0]["version"], rows[0]["digest"], rows[0]["digest_short"]) == ("", "", "")

    html = _render(module_provenance=rows)
    assert "Not stated" in html


def test_a_run_with_no_manifest_still_reports_its_modules(tmp_path):
    """The report is also generated from a directory of parquets alone — that must not crash,
    and the lead table still falls back to the discovered ModuleInfo (the pre-existing contract)."""
    assert _module_outputs_from_manifest(tmp_path) == {}

    info = ModuleInfo(
        name="pharmgkb", repo_id="local", path=str(tmp_path),
        lead_table="pharm_variants", lead_url=str(tmp_path / "pharm_variants.parquet"),
        source_url="/registered/pharmgkb",
    )
    rows = build_module_provenance(["pharmgkb"], {}, {"pharmgkb": info})
    assert rows[0]["lead_table"] == "pharm_variants"
    assert rows[0]["source_url"] == "/registered/pharmgkb"
    assert rows[0]["version"] == ""


def test_a_stale_parquet_cannot_hide_this_runs_skipped_outcome(tmp_path, monkeypatch):
    """A module skipped *this* run must not be re-rendered from a parquet an earlier run left.

    The output directory is reused across runs, so `{module}_weights.parquet` outliving the run that
    wrote it is ordinary. Deciding what to render by globbing the directory therefore reports last
    week's rows under this week's heading, and — worse here — hides the skip that is the only honest
    thing this run has to say about the module. The manifest is the authority for one run; the
    directory is only its history.
    """
    reason = (
        "pgx: the module exposes only rsid + genotype join keys, but this VCF carries no rsIDs"
    )
    manifest = AnnotationManifest(
        user_name="u",
        sample_name="s",
        source_vcf="/sample.vcf",
        output_dir=str(tmp_path),
        modules=[],
        skipped_modules={"pgx": reason},
    )
    (tmp_path / "manifest.json").write_text(manifest.model_dump_json(indent=2))
    # The leftover. Its deliberately incomplete schema would raise if the report ever loaded it, so
    # this asserts the guard rather than merely that the rows went unrendered.
    pl.DataFrame({"stale": [True]}).write_parquet(tmp_path / "pgx_weights.parquet")

    monkeypatch.setattr(
        "just_dna_pipelines.annotation.report_logic.discover_hf_modules", dict
    )
    report = generate_longevity_report(
        tmp_path,
        tmp_path / "report.html",
        module_names=["pgx"],
        user_name="u",
        sample_name="s",
    )
    html = report.read_text(encoding="utf-8")

    assert "Modules not read in this run" in html
    assert reason in html
    assert "No annotated variants were found for this module" not in html


