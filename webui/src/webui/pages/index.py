from __future__ import annotations

import reflex as rx

from webui.components.layout import template, DAISY_CARD


@rx.page(route="/")
def index_page() -> rx.Component:
    """Index page - welcome screen."""
    return template(
        rx.center(
            rx.vstack(
                rx.image(
                    src="/just_dna_seq.jpg",
                    width="200px",
                    height="auto",
                    class_name="rounded-md shadow-lg",
                ),
                rx.heading("Just DNA Lite", size="9", weight="bold", class_name="text-primary"),
                rx.text("Your personal genomic analysis workbench", size="5", class_name="text-base-content/70"),
                
                rx.vstack(
                    rx.box(
                        rx.hstack(
                            # Upload VCF
                            rx.link(
                                rx.box(
                                    rx.vstack(
                                        rx.icon("upload", size=48, class_name="text-primary"),
                                        rx.heading("Upload VCF", size="5", weight="bold"),
                                        rx.text("DNA sample in VCF format", size="2", class_name="text-base-content/60", align="center"),
                                        align="center",
                                        spacing="2",
                                    ),
                                    class_name=f"{DAISY_CARD} w-64 hover:shadow-lg active:scale-95 transition-all cursor-pointer",
                                ),
                                href="/dashboard",
                                underline="none",
                            ),
                            
                            # Arrow to Annotate
                            rx.vstack(
                                rx.icon("arrow-right", size=32, class_name="text-base-content/30"),
                                width="60px",
                                align="center",
                            ),
                            
                            # Annotate
                            rx.link(
                                rx.box(
                                    rx.vstack(
                                        rx.icon("microscope", size=48, class_name="text-success"),
                                        rx.heading("Annotate", size="5", weight="bold"),
                                        rx.text("Genetic & Longevity filters", size="2", class_name="text-base-content/60", align="center"),
                                        align="center",
                                        spacing="2",
                                    ),
                                    class_name=f"{DAISY_CARD} w-64 hover:shadow-lg active:scale-95 transition-all cursor-pointer",
                                ),
                                href="/dashboard",
                                underline="none",
                            ),
                            
                            # Branching Arrows
                            rx.box(
                                rx.html("""
                                <svg width="60" height="120" viewBox="0 0 60 120" fill="none" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M0 60 H20 C35 60 35 20 50 20 H60" stroke="currentColor" stroke-width="2" class="text-base-content/20"/>
                                    <path d="M0 60 H20 C35 60 35 100 50 100 H60" stroke="currentColor" stroke-width="2" class="text-base-content/20"/>
                                    <path d="M55 15 L60 20 L55 25" stroke="currentColor" stroke-width="2" class="text-base-content/20"/>
                                    <path d="M55 95 L60 100 L55 105" stroke="currentColor" stroke-width="2" class="text-base-content/20"/>
                                </svg>
                                """),
                                width="60px",
                                height="120px",
                            ),
                            
                            # Parallel Explore & Report
                            rx.vstack(
                                rx.link(
                                    rx.box(
                                        rx.hstack(
                                            rx.icon("search", size=32, class_name="text-info"),
                                            rx.vstack(
                                                rx.text("Explore", weight="bold", size="4"),
                                                rx.text("Interactive discovery", size="2", class_name="text-base-content/60"),
                                                align="start",
                                                spacing="0",
                                            ),
                                            align="center",
                                            spacing="3",
                                        ),
                                        class_name=f"{DAISY_CARD} w-64 p-4 hover:shadow-lg active:scale-95 transition-all cursor-pointer",
                                    ),
                                    href="/analysis",
                                    underline="none",
                                ),
                                rx.link(
                                    rx.box(
                                        rx.hstack(
                                            rx.icon("file-text", size=32, class_name="text-warning"),
                                            rx.vstack(
                                                rx.text("Report", weight="bold", size="4"),
                                                rx.text("Genetic longevity reports", size="2", class_name="text-base-content/60"),
                                                align="start",
                                                spacing="0",
                                            ),
                                            align="center",
                                            spacing="3",
                                        ),
                                        class_name=f"{DAISY_CARD} w-64 p-4 hover:shadow-lg active:scale-95 transition-all cursor-pointer",
                                    ),
                                    href="/analysis",
                                    underline="none",
                                ),
                                spacing="4",
                                justify="center",
                            ),
                            align="center",
                            spacing="0",
                        ),
                        width="100%",
                        overflow_x="auto",
                        padding_x="4",
                    ),
                    width="100%",
                    padding_y="12",
                    align="center",
                ),

                spacing="6",
                align="center",
                max_width="1000px",
            ),
            height="80vh",
        )
    )


