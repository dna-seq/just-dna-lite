"""
Path helpers and resource utilities for annotation pipelines.

These are not Dagster resources, but shared utility functions for
determining cache, input, and output directories.
"""

import os
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Optional

import requests
from platformdirs import user_cache_dir


@lru_cache(maxsize=1)
def get_workspace_root() -> Path:
    """Return the absolute path to the uv workspace root.

    Resolution order:
    1. ``JUST_DNA_PIPELINES_ROOT`` environment variable (explicit override)
    2. Walk up from this file until we find the workspace-level
       ``pyproject.toml`` that contains ``[tool.uv.workspace]``.

    The result is cached so the filesystem walk only happens once.
    """
    env_root = os.getenv("JUST_DNA_PIPELINES_ROOT")
    if env_root:
        return Path(env_root).resolve()

    # Walk upward from this file (annotation/resources.py)
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        candidate = parent / "pyproject.toml"
        if candidate.exists():
            text = candidate.read_text(encoding="utf-8")
            if "[tool.uv.workspace]" in text:
                return parent
    # Fallback: 5 levels up from annotation/resources.py
    # just-dna-pipelines/src/just_dna_pipelines/annotation/resources.py
    return Path(__file__).resolve().parents[4]


def get_default_ensembl_cache_dir() -> Path:
    """Get the default cache directory for ensembl_variations.

    Layout after downloading via fsspec::

        {cache_dir}/ensembl_variations/data/homo_sapiens-chr1.parquet
        {cache_dir}/ensembl_variations/data/homo_sapiens-chr2.parquet
        ...

    The directory is created automatically if it does not exist yet.
    """
    env_cache = os.getenv("JUST_DNA_PIPELINES_CACHE_DIR")
    if env_cache:
        cache_dir = Path(env_cache) / "ensembl_variations"
    else:
        user_cache_path = Path(user_cache_dir(appname="just-dna-pipelines"))
        cache_dir = user_cache_path / "ensembl_variations"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_ensembl_parquet_dir(ensembl_cache: Optional[Path] = None) -> Path:
    """Return the directory containing Ensembl chromosome parquet files.

    The canonical location is ``{ensembl_cache}/data/``.  If *ensembl_cache*
    is ``None``, :func:`get_default_ensembl_cache_dir` is used.

    Raises:
        FileNotFoundError: If no parquet files can be found.
    """
    cache = ensembl_cache or get_default_ensembl_cache_dir()
    data_dir = cache / "data"
    if data_dir.exists() and any(data_dir.glob("*.parquet")):
        return data_dir
    raise FileNotFoundError(
        f"No Ensembl Parquet files found at {data_dir}. "
        "Please materialize the ensembl_annotations asset first via Dagster UI, "
        "or run: uv run dg asset materialize --select ensembl_annotations"
    )


def ensure_ensembl_cache_exists(logger=None) -> Path:
    """Validate that the Ensembl parquet cache is populated.

    Returns the *root* cache directory (the parent of ``data/``).

    Raises:
        FileNotFoundError: If the cache is empty or missing.
    """
    cache_dir = get_default_ensembl_cache_dir()
    data_dir = get_ensembl_parquet_dir(cache_dir)
    parquet_files = list(data_dir.glob("*.parquet"))
    if logger:
        logger.info(f"Using Ensembl cache at {data_dir} with {len(parquet_files)} Parquet files")
    return cache_dir


def get_cache_dir() -> Path:
    """Get the root cache directory for all annotations."""
    env_cache = os.getenv("JUST_DNA_PIPELINES_CACHE_DIR")
    if env_cache:
        return Path(env_cache)
    return Path(user_cache_dir(appname="just-dna-pipelines"))


def get_user_output_dir() -> Path:
    """Get the root output directory for user-specific assets.

    Always returns an absolute path so the result is CWD-independent.
    """
    env_output = os.getenv("JUST_DNA_PIPELINES_OUTPUT_DIR")
    if env_output:
        return Path(env_output).resolve()
    return get_workspace_root() / "data" / "output" / "users"


def get_user_input_dir() -> Path:
    """Get the root input directory for user-uploaded VCF files.

    Always returns an absolute path so the result is CWD-independent.
    
    Expected structure:
    data/input/users/{user_name}/*.vcf
    """
    env_input = os.getenv("JUST_DNA_PIPELINES_INPUT_DIR")
    if env_input:
        return Path(env_input).resolve()
    return get_workspace_root() / "data" / "input" / "users"


def download_vcf_from_zenodo(
    zenodo_url: str,
    filename: Optional[str] = None,
    logger=None,
) -> Path:
    """
    Download a VCF file from Zenodo.
    
    Supports:
    - Record URLs: https://zenodo.org/records/18370498 (finds first VCF)
    - Direct file URLs: https://zenodo.org/api/records/18370498/files/antonkulaga.vcf/content
    
    Downloaded files are cached in ~/.cache/just-dna-pipelines/zenodo/
    
    Args:
        zenodo_url: Zenodo record URL or direct file URL
        filename: Optional filename override (auto-detected if not provided)
        logger: Optional logger for messages
        
    Returns:
        Path to the downloaded VCF file
    """
    cache_dir = get_cache_dir() / "zenodo"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Handle record URLs: https://zenodo.org/records/{record_id}
    if "/records/" in zenodo_url and "/files/" not in zenodo_url:
        record_id = zenodo_url.split("/records/")[-1].split("?")[0].split("/")[0]
        api_url = f"https://zenodo.org/api/records/{record_id}"
        
        if logger:
            logger.info(f"Fetching Zenodo record metadata: {api_url}")
        
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        
        # Find the first VCF file
        vcf_file = next(
            (f for f in data["files"] if f["key"].endswith(".vcf") or f["key"].endswith(".vcf.gz")),
            None
        )
        if not vcf_file:
            raise ValueError(f"No VCF file found in Zenodo record {record_id}")
        
        download_url = vcf_file["links"]["self"]
        resolved_filename = filename or vcf_file["key"]
    else:
        # Direct file URL
        download_url = zenodo_url
        if filename:
            resolved_filename = filename
        else:
            # Extract filename from URL
            resolved_filename = zenodo_url.split("/")[-1].split("?")[0]
            if not (resolved_filename.endswith(".vcf") or resolved_filename.endswith(".vcf.gz")):
                resolved_filename = "genome.vcf"
    
    vcf_path = cache_dir / resolved_filename
    
    # Check if already cached
    if vcf_path.exists():
        if logger:
            logger.info(f"Using cached VCF from Zenodo: {vcf_path}")
        return vcf_path
    
    # Download
    if logger:
        logger.info(f"Downloading VCF from Zenodo: {download_url}")
    
    response = requests.get(download_url, stream=True)
    response.raise_for_status()
    
    with open(vcf_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    if logger:
        size_mb = vcf_path.stat().st_size / (1024 * 1024)
        logger.info(f"Downloaded VCF: {vcf_path} ({size_mb:.1f} MB)")
    
    return vcf_path


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

