"""
Genomic Annotation Page - Two-panel layout with run-centric workflow.

Left Panel: File Management (upload and selection)
Right Panel (Run-Centric View):
  - Last Run Summary: Shows most recent run with status, modules, and quick actions
  - Run Timeline: Expandable list of past runs with details
  - New Analysis Section: Collapsible module selection and run button
  - Outputs Modal: View and download output files
"""
from __future__ import annotations

import reflex as rx

from webui.components.layout import template, two_column_layout, fomantic_icon
from webui.state import UploadState, AuthState


# ============================================================================
# COLUMN 1: FILE MANAGEMENT
# ============================================================================

def upload_zone() -> rx.Component:
    """Minimal upload zone - single line."""
    return rx.upload(
        rx.el.div(
            fomantic_icon("cloud-upload", size=16, color="#2185d0"),
            rx.el.span("Drop VCF files here", style={"fontWeight": "500", "fontSize": "0.85rem", "marginLeft": "6px"}),
            rx.el.span(" or click", style={"fontSize": "0.8rem", "color": "#888"}),
            style={"display": "flex", "alignItems": "center", "justifyContent": "center", "padding": "8px"},
        ),
        id="vcf_upload",
        style={
            "border": "1px dashed #ccc",
            "borderRadius": "4px",
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


def file_metadata_section() -> rx.Component:
    """Display metadata for the currently selected file with editable fields."""
    info = UploadState.selected_file_info
    
    def metadata_row(label: str, value: rx.Var[str], icon: str) -> rx.Component:
        """Single metadata row with icon, label, and value (read-only)."""
        return rx.el.div(
            rx.el.div(
                fomantic_icon(icon, size=14, color="#888"),
                rx.el.span(label, style={"color": "#666", "fontSize": "0.8rem", "marginLeft": "6px"}),
                style={"display": "flex", "alignItems": "center", "minWidth": "80px"},
            ),
            rx.el.span(value, style={"fontSize": "0.85rem", "fontWeight": "500"}),
            style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "padding": "3px 0"},
        )
    
    def dropdown_row(label: str, icon: str, options: rx.Var[list], value: rx.Var[str], on_change: rx.EventHandler) -> rx.Component:
        """Dropdown row for editable metadata fields."""
        return rx.el.div(
            rx.el.div(
                fomantic_icon(icon, size=14, color="#888"),
                rx.el.span(label, style={"color": "#666", "fontSize": "0.8rem", "marginLeft": "6px"}),
                style={"display": "flex", "alignItems": "center", "minWidth": "80px"},
            ),
            rx.el.select(
                rx.foreach(
                    options,
                    lambda opt: rx.el.option(opt, value=opt),
                ),
                value=value,
                on_change=on_change,
                style={
                    "fontSize": "0.8rem",
                    "padding": "2px 6px",
                    "borderRadius": "4px",
                    "border": "1px solid #ddd",
                    "backgroundColor": "#fff",
                    "cursor": "pointer",
                    "minWidth": "100px",
                },
            ),
            style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "padding": "3px 0"},
        )
    
    def input_row(label: str, icon: str, value: rx.Var[str], on_change: rx.EventHandler, placeholder: str = "") -> rx.Component:
        """Text input row for user-editable metadata."""
        return rx.el.div(
            rx.el.div(
                fomantic_icon(icon, size=14, color="#888"),
                rx.el.span(label, style={"color": "#666", "fontSize": "0.8rem", "marginLeft": "6px"}),
                style={"display": "flex", "alignItems": "center", "minWidth": "80px"},
            ),
            rx.el.input(
                value=value,
                on_change=on_change,
                placeholder=placeholder,
                style={
                    "fontSize": "0.8rem",
                    "padding": "4px 8px",
                    "borderRadius": "4px",
                    "border": "1px solid #ddd",
                    "backgroundColor": "#fff",
                    "flex": "1",
                    "minWidth": "120px",
                },
            ),
            style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "padding": "3px 0", "gap": "8px"},
        )
    
    return rx.cond(
        UploadState.has_file_metadata,
        rx.el.div(
            # Header
            rx.el.div(
                fomantic_icon("edit", size=14, color="#2185d0"),
                rx.el.span(" Sample Info", style={"fontSize": "0.9rem", "fontWeight": "600", "marginLeft": "4px"}),
                style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
            ),
            rx.el.div(
                # Auto-detected fields (read-only)
                metadata_row("File", info["sample_name"].to(str), "file-text"),
                metadata_row("Size", rx.Var.create("") + info["size_mb"].to(str) + " MB", "hard-drive"),
                # Editable dropdowns
                dropdown_row(
                    "Species",
                    "paw-print",
                    UploadState.species_options,
                    UploadState.current_species,
                    UploadState.update_file_species,
                ),
                dropdown_row(
                    "Reference",
                    "dna",
                    UploadState.available_reference_genomes,
                    UploadState.current_reference_genome,
                    UploadState.update_file_reference_genome,
                ),
                # User-editable text fields
                input_row(
                    "Subject ID",
                    "user",
                    UploadState.current_subject_id,
                    UploadState.update_file_subject_id,
                    "e.g. Patient-001",
                ),
                input_row(
                    "Study",
                    "folder",
                    UploadState.current_study_name,
                    UploadState.update_file_study_name,
                    "e.g. Longevity Study 2026",
                ),
                # Notes field (multiline)
                rx.el.div(
                    rx.el.div(
                        fomantic_icon("clipboard", size=14, color="#888"),
                        rx.el.span("Notes", style={"color": "#666", "fontSize": "0.8rem", "marginLeft": "6px"}),
                        style={"display": "flex", "alignItems": "center", "marginBottom": "4px"},
                    ),
                    rx.el.textarea(
                        value=UploadState.current_notes,
                        on_change=UploadState.update_file_notes,
                        placeholder="Add notes about this sample...",
                        style={
                            "fontSize": "0.8rem",
                            "padding": "6px 8px",
                            "borderRadius": "4px",
                            "border": "1px solid #ddd",
                            "backgroundColor": "#fff",
                            "width": "100%",
                            "minHeight": "50px",
                            "resize": "vertical",
                        },
                    ),
                    style={"padding": "3px 0"},
                ),
                # Custom fields section
                rx.el.div(
                    rx.el.div(
                        fomantic_icon("tags", size=14, color="#888"),
                        rx.el.span("Custom Fields", style={"color": "#666", "fontSize": "0.8rem", "marginLeft": "6px"}),
                        style={"display": "flex", "alignItems": "center", "marginBottom": "4px"},
                    ),
                    # Existing custom fields
                    rx.cond(
                        UploadState.has_custom_fields,
                        rx.el.div(
                            rx.foreach(
                                UploadState.custom_fields_list,
                                lambda field: rx.el.div(
                                    rx.el.span(
                                        field["name"].to(str),
                                        style={"fontWeight": "500", "color": "#444", "fontSize": "0.8rem", "minWidth": "80px"},
                                    ),
                                    rx.el.span(
                                        field["value"].to(str),
                                        style={"fontSize": "0.8rem", "color": "#666", "flex": "1"},
                                    ),
                                    rx.el.button(
                                        fomantic_icon("x", size=12),
                                        on_click=lambda f=field: UploadState.remove_custom_field(f["name"].to(str)),
                                        class_name="ui mini icon button",
                                        title="Remove field",
                                        style={"padding": "2px 4px", "marginLeft": "4px"},
                                    ),
                                    style={"display": "flex", "alignItems": "center", "gap": "8px", "padding": "2px 0"},
                                ),
                            ),
                            style={"marginBottom": "8px"},
                        ),
                        rx.box(),
                    ),
                    # Add new custom field
                    rx.el.div(
                        rx.el.input(
                            value=UploadState.new_custom_field_name,
                            on_change=UploadState.set_new_field_name,
                            placeholder="Field name",
                            style={
                                "fontSize": "0.75rem",
                                "padding": "3px 6px",
                                "borderRadius": "4px",
                                "border": "1px solid #ddd",
                                "width": "80px",
                            },
                        ),
                        rx.el.input(
                            value=UploadState.new_custom_field_value,
                            on_change=UploadState.set_new_field_value,
                            placeholder="Value",
                            style={
                                "fontSize": "0.75rem",
                                "padding": "3px 6px",
                                "borderRadius": "4px",
                                "border": "1px solid #ddd",
                                "flex": "1",
                            },
                        ),
                        rx.el.button(
                            fomantic_icon("plus", size=12),
                            on_click=UploadState.save_new_custom_field,
                            class_name="ui mini icon positive button",
                            title="Add field",
                            style={"padding": "4px 6px"},
                        ),
                        style={"display": "flex", "gap": "4px", "alignItems": "center"},
                    ),
                    style={"padding": "6px 0", "marginTop": "4px", "borderTop": "1px dashed #ddd"},
                ),
                style={
                    "backgroundColor": "#f8f9fa",
                    "borderRadius": "6px",
                    "padding": "10px 12px",
                    "border": "1px solid #e9ecef",
                },
            ),
            style={"marginBottom": "16px"},
            id="file-metadata-section",
        ),
        rx.fragment(),
    )


def file_item(filename: rx.Var[str]) -> rx.Component:
    """Compact file item for the library list."""
    is_selected = UploadState.selected_file == filename
    return rx.el.div(
        # File icon (small)
        fomantic_icon(
            "file-text", 
            size=16, 
            color=rx.cond(is_selected, "#fff", "#666"),
            style={"marginRight": "8px"},
        ),
        # Filename
        rx.el.span(
            filename,
            style={"fontSize": "0.85rem", "flex": "1", "overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap"},
        ),
        # Status label
        file_status_label(UploadState.file_statuses[filename]),
        # Delete button
        rx.el.button(
            fomantic_icon("trash-2", size=12),
            on_click=lambda: UploadState.delete_file(filename),
            class_name=rx.cond(is_selected, "ui mini icon inverted button", "ui mini icon button"),
            title="Delete",
            style={"padding": "4px 6px", "marginLeft": "4px"},
        ),
        id=rx.Var.create("file-item-") + filename.to(str),
        on_click=lambda: UploadState.select_file(filename),
        style={
            "display": "flex",
            "alignItems": "center",
            "cursor": "pointer",
            "padding": "6px 10px",
            "marginBottom": "4px",
            "backgroundColor": rx.cond(is_selected, "#2185d0", "#fff"),
            "color": rx.cond(is_selected, "#fff", "inherit"),
            "border": rx.cond(is_selected, "1px solid #1678c2", "1px solid #e0e0e0"),
            "borderRadius": "4px",
            "transition": "all 0.15s ease",
        },
    )


def file_column_content() -> rx.Component:
    """Column 1 content: File upload and selection."""
    return rx.el.div(
        # Header with icon
        rx.el.div(
            fomantic_icon("files", size=18, color="#2185d0"),
            rx.el.span(" Files", style={"fontSize": "1rem", "fontWeight": "600", "marginLeft": "6px"}),
            style={"display": "flex", "alignItems": "center", "marginBottom": "10px"},
        ),
        
        # File metadata section (shown when file is selected)
        file_metadata_section(),
        
        # Instruction message when no file is selected (compact)
        rx.cond(
            ~UploadState.has_selected_file,
            rx.el.div(
                fomantic_icon("info", size=14, color="#2185d0", style={"marginRight": "6px"}),
                rx.el.span("Upload or select a VCF file to begin", style={"fontSize": "0.85rem"}),
                style={"display": "flex", "alignItems": "center", "padding": "8px 10px", "backgroundColor": "#e8f4fd", "borderRadius": "4px", "marginBottom": "10px"},
            ),
            rx.fragment(),
        ),
        
        # Upload Section (no divider above)
        upload_zone(),
        
        # Selected files preview + Upload button on same row
        rx.el.div(
            rx.el.div(
                rx.foreach(
                    rx.selected_files("vcf_upload"),
                    lambda f: rx.el.span(f, class_name="ui mini blue label", style={"margin": "1px"}),
                ),
                style={"flex": "1", "display": "flex", "flexWrap": "wrap", "alignItems": "center"},
            ),
            rx.el.button(
                rx.el.i("", class_name="upload icon"),
                " Upload",
                on_click=UploadState.handle_upload(rx.upload_files(upload_id="vcf_upload")),
                loading=UploadState.uploading,
                disabled=rx.selected_files("vcf_upload").length() == 0,
                class_name="ui positive small button",
                id="upload-button",
            ),
            style={"display": "flex", "alignItems": "center", "gap": "8px", "marginTop": "6px"},
        ),
        
        rx.el.div(class_name="ui divider", style={"margin": "8px 0"}),
        
        # Library header with refresh (compact)
        rx.el.div(
            rx.el.span("Library", style={"fontSize": "0.9rem", "fontWeight": "600", "color": "#555"}),
            rx.el.button(
                fomantic_icon("refresh-cw", size=12),
                on_click=UploadState.on_load,
                class_name="ui mini icon button",
                id="refresh-files-button",
                title="Refresh",
            ),
            style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "6px"},
        ),
        
        # File list (scrollable area)
        rx.cond(
            UploadState.files.length() > 0,
            rx.el.div(
                rx.foreach(UploadState.files, file_item),
                id="file-list",
            ),
            rx.el.div(
                fomantic_icon("inbox", size=40, color="#ccc"),
                rx.el.div("No files yet", style={"color": "#888", "marginTop": "8px"}),
                style={"textAlign": "center", "padding": "30px 10px"},
                id="empty-file-list",
            ),
        ),
        id="file-column-content",
    )


# ============================================================================
# MODULE SELECTION COMPONENTS
# ============================================================================

def module_icon(name: rx.Var[str]) -> rx.Component:
    """
    Return the appropriate icon for a module.
    Icons must be static strings - use rx.match for dynamic selection.
    """
    return rx.match(
        name,
        ("coronary", fomantic_icon("heart", size=24, color="#fff")),
        ("lipidmetabolism", fomantic_icon("droplets", size=24, color="#fff")),
        ("longevitymap", fomantic_icon("heart-pulse", size=24, color="#fff")),
        ("superhuman", fomantic_icon("zap", size=24, color="#fff")),
        ("vo2max", fomantic_icon("activity", size=24, color="#fff")),
        ("drugs", fomantic_icon("pill", size=24, color="#fff")),
        fomantic_icon("database", size=24, color="#fff"),  # default
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


# ============================================================================
# RUN-CENTRIC UI COMPONENTS
# ============================================================================

def run_status_badge(status: rx.Var[str]) -> rx.Component:
    """Return a colored badge based on run status."""
    return rx.match(
        status,
        ("SUCCESS", rx.el.span("SUCCESS", class_name="ui green label")),
        ("FAILURE", rx.el.span("FAILURE", class_name="ui red label")),
        ("RUNNING", rx.el.span("RUNNING", class_name="ui blue label")),
        ("QUEUED", rx.el.span("QUEUED", class_name="ui grey label")),
        ("CANCELED", rx.el.span("CANCELED", class_name="ui orange label")),
        rx.el.span(status, class_name="ui grey label"),
    )


def file_type_icon(file_type: rx.Var[str]) -> rx.Component:
    """Return an icon for file type."""
    return rx.match(
        file_type,
        ("weights", fomantic_icon("scale", size=18, color="#2185d0")),
        ("annotations", fomantic_icon("file-text", size=18, color="#21ba45")),
        ("studies", fomantic_icon("book-open", size=18, color="#f2711c")),
        fomantic_icon("file", size=18, color="#767676"),
    )


def file_type_label(file_type: rx.Var[str]) -> rx.Component:
    """Return a colored label for file type."""
    return rx.match(
        file_type,
        ("weights", rx.el.span("weights", class_name="ui mini blue label")),
        ("annotations", rx.el.span("annotations", class_name="ui mini green label")),
        ("studies", rx.el.span("studies", class_name="ui mini orange label")),
        rx.el.span(file_type, class_name="ui mini grey label"),
    )


def _collapsible_header(
    expanded: rx.Var[bool],
    icon_name: str,
    title: str,
    right_badge: rx.Component,
    on_toggle: rx.EventSpec,
) -> rx.Component:
    """
    Reusable foldable section header matching New Analysis style.
    Chevron + icon + title on left; optional badge on right.
    """
    return rx.el.div(
        rx.el.div(
            rx.cond(
                expanded,
                fomantic_icon("chevron-down", size=20, color="#2185d0"),
                fomantic_icon("chevron-right", size=20, color="#2185d0"),
            ),
            fomantic_icon(icon_name, size=20, color="#2185d0", style={"marginLeft": "6px"}),
            rx.el.span(title, style={"fontSize": "1.1rem", "fontWeight": "600", "marginLeft": "8px"}),
            style={"display": "flex", "alignItems": "center"},
        ),
        right_badge,
        on_click=on_toggle,
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "cursor": "pointer",
            "padding": "12px",
            "backgroundColor": "#f9fafb",
            "borderRadius": "6px",
            "marginBottom": rx.cond(expanded, "16px", "0"),
        },
    )


def output_file_card(file_info: rx.Var[dict]) -> rx.Component:
    """Compact card for a single output file with download button."""
    # Use the backend API URL (port 8000) for downloads since frontend is on port 3000
    download_url = UploadState.backend_api_url + "/api/download/" + UploadState.safe_user_id + "/" + file_info["sample_name"].to(str) + "/" + file_info["name"].to(str)
    
    return rx.el.div(
        rx.el.div(
            # File type icon
            file_type_icon(file_info["type"]),
            # File info
            rx.el.div(
                rx.el.strong(file_info["name"].to(str), style={"fontSize": "0.85rem"}),
                rx.el.div(
                    file_type_label(file_info["type"]),
                    rx.el.span(
                        file_info["module"].to(str),
                        class_name="ui mini label",
                        style={"marginLeft": "4px"},
                    ),
                    rx.el.span(
                        file_info["size_mb"].to(str),
                        " MB",
                        style={"color": "#888", "fontSize": "0.75rem", "marginLeft": "8px"},
                    ),
                    style={"display": "flex", "alignItems": "center", "gap": "4px", "marginTop": "2px"},
                ),
                style={"flex": "1", "marginLeft": "10px"},
            ),
            # Download button
            rx.el.a(
                fomantic_icon("download", size=14),
                href=download_url,
                download=file_info["name"].to(str),
                class_name="ui mini icon primary button",
                style={"marginLeft": "auto"},
            ),
            style={"display": "flex", "alignItems": "center", "width": "100%"},
        ),
        style={
            "padding": "8px 10px",
            "borderBottom": "1px solid #eee",
        },
    )


def outputs_section() -> rx.Component:
    """
    Collapsible section showing output files for the selected sample.
    Positioned at the top of the right panel for easy access.
    """
    return rx.el.div(
        # Foldable header
        _collapsible_header(
            expanded=UploadState.outputs_expanded,
            icon_name="folder-output",
            title="Outputs",
            right_badge=rx.el.span(
                UploadState.output_file_count,
                " files",
                class_name="ui mini teal label",
            ),
            on_toggle=UploadState.toggle_outputs,
        ),
        
        # Expanded content
        rx.cond(
            UploadState.outputs_expanded,
            rx.cond(
                UploadState.has_output_files,
                # File list
                rx.el.div(
                    rx.foreach(UploadState.output_files, output_file_card),
                    style={
                        "maxHeight": "280px",
                        "overflowY": "auto",
                        "border": "1px solid #e0e0e0",
                        "borderRadius": "6px",
                        "backgroundColor": "#fff",
                    },
                ),
                # Empty state - prompt to analyze
                rx.el.div(
                    fomantic_icon("inbox", size=36, color="#ccc"),
                    rx.el.div(
                        "No outputs yet",
                        style={"color": "#888", "marginTop": "10px", "fontSize": "1rem", "fontWeight": "500"},
                    ),
                    rx.el.div(
                        "Run an analysis to generate output files",
                        style={"color": "#aaa", "marginTop": "4px", "fontSize": "0.85rem"},
                    ),
                    style={"textAlign": "center", "padding": "24px 16px"},
                ),
            ),
            rx.box(),
        ),
        
        style={"padding": "0", "overflow": "hidden"},
        id="outputs-section",
    )


def run_timeline_card(run: rx.Var[dict]) -> rx.Component:
    """
    Card for a run in the timeline.
    
    Shows status, date, module count. Expands on click to show details.
    The first run (latest) shows additional action buttons and is highlighted.
    """
    run_id = run["run_id"].to(str)
    is_expanded = UploadState.expanded_run_id == run_id
    is_latest = UploadState.latest_run_id == run_id
    dagster_url = UploadState.dagster_web_url + "/runs/" + run_id
    
    return rx.el.div(
        # Main row (always visible)
        rx.el.div(
            # Status badge
            run_status_badge(run["status"].to(str)),
            # Latest badge for first run
            rx.cond(
                is_latest,
                rx.el.span("latest", class_name="ui mini teal label", style={"marginLeft": "6px"}),
                rx.box(),
            ),
            # Timestamp
            rx.el.span(
                run["started_at"].to(str),
                style={"marginLeft": "12px", "color": "#666", "fontSize": "0.85rem", "flex": "1"},
            ),
            # Module count
            rx.el.span(
                run["modules"].to(list).length(),
                " modules",
                class_name="ui mini label",
                style={"marginRight": "8px"},
            ),
            # Expand/collapse button
            rx.el.button(
                rx.cond(
                    is_expanded,
                    fomantic_icon("chevron-up", size=16),
                    fomantic_icon("chevron-down", size=16),
                ),
                on_click=lambda: UploadState.toggle_run_expansion(run_id),
                class_name="ui mini icon button",
                style={"padding": "6px"},
            ),
            style={"display": "flex", "alignItems": "center", "cursor": "pointer"},
            on_click=lambda: UploadState.toggle_run_expansion(run_id),
        ),
        
        # Expanded details (conditionally shown)
        rx.cond(
            is_expanded,
            rx.el.div(
                # Modules list
                rx.el.div(
                    rx.el.span("Modules: ", style={"color": "#666", "fontSize": "0.85rem"}),
                    rx.foreach(
                        run["modules"].to(list),
                        lambda m: rx.el.span(m.to(str), class_name="ui mini label", style={"marginRight": "3px"}),
                    ),
                    style={"marginBottom": "10px"},
                ),
                # Action buttons (only for latest run)
                rx.cond(
                    is_latest,
                    rx.el.div(
                        rx.el.button(
                            fomantic_icon("refresh-cw", size=14),
                            " Re-run",
                            on_click=UploadState.rerun_with_same_modules,
                            disabled=UploadState.running,
                            class_name="ui mini primary button",
                            style={"display": "inline-flex", "alignItems": "center", "gap": "4px"},
                        ),
                        rx.el.button(
                            fomantic_icon("sliders-horizontal", size=14),
                            " Modify",
                            on_click=UploadState.modify_and_run,
                            class_name="ui mini button",
                            style={"display": "inline-flex", "alignItems": "center", "gap": "4px", "marginLeft": "6px"},
                        ),
                        style={"marginBottom": "10px"},
                    ),
                    rx.box(),
                ),
                # Run ID
                rx.el.div(
                    rx.el.span("Run ID: ", style={"color": "#666", "fontSize": "0.85rem"}),
                    rx.el.code(run_id, style={"fontSize": "0.75rem"}),
                    style={"marginBottom": "10px"},
                ),
                # Dagster link
                rx.el.a(
                    fomantic_icon("external-link", size=12),
                    " Open in Dagster",
                    href=dagster_url,
                    target="_blank",
                    class_name="ui mini button",
                    style={"display": "inline-flex", "alignItems": "center", "gap": "4px"},
                ),
                style={"marginTop": "12px", "paddingTop": "12px", "borderTop": "1px solid #eee"},
            ),
            rx.box(),
        ),
        
        class_name=rx.cond(is_latest, "ui blue segment", "ui segment"),
        style={"margin": "0 0 8px 0", "padding": "10px 12px"},
        id=rx.Var.create("timeline-run-") + run_id,
    )


def run_timeline() -> rx.Component:
    """
    Collapsible scrollable list of all runs for the selected file.
    The most recent run is highlighted and has action buttons.
    """
    run_count_badge = rx.el.span(
        UploadState.filtered_runs.length(),
        " runs",
        class_name="ui mini blue label",
    )
    return rx.el.div(
        # Foldable header
        _collapsible_header(
            expanded=UploadState.run_history_expanded,
            icon_name="history",
            title="Run History",
            right_badge=run_count_badge,
            on_toggle=UploadState.toggle_run_history,
        ),
        
        # Expanded content
        rx.cond(
            UploadState.run_history_expanded,
            rx.cond(
                UploadState.has_filtered_runs,
                rx.el.div(
                    rx.foreach(
                        UploadState.filtered_runs,
                        run_timeline_card,
                    ),
                    style={"maxHeight": "300px", "overflowY": "auto"},
                    id="run-timeline-list",
                ),
                rx.el.div(
                    fomantic_icon("inbox", size=32, color="#ccc"),
                    rx.el.div(
                        "No runs yet",
                        style={"color": "#888", "marginTop": "8px", "fontSize": "0.95rem"},
                    ),
                    rx.el.div(
                        "Start an analysis to see run history",
                        style={"color": "#aaa", "marginTop": "4px", "fontSize": "0.85rem"},
                    ),
                    style={"textAlign": "center", "padding": "20px 16px"},
                ),
            ),
            rx.box(),
        ),
        id="run-timeline-section",
        style={"padding": "0", "overflow": "hidden"},
    )


def new_analysis_section() -> rx.Component:
    """
    Collapsible section for starting a new analysis.
    
    Contains module selection grid and start button.
    Uses shared _collapsible_header for uniform design.
    """
    return rx.el.div(
        # Foldable header (same style as Last Run and Run History)
        _collapsible_header(
            expanded=UploadState.new_analysis_expanded,
            icon_name="plus-circle",
            title="New Analysis",
            right_badge=rx.el.span(
                UploadState.selected_modules.length(),
                " modules selected",
                class_name="ui mini blue label",
            ),
            on_toggle=UploadState.toggle_new_analysis,
        ),
        
        # Expanded content
        rx.cond(
            UploadState.new_analysis_expanded,
            rx.el.div(
                # Selection controls
                rx.el.div(
                    rx.el.button(
                        "Select All",
                        on_click=UploadState.select_all_modules,
                        class_name="ui mini button",
                    ),
                    rx.el.button(
                        "Select None",
                        on_click=UploadState.deselect_all_modules,
                        class_name="ui mini button",
                        style={"marginLeft": "6px"},
                    ),
                    style={"marginBottom": "16px"},
                ),
                
                # Module cards grid – scroll after ~2 rows
                rx.el.div(
                    rx.foreach(UploadState.module_metadata_list, module_card),
                    style={
                        "display": "grid",
                        "gridTemplateColumns": "repeat(auto-fill, minmax(280px, 1fr))",
                        "gap": "10px",
                        "marginBottom": "16px",
                        "maxHeight": "320px",
                        "overflowY": "auto",
                    },
                    id="module-cards-grid",
                ),
                
                # Start button
                rx.el.button(
                    UploadState.analysis_button_text,
                    rx.el.i(
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
                    style={"maxWidth": "400px"},
                ),
            ),
            rx.box(),
        ),
        
        style={"padding": "0", "overflow": "hidden"},
        id="new-analysis-section",
    )


def no_file_selected_message() -> rx.Component:
    """Message shown when no file is selected."""
    return rx.el.div(
        fomantic_icon("file-text", size=48, color="#ccc"),
        rx.el.div(
            "Select a file to view run history",
            style={"color": "#888", "marginTop": "16px", "fontSize": "1rem"},
        ),
        rx.el.div(
            "Choose a VCF file from the Files panel to see previous runs and start new analyses",
            style={"color": "#aaa", "marginTop": "8px", "fontSize": "0.9rem", "maxWidth": "300px"},
        ),
        style={"textAlign": "center", "padding": "60px 20px"},
        id="no-file-selected-message",
    )




def right_panel_run_view() -> rx.Component:
    """
    Run-centric right panel with three sections:
    1. Outputs (top) - results the user wants to see first
    2. Run History (middle) - unified timeline of all runs
    3. New Analysis (bottom) - start new work
    """
    return rx.el.div(
        # Header – inverted bar (dark bg, light text) for emphasis
        rx.el.div(
            fomantic_icon("file-text", size=22, color="#fff"),
            rx.cond(
                UploadState.has_selected_file,
                rx.el.span(
                    " Results for ",
                    rx.el.strong(UploadState.selected_file, style={"fontWeight": "600"}),
                    style={"fontSize": "1.1rem", "marginLeft": "8px", "color": "#fff"},
                ),
                rx.el.span(
                    " Select a file to view results and start analysis",
                    style={"fontSize": "1.1rem", "marginLeft": "8px", "color": "rgba(255,255,255,0.9)"},
                ),
            ),
            style={
                "display": "flex",
                "alignItems": "center",
                "padding": "14px 16px",
                "marginBottom": "16px",
                "backgroundColor": "#2185d0",
                "color": "#fff",
                "borderRadius": "6px",
            },
            id="right-column-header",
        ),
        # Content: three sections or empty state
        rx.cond(
            UploadState.has_selected_file,
            rx.fragment(
                # Section 1: Outputs (top) - teal segment
                rx.el.div(
                    outputs_section(),
                    class_name="ui teal segment",
                    style={"padding": "16px", "marginBottom": "16px"},
                    id="segment-outputs",
                ),
                # Section 2: Run History (middle) - green segment
                rx.el.div(
                    run_timeline(),
                    class_name="ui green segment",
                    style={"padding": "16px", "marginBottom": "16px"},
                    id="segment-run-history",
                ),
                # Section 3: New Analysis (bottom) - blue segment
                rx.el.div(
                    new_analysis_section(),
                    class_name="ui blue segment",
                    style={"padding": "16px"},
                    id="segment-new-analysis",
                ),
            ),
            no_file_selected_message(),
        ),
        id="right-panel-run-view",
        style={"padding": "0"},
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
    """Annotation page with two-panel run-centric layout."""
    return template(
        # Two-column layout with run-centric right panel
        two_column_layout(
            left=file_column_content(),
            right=right_panel_run_view(),
        ),
        
        # Polling component (hidden)
        polling_interval(),
    )
