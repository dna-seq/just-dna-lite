from __future__ import annotations

import reflex as rx

from webui.state import AuthState

# DaisyUI inspired classes from AGENTS.md
DAISY_CARD = "card card-bordered bg-base-100 p-8 rounded-xl shadow-md border-base-300"
DAISY_BUTTON_PRIMARY = "btn btn-primary btn-lg rounded-xl font-black uppercase tracking-tight shadow-md"
DAISY_INPUT = "input input-bordered input-lg rounded-xl"
DAISY_ALERT = "alert shadow-md border border-base-300 rounded-xl"
DAISY_BADGE = "badge badge-outline p-4 font-bold rounded-lg"


def login_form() -> rx.Component:
    return rx.form(
        rx.hstack(
            rx.input(
                placeholder="Email",
                name="email",
                type="email",
                class_name="input input-bordered input-md font-bold",
                width="200px",
            ),
            rx.button(
                "Sign in", 
                type="submit", 
                class_name="btn btn-primary btn-md font-black uppercase shadow-sm"
            ),
            spacing="3",
            align="center",
        ),
        on_submit=AuthState.login,
    )


def nav_item(text: str, icon: str, href: str) -> rx.Component:
    return rx.link(
        rx.center(
            rx.hstack(
                rx.icon(icon, size=20, class_name="text-primary"),
                rx.text(text, class_name="font-black uppercase tracking-widest text-xs"),
                align="center",
                spacing="2",
            ),
            class_name="h-full px-8 hover:bg-base-200 transition-all border-r border-base-300 active:bg-base-300 cursor-pointer",
        ),
        href=href,
        underline="none",
        class_name="text-base-content h-full block",
    )


def topbar() -> rx.Component:
    return rx.box(
        rx.flex(
            # Brand section
            rx.link(
                rx.center(
                    rx.hstack(
                        rx.image(
                            src="/just_dna_seq.jpg",
                            height="2.5rem",
                            width="auto",
                            class_name="rounded-md shadow-sm",
                        ),
                        rx.heading(
                            "just-dna-lite",
                            size="7",
                            weight="bold",
                            class_name="text-primary tracking-tighter",
                            style={"whiteSpace": "nowrap"},
                        ),
                        align="center",
                        spacing="3",
                    ),
                    class_name="h-full px-8 border-r border-base-300 hover:bg-base-200 transition-all",
                ),
                href="/",
                underline="none",
                class_name="h-full block",
            ),
            
            # Nav section
            rx.hstack(
                spacing="0",
                align="stretch",
                class_name="h-full",
            ),
            
            rx.spacer(),
            
            # Auth section
            rx.box(
                rx.cond(
                    AuthState.is_authenticated,
                    rx.hstack(
                        rx.center(
                            rx.text(AuthState.user_email, weight="bold", class_name="text-sm px-6"),
                            class_name="h-full border-l border-base-300",
                        ),
                        rx.button(
                            rx.hstack(rx.icon("log-out", size=20), rx.text("Logout"), spacing="2"),
                            class_name="btn btn-primary btn-lg h-full rounded-none border-l border-base-300 hover:bg-error transition-all font-black uppercase shadow-none border-y-0",
                            on_click=AuthState.logout,
                        ),
                        spacing="0",
                        align="stretch",
                        class_name="h-full",
                    ),
                    rx.center(
                        login_form(),
                        class_name="h-full px-8 border-l border-base-300",
                    ),
                ),
                class_name="h-full",
            ),
            width="100%",
            align="stretch",
            justify="between",
            class_name="h-full flex",
        ),
        class_name="bg-base-100 border-b-4 border-primary sticky top-0 z-[100] shadow-md h-20",
        width="100%",
    )


def template(*children: rx.Component) -> rx.Component:
    return rx.box(
        topbar(),
        rx.box(
            rx.scroll_area(
                rx.box(
                    *children,
                    padding_y="16",
                    padding_x="8",
                    width="100%",
                    max_width="6xl", # Increased from 4xl for better dashboard layout
                    class_name="mx-auto",
                ),
                width="100%",
                height="calc(100vh - 80px)", 
            ),
            width="100%",
            flex="1",
            class_name="bg-base-200",
        ),
        width="100%",
        min_height="100vh",
        class_name="flex flex-col font-sans",
        custom_attrs={"data-theme": "light"},
    )
