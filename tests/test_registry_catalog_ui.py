"""Module catalog: uninstall must update the installed list immediately; Get busy is per-card.

Card counts: the registry projects ``manifest.stats`` unchanged, where ``variant_count`` counts
``variants.csv`` alone and the ClinVar counters count genotype rows. A card must never say "0
variants" for a module that has rows, nor show a pathogenic number larger than its variant count.
"""

from __future__ import annotations

from typing import Any

import pytest
from just_dna_format.manifest import Stats

from webui.pages.registry import _CARD_BLURB_STYLE
from webui.state import (
    _NO_VARIANT_LIST_TITLE,
    RegistryState,
    _card_blurb,
    _cards_with_installed,
    _catalog_card,
    _catalog_counts,
    _local_key,
    _without_local_module,
)

LONG = "GWAS-significant common variants in genes with established roles " * 8
REGISTRY_URL = "https://registry.example"


def _listing_item(name: str, **stats: int) -> dict[str, Any]:
    """A registry listing item as `GET /api/v1/modules` returns it: `stats` is a `manifest.Stats`."""
    assert set(stats) <= set(Stats.model_fields), f"not a manifest.Stats field: {set(stats) - set(Stats.model_fields)}"
    return {
        "namespace": "just-dna-seq",
        "name": name,
        "title": name,
        "description": f"The {name} module.",
        "short_description": "",
        "logo_url": f"/api/v1/modules/just-dna-seq/{name}/versions/1.0.0/logo",
        "downloads": 7,
        "stats": Stats(**stats).model_dump(),
    }


# One listing item per lead-table family, shaped like the production listing on 2026-10-26.
WEIGHTS = _listing_item("longevitymap", variant_count=528, weights_rows=1022, gene_count=272, study_count=671)
PHARM_VARIANTS = _listing_item("pharmgkb", variant_count=0, weights_rows=0, gene_count=35)
PHENOTYPE = _listing_item("fut2_secretor", variant_count=0, weights_rows=0, gene_count=1, study_count=12)
CLINVAR_PANEL = _listing_item(
    "pathogenic", variant_count=308990, weights_rows=618629, gene_count=4793,
    clinvar_count=617822, pathogenic_count=617822,
)
# A curated weights module where some variants are ClinVar-pathogenic (FMO3 in the smell module).
PARTLY_PATHOGENIC = _listing_item(
    "smell", variant_count=31, weights_rows=67, gene_count=6, clinvar_count=52, pathogenic_count=52,
)
ALL_FAMILIES = [WEIGHTS, PHARM_VARIANTS, PHENOTYPE, CLINVAR_PANEL, PARTLY_PATHOGENIC]


@pytest.mark.parametrize(
    ("item", "count_text", "gene_text", "clinvar_text"),
    [
        (WEIGHTS, "528 variants", "272 genes", ""),
        # No variants.csv, so variant_count is 0 although the module has rows: show its genes.
        (PHARM_VARIANTS, "35 genes", "", ""),
        (PHENOTYPE, "1 gene", "", ""),
        # 617,822 pathogenic genotype rows over 308,990 variants: the row count is not shown as a
        # number beside the variant count.
        (CLINVAR_PANEL, "308,990 variants", "4,793 genes", "ClinVar pathogenic"),
        (PARTLY_PATHOGENIC, "31 variants", "6 genes", "ClinVar pathogenic"),
    ],
    ids=["weights", "pharm_variants", "phenotype", "clinvar_panel", "partly_pathogenic"],
)
def test_catalog_card_counts_per_lead_family(
    item: dict[str, Any], count_text: str, gene_text: str, clinvar_text: str,
) -> None:
    card = _catalog_card(item, REGISTRY_URL)
    assert card["count_text"] == count_text
    assert card["gene_text"] == gene_text
    assert card["clinvar_text"] == clinvar_text
    stats = item["stats"]
    # The hover names what the gene count stands in for, and only where it stands in.
    assert card["count_title"] == ("" if stats["variant_count"] else _NO_VARIANT_LIST_TITLE)
    if clinvar_text:
        assert f"{stats['pathogenic_count']:,} flagged pathogenic or likely pathogenic" in card["clinvar_title"]
        assert "Genotype rows" in card["clinvar_title"]
    else:
        assert card["clinvar_title"] == ""


@pytest.mark.parametrize("item", ALL_FAMILIES, ids=lambda i: i["name"])
def test_no_card_says_zero_or_more_pathogenic_than_variants(item: dict[str, Any]) -> None:
    """The two defects seen on the public catalog: "0 variants" on modules with rows, and
    "617,822 pathogenic" beside "308,990 variants"."""
    card = _catalog_card(item, REGISTRY_URL)
    assert card["count_text"] and not card["count_text"].startswith("0 ")
    # The ClinVar label carries no number at all, so it cannot outnumber the variants.
    assert not any(ch.isdigit() for ch in card["clinvar_text"])
    # The variant count shown is the listing's distinct count, never a row count.
    if item["stats"]["variant_count"]:
        assert card["count_text"] == f"{item['stats']['variant_count']:,} variants"
        assert f"{item['stats']['weights_rows']:,}" not in card["count_text"]


@pytest.mark.parametrize(
    ("stats", "clinvar_text"),
    [
        ({"variant_count": 4, "clinvar_count": 6, "benign_count": 6}, "ClinVar benign"),
        (
            {"variant_count": 4, "clinvar_count": 8, "pathogenic_count": 2, "benign_count": 6},
            "ClinVar pathogenic and benign",
        ),
        # In ClinVar but flagged neither way (uncertain significance).
        ({"variant_count": 4, "clinvar_count": 3}, "In ClinVar"),
        ({"variant_count": 4}, ""),
    ],
)
def test_catalog_counts_clinvar_label(stats: dict[str, int], clinvar_text: str) -> None:
    counts = _catalog_counts(Stats(**stats).model_dump())
    assert counts["clinvar_text"] == clinvar_text
    assert bool(counts["clinvar_title"]) == bool(clinvar_text)


@pytest.mark.parametrize("stats", [{}, Stats().model_dump(), {"variant_count": None, "gene_count": None}])
def test_catalog_counts_hide_labels_when_the_manifest_says_nothing(stats: dict[str, Any]) -> None:
    """A manifest with no stats (or a pre-stats one) renders no labels rather than zeros."""
    assert set(_catalog_counts(stats).values()) == {""}


def test_catalog_counts_read_fields_the_format_publishes() -> None:
    """A rename in `manifest.Stats` would silently turn every count to 0 here."""
    assert {"variant_count", "gene_count", "clinvar_count", "pathogenic_count", "benign_count"} <= set(
        Stats.model_fields
    )


def test_catalog_card_keeps_the_listing_item_and_resolves_its_logo() -> None:
    card = _catalog_card(WEIGHTS, REGISTRY_URL)
    assert card["logo_full"] == REGISTRY_URL + WEIGHTS["logo_url"]
    assert card["blurb"] == WEIGHTS["description"]
    assert "count_text" not in WEIGHTS
    hosted = _catalog_card({**WEIGHTS, "logo_url": "https://cdn.example/logo.png"}, REGISTRY_URL)
    assert hosted["logo_full"] == "https://cdn.example/logo.png"


@pytest.mark.parametrize(
    ("record", "blurb", "title"),
    [
        # Published before format 0.7 had a short description: the registry sends it empty.
        ({"short_description": "", "description": LONG}, LONG.strip(), LONG.strip()),
        ({"short_description": None, "description": LONG}, LONG.strip(), LONG.strip()),
        ({"description": LONG}, LONG.strip(), LONG.strip()),
        ({"short_description": "   ", "description": "Full text."}, "Full text.", "Full text."),
        # A curated short description is shown, and the hover still carries the full description.
        ({"short_description": "Curated alleles", "description": "Elite variants"}, "Curated alleles", "Elite variants"),
        ({"short_description": "Curated alleles", "description": ""}, "Curated alleles", "Curated alleles"),
        ({}, "", ""),
    ],
)
def test_card_blurb_falls_back_to_the_description(record: dict, blurb: str, title: str) -> None:
    assert _card_blurb(record) == {"blurb": blurb, "blurb_title": title}


def test_card_blurb_is_clamped_with_an_ellipsis_at_a_fixed_height() -> None:
    """A long description used to be cut at the box edge with no ellipsis, mid-sentence.

    The height must stay fixed so a short blurb and a long one keep the grid aligned, and it must
    hold exactly the clamped lines, or the clamp's last line is itself cut in half.
    """
    lines = int(_CARD_BLURB_STYLE["WebkitLineClamp"])
    assert _CARD_BLURB_STYLE["display"] == "-webkit-box"
    assert _CARD_BLURB_STYLE["overflow"] == "hidden"
    assert float(_CARD_BLURB_STYLE["height"].removesuffix("em")) == pytest.approx(
        lines * float(_CARD_BLURB_STYLE["lineHeight"])
    )


def test_catalog_get_busy_is_a_card_field_not_a_global_frontend_var() -> None:
    """Would have made every Get look clicked: comparing a global ``busy_key``
    to ``card["local_key"]`` inside ``rx.foreach`` compiles as one shared Var.

    The grid reads ``card["busy"]``. The stamp source is backend-only.
    """
    assert "_busy_key" in RegistryState.get_fields()
    assert "_busy_key" not in RegistryState.base_vars
    assert "busy_key" not in RegistryState.base_vars


def test_without_local_module_drops_only_that_row() -> None:
    modules = [
        {"name": "just_dna_seq__irritability", "title": "Irritability"},
        {"name": "just_dna_seq__lactose", "title": "Lactose"},
    ]
    remaining = _without_local_module(modules, "just_dna_seq__irritability")
    assert [m["name"] for m in remaining] == ["just_dna_seq__lactose"]
    assert [m["name"] for m in modules] == [
        "just_dna_seq__irritability",
        "just_dna_seq__lactose",
    ]


def test_cards_with_installed_flips_only_the_uninstalled_card() -> None:
    """Would have left every Get button looking installed until a catalog search returned."""
    cards = [
        {"namespace": "just-dna-seq", "name": "irritability", "installed": True},
        {"namespace": "just-dna-seq", "name": "cognitive_intelligence", "installed": False},
        {"namespace": "just-dna-seq", "name": "lactose_tolerance", "installed": True},
    ]
    kept = ["just_dna_seq__lactose_tolerance"]
    updated = _cards_with_installed(cards, kept)
    by_name = {c["name"]: c for c in updated}
    assert by_name["irritability"]["installed"] is False
    assert by_name["lactose_tolerance"]["installed"] is True
    assert by_name["cognitive_intelligence"]["installed"] is False
    assert by_name["irritability"]["local_key"] == _local_key("just-dna-seq", "irritability")
    assert by_name["cognitive_intelligence"]["local_key"] == _local_key(
        "just-dna-seq", "cognitive_intelligence",
    )
    assert all(c["busy"] is False for c in updated)


def test_cards_with_installed_stamps_busy_only_on_the_clicked_card() -> None:
    """One Get click must not light every primary button in the catalog grid."""
    cards = [
        {"namespace": "just-dna-seq", "name": "irritability"},
        {"namespace": "just-dna-seq", "name": "lactose_tolerance"},
        {"namespace": "just-dna-seq", "name": "cognitive_intelligence"},
    ]
    busy = _local_key("just-dna-seq", "irritability")
    updated = _cards_with_installed(cards, [], busy)
    by_name = {c["name"]: c for c in updated}
    assert by_name["irritability"]["busy"] is True
    assert by_name["lactose_tolerance"]["busy"] is False
    assert by_name["cognitive_intelligence"]["busy"] is False
    cleared = _cards_with_installed(updated, [], "")
    assert all(c["busy"] is False for c in cleared)


def test_begin_action_stamps_busy_on_cards_the_grid_already_holds() -> None:
    """The browser never compares ``_busy_key``; it only sees restamped cards."""
    state = RegistryState()
    irritability = _local_key("just-dna-seq", "irritability")
    lactose = _local_key("just-dna-seq", "lactose_tolerance")
    state._local_names = []
    state.cards = [
        {"namespace": "just-dna-seq", "name": "irritability", "local_key": irritability},
        {"namespace": "just-dna-seq", "name": "lactose_tolerance", "local_key": lactose},
    ]
    state._begin_action("Downloading irritability…", busy_key=irritability)
    by_name = {c["name"]: c for c in state.cards}
    assert by_name["irritability"]["busy"] is True
    assert by_name["lactose_tolerance"]["busy"] is False
    state._end_action("Installed.")
    assert all(c["busy"] is False for c in state.cards)
    assert state._busy_key == ""


def test_publish_local_snapshot_updates_installed_list_without_catalog_search() -> None:
    """Uninstall used to wait on artifact hashing + registry lookup before the list moved."""
    state = RegistryState()
    irritability = _local_key("just-dna-seq", "irritability")
    lactose = _local_key("just-dna-seq", "lactose_tolerance")
    state.local_modules = [
        {"name": irritability, "title": "Irritability", "in_catalog": True},
        {"name": lactose, "title": "Lactose", "in_catalog": True},
    ]
    state.cards = [
        {"namespace": "just-dna-seq", "name": "irritability", "installed": True},
        {"namespace": "just-dna-seq", "name": "cognitive_intelligence", "installed": False},
        {"namespace": "just-dna-seq", "name": "lactose_tolerance", "installed": True},
    ]

    state._publish_local_snapshot(_without_local_module(list(state.local_modules), irritability))

    assert [m["name"] for m in state.local_modules] == [lactose]
    assert state._local_names == [lactose]
    by_name = {c["name"]: c for c in state.cards}
    assert by_name["irritability"]["installed"] is False
    assert by_name["lactose_tolerance"]["installed"] is True
    assert by_name["cognitive_intelligence"]["installed"] is False
