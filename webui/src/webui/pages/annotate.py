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
    is_selected = UploadState.selected_file == filename
    return rx.el.div(
        rx.el.div(
            # File icon
            rx.el.div(
                rx.icon(
                    "file-text", 
                    size=22, 
                    color=rx.cond(is_selected, "#fff", "#5a5a5a")
                ),
                style={
                    "width": "44px",
                    "height": "44px",
                    "backgroundColor": rx.cond(is_selected, "rgba(255,255,255,0.2)", "#f0f0f0"),
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
                    rx.el.span(
                        "VCF", 
                        class_name=rx.cond(is_selected, "ui mini label", "ui mini grey label"), 
                        style={"marginLeft": "4px"}
                    ),
                    style={"display": "flex", "gap": "4px"},
                ),
                style={"flex": "1", "color": "inherit"},
            ),
            # Action buttons
            rx.el.div(
                rx.el.button(
                    rx.icon("trash-2", size=14),
                    on_click=lambda: UploadState.delete_file(filename),
                    class_name=rx.cond(is_selected, "ui mini icon inverted button", "ui mini icon button"),
                    title="Delete",
                ),
                style={"marginLeft": "auto"},
            ),
            style={"display": "flex", "alignItems": "center", "width": "100%"},
        ),
        id=rx.Var.create("file-item-") + filename.to(str),
        on_click=lambda: UploadState.select_file(filename),
        class_name=rx.cond(
            is_selected,
            "ui blue inverted segment",
            "ui segment",
        ),
        style={
            "cursor": "pointer",
            "margin": "0 0 8px 0",
            "padding": "12px",
            "backgroundColor": rx.cond(is_selected, "#2185d0", "#ffffff"),
            "color": rx.cond(is_selected, "#ffffff", "inherit"),
            "border": rx.cond(
                is_selected,
                "2px solid #0d71bb",
                "1px solid #e0e0e0",
            ),
            "borderRadius": "6px",
            "transition": "all 0.2s ease",
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
        
        # Instruction message when no file is selected
        rx.cond(
            ~UploadState.has_selected_file,
            rx.el.div(
                rx.el.div(
                    rx.el.div("Please upload or select vcf file", class_name="header"),
                    rx.el.p("Choose a file from the library below or upload a new one to begin analysis."),
                    class_name="content",
                ),
                class_name="ui info message",
                style={"marginBottom": "16px"},
            ),
            rx.fragment(),
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
            rx.el.i("", class_name="upload icon"),
            " Upload Files",
            on_click=UploadState.handle_upload(rx.upload_files(upload_id="vcf_upload")),
            loading=UploadState.uploading,
            disabled=rx.selected_files("vcf_upload").length() == 0,
            class_name="ui positive inverted big labeled icon button fluid",
            id="upload-button",
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
                id="refresh-files-button",
            ),
            style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "12px"},
        ),
        
        # File list (scrollable area)
        rx.cond(
            UploadState.files.length() > 0,
            rx.el.div(
                rx.foreach(UploadState.files, file_item),
                id="file-list",
            ),
            rx.el.div(
                rx.icon("inbox", size=40, color="#ccc"),
                rx.el.div("No files yet", style={"color": "#888", "marginTop": "8px"}),
                style={"textAlign": "center", "padding": "30px 10px"},
                id="empty-file-list",
            ),
        ),
        id="file-column-content",
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


def fomantic_checkbox(checked: rx.Var[bool]) -> rx.Component:
    """
    Fomantic UI styled checkbox (display only, parent handles click).
    
    Structure: <div class="ui checkbox"><input type="checkbox"><label></label></div>
    The checkbox state is controlled via class name (checked adds 'checked' class).
    Note: No on_click here - parent card handles the toggle to avoid double-firing.
    """
    return rx.el.div(
        rx.el.input(
            type="checkbox",
            checked=checked,
            read_only=True,  # Controlled by parent click
            style={"pointerEvents": "none"},  # Let clicks pass through to parent
        ),
        rx.el.label(),
        class_name=rx.cond(checked, "ui checked checkbox", "ui checkbox"),
        style={"marginRight": "12px", "pointerEvents": "none"},  # Let clicks pass through
    )


def module_card(module: rx.Var[dict]) -> rx.Component:
    """
    Module card styled like the reference screenshot.
    Shows: Fomantic checkbox, icon, title, description, badges.
    """
    is_selected = module["selected"].to(bool)
    has_file = UploadState.has_selected_file
    
    return rx.el.div(
        rx.el.div(
            # Left: Fomantic UI Checkbox (display only, card handles click)
            fomantic_checkbox(checked=rx.cond(has_file, is_selected, False)),
            # Module icon (colored box with Lucide icon)
            rx.el.div(
                module_icon(module["name"]),
                style={
                    "width": "48px",
                    "height": "48px",
                    "backgroundColor": rx.cond(
                        has_file,
                        rx.cond(is_selected, "#2185d0", "#888"),
                        "#ccc"
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
                # No confusing labels - selection state is shown by checkbox and background color
                style={"flex": "1"},
            ),
            style={
                "display": "flex", 
                "alignItems": "flex-start", 
                "width": "100%",
                "opacity": rx.cond(has_file, "1.0", "0.5"),
            },
        ),
        id=rx.Var.create("module-card-") + module["name"].to(str),
        on_click=rx.cond(has_file, UploadState.toggle_module(module["name"]), UploadState.do_nothing),
        class_name=rx.cond(has_file, "ui segment", "ui disabled segment"),
        style={
            "cursor": rx.cond(has_file, "pointer", "not-allowed"),
            "margin": "0 0 10px 0",
            "padding": "14px",
            "border": "1px solid #e0e0e0",
            "borderRadius": "6px",
            "backgroundColor": rx.cond(
                has_file,
                rx.cond(is_selected, "#f8faff", "#fff"),
                "#fafafa"
            ),
            "transition": "all 0.2s ease",
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
                id="select-all-modules-button",
                disabled=~UploadState.has_selected_file,
            ),
            rx.el.button(
                "None",
                on_click=UploadState.deselect_all_modules,
                class_name="ui mini button",
                id="deselect-all-modules-button",
                style={"marginLeft": "6px"},
                disabled=~UploadState.has_selected_file,
            ),
            style={"marginBottom": "16px", "display": "flex", "gap": "6px"},
        ),
        
        # Module cards (scrollable)
        rx.el.div(
            rx.foreach(UploadState.module_metadata_list, module_card),
            id="module-list",
        ),
        
        # ---- Action Section (visually separated) ----
        rx.el.div(class_name="ui horizontal divider", style={"margin": "20px 0 16px 0"}),
        
        rx.el.div(
            rx.icon("zap", size=18, color="#2185d0"),
            rx.el.span(" Run Analysis", style={"fontSize": "1rem", "fontWeight": "600", "marginLeft": "6px"}),
            style={"display": "flex", "alignItems": "center", "marginBottom": "12px"},
        ),
        
        # Run button - Fomantic UI right labeled icon button
        rx.el.button(
            UploadState.analysis_button_text,
            rx.el.i(
                # Empty string to force element to render
                "",
                class_name=rx.cond(
                    UploadState.running,
                    "spinner loading icon",
                    rx.cond(
                        UploadState.last_run_success,
                        "check circle icon",
                        "play icon",
                    ),
                ),
            ),
            on_click=UploadState.start_annotation_run,
            disabled=~UploadState.can_run_annotation,
            class_name=UploadState.analysis_button_color,
            id="start-analysis-button",
        ),
        
        # Show selected file below button as helper text
        rx.cond(
            ~UploadState.has_selected_file,
            rx.el.div(
                "Select a file from the library to start",
                style={"color": "#888", "fontSize": "0.85rem", "marginTop": "10px", "textAlign": "center"},
                id="no-file-selected-warning",
            ),
            rx.box(),
        ),
        id="module-column-content",
    )


# ============================================================================
# COLUMN 3: RESULTS
# ============================================================================

def run_card(run: rx.Var[dict]) -> rx.Component:
    """Run history card with status badge, timing, and Dagster link."""
    run_id_str = run["run_id"].to(str)
    dagster_url = UploadState.dagster_web_url + "/runs/" + run_id_str
    
    return rx.el.div(
        # Header row: Status + Timestamp
        rx.el.div(
            # Status badge
            rx.el.div(
                run["status"].to(str),
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
                run["started_at"].to(str),
                style={"fontSize": "0.85rem", "color": "#666", "marginLeft": "10px"},
            ),
            style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
        ),
        
        # Run ID with clickable Dagster link
        rx.el.div(
            rx.el.a(
                rx.icon("external-link", size=12),
                rx.el.span(
                    " ",
                    run_id_str,
                    style={"fontFamily": "monospace", "fontSize": "0.75rem"},
                ),
                href=dagster_url,
                target="_blank",
                style={
                    "display": "inline-flex",
                    "alignItems": "center",
                    "color": "#2185d0",
                    "textDecoration": "none",
                    "gap": "4px",
                },
                title="Open in Dagster UI",
            ),
            style={"marginBottom": "8px"},
        ),
        
        # Modules used
        rx.el.div(
            rx.el.span("Modules: ", style={"color": "#888", "fontSize": "0.85rem"}),
            rx.foreach(
                run["modules"].to(list),
                lambda m: rx.el.span(m.to(str), class_name="ui mini label", style={"marginRight": "3px"}),
            ),
            style={"marginBottom": "8px"},
        ),
        
        # Action buttons row
        rx.el.div(
            # Dagster UI button
            rx.el.a(
                rx.icon("external-link", size=14),
                " Dagster",
                href=dagster_url,
                target="_blank",
                class_name="ui mini button",
                style={"display": "inline-flex", "alignItems": "center", "gap": "4px"},
            ),
            # Download button if output available
            rx.cond(
                run["output_path"],
                rx.el.div(
                    rx.icon("download", size=14),
                    " Results",
                    class_name="ui mini primary button",
                    style={"display": "inline-flex", "alignItems": "center", "gap": "4px", "marginLeft": "6px"},
                ),
                rx.box(),
            ),
            style={"display": "flex", "alignItems": "center", "marginTop": "4px"},
        ),
        id=rx.Var.create("run-card-") + run_id_str,
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
                id="refresh-results-button",
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
                    id="run-history-list",
                ),
                rx.el.div(
                    rx.icon("history", size=40, color="#ccc"),
                    rx.el.div("No runs for this file", style={"color": "#888", "marginTop": "8px"}),
                    style={"textAlign": "center", "padding": "30px 10px"},
                    id="empty-run-history",
                    class_name="ui disabled segment",
                ),
            ),
            rx.el.div(
                rx.icon("file-text", size=40, color="#ccc"),
                rx.el.div("Select a file to see history", style={"color": "#888", "marginTop": "8px"}),
                style={"textAlign": "center", "padding": "30px 10px"},
                id="no-file-selected-history",
                class_name="ui disabled segment",
            ),
        ),
        
        rx.el.div(class_name="ui divider", style={"margin": "20px 0 16px 0"}),
        
        # Logs section - scrollable frame
        rx.el.div(
            rx.el.div(
                rx.icon("terminal", size=18, color="#2185d0"),
                rx.el.span(" Logs", style={"fontSize": "1rem", "fontWeight": "600", "marginLeft": "6px"}),
                # Status indicator
                rx.cond(
                    UploadState.running,
                    rx.el.span(
                        rx.icon("loader-circle", size=14),
                        " Running",
                        class_name="ui mini blue label",
                        style={"marginLeft": "auto", "display": "inline-flex", "alignItems": "center", "gap": "4px"},
                    ),
                    rx.cond(
                        UploadState.has_logs,
                        rx.el.span(
                            UploadState.log_count,
                            " entries",
                            class_name="ui mini label",
                            style={"marginLeft": "auto"},
                        ),
                        rx.box(),
                    ),
                ),
                style={"display": "flex", "alignItems": "center", "marginBottom": "10px"},
            ),
            
            # Scrollable log container
            rx.el.div(
                rx.cond(
                    UploadState.has_logs,
                    rx.el.div(
                        rx.foreach(
                            UploadState.run_logs,
                            lambda log_line: rx.el.div(
                                log_line,
                                style={
                                    "padding": "4px 8px",
                                    "borderBottom": "1px solid #333",
                                    "fontSize": "0.8rem",
                                    "fontFamily": "monospace",
                                    "whiteSpace": "pre-wrap",
                                    "wordBreak": "break-word",
                                },
                            ),
                        ),
                        id="log-entries",
                    ),
                    rx.el.div(
                        rx.icon("terminal", size=32, color="#555"),
                        rx.el.div("No logs yet", style={"color": "#888", "marginTop": "8px", "fontSize": "0.85rem"}),
                        rx.el.div("Run an analysis to see logs here", style={"color": "#666", "marginTop": "4px", "fontSize": "0.75rem"}),
                        style={"textAlign": "center", "padding": "30px 10px"},
                    ),
                ),
                style={
                    "backgroundColor": "#1e1e1e",
                    "color": "#d4d4d4",
                    "borderRadius": "6px",
                    "maxHeight": "250px",
                    "minHeight": "100px",
                    "overflowY": "auto",
                    "overflowX": "hidden",
                },
                id="logs-container",
            ),
            id="logs-section",
        ),
        
        rx.el.div(class_name="ui divider", style={"margin": "16px 0"}),
        
        # External links
        rx.el.div(
            rx.el.a(
                rx.icon("external-link", size=14),
                " Open Dagster UI",
                href=UploadState.dagster_web_url,
                target="_blank",
                class_name="ui button",
                id="dagster-ui-link",
                style={"display": "inline-flex", "alignItems": "center", "gap": "6px"},
            ),
        ),
        id="results-column-content",
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
