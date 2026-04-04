"""Verify CI annotation output exists and has expected structure."""

from pathlib import Path

import polars as pl

OUTPUT_DIR = Path("data/output/users/ci_test")


def main() -> None:
    parquets = list(OUTPUT_DIR.rglob("*_weights.parquet"))
    assert len(parquets) >= 1, "No weight parquet files found"

    df = pl.read_parquet(parquets[0])
    assert df.height > 0, "Empty annotation result"
    for col in ("chrom", "start", "genotype"):
        assert col in df.columns, f"Missing column {col}"
    print(f"OK: {df.height} annotated variants in {parquets[0].name}")

    manifest = list(OUTPUT_DIR.rglob("manifest.json"))
    assert len(manifest) >= 1, "No manifest.json found"
    print("OK: manifest.json present")


if __name__ == "__main__":
    main()
