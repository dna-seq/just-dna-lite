from __future__ import annotations

import reflex as rx

from webui.components.layout import template


@rx.page(route="/analysis")
def analysis_page() -> rx.Component:
    """Analysis page using Fomantic UI styling."""
    return template(
        rx.el.div(
            rx.el.h1(
                rx.icon("chart-bar", size=40),
                " Interpretation & Discovery", 
                class_name="ui header",
                style={"color": "#2185d0"}
            ),
            rx.el.p(
                "Parallel paths for discovery: genetic reports and interactive exploration.", 
                style={"color": "#666", "fontSize": "1.2rem"}
            ),
            
            rx.el.div(
                rx.el.div(
                    rx.el.div(
                        rx.el.div(
                            rx.icon("file-text", size=48, style={"color": "#f2711c"}),
                            rx.el.h3("Genetic Reports", class_name="ui header"),
                            rx.el.p(
                                "Static, genetic-grade longevity reports for easy reading and sharing.", 
                                style={"color": "#888"}
                            ),
                            rx.el.button("View Reports", class_name="ui orange fluid button"),
                            class_name="ui segment raised center aligned",
                        ),
                        class_name="column",
                    ),
                    rx.el.div(
                        rx.el.div(
                            rx.icon("search", size=48, style={"color": "#2185d0"}),
                            rx.el.h3("Interactive Explore", class_name="ui header"),
                            rx.el.p(
                                "Deep dive into variants, filter by consequence and genetic significance.", 
                                style={"color": "#888"}
                            ),
                            rx.el.button("Start Exploring", class_name="ui blue fluid button"),
                            class_name="ui segment raised center aligned",
                        ),
                        class_name="column",
                    ),
                    class_name="row",
                ),
                class_name="ui two column stackable grid",
                style={"paddingY": "20px"},
            ),
            
            rx.el.div(
                rx.el.h3("Sample Information", class_name="ui header"),
                rx.el.p(
                    "Details about the currently selected genomic sample.", 
                    style={"color": "#888"}
                ),
                class_name="ui segment raised",
                style={"width": "100%", "marginTop": "20px"},
            ),
            
            style={"width": "100%", "padding": "20px"},
        )
    )
