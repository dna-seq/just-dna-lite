"""Regions of GRCh38 where a missing call on a whole genome does not mean "reference".

On a whole-genome callset a site the caller did not emit is almost always homozygous reference: a
plain (non-g) VCF from a WGS run is a complete statement about every base the reads covered well.
That is the assumption reference-genotype restoration (``restoration.py``) and the phenotype caller
build on. It fails where short reads cannot be placed: segmental duplications and low-mappability
sequence, where reads from a paralog land elsewhere or are filtered for low MAPQ and the caller
emits nothing whatever the sample carries. RHD/RHCE is the textbook case: the two genes are near
identical, and one real genome here has a 72 kb stretch with no calls across RHD.

This module is the **first-order** answer: a published mask of those regions, inside which no
absence is ever read as reference. It is deliberately coarse (a site is in or out), and the better
answer is probabilistic: the chance a variant at this base would have been called, from population
coverage (gnomAD's per-base depth summaries), which is the planned next step.

The mask is GIAB's genome stratifications v3.6, GRCh38, the union of low-mappability regions and
segmental duplications (``GRCh38_alllowmapandsegdupregions.bed.gz``, 9.9% of the genome). The wider
``alldifficultregions`` union (20%) was measured and rejected: it adds homopolymers, tandem repeats
and GC extremes, which a WGS caller handles well at a SNV, and it would switch inference off at
both APOE sites and at FUT2.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Optional

import fsspec
import polars as pl
from eliot import log_message

from just_dna_pipelines.annotation.resources import get_cache_dir

GIAB_STRATIFICATION_VERSION = "v3.6"
HARD_REGIONS_FILE = "GRCh38_alllowmapandsegdupregions.bed.gz"
HARD_REGIONS_URL = (
    "https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/genome-stratifications/"
    f"{GIAB_STRATIFICATION_VERSION}/GRCh38@all/Union/{HARD_REGIONS_FILE}"
)
# From GIAB's own GRCh38-genome-stratifications-md5s.txt for this release.
HARD_REGIONS_MD5 = "b1b8a7e364aa8bc6b470b3b549e126d6"
HARD_REGIONS_DESCRIPTION = (
    f"GIAB genome stratifications {GIAB_STRATIFICATION_VERSION} (GRCh38): low mappability and "
    "segmental duplications"
)


def hard_regions_path() -> Path:
    return get_cache_dir() / "giab_stratifications" / GIAB_STRATIFICATION_VERSION / HARD_REGIONS_FILE


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_hard_regions() -> Path:
    """Download the mask into the cache if it is absent or damaged; return its path.

    Written to ``<file>.part`` and moved into place only after its md5 matches GIAB's published
    checksum, so a killed download never leaves a truncated mask that loads as "fewer hard regions".
    """
    target = hard_regions_path()
    if target.exists() and _md5(target) == HARD_REGIONS_MD5:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    with fsspec.open(HARD_REGIONS_URL, "rb") as remote, partial.open("wb") as local:
        for block in iter(lambda: remote.read(1 << 20), b""):
            local.write(block)
    actual = _md5(partial)
    if actual != HARD_REGIONS_MD5:
        partial.unlink()
        raise ValueError(
            f"{HARD_REGIONS_URL} downloaded with md5 {actual}, expected {HARD_REGIONS_MD5}"
        )
    partial.replace(target)
    return target


@lru_cache(maxsize=1)
def _load_cached(path_str: str) -> pl.DataFrame:
    return read_hard_regions(Path(path_str))


def read_hard_regions(path: Path) -> pl.DataFrame:
    """Read a BED mask into ``chrom`` (no ``chr`` prefix), ``region_start`` (0-based), ``region_end``.

    Sorted by ``(chrom, region_start)``, the order :func:`mark_hard_regions` joins on. The GIAB union
    is already merged, so intervals do not overlap and the nearest start at or before a site is the
    only interval that can contain it.
    """
    return (
        pl.read_csv(
            path,
            separator="\t",
            has_header=False,
            comment_prefix="#",
            columns=[0, 1, 2],
            new_columns=["chrom", "region_start", "region_end"],
            schema_overrides={"chrom": pl.String, "region_start": pl.Int64, "region_end": pl.Int64},
        )
        .with_columns(pl.col("chrom").str.replace(r"^chr", ""))
        .sort(["chrom", "region_start"])
    )


def load_hard_regions() -> tuple[Optional[pl.DataFrame], str]:
    """The mask, provisioning it on first use, or ``(None, reason)`` when it cannot be had.

    A missing mask is not a reason to stop annotating, but it is never silent: the reason is logged
    and travels on the restoration context, and restoration then falls back to what it did before
    the mask existed (the flank gate alone, and ``requires_callable`` rows withheld).
    """
    try:
        path = ensure_hard_regions()
    except Exception as exc:  # network or disk: the fallback is defined and reported
        reason = f"hard-region mask unavailable ({type(exc).__name__}: {exc}); {HARD_REGIONS_URL}"
        log_message(message_type="hard_regions", step="unavailable", reason=reason)
        return None, reason
    return _load_cached(str(path)), HARD_REGIONS_DESCRIPTION


IN_HARD_REGION = "_in_hard_region"


def mark_hard_regions(sites: pl.LazyFrame, regions: pl.DataFrame) -> pl.LazyFrame:
    """Add a boolean ``_in_hard_region`` column to a frame carrying ``chrom`` and 1-based ``start``.

    A 1-based position ``p`` lies in a 0-based half-open BED interval ``[s, e)`` when ``s < p <= e``.
    The input's row order is not preserved (the as-of join sorts), which no caller relies on.
    """
    probe = sites.with_columns(pl.col("start").cast(pl.Int64).alias("_pos"))
    joined = probe.sort(["chrom", "_pos"]).join_asof(
        regions.lazy().sort(["chrom", "region_start"]),
        left_on="_pos",
        right_on="region_start",
        by="chrom",
        strategy="backward",
        check_sortedness=False,
    )
    return joined.with_columns(
        (
            pl.col("region_start").is_not_null()
            & (pl.col("_pos") > pl.col("region_start"))
            & (pl.col("_pos") <= pl.col("region_end"))
        ).alias(IN_HARD_REGION)
    ).drop("_pos", "region_start", "region_end")


def fraction_in_hard_regions(chrom: str, start: int, end: int, regions: pl.DataFrame) -> float:
    """Share of the 1-based closed span ``[start, end]`` covered by the mask."""
    length = end - start + 1
    if length <= 0:
        return 0.0
    overlap = (
        regions.filter(
            (pl.col("chrom") == chrom)
            & (pl.col("region_end") >= start)
            & (pl.col("region_start") < end)
        )
        .select(
            (
                pl.min_horizontal(pl.col("region_end"), pl.lit(end))
                - pl.max_horizontal(pl.col("region_start"), pl.lit(start - 1))
            ).sum()
        )
        .item()
    )
    return float(overlap or 0) / length
