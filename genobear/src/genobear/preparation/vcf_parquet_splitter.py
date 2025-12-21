import time
from pathlib import Path
from typing import Dict, Optional, List

import polars as pl
from eliot import start_action
from genobear.config import get_default_workers
    

def split_variants_by_tsa(
    parquet_path: Path, 
    explode_snv_alt: bool = True,
    write_to: Optional[Path] = None
) -> Dict[str, Path]:
    """
    Split variants in a parquet file by TSA (variant type).
    
    Args:
        parquet_path: Path to parquet file containing VCF data
        explode_snv_alt: Whether to explode ALT column on "|" separator for SNV variants
        write_to: Optional directory to write split parquet files to
        
    Returns:
        Dictionary mapping TSA (variant type) to written parquet file paths
    """
    # Skip non-parquet files
    if not parquet_path.suffix == '.parquet':
        return {}
        
    # Default output directory next to the input parquet if not provided
    if write_to is None:
        write_to = parquet_path.parent / "splitted_variants"
    write_to.mkdir(parents=True, exist_ok=True)
    
    with start_action(action_type="split_variants_by_tsa", parquet_path=str(parquet_path), explode_snv_alt=explode_snv_alt, write_to=str(write_to)) as action:
        df = pl.scan_parquet(parquet_path)
        stem = parquet_path.stem
        
        # Get unique TSAs (variant types)
        tsas = df.select("tsa").unique().collect(streaming=True).to_series().to_list()
        action.log(message_type="info", tsas=tsas, explode_snv_alt=explode_snv_alt)
        
        # Check if all split files already exist
        result: Dict[str, Path] = {}
        all_exist = True
        
        for tsa in tsas:
            tsa_folder = write_to / tsa
            where = tsa_folder / f"{stem}.parquet"
            result[tsa] = where
            
            if not where.exists():
                all_exist = False
                break
        
        # If all split files already exist, skip splitting
        if all_exist:
            action.log(
                message_type="info",
                step="reusing_existing_splits",
                split_count=len(result),
                tsas=tsas
            )
            return result
        
        # Otherwise, perform splitting
        action.log(message_type="info", step="performing_split", tsas=tsas)
        result = {}
        start_time = time.time()
        
        for tsa in tsas:
            df_tsa = df.filter(pl.col("tsa") == tsa)
            
            # Explode ALT column for SNV variants if requested
            if tsa == "SNV" and explode_snv_alt:
                df_tsa = df_tsa.with_columns(pl.col("alt").str.split("|")).explode("alt")
            
            # Create TSA-specific subfolder
            tsa_folder = write_to / tsa
            tsa_folder.mkdir(parents=True, exist_ok=True)
            
            # Write to parquet file
            where = tsa_folder / f"{stem}.parquet"
            action.log(message_type="info", tsa=tsa, where=str(where))
            df_tsa.sink_parquet(where)
            result[tsa] = where
        
        # Calculate execution time
        end_time = time.time()
        elapsed_seconds = end_time - start_time
        minutes = int(elapsed_seconds // 60)
        seconds = elapsed_seconds % 60
        execution_time = f"{minutes}:{seconds:06.3f}"
        
        action.log(message_type="info", execution_time=execution_time, tsas=tsas, result_count=len(result))
        return result


def validate_split_outputs(
    vcf_parquet_path: list[Path],
    split_variants_dict: list[Dict[str, Path]],
) -> tuple[list[Path], list[Dict[str, Path]]]:
    """
    Validate that for each input parquet file we produced split outputs and all
    referenced files exist. Non-parquet inputs are ignored.
    """
    with start_action(action_type="validate_split_outputs") as action:
        # Normalize to lists
        parquet_list = [vcf_parquet_path] if isinstance(vcf_parquet_path, Path) else list(vcf_parquet_path)
        split_list = [split_variants_dict] if isinstance(split_variants_dict, dict) else list(split_variants_dict)

        # Validate existence
        def _is_parquet(p: Path) -> bool:
            return p.suffix == ".parquet"

        problems: list[str] = []
        for idx, p in enumerate(parquet_list):
            if not _is_parquet(p):
                continue
            if not p.exists():
                problems.append(f"missing input parquet: {p}")
                continue
            # Get corresponding split dict if available
            split_dict = split_list[idx] if idx < len(split_list) else {}
            if not split_dict:
                problems.append(f"no splits produced for: {p}")
                continue
            # Check that all split files exist
            missing = [str(out) for out in split_dict.values() if not Path(out).exists()]
            if missing:
                problems.append(f"missing split files for {p}: {missing}")

        if problems:
            action.log(message_type="error", problems=problems)
            raise FileNotFoundError("; ".join(problems))

        action.log(message_type="info", validated=len(parquet_list))
        return parquet_list, split_list


def split_parquet_variants(
    vcf_parquet_path: Path | list[Path],
    explode_snv_alt: bool = True,
    write_to: Optional[Path] = None,
    parallel: bool = True,
    workers: Optional[int] = None,
    return_results: bool = True,
    **kwargs
) -> dict:
    """Split variants in parquet files by TSA using Prefect.
    
    Args:
        vcf_parquet_path: Path or list of paths to parquet files containing VCF data
        explode_snv_alt: Whether to explode ALT column on "|" separator for SNV variants
        write_to: Optional directory to write split parquet files to
        parallel: Handled by Prefect
        return_results: Return results dict (default True)
        **kwargs: Additional parameters
    
    Returns:
        Dictionary with pipeline results containing 'split_variants_dict'
    """
    from genobear.preparation.runners_prefect import split_parquets_task
    from genobear.runtime import prefect_flow_run
    
    # Handle single path or list of paths
    if isinstance(vcf_parquet_path, Path):
        vcf_parquet_path = [vcf_parquet_path]
    
    with prefect_flow_run("Split Parquet Variants"):
        results = split_parquets_task(
            parquet_paths=vcf_parquet_path,
            explode_snv_alt=explode_snv_alt,
            write_to=write_to,
        )
        return {"split_variants_dict": results}


def download_convert_and_split_vcf(
    url: str,
    pattern: str | None = None,
    name: str | Path = "downloads",
    output_names: set[str] | None = None,
    parallel: bool = True,
    return_results: bool = True,
    explode_snv_alt: bool = True,
    **kwargs
) -> dict:
    """Download, convert VCF files to parquet, and split variants by TSA using Prefect.
    
    Args:
        url: Base URL to search for VCF files
        pattern: Regex pattern to filter files (optional)
        name: Directory name or Path for downloads
        output_names: Handled by return results
        parallel: Handled by Prefect
        return_results: Return results dict (default True)
        explode_snv_alt: Whether to explode ALT column on "|" separator for SNV variants
        **kwargs: Additional parameters
    
    Returns:
        Dictionary with pipeline results containing 'vcf_parquet_path' and 'split_variants_dict'
    """
    from genobear.preparation.runners_prefect import prepare_vcf_source_flow
    
    return prepare_vcf_source_flow(
        url=url,
        pattern=pattern,
        name=str(name),
        with_splitting=True,
        explode_snv_alt=explode_snv_alt,
        **kwargs
    )
