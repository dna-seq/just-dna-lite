from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_IS_WINDOWS = sys.platform == "win32"


def _bun_available() -> bool:
    """Whether reflex can find a bun binary to run the Vite SSR pass.

    @mui/x-data-grid ships a bare `.css` import that bun resolves transparently
    but Node's ESM loader cannot (``Unknown file extension ".css"``).  Reflex
    runs SSR through bun when present and falls back to Node otherwise, so bun
    availability — not the OS — decides whether SSR is safe here.  We mirror the
    locations reflex searches without importing reflex (which must not happen
    before REFLEX_SSR is set, or the setting would miss the process fork).
    """
    exe = "bun.exe" if _IS_WINDOWS else "bun"
    if shutil.which(exe):
        return True
    roots: list[Path] = []
    bun_install = os.environ.get("BUN_INSTALL")
    if bun_install:
        roots.append(Path(bun_install))
    reflex_dir = os.environ.get("REFLEX_DIR")
    if reflex_dir:
        roots.append(Path(reflex_dir) / "bun")
    try:
        from platformdirs import user_data_dir

        roots.append(Path(user_data_dir("reflex")) / "bun")
    except ImportError:
        pass
    return any((root / "bin" / exe).exists() for root in roots)


# Resolve REFLEX_SSR *before* importing reflex, so the value is in place before
# reflex forks its frontend/backend processes.  Default SSR off when bun is not
# available (Node would crash on the @mui/x-data-grid CSS import); leave the
# user's / reflex's own choice untouched when bun is present or REFLEX_SSR is
# set explicitly.  Upstream fix needed in reflex-mui-datagrid / reflex.
if os.environ.get("REFLEX_SSR") is None and not _bun_available():
    os.environ["REFLEX_SSR"] = "false"
os.environ.setdefault("REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE", "50000000")

import reflex as rx  # noqa: E402
from reflex.plugins.sitemap import SitemapPlugin  # noqa: E402

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
