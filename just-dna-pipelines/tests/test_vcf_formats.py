#!/usr/bin/env python3
"""
Tests for VCF FORMAT field reading via read_vcf_file.

Tests verify:
- Type correctness: FORMAT fields have proper types (Int32, List[Int32], etc.)
- Genotype computation: GT + ref + alt → sorted allele list
- Determinism: multiple collects return identical results
- Row alignment: FORMAT fields are correctly aligned with VCF coordinates
- Ground truth: FORMAT values match raw VCF parsing when converted

Note: polars-bio natively handles FORMAT fields with types:
- GT: String
- GQ: Int32
- DP: Int32
- AD: List(Int32)
- VAF: List(Float32)
- PL: List(Int32)
"""

from pathlib import Path
from typing import Any

import polars as pl
import pytest

from just_dna_pipelines.io import read_vcf_file


@pytest.fixture
def test_vcf_path() -> Path:
    """Path to the test VCF file."""
    # Navigate from tests/ -> just-dna-pipelines/ -> just-dna-lite/
    base = Path(__file__).parent.parent.parent
    return base / "data" / "input" / "tests" / "antku_small.vcf"


@pytest.fixture
def expected_format_order() -> list[str]:
    """FORMAT field order from the test VCF (GT:GQ:DP:AD:VAF:PL)."""
    return ["GT", "GQ", "DP", "AD", "VAF", "PL"]


@pytest.fixture
def raw_vcf_ground_truth(test_vcf_path: Path) -> list[dict[str, Any]]:
    """
    Parse raw VCF to get ground truth FORMAT values.
    
    Returns list of dicts with chrom, pos, ref, alt, and FORMAT fields.
    FORMAT values are converted to proper types for comparison.
    """
    rows = []
    with open(test_vcf_path, "r") as f:
        for line in f:
            if line.startswith("#"):
                continue
            cols = line.strip().split("\t")
            format_keys = cols[8].split(":")
            sample_values = cols[9].split(":")
            
            row: dict[str, Any] = {
                "chrom": cols[0],
                "pos": int(cols[1]),
                "ref": cols[3],
                "alt": cols[4],
            }
            for key, val in zip(format_keys, sample_values):
                row[key] = val
            rows.append(row)
    return rows


def parse_gt_to_genotype(gt: str, ref: str, alt: str) -> list[str]:
    """Compute expected genotype from GT, REF, ALT (ground truth helper).
    
    Note: polars-bio uses "|" as separator for multi-allelic ALT alleles.
    For raw VCF parsing (ground truth), ALT uses "," as separator.
    """
    if gt in (".", "./.", ".|."):
        return []
    
    # Build alleles array: [REF, ALT1, ALT2, ...]
    # Raw VCF uses comma separator, polars-bio uses pipe
    # Handle both separators for compatibility
    if "|" in alt:
        alt_alleles = alt.split("|")
    else:
        alt_alleles = alt.split(",")
    alleles = [ref] + alt_alleles
    
    indices = gt.replace("|", "/").split("/")
    genotype = []
    for idx in indices:
        if idx == ".":
            continue
        try:
            genotype.append(alleles[int(idx)])
        except (ValueError, IndexError):
            continue
    
    return sorted(genotype)


# =============================================================================
# Type correctness tests
# =============================================================================


def test_format_field_types(test_vcf_path: Path) -> None:
    """FORMAT fields should have correct Polars types per polars-bio spec."""
    lf = read_vcf_file(str(test_vcf_path), with_formats=True, save_parquet=None)
    schema = lf.collect_schema()
    
    # GT stays as String
    assert schema["GT"] == pl.String, f"GT should be String, got {schema['GT']}"
    
    # Integer fields (polars-bio uses Int32)
    assert schema["GQ"] == pl.Int32, f"GQ should be Int32, got {schema['GQ']}"
    assert schema["DP"] == pl.Int32, f"DP should be Int32, got {schema['DP']}"
    
    # List of integers (polars-bio uses Int32)
    assert schema["AD"] == pl.List(pl.Int32), f"AD should be List(Int32), got {schema['AD']}"
    assert schema["PL"] == pl.List(pl.Int32), f"PL should be List(Int32), got {schema['PL']}"
    
    # List of floats (polars-bio uses Float32)
    assert schema["VAF"] == pl.List(pl.Float32), f"VAF should be List(Float32), got {schema['VAF']}"
    
    # Genotype column (computed by read_vcf_file)
    assert schema["genotype"] == pl.List(pl.String), f"genotype should be List(String), got {schema['genotype']}"


def test_integer_fields_values(test_vcf_path: Path, raw_vcf_ground_truth: list[dict]) -> None:
    """GQ and DP values should match raw VCF when parsed as integers."""
    lf = read_vcf_file(str(test_vcf_path), with_formats=True, save_parquet=None)
    df = lf.collect()
    
    # Sample multiple rows for verification
    sample_indices = [0, 1, 10, 50, 100, len(raw_vcf_ground_truth) - 1]
    sample_indices = [i for i in sample_indices if i < len(raw_vcf_ground_truth)]
    
    for idx in sample_indices:
        expected = raw_vcf_ground_truth[idx]
        actual = df.row(idx, named=True)
        
        # GQ
        expected_gq = None if expected.get("GQ") == "." else int(expected["GQ"])
        assert actual["GQ"] == expected_gq, (
            f"Row {idx}: GQ mismatch - got {actual['GQ']}, expected {expected_gq}"
        )
        
        # DP
        expected_dp = None if expected.get("DP") == "." else int(expected["DP"])
        assert actual["DP"] == expected_dp, (
            f"Row {idx}: DP mismatch - got {actual['DP']}, expected {expected_dp}"
        )


def test_list_integer_fields_values(test_vcf_path: Path, raw_vcf_ground_truth: list[dict]) -> None:
    """AD and PL values should match raw VCF when parsed as list of integers."""
    lf = read_vcf_file(str(test_vcf_path), with_formats=True, save_parquet=None)
    df = lf.collect()
    
    sample_indices = [0, 1, 10, 50, 100, len(raw_vcf_ground_truth) - 1]
    sample_indices = [i for i in sample_indices if i < len(raw_vcf_ground_truth)]
    
    for idx in sample_indices:
        expected = raw_vcf_ground_truth[idx]
        actual = df.row(idx, named=True)
        
        # AD
        if expected.get("AD") == ".":
            assert actual["AD"] is None, f"Row {idx}: AD should be None for missing value"
        else:
            expected_ad = [int(x) for x in expected["AD"].split(",")]
            assert actual["AD"] == expected_ad, (
                f"Row {idx}: AD mismatch - got {actual['AD']}, expected {expected_ad}"
            )
        
        # PL
        if expected.get("PL") == ".":
            assert actual["PL"] is None, f"Row {idx}: PL should be None for missing value"
        else:
            expected_pl = [int(x) for x in expected["PL"].split(",")]
            assert actual["PL"] == expected_pl, (
                f"Row {idx}: PL mismatch - got {actual['PL']}, expected {expected_pl}"
            )


def test_vaf_float_list_values(test_vcf_path: Path, raw_vcf_ground_truth: list[dict]) -> None:
    """VAF values should match raw VCF when parsed as list of floats."""
    lf = read_vcf_file(str(test_vcf_path), with_formats=True, save_parquet=None)
    df = lf.collect()
    
    sample_indices = [0, 1, 10, 50, 100, len(raw_vcf_ground_truth) - 1]
    sample_indices = [i for i in sample_indices if i < len(raw_vcf_ground_truth)]
    
    for idx in sample_indices:
        expected = raw_vcf_ground_truth[idx]
        actual = df.row(idx, named=True)
        
        if expected.get("VAF") == ".":
            assert actual["VAF"] is None, f"Row {idx}: VAF should be None for missing value"
        else:
            expected_vaf = [float(x) for x in expected["VAF"].split(",")]
            actual_vaf = actual["VAF"]
            assert len(actual_vaf) == len(expected_vaf), (
                f"Row {idx}: VAF length mismatch - got {len(actual_vaf)}, expected {len(expected_vaf)}"
            )
            for j, (a, e) in enumerate(zip(actual_vaf, expected_vaf)):
                assert abs(a - e) < 1e-6, (
                    f"Row {idx}: VAF[{j}] mismatch - got {a}, expected {e}"
                )


# =============================================================================
# Genotype computation tests
# =============================================================================


def test_genotype_computation_heterozygous(test_vcf_path: Path) -> None:
    """Heterozygous variants should have two different alleles in genotype."""
    lf = read_vcf_file(str(test_vcf_path), with_formats=True, save_parquet=None)
    df = lf.filter(pl.col("GT") == "0/1").collect()
    
    # Should have heterozygous variants
    assert df.height > 0, "Test VCF should contain heterozygous (0/1) variants"
    
    for row in df.iter_rows(named=True):
        ref = row["ref"]
        alt = row["alt"]
        genotype = row["genotype"]
        
        # For multi-allelic sites, polars-bio uses "|" separator
        # 0/1 means REF + first ALT allele
        alt_alleles = alt.split("|")
        first_alt = alt_alleles[0]
        
        # Genotype should contain REF and first ALT (sorted)
        expected = sorted([ref, first_alt])
        assert genotype == expected, (
            f"Het variant at {row['chrom']}:{row['start']} - "
            f"expected {expected}, got {genotype}"
        )


def test_genotype_computation_homozygous_ref(test_vcf_path: Path) -> None:
    """Homozygous ref variants should have two copies of REF allele."""
    lf = read_vcf_file(str(test_vcf_path), with_formats=True, save_parquet=None)
    df = lf.filter(pl.col("GT") == "0/0").collect()
    
    # Should have homozygous ref variants
    assert df.height > 0, "Test VCF should contain homozygous ref (0/0) variants"
    
    for row in df.iter_rows(named=True):
        ref = row["ref"]
        genotype = row["genotype"]
        
        # Genotype should be [ref, ref]
        expected = [ref, ref]
        assert genotype == expected, (
            f"Hom ref variant at {row['chrom']}:{row['start']} - "
            f"expected {expected}, got {genotype}"
        )


def test_genotype_computation_homozygous_alt(test_vcf_path: Path) -> None:
    """Homozygous alt variants should have two copies of ALT allele."""
    lf = read_vcf_file(str(test_vcf_path), with_formats=True, save_parquet=None)
    df = lf.filter(pl.col("GT") == "1/1").collect()
    
    # Should have homozygous alt variants
    assert df.height > 0, "Test VCF should contain homozygous alt (1/1) variants"
    
    for row in df.iter_rows(named=True):
        alt = row["alt"]
        genotype = row["genotype"]
        
        # Genotype should be [alt, alt]
        expected = [alt, alt]
        assert genotype == expected, (
            f"Hom alt variant at {row['chrom']}:{row['start']} - "
            f"expected {expected}, got {genotype}"
        )


def test_genotype_ground_truth_alignment(
    test_vcf_path: Path, 
    raw_vcf_ground_truth: list[dict]
) -> None:
    """Genotype column should match computed ground truth for all rows."""
    lf = read_vcf_file(str(test_vcf_path), with_formats=True, save_parquet=None)
    df = lf.collect()
    
    assert df.height == len(raw_vcf_ground_truth), "Row count mismatch with ground truth"
    
    # Check every row
    for idx, expected in enumerate(raw_vcf_ground_truth):
        actual = df.row(idx, named=True)
        
        expected_genotype = parse_gt_to_genotype(
            expected["GT"], expected["ref"], expected["alt"]
        )
        actual_genotype = actual["genotype"]
        
        assert actual_genotype == expected_genotype, (
            f"Row {idx} ({expected['chrom']}:{expected['pos']}): "
            f"genotype mismatch - got {actual_genotype}, expected {expected_genotype}"
        )


def test_genotype_disabled(test_vcf_path: Path) -> None:
    """compute_genotype=False should not add genotype column."""
    lf = read_vcf_file(str(test_vcf_path), with_formats=True, save_parquet=None, compute_genotype=False)
    df = lf.collect()
    
    assert "genotype" not in df.columns, "genotype column should not be present when disabled"


def test_genotype_requires_gt_field(test_vcf_path: Path) -> None:
    """Genotype is only computed when GT is in format_fields."""
    # Use only GT field to verify genotype is computed
    lf_with_gt = read_vcf_file(
        str(test_vcf_path), 
        with_formats=True,
        save_parquet=None,
        format_fields=["GT"],
        compute_genotype=True
    )
    df_with_gt = lf_with_gt.collect()
    assert "genotype" in df_with_gt.columns, (
        "genotype column should be present when GT is in format_fields"
    )
    
    # When format_fields is empty, no genotype should be computed
    lf_no_formats = read_vcf_file(
        str(test_vcf_path), 
        with_formats=True,
        save_parquet=None,
        format_fields=[],
        compute_genotype=True
    )
    df_no_formats = lf_no_formats.collect()
    assert "genotype" not in df_no_formats.columns, (
        "genotype column should not be present when format_fields is empty"
    )


# =============================================================================
# Determinism and alignment tests
# =============================================================================


def test_read_vcf_determinism(
    test_vcf_path: Path, 
    expected_format_order: list[str]
) -> None:
    """Multiple collects should return identical results."""
    results = []
    for _ in range(5):
        lf = read_vcf_file(str(test_vcf_path), with_formats=True, save_parquet=None, format_fields=expected_format_order)
        df = lf.collect()
        results.append(df)
    
    for i in range(1, len(results)):
        assert results[0].equals(results[i]), f"Result {i} differs from result 0"


def test_read_vcf_row_count(
    test_vcf_path: Path, 
    raw_vcf_ground_truth: list[dict]
) -> None:
    """Row count should match raw VCF line count."""
    lf = read_vcf_file(str(test_vcf_path), with_formats=True, save_parquet=None)
    df = lf.collect()
    
    assert df.height == len(raw_vcf_ground_truth), (
        f"Row count mismatch: got {df.height}, expected {len(raw_vcf_ground_truth)}"
    )


def test_read_vcf_columns(
    test_vcf_path: Path, 
    expected_format_order: list[str]
) -> None:
    """Output should contain standard VCF columns plus requested FORMAT fields."""
    lf = read_vcf_file(str(test_vcf_path), with_formats=True, save_parquet=None, format_fields=expected_format_order)
    df = lf.collect()
    
    # Standard polars-bio columns
    expected_base_cols = {"chrom", "start", "end", "id", "ref", "alt", "qual", "filter"}
    
    actual_cols = set(df.columns)
    
    # All base columns should be present
    assert expected_base_cols.issubset(actual_cols), (
        f"Missing base columns: {expected_base_cols - actual_cols}"
    )
    
    # All FORMAT fields should be present
    assert set(expected_format_order).issubset(actual_cols), (
        f"Missing FORMAT columns: {set(expected_format_order) - actual_cols}"
    )
    
    # Genotype column should be present (default)
    assert "genotype" in actual_cols, "genotype column should be present by default"


def test_read_vcf_coordinate_alignment(
    test_vcf_path: Path, 
    raw_vcf_ground_truth: list[dict],
) -> None:
    """Coordinates and alleles should be correctly aligned with VCF."""
    lf = read_vcf_file(str(test_vcf_path), with_formats=True, save_parquet=None)
    df = lf.collect()
    
    # Check alignment for multiple rows
    sample_indices = [0, 1, 10, 50, 100, len(raw_vcf_ground_truth) - 1]
    sample_indices = [i for i in sample_indices if i < len(raw_vcf_ground_truth)]
    
    for idx in sample_indices:
        expected = raw_vcf_ground_truth[idx]
        actual = df.row(idx, named=True)
        
        # polars-bio uses 'start' which is 0-based, VCF POS is 1-based
        # But polars-bio seems to keep the original position
        assert actual["chrom"] == expected["chrom"], f"Row {idx}: chrom mismatch"
        assert actual["start"] == expected["pos"], f"Row {idx}: pos mismatch"
        assert actual["ref"] == expected["ref"], f"Row {idx}: ref mismatch"
        assert actual["alt"] == expected["alt"], f"Row {idx}: alt mismatch"


def test_read_vcf_empty_format_fields(test_vcf_path: Path) -> None:
    """Empty format_fields should return polars-bio result only."""
    lf = read_vcf_file(str(test_vcf_path), with_formats=True, save_parquet=None, format_fields=[])
    df = lf.collect()
    
    # Should not have any FORMAT columns
    format_cols = {"GT", "GQ", "DP", "AD", "VAF", "PL", "genotype"}
    actual_cols = set(df.columns)
    
    assert not format_cols.intersection(actual_cols), (
        f"FORMAT columns should not be present: {format_cols.intersection(actual_cols)}"
    )


# =============================================================================
# Filtering and aggregation tests (practical usage)
# =============================================================================


def test_filter_by_depth(test_vcf_path: Path) -> None:
    """Should be able to filter variants by read depth (DP)."""
    lf = read_vcf_file(str(test_vcf_path), with_formats=True, save_parquet=None)
    
    # Filter for high-depth variants
    df_high_dp = lf.filter(pl.col("DP") >= 30).collect()
    
    # All variants should have DP >= 30
    assert (df_high_dp["DP"] >= 30).all(), "All filtered variants should have DP >= 30"
    
    # Should have fewer variants than total
    df_all = lf.collect()
    assert df_high_dp.height < df_all.height, "High DP filter should reduce variant count"


def test_filter_by_genotype_quality(test_vcf_path: Path) -> None:
    """Should be able to filter variants by genotype quality (GQ)."""
    lf = read_vcf_file(str(test_vcf_path), with_formats=True, save_parquet=None)
    
    # Filter for high-quality genotype calls
    df_high_gq = lf.filter(pl.col("GQ") >= 20).collect()
    
    # All variants should have GQ >= 20
    assert (df_high_gq["GQ"] >= 20).all(), "All filtered variants should have GQ >= 20"


def test_filter_by_genotype(test_vcf_path: Path) -> None:
    """Should be able to filter variants by GT string."""
    lf = read_vcf_file(str(test_vcf_path), with_formats=True, save_parquet=None)
    
    # Filter for heterozygous variants
    df_het = lf.filter(pl.col("GT") == "0/1").collect()
    
    # All should be heterozygous
    assert (df_het["GT"] == "0/1").all(), "All filtered variants should be 0/1"


def test_aggregate_ad_values(test_vcf_path: Path) -> None:
    """AD (allelic depth) list should be usable for computations."""
    lf = read_vcf_file(str(test_vcf_path), with_formats=True, save_parquet=None)
    df = lf.collect()
    
    # Compute total AD per variant (sum of all allele depths)
    df_with_total = df.with_columns(
        pl.col("AD").list.sum().alias("total_ad")
    )
    
    # Total AD should equal or be close to DP for most variants
    # (may differ due to reads filtered out)
    for row in df_with_total.head(10).iter_rows(named=True):
        total_ad = row["total_ad"]
        dp = row["DP"]
        if total_ad is not None and dp is not None:
            # AD sum should not exceed DP (can be equal or less)
            assert total_ad <= dp, (
                f"AD sum ({total_ad}) should not exceed DP ({dp})"
            )


def test_vaf_range(test_vcf_path: Path) -> None:
    """VAF values should be in valid range [0, 1]."""
    lf = read_vcf_file(str(test_vcf_path), with_formats=True, save_parquet=None)
    df = lf.collect()
    
    # Explode VAF list to check all values
    df_vaf = df.select(
        pl.col("VAF").explode().alias("vaf_value")
    ).drop_nulls()
    
    # All VAF values should be between 0 and 1
    assert (df_vaf["vaf_value"] >= 0.0).all(), "All VAF values should be >= 0"
    assert (df_vaf["vaf_value"] <= 1.0).all(), "All VAF values should be <= 1"


def test_pl_genotype_likelihood_structure(test_vcf_path: Path) -> None:
    """PL (Phred-scaled likelihoods) should have expected structure."""
    lf = read_vcf_file(str(test_vcf_path), with_formats=True, save_parquet=None)
    df = lf.collect()
    
    # For diploid biallelic variants, PL should have 3 values: [0/0, 0/1, 1/1]
    df_biallelic = df.filter(~pl.col("alt").str.contains(","))
    
    for row in df_biallelic.head(20).iter_rows(named=True):
        pl_values = row["PL"]
        if pl_values is not None:
            assert len(pl_values) == 3, (
                f"Biallelic PL should have 3 values, got {len(pl_values)}: {pl_values}"
            )
            # At least one value should be 0 (the most likely genotype)
            assert 0 in pl_values, (
                f"PL should contain 0 for the most likely genotype: {pl_values}"
            )
