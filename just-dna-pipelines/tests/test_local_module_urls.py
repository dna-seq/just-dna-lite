"""A locally-installed module must be readable on every platform this app supports.

The bug these pin: `_build_url` built a `file:` URI by concatenation, which is valid for a POSIX
path (`file:///data/…`, empty authority) and malformed for a Windows one (`file://C:/Users/…`,
where `C:` parses as the URI *hostname*). Polars rejected the latter outright, so every module
installed from the registry or compiled locally was undiscoverable to the annotation engine on
Windows — while discovery still listed it, and the run still went green with the module silently
missing from the report.

Everything here is a pure string/path function, so the Windows case is pinned on any platform.
"""

from pathlib import Path

import polars as pl
import pytest

from just_dna_pipelines.annotation.hf_logic import download_file
from just_dna_pipelines.annotation.hf_modules import (
    _build_url,
    is_local_module_url,
    local_module_path,
)


WINDOWS_MODULE = "C:/Users/liv/sources/just-dna-lite/data/interim/registered_modules/mod"
POSIX_MODULE = "/data/sources/just-dna-lite/data/interim/registered_modules/mod"


class TestBuildUrl:
    """`_build_url` must never mint a `file:` URI whose authority is a drive letter."""

    @pytest.mark.parametrize("path", [WINDOWS_MODULE, POSIX_MODULE])
    def test_local_path_is_returned_unchanged(self, path: str) -> None:
        assert _build_url("file", f"{path}/weights.parquet") == f"{path}/weights.parquet"

    @pytest.mark.parametrize("path", [WINDOWS_MODULE, POSIX_MODULE])
    def test_local_path_never_gains_a_scheme(self, path: str) -> None:
        # The regression itself: `file://` + a Windows path puts `C:` in the hostname slot.
        assert not _build_url("file", path).startswith("file://")

    def test_remote_protocols_are_untouched(self) -> None:
        assert _build_url("hf", "datasets/org/repo/data/mod/weights.parquet") == (
            "hf://datasets/org/repo/data/mod/weights.parquet"
        )
        assert _build_url("https", "https://example.org/mod/weights.parquet") == (
            "https://example.org/mod/weights.parquet"
        )
        assert _build_url("s3", "bucket/mod/weights.parquet") == "s3://bucket/mod/weights.parquet"


class TestLocalModulePath:
    """One predicate for "are these bytes on this machine", replacing three prefix guesses."""

    @pytest.mark.parametrize("url", [WINDOWS_MODULE, POSIX_MODULE])
    def test_absolute_paths_are_local_in_either_grammar(self, url: str) -> None:
        assert is_local_module_url(url)
        assert local_module_path(url) == Path(url)

    @pytest.mark.parametrize(
        "url",
        [f"file://{POSIX_MODULE}", f"file://{WINDOWS_MODULE}"],
    )
    def test_legacy_file_urls_still_resolve(self, url: str) -> None:
        # Artifacts written before the fix carry one; they must not stop resolving.
        assert is_local_module_url(url)
        assert local_module_path(url) == Path(url[len("file://") :])

    @pytest.mark.parametrize(
        "url",
        [
            "hf://datasets/just-dna-seq/annotators/data/coronary/weights.parquet",
            "https://example.org/mod/weights.parquet",
            "s3://bucket/mod/weights.parquet",
            "github://org/repo/mod/weights.parquet",
        ],
    )
    def test_remote_urls_are_not_local(self, url: str) -> None:
        assert not is_local_module_url(url)
        assert local_module_path(url) is None

    @pytest.mark.parametrize("url", ["", "modules/mod/weights.parquet", "file://"])
    def test_empty_and_relative_are_not_local(self, url: str) -> None:
        assert local_module_path(url) is None


class TestPolarsReadsWhatWeBuild:
    """The end the bug was actually felt at: `scan_module_table` hands this string to polars."""

    def test_scan_parquet_reads_a_locally_built_url(self, tmp_path: Path) -> None:
        module_dir = tmp_path / "antonkulaga__cognitive_intelligence"
        module_dir.mkdir()
        pl.DataFrame({"rsid": ["rs1"], "weight": [1.0]}).write_parquet(
            module_dir / "weights.parquet"
        )

        url = _build_url("file", str(module_dir / "weights.parquet").replace("\\", "/"))
        assert pl.scan_parquet(url).collect().height == 1

    def test_a_drive_letter_authority_is_what_polars_rejects(self) -> None:
        # Demonstrates the failure the fix avoids, without needing Windows: the URL shape alone
        # is enough for polars to refuse before it ever touches the filesystem.
        with pytest.raises(Exception) as exc:
            pl.scan_parquet(f"file://{WINDOWS_MODULE}/weights.parquet").collect()
        assert "non-empty hostname" in str(exc.value)


class TestDownloadFileCopiesLocalBytes:
    """A local module states a path for its logo/metadata; `requests` has no adapter for one."""

    def test_local_source_is_copied(self, tmp_path: Path) -> None:
        source = tmp_path / "mod" / "logo.png"
        source.parent.mkdir()
        source.write_bytes(b"\x89PNG\r\n\x1a\n")

        target = tmp_path / "out" / "mod_logo.png"
        assert download_file(str(source), target) == target
        assert target.read_bytes() == source.read_bytes()

    def test_legacy_file_url_source_is_copied(self, tmp_path: Path) -> None:
        source = tmp_path / "mod" / "metadata.json"
        source.parent.mkdir()
        source.write_text('{"name": "mod"}', encoding="utf-8")

        target = tmp_path / "out" / "mod_metadata.json"
        assert download_file(source.as_uri(), target) == target
        assert target.read_text(encoding="utf-8") == '{"name": "mod"}'
