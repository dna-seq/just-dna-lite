"""
Dagster Definitions for annotation pipelines.

This module exports the main Definitions object that Dagster uses
to discover all assets, jobs, and resources.
"""

from pathlib import Path
from dagster import Definitions, define_asset_job, AssetSelection

from just_dna_pipelines.annotation.utils import resource_summary_hook
from just_dna_pipelines.annotation.assets import (
    ensembl_hf_dataset,
    ensembl_annotations,
    quality_filters_config,
    user_vcf_source,
    user_vcf_normalized,
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
from just_dna_pipelines.annotation.report_assets import user_longevity_report
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


# Job for normalizing user VCF to parquet (triggered on upload)
normalize_vcf_job = define_asset_job(
    name="normalize_vcf_job",
    selection=AssetSelection.assets("quality_filters_config", "user_vcf_normalized"),
    description="Normalize user VCF (strip chr prefix, compute genotype, apply quality filters) and persist as parquet.",
    tags={"normalization": "vcf", "multi-user": "true"},
    hooks={resource_summary_hook},
)

# Job for HF module annotation
annotate_with_hf_modules_job = define_asset_job(
    name="annotate_with_hf_modules_job",
    selection=AssetSelection.assets("user_hf_module_annotations"),
    description="Annotate user VCF with HuggingFace modules (longevitymap, lipidmetabolism, vo2max, etc.)",
    tags={"annotation": "hf_modules", "multi-user": "true"},
    hooks={resource_summary_hook},
)

# Job for generating longevity report (depends on module annotations)
generate_longevity_report_job = define_asset_job(
    name="generate_longevity_report_job",
    selection=AssetSelection.assets("user_longevity_report"),
    description="Generate HTML longevity report from annotated module parquets.",
    tags={"report": "longevity", "multi-user": "true"},
    hooks={resource_summary_hook},
)

# Job for full pipeline: normalize + annotate + report
annotate_and_report_job = define_asset_job(
    name="annotate_and_report_job",
    selection=AssetSelection.assets("quality_filters_config", "user_vcf_normalized", "user_hf_module_annotations", "user_longevity_report"),
    description="Full pipeline: normalize VCF, annotate with HF modules, and generate longevity report.",
    tags={"annotation": "hf_modules", "report": "longevity", "multi-user": "true"},
    hooks={resource_summary_hook},
)

# Job for full pipeline with Ensembl: normalize + HF modules + Ensembl DuckDB + report
annotate_all_job = define_asset_job(
    name="annotate_all_job",
    selection=AssetSelection.assets(
        "quality_filters_config", "user_vcf_normalized",
        "user_hf_module_annotations", "user_annotated_vcf_duckdb",
        "ensembl_duckdb", "ensembl_annotations",
        "user_longevity_report",
    ),
    description="Full pipeline: normalize VCF, annotate with HF modules + Ensembl (DuckDB), generate report.",
    tags={"annotation": "all", "multi-user": "true"},
    hooks={resource_summary_hook},
)

# Job for Ensembl-only annotation: normalize + Ensembl DuckDB (no HF modules, no report)
annotate_ensembl_only_job = define_asset_job(
    name="annotate_ensembl_only_job",
    selection=AssetSelection.assets(
        "quality_filters_config", "user_vcf_normalized",
        "user_annotated_vcf_duckdb",
        "ensembl_duckdb", "ensembl_annotations",
    ),
    description="Ensembl-only pipeline: normalize VCF, annotate with Ensembl variations via DuckDB.",
    tags={"annotation": "ensembl", "multi-user": "true"},
    hooks={resource_summary_hook},
)


def _build_definitions() -> Definitions:
    """Build the combined definitions from core + discovered modules."""
    # 1. Core definitions (Ensembl-based, Polars)
    _core = Definitions(
        assets=[
            ensembl_hf_dataset,
            ensembl_annotations,
            quality_filters_config,
            user_vcf_source,
            user_vcf_normalized,
            user_annotated_vcf,
        ],
        jobs=[annotate_vcf_job, annotate_vcf_duckdb_job, normalize_vcf_job],
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
    
    # 4. Report generation assets (depend on module annotation outputs)
    _reports = Definitions(
        assets=[user_longevity_report],
        jobs=[generate_longevity_report_job, annotate_and_report_job, annotate_all_job, annotate_ensembl_only_job],
    )
    
    # 5. Discover and merge module definitions from data/modules/
    modules_dir = Path("data") / "modules"
    module_defs_list = load_module_definitions(modules_dir)
    
    # 6. Merge everything
    all_defs = [_core, _duckdb, _hf_modules, _reports]
    if module_defs_list:
        all_defs.extend(module_defs_list)
    
    return Definitions.merge(*all_defs)


# Single Definitions object at module scope (required by Dagster)
defs = _build_definitions()

