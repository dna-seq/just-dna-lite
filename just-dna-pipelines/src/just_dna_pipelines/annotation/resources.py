"""
Path helpers and resource utilities for annotation pipelines.

These are not Dagster resources, but shared utility functions for
determining cache, input, and output directories.
"""

import os
import shutil
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional

from platformdirs import user_cache_dir

LONGEVITYMAP_SQLITE_SOURCE_URL = (
    "https://github.com/dna-seq/just_longevitymap/blob/master/data/longevitymap.sqlite"
)
LONGEVITYMAP_SQLITE_RAW_URL = (
    "https://raw.githubusercontent.com/dna-seq/just_longevitymap/master/data/longevitymap.sqlite"
)


def get_default_ensembl_cache_dir() -> Path:
    """Get the default cache directory for ensembl_variations."""
    env_cache = os.getenv("JUST_DNA_PIPELINES_CACHE_DIR")
    if env_cache:
        return Path(env_cache) / "ensembl_variations" / "splitted_variants"
    else:
        user_cache_path = Path(user_cache_dir(appname="just-dna-pipelines"))
        return user_cache_path / "ensembl_variations" / "splitted_variants"


def ensure_ensembl_cache_exists(logger=None) -> Path:
    """
    Ensure the Ensembl annotations cache exists.
    
    Unlike the DuckDB helper, this cannot auto-create the cache because
    it requires downloading from HuggingFace. It only validates and
    provides a helpful error message.
    
    Args:
        logger: Optional logger for messages
        
    Returns:
        Path to the Ensembl cache directory
        
    Raises:
        FileNotFoundError: If cache doesn't exist
    """
    cache_dir = get_default_ensembl_cache_dir()
    
    if not cache_dir.exists():
        raise FileNotFoundError(
            f"Ensembl cache not found at {cache_dir}. "
            "Please materialize the ensembl_annotations asset first via Dagster UI, "
            "or run: uv run dg asset materialize --select ensembl_annotations"
        )
    
    # Verify parquet files exist
    parquet_files = list(cache_dir.rglob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(
            f"Ensembl cache at {cache_dir} exists but contains no Parquet files. "
            "Please re-materialize the ensembl_annotations asset."
        )
    
    if logger:
        logger.info(f"Using Ensembl cache at {cache_dir} with {len(parquet_files)} Parquet files")
    
    return cache_dir


def get_cache_dir() -> Path:
    """Get the root cache directory for all annotations."""
    env_cache = os.getenv("JUST_DNA_PIPELINES_CACHE_DIR")
    if env_cache:
        return Path(env_cache)
    return Path(user_cache_dir(appname="just-dna-pipelines"))


def get_longevitymap_sqlite_path() -> Path:
    """Get the default cache path for the LongevityMap SQLite weights."""
    return get_cache_dir() / "longevitymap" / "longevitymap.sqlite"


def download_longevitymap_sqlite(
    source_url: str = LONGEVITYMAP_SQLITE_RAW_URL,
    force_download: bool = False,
    logger=None,
) -> tuple[Path, bool]:
    """
    Download the LongevityMap SQLite weights database.

    Returns:
        (sqlite_path, downloaded) where downloaded is True if a new download happened.
    """
    sqlite_path = get_longevitymap_sqlite_path()
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    if sqlite_path.exists() and not force_download:
        if logger:
            logger.info(f"Using cached LongevityMap SQLite at {sqlite_path}")
        return sqlite_path, False

    if logger:
        logger.info(f"Downloading LongevityMap SQLite from {source_url} to {sqlite_path}")

    with urllib.request.urlopen(source_url) as response:
        with tempfile.NamedTemporaryFile(
            delete=False,
            dir=sqlite_path.parent,
            suffix=".sqlite",
        ) as tmp_file:
            shutil.copyfileobj(response, tmp_file)
            tmp_path = Path(tmp_file.name)

    tmp_path.replace(sqlite_path)
    return sqlite_path, True


def get_user_output_dir() -> Path:
    """Get the root output directory for user-specific assets."""
    env_output = os.getenv("JUST_DNA_PIPELINES_OUTPUT_DIR")
    if env_output:
        return Path(env_output)
    return Path("data") / "output" / "users"


def get_user_input_dir() -> Path:
    """Get the root input directory for user-uploaded VCF files.
    
    Expected structure:
    data/input/users/{user_name}/*.vcf
    """
    env_input = os.getenv("JUST_DNA_PIPELINES_INPUT_DIR")
    if env_input:
        return Path(env_input)
    return Path("data") / "input" / "users"


def ensure_vcf_in_user_input_dir(
    vcf_path: Path,
    user_name: str,
    logger,
) -> Path:
    """
    Ensure the VCF file is in the expected user input directory.
    
    If the VCF is already in data/input/users/{user_name}/, return as-is.
    If the VCF is elsewhere, copy it to the expected location.
    
    Returns the path to the VCF in the user input directory.
    """
    user_input_dir = get_user_input_dir() / user_name
    expected_vcf_path = user_input_dir / vcf_path.name
    
    # Check if already in the expected location
    if vcf_path.resolve() == expected_vcf_path.resolve():
        logger.info(f"VCF already in expected location: {vcf_path}")
        return vcf_path
    
    # Check if already exists in expected location (by name)
    if expected_vcf_path.exists():
        # Compare file sizes to detect if it's the same file
        if vcf_path.stat().st_size == expected_vcf_path.stat().st_size:
            logger.info(f"VCF already exists in user input directory: {expected_vcf_path}")
            return expected_vcf_path
        else:
            logger.warning(
                f"VCF with same name but different size exists. "
                f"Source: {vcf_path.stat().st_size} bytes, "
                f"Existing: {expected_vcf_path.stat().st_size} bytes. "
                f"Overwriting with source file."
            )
    
    # Copy to expected location
    user_input_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Copying VCF to user input directory: {vcf_path} -> {expected_vcf_path}")
    shutil.copy2(vcf_path, expected_vcf_path)
    
    return expected_vcf_path

