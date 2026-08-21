"""
Registry identity — backend groundwork for publishing.

Persists a proof-of-work *install-id* (and, once minted, an account token) so the
publishing flow can later call ``RegistryClient.register(install_id, account)``
without re-grinding the PoW. Pure backend: no UI wiring here.

Stored as JSON next to the working modules config (``data/interim/registry_identity.json``,
gitignored). The install-id is machine-local and non-secret; the token, once present, is a
bearer credential and must not be exposed to the frontend.

**The profile is per store, the install-id is not.** An account, its token and its namespaces are
minted by one registry server and mean nothing to another, so each store keyed in ``registries:``
gets its own slot under ``stores``. The proof-of-work install-id identifies this *machine* and is
shared. A file written before stores existed is a flat profile; it is migrated into the default
store's slot on first read (see ``_migrated``).
"""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any, Dict

from just_dna_registry import generate_install_id, validate_install_id
from just_dna_pipelines.module_config import default_registry_store, get_config_path

_DIFFICULTY: int = 20

# Account handle slug rule (registry): ^[a-z0-9][a-z0-9-]*$ — lowercase alnum + hyphens.
# Note this differs from the display-name rule ([A-Za-z0-9_]), so underscores map to hyphens.


def derive_handle(display_name: str) -> str:
    """Derive an immutable account handle from a (already-validated) display name.

    Lowercase, map ``_`` → ``-``, drop anything outside ``[a-z0-9-]``, and append a short random
    suffix so distinct users with the same display name don't collide. Retry with a fresh suffix on
    a ``409 account_taken`` at the call site.
    """
    base = "".join(c if (c.isalnum() or c == "-") else "" for c in display_name.lower().replace("_", "-"))
    base = base.strip("-")[:24] or "user"
    if not base[0].isalnum():
        base = "u" + base
    return f"{base}-{secrets.token_hex(3)}"


def set_env_var(name: str, value: str) -> None:
    """Mirror a value into ``os.environ`` and the workspace ``.env`` (read-modify-write).

    Used to back up the registry token as ``REGISTRY_TOKEN`` so it's copyable/portable,
    mirroring how API keys are persisted. The identity JSON remains the source of truth.
    """
    os.environ[name] = value
    env_path = Path(__file__).resolve().parents[3] / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    for i, line in enumerate(lines):
        if line.lstrip("# \t").startswith(f"{name}="):
            lines[i] = f"{name}={value}"
            break
    else:
        lines.append(f"{name}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def identity_path() -> Path:
    """Location of the persisted identity file (alongside the working modules.yaml)."""
    return get_config_path().parent / "registry_identity.json"


#: Profile fields that belong to one registry server rather than to this machine.
_PROFILE_KEYS: tuple[str, ...] = (
    "token", "account", "namespaces", "display_name", "email", "avatar_local",
)


def _migrated(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a stored identity to the per-store shape, moving a flat profile into a slot.

    A pre-store file holds one profile at the top level, and that profile was necessarily minted
    against whatever ``REGISTRY_URL`` pointed at, i.e. the default store. Dropping the flat keys
    afterwards is deliberate: leaving them would give a second, ambiguous copy of a bearer token
    that no store owns.
    """
    out = {k: v for k, v in data.items() if k not in _PROFILE_KEYS}
    stores = out.get("stores")
    out["stores"] = dict(stores) if isinstance(stores, dict) else {}
    flat = {k: data[k] for k in _PROFILE_KEYS if data.get(k)}
    # Keyed on the slot being absent rather than on `stores` being empty: a half-migrated file
    # (another store already saved, the flat profile not yet moved) would otherwise have its flat
    # token dropped instead of migrated.
    default_key = default_registry_store().key
    if flat and default_key not in out["stores"]:
        out["stores"][default_key] = flat
    return out


def load_identity() -> Dict[str, Any]:
    """Read the persisted identity (per-store shape), or an empty dict if absent/corrupt."""
    path = identity_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - corrupt file degrades to "no identity yet"
        return {}
    return _migrated(data) if isinstance(data, dict) else {}


def load_store_identity(store_key: str) -> Dict[str, Any]:
    """The account profile held for one registry server ({} when that store has none yet)."""
    slot = load_identity().get("stores", {}).get(store_key)
    return dict(slot) if isinstance(slot, dict) else {}


def save_store_identity(store_key: str, profile: Dict[str, Any]) -> None:
    """Replace one store's profile slot, leaving the install-id and other stores untouched."""
    data = load_identity()
    stores = dict(data.get("stores") or {})
    stores[store_key] = profile
    data["stores"] = stores
    save_identity(data)


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
