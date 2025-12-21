import re
from pathlib import Path
from typing import List

import pytest
from eliot import start_action

from genobear.preparation.runners_prefect import prepare_vcf_source_flow
from genobear.preparation.vcf_downloader import list_paths


@pytest.mark.integration
def test_vcf_pipeline_downloads_to_temp(tmp_path: Path) -> None:
    """Integration test for the `prepare_vcf_source_flow` using a temporary destination.

    Mirrors the logic while preferring a small index file (".tbi") to keep the
    test lightweight. Falls back to the larger VCF if needed.
    """
    base_url = "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/"
    # Prefer a tiny index file first; fall back to the full VCF if index is unavailable
    preferred_pattern = r"clinvar\.vcf\.gz\.tbi$"
    fallback_pattern = r"clinvar\.vcf\.gz$"

    with start_action(action_type="test_run_download_pipeline", url=base_url, dest=str(tmp_path)):
        # Probe remote listing to decide which pattern to use (no mocking)
        preferred_urls = list_paths(url=base_url, pattern=preferred_pattern, file_only=True)
        pattern = preferred_pattern if preferred_urls else fallback_pattern

        # Run Prefect flow
        results = prepare_vcf_source_flow(
            url=base_url,
            pattern=pattern,
            name="pytest_vcf_pipeline",
            dest_dir=tmp_path,
            profile=True,
        )

        local_paths = results["vcf_local"]
        parquet_paths = results["vcf_parquet_path"]

        # Assertions with clear messages
        assert len(local_paths) >= 1, "Expected at least one downloaded file"
        assert len(parquet_paths) == len(local_paths), "Should have same number of parquet and local paths"
        
        for i, (local_p, parquet_p) in enumerate(zip(local_paths, parquet_paths)):
            assert local_p.exists(), f"Downloaded file does not exist: {local_p}"
            assert local_p.stat().st_size > 0, f"Downloaded file is empty: {local_p}"
            assert local_p.parent.resolve() == tmp_path.resolve(), (
                f"File {local_p} not saved under the temporary destination {tmp_path}"
            )
            
            # Check if this is a VCF file that should have been converted
            is_vcf = ".vcf" in local_p.suffixes and not any(
                local_p.suffixes[-1] == ext for ext in [".tbi", ".csi", ".idx"]
            )
            
            if is_vcf:
                assert parquet_p.suffix == ".parquet", f"Expected .parquet extension for VCF conversion: {parquet_p}"
                assert parquet_p.exists(), f"Parquet file should exist for VCF: {parquet_p}"
                assert parquet_p.stat().st_size > 0, f"Parquet file should not be empty: {parquet_p}"
            else:
                # Non-VCF files should return the original path 
                assert parquet_p == local_p, f"Non-VCF file should return original path: {local_p} != {parquet_p}"


