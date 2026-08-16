"""Browser-facing URL helpers resolved from environment / ``.env``.

Defaults match ``.env.template``. Prefer ``PUBLIC_*`` overrides in production.
"""

from __future__ import annotations

import os


def _strip_base(url: str) -> str:
    return url.strip().rstrip("/")


def resolve_dagster_web_public_url() -> str:
    """Return the Dagster web UI base URL as seen from the user's browser.

    Precedence (same as the Web UI "Open in Dagster" links):
    1. ``PUBLIC_DAGSTER_WEB_URL``
    2. ``DAGSTER_WEB_URL``
    3. ``http://localhost:{DAGSTER_PORT}`` with default port ``3005``
    """
    pub = os.environ.get("PUBLIC_DAGSTER_WEB_URL", "").strip()
    if pub:
        return _strip_base(pub)
    base = os.environ.get("DAGSTER_WEB_URL", "").strip()
    if base:
        return _strip_base(base)
    port = os.environ.get("DAGSTER_PORT", "3005").strip() or "3005"
    return f"http://localhost:{port}"
