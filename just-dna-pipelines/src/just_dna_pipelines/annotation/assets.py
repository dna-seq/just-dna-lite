"""
Dagster assets for annotation pipelines.

Assets represent persistent data products that can be materialized,
tracked, and lineage-aware.
"""

from pathlib import Path

from huggingface_hub import snapshot_download
from dagster import (
    asset,
    AssetExecutionContext,
    Output,
    MetadataValue,
    DynamicPartitionsDefinition,
    AssetIn,
    AssetSpec,
    DataVersion,
)

import polars as pl

from just_dna_pipelines.runtime import resource_tracker
from just_dna_pipelines.io import read_vcf_file
from just_dna_pipelines.annotation.chromosomes import rewrite_chromosome_column_strip_chr_prefix
from just_dna_pipelines.annotation.configs import (
    EnsemblAnnotationsConfig,
    AnnotationConfig,
    NormalizeVcfConfig,
)
from just_dna_pipelines.annotation.resources import (
    get_default_ensembl_cache_dir,
    get_user_input_dir,
    get_user_output_dir,
    ensure_vcf_in_user_input_dir,
)
from just_dna_pipelines.annotation.logic import annotate_vcf_with_ensembl


# ============================================================================
# SOURCE ASSETS - HUGGINGFACE REPOS AS REMOTE DATA SOURCES
# ============================================================================

# External source asset representing the HuggingFace dataset.
# This establishes the data lineage: HF Repo → Local Cache → User Analysis
ensembl_hf_dataset = AssetSpec(
    key="ensembl_hf_dataset",
    description="Remote Ensembl variations dataset on HuggingFace Hub (just-dna-seq/ensembl_variations). "
                "This is the external source of truth for Ensembl variation data.",
    metadata={
        "source": "HuggingFace Hub",
        "repo_id": "just-dna-seq/ensembl_variations",
        "type": "external_dataset",
        "url": "https://huggingface.co/datasets/just-dna-seq/ensembl_variations",
    },
)


# ============================================================================
# DYNAMIC PARTITIONS FOR USER VCF FILES
# ============================================================================

# Dynamic partitions allow tracking each user's annotated file as a separate asset instance
# New users/files can be added at runtime without code changes
user_vcf_partitions = DynamicPartitionsDefinition(name="user_vcf_files")


def get_vcf_source_observation_data(partition_key: str) -> tuple[DataVersion, dict]:
    """Helper to get data version and metadata for user VCF source.
    
    Partition key can be:
    - "{user_name}" (backward compatibility)
    - "{user_name}/{sample_name}" (modern multi-sample approach)
    """
    if "/" in partition_key:
        user_name, sample_name = partition_key.split("/", 1)
    else:
        user_name = partition_key
        sample_name = None
        
    user_vcf_dir = get_user_input_dir() / user_name
    
    if not user_vcf_dir.exists():
        return DataVersion("not_found"), {
            "user_name": MetadataValue.text(user_name),
            "sample_name": MetadataValue.text(sample_name or "all"),
            "status": MetadataValue.text("directory_not_found"),
        }
    
    # Find VCF files
    if sample_name:
        # Match specific sample name (e.g. sample1 matches sample1.vcf or sample1.vcf.gz)
        vcf_files = [f for f in user_vcf_dir.glob("*") if f.name.startswith(sample_name) and (f.name.endswith(".vcf") or f.name.endswith(".vcf.gz"))]
    else:
        vcf_files = list(user_vcf_dir.glob("*.vcf")) + list(user_vcf_dir.glob("*.vcf.gz"))
    
    if not vcf_files:
        return DataVersion("no_vcf_files"), {
            "user_name": MetadataValue.text(user_name),
            "sample_name": MetadataValue.text(sample_name or "all"),
            "status": MetadataValue.text("no_vcf_files"),
        }
    
    # Use latest modification time as version for staleness detection
    latest_mtime = max(f.stat().st_mtime for f in vcf_files)
    total_size_mb = sum(f.stat().st_size for f in vcf_files) / (1024 * 1024)
    version = f"mtime_{int(latest_mtime)}"
    
    metadata = {
        "user_name": MetadataValue.text(user_name),
        "vcf_count": MetadataValue.int(len(vcf_files)),
        "vcf_files": MetadataValue.text(", ".join(f.name for f in vcf_files)),
        "total_size_mb": MetadataValue.float(round(total_size_mb, 2)),
        "latest_modified": MetadataValue.float(latest_mtime),
        "status": MetadataValue.text("found"),
    }
    
    if sample_name:
        metadata["sample_name"] = MetadataValue.text(sample_name)
        
    return DataVersion(version), metadata


# ============================================================================
# SOURCE ASSET - USER VCF FILES
# ============================================================================

@asset(
    partitions_def=user_vcf_partitions,
    description="User-uploaded VCF files for annotation. Materializes metadata about available VCF files.",
    io_manager_key="source_metadata_io_manager",  # Lightweight metadata-only IO manager
    metadata={
        "storage": "input",
        "format": "vcf",
        "location": "data/input/users/{user_name}/{sample_name}.vcf",
    },
)
def user_vcf_source(context: AssetExecutionContext) -> Output[dict]:
    """
    Source asset representing user VCF uploads.
    
    Materializes metadata about the user's VCF files, enabling proper
    partition tracking and staleness detection for downstream assets.
    """
    partition_key = context.partition_key
    version, metadata = get_vcf_source_observation_data(partition_key)
    
    # Add data version to metadata for tracking
    metadata["data_version"] = MetadataValue.text(version.value)
    
    return Output(
        value={"partition_key": partition_key, "data_version": version.value},
        metadata=metadata
    )


# ============================================================================
# QUALITY FILTERS CONFIG ASSET
# ============================================================================

@asset(
    description="Quality filter settings from modules.yaml. Re-materialize to pick up config changes. "
                "Downstream assets (user_vcf_normalized) depend on this for staleness tracking.",
    compute_kind="config",
)
def quality_filters_config(context: AssetExecutionContext) -> Output[dict]:
    """
    Lightweight asset that materializes the current quality filter settings.

    Reads modules.yaml at materialization time (not import time) so edits
    to the YAML are picked up on re-materialization. The DataVersion is a
    hash of the filter config — when it changes, Dagster marks downstream
    assets as stale.
    """
    from just_dna_pipelines.module_config import _load_config, QualityFilters

    config = _load_config()
    filters = config.quality_filters
    logger = context.log

    logger.info(f"Quality filters loaded: {filters.model_dump()}")
    logger.info(f"Config hash: {filters.config_hash()}")

    dump = filters.model_dump()
    metadata_dict: dict = {
        "config_hash": MetadataValue.text(filters.config_hash()),
        "is_active": MetadataValue.bool(filters.is_active),
    }
    if filters.pass_filters:
        metadata_dict["pass_filters"] = MetadataValue.text(", ".join(filters.pass_filters))
    if filters.min_depth is not None:
        metadata_dict["min_depth"] = MetadataValue.int(filters.min_depth)
    if filters.min_qual is not None:
        metadata_dict["min_qual"] = MetadataValue.float(filters.min_qual)

    return Output(
        value=dump,
        data_version=DataVersion(filters.config_hash()),
        metadata=metadata_dict,
    )


# ============================================================================
# NORMALIZED VCF ASSET
# ============================================================================

@asset(
    description="Normalized VCF as parquet: chromosomes stripped of 'chr' prefix, "
                "'id' renamed to 'rsid', genotype computed from GT+ref+alt, "
                "quality-filtered per modules.yaml settings.",
    compute_kind="polars",
    partitions_def=user_vcf_partitions,
    io_manager_key="user_asset_io_manager",
    ins={
        "user_vcf_source": AssetIn(),
        "quality_filters_config": AssetIn(),
    },
    metadata={
        "partition_type": "user",
        "output_format": "parquet",
        "storage": "output",
    },
)
def user_vcf_normalized(
    context: AssetExecutionContext,
    user_vcf_source: dict,
    quality_filters_config: dict,
    config: NormalizeVcfConfig,
) -> Output[Path]:
    """
    Read a raw VCF, normalise it, apply quality filters, and persist as parquet.

    Normalization steps:
    1. Strip 'chr' prefix from chromosome column (case-insensitive)
    2. Rename 'id' column to 'rsid'
    3. Compute genotype column from GT + ref + alt
    4. Apply quality filters from modules.yaml (FILTER, min depth, min qual)

    If sex="Female" is set, logs a warning when chrY variants are present
    (informational only — never removes chrY).
    """
    from just_dna_pipelines.module_config import QualityFilters, build_quality_filter_expr

    logger = context.log
    partition_key = context.partition_key

    logger.info(f"Normalizing VCF for partition: {partition_key}")
    logger.info(f"VCF source metadata: {user_vcf_source}")

    if "/" in partition_key:
        user_name, sample_name = partition_key.split("/", 1)
    else:
        user_name = partition_key
        sample_name = config.sample_name

    user_name = config.user_name or user_name
    sample_name = config.sample_name or sample_name

    vcf_path = Path(config.vcf_path)
    vcf_path = ensure_vcf_in_user_input_dir(vcf_path, user_name, logger)

    filters = QualityFilters.model_validate(quality_filters_config)
    logger.info(f"Quality filters: {filters.model_dump()}")

    with resource_tracker("Normalize VCF to Parquet", context=context):
        lf = read_vcf_file(
            vcf_path,
            info_fields=config.info_fields,
            save_parquet=None,
            with_formats=True,
            format_fields=config.format_fields,
        )

        schema = lf.collect_schema()

        if "id" in schema.names() and "rsid" not in schema.names():
            lf = lf.rename({"id": "rsid"})

        if "chrom" in schema.names():
            lf = rewrite_chromosome_column_strip_chr_prefix(lf, chrom_col="chrom")

        # --- Quality filtering ---
        rows_before_filter: int | None = None
        filter_expr = build_quality_filter_expr(filters, lf.collect_schema().names())

        if filter_expr is not None:
            # Materialize row count before filtering (reads parquet metadata only
            # if lf comes from scan_parquet, otherwise a cheap count)
            rows_before_filter = lf.select(pl.len()).collect().item()
            lf = lf.filter(filter_expr)
            logger.info(
                f"Quality filter applied: {rows_before_filter} rows before filter"
            )

        # --- chrY informational warning for female-labeled samples ---
        if config.sex and config.sex.strip().lower() == "female":
            chrom_col = "chrom" if "chrom" in lf.collect_schema().names() else None
            if chrom_col:
                y_count = (
                    lf.filter(pl.col(chrom_col).is_in(["Y", "chrY"]))
                    .select(pl.len())
                    .collect()
                    .item()
                )
                if y_count > 0:
                    logger.warning(
                        f"WARNING: {y_count} chrY variants found in female-labeled "
                        f"sample '{sample_name}'. These are likely sequencing noise "
                        f"but are NOT removed. Quality filters may reduce this count."
                    )

        output_dir = get_user_output_dir() / partition_key
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "user_vcf_normalized.parquet"

        lf.sink_parquet(str(output_path), compression=config.compression)

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    row_count = pl.scan_parquet(str(output_path)).select(pl.len()).collect().item()

    if rows_before_filter is not None:
        rows_removed = rows_before_filter - row_count
        logger.info(
            f"Quality filter result: {row_count} rows after filter "
            f"({rows_removed} removed, {rows_removed / rows_before_filter * 100:.1f}% filtered)"
        )

    metadata_dict: dict = {
        "partition_key": MetadataValue.text(partition_key),
        "output_path": MetadataValue.path(str(output_path)),
        "row_count": MetadataValue.int(row_count),
        "size_mb": MetadataValue.float(round(file_size_mb, 2)),
    }
    if rows_before_filter is not None:
        metadata_dict["rows_before_filter"] = MetadataValue.int(rows_before_filter)
        metadata_dict["rows_after_filter"] = MetadataValue.int(row_count)
        metadata_dict["rows_removed"] = MetadataValue.int(rows_before_filter - row_count)
    metadata_dict["quality_filters_hash"] = MetadataValue.text(filters.config_hash())

    return Output(output_path, metadata=metadata_dict)


# ============================================================================
# REFERENCE DATA ASSETS
# ============================================================================

@asset(
    description="Ensembl variation annotations downloaded from HuggingFace Hub.",
    compute_kind="huggingface",
    io_manager_key="annotation_cache_io_manager",
    deps=[ensembl_hf_dataset],  # Depends on the HF source asset for staleness tracking
    metadata={
        "dataset": "just-dna-seq/ensembl_variations",
        "source": "Ensembl Variation Database",
        "storage": "cache",
    }
)
def ensembl_annotations(context: AssetExecutionContext, config: EnsemblAnnotationsConfig) -> Output[Path]:
    """
    Asset representing the Ensembl variation annotations.
    This is a persistent data product that can be materialized once and reused.
    """
    logger = context.log
    
    # Determine cache directory
    if config.cache_dir is None:
        cache_dir = get_default_ensembl_cache_dir()
    else:
        cache_dir = Path(config.cache_dir)
    
    logger.info(f"Determined cache directory: {cache_dir}")
    
    with resource_tracker("Download Ensembl Reference") as tracker:
        # Check if cache exists and skip download if not forced
        if cache_dir.exists() and not config.force_download:
            parquet_files = list(cache_dir.rglob("*.parquet"))
            if parquet_files:
                logger.info(f"Cache exists, skipping download. Found {len(parquet_files)} parquet files.")
                total_size = sum(p.stat().st_size for p in parquet_files) / (1024 * 1024 * 1024)
                
                return Output(
                    cache_dir,
                    metadata={
                        "cache_path": MetadataValue.path(str(cache_dir.absolute())),
                        "num_files": MetadataValue.int(len(parquet_files)),
                        "total_size_gb": MetadataValue.float(round(total_size, 2)),
                        "status": MetadataValue.text("cached"),
                    }
                )
        
        logger.info(f"Downloading {config.repo_id} from HuggingFace Hub...")
        
        # Get token from config or from HF login (for private repos)
        from huggingface_hub import get_token
        token = config.token or get_token()
        
        downloaded_path = snapshot_download(
            repo_id=config.repo_id,
            repo_type="dataset",
            local_dir=cache_dir,
            local_dir_use_symlinks=False,
            token=token,
            allow_patterns=config.allow_patterns or ["data/**/*.parquet"],
        )
        
        logger.info(f"Download complete: {downloaded_path}")
    
    # Get stats for metadata
    parquet_files = list(cache_dir.rglob("*.parquet"))
    total_size = sum(p.stat().st_size for p in parquet_files) / (1024 * 1024 * 1024)
    
    metadata_dict = {
        "cache_path": MetadataValue.path(str(cache_dir.absolute())),
        "num_files": MetadataValue.int(len(parquet_files)),
        "total_size_gb": MetadataValue.float(round(total_size, 2)),
        "status": MetadataValue.text("downloaded"),
    }
    
    # Add resource metrics if available
    if "report" in tracker:
        report = tracker["report"]
        metadata_dict.update({
            "download_duration_sec": MetadataValue.float(round(report.duration, 2)),
            "download_cpu_percent": MetadataValue.float(round(report.cpu_usage_percent, 1)),
        })
    
    return Output(cache_dir, metadata=metadata_dict)


# ============================================================================
# USER OUTPUT ASSETS
# ============================================================================

@asset(
    description="User-specific annotated VCF variants with Ensembl variation database.",
    compute_kind="polars",
    partitions_def=user_vcf_partitions,
    io_manager_key="user_asset_io_manager",
    ins={
        "ensembl_annotations": AssetIn(input_manager_key="annotation_cache_io_manager"),
        "user_vcf_source": AssetIn(),  # Explicit dependency for partition tracking
    },
    metadata={
        "partition_type": "user",
        "output_format": "parquet",
        "storage": "output",
    },
)
def user_annotated_vcf(
    context: AssetExecutionContext,
    ensembl_annotations: Path,
    user_vcf_source: dict,  # Receives metadata from source asset
    config: AnnotationConfig,
) -> Output[Path]:
    """
    Dynamically partitioned asset for user VCF annotations.
    
    Each partition represents a user's annotated VCF file:
    - Partition key: {user_name}/{sample_name} or {user_name}
    - Full asset tracking and lineage
    - Reports can depend on specific partitions
    """
    logger = context.log
    partition_key = context.partition_key
    
    # Log source asset info for debugging
    logger.info(f"Received VCF source metadata: {user_vcf_source}")
    
    if "/" in partition_key:
        user_name, sample_name = partition_key.split("/", 1)
    else:
        user_name = partition_key
        sample_name = config.sample_name
    
    # Overwrite with config if provided
    user_name = config.user_name or user_name
    sample_name = config.sample_name or sample_name
    
    vcf_path = Path(config.vcf_path)
    
    # Ensure VCF is in the expected user input directory
    vcf_path = ensure_vcf_in_user_input_dir(vcf_path, user_name, logger)
    
    final_output_path, metadata_dict = annotate_vcf_with_ensembl(
        logger=logger,
        vcf_path=vcf_path,
        ensembl_cache=ensembl_annotations,
        config=config,
        user_name=user_name,
        sample_name=sample_name
    )
    
    # Add partition-specific metadata
    metadata_dict["partition_key"] = MetadataValue.text(partition_key)
    
    return Output(final_output_path, metadata=metadata_dict)

