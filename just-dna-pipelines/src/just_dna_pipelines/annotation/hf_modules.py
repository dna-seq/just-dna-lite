"""
HuggingFace Annotator Modules - Dynamic discovery and utilities.

This module discovers available annotation modules from the
just-dna-seq/annotators HuggingFace repository by scanning
the repository folders at startup.
"""

from enum import Enum
from typing import Optional

import polars as pl
from eliot import log_message
from pydantic import BaseModel


# HuggingFace repository info
HF_DEFAULT_REPOS = ["just-dna-seq/annotators"]
HF_REPO_ID = HF_DEFAULT_REPOS[0]  # For backward compatibility

# Tables available in each module
MODULE_TABLES = ["annotations", "studies", "weights"]

# Static fallback list (used if HF is unreachable)
STATIC_FALLBACK_MODULES = ["longevitymap", "lipidmetabolism", "vo2max", "superhuman", "coronary"]


class ModuleInfo(BaseModel):
    """Information about a discovered HF module."""
    name: str
    repo_id: str
    path: str  # Path within the repo (e.g. datasets/repo/data/module)
    weights_url: str
    annotations_url: Optional[str] = None
    studies_url: Optional[str] = None
    logo_url: Optional[str] = None
    metadata_url: Optional[str] = None


def discover_hf_modules(repo_ids: Optional[list[str]] = None) -> dict[str, ModuleInfo]:
    """
    Discover available modules by scanning folders in one or more HF repositories.
    
    Scans datasets/{repo_id}/data/ and returns a mapping of module names to ModuleInfo.
    If a name collision occurs, the first repository in the list takes precedence.
    
    Falls back to a basic mapping if HF is unreachable.
    
    Args:
        repo_ids: List of HF repository IDs to scan. Defaults to HF_DEFAULT_REPOS.
        
    Returns:
        Mapping of module names to ModuleInfo (e.g., {"longevitymap": ModuleInfo(...), ...})
    """
    repos = repo_ids or HF_DEFAULT_REPOS
    module_infos = {}
    
    try:
        from huggingface_hub import HfFileSystem
        fs = HfFileSystem()
        
        for repo_id in repos:
            base_path = f"datasets/{repo_id}/data"
            try:
                if not fs.exists(base_path):
                    continue
                    
                entries = fs.ls(base_path, detail=True)
                for entry in entries:
                    if entry["type"] == "directory":
                        folder_name = entry["name"].split("/")[-1]
                        
                        # Skip if already discovered (precedence to earlier repos)
                        if folder_name in module_infos:
                            continue
                            
                        # Verify it has weights.parquet
                        weights_path = f"{entry['name']}/weights.parquet"
                        if not fs.exists(weights_path):
                            continue
                            
                        # Check for optional files
                        annotations_path = f"{entry['name']}/annotations.parquet"
                        studies_path = f"{entry['name']}/studies.parquet"
                        logo_path = f"{entry['name']}/logo.png"
                        metadata_path = f"{entry['name']}/metadata.json"
                        
                        info = ModuleInfo(
                            name=folder_name,
                            repo_id=repo_id,
                            path=entry["name"],
                            weights_url=f"hf://{entry['name']}/weights.parquet",
                            annotations_url=f"hf://{annotations_path}" if fs.exists(annotations_path) else None,
                            studies_url=f"hf://{studies_path}" if fs.exists(studies_path) else None,
                            logo_url=f"hf://{logo_path}" if fs.exists(logo_path) else None,
                            metadata_url=f"hf://{metadata_path}" if fs.exists(metadata_path) else None,
                        )
                        module_infos[folder_name] = info
                        
            except Exception as e:
                log_message(
                    message_type="warning",
                    action="discover_hf_modules",
                    repo_id=repo_id,
                    message=f"Failed to scan repo {repo_id}: {e}",
                )
                
        if module_infos:
            log_message(
                message_type="info",
                action="discover_hf_modules",
                modules=list(module_infos.keys()),
                source="huggingface",
            )
            return module_infos
            
        log_message(
            message_type="warning",
            action="discover_hf_modules",
            message="No modules found in HF repos, using fallback",
        )
        return {m: ModuleInfo(
            name=m, 
            repo_id=HF_REPO_ID, 
            path=f"datasets/{HF_REPO_ID}/data/{m}",
            weights_url=f"hf://datasets/{HF_REPO_ID}/data/{m}/weights.parquet"
        ) for m in STATIC_FALLBACK_MODULES}
        
    except Exception as e:
        log_message(
            message_type="warning",
            action="discover_hf_modules",
            message=f"Critical failure in module discovery: {e}, using fallback",
        )
        return {m: ModuleInfo(
            name=m, 
            repo_id=HF_REPO_ID, 
            path=f"datasets/{HF_REPO_ID}/data/{m}",
            weights_url=f"hf://datasets/{HF_REPO_ID}/data/{m}/weights.parquet"
        ) for m in STATIC_FALLBACK_MODULES}


# Cache discovered modules at import time
MODULE_INFOS: dict[str, ModuleInfo] = discover_hf_modules()
DISCOVERED_MODULES: list[str] = sorted(list(MODULE_INFOS.keys()))


class ModuleTable(str, Enum):
    """Tables available in each HF annotator module."""
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
    Get the HuggingFace URL for a specific module table.
    
    Args:
        module_name: Name of the module (e.g., "longevitymap")
        table: Table name or ModuleTable enum
        module_info: Optional ModuleInfo. If not provided, uses global DISCOVERED_MODULES.
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
    
    # Fallback/default logic for unknown tables
    return f"hf://{info.path}/{table_name}.parquet"


def scan_module_table(
    module_name: str,
    table: str | ModuleTable,
    cache_dir: Optional[str] = None,
    module_info: Optional[ModuleInfo] = None,
) -> pl.LazyFrame:
    """
    Lazily scan a module table from HuggingFace.
    
    Uses Polars' native HF support for efficient streaming.
    
    Args:
        module_name: Name of the module (e.g., "longevitymap")
        table: Which table to load (annotations, studies, weights)
        cache_dir: Optional local cache directory (uses HF cache by default)
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
