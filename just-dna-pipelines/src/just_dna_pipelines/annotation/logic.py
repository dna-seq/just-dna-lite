"""
Shared business logic for VCF annotation.

This module contains the core annotation logic that is used by
Dagster assets and ops.
"""

from pathlib import Path
from typing import Optional

import duckdb
import polars as pl
from dagster import MetadataValue

from just_dna_pipelines.runtime import resource_tracker
from just_dna_pipelines.io import read_vcf_file
from just_dna_pipelines.annotation.chromosomes import (
    rewrite_chromosome_column_strip_chr_prefix,
    rewrite_chromosome_column_to_chr_prefixed,
    get_input_chrom_style_and_values,
)
from just_dna_pipelines.annotation.configs import AnnotationConfig
from just_dna_pipelines.annotation.resources import get_user_output_dir, get_default_ensembl_cache_dir


def annotate_vcf_with_ensembl(
    logger,
    vcf_path: Path,
    ensembl_cache: Path,
    config: AnnotationConfig,
    user_name: str,
    sample_name: Optional[str] = None,
) -> tuple[Path, dict]:
    """
    Core VCF annotation logic used by Dagster assets and ops.
    
    Args:
        logger: Logger instance (can be Dagster context.log or Python logging)
        vcf_path: Path to the input VCF file
        ensembl_cache: Path to the Ensembl reference cache
        config: AnnotationConfig with annotation parameters
        user_name: User identifier for output organization
        sample_name: Optional sample name for output organization
        
    Returns:
        Tuple of (output_path, metadata_dict)
    """
    # Organize output by user and optionally sample
    if config.output_path:
        final_output_path = Path(config.output_path)
    else:
        # If we have a sample name, create a subfolder for it
        if sample_name:
            user_dir = get_user_output_dir() / user_name / sample_name
        else:
            user_dir = get_user_output_dir() / user_name
            
        user_dir.mkdir(parents=True, exist_ok=True)
        final_output_path = user_dir / f"{vcf_path.stem}_annotated.parquet"
        logger.info(f"Output for user '{user_name}' (sample: {sample_name or 'default'}): {final_output_path}")
    
    with resource_tracker("Annotate VCF with Ensembl") as tracker:
        # Load VCF
        logger.info(f"Loading VCF from {vcf_path} (with_formats={config.with_formats})...")
        input_dataframe = read_vcf_file(
            vcf_path, 
            info_fields=config.info_fields,
            with_formats=config.with_formats,
            format_fields=config.format_fields
        )
        
        # Default join columns
        join_columns = config.join_columns or ["chrom", "start", "ref", "alt"]
        chrom_col = "chrom" if "chrom" in join_columns else "chrom"

        # Determine variant directory
        variant_dir = ensembl_cache / config.variant_type
        if not variant_dir.exists():
            variant_dir = ensembl_cache / "data" / config.variant_type

        if not variant_dir.exists():
            raise FileNotFoundError(f"Variant directory not found: {variant_dir}")

        # Get input chromosome style and values
        input_style, input_chrom_values = get_input_chrom_style_and_values(input_dataframe, chrom_col)
        input_has_chr = input_style == "chr_prefixed"

        # Determine files to scan based on input chromosomes
        input_chroms_normalized = {c.lower().replace("chr", "") for c in input_chrom_values}
        
        relevant_parquet_files = []
        for p in variant_dir.rglob("*.parquet"):
            stem_lower = p.stem.lower().replace("chr", "")
            if any(f"-{c}" in stem_lower for c in input_chroms_normalized):
                relevant_parquet_files.append(p)
        
        if not relevant_parquet_files:
            logger.warning(f"No relevant parquet files found for chromosomes: {input_chrom_values}")
            final_output_path.parent.mkdir(parents=True, exist_ok=True)
            input_dataframe.sink_parquet(final_output_path, compression=config.compression, engine="streaming")
            
            file_size_mb = final_output_path.stat().st_size / (1024 * 1024)
            num_columns = len(pl.scan_parquet(final_output_path).collect_schema())
            
            return final_output_path, {
                "output_file": MetadataValue.path(str(final_output_path.absolute())),
                "file_size_mb": MetadataValue.float(round(file_size_mb, 2)),
                "num_columns": MetadataValue.int(num_columns),
                "compression": MetadataValue.text(config.compression),
            }

        logger.info(f"Scanning {len(relevant_parquet_files)} relevant Ensembl files...")
        ensembl_lf = pl.scan_parquet(relevant_parquet_files)

        # Detect chromosome naming style from reference
        reference_sample = ensembl_lf.select(pl.col(chrom_col).head(10)).collect().get_column(chrom_col).to_list()
        reference_has_chr = any(c.lower().startswith("chr") for c in reference_sample if c)

        # Determine if we need to rewrite input chromosomes
        input_lf = input_dataframe
        if reference_has_chr and not input_has_chr:
            input_lf = rewrite_chromosome_column_to_chr_prefixed(input_lf, chrom_col=chrom_col)
        elif (not reference_has_chr) and input_has_chr:
            input_lf = rewrite_chromosome_column_strip_chr_prefix(input_lf, chrom_col=chrom_col)

        # Rename Ensembl 'id' column to 'rsid'
        if "id" in ensembl_lf.collect_schema().names():
            ensembl_lf = ensembl_lf.rename({"id": "rsid"})

        # Left join
        annotated_lf = input_lf.join(
            ensembl_lf,
            on=join_columns,
            how="left",
            suffix="_ensembl"
        )

        # Reorder columns
        columns = annotated_lf.collect_schema().names()
        if "rsid" in columns and "id" in columns:
            id_idx = columns.index("id")
            columns.remove("rsid")
            columns.insert(id_idx, "rsid")
            annotated_lf = annotated_lf.select(columns)

        final_output_path.parent.mkdir(parents=True, exist_ok=True)
        annotated_lf.sink_parquet(
            final_output_path, 
            compression=config.compression, 
            engine="streaming"
        )
    
    # Get file stats and resource metrics for metadata
    file_size_mb = final_output_path.stat().st_size / (1024 * 1024)
    num_columns = len(pl.scan_parquet(final_output_path).collect_schema())
    
    metadata_dict = {
        "user_name": MetadataValue.text(user_name),
        "sample_name": MetadataValue.text(sample_name or "default"),
        "sample_description": MetadataValue.text(config.sample_description or "No description provided"),
        "sequencing_type": MetadataValue.text(config.sequencing_type),
        "species": MetadataValue.text(config.species),
        "reference_genome": MetadataValue.text(config.reference_genome),
        "source_vcf": MetadataValue.path(str(vcf_path.absolute())),
        "output_file": MetadataValue.path(str(final_output_path.absolute())),
        "file_size_mb": MetadataValue.float(round(file_size_mb, 2)),
        "num_columns": MetadataValue.int(num_columns),
        "compression": MetadataValue.text(config.compression),
    }
    
    # Add resource metrics if available
    if "report" in tracker:
        report = tracker["report"]
        metadata_dict.update({
            "duration_sec": MetadataValue.float(round(report.duration, 2)),
            "cpu_percent": MetadataValue.float(round(report.cpu_usage_percent, 1)),
            "peak_memory_mb": MetadataValue.float(round(report.peak_memory_mb, 2)),
            "memory_delta_mb": MetadataValue.float(round(report.memory_delta_mb, 2)),
        })
    
    return final_output_path, metadata_dict


def annotate_vcf_with_duckdb(
    logger,
    vcf_path: Path,
    duckdb_path: Path,
    config: AnnotationConfig,
    user_name: str,
    sample_name: Optional[str] = None,
) -> tuple[Path, dict]:
    """
    Annotate VCF using DuckDB with memory-efficient streaming.
    
    This provides maximum memory efficiency by:
    - Reading VCF directly from Parquet/file into DuckDB
    - Using DuckDB's streaming join engine
    - Writing results directly to Parquet without collecting
    - Leveraging Parquet column statistics for filtering
    
    Args:
        logger: Logger instance
        vcf_path: Path to the input VCF file
        duckdb_path: Path to the DuckDB database
        config: AnnotationConfig with annotation parameters
        user_name: User identifier
        sample_name: Optional sample name
        
    Returns:
        Tuple of (output_path, metadata_dict)
    """
    # Organize output
    if config.output_path:
        final_output_path = Path(config.output_path)
    else:
        if sample_name:
            user_dir = get_user_output_dir() / user_name / sample_name
        else:
            user_dir = get_user_output_dir() / user_name
            
        user_dir.mkdir(parents=True, exist_ok=True)
        final_output_path = user_dir / f"{vcf_path.stem}_annotated_duckdb.parquet"
        logger.info(f"DuckDB output for user '{user_name}': {final_output_path}")
    
    with resource_tracker("Annotate VCF with DuckDB") as tracker:
        # Load VCF as LazyFrame (not collected!)
        logger.info(f"Loading VCF from {vcf_path} (with_formats={config.with_formats})...")
        input_lf = read_vcf_file(
            vcf_path, 
            info_fields=config.info_fields,
            with_formats=config.with_formats,
            format_fields=config.format_fields
        )
        
        # Join columns
        join_columns = config.join_columns or ["chrom", "start", "ref", "alt"]
        chrom_col = "chrom"
        
        # Get input chromosome style (minimal scan)
        input_style, input_chrom_values = get_input_chrom_style_and_values(
            input_lf, chrom_col
        )
        input_has_chr = input_style == "chr_prefixed"
        
        # Connect to DuckDB with memory-efficient settings
        logger.info(f"Connecting to DuckDB: {duckdb_path}")
        con = duckdb.connect(str(duckdb_path), read_only=True)
        
        # Configure for memory efficiency (auto-detect if not provided)
        from just_dna_pipelines.annotation.duckdb_assets import configure_duckdb_for_memory_efficiency
        configure_duckdb_for_memory_efficiency(con, config.duckdb_config, logger)
        
        # Determine which view/table to use
        view_name = f"ensembl_{config.variant_type.lower()}"
        
        # Check if view/table exists
        available = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
        
        if view_name not in available:
            logger.warning(f"View/table '{view_name}' not found. Available: {available}")
            con.close()
            # Fall back to returning input
            final_output_path.parent.mkdir(parents=True, exist_ok=True)
            input_lf.sink_parquet(final_output_path, compression=config.compression)
            
            file_size_mb = final_output_path.stat().st_size / (1024 * 1024)
            num_columns = len(pl.scan_parquet(final_output_path).collect_schema())
            
            return final_output_path, {
                "output_file": MetadataValue.path(str(final_output_path.absolute())),
                "file_size_mb": MetadataValue.float(round(file_size_mb, 2)),
                "num_columns": MetadataValue.int(num_columns),
                "warning": MetadataValue.text(f"View/table {view_name} not found"),
            }
        
        # Sample reference data to check chromosome style (only 10 rows)
        reference_sample = con.execute(f"SELECT {chrom_col} FROM {view_name} LIMIT 10").fetchall()
        reference_has_chr = any(
            str(c[0]).lower().startswith("chr") 
            for c in reference_sample
            if c and c[0] is not None
        )
        
        # Adjust input chromosome naming if needed
        if reference_has_chr and not input_has_chr:
            input_lf = rewrite_chromosome_column_to_chr_prefixed(
                input_lf, chrom_col=chrom_col
            )
        elif (not reference_has_chr) and input_has_chr:
            input_lf = rewrite_chromosome_column_strip_chr_prefix(
                input_lf, chrom_col=chrom_col
            )
        
        # Write VCF to temporary Parquet for DuckDB to read efficiently
        # This is unavoidable but at least it's streaming
        import tempfile
        temp_vcf_parquet = Path(tempfile.mktemp(suffix=".parquet"))
        
        logger.info("Writing VCF to temporary Parquet for DuckDB...")
        input_lf.sink_parquet(temp_vcf_parquet, compression="snappy")
        
        # Build join query - DuckDB will stream this!
        join_conditions = " AND ".join([f"v.{col} = e.{col}" for col in join_columns])
        
        logger.info(f"Executing streaming DuckDB join on {view_name}...")
        
        # Write directly to output - NO COLLECTION!
        # DuckDB will stream the join results directly to Parquet
        query = f"""
            COPY (
                SELECT 
                    v.*,
                    e.* EXCLUDE ({', '.join(join_columns)})
                FROM read_parquet('{temp_vcf_parquet}') v
                LEFT JOIN {view_name} e
                    ON {join_conditions}
            ) TO '{final_output_path}' 
            (FORMAT PARQUET, COMPRESSION '{config.compression.upper()}')
        """
        
        con.execute(query)
        con.close()
        
        # Clean up temp file
        temp_vcf_parquet.unlink()
        
        logger.info(f"Annotation complete, written to {final_output_path}")
    
    # Collect metadata (lazy scan, no collection)
    file_size_mb = final_output_path.stat().st_size / (1024 * 1024)
    output_schema = pl.scan_parquet(final_output_path).collect_schema()
    num_columns = len(output_schema)
    
    # Get row count efficiently (from Parquet metadata)
    num_rows = pl.scan_parquet(final_output_path).select(pl.len()).collect().item()
    
    metadata_dict = {
        "user_name": MetadataValue.text(user_name),
        "sample_name": MetadataValue.text(sample_name or "default"),
        "sample_description": MetadataValue.text(config.sample_description or "No description"),
        "sequencing_type": MetadataValue.text(config.sequencing_type),
        "species": MetadataValue.text(config.species),
        "reference_genome": MetadataValue.text(config.reference_genome),
        "source_vcf": MetadataValue.path(str(vcf_path.absolute())),
        "output_file": MetadataValue.path(str(final_output_path.absolute())),
        "file_size_mb": MetadataValue.float(round(file_size_mb, 2)),
        "num_rows": MetadataValue.int(num_rows),
        "num_columns": MetadataValue.int(num_columns),
        "compression": MetadataValue.text(config.compression),
        "engine": MetadataValue.text("duckdb_streaming"),
    }
    
    # Add resource metrics if available
    if "report" in tracker:
        report = tracker["report"]
        metadata_dict.update({
            "duration_sec": MetadataValue.float(round(report.duration, 2)),
            "cpu_percent": MetadataValue.float(round(report.cpu_usage_percent, 1)),
            "peak_memory_mb": MetadataValue.float(round(report.peak_memory_mb, 2)),
            "memory_delta_mb": MetadataValue.float(round(report.memory_delta_mb, 2)),
        })
    
    return final_output_path, metadata_dict

