from __future__ import annotations

import reflex as rx
from genobear.runtime import load_env

from webui.pages.dashboard import dashboard_page
from webui.pages.index import index_page
from webui.pages.analysis import analysis_page
from webui.pages.jobs import jobs_page

# Load environment variables from .env file (searching up to root)
load_env()

app = rx.App(
    theme=rx.theme(
        appearance="light",
        has_background=True,
        accent_color="indigo",
        radius="large",
    )
)

# Ensure pages are registered.
app.add_page(dashboard_page)
app.add_page(index_page)
app.add_page(analysis_page)
app.add_page(jobs_page)
