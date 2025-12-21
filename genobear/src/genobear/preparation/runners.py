"""
Preparation pipelines for genomic data sources.

This module provides pipelines for downloading, converting, splitting, and uploading
genomic data from various sources (ClinVar, Ensembl, dbSNP, gnomAD).
"""

import os
from pathlib import Path
from typing import Optional

from eliot import start_action

from genobear.preparation.vcf_downloader import (
    list_paths,
    download_path,
    convert_to_parquet,
    validate_downloads_and_parquet,
)
from genobear.preparation.huggingface_uploader import (
    collect_parquet_files,
)
from pycomfort.logging import to_nice_stdout, to_nice_file
from genobear.config import get_default_workers
from genobear.preparation.runners_prefect import (
    prepare_clinvar_flow,
    prepare_ensembl_flow,
    prepare_dbsnp_flow,
    prepare_gnomad_flow,
)


class PreparationPipelines:
    """Pipelines for preparing genomic data from various sources using Prefect.
    
    This class provides static methods for:
    - Downloading, converting, and splitting VCF data
    - Uploading processed data to Hugging Face Hub
    """
    
    @staticmethod
    def download_clinvar(
        dest_dir: Optional[Path] = None,
        with_splitting: bool = False,
        download_workers: Optional[int] = None,
        parquet_workers: Optional[int] = None,
        workers: Optional[int] = None,
        log: bool = True,
        timeout: Optional[float] = None,
        run_folder: Optional[str] = None,
        profile: bool = True,
        **kwargs
    ) -> dict:
        """Download ClinVar VCF files and convert to parquet using Prefect.
        
        Args:
            dest_dir: Destination directory. If None, uses platformdirs cache
            with_splitting: If True, splits variants by type (TSA)
            download_workers: Number of download workers (handled by Prefect)
            parquet_workers: Number of parquet processing workers (handled by Prefect)
            workers: Number of general workers (handled by Prefect)
            log: Enable logging
            timeout: Download timeout in seconds
            run_folder: Optional run folder for caching (handled by Prefect)
            profile: If True, tracks resource usage
            **kwargs: Additional pipeline inputs
            
        Returns:
            Pipeline results dictionary
        """
        if log:
            to_nice_stdout()
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            to_nice_file(log_dir / "download_clinvar.json", log_dir / "download_clinvar.log")
        
        return prepare_clinvar_flow(
            dest_dir=dest_dir,
            with_splitting=with_splitting,
            profile=profile,
            **kwargs
        )
    
    @staticmethod
    def download_ensembl(
        dest_dir: Optional[Path] = None,
        with_splitting: bool = False,
        download_workers: Optional[int] = None,
        parquet_workers: Optional[int] = None,
        workers: Optional[int] = None,
        log: bool = True,
        timeout: Optional[float] = None,
        run_folder: Optional[str] = None,
        pattern: Optional[str] = None,
        url: Optional[str] = None,
        profile: bool = True,
        **kwargs
    ) -> dict:
        """Download Ensembl VCF files and convert to parquet using Prefect.
        
        Args:
            dest_dir: Destination directory. If None, uses platformdirs cache
            with_splitting: If True, splits variants by type (TSA)
            download_workers: Number of download workers
            parquet_workers: Number of parquet processing workers
            workers: Number of general workers
            log: Enable logging
            timeout: Download timeout in seconds
            run_folder: Optional run folder for caching
            pattern: Regex pattern to filter files
            url: Base URL for Ensembl data
            profile: If True, tracks resource usage
            **kwargs: Additional pipeline inputs
            
        Returns:
            Pipeline results dictionary
        """
        if log:
            to_nice_stdout()
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            to_nice_file(log_dir / "download_ensembl.json", log_dir / "download_ensembl.log")
        
        return prepare_ensembl_flow(
            dest_dir=dest_dir,
            with_splitting=with_splitting,
            pattern=pattern,
            profile=profile,
            **kwargs
        )
    
    @staticmethod
    def download_dbsnp(
        dest_dir: Optional[Path] = None,
        build: str = "GRCh38",
        with_splitting: bool = False,
        download_workers: Optional[int] = None,
        parquet_workers: Optional[int] = None,
        workers: Optional[int] = None,
        log: bool = True,
        timeout: Optional[float] = None,
        run_folder: Optional[str] = None,
        profile: bool = True,
        **kwargs
    ) -> dict:
        """Download dbSNP VCF files and convert to parquet using Prefect.
        
        Args:
            dest_dir: Destination directory. If None, uses platformdirs cache
            build: Genome build (GRCh38 or GRCh37)
            with_splitting: If True, splits variants by type (TSA)
            download_workers: Number of download workers
            parquet_workers: Number of parquet processing workers
            workers: Number of general workers
            log: Enable logging
            timeout: Download timeout in seconds
            run_folder: Optional run folder for caching
            profile: If True, tracks resource usage
            **kwargs: Additional pipeline inputs
            
        Returns:
            Pipeline results dictionary
        """
        if log:
            to_nice_stdout()
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            to_nice_file(log_dir / "download_dbsnp.json", log_dir / "download_dbsnp.log")
        
        return prepare_dbsnp_flow(
            build=build,
            dest_dir=dest_dir,
            with_splitting=with_splitting,
            profile=profile,
            **kwargs
        )
    
    @staticmethod
    def download_gnomad(
        dest_dir: Optional[Path] = None,
        version: str = "v4",
        with_splitting: bool = False,
        download_workers: Optional[int] = None,
        parquet_workers: Optional[int] = None,
        workers: Optional[int] = None,
        log: bool = True,
        timeout: Optional[float] = None,
        run_folder: Optional[str] = None,
        profile: bool = True,
        **kwargs
    ) -> dict:
        """Download gnomAD VCF files and convert to parquet using Prefect.
        
        Args:
            dest_dir: Destination directory. If None, uses platformdirs cache
            version: gnomAD version (v3 or v4)
            with_splitting: If True, splits variants by type (TSA)
            download_workers: Number of download workers
            parquet_workers: Number of parquet processing workers
            workers: Number of general workers
            log: Enable logging
            timeout: Download timeout in seconds
            run_folder: Optional run folder for caching
            profile: If True, tracks resource usage
            **kwargs: Additional pipeline inputs
            
        Returns:
            Pipeline results dictionary
        """
        if log:
            to_nice_stdout()
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            to_nice_file(log_dir / "download_gnomad.json", log_dir / "download_gnomad.log")
        
        return prepare_gnomad_flow(
            version=version,
            dest_dir=dest_dir,
            with_splitting=with_splitting,
            profile=profile,
            **kwargs
        )
    
    @staticmethod
    def split_existing_parquets(
        parquet_files: list[Path] | Path,
        explode_snv_alt: bool = True,
        write_to: Optional[Path] = None,
        workers: Optional[int] = None,
        log: bool = True,
        profile: bool = True,
        **kwargs
    ) -> dict:
        """Quick function to split existing parquet files by variant type using Prefect.
        
        Args:
            parquet_files: Path or list of paths to parquet files
            explode_snv_alt: Whether to explode ALT column for SNV variants
            write_to: Output directory for split files
            workers: Number of parallel workers (handled by Prefect)
            log: Enable logging
            profile: If True, tracks resource usage
            **kwargs: Additional arguments
            
        Returns:
            Pipeline results dictionary
        """
        from genobear.preparation.runners_prefect import split_parquets_task
        from genobear.runtime import prefect_flow_run
        
        if isinstance(parquet_files, Path):
            parquet_files = [parquet_files]
            
        if log:
            to_nice_stdout()
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            to_nice_file(log_dir / "split_parquets.json", log_dir / "split_parquets.log")
            
        with prefect_flow_run("Split Existing Parquets", profile=profile):
            results = split_parquets_task(
                parquet_paths=parquet_files,
                explode_snv_alt=explode_snv_alt,
                write_to=write_to
            )
            return {"split_variants_dict": results}
    
    @staticmethod
    def upload_clinvar_to_hf(
        source_dir: Optional[Path] = None,
        repo_id: str = "just-dna-seq/clinvar",
        token: Optional[str] = None,
        pattern: str = "**/*.parquet",
        path_prefix: str = "data",
        workers: Optional[int] = None,
        log: bool = True,
        **kwargs
    ) -> dict:
        """Upload ClinVar parquet files to Hugging Face Hub.
        
        Only uploads files that differ in size from the remote versions,
        avoiding unnecessary data transfers.
        
        Args:
            source_dir: Source directory containing parquet files. If None, uses default cache
            repo_id: Hugging Face repository ID (default: just-dna-seq/clinvar)
            token: Hugging Face API token. If None, uses HF_TOKEN env variable
            pattern: Glob pattern for finding parquet files (default: **/*.parquet)
            path_prefix: Prefix for paths in the repository (default: data)
            workers: Number of parallel workers (default from env or cpu_count)
            log: Enable logging
            **kwargs: Additional arguments passed to upload function
            
        Returns:
            Pipeline results dictionary with upload status for each file
        """
        from platformdirs import user_cache_dir
        
        if workers is None:
            workers = get_default_workers()
        
        # Determine source directory
        if source_dir is None:
            user_cache_path = Path(user_cache_dir(appname="genobear"))
            default_name = "clinvar"
            base_dir = user_cache_path / default_name
            # Prefer splitted_variants subdirectory if it exists (preserves variant type structure)
            splitted_dir = base_dir / "splitted_variants"
            if splitted_dir.exists() and splitted_dir.is_dir():
                source_dir = splitted_dir
            else:
                source_dir = base_dir
        else:
            source_dir = Path(source_dir)
        
        if log:
            to_nice_stdout()
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            to_nice_file(log_dir / "upload_clinvar.json", log_dir / "upload_clinvar.log")
        
        with start_action(
            action_type="upload_clinvar_to_hf",
            source_dir=str(source_dir),
            repo_id=repo_id,
            pattern=pattern
        ) as action:
            # Collect parquet files
            parquet_files = collect_parquet_files(source_dir, pattern=pattern)
            
            if not parquet_files:
                action.log(
                    message_type="warning",
                    reason="no_files_found",
                    source_dir=str(source_dir)
                )
                return {"uploaded_files": []}
            
            action.log(
                message_type="info",
                step="files_collected",
                num_files=len(parquet_files)
            )
            
            # Generate dataset card
            from genobear.preparation.dataset_card_generator import generate_clinvar_card
            
            # Detect variant types from directory structure
            variant_types = set()
            for f in parquet_files:
                try:
                    relative = f.relative_to(source_dir)
                    parts = relative.parts
                    if len(parts) > 1:
                        variant_types.add(parts[0])
                except ValueError:
                    pass
            
            total_size_gb = sum(f.stat().st_size for f in parquet_files) / (1024**3)
            dataset_card = generate_clinvar_card(
                num_files=len(parquet_files),
                total_size_gb=total_size_gb,
                variant_types=list(variant_types) if variant_types else None
            )
            
            action.log(
                message_type="info",
                step="dataset_card_generated",
                card_size=len(dataset_card),
                variant_types=list(variant_types) if variant_types else None
            )
            
            # Use upload_parquet_to_hf which handles directory structure preservation
            # This now uses batch upload - all files in ONE commit!
            from genobear.preparation.huggingface_uploader import upload_parquet_to_hf
            
            results = upload_parquet_to_hf(
                parquet_files=parquet_files,
                repo_id=repo_id,
                repo_type="dataset",
                token=token,
                path_prefix=path_prefix,
                source_dir=source_dir,  # Pass source_dir to preserve directory structure
                dataset_card_content=dataset_card,  # Include dataset card
                **kwargs
            )
            
            # Get results from batch upload
            uploaded_files = results.get("uploaded_files", [])
            num_uploaded = results.get("num_uploaded", 0)
            num_skipped = results.get("num_skipped", 0)
            
            action.log(
                message_type="summary",
                total_files=len(uploaded_files),
                uploaded=num_uploaded,
                skipped=num_skipped
            )
            
            return results

    @staticmethod
    def upload_ensembl_to_hf(
        source_dir: Optional[Path] = None,
        repo_id: str = "just-dna-seq/ensembl_variations",
        token: Optional[str] = None,
        pattern: str = "**/*.parquet",
        path_prefix: str = "data",
        workers: Optional[int] = None,
        log: bool = True,
        **kwargs
    ) -> dict:
        """Upload Ensembl variation parquet files to Hugging Face Hub.
        
        Only uploads files that differ in size from the remote versions,
        avoiding unnecessary data transfers.
        
        Args:
            source_dir: Source directory containing parquet files. If None, uses default cache
            repo_id: Hugging Face repository ID (default: just-dna-seq/ensembl_variations)
            token: Hugging Face API token. If None, uses HF_TOKEN env variable
            pattern: Glob pattern for finding parquet files (default: **/*.parquet)
            path_prefix: Prefix for paths in the repository (default: data)
            workers: Number of parallel workers (default from env or cpu_count)
            log: Enable logging
            **kwargs: Additional arguments passed to upload function
            
        Returns:
            Pipeline results dictionary with upload status for each file
        """
        from platformdirs import user_cache_dir
        
        if workers is None:
            workers = get_default_workers()
        
        # Determine source directory
        if source_dir is None:
            user_cache_path = Path(user_cache_dir(appname="genobear"))
            default_name = "ensembl_variations"
            base_dir = user_cache_path / default_name
            # Prefer splitted_variants subdirectory if it exists (preserves variant type structure)
            splitted_dir = base_dir / "splitted_variants"
            if splitted_dir.exists() and splitted_dir.is_dir():
                source_dir = splitted_dir
            else:
                source_dir = base_dir
        else:
            source_dir = Path(source_dir)
        
        if log:
            to_nice_stdout()
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            to_nice_file(log_dir / "upload_ensembl.json", log_dir / "upload_ensembl.log")
        
        with start_action(
            action_type="upload_ensembl_to_hf",
            source_dir=str(source_dir),
            repo_id=repo_id,
            pattern=pattern
        ) as action:
            # Collect parquet files
            parquet_files = collect_parquet_files(source_dir, pattern=pattern)
            
            if not parquet_files:
                action.log(
                    message_type="warning",
                    reason="no_files_found",
                    source_dir=str(source_dir)
                )
                return {"uploaded_files": []}
            
            action.log(
                message_type="info",
                step="files_collected",
                num_files=len(parquet_files)
            )
            
            # Generate dataset card
            from genobear.preparation.dataset_card_generator import generate_ensembl_card
            
            # Detect variant types from directory structure
            variant_types = set()
            for f in parquet_files:
                try:
                    relative = f.relative_to(source_dir)
                    parts = relative.parts
                    if len(parts) > 1:
                        variant_types.add(parts[0])
                except ValueError:
                    pass
            
            total_size_gb = sum(f.stat().st_size for f in parquet_files) / (1024**3)
            dataset_card = generate_ensembl_card(
                num_files=len(parquet_files),
                total_size_gb=total_size_gb,
                variant_types=list(variant_types) if variant_types else None
            )
            
            action.log(
                message_type="info",
                step="dataset_card_generated",
                card_size=len(dataset_card),
                variant_types=list(variant_types) if variant_types else None
            )
            
            # Use upload_parquet_to_hf which handles directory structure preservation
            # This now uses batch upload - all files in ONE commit!
            from genobear.preparation.huggingface_uploader import upload_parquet_to_hf
            
            results = upload_parquet_to_hf(
                parquet_files=parquet_files,
                repo_id=repo_id,
                repo_type="dataset",
                token=token,
                path_prefix=path_prefix,
                source_dir=source_dir,  # Pass source_dir to preserve directory structure
                dataset_card_content=dataset_card,  # Include dataset card
                **kwargs
            )
            
            # Get results from batch upload
            uploaded_files = results.get("uploaded_files", [])
            num_uploaded = results.get("num_uploaded", 0)
            num_skipped = results.get("num_skipped", 0)
            
            action.log(
                message_type="summary",
                total_files=len(uploaded_files),
                uploaded=num_uploaded,
                skipped=num_skipped
            )
            
            return results
