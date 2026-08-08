"""
Ensembl rsid <-> position resolution for just-dna-pipelines.

The rsid/position *lookup* logic lives in ``just-dna-enricher`` (``just_dna_enricher.resolver``),
which is deliberately inject-only — it never downloads a reference. This module keeps the
pipelines-specific *provisioning* the library omits: ``ensure_resolver_db`` builds the Ensembl
DuckDB from the local parquet cache, downloading it from HuggingFace Hub if absent. ``resolve_variants``
here provisions that DuckDB on demand and then delegates the actual lookup to the library, so direct
callers keep the pre-extraction behavior. See just-dna-format/docs/{CHANGELOG,ROADMAP}.md.

As of the 0.5 line the lookup moved out of ``just-dna-compiler`` into the enricher's network/reference
tier; ``just_dna_compiler.resolution`` is now purely table-injected (``resolve_from_table``) and carries
no DuckDB path.
"""

import logging
from pathlib import Path
from typing import List, Optional, Tuple

from just_dna_enricher.resolver import EnsemblReferenceError
from just_dna_enricher.resolver import resolve_variants as _lib_resolve_variants

from just_dna_pipelines.module_compiler.models import VariantRow

logger = logging.getLogger(__name__)

__all__ = ["EnsemblReferenceError", "ensure_resolver_db", "resolve_variants"]


def ensure_resolver_db(ensembl_cache: Optional[Path] = None) -> Path:
    """Get or build the Ensembl DuckDB needed for resolution.

    Args:
        ensembl_cache: Explicit path to the Ensembl parquet cache directory.
            If None, uses the default cache location.

    Returns:
        Path to a ready-to-query DuckDB database with ``ensembl_variations`` view.
    """
    from just_dna_pipelines.annotation.duckdb_assets import (
        build_duckdb_from_parquet,
        ensure_ensembl_duckdb_exists,
    )
    from just_dna_pipelines.annotation.resources import get_default_ensembl_cache_dir

    if ensembl_cache is not None:
        db_path = ensembl_cache / "ensembl_variations.duckdb"
        if not db_path.exists():
            logger.info("Building Ensembl DuckDB from parquet cache at %s ...", ensembl_cache)
            build_duckdb_from_parquet(ensembl_cache, db_path, logger=logger)
        return db_path

    cache_dir = get_default_ensembl_cache_dir()
    data_dir = cache_dir / "data"
    if not data_dir.exists() or not any(data_dir.glob("*.parquet")):
        logger.info("Ensembl parquet cache not found — downloading from HuggingFace Hub ...")
        from huggingface_hub import HfFileSystem, get_token

        data_dir.mkdir(parents=True, exist_ok=True)
        fs = HfFileSystem(token=get_token())
        remote_prefix = "datasets/just-dna-seq/ensembl_variations/data"
        remote_files = [
            f for f in fs.ls(remote_prefix, detail=False)
            if f.endswith(".parquet")
        ]
        logger.info("Found %d remote parquet files", len(remote_files))
        for remote_path in remote_files:
            filename = remote_path.rsplit("/", 1)[-1]
            local_path = data_dir / filename
            if local_path.exists():
                continue
            logger.info("  Downloading %s ...", filename)
            fs.get(remote_path, str(local_path))
        logger.info("Download complete: %s", cache_dir)

    return ensure_ensembl_duckdb_exists(logger=logger)


def resolve_variants(
    variants: List[VariantRow],
    ensembl_cache: Optional[Path] = None,
) -> Tuple[List[VariantRow], List[str]]:
    """Fill in missing rsid or position using Ensembl DuckDB (GRCh38).

    Provisions the Ensembl DuckDB via :func:`ensure_resolver_db` (building/downloading it if
    needed), then delegates the lookup to ``just_dna_compiler.resolver.resolve_variants``.
    Variants that already carry both identifiers, or an empty resolution set, short-circuit
    without provisioning.

    Args:
        variants: Validated list of VariantRow objects.
        ensembl_cache: Optional explicit path to the Ensembl parquet cache.

    Returns:
        Tuple of (patched_variants, warnings).
    """
    need_pos = any(v.rsid is not None and v.chrom is None for v in variants)
    need_rsid = any(v.rsid is None and v.chrom is not None for v in variants)
    if not need_pos and not need_rsid:
        return variants, []

    try:
        db_path = ensure_resolver_db(ensembl_cache)
    except FileNotFoundError as exc:
        msg = f"Ensembl resolution skipped: {exc}"
        logger.warning(msg)
        return variants, [msg]

    return _lib_resolve_variants(variants, ensembl_cache=db_path)
