"""The analysis picker's source tag: HF, Catalog or Local.

Two copies of one module (a local build beside its Catalog install, or an HF module beside the same
module installed from the Catalog) rendered as identical cards, because the card showed only a title
and a repo badge that was a folder path for anything on this machine. `module_source` tells them
apart. A Catalog install and a local compile are both directories here; what separates them is the
`published_at` the registry stamps on the manifest it serves. The install key `{namespace}__{name}`
cannot, because `__` is legal inside a module name.
"""

import json
import shutil
from pathlib import Path

import pytest
from fsspec.implementations.local import LocalFileSystem

from just_dna_pipelines.annotation.hf_modules import (
    ModuleInfo,
    _probe_module_at_path,
    module_source,
)

PHARMGKB = Path("data/interim/v1_port/pharmgkb")


def _probe(path: Path) -> ModuleInfo | None:
    return _probe_module_at_path(LocalFileSystem(), str(path), "file", path.name, str(path), str(path))


@pytest.fixture
def local_build(tmp_path: Path) -> Path:
    """A real local compile, copied so the test can stamp its manifest."""
    if not (PHARMGKB / "manifest.json").is_file():
        pytest.skip("v1_port pharmgkb artifact not built in this checkout")
    dest = tmp_path / "pharmgkb"
    shutil.copytree(PHARMGKB, dest)
    manifest = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("published_at"):
        pytest.skip("this pharmgkb build carries a published_at, so it is not a local compile")
    return dest


def _stamp_as_served(module_dir: Path, namespace: str) -> None:
    """Add what the registry adds to a manifest it serves, and nothing else."""
    path = module_dir / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["published_at"] = "2026-09-27T05:00:00Z"
    manifest["identity"]["namespace"] = namespace
    path.write_text(json.dumps(manifest), encoding="utf-8")


class TestLocalDirectoriesAreToldApartByTheManifest:
    def test_a_local_compile_is_local(self, local_build: Path) -> None:
        info = _probe(local_build)
        assert info is not None
        assert info.manifest_published_at is None
        assert module_source(info) == "local"

    def test_the_same_bytes_as_served_by_the_registry_are_catalog(self, local_build: Path) -> None:
        _stamp_as_served(local_build, "just-dna-seq")
        info = _probe(local_build)
        assert info is not None
        assert module_source(info) == "catalog"
        # The namespace the tag shows is the manifest's own spelling, not the sanitized install key.
        assert info.manifest_namespace == "just-dna-seq"

    def test_a_namespace_alone_does_not_make_a_catalog_install(self, local_build: Path) -> None:
        """A local build may state its namespace before it is ever published."""
        path = local_build / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["identity"]["namespace"] = "just-dna-seq"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        assert module_source(_probe(local_build)) == "local"


class TestRemoteSources:
    def _remote(self, lead_url: str, **kw: object) -> ModuleInfo:
        return ModuleInfo(name="m", repo_id="org/repo", path="data/m", lead_url=lead_url, **kw)  # type: ignore[arg-type]

    def test_huggingface_is_hf_even_when_its_manifest_was_published(self) -> None:
        """HF copies of registry modules carry `published_at` too; being remote decides first."""
        info = self._remote(
            "hf://datasets/org/repo/data/m/weights.parquet",
            manifest_published_at="2026-09-26T23:45:05Z",
            manifest_namespace="just-dna-seq",
        )
        assert module_source(info) == "hf"

    @pytest.mark.parametrize(
        "lead_url",
        ["https://example.org/m/weights.parquet", "s3://bucket/m/weights.parquet"],
    )
    def test_other_remote_schemes_are_not_labelled_hf(self, lead_url: str) -> None:
        assert module_source(self._remote(lead_url)) == "remote"

    def test_an_unknown_module_has_no_source(self) -> None:
        assert module_source(None) is None
