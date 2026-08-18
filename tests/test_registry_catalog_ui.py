"""Module catalog: uninstall must update the installed list immediately; Get busy is per-card."""

from __future__ import annotations

from reflex_base.utils.types import is_backend_base_variable

from webui.state import (
    RegistryState,
    _cards_with_installed,
    _local_key,
    _without_local_module,
)


def test_catalog_get_busy_is_a_card_field_not_a_global_frontend_var() -> None:
    """Would have made every Get look clicked: comparing a global ``busy_key``
    to ``card["local_key"]`` inside ``rx.foreach`` compiles as one shared Var.

    The grid reads ``card["busy"]``. The stamp source is backend-only.
    """
    assert is_backend_base_variable("_busy_key", RegistryState)
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
