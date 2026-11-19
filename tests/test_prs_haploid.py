"""A one-allele genotype (male chrX, chrM) is scored, as one copy at most, by both engines.

just-prs 0.10.1 raised ``ComputeError: get index is out of bounds`` on a haploid GT such as ``"1"`` in
its Polars engine, the one the web UI's single-score path calls, while its DuckDB engine scored the row
(docs/INVESTIGATE_HAPLOID_PRS.md). Fixed upstream in 0.10.3. The expected score is computed here from
the genotypes, never copied from a run.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from just_prs.prs import compute_prs, compute_prs_duckdb

# (chrom, pos, ref, alt, GT, effect_allele, weight)
SITES: list[tuple[str, int, str, str, str, str, float]] = [
    ("1", 1000, "A", "G", "0/1", "G", 0.5),   # diploid, one copy
    ("2", 2000, "C", "T", "1/1", "T", 0.25),  # diploid, two copies
    ("X", 3000, "G", "A", "1", "A", 2.0),     # haploid alt: one copy
    ("X", 4000, "T", "C", "0", "C", 4.0),     # haploid ref: no copy of the effect allele
    ("MT", 5000, "A", "G", "1", "G", 8.0),    # haploid alt on the mitochondrion
]


def _copies(gt: str) -> int:
    """Copies of the ALT allele a GT string states: one allele gives one copy at most."""
    return sum(1 for allele in gt.replace("|", "/").split("/") if allele == "1")


def _genotypes() -> pl.LazyFrame:
    return pl.LazyFrame(
        {
            "chrom": [s[0] for s in SITES],
            "pos": [s[1] for s in SITES],
            "ref": [s[2] for s in SITES],
            "alt": [s[3] for s in SITES],
            "GT": [s[4] for s in SITES],
        },
        schema_overrides={"pos": pl.Int64},
    )


def _scoring() -> pl.LazyFrame:
    return pl.LazyFrame(
        {
            "chr_name": [s[0] for s in SITES],
            "chr_position": [s[1] for s in SITES],
            "effect_allele": [s[5] for s in SITES],
            "other_allele": [s[2] for s in SITES],
            "effect_weight": [s[6] for s in SITES],
        },
        schema_overrides={"chr_position": pl.Int64},
    )


EXPECTED = sum(weight * _copies(gt) for *_, gt, _allele, weight in SITES)


@pytest.mark.parametrize("engine", [compute_prs, compute_prs_duckdb], ids=["polars", "duckdb"])
def test_a_haploid_genotype_scores_as_one_copy(engine, tmp_path: Path) -> None:
    result = engine(
        vcf_path=tmp_path / "unused.vcf",
        scoring_file=_scoring(),
        cache_dir=tmp_path,
        pgs_id="TEST_HAPLOID",
        genotypes_lf=_genotypes(),
    )
    assert result.variants_matched == len(SITES)
    assert result.score == pytest.approx(EXPECTED)


def test_the_two_engines_agree_on_haploid_calls(tmp_path: Path) -> None:
    kwargs = {
        "vcf_path": tmp_path / "unused.vcf",
        "scoring_file": _scoring(),
        "cache_dir": tmp_path,
        "pgs_id": "TEST_HAPLOID",
        "genotypes_lf": _genotypes(),
    }
    assert compute_prs(**kwargs).score == pytest.approx(compute_prs_duckdb(**kwargs).score)
