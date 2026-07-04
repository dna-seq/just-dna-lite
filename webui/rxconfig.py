from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import reflex as rx  # noqa: E402
from reflex.plugins.sitemap import SitemapPlugin  # noqa: E402

_IS_WINDOWS = sys.platform == "win32"

# SSR is disabled on Windows because @mui/x-data-grid ships a bare CSS import
# that Node.js cannot resolve during the Vite SSR build (bun handles it on
# Linux/macOS).  Upstream fix needed in reflex-mui-datagrid / reflex.
os.environ.setdefault("REFLEX_SSR", "false" if _IS_WINDOWS else "true")
os.environ.setdefault("REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE", "50000000")

_IN_CONTAINER = os.path.exists("/.dockerenv") or os.environ.get("container") == "podman"


def _configured_hosts() -> list[str] | bool:
    if _IN_CONTAINER:
        return True

    hosts = {"lite.just-dna.life"}
    for env_name in ("DEPLOY_URL", "PUBLIC_APP_URL"):
        parsed = urlparse(os.environ.get(env_name, "").strip())
        if parsed.hostname:
            hosts.add(parsed.hostname)
    extra_hosts = os.environ.get("VITE_ALLOWED_HOSTS", "").strip()
    if extra_hosts:
        hosts.update(host.strip() for host in extra_hosts.split(",") if host.strip())
    return sorted(hosts)


_vite_hosts = _configured_hosts()

def _head_components() -> list[rx.Component]:
    """Build static head scripts compiled into the Reflex frontend."""

    return [
        rx.script(src="https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js"),
        rx.script(src="https://cdn.jsdelivr.net/npm/fomantic-ui@2.9.4/dist/semantic.min.js"),
    ]

config = rx.Config(
    app_name="webui",
    plugins=[rx.plugins.RadixThemesPlugin()],
    disable_plugins=[SitemapPlugin],
    vite_allowed_hosts=_vite_hosts,
    stylesheets=[
        "https://cdn.jsdelivr.net/npm/fomantic-ui@2.9.4/dist/semantic.min.css",
    ],
    head_components=_head_components(),
    tailwind=None,
    show_built_with_reflex=False,
)
