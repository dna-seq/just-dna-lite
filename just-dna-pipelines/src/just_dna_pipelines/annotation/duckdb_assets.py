"""
DuckDB-based annotation assets for performance comparison.

This module provides alternative annotation assets using DuckDB for joins,
which can be more efficient for large-scale genomic data joins, especially
for interval/range queries.
"""

from pathlib import Path
from typing import Optional

import duckdb
import polars as pl
from dagster import (
    asset,
    AssetExecutionContext,
    Output,
    MetadataValue,
    AssetIn,
    AutoMaterializePolicy,
)

from just_dna_pipelines.runtime import resource_tracker
from just_dna_pipelines.io import read_vcf_file
from just_dna_pipelines.annotation.configs import AnnotationConfig, DuckDBConfig
from just_dna_pipelines.annotation.resources import (
    get_default_ensembl_cache_dir,
    get_user_output_dir,
    ensure_vcf_in_user_input_dir,
)
from just_dna_pipelines.annotation.chromosomes import (
    get_input_chrom_style_and_values,
    rewrite_chromosome_column_strip_chr_prefix,
    rewrite_chromosome_column_to_chr_prefixed,
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
        # Create new database with memory-efficient settings
        con = duckdb.connect(str(duckdb_path))
        
        # Configure DuckDB for memory efficiency (auto-detect system resources)
        configure_duckdb_for_memory_efficiency(con, logger=logger)
        
        # Find variant directories (e.g., SNV, INDEL)
        variant_dirs = [d for d in ensembl_cache.iterdir() if d.is_dir() and d.name in ["SNV", "INDEL"]]
        if not variant_dirs:
            # Try data subdirectory
            data_dir = ensembl_cache / "data"
            if data_dir.exists():
                variant_dirs = [d for d in data_dir.iterdir() if d.is_dir() and d.name in ["SNV", "INDEL"]]
        
        if not variant_dirs:
            con.close()
            raise FileNotFoundError(f"No variant directories (SNV/INDEL) found in {ensembl_cache}")
        
        if logger:
            logger.info(f"Found variant types: {[d.name for d in variant_dirs]}")
        
        views_created = []
        total_files = 0
        
        for variant_dir in variant_dirs:
            variant_type = variant_dir.name.lower()
            view_name = f"ensembl_{variant_type}"
            
            # Find all Parquet files for this variant type
            parquet_files = list(variant_dir.rglob("*.parquet"))
            
            if not parquet_files:
                if logger:
                    logger.warning(f"No Parquet files found in {variant_dir}")
                continue
            
            if logger:
                logger.info(f"Creating VIEW '{view_name}' referencing {len(parquet_files)} Parquet files...")
            
            # Use glob pattern - DuckDB will scan Parquet metadata only
            parquet_pattern = str(variant_dir / "**/*.parquet")
            
            # Create VIEW (not TABLE) - this is just metadata, no data copying!
            # DuckDB will use Parquet column statistics (min/max per row group) for filtering
            con.execute(f"""
                CREATE OR REPLACE VIEW {view_name} AS 
                SELECT * FROM read_parquet('{parquet_pattern}', 
                    hive_partitioning=false,
                    union_by_name=true
                )
            """)
            
            if logger:
                logger.info(f"VIEW '{view_name}' created (streaming access to Parquet files)")
            
            views_created.append(view_name)
            total_files += len(parquet_files)
        
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
    
    # Check if Ensembl Parquet cache exists
    if not cache_dir.exists():
        raise FileNotFoundError(
            f"Ensembl cache not found at {cache_dir}. "
            "Please materialize the ensembl_annotations asset first via Dagster UI."
        )
    
    # Check for variant directories
    variant_dirs = [d for d in cache_dir.iterdir() if d.is_dir() and d.name in ["SNV", "INDEL"]]
    if not variant_dirs:
        data_dir = cache_dir / "data"
        if data_dir.exists():
            variant_dirs = [d for d in data_dir.iterdir() if d.is_dir() and d.name in ["SNV", "INDEL"]]
    
    if not variant_dirs:
        raise FileNotFoundError(
            f"No variant directories found in Ensembl cache at {cache_dir}. "
            "Please materialize the ensembl_annotations asset first via Dagster UI."
        )
    
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
                "Alternative to Polars-based annotation for performance comparison.",
    compute_kind="duckdb",
    partitions_def=user_vcf_partitions,
    io_manager_key="user_asset_io_manager",
    ins={
        "ensembl_duckdb": AssetIn(input_manager_key="annotation_cache_io_manager"),
        "user_vcf_source": AssetIn(),
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
    config: AnnotationConfig,
) -> Output[Path]:
    """
    DuckDB-based user VCF annotation asset.
    
    This asset uses DuckDB for the annotation join instead of Polars.
    Compare performance and memory usage with the standard `user_annotated_vcf` asset.
    
    Advantages:
    - Better join optimization for large datasets
    - More predictable memory usage
    - Native support for complex joins (future: interval joins)
    - Easier to extend with multiple annotation sources
    """
    logger = context.log
    partition_key = context.partition_key
    
    logger.info(f"DuckDB annotation for partition: {partition_key}")
    logger.info(f"VCF source metadata: {user_vcf_source}")
    
    # Parse partition key
    if "/" in partition_key:
        user_name, sample_name = partition_key.split("/", 1)
    else:
        user_name = partition_key
        sample_name = config.sample_name
    
    # Overwrite with config if provided
    user_name = config.user_name or user_name
    sample_name = config.sample_name or sample_name
    
    vcf_path = Path(config.vcf_path)
    
    # Ensure VCF is in expected directory
    vcf_path = ensure_vcf_in_user_input_dir(vcf_path, user_name, logger)
    
    # Run DuckDB annotation
    final_output_path, metadata_dict = annotate_vcf_with_duckdb(
        logger=logger,
        vcf_path=vcf_path,
        duckdb_path=ensembl_duckdb,
        config=config,
        user_name=user_name,
        sample_name=sample_name
    )
    
    # Add partition metadata
    metadata_dict["partition_key"] = MetadataValue.text(partition_key)
    
    return Output(final_output_path, metadata=metadata_dict)

