from __future__ import annotations

import reflex as rx

from webui.state import AuthState


def login_form() -> rx.Component:
    return rx.form(
        rx.hstack(
            rx.input(
                placeholder="Email",
                name="email",
                type="email",
                size="1",
                width="150px",
            ),
            rx.button("Sign in", type="submit", size="1"),
            spacing="2",
            align="center",
        ),
        on_submit=AuthState.login,
    )


def topbar() -> rx.Component:
    return rx.hstack(
        rx.hstack(
            rx.image(
                src="/just_dna_seq.jpg",
                height="2rem",
                width="auto",
                border_radius="20%",
            ),
            rx.heading("just-dna-lite", size="5", weight="bold"),
            align="center",
            spacing="2",
            min_width="180px",
        ),
        rx.spacer(),
        rx.cond(
            AuthState.is_authenticated,
            rx.hstack(
                rx.text(AuthState.user_email, size="2", weight="medium"),
                rx.button(
                    "Logout",
                    size="1",
                    variant="ghost",
                    on_click=AuthState.logout,
                ),
                spacing="3",
                align="center",
            ),
            rx.cond(
                AuthState.login_disabled,
                rx.badge("Public Mode", color_scheme="gray", variant="soft"),
                login_form(),
            ),
        ),
        padding_x="6",
        padding_y="3",
        border_bottom="1px solid var(--gray-4)",
        background_color="var(--gray-1)",
        width="100%",
        align="center",
        position="sticky",
        top="0",
        z_index="100",
    )


def sidebar_item(text: str, icon: str, href: str) -> rx.Component:
    return rx.link(
        rx.hstack(
            rx.icon(icon, size=18),
            rx.text(text, size="2", weight="medium"),
            align="center",
            spacing="3",
            padding_x="3",
            padding_y="2",
            border_radius="md",
            width="100%",
            _hover={
                "background_color": "var(--gray-3)",
            },
            transition="background-color 0.2s",
        ),
        href=href,
        width="100%",
        underline="none",
    )


def sidebar() -> rx.Component:
    return rx.vstack(
        sidebar_item("Dashboard", "layout-dashboard", "/dashboard"),
        sidebar_item("Analysis", "microscope", "/analysis"),
        sidebar_item("Jobs", "list-todo", "/jobs"),
        rx.spacer(),
        rx.divider(),
        rx.vstack(
            rx.text("v0.1.0", size="1", color_scheme="gray"),
            align="center",
            width="100%",
        ),
        width="240px",
        padding="4",
        border_right="1px solid var(--gray-4)",
        background_color="var(--gray-1)",
        height="calc(100vh - 56px)",
        spacing="2",
        align="start",
    )


def app_shell(*children: rx.Component) -> rx.Component:
    return rx.vstack(
        topbar(),
        rx.hstack(
            sidebar(),
            rx.scroll_area(
                rx.box(
                    *children,
                    padding="8",
                    width="100%",
                    max_width="1200px",
                    margin_x="auto",
                ),
                width="100%",
                height="calc(100vh - 56px)",
            ),
            width="100%",
            height="calc(100vh - 56px)",
            align="start",
            spacing="0",
            background_color="var(--gray-2)",
        ),
        width="100%",
        height="100vh",
        spacing="0",
    )
