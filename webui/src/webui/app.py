from __future__ import annotations

import contextlib
import io
import logging
import sys
from collections.abc import AsyncIterator
from pathlib import Path
import zipfile

import reflex as rx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from just_dna_pipelines.annotation.analytics import inject_umami_tracker, umami_config
from just_dna_pipelines.runtime import load_env
from just_dna_pipelines.annotation.resources import get_user_output_dir
from webui.compute.jobs import kill_all_jobs
from webui.compute.pool import start_pool, stop_pool
from webui.grid import clear_grid_artifacts
from reflex import constants
from reflex.app import default_frontend_exception_handler
from reflex_base.config import get_config
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Receive, Scope, Send

# Load environment variables before importing pages/state modules that resolve
# data paths at import time.
load_env()

from webui.features import MODULE_CREATOR_ENABLED  # noqa: E402
from webui.pages.dashboard import dashboard_page  # noqa: E402
from webui.pages.index import index_page  # noqa: E402
from webui.pages.analysis import analysis_page  # noqa: E402
from webui.pages.annotate import annotate_page  # noqa: E402
from webui.pages.modules import modules_page  # noqa: E402
from webui.pages.registry import registry_page  # noqa: E402
from webui.pages.faq import faq_page  # noqa: E402

# Note: Shutdown cleanup of STARTED runs is handled by the parent `uv run start` command,
# which catches Ctrl+C and cleans up before killing subprocesses.

logger = logging.getLogger(__name__)
_SUPPRESSED_STALE_CLIENT_FRONTEND_ERROR_MARKERS = (
    "typeerror: t is not a function",
)
_SUPPRESSED_STALE_CLIENT_STACK_MARKERS = (
    "connect/<@",
    "socket.<anonymous>",
    "/assets/context-",
    "/assets/helmet-",
)
_logged_suppressed_frontend_errors: set[str] = set()


# ============================================================================
# HUGGINGFACE AUTHENTICATION CHECK
# ============================================================================

def check_hf_authentication() -> None:
    """
    Verify HuggingFace authentication before app starts.
    Exits with error code 1 if not authenticated or authentication fails.
    """
    try:
        from huggingface_hub import HfApi, get_token
        
        # Check if token exists
        token = get_token()
        if token is None:
            print("=" * 80, file=sys.stderr)
            print("ERROR: HuggingFace authentication not found!", file=sys.stderr)
            print("=" * 80, file=sys.stderr)
            print("", file=sys.stderr)
            print("You must log in to HuggingFace to use this application.", file=sys.stderr)
            print("", file=sys.stderr)
            print("To authenticate, run:", file=sys.stderr)
            print("  huggingface-cli login", file=sys.stderr)
            print("  # or", file=sys.stderr)
            print("  uv run huggingface-cli login", file=sys.stderr)
            print("", file=sys.stderr)
            print("You can get your token from: https://huggingface.co/settings/tokens", file=sys.stderr)
            print("=" * 80, file=sys.stderr)
            sys.exit(1)
        
        # Verify token is valid by calling whoami
        api = HfApi(token=token)
        user_info = api.whoami()
        
        print(f"✓ HuggingFace authentication verified: {user_info.get('name', 'Unknown user')}")
        
    except ImportError as e:
        print("=" * 80, file=sys.stderr)
        print(f"ERROR: Failed to import huggingface_hub: {e}", file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        print("", file=sys.stderr)
        print("To install huggingface_hub, run:", file=sys.stderr)
        print("  uv add huggingface_hub", file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print("=" * 80, file=sys.stderr)
        print(f"ERROR: HuggingFace authentication check failed: {e}", file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        print("", file=sys.stderr)
        print("This could mean:", file=sys.stderr)
        print("  1. Your token is invalid or expired", file=sys.stderr)
        print("  2. You don't have network connectivity", file=sys.stderr)
        print("  3. HuggingFace API is unavailable", file=sys.stderr)
        print("", file=sys.stderr)
        print("To re-authenticate, run:", file=sys.stderr)
        print("  huggingface-cli login", file=sys.stderr)
        print("  # or", file=sys.stderr)
        print("  uv run huggingface-cli login", file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        sys.exit(1)


# Run authentication check before anything else
# check_hf_authentication()

from just_dna_pipelines.annotation.resources import get_generated_modules_dir  # noqa: E402
from just_dna_pipelines.module_registry import CUSTOM_MODULES_DIR  # noqa: E402

_GENERATED_MODULES_DIR = get_generated_modules_dir()



# ============================================================================
# CUSTOM API ENDPOINTS
# ============================================================================

# Create a FastAPI app for custom API routes
api = FastAPI()

# No liveness route is defined here on purpose.  Reflex already registers `/ping`
# (JSONResponse("pong"), no dependency checks) and `/_health` (which also probes the
# DB and Redis and returns 503 when they fail).  The serve watchdog polls `/ping`:
# a 503 from `/_health` would make it SIGKILL a perfectly live server over an
# unrelated dependency hiccup.  See webui/serve_watchdog.py.


@api.get("/api/download/{user_id}/{sample_name}/{filename}")
async def download_output_file(user_id: str, sample_name: str, filename: str) -> FileResponse:
    """
    Download an output file (parquet) from the user's output directory.
    
    Path: /api/download/{user_id}/{sample_name}/{filename}
    Example: /api/download/anonymous/antku_small/longevitymap_weights.parquet
    """
    # Validate inputs to prevent path traversal
    if ".." in user_id or ".." in sample_name or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid path components")
    
    # Only allow parquet files
    if not filename.endswith(".parquet"):
        raise HTTPException(status_code=400, detail="Only parquet files can be downloaded")
    
    file_path = get_user_output_dir() / user_id / sample_name / "modules" / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename} (looked at {file_path})")
    
    if not file_path.is_file():
        raise HTTPException(status_code=400, detail=f"Path is not a file: {file_path}")
    
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream",
    )


@api.get("/api/download-vcf/{user_id}/{sample_name}/{filename}")
async def download_vcf_export(user_id: str, sample_name: str, filename: str) -> FileResponse:
    """Download an exported VCF file from the user's vcf_exports directory.

    Path: /api/download-vcf/{user_id}/{sample_name}/{filename}
    Example: /api/download-vcf/anonymous/sample1/longevitymap_annotated.vcf.gz
    """
    if ".." in user_id or ".." in sample_name or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid path components")

    allowed_extensions = (".vcf", ".vcf.gz", ".vcf.bgz")
    if not any(filename.endswith(ext) for ext in allowed_extensions):
        raise HTTPException(status_code=400, detail="Only VCF files can be downloaded")

    file_path = get_user_output_dir() / user_id / sample_name / "vcf_exports" / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream",
    )


@api.get("/api/agent-spec/{spec_name}/{filename}")
async def download_agent_spec_file(spec_name: str, filename: str) -> FileResponse:
    """Serve generated spec files (module_spec.yaml, variants.csv, studies.csv)."""
    if ".." in spec_name or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid path components")

    allowed_extensions = {".yaml", ".yml", ".csv"}
    if not any(filename.endswith(ext) for ext in allowed_extensions):
        raise HTTPException(status_code=400, detail="Only YAML and CSV files can be downloaded")

    import tempfile
    temp_root = Path(tempfile.gettempdir())
    for candidate in temp_root.iterdir():
        if candidate.name.startswith("module_spec_") and candidate.is_dir():
            target = candidate / spec_name / filename
            if target.exists() and target.is_file():
                return FileResponse(
                    path=str(target),
                    filename=filename,
                    media_type="application/octet-stream",
                )

    raise HTTPException(status_code=404, detail=f"Spec file not found: {spec_name}/{filename} (scanned {temp_root}/module_spec_*/)")


@api.get("/api/agent-spec-zip/{spec_name}")
async def download_agent_spec_zip(spec_name: str, v: int = 0) -> StreamingResponse:
    """Download generated spec files as a zip (excluding auto-generated parquets)."""
    if ".." in spec_name or "/" in spec_name:
        raise HTTPException(status_code=400, detail="Invalid spec name")

    module_dir = _GENERATED_MODULES_DIR / spec_name
    if v > 0:
        spec_dir = module_dir / f"v{v}"
    else:
        spec_dir = module_dir
    if not spec_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Spec not found: {spec_name}/v{v} (looked at {spec_dir})")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(spec_dir.iterdir()):
            if f.is_file() and f.suffix != ".parquet":
                zf.write(f, f.name)
    buf.seek(0)

    zip_filename = f"{spec_name}_v{v}.zip" if v > 0 else f"{spec_name}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )


@api.get("/api/module-zip/{module_name}")
async def download_module_zip(module_name: str) -> StreamingResponse:
    """Download a locally-registered module's files as a zip (excludes compiled parquets)."""
    if ".." in module_name or "/" in module_name:
        raise HTTPException(status_code=400, detail="Invalid module name")

    module_dir = CUSTOM_MODULES_DIR / module_name
    if not module_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Module not found: {module_name} (looked at {module_dir})")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(module_dir.rglob("*")):
            if f.is_file() and f.suffix != ".parquet":
                zf.write(f, f.relative_to(module_dir).as_posix())
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{module_name}.zip"'},
    )


@api.get("/api/agent-log/{spec_name}/{version_dir}/{log_name}")
async def download_agent_run_log(spec_name: str, version_dir: str, log_name: str) -> FileResponse:
    """Download a versioned run log from a module's generated directory."""
    for part in (spec_name, version_dir, log_name):
        if ".." in part or "/" in part:
            raise HTTPException(status_code=400, detail="Invalid path")

    log_path = _GENERATED_MODULES_DIR / spec_name / version_dir / log_name
    if not log_path.is_file():
        raise HTTPException(status_code=404, detail=f"Log not found: {spec_name}/{version_dir}/{log_name} (looked at {log_path})")

    return FileResponse(
        path=str(log_path),
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{spec_name}_{log_name}"'},
    )


@api.get("/api/report/{user_id}/{sample_name}/{filename}", response_model=None)
async def view_report_file(user_id: str, sample_name: str, filename: str) -> Response:
    """
    Serve an HTML report file for viewing in the browser.
    
    Path: /api/report/{user_id}/{sample_name}/{filename}
    Example: /api/report/anonymous/antku_small/report_20260818_221532.html
    """
    # Validate inputs to prevent path traversal
    if ".." in user_id or ".." in sample_name or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid path components")
    
    # Only allow HTML files
    if not filename.endswith(".html"):
        raise HTTPException(status_code=400, detail="Only HTML files can be viewed")
    
    file_path = get_user_output_dir() / user_id / sample_name / "reports" / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Report not found: {filename} (looked at {file_path})")
    
    if not file_path.is_file():
        raise HTTPException(status_code=400, detail=f"Path is not a file: {file_path}")
    
    html = file_path.read_text(encoding="utf-8")
    tracked_html = inject_umami_tracker(html)
    if tracked_html == html:
        return FileResponse(
            path=str(file_path),
            media_type="text/html",
        )
    return HTMLResponse(content=tracked_html)


@api.get("/api/module-logo/{module_name}")
async def serve_module_logo(module_name: str) -> FileResponse:
    """Serve a logo image for a local (non-HF) annotation module."""
    if ".." in module_name or "/" in module_name:
        raise HTTPException(status_code=400, detail="Invalid module name")

    from just_dna_pipelines.annotation.hf_modules import MODULE_INFOS

    info = MODULE_INFOS.get(module_name)
    if not info or not info.logo_url:
        raise HTTPException(status_code=404, detail=f"No logo for module: {module_name}")

    logo_path_str = info.logo_url
    if logo_path_str.startswith("file://"):
        logo_path_str = logo_path_str[len("file://"):]

    logo_path = Path(logo_path_str)
    if not logo_path.is_file():
        raise HTTPException(status_code=404, detail=f"Logo file not found: {module_name} (looked at {logo_path})")

    suffix = logo_path.suffix.lower()
    media_types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
    media_type = media_types.get(suffix, "application/octet-stream")

    return FileResponse(path=str(logo_path), media_type=media_type)


# ============================================================================
# REFLEX APP
# ============================================================================


def _event_websocket_path() -> str:
    """Return the configured Reflex websocket endpoint path."""
    config = get_config()
    return config.prepend_backend_path(str(constants.Endpoint.EVENT))


def _is_reflex_event_websocket(path: str) -> bool:
    """Check whether a websocket path targets Reflex's event endpoint."""
    event_path = _event_websocket_path().rstrip("/")
    return path == event_path or path.startswith(f"{event_path}/")


def _handle_frontend_exception(exception: Exception) -> None:
    """Suppress known stale-client frontend errors; keep normal Reflex logging."""

    message = str(exception).lower()
    if all(marker in message for marker in _SUPPRESSED_STALE_CLIENT_FRONTEND_ERROR_MARKERS) and any(
        marker in message for marker in _SUPPRESSED_STALE_CLIENT_STACK_MARKERS
    ):
        if "reflex-version-mismatch" not in _logged_suppressed_frontend_errors:
            logger.warning("Suppressing repeated stale Reflex frontend bundle errors")
            _logged_suppressed_frontend_errors.add("reflex-version-mismatch")
        return

    default_frontend_exception_handler(exception)


def _normalize_raw_path(raw_path: object, new_path: str) -> bytes:
    """Return a raw_path compatible with a rewritten ASGI path."""

    if isinstance(raw_path, bytes) and raw_path:
        query_index = raw_path.find(b"?")
        if query_index >= 0:
            return new_path.encode("utf-8") + raw_path[query_index:]
    return new_path.encode("utf-8")


def _guard_reflex_event_websockets(asgi_app: ASGIApp) -> ASGIApp:
    """Normalize Reflex event websockets and close stale frontend clients early.

    In production fullstack mode Reflex mounts the compiled frontend at `/`.
    Unknown websocket paths can otherwise reach Starlette StaticFiles, which
    asserts that the ASGI scope is HTTP-only and logs a server exception.

    Reflex also only warns after accepting a frontend/backend version mismatch.
    Closing stale clients with 1012 forces old browser bundles to reconnect
    against the current hashed assets instead of spamming frontend exceptions.
    """

    async def guarded_app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            path = str(scope.get("path", ""))
            event_path = _event_websocket_path().rstrip("/")
            if path == event_path:
                normalized_path = f"{event_path}/"
                scope = {
                    **scope,
                    "path": normalized_path,
                    "raw_path": _normalize_raw_path(scope.get("raw_path"), normalized_path),
                }
                path = normalized_path

            if not _is_reflex_event_websocket(path):
                await send({"type": "websocket.close", "code": 1000})
                return

            subprotocols = scope.get("subprotocols") or []
            frontend_version = str(subprotocols[0]) if subprotocols else ""
            if frontend_version and frontend_version != constants.Reflex.VERSION:
                if "stale-ws" not in _logged_suppressed_frontend_errors:
                    logger.warning(
                        "Closing stale Reflex frontend websocket: frontend=%s backend=%s "
                        "(further occurrences suppressed)",
                        frontend_version,
                        constants.Reflex.VERSION,
                    )
                    _logged_suppressed_frontend_errors.add("stale-ws")
                await send({"type": "websocket.close", "code": 1012})
                return

        await asgi_app(scope, receive, send)

    return guarded_app


_NO_STORE_FRONTEND_PATHS = {
    "/",
    "/index.html",
    "/manifest.json",
}
_NO_STORE_FRONTEND_PREFIXES = (
    "/utils/",
)


def _should_disable_frontend_cache(path: str) -> bool:
    """Return whether a frontend response should be revalidated on every load."""
    return (
        path in _NO_STORE_FRONTEND_PATHS
        or path.endswith(".html")
        or any(path.startswith(prefix) for prefix in _NO_STORE_FRONTEND_PREFIXES)
    )


def _disable_stale_frontend_cache(asgi_app: ASGIApp) -> ASGIApp:
    """Avoid serving a Reflex frontend built for an older backend version.

    Reflex embeds its package version in the generated client runtime. If the
    browser keeps an old HTML shell or `/utils/state.js`, it reconnects with the
    previous client version and can spam version-mismatch warnings until the tab
    is refreshed.
    """

    async def guarded_app(scope: Scope, receive: Receive, send: Send) -> None:
        path = str(scope.get("path", ""))
        disable_cache = scope["type"] == "http" and _should_disable_frontend_cache(path)

        async def send_with_cache_headers(message: dict[str, object]) -> None:
            if disable_cache and message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                headers["Pragma"] = "no-cache"
                headers["Expires"] = "0"
            await send(message)

        await asgi_app(scope, receive, send_with_cache_headers)

    return guarded_app


def _head_components() -> list[rx.Component]:
    """Build app-level head scripts compiled into the Reflex frontend shell."""

    umami_script_url, umami_website_id, umami_domains, umami_host_url = umami_config()
    if not umami_script_url or not umami_website_id:
        return []

    umami_attrs: dict[str, str] = {"data-website-id": umami_website_id}
    if umami_domains:
        umami_attrs["data-domains"] = umami_domains
    if umami_host_url:
        umami_attrs["data-host-url"] = umami_host_url

    return [rx.script(src=umami_script_url, custom_attrs=umami_attrs)]


app = rx.App(
    # Disable Radix theme to let Fomantic UI styles work properly
    theme=None,
    head_components=_head_components(),
    frontend_exception_handler=_handle_frontend_exception,
    # Guard the Reflex backend before mounting it under custom FastAPI routes,
    # so future FastAPI websocket routes can still be handled explicitly.
    api_transformer=[_guard_reflex_event_websockets, _disable_stale_frontend_cache, api],
)


@contextlib.asynccontextmanager
async def _compute_tier_lifespan() -> AsyncIterator[None]:
    """Own the compute tier for the lifetime of the ASGI app.

    Bringing the pool up here rather than on first use means the spawn cost and the
    workers' polars import are paid at startup, not by whoever clicks a column header
    first.  On the way out, workers and job children are SIGKILLed: a child parked in a
    native thread pool never runs a Python signal handler, so a polite shutdown would
    leave orphans behind.
    """
    clear_grid_artifacts()  # a SIGKILLed previous run leaves ownerless sorted parquet
    start_pool()
    try:
        yield
    finally:
        stop_pool()
        killed = kill_all_jobs()
        if killed:
            print(f"[compute] killed {len(killed)} job child(ren) on shutdown", flush=True)
        clear_grid_artifacts()


app.register_lifespan_task(_compute_tier_lifespan)

# Ensure pages are registered.
app.add_page(dashboard_page)
app.add_page(index_page)
app.add_page(analysis_page)
app.add_page(annotate_page)
if MODULE_CREATOR_ENABLED:
    app.add_page(modules_page)
app.add_page(registry_page)
app.add_page(faq_page)
