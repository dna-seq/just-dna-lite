"""
Index page - Main annotation interface with 3-column layout.

This is the primary page where users upload VCF files, select modules, and run annotation jobs.
"""
from __future__ import annotations

import reflex as rx

from webui.components.layout import template, three_column_layout
from webui.state import UploadState
from webui.pages.annotate import (
    file_column_content,
    module_column_content,
    results_column_content,
    polling_interval,
)


@rx.page(route="/", on_load=UploadState.on_load)
def index_page() -> rx.Component:
    """Main annotation page with three-column layout."""
    return template(
        # Page header
        rx.el.div(
            rx.el.h2(
                rx.icon("dna", size=32, color="#2185d0"),
                " Genomic Annotation",
                style={"display": "flex", "alignItems": "center", "gap": "10px", "margin": "0"},
            ),
            rx.el.div(
                "Analyze your VCF files with specialized annotation modules",
                style={"color": "#666", "marginTop": "6px"},
            ),
            style={"marginBottom": "20px"},
        ),
        
        # Three-column layout
        three_column_layout(
            left=file_column_content(),
            center=module_column_content(),
            right=results_column_content(),
        ),
        
        # Polling component (hidden)
        polling_interval(),
    )
