"""Dagster instance resolution, free of any reflex import.

Extracted from ``webui.state`` so compute-tier children can reach a Dagster instance
without importing the whole UI state module (which pulls reflex, agno and the module
registry).  Spawned children start from a bare interpreter, so what a child imports is
what a child pays for.
"""

from __future__ import annotations

import os
from pathlib import Path

from dagster import DagsterInstance

DEFAULT_DAGSTER_HOME = "data/interim/dagster"

_DAGSTER_CONFIG = """# Dagster instance configuration
# Storage defaults to DAGSTER_HOME

# Enable auto-materialization for assets with AutoMaterializePolicy
auto_materialize:
  enabled: true
  minimum_interval_seconds: 60
"""


def workspace_root() -> Path:
    """Return the uv workspace root (the directory holding webui/ and data/)."""
    return Path(__file__).resolve().parents[3]


def ensure_dagster_config(dagster_home: Path) -> None:
    """Create ``dagster.yaml`` with auto-materialization enabled if it is missing."""
    config_file = dagster_home / "dagster.yaml"
    if config_file.exists():
        return
    dagster_home.mkdir(parents=True, exist_ok=True)
    config_file.write_text(_DAGSTER_CONFIG, encoding="utf-8")


def ensure_dagster_home() -> Path:
    """Resolve DAGSTER_HOME to an absolute path, create its config, and export it.

    Exporting into ``os.environ`` matters for the compute tier: spawned children
    inherit the parent's environment, so a child calling ``DagsterInstance.get()``
    lands on the same instance the UI is reading from.
    """
    configured = os.getenv("DAGSTER_HOME", DEFAULT_DAGSTER_HOME)
    dagster_home = Path(configured)
    if not dagster_home.is_absolute():
        dagster_home = (workspace_root() / dagster_home).resolve()
    ensure_dagster_config(dagster_home)
    os.environ["DAGSTER_HOME"] = str(dagster_home)
    return dagster_home


def get_dagster_instance() -> DagsterInstance:
    """Return the shared Dagster instance, ensuring DAGSTER_HOME is set first."""
    ensure_dagster_home()
    return DagsterInstance.get()
