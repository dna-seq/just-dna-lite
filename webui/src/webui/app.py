from __future__ import annotations

import reflex as rx
from just_dna_pipelines.runtime import load_env

from webui.pages.dashboard import dashboard_page
from webui.pages.index import index_page
from webui.pages.analysis import analysis_page
from webui.pages.annotate import annotate_page

# Load environment variables from .env file (searching up to root)
load_env()

app = rx.App(
    # Disable Radix theme to let Fomantic UI styles work properly
    theme=None,
)

# Ensure pages are registered.
app.add_page(dashboard_page)
app.add_page(index_page)
app.add_page(analysis_page)
app.add_page(annotate_page)
