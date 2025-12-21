"""
GenoBear Pipeline Registry - Extensible pipeline management system.

This module provides an app-store-like registry for Prefect-based pipelines,
allowing users to discover, register, and serve genomic annotation pipelines.

The registry supports:
- Built-in pipelines (annotation, preparation, etc.)
- User-installed pipelines via entry points
- Dynamic flow discovery and registration

Usage:
    from genobear.pipelines import store
    
    # Get all registered pipelines
    pipelines = store.list_pipelines()
    
    # Serve all pipelines with Prefect
    from genobear.pipelines import serve_pipelines
    serve_pipelines()

CLI Usage:
    # List all pipelines
    uv run pipelines list
    
    # Serve all pipelines
    uv run pipelines serve
"""

from genobear.pipelines.registry import (
    PipelineStore,
    PipelineInfo,
    PipelineCategory,
    store,
)
from genobear.pipelines.serve import serve_pipelines
from genobear.pipelines.cli import app

__all__ = [
    "PipelineStore",
    "PipelineInfo",
    "PipelineCategory",
    "store",
    "serve_pipelines",
    "app",
]

