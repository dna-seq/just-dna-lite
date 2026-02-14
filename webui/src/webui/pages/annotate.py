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
from webui.state import UploadState
from reflex_mui_datagrid import data_grid


# ============================================================================
# COLUMN 1: FILE MANAGEMENT
# ============================================================================

def add_sample_form() -> rx.Component:
    """
    Compact Add Sample form - minimal file picker + metadata fields.
    Single "Add Sample" button submits both file and metadata together.
    """
    return rx.el.div(
        # Form header with inline file picker
        rx.el.div(
            fomantic_icon("plus-circle", size=16, color="#2185d0"),  # primary blue
            rx.el.span(" Add Sample", style={"fontSize": "0.95rem", "fontWeight": "600", "marginLeft": "4px"}),
            # Inline file picker - compact button style
            rx.upload(
                rx.el.div(
                    fomantic_icon("file-text", size=12, color="#666"),
                    rx.cond(
                        rx.selected_files("vcf_upload").length() > 0,
                        rx.foreach(
                            rx.selected_files("vcf_upload"),
                            lambda f: rx.el.span(f, style={"marginLeft": "4px", "color": "#00b5ad", "fontSize": "0.8rem", "maxWidth": "120px", "overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap"}),
                        ),
                        rx.el.span("Select VCF...", style={"marginLeft": "4px", "color": "#888", "fontSize": "0.8rem"}),
                    ),
                    style={"display": "flex", "alignItems": "center"},
                ),
                id="vcf_upload",
                style={
                    "padding": "4px 8px",
                    "border": "1px solid #ccc",
                    "borderRadius": "4px",
                    "backgroundColor": "#fff",
                    "cursor": "pointer",
                    "marginLeft": "auto",
                },
                multiple=False,
                accept={
                    "application/vcf": [".vcf", ".vcf.gz"],
                    "text/vcf": [".vcf", ".vcf.gz"],
                    "application/gzip": [".vcf.gz"],
                },
            ),
            style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
        ),
        
        # Compact form - 2 columns
        rx.el.div(
            # Row 1: Subject ID + Sex
            rx.el.div(
                rx.el.input(
                    value=UploadState.new_sample_subject_id,
                    on_change=UploadState.set_new_sample_subject_id,
                    placeholder="Subject ID",
                    style={"flex": "1", "padding": "5px 8px", "borderRadius": "4px", "border": "1px solid #ddd", "fontSize": "0.8rem"},
                ),
                rx.el.select(
                    rx.foreach(UploadState.sex_options, lambda opt: rx.el.option(opt, value=opt)),
                    value=UploadState.new_sample_sex,
                    on_change=UploadState.set_new_sample_sex,
                    style={"width": "80px", "padding": "5px", "borderRadius": "4px", "border": "1px solid #ddd", "fontSize": "0.8rem", "backgroundColor": "#fff"},
                ),
                style={"display": "flex", "gap": "6px", "marginBottom": "6px"},
            ),
            # Row 2: Species + Reference Genome
            rx.el.div(
                rx.el.select(
                    rx.foreach(UploadState.species_options, lambda opt: rx.el.option(opt, value=opt)),
                    value=UploadState.new_sample_species,
                    on_change=UploadState.set_new_sample_species,
                    style={"flex": "1", "padding": "5px", "borderRadius": "4px", "border": "1px solid #ddd", "fontSize": "0.8rem", "backgroundColor": "#fff"},
                ),
                rx.el.select(
                    rx.foreach(UploadState.new_sample_available_genomes, lambda opt: rx.el.option(opt, value=opt)),
                    value=UploadState.new_sample_reference_genome,
                    on_change=UploadState.set_new_sample_reference_genome,
                    style={"width": "100px", "padding": "5px", "borderRadius": "4px", "border": "1px solid #ddd", "fontSize": "0.8rem", "backgroundColor": "#fff"},
                ),
                style={"display": "flex", "gap": "6px", "marginBottom": "6px"},
            ),
            # Row 3: Tissue + Study Name
            rx.el.div(
                rx.el.select(
                    rx.foreach(UploadState.tissue_options, lambda opt: rx.el.option(opt, value=opt)),
                    value=UploadState.new_sample_tissue,
                    on_change=UploadState.set_new_sample_tissue,
                    style={"flex": "1", "padding": "5px", "borderRadius": "4px", "border": "1px solid #ddd", "fontSize": "0.8rem", "backgroundColor": "#fff"},
                ),
                rx.el.input(
                    value=UploadState.new_sample_study_name,
                    on_change=UploadState.set_new_sample_study_name,
                    placeholder="Study name",
                    style={"flex": "1", "padding": "5px 8px", "borderRadius": "4px", "border": "1px solid #ddd", "fontSize": "0.8rem"},
                ),
                style={"display": "flex", "gap": "6px", "marginBottom": "8px"},
            ),
            # Add button
            rx.el.button(
                rx.cond(
                    UploadState.uploading,
                    rx.el.i("", class_name="spinner loading icon"),
                    rx.el.i("", class_name="plus icon"),
                ),
                " Add",
                on_click=UploadState.handle_upload_with_metadata(rx.upload_files(upload_id="vcf_upload")),
                disabled=rx.selected_files("vcf_upload").length() == 0,
                class_name="ui primary small button",
                style={"width": "100%"},
            ),
        ),
        
        class_name="ui blue segment",
        style={"padding": "10px 12px", "marginBottom": "12px"},
    )


def file_status_label(status: rx.Var[str]) -> rx.Component:
    """Return a colored label based on file status (DNA palette: green/yellow/red/grey)."""
    return rx.match(
        status,
        ("completed", rx.el.span("completed", class_name="ui mini green label")),
        ("running", rx.el.span("running", class_name="ui mini yellow label")),
        ("uploaded", rx.el.span("uploaded", class_name="ui mini label")),
        ("error", rx.el.span("error", class_name="ui mini red label")),
        rx.el.span(status, class_name="ui mini grey label"),
    )


def file_metadata_section() -> rx.Component:
    """
    Display metadata for the currently selected file using Fomantic UI form.
    
    Uses proper form structure with:
    - Required fields marked with asterisk
    - Two-column layout for compact display
    - Grouped related fields
    """
    info = UploadState.selected_file_info
    
    def required_field(label: str) -> rx.Component:
        """Label with required asterisk."""
        return rx.el.label(
            label,
            rx.el.span(" *", style={"color": "#db2828"}),  # Fomantic red
        )
    
    def optional_field(label: str) -> rx.Component:
        """Label for optional field."""
        return rx.el.label(label)
    
    return rx.cond(
        UploadState.has_file_metadata,
        rx.el.div(
            # Form header
            rx.el.div(
                fomantic_icon("file-text", size=18, color="#21ba45"),
                rx.el.span(
                    " Sample: ",
                    rx.el.strong(info["sample_name"].to(str)),
                    style={"fontSize": "1rem", "marginLeft": "6px"},
                ),
                rx.el.span(
                    " (",
                    info["size_mb"].to(str),
                    " MB)",
                    style={"fontSize": "0.85rem", "color": "#888", "marginLeft": "4px"},
                ),
                style={"display": "flex", "alignItems": "center", "marginBottom": "12px"},
            ),
            
            # Fomantic UI Form
            rx.el.form(
                # === REQUIRED FIELDS SECTION ===
                rx.el.h5("Required Fields", class_name="ui dividing header", style={"marginTop": "0"}),
                
                # Row 1: Subject ID and Sex (two fields inline)
                rx.el.div(
                    rx.el.div(
                        required_field("Subject ID"),
                        rx.el.input(
                            type="text",
                            value=UploadState.current_subject_id,
                            on_change=UploadState.update_file_subject_id,
                            placeholder="e.g. Patient-001",
                        ),
                        class_name="required field",
                    ),
                    rx.el.div(
                        required_field("Sex"),
                        rx.el.select(
                            rx.foreach(
                                UploadState.sex_options,
                                lambda opt: rx.el.option(opt, value=opt),
                            ),
                            value=UploadState.current_sex,
                            on_change=UploadState.update_file_sex,
                            class_name="ui dropdown",
                        ),
                        class_name="required field",
                    ),
                    class_name="two fields",
                ),
                
                # Row 2: Species and Reference Genome
                rx.el.div(
                    rx.el.div(
                        required_field("Species"),
                        rx.el.select(
                            rx.foreach(
                                UploadState.species_options,
                                lambda opt: rx.el.option(opt, value=opt),
                            ),
                            value=UploadState.current_species,
                            on_change=UploadState.update_file_species,
                            class_name="ui dropdown",
                        ),
                        class_name="required field",
                    ),
                    rx.el.div(
                        required_field("Reference Genome"),
                        rx.el.select(
                            rx.foreach(
                                UploadState.available_reference_genomes,
                                lambda opt: rx.el.option(opt, value=opt),
                            ),
                            value=UploadState.current_reference_genome,
                            on_change=UploadState.update_file_reference_genome,
                            class_name="ui dropdown",
                        ),
                        class_name="required field",
                    ),
                    class_name="two fields",
                ),
                
                # Row 3: Tissue
                rx.el.div(
                    required_field("Tissue Source"),
                    rx.el.select(
                        rx.foreach(
                            UploadState.tissue_options,
                            lambda opt: rx.el.option(opt, value=opt),
                        ),
                        value=UploadState.current_tissue,
                        on_change=UploadState.update_file_tissue,
                        class_name="ui dropdown",
                    ),
                    class_name="required field",
                ),
                
                # === OPTIONAL FIELDS SECTION ===
                rx.el.h5("Optional Fields", class_name="ui dividing header"),
                
                # Study Name
                rx.el.div(
                    optional_field("Study / Project"),
                    rx.el.input(
                        type="text",
                        value=UploadState.current_study_name,
                        on_change=UploadState.update_file_study_name,
                        placeholder="e.g. Longevity Study 2026",
                    ),
                    class_name="field",
                ),
                
                # Notes
                rx.el.div(
                    optional_field("Notes"),
                    rx.el.textarea(
                        value=UploadState.current_notes,
                        on_change=UploadState.update_file_notes,
                        placeholder="Additional notes about this sample...",
                        rows=2,
                    ),
                    class_name="field",
                ),
                
                # === CUSTOM FIELDS SECTION ===
                rx.el.h5("Custom Fields", class_name="ui dividing header"),
                
                # Existing custom fields
                rx.cond(
                    UploadState.has_custom_fields,
                    rx.el.div(
                        rx.foreach(
                            UploadState.custom_fields_list,
                            lambda field: rx.el.div(
                                rx.el.span(
                                    field["name"].to(str),
                                    class_name="ui label",
                                    style={"marginRight": "8px"},
                                ),
                                rx.el.span(field["value"].to(str), style={"flex": "1"}),
                                rx.el.button(
                                    fomantic_icon("x", size=12),
                                    on_click=lambda f=field: UploadState.remove_custom_field(f["name"].to(str)),
                                    class_name="ui mini icon button",
                                    type="button",
                                    style={"marginLeft": "8px"},
                                ),
                                style={"display": "flex", "alignItems": "center", "marginBottom": "6px"},
                            ),
                        ),
                        style={"marginBottom": "10px"},
                    ),
                    rx.box(),
                ),
                
                # Add new custom field
                rx.el.div(
                    rx.el.div(
                        rx.el.input(
                            type="text",
                            value=UploadState.new_custom_field_name,
                            on_change=UploadState.set_new_field_name,
                            placeholder="Field name",
                        ),
                        class_name="field",
                        style={"flex": "1"},
                    ),
                    rx.el.div(
                        rx.el.input(
                            type="text",
                            value=UploadState.new_custom_field_value,
                            on_change=UploadState.set_new_field_value,
                            placeholder="Value",
                        ),
                        class_name="field",
                        style={"flex": "2"},
                    ),
                    rx.el.button(
                        fomantic_icon("plus", size=14),
                        " Add",
                        on_click=UploadState.save_new_custom_field,
                        class_name="ui mini positive button",
                        type="button",
                    ),
                    class_name="inline fields",
                    style={"alignItems": "flex-end"},
                ),
                
                rx.el.div(class_name="ui divider"),
                
                # Save button
                rx.el.button(
                    fomantic_icon("save", size=16),
                    " Save Metadata",
                    on_click=UploadState.save_metadata_to_dagster,
                    class_name="ui green button",
                    type="button",
                ),
                rx.el.span(
                    " Persists to Dagster asset catalog",
                    style={"fontSize": "0.8rem", "color": "#888", "marginLeft": "10px"},
                ),
                
                class_name="ui form",
            ),
            
            class_name="ui green segment",
            style={"marginBottom": "16px"},
            id="file-metadata-section",
        ),
        rx.fragment(),
    )


def file_item_expanded_content() -> rx.Component:
    """
    Expanded accordion content showing metadata preview for the selected file.
    Uses the selected_file_info computed var for safe access.
    """
    info = UploadState.selected_file_info
    
    def metadata_preview_row(label: str, value: rx.Var[str], fallback: str = "—") -> rx.Component:
        """Compact metadata row for accordion content."""
        return rx.el.div(
            rx.el.span(label + ": ", style={"color": "rgba(255,255,255,0.7)", "fontSize": "0.75rem", "minWidth": "60px"}),
            rx.el.span(
                rx.cond(value != "", value, fallback),
                style={"fontSize": "0.75rem", "fontWeight": "500"},
            ),
            style={"display": "flex", "alignItems": "center", "padding": "1px 0"},
        )
    
    return rx.el.div(
        # Metadata grid (2 columns)
        rx.el.div(
            metadata_preview_row("Subject", info["subject_id"].to(str)),
            metadata_preview_row("Sex", info["sex"].to(str)),
            metadata_preview_row("Tissue", info["tissue"].to(str)),
            metadata_preview_row("Species", info["species"].to(str)),
            metadata_preview_row("Genome", info["reference_genome"].to(str)),
            metadata_preview_row("Size", info["size_mb"].to(str) + " MB"),
            style={
                "display": "grid",
                "gridTemplateColumns": "1fr 1fr",
                "gap": "2px 12px",
                "padding": "8px 12px 8px 28px",
                "backgroundColor": "rgba(0,0,0,0.1)",
                "borderTop": "1px solid rgba(255,255,255,0.15)",
            },
        ),
        # Hint text
        rx.el.div(
            fomantic_icon("edit", size=10, color="rgba(255,255,255,0.5)", style={"marginRight": "4px"}),
            rx.el.span(
                "Edit in form above",
                style={"fontSize": "0.7rem", "color": "rgba(255,255,255,0.6)"},
            ),
            style={"display": "flex", "alignItems": "center", "padding": "4px 12px 8px 28px"},
        ),
    )


def file_item(filename: rx.Var[str]) -> rx.Component:
    """
    Accordion-style file item for the library list.
    
    - Header shows Subject ID (if available) or sample name
    - VCF filename shown inside when expanded
    - Read-only metadata by default, Edit button to enable editing
    """
    is_selected = UploadState.selected_file == filename
    display_name = UploadState.sample_display_names[filename]
    
    return rx.el.div(
        # === HEADER ROW (always visible) ===
        rx.el.div(
            # Expand/collapse chevron
            rx.cond(
                is_selected,
                fomantic_icon("chevron-down", size=12, color="#fff", style={"marginRight": "4px", "flexShrink": "0"}),
                fomantic_icon("chevron-right", size=12, color="#888", style={"marginRight": "4px", "flexShrink": "0"}),
            ),
            # Display name (Subject ID or sample name)
            rx.el.span(
                display_name,
                style={
                    "fontSize": "0.85rem", 
                    "flex": "1", 
                    "overflow": "hidden", 
                    "textOverflow": "ellipsis", 
                    "whiteSpace": "nowrap",
                    "fontWeight": "500",
                },
            ),
            # Status label
            file_status_label(UploadState.file_statuses[filename]),
            # Delete button
            rx.el.button(
                fomantic_icon("trash-2", size=10),
                on_click=lambda: UploadState.delete_file(filename),
                class_name=rx.cond(is_selected, "ui mini icon inverted button", "ui mini icon button"),
                title="Delete sample",
                style={"padding": "3px 5px", "marginLeft": "4px", "flexShrink": "0"},
            ),
            on_click=lambda: UploadState.select_file(filename),
            style={
                "display": "flex",
                "alignItems": "center",
                "cursor": "pointer",
                "padding": "6px 8px",
            },
        ),
        
        # === EXPANDED CONTENT (read-only metadata) ===
        rx.cond(
            is_selected & UploadState.has_file_metadata,
            file_item_readonly_content(filename),
            rx.fragment(),
        ),
        
        id=rx.Var.create("file-item-") + filename.to(str),
        style={
            "marginBottom": "4px",
            "backgroundColor": rx.cond(is_selected, "#00b5ad", "#fff"),
            "color": rx.cond(is_selected, "#fff", "inherit"),
            "border": rx.cond(is_selected, "1px solid #009c95", "1px solid #e0e0e0"),
            "borderRadius": "4px",
            "transition": "all 0.15s ease",
            "overflow": "hidden",
        },
    )


def file_item_readonly_content(filename: rx.Var[str]) -> rx.Component:
    """
    Read-only metadata display for expanded accordion item.
    Shows key info in a compact format with an Edit button.
    """
    info = UploadState.selected_file_info
    
    def meta_row(label: str, value: rx.Var[str]) -> rx.Component:
        """Compact read-only metadata row."""
        return rx.el.div(
            rx.el.span(label + ":", style={"color": "rgba(255,255,255,0.7)", "fontSize": "0.75rem", "minWidth": "60px"}),
            rx.el.span(value, style={"fontSize": "0.75rem", "fontWeight": "500"}),
            style={"display": "flex", "gap": "4px", "alignItems": "center"},
        )
    
    return rx.el.div(
        # VCF filename (always show since header may show Subject ID)
        rx.el.div(
            fomantic_icon("file-text", size=10, color="rgba(255,255,255,0.6)", style={"marginRight": "4px"}),
            rx.el.span(filename, style={"fontSize": "0.7rem", "color": "rgba(255,255,255,0.8)"}),
            style={"display": "flex", "alignItems": "center", "marginBottom": "6px"},
        ),
        # Metadata in compact grid
        rx.el.div(
            meta_row("Species", info["species"].to(str)),
            meta_row("Genome", info["reference_genome"].to(str)),
            meta_row("Sex", UploadState.current_sex),
            meta_row("Tissue", UploadState.current_tissue),
            rx.cond(
                UploadState.current_study_name != "",
                meta_row("Study", UploadState.current_study_name),
                rx.fragment(),
            ),
            style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "2px 8px", "marginBottom": "6px"},
        ),
        # Action buttons
        rx.el.div(
            rx.el.button(
                fomantic_icon("edit", size=10),
                " Edit",
                on_click=UploadState.enable_metadata_edit_mode,
                class_name="ui mini inverted button",
                style={"padding": "3px 8px", "fontSize": "0.7rem"},
            ),
            style={"display": "flex", "justifyContent": "flex-end"},
        ),
        style={"padding": "6px 10px", "backgroundColor": "rgba(0,0,0,0.1)"},
    )


def file_column_content() -> rx.Component:
    """Column 1 content: Unified add sample form and library."""
    return rx.el.div(
        # ============================================================
        # ADD SAMPLE FORM - Compact file + metadata form
        # ============================================================
        add_sample_form(),
        
        # ============================================================
        # METADATA EDIT SECTION - Only shown when edit mode is enabled
        # ============================================================
        rx.cond(
            UploadState.has_selected_file & UploadState.metadata_edit_mode,
            rx.el.div(
                # Header with close button
                rx.el.div(
                    fomantic_icon("edit", size=16, color="#21ba45"),  # green for edit/save
                    rx.el.span(" Edit Metadata", style={"fontSize": "0.95rem", "fontWeight": "600", "marginLeft": "6px", "flex": "1"}),
                    rx.el.button(
                        fomantic_icon("x", size=12),
                        " Done",
                        on_click=UploadState.disable_metadata_edit_mode,
                        class_name="ui mini button",
                        style={"padding": "4px 8px"},
                    ),
                    style={"display": "flex", "alignItems": "center", "marginBottom": "10px"},
                ),
                file_metadata_section(),
                class_name="ui green segment",
                style={"padding": "10px 12px", "marginBottom": "12px"},
            ),
            rx.fragment(),
        ),
        
        # ============================================================
        # LIBRARY SECTION - List of uploaded samples
        # ============================================================
        rx.el.div(
            # Library header with count and refresh
            rx.el.div(
                rx.el.div(
                    fomantic_icon("database", size=16, color="#767676"),
                    rx.el.span(" Samples", style={"fontSize": "0.95rem", "fontWeight": "600", "marginLeft": "4px"}),
                    rx.el.span(
                        UploadState.files.length(),
                        class_name="ui mini circular label",
                        style={"marginLeft": "6px"},
                    ),
                    style={"display": "flex", "alignItems": "center"},
                ),
                rx.el.button(
                    fomantic_icon("refresh-cw", size=12),
                    on_click=UploadState.on_load,
                    class_name="ui mini icon button",
                    id="refresh-files-button",
                    title="Refresh library",
                ),
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "10px"},
            ),
            
            # File list (scrollable accordion area)
            rx.cond(
                UploadState.files.length() > 0,
                rx.el.div(
                    rx.foreach(UploadState.files, file_item),
                    id="file-list",
                    style={
                        "maxHeight": "400px", 
                        "overflowY": "auto",
                        "paddingRight": "4px",  # Space for scrollbar
                    },
                ),
                rx.el.div(
                    fomantic_icon("inbox", size=40, color="#ccc"),
                    rx.el.div("No samples yet", style={"color": "#888", "marginTop": "8px"}),
                    rx.el.div("Upload a VCF file to get started", style={"color": "#aaa", "fontSize": "0.85rem", "marginTop": "4px"}),
                    style={"textAlign": "center", "padding": "30px 10px"},
                    id="empty-file-list",
                ),
            ),
            
            class_name="ui segment",
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


def module_logo_or_icon(module: rx.Var[dict]) -> rx.Component:
    """
    Show the module's HF logo image if available, otherwise fall back to the static icon.
    Logo images are served directly from HuggingFace.
    """
    return rx.cond(
        module["logo_url"].to(str) != "",
        # Logo image from HuggingFace
        rx.el.img(
            src=module["logo_url"].to(str),
            alt=module["name"].to(str),
            style={
                "width": "100%",
                "height": "100%",
                "objectFit": "cover",
                "borderRadius": "4px",
            },
        ),
        # Fallback to static icon
        module_icon(module["name"]),
    )


def module_card(module: rx.Var[dict]) -> rx.Component:
    """
    Module card styled like the reference screenshot.
    Shows: Fomantic checkbox, logo/icon, title, description, repo source badge.
    """
    is_selected = module["selected"].to(bool)
    has_file = UploadState.has_selected_file
    
    return rx.el.div(
        rx.el.div(
            # Left: Fomantic UI Checkbox (display only, card handles click)
            fomantic_checkbox(checked=rx.cond(has_file, is_selected, False)),
            # Module logo or icon (colored box using per-module color from DNA palette)
            rx.el.div(
                module_logo_or_icon(module),
                style={
                    "width": "48px",
                    "height": "48px",
                    "backgroundColor": rx.cond(
                        module["logo_url"].to(str) != "",
                        "transparent",
                        rx.cond(
                            has_file,
                            rx.cond(is_selected, module["color"].to(str), "#bbb"),
                            "#ccc"
                        ),
                    ),
                    "borderRadius": "6px",
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "marginRight": "12px",
                    "flexShrink": "0",
                    "overflow": "hidden",
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
                # Source repo badge (compact, muted)
                rx.cond(
                    module["repo_id"].to(str) != "",
                    rx.el.span(
                        module["repo_id"].to(str),
                        class_name="ui mini label",
                        style={"fontSize": "0.7rem", "fontWeight": "400", "color": "#888"},
                    ),
                    rx.fragment(),
                ),
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
    """Return a colored badge based on run status (DNA palette: green/yellow/red/grey)."""
    return rx.match(
        status,
        ("SUCCESS", rx.el.span("SUCCESS", class_name="ui green label")),
        ("FAILURE", rx.el.span("FAILURE", class_name="ui red label")),
        ("RUNNING", rx.el.span("RUNNING", class_name="ui yellow label")),
        ("QUEUED", rx.el.span("QUEUED", class_name="ui grey label")),
        ("CANCELED", rx.el.span("CANCELED", class_name="ui grey label")),
        rx.el.span(status, class_name="ui grey label"),
    )


def file_type_icon(file_type: rx.Var[str]) -> rx.Component:
    """Return an icon for file type (DNA palette)."""
    return rx.match(
        file_type,
        ("weights", fomantic_icon("scale", size=18, color="#2185d0")),
        ("annotations", fomantic_icon("file-text", size=18, color="#21ba45")),
        ("studies", fomantic_icon("book-open", size=18, color="#00b5ad")),
        fomantic_icon("file", size=18, color="#767676"),
    )


def file_type_label(file_type: rx.Var[str]) -> rx.Component:
    """Return a colored label for file type (DNA palette: blue/green/teal)."""
    return rx.match(
        file_type,
        ("weights", rx.el.span("weights", class_name="ui mini blue label")),
        ("annotations", rx.el.span("annotations", class_name="ui mini green label")),
        ("studies", rx.el.span("studies", class_name="ui mini teal label")),
        rx.el.span(file_type, class_name="ui mini grey label"),
    )


def _collapsible_header(
    expanded: rx.Var[bool],
    icon_name: str,
    title: str,
    right_badge: rx.Component,
    on_toggle: rx.EventSpec,
    accent_color: str = "#2185d0",
) -> rx.Component:
    """
    Reusable foldable section header matching New Analysis style.
    Chevron + icon + title on left; optional badge on right.
    accent_color should match the parent segment color (teal/green/blue).
    """
    return rx.el.div(
        rx.el.div(
            rx.cond(
                expanded,
                fomantic_icon("chevron-down", size=20, color=accent_color),
                fomantic_icon("chevron-right", size=20, color=accent_color),
            ),
            fomantic_icon(icon_name, size=20, color=accent_color, style={"marginLeft": "6px"}),
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


def report_file_card(file_info: rx.Var[dict]) -> rx.Component:
    """Card for a single report file with view and download buttons."""
    # Build URL for viewing in browser (serves HTML)
    view_url = (
        UploadState.backend_api_url + "/api/report/"
        + UploadState.safe_user_id + "/"
        + file_info["sample_name"].to(str) + "/"
        + file_info["name"].to(str)
    )

    return rx.el.div(
        rx.el.div(
            # Report icon
            fomantic_icon("file-text", size=20, color="#e03997"),
            # File info
            rx.el.div(
                rx.el.strong(file_info["name"].to(str), style={"fontSize": "0.85rem"}),
                rx.el.div(
                    rx.el.span("report", class_name="ui mini pink label"),
                    rx.el.span(
                        file_info["size_kb"].to(str),
                        " KB",
                        style={"color": "#888", "fontSize": "0.75rem", "marginLeft": "8px"},
                    ),
                    style={"display": "flex", "alignItems": "center", "gap": "4px", "marginTop": "2px"},
                ),
                style={"flex": "1", "marginLeft": "10px"},
            ),
            # View button (opens in new tab)
            rx.el.a(
                fomantic_icon("external-link", size=14),
                " View",
                href=view_url,
                target="_blank",
                class_name="ui mini pink button",
                style={"marginLeft": "auto", "display": "flex", "alignItems": "center", "gap": "4px"},
            ),
            # Download button
            rx.el.a(
                fomantic_icon("download", size=14),
                href=view_url,
                download=file_info["name"].to(str),
                class_name="ui mini icon button",
                style={"marginLeft": "6px"},
            ),
            style={"display": "flex", "alignItems": "center", "width": "100%"},
        ),
        style={
            "padding": "10px 12px",
            "borderBottom": "1px solid #eee",
        },
    )


def _outputs_tab_menu() -> rx.Component:
    """Sub-tab menu for switching between Data Files and Reports."""
    return rx.el.div(
        rx.el.a(
            fomantic_icon("database", size=14, color=rx.cond(UploadState.outputs_active_tab == "data", "#00b5ad", "#888")),
            " Data Files",
            rx.el.span(
                UploadState.output_file_count,
                class_name="ui mini circular label",
                style={"marginLeft": "6px"},
            ),
            class_name=rx.cond(
                UploadState.outputs_active_tab == "data",
                "active item",
                "item",
            ),
            on_click=lambda: UploadState.switch_outputs_tab("data"),
            style={"cursor": "pointer", "display": "flex", "alignItems": "center", "gap": "4px"},
        ),
        rx.el.a(
            fomantic_icon("file-text", size=14, color=rx.cond(UploadState.outputs_active_tab == "reports", "#e03997", "#888")),
            " Reports",
            rx.cond(
                UploadState.has_report_files,
                rx.el.span(
                    UploadState.report_file_count,
                    class_name="ui mini circular pink label",
                    style={"marginLeft": "6px"},
                ),
                rx.fragment(),
            ),
            class_name=rx.cond(
                UploadState.outputs_active_tab == "reports",
                "active item",
                "item",
            ),
            on_click=lambda: UploadState.switch_outputs_tab("reports"),
            style={"cursor": "pointer", "display": "flex", "alignItems": "center", "gap": "4px"},
        ),
        class_name="ui top attached tabular menu",
        style={"marginBottom": "0"},
    )


def _data_files_content() -> rx.Component:
    """Content for the Data Files sub-tab."""
    return rx.cond(
        UploadState.output_file_count > 0,
        rx.el.div(
            rx.foreach(UploadState.output_files, output_file_card),
            style={
                "maxHeight": "260px",
                "overflowY": "auto",
            },
        ),
        rx.el.div(
            fomantic_icon("inbox", size=30, color="#ccc"),
            rx.el.div(
                "No data files yet",
                style={"color": "#888", "marginTop": "8px", "fontSize": "0.95rem"},
            ),
            rx.el.div(
                "Run an analysis to generate parquet output files",
                style={"color": "#aaa", "marginTop": "4px", "fontSize": "0.82rem"},
            ),
            style={"textAlign": "center", "padding": "20px 16px"},
        ),
    )


def _reports_content() -> rx.Component:
    """Content for the Reports sub-tab."""
    return rx.cond(
        UploadState.has_report_files,
        rx.el.div(
            rx.foreach(UploadState.report_files, report_file_card),
            style={
                "maxHeight": "260px",
                "overflowY": "auto",
            },
        ),
        rx.el.div(
            fomantic_icon("file-text", size=30, color="#ccc"),
            rx.el.div(
                "No reports yet",
                style={"color": "#888", "marginTop": "8px", "fontSize": "0.95rem"},
            ),
            rx.el.div(
                "Generate a report after running the annotation pipeline",
                style={"color": "#aaa", "marginTop": "4px", "fontSize": "0.82rem"},
            ),
            style={"textAlign": "center", "padding": "20px 16px"},
        ),
    )


def outputs_section() -> rx.Component:
    """
    Collapsible section showing output files for the selected sample.
    Contains two sub-tabs: Data Files (parquets) and Reports (HTML).
    Positioned at the top of the right panel for easy access.
    """
    return rx.el.div(
        # Foldable header (teal accent to match ui teal segment)
        _collapsible_header(
            expanded=UploadState.outputs_expanded,
            icon_name="folder-output",
            title="Outputs",
            right_badge=rx.el.span(
                UploadState.total_output_count,
                " files",
                class_name="ui mini teal label",
            ),
            on_toggle=UploadState.toggle_outputs,
            accent_color="#00b5ad",
        ),
        
        # Expanded content
        rx.cond(
            UploadState.outputs_expanded,
            rx.cond(
                UploadState.has_output_files,
                # Tabbed content
                rx.el.div(
                    _outputs_tab_menu(),
                    rx.el.div(
                        rx.match(
                            UploadState.outputs_active_tab,
                            ("data", _data_files_content()),
                            ("reports", _reports_content()),
                            _data_files_content(),  # default
                        ),
                        class_name="ui bottom attached segment",
                        style={"padding": "0", "border": "1px solid #e0e0e0", "borderTop": "none"},
                    ),
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


def input_vcf_preview_section() -> rx.Component:
    """Collapsible section showing selected input VCF as an interactive grid."""
    return rx.el.div(
        _collapsible_header(
            expanded=UploadState.vcf_preview_expanded,
            icon_name="database",
            title="Input VCF Preview",
            right_badge=rx.el.span(
                UploadState.vcf_preview_row_count,
                " rows",
                class_name="ui mini violet label",
            ),
            on_toggle=UploadState.toggle_vcf_preview,
            accent_color="#6435c9",
        ),
        rx.cond(
            UploadState.vcf_preview_expanded,
            rx.el.div(
                rx.cond(
                    UploadState.vcf_preview_loading,
                    rx.el.div(
                        rx.el.i("", class_name="spinner loading icon"),
                        rx.el.span(" Loading VCF preview...", style={"marginLeft": "8px"}),
                        style={"padding": "16px", "color": "#666"},
                    ),
                    rx.cond(
                        UploadState.has_vcf_preview_error,
                        rx.el.div(
                            rx.el.div(
                                rx.el.strong("Failed to load VCF preview"),
                                rx.el.div(
                                    UploadState.vcf_preview_error,
                                    style={"fontSize": "0.85rem", "marginTop": "6px"},
                                ),
                                class_name="content",
                            ),
                            class_name="ui negative message",
                            style={"margin": "0"},
                        ),
                        rx.cond(
                            UploadState.has_vcf_preview,
                            rx.el.div(
                                rx.el.div(
                                    rx.el.span(
                                        "Showing first ",
                                        UploadState.vcf_preview_limit,
                                        " rows",
                                        style={"fontSize": "0.8rem", "color": "#666"},
                                    ),
                                    style={"padding": "8px 4px 10px 4px"},
                                ),
                                data_grid(
                                    rows=UploadState.vcf_preview_rows,
                                    columns=UploadState.vcf_preview_columns,
                                    row_id_field="__row_id__",
                                    show_toolbar=True,
                                    density="compact",
                                    height="420px",
                                    width="100%",
                                ),
                            ),
                            rx.el.div(
                                fomantic_icon("inbox", size=30, color="#ccc"),
                                rx.el.div(
                                    "No rows to preview",
                                    style={"color": "#888", "marginTop": "8px", "fontSize": "0.95rem"},
                                ),
                                style={"textAlign": "center", "padding": "20px 16px"},
                            ),
                        ),
                    ),
                ),
            ),
            rx.box(),
        ),
        style={"padding": "0", "overflow": "hidden"},
        id="input-vcf-preview-section",
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
                class_name="ui mini icon button",
                style={"padding": "6px", "pointerEvents": "none"},  # Let parent handle click
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
                            disabled=UploadState.selected_file_is_running,
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
        
        class_name=rx.cond(is_latest, "ui teal segment", "ui segment"),
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
        class_name="ui mini green label",
    )
    return rx.el.div(
        # Foldable header (green accent to match ui green segment)
        _collapsible_header(
            expanded=UploadState.run_history_expanded,
            icon_name="history",
            title="Run History",
            right_badge=run_count_badge,
            on_toggle=UploadState.toggle_run_history,
            accent_color="#21ba45",
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


def repo_source_card(repo: rx.Var[dict]) -> rx.Component:
    """
    Compact card showing a HuggingFace repository used as a module source.
    Displays repo name, link, and module count.
    """
    return rx.el.div(
        rx.el.div(
            # HF icon (using database as closest match)
            fomantic_icon("database", size=18, color="#2185d0"),
            # Repo name (linked to HF)
            rx.el.a(
                repo["repo_id"].to(str),
                href=repo["url"].to(str),
                target="_blank",
                style={
                    "fontSize": "0.9rem",
                    "fontWeight": "600",
                    "marginLeft": "8px",
                    "color": "#2185d0",
                    "textDecoration": "none",
                },
            ),
            # External link icon
            fomantic_icon("external-link", size=12, color="#888", style={"marginLeft": "4px"}),
            # Module count badge
            rx.el.span(
                repo["module_count"].to(int),
                " modules",
                class_name="ui mini label",
                style={"marginLeft": "auto"},
            ),
            style={
                "display": "flex",
                "alignItems": "center",
                "width": "100%",
            },
        ),
        style={
            "padding": "8px 12px",
            "border": "1px solid #e0e0e0",
            "borderRadius": "4px",
            "backgroundColor": "#f8f9fa",
            "marginBottom": "6px",
        },
    )


def new_analysis_section() -> rx.Component:
    """
    Collapsible section for starting a new analysis.
    
    Contains:
    - HF repository sources (where modules come from)
    - Module selection grid with logos
    - Start button
    
    Uses shared _collapsible_header for uniform design.
    """
    return rx.el.div(
        # Foldable header (blue accent to match ui blue segment)
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
            accent_color="#2185d0",
        ),
        
        # Expanded content
        rx.cond(
            UploadState.new_analysis_expanded,
            rx.el.div(
                # === HF REPOSITORY SOURCES ===
                rx.el.div(
                    rx.el.div(
                        fomantic_icon("boxes", size=16, color="#767676"),
                        rx.el.span(
                            " Module Sources",
                            style={"fontSize": "0.9rem", "fontWeight": "600", "marginLeft": "4px", "color": "#555"},
                        ),
                        style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
                    ),
                    rx.foreach(UploadState.repo_info_list, repo_source_card),
                    style={"marginBottom": "16px"},
                ),
                
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
                            UploadState.selected_file_is_running,
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
    """
    Welcome/onboarding message when no sample is selected.
    Explains the workflow instead of duplicating the left panel.
    """
    step_style = {
        "display": "flex",
        "alignItems": "flex-start",
        "gap": "14px",
        "marginBottom": "20px",
    }
    number_style = {
        "width": "32px",
        "height": "32px",
        "borderRadius": "50%",
        "display": "flex",
        "alignItems": "center",
        "justifyContent": "center",
        "fontWeight": "700",
        "fontSize": "0.9rem",
        "color": "#fff",
        "flexShrink": "0",
    }

    def workflow_step(
        number: str, bg_color: str, icon: str, title: str, desc: str,
    ) -> rx.Component:
        return rx.el.div(
            rx.el.div(number, style={**number_style, "backgroundColor": bg_color}),
            rx.el.div(
                rx.el.div(
                    fomantic_icon(icon, size=16, color=bg_color, style={"marginRight": "6px"}),
                    rx.el.strong(title, style={"fontSize": "0.95rem"}),
                    style={"display": "flex", "alignItems": "center", "marginBottom": "4px"},
                ),
                rx.el.div(desc, style={"fontSize": "0.85rem", "color": "#666", "lineHeight": "1.4"}),
            ),
            style=step_style,
        )

    return rx.el.div(
        # DNA icon + project title
        fomantic_icon("dna", size=80, color="#00b5ad"),
        rx.el.h1(
            "Just-DNA-Lite",
            class_name="ui huge header",
            style={"marginTop": "10px", "marginBottom": "0"},
        ),
        rx.el.p(
            "Next-generation personal genomics platform — lite, fast, and OakVar-free.",
            style={"fontSize": "1.2rem", "color": "#555", "fontStyle": "italic", "marginBottom": "40px"},
        ),
        
        # Two-column layout for Info vs Workflow
        rx.el.div(
            # Left: Core Philosophy
            rx.el.div(
                rx.el.h3("Core Philosophy", class_name="ui large header", style={"textAlign": "left", "marginBottom": "20px"}),
                rx.el.div(
                    rx.el.div(
                        fomantic_icon("database", size=20, color="#2185d0", style={"marginRight": "12px"}),
                        rx.el.div(
                            rx.el.strong("Data as first-class citizen"),
                            rx.el.div("Software-Defined Assets with Dagster for automatic lineage tracking", style={"fontSize": "0.9rem", "color": "#666"}),
                            style={"flex": "1"}
                        ),
                        style={"display": "flex", "alignItems": "start", "marginBottom": "15px"}
                    ),
                    rx.el.div(
                        fomantic_icon("zap", size=20, color="#fbbd08", style={"marginRight": "12px"}),
                        rx.el.div(
                            rx.el.strong("Fast Engines"),
                            rx.el.div("Polars (default) or DuckDB (streaming, low memory)", style={"fontSize": "0.9rem", "color": "#666"}),
                            style={"flex": "1"}
                        ),
                        style={"display": "flex", "alignItems": "start", "marginBottom": "15px"}
                    ),
                    rx.el.div(
                        fomantic_icon("terminal", size=20, color="#21ba45", style={"marginRight": "12px"}),
                        rx.el.div(
                            rx.el.strong("Pure Python Stack"),
                            rx.el.div("Reflex for Web UI, no React/JS needed", style={"fontSize": "0.9rem", "color": "#666"}),
                            style={"flex": "1"}
                        ),
                        style={"display": "flex", "alignItems": "start", "marginBottom": "15px"}
                    ),
                    rx.el.div(
                        fomantic_icon("file-text", size=20, color="#767676", style={"marginRight": "12px"}),
                        rx.el.div(
                            rx.el.strong("Parquet-native"),
                            rx.el.div("VCF → annotated Parquet outputs", style={"fontSize": "0.9rem", "color": "#666"}),
                            style={"flex": "1"}
                        ),
                        style={"display": "flex", "alignItems": "start"}
                    ),
                ),
                style={"flex": "1", "paddingRight": "40px", "borderRight": "1px solid #eee"}
            ),
            
            # Right: Workflow
            rx.el.div(
                rx.el.h3("How to use", class_name="ui large header", style={"textAlign": "left", "marginBottom": "20px"}),
                workflow_step(
                    "1", "#21ba45", "cloud-upload",
                    "Upload a VCF sample",
                    "Use the \"Add Sample\" form in the left column to upload a VCF file.",
                ),
                workflow_step(
                    "2", "#00b5ad", "dna",
                    "Select and choose modules",
                    "Click a sample on the left. Then pick annotation modules that will appear here.",
                ),
                workflow_step(
                    "3", "#2185d0", "play",
                    "Run and get results",
                    "Start the pipeline. Outputs and history will appear in this panel.",
                ),
                style={"flex": "1", "paddingLeft": "40px"}
            ),
            style={"display": "flex", "maxWidth": "900px", "margin": "0 auto", "textAlign": "left"}
        ),
        
        rx.el.div(class_name="ui divider", style={"margin": "40px 0"}),
        
        # Final CTA
        rx.el.div(
            fomantic_icon("chevron-left", size=18, color="#aaa", style={"marginRight": "8px"}),
            rx.el.span("Upload or select a sample in the left column to begin", style={"fontSize": "1.1rem", "color": "#888"}),
            style={"display": "flex", "alignItems": "center", "justifyContent": "center"},
        ),
        
        style={"textAlign": "center", "padding": "60px 40px"},
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
        # Header – DNA gradient banner (green -> teal -> blue from logo)
        rx.el.div(
            fomantic_icon("dna", size=22, color="#fff"),
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
                "background": "linear-gradient(135deg, #21ba45, #00b5ad, #2185d0)",
                "color": "#fff",
                "borderRadius": "6px",
            },
            id="right-column-header",
        ),
        # Content: show sections based on whether sample has been analyzed
        rx.cond(
            UploadState.has_selected_file,
            rx.fragment(
                # Section 0: Input VCF Preview (top) - inspect user input directly
                rx.el.div(
                    input_vcf_preview_section(),
                    class_name="ui violet segment",
                    style={"padding": "16px", "marginBottom": "16px"},
                    id="segment-vcf-preview",
                ),
                # Section 1: Outputs (top) - only shown when there are output files
                rx.cond(
                    UploadState.has_output_files,
                    rx.el.div(
                        outputs_section(),
                        class_name="ui teal segment",
                        style={"padding": "16px", "marginBottom": "16px"},
                        id="segment-outputs",
                    ),
                    rx.fragment(),
                ),
                # Section 2: Run History (middle) - only shown when there are runs
                rx.cond(
                    UploadState.has_filtered_runs,
                    rx.el.div(
                        run_timeline(),
                        class_name="ui green segment",
                        style={"padding": "16px", "marginBottom": "16px"},
                        id="segment-run-history",
                    ),
                    rx.fragment(),
                ),
                # Section 3: New Analysis (always shown)
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
        UploadState.selected_file_is_running,
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
