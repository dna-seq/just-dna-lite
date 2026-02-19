"""
DuckDB-based annotation assets for performance comparison.

This module provides alternative annotation assets using DuckDB for joins,
which can be more efficient for large-scale genomic data joins, especially
for interval/range queries.
"""

from pathlib import Path
from typing import Optional

import duckdb
from dagster import (
    asset,
    AssetExecutionContext,
    Output,
    MetadataValue,
    AssetIn,
    AutoMaterializePolicy,
)

from just_dna_pipelines.runtime import resource_tracker
from just_dna_pipelines.annotation.configs import AnnotationConfig, DuckDBConfig
from just_dna_pipelines.annotation.resources import (
    get_default_ensembl_cache_dir,
    get_ensembl_parquet_dir,
    ensure_vcf_in_user_input_dir,
)
from just_dna_pipelines.annotation.assets import user_vcf_partitions


def configure_duckdb_for_memory_efficiency(con, config: Optional[DuckDBConfig] = None, logger=None):
    """
    Apply memory-efficient settings to a DuckDB connection.
    
    Auto-detects system resources (RAM, CPUs) and configures DuckDB accordingly.
    
    Args:
        con: DuckDB connection object
        config: Optional DuckDBConfig with custom settings
        logger: Optional logger for reporting settings
    """
    if config:
        memory_limit = config.get_memory_limit()
        threads = config.get_threads()
        temp_dir = config.temp_directory
        preserve_order = config.preserve_insertion_order
        enable_cache = config.enable_object_cache
    else:
        # Auto-detect system resources
        from just_dna_pipelines.annotation.configs import get_default_duckdb_memory_limit, get_default_duckdb_threads
        memory_limit = get_default_duckdb_memory_limit()
        threads = get_default_duckdb_threads()
        temp_dir = "/tmp/duckdb_temp"
        preserve_order = False
        enable_cache = True
    
    # Apply settings
    con.execute(f"SET memory_limit='{memory_limit}'")
    con.execute(f"SET threads={threads}")
    con.execute(f"SET temp_directory='{temp_dir}'")
    con.execute(f"SET preserve_insertion_order={str(preserve_order).lower()}")
    if enable_cache:
        con.execute("SET enable_object_cache=true")
    
    if logger:
        logger.info(f"DuckDB configured: memory={memory_limit}, threads={threads}, temp={temp_dir}")


def build_duckdb_from_parquet(
    ensembl_cache: Path,
    duckdb_path: Path,
    logger = None,
) -> tuple[Path, dict]:
    """
    Build DuckDB database from Ensembl Parquet files using VIEWs for memory efficiency.
    
    This creates a lightweight DuckDB catalog that references Parquet files directly
    without materializing them into tables. This approach:
    - Uses minimal memory (only metadata, no data copying)
    - Leverages Parquet column statistics for query optimization
    - Allows DuckDB to stream data during joins
    - Keeps database size small (just schema, no data)
    
    Args:
        ensembl_cache: Path to Ensembl Parquet cache directory
        duckdb_path: Path where DuckDB database should be created
        logger: Optional logger for progress messages
        
    Returns:
        Tuple of (duckdb_path, metadata_dict)
    """
    if logger:
        logger.info(f"Creating memory-efficient DuckDB catalog at: {duckdb_path}")
    
    with resource_tracker("Build Ensembl DuckDB") as tracker:
        con = duckdb.connect(str(duckdb_path))
        configure_duckdb_for_memory_efficiency(con, logger=logger)
        
        parquet_dir = get_ensembl_parquet_dir(ensembl_cache)
        parquet_files = list(parquet_dir.glob("*.parquet"))
        
        if logger:
            logger.info(f"Creating VIEW 'ensembl_variations' over {len(parquet_files)} Parquet files in {parquet_dir}")
        
        parquet_pattern = str(parquet_dir / "*.parquet")
        con.execute(f"""
            CREATE OR REPLACE VIEW ensembl_variations AS 
            SELECT * FROM read_parquet('{parquet_pattern}', 
                hive_partitioning=false,
                union_by_name=true
            )
        """)
        
        views_created = ["ensembl_variations"]
        total_files = len(parquet_files)
        
        if logger:
            logger.info(f"VIEW 'ensembl_variations' created (streaming access to {total_files} Parquet files)")
        
        con.close()
    
    # Get final database stats (should be tiny - just metadata)
    db_size_mb = duckdb_path.stat().st_size / (1024 * 1024)
    
    metadata_dict = {
        "db_path": str(duckdb_path.absolute()),
        "db_size_mb": round(db_size_mb, 2),
        "num_views": len(views_created),
        "view_names": ", ".join(views_created),
        "total_parquet_files": total_files,
        "status": "created",
        "storage_type": "views_over_parquet",
        "memory_efficient": True,
    }
    
    # Add resource metrics if available
    if "report" in tracker:
        report = tracker["report"]
        metadata_dict.update({
            "build_duration_sec": round(report.duration, 2),
            "build_cpu_percent": round(report.cpu_usage_percent, 1),
            "peak_memory_mb": round(report.peak_memory_mb, 2),
        })
    
    return duckdb_path, metadata_dict


def ensure_ensembl_duckdb_exists(logger = None) -> Path:
    """
    Ensure the Ensembl DuckDB database exists, creating it if necessary.
    
    This function checks for the DuckDB database and builds it from
    Ensembl Parquet files if it doesn't exist.
    
    Args:
        logger: Optional logger for progress messages
        
    Returns:
        Path to the DuckDB database
        
    Raises:
        FileNotFoundError: If Ensembl Parquet cache doesn't exist
    """
    cache_dir = get_default_ensembl_cache_dir()
    duckdb_path = cache_dir / "ensembl_variations.duckdb"
    
    # Check if DuckDB already exists and is valid
    if duckdb_path.exists():
        con = duckdb.connect(str(duckdb_path), read_only=True)
        tables = con.execute("SHOW TABLES").fetchall()
        con.close()
        
        if tables:
            if logger:
                logger.info(f"Using existing DuckDB database at {duckdb_path} with {len(tables)} objects")
            return duckdb_path
        else:
            # Empty database, need to rebuild
            if logger:
                logger.warning(f"DuckDB database exists but has no tables/views, rebuilding...")
            duckdb_path.unlink()
    
    # Validates that parquet data exists (raises FileNotFoundError if not)
    get_ensembl_parquet_dir(cache_dir)
    
    # Build the DuckDB from Parquet files
    if logger:
        logger.info(f"DuckDB not found, building from Ensembl Parquet files at {cache_dir}...")
    
    build_duckdb_from_parquet(cache_dir, duckdb_path, logger)
    
    return duckdb_path


@asset(
    description="DuckDB database for Ensembl variation annotations. "
                "Provides faster joins and better memory management for large datasets.",
    compute_kind="duckdb",
    io_manager_key="annotation_cache_io_manager",
    ins={
        "ensembl_annotations": AssetIn(input_manager_key="annotation_cache_io_manager"),
    },
    auto_materialize_policy=AutoMaterializePolicy.eager(),
    metadata={
        "dataset": "just-dna-seq/ensembl_variations",
        "storage": "cache",
        "format": "duckdb",
    }
)
def ensembl_duckdb(context: AssetExecutionContext, ensembl_annotations: Path) -> Output[Path]:
    """
    Create a DuckDB database from Ensembl Parquet files.
    
    This asset builds an indexed DuckDB database for faster annotation queries.
    Benefits over direct Parquet scanning:
    - Better join optimization for multi-source annotations
    - Native support for interval/range joins
    - More predictable out-of-core processing
    - Query result caching
    
    Args:
        context: Dagster execution context
        ensembl_annotations: Path to Ensembl Parquet cache directory
        
    Returns:
        Path to the created DuckDB database file
    """
    logger = context.log
    
    # Database will be stored in cache alongside Parquet files
    cache_dir = get_default_ensembl_cache_dir()
    db_path = cache_dir / "ensembl_variations.duckdb"
    
    # Check if database already exists and is valid (cache optimization)
    if db_path.exists():
        logger.info("DuckDB database already exists. Checking views/tables...")
        con = duckdb.connect(str(db_path), read_only=True)
        tables = con.execute("SHOW TABLES").fetchall()
        con.close()
        
        if tables:
            logger.info(f"Found {len(tables)} objects in existing database. Skipping rebuild.")
            db_size_mb = db_path.stat().st_size / (1024 * 1024)
            return Output(
                db_path,
                metadata={
                    "db_path": MetadataValue.path(str(db_path.absolute())),
                    "db_size_mb": MetadataValue.float(round(db_size_mb, 2)),
                    "num_objects": MetadataValue.int(len(tables)),
                    "status": MetadataValue.text("cached"),
                }
            )
        else:
            logger.warning("Database exists but is empty. Rebuilding...")
            db_path.unlink()
    
    # Build DuckDB using shared helper function
    _, raw_metadata = build_duckdb_from_parquet(ensembl_annotations, db_path, logger)
    
    # Convert to Dagster MetadataValue format
    metadata_dict = {
        "db_path": MetadataValue.path(raw_metadata["db_path"]),
        "db_size_mb": MetadataValue.float(raw_metadata["db_size_mb"]),
        "num_views": MetadataValue.int(raw_metadata["num_views"]),
        "view_names": MetadataValue.text(raw_metadata["view_names"]),
        "total_parquet_files": MetadataValue.int(raw_metadata["total_parquet_files"]),
        "storage_type": MetadataValue.text(raw_metadata["storage_type"]),
        "memory_efficient": MetadataValue.bool(raw_metadata["memory_efficient"]),
        "status": MetadataValue.text(raw_metadata["status"]),
    }
    
    # Add resource metrics if available
    if "build_duration_sec" in raw_metadata:
        metadata_dict.update({
            "build_duration_sec": MetadataValue.float(raw_metadata["build_duration_sec"]),
            "build_cpu_percent": MetadataValue.float(raw_metadata["build_cpu_percent"]),
            "peak_memory_mb": MetadataValue.float(raw_metadata["peak_memory_mb"]),
        })
    
    return Output(db_path, metadata=metadata_dict)


from just_dna_pipelines.annotation.logic import annotate_vcf_with_duckdb


@asset(
    description="User-specific annotated VCF variants using DuckDB for annotation joins. "
                "Uses the normalized VCF (quality-filtered, chr-stripped) as input.",
    compute_kind="duckdb",
    partitions_def=user_vcf_partitions,
    io_manager_key="user_asset_io_manager",
    ins={
        "ensembl_duckdb": AssetIn(input_manager_key="annotation_cache_io_manager"),
        "user_vcf_source": AssetIn(),
        "user_vcf_normalized": AssetIn(),
    },
    metadata={
        "partition_type": "user",
        "output_format": "parquet",
        "storage": "output",
        "engine": "duckdb",
    },
)
def user_annotated_vcf_duckdb(
    context: AssetExecutionContext,
    ensembl_duckdb: Path,
    user_vcf_source: dict,
    user_vcf_normalized: Path,
    config: AnnotationConfig,
) -> Output[Path]:
    """
    DuckDB-based user VCF annotation asset.
    
    Reads from the normalized parquet (chr-stripped, quality-filtered)
    produced by user_vcf_normalized, and joins with Ensembl reference
    data via DuckDB streaming engine.
    """
    logger = context.log
    partition_key = context.partition_key
    
    logger.info(f"DuckDB annotation for partition: {partition_key}")
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
    
    final_output_path, metadata_dict = annotate_vcf_with_duckdb(
        logger=logger,
        vcf_path=vcf_path,
        duckdb_path=ensembl_duckdb,
        config=config,
        user_name=user_name,
        sample_name=sample_name,
        normalized_parquet=user_vcf_normalized,
    )
    
    metadata_dict["partition_key"] = MetadataValue.text(partition_key)
    
    return Output(final_output_path, metadata=metadata_dict)

