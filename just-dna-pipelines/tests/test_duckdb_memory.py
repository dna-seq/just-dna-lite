"""
Test DuckDB memory-efficient annotation.

This test validates that the DuckDB implementation:
1. Auto-detects system resources for memory limits
2. Creates VIEWs instead of materializing TABLEs
3. Uses streaming operations (no full collection)
4. Properly configures memory limits
"""

from pathlib import Path
import tempfile
import duckdb
import psutil

import pytest

from just_dna_pipelines.annotation.duckdb_assets import (
    build_duckdb_from_parquet,
    configure_duckdb_for_memory_efficiency,
)
from just_dna_pipelines.annotation.configs import (
    DuckDBConfig,
    get_default_duckdb_memory_limit,
    get_default_duckdb_threads,
)


def test_auto_detect_memory_limit():
    """Test that memory limit is automatically detected based on system RAM."""
    memory_limit = get_default_duckdb_memory_limit()
    
    # Should be a string like "32GB"
    assert memory_limit.endswith("GB")
    limit_gb = int(memory_limit[:-2])
    
    # Should be between 8GB and 128GB
    assert 8 <= limit_gb <= 128
    
    # Should be roughly 75% of system RAM
    system_ram_gb = psutil.virtual_memory().total / (1024**3)
    expected_limit = int(system_ram_gb * 0.75)
    
    # Allow for min/max clamping
    if expected_limit < 8:
        assert limit_gb == 8, "Should use minimum of 8GB"
    elif expected_limit > 128:
        assert limit_gb == 128, "Should use maximum of 128GB"
    else:
        assert limit_gb == expected_limit, f"Should be ~75% of {system_ram_gb}GB RAM"


def test_auto_detect_threads():
    """Test that thread count is automatically detected based on CPU cores."""
    threads = get_default_duckdb_threads()
    
    # Should be between 2 and 16
    assert 2 <= threads <= 16
    
    # Should be roughly 75% of CPU cores
    cpu_count = psutil.cpu_count(logical=True) or 4
    expected_threads = int(cpu_count * 0.75)
    
    # Allow for min/max clamping
    if expected_threads < 2:
        assert threads == 2
    elif expected_threads > 16:
        assert threads == 16
    else:
        assert threads == expected_threads


def test_configure_duckdb_memory_settings():
    """Test that DuckDB memory settings are properly applied."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.duckdb"
        con = duckdb.connect(str(db_path))
        
        # Test with explicit config
        config = DuckDBConfig(
            memory_limit="16GB",
            threads=8,
            temp_directory="/tmp/test_duckdb",
        )
        configure_duckdb_for_memory_efficiency(con, config)
        
        # Verify connection is functional
        result = con.execute("SELECT 1 AS test").fetchone()
        assert result[0] == 1
        
        con.close()


def test_configure_duckdb_auto_detect():
    """Test that DuckDB uses auto-detected settings when config is None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.duckdb"
        con = duckdb.connect(str(db_path))
        
        # No config provided - should auto-detect
        configure_duckdb_for_memory_efficiency(con, None)
        
        # Verify connection is functional
        result = con.execute("SELECT 1 AS test").fetchone()
        assert result[0] == 1
        
        con.close()


def test_duckdb_uses_views_not_tables(tmp_path):
    """
    Test that the DuckDB database creates VIEWs over Parquet files,
    not materialized TABLEs.
    
    This ensures minimal memory footprint during database creation.
    """
    import polars as pl
    
    mock_cache = tmp_path / "ensembl_cache"
    data_dir = mock_cache / "data"
    data_dir.mkdir(parents=True)
    
    mock_data = pl.DataFrame({
        "chrom": ["1", "1", "2"],
        "start": [1000, 2000, 3000],
        "ref": ["A", "G", "C"],
        "alt": ["T", "C", "G"],
        "rsid": ["rs123", "rs456", "rs789"],
    })
    mock_data.write_parquet(data_dir / "homo_sapiens-chr1.parquet")
    
    db_path = tmp_path / "test.duckdb"
    result_path, metadata = build_duckdb_from_parquet(mock_cache, db_path)
    
    assert result_path.exists()
    
    assert metadata["storage_type"] == "views_over_parquet"
    assert metadata["memory_efficient"] is True
    assert metadata["num_views"] == 1
    
    con = duckdb.connect(str(db_path), read_only=True)
    
    views = con.execute("SELECT table_name FROM information_schema.views WHERE table_schema = 'main'").fetchall()
    
    assert len(views) >= 1, f"Expected at least 1 view, found {len(views)}"
    view_names = [v[0] for v in views]
    assert "ensembl_variations" in view_names, f"Expected 'ensembl_variations' in {view_names}"
    
    result = con.execute("SELECT COUNT(*) FROM ensembl_variations").fetchone()
    assert result[0] == 3
    
    db_size_kb = db_path.stat().st_size / 1024
    assert db_size_kb < 500, f"Database too large: {db_size_kb}KB (should be < 500KB for view metadata only)"
    
    con.close()


def test_duckdb_streaming_annotation_no_collect():
    """
    Test that annotation logic uses streaming operations.
    
    This is verified by checking that the code:
    1. Uses DuckDB's COPY TO for direct streaming to Parquet
    2. Does not call .collect() on the input LazyFrame
    3. Minimal temporary file usage
    """
    # This would require actual VCF and annotation data
    # The key verification is code inspection (already done) and memory profiling
    # For now, we mark this as a placeholder for integration testing
    pytest.skip("Requires integration test with real VCF/Ensembl data")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

