"""The panel for `LocalModelExplainMixin`: one button, the streamed answer, and what it was about.

Shown only when a local model is configured and the app is not in immutable mode. The answer is
plain text (`white-space: pre-wrap`), never rendered as Markdown or HTML: it comes from a model.
"""

from __future__ import annotations

from typing import Any

import reflex as rx

from webui.components.layout import fomantic_icon

_NOTE_STYLE = {"color": "#555", "fontSize": "0.92rem", "lineHeight": "1.5", "margin": "0.4rem 0 0"}


def local_explain_panel(state: Any, target: Any, what: str) -> rx.Component:
    """The local-model panel for *state* (a `LocalModelExplainMixin` state).

    Args:
        state: The state class that mixes in `LocalModelExplainMixin`.
        target: A var naming what the button explains now (e.g. the selected score), "" for none.
        what: What the question contains, in a few words, for the privacy line.
    """
    answer = rx.el.div(
        rx.el.div(
            rx.el.span("About ", style={"color": "#777"}),
            rx.el.strong(state.local_explain_subject),
            rx.cond(
                state.local_explain_model != "",
                rx.el.span(" · answered by ", state.local_explain_model, style={"color": "#777"}),
            ),
            style={"fontSize": "0.9rem", "marginBottom": "0.5rem"},
        ),
        rx.el.div(
            state.local_explain_text,
            style={"whiteSpace": "pre-wrap", "lineHeight": "1.55", "fontSize": "0.98rem"},
        ),
        rx.el.p(
            "A model's answer can be wrong even when it sounds sure. Anything medical is for a "
            "doctor or genetic counsellor to judge.",
            style=_NOTE_STYLE,
        ),
        class_name="ui segment",
        style={"marginTop": "0.8rem"},
    )
    body = rx.el.div(
        rx.el.div(
            fomantic_icon("microchip", size=20, color="#6435c9"),
            rx.el.span(" Explain with your local model", style={"fontWeight": "700", "fontSize": "1.05rem"}),
            style={"display": "flex", "alignItems": "center", "gap": "0.4rem"},
        ),
        rx.el.p(
            "Sends ", what, " to ", state.local_explain_where, ", the model set under Reports → Local model.",
            style=_NOTE_STYLE,
        ),
        rx.el.div(
            rx.el.button(
                fomantic_icon("comment", size=16),
                rx.cond(target != "", " Explain " + target, " Explain"),
                on_click=state.explain_with_local_model,
                class_name=rx.cond(state.local_explain_busy, "ui violet loading button", "ui violet button"),
                type="button",
            ),
            rx.cond(
                (state.local_explain_text != "") | (state.local_explain_error != ""),
                rx.el.button(
                    "Clear",
                    on_click=state.clear_local_explanation,
                    class_name="ui basic button",
                    type="button",
                ),
            ),
            style={"display": "flex", "gap": "0.5rem", "flexWrap": "wrap", "marginTop": "0.7rem"},
        ),
        rx.cond(
            state.local_explain_error != "",
            rx.el.div(state.local_explain_error, class_name="ui negative message"),
        ),
        rx.cond(state.local_explain_text != "", answer),
        class_name="ui violet segment",
    )
    return rx.el.div(
        rx.cond(state.local_explain_ready, body),
        on_mount=state.refresh_local_explain,
        style={"width": "100%"},
    )
