"""The report download button must get an attachment, not the view HTML."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from webui.app import api


@pytest.fixture
def report_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    report_dir = tmp_path / "anonymous" / "antonkulaga" / "reports"
    report_dir.mkdir(parents=True)
    (report_dir / "report_20260820.html").write_text(
        "<html><title>Genomic Annotation Report</title></html>",
        encoding="utf-8",
    )
    monkeypatch.setattr("webui.app.get_user_output_dir", lambda: tmp_path)
    return TestClient(api)


def test_download_report_is_an_attachment(report_client: TestClient) -> None:
    response = report_client.get(
        "/api/download-report/anonymous/antonkulaga/report_20260820.html"
    )

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert "report_20260820.html" in response.headers["content-disposition"]
    assert "Genomic Annotation Report" in response.text


def test_view_report_stays_inline(report_client: TestClient) -> None:
    """Would have been the download target: the browser renders this instead of saving."""
    response = report_client.get("/api/report/anonymous/antonkulaga/report_20260820.html")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "attachment" not in response.headers.get("content-disposition", "")
