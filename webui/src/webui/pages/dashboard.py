from __future__ import annotations

import reflex as rx

from webui.components.layout import template, DAISY_CARD, DAISY_BUTTON_PRIMARY, DAISY_BADGE
from webui.state import AuthState, UploadState


def upload_zone() -> rx.Component:
    return rx.vstack(
        rx.upload(
            rx.vstack(
                rx.icon("cloud-upload", size=80, class_name="text-primary mb-4"),
                rx.button(
                    "Select VCF Files",
                    class_name="btn btn-primary btn-lg px-12",
                ),
                rx.text(
                    "Drag and drop VCF files here or click to select",
                    class_name="text-xl text-base-content/60 font-bold mt-4",
                ),
                spacing="0",
                align="center",
            ),
            id="vcf_upload",
            class_name="border-4 border-dashed border-base-300 rounded-3xl bg-base-100 hover:border-primary transition-all hover:bg-base-200 cursor-pointer w-full p-20",
            multiple=True,
            accept={
                "application/vcf": [".vcf", ".vcf.gz"],
                "text/vcf": [".vcf", ".vcf.gz"],
                "application/gzip": [".vcf.gz"],
            },
        ),
        rx.hstack(
            rx.foreach(
                rx.selected_files("vcf_upload"),
                lambda f: rx.badge(
                    f, 
                    class_name="badge badge-primary badge-lg p-6 font-bold rounded-xl"
                ),
            ),
            spacing="4",
            flex_wrap="wrap",
            width="100%",
        ),
        rx.button(
            rx.hstack(
                rx.icon("upload", size=32),
                rx.text("Upload & Register"),
                spacing="4",
            ),
            on_click=UploadState.handle_upload(rx.upload_files(upload_id="vcf_upload")),
            loading=UploadState.uploading,
            class_name=DAISY_BUTTON_PRIMARY + " w-full h-24 text-2xl shadow-2xl hover:scale-[1.02] active:scale-[0.98] transition-all",
        ),
        width="100%",
        spacing="8",
        align="stretch",
    )


def sample_catalog() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.icon("files", size=48, class_name="text-primary"),
            rx.heading("Sample Catalog", size="8", class_name="font-black"),
            rx.spacer(),
            rx.button(
                rx.icon("refresh-cw", size=24),
                on_click=UploadState.on_load,
                class_name="btn btn-ghost btn-circle btn-lg",
            ),
            spacing="4",
            align="center",
            width="100%",
        ),
        rx.divider(class_name="divider my-4"),
        rx.list(
            rx.foreach(
                UploadState.files,
                lambda f: rx.list_item(
                    rx.hstack(
                        rx.icon("file-text", size=40, class_name="text-primary"),
                        rx.vstack(
                            rx.text(f, class_name="font-black text-2xl tracking-tight"),
                            rx.badge(
                                UploadState.file_statuses[f],
                                class_name=rx.match(
                                    UploadState.file_statuses[f],
                                    ("materialized", "badge badge-success badge-lg p-4 font-bold"),
                                    ("running", "badge badge-info badge-lg p-4 font-bold animate-pulse"),
                                    ("pending", "badge badge-warning badge-lg p-4 font-bold"),
                                    ("completed", "badge badge-success badge-lg p-4 font-bold"),
                                    ("error", "badge badge-error badge-lg p-4 font-bold"),
                                    "badge badge-ghost badge-lg p-4 font-bold"
                                ),
                            ),
                            align_items="start",
                            spacing="2",
                        ),
                        rx.spacer(),
                        rx.button(
                            rx.cond(
                                UploadState.file_statuses[f] == "running",
                                rx.icon("loader-circle", size=32, class_name="animate-spin"),
                                rx.hstack(
                                    rx.icon("play", size=32),
                                    rx.text("Run"),
                                    spacing="3",
                                ),
                            ),
                            on_click=UploadState.run_annotation(f),
                            disabled=UploadState.file_statuses[f] == "running",
                            class_name="btn btn-success btn-lg h-20 px-8 text-xl shadow-lg hover:shadow-xl active:scale-95 transition-all",
                        ),
                        align="center",
                        width="100%",
                        class_name="p-8 bg-base-100 border-4 border-base-200 rounded-2xl mb-6 hover:border-primary transition-all shadow-sm",
                    )
                )
            ),
            class_name="w-full",
        ),
        rx.cond(
            UploadState.files.length == 0,
            rx.vstack(
                rx.icon("inbox", size=100, class_name="text-base-content/10"),
                rx.text("No files uploaded yet.", class_name="text-3xl text-base-content/20 italic font-black"),
                spacing="6",
                padding="20",
                align="center",
                width="100%",
            ),
        ),
        width="100%",
        spacing="6",
        align="stretch",
    )


def dagster_section() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon("activity", size=48, class_name="text-success"),
                rx.heading("Pipeline Engine", size="8", class_name="font-black"),
                spacing="4",
                align="center",
            ),
            rx.text(
                "Powered by Dagster. All annotation runs are orchestrated and tracked for full data lineage.",
                class_name="text-xl text-base-content/70 font-medium",
            ),
            rx.hstack(
                rx.link(
                    rx.button(
                        rx.hstack(
                            rx.icon("external-link", size=28),
                            rx.text("Open Dagster UI"),
                            spacing="3",
                        ),
                        class_name="btn btn-outline btn-success btn-lg px-8 rounded-xl font-black",
                    ),
                    href="http://localhost:3005",
                    is_external=True,
                ),
                rx.badge("Daemon Running", class_name="badge badge-success badge-outline p-6 text-lg font-black rounded-xl"),
                spacing="6",
                align="center",
            ),
            width="100%",
            spacing="6",
            align="stretch",
        ),
        class_name=DAISY_CARD + " border-success/30 bg-success/5 mt-12",
        width="100%",
    )


@rx.page(route="/dashboard", on_load=UploadState.on_load)
def dashboard_page() -> rx.Component:
    return template(
        rx.vstack(
            rx.hstack(
                rx.icon("dna", size=64, class_name="text-primary"),
                rx.vstack(
                    rx.heading("Genomic Dashboard", size="9", class_name="text-primary font-black uppercase tracking-tight"),
                    rx.text(
                        "Sequencing ➔ Upload ➔ Annotation ➔ Interpretation", 
                        class_name="text-2xl text-base-content/40 font-black italic"
                    ),
                    align_items="start",
                    spacing="0",
                ),
                spacing="6",
                align="center",
                width="100%",
                margin_bottom="12",
            ),
            
            rx.grid(
                rx.box(
                    rx.vstack(
                        rx.hstack(
                            rx.icon("cloud-upload", size=48, class_name="text-primary"),
                            rx.heading("Upload VCF", size="8", class_name="font-black"),
                            spacing="4",
                            align="center",
                        ),
                        rx.divider(class_name="divider my-6"),
                        upload_zone(),
                        width="100%",
                        spacing="6",
                        align="stretch",
                    ),
                    class_name=DAISY_CARD,
                ),
                rx.box(
                    sample_catalog(),
                    class_name=DAISY_CARD,
                ),
                columns=rx.breakpoints(initial="1", lg="2"),
                spacing="8",
                width="100%",
                align_items="stretch",
            ),
            
            dagster_section(),
            
            spacing="0",
            width="100%",
            align="stretch",
        )
    )
