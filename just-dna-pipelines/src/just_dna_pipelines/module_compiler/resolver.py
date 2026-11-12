"""
Ensembl rsid <-> position resolution for just-dna-pipelines.

The rsid/position *lookup* logic lives in ``just-dna-enricher`` (``just_dna_enricher.resolver``),
which is deliberately inject-only — it never downloads a reference. This module keeps the
pipelines-specific step: ``ensure_resolver_db`` has the enricher's ``ensembl`` lane provision the
parquet (``download.ensure_snapshot``) and builds our DuckDB view over it. ``resolve_variants``
here provisions that DuckDB on demand and then delegates the actual lookup to the library, so direct
callers keep the pre-extraction behavior. See just-dna-format/docs/{CHANGELOG,ROADMAP}.md.

As of the 0.5 line the lookup moved out of ``just-dna-compiler`` into the enricher's network/reference
tier; ``just_dna_compiler.resolution`` is now purely table-injected (``resolve_from_table``) and carries
no DuckDB path.
"""

import logging
from pathlib import Path
from typing import List, Optional, Tuple

from just_dna_enricher.download import ensure_snapshot
from just_dna_enricher.locations import parquet_footer_ok
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
    had_corrupt = any(not parquet_footer_ok(p) for p in data_dir.glob("*.parquet")) if data_dir.exists() else False

    # The enricher's lane provisions the parquet: it trusts a cache its pull record calls whole,
    # removes and refetches a truncated file, and re-pulls a cache of another repo (RM372).
    ensure_snapshot(cache_dir)
    if had_corrupt:
        # The DuckDB view was built over a file the pull just replaced; drop it so it rebuilds.
        (cache_dir / "ensembl_variations.duckdb").unlink(missing_ok=True)

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
