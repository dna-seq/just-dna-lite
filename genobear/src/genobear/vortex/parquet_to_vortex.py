"""Convert Ensembl parquet files to Vortex format for efficient storage and querying."""

from pathlib import Path
from typing import Optional, Union
import polars as pl
import vortex as vx
from eliot import start_action


def parquet_to_vortex(
    parquet_path: Union[str, Path],
    vortex_path: Optional[Union[str, Path]] = None,
    overwrite: bool = False,
    batch_size: int = 100_000,
) -> Path:
    """
    Convert a single parquet file to Vortex format using true streaming to handle large files.
    
    This function uses PyArrow's RecordBatchReader with a generator to stream the data in batches,
    avoiding loading the entire file into memory at any point. This is essential for multi-gigabyte files.
    Uses compact compression by default for optimal storage efficiency.
    
    The streaming approach ensures constant memory usage regardless of file size, making it suitable
    for converting very large genomic datasets without running out of memory.
    
    Args:
        parquet_path: Path to the input parquet file
        vortex_path: Path where to save the Vortex file. If None, saves next to parquet with .vortex extension
        overwrite: Whether to overwrite existing Vortex file (default False)
        batch_size: Number of rows per batch for streaming (default 100,000)
        
    Returns:
        Path to the created Vortex file
        
    Example:
        >>> parquet_path = Path("data/large_variants.parquet")
        >>> vortex_path = parquet_to_vortex(parquet_path, batch_size=100_000)
        >>> print(f"Converted to: {vortex_path}")
    """
    with start_action(
        action_type="parquet_to_vortex",
        parquet_path=str(parquet_path),
        vortex_path=str(vortex_path) if vortex_path else None,
        overwrite=overwrite,
        batch_size=batch_size
    ) as action:
        import pyarrow.parquet as pq
        
        parquet_path = Path(parquet_path)
        
        # Determine output path
        if vortex_path is None:
            output_path = parquet_path.with_suffix('.vortex')
        else:
            output_path = Path(vortex_path)
        
        action.log(
            message_type="info",
            step="output_path_determined",
            output_path=str(output_path)
        )
        
        # If vortex file already exists and overwrite is False, skip conversion
        if output_path.exists() and not overwrite:
            action.log(
                message_type="info",
                step="vortex_exists_skip_conversion",
                path=str(output_path)
            )
            return output_path
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        action.log(
            message_type="info",
            step="opening_parquet_for_streaming",
            parquet_path=str(parquet_path),
            batch_size=batch_size
        )
        
        # Open parquet file for streaming
        parquet_file = pq.ParquetFile(str(parquet_path))
        
        # Get metadata
        num_rows = parquet_file.metadata.num_rows
        num_batches = (num_rows + batch_size - 1) // batch_size
        
        action.log(
            message_type="info",
            step="parquet_metadata",
            num_rows=num_rows,
            num_row_groups=parquet_file.metadata.num_row_groups,
            estimated_batches=num_batches
        )
        
        # Create a RecordBatchReader for streaming
        # This reads the data lazily without loading everything into memory
        action.log(
            message_type="info",
            step="streaming_to_vortex",
            output_path=str(output_path)
        )
        
        # Write directly using RecordBatchReader - Vortex handles streaming
        # We need to create a proper RecordBatchReader from the iterator
        import pyarrow as pa
        
        # Get the schema first
        schema = parquet_file.schema_arrow
        
        # Create a generator function for true streaming (no materialization)
        def batch_iter():
            for batch in parquet_file.iter_batches(batch_size=batch_size):
                yield batch
        
        # Create RecordBatchReader from the generator
        record_batch_reader = pa.RecordBatchReader.from_batches(schema, batch_iter())
        
        # Write to Vortex file using streaming with compact compression
        write_options = vx.io.VortexWriteOptions.compact()
        write_options.write_path(record_batch_reader, str(output_path))
        
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        parquet_size_mb = parquet_path.stat().st_size / (1024 * 1024)
        
        action.log(
            message_type="info",
            step="conversion_complete",
            output_path=str(output_path),
            parquet_size_mb=round(parquet_size_mb, 2),
            vortex_size_mb=round(file_size_mb, 2),
            compression_ratio=round((1 - file_size_mb / parquet_size_mb) * 100, 1) if parquet_size_mb > 0 else 0
        )
        
        return output_path


def convert_ensembl_directory_to_vortex(
    ensembl_cache_path: Path,
    variant_type: str = "SNV",
    output_dir: Optional[Path] = None,
    overwrite: bool = False,
    batch_size: int = 100_000,
    max_workers: Optional[int] = None,
) -> Path:
    """
    Convert all Ensembl parquet files in a directory to Vortex format using streaming.
    
    This function scans a directory containing Ensembl annotation parquet files
    and converts them all to Vortex format for improved query performance.
    Uses streaming to handle large multi-gigabyte files efficiently.
    
    Args:
        ensembl_cache_path: Path to Ensembl cache directory (containing variant type subdirectories)
        variant_type: Variant type directory to convert (default: "SNV")
        output_dir: Optional output directory for Vortex files. If None, saves next to parquet files
        overwrite: Whether to overwrite existing Vortex files (default False)
        batch_size: Number of rows per batch for streaming (default 100,000)
        max_workers: Number of parallel workers for conversion (default: None = sequential)
        
    Returns:
        Path to the directory containing converted Vortex files
        
    Example:
        >>> cache_path = Path("~/.cache/genobear/ensembl_variations/splitted_variants")
        >>> vortex_dir = convert_ensembl_directory_to_vortex(cache_path, "SNV", batch_size=50000)
        >>> print(f"Converted files in: {vortex_dir}")
    """
    with start_action(
        action_type="convert_ensembl_directory_to_vortex",
        ensembl_cache_path=str(ensembl_cache_path),
        variant_type=variant_type,
        output_dir=str(output_dir) if output_dir else None,
        batch_size=batch_size
    ) as action:
        
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
        
        # Find all parquet files in the variant directory
        parquet_files = list(variant_dir.glob("*.parquet"))
        
        if not parquet_files:
            action.log(
                message_type="warning",
                step="no_parquet_files_found",
                variant_dir=str(variant_dir)
            )
            return variant_dir
        
        action.log(
            message_type="info",
            step="found_parquet_files",
            num_files=len(parquet_files)
        )
        
        # Determine output directory
        if output_dir is None:
            vortex_output_dir = variant_dir
        else:
            vortex_output_dir = Path(output_dir)
            vortex_output_dir.mkdir(parents=True, exist_ok=True)
        
        action.log(
            message_type="info",
            step="starting_conversion",
            output_dir=str(vortex_output_dir),
            num_files=len(parquet_files)
        )
        
        # Convert each parquet file to vortex
        converted_files = []
        for idx, parquet_file in enumerate(parquet_files, 1):
            with start_action(
                action_type="convert_file",
                file_index=idx,
                total_files=len(parquet_files),
                parquet_file=str(parquet_file)
            ):
                if output_dir is None:
                    vortex_file_path = parquet_file.with_suffix('.vortex')
                else:
                    vortex_file_path = vortex_output_dir / f"{parquet_file.stem}.vortex"
                
                try:
                    result_path = parquet_to_vortex(
                        parquet_path=parquet_file,
                        vortex_path=vortex_file_path,
                        overwrite=overwrite,
                        batch_size=batch_size,
                    )
                    converted_files.append(result_path)
                except Exception as e:
                    action.log(
                        message_type="error",
                        step="conversion_failed",
                        parquet_file=str(parquet_file),
                        error=str(e)
                    )
                    # Continue with other files
                    continue
        
        action.log(
            message_type="info",
            step="conversion_complete",
            total_files=len(parquet_files),
            converted_files=len(converted_files),
            failed_files=len(parquet_files) - len(converted_files),
            output_dir=str(vortex_output_dir)
        )
        
        return vortex_output_dir


def read_vortex_with_polars(
    vortex_path: Union[str, Path],
    columns: Optional[list[str]] = None,
    filter_expr: Optional[pl.Expr] = None,
) -> pl.LazyFrame:
    """
    Read a Vortex file using Polars with efficient column and row filtering.
    
    Args:
        vortex_path: Path to the Vortex file
        columns: Optional list of columns to select
        filter_expr: Optional Polars expression for row filtering
        
    Returns:
        Polars LazyFrame with the data from the Vortex file
        
    Example:
        >>> vortex_path = Path("data/variants.vortex")
        >>> lf = read_vortex_with_polars(vortex_path, columns=['chrom', 'start', 'ref', 'alt'])
        >>> lf = lf.filter(pl.col('chrom') == 'chr1')
        >>> df = lf.collect()
    """
    with start_action(
        action_type="read_vortex_with_polars",
        vortex_path=str(vortex_path)
    ) as action:
        vortex_path = Path(vortex_path)
        
        if not vortex_path.exists():
            action.log(
                message_type="error",
                step="vortex_file_not_found",
                vortex_path=str(vortex_path)
            )
            raise FileNotFoundError(f"Vortex file not found: {vortex_path}")
        
        action.log(
            message_type="info",
            step="opening_vortex_file"
        )
        
        # Open Vortex file and convert to Arrow dataset
        ds = vx.open(str(vortex_path)).to_dataset()
        
        # Scan the dataset with Polars
        lf = pl.scan_pyarrow_dataset(ds)
        
        # Apply column selection if specified
        if columns:
            lf = lf.select(columns)
            action.log(
                message_type="info",
                step="columns_selected",
                columns=columns
            )
        
        # Apply filter if specified
        if filter_expr is not None:
            lf = lf.filter(filter_expr)
            action.log(
                message_type="info",
                step="filter_applied"
            )
        
        action.log(
            message_type="info",
            step="vortex_file_opened_successfully"
        )
        
        return lf



