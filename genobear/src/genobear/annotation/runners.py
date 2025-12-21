"""
Annotation pipelines for genomic VCF files.

This module provides pipelines for annotating VCF files with ensembl_variations data.

Functions:
    - ensembl_annotation_pipeline: Get pipeline for annotating VCF with ensembl_variations
    - ensembl_downloader_pipeline: Get pipeline for downloading ensembl_variations data
    - execute_annotation_pipeline: Execute annotation pipelines (sequential by default)
    - annotate_vcf: High-level function to annotate VCF files
    - download_ensembl_reference: Download ensembl_variations reference data
"""

from pathlib import Path
from typing import Optional

from eliot import start_action
from genobear.annotation.ensembl_annotations_prefect import (
    download_ensembl_annotations_task,
    annotate_with_ensembl_flow,
    load_vcf_as_lazy_frame_task,
)
from pycomfort.logging import to_nice_stdout, to_nice_file
from genobear.config import get_default_workers


def annotate_vcf(
    vcf_path: Path,
    output_path: Optional[Path] = None,
    cache_dir: Optional[Path] = None,
    repo_id: str = "just-dna-seq/ensembl_variations",
    variant_type: str = "SNV",
    token: Optional[str] = None,
    force_download: bool = False,
    workers: Optional[int] = None,
    log: bool = True,
    run_folder: Optional[str] = None,
    profile: bool = True,
    cache: bool = True,
    **kwargs
) -> dict:
    """Annotate a VCF file with ensembl_variations data using Prefect."""
    if log:
        to_nice_stdout()
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        to_nice_file(log_dir / "annotate_vcf.json", log_dir / "annotate_vcf.log")
    
    from genobear.runtime import prefect_flow_run
    
    with prefect_flow_run("Annotate VCF (High-level)", profile=profile):
        # Step 1: Download/Check Reference (Task)
        ensembl_cache = download_ensembl_annotations_task(
            repo_id=repo_id,
            cache_dir=cache_dir,
            token=token,
            force_download=force_download
        )

        # Step 2: Load VCF (Task)
        vcf_lf = load_vcf_as_lazy_frame_task(vcf_path=vcf_path)

        # Step 3: Run Annotation Flow
        result_lf = annotate_with_ensembl_flow(
            input_dataframe=vcf_lf,
            ensembl_cache_path=ensembl_cache,
            variant_type=variant_type,
            output_path=output_path,
            profile=profile
        )
        
        results = {
            "annotated_dataframe": result_lf,
            "ensembl_cache_path": ensembl_cache
        }
        if output_path:
            results["annotated_vcf_path"] = Path(output_path)
            
        return results


def download_ensembl_reference(
    cache_dir: Optional[Path] = None,
    repo_id: str = "just-dna-seq/ensembl_variations",
    token: Optional[str] = None,
    force_download: bool = False,
    log: bool = True,
    profile: bool = True,
    **kwargs
) -> dict:
    """Download ensembl_variations reference data using Prefect.
    
    Args:
        cache_dir: Local cache directory
        repo_id: HuggingFace repository ID
        token: HuggingFace API token
        force_download: Force re-download even if cache exists
        log: Enable logging
        profile: If True, tracks resource usage
        **kwargs: Additional pipeline inputs
        
    Returns:
        Pipeline results dictionary with cache path
    """
    if log:
        to_nice_stdout()
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        to_nice_file(log_dir / "download_ensembl_ref.json", log_dir / "download_ensembl_ref.log")
    
    from genobear.runtime import prefect_flow_run
    
    with prefect_flow_run("Download Ensembl Reference", profile=profile):
        cache_path = download_ensembl_annotations_task(
            repo_id=repo_id,
            cache_dir=cache_dir,
            token=token,
            force_download=force_download
        )
        return {"ensembl_cache_path": cache_path}

