"""
Bidirectional rsid <-> position resolver using Ensembl DuckDB.

Resolves missing rsid or position fields on VariantRow objects
by looking up the local Ensembl variations cache (GRCh38).

When the Ensembl DuckDB doesn't exist, it is auto-built from
the Ensembl parquet cache (downloaded via the Dagster asset or HF Hub).
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import duckdb

from just_dna_pipelines.module_compiler.models import VariantRow

logger = logging.getLogger(__name__)


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

    - Variants with rsid but no position → look up chrom/start/ref/alts
    - Variants with position but no rsid → look up rsid

    Variants that already have both identifiers are left unchanged.

    Args:
        variants: Validated list of VariantRow objects.
        ensembl_cache: Optional explicit path to Ensembl cache.

    Returns:
        Tuple of (patched_variants, warnings).
    """
    need_pos = [v for v in variants if v.rsid is not None and v.chrom is None]
    need_rsid = [v for v in variants if v.rsid is None and v.chrom is not None]

    if not need_pos and not need_rsid:
        return variants, []

    try:
        db_path = ensure_resolver_db(ensembl_cache)
    except FileNotFoundError as exc:
        msg = f"Ensembl resolution skipped: {exc}"
        logger.warning(msg)
        return variants, [msg]

    con = duckdb.connect(str(db_path), read_only=True)
    warnings: List[str] = []

    rsid_to_pos: Dict[str, Dict] = {}
    if need_pos:
        unique_rsids = list({v.rsid for v in need_pos if v.rsid is not None})
        rsid_to_pos = _lookup_positions_by_rsid(con, unique_rsids, warnings)

    pos_to_rsid: Dict[str, str] = {}
    if need_rsid:
        unique_positions = list({
            (v.chrom, v.start, v.ref)
            for v in need_rsid
            if v.chrom is not None and v.start is not None
        })
        pos_to_rsid = _lookup_rsids_by_position(con, unique_positions, warnings)

    con.close()

    patched: List[VariantRow] = []
    for v in variants:
        if v.rsid is not None and v.chrom is None and v.rsid in rsid_to_pos:
            patched.append(v.model_copy(update=rsid_to_pos[v.rsid]))
        elif v.rsid is None and v.chrom is not None:
            key = f"{v.chrom}:{v.start}:{v.ref}"
            if key in pos_to_rsid:
                patched.append(v.model_copy(update={"rsid": pos_to_rsid[key]}))
            else:
                warnings.append(f"Position {key}: no rsid found in Ensembl")
                patched.append(v)
        else:
            patched.append(v)

    resolved_pos = sum(1 for v in need_pos if v.rsid is not None and v.rsid in rsid_to_pos)
    resolved_rsid = sum(
        1 for v in need_rsid
        if f"{v.chrom}:{v.start}:{v.ref}" in pos_to_rsid
    )
    logger.info(
        "Resolved %d/%d rsid->pos, %d/%d pos->rsid",
        resolved_pos, len(need_pos), resolved_rsid, len(need_rsid),
    )
    return patched, warnings


def _lookup_positions_by_rsid(
    con: duckdb.DuckDBPyConnection,
    rsids: List[str],
    warnings: List[str],
) -> Dict[str, Dict]:
    """Batch lookup: rsid -> {chrom, start, ref, alts}."""
    if not rsids:
        return {}

    placeholders = ", ".join(f"'{r}'" for r in rsids)
    rows = con.execute(f"""
        SELECT id, chrom, start, ref,
               string_agg(DISTINCT alt, ',' ORDER BY alt) AS alts
        FROM ensembl_variations
        WHERE id IN ({placeholders})
        GROUP BY id, chrom, start, ref
    """).fetchall()

    result: Dict[str, Dict] = {}
    for row_id, chrom, start, ref, alts in rows:
        if row_id in result:
            continue
        result[row_id] = {
            "chrom": str(chrom),
            "start": int(start),
            "ref": str(ref),
            "alts": str(alts),
        }

    for rsid in rsids:
        if rsid not in result:
            warnings.append(f"{rsid}: not found in Ensembl, position remains unset")
    return result


def _lookup_rsids_by_position(
    con: duckdb.DuckDBPyConnection,
    positions: List[Tuple[Optional[str], Optional[int], Optional[str]]],
    warnings: List[str],
) -> Dict[str, str]:
    """Batch lookup: (chrom, start, ref) -> rsid."""
    if not positions:
        return {}

    conditions = []
    for chrom, start, ref in positions:
        if ref is not None:
            conditions.append(
                f"(chrom = '{chrom}' AND start = {start} AND ref = '{ref}')"
            )
        else:
            conditions.append(f"(chrom = '{chrom}' AND start = {start})")
    where = " OR ".join(conditions)

    rows = con.execute(f"""
        SELECT DISTINCT chrom, start, ref, id
        FROM ensembl_variations
        WHERE ({where}) AND id LIKE 'rs%'
    """).fetchall()

    result: Dict[str, str] = {}
    for chrom, start, ref, row_id in rows:
        key = f"{chrom}:{start}:{ref}"
        if key not in result:
            result[key] = str(row_id)
    return result
