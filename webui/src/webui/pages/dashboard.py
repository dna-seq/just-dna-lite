from __future__ import annotations

import reflex as rx

from webui.components.layout import template, fomantic_icon
from webui.state import AuthState, UploadState


def upload_zone() -> rx.Component:
    """Upload zone for VCF files using Fomantic UI styling."""
    return rx.el.div(
        rx.upload(
            rx.el.div(
                fomantic_icon("cloud-upload", size=80, style={"color": "#2185d0", "marginBottom": "20px"}),
                rx.el.button(
                    "Select VCF Files",
                    class_name="ui primary massive button",
                    id="select-vcf-files-button",
                ),
                rx.el.p(
                    "Drag and drop VCF files here or click to select",
                    style={"fontSize": "1.5rem", "color": "#666", "fontWeight": "bold", "marginTop": "20px"},
                ),
                style={"textAlign": "center", "padding": "60px"},
            ),
            id="vcf_upload",
            style={
                "border": "4px dashed #ccc",
                "borderRadius": "1.5rem",
                "backgroundColor": "#fff",
                "cursor": "pointer",
                "width": "100%",
            },
            multiple=True,
            accept={
                "application/vcf": [".vcf", ".vcf.gz"],
                "text/vcf": [".vcf", ".vcf.gz"],
                "application/gzip": [".vcf.gz"],
            },
        ),
        rx.el.div(
            rx.foreach(
                rx.selected_files("vcf_upload"),
                lambda f: rx.el.div(
                    f, 
                    class_name="ui blue large label",
                    style={"margin": "5px"},
                ),
            ),
            style={"display": "flex", "flexWrap": "wrap", "marginTop": "20px"},
            id="selected-files-list",
        ),
        rx.el.button(
            fomantic_icon("upload", size=32),
            " Upload & Register",
            on_click=UploadState.handle_upload(rx.upload_files(upload_id="vcf_upload")),
            loading=UploadState.uploading,
            class_name="ui primary massive button fluid",
            id="upload-register-button",
            style={"height": "6rem", "fontSize": "1.5rem", "marginTop": "20px"},
        ),
        class_name="ui segment",
        style={"width": "100%"},
        id="upload-zone-container",
    )


def module_selector() -> rx.Component:
    """Component for selecting which HF modules to use for annotation."""
    return rx.el.div(
        rx.el.div(
            rx.el.h3(
                fomantic_icon("boxes", size=24),
                " Annotation Modules",
                class_name="ui header",
                style={"flex": "1"},
            ),
            rx.el.div(
                rx.el.button(
                    "All",
                    on_click=UploadState.select_all_modules,
                    class_name="ui mini button",
                    id="dashboard-select-all-modules",
                ),
                rx.el.button(
                    "None",
                    on_click=UploadState.deselect_all_modules,
                    class_name="ui mini button",
                    id="dashboard-deselect-all-modules",
                ),
                class_name="ui buttons",
            ),
            style={"display": "flex", "alignItems": "center", "width": "100%"},
        ),
        rx.el.p(
            "Select which modules to use for HF annotation:",
            style={"color": "#666", "marginBottom": "10px"},
        ),
        rx.el.div(
            rx.foreach(
                UploadState.available_modules,
                lambda m: rx.el.button(
                    m,
                    on_click=UploadState.toggle_module(m),
                    class_name=rx.cond(
                        UploadState.selected_modules.contains(m),
                        "ui info small button",
                        "ui basic small button",
                    ),
                    id=rx.Var.create("module-button-") + m.to(str),
                    style={"margin": "2px"},
                ),
            ),
            style={"display": "flex", "flexWrap": "wrap"},
            id="dashboard-module-list",
        ),
        class_name="ui secondary segment",
        style={"marginTop": "20px", "marginBottom": "20px"},
        id="dashboard-module-selector",
    )


def sample_catalog() -> rx.Component:
    """List of uploaded samples using Fomantic UI."""
    return rx.el.div(
        rx.el.div(
            rx.el.h2(
                fomantic_icon("files", size=32),
                " Sample Catalog",
                class_name="ui header",
                style={"flex": "1"},
            ),
            rx.el.button(
                fomantic_icon("refresh-cw", size=24),
                on_click=UploadState.on_load,
                class_name="ui massive icon button",
                id="dashboard-refresh-samples-button",
            ),
            style={"display": "flex", "alignItems": "center", "width": "100%", "marginBottom": "20px"},
        ),
        module_selector(),
        rx.el.div(
            rx.foreach(
                UploadState.files,
                lambda f: rx.el.div(
                    rx.el.div(
                        fomantic_icon("file-text", size=40, style={"color": "#2185d0"}),
                        rx.el.div(
                            rx.el.div(f, class_name="header", style={"fontSize": "1.5rem", "fontWeight": "bold"}),
                            rx.el.div(
                                UploadState.file_statuses[f],
                                class_name=rx.match(
                                    UploadState.file_statuses[f],
                                    ("completed", "ui green label"),
                                    ("running", "ui blue label"),
                                    ("pending", "ui yellow label"),
                                    ("error", "ui red label"),
                                    "ui grey label"
                                ),
                            ),
                            class_name="content",
                            style={"marginLeft": "15px", "flex": "1"},
                        ),
                        rx.el.div(
                            rx.el.button(
                                fomantic_icon("database", size=20),
                                " Ensembl",
                                on_click=lambda: UploadState.run_annotation(f),
                                disabled=UploadState.file_statuses[f] == "running",
                                class_name="ui green button",
                                style={"marginBottom": "5px"},
                                id=rx.Var.create("ensembl-button-") + f.to(str),
                            ),
                            rx.el.button(
                                fomantic_icon("boxes", size=20),
                                " HF Modules",
                                on_click=lambda: UploadState.run_hf_annotation(f),
                                class_name="ui blue button",
                                id=rx.Var.create("hf-modules-button-") + f.to(str),
                            ),
                            style={"display": "flex", "flexDirection": "column"},
                        ),
                        style={"display": "flex", "alignItems": "center", "padding": "20px"},
                    ),
                    class_name="ui raised segment",
                    style={"marginBottom": "15px"},
                    id=rx.Var.create("sample-segment-") + f.to(str),
                )
            ),
            class_name="ui segments",
            style={"border": "none", "boxShadow": "none"},
            id="sample-catalog-list",
        ),
        rx.cond(
            UploadState.files.length() == 0,
            rx.el.div(
                fomantic_icon("inbox", size=100, style={"color": "#eee"}),
                rx.el.h2("No files uploaded yet.", style={"color": "#ccc", "fontStyle": "italic"}),
                class_name="ui placeholder segment",
                style={"textAlign": "center", "padding": "60px"},
                id="empty-sample-catalog",
            ),
        ),
        class_name="ui segment",
        id="sample-catalog-container",
    )


def dagster_section() -> rx.Component:
    """External link to Dagster UI using Fomantic UI."""
    return rx.el.div(
        rx.el.h2(
            fomantic_icon("activity", size=32),
            " Pipeline Engine",
            class_name="ui header",
        ),
        rx.el.p(
            "Powered by Dagster. All annotation runs are orchestrated and tracked for full data lineage.",
            style={"fontSize": "1.2rem", "color": "#666"},
        ),
        rx.el.div(
            rx.el.a(
                rx.el.button(
                    fomantic_icon("external-link", size=24),
                    " Open Dagster UI",
                    class_name="ui positive massive button",
                ),
                href=UploadState.dagster_web_url,
                target="_blank",
            ),
            rx.el.div(
                "Daemon Running",
                class_name="ui green circular label",
                style={"marginLeft": "20px", "fontSize": "1.2rem", "padding": "15px"},
            ),
            style={"display": "flex", "alignItems": "center", "marginTop": "20px"},
        ),
        class_name="ui segment positive",
        style={"marginTop": "40px"},
    )


@rx.page(route="/dashboard", on_load=UploadState.on_load)
def dashboard_page() -> rx.Component:
    """Dashboard page with Fomantic UI layout."""
    return template(
        rx.el.div(
            rx.el.div(
                fomantic_icon("dna", size=64, style={"color": "#2185d0"}),
                rx.el.div(
                    rx.el.h1("Genomic Dashboard", class_name="ui header", style={"fontSize": "3rem", "margin": "0"}),
                    rx.el.p(
                        "Sequencing ➔ Upload ➔ Annotation ➔ Interpretation", 
                        style={"fontSize": "1.5rem", "color": "#999", "fontStyle": "italic", "fontWeight": "bold"}
                    ),
                    style={"marginLeft": "20px"},
                ),
                style={"display": "flex", "alignItems": "center", "marginBottom": "40px"},
                id="dashboard-header",
            ),
            
            rx.el.div(
                rx.el.div(
                    rx.el.div(
                        rx.el.h2(
                            fomantic_icon("cloud-upload", size=32),
                            " Upload VCF",
                            class_name="ui header",
                        ),
                        rx.el.div(class_name="ui divider"),
                        upload_zone(),
                        class_name="column",
                        id="dashboard-upload-column",
                    ),
                    rx.el.div(
                        sample_catalog(),
                        class_name="column",
                        id="dashboard-catalog-column",
                    ),
                    class_name="row",
                ),
                class_name="ui two column stackable grid",
                id="dashboard-grid",
            ),
            
            dagster_section(),
            style={"width": "100%"},
            id="dashboard-main-container",
        )
    )
