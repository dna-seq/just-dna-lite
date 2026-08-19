"""Verify CI annotation output exists and has expected structure."""

from pathlib import Path

import polars as pl

SAMPLE_DIR = Path("data/output/users/ci_test/antku_small")


def main() -> None:
    normalized = SAMPLE_DIR / "user_vcf_normalized.parquet"
    assert normalized.exists(), f"Missing normalized parquet: {normalized}"
    norm_df = pl.read_parquet(normalized)
    assert norm_df.height > 0, "Empty normalized VCF"
    print(f"OK: {norm_df.height} normalized variants")

    weights = list((SAMPLE_DIR / "modules").glob("*_weights.parquet"))
    assert len(weights) >= 1, "No weight parquet files found"
    weights_df = pl.read_parquet(weights[0])
    for col in ("chrom", "start", "genotype"):
        assert col in weights_df.columns, f"Missing column {col} in {weights[0].name}"
    print(
        f"OK: {weights[0].name} present "
        f"({weights_df.height} annotated rows; zero is ok for a tiny fixture VCF)"
    )

    manifest = SAMPLE_DIR / "modules" / "manifest.json"
    assert manifest.exists(), "No manifest.json found"
    print("OK: manifest.json present")

    # The report stem is derived from the selected module (report_logic.report_filename_stem),
    # so match any HTML in reports/ rather than a single hardcoded name.
    reports = list((SAMPLE_DIR / "reports").glob("*.html"))
    assert len(reports) >= 1, "No HTML report found in reports/"
    latest = max(reports, key=lambda path: path.stat().st_mtime)
    assert latest.stat().st_size > 0, "Empty HTML report"
    print(f"OK: report {latest.name}")


if __name__ == "__main__":
    main()
