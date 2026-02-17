"""
Module configuration loader.

Reads modules.yaml to determine which sources to scan for annotation modules
and provides optional display metadata overrides for discovered modules.

Modules are always auto-discovered from sources. This config only controls
which sources to scan and how modules are displayed in the UI, CLI, and
reports. Modules not listed in the YAML get sensible defaults.

Supported source types (auto-detected from URL):
  - "org/repo" or "hf://datasets/org/repo" -> HuggingFace
  - "github://org/repo"                    -> GitHub via fsspec
  - "https://..." / "http://..."           -> HTTP via fsspec
  - "s3://...", "gcs://...", etc.           -> cloud storage via fsspec

Each source can be a single module or a collection of modules.
Auto-detect: weights.parquet at root = module, subfolders = collection.
Override with kind: "module" or kind: "collection".
"""

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, model_validator


# Default values for modules not listed in the YAML
_DEFAULT_ICON = "database"
_DEFAULT_COLOR = "#6435c9"


class ModuleMetadata(BaseModel):
    """Display metadata for an annotation module."""
    title: Optional[str] = None
    description: Optional[str] = None
    report_title: Optional[str] = None
    icon: str = _DEFAULT_ICON
    color: str = _DEFAULT_COLOR


class Source(BaseModel):
    """
    A source of annotation modules.

    Can be a collection (scans subfolders) or a single module.
    Source type is auto-detected from the URL pattern.
    """
    url: str
    kind: Optional[Literal["module", "collection"]] = None  # None = auto-detect
    name: Optional[str] = None  # Name override for single-module sources

    @property
    def is_hf(self) -> bool:
        """Check if this is a HuggingFace source."""
        if self.url.startswith("hf://"):
            return True
        # Shorthand: "org/repo" with no protocol prefix and exactly one slash
        if "://" not in self.url and self.url.count("/") == 1:
            return True
        return False

    @property
    def hf_repo_id(self) -> Optional[str]:
        """Extract HuggingFace repo ID from the URL."""
        if not self.is_hf:
            return None
        if self.url.startswith("hf://datasets/"):
            return self.url.removeprefix("hf://datasets/").rstrip("/")
        if self.url.startswith("hf://"):
            return self.url.removeprefix("hf://").rstrip("/")
        # Shorthand: "org/repo"
        return self.url.rstrip("/")

    @property
    def protocol(self) -> str:
        """Extract the fsspec protocol from the URL."""
        if "://" in self.url:
            return self.url.split("://")[0]
        # Shorthand HF
        if self.is_hf:
            return "hf"
        return "file"


class ModulesConfig(BaseModel):
    """Top-level configuration from modules.yaml."""
    sources: list[Source] = [Source(url="just-dna-seq/annotators")]
    module_metadata: dict[str, ModuleMetadata] = {}

    @model_validator(mode="before")
    @classmethod
    def _normalize_sources(cls, data: dict) -> dict:
        """Allow sources to be plain strings or dicts."""
        if "sources" in data and isinstance(data["sources"], list):
            normalized = []
            for item in data["sources"]:
                if isinstance(item, str):
                    normalized.append({"url": item})
                else:
                    normalized.append(item)
            data["sources"] = normalized
        return data


def _load_config() -> ModulesConfig:
    """Load modules.yaml from the package directory."""
    config_path = Path(__file__).parent / "modules.yaml"
    if not config_path.exists():
        return ModulesConfig()
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    if raw is None:
        return ModulesConfig()
    return ModulesConfig.model_validate(raw)


# Loaded once at import time
MODULES_CONFIG: ModulesConfig = _load_config()

# Backward-compatible: list of HF repo IDs extracted from sources
DEFAULT_REPOS: list[str] = [
    s.hf_repo_id for s in MODULES_CONFIG.sources
    if s.is_hf and s.hf_repo_id is not None
]


def get_module_meta(name: str) -> ModuleMetadata:
    """
    Get display metadata for a module.

    Returns the YAML override if present, otherwise auto-generates
    sensible defaults from the module folder name.
    """
    if name in MODULES_CONFIG.module_metadata:
        meta = MODULES_CONFIG.module_metadata[name]
        title = meta.title or name.replace("_", " ").title()
        return ModuleMetadata(
            title=title,
            description=meta.description or f"Annotation module: {name}",
            report_title=meta.report_title or title,
            icon=meta.icon,
            color=meta.color,
        )
    # Fully auto-generated for unknown modules
    title = name.replace("_", " ").title()
    return ModuleMetadata(
        title=title,
        description=f"Annotation module: {name}",
        report_title=title,
        icon=_DEFAULT_ICON,
        color=_DEFAULT_COLOR,
    )


def get_module_display_name(name: str) -> str:
    """Get the report/display title for a module."""
    return get_module_meta(name).report_title or name.replace("_", " ").title()


def get_module_description(name: str) -> str:
    """Get the description for a module."""
    return get_module_meta(name).description or f"Annotation module: {name}"


def build_module_metadata_dict(module_names: list[str]) -> dict[str, dict[str, str]]:
    """
    Build a MODULE_METADATA-style dict for a list of discovered module names.

    Returns a dict compatible with the format used by webui state.py:
        {name: {"title": ..., "description": ..., "icon": ..., "color": ...}}
    """
    result: dict[str, dict[str, str]] = {}
    for name in module_names:
        meta = get_module_meta(name)
        result[name] = {
            "title": meta.title or name,
            "description": meta.description or "",
            "icon": meta.icon,
            "color": meta.color,
        }
    return result


def build_display_names_dict(module_names: list[str]) -> dict[str, str]:
    """
    Build a MODULE_DISPLAY_NAMES-style dict for a list of discovered module names.

    Returns {name: report_title} compatible with report_logic.py.
    """
    return {name: get_module_display_name(name) for name in module_names}
