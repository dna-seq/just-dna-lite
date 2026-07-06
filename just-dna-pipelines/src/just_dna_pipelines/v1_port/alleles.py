"""
Ref/alt allele lookup from the Ensembl variations parquet cache.

longevitymap's curated data stores only the effect allele + zygosity (het/hom); the reference
allele — needed to build a heterozygous genotype — lived in dbSNP at runtime, not in the module.
This helper reconstructs the ref/alt pair for a set of rsids straight from the local Ensembl cache
(``id``/``ref``/``alt`` columns), so het = ref/alt and hom = effect/effect.
"""

from pathlib import Path
from typing import Optional

import polars as pl


def _data_dir(ensembl_cache: Path) -> Optional[Path]:
    if (ensembl_cache / "data").is_dir():
        return ensembl_cache / "data"
    if ensembl_cache.is_dir() and any(ensembl_cache.glob("*.parquet")):
        return ensembl_cache
    return None


def lookup_alleles(
    rsids: set[str], ensembl_cache: Optional[Path]
) -> dict[str, tuple[Optional[str], Optional[str]]]:
    """Return ``{rsid: (ref, alt)}`` for the given rsids from the Ensembl cache (empty if absent)."""
    if not rsids or ensembl_cache is None:
        return {}
    data = _data_dir(ensembl_cache)
    if data is None:
        return {}
    got = (
        pl.scan_parquet(str(data / "*.parquet"))
        .filter(pl.col("id").is_in(list(rsids)))
        .select(["id", "ref", "alt"])
        .unique(subset=["id"])
        .collect(engine="streaming")
    )
    return {row["id"]: (row["ref"], row["alt"]) for row in got.iter_rows(named=True)}
