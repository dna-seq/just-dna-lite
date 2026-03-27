"""
Module configuration loader.

Reads modules.yaml to determine which sources to scan for annotation modules
and provides optional display metadata overrides for discovered modules.

The file is searched in three locations (first found wins):
  1. Working copy ``data/interim/modules.yaml`` (mutable, gitignored)
  2. Project root ``modules.yaml`` (git-tracked, read-only defaults)
  3. Package directory ``just_dna_pipelines/`` (bundled fallback)

All writes (register/unregister custom modules) go to the working copy.
On first write the repo default is copied as the seed so settings like
quality_filters and ensembl_source carry over.

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

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Literal, Optional

import polars as pl
import yaml
from pydantic import BaseModel, model_validator


# Default values for modules not listed in the YAML
_DEFAULT_ICON = "database"
_DEFAULT_COLOR = "#6435c9"


class QualityFilters(BaseModel):
    """VCF quality filter thresholds loaded from modules.yaml.

    Applied during normalization to remove low-quality variants before annotation.
    All fields default to None (no filtering) for backward compatibility.
    """
    pass_filters: Optional[list[str]] = None
    min_depth: Optional[int] = None
    min_qual: Optional[float] = None

    @property
    def is_active(self) -> bool:
        """True if at least one filter is configured."""
        return bool(self.pass_filters) or bool(self.min_depth) or bool(self.min_qual)

    def config_hash(self) -> str:
        """Deterministic hash of the active filter settings for DataVersion tracking."""
        canonical = json.dumps(self.model_dump(), sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _find_column(schema_names: list[str], candidates: tuple[str, ...]) -> Optional[str]:
    """Return the first column name from *candidates* found in *schema_names*, or None."""
    for col in candidates:
        if col in schema_names:
            return col
    return None


def build_quality_filter_expr(
    filters: QualityFilters,
    schema_names: list[str],
) -> Optional[pl.Expr]:
    """Build a combined Polars filter expression from quality filter config.

    Returns None if no filters are active or no matching columns exist.
    """
    conditions: list[pl.Expr] = []

    if filters.pass_filters:
        col = _find_column(schema_names, ("filter", "Filter", "FILTER"))
        if col is not None:
            conditions.append(pl.col(col).is_in(filters.pass_filters))

    if filters.min_depth is not None and filters.min_depth > 0:
        col = _find_column(schema_names, ("DP", "Dp", "dp"))
        if col is not None:
            conditions.append(pl.col(col).cast(pl.Int64, strict=False) >= filters.min_depth)

    if filters.min_qual is not None and filters.min_qual > 0:
        col = _find_column(schema_names, ("qual", "Qual", "QUAL"))
        if col is not None:
            conditions.append(pl.col(col).cast(pl.Float64, strict=False) >= filters.min_qual)

    if not conditions:
        return None
    return conditions[0] if len(conditions) == 1 else pl.all_horizontal(conditions)


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


class EnsemblSource(BaseModel):
    """Ensembl variation reference dataset configuration.

    Loaded from ``ensembl_source:`` in modules.yaml.
    The ``repo_id`` must be a HuggingFace dataset (``org/repo``).
    """
    repo_id: str = "just-dna-seq/ensembl_variations"


class ModulesConfig(BaseModel):
    """Top-level configuration from modules.yaml."""
    sources: list[Source] = [Source(url="just-dna-seq/annotators")]
    module_metadata: dict[str, ModuleMetadata] = {}
    quality_filters: QualityFilters = QualityFilters()
    ensembl_source: EnsemblSource = EnsemblSource()

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


def _find_project_root() -> Optional[Path]:
    """Find the workspace root.

    Resolution: ``JUST_DNA_PIPELINES_ROOT`` env var, then walk up from CWD
    looking for a pyproject.toml with ``[tool.uv.workspace]``.
    """
    env_root = os.getenv("JUST_DNA_PIPELINES_ROOT")
    if env_root:
        return Path(env_root).resolve()
    candidate = Path.cwd()
    for _ in range(10):
        pyproject = candidate / "pyproject.toml"
        if pyproject.exists() and "[tool.uv.workspace]" in pyproject.read_text():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    return None


def _working_config_path() -> Optional[Path]:
    """Return the path for the mutable working copy of modules.yaml.

    Resolution order:
      1. ``JUST_DNA_MODULES_YAML`` env var (absolute path)
      2. ``data/interim/modules.yaml`` under the project root (gitignored)

    Returns None when neither is available.
    """
    env = os.getenv("JUST_DNA_MODULES_YAML")
    if env:
        return Path(env)
    project_root = _find_project_root()
    if project_root is None:
        return None
    return project_root / "data" / "interim" / "modules.yaml"


def _default_config_path() -> Optional[Path]:
    """Return the path of the repo-shipped (read-only) modules.yaml.

    Checks project root first, then falls back to the package directory.
    """
    project_root = _find_project_root()
    if project_root is not None:
        candidate = project_root / "modules.yaml"
        if candidate.exists():
            return candidate
    pkg = Path(__file__).parent / "modules.yaml"
    if pkg.exists():
        return pkg
    return None


def _load_config() -> ModulesConfig:
    """Load modules.yaml, checking three locations in order:

    1. Working copy at ``data/interim/modules.yaml`` (mutable, gitignored)
    2. Project root ``modules.yaml`` (git-tracked, read-only defaults)
    3. Package directory ``modules.yaml`` (bundled fallback)

    The first file found wins.  If none exist, returns defaults.
    """
    search_paths: list[Path] = []

    working = _working_config_path()
    if working is not None:
        search_paths.append(working)

    project_root = _find_project_root()
    if project_root is not None:
        search_paths.append(project_root / "modules.yaml")

    search_paths.append(Path(__file__).parent / "modules.yaml")

    for config_path in search_paths:
        if config_path.exists():
            with open(config_path) as f:
                raw = yaml.safe_load(f)
            if raw is not None:
                return ModulesConfig.model_validate(raw)

    return ModulesConfig()


def get_config_path() -> Path:
    """Return the writable modules.yaml path (working copy).

    All mutations (register/unregister) target this path, never the
    git-tracked repo default.  Falls back to the package directory only
    when no project root can be found.
    """
    working = _working_config_path()
    if working is not None:
        return working
    return Path(__file__).parent / "modules.yaml"


def save_config(config: ModulesConfig, path: Optional[Path] = None) -> None:
    """Persist a ModulesConfig to the working copy using a merge strategy.

    On first write the repo default is copied as the seed so that
    quality_filters, ensembl_source, etc. are preserved.  Only the
    ``sources`` and ``module_metadata`` keys are patched.
    """
    target = path or get_config_path()

    raw: Dict[str, Any] = {}
    if target.exists():
        with open(target) as f:
            raw = yaml.safe_load(f) or {}
    else:
        default = _default_config_path()
        if default is not None and default.exists():
            with open(default) as f:
                raw = yaml.safe_load(f) or {}

    sources_data = []
    for src in config.sources:
        entry: Dict[str, Any] = {"url": src.url}
        if src.kind is not None:
            entry["kind"] = src.kind
        if src.name is not None:
            entry["name"] = src.name
        sources_data.append(entry)
    raw["sources"] = sources_data

    metadata_data: Dict[str, Any] = {}
    for name, meta in config.module_metadata.items():
        entry = {}
        if meta.title is not None:
            entry["title"] = meta.title
        if meta.description is not None:
            entry["description"] = meta.description
        if meta.report_title is not None:
            entry["report_title"] = meta.report_title
        if meta.icon != _DEFAULT_ICON:
            entry["icon"] = meta.icon
        if meta.color != _DEFAULT_COLOR:
            entry["color"] = meta.color
        metadata_data[name] = entry
    raw["module_metadata"] = metadata_data

    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w") as f:
        yaml.dump(raw, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


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
