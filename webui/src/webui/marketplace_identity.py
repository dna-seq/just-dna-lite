"""
Marketplace identity — backend groundwork for publishing.

Persists a proof-of-work *install-id* (and, once minted, an account token) so the
publishing flow can later call ``RegistryClient.register(install_id, account)``
without re-grinding the PoW. Pure backend: no UI wiring here.

Stored as JSON next to the working modules config (``data/interim/marketplace_identity.json``,
gitignored). The install-id is machine-local and non-secret; the token, once present, is a
bearer credential and must not be exposed to the frontend.
"""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any, Dict

from just_dna_registry import generate_install_id, validate_install_id
from just_dna_pipelines.module_config import get_config_path

_DIFFICULTY: int = 20

# Account handle slug rule (marketplace): ^[a-z0-9][a-z0-9-]*$ — lowercase alnum + hyphens.
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
