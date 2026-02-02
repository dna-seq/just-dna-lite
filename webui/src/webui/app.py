from __future__ import annotations

from pathlib import Path

import reflex as rx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from just_dna_pipelines.runtime import load_env

from webui.pages.dashboard import dashboard_page
from webui.pages.index import index_page
from webui.pages.analysis import analysis_page
from webui.pages.annotate import annotate_page

# Load environment variables from .env file (searching up to root)
load_env()

# Get workspace root for file paths
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]


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
    
    # Build the file path
    file_path = WORKSPACE_ROOT / "data" / "output" / "users" / user_id / sample_name / "modules" / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    
    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")
    
    # Return the file for download
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream",
    )


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
