from pathlib import Path
from typing import Union, Optional, Literal, Tuple, TypeVar
import polars as pl
import polars_bio as pb
from eliot import start_action
import os
import pooch
import tempfile

# Type variable for generic data types
T = TypeVar('T')

# Generic type for results that include both data and the file path where it's saved
AnnotatedResult = Tuple[T, Path]

# Specific type alias for LazyFrame results with their parquet paths
AnnotatedLazyFrame = AnnotatedResult[pl.LazyFrame]

# Type alias describing how parquet saving is configured:
# - None: do not save
# - "auto": save next to the input, replacing .vcf/.vcf.gz with .parquet
# - Path: save to the provided absolute/relative path
SaveParquet = Union[Path, Literal["auto"], None]

def _default_parquet_path(vcf_path: Path) -> Path:
    """Generate default parquet path next to VCF file."""
    # Remove .vcf or .vcf.gz extension before adding .parquet
    if vcf_path.suffixes == ['.vcf', '.gz']:
        # Handle .vcf.gz files
        return vcf_path.with_suffix('').with_suffix('.parquet')
    elif vcf_path.suffix == '.vcf':
        # Handle .vcf files
        return vcf_path.with_suffix('.parquet')
    else:
        # Fallback for other file types
        return vcf_path.with_suffix('.parquet')


def resolve_just_dna_pipelines_subfolder(subdir_name: str, base: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolve a subfolder path for just-dna-pipelines data storage.
    
    This function provides a consistent way to resolve data storage paths across
    the just-dna-pipelines package, respecting the JUST_DNA_PIPELINES_FOLDER environment variable.
    
    Args:
        subdir_name: Name of the subdirectory to create/use
        base: Base directory path. If None, uses JUST_DNA_PIPELINES_FOLDER env var or defaults to "just-dna-pipelines"
        
    Returns:
        Absolute path to the resolved subfolder
        
    Examples:
        >>> # Using default base (JUST_DNA_PIPELINES_FOLDER env var or "just-dna-pipelines")
        >>> resolve_just_dna_pipelines_subfolder("downloads")
        PosixPath('/home/user/.cache/just-dna-pipelines/downloads')
        
        >>> # Using custom base
        >>> resolve_just_dna_pipelines_subfolder("vcf_files", "/tmp/myproject")
        PosixPath('/tmp/myproject/vcf_files')
    """
    if base is None:
        base = os.getenv("JUST_DNA_PIPELINES_FOLDER", "just-dna-pipelines")
    
    base_path = Path(base)
    
    # If it's just a name (no path separators), use OS cache
    if len(base_path.parts) == 1 and not base_path.is_absolute():
        cache_path = Path(pooch.os_cache(str(base_path))) / subdir_name
    else:
        cache_path = base_path / subdir_name
        
    return cache_path.resolve()


def get_info_fields(vcf_path: str) -> list[str]:
    """
    Extract INFO field names from a VCF file header by parsing the header directly.
    
    Args:
        vcf_path: Path to the VCF file
        
    Returns:
        List of INFO field names found in the header
    """
    with start_action(action_type="get_info_fields", vcf_path=vcf_path) as action:
        try:
            import gzip
            info_fields = []
            
            # Determine if file is gzipped
            open_func = gzip.open if vcf_path.endswith('.gz') else open
            mode = 'rt' if vcf_path.endswith('.gz') else 'r'
            
            with open_func(vcf_path, mode) as f:
                for line in f:
                    line = line.strip()
                    # Stop when we reach the data (non-header lines)
                    if not line.startswith('#'):
                        break
                    # Look for INFO field definitions
                    if line.startswith('##INFO=<ID='):
                        # Extract the ID from ##INFO=<ID=FIELD_NAME,...>
                        start_idx = line.find('ID=') + 3
                        end_idx = line.find(',', start_idx)
                        if end_idx == -1:  # In case there's no comma after ID
                            end_idx = line.find('>', start_idx)
                        if end_idx > start_idx:
                            field_name = line[start_idx:end_idx]
                            info_fields.append(field_name)
            
            action.log(
                message_type="info",
                step="info_fields_extracted",
                count=len(info_fields),
                fields=info_fields
            )
            return info_fields
            
        except Exception as e:
            action.log(
                message_type="error",
                step="info_fields_extraction_failed",
                error=str(e)
            )
            # Return empty list if extraction fails
            return []


def _cast_format_field(field: str, expr: pl.Expr) -> pl.Expr:
    """
    Cast a FORMAT field expression to its proper type based on VCF spec.
    
    VCF FORMAT field types:
    - GT: String (genotype indices like "0/1")
    - GQ: Int64 (genotype quality, Phred-scaled)
    - DP: Int64 (read depth)
    - MIN_DP: Int64 (minimum read depth in GVCF block)
    - AD: List[Int64] (allelic depths, comma-separated e.g., "30,25")
    - VAF: List[Float64] (variant allele fractions, can be multi-valued for multi-allelic sites)
    - PL: List[Int64] (Phred-scaled likelihoods, comma-separated)
    - QD: Float64 (quality by depth - though usually in INFO, not FORMAT)
    """
    field_upper = field.upper()
    
    # Integer fields
    if field_upper in ("GQ", "DP", "MIN_DP"):
        return (
            pl.when(expr == ".")
            .then(pl.lit(None))
            .otherwise(expr.cast(pl.Int64))
            .alias(field)
        )
    
    # Float fields (single value)
    if field_upper in ("QD",):
        return (
            pl.when(expr == ".")
            .then(pl.lit(None))
            .otherwise(expr.cast(pl.Float64))
            .alias(field)
        )
    
    # List of floats (comma-separated) - VAF can have multiple values for multi-allelic sites
    if field_upper in ("VAF",):
        return (
            pl.when(expr == ".")
            .then(pl.lit(None))
            .otherwise(
                expr.str.split(",").list.eval(
                    pl.when(pl.element() == ".")
                    .then(pl.lit(None))
                    .otherwise(pl.element().cast(pl.Float64))
                )
            )
            .alias(field)
        )
    
    # List of integers (comma-separated)
    if field_upper in ("AD", "PL"):
        return (
            pl.when(expr == ".")
            .then(pl.lit(None))
            .otherwise(
                expr.str.split(",").list.eval(
                    pl.when(pl.element() == ".")
                    .then(pl.lit(None))
                    .otherwise(pl.element().cast(pl.Int64))
                )
            )
            .alias(field)
        )
    
    # Default: keep as string (GT and others)
    return expr.alias(field)


def _compute_genotype_expr(gt_col: str = "GT", ref_col: str = "ref", alt_col: str = "alt") -> pl.Expr:
    """
    Compute genotype as List[String] from GT indices and REF/ALT alleles.
    
    Pure Polars expression for lazy evaluation. Maps GT indices (e.g., "0/1") 
    to actual alleles using REF and ALT columns. Result is sorted alphabetically.
    
    Handles:
    - Missing values by extracting only numeric indices from GT string
    - Multi-allelic sites by splitting ALT on comma (e.g., "G,T" → ["G", "T"])
    
    Examples:
        - GT="0/1", REF="A", ALT="G" → ["A", "G"]
        - GT="1/1", REF="C", ALT="T" → ["T", "T"]
        - GT="1/2", REF="A", ALT="G,T" → ["G", "T"]
        - GT="./.", REF="G", ALT="A" → [] (empty list for missing)
    """
    # Extract only numeric indices from GT using regex (avoids "." cast issues)
    # Pattern matches one or more digits
    gt_indices = (
        pl.col(gt_col)
        .str.extract_all(r"\d+")
        .list.eval(pl.element().cast(pl.Int64))
    )
    
    # Build alleles array: [REF, ALT1, ALT2, ...] for multi-allelic support
    # polars-bio uses "|" as separator for multi-allelic ALT (e.g., "G|T")
    # Use str.split("|") on both to create lists, then concat
    # REF has no pipe, so split creates single-element list
    alleles = pl.concat_list(
        pl.col(ref_col).str.split("|"),
        pl.col(alt_col).str.split("|")
    )
    
    # Gather alleles by indices and sort alphabetically
    return (
        alleles
        .list.gather(gt_indices)
        .list.sort()
        .alias("genotype")
    )


def scan_vcf_with_formats(
    path: str,
    info_fields: Optional[list[str]] = None,
    format_fields: list[str] = ["GT", "GQ", "DP", "AD", "VAF", "PL"],
    thread_num: int = 1,
    chunk_size: int = 8,
    concurrent_fetches: int = 1,
    allow_anonymous: bool = True,
    enable_request_payer: bool = False,
    max_retries: int = 5,
    timeout: int = 300,
    compression_type: str = "auto",
    projection_pushdown: bool = False,
    sample_index: int = 0,
    compute_genotype: bool = True,
) -> pl.LazyFrame:
    """
    Lazily read a VCF file into a LazyFrame, including FORMAT fields with proper types.
    
    This function extends polars-bio's scan_vcf to include FORMAT fields
    (GT, DP, GQ, AD, VAF, PL, etc.) that polars-bio doesn't parse.
    
    The approach:
    1. Read with polars-bio (gets chrom, start, end, id, ref, alt, qual, filter, INFO fields)
    2. Read FORMAT/sample columns with regular Polars CSV reader
    3. Cast FORMAT fields to proper types (Int64, Float64, List[Int64])
    4. Optionally compute genotype from GT + ref + alt
    5. Horizontal concat (both readers preserve the same row order)
    
    FORMAT field types (per VCF spec):
    - GT: String (genotype indices like "0/1")
    - GQ: Int64 (genotype quality, Phred-scaled)
    - DP: Int64 (read depth)
    - MIN_DP: Int64 (minimum read depth in GVCF block)
    - AD: List[Int64] (allelic depths, e.g., [30, 25])
    - VAF: List[Float64] (variant allele fractions, can be multi-valued for multi-allelic sites)
    - PL: List[Int64] (Phred-scaled likelihoods, e.g., [0, 27, 34])
    
    Parameters:
        path: The path to the VCF file.
        info_fields: List of INFO field names to include. If None, all INFO fields 
            will be detected automatically from the VCF header.
        format_fields: List of FORMAT field names to extract, in order as they appear
            in the VCF FORMAT column. Default: ["GT", "GQ", "DP", "AD", "VAF", "PL"].
            Pass an empty list to skip FORMAT field extraction.
        thread_num: The number of threads to use for reading the VCF file.
            Used only for parallel decompression of BGZF blocks. Works only for local files.
        chunk_size: The size in MB of a chunk when reading from an object store. Default is 8 MB.
        concurrent_fetches: [GCS] The number of concurrent fetches when reading from object storage.
        allow_anonymous: [GCS, AWS S3] Whether to allow anonymous access to object storage.
        enable_request_payer: [AWS S3] Whether to enable request payer for object storage.
        max_retries: The maximum number of retries for reading from object storage.
        timeout: The timeout in seconds for reading from object storage.
        compression_type: The compression type of the VCF file. Auto-detected if not specified.
        projection_pushdown: Enable column projection pushdown for query optimization.
        sample_index: Which sample to extract FORMAT fields from (default: 0, first sample).
        compute_genotype: Whether to compute genotype column from GT + ref + alt (default: True).
            Requires "GT" to be in format_fields.
    
    Returns:
        LazyFrame with all standard VCF columns plus FORMAT fields as separate columns.
        If compute_genotype=True and GT is present, includes "genotype" column as List[String].
        
    Example:
        >>> lf = scan_vcf_with_formats("sample.vcf")
        >>> df = lf.filter(pl.col("GT") == "0/1").collect()
        >>> df.columns
        ['chrom', 'start', 'end', 'id', 'ref', 'alt', 'qual', 'filter', 
         'END', 'GT', 'GQ', 'DP', 'AD', 'VAF', 'PL', 'genotype']
        >>> df["genotype"][0]  # e.g., ["A", "G"] for a het variant
    """
    with start_action(
        action_type="scan_vcf_with_formats",
        path=path,
        format_fields=format_fields,
        sample_index=sample_index,
        compute_genotype=compute_genotype
    ) as action:
        # Get INFO fields if not provided
        actual_info_fields = get_info_fields(path) if info_fields is None else info_fields
        
        # Get polars-bio LazyFrame
        lf_bio = pb.scan_vcf(
            path=path,
            info_fields=actual_info_fields,
            thread_num=thread_num,
            chunk_size=chunk_size,
            concurrent_fetches=concurrent_fetches,
            allow_anonymous=allow_anonymous,
            enable_request_payer=enable_request_payer,
            max_retries=max_retries,
            timeout=timeout,
            compression_type=compression_type,
            projection_pushdown=projection_pushdown,
        )
        
        # If no FORMAT fields requested, return polars-bio result only
        if not format_fields:
            action.log(
                message_type="info",
                step="no_format_fields",
                info_fields_count=len(actual_info_fields)
            )
            return lf_bio
        
        # Extract FORMAT fields using regular Polars CSV reader
        lf_raw = pl.scan_csv(
            path,
            separator="\t",
            comment_prefix="##",
            has_header=True,
            infer_schema_length=0,
        )
        
        # Get column names
        cols = list(lf_raw.collect_schema().names())
        
        # Sample columns start at index 9 (after FORMAT)
        # Columns: CHROM, POS, ID, REF, ALT, QUAL, FILTER, INFO, FORMAT, SAMPLE1, SAMPLE2, ...
        if len(cols) <= 9:
            action.log(
                message_type="info",
                step="no_sample_columns",
                column_count=len(cols)
            )
            return lf_bio  # No sample columns, return polars-bio result only
        
        sample_cols = cols[9:]
        if sample_index >= len(sample_cols):
            raise ValueError(f"Sample index {sample_index} out of range. Available samples: {sample_cols}")
        
        sample_col = sample_cols[sample_index]
        
        # Build expressions to extract each FORMAT field by index with proper type casting
        format_exprs = []
        for i, field in enumerate(format_fields):
            raw_expr = pl.col(sample_col).str.split(":").list.get(i)
            typed_expr = _cast_format_field(field, raw_expr)
            format_exprs.append(typed_expr)
        
        lf_formats = lf_raw.select(format_exprs)
        
        # Horizontal concat - both readers preserve the same row order
        result = pl.concat([lf_bio, lf_formats], how="horizontal")
        
        # Compute genotype from GT + ref + alt if requested and GT is present
        if compute_genotype and "GT" in format_fields:
            result = result.with_columns(_compute_genotype_expr())
            action.log(
                message_type="info",
                step="genotype_computed",
            )
        
        action.log(
            message_type="info",
            step="format_fields_concatenated",
            format_fields_count=len(format_fields)
        )
        
        return result


def read_vcf_file(
    file_path: Union[str, Path],
    info_fields: Optional[list[str]] = None,
    save_parquet: SaveParquet = "auto",
    engine: str = "streaming",
    thread_num: int = 1,
    with_formats: Optional[bool] = None,
    format_fields: Optional[list[str]] = None,
) -> pl.LazyFrame:
    """
    Read a VCF file using polars-bio, automatically handling gzipped files.

    Args:
        file_path: Path to the VCF file (can be .vcf or .vcf.gz)
        info_fields: The fields to read from the INFO column.
        save_parquet: Controls saving to parquet.
            - None: do not save
            - "auto" (default): save next to the input VCF, replacing .vcf/.vcf.gz with .parquet.
              Example: data.vcf.gz -> data.parquet
            - Path: save to the provided location
        engine: Parquet engine to use for sinking (defaults to "streaming")
        thread_num: The number of threads to use for reading the VCF file. Used **only** for parallel decompression of BGZF blocks. Works only for **local** files.
        with_formats: Whether to extract FORMAT fields (GT, GQ, etc.) using scan_vcf_with_formats.
            If None (default), auto-detected: True for user VCFs (path containing "users"), False otherwise.
        format_fields: List of FORMAT fields to extract. If None and with_formats is True, 
            uses default fields: ["GT", "GQ", "DP", "AD", "VAF", "PL"].

    Returns:
        Polars LazyFrame containing the VCF data.
        If save_parquet is not None, returns a LazyFrame that scans the newly created parquet file.
        If save_parquet is None, returns the original LazyFrame from polars-bio.
    """
    with start_action(
        action_type="read_vcf_file",
        file_path=str(file_path),
        save_parquet=str(save_parquet) if save_parquet else None,
        with_formats=with_formats
    ) as action:
        file_path = Path(file_path)

        if with_formats is None:
            # Default to True if it looks like a user VCF (contains "users" in path), False otherwise
            with_formats = "users" in str(file_path).lower()
            action.log(message_type="info", step="auto_detected_with_formats", with_formats=with_formats)

        # If it's already a parquet file, just scan it
        if file_path.suffix == ".parquet":
            action.log(message_type="info", step="detected_parquet", path=str(file_path))
            return pl.scan_parquet(str(file_path))

        # Resolve parquet path decision early
        if isinstance(save_parquet, Path):
            parquet_path: Optional[Path] = save_parquet
        elif save_parquet == "auto":
            parquet_path = _default_parquet_path(file_path)
        else:
            parquet_path = None

        action.log(
            message_type="info",
            step="reading_vcf",
            parquet_path=str(parquet_path) if parquet_path else None,
        )

        # Let polars-bio handle compression autodetection and any VCF format issues
        actual_info_fields = get_info_fields(str(file_path)) if info_fields is None else info_fields

        if with_formats:
            # Use the custom scanner that handles FORMAT columns
            kwargs = {"info_fields": actual_info_fields, "thread_num": thread_num}
            if format_fields is not None:
                kwargs["format_fields"] = format_fields
                
            result = scan_vcf_with_formats(str(file_path), **kwargs)
        else:
            # Use standard polars-bio scanner
            result = pb.scan_vcf(
                str(file_path),
                info_fields=actual_info_fields,
                thread_num=thread_num
            )

        action.log(
            message_type="info",
            step="vcf_read_complete",
            result_type=type(result).__name__,
        )

        # Save parquet if requested
        if parquet_path is not None:
            with start_action(
                action_type="save_parquet",
                parquet_path=str(parquet_path),
            ) as save_action:
                if isinstance(result, pl.LazyFrame):
                    # Stream directly to parquet without collecting into memory
                    result.sink_parquet(str(parquet_path), engine=engine)
                else:
                    # DataFrame path (rare here) – write directly
                    result.write_parquet(str(parquet_path))

                save_action.log(
                    message_type="info",
                    step="parquet_saved",
                    parquet_path=str(parquet_path),
                )

        # If we saved parquet, return a LazyFrame scanning it
        if parquet_path is not None:
            return pl.scan_parquet(str(parquet_path))

        return result


def vcf_to_parquet(
    vcf_path: Union[str, Path],
    parquet_path: Optional[Union[str, Path]] = None,
    info_fields: Optional[list[str]] = None,
    thread_num: int = 1,
    overwrite: bool = False,
    with_formats: Optional[bool] = None,
    format_fields: Optional[list[str]] = None,
) -> AnnotatedLazyFrame:
    """
    Read a VCF file and save it to Parquet format, returning both the path and LazyFrame.
    
    Args:
        vcf_path: Path to the input VCF file (can be .vcf or .vcf.gz)
        parquet_path: Path where to save the Parquet file. 
            If None (default), saves next to VCF with .parquet extension ("auto" behavior).
        info_fields: The fields to read from the INFO column. If None, reads all available fields
        thread_num: The number of threads to use for reading the VCF file. 
            Used only for parallel decompression of BGZF blocks. Works only for local files.
        overwrite: Whether to overwrite existing Parquet file (default False)
        with_formats: Whether to extract FORMAT fields (GT, GQ, etc.).
            If None (default), auto-detected in read_vcf_file.
        format_fields: Specific FORMAT fields to extract.
        
    Returns:
        AnnotatedLazyFrame: A tuple containing:
            - LazyFrame reading from the Parquet file for immediate data access  
            - Path to the created Parquet file
    """
    with start_action(
        action_type="vcf_to_parquet",
        vcf_path=str(vcf_path),
        parquet_path=str(parquet_path) if parquet_path else None,
        overwrite=overwrite,
        with_formats=with_formats
    ) as action:
        vcf_path = Path(vcf_path)
        
        # Determine output path
        if parquet_path is None:
            output_path = _default_parquet_path(vcf_path)
        else:
            output_path = Path(parquet_path)
        
        action.log(
            message_type="info",
            step="output_path_determined",
            output_path=str(output_path)
        )
        
        # If parquet already exists and overwrite is False, reuse it
        if output_path.exists() and not overwrite:
            action.log(
                message_type="info",
                step="reusing_existing_parquet",
                path=str(output_path)
            )
            return pl.scan_parquet(str(output_path)), output_path
        
        # Use read_vcf_file with forced parquet saving
        lazy_frame = read_vcf_file(
            file_path=vcf_path,
            info_fields=info_fields,
            save_parquet=output_path,
            thread_num=thread_num,
            with_formats=with_formats,
            format_fields=format_fields
        )
        
        action.log(
            message_type="info",
            step="conversion_complete",
            output_path=str(output_path)
        )
        
        return lazy_frame, output_path
    






