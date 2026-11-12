from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Prerendering (REFLEX_SSR) follows Reflex's default: on in production. It used to be gated off
# wherever Node would run it, because @mui/x-data-grid's CSS import failed every route under Node;
# webui.vite_ssr bundles @mui/* into the SSR build instead, so Node and bun both prerender.
os.environ.setdefault("REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE", "50000000")

import reflex as rx  # noqa: E402
from reflex.plugins.sitemap import SitemapPlugin  # noqa: E402
from webui.vite_ssr import SsrBundleMuiPlugin  # noqa: E402

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
    # The UI is Fomantic and always light. "system" puts class `dark` on <html>
    # when Windows/Firefox is in dark mode, and Radix then paints --gray-1 /
    # --color-background / --blue-2 near black. Light stops that class.
    default_color_mode="light",
    plugins=[
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(appearance="light", accent_color="blue"),
        ),
        # Lets Node prerender: @mui/x-data-grid imports its own CSS (see webui.vite_ssr).
        SsrBundleMuiPlugin(),
    ],
    disable_plugins=[SitemapPlugin],
    vite_allowed_hosts=_vite_hosts,
    stylesheets=[
        "https://cdn.jsdelivr.net/npm/fomantic-ui@2.9.4/dist/semantic.min.css",
    ],
    head_components=_head_components(),
    tailwind=None,
    show_built_with_reflex=False,
)
