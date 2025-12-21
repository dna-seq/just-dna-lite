from __future__ import annotations

import reflex as rx

from webui.components.layout import app_shell


@rx.page(route="/")
def index_page() -> rx.Component:
    """Index page - welcome screen."""
    return app_shell(
        rx.center(
            rx.vstack(
                rx.icon("dna", size=64, color="var(--indigo-9)"),
                rx.heading("GenoBear Platform", size="8"),
                rx.text("Personalized genomics platform", size="4", color="gray"),
                rx.button(
                    "Go to Dashboard",
                    size="3",
                    on_click=rx.redirect("/dashboard"),
                ),
                spacing="4",
                align="center",
            ),
            height="60vh",
        )
    )


