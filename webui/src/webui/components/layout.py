from __future__ import annotations

import reflex as rx
import os


def get_dagster_web_url() -> str:
    """Get the URL for the Dagster web UI from environment or default."""
    return os.getenv("DAGSTER_WEB_URL", "http://localhost:3005").rstrip("/")


def topbar() -> rx.Component:
    """Top navigation bar using flexbox for reliable horizontal layout."""
    dagster_url = get_dagster_web_url()
    return rx.el.div(
        # Left: Logo and Nav
        rx.el.div(
            # Logo
            rx.el.a(
                rx.el.img(
                    src="/just_dna_seq.jpg",
                    style={"height": "32px", "width": "auto", "marginRight": "12px"},
                ),
                rx.el.span(
                    "just-dna-lite",
                    style={"fontSize": "1.3rem", "fontWeight": "600", "color": "#333"},
                ),
                href="/",
                style={"display": "flex", "alignItems": "center", "textDecoration": "none", "marginRight": "30px"},
            ),
            # Nav Links
            rx.el.a(
                rx.icon("dna", size=18),
                rx.el.span(" Annotate", style={"marginLeft": "6px"}),
                href="/",
                style={"display": "flex", "alignItems": "center", "padding": "10px 16px", "color": "#555", "textDecoration": "none", "borderRadius": "4px", "fontSize": "1rem"},
                id="nav-annotate",
            ),
            rx.el.a(
                rx.icon("chart-bar", size=18),
                rx.el.span(" Analysis", style={"marginLeft": "6px"}),
                href="/analysis",
                style={"display": "flex", "alignItems": "center", "padding": "10px 16px", "color": "#555", "textDecoration": "none", "borderRadius": "4px", "fontSize": "1rem"},
                id="nav-analysis",
            ),
            style={"display": "flex", "alignItems": "center"},
        ),
        # Right: External Links
        rx.el.div(
            rx.el.a(
                rx.icon("external-link", size=16),
                rx.el.span(" Dagster", style={"marginLeft": "6px"}),
                href=dagster_url,
                target="_blank",
                class_name="ui button",
                id="topbar-dagster-link",
                style={"display": "flex", "alignItems": "center", "marginRight": "10px", "whiteSpace": "nowrap"},
            ),
            rx.el.a(
                rx.icon("git-fork", size=16),
                rx.el.span(" Fork on GitHub", style={"marginLeft": "6px"}),
                href="https://github.com/dna-seq/just-dna-lite",
                target="_blank",
                class_name="ui button",
                id="topbar-github-link",
                style={"display": "flex", "alignItems": "center", "whiteSpace": "nowrap"},
            ),
            style={"display": "flex", "alignItems": "center"},
        ),
        style={
            "position": "fixed",
            "top": "0",
            "left": "0",
            "right": "0",
            "height": "56px",
            "backgroundColor": "#ffffff",
            "borderBottom": "1px solid #e0e0e0",
            "boxShadow": "0 1px 3px rgba(0,0,0,0.08)",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "space-between",
            "padding": "0 24px",
            "zIndex": "1000",
        },
        id="topbar",
    )


def fomantic_stylesheets() -> rx.Component:
    """Load Fomantic UI stylesheets directly (rxconfig stylesheets may not load)."""
    return rx.fragment(
        rx.el.link(
            rel="stylesheet",
            href="https://cdn.jsdelivr.net/npm/fomantic-ui@2.9.4/dist/semantic.min.css",
        ),
        rx.script(src="https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js"),
        rx.script(src="https://cdn.jsdelivr.net/npm/fomantic-ui@2.9.4/dist/semantic.min.js"),
    )


def template(*children: rx.Component) -> rx.Component:
    """Main page template with Fomantic UI styling."""
    return rx.el.div(
        # Load Fomantic UI directly
        fomantic_stylesheets(),
        topbar(),
        rx.el.div(
            rx.el.div(
                *children,
                class_name="ui fluid container",
            ),
            style={
                "marginTop": "56px",
                "padding": "20px",
                "minHeight": "calc(100vh - 56px)",
                "backgroundColor": "#f5f7fa",
            },
        ),
        style={"fontFamily": "'Lato', 'Helvetica Neue', Arial, Helvetica, sans-serif"},
    )


def three_column_layout(
    left: rx.Component,
    center: rx.Component,
    right: rx.Component,
) -> rx.Component:
    """
    Three-column layout with independently scrollable columns.
    
    Uses flexbox for reliable horizontal layout with dividers between columns.
    """
    # 56px header + 20px padding top + 20px padding bottom + ~50px page header
    column_height = "calc(100vh - 150px)"
    
    # Common column styles
    column_base = {
        "height": column_height,
        "overflowY": "auto",
        "overflowX": "hidden",
        "padding": "16px",
        "backgroundColor": "#ffffff",
        "borderRadius": "4px",
        "boxShadow": "0 1px 2px rgba(0,0,0,0.1)",
    }
    
    # Divider style
    divider_style = {
        "width": "1px",
        "backgroundColor": "#e0e0e0",
        "margin": "0 10px",
        "flexShrink": "0",
    }
    
    return rx.el.div(
        # Left Column (width: 30%)
        rx.el.div(
            left,
            style={**column_base, "flex": "0 0 30%", "minWidth": "280px"},
            id="layout-left-column",
        ),
        # Divider
        rx.el.div(style=divider_style),
        # Center Column (width: 40%)
        rx.el.div(
            center,
            style={**column_base, "flex": "0 0 35%", "minWidth": "320px"},
            id="layout-center-column",
        ),
        # Divider
        rx.el.div(style=divider_style),
        # Right Column (width: 30%)
        rx.el.div(
            right,
            style={**column_base, "flex": "1 1 30%", "minWidth": "280px"},
            id="layout-right-column",
        ),
        style={
            "display": "flex",
            "flexDirection": "row",
            "gap": "0",
            "width": "100%",
            "alignItems": "stretch",
        },
        id="three-column-layout",
    )
