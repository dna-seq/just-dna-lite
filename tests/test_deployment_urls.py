"""Custom API links must follow the port Reflex actually bound."""

from __future__ import annotations

import os

import pytest

from webui.deployment_urls import (
    persist_local_backend_api_url,
    resolve_local_backend_port,
    resolve_public_backend_base_url,
)


def test_local_backend_port_reads_reflex_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REFLEX_BACKEND_PORT", raising=False)
    assert resolve_local_backend_port() == 8000
    monkeypatch.setenv("REFLEX_BACKEND_PORT", "8002")
    assert resolve_local_backend_port() == 8002


def test_backend_url_follows_reflex_port_not_hardcoded_8000(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Would have sent report/download links to Claude-on-8000 before this fix."""
    for key in ("PUBLIC_BACKEND_URL", "DEPLOY_URL", "PUBLIC_APP_URL", "API_URL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("REFLEX_BACKEND_PORT", "8002")
    assert resolve_public_backend_base_url() == "http://localhost:8002"


def test_stale_localhost_api_url_does_not_shadow_bound_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in ("PUBLIC_BACKEND_URL", "DEPLOY_URL", "PUBLIC_APP_URL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("API_URL", "http://localhost:8000")
    monkeypatch.setenv("REFLEX_BACKEND_PORT", "8002")
    assert resolve_public_backend_base_url() == "http://localhost:8002"


def test_public_backend_url_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PUBLIC_BACKEND_URL", "https://lite.example/api")
    monkeypatch.setenv("API_URL", "http://localhost:8000")
    monkeypatch.setenv("REFLEX_BACKEND_PORT", "8002")
    assert resolve_public_backend_base_url() == "https://lite.example/api"


def test_remote_api_url_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("PUBLIC_BACKEND_URL", "DEPLOY_URL", "PUBLIC_APP_URL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("API_URL", "https://backend.example")
    monkeypatch.setenv("REFLEX_BACKEND_PORT", "8002")
    assert resolve_public_backend_base_url() == "https://backend.example"


def test_persist_replaces_stale_localhost_api_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in ("PUBLIC_BACKEND_URL", "DEPLOY_URL", "PUBLIC_APP_URL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("API_URL", "http://localhost:8000")
    monkeypatch.setenv("REFLEX_BACKEND_PORT", "8000")
    url = persist_local_backend_api_url(8002)
    assert url == "http://localhost:8002"
    assert os.environ["API_URL"] == "http://localhost:8002"
    assert os.environ["REFLEX_BACKEND_PORT"] == "8002"


def test_persist_keeps_remote_api_url(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("PUBLIC_BACKEND_URL", "DEPLOY_URL", "PUBLIC_APP_URL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("API_URL", "https://backend.example")
    monkeypatch.setenv("REFLEX_BACKEND_PORT", "8000")
    url = persist_local_backend_api_url(8002)
    assert url == "https://backend.example"
    assert os.environ["API_URL"] == "https://backend.example"
