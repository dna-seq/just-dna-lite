"""
Logic for annotating VCF files with HuggingFace modules.

This module contains the core annotation logic using lazy Polars
for memory-efficient processing. HF modules are self-contained
and don't require Ensembl joins.
"""

from pathlib import Path
from typing import Optional

import polars as pl
from dagster import MetadataValue
from eliot import start_action

from just_dna_pipelines.io import read_vcf_file
from just_dna_pipelines.runtime import resource_tracker
from just_dna_pipelines.annotation.hf_modules import (
    AnnotatorModule,
    ModuleTable,
    ModuleOutputMapping,
    AnnotationManifest,
    scan_module_table,
)
from just_dna_pipelines.annotation.configs import HfModuleAnnotationConfig
from just_dna_pipelines.annotation.resources import get_user_output_dir


def prepare_vcf_for_module_annotation(
    vcf_path: Path,
    info_fields: Optional[list[str]] = None,
    format_fields: Optional[list[str]] = None,
) -> pl.LazyFrame:
    """
    Read and prepare VCF for module annotation.
    
    Ensures VCF has:
    - rsid column (from 'id' column, may be null/empty for position-based join)
    - genotype column as List[String] sorted alphabetically
    - Normalized chrom column (without 'chr' prefix for HF module compatibility)
    
    Args:
        vcf_path: Path to the VCF file
        info_fields: Optional INFO fields to extract
        format_fields: Optional FORMAT fields (must include GT for genotype)
        
    Returns:
        LazyFrame with genotype column ready for joining
    """
    with start_action(action_type="prepare_vcf_for_module_annotation", vcf_path=str(vcf_path)):
        # Read VCF with FORMAT fields enabled (needed for genotype)
        lf = read_vcf_file(
            vcf_path,
            info_fields=info_fields,
            save_parquet=None,  # Don't auto-save, we'll control output
            with_formats=True,
            format_fields=format_fields,
        )
        
        # Ensure we have an rsid column (copy from 'id' if exists)
        schema = lf.collect_schema()
        if "id" in schema.names() and "rsid" not in schema.names():
            lf = lf.rename({"id": "rsid"})
        
        # Normalize chromosome: strip 'chr' prefix if present for HF module compatibility
        if "chrom" in schema.names():
            lf = lf.with_columns(
                pl.col("chrom").str.replace(r"^chr", "").alias("chrom")
            )
        
        return lf


def prepare_vcf_rsid_only(
    vcf_path: Path,
    info_fields: Optional[list[str]] = None,
    format_fields: Optional[list[str]] = None,
) -> pl.LazyFrame:
    """
    Prepare VCF and filter to only variants with rsids.
    
    Use this when you want to join strictly on rsid + genotype.
    """
    lf = prepare_vcf_for_module_annotation(vcf_path, info_fields, format_fields)
    
    # Filter to only variants with rsid starting with "rs"
    return lf.filter(
        pl.col("rsid").is_not_null() & 
        pl.col("rsid").str.starts_with("rs")
    )


def annotate_vcf_with_module_weights(
    vcf_lf: pl.LazyFrame,
    module: AnnotatorModule,
    output_path: Path,
    compression: str = "zstd",
    join_on: str = "position",
) -> tuple[Path, int]:
    """
    Annotate VCF variants with a module's weights table.
    
    Supports two join strategies:
    - "position": Join on chrom + start + ref + alt, then filter by genotype (default)
    - "rsid": Join on rsid + genotype (requires VCF to have rsids)
    
    Uses streaming sink_parquet for memory efficiency.
    
    Args:
        vcf_lf: Prepared VCF LazyFrame with genotype column
        module: The annotator module to use
        output_path: Where to write the output parquet
        compression: Parquet compression (default: zstd)
        join_on: Join strategy - "position" or "rsid"
        
    Returns:
        Tuple of (output_path, num_annotated_variants)
    """
    with start_action(action_type="annotate_with_module_weights", module=module.value, join_on=join_on) as action:
        # Load module weights table (lazy)
        weights_lf = scan_module_table(module, ModuleTable.WEIGHTS)
        
        if join_on == "rsid":
            # Join on rsid + genotype (requires VCF to have rsids)
            module_rsids = weights_lf.select("rsid").unique()
            vcf_filtered = vcf_lf.join(module_rsids, on="rsid", how="semi")
            
            annotated_lf = vcf_filtered.join(
                weights_lf,
                on=["rsid", "genotype"],
                how="left",
                suffix=f"_{module.value}"
            )
        else:
            # Join on position (chrom, start) + genotype
            # HF modules use 'start' for position, VCF also uses 'start' after polars-bio parsing
            
            # The HF weights table has: chrom, start, ref, alts (list), genotype (list)
            # VCF has: chrom, start, ref, alt (string), genotype (list)
            
            # We need to match: VCF.alt should be in weights.alts list
            # First, get position keys from module
            module_positions = weights_lf.select(["chrom", "start"]).unique()
            
            # Semi-join to filter VCF to only positions in module
            vcf_filtered = vcf_lf.join(
                module_positions,
                on=["chrom", "start"],
                how="semi"
            )
            
            # Join on position + genotype
            # Note: We can't directly match alt with alts list in a join,
            # so we join on position + genotype first, then filter
            annotated_lf = vcf_filtered.join(
                weights_lf.drop("ref"),  # Drop ref to avoid conflict
                on=["chrom", "start", "genotype"],
                how="left",
                suffix=f"_{module.value}"
            )
        
        # Write to parquet using streaming
        output_path.parent.mkdir(parents=True, exist_ok=True)
        annotated_lf.sink_parquet(output_path, compression=compression)
        
        # Get row count for metadata (efficient - reads parquet metadata)
        num_rows = pl.scan_parquet(output_path).select(pl.len()).collect().item()
        
        action.log(
            message_type="info",
            step="weights_annotation_complete",
            module=module.value,
            num_variants=num_rows,
            join_on=join_on,
            output_path=str(output_path)
        )
        
        return output_path, num_rows


def annotate_vcf_with_module_annotations(
    vcf_lf: pl.LazyFrame,
    module: AnnotatorModule,
    output_path: Path,
    compression: str = "zstd",
) -> tuple[Path, int]:
    """
    Annotate VCF variants with a module's annotations table.
    
    Joins on rsid only (annotations are variant-level, not genotype-specific).
    
    Args:
        vcf_lf: Prepared VCF LazyFrame with rsid column
        module: The annotator module to use
        output_path: Where to write the output parquet
        compression: Parquet compression (default: zstd)
        
    Returns:
        Tuple of (output_path, num_annotated_variants)
    """
    with start_action(action_type="annotate_with_module_annotations", module=module.value) as action:
        annotations_lf = scan_module_table(module, ModuleTable.ANNOTATIONS)
        
        # Pre-filter VCF to only rsids that exist in the module
        module_rsids = annotations_lf.select("rsid").unique()
        vcf_filtered = vcf_lf.join(module_rsids, on="rsid", how="semi")
        
        # Join on rsid
        annotated_lf = vcf_filtered.join(
            annotations_lf,
            on="rsid",
            how="left",
            suffix=f"_{module.value}"
        )
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        annotated_lf.sink_parquet(output_path, compression=compression)
        
        num_rows = pl.scan_parquet(output_path).select(pl.len()).collect().item()
        
        action.log(
            message_type="info",
            step="annotations_complete",
            module=module.value,
            num_variants=num_rows
        )
        
        return output_path, num_rows


def annotate_vcf_with_module_studies(
    vcf_lf: pl.LazyFrame,
    module: AnnotatorModule,
    output_path: Path,
    compression: str = "zstd",
) -> tuple[Path, int]:
    """
    Annotate VCF variants with a module's studies table.
    
    Joins on rsid only. Note: studies table has one row per (rsid, pmid),
    so this may produce multiple rows per variant.
    
    Args:
        vcf_lf: Prepared VCF LazyFrame with rsid column
        module: The annotator module to use
        output_path: Where to write the output parquet
        compression: Parquet compression (default: zstd)
        
    Returns:
        Tuple of (output_path, num_rows)
    """
    with start_action(action_type="annotate_with_module_studies", module=module.value) as action:
        studies_lf = scan_module_table(module, ModuleTable.STUDIES)
        
        # Pre-filter VCF to only rsids that exist in the module
        module_rsids = studies_lf.select("rsid").unique()
        vcf_filtered = vcf_lf.join(module_rsids, on="rsid", how="semi")
        
        # Join on rsid
        annotated_lf = vcf_filtered.join(
            studies_lf,
            on="rsid",
            how="left",
            suffix=f"_{module.value}"
        )
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        annotated_lf.sink_parquet(output_path, compression=compression)
        
        num_rows = pl.scan_parquet(output_path).select(pl.len()).collect().item()
        
        action.log(
            message_type="info",
            step="studies_complete",
            module=module.value,
            num_rows=num_rows
        )
        
        return output_path, num_rows


def annotate_vcf_with_all_modules(
    logger,
    vcf_path: Path,
    config: HfModuleAnnotationConfig,
    user_name: str,
    sample_name: Optional[str] = None,
) -> tuple[AnnotationManifest, dict]:
    """
    Annotate VCF with all selected HF modules.
    
    Produces one set of parquet files per module:
    - {module}_weights.parquet (genotype-specific scores)
    - {module}_annotations.parquet (variant facts, optional)
    - {module}_studies.parquet (literature evidence, optional)
    
    Args:
        logger: Logger instance
        vcf_path: Path to input VCF
        config: HfModuleAnnotationConfig with module selection
        user_name: User identifier for output organization
        sample_name: Optional sample name
        
    Returns:
        Tuple of (AnnotationManifest, metadata_dict)
    """
    modules = config.get_modules()
    sample_name = sample_name or config.sample_name or vcf_path.stem
    
    # Determine output directory
    if config.output_dir:
        output_dir = Path(config.output_dir)
    else:
        output_dir = get_user_output_dir() / user_name / sample_name / "modules"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Annotating with modules: {[m.value for m in modules]}")
    
    with resource_tracker("Annotate VCF with HF Modules") as tracker:
        # Prepare VCF once (with genotype column)
        logger.info(f"Preparing VCF: {vcf_path}")
        vcf_lf = prepare_vcf_for_module_annotation(
            vcf_path,
            info_fields=config.info_fields,
            format_fields=config.format_fields,
        )
        
        # Process each module
        module_outputs: list[ModuleOutputMapping] = []
        total_annotated = 0
        
        for module in modules:
            logger.info(f"Processing module: {module.value}")
            
            # Weights (genotype-specific) - main annotation
            weights_path = output_dir / f"{module.value}_weights.parquet"
            weights_path, num_weights = annotate_vcf_with_module_weights(
                vcf_lf, module, weights_path, config.compression
            )
            
            module_output = ModuleOutputMapping(
                module=module.value,
                weights_path=str(weights_path),
            )
            
            total_annotated += num_weights
            module_outputs.append(module_output)
            
            logger.info(f"  {module.value}: {num_weights} variants with weights")
    
    # Build manifest
    manifest = AnnotationManifest(
        user_name=user_name,
        sample_name=sample_name,
        source_vcf=str(vcf_path),
        modules=module_outputs,
        total_variants_annotated=total_annotated,
    )
    
    # Write manifest to JSON
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2))
    logger.info(f"Manifest written to: {manifest_path}")
    
    # Build metadata for Dagster
    metadata_dict = {
        "user_name": MetadataValue.text(user_name),
        "sample_name": MetadataValue.text(sample_name),
        "source_vcf": MetadataValue.path(str(vcf_path.absolute())),
        "output_dir": MetadataValue.path(str(output_dir.absolute())),
        "manifest_path": MetadataValue.path(str(manifest_path.absolute())),
        "modules_processed": MetadataValue.int(len(modules)),
        "module_names": MetadataValue.text(", ".join(m.value for m in modules)),
        "total_variants_annotated": MetadataValue.int(total_annotated),
        "compression": MetadataValue.text(config.compression),
    }
    
    # Add resource metrics if available
    if "report" in tracker:
        report = tracker["report"]
        metadata_dict.update({
            "duration_sec": MetadataValue.float(round(report.duration, 2)),
            "cpu_percent": MetadataValue.float(round(report.cpu_usage_percent, 1)),
            "peak_memory_mb": MetadataValue.float(round(report.peak_memory_mb, 2)),
        })
    
    return manifest, metadata_dict
