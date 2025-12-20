from pathlib import Path

import polars as pl

from genobear.io import read_vcf_file


def test_read_vcf_file_save_vortex_auto_with_parquet(tmp_path: Path) -> None:
    vcf_path = Path(__file__).resolve().parents[2] / "data" / "input" / "tests" / "antku_small.vcf"
    assert vcf_path.exists(), f"Test VCF file not found: {vcf_path}"

    parquet_path = tmp_path / "variants.parquet"

    lf = read_vcf_file(
        file_path=vcf_path,
        save_parquet=parquet_path,
        save_vortex="auto",
    )

    assert isinstance(lf, pl.LazyFrame), "Expected LazyFrame result"
    assert parquet_path.exists(), f"Expected parquet to be written: {parquet_path}"

    vortex_path = parquet_path.with_suffix(".vortex")
    assert vortex_path.exists(), f"Expected vortex to be written (auto): {vortex_path}"


def test_read_vcf_file_save_vortex_only(tmp_path: Path) -> None:
    vcf_path = Path(__file__).resolve().parents[2] / "data" / "input" / "tests" / "antku_small.vcf"
    assert vcf_path.exists(), f"Test VCF file not found: {vcf_path}"

    vortex_path = tmp_path / "variants_only.vortex"

    lf = read_vcf_file(
        file_path=vcf_path,
        save_parquet=None,
        save_vortex=vortex_path,
    )

    assert isinstance(lf, pl.LazyFrame), "Expected LazyFrame result"
    assert vortex_path.exists(), f"Expected vortex to be written: {vortex_path}"


