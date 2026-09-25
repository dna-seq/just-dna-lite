"""The Ensembl cache downloader repairs a damaged cache instead of trusting it.

The Dagster ``ensembl_annotations`` asset used to skip the download whenever any parquet was
present and wrote straight to the final filename, so a partial or damaged file stayed in the
cache for good and every Ensembl join failed inside DuckDB (a Windows user saw
``_duckdb.Error: Out of buffer``). The asset now goes through ``download_ensembl_cache``;
these tests pin that the downloader notices both kinds of damage and puts the real bytes back.
"""

import os
from pathlib import Path

import duckdb
import pytest

from just_dna_pipelines.annotation.ensembl_download import (
    DEFAULT_ENSEMBL_REPO,
    download_ensembl_cache,
    fetch_ensembl_manifest,
    file_is_valid,
    sha256_file,
)

# The mitochondrial table is the smallest file in the dataset (tens of kB), so the round trip
# through HuggingFace stays cheap.
SMALL_FILE = "homo_sapiens-chrMT.parquet"


def _flip_middle_byte(path: Path) -> None:
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    path.write_bytes(bytes(data))


class TestVerifiedStamp:
    """Hashing happens once per file version, and a changed file is hashed again."""

    def test_valid_file_is_stamped_and_then_trusted(self, tmp_path: Path) -> None:
        path = tmp_path / "x.parquet"
        path.write_bytes(b"0123456789" * 1000)
        digest = sha256_file(path)

        assert file_is_valid(path, path.stat().st_size, digest)
        stamp = tmp_path / "x.parquet.sha256"
        assert stamp.read_text(encoding="utf-8").split()[-1] == digest

    def test_wrong_digest_is_rejected_and_not_stamped(self, tmp_path: Path) -> None:
        path = tmp_path / "x.parquet"
        path.write_bytes(b"abc" * 1000)

        assert not file_is_valid(path, path.stat().st_size, "0" * 64)
        assert not (tmp_path / "x.parquet.sha256").exists()

    def test_rewritten_file_is_hashed_again(self, tmp_path: Path) -> None:
        path = tmp_path / "x.parquet"
        path.write_bytes(b"0123456789" * 1000)
        digest = sha256_file(path)
        assert file_is_valid(path, path.stat().st_size, digest)

        # Same size, different bytes, newer mtime: the stamp no longer describes this file.
        _flip_middle_byte(path)
        st = path.stat()
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))

        assert not file_is_valid(path, st.st_size, digest)

    def test_wrong_size_is_rejected_without_hashing(self, tmp_path: Path) -> None:
        path = tmp_path / "x.parquet"
        path.write_bytes(b"abc")
        assert not file_is_valid(path, 4, sha256_file(path))


@pytest.fixture(scope="module")
def small_manifest() -> dict[str, tuple[int, str]]:
    manifest = fetch_ensembl_manifest(DEFAULT_ENSEMBL_REPO, token=None)
    assert SMALL_FILE in manifest
    return {SMALL_FILE: manifest[SMALL_FILE]}


@pytest.mark.integration
class TestRepairAgainstHuggingFace:
    """A damaged cache file is replaced with the published bytes, which DuckDB can then read."""

    @pytest.mark.parametrize("damage", ["truncated", "corrupted"])
    def test_damaged_file_is_redownloaded(
        self, tmp_path: Path, small_manifest: dict[str, tuple[int, str]], damage: str
    ) -> None:
        size, digest = small_manifest[SMALL_FILE]
        download_ensembl_cache(manifest=small_manifest, target_dir=tmp_path)
        path = tmp_path / SMALL_FILE
        assert sha256_file(path) == digest

        if damage == "truncated":
            path.write_bytes(path.read_bytes()[: size // 2])
        else:
            _flip_middle_byte(path)
            st = path.stat()
            os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
        assert not file_is_valid(path, size, digest)

        download_ensembl_cache(manifest=small_manifest, target_dir=tmp_path)

        assert path.stat().st_size == size
        assert sha256_file(path) == digest
        assert not list(tmp_path.glob("*.part"))
        rows = duckdb.connect().execute(
            f"SELECT count(*) FROM read_parquet('{path.as_posix()}') WHERE chrom IS NOT NULL"
        ).fetchone()[0]
        assert rows > 0
