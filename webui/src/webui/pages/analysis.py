from __future__ import annotations

import reflex as rx

from webui.components.layout import template, DAISY_CARD, DAISY_BUTTON_PRIMARY


@rx.page(route="/analysis")
def analysis_page() -> rx.Component:
    return template(
        rx.vstack(
            rx.heading("Interpretation & Discovery", size="8", class_name="text-primary"),
            rx.text("Parallel paths for discovery: genetic reports and interactive exploration.", class_name="text-base-content/60"),
            rx.grid(
                rx.box(
                    rx.vstack(
                        rx.icon("file-text", size=48, class_name="text-warning"),
                        rx.heading("Genetic Reports", size="5"),
                        rx.text("Static, genetic-grade longevity reports for easy reading and sharing.", size="2", class_name="text-base-content/60", align="center"),
                        rx.button("View Reports", class_name="btn btn-warning btn-md w-full font-bold"),
                        spacing="3",
                        align="center",
                        padding="6",
                    ),
                    class_name=DAISY_CARD,
                    width="100%",
                ),
                rx.box(
                    rx.vstack(
                        rx.icon("search", size=48, class_name="text-info"),
                        rx.heading("Interactive Explore", size="5"),
                        rx.text("Deep dive into variants, filter by consequence and genetic significance.", size="2", class_name="text-base-content/60", align="center"),
                        rx.button("Start Exploring", class_name="btn btn-info btn-md w-full font-bold"),
                        spacing="3",
                        align="center",
                        padding="6",
                    ),
                    class_name=DAISY_CARD,
                    width="100%",
                ),
                columns=rx.breakpoints(initial="1", sm="2"),
                spacing="6",
                width="100%",
                padding_y="6",
            ),
            rx.box(
                rx.vstack(
                    rx.heading("Sample Information", size="5"),
                    rx.text("Details about the currently selected genomic sample.", size="2", class_name="text-base-content/60"),
                    width="100%",
                    spacing="2",
                ),
                class_name=DAISY_CARD,
                width="100%",
            ),
            spacing="8",
            width="100%",
        )
    )

