"""
Dagster ops for annotation pipelines.

Ops are the building blocks for jobs. They perform specific operations
and can be composed into larger workflows.
"""

from pathlib import Path

from dagster import op, Output, AssetMaterialization, AssetObservation

from just_dna_pipelines.annotation.configs import AnnotationConfig
from just_dna_pipelines.annotation.resources import (
    ensure_ensembl_cache_exists,
    ensure_vcf_in_user_input_dir,
)
from just_dna_pipelines.annotation.duckdb_assets import ensure_ensembl_duckdb_exists
from just_dna_pipelines.annotation.assets import user_vcf_partitions, get_vcf_source_observation_data
from just_dna_pipelines.annotation.logic import annotate_vcf_with_ensembl, annotate_vcf_with_duckdb


@op(
    description="Annotate a user's VCF file with Ensembl annotations.",
)
def annotate_user_vcf_op(
    context,
    config: AnnotationConfig,
) -> Output[Path]:
    """
    Op for annotating a single user's VCF.
    
    If the VCF is not in the expected user input directory (data/input/users/{user_name}/),
    it will be copied there first. This ensures:
    - Consistent file organization
    - Proper lineage tracking via user_vcf_source observable asset
    - Staleness detection when VCFs are updated
    """
    logger = context.log
    
    # Ensure Ensembl cache exists (will raise informative error if not)
    ensembl_cache = ensure_ensembl_cache_exists(logger)
    
    vcf_path = Path(config.vcf_path)
    user_name = config.user_name or vcf_path.parent.name
    sample_name = config.sample_name or vcf_path.stem
    partition_key = f"{user_name}/{sample_name}"
    
    # Ensure VCF is in the expected user input directory
    vcf_path = ensure_vcf_in_user_input_dir(vcf_path, user_name, logger)
    
    final_output_path, metadata_dict = annotate_vcf_with_ensembl(
        logger=logger,
        vcf_path=vcf_path,
        ensembl_cache=ensembl_cache,
        config=config,
        user_name=user_name,
        sample_name=sample_name
    )
    
    # ------------------------------------------------------------------------
    # LINK TO ASSET LINEAGE
    # ------------------------------------------------------------------------
    # By logging an AssetMaterialization event, this ad-hoc job run will 
    # show up in the Global Asset Lineage for 'user_annotated_vcf'.
    
    # Ensure the dynamic partition exists for this user/sample
    if context.instance.has_dynamic_partition(user_vcf_partitions.name, partition_key):
        logger.info(f"Partition '{partition_key}' already exists.")
    else:
        logger.info(f"Adding new dynamic partition: {partition_key}")
        context.instance.add_dynamic_partitions(user_vcf_partitions.name, [partition_key])
    
    context.log_event(
        AssetMaterialization(
            asset_key="user_annotated_vcf",
            partition=partition_key,
            metadata=metadata_dict
        )
    )
    
    # Also log an observation for the source VCF to show it exists in lineage
    version, source_metadata = get_vcf_source_observation_data(partition_key)
    context.log_event(
        AssetObservation(
            asset_key="user_vcf_source",
            partition=partition_key,
            tags={"dagster/data_version": version.value},
            metadata=source_metadata
        )
    )
    
    return Output(final_output_path, metadata=metadata_dict)


@op(
    description="Annotate a user's VCF file using DuckDB for faster joins.",
)
def annotate_user_vcf_duckdb_op(
    context,
    config: AnnotationConfig,
) -> Output[Path]:
    """
    Op for annotating a single user's VCF using DuckDB.
    
    This matches the pattern of annotate_user_vcf_op but uses DuckDB
    for better performance on large datasets.
    
    The DuckDB database will be automatically created from Ensembl Parquet
    files if it doesn't exist.
    """
    logger = context.log
    
    # Ensure DuckDB exists - will auto-create from Parquet if needed
    duckdb_path = ensure_ensembl_duckdb_exists(logger)
    
    logger.info(f"Using DuckDB database at: {duckdb_path}")
    
    vcf_path = Path(config.vcf_path)
    user_name = config.user_name or vcf_path.parent.name
    sample_name = config.sample_name or vcf_path.stem
    partition_key = f"{user_name}/{sample_name}"
    
    # Ensure VCF is in the expected user input directory
    vcf_path = ensure_vcf_in_user_input_dir(vcf_path, user_name, logger)
    
    final_output_path, metadata_dict = annotate_vcf_with_duckdb(
        logger=logger,
        vcf_path=vcf_path,
        duckdb_path=duckdb_path,
        config=config,
        user_name=user_name,
        sample_name=sample_name
    )
    
    # ------------------------------------------------------------------------
    # LINK TO ASSET LINEAGE
    # ------------------------------------------------------------------------
    
    # Ensure the dynamic partition exists
    if context.instance.has_dynamic_partition(user_vcf_partitions.name, partition_key):
        logger.info(f"Partition '{partition_key}' already exists.")
    else:
        logger.info(f"Adding new dynamic partition: {partition_key}")
        context.instance.add_dynamic_partitions(user_vcf_partitions.name, [partition_key])
    
    context.log_event(
        AssetMaterialization(
            asset_key="user_annotated_vcf_duckdb",
            partition=partition_key,
            metadata=metadata_dict
        )
    )
    
    return Output(final_output_path, metadata=metadata_dict)

