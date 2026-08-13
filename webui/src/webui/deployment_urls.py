"""Build browser-reachable URLs for the app, custom API routes, and Dagster UI."""

from __future__ import annotations

import os
from urllib.parse import urlparse

DEFAULT_BACKEND_PORT = 8000


def _strip_base(url: str) -> str:
    return url.strip().rstrip("/")


def _is_loopback_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def resolve_local_backend_port() -> int:
    """Return the port Reflex actually bound, or 8000 before it has started.

    Reflex writes ``REFLEX_BACKEND_PORT`` via ``Config._set_persistent`` after it
    auto-increments past a taken 8000/8001.  That is the source of truth for
    local split-backend URLs; do not hardcode 8000.
    """
    env_port = os.environ.get("REFLEX_BACKEND_PORT", "").strip()
    if env_port.isdigit():
        return int(env_port)
    return DEFAULT_BACKEND_PORT


def resolve_public_backend_base_url(backend_port: int | None = None) -> str:
    """Return the base URL for the Reflex backend as seen from the user's browser.

    Precedence:
    1. ``PUBLIC_BACKEND_URL`` — explicit backend/custom API override
    2. ``DEPLOY_URL`` / ``PUBLIC_APP_URL`` — production fullstack app origin
    3. ``API_URL`` — persisted local origin, or a non-loopback split-backend override
    4. ``http://localhost:{backend_port}`` — local dev backend
    """
    pub = os.environ.get("PUBLIC_BACKEND_URL", "").strip()
    if pub:
        return _strip_base(pub)
    app_url = resolve_configured_public_app_url()
    if app_url:
        return app_url
    port = backend_port if backend_port is not None else resolve_local_backend_port()
    api = os.environ.get("API_URL", "").strip()
    if api:
        # A leftover localhost:8000 must not shadow the port Reflex actually bound.
        if not _is_loopback_url(api):
            return _strip_base(api)
        api_port = urlparse(api).port
        if api_port is None or api_port == port:
            return _strip_base(api)
    return f"http://localhost:{port}"


def persist_local_backend_api_url(backend_port: int) -> str:
    """Record ``API_URL`` for the selected local backend port.

    Public-origin env vars win.  A localhost ``API_URL`` is replaced so an
    auto-incremented port is not shadowed by a stale default of 8000.
    """
    pub = os.environ.get("PUBLIC_BACKEND_URL", "").strip()
    if pub:
        return _strip_base(pub)
    app_url = resolve_configured_public_app_url()
    if app_url:
        os.environ["API_URL"] = app_url
        return app_url
    url = f"http://localhost:{backend_port}"
    current = os.environ.get("API_URL", "").strip()
    if not current or _is_loopback_url(current):
        os.environ["API_URL"] = url
        os.environ["REFLEX_BACKEND_PORT"] = str(backend_port)
        return url
    return _strip_base(current)


def resolve_configured_public_app_url() -> str:
    """Return the configured public app origin, or empty when unset."""

    deploy = os.environ.get("DEPLOY_URL", "").strip()
    if deploy:
        return _strip_base(deploy)
    public_app = os.environ.get("PUBLIC_APP_URL", "").strip()
    if public_app:
        return _strip_base(public_app)
    return ""


def resolve_public_app_url() -> str:
    """Return the canonical browser-facing app origin for public metadata.

    ``DEPLOY_URL`` is preferred because production reverse proxies often expose a
    different public origin than the internal Reflex backend URL.
    """

    return resolve_configured_public_app_url() or "http://localhost:3000"


def resolve_dagster_web_public_url() -> str:
    """Return the Dagster web UI base URL as seen from the user's browser."""
    pub = os.environ.get("PUBLIC_DAGSTER_WEB_URL", "").strip()
    if pub:
        return _strip_base(pub)
    base = os.environ.get("DAGSTER_WEB_URL", "").strip()
    if base:
        return _strip_base(base)
    port = os.environ.get("DAGSTER_PORT", "3005").strip() or "3005"
    return f"http://localhost:{port}"
