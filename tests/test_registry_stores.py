"""Registry stores: the Catalog can point at more than one registry server.

The properties worth pinning are the ones whose failure is silent: a token minted by one server
reaching another (it answers `403 insufficient_capability`, which reads as a permissions bug),
a working copy of modules.yaml deleting a shipped store, and the previous server's account
staying on screen after a switch.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from just_dna_pipelines.module_config import (
    ModulesConfig,
    RegistryStore,
    _merge_config,
    default_registry_store,
    get_registry_store,
    get_registry_stores,
)


# --------------------------------------------------------------------------- config

def test_shipped_stores_include_the_public_registry_and_the_polygon_test_ground() -> None:
    by_key = {store.key: store for store in get_registry_stores()}
    assert {"prod", "polygon"} <= set(by_key)
    assert by_key["prod"].base_url == "https://module-registry.just-dna.life"
    assert by_key["polygon"].base_url == "https://module-polygon.just-dna.life"
    # `mode` mirrors what each server answers on /api/v1/version.
    assert by_key["prod"].is_test is False
    assert by_key["polygon"].is_test is True


def test_no_two_stores_share_a_token_variable() -> None:
    """A shared variable is how a test token ends up authenticating against the public server.

    That failure does not surface as anything auth-shaped: the public registry answers
    `403 insufficient_capability` on check/publish, which reads as a namespace-permissions bug.
    """
    envs = [store.token_env for store in get_registry_stores() if store.token_env]
    assert len(envs) == len(set(envs))
    assert get_registry_store("polygon").token_env != get_registry_store("prod").token_env


def test_url_is_normalized_for_the_client() -> None:
    store = RegistryStore(key="x", label="X", url="https://example.org/")
    assert store.base_url == "https://example.org"


def test_a_working_copy_written_before_stores_existed_keeps_the_shipped_ones() -> None:
    """Would have hidden every store: `registries` taken from the working copy wholesale.

    A working copy is written the first time a custom module is registered, and one written
    before this key shipped names no store at all.
    """
    default = {"registries": [{"key": "prod", "label": "Prod", "url": "https://prod.example"}]}
    working = {"module_metadata": {"custom": {"title": "Custom"}}}
    merged = _merge_config(default, working)
    assert merged["registries"] == default["registries"]


def test_a_working_copy_overriding_one_store_keeps_the_others() -> None:
    default = {"registries": [
        {"key": "prod", "label": "Prod", "url": "https://prod.example"},
        {"key": "polygon", "label": "Polygon", "url": "https://polygon.example", "mode": "test"},
    ]}
    working = {"registries": [{"key": "prod", "label": "Self-hosted", "url": "https://mine.example"}]}
    merged = _merge_config(default, working)
    config = ModulesConfig.model_validate(merged)
    by_key = {store.key: store for store in config.registries}
    assert by_key["prod"].base_url == "https://mine.example"      # working copy wins per store
    assert by_key["polygon"].base_url == "https://polygon.example"  # and does not delete the rest


# --------------------------------------------------------------------------- default selection

def test_registry_url_decides_which_store_opens(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI, the bundled client and registry_precheck.py all read $REGISTRY_URL.

    If the UI ignored it, a checkout wired to one server would browse another.
    """
    monkeypatch.setenv("REGISTRY_URL", "https://module-polygon.just-dna.life")
    assert default_registry_store().key == "polygon"
    monkeypatch.setenv("REGISTRY_URL", "https://module-registry.just-dna.life/")
    assert default_registry_store().key == "prod"


def test_an_unlisted_registry_url_becomes_its_own_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """A self-hosted server must stay reachable, and must not delete the configured ones."""
    monkeypatch.setenv("REGISTRY_URL", "https://registry.selfhosted.example")
    stores = get_registry_stores()
    assert default_registry_store().base_url == "https://registry.selfhosted.example"
    assert {"prod", "polygon"} <= {store.key for store in stores}


def test_an_unknown_key_falls_back_to_the_default_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Selection arrives from the client, so an unknown key is a possibility, not a bug."""
    from webui.state import _resolve_store

    monkeypatch.setenv("REGISTRY_URL", "https://module-registry.just-dna.life")
    assert _resolve_store("nonesuch").key == "prod"
    assert _resolve_store("polygon").key == "polygon"


# --------------------------------------------------------------------------- identity

def _identity_at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from webui import registry_identity

    path = tmp_path / "registry_identity.json"
    monkeypatch.setattr(registry_identity, "identity_path", lambda: path)
    return path


def test_a_flat_pre_store_identity_migrates_into_the_default_store_slot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stored profile predates stores, and was minted against whatever $REGISTRY_URL named."""
    from webui import registry_identity

    monkeypatch.setenv("REGISTRY_URL", "https://module-registry.just-dna.life")
    path = _identity_at(tmp_path, monkeypatch)
    path.write_text(json.dumps({
        "install_id": "iid-1", "token": "tok-prod", "account": "just-dna-seq",
        "namespaces": ["just-dna-seq"], "display_name": "Someone", "email": "a@b.c",
    }), encoding="utf-8")

    data = registry_identity.load_identity()
    assert data["install_id"] == "iid-1"          # machine-local, shared across stores
    assert data["stores"]["prod"]["token"] == "tok-prod"
    assert "token" not in data                     # no second, unowned copy of a bearer token
    assert registry_identity.load_store_identity("polygon") == {}


def test_saving_one_store_leaves_the_other_and_the_install_id_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from webui import registry_identity

    path = _identity_at(tmp_path, monkeypatch)
    path.write_text(json.dumps({
        "install_id": "iid-1",
        "stores": {"prod": {"token": "tok-prod", "account": "just-dna-seq"}},
    }), encoding="utf-8")

    registry_identity.save_store_identity("polygon", {"token": "tok-poly", "account": "tester"})

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["install_id"] == "iid-1"
    assert data["stores"]["prod"]["token"] == "tok-prod"
    assert data["stores"]["polygon"]["token"] == "tok-poly"


# --------------------------------------------------------------------------- state wiring

def _state():
    from webui.state import RegistryState

    return RegistryState(_reflex_internal_init=True)


def test_every_registry_call_follows_the_selected_store() -> None:
    """`_client_args` is the single choke point all ~15 RegistryClient sites go through."""
    state = _state()
    state.store_key = "polygon"
    assert state._client_args()[0] == "https://module-polygon.just-dna.life"
    state.store_key = "prod"
    assert state._client_args()[0] == "https://module-registry.just-dna.life"


def test_switching_stores_drops_the_previous_server_s_account() -> None:
    """Would have sent one server's bearer token to another, and shown its account as signed in."""
    state = _state()
    state.store_key = "prod"
    state.token = "tok-prod"
    state.account = "just-dna-seq"
    state.namespaces = ["just-dna-seq"]
    state.publish_namespace = "just-dna-seq"
    state.cards = [{"name": "coronary"}]
    state.selected_name = "just_dna_seq__coronary"
    state.selected_versions = ["1.0.0"]

    state._reset_for_store_switch()

    assert state.token == ""
    assert state.account == ""
    assert state.namespaces == []
    assert state.publish_namespace == ""
    assert state.cards == []
    assert state.selected_name == ""
    assert state.selected_versions == []


def test_a_half_migrated_file_still_moves_the_flat_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One store already saved must not cost the pre-store profile its token."""
    from webui import registry_identity

    monkeypatch.setenv("REGISTRY_URL", "https://module-registry.just-dna.life")
    path = _identity_at(tmp_path, monkeypatch)
    path.write_text(json.dumps({
        "install_id": "iid-1", "token": "tok-prod", "account": "just-dna-seq",
        "stores": {"polygon": {"token": "tok-poly"}},
    }), encoding="utf-8")

    data = registry_identity.load_identity()
    assert data["stores"]["prod"]["token"] == "tok-prod"
    assert data["stores"]["polygon"]["token"] == "tok-poly"


def test_the_ui_does_not_sign_in_with_the_cli_s_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`$REGISTRY_TOKEN` is the CLI's publishing credential, not a UI session.

    Reading it here would sign the page in as whichever account owns it with no user action, and
    `_refresh_account` would then persist it into the store slot — a second copy of a bearer token
    that shadows `.env` from then on, which is exactly what the per-store migration avoids.
    """
    import asyncio

    from webui import registry_identity

    monkeypatch.setenv("REGISTRY_URL", "https://module-registry.just-dna.life")
    monkeypatch.setenv("REGISTRY_TOKEN", "cli-token")
    path = _identity_at(tmp_path, monkeypatch)
    path.write_text(json.dumps({"install_id": "iid-1", "stores": {}}), encoding="utf-8")

    state = _state()
    state.store_key = "prod"
    asyncio.run(state._ensure_identity())

    assert state.token == ""
    assert state.account == ""
    assert registry_identity.load_store_identity("prod") == {}


def test_a_stores_own_slot_is_what_signs_the_page_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """And it is per store: polygon's slot must not inherit prod's account."""
    import asyncio

    monkeypatch.setenv("REGISTRY_URL", "https://module-registry.just-dna.life")
    path = _identity_at(tmp_path, monkeypatch)
    path.write_text(json.dumps({
        "install_id": "iid-1",
        "stores": {"prod": {"token": "tok-prod", "account": "just-dna-seq",
                            "namespaces": ["just-dna-seq"]}},
    }), encoding="utf-8")

    state = _state()
    state.store_key = "prod"
    asyncio.run(state._ensure_identity())
    assert (state.token, state.account) == ("tok-prod", "just-dna-seq")

    state.store_key = "polygon"
    asyncio.run(state._ensure_identity())
    assert (state.token, state.account) == ("", "")
