from __future__ import annotations

import reflex as rx

from webui.components.layout import app_shell
from webui.state import AuthState


@rx.page(route="/analysis")
def analysis_page() -> rx.Component:
    return app_shell(
        rx.cond(
            AuthState.is_authenticated,
            rx.vstack(
                rx.heading("Analysis", size="6"),
                rx.text("Interactive VCF analysis and filtering coming soon."),
                spacing="4",
            ),
            rx.cond(
                AuthState.login_disabled,
                rx.vstack(
                    rx.heading("Public Analysis", size="6"),
                    rx.text("Login is disabled. You are viewing the public version of the app."),
                    spacing="4",
                ),
                rx.center(
                    rx.vstack(
                        rx.icon("lock", size=48, color_scheme="gray"),
                        rx.heading("Protected Content", size="6"),
                        rx.text("Please sign in using the form in the top-right corner to access analysis tools."),
                        spacing="4",
                        padding_y="12",
                    ),
                    width="100%",
                ),
            ),
        )
    )

