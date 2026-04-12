"""
Path helpers and resource utilities for annotation pipelines.

These are not Dagster resources, but shared utility functions for
determining cache, input, and output directories.
"""

import logging
import os
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import requests
from platformdirs import user_cache_dir

logger = logging.getLogger(__name__)

PERMISSIVE_LICENSES = {
    "cc-zero", "cc0-1.0", "cc-by-4.0", "cc-by-sa-4.0",
    "cc-by-3.0", "cc-by-sa-3.0", "cc-by-nc-4.0", "cc-by-nc-sa-4.0",
    "mit", "apache-2.0", "bsd-3-clause",
}


@lru_cache(maxsize=1)
def get_workspace_root() -> Path:
    """Return the absolute path to the uv workspace root.

    Resolution order:
    1. ``JUST_DNA_PIPELINES_ROOT`` environment variable (explicit override)
    2. Walk up from CWD until we find a ``pyproject.toml`` with ``[tool.uv.workspace]``.
    3. Walk up from this file (works in editable installs / dev mode).
    4. Fallback: CWD itself (prod: the app is always started from the project root).

    The result is cached so the filesystem walk only happens once.
    """
    env_root = os.getenv("JUST_DNA_PIPELINES_ROOT")
    if env_root:
        return Path(env_root).resolve()

    def _find_workspace_root(start: Path) -> Path | None:
        for parent in [start] + list(start.parents):
            candidate = parent / "pyproject.toml"
            if candidate.exists():
                text = candidate.read_text(encoding="utf-8")
                if "[tool.uv.workspace]" in text:
                    return parent
        return None

    # Try CWD first (reliable when app is launched from project root, even with
    # non-editable installs where __file__ points into site-packages)
    cwd_root = _find_workspace_root(Path.cwd().resolve())
    if cwd_root:
        return cwd_root

    # Try walking up from this source file (works in editable/dev installs)
    file_root = _find_workspace_root(Path(__file__).resolve().parent)
    if file_root:
        return file_root

    # Last resort: assume CWD is the project root
    return Path.cwd().resolve()


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


def get_registered_modules_dir() -> Path:
    """Get the directory for compiled/registered custom modules.

    Resolution: ``JUST_DNA_PIPELINES_OUTPUT_DIR``/registered_modules
    or ``{workspace}/data/interim/registered_modules``.
    """
    env_output = os.getenv("JUST_DNA_PIPELINES_OUTPUT_DIR")
    if env_output:
        return Path(env_output).resolve() / "registered_modules"
    return get_workspace_root() / "data" / "interim" / "registered_modules"


def get_generated_modules_dir() -> Path:
    """Get the directory for agent-generated module specs (versioned).

    Resolution: ``JUST_DNA_PIPELINES_OUTPUT_DIR``/generated_modules
    or ``{workspace}/data/output/generated_modules``.
    """
    env_output = os.getenv("JUST_DNA_PIPELINES_OUTPUT_DIR")
    if env_output:
        return Path(env_output).resolve() / "generated_modules"
    return get_workspace_root() / "data" / "output" / "generated_modules"


def download_vcf_from_zenodo(
    zenodo_url: str,
    filename: Optional[str] = None,
    logger: Optional[Any] = None,
) -> Path:
    """Download a VCF file from Zenodo.

    Supports:
    - Record URLs: ``https://zenodo.org/records/18370498`` (finds first VCF)
    - Direct file URLs: ``https://zenodo.org/api/records/.../files/.../content``

    Downloaded files are cached in ``~/.cache/just-dna-pipelines/zenodo/``
    and are not re-downloaded on subsequent calls.
    """
    from just_dna_pipelines.annotation.resources import logger as _module_logger
    _log = logger or _module_logger

    cache_dir = get_cache_dir() / "zenodo"
    cache_dir.mkdir(parents=True, exist_ok=True)

    if "/records/" in zenodo_url and "/files/" not in zenodo_url:
        record_id = zenodo_url.split("/records/")[-1].split("?")[0].split("/")[0]
        api_url = f"https://zenodo.org/api/records/{record_id}"

        _log.info(f"Fetching Zenodo record metadata: {api_url}")

        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        data = response.json()

        vcf_file = next(
            (f for f in data["files"]
             if f["key"].endswith(".vcf") or f["key"].endswith(".vcf.gz")),
            None,
        )
        if not vcf_file:
            raise ValueError(f"No VCF file found in Zenodo record {record_id}")

        download_url = vcf_file["links"]["self"]
        resolved_filename = filename or vcf_file["key"]
    else:
        download_url = zenodo_url
        if filename:
            resolved_filename = filename
        else:
            resolved_filename = zenodo_url.split("/")[-1].split("?")[0]
            if not (resolved_filename.endswith(".vcf") or resolved_filename.endswith(".vcf.gz")):
                resolved_filename = "genome.vcf"

    vcf_path = cache_dir / resolved_filename

    if vcf_path.exists():
        _log.info(f"Using cached VCF from Zenodo: {vcf_path}")
        return vcf_path

    _log.info(f"Downloading VCF from Zenodo: {download_url}")

    response = requests.get(download_url, stream=True, timeout=30)
    response.raise_for_status()

    with open(vcf_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    size_mb = vcf_path.stat().st_size / (1024 * 1024)
    _log.info(f"Downloaded VCF: {vcf_path} ({size_mb:.1f} MB)")

    return vcf_path


def ensure_vcf_in_user_input_dir(
    vcf_path: Path,
    user_name: str,
    log: Optional[Any] = None,
) -> Path:
    """Ensure the VCF file is in the expected user input directory.

    If the VCF is already in ``data/input/users/{user_name}/``, return as-is.
    If elsewhere, copy it to the expected location.

    Returns the path to the VCF in the user input directory.
    """
    _log = log or logger
    user_input_dir = get_user_input_dir() / user_name
    expected_vcf_path = user_input_dir / vcf_path.name

    if vcf_path.resolve() == expected_vcf_path.resolve():
        _log.info(f"VCF already in expected location: {vcf_path}")
        return vcf_path

    if expected_vcf_path.exists():
        if vcf_path.stat().st_size == expected_vcf_path.stat().st_size:
            _log.info(f"VCF already exists in user input directory: {expected_vcf_path}")
            return expected_vcf_path
        else:
            _log.warning(
                f"VCF with same name but different size exists. "
                f"Source: {vcf_path.stat().st_size} bytes, "
                f"Existing: {expected_vcf_path.stat().st_size} bytes. "
                f"Overwriting with source file."
            )

    user_input_dir.mkdir(parents=True, exist_ok=True)
    _log.info(f"Copying VCF to user input directory: {vcf_path} -> {expected_vcf_path}")
    shutil.copy2(vcf_path, expected_vcf_path)

    return expected_vcf_path


def validate_zenodo_record(zenodo_url: str) -> dict[str, Any]:
    """Validate a Zenodo record for open-access VCF import.

    Checks that the record:
    - Has ``access_right == "open"``
    - Has a permissive license
    - Contains at least one ``.vcf`` or ``.vcf.gz`` file

    Returns a metadata dict on success::

        {
            "record_id": str,
            "title": str,
            "creator": str,
            "license": str,
            "doi": str,
            "vcf_filename": str,
            "vcf_size_bytes": int,
        }

    Raises ``ValueError`` with a user-friendly message on failure.
    """
    if "/records/" not in zenodo_url:
        raise ValueError(
            "Not a valid Zenodo record URL. "
            "Expected format: https://zenodo.org/records/<record_id>"
        )

    record_id = zenodo_url.split("/records/")[-1].split("?")[0].split("/")[0]
    api_url = f"https://zenodo.org/api/records/{record_id}"

    resp = requests.get(api_url, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    metadata = data.get("metadata", {})
    access_right = metadata.get("access_right", "")
    if access_right != "open":
        raise ValueError(
            f"Zenodo record {record_id} is not open-access (access_right={access_right!r}). "
            "Only open-access records with permissive licenses can be imported."
        )

    license_id = (metadata.get("license", {}).get("id") or "").lower()
    if license_id not in PERMISSIVE_LICENSES:
        raise ValueError(
            f"Zenodo record {record_id} has license {license_id!r} which is not "
            f"in the allowed list. Allowed licenses: {', '.join(sorted(PERMISSIVE_LICENSES))}"
        )

    vcf_file = next(
        (f for f in data.get("files", [])
         if f["key"].endswith(".vcf") or f["key"].endswith(".vcf.gz")),
        None,
    )
    if vcf_file is None:
        raise ValueError(
            f"Zenodo record {record_id} does not contain a .vcf or .vcf.gz file."
        )

    creators = metadata.get("creators", [])
    creator_name = creators[0].get("name", "Unknown") if creators else "Unknown"

    return {
        "record_id": record_id,
        "title": metadata.get("title", ""),
        "creator": creator_name,
        "license": license_id,
        "doi": metadata.get("doi", ""),
        "vcf_filename": vcf_file["key"],
        "vcf_size_bytes": vcf_file.get("size", 0),
    }


def resolve_default_samples(
    user_name: str = "public",
    log: Optional[Any] = None,
) -> list[dict[str, Any]]:
    """Download and place all default samples from the immutable mode config.

    For each ``DefaultSample`` in ``modules.yaml`` ``immutable_mode.default_samples``:
    1. Download from Zenodo (cached in ``~/.cache/just-dna-pipelines/zenodo/``)
    2. Copy into ``data/input/users/{user_name}/``

    Returns a list of dicts with ``path`` (Path) and all sample metadata fields.
    Already-cached files are not re-downloaded.
    """
    from just_dna_pipelines.module_config import get_immutable_config

    _log = log or logger
    config = get_immutable_config()
    results: list[dict[str, Any]] = []

    for sample in config.default_samples:
        vcf_path = download_vcf_from_zenodo(sample.zenodo_url, logger=_log)
        placed = ensure_vcf_in_user_input_dir(vcf_path, user_name, _log)
        results.append({
            "path": placed,
            "filename": placed.name,
            "label": sample.label,
            "subject_id": sample.subject_id,
            "sex": sample.sex,
            "species": sample.species,
            "reference_genome": sample.reference_genome,
            "license": sample.license,
            "zenodo_url": sample.zenodo_url,
            "source": "zenodo",
        })

    return results

