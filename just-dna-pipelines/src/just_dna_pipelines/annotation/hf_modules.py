"""
Annotator Modules - Dynamic discovery and utilities.

Discovers available annotation modules by scanning configured sources
(HuggingFace, GitHub, HTTP, S3, or any fsspec-compatible URL) at startup.
Sources are configured in modules.yaml (see module_config.py).
"""

from enum import Enum
from typing import Optional

import polars as pl
from eliot import log_message
from pydantic import BaseModel

from just_dna_pipelines.module_config import DEFAULT_REPOS, MODULES_CONFIG, Source


# Backward-compatible aliases sourced from modules.yaml
HF_DEFAULT_REPOS: list[str] = DEFAULT_REPOS
HF_REPO_ID: str = HF_DEFAULT_REPOS[0] if HF_DEFAULT_REPOS else ""

# Tables available in each module
MODULE_TABLES = ["annotations", "studies", "weights"]


class ModuleInfo(BaseModel):
    """Information about a discovered annotation module."""
    name: str
    repo_id: str  # HF repo ID or source URL
    source_url: str = ""  # Original source URL from config
    path: str  # Base path for the module data
    weights_url: str
    annotations_url: Optional[str] = None
    studies_url: Optional[str] = None
    logo_url: Optional[str] = None
    metadata_url: Optional[str] = None


def _get_hf_filesystem() -> "HfFileSystem":
    """Create an HfFileSystem with optional token."""
    from huggingface_hub import HfFileSystem, get_token
    token = get_token()
    return HfFileSystem(token=token)


def _get_fsspec_filesystem(protocol: str, url: str) -> "AbstractFileSystem":
    """Create an fsspec filesystem for the given protocol."""
    import fsspec
    if protocol in ("http", "https"):
        return fsspec.filesystem("http")
    if protocol == "github":
        # github://org/repo -> extract org and repo
        path_part = url.split("://", 1)[1] if "://" in url else url
        parts = path_part.strip("/").split("/")
        if len(parts) >= 2:
            return fsspec.filesystem("github", org=parts[0], repo=parts[1])
        raise ValueError(f"Invalid GitHub URL: {url}")
    return fsspec.filesystem(protocol)


def _build_url(protocol: str, path: str) -> str:
    """Build a full URL from protocol and path."""
    if protocol == "hf":
        return f"hf://{path}"
    if protocol in ("http", "https"):
        return path  # Already a full URL
    return f"{protocol}://{path}"


def _probe_module_at_path(
    fs: "AbstractFileSystem",
    base_path: str,
    protocol: str,
    module_name: str,
    source_url: str,
    repo_id: str,
) -> Optional[ModuleInfo]:
    """
    Probe a directory for module files (weights.parquet, etc.).

    Returns ModuleInfo if weights.parquet exists, None otherwise.
    """
    weights_path = f"{base_path}/weights.parquet"
    if not fs.exists(weights_path):
        return None

    annotations_path = f"{base_path}/annotations.parquet"
    studies_path = f"{base_path}/studies.parquet"
    metadata_json_path = f"{base_path}/metadata.json"
    metadata_yaml_path = f"{base_path}/metadata.yaml"

    # Logo can be .png, .jpg, or .jpeg
    logo_url = None
    for ext in ("png", "jpg", "jpeg"):
        logo_candidate = f"{base_path}/logo.{ext}"
        if fs.exists(logo_candidate):
            logo_url = _build_url(protocol, logo_candidate)
            break

    # Metadata can be .json or .yaml
    resolved_metadata_url = None
    if fs.exists(metadata_json_path):
        resolved_metadata_url = _build_url(protocol, metadata_json_path)
    elif fs.exists(metadata_yaml_path):
        resolved_metadata_url = _build_url(protocol, metadata_yaml_path)

    return ModuleInfo(
        name=module_name,
        repo_id=repo_id,
        source_url=source_url,
        path=base_path,
        weights_url=_build_url(protocol, weights_path),
        annotations_url=_build_url(protocol, annotations_path) if fs.exists(annotations_path) else None,
        studies_url=_build_url(protocol, studies_path) if fs.exists(studies_path) else None,
        logo_url=logo_url,
        metadata_url=resolved_metadata_url,
    )


def _discover_hf_source(source: Source) -> dict[str, ModuleInfo]:
    """Discover modules from a HuggingFace source."""
    repo_id = source.hf_repo_id
    if not repo_id:
        return {}

    fs = _get_hf_filesystem()
    base_path = f"datasets/{repo_id}/data"
    module_infos: dict[str, ModuleInfo] = {}

    # Auto-detect or use explicit kind
    kind = source.kind

    if kind == "module" or (kind is None and not fs.exists(base_path)):
        # Single module: check for weights.parquet at data root or repo root
        for candidate_path in (base_path, f"datasets/{repo_id}"):
            if fs.exists(f"{candidate_path}/weights.parquet"):
                name = source.name or repo_id.split("/")[-1]
                info = _probe_module_at_path(fs, candidate_path, "hf", name, source.url, repo_id)
                if info:
                    module_infos[name] = info
                break
        return module_infos

    # Collection: scan subfolders
    if not fs.exists(base_path):
        return module_infos

    entries = fs.ls(base_path, detail=True)
    for entry in entries:
        if entry["type"] == "directory":
            folder_name = entry["name"].split("/")[-1]
            if folder_name in module_infos:
                continue
            info = _probe_module_at_path(fs, entry["name"], "hf", folder_name, source.url, repo_id)
            if info:
                module_infos[folder_name] = info

    return module_infos


def _discover_fsspec_source(source: Source) -> dict[str, ModuleInfo]:
    """Discover modules from a generic fsspec source."""
    protocol = source.protocol
    fs = _get_fsspec_filesystem(protocol, source.url)
    module_infos: dict[str, ModuleInfo] = {}

    # Determine the base path (strip protocol prefix)
    if "://" in source.url:
        raw_path = source.url.split("://", 1)[1]
    else:
        raw_path = source.url

    # For GitHub, strip org/repo from the path for fs operations
    if protocol == "github":
        parts = raw_path.strip("/").split("/")
        base_path = "/".join(parts[2:]) if len(parts) > 2 else ""
    else:
        base_path = raw_path.rstrip("/")

    kind = source.kind

    if kind == "module":
        name = source.name or base_path.split("/")[-1] if base_path else "unknown"
        info = _probe_module_at_path(fs, base_path, protocol, name, source.url, source.url)
        if info:
            module_infos[name] = info
        return module_infos

    # Auto-detect: check if weights.parquet at root (single module)
    if kind is None and fs.exists(f"{base_path}/weights.parquet"):
        name = source.name or base_path.split("/")[-1] if base_path else "unknown"
        info = _probe_module_at_path(fs, base_path, protocol, name, source.url, source.url)
        if info:
            module_infos[name] = info
        return module_infos

    # Collection: scan subfolders
    entries = fs.ls(base_path, detail=True) if base_path else fs.ls("", detail=True)
    for entry in entries:
        entry_type = entry.get("type", "")
        if entry_type == "directory":
            folder_name = entry["name"].split("/")[-1]
            if folder_name in module_infos:
                continue
            info = _probe_module_at_path(fs, entry["name"], protocol, folder_name, source.url, source.url)
            if info:
                module_infos[folder_name] = info

    return module_infos


def discover_modules_from_source(source: Source) -> dict[str, ModuleInfo]:
    """
    Discover modules from a single source.

    Dispatches to HF-specific or generic fsspec discovery based on the source URL.
    """
    try:
        if source.is_hf:
            return _discover_hf_source(source)
        return _discover_fsspec_source(source)
    except Exception as e:
        log_message(
            message_type="warning",
            action="discover_modules_from_source",
            source_url=source.url,
            message=f"Failed to discover modules from {source.url}: {e}",
        )
        return {}


def discover_all_modules() -> dict[str, ModuleInfo]:
    """
    Discover modules from all configured sources in modules.yaml.

    Earlier sources take precedence on name collisions.
    """
    all_modules: dict[str, ModuleInfo] = {}
    for source in MODULES_CONFIG.sources:
        discovered = discover_modules_from_source(source)
        for name, info in discovered.items():
            if name not in all_modules:
                all_modules[name] = info

    log_message(
        message_type="info",
        action="discover_all_modules",
        modules=list(all_modules.keys()),
        sources=[s.url for s in MODULES_CONFIG.sources],
    )
    return all_modules


def discover_hf_modules(repo_ids: Optional[list[str]] = None) -> dict[str, ModuleInfo]:
    """
    Discover modules from HuggingFace repositories.

    Backward-compatible wrapper. If repo_ids is provided, scans those repos.
    Otherwise uses all configured sources from modules.yaml.

    Args:
        repo_ids: Optional list of HF repo IDs. If None, uses all configured sources.

    Returns:
        Mapping of module names to ModuleInfo.
    """
    if repo_ids is not None:
        # Explicit repo list: build Source objects and discover
        module_infos: dict[str, ModuleInfo] = {}
        for repo_id in repo_ids:
            source = Source(url=repo_id)
            discovered = discover_modules_from_source(source)
            for name, info in discovered.items():
                if name not in module_infos:
                    module_infos[name] = info
        return module_infos

    # Default: use all configured sources
    return discover_all_modules()


# Cache discovered modules at import time
MODULE_INFOS: dict[str, ModuleInfo] = discover_hf_modules()
DISCOVERED_MODULES: list[str] = sorted(list(MODULE_INFOS.keys()))


def refresh_modules() -> dict[str, ModuleInfo]:
    """Reload modules.yaml from disk, re-discover all modules, and update globals.

    This allows runtime registration/unregistration of custom modules
    without restarting the process.

    Returns:
        The refreshed MODULE_INFOS dict.
    """
    import just_dna_pipelines.module_config as mc
    mc.MODULES_CONFIG = mc._load_config()
    mc.DEFAULT_REPOS[:] = [
        s.hf_repo_id for s in mc.MODULES_CONFIG.sources
        if s.is_hf and s.hf_repo_id is not None
    ]

    fresh = discover_all_modules()
    MODULE_INFOS.clear()
    MODULE_INFOS.update(fresh)
    DISCOVERED_MODULES[:] = sorted(MODULE_INFOS.keys())

    log_message(
        message_type="info",
        action="refresh_modules",
        modules=list(DISCOVERED_MODULES),
    )
    return MODULE_INFOS


class ModuleTable(str, Enum):
    """Tables available in each annotator module."""
    ANNOTATIONS = "annotations"
    STUDIES = "studies"
    WEIGHTS = "weights"


def get_module_info(module_name: str) -> ModuleInfo:
    """Get ModuleInfo for a specific module."""
    if module_name not in MODULE_INFOS:
        raise ValueError(f"Module {module_name} not found in discovered modules")
    return MODULE_INFOS[module_name]


def get_module_table_url(module_name: str, table: str | ModuleTable, module_info: Optional[ModuleInfo] = None) -> str:
    """
    Get the URL for a specific module table.

    Args:
        module_name: Name of the module (e.g., "longevitymap")
        table: Table name or ModuleTable enum
        module_info: Optional ModuleInfo. If not provided, uses global MODULE_INFOS.
    """
    info = module_info or get_module_info(module_name)
    table_name = table.value if isinstance(table, ModuleTable) else table

    if table_name == "weights":
        return info.weights_url
    elif table_name == "annotations":
        if not info.annotations_url:
            raise ValueError(f"Module {module_name} does not have an annotations table")
        return info.annotations_url
    elif table_name == "studies":
        if not info.studies_url:
            raise ValueError(f"Module {module_name} does not have a studies table")
        return info.studies_url

    # Fallback for unknown tables
    return f"{info.path}/{table_name}.parquet"


def scan_module_table(
    module_name: str,
    table: str | ModuleTable,
    cache_dir: Optional[str] = None,
    module_info: Optional[ModuleInfo] = None,
) -> pl.LazyFrame:
    """
    Lazily scan a module table.

    Uses Polars' native support for various storage backends.

    Args:
        module_name: Name of the module (e.g., "longevitymap")
        table: Which table to load (annotations, studies, weights)
        cache_dir: Optional local cache directory
        module_info: Optional ModuleInfo for the module

    Returns:
        LazyFrame for memory-efficient processing
    """
    url = get_module_table_url(module_name, table, module_info=module_info)
    return pl.scan_parquet(url)


def scan_module_weights(module_name: str) -> pl.LazyFrame:
    """Convenience function to scan a module's weights table."""
    return scan_module_table(module_name, ModuleTable.WEIGHTS)


def scan_module_annotations(module_name: str) -> pl.LazyFrame:
    """Convenience function to scan a module's annotations table."""
    return scan_module_table(module_name, ModuleTable.ANNOTATIONS)


def scan_module_studies(module_name: str) -> pl.LazyFrame:
    """Convenience function to scan a module's studies table."""
    return scan_module_table(module_name, ModuleTable.STUDIES)


def get_all_modules() -> list[str]:
    """Return all discovered modules."""
    return DISCOVERED_MODULES.copy()


def validate_module(module_name: str) -> bool:
    """Check if a module name is valid (exists in discovered modules)."""
    return module_name.lower() in [m.lower() for m in DISCOVERED_MODULES]


def validate_modules(module_names: list[str]) -> list[str]:
    """
    Validate and filter a list of module names.

    Returns only valid modules that exist in DISCOVERED_MODULES.
    """
    valid = []
    for name in module_names:
        name_lower = name.lower()
        for discovered in DISCOVERED_MODULES:
            if discovered.lower() == name_lower:
                valid.append(discovered)
                break
    return valid


class ModuleOutputMapping(BaseModel):
    """Mapping of output files to their source modules."""
    module: str
    annotations_path: Optional[str] = None
    weights_path: Optional[str] = None
    studies_path: Optional[str] = None
    logo_path: Optional[str] = None
    metadata_path: Optional[str] = None


class AnnotationManifest(BaseModel):
    """Manifest describing all annotation outputs for a user's VCF."""
    user_name: str
    sample_name: str
    source_vcf: str
    modules: list[ModuleOutputMapping]
    total_variants_annotated: int = 0
    # Execution metrics
    duration_sec: Optional[float] = None
    cpu_percent: Optional[float] = None
    peak_memory_mb: Optional[float] = None
    timestamp: Optional[str] = None  # ISO format
