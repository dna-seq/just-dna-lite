from __future__ import annotations

import sys
from pathlib import Path

import reflex as rx
import io
import zipfile

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from just_dna_pipelines.runtime import load_env
from just_dna_pipelines.annotation.resources import get_user_output_dir

from webui.pages.dashboard import dashboard_page
from webui.pages.index import index_page
from webui.pages.analysis import analysis_page
from webui.pages.annotate import annotate_page
from webui.pages.modules import modules_page

# Load environment variables from .env file (searching up to root)
load_env()

# Note: Shutdown cleanup of STARTED runs is handled by the parent `uv run start` command,
# which catches Ctrl+C and cleans up before killing subprocesses.


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

from just_dna_pipelines.annotation.resources import get_generated_modules_dir

_GENERATED_MODULES_DIR = get_generated_modules_dir()



# ============================================================================
# CUSTOM API ENDPOINTS
# ============================================================================

# Create a FastAPI app for custom API routes
api = FastAPI()


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

    file_path = USER_OUTPUT_DIR / user_id / sample_name / "vcf_exports" / filename

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


@api.get("/api/report/{user_id}/{sample_name}/{filename}")
async def view_report_file(user_id: str, sample_name: str, filename: str) -> FileResponse:
    """
    Serve an HTML report file for viewing in the browser.
    
    Path: /api/report/{user_id}/{sample_name}/{filename}
    Example: /api/report/anonymous/antku_small/longevity_report.html
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
    
    return FileResponse(
        path=str(file_path),
        media_type="text/html",
    )


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

app = rx.App(
    # Disable Radix theme to let Fomantic UI styles work properly
    theme=None,
    # Use api_transformer to add custom FastAPI routes
    api_transformer=api,
)

# Ensure pages are registered.
app.add_page(dashboard_page)
app.add_page(index_page)
app.add_page(analysis_page)
app.add_page(annotate_page)
app.add_page(modules_page)
