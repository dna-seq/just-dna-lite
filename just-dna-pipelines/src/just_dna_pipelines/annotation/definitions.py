"""
Dagster Definitions for annotation pipelines.

This module exports the main Definitions object that Dagster uses
to discover all assets, jobs, and resources.
"""

from pathlib import Path
from dagster import Definitions, define_asset_job, AssetSelection

from just_dna_pipelines.annotation.assets import (
    ensembl_hf_dataset,
    ensembl_annotations,
    user_vcf_source,
    user_annotated_vcf,
)
from just_dna_pipelines.annotation.duckdb_assets import (
    ensembl_duckdb,
    user_annotated_vcf_duckdb,
)
from just_dna_pipelines.annotation.hf_assets import (
    hf_annotators_dataset,
    user_hf_module_annotations,
    hf_module_source_assets,
)
from just_dna_pipelines.annotation.jobs import (
    annotate_vcf_job, 
    annotate_vcf_duckdb_job,
    build_ensembl_duckdb_job,
)
from just_dna_pipelines.annotation.sensors import discover_user_vcf_sensor
from just_dna_pipelines.annotation.io_managers import (
    source_metadata_io_manager,
    annotation_cache_io_manager,
    user_asset_io_manager,
)
from just_dna_pipelines.annotation.registry import load_module_definitions


# Job for HF module annotation
annotate_with_hf_modules_job = define_asset_job(
    name="annotate_with_hf_modules_job",
    selection=AssetSelection.assets(user_hf_module_annotations),
    description="Annotate user VCF with HuggingFace modules (longevitymap, lipidmetabolism, vo2max, etc.)",
    tags={"annotation": "hf_modules", "multi-user": "true"},
)


def _build_definitions() -> Definitions:
    """Build the combined definitions from core + discovered modules."""
    # 1. Core definitions (Ensembl-based, Polars)
    _core = Definitions(
        assets=[
            ensembl_hf_dataset,
            ensembl_annotations,
            user_vcf_source,
            user_annotated_vcf,
        ],
        jobs=[annotate_vcf_job, annotate_vcf_duckdb_job],
        sensors=[discover_user_vcf_sensor],
        resources={
            "source_metadata_io_manager": source_metadata_io_manager,
            "annotation_cache_io_manager": annotation_cache_io_manager,
            "user_asset_io_manager": user_asset_io_manager,
        },
    )
    
    # 2. DuckDB-based alternative assets for performance comparison
    _duckdb = Definitions(
        assets=[ensembl_duckdb, user_annotated_vcf_duckdb],
        jobs=[build_ensembl_duckdb_job],
    )
    
    # 3. HuggingFace module annotation assets (self-contained, no Ensembl needed)
    _hf_modules = Definitions(
        assets=[
            hf_annotators_dataset,
            user_hf_module_annotations,
            *hf_module_source_assets,
        ],
        jobs=[annotate_with_hf_modules_job],
    )
    
    # 4. Discover and merge module definitions from data/modules/
    modules_dir = Path("data") / "modules"
    module_defs_list = load_module_definitions(modules_dir)
    
    # 5. Merge everything
    all_defs = [_core, _duckdb, _hf_modules]
    if module_defs_list:
        all_defs.extend(module_defs_list)
    
    return Definitions.merge(*all_defs)


# Single Definitions object at module scope (required by Dagster)
defs = _build_definitions()

