"""Ensembl annotations and downloads."""

import os
from pathlib import Path
from typing import Optional

import polars as pl
from eliot import start_action
from huggingface_hub import snapshot_download
from platformdirs import user_cache_dir
from pipefunc import pipefunc


@pipefunc(output_name="ensembl_cache_path", cache=True)
def download_ensembl_annotations(
    repo_id: str = "just-dna-seq/ensembl_variations",
    cache_dir: Optional[Path] = None,
    token: Optional[str] = None,
    force_download: bool = False,
    allow_patterns: Optional[list[str]] = None,
) -> Path:
    """
    Download ensembl_variations dataset from HuggingFace Hub to local cache.
    
    If the cache directory already exists and force_download is False, the download is skipped.
    
    Args:
        repo_id: HuggingFace repository ID (default: just-dna-seq/ensembl_variations)
        cache_dir: Local cache directory. If None, uses ~/.cache/genobear/ensembl_variations/splitted_variants
        token: HuggingFace API token. If None, uses HF_TOKEN env variable or public access
        force_download: If True, download even if cache exists
        allow_patterns: List of glob patterns to filter files to download (e.g., ["data/SNV/*.parquet"])
        
    Returns:
        Path to the local cache directory containing downloaded parquet files
        
    Example:
        >>> cache_path = download_ensembl_annotations()
        >>> print(f"Downloaded to: {cache_path}")
        >>> # Skip download if already exists
        >>> cache_path = download_ensembl_annotations(force_download=False)
    """
    with start_action(
        action_type="download_ensembl_annotations",
        repo_id=repo_id,
        force_download=force_download
    ) as action:
        # Determine cache directory
        if cache_dir is None:
            # Check for environment variable override
            env_cache = os.getenv("GENOBEAR_CACHE_DIR")
            if env_cache:
                cache_dir = Path(env_cache) / "ensembl_variations" / "splitted_variants"
            else:
                user_cache_path = Path(user_cache_dir(appname="genobear"))
                cache_dir = user_cache_path / "ensembl_variations" / "splitted_variants"
        else:
            cache_dir = Path(cache_dir)
        
        action.log(
            message_type="info",
            step="cache_dir_determined",
            cache_dir=str(cache_dir)
        )
        
        # Check if cache exists and skip download if not forced
        if cache_dir.exists() and not force_download:
            parquet_file = next(cache_dir.rglob("*.parquet"), None)
            if parquet_file is not None:
                action.log(
                    message_type="info",
                    step="cache_exists_skip_download",
                    first_parquet_file=str(parquet_file),
                )
                return cache_dir
        
        action.log(
            message_type="info",
            step="downloading_from_hf",
            repo_id=repo_id
        )
        
        # Download from HuggingFace Hub
        # snapshot_download returns the path to the downloaded snapshot
        # We specify local_dir to control where files are extracted
        downloaded_path = snapshot_download(
            repo_id=repo_id,
            repo_type="dataset",
            local_dir=cache_dir,
            local_dir_use_symlinks=False,  # Copy files instead of symlinks for reliability
            token=token,
            allow_patterns=allow_patterns or ["data/**/*.parquet"],  # Only download parquet files from data folder
        )
        
        action.log(
            message_type="info",
            step="download_complete",
            downloaded_path=str(downloaded_path)
        )
        
        return Path(downloaded_path)


@pipefunc(output_name="annotated_dataframe", renames={"input_dataframe": "vcf_lazy_frame"}, cache=False)
def annotate_with_ensembl(
    input_dataframe: pl.LazyFrame,
    ensembl_cache_path: Path,
    join_columns: Optional[list[str]] = None,
    variant_type: str = "SNV",
    output_path: Optional[Path] = None,
    compression: str = "zstd",
    input_is_sorted: bool = True,
    save_vortex: bool = False,
) -> pl.LazyFrame:
    """
    Annotate a polars LazyFrame with Ensembl variations data.
    
    This function takes an input dataframe (lazy), scans the Ensembl cache,
    performs a join, and optionally writes the result using streaming engine.
    
    Args:
        input_dataframe: Input LazyFrame to annotate
        ensembl_cache_path: Path to Ensembl cache (should be already downloaded)
        join_columns: Columns to join on (default: ["chrom", "start", "ref", "alt"])
        variant_type: Variant type directory to use (default: "SNV")
        output_path: Optional output path to write the joined result
        compression: Compression type for output parquet (default: "zstd")
        input_is_sorted: Whether input data is sorted (default: True)
        save_vortex: If True, convert output to Vortex format
        
    Returns:
        Annotated LazyFrame (or the same LazyFrame if output_path is provided,
        since data is written using sink_parquet)
        
    Example:
        >>> lf = pl.scan_parquet("input.parquet")
        >>> annotated = annotate_with_ensembl(lf, cache_path, output_path=Path("output.parquet"))
    """
    with start_action(
        action_type="annotate_with_ensembl",
        ensembl_cache_path=str(ensembl_cache_path),
        variant_type=variant_type,
        has_output_path=output_path is not None
    ) as action:
        # Default join columns
        if join_columns is None:
            join_columns = ["chrom", "start", "ref", "alt"]
        
        action.log(
            message_type="info",
            step="preparing_ensembl_scan",
            join_columns=join_columns
        )
        
        # Determine variant directory
        variant_dir = ensembl_cache_path / variant_type
        if not variant_dir.exists():
            variant_dir = ensembl_cache_path / "data" / variant_type
        
        if not variant_dir.exists():
            action.log(
                message_type="error",
                step="variant_dir_not_found",
                variant_dir=str(variant_dir)
            )
            raise FileNotFoundError(f"Variant directory not found: {variant_dir}")
        
        parquet_glob = str(variant_dir / "*.parquet")
        first_parquet_file = next(variant_dir.glob("*.parquet"), None)
        if first_parquet_file is None:
            action.log(
                message_type="warning",
                step="no_parquet_files_found",
                variant_dir=str(variant_dir)
            )
            # Return original dataframe if no annotation files found
            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                input_dataframe.sink_parquet(output_path, compression=compression)
                action.log(
                    message_type="info",
                    step="saved_unannotated",
                    output_path=str(output_path)
                )
            return input_dataframe
        
        action.log(
            message_type="info",
            step="scanning_ensembl_files",
            parquet_glob=parquet_glob,
            first_parquet_file=str(first_parquet_file),
        )
        ensembl_lf = pl.scan_parquet(parquet_glob)
        
        # Perform left join to keep all input records
        annotated_lf = input_dataframe.join(
            ensembl_lf,
            on=join_columns,
            how="left",
            suffix="_ensembl"
        )
        
        action.log(
            message_type="info",
            step="join_complete"
        )
        
        # Write using streaming engine if output_path is provided
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            action.log(
                message_type="info",
                step="writing_with_streaming",
                output_path=str(output_path),
                compression=compression
            )
            
            # Use sink_parquet for memory-efficient streaming write
            annotated_lf.sink_parquet(
                output_path,
                compression=compression,
                engine="streaming"
            )
            
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            action.log(
                message_type="info",
                step="write_complete",
                output_path=str(output_path),
                file_size_mb=round(file_size_mb, 2)
            )
            
            # Convert to Vortex if requested
            if save_vortex:
                from genobear.vortex.parquet_to_vortex import parquet_to_vortex as _parquet_to_vortex
                
                vortex_path = output_path.with_suffix(".vortex")
                
                action.log(
                    message_type="info",
                    step="converting_to_vortex",
                    vortex_path=str(vortex_path)
                )
                
                vortex_output = _parquet_to_vortex(
                    parquet_path=output_path,
                    vortex_path=vortex_path,
                    overwrite=True,
                )
                
                vortex_size_mb = vortex_output.stat().st_size / (1024 * 1024)
                compression_ratio = (1 - vortex_size_mb / file_size_mb) * 100 if file_size_mb > 0 else 0
                
                action.log(
                    message_type="info",
                    step="vortex_conversion_complete",
                    vortex_path=str(vortex_output),
                    vortex_size_mb=round(vortex_size_mb, 2),
                    compression_ratio=round(compression_ratio, 1)
                )
        return annotated_lf
