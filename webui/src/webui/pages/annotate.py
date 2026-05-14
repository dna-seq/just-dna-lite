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
from webui.state import UploadState, OutputPreviewState, PRSState, PRSTraitState
from reflex_mui_datagrid import data_grid, lazyframe_grid, lazyframe_grid_stats_bar
from prs_ui import (
    prs_ancestry_selector,
    prs_build_selector,
    prs_compute_button,
    prs_progress_section,
    prs_results_table,
    prs_scores_selector,
    trait_summary_table,
)
from prs_ui.components.prs_section import _prs_results_header
from prs_ui.grid_style import data_grid_scroll_container


RIGHT_PANEL_TAB_STYLE = {
    "cursor": "pointer",
    "display": "flex",
    "alignItems": "center",
    "gap": "8px",
    "fontSize": "1rem",
    "fontWeight": "600",
    "padding": "14px 18px",
    "minHeight": "52px",
}

RIGHT_PANEL_TAB_BADGE_STYLE = {
    "marginLeft": "4px",
    "fontSize": "0.8rem",
    "padding": "4px 7px",
}

OUTPUT_CARD_META_ROW_STYLE = {
    "display": "flex",
    "alignItems": "center",
    "gap": "12px",
    "marginTop": "8px",
    "flexWrap": "wrap",
}


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
                    key=UploadState._form_key,
                    default_value=UploadState.new_sample_subject_id,
                    on_change=UploadState.set_new_sample_subject_id.debounce(300),
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
                    key=UploadState._form_key,
                    default_value=UploadState.new_sample_study_name,
                    on_change=UploadState.set_new_sample_study_name.debounce(300),
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

            # Divider + Zenodo import (inline, inside the same segment)
            rx.el.div(
                rx.text("or import from Zenodo"),
                class_name="ui horizontal divider",
                style={"margin": "10px 0 8px 0", "fontSize": "0.75rem", "color": "#aaa"},
            ),
            rx.el.div(
                rx.el.input(
                    value=UploadState.zenodo_url_input,
                    on_change=UploadState.set_zenodo_url_input,
                    placeholder="https://zenodo.org/records/...",
                    style={
                        "flex": "1",
                        "padding": "5px 8px",
                        "borderRadius": "4px",
                        "border": "1px solid #ddd",
                        "fontSize": "0.8rem",
                    },
                ),
                rx.el.button(
                    rx.cond(
                        UploadState.zenodo_importing,
                        rx.el.i("", class_name="spinner loading icon"),
                        rx.el.i("", class_name="cloud upload icon"),
                    ),
                    on_click=UploadState.handle_zenodo_import,
                    disabled=UploadState.zenodo_importing,
                    class_name="ui mini purple icon button",
                    style={"marginLeft": "6px"},
                    title="Import from Zenodo",
                ),
                style={"display": "flex", "alignItems": "center"},
            ),
        ),

        class_name="ui blue segment",
        style={"padding": "10px 12px", "marginBottom": "12px"},
    )


def file_status_label(status: rx.Var[str]) -> rx.Component:
    """Return a colored label based on file status (DNA palette: green/yellow/red/grey)."""
    return rx.match(
        status,
        ("completed", rx.el.span("completed", class_name="ui green label")),
        ("running", rx.el.span("running", class_name="ui yellow label")),
        ("uploaded", rx.el.span("uploaded", class_name="ui label")),
        ("error", rx.el.span("error", class_name="ui red label")),
        rx.el.span(status, class_name="ui grey label"),
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
                            key=UploadState.selected_file,
                            default_value=UploadState.current_subject_id,
                            on_change=UploadState.update_file_subject_id.debounce(300),
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
                        key=UploadState.selected_file + "_study",
                        default_value=UploadState.current_study_name,
                        on_change=UploadState.update_file_study_name.debounce(300),
                        placeholder="e.g. Longevity Study 2026",
                    ),
                    class_name="field",
                ),
                
                # Notes
                rx.el.div(
                    optional_field("Notes"),
                    rx.el.textarea(
                        key=UploadState.selected_file + "_notes",
                        default_value=UploadState.current_notes,
                        on_change=UploadState.update_file_notes.debounce(300),
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
                            default_value=UploadState.new_custom_field_name,
                            on_change=UploadState.set_new_field_name.debounce(300),
                            placeholder="Field name",
                        ),
                        class_name="field",
                        style={"flex": "1"},
                    ),
                    rx.el.div(
                        rx.el.input(
                            type="text",
                            default_value=UploadState.new_custom_field_value,
                            on_change=UploadState.set_new_field_value.debounce(300),
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
    upload_date = UploadState.sample_upload_dates[filename]
    
    return rx.el.div(
        # === HEADER ROW (always visible) ===
        rx.el.div(
            # Expand/collapse chevron
            rx.cond(
                is_selected,
                fomantic_icon("chevron-down", size=14, color="#fff", style={"marginRight": "6px", "flexShrink": "0"}),
                fomantic_icon("chevron-right", size=14, color="#888", style={"marginRight": "6px", "flexShrink": "0"}),
            ),
            # Name + upload date stacked
            rx.el.div(
                # Display name (Subject ID or sample name)
                rx.el.div(
                    display_name,
                    style={
                        "fontSize": "1rem",
                        "overflow": "hidden", 
                        "textOverflow": "ellipsis", 
                        "whiteSpace": "nowrap",
                        "fontWeight": "600",
                    },
                ),
                # Upload date
                rx.cond(
                    upload_date != "",
                    rx.el.div(
                        upload_date,
                        style={
                            "fontSize": "0.78rem",
                            "color": rx.cond(is_selected, "rgba(255,255,255,0.7)", "#999"),
                            "lineHeight": "1.2",
                        },
                    ),
                    rx.fragment(),
                ),
                style={"flex": "1", "minWidth": "0"},
            ),
            # Status label
            file_status_label(UploadState.file_statuses[filename]),
            # Delete button
            rx.el.button(
                fomantic_icon("trash-2", size=12),
                on_click=lambda: UploadState.delete_file(filename),
                class_name=rx.cond(is_selected, "ui small icon inverted button", "ui small icon button"),
                title="Delete sample",
                style={"padding": "6px 8px", "marginLeft": "6px", "flexShrink": "0"},
            ),
            on_click=lambda: UploadState.select_file(filename),
            role="button",
            tab_index=0,
            style={
                "display": "flex",
                "alignItems": "center",
                "cursor": "pointer",
                "padding": "10px 10px",
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
        # Zenodo source link (shown when file was imported from Zenodo)
        rx.cond(
            UploadState.current_zenodo_url != "",
            rx.el.div(
                fomantic_icon("external-link", size=10, color="rgba(255,255,255,0.6)", style={"marginRight": "4px", "flexShrink": "0"}),
                rx.el.a(
                    UploadState.current_zenodo_url,
                    href=UploadState.current_zenodo_url,
                    target="_blank",
                    style={
                        "fontSize": "0.7rem",
                        "color": "rgba(255,255,255,0.9)",
                        "textDecoration": "underline",
                        "overflow": "hidden",
                        "textOverflow": "ellipsis",
                        "whiteSpace": "nowrap",
                    },
                ),
                rx.cond(
                    UploadState.current_zenodo_license != "",
                    rx.el.span(
                        UploadState.current_zenodo_license,
                        class_name="ui mini label",
                        style={"marginLeft": "6px", "padding": "2px 4px", "fontSize": "0.6rem", "flexShrink": "0"},
                    ),
                    rx.fragment(),
                ),
                style={"display": "flex", "alignItems": "center", "marginBottom": "6px"},
            ),
            rx.fragment(),
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


def _immutable_disclaimer_box() -> rx.Component:
    """Yellow info box shown instead of upload form in immutable mode."""
    return rx.el.div(
        rx.el.div(
            fomantic_icon("lock", size=16, color="#b58105"),
            rx.el.strong(" Public Demo Mode", style={"marginLeft": "6px"}),
            style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
        ),
        rx.el.p(
            UploadState.immutable_disclaimer,
            style={"fontSize": "0.85rem", "color": "#666", "marginBottom": "8px", "lineHeight": "1.4"},
        ),
        rx.el.a(
            fomantic_icon("download", size=12),
            " Install locally",
            href="https://github.com/dna-seq/just-dna-lite#quick-start",
            target="_blank",
            class_name="ui mini yellow button",
        ),
        rx.cond(
            UploadState.allow_zenodo_import,
            rx.el.div(
                rx.el.div(
                    rx.text("or import from Zenodo"),
                    class_name="ui horizontal divider",
                    style={"margin": "10px 0 8px 0", "fontSize": "0.75rem", "color": "#aaa"},
                ),
                rx.el.div(
                    rx.el.input(
                        value=UploadState.zenodo_url_input,
                        on_change=UploadState.set_zenodo_url_input,
                        placeholder="https://zenodo.org/records/...",
                        style={
                            "flex": "1",
                            "padding": "5px 8px",
                            "borderRadius": "4px",
                            "border": "1px solid #ddd",
                            "fontSize": "0.8rem",
                        },
                    ),
                    rx.el.button(
                        rx.cond(
                            UploadState.zenodo_importing,
                            rx.el.i("", class_name="spinner loading icon"),
                            rx.el.i("", class_name="cloud upload icon"),
                        ),
                        on_click=UploadState.handle_zenodo_import,
                        disabled=UploadState.zenodo_importing,
                        class_name="ui mini purple icon button",
                        style={"marginLeft": "6px"},
                        title="Import from Zenodo",
                    ),
                    style={"display": "flex", "alignItems": "center"},
                ),
            ),
            rx.fragment(),
        ),
        class_name="ui yellow message",
        style={"padding": "12px", "marginBottom": "12px"},
    )


def _public_genome_hint() -> rx.Component:
    """Non-blocking info message suggesting public genomes for quick import."""
    return rx.el.div(
        rx.el.div(
            fomantic_icon("dna", size=14, color="#2185d0"),
            rx.el.span(
                " Try a public genome",
                style={"fontSize": "0.9rem", "fontWeight": "600", "marginLeft": "4px"},
            ),
            style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
        ),
        rx.el.div(
            rx.el.div(
                rx.el.span("Anton Kulaga ", style={"fontWeight": "500", "fontSize": "0.85rem"}),
                rx.el.span("CC-Zero", class_name="ui mini teal label", style={"marginLeft": "4px"}),
                rx.el.button(
                    rx.cond(
                        UploadState.zenodo_importing,
                        rx.el.i("", class_name="spinner loading icon"),
                        rx.el.i("", class_name="download icon"),
                    ),
                    " Import",
                    on_click=UploadState.import_default_sample("https://zenodo.org/records/18370498"),
                    disabled=UploadState.zenodo_importing,
                    class_name="ui mini button",
                    style={"marginLeft": "auto", "padding": "4px 8px"},
                ),
                style={"display": "flex", "alignItems": "center", "marginBottom": "6px"},
            ),
            rx.el.div(
                rx.el.span("Livia Zaharia ", style={"fontWeight": "500", "fontSize": "0.85rem"}),
                rx.el.span("CC-BY-4.0", class_name="ui mini teal label", style={"marginLeft": "4px"}),
                rx.el.button(
                    rx.cond(
                        UploadState.zenodo_importing,
                        rx.el.i("", class_name="spinner loading icon"),
                        rx.el.i("", class_name="download icon"),
                    ),
                    " Import",
                    on_click=UploadState.import_default_sample("https://zenodo.org/records/19487816"),
                    disabled=UploadState.zenodo_importing,
                    class_name="ui mini button",
                    style={"marginLeft": "auto", "padding": "4px 8px"},
                ),
                style={"display": "flex", "alignItems": "center"},
            ),
        ),
        rx.el.div(
            "Voluntarily shared under open licenses for research use.",
            style={"fontSize": "0.75rem", "color": "#999", "marginTop": "8px"},
        ),
        class_name="ui info message",
        style={"padding": "10px 12px", "marginBottom": "12px"},
    )


def _progress_indicator() -> rx.Component:
    """Non-blocking progress indicator for long operations."""
    return rx.cond(
        UploadState.has_progress_status,
        rx.el.div(
            rx.el.i("", class_name="spinner loading icon"),
            rx.el.span(
                UploadState.progress_status,
                style={"marginLeft": "8px", "fontSize": "0.85rem"},
            ),
            class_name="ui icon message",
            style={"padding": "10px 12px", "marginBottom": "12px"},
        ),
        rx.fragment(),
    )


def file_column_content() -> rx.Component:
    """Column 1 content: Unified add sample form and library."""
    return rx.el.div(
        # ============================================================
        # ADD SAMPLE FORM or IMMUTABLE DISCLAIMER
        # ============================================================
        rx.cond(
            UploadState.is_immutable_mode,
            _immutable_disclaimer_box(),
            add_sample_form(),
        ),

        # ============================================================
        # PUBLIC GENOME SUGGESTION
        # Always visible in immutable mode; in normal mode only when no files yet
        # ============================================================
        rx.cond(
            UploadState.is_immutable_mode | (UploadState.files.length() == 0),
            _public_genome_hint(),
            rx.fragment(),
        ),

        # ============================================================
        # PROGRESS INDICATOR for long operations
        # ============================================================
        _progress_indicator(),

        # ============================================================
        # METADATA EDIT SECTION - Only shown when edit mode is enabled
        # ============================================================
        rx.cond(
            UploadState.has_selected_file & UploadState.metadata_edit_mode,
            rx.el.div(
                rx.el.div(
                    fomantic_icon("edit", size=16, color="#21ba45"),
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

            rx.cond(
                UploadState.files.length() > 0,
                rx.el.div(
                    rx.foreach(UploadState.files, file_item),
                    id="file-list",
                    style={
                        "maxHeight": "400px",
                        "overflowY": "auto",
                        "paddingRight": "4px",
                    },
                ),
                rx.el.div(
                    fomantic_icon("inbox", size=40, color="#ccc"),
                    rx.el.div("No samples yet", style={"color": "#888", "marginTop": "8px"}),
                    rx.el.div(
                        "Upload a VCF file or import from Zenodo to get started",
                        style={"color": "#aaa", "fontSize": "0.85rem", "marginTop": "4px"},
                    ),
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
    Show the module's logo image if available, otherwise fall back to the static icon.
    HF logos are served from HuggingFace CDN, local logos via /api/module-logo/.
    """
    return rx.cond(
        module["logo_url"].to(str) != "",
        rx.el.img(
            src=module["logo_url"].to(str),
            alt=module["name"].to(str),
            style={
                "position": "absolute",
                "inset": "0",
                "width": "100%",
                "height": "100%",
                "objectFit": "contain",
                "borderRadius": "4px",
            },
        ),
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
                    "position": "relative",
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
                    rx.el.strong(module["title"], style={"fontSize": "1.05rem"}),
                    style={"marginBottom": "5px"},
                ),
                rx.el.div(
                    module["description"],
                    style={"fontSize": "0.94rem", "color": "#666", "lineHeight": "1.35", "marginBottom": "8px"},
                ),
                # Source repo badge (compact, muted)
                rx.cond(
                    module["repo_id"].to(str) != "",
                    rx.el.span(
                        module["repo_id"].to(str),
                        class_name="ui mini label",
                        style={"fontSize": "0.78rem", "fontWeight": "400", "color": "#888"},
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
            "padding": "16px",
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
        ("weights", fomantic_icon("scale", size=22, color="#2185d0")),
        ("annotations", fomantic_icon("file-text", size=22, color="#21ba45")),
        ("studies", fomantic_icon("book-open", size=22, color="#00b5ad")),
        ("vcf_export", fomantic_icon("dna", size=22, color="#6435c9")),
        fomantic_icon("file", size=22, color="#767676"),
    )


def file_type_label(file_type: rx.Var[str]) -> rx.Component:
    """Return a colored label for file type (DNA palette: blue/green/teal)."""
    return rx.match(
        file_type,
        ("weights", rx.el.span("weights", class_name="ui blue label")),
        ("annotations", rx.el.span("annotations", class_name="ui green label")),
        ("studies", rx.el.span("studies", class_name="ui teal label")),
        ("vcf_export", rx.el.span("vcf", class_name="ui violet label")),
        rx.el.span(file_type, class_name="ui grey label"),
    )


def _collapsible_header(
    expanded: rx.Var[bool],
    icon_name: str,
    title: str | rx.Var[str],
    right_badge: rx.Component,
    on_toggle: rx.EventSpec,
    accent_color: str | rx.Var[str] = "#2185d0",
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


def _materialization_badge(
    materialized_at: rx.Var[str],
    needs_materialization: rx.Var[bool],
) -> rx.Component:
    """Compact badge showing last materialization datetime and staleness."""
    return rx.el.div(
        rx.cond(
            materialized_at != "",
            rx.el.div(
                rx.cond(
                    needs_materialization,
                    fomantic_icon("circle-alert", size=12, color="#f2711c", style={"marginRight": "4px"}),
                    fomantic_icon("circle-check", size=12, color="#21ba45", style={"marginRight": "4px"}),
                ),
                rx.el.span(
                    materialized_at,
                    style={"fontSize": "0.86rem", "color": "#666"},
                ),
                rx.cond(
                    needs_materialization,
                    rx.el.span(
                        " stale",
                        class_name="ui mini orange label",
                        style={"marginLeft": "4px", "fontSize": "0.72rem", "padding": "3px 5px"},
                    ),
                    rx.fragment(),
                ),
                style={"display": "flex", "alignItems": "center"},
            ),
            rx.el.div(
                fomantic_icon("circle-x", size=12, color="#999", style={"marginRight": "4px"}),
                rx.el.span("not materialized", style={"fontSize": "0.86rem", "color": "#999"}),
                style={"display": "flex", "alignItems": "center"},
            ),
        ),
        style={"display": "inline-flex", "alignItems": "center"},
    )


def _run_id_badge(file_info: rx.Var[dict]) -> rx.Component:
    """Compact 'run abc12345' label under an output card, linked to the Dagster run page.

    Hidden when the file's materialization has no associated run_id (e.g.,
    runless events from PRS checkpoints or pre-tracking historical files).
    """
    run_id = file_info["run_id"].to(str)
    run_short = file_info["run_short"].to(str)
    dagster_url = UploadState.dagster_web_url + "/runs/" + run_id
    return rx.cond(
        run_short != "",
        rx.el.a(
            fomantic_icon("history", size=13, color="#2185d0"),
            " run ",
            rx.el.code(
                run_short,
                style={
                    "fontSize": "0.86rem",
                    "background": "transparent",
                    "padding": "0",
                    "color": "#2185d0",
                    "fontWeight": "700",
                },
            ),
            href=dagster_url,
            target="_blank",
            title="Open the run that produced this file in Dagster",
            style={
                "display": "inline-flex",
                "alignItems": "center",
                "gap": "5px",
                "fontSize": "0.86rem",
                "fontWeight": "600",
                "color": "#2185d0",
                "textDecoration": "none",
                "padding": "4px 8px",
                "border": "1px solid #d4e6f6",
                "borderRadius": "999px",
                "backgroundColor": "#f3f8fc",
            },
        ),
        rx.fragment(),
    )


def _output_card_meta_row(file_info: rx.Var[dict]) -> rx.Component:
    """Single metadata row for output cards: materialized date plus run link."""
    return rx.el.div(
        _materialization_badge(
            file_info["materialized_at"].to(str),
            file_info["needs_materialization"].to(bool),
        ),
        _run_id_badge(file_info),
        style=OUTPUT_CARD_META_ROW_STYLE,
    )


def output_file_card(file_info: rx.Var[dict]) -> rx.Component:
    """Card for a single output file with view and download buttons."""
    download_url = rx.cond(
        file_info["type"].to(str) == "vcf_export",
        UploadState.backend_api_url + "/api/download-vcf/" + UploadState.safe_user_id + "/" + file_info["sample_name"].to(str) + "/" + file_info["name"].to(str),
        UploadState.backend_api_url + "/api/download/" + UploadState.safe_user_id + "/" + file_info["sample_name"].to(str) + "/" + file_info["name"].to(str),
    )

    return rx.el.div(
        rx.el.div(
            # File type icon
            file_type_icon(file_info["type"]),
            # File info
            rx.el.div(
                rx.el.span(
                    file_info["name"].to(str),
                    on_click=OutputPreviewState.view_output_file(file_info["path"].to(str)),
                    style={
                        "fontSize": "1.12rem",
                        "fontWeight": "700",
                        "color": "#2185d0",
                        "cursor": "pointer",
                        "lineHeight": "1.25",
                        "wordBreak": "break-word",
                    },
                ),
                rx.el.div(
                    file_type_label(file_info["type"]),
                    rx.el.span(
                        "Produced by ",
                        rx.el.strong(file_info["module"].to(str)),
                        " module",
                        style={
                            "color": "#444",
                            "fontSize": "0.96rem",
                            "marginLeft": "6px",
                        },
                    ),
                    rx.el.span(
                        file_info["size_mb"].to(str),
                        " MB",
                        class_name="ui label",
                        style={
                            "color": "#666",
                            "fontSize": "0.86rem",
                            "marginLeft": "8px",
                        },
                    ),
                    style={
                        "display": "flex",
                        "alignItems": "center",
                        "gap": "6px",
                        "marginTop": "6px",
                        "flexWrap": "wrap",
                    },
                ),
                _output_card_meta_row(file_info),
                style={"flex": "1", "marginLeft": "14px", "minWidth": "0"},
            ),
            # Action buttons
            rx.el.div(
                # View in grid button
                rx.el.button(
                    fomantic_icon("eye", size=15),
                    on_click=OutputPreviewState.view_output_file(file_info["path"].to(str)),
                    class_name="ui icon button",
                    title="Preview in data grid",
                ),
                # Download button
                rx.el.a(
                    fomantic_icon("download", size=15),
                    href=download_url,
                    download=file_info["name"].to(str),
                    class_name="ui icon primary button",
                ),
                style={"display": "flex", "gap": "8px", "marginLeft": "auto", "flexShrink": "0"},
            ),
            style={"display": "flex", "alignItems": "center", "width": "100%"},
        ),
        style={
            "padding": "16px 12px",
            "borderBottom": "1px solid #eee",
        },
    )


def report_file_card(file_info: rx.Var[dict]) -> rx.Component:
    """Card for a single report file with view and download buttons."""
    view_url = (
        UploadState.backend_api_url + "/api/report/"
        + UploadState.safe_user_id + "/"
        + file_info["sample_name"].to(str) + "/"
        + file_info["name"].to(str)
    )

    return rx.el.div(
        rx.el.div(
            # Report icon
            fomantic_icon("file-text", size=22, color="#e03997"),
            # File info
            rx.el.div(
                rx.el.a(
                    file_info["name"].to(str),
                    href=view_url,
                    target="_blank",
                    style={
                        "fontSize": "1.12rem",
                        "fontWeight": "700",
                        "color": "#e03997",
                        "textDecoration": "none",
                        "cursor": "pointer",
                        "lineHeight": "1.25",
                        "wordBreak": "break-word",
                    },
                ),
                rx.el.div(
                    rx.el.span("report", class_name="ui pink label"),
                    rx.el.span(
                        file_info["size_kb"].to(str),
                        " KB",
                        style={"color": "#666", "fontSize": "0.86rem", "marginLeft": "8px"},
                    ),
                    style={"display": "flex", "alignItems": "center", "gap": "6px", "marginTop": "6px"},
                ),
                _output_card_meta_row(file_info),
                style={"flex": "1", "marginLeft": "14px", "minWidth": "0"},
            ),
            # View button (opens in new tab)
            rx.el.a(
                fomantic_icon("external-link", size=15),
                " View",
                href=view_url,
                target="_blank",
                class_name="ui pink button",
                style={"marginLeft": "auto", "display": "flex", "alignItems": "center", "gap": "6px", "flexShrink": "0"},
            ),
            # Download button
            rx.el.a(
                fomantic_icon("download", size=15),
                href=view_url,
                download=file_info["name"].to(str),
                class_name="ui icon button",
                style={"marginLeft": "8px", "flexShrink": "0"},
            ),
            style={"display": "flex", "alignItems": "center", "width": "100%"},
        ),
        style={
            "padding": "16px 12px",
            "borderBottom": "1px solid #eee",
        },
    )


def _vcf_export_button() -> rx.Component:
    """Button to trigger VCF export for the current sample, with Dagster link while running."""
    return rx.el.div(
        rx.el.div(
            rx.cond(
                UploadState.vcf_exporting,
                rx.el.span(
                    fomantic_icon("loader-circle", size=12, color="#6435c9"),
                    " Exporting VCF...",
                    style={"color": "#6435c9", "fontSize": "0.8rem", "display": "flex", "alignItems": "center", "gap": "4px"},
                ),
                rx.fragment(),
            ),
            rx.cond(
                UploadState.vcf_export_dagster_url != "",
                rx.el.a(
                    fomantic_icon("external-link", size=12, color="#6435c9"),
                    " View in Dagster",
                    href=UploadState.vcf_export_dagster_url,
                    target="_blank",
                    style={
                        "color": "#6435c9",
                        "fontSize": "0.78rem",
                        "textDecoration": "none",
                        "display": "flex",
                        "alignItems": "center",
                        "gap": "3px",
                        "marginLeft": "8px",
                    },
                ),
                rx.fragment(),
            ),
            style={"display": "flex", "alignItems": "center"},
        ),
        rx.el.button(
            rx.cond(
                UploadState.vcf_exporting,
                fomantic_icon("loader-circle", size=14, color="white"),
                fomantic_icon("dna", size=14, color="white"),
            ),
            rx.cond(
                UploadState.vcf_exporting,
                " Exporting...",
                " Export VCF",
            ),
            on_click=UploadState.run_vcf_export,
            disabled=UploadState.vcf_exporting,
            class_name=rx.cond(
                UploadState.vcf_exporting,
                "ui mini violet loading button",
                "ui mini violet button",
            ),
            style={"display": "flex", "alignItems": "center", "gap": "4px"},
            title="Export annotated data as VCF files (per-module + combined)",
        ),
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "padding": "6px 10px",
            "borderBottom": "1px solid #eee",
            "backgroundColor": "#fafafa",
        },
    )


def _data_files_content() -> rx.Component:
    """Content for the Data Files sub-tab."""
    return rx.cond(
        UploadState.output_file_count > 0,
        rx.el.div(
            _vcf_export_button(),
            rx.el.div(
                rx.foreach(UploadState.output_files, output_file_card),
            ),
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


def _prs_results_content() -> rx.Component:
    """PRS results section with Grouped/Individual toggle from prs-ui."""
    return rx.cond(
        PRSState.prs_results.length() > 0,
        rx.vstack(
            rx.cond(
                PRSState.low_match_warning,
                rx.callout(
                    "One or more scores have a match rate below 10%. "
                    "This may indicate a genome build mismatch between "
                    "the VCF and scoring files. Check your genome build selection.",
                    icon="triangle_alert",
                    color_scheme="red",
                    size="1",
                    width="100%",
                ),
            ),
            _prs_results_header(PRSState),
            trait_summary_table(PRSState, detail_height=800),
            prs_results_table(PRSState, detail_height=800),
            spacing="3",
            width="100%",
        ),
        rx.el.div(
            fomantic_icon("chart-bar", size=30, color="#ccc"),
            rx.el.div(
                "No PRS results yet",
                style={"color": "#888", "marginTop": "8px", "fontSize": "0.95rem"},
            ),
            rx.el.div(
                "Compute PRS scores using the Polygenic Risk Scores panel above",
                style={"color": "#aaa", "marginTop": "4px", "fontSize": "0.82rem"},
            ),
            style={"textAlign": "center", "padding": "20px 16px"},
        ),
    )


def _prs_interpretation_guide() -> rx.Component:
    """Collapsible guide explaining how to read PRS results.

    Uses an inline span in the native summary so the browser disclosure
    triangle and title stay on the same baseline.
    """
    return rx.el.details(
        rx.el.summary(
            rx.el.span(
                "How to interpret PRS results",
                style={
                    "fontSize": "0.875rem",
                    "fontWeight": "500",
                    "cursor": "pointer",
                    "verticalAlign": "middle",
                },
            ),
            style={
                "cursor": "pointer",
                "lineHeight": "1.4",
            },
        ),
        rx.vstack(
            rx.text(
                "The raw PRS score (e.g. 0.098) is model-specific and unitless - "
                "it cannot be read as 'protective' or 'risky' on its own, and scores "
                "from different PGS models cannot be compared to each other.",
                size="2",
            ),
            rx.text(
                "The percentile is the key number. It shows where your score falls "
                "relative to a reference population of the same ancestry. "
                "For virtually all standard PRS models, higher percentile = more "
                "genetic variants associated with increased risk for that trait.",
                size="2",
            ),
            rx.hstack(
                rx.badge("< 25th", color_scheme="blue", size="1", variant="soft"),
                rx.text("Below average predisposition", size="2"),
                spacing="2",
                align="center",
            ),
            rx.hstack(
                rx.badge("25th - 75th", color_scheme="gray", size="1", variant="soft"),
                rx.text("Average predisposition", size="2"),
                spacing="2",
                align="center",
            ),
            rx.hstack(
                rx.badge("75th - 90th", color_scheme="orange", size="1", variant="soft"),
                rx.text("Above average predisposition", size="2"),
                spacing="2",
                align="center",
            ),
            rx.hstack(
                rx.badge("> 90th", color_scheme="red", size="1", variant="soft"),
                rx.text("High predisposition", size="2"),
                spacing="2",
                align="center",
            ),
            rx.text(
                "PRS captures only inherited genetic variants - not lifestyle, "
                "environment, or treatment. Most people with a high PRS never develop "
                "the condition, and many with a low PRS do. This is a research tool, "
                "not a diagnostic test.",
                size="2",
                color="var(--gray-11)",
            ),
            spacing="2",
            padding_top="8px",
            padding_x="4px",
        ),
    )


def _output_preview_grid() -> rx.Component:
    """Inline output preview grid inside the Outputs section.

    Uses ``OutputPreviewState`` which has its own ``LazyFrameGridMixin``,
    completely independent from the VCF input grid.  Hidden until the
    user clicks the eye icon on a data file.
    """
    return rx.cond(
        OutputPreviewState.output_preview_expanded,
        rx.el.div(
            # Header bar with file name and row count
            rx.el.div(
                rx.el.div(
                    fomantic_icon("eye", size=16, color="#00b5ad"),
                    rx.el.strong(
                        "Output Preview",
                        style={"marginLeft": "6px"},
                    ),
                    rx.cond(
                        OutputPreviewState.output_preview_label != "",
                        rx.el.span(
                            OutputPreviewState.output_preview_label,
                            class_name="ui mini teal label",
                            style={"marginLeft": "8px"},
                        ),
                        rx.fragment(),
                    ),
                    rx.cond(
                        OutputPreviewState.has_output_preview,
                        rx.el.span(
                            OutputPreviewState.output_preview_row_count,
                            " rows",
                            class_name="ui mini teal label",
                            style={"marginLeft": "4px"},
                        ),
                        rx.fragment(),
                    ),
                    style={
                        "display": "flex",
                        "alignItems": "center",
                        "flexWrap": "wrap",
                        "gap": "4px",
                    },
                ),
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "padding": "8px 0",
                    "marginBottom": "10px",
                    "borderBottom": "1px solid #e0e0e0",
                },
            ),
            # Loading spinner
            rx.cond(
                OutputPreviewState.output_preview_loading,
                rx.el.div(
                    rx.el.i("", class_name="spinner loading icon"),
                    rx.el.span(" Loading output preview...", style={"marginLeft": "8px"}),
                    style={"padding": "16px", "color": "#666"},
                ),
                rx.fragment(),
            ),
            # Error overlay
            rx.cond(
                OutputPreviewState.has_output_preview_error,
                rx.el.div(
                    rx.el.div(
                        rx.el.strong("Failed to load output preview"),
                        rx.el.div(
                            OutputPreviewState.output_preview_error,
                            style={"fontSize": "0.85rem", "marginTop": "6px"},
                        ),
                        class_name="content",
                    ),
                    class_name="ui negative message",
                    style={"margin": "0 0 8px 0"},
                ),
                rx.fragment(),
            ),
            # Grid – hidden via CSS when no data loaded yet
            rx.el.div(
                lazyframe_grid(
                    OutputPreviewState,
                    show_toolbar=True,
                    show_description_in_header=True,
                    density="compact",
                    column_header_height=70,
                    height="72vh",
                    width="100%",
                    debug_log=False,
                ),
                style={
                    "display": rx.cond(OutputPreviewState.has_output_preview, "block", "none"),
                },
            ),
            style={
                "marginTop": "18px",
            },
        ),
        rx.fragment(),
    )


def quality_filter_stats_banner() -> rx.Component:
    """Compact banner showing quality filter statistics from normalization.

    Displayed between the collapsible header and the data grid when
    filter stats are available from the Dagster materialization metadata.
    """
    return rx.cond(
        UploadState.has_norm_stats,
        rx.el.div(
            # Icon + main message
            rx.el.div(
                fomantic_icon("filter", size=16, color="#6435c9", style={"marginRight": "8px", "flexShrink": "0"}),
                rx.el.span(
                    "Quality Filters Applied",
                    style={"fontWeight": "600", "fontSize": "0.9rem", "marginRight": "12px"},
                ),
                # Stats chips
                rx.el.span(
                    UploadState.norm_rows_before.to(str),
                    " total",
                    class_name="ui mini label",
                    style={"marginRight": "4px"},
                ),
                fomantic_icon("arrow-right", size=12, color="#888", style={"margin": "0 4px"}),
                rx.el.span(
                    UploadState.norm_rows_after.to(str),
                    " kept",
                    class_name="ui mini green label",
                    style={"marginRight": "4px"},
                ),
                rx.cond(
                    UploadState.norm_filters_active,
                    rx.el.span(
                        UploadState.norm_rows_removed.to(str),
                        " quality filtered (",
                        UploadState.norm_removed_pct,
                        "%)",
                        class_name="ui mini orange label",
                    ),
                    rx.el.span(
                        "0 quality filtered",
                        class_name="ui mini label",
                    ),
                ),
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "flexWrap": "wrap",
                    "gap": "2px",
                },
            ),
            style={
                "padding": "8px 12px",
                "marginBottom": "10px",
                "backgroundColor": "#f8f6ff",
                "border": "1px solid #e0d8f0",
                "borderRadius": "4px",
            },
            id="quality-filter-stats-banner",
        ),
        rx.fragment(),
    )


def input_vcf_preview_section() -> rx.Component:
    """Show the selected input VCF file without an inner accordion.

    The grid is rendered once and kept mounted to avoid DOM destruction on
    state changes (which causes blinking).  Only the initial loading spinner
    and error overlay are conditionally shown on top.
    """
    return rx.el.div(
        rx.el.div(
            fomantic_icon("database", size=16, color="#6435c9"),
            rx.el.strong(
                "Normalized VCF Preview",
                style={"marginLeft": "6px"},
            ),
            rx.cond(
                UploadState.preview_source_label != "",
                rx.el.span(
                    UploadState.preview_source_label,
                    class_name="ui mini violet label",
                    style={"marginLeft": "8px"},
                ),
                rx.fragment(),
            ),
            rx.el.span(
                UploadState.vcf_preview_row_count,
                " rows",
                class_name="ui mini violet label",
                style={"marginLeft": "4px"},
            ),
            style={
                "display": "flex",
                "alignItems": "center",
                "flexWrap": "wrap",
                "gap": "4px",
                "padding": "4px 0 10px 0",
                "marginBottom": "10px",
                "borderBottom": "1px solid #e0d8f0",
            },
        ),
        # Quality filter statistics banner
        quality_filter_stats_banner(),
        # Initial-load spinner (only during first VCF scan, NOT scroll loads)
        rx.cond(
            UploadState.vcf_preview_loading,
            rx.el.div(
                rx.el.i("", class_name="spinner loading icon"),
                rx.el.span(" Loading VCF preview...", style={"marginLeft": "8px"}),
                style={"padding": "16px", "color": "#666"},
            ),
            rx.fragment(),
        ),
        # Error overlay
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
            rx.fragment(),
        ),
        # Grid – always mounted once UploadState inherits from the mixin.
        # Hidden via CSS when no data loaded yet (avoids DOM destroy/recreate).
        rx.el.div(
            lazyframe_grid(
                UploadState,
                show_toolbar=True,
                show_description_in_header=True,
                density="compact",
                column_header_height=70,
                height="calc(100vh - 270px)",
                width="100%",
                debug_log=False,
            ),
            style={
                "display": rx.cond(UploadState.has_vcf_preview, "block", "none"),
            },
        ),
        # Empty state placeholder (only when nothing loaded and no error)
        rx.cond(
            ~UploadState.has_vcf_preview & ~UploadState.has_vcf_preview_error & ~UploadState.vcf_preview_loading,
            rx.el.div(
                fomantic_icon("inbox", size=30, color="#ccc"),
                rx.el.div(
                    "No rows to preview",
                    style={"color": "#888", "marginTop": "8px", "fontSize": "0.95rem"},
                ),
                style={"textAlign": "center", "padding": "20px 16px"},
            ),
            rx.fragment(),
        ),
        style={"padding": "0"},
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
                rx.el.span("latest", class_name="ui teal label", style={"marginLeft": "6px"}),
                rx.box(),
            ),
            # Timestamp
            rx.el.span(
                run["started_at"].to(str),
                style={"marginLeft": "12px", "color": "#666", "fontSize": "0.95rem", "flex": "1"},
            ),
            # Module count
            rx.el.span(
                run["modules"].to(list).length(),
                " modules",
                class_name="ui label",
                style={"marginRight": "8px"},
            ),
            # Expand/collapse button
            rx.el.button(
                rx.cond(
                    is_expanded,
                    fomantic_icon("chevron-up", size=16),
                    fomantic_icon("chevron-down", size=16),
                ),
                class_name="ui icon button",
                style={"padding": "8px", "pointerEvents": "none"},  # Let parent handle click
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
                    rx.el.span("Modules: ", style={"color": "#666", "fontSize": "0.95rem"}),
                    rx.foreach(
                        run["modules"].to(list),
                        lambda m: rx.el.span(m.to(str), class_name="ui label", style={"marginRight": "4px"}),
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
                            class_name="ui primary button",
                            style={"display": "inline-flex", "alignItems": "center", "gap": "4px"},
                        ),
                        rx.el.button(
                            fomantic_icon("sliders-horizontal", size=14),
                            " Modify",
                            on_click=UploadState.modify_and_run,
                            class_name="ui button",
                            style={"display": "inline-flex", "alignItems": "center", "gap": "4px", "marginLeft": "6px"},
                        ),
                        style={"marginBottom": "10px"},
                    ),
                    rx.box(),
                ),
                # Run ID
                rx.el.div(
                    rx.el.span("Run ID: ", style={"color": "#666", "fontSize": "0.95rem"}),
                    rx.el.code(run_id, style={"fontSize": "0.86rem"}),
                    style={"marginBottom": "10px"},
                ),
                # Dagster link
                rx.el.a(
                    fomantic_icon("external-link", size=12),
                    " Open in Dagster",
                    href=dagster_url,
                    target="_blank",
                    class_name="ui button",
                    style={"display": "inline-flex", "alignItems": "center", "gap": "4px"},
                ),
                style={"marginTop": "12px", "paddingTop": "12px", "borderTop": "1px solid #eee"},
            ),
            rx.box(),
        ),
        
        class_name=rx.cond(is_latest, "ui teal segment", "ui segment"),
        style={"margin": "0 0 10px 0", "padding": "14px 16px"},
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


def new_analysis_section() -> rx.Component:
    """
    Section for starting a new analysis (always shown — no accordion header
    because the parent New Analysis tab is the entry point).

    Contains:
    - Manage-module-sources link
    - Module selection grid with logos (no internal scroll, grows naturally)
    - Ensembl annotation toggle
    - Start button
    """
    return rx.el.div(
        rx.el.div(
            fomantic_icon("boxes", size=14, color="#a333c8"),
            rx.el.a(
                " Manage module sources",
                href="/modules",
                style={"fontSize": "0.85rem", "color": "#a333c8", "marginLeft": "4px"},
            ),
            style={"display": "flex", "alignItems": "center", "marginBottom": "14px"},
        ),
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
        rx.el.div(
            rx.foreach(UploadState.module_metadata_list, module_card),
            style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fill, minmax(320px, 1fr))",
                "gap": "12px",
                "marginBottom": "16px",
            },
            id="module-cards-grid",
        ),
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.el.input(
                        type="checkbox",
                        checked=UploadState.include_ensembl,
                        read_only=True,
                    ),
                    rx.el.label(
                        rx.el.strong("Include Ensembl Variation Annotations"),
                    ),
                    on_click=UploadState.toggle_ensembl,
                    class_name=rx.cond(
                        UploadState.include_ensembl,
                        "ui checked checkbox",
                        "ui checkbox",
                    ),
                ),
                style={"display": "flex", "alignItems": "center", "gap": "10px"},
            ),
            rx.el.div(
                "Position-based annotation with the Ensembl variation database via DuckDB. "
                "Adds rsid mapping and known variant classifications.",
                style={
                    "fontSize": "0.85rem",
                    "color": "#666",
                    "marginTop": "6px",
                    "lineHeight": "1.3",
                },
            ),
            class_name="ui segment",
            style={
                "padding": "14px",
                "marginBottom": "16px",
                "border": "1px solid #e0e0e0",
                "borderRadius": "6px",
                "backgroundColor": rx.cond(
                    UploadState.include_ensembl,
                    "#f0f7ff",
                    "#fff",
                ),
            },
        ),
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
        style={"padding": "0"},
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
            style={"fontSize": "1.2rem", "color": "#555", "fontStyle": "italic", "marginBottom": "20px"},
        ),
        
        # RUO Warning Banner
        rx.el.div(
            rx.el.div(
                fomantic_icon("exclamation-triangle", size=24, color="#db2828", style={"marginBottom": "8px"}),
                rx.el.div(
                    rx.el.strong("Medical Disclaimer & Research Use Only (RUO)"),
                    style={"fontSize": "1.1rem", "color": "#db2828", "marginBottom": "6px"},
                ),
                rx.el.div(
                    "This tool is for research, educational, and self-exploration purposes only. "
                    "It is ",
                    rx.el.strong("not a medical device"),
                    " and provides no medical advice. "
                    "The genetic modules and Polygenic Risk Scores (PRS) here are ",
                    rx.el.strong("not clinically validated"),
                    ". You must never use this tool for diagnostic or medical decisions. "
                    "Interesting findings should be re-tested with clinically validated methods "
                    "such as PCR or other orthogonal confirmation in a certified lab.",
                    style={"fontSize": "0.95rem", "color": "#444", "lineHeight": "1.45"},
                ),
                class_name="ui red message",
                style={
                    "maxWidth": "840px",
                    "width": "100%",
                    "textAlign": "center",
                    "margin": "0",
                },
            ),
            style={
                "display": "flex",
                "justifyContent": "center",
                "width": "100%",
                "marginBottom": "40px",
            },
        ),
        
        # Two-column layout for Info vs Workflow
        rx.el.div(
            # Left: Core Philosophy
            rx.el.div(
                rx.el.h3("Core Philosophy", class_name="ui large header", style={"textAlign": "left", "marginBottom": "20px"}),
                rx.el.div(
                    rx.el.div(
                        fomantic_icon("lock", size=20, color="#2185d0", style={"marginRight": "12px"}),
                        rx.el.div(
                            rx.el.strong("Your data, your call"),
                            rx.el.div("Runs entirely on your machine. Nothing leaves your computer.", style={"fontSize": "0.9rem", "color": "#666"}),
                            style={"flex": "1"}
                        ),
                        style={"display": "flex", "alignItems": "start", "marginBottom": "15px"}
                    ),
                    rx.el.div(
                        fomantic_icon("eye", size=20, color="#fbbd08", style={"marginRight": "12px"}),
                        rx.el.div(
                            rx.el.strong("Unfiltered access"),
                            rx.el.div("We show the full research view, not a pre-filtered clinical summary.", style={"fontSize": "0.9rem", "color": "#666"}),
                            style={"flex": "1"}
                        ),
                        style={"display": "flex", "alignItems": "start", "marginBottom": "15px"}
                    ),
                    rx.el.div(
                        fomantic_icon("rocket", size=20, color="#21ba45", style={"marginRight": "12px"}),
                        rx.el.div(
                            rx.el.strong("Speed & Iteration"),
                            rx.el.div("We optimize for rapid exploration and fast module creation, not clinical-style validation cycles.", style={"fontSize": "0.9rem", "color": "#666"}),
                            style={"flex": "1"}
                        ),
                        style={"display": "flex", "alignItems": "start", "marginBottom": "15px"}
                    ),
                    rx.el.div(
                        fomantic_icon("warning sign", size=20, color="#767676", style={"marginRight": "12px"}),
                        rx.el.div(
                            rx.el.strong("Scientific realism"),
                            rx.el.div("Modules, PRS, and especially AI-generated content can be wrong, incomplete, or clinically irrelevant.", style={"fontSize": "0.9rem", "color": "#666"}),
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
                rx.el.div(class_name="ui divider", style={"margin": "16px 0"}),
                workflow_step(
                    "~", "#a333c8", "boxes",
                    "Create custom modules",
                    "Use the Module Manager tab to upload DSL specs or let the AI agent build one from a research paper.",
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




def _right_panel_tab_menu() -> rx.Component:
    """Top-level horizontal tab menu for the right panel.

    Tabs are flat: Input | PRS | Annotated Files | Reports | New Analysis.
    """
    return rx.el.div(
        rx.el.a(
            fomantic_icon(
                "database",
                size=16,
                color=rx.cond(UploadState.right_panel_active_tab == "input", "#6435c9", "#888"),
            ),
            " Input",
            rx.cond(
                UploadState.vcf_preview_row_count > 0,
                rx.el.span(
                    UploadState.vcf_preview_row_count,
                    " rows",
                    class_name="ui mini circular violet label",
                    style=RIGHT_PANEL_TAB_BADGE_STYLE,
                ),
                rx.fragment(),
            ),
            class_name=rx.cond(
                UploadState.right_panel_active_tab == "input",
                "active item",
                "item",
            ),
            on_click=UploadState.switch_to_input_tab,
            style=RIGHT_PANEL_TAB_STYLE,
        ),
        rx.el.a(
            fomantic_icon(
                "chart-bar",
                size=16,
                color=rx.cond(UploadState.right_panel_active_tab == "prs", "#f2711c", "#888"),
            ),
            " PRS",
            rx.cond(
                PRSState.prs_results.length() > 0,
                rx.el.span(
                    PRSState.prs_results.length(),
                    class_name="ui mini circular orange label",
                    style=RIGHT_PANEL_TAB_BADGE_STYLE,
                ),
                rx.fragment(),
            ),
            class_name=rx.cond(
                UploadState.right_panel_active_tab == "prs",
                "active item",
                "item",
            ),
            on_click=UploadState.switch_to_prs_tab,
            style=RIGHT_PANEL_TAB_STYLE,
        ),
        rx.el.a(
            fomantic_icon(
                "folder-output",
                size=16,
                color=rx.cond(UploadState.right_panel_active_tab == "annotated_files", "#00b5ad", "#888"),
            ),
            " Annotated Files",
            rx.el.span(
                UploadState.output_file_count,
                class_name="ui mini circular teal label",
                style=RIGHT_PANEL_TAB_BADGE_STYLE,
            ),
            class_name=rx.cond(
                UploadState.right_panel_active_tab == "annotated_files",
                "active item",
                "item",
            ),
            on_click=UploadState.switch_to_annotated_files_tab,
            style=RIGHT_PANEL_TAB_STYLE,
        ),
        rx.el.a(
            fomantic_icon(
                "file-text",
                size=16,
                color=rx.cond(UploadState.right_panel_active_tab == "reports", "#e03997", "#888"),
            ),
            " Reports",
            rx.cond(
                UploadState.has_report_files,
                rx.el.span(
                    UploadState.report_file_count,
                    class_name="ui mini circular pink label",
                    style=RIGHT_PANEL_TAB_BADGE_STYLE,
                ),
                rx.fragment(),
            ),
            class_name=rx.cond(
                UploadState.right_panel_active_tab == "reports",
                "active item",
                "item",
            ),
            on_click=UploadState.switch_to_reports_tab,
            style=RIGHT_PANEL_TAB_STYLE,
        ),
        rx.el.a(
            fomantic_icon(
                "plus-circle",
                size=16,
                color=rx.cond(UploadState.right_panel_active_tab == "analysis", "#2185d0", "#888"),
            ),
            " New Analysis",
            rx.cond(
                UploadState.selected_modules.length() > 0,
                rx.el.span(
                    UploadState.selected_modules.length(),
                    " selected",
                    class_name="ui mini circular blue label",
                    style=RIGHT_PANEL_TAB_BADGE_STYLE,
                ),
                rx.fragment(),
            ),
            class_name=rx.cond(
                UploadState.right_panel_active_tab == "analysis",
                "active item",
                "item",
            ),
            on_click=UploadState.switch_to_analysis_tab,
            style=RIGHT_PANEL_TAB_STYLE,
        ),
        class_name="ui top attached tabular menu",
        style={"marginBottom": "0"},
        id="right-panel-tab-menu",
    )


def _tab_info_message(
    visible: rx.Var[bool],
    close_event: rx.event.EventHandler,
    icon_name: str,
    title: str,
    body: str,
) -> rx.Component:
    """Closable Fomantic info message for right-panel tabs."""
    return rx.cond(
        visible,
        rx.el.div(
            rx.el.i(
                "",
                class_name="close icon",
                on_click=close_event,
                role="button",
                aria_label=f"Close {title} message",
                tab_index=0,
                style={"cursor": "pointer"},
            ),
            fomantic_icon(icon_name, size=20, color="#2185d0"),
            rx.el.div(
                rx.el.div(title, class_name="header"),
                rx.el.p(body),
                class_name="content",
            ),
            class_name="ui icon info message",
            style={"margin": "0 0 16px 0"},
        ),
        rx.fragment(),
    )


def _input_tab_content() -> rx.Component:
    """Content for the Input tab: the normalized VCF preview."""
    return rx.el.div(
        _tab_info_message(
            UploadState.show_input_tab_info,
            UploadState.close_input_tab_info,
            "database",
            "Your uploaded DNA file, prepared for analysis",
            "This preview shows the variants after cleanup: low-quality rows are filtered, chromosome names are standardized, and the table is ready to match against annotation modules.",
        ),
        input_vcf_preview_section(),
        id="segment-vcf-preview",
    )


def _prs_mode_toggle() -> rx.Component:
    """Segmented toggle for switching between trait-grouped and individual PRS selection."""
    return rx.el.div(
        rx.el.button(
            fomantic_icon("layers", size=16),
            " By Trait",
            on_click=PRSState.set_prs_selection_mode("traits"),
            class_name=rx.cond(
                PRSState.prs_selection_mode == "traits",
                "ui blue button",
                "ui basic button",
            ),
            style={"marginRight": "0"},
        ),
        rx.el.button(
            fomantic_icon("list", size=16),
            " Individual",
            on_click=PRSState.set_prs_selection_mode("individual"),
            class_name=rx.cond(
                PRSState.prs_selection_mode == "individual",
                "ui blue button",
                "ui basic button",
            ),
            style={"marginLeft": "0"},
        ),
        class_name="ui buttons",
    )


def _prs_trait_selector() -> rx.Component:
    """Trait selection grid for grouped-by-trait PRS input."""
    return rx.vstack(
        rx.hstack(
            rx.icon("layers", size=16),
            rx.text("Select Traits", size="3", weight="bold"),
            rx.text(
                "Choose traits to compute PRS for all associated scoring models.",
                size="2",
                color="gray",
            ),
            spacing="2",
            align="center",
        ),
        rx.hstack(
            rx.button(
                rx.icon("list-checks", size=14),
                "Select Filtered",
                on_click=PRSTraitState.select_filtered_traits,
                variant="outline",
                size="2",
                disabled=~PRSTraitState.traits_loaded,  # type: ignore[operator]
            ),
            rx.button(
                "Clear Selection",
                on_click=PRSTraitState.deselect_all_traits,
                variant="outline",
                color_scheme="gray",
                size="2",
                disabled=PRSTraitState.selected_traits.length() == 0,  # type: ignore[operator]
            ),
            rx.spacer(),
            rx.cond(
                PRSTraitState.selected_traits.length() > 0,  # type: ignore[operator]
                rx.hstack(
                    rx.badge(
                        rx.text(PRSTraitState.selected_traits.length(), " traits"),  # type: ignore[operator]
                        color_scheme="blue",
                        size="2",
                    ),
                    rx.badge(
                        rx.text(PRSTraitState.trait_selected_pgs_ids.length(), " PGS IDs"),  # type: ignore[operator]
                        color_scheme="green",
                        size="2",
                    ),
                    spacing="2",
                ),
            ),
            wrap="wrap",
            spacing="2",
            align="center",
            width="100%",
        ),
        rx.cond(
            PRSTraitState.traits_loaded,
            rx.vstack(
                lazyframe_grid_stats_bar(PRSTraitState),
                data_grid_scroll_container(
                    lazyframe_grid(
                        PRSTraitState,
                        height="400px",
                        density="compact",
                        column_header_height=56,
                        checkbox_selection=True,
                    ),
                ),
                width="100%",
                spacing="2",
            ),
            rx.hstack(
                rx.spinner(size="3"),
                rx.text("Loading traits from PGS Catalog...", size="2", color="gray"),
                spacing="2",
                align="center",
                padding="16px",
            ),
        ),
        spacing="3",
        width="100%",
    )


def _prs_tab_content() -> rx.Component:
    """Content for the PRS tab.

    Compose the reusable PRS controls locally so the result grid can use a
    row-count-based height instead of the fixed 500px height in `prs_section`.
    Supports both trait-grouped (default) and individual PRS selection modes.
    """
    return rx.el.div(
        _tab_info_message(
            UploadState.show_prs_tab_info,
            UploadState.close_prs_tab_info,
            "chart-bar",
            "Polygenic Risk Scores from the PGS Catalog",
            "A PRS combines many DNA variants into one score using weights from a published model. We import the full PGS Catalog here, so you can search available scores, pick relevant models, and compute them for the selected genome.",
        ),
        rx.theme(
            rx.vstack(
                rx.hstack(
                    prs_build_selector(PRSState),
                    rx.separator(orientation="vertical", size="2"),
                    prs_ancestry_selector(PRSState),
                    rx.spacer(),
                    _prs_mode_toggle(),
                    spacing="4",
                    align="center",
                    wrap="wrap",
                    width="100%",
                ),
                rx.cond(
                    PRSState.prs_selection_mode == "traits",
                    _prs_trait_selector(),
                    prs_scores_selector(PRSState),
                ),
                prs_compute_button(PRSState),
                rx.checkbox(
                    "Force recompute (ignore saved results)",
                    checked=PRSState.prs_force_recompute,
                    on_change=PRSState.set_prs_force_recompute,
                    size="1",
                    color_scheme="gray",
                ),
                prs_progress_section(PRSState),
                _prs_results_content(),
                width="100%",
                spacing="4",
            ),
            has_background=False,
        ),
        id="segment-prs",
    )


def _annotated_files_tab_content() -> rx.Component:
    """Content for the Annotated Files tab: output data cards and inline preview."""
    return rx.el.div(
        _tab_info_message(
            UploadState.show_annotated_files_tab_info,
            UploadState.close_annotated_files_tab_info,
            "folder-output",
            "Annotated files created by your analysis",
            "Each file shows which module produced it. You can open any result in the data grid to explore the annotated variants with search, sorting, and filtering options.",
        ),
        _data_files_content(),
        _output_preview_grid(),
        id="segment-annotated-files",
    )


def _reports_tab_content() -> rx.Component:
    """Content for the Reports tab: generated HTML reports."""
    return rx.el.div(
        _tab_info_message(
            UploadState.show_reports_tab_info,
            UploadState.close_reports_tab_info,
            "file-text",
            "Readable summaries",
            "Reports turn the output tables into a browser-friendly view so you can explore the main matches without opening parquet files.",
        ),
        _reports_content(),
        id="segment-reports",
    )


def _latest_run_status_card() -> rx.Component:
    """Compact card under the New Analysis form showing the most recently started run.

    Gives the user immediate feedback after clicking Run. Highlights with a yellow border + spinner
    while the run is still RUNNING/QUEUED/STARTING.
    """
    last = UploadState.last_run_for_file
    last_id = UploadState.latest_run_id
    is_running = UploadState.selected_file_is_running
    dagster_url = UploadState.dagster_web_url + "/runs/" + last_id

    return rx.cond(
        UploadState.has_last_run,
        rx.el.div(
            rx.el.div(
                rx.cond(
                    is_running,
                    fomantic_icon("loader-circle", size=16, color="#fbbd08"),
                    fomantic_icon("history", size=16, color="#2185d0"),
                ),
                rx.el.span(
                    rx.cond(is_running, "Run in progress", "Latest run"),
                    style={"fontWeight": "700", "marginLeft": "8px", "fontSize": "1.05rem"},
                ),
                run_status_badge(last["status"].to(str)),
                rx.el.span(
                    last["started_at"].to(str),
                    style={"marginLeft": "10px", "color": "#666", "fontSize": "0.95rem", "flex": "1"},
                ),
                rx.el.span(
                    last["modules"].to(list).length(),
                    " modules",
                    class_name="ui blue label",
                    style={"marginLeft": "8px"},
                ),
                style={"display": "flex", "alignItems": "center", "gap": "6px", "flexWrap": "wrap"},
            ),
            rx.el.div(
                rx.el.button(
                    fomantic_icon("history", size=12),
                    " View Annotated Files",
                    on_click=lambda: UploadState.view_run_in_results(last_id),
                    class_name="ui green button",
                    style={"display": "inline-flex", "alignItems": "center", "gap": "6px"},
                ),
                rx.el.a(
                    fomantic_icon("external-link", size=12),
                    " Dagster",
                    href=dagster_url,
                    target="_blank",
                    class_name="ui basic button",
                    style={"display": "inline-flex", "alignItems": "center", "gap": "6px", "marginLeft": "8px"},
                ),
                style={"marginTop": "10px"},
            ),
            class_name=rx.cond(
                is_running,
                "ui yellow segment",
                "ui segment",
            ),
            style={"marginTop": "16px", "padding": "14px 16px"},
            id="segment-latest-run-status",
        ),
        rx.fragment(),
    )


def _analysis_tab_content() -> rx.Component:
    """Content for the Analysis tab: module selection, start button, and latest-run status."""
    return rx.el.div(
        _tab_info_message(
            UploadState.show_analysis_tab_info,
            UploadState.close_analysis_tab_info,
            "plus-circle",
            "Choose what to compare",
            "Pick one or more annotation modules, then run the pipeline. The tool joins your cleaned variant table with those module databases and saves the results.",
        ),
        new_analysis_section(),
        _latest_run_status_card(),
        id="segment-new-analysis",
    )


def right_panel_run_view() -> rx.Component:
    """
    Run-centric right panel organized as flat horizontal tabs:
    Input | PRS | Annotated Files | Reports | New Analysis.
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
        # Tabbed content (only when a file is selected)
        rx.cond(
            UploadState.has_selected_file,
            rx.fragment(
                _right_panel_tab_menu(),
                rx.el.div(
                    rx.match(
                        UploadState.right_panel_active_tab,
                        ("input", _input_tab_content()),
                        ("prs", _prs_tab_content()),
                        ("annotated_files", _annotated_files_tab_content()),
                        ("reports", _reports_tab_content()),
                        ("analysis", _analysis_tab_content()),
                        _input_tab_content(),  # default
                    ),
                    class_name="ui bottom attached segment",
                    style={"padding": "16px"},
                    id="right-panel-tab-content",
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

@rx.page(route="/annotate", title="Annotate | Just DNA Lite", on_load=UploadState.on_load)
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
