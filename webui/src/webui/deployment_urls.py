"""Build browser-reachable URLs for Reflex backend routes and Dagster UI.

Custom FastAPI routes (reports, downloads, etc.) run on the Reflex backend port.
Remote users must not receive ``http://localhost:...`` from inside the container;
set ``PUBLIC_BACKEND_URL`` (or ``API_URL``) to the host:port users open.
"""

from __future__ import annotations

import os


def _strip_base(url: str) -> str:
    return url.strip().rstrip("/")


def resolve_public_backend_base_url(backend_port: int) -> str:
    """Return the base URL for the Reflex backend as seen from the user's browser.

    Precedence:
    1. ``PUBLIC_BACKEND_URL`` — preferred for public / reverse-proxy deployments
    2. ``API_URL`` — Reflex also reads this; may be set by compose or operators
    3. ``http://localhost:{backend_port}`` — local dev
    """
    pub = os.environ.get("PUBLIC_BACKEND_URL", "").strip()
    if pub:
        return _strip_base(pub)
    api = os.environ.get("API_URL", "").strip()
    if api:
        return _strip_base(api)
    return f"http://localhost:{backend_port}"


def resolve_dagster_web_public_url() -> str:
    """Return the Dagster web UI base URL as seen from the user's browser."""
    pub = os.environ.get("PUBLIC_DAGSTER_WEB_URL", "").strip()
    if pub:
        return _strip_base(pub)
    base = os.environ.get("DAGSTER_WEB_URL", "").strip()
    if base:
        return _strip_base(base)
    return "http://localhost:3005"
