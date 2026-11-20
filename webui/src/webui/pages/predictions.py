"""The Predictions tab: run a genome prediction model on the selected sample and open its reports.

One card per model in ``PREDICTION_MODELS`` (today KronGenome F), the variant set (the variants the
sample's analysis matched, or a region), a cap, and the Run button. A prediction writes its own report
into the sample's ``reports/`` folder, so it also appears in the Reports tab; the newest ones are
linked here too. In immutable (public demo) mode the Run control is hidden: a run holds a CPU for
many minutes, which a shared demo server cannot offer to every visitor.
"""

from __future__ import annotations

import reflex as rx

from webui.components.layout import fomantic_icon
from webui.predictions_state import MAX_VARIANTS_LIMIT, PredictionState
from webui.state import UploadState


def _model_card(model: rx.Var[dict]) -> rx.Component:
    selected = PredictionState.model_id == model["id"].to(str)
    return rx.el.div(
        rx.el.div(
            fomantic_icon("dna", size=22, color=rx.cond(selected, "#6435c9", "#888")),
            rx.el.strong(model["title"].to(str), style={"fontSize": "1.1rem"}),
            rx.el.span(model["licence"].to(str), class_name="ui mini basic label"),
            rx.el.span("Research model", class_name="ui mini yellow label"),
            style={"display": "flex", "alignItems": "center", "gap": "8px", "flexWrap": "wrap"},
        ),
        rx.el.p(model["summary"].to(str), style={"margin": "6px 0 4px", "color": "#444"}),
        rx.el.a(
            "Model card",
            href=model["card_url"].to(str),
            target="_blank",
            rel="noopener noreferrer",
            style={"fontSize": "0.9rem"},
        ),
        on_click=PredictionState.set_model_id(model["id"].to(str)),
        class_name=rx.cond(selected, "ui raised segment", "ui segment"),
        style={
            "cursor": "pointer",
            "borderLeft": rx.cond(selected, "4px solid #6435c9", "4px solid transparent"),
            "marginBottom": "10px",
        },
    )


def _variant_set_choice() -> rx.Component:
    return rx.el.div(
        rx.el.label("Which variants", style={"fontWeight": "700", "display": "block", "marginBottom": "6px"}),
        rx.segmented_control.root(
            rx.segmented_control.item("Found by your analysis", value="annotated"),
            rx.segmented_control.item("A region", value="region"),
            value=PredictionState.variant_set,
            on_change=PredictionState.set_variant_set,
        ),
        rx.cond(
            PredictionState.uses_region,
            rx.el.div(
                rx.el.div(
                    rx.el.input(
                        value=PredictionState.region,
                        on_change=PredictionState.set_region,
                        placeholder="7:117,559,000-117,560,000",
                    ),
                    class_name="ui input",
                    style={"width": "100%", "maxWidth": "360px"},
                ),
                rx.el.div(
                    "Every variant in your file inside this stretch, at most ",
                    PredictionState.max_region_text,
                    " bases, GRCh38 positions.",
                    style={"color": "#666", "fontSize": "0.9rem", "marginTop": "4px"},
                ),
                rx.cond(
                    PredictionState.region_error != "",
                    rx.el.div(PredictionState.region_error, class_name="ui pointing red basic label"),
                    rx.fragment(),
                ),
                style={"marginTop": "10px"},
            ),
            rx.el.div(
                "The variants your latest analysis matched in its modules, most heavily weighted first.",
                style={"color": "#666", "fontSize": "0.9rem", "marginTop": "6px"},
            ),
        ),
        style={"marginBottom": "14px"},
    )


def _cap_input() -> rx.Component:
    return rx.el.div(
        rx.el.label("Score at most", style={"fontWeight": "700", "marginRight": "8px"}),
        rx.el.div(
            rx.el.input(
                type="number",
                min=1,
                max=MAX_VARIANTS_LIMIT,
                value=PredictionState.max_variants,
                on_change=PredictionState.set_max_variants,
                style={"width": "90px"},
            ),
            class_name="ui mini input",
        ),
        rx.el.span(
            " variants. Each takes about a minute and a half on a computer without a graphics card.",
            style={"color": "#666", "fontSize": "0.9rem", "marginLeft": "8px"},
        ),
        style={"display": "flex", "alignItems": "center", "flexWrap": "wrap", "marginBottom": "16px"},
    )


def _run_controls() -> rx.Component:
    is_running = UploadState.selected_file_is_running
    last = UploadState.last_run_for_file
    return rx.cond(
        UploadState.is_immutable_mode,
        rx.el.div(
            fomantic_icon("info circle", size=18),
            " Predictions are turned off in this public demo: each run holds a processor for many minutes.",
            class_name="ui message",
        ),
        rx.el.div(
            rx.cond(
                UploadState.selected_build_unsupported != "",
                rx.el.div(UploadState.selected_build_unsupported, class_name="ui warning message"),
                rx.fragment(),
            ),
            rx.el.button(
                rx.cond(is_running, "Run in progress...", "Run prediction"),
                rx.cond(is_running, fomantic_icon("spinner", size=16), fomantic_icon("play", size=16)),
                # No disabled=: the handler refuses a second run, a bad region or an unsupported build
                # with a toast, and a disabled primary button reads as pressed.
                on_click=PredictionState.start_prediction_run,
                class_name=rx.cond(
                    is_running,
                    "ui yellow right labeled icon large button fluid",
                    "ui primary right labeled icon large button fluid",
                ),
                id="start-prediction-button",
            ),
            rx.cond(
                is_running,
                rx.el.div(
                    "A run is in progress for this sample. ",
                    rx.el.a(
                        "Open it in Dagster",
                        href=UploadState.dagster_web_url + "/runs/" + UploadState.latest_run_id,
                        target="_blank",
                    ),
                    style={"marginTop": "8px", "color": "#666"},
                ),
                rx.cond(
                    last["status"].to(str) == "FAILURE",
                    rx.el.div(
                        "The latest run for this sample failed. ",
                        rx.el.a(
                            "See why in Dagster",
                            href=UploadState.dagster_web_url + "/runs/" + UploadState.latest_run_id,
                            target="_blank",
                        ),
                        style={"marginTop": "8px", "color": "#db2828"},
                    ),
                    rx.fragment(),
                ),
            ),
        ),
    )


def _report_link(report: rx.Var[dict]) -> rx.Component:
    view_url = (
        UploadState.backend_api_url + "/api/report/"
        + UploadState.safe_user_id + "/"
        + report["sample_name"].to(str) + "/"
        + report["name"].to(str)
    )
    return rx.cond(
        report["name"].to(str).startswith(PredictionState.selected_model["output_stem"]),
        rx.el.a(
            fomantic_icon("file alternate outline", size=16),
            rx.el.span(report["name"].to(str)),
            rx.el.span(report["materialized_at"].to(str), style={"color": "#888", "marginLeft": "auto"}),
            href=view_url,
            target="_blank",
            class_name="item",
            style={"display": "flex", "alignItems": "center", "gap": "8px"},
        ),
        rx.fragment(),
    )


def _reports_list() -> rx.Component:
    return rx.el.div(
        rx.el.h4("Prediction reports for this sample", class_name="ui header", style={"marginTop": "20px"}),
        rx.el.div(
            rx.foreach(UploadState.report_files, _report_link),
            class_name="ui relaxed divided list",
        ),
        rx.el.div(
            "Newest first. They also appear in the Reports tab.",
            style={"color": "#888", "fontSize": "0.85rem"},
        ),
    )


def predictions_tab_content() -> rx.Component:
    """Content of the Predictions tab."""
    return rx.el.div(
        rx.el.p(
            "A prediction model reads the DNA around each of your variants and estimates how the variant "
            "changes splicing, how open the DNA is, and other cell signals. These are predictions from a "
            "research model, not measurements and not medical advice. Each run writes its own report.",
            style={"color": "#444", "marginBottom": "14px"},
        ),
        rx.el.label("Model", style={"fontWeight": "700", "display": "block", "marginBottom": "6px"}),
        rx.foreach(PredictionState.model_options, _model_card),
        _variant_set_choice(),
        _cap_input(),
        _run_controls(),
        _reports_list(),
        id="segment-predictions",
    )
