"""Module ZIP downloads tolerate timestamps outside the ZIP date range."""

from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from webui.app import api


@pytest.fixture
def module_client() -> TestClient:
    return TestClient(api)


def _write_epoch_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    os.utime(path, (0, 0))


def test_download_module_zip_accepts_pre_1980_timestamps(
    module_client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module_dir = tmp_path / "registered" / "example_module"
    module_dir.mkdir(parents=True)
    _write_epoch_file(module_dir / "manifest.json", '{"name": "example_module"}')
    _write_epoch_file(module_dir / "module_spec.yaml", "name: example_module\n")
    _write_epoch_file(module_dir / "weights.parquet", "compiled")
    monkeypatch.setattr("webui.app.CUSTOM_MODULES_DIR", tmp_path / "registered")

    response = module_client.get("/api/module-zip/example_module")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        'attachment; filename="example_module.zip"'
    )
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.namelist() == ["manifest.json", "module_spec.yaml"]
        assert archive.getinfo("manifest.json").date_time == (1980, 1, 1, 0, 0, 0)
        assert archive.read("manifest.json") == b'{"name": "example_module"}'


def test_download_agent_spec_zip_accepts_pre_1980_timestamps(
    module_client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_dir = tmp_path / "generated" / "example_module" / "v1"
    spec_dir.mkdir(parents=True)
    _write_epoch_file(spec_dir / "module_spec.yaml", "name: example_module\n")
    _write_epoch_file(spec_dir / "variants.csv", "rsid\nrs1\n")
    _write_epoch_file(spec_dir / "weights.parquet", "compiled")
    monkeypatch.setattr("webui.app._GENERATED_MODULES_DIR", tmp_path / "generated")

    response = module_client.get("/api/agent-spec-zip/example_module?v=1")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        'attachment; filename="example_module_v1.zip"'
    )
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.namelist() == ["module_spec.yaml", "variants.csv"]
        assert archive.getinfo("module_spec.yaml").date_time == (
            1980,
            1,
            1,
            0,
            0,
            0,
        )
