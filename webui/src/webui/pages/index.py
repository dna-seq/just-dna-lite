"""
Index page - Main annotation interface with 2-panel run-centric layout.

This is the primary page where users upload VCF files, select modules, and run annotation jobs.
"""
from __future__ import annotations

import reflex as rx

from webui.components.layout import template, two_column_layout, fomantic_icon
from webui.state import UploadState
from webui.pages.annotate import (
    file_column_content,
    right_panel_run_view,
    polling_interval,
)


@rx.page(route="/", on_load=UploadState.on_load)
def index_page() -> rx.Component:
    """Main annotation page with two-panel run-centric layout."""
    return template(
        # Two-column layout with run-centric right panel
        two_column_layout(
            left=file_column_content(),
            right=right_panel_run_view(),
        ),
        
        # Polling component (hidden)
        polling_interval(),
    )
