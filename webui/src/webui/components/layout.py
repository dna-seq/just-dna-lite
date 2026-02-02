from __future__ import annotations

import reflex as rx


def fomantic_icon(name: str, size: int | str | None = None, color: str | None = None, style: dict | None = None) -> rx.Component:
    """
    Fomantic UI icon component.
    Replaces rx.icon because Lucide icons often fail to load or give warnings.
    
    Args:
        name: The Fomantic UI icon name (e.g. "dna", "heart", "cloud upload")
        size: Font size (e.g. 24, "1.5rem")
        color: Icon color (CSS color)
        style: Additional CSS styles
    """
    # Mapping some common Lucide names to Fomantic names if they differ
    mapping = {
        "circle-check": "check circle",
        "circle-x": "times circle",
        "circle-alert": "exclamation circle",
        "circle-play": "play circle",
        "cloud-upload": "cloud upload",
        "file-text": "file alternate",
        "refresh-cw": "sync",
        "external-link": "external alternate",
        "chart-bar": "chart bar",
        "git-fork": "fork",
        "trash-2": "trash alternate",
        "sliders-horizontal": "sliders",
        "folder-output": "folder open",
        "plus-circle": "plus circle",
        "folder-x": "folder open",
        "heart-pulse": "heartbeat",
        "activity": "pulse",
        "zap": "bolt",
        "droplets": "tint",
        "pill": "pills",
        "book-open": "book open",
        "chevron-up": "chevron up",
        "chevron-down": "chevron down",
        "chevron-right": "chevron right",
        "trash-2": "trash alternate",
        "folder-output": "folder open",
        "plus-circle": "plus circle",
        "x": "times",
    }
    
    fomantic_name = mapping.get(name, name)
    
    icon_style = style or {}
    if size is not None:
        # If size is numeric, assume pixels
        if isinstance(size, (int, float)) or (isinstance(size, str) and size.isdigit()):
            icon_style["fontSize"] = f"{size}px"
        else:
            icon_style["fontSize"] = size
            
    if color is not None:
        icon_style["color"] = color
        
    return rx.el.i(
        class_name=f"icon {fomantic_name}",
        style=icon_style,
    )


def github_corner() -> rx.Component:
    """
    GitHub Corners - modern SVG octocat in top-right corner.
    Based on tholman.com/github-corners with waving arm animation.
    """
    # CSS for the animation
    animation_css = """
    .github-corner:hover .octo-arm {
        animation: octocat-wave 560ms ease-in-out;
    }
    @keyframes octocat-wave {
        0%, 100% { transform: rotate(0); }
        20%, 60% { transform: rotate(-25deg); }
        40%, 80% { transform: rotate(10deg); }
    }
    @media (max-width: 500px) {
        .github-corner:hover .octo-arm { animation: none; }
        .github-corner .octo-arm { animation: octocat-wave 560ms ease-in-out; }
    }
    """
    
    # The octocat SVG paths from github-corners by Tim Holman
    svg_html = '''<svg width="80" height="80" viewBox="0 0 250 250" style="fill:#151513; color:#fff; position: absolute; top: 0; border: 0; right: 0;" aria-hidden="true">
        <path d="M0,0 L115,115 L130,115 L142,142 L250,250 L250,0 Z"></path>
        <path d="M128.3,109.0 C113.8,99.7 119.0,89.6 119.0,89.6 C122.0,82.7 120.5,78.6 120.5,78.6 C119.2,72.0 123.4,76.3 123.4,76.3 C127.3,80.9 125.5,87.3 125.5,87.3 C122.9,97.6 130.6,101.9 134.4,103.2" fill="currentColor" style="transform-origin: 130px 106px;" class="octo-arm"></path>
        <path d="M115.0,115.0 C114.9,115.1 118.7,116.5 119.8,115.4 L133.7,101.6 C136.9,99.2 139.9,98.4 142.2,98.6 C133.8,88.0 127.5,74.4 143.8,58.0 C148.5,53.4 154.0,51.2 159.7,51.0 C160.3,49.4 163.2,43.6 171.4,40.1 C171.4,40.1 176.1,42.5 178.8,56.2 C183.1,58.6 187.2,61.8 190.9,65.4 C194.5,69.0 197.7,73.2 200.1,77.6 C213.8,80.2 216.3,84.9 216.3,84.9 C212.7,93.1 206.9,96.0 205.4,96.6 C205.1,102.4 203.0,107.8 198.3,112.5 C181.9,128.9 168.3,122.5 157.7,114.1 C157.9,116.9 156.7,120.9 152.7,124.9 L141.0,136.5 C139.8,137.7 141.6,141.9 141.8,141.8 Z" fill="currentColor" class="octo-body"></path>
    </svg>'''
    
    return rx.fragment(
        # Inject animation CSS
        rx.el.style(animation_css),
        # GitHub corner SVG
        rx.el.a(
            rx.html(svg_html),
            href="https://github.com/dna-seq/just-dna-lite",
            target="_blank",
            class_name="github-corner",
            aria_label="View source on GitHub",
            style={
                "position": "fixed",
                "top": "0",
                "right": "0",
                "zIndex": "2000",
            },
        ),
    )


def topbar() -> rx.Component:
    """Top navigation bar using flexbox for reliable horizontal layout."""
    return rx.el.div(
        # Left: Logo
        rx.el.div(
            rx.el.a(
                rx.el.img(
                    src="/just_dna_seq.jpg",
                    style={"height": "36px", "width": "auto", "marginRight": "12px"},
                ),
                rx.el.span(
                    "just-dna-lite",
                    style={"fontSize": "1.3rem", "fontWeight": "600", "color": "#333"},
                ),
                href="/",
                style={"display": "flex", "alignItems": "center", "textDecoration": "none"},
            ),
            style={"display": "flex", "alignItems": "center", "flex": "0 0 auto"},
        ),
        # Center: Page title and subtitle
        rx.el.div(
            fomantic_icon("dna", size=28, color="#2185d0"),
            rx.el.div(
                rx.el.span(
                    "Genomic Annotation",
                    style={"fontSize": "1.25rem", "fontWeight": "600", "color": "#333"},
                ),
                rx.el.span(
                    " — Analyze your VCF files with specialized annotation modules",
                    style={"fontSize": "0.95rem", "color": "#666", "marginLeft": "8px"},
                ),
                style={"display": "flex", "alignItems": "baseline", "marginLeft": "10px"},
            ),
            style={"display": "flex", "alignItems": "center", "justifyContent": "center", "flex": "1 1 auto"},
        ),
        # Right: Spacer for GitHub corner (the corner is positioned fixed separately)
        rx.el.div(
            style={"width": "80px", "flex": "0 0 80px"},  # Reserve space for the corner
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
        # GitHub corner ribbon (top-right)
        github_corner(),
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


def two_column_layout(
    left: rx.Component,
    right: rx.Component,
) -> rx.Component:
    """
    Two-column layout with independently scrollable columns.
    
    Left column is narrow (files), right column is wide (tabbed content).
    Uses flexbox for reliable horizontal layout.
    """
    # 56px header + 20px padding top + 20px padding bottom
    column_height = "calc(100vh - 96px)"
    
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
        "margin": "0 12px",
        "flexShrink": "0",
    }
    
    return rx.el.div(
        # Left Column (width: ~28%)
        rx.el.div(
            left,
            style={**column_base, "flex": "0 0 28%", "minWidth": "280px", "maxWidth": "350px"},
            id="layout-left-column",
        ),
        # Divider
        rx.el.div(style=divider_style),
        # Right Column (width: ~70%, flexible)
        rx.el.div(
            right,
            style={**column_base, "flex": "1 1 70%", "minWidth": "500px"},
            id="layout-right-column",
        ),
        style={
            "display": "flex",
            "flexDirection": "row",
            "gap": "0",
            "width": "100%",
            "alignItems": "stretch",
        },
        id="two-column-layout",
    )


def three_column_layout(
    left: rx.Component,
    center: rx.Component,
    right: rx.Component,
) -> rx.Component:
    """
    Three-column layout with independently scrollable columns.
    
    Uses flexbox for reliable horizontal layout with dividers between columns.
    
    DEPRECATED: Use two_column_layout with tabs instead.
    """
    # 56px header + 20px padding top + 20px padding bottom
    column_height = "calc(100vh - 96px)"
    
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
