"""
Logic for annotating VCF files with HuggingFace modules.

This module contains the core annotation logic using lazy Polars
for memory-efficient processing. HF modules are self-contained
and don't require Ensembl joins.

Modules are identified by string names (e.g., "longevitymap") rather than
enums, enabling dynamic discovery of new modules from the HF repository.
"""

from pathlib import Path
from typing import Optional

import polars as pl
from dagster import MetadataValue
from eliot import start_action

from just_dna_pipelines.io import read_vcf_file
from just_dna_pipelines.runtime import resource_tracker
from just_dna_pipelines.annotation.hf_modules import (
    ModuleTable,
    ModuleOutputMapping,
    AnnotationManifest,
    scan_module_table,
    get_module_info,
    ModuleInfo,
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
    module_name: str,
    output_path: Path,
    compression: str = "zstd",
    join_on: str = "position",
    module_info: Optional[ModuleInfo] = None,
) -> tuple[Path, int]:
    """
    Annotate VCF variants with a module's weights table.
    
    Supports two join strategies:
    - "position": Join on chrom + start + ref + alt, then filter by genotype (default)
    - "rsid": Join on rsid + genotype (requires VCF to have rsids)
    
    Uses streaming sink_parquet for memory efficiency.
    
    Args:
        vcf_lf: Prepared VCF LazyFrame with genotype column
        module_name: Name of the annotator module (e.g., "longevitymap")
        output_path: Where to write the output parquet
        compression: Parquet compression (default: zstd)
        join_on: Join strategy - "position" or "rsid"
        module_info: Optional ModuleInfo for the module
        
    Returns:
        Tuple of (output_path, num_annotated_variants)
    """
    with start_action(action_type="annotate_with_module_weights", module=module_name, join_on=join_on) as action:
        # Load module weights table (lazy)
        weights_lf = scan_module_table(module_name, ModuleTable.WEIGHTS, module_info=module_info)
        
        if join_on == "rsid":
            # Join on rsid + genotype (requires VCF to have rsids)
            module_rsids = weights_lf.select("rsid").unique()
            vcf_filtered = vcf_lf.join(module_rsids, on="rsid", how="semi")
            
            annotated_lf = vcf_filtered.join(
                weights_lf,
                on=["rsid", "genotype"],
                how="left",
                suffix=f"_{module_name}"
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
                suffix=f"_{module_name}"
            )
        
        # Write to parquet using streaming
        output_path.parent.mkdir(parents=True, exist_ok=True)
        annotated_lf.sink_parquet(output_path, compression=compression)
        
        # Get row count for metadata (efficient - reads parquet metadata)
        num_rows = pl.scan_parquet(output_path).select(pl.len()).collect().item()
        
        action.log(
            message_type="info",
            step="weights_annotation_complete",
            module=module_name,
            num_variants=num_rows,
            join_on=join_on,
            output_path=str(output_path)
        )
        
        return output_path, num_rows


def annotate_vcf_with_module_annotations(
    vcf_lf: pl.LazyFrame,
    module_name: str,
    output_path: Path,
    compression: str = "zstd",
    module_info: Optional[ModuleInfo] = None,
) -> tuple[Path, int]:
    """
    Annotate VCF variants with a module's annotations table.
    
    Joins on rsid only (annotations are variant-level, not genotype-specific).
    
    Args:
        vcf_lf: Prepared VCF LazyFrame with rsid column
        module_name: Name of the annotator module (e.g., "longevitymap")
        output_path: Where to write the output parquet
        compression: Parquet compression (default: zstd)
        module_info: Optional ModuleInfo for the module
        
    Returns:
        Tuple of (output_path, num_annotated_variants)
    """
    with start_action(action_type="annotate_with_module_annotations", module=module_name) as action:
        annotations_lf = scan_module_table(module_name, ModuleTable.ANNOTATIONS, module_info=module_info)
        
        # Pre-filter VCF to only rsids that exist in the module
        module_rsids = annotations_lf.select("rsid").unique()
        vcf_filtered = vcf_lf.join(module_rsids, on="rsid", how="semi")
        
        # Join on rsid
        annotated_lf = vcf_filtered.join(
            annotations_lf,
            on="rsid",
            how="left",
            suffix=f"_{module_name}"
        )
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        annotated_lf.sink_parquet(output_path, compression=compression)
        
        num_rows = pl.scan_parquet(output_path).select(pl.len()).collect().item()
        
        action.log(
            message_type="info",
            step="annotations_complete",
            module=module_name,
            num_variants=num_rows
        )
        
        return output_path, num_rows


def annotate_vcf_with_module_studies(
    vcf_lf: pl.LazyFrame,
    module_name: str,
    output_path: Path,
    compression: str = "zstd",
    module_info: Optional[ModuleInfo] = None,
) -> tuple[Path, int]:
    """
    Annotate VCF variants with a module's studies table.
    
    Joins on rsid only. Note: studies table has one row per (rsid, pmid),
    so this may produce multiple rows per variant.
    
    Args:
        vcf_lf: Prepared VCF LazyFrame with rsid column
        module_name: Name of the annotator module (e.g., "longevitymap")
        output_path: Where to write the output parquet
        compression: Parquet compression (default: zstd)
        module_info: Optional ModuleInfo for the module
        
    Returns:
        Tuple of (output_path, num_rows)
    """
    with start_action(action_type="annotate_with_module_studies", module=module_name) as action:
        studies_lf = scan_module_table(module_name, ModuleTable.STUDIES, module_info=module_info)
        
        # Pre-filter VCF to only rsids that exist in the module
        module_rsids = studies_lf.select("rsid").unique()
        vcf_filtered = vcf_lf.join(module_rsids, on="rsid", how="semi")
        
        # Join on rsid
        annotated_lf = vcf_filtered.join(
            studies_lf,
            on="rsid",
            how="left",
            suffix=f"_{module_name}"
        )
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        annotated_lf.sink_parquet(output_path, compression=compression)
        
        num_rows = pl.scan_parquet(output_path).select(pl.len()).collect().item()
        
        action.log(
            message_type="info",
            step="studies_complete",
            module=module_name,
            num_rows=num_rows
        )
        
        return output_path, num_rows


def download_file(url: str, output_path: Path) -> Path:
    """Download a file from a URL or HuggingFace."""
    import requests
    
    # hf:// protocol handling
    if url.startswith("hf://"):
        from huggingface_hub import hf_hub_download
        
        # hf://datasets/repo/data/module/file -> repo, data/module/file
        parts = url.replace("hf://datasets/", "").split("/", 1)
        repo_id = parts[0]
        subpath = parts[1]
        
        downloaded_path = hf_hub_download(
            repo_id=repo_id,
            filename=subpath,
            repo_type="dataset"
        )
        import shutil
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(downloaded_path, output_path)
        return output_path
    
    # Zenodo URL handling
    if "zenodo.org/record" in url or "zenodo.org/api/records" in url:
        # If it's a record URL but not a direct content link, we might need to resolve it
        if "content" not in url and "/files/" in url:
             # Already a file link, might work directly or need /content
             pass
    
    # Regular URL handling
    response = requests.get(url, stream=True)
    response.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return output_path


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
    from just_dna_pipelines.annotation.hf_modules import discover_hf_modules
    
    # Discover modules from the configured repos
    module_infos = discover_hf_modules(config.repos)
    selected_names = config.get_modules()
    
    sample_name = sample_name or config.sample_name or vcf_path.stem
    
    # Determine output directory
    if config.output_dir:
        output_dir = Path(config.output_dir)
    else:
        output_dir = get_user_output_dir() / user_name / sample_name / "modules"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Annotating with modules: {selected_names}")
    
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
        
        for module_name in selected_names:
            logger.info(f"Processing module: {module_name}")
            info = module_infos[module_name]
            
            # Weights (genotype-specific) - main annotation
            weights_path = output_dir / f"{module_name}_weights.parquet"
            weights_path, num_weights = annotate_vcf_with_module_weights(
                vcf_lf, module_name, weights_path, config.compression, module_info=info
            )
            
            # Download logo if exists
            logo_path = None
            if info.logo_url:
                try:
                    ext = info.logo_url.split(".")[-1]
                    target = output_dir / f"{module_name}_logo.{ext}"
                    logo_path = str(download_file(info.logo_url, target))
                    logger.info(f"  Downloaded logo: {logo_path}")
                except Exception as e:
                    logger.warning(f"  Failed to download logo for {module_name}: {e}")

            # Download metadata if exists
            metadata_json_path = None
            if info.metadata_url:
                try:
                    target = output_dir / f"{module_name}_metadata.json"
                    metadata_json_path = str(download_file(info.metadata_url, target))
                    logger.info(f"  Downloaded metadata: {metadata_json_path}")
                except Exception as e:
                    logger.warning(f"  Failed to download metadata for {module_name}: {e}")
            
            module_output = ModuleOutputMapping(
                module=module_name,
                weights_path=str(weights_path),
                logo_path=logo_path,
                metadata_path=metadata_json_path,
            )
            
            total_annotated += num_weights
            module_outputs.append(module_output)
            
            logger.info(f"  {module_name}: {num_weights} variants with weights")
    
    # Get execution metrics from resource tracker
    from datetime import datetime, timezone
    duration_sec = None
    cpu_percent = None
    peak_memory_mb = None
    
    if "report" in tracker:
        report = tracker["report"]
        duration_sec = round(report.duration, 2)
        cpu_percent = round(report.cpu_usage_percent, 1)
        peak_memory_mb = round(report.peak_memory_mb, 2)
    
    # Build manifest with execution metrics
    manifest = AnnotationManifest(
        user_name=user_name,
        sample_name=sample_name,
        source_vcf=str(vcf_path),
        modules=module_outputs,
        total_variants_annotated=total_annotated,
        duration_sec=duration_sec,
        cpu_percent=cpu_percent,
        peak_memory_mb=peak_memory_mb,
        timestamp=datetime.now(timezone.utc).isoformat(),
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
        "modules_processed": MetadataValue.int(len(selected_names)),
        "module_names": MetadataValue.text(", ".join(selected_names)),
        "total_variants_annotated": MetadataValue.int(total_annotated),
        "compression": MetadataValue.text(config.compression),
    }
    
    # Add resource metrics to Dagster metadata
    if duration_sec is not None:
        metadata_dict.update({
            "duration_sec": MetadataValue.float(duration_sec),
            "cpu_percent": MetadataValue.float(cpu_percent),
            "peak_memory_mb": MetadataValue.float(peak_memory_mb),
        })
    
    # Add sample/subject metadata from SampleInfo base class
    if config.species:
        metadata_dict["species"] = MetadataValue.text(config.species)
    if config.reference_genome:
        metadata_dict["reference_genome"] = MetadataValue.text(config.reference_genome)
    if config.sample_description:
        metadata_dict["sample_description"] = MetadataValue.text(config.sample_description)
    if config.sequencing_type:
        metadata_dict["sequencing_type"] = MetadataValue.text(config.sequencing_type)
    
    # Add user-provided metadata (well-known optional fields)
    if config.subject_id:
        metadata_dict["subject_id"] = MetadataValue.text(config.subject_id)
    if config.sex:
        metadata_dict["sex"] = MetadataValue.text(config.sex)
    if config.tissue:
        metadata_dict["tissue"] = MetadataValue.text(config.tissue)
    if config.study_name:
        metadata_dict["study_name"] = MetadataValue.text(config.study_name)
    if config.description:
        metadata_dict["description"] = MetadataValue.text(config.description)
    
    # Add arbitrary custom metadata fields (user-defined key-value pairs)
    if config.custom_metadata:
        # Store the full dict as JSON for complete access
        metadata_dict["custom_metadata"] = MetadataValue.json(config.custom_metadata)
        # Also add each field individually with a "custom/" prefix for visibility in Dagster UI
        for key, value in config.custom_metadata.items():
            # Sanitize key to be a valid metadata key (alphanumeric + underscore)
            safe_key = "".join(c if c.isalnum() or c == "_" else "_" for c in key)
            metadata_dict[f"custom/{safe_key}"] = MetadataValue.text(str(value))
    
    return manifest, metadata_dict
