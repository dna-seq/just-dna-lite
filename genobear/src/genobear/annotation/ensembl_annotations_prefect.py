"""Ensembl annotations and downloads using Prefect."""

import os
import shutil
from pathlib import Path
from typing import Optional

import polars as pl
from huggingface_hub import snapshot_download
from platformdirs import user_cache_dir
from prefect import task, flow, get_run_logger
from prefect.artifacts import create_markdown_artifact

from genobear.pipelines.registry import store, PipelineCategory
from genobear.runtime import resource_tracker, prefect_flow_run
from genobear.annotation.chromosomes import (
    detect_chrom_style_from_values,
    rewrite_chromosome_column_strip_chr_prefix,
    rewrite_chromosome_column_to_chr_prefixed,
    get_input_chrom_style_and_values,
    normalize_chrom_value,
)
from genobear.io import read_vcf_file


def _configure_polars_memory_efficient() -> None:
    """Configure Polars for memory-efficient operations."""
    try:
        pl.Config.set_streaming_chunk_size(50_000)
    except AttributeError:
        pass

# Configure Polars for memory efficiency by default
_configure_polars_memory_efficient()


@task(name="Load VCF as LazyFrame")
def load_vcf_as_lazy_frame_task(
    vcf_path: str | Path,
    info_fields: list[str] | None = None,
) -> pl.LazyFrame:
    """Load VCF file as a Polars LazyFrame."""
    logger = get_run_logger()
    logger.info(f"Loading VCF from {vcf_path}...")
    vcf_lazy = read_vcf_file(vcf_path, info_fields=info_fields, save_parquet=None)
    schema = vcf_lazy.collect_schema()
    logger.info(f"VCF loaded with {len(schema)} columns.")
    return vcf_lazy


def get_default_ensembl_cache_dir() -> Path:
    """Get the default cache directory for ensembl_variations."""
    env_cache = os.getenv("GENOBEAR_CACHE_DIR")
    if env_cache:
        return Path(env_cache) / "ensembl_variations" / "splitted_variants"
    else:
        user_cache_path = Path(user_cache_dir(appname="genobear"))
        return user_cache_path / "ensembl_variations" / "splitted_variants"


@task(name="Download Ensembl Annotations", cache_key_fn=None, retries=2)
def download_ensembl_annotations_task(
    repo_id: str = "just-dna-seq/ensembl_variations",
    cache_dir: Optional[Path] = None,
    token: Optional[str] = None,
    force_download: bool = False,
    allow_patterns: Optional[list[str]] = None,
) -> Path:
    """Download ensembl_variations dataset from HuggingFace Hub to local cache."""
    logger = get_run_logger()
    
    # Determine cache directory
    if cache_dir is None:
        cache_dir = get_default_ensembl_cache_dir()
    else:
        cache_dir = Path(cache_dir)
    
    logger.info(f"Determined cache directory: {cache_dir}")
    
    # Check if cache exists and skip download if not forced
    if cache_dir.exists() and not force_download:
        parquet_file = next(cache_dir.rglob("*.parquet"), None)
        if parquet_file is not None:
            logger.info(f"Cache exists, skipping download. Found: {parquet_file}")
            return cache_dir
    
    logger.info(f"Downloading {repo_id} from HuggingFace Hub...")
    
    downloaded_path = snapshot_download(
        repo_id=repo_id,
        repo_type="dataset",
        local_dir=cache_dir,
        local_dir_use_symlinks=False,
        token=token,
        allow_patterns=allow_patterns or ["data/**/*.parquet"],
    )
    
    logger.info(f"Download complete: {downloaded_path}")
    return Path(downloaded_path)


@task(name="Get Chromosomes in Parquet")
def get_chromosomes_in_file_task(parquet_file: Path, chrom_col: str = "chrom") -> set[str]:
    """Get unique chromosome values from a parquet file."""
    chroms = (
        pl.scan_parquet(parquet_file)
        .select(pl.col(chrom_col).cast(pl.Utf8).unique())
        .collect()
        .get_column(chrom_col)
        .to_list()
    )
    return {c for c in chroms if c is not None}


@task(name="Annotate Chromosome File")
def annotate_single_chromosome_file_task(
    input_df: pl.DataFrame,
    ensembl_file: Path,
    join_columns: list[str],
    chrom_col: str,
    output_file: Path,
    compression: str,
) -> int:
    """Annotate input with a single Ensembl chromosome file."""
    # Scan the single Ensembl file
    ensembl_lf = pl.scan_parquet(ensembl_file)

    # Rename Ensembl 'id' column to 'rsid' to avoid clash with VCF 'id' column
    if "id" in ensembl_lf.collect_schema().names():
        ensembl_lf = ensembl_lf.rename({"id": "rsid"})

    input_lf = input_df.lazy()

    # Semi-join to filter Ensembl to only matching keys
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

    # Reorder columns to put rsid before id
    columns = annotated_lf.collect_schema().names()
    if "rsid" in columns and "id" in columns:
        id_idx = columns.index("id")
        columns.remove("rsid")
        columns.insert(id_idx, "rsid")
        annotated_lf = annotated_lf.select(columns)

    # Write output using streaming engine
    output_file.parent.mkdir(parents=True, exist_ok=True)
    annotated_lf.sink_parquet(
        output_file,
        compression=compression,
        engine="streaming",
    )

    return pl.scan_parquet(output_file).select(pl.len()).collect().item()


@store.register(
    name="annotate_vcf_with_ensembl",
    description="Annotate a VCF file with Ensembl variation data and save as Parquet",
    category=PipelineCategory.ANNOTATION,
    author="GenoBear",
    tags=["vcf", "ensembl", "annotation", "file"],
    source="builtin",
)
@flow(name="Annotate VCF with Ensembl")
def annotate_vcf_with_ensembl_flow(
    vcf_path: str,
    output_path: Optional[str] = None,
    ensembl_cache_path: Optional[str] = None,
    variant_type: str = "SNV",
    compression: str = "zstd",
) -> str:
    """Entry point flow to annotate a VCF file, suitable for UI triggering."""
    vcf_input = Path(vcf_path)
    
    # Smart default for output path
    if output_path is None:
        output_dir = Path("data") / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        final_output_path = output_dir / f"{vcf_input.stem}_annotated.parquet"
    else:
        final_output_path = Path(output_path)
        
    # Smart default for cache path
    if ensembl_cache_path is None:
        final_cache_path = get_default_ensembl_cache_dir()
    else:
        final_cache_path = Path(ensembl_cache_path)

    vcf_lf = load_vcf_as_lazy_frame_task(vcf_path)
    result_lf = annotate_with_ensembl_flow(
        input_dataframe=vcf_lf,
        ensembl_cache_path=final_cache_path,
        variant_type=variant_type,
        output_path=final_output_path,
        compression=compression,
    )
    return str(final_output_path)


@flow(name="Annotate with Ensembl")
def annotate_with_ensembl_flow(
    input_dataframe: pl.LazyFrame,
    ensembl_cache_path: Path,
    join_columns: Optional[list[str]] = None,
    variant_type: str = "SNV",
    output_path: Optional[Path] = None,
    compression: str = "zstd",
    profile: bool = True,
) -> pl.LazyFrame:
    """Prefect flow to annotate a polars LazyFrame with Ensembl variations."""
    logger = get_run_logger()
    
    with prefect_flow_run("Annotate with Ensembl", profile=profile):
        # Default join columns
        if join_columns is None:
            join_columns = ["chrom", "start", "ref", "alt"]

        chrom_col = "chrom" if "chrom" in join_columns else "chrom"

        # Determine variant directory
        variant_dir = ensembl_cache_path / variant_type
        if not variant_dir.exists():
            variant_dir = ensembl_cache_path / "data" / variant_type

        if not variant_dir.exists():
            raise FileNotFoundError(f"Variant directory not found: {variant_dir}")

        parquet_files = sorted(variant_dir.glob("*.parquet"))
        if not parquet_files:
            logger.warning(f"No parquet files found in {variant_dir}")
            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                input_dataframe.sink_parquet(output_path, compression=compression, engine="streaming")
            return input_dataframe

        # Detect chromosome naming style from first Ensembl file
        first_file_chroms = get_chromosomes_in_file_task(parquet_files[0], chrom_col)
        reference_has_chr = any(c.lower().startswith("chr") for c in first_file_chroms if c)

        # Get input chromosome style and values
        input_style, input_chrom_values = get_input_chrom_style_and_values(input_dataframe, chrom_col)
        input_has_chr = input_style == "chr_prefixed"

        # Determine if we need to rewrite input chromosomes
        input_lf = input_dataframe
        if reference_has_chr and not input_has_chr:
            input_lf = rewrite_chromosome_column_to_chr_prefixed(input_lf, chrom_col=chrom_col)
            input_chrom_values = {normalize_chrom_value(c, "chr_prefixed") for c in input_chrom_values}
        elif (not reference_has_chr) and input_has_chr:
            input_lf = rewrite_chromosome_column_strip_chr_prefix(input_lf, chrom_col=chrom_col)
            input_chrom_values = {normalize_chrom_value(c, "no_prefix") for c in input_chrom_values}

        # Determine output folder for per-chromosome files
        if output_path:
            output_path = Path(output_path)
            output_folder = output_path.parent / f".{output_path.stem}_parts"
        else:
            import tempfile
            output_folder = Path(tempfile.mkdtemp(prefix="ensembl_annotated_"))

        output_folder.mkdir(parents=True, exist_ok=True)

        # Collect the input once for in-memory filtering (small enough for genomic variants usually)
        input_df = input_lf.collect()
        
        processed_files = []
        total_annotated_rows = 0

        # We could submit tasks in parallel here if we had a proper Dask/Ray executor
        for ensembl_file in parquet_files:
            file_chroms = get_chromosomes_in_file_task(ensembl_file, chrom_col)
            matching_chroms = input_chrom_values.intersection(file_chroms)
            
            if not matching_chroms:
                continue

            filtered_input_df = input_df.filter(pl.col(chrom_col).is_in(list(matching_chroms)))
            if filtered_input_df.is_empty():
                continue

            chrom_output_file = output_folder / ensembl_file.name
            
            rows_written = annotate_single_chromosome_file_task(
                input_df=filtered_input_df,
                ensembl_file=ensembl_file,
                join_columns=join_columns,
                chrom_col=chrom_col,
                output_file=chrom_output_file,
                compression=compression,
            )

            processed_files.append(chrom_output_file)
            total_annotated_rows += rows_written

        if not processed_files:
            if output_path:
                input_df.lazy().sink_parquet(output_path, compression=compression, engine="streaming")
            if output_folder.exists():
                shutil.rmtree(output_folder)
            return input_df.lazy()

        result_lf = pl.scan_parquet(str(output_folder / "*.parquet"))

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            result_lf.sink_parquet(output_path, compression=compression, engine="streaming")
            shutil.rmtree(output_folder)
            result_lf = pl.scan_parquet(output_path)

    return result_lf
