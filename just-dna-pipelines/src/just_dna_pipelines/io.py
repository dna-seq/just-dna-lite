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


def _parse_vcf_header_fields(vcf_path: str) -> tuple[list[str], list[str]]:
    """
    Extract INFO and FORMAT field names from a VCF file header.
    
    Parses ``##INFO=<ID=...>`` and ``##FORMAT=<ID=...>`` header lines.

    Args:
        vcf_path: Path to the VCF file

    Returns:
        Tuple of (info_fields, format_fields) lists.
    """
    import gzip

    open_func = gzip.open if vcf_path.endswith('.gz') else open
    mode = 'rt' if vcf_path.endswith('.gz') else 'r'

    info_fields: list[str] = []
    format_fields: list[str] = []

    with open_func(vcf_path, mode) as f:
        for line in f:
            line = line.strip()
            if not line.startswith('#'):
                break
            for prefix, target_list in (('##INFO=<ID=', info_fields), ('##FORMAT=<ID=', format_fields)):
                if line.startswith(prefix):
                    start_idx = line.find('ID=') + 3
                    end_idx = line.find(',', start_idx)
                    if end_idx == -1:
                        end_idx = line.find('>', start_idx)
                    if end_idx > start_idx:
                        target_list.append(line[start_idx:end_idx])

    return info_fields, format_fields


# INFO fields that cause polars-bio Rust panic (OptionalField::append_array_string_iter
# unwrap on None) when parsing DRAGEN/Illumina VCFs. ALLELE_ID has Number=R with "." for REF
# in some records, triggering the bug. Exclude from auto-detect to avoid crash.
_VCF_INFO_BLOCKLIST: frozenset[str] = frozenset({"ALLELE_ID"})


def get_info_fields(vcf_path: str) -> list[str]:
    """
    Extract INFO field names from a VCF file header by parsing the header directly.
    
    Excludes fields in _VCF_INFO_BLOCKLIST that cause polars-bio panics.
    
    Args:
        vcf_path: Path to the VCF file
        
    Returns:
        List of INFO field names found in the header
    """
    with start_action(action_type="get_info_fields", vcf_path=vcf_path) as action:
        try:
            info_fields, _ = _parse_vcf_header_fields(vcf_path)
            info_fields = [f for f in info_fields if f not in _VCF_INFO_BLOCKLIST]
            
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


def read_vcf_file(
    file_path: Union[str, Path],
    info_fields: Optional[list[str]] = None,
    save_parquet: SaveParquet = "auto",
    engine: str = "streaming",
    thread_num: int = 1,
    with_formats: Optional[bool] = None,
    format_fields: Optional[list[str]] = None,
    compute_genotype: bool = True,
) -> pl.LazyFrame:
    """
    Read a VCF file using polars-bio, automatically handling gzipped files.

    Args:
        file_path: Path to the VCF file (can be .vcf or .vcf.gz)
        info_fields: The fields to read from the INFO column. If None, auto-detected from header.
        save_parquet: Controls saving to parquet.
            - None: do not save
            - "auto" (default): save next to the input VCF, replacing .vcf/.vcf.gz with .parquet.
              Example: data.vcf.gz -> data.parquet
            - Path: save to the provided location
        engine: Parquet engine to use for sinking (defaults to "streaming")
        thread_num: Backward-compatible concurrency knob for VCF reading.
            In polars-bio >= 0.23 this is mapped to ``concurrent_fetches``.
        with_formats: Whether to extract FORMAT fields (GT, GQ, etc.).
            If None (default), auto-detected: True for user VCFs (path containing "users"), False otherwise.
        format_fields: List of FORMAT fields to extract. If None and with_formats is True, 
            all FORMAT fields are auto-detected from the VCF header by polars-bio.
            Pass an empty list [] to explicitly disable FORMAT field extraction.
        compute_genotype: Whether to compute genotype column from GT + ref + alt (default: True).
            Only applies when with_formats is True and GT is present in the result.
            The genotype column is a List[String] with actual alleles sorted alphabetically.

    Returns:
        Polars LazyFrame containing the VCF data.
        If save_parquet is not None, returns a LazyFrame that scans the newly created parquet file.
        If save_parquet is None, returns the original LazyFrame from polars-bio.
    """
    with start_action(
        action_type="read_vcf_file",
        file_path=str(file_path),
        save_parquet=str(save_parquet) if save_parquet else None,
        with_formats=with_formats,
        compute_genotype=compute_genotype
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

        # Determine format fields to use:
        # - with_formats=True + format_fields=None → pass None to polars-bio (auto-detect all)
        # - with_formats=True + format_fields=[] → pass [] to polars-bio (no format fields)
        # - with_formats=True + format_fields=[...] → pass the list
        # - with_formats=False → pass [] to disable format field extraction
        if with_formats:
            actual_format_fields = format_fields  # None means auto-detect all, [] means none
        else:
            actual_format_fields = []  # Explicitly disable format fields

        # ── Deduplicate: fields present in both INFO and FORMAT cause
        #    DuplicateQualifiedField errors in polars-bio.  When a field
        #    name (e.g. "AF") appears in both sections we keep it in INFO
        #    and remove it from FORMAT to avoid the schema collision.
        if with_formats and actual_info_fields:
            info_set = set(actual_info_fields)
            if actual_format_fields is None:
                # Auto-detect is requested → parse FORMAT fields from
                # the header so we can strip collisions before calling
                # polars-bio.
                _, header_format_fields = _parse_vcf_header_fields(str(file_path))
                duplicates = info_set & set(header_format_fields)
                if duplicates:
                    actual_format_fields = [f for f in header_format_fields if f not in info_set]
                    action.log(
                        message_type="info",
                        step="dedup_info_format_fields",
                        removed_from_format=sorted(duplicates),
                    )
            elif actual_format_fields:
                duplicates = info_set & set(actual_format_fields)
                if duplicates:
                    actual_format_fields = [f for f in actual_format_fields if f not in info_set]
                    action.log(
                        message_type="info",
                        step="dedup_info_format_fields",
                        removed_from_format=sorted(duplicates),
                    )

        # polars-bio >= 0.23 removed `thread_num`; map to `concurrent_fetches`.
        # predicate_pushdown=False: polars-bio 0.23 has a bug in _translate_in_expr
        # where the `column` variable is unbound when the regex doesn't match,
        # causing spurious warnings on semi-joins. Since we read the full VCF and
        # immediately sink to parquet, pushdown gives no benefit here anyway.
        result = pb.scan_vcf(
            str(file_path),
            info_fields=actual_info_fields,
            format_fields=actual_format_fields,
            concurrent_fetches=max(1, int(thread_num)),
            predicate_pushdown=False,
        )

        # Compute genotype from GT + ref + alt if requested and GT is present in schema
        schema = result.collect_schema()
        if with_formats and compute_genotype and "GT" in schema:
            result = result.with_columns(_compute_genotype_expr())
            action.log(message_type="info", step="genotype_computed")

        action.log(
            message_type="info",
            step="vcf_read_complete",
            result_type=type(result).__name__,
            format_fields="auto-detected" if actual_format_fields is None else actual_format_fields,
            columns=list(schema.names()),
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
    compute_genotype: bool = True,
) -> AnnotatedLazyFrame:
    """
    Read a VCF file and save it to Parquet format, returning both the path and LazyFrame.
    
    Args:
        vcf_path: Path to the input VCF file (can be .vcf or .vcf.gz)
        parquet_path: Path where to save the Parquet file. 
            If None (default), saves next to VCF with .parquet extension ("auto" behavior).
        info_fields: The fields to read from the INFO column. If None, reads all available fields
        thread_num: Backward-compatible concurrency knob for VCF reading.
            In polars-bio >= 0.23 this is mapped to ``concurrent_fetches``.
        overwrite: Whether to overwrite existing Parquet file (default False)
        with_formats: Whether to extract FORMAT fields (GT, GQ, etc.).
            If None (default), auto-detected in read_vcf_file.
        format_fields: Specific FORMAT fields to extract. If None, all FORMAT fields 
            are auto-detected from the VCF header by polars-bio.
        compute_genotype: Whether to compute genotype column from GT + ref + alt (default: True).
        
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
            format_fields=format_fields,
            compute_genotype=compute_genotype
        )
        
        action.log(
            message_type="info",
            step="conversion_complete",
            output_path=str(output_path)
        )
        
        return lazy_frame, output_path
    






