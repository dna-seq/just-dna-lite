"""Integration tests for parquet to Vortex conversion."""

import pytest
from pathlib import Path
import polars as pl
from genobear.vortex.parquet_to_vortex import (
    parquet_to_vortex,
    read_vortex_with_polars,
)


@pytest.fixture
def sample_parquet_file(tmp_path: Path) -> Path:
    """Create a sample parquet file for testing."""
    # Create a sample DataFrame
    df = pl.DataFrame({
        "chrom": ["chr1", "chr1", "chr2", "chr2", "chr3"],
        "start": [100, 200, 300, 400, 500],
        "end": [101, 201, 301, 401, 501],
        "ref": ["A", "C", "G", "T", "A"],
        "alt": ["T", "G", "A", "C", "G"],
        "gene_name": ["GENE1", "GENE2", "GENE3", "GENE4", "GENE5"],
        "consequence": ["missense", "synonymous", "missense", "nonsense", "missense"],
    })
    
    # Write to parquet
    parquet_path = tmp_path / "test_variants.parquet"
    df.write_parquet(parquet_path)
    
    return parquet_path


def test_parquet_to_vortex_and_read(sample_parquet_file: Path):
    """Test parquet to vortex conversion and reading back data with integrity check."""
    # Convert to vortex
    vortex_path = parquet_to_vortex(
        parquet_path=sample_parquet_file,
        overwrite=True,
        batch_size=2  # Small batch size to test streaming
    )
    
    # Verify the vortex file was created
    assert vortex_path.exists(), "Vortex file should be created"
    assert vortex_path.suffix == ".vortex", "File should have .vortex extension"
    assert vortex_path.stat().st_size > 0, "Vortex file should not be empty"
    
    # Read the original parquet
    original_df = pl.read_parquet(sample_parquet_file)
    
    # Read the vortex file
    vortex_lf = read_vortex_with_polars(vortex_path)
    vortex_df = vortex_lf.collect()
    
    # Verify data integrity
    assert vortex_df.shape == original_df.shape, "Shape should match original data"
    assert vortex_df.columns == original_df.columns, "Columns should match original data"
    
    # Sort both dataframes for comparison (order might differ)
    original_sorted = original_df.sort(by=["chrom", "start"])
    vortex_sorted = vortex_df.sort(by=["chrom", "start"])
    
    assert original_sorted.equals(vortex_sorted), "Data should match original parquet file"


def test_vortex_file_not_found():
    """Test that reading non-existent vortex file raises error."""
    non_existent = Path("/tmp/non_existent_file.vortex")
    
    with pytest.raises(FileNotFoundError):
        read_vortex_with_polars(non_existent)



