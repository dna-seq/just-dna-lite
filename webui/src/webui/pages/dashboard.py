from __future__ import annotations

import reflex as rx

from webui.components.layout import app_shell
from webui.state import AuthState, UploadState


def upload_zone() -> rx.Component:
    return rx.vstack(
        rx.upload(
            rx.vstack(
                rx.button(
                    "Select VCF Files",
                    color_scheme="indigo",
                    variant="soft",
                ),
                rx.text(
                    "Drag and drop VCF files here or click to select",
                    size="2",
                    color_scheme="gray",
                ),
                spacing="2",
                align="center",
                padding="6",
            ),
            id="vcf_upload",
            border="1px dashed var(--gray-6)",
            border_radius="lg",
            padding="4",
            width="100%",
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
                rx.badge,
            ),
            spacing="2",
        ),
        rx.button(
            "Upload Files",
            on_click=UploadState.handle_upload(rx.upload_files(upload_id="vcf_upload")),
            loading=UploadState.uploading,
            width="100%",
        ),
        width="100%",
        spacing="4",
    )


@rx.page(route="/dashboard")
def dashboard_page() -> rx.Component:
    return app_shell(
        rx.cond(
            AuthState.is_authenticated,
            rx.vstack(
                rx.heading("Dashboard", size="6"),
                rx.text("Upload your VCF files to start annotation.", color_scheme="gray", size="2"),
                rx.divider(),
                
                rx.grid(
                    rx.card(
                        rx.vstack(
                            rx.heading("Upload VCF", size="4"),
                            upload_zone(),
                            width="100%",
                            spacing="3",
                        ),
                        flex="1",
                    ),
                    rx.card(
                        rx.vstack(
                            rx.heading("Uploaded Files", size="4"),
                            rx.list(
                                rx.foreach(
                                    UploadState.files,
                                    lambda f: rx.list_item(
                                        rx.hstack(
                                            rx.icon("file-text", size=16),
                                            rx.text(f),
                                            rx.spacer(),
                                            rx.button(
                                                rx.icon("play", size=14),
                                                size="1",
                                                variant="ghost",
                                                color_scheme="green",
                                            ),
                                            align="center",
                                            width="100%",
                                        )
                                    )
                                ),
                                width="100%",
                            ),
                            rx.cond(
                                UploadState.files.length == 0,
                                rx.text("No files uploaded yet.", size="2", color_scheme="gray"),
                            ),
                            width="100%",
                            spacing="3",
                        ),
                        flex="1",
                    ),
                    columns="2",
                    spacing="4",
                    width="100%",
                ),
                
                rx.card(
                    rx.vstack(
                        rx.heading("Recent Jobs", size="4"),
                        rx.text("No jobs running or completed yet.", size="2", color_scheme="gray"),
                        width="100%",
                        spacing="3",
                    ),
                    width="100%",
                ),
                
                spacing="6",
                width="100%",
                align="start",
            ),
            rx.cond(
                AuthState.login_disabled,
                rx.vstack(
                    rx.heading("Public Dashboard", size="6"),
                    rx.text("Login is disabled. You are viewing the public version of the app."),
                    spacing="4",
                ),
                rx.center(
                    rx.vstack(
                        rx.icon("lock", size=48, color_scheme="gray"),
                        rx.heading("Protected Content", size="6"),
                        rx.text("Please sign in using the form in the top-right corner to access your dashboard."),
                        spacing="4",
                        padding_y="12",
                    ),
                    width="100%",
                ),
            ),
        )
    )
