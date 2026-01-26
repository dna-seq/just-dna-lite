"""
Genomic Annotation Page - Three-column layout for VCF annotation workflow.

Column 1: File Management (upload and selection)
Column 2: Module Selection (HF annotation modules)
Column 3: Results (run history, logs, downloads)
"""
from __future__ import annotations

import reflex as rx

from webui.components.layout import template, three_column_layout
from webui.state import UploadState, AuthState


# ============================================================================
# COLUMN 1: FILE MANAGEMENT
# ============================================================================

def upload_zone() -> rx.Component:
    """Drag-and-drop upload zone for VCF files."""
    return rx.upload(
        rx.el.div(
            rx.icon("cloud-upload", size=40, color="#2185d0"),
            rx.el.div("Drop VCF files here", style={"fontWeight": "600", "marginTop": "10px", "fontSize": "1rem"}),
            rx.el.div("or click to browse", style={"fontSize": "0.85rem", "color": "#888", "marginTop": "4px"}),
            style={"textAlign": "center", "padding": "20px 10px"},
        ),
        id="vcf_upload",
        style={
            "border": "2px dashed #d4d4d5",
            "borderRadius": "8px",
            "backgroundColor": "#fafafa",
            "cursor": "pointer",
            "width": "100%",
        },
        multiple=True,
        accept={
            "application/vcf": [".vcf", ".vcf.gz"],
            "text/vcf": [".vcf", ".vcf.gz"],
            "application/gzip": [".vcf.gz"],
        },
    )


def file_status_label(status: rx.Var[str]) -> rx.Component:
    """Return a colored label based on file status."""
    return rx.match(
        status,
        ("completed", rx.el.span("completed", class_name="ui mini green label")),
        ("running", rx.el.span("running", class_name="ui mini blue label")),
        ("ready", rx.el.span("ready", class_name="ui mini label")),
        ("error", rx.el.span("error", class_name="ui mini red label")),
        rx.el.span(status, class_name="ui mini grey label"),
    )


def file_item(filename: rx.Var[str]) -> rx.Component:
    """Single file item - card style like the module browser."""
    return rx.el.div(
        rx.el.div(
            # File icon
            rx.el.div(
                rx.icon("file-text", size=22, color="#5a5a5a"),
                style={
                    "width": "44px",
                    "height": "44px",
                    "backgroundColor": "#f0f0f0",
                    "borderRadius": "6px",
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "marginRight": "12px",
                    "flexShrink": "0",
                },
            ),
            # File info
            rx.el.div(
                rx.el.div(
                    rx.el.strong(filename, style={"fontSize": "0.9rem"}),
                    style={"marginBottom": "4px"},
                ),
                rx.el.div(
                    file_status_label(UploadState.file_statuses[filename]),
                    rx.el.span("VCF", class_name="ui mini grey label", style={"marginLeft": "4px"}),
                    style={"display": "flex", "gap": "4px"},
                ),
                style={"flex": "1"},
            ),
            # Action buttons
            rx.el.div(
                rx.el.button(
                    rx.icon("trash-2", size=14),
                    on_click=lambda: UploadState.delete_file(filename),
                    class_name="ui mini icon button",
                    title="Delete",
                ),
                style={"marginLeft": "auto"},
            ),
            style={"display": "flex", "alignItems": "center", "width": "100%"},
        ),
        on_click=lambda: UploadState.select_file(filename),
        class_name=rx.cond(
            UploadState.selected_file == filename,
            "ui segment secondary",
            "ui segment",
        ),
        style={
            "cursor": "pointer",
            "margin": "0 0 8px 0",
            "padding": "12px",
            "border": rx.cond(
                UploadState.selected_file == filename,
                "2px solid #2185d0",
                "1px solid #e0e0e0",
            ),
            "borderRadius": "6px",
        },
    )


def file_column_content() -> rx.Component:
    """Column 1 content: File upload and selection."""
    return rx.el.div(
        # Header with icon
        rx.el.div(
            rx.icon("files", size=24, color="#2185d0"),
            rx.el.span(" Files", style={"fontSize": "1.2rem", "fontWeight": "600", "marginLeft": "8px"}),
            style={"display": "flex", "alignItems": "center", "marginBottom": "16px"},
        ),
        
        rx.el.div(class_name="ui divider", style={"margin": "0 0 16px 0"}),
        
        # Upload Section
        upload_zone(),
        
        # Selected files preview
        rx.el.div(
            rx.foreach(
                rx.selected_files("vcf_upload"),
                lambda f: rx.el.span(f, class_name="ui mini blue label", style={"margin": "2px"}),
            ),
            style={"marginTop": "8px", "minHeight": "20px"},
        ),
        
        # Upload button
        rx.el.button(
            rx.icon("upload", size=16),
            " Upload",
            on_click=UploadState.handle_upload(rx.upload_files(upload_id="vcf_upload")),
            loading=UploadState.uploading,
            class_name="ui primary button fluid",
            style={"marginTop": "10px"},
        ),
        
        rx.el.div(class_name="ui divider", style={"margin": "20px 0 16px 0"}),
        
        # Library header with refresh
        rx.el.div(
            rx.el.span("Library", style={"fontSize": "1rem", "fontWeight": "600"}),
            rx.el.button(
                rx.icon("refresh-cw", size=14),
                " Refresh",
                on_click=UploadState.on_load,
                class_name="ui mini button",
            ),
            style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "12px"},
        ),
        
        # File list (scrollable area)
        rx.cond(
            UploadState.files.length() > 0,
            rx.el.div(
                rx.foreach(UploadState.files, file_item),
            ),
            rx.el.div(
                rx.icon("inbox", size=40, color="#ccc"),
                rx.el.div("No files yet", style={"color": "#888", "marginTop": "8px"}),
                style={"textAlign": "center", "padding": "30px 10px"},
            ),
        ),
    )


# ============================================================================
# COLUMN 2: MODULE SELECTION
# ============================================================================

def module_icon(name: rx.Var[str]) -> rx.Component:
    """
    Return the appropriate icon for a module.
    Icons must be static strings - use rx.match for dynamic selection.
    """
    return rx.match(
        name,
        ("coronary", rx.icon("heart", size=24, color="#fff")),
        ("lipidmetabolism", rx.icon("droplets", size=24, color="#fff")),
        ("longevitymap", rx.icon("heart-pulse", size=24, color="#fff")),
        ("superhuman", rx.icon("zap", size=24, color="#fff")),
        ("vo2max", rx.icon("activity", size=24, color="#fff")),
        ("drugs", rx.icon("pill", size=24, color="#fff")),
        rx.icon("database", size=24, color="#fff"),  # default
    )


def fomantic_checkbox(checked: rx.Var[bool], on_click: rx.EventHandler) -> rx.Component:
    """
    Fomantic UI styled checkbox.
    
    Structure: <div class="ui checkbox"><input type="checkbox"><label></label></div>
    The checkbox state is controlled via class name (checked adds 'checked' class).
    """
    return rx.el.div(
        rx.el.input(
            type="checkbox",
            checked=checked,
            read_only=True,  # Controlled by parent click
            style={"cursor": "pointer"},
        ),
        rx.el.label(),
        on_click=on_click,
        class_name=rx.cond(checked, "ui checked checkbox", "ui checkbox"),
        style={"marginRight": "12px"},
    )


def module_card(module: rx.Var[dict]) -> rx.Component:
    """
    Module card styled like the reference screenshot.
    Shows: Fomantic checkbox, icon, title, description, badges.
    """
    return rx.el.div(
        rx.el.div(
            # Left: Fomantic UI Checkbox
            fomantic_checkbox(
                checked=module["selected"].to(bool),
                on_click=lambda: UploadState.toggle_module(module["name"]),
            ),
            # Module icon (colored box with Lucide icon)
            rx.el.div(
                module_icon(module["name"]),
                style={
                    "width": "48px",
                    "height": "48px",
                    "backgroundColor": rx.cond(
                        module["selected"].to(bool),
                        "#2185d0",
                        "#888",
                    ),
                    "borderRadius": "6px",
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "marginRight": "12px",
                    "flexShrink": "0",
                },
            ),
            # Content
            rx.el.div(
                rx.el.div(
                    rx.el.strong(module["title"], style={"fontSize": "0.95rem"}),
                    style={"marginBottom": "4px"},
                ),
                rx.el.div(
                    module["description"],
                    style={"fontSize": "0.85rem", "color": "#666", "lineHeight": "1.3", "marginBottom": "6px"},
                ),
                rx.el.div(
                    rx.el.span("annotator", class_name="ui mini grey label"),
                    rx.cond(
                        module["selected"].to(bool),
                        rx.el.span("Selected", class_name="ui mini green label", style={"marginLeft": "4px"}),
                        rx.box(),
                    ),
                ),
                style={"flex": "1"},
            ),
            style={"display": "flex", "alignItems": "flex-start", "width": "100%"},
        ),
        on_click=lambda: UploadState.toggle_module(module["name"]),
        class_name="ui segment",
        style={
            "cursor": "pointer",
            "margin": "0 0 10px 0",
            "padding": "14px",
            "border": "1px solid #e0e0e0",
            "borderRadius": "6px",
            "backgroundColor": rx.cond(module["selected"].to(bool), "#f8faff", "#fff"),
        },
    )


def module_column_content() -> rx.Component:
    """Column 2 content: Module selection."""
    return rx.el.div(
        # Header
        rx.el.div(
            rx.icon("boxes", size=24, color="#2185d0"),
            rx.el.span(" Modules", style={"fontSize": "1.2rem", "fontWeight": "600", "marginLeft": "8px"}),
            rx.el.span(
                UploadState.selected_modules.length(),
                " selected",
                class_name="ui blue label",
                style={"marginLeft": "auto"},
            ),
            style={"display": "flex", "alignItems": "center", "marginBottom": "16px"},
        ),
        
        rx.el.div(class_name="ui divider", style={"margin": "0 0 12px 0"}),
        
        # Selection controls
        rx.el.div(
            rx.el.button(
                "All",
                on_click=UploadState.select_all_modules,
                class_name="ui mini button",
            ),
            rx.el.button(
                "None",
                on_click=UploadState.deselect_all_modules,
                class_name="ui mini button",
                style={"marginLeft": "6px"},
            ),
            style={"marginBottom": "16px", "display": "flex", "gap": "6px"},
        ),
        
        # Module cards (scrollable)
        rx.el.div(
            rx.foreach(UploadState.module_metadata_list, module_card),
        ),
        
        rx.el.div(class_name="ui divider", style={"margin": "16px 0"}),
        
        # Selected file indicator
        rx.el.div(
            rx.cond(
                UploadState.has_selected_file,
                rx.el.div(
                    rx.icon("file-text", size=16),
                    rx.el.span(" ", UploadState.selected_file),
                    class_name="ui label",
                ),
                rx.el.div(
                    rx.icon("file-text", size=16),
                    " No file selected",
                    class_name="ui grey label",
                ),
            ),
            style={"marginBottom": "12px"},
        ),
        
        # Run button
        rx.el.button(
            rx.icon("play", size=18),
            " Start Analysis",
            on_click=UploadState.start_annotation_run,
            disabled=~UploadState.can_run_annotation,
            loading=UploadState.running,
            class_name="ui primary large button fluid",
        ),
    )


# ============================================================================
# COLUMN 3: RESULTS
# ============================================================================

def run_card(run: rx.Var[dict]) -> rx.Component:
    """Run history card with status badge and details."""
    return rx.el.div(
        rx.el.div(
            # Status badge
            rx.el.div(
                run["status"],
                class_name=rx.cond(
                    run["status"] == "SUCCESS",
                    "ui green label",
                    rx.cond(
                        run["status"] == "FAILURE",
                        "ui red label",
                        rx.cond(
                            run["status"] == "RUNNING",
                            "ui blue label",
                            "ui grey label",
                        ),
                    ),
                ),
            ),
            # Timestamp
            rx.el.div(
                run["started_at"],
                style={"fontSize": "0.85rem", "color": "#666", "marginLeft": "10px"},
            ),
            style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
        ),
        # Modules used
        rx.el.div(
            rx.el.span("Modules: ", style={"color": "#888", "fontSize": "0.85rem"}),
            rx.foreach(
                run["modules"].to(list),
                lambda m: rx.el.span(m, class_name="ui mini label", style={"marginRight": "3px"}),
            ),
            style={"marginBottom": "8px"},
        ),
        # Output link if available
        rx.cond(
            run["output_path"],
            rx.el.div(
                rx.icon("download", size=14),
                rx.el.span(" Download results", style={"marginLeft": "4px", "fontSize": "0.85rem"}),
                class_name="ui mini button",
                style={"marginTop": "4px"},
            ),
            rx.box(),
        ),
        class_name="ui segment",
        style={
            "margin": "0 0 10px 0",
            "padding": "12px",
            "border": "1px solid #e0e0e0",
            "borderRadius": "6px",
        },
    )


def results_column_content() -> rx.Component:
    """Column 3 content: Results and run history."""
    return rx.el.div(
        # Header
        rx.el.div(
            rx.icon("chart-bar", size=24, color="#2185d0"),
            rx.el.span(" Results", style={"fontSize": "1.2rem", "fontWeight": "600", "marginLeft": "8px"}),
            rx.el.button(
                rx.icon("refresh-cw", size=14),
                on_click=UploadState.on_load,
                class_name="ui mini icon button",
                style={"marginLeft": "auto"},
            ),
            style={"display": "flex", "alignItems": "center", "marginBottom": "16px"},
        ),
        
        rx.el.div(class_name="ui divider", style={"margin": "0 0 16px 0"}),
        
        # Run history section
        rx.el.div(
            rx.el.span("Run History", style={"fontSize": "1rem", "fontWeight": "600"}),
            style={"marginBottom": "12px"},
        ),
        
        rx.cond(
            UploadState.has_selected_file,
            rx.cond(
                UploadState.has_filtered_runs,
                rx.el.div(
                    rx.foreach(UploadState.filtered_runs, run_card),
                ),
                rx.el.div(
                    rx.icon("history", size=40, color="#ccc"),
                    rx.el.div("No runs for this file", style={"color": "#888", "marginTop": "8px"}),
                    style={"textAlign": "center", "padding": "30px 10px"},
                ),
            ),
            rx.el.div(
                rx.icon("file-text", size=40, color="#ccc"),
                rx.el.div("Select a file to see history", style={"color": "#888", "marginTop": "8px"}),
                style={"textAlign": "center", "padding": "30px 10px"},
            ),
        ),
        
        rx.el.div(class_name="ui divider", style={"margin": "20px 0 16px 0"}),
        
        # Console section
        rx.el.div(
            rx.el.span("Console", style={"fontSize": "1rem", "fontWeight": "600"}),
            style={"marginBottom": "12px"},
        ),
        
        rx.cond(
            UploadState.running,
            rx.el.div(
                rx.el.div(
                    rx.icon("loader-circle", size=16),
                    rx.el.span(" Running...", style={"marginLeft": "6px", "color": "#2185d0"}),
                    style={"marginBottom": "8px", "display": "flex", "alignItems": "center"},
                ),
                rx.el.pre(
                    UploadState.console_output,
                    style={
                        "backgroundColor": "#1e1e1e",
                        "color": "#d4d4d4",
                        "padding": "12px",
                        "borderRadius": "6px",
                        "fontSize": "0.75rem",
                        "fontFamily": "monospace",
                        "maxHeight": "200px",
                        "overflowY": "auto",
                        "margin": "0",
                    },
                ),
            ),
            rx.el.div(
                rx.el.div("No active process", style={"color": "#888", "fontSize": "0.85rem"}),
                style={"padding": "10px 0"},
            ),
        ),
        
        rx.el.div(class_name="ui divider", style={"margin": "16px 0"}),
        
        # External links
        rx.el.div(
            rx.el.a(
                rx.icon("external-link", size=14),
                " Open Dagster UI",
                href="http://localhost:3005",
                target="_blank",
                class_name="ui button",
                style={"display": "inline-flex", "alignItems": "center", "gap": "6px"},
            ),
        ),
    )


# ============================================================================
# POLLING INTERVAL FOR REAL-TIME UPDATES
# ============================================================================

def polling_interval() -> rx.Component:
    """Hidden interval component for polling run status."""
    return rx.cond(
        UploadState.running,
        rx.moment(
            interval=3000,
            on_change=UploadState.poll_run_status,
        ),
        rx.box(),
    )


# ============================================================================
# MAIN PAGE
# ============================================================================

@rx.page(route="/annotate", on_load=UploadState.on_load)
def annotate_page() -> rx.Component:
    """Annotation page with three-column layout."""
    return template(
        # Page header
        rx.el.div(
            rx.el.h2(
                rx.icon("dna", size=32, color="#2185d0"),
                " Genomic Annotation",
                style={"display": "flex", "alignItems": "center", "gap": "10px", "margin": "0"},
            ),
            rx.el.div(
                "Analyze your VCF files with specialized annotation modules",
                style={"color": "#666", "marginTop": "6px"},
            ),
            style={"marginBottom": "20px"},
        ),
        
        # Three-column layout
        three_column_layout(
            left=file_column_content(),
            center=module_column_content(),
            right=results_column_content(),
        ),
        
        # Polling component (hidden)
        polling_interval(),
    )
