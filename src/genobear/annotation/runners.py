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

from pipefunc import Pipeline
from eliot import start_action
import contextlib
import io

from genobear.annotation.ensembl_annotations import (
    download_ensembl_annotations,
    annotate_with_ensembl,
)
from genobear.annotation.vcf_parser import (
    load_vcf_as_lazy_frame,
)
from pycomfort.logging import to_nice_stdout, to_nice_file
from genobear.config import get_default_workers
from genobear.runtime import run_pipeline


def annotation_base_pipeline(profile: bool = False) -> Pipeline:
    """Internal: base annotation pipeline.
    
    Args:
        profile: If True, enables profiling to track CPU, memory, and execution time
    """
    return Pipeline(
        [
            download_ensembl_annotations,
            load_vcf_as_lazy_frame,
            annotate_with_ensembl,
        ],
        print_error=True,
        profile=profile,
    )


def ensembl_annotation_pipeline(profile: bool = False) -> Pipeline:
    """Get a pipeline for annotating VCF with ensembl_variations data.
    
    Args:
        profile: If True, enables profiling to track CPU, memory, and execution time
        
    Returns:
        Configured pipeline for VCF annotation
    """
    pipeline = annotation_base_pipeline(profile=profile)
    
    # Set defaults
    defaults = {
        "variant_type": "SNV",
        "repo_id": "just-dna-seq/ensembl_variations",
    }
    
    pipeline.update_defaults(defaults)
    return pipeline


def ensembl_downloader_pipeline() -> Pipeline:
    """Get a standalone pipeline for downloading ensembl_variations data.
    
    Returns:
        Pipeline for downloading ensembl_variations from HuggingFace Hub
    """
    return Pipeline([download_ensembl_annotations], print_error=True)


def execute_pipeline(
    pipeline: Pipeline,
    inputs: dict,
    output_names: Optional[set[str]] = None,
    run_folder: Optional[str | Path] = None,
    return_results: bool = True,
    show_progress: str | bool = "rich",
    parallel: Optional[bool] = None,
    workers: Optional[int] = None,
):
    """Execute a pipefunc Pipeline for annotation (sequential by default due to LazyFrames)."""
    # Annotation pipelines use LazyFrames which cannot be pickled for multiprocessing
    # So we run sequentially without executors
    use_parallel = parallel if parallel is not None else False
    
    if use_parallel:
        # If user explicitly requests parallel, use the annotation executor mode
        return run_pipeline(
            pipeline=pipeline,
            inputs=inputs,
            output_names=output_names,
            run_folder=run_folder,
            return_results=return_results,
            show_progress=show_progress,
            parallel=True,
            workers=workers,
            executor_mode="annotation",
        )
    else:
        # Run sequentially without executors (default for annotation)
        with start_action(
            action_type="execute_annotation_pipeline",
            run_folder=str(run_folder) if run_folder else None,
            parallel=False
        ):
            return pipeline.map(
                inputs=inputs,
                output_names=output_names,
                parallel=False,
                return_results=return_results,
                show_progress=show_progress,
                run_folder=run_folder,
            )


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
    save_vortex: bool = False,
    profile: bool = True,
    cache: bool = True,
    **kwargs
) -> dict:
    """Annotate a VCF file with ensembl_variations data.
    
    High-level convenience function that builds and executes the annotation pipeline.
    
    Args:
        vcf_path: Path to the input VCF file
        output_path: Path where to save annotated parquet file
        cache_dir: Local cache directory for ensembl_variations data
        repo_id: HuggingFace repository ID for ensembl_variations
        variant_type: Variant type to use for annotation (default: "SNV")
        token: HuggingFace API token
        force_download: Force re-download of ensembl_variations data
        workers: Number of parallel workers
        log: Enable logging
        run_folder: Optional run folder for caching
        save_vortex: If True, convert output to Vortex format
        profile: If True, track CPU, memory, and execution time (default: True)
        cache: If True, enable pipefunc caching for faster repeated runs (default: True)
        **kwargs: Additional pipeline inputs
        
    Returns:
        Pipeline results dictionary (includes 'profiling_report' if profiling is enabled)
    """
    if log:
        to_nice_stdout()
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        to_nice_file(log_dir / "annotate_vcf.json", log_dir / "annotate_vcf.log")
    
    with start_action(
        action_type="annotate_vcf",
        vcf_path=str(vcf_path),
        output_path=str(output_path) if output_path else None,
        variant_type=variant_type,
        profile=profile,
        cache=cache
    ) as action:
        # Use simplified pipeline (no save step needed, handled by annotate_with_ensembl)
        pipeline = ensembl_annotation_pipeline(profile=profile)
        
        inputs = {
            "vcf_path": vcf_path,
            "cache_dir": cache_dir,
            "repo_id": repo_id,
            "variant_type": variant_type,
            "token": token,
            "force_download": force_download or not cache,  # Disable cache = force download
        }
        
        # Map parameter names correctly
        # annotate_with_ensembl expects:
        # - input_dataframe (from vcf_lazy_frame)
        # - ensembl_cache_path (from download_ensembl_annotations -> ensembl_cache_path)
        # - output_path (optional)
        # - save_vortex (optional)
        if output_path:
            inputs["output_path"] = output_path
        if save_vortex:
            inputs["save_vortex"] = save_vortex
        
        inputs.update(kwargs)
        
        # IMPORTANT: pipefunc 0.88.0 profiling reports zero calls when `output_names` is set.
        # Workaround: when profiling is enabled, run full pipeline (output_names=None).
        output_names = None if profile else {"annotated_dataframe"}
        
        results = execute_pipeline(
            pipeline=pipeline,
            inputs=inputs,
            output_names=output_names,
            run_folder=run_folder if cache else None,  # Disable run_folder caching if cache=False
            return_results=True,
            show_progress="rich" if log else False,
            parallel=False,  # Annotation uses LazyFrames which cannot be pickled
            workers=workers,
        )
        
        # Extract actual values from Result objects if needed
        if results and isinstance(results, dict):
            # Handle pipefunc Result objects - extract .output if present
            extracted_results = {}
            for key, value in results.items():
                if hasattr(value, "output"):
                    # It's a Result object, extract the output
                    extracted_results[key] = value.output
                else:
                    extracted_results[key] = value
            results = extracted_results

        # Emit pipefunc profiling report into Eliot (and return it) if enabled
        if profile:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                pipeline.print_profiling_stats()
            profiling_report = buffer.getvalue().strip()
            
            # Check if profiling captured any actual execution
            lines_with_calls = [
                line for line in profiling_report.split("\n") 
                if "|" in line and "Function" not in line and "---" not in line
            ]
            has_zero_calls = any("| 0              " in line or "| 0       " in line for line in lines_with_calls)
            
            note = None
            if has_zero_calls:
                note = (
                    "Profiling shows 0 calls. This typically means: "
                    "(1) download_ensembl_annotations skipped because data exists (set force_download=True to re-execute), "
                    "(2) functions were cached from a previous run, or "
                    "(3) pipefunc profiling didn't instrument the functions. "
                    "Use --no-cache to force re-execution, or use system tools (htop, /usr/bin/time -v) for monitoring."
                )
            
            action.log(
                message_type="pipefunc_profiling_stats",
                report=profiling_report,
                has_zero_calls=has_zero_calls,
                note=note
            )
            if results is None:
                results = {}
            results["profiling_report"] = profiling_report
        
        # If output_path was provided, verify file was saved
        if output_path:
            output_path_obj = Path(output_path)
            if output_path_obj.exists():
                if results is None:
                    results = {}
                results["annotated_vcf_path"] = output_path_obj
            
            # Check for vortex output if save_vortex was requested
            if save_vortex:
                vortex_path = output_path_obj.with_suffix(".vortex")
                if vortex_path.exists():
                    if results is None:
                        results = {}
                    results["vortex_path"] = vortex_path
        
        return results or {}


def download_ensembl_reference(
    cache_dir: Optional[Path] = None,
    repo_id: str = "just-dna-seq/ensembl_variations",
    token: Optional[str] = None,
    force_download: bool = False,
    log: bool = True,
    **kwargs
) -> dict:
    """Download ensembl_variations reference data from HuggingFace Hub.
    
    Args:
        cache_dir: Local cache directory
        repo_id: HuggingFace repository ID
        token: HuggingFace API token
        force_download: Force re-download even if cache exists
        log: Enable logging
        **kwargs: Additional pipeline inputs
        
    Returns:
        Pipeline results dictionary with cache path
    """
    if log:
        to_nice_stdout()
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        to_nice_file(log_dir / "download_ensembl_ref.json", log_dir / "download_ensembl_ref.log")
    
    with start_action(
        action_type="download_ensembl_reference",
        repo_id=repo_id,
        force_download=force_download
    ):
        pipeline = ensembl_downloader_pipeline()
        
        inputs = {
            "cache_dir": cache_dir,
            "repo_id": repo_id,
            "token": token,
            "force_download": force_download,
        }
        inputs.update(kwargs)
        
        return execute_pipeline(
            pipeline=pipeline,
            inputs=inputs,
            output_names={"ensembl_cache_path"},
            run_folder=None,
            return_results=True,
            show_progress="rich" if log else False,
            parallel=False,
        )

