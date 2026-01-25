"""
Dagster assets for HuggingFace module annotation.

These assets annotate user VCF files with modules from the
just-dna-seq/annotators HuggingFace repository.

The modules are self-contained - they include all annotation data
and don't require Ensembl joins.

Modules are discovered dynamically by scanning the HF repository folders.
Each module gets its own asset group for clear lineage visualization.
"""

from pathlib import Path

from dagster import (
    asset,
    AssetExecutionContext,
    Output,
    MetadataValue,
    AssetIn,
    AssetSpec,
)

from just_dna_pipelines.annotation.assets import user_vcf_partitions
from just_dna_pipelines.annotation.configs import HfModuleAnnotationConfig
from just_dna_pipelines.annotation.hf_modules import (
    HF_DEFAULT_REPOS,
    MODULE_TABLES,
    DISCOVERED_MODULES,
    MODULE_INFOS,
    AnnotationManifest,
    get_module_table_url,
)
from just_dna_pipelines.annotation.hf_logic import annotate_vcf_with_all_modules
from just_dna_pipelines.annotation.resources import ensure_vcf_in_user_input_dir


# ============================================================================
# SOURCE ASSETS - HUGGINGFACE ANNOTATOR MODULES
# ============================================================================

# External source asset representing the HuggingFace annotators repositories
hf_annotators_dataset = AssetSpec(
    key="hf_annotators_dataset",
    group_name="hf_sources",
    description="Remote annotator modules on HuggingFace Hub. "
                "Modules are discovered dynamically from one or more repositories.",
    metadata={
        "source": "HuggingFace Hub",
        "repos": ", ".join(HF_DEFAULT_REPOS),
        "type": "external_dataset",
        "modules": ", ".join(DISCOVERED_MODULES),
    },
)


# ============================================================================
# USER MODULE ANNOTATION ASSET
# ============================================================================

@asset(
    description="User VCF annotated with HuggingFace modules. "
                "Produces one parquet file per selected module containing genotype-specific annotations.",
    compute_kind="polars",
    group_name="user_annotations",
    partitions_def=user_vcf_partitions,
    io_manager_key="user_asset_io_manager",
    ins={
        "user_vcf_source": AssetIn(),  # Partition dependency for lineage
    },
    deps=[hf_annotators_dataset],  # Lineage to HF source
    metadata={
        "partition_type": "user",
        "output_format": "parquet",
        "storage": "output",
        "annotation_source": "huggingface_modules",
    },
)
def user_hf_module_annotations(
    context: AssetExecutionContext,
    user_vcf_source: dict,
    config: HfModuleAnnotationConfig,
) -> Output[Path]:
    """
    Annotate user VCF with selected HuggingFace modules.
    
    This asset:
    1. Reads the user's VCF with FORMAT fields (including genotype)
    2. For each selected module, joins with the weights table on rsid + genotype
    3. Outputs one parquet file per module
    4. Returns a manifest describing all outputs
    
    The genotype column is computed from GT field as List[String] sorted alphabetically,
    matching the format in the HF modules.
    
    Output structure:
    data/output/users/{user}/{sample}/modules/
    ├── longevitymap_weights.parquet
    ├── lipidmetabolism_weights.parquet
    ├── ...
    └── manifest.json
    """
    logger = context.log
    partition_key = context.partition_key
    
    logger.info(f"HF Module annotation for partition: {partition_key}")
    logger.info(f"VCF source metadata: {user_vcf_source}")
    
    # Parse partition key
    if "/" in partition_key:
        user_name, sample_name = partition_key.split("/", 1)
    else:
        user_name = partition_key
        sample_name = config.sample_name
    
    # Override with config if provided
    user_name = config.user_name or user_name
    sample_name = config.sample_name or sample_name
    
    # Resolve VCF path (supports local path or Zenodo URL)
    resolved_vcf_path = config.resolve_vcf_path(logger=logger)
    vcf_path = Path(resolved_vcf_path)
    
    # Log source type
    if config.zenodo_url:
        logger.info(f"VCF source: Zenodo ({config.zenodo_url})")
    else:
        logger.info(f"VCF source: Local ({vcf_path})")
    
    # Ensure VCF is in expected directory
    vcf_path = ensure_vcf_in_user_input_dir(vcf_path, user_name, logger)
    
    # Run annotation with all selected modules
    manifest, metadata_dict = annotate_vcf_with_all_modules(
        logger=logger,
        vcf_path=vcf_path,
        config=config,
        user_name=user_name,
        sample_name=sample_name,
    )
    
    # Add partition metadata
    metadata_dict["partition_key"] = MetadataValue.text(partition_key)
    
    # Add source type metadata
    if config.zenodo_url:
        metadata_dict["vcf_source_type"] = MetadataValue.text("zenodo")
        metadata_dict["vcf_source_url"] = MetadataValue.url(config.zenodo_url)
    else:
        metadata_dict["vcf_source_type"] = MetadataValue.text("local")
    
    # Return the manifest path (directory containing all module outputs)
    output_dir = Path(manifest.modules[0].weights_path).parent if manifest.modules else Path(config.output_dir or "")
    
    return Output(output_dir, metadata=metadata_dict)


# ============================================================================
# DYNAMICALLY GENERATED MODULE SOURCE ASSETS
# ============================================================================

def create_module_source_assets() -> list[AssetSpec]:
    """
    Create source asset specs for each discovered HF module.
    
    Modules are discovered by scanning the HuggingFace repository folders.
    Each module gets its own asset group, with prefixed asset names for clarity.
    """
    assets = []
    for module_name, info in MODULE_INFOS.items():
        # Core tables
        for table in MODULE_TABLES:
            try:
                url = get_module_table_url(module_name, table)
                assets.append(
                    AssetSpec(
                        key=f"{module_name}_{table}",
                        group_name=module_name,
                        description=f"{module_name} {table} from HuggingFace (repo: {info.repo_id})",
                        metadata={
                            "module": module_name,
                            "repo": info.repo_id,
                            "table": table,
                            "url": url,
                        },
                        deps=[hf_annotators_dataset],
                    )
                )
            except ValueError:
                # Table not available for this module
                continue
                
        # Logo and metadata as additional metadata on the weights asset if they exist
        # (Alternatively, we could create separate assets for them, but usually they are small)
    return assets


# Pre-create the module source assets for inclusion in Definitions
hf_module_source_assets = create_module_source_assets()
