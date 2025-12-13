"""Ensembl annotations and downloads."""

import os
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Optional

import polars as pl
from eliot import start_action
from huggingface_hub import snapshot_download
from platformdirs import user_cache_dir
from pipefunc import pipefunc

from genobear.annotation.chromosomes import (
    detect_chrom_style_from_values,
    rewrite_chromosome_column_strip_chr_prefix,
    rewrite_chromosome_column_to_chr_prefixed,
)


def _configure_polars_memory_efficient() -> None:
    """
    Configure Polars for memory-efficient operations.
    
    This complements POLARS_ENGINE_AFFINITY=streaming (set in CLI entry points)
    by tuning streaming chunk size for better memory control.
    """
    # Set streaming chunk size (in number of rows) for better memory control
    # Smaller chunks = lower peak memory, but may be slightly slower
    # Note: POLARS_ENGINE_AFFINITY=streaming is the primary mechanism (set in CLI)
    try:
        pl.Config.set_streaming_chunk_size(50_000)
    except AttributeError:
        # Older Polars versions may not have this setting
        pass


# Configure Polars for memory efficiency by default
_configure_polars_memory_efficient()


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


@lru_cache(maxsize=4096)
def _get_chromosomes_in_file(parquet_file: Path, chrom_col: str = "chrom") -> set[str]:
    """
    Get unique chromosome values from a parquet file by scanning the chromosome column.

    This is memory-efficient: we only read the chrom column and get unique values.
    """
    chroms = (
        pl.scan_parquet(parquet_file)
        .select(pl.col(chrom_col).cast(pl.Utf8).unique())
        .collect()
        .get_column(chrom_col)
        .to_list()
    )
    return {c for c in chroms if c is not None}


def _annotate_single_chromosome_file(
    input_lf: pl.LazyFrame,
    ensembl_file: Path,
    join_columns: list[str],
    chrom_col: str,
    output_file: Path,
    compression: str,
) -> int:
    """
    Annotate input with a single Ensembl chromosome file and write output.

    Args:
        input_lf: Input LazyFrame (already filtered to matching chromosomes)
        ensembl_file: Path to single Ensembl parquet file
        join_columns: Columns to join on
        chrom_col: Chromosome column name
        output_file: Output parquet file path
        compression: Compression type

    Returns:
        Number of rows written
    """
    # Scan the single Ensembl file
    ensembl_lf = pl.scan_parquet(ensembl_file)

    # Semi-join to filter Ensembl to only matching keys (keeps build side small)
    input_keys_lf = input_lf.select(join_columns).unique()
    ensembl_filtered_lf = ensembl_lf.join(
        input_keys_lf,
        on=join_columns,
        how="semi",
    )

    # Left join to keep all input records
    annotated_lf = input_lf.join(
        ensembl_filtered_lf,
        on=join_columns,
        how="left",
        suffix="_ensembl"
    )

    # Write output using streaming engine for memory efficiency
    output_file.parent.mkdir(parents=True, exist_ok=True)
    annotated_lf.sink_parquet(
        output_file,
        compression=compression,
        engine="streaming",
    )

    # Return row count for logging
    return pl.scan_parquet(output_file).select(pl.len()).collect().item()


@pipefunc(output_name="annotated_dataframe", renames={"input_dataframe": "vcf_lazy_frame"}, cache=False)
def annotate_with_ensembl(
    input_dataframe: pl.LazyFrame,
    ensembl_cache_path: Path,
    join_columns: Optional[list[str]] = None,
    variant_type: str = "SNV",
    output_path: Optional[Path] = None,
    compression: str = "zstd",
) -> pl.LazyFrame:
    """
    Annotate a polars LazyFrame with Ensembl variations data.

    This function processes per-chromosome-file to reduce memory usage.
    For each Ensembl chromosome file:
    1. Filter input to rows with matching chromosome(s) using is_in
    2. Join with that chromosome's Ensembl data
    3. Write output per-chromosome to a temporary folder
    4. Scan the output folder to return a unified LazyFrame

    Args:
        input_dataframe: Input LazyFrame to annotate
        ensembl_cache_path: Path to Ensembl cache (should be already downloaded)
        join_columns: Columns to join on (default: ["chrom", "start", "ref", "alt"])
        variant_type: Variant type directory to use (default: "SNV")
        output_path: Optional output path to write the joined result (single file)
                     If not provided, returns LazyFrame scanning temp folder
        compression: Compression type for output parquet (default: "zstd")

    Returns:
        Annotated LazyFrame scanning the output files

    Example:
        >>> lf = pl.scan_parquet("input.parquet")
        >>> annotated = annotate_with_ensembl(lf, cache_path, output_path=Path("output.parquet"))
    """
    with start_action(
        action_type="annotate_with_ensembl",
        ensembl_cache_path=str(ensembl_cache_path),
        variant_type=variant_type,
        has_output_path=output_path is not None,
    ) as action:
        input_lf = input_dataframe

        # Default join columns
        if join_columns is None:
            join_columns = ["chrom", "start", "ref", "alt"]

        chrom_col = "chrom" if "chrom" in join_columns else None

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

        parquet_files = sorted(variant_dir.glob("*.parquet"))
        if not parquet_files:
            action.log(
                message_type="warning",
                step="no_parquet_files_found",
                variant_dir=str(variant_dir),
            )
            # Return original dataframe if no annotation files found
            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                input_lf.sink_parquet(
                    output_path,
                    compression=compression,
                    engine="streaming",
                )
            return input_lf

        # Detect chromosome naming style from first Ensembl file
        first_file_chroms = _get_chromosomes_in_file(parquet_files[0], chrom_col or "chrom")
        reference_has_chr = any(c.lower().startswith("chr") for c in first_file_chroms if c)

        # Get input chromosome style and unique values (one collect on small input)
        from genobear.annotation.chromosomes import (
            get_input_chrom_style_and_values,
            normalize_chrom_value,
        )
        input_style, input_chrom_values = get_input_chrom_style_and_values(input_lf, chrom_col or "chrom")
        input_has_chr = input_style == "chr_prefixed"

        # Determine if we need to rewrite input chromosomes
        rewrite_applied: str | None = None
        if reference_has_chr and not input_has_chr:
            input_lf = rewrite_chromosome_column_to_chr_prefixed(input_lf, chrom_col=chrom_col or "chrom")
            rewrite_applied = "to_chr_prefixed"
            # Normalize input chrom values to match
            input_chrom_values = {normalize_chrom_value(c, "chr_prefixed") for c in input_chrom_values}
        elif (not reference_has_chr) and input_has_chr:
            input_lf = rewrite_chromosome_column_strip_chr_prefix(input_lf, chrom_col=chrom_col or "chrom")
            rewrite_applied = "strip_chr_prefix"
            input_chrom_values = {normalize_chrom_value(c, "no_prefix") for c in input_chrom_values}

        action.log(
            message_type="info",
            step="chromosome_rewrite_check",
            applied=rewrite_applied is not None,
            rewrite=rewrite_applied,
            input_chromosomes=sorted(input_chrom_values),
            num_ensembl_files=len(parquet_files),
        )

        # Determine output folder for per-chromosome files
        if output_path:
            output_path = Path(output_path)
            # Use a temp folder next to output for per-chromosome files
            output_folder = output_path.parent / f".{output_path.stem}_parts"
        else:
            # Use a temp folder in the current directory
            import tempfile
            output_folder = Path(tempfile.mkdtemp(prefix="ensembl_annotated_"))

        output_folder.mkdir(parents=True, exist_ok=True)

        # Collect the input once, then filter per chromosome in-memory
        # This avoids re-collecting for each chromosome file
        input_df = input_lf.collect()
        total_input_rows = len(input_df)

        processed_files = []
        total_annotated_rows = 0
        skipped_files = 0

        for ensembl_file in parquet_files:
            # Get chromosomes in this Ensembl file
            file_chroms = _get_chromosomes_in_file(ensembl_file, chrom_col or "chrom")

            # Check if any input chromosomes match
            matching_chroms = input_chrom_values.intersection(file_chroms)
            if not matching_chroms:
                skipped_files += 1
                continue

            # Filter input to only rows with matching chromosomes
            filtered_input_df = input_df.filter(
                pl.col(chrom_col or "chrom").is_in(list(matching_chroms))
            )
            if filtered_input_df.is_empty():
                skipped_files += 1
                continue

            # Convert back to lazy for join
            filtered_input_lf = filtered_input_df.lazy()

            # Output file for this chromosome
            chrom_output_file = output_folder / ensembl_file.name

            # Process this chromosome file
            rows_written = _annotate_single_chromosome_file(
                input_lf=filtered_input_lf,
                ensembl_file=ensembl_file,
                join_columns=join_columns,
                chrom_col=chrom_col or "chrom",
                output_file=chrom_output_file,
                compression=compression,
            )

            processed_files.append(chrom_output_file)
            total_annotated_rows += rows_written

        action.log(
            message_type="info",
            step="per_chromosome_processing_complete",
            total_input_rows=total_input_rows,
            total_annotated_rows=total_annotated_rows,
            processed_files=len(processed_files),
            skipped_files=skipped_files,
        )

        # Handle case where no files were processed (no matching chromosomes)
        if not processed_files:
            action.log(
                message_type="warning",
                step="no_matching_chromosomes",
            )
            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                # Use lazy frame with streaming sink for memory efficiency
                input_df.lazy().sink_parquet(
                    output_path,
                    compression=compression,
                    engine="streaming",
                )
            # Clean up empty output folder
            if output_folder.exists():
                shutil.rmtree(output_folder)
            return input_df.lazy()

        # Scan the output folder as final result
        result_lf = pl.scan_parquet(str(output_folder / "*.parquet"))

        # If output_path is specified, consolidate to single file
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            result_lf.sink_parquet(
                output_path,
                compression=compression,
                engine="streaming",
            )
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            action.log(
                message_type="info",
                step="consolidated_output",
                output_path=str(output_path),
                file_size_mb=round(file_size_mb, 2),
            )
            # Clean up temp folder
            shutil.rmtree(output_folder)
            # Return scan of final file
            result_lf = pl.scan_parquet(output_path)

        return result_lf
