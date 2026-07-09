"""
Marketplace identity — backend groundwork for publishing.

Persists a proof-of-work *install-id* (and, once minted, an account token) so the
publishing flow can later call ``MarketplaceClient.register(install_id, account)``
without re-grinding the PoW. Pure backend: no UI wiring here.

Stored as JSON next to the working modules config (``data/interim/marketplace_identity.json``,
gitignored). The install-id is machine-local and non-secret; the token, once present, is a
bearer credential and must not be exposed to the frontend.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from just_dna_marketplace import generate_install_id, validate_install_id
from just_dna_pipelines.module_config import get_config_path

_DIFFICULTY: int = 20


def identity_path() -> Path:
    """Location of the persisted identity file (alongside the working modules.yaml)."""
    return get_config_path().parent / "marketplace_identity.json"


def load_identity() -> Dict[str, Any]:
    """Read the persisted identity, or an empty dict if absent/corrupt."""
    path = identity_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 - corrupt file degrades to "no identity yet"
        return {}


def save_identity(data: Dict[str, Any]) -> None:
    """Persist the identity dict (creates the interim dir if needed)."""
    path = identity_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def ensure_install_id() -> str:
    """Return a valid persisted install-id, minting + persisting one if absent.

    Grinding the proof-of-work takes ~1s; call this off the UI thread (executor / background
    event). Idempotent: an already-valid stored id is returned unchanged.
    """
    data = load_identity()
    stored = data.get("install_id", "")
    if stored and validate_install_id(stored, _DIFFICULTY):
        return stored
    minted = generate_install_id(_DIFFICULTY)
    data["install_id"] = minted
    save_identity(data)
    return minted
