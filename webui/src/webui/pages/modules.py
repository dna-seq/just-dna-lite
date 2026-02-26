"""
Module Manager Page — manage module sources, upload custom DSL modules,
and interact with the Paper-to-Module AI agent.

Left Panel:  Module sources tree, editing slot with module details + actions
Right Panel: Agent chat (Module Creator AI)
"""
from __future__ import annotations

import reflex as rx

from webui.components.layout import template, two_column_layout, fomantic_icon
from webui.state import UploadState, AgentState


# ============================================================================
# MODULE SOURCE COMPONENTS
# ============================================================================

def _custom_module_item(name: rx.Var[str]) -> rx.Component:
    """Single custom module entry with load-to-slot and remove buttons."""
    return rx.el.div(
        fomantic_icon("dna", size=14, color="#a333c8"),
        rx.el.span(name, style={"flex": "1", "marginLeft": "6px", "fontSize": "0.85rem"}),
        rx.el.button(
            fomantic_icon("edit", size=12, color="#a333c8"),
            on_click=AgentState.load_custom_module_to_slot(name),
            class_name="ui mini icon button",
            style={"padding": "3px 6px", "background": "none", "border": "none", "cursor": "pointer"},
            title="Load into editing slot",
        ),
        rx.el.button(
            fomantic_icon("circle-x", size=12, color="#db2828"),
            on_click=UploadState.remove_custom_module(name),
            class_name="ui mini icon button",
            style={"padding": "3px 6px", "background": "none", "border": "none", "cursor": "pointer"},
            title="Remove module",
        ),
        style={"display": "flex", "alignItems": "center", "padding": "3px 0"},
    )


def repo_source_card(repo: rx.Var[dict]) -> rx.Component:
    """Compact card showing a module source."""
    is_local = repo["is_local"].to(bool)

    return rx.el.div(
        rx.el.div(
            rx.cond(
                is_local,
                fomantic_icon("folder-open", size=18, color="#a333c8"),
                fomantic_icon("database", size=18, color="#2185d0"),
            ),
            rx.cond(
                is_local,
                rx.el.span(
                    "Custom Modules",
                    style={"fontSize": "0.9rem", "fontWeight": "600", "marginLeft": "8px", "color": "#a333c8"},
                ),
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
            ),
            rx.cond(
                is_local,
                rx.el.span("custom", class_name="ui mini purple label", style={"marginLeft": "6px"}),
                fomantic_icon("external-link", size=12, color="#888", style={"marginLeft": "4px"}),
            ),
            rx.el.span(
                repo["module_count"].to(int),
                " modules",
                class_name="ui mini label",
                style={"marginLeft": "auto"},
            ),
            style={"display": "flex", "alignItems": "center", "width": "100%"},
        ),
        rx.cond(
            is_local,
            rx.el.div(
                rx.foreach(repo["modules"].to(list[str]), _custom_module_item),
                style={"marginTop": "6px", "paddingLeft": "26px"},
            ),
            rx.fragment(),
        ),
        style={
            "padding": "8px 12px",
            "border": rx.cond(is_local, "1px solid #d6c4e8", "1px solid #e0e0e0"),
            "borderRadius": "4px",
            "backgroundColor": rx.cond(is_local, "#faf6ff", "#f8f9fa"),
            "marginBottom": "6px",
        },
    )


# ============================================================================
# EDITING SLOT COMPONENT
# ============================================================================

def _slot_empty_state() -> rx.Component:
    """Shown when the editing slot is empty."""
    return rx.el.div(
        rx.el.div(
            fomantic_icon("inbox", size=28, color="#ccc"),
            rx.el.div(
                "No module loaded",
                style={"color": "#999", "fontSize": "0.9rem", "marginTop": "6px"},
            ),
            style={"textAlign": "center", "padding": "14px 8px 10px"},
        ),
        # Info callout
        rx.el.div(
            rx.el.i("", class_name="info circle icon", style={"color": "#a333c8", "opacity": "0.7", "marginRight": "6px", "flexShrink": "0"}),
            rx.el.span(
                "Just start chatting — the agent will create a module and load it here automatically. "
                "Upload an existing module here to edit or use it for annotation. "
                "Use the button below to register a module as an annotation source",
                style={"fontSize": "0.78rem", "color": "#7a6a8a", "lineHeight": "1.4"},
            ),
            style={
                "display": "flex",
                "alignItems": "flex-start",
                "backgroundColor": "#f3eeff",
                "border": "1px solid #d6c4e8",
                "borderRadius": "6px",
                "padding": "8px 10px",
                "marginTop": "4px",
            },
        ),
    )


def _slot_populated_state() -> rx.Component:
    """Shown when the editing slot has a module loaded."""
    return rx.el.div(
        # Module name + version badge
        rx.el.div(
            fomantic_icon("circle-check", size=16, color="#21ba45"),
            rx.el.span(
                AgentState.slot_module_name,
                style={
                    "fontSize": "0.95rem",
                    "fontWeight": "600",
                    "color": "#a333c8",
                    "marginLeft": "6px",
                },
            ),
            rx.cond(
                AgentState.slot_version > 0,
                rx.el.span(
                    "v", AgentState.slot_version.to(str),
                    class_name="ui mini purple label",
                    style={"marginLeft": "8px"},
                ),
                rx.fragment(),
            ),
            style={"display": "flex", "alignItems": "center", "marginBottom": "6px"},
        ),
        # Title
        rx.cond(
            AgentState.slot_module_title != "",
            rx.el.div(
                AgentState.slot_module_title,
                style={"fontSize": "0.85rem", "fontWeight": "500", "color": "#555", "marginBottom": "4px"},
            ),
            rx.fragment(),
        ),
        # Description
        rx.cond(
            AgentState.slot_module_description != "",
            rx.el.div(
                AgentState.slot_module_description,
                style={"fontSize": "0.8rem", "color": "#777", "marginBottom": "6px", "lineHeight": "1.3"},
            ),
            rx.fragment(),
        ),
        # File list
        rx.el.div(
            rx.foreach(
                AgentState.slot_files,
                lambda fname: rx.el.span(
                    fomantic_icon("file-text", size=11, color="#666"),
                    rx.el.span(fname, style={"marginLeft": "3px"}),
                    style={
                        "display": "inline-flex",
                        "alignItems": "center",
                        "fontSize": "0.78rem",
                        "color": "#555",
                        "marginRight": "8px",
                    },
                ),
            ),
            style={"marginBottom": "2px"},
        ),
    )


def _slot_button_bar() -> rx.Component:
    """Upload / Clear / Download button row for the editing slot."""
    return rx.el.div(
        # Upload button
        rx.upload(
            rx.el.button(
                fomantic_icon("upload", size=13),
                " Upload",
                class_name="ui mini button",
                style={"flex": "1", "cursor": "pointer"},
            ),
            id="slot_upload",
            multiple=True,
            accept={
                "text/yaml": [".yaml", ".yml"],
                "text/csv": [".csv"],
                "application/zip": [".zip"],
            },
            on_drop=AgentState.upload_to_slot(
                rx.upload_files(upload_id="slot_upload"),
            ),
            style={"display": "contents"},
        ),
        # Clear
        rx.el.button(
            fomantic_icon("trash-2", size=13),
            " Clear",
            on_click=AgentState.clear_slot,
            disabled=~AgentState.slot_is_populated,
            class_name="ui mini button",
            style={"flex": "1"},
        ),
        # Download zip
        rx.cond(
            AgentState.slot_is_populated,
            rx.el.a(
                fomantic_icon("download", size=13, color="#fff"),
                " .zip",
                href=AgentState.slot_zip_url,
                class_name="ui mini teal button",
                style={"flex": "1", "textAlign": "center"},
            ),
            rx.el.button(
                fomantic_icon("download", size=13),
                " .zip",
                disabled=True,
                class_name="ui mini button",
                style={"flex": "1"},
            ),
        ),
        style={"display": "flex", "gap": "4px", "marginTop": "8px"},
    )


def _register_button() -> rx.Component:
    """Standalone Register button between slot and module sources — visual 'push down'."""
    return rx.el.div(
        rx.el.button(
            rx.cond(
                AgentState.slot_adding,
                rx.el.i("", class_name="spinner loading icon"),
                rx.fragment(
                    fomantic_icon("arrow down", size=14),
                    " Register Module as source",
                ),
            ),
            on_click=AgentState.add_slot_module,
            disabled=~AgentState.slot_is_populated | AgentState.slot_adding,
            class_name="ui purple button",
            style={"width": "100%"},
        ),
        style={"marginBottom": "10px"},
    )


def editing_slot() -> rx.Component:
    """Editing slot card — shows module details or empty state + action buttons."""
    return rx.el.div(
        rx.el.div(
            fomantic_icon("edit", size=16, color="#a333c8"),
            rx.el.span(
                " Editing Slot",
                style={"fontSize": "0.9rem", "fontWeight": "600", "marginLeft": "4px", "color": "#555"},
            ),
            style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
        ),
        # Confirm-replace banner (shown when a custom module is selected while slot is occupied)
        rx.cond(
            AgentState.slot_replace_pending_name != "",
            rx.el.div(
                rx.el.div(
                    "Replace ",
                    rx.el.strong(AgentState.slot_module_name),
                    rx.cond(
                        AgentState.slot_version > 0,
                        rx.el.span(
                            " v", AgentState.slot_version.to(str),
                            style={"color": "#a333c8", "fontWeight": "500"},
                        ),
                        rx.fragment(),
                    ),
                    " with ",
                    rx.el.strong(AgentState.slot_replace_pending_name),
                    "?",
                    style={"fontSize": "0.82rem", "color": "#555"},
                ),
                rx.el.div(
                    rx.el.button(
                        "Replace",
                        on_click=AgentState.confirm_replace_slot,
                        class_name="ui mini red button",
                        style={"marginRight": "6px"},
                    ),
                    rx.el.button(
                        "Cancel",
                        on_click=AgentState.cancel_replace_slot,
                        class_name="ui mini button",
                    ),
                    style={"marginTop": "6px"},
                ),
                style={
                    "backgroundColor": "#fff8f0",
                    "border": "1px solid #f0c070",
                    "borderRadius": "6px",
                    "padding": "8px 10px",
                    "marginBottom": "8px",
                },
            ),
            rx.fragment(),
        ),
        # Content: empty or populated
        rx.cond(
            AgentState.slot_is_populated,
            _slot_populated_state(),
            _slot_empty_state(),
        ),
        # Button bar (always visible)
        _slot_button_bar(),
        rx.el.div(
            "Upload module_spec.yaml + variants.csv (.zip OK)",
            style={"fontSize": "0.72rem", "color": "#aaa", "marginTop": "6px"},
        ),
        class_name="ui segment",
        style={"padding": "12px", "marginBottom": "12px", "border": "1px solid #d6c4e8", "backgroundColor": "#faf6ff"},
    )


def _api_key_field(label: str, name: str, placeholder: rx.Var) -> rx.Component:
    """A single masked API key input row."""
    return rx.el.div(
        rx.el.label(
            label,
            html_for=name,
            style={"fontSize": "0.78rem", "color": "#666", "marginBottom": "3px", "display": "block"},
        ),
        rx.el.input(
            id=name,
            name=name,
            type="password",
            placeholder=placeholder,
            auto_complete="off",
            style={
                "width": "100%",
                "padding": "5px 8px",
                "border": "1px solid #ddd",
                "borderRadius": "4px",
                "fontSize": "0.82rem",
                "boxSizing": "border-box",
                "fontFamily": "monospace",
            },
        ),
        style={"marginBottom": "8px"},
    )


def _settings_pane() -> rx.Component:
    """Collapsible API key settings at the bottom of the left panel."""
    return rx.el.details(
        rx.el.summary(
            fomantic_icon("settings", size=14, color="#888"),
            rx.el.span(
                " API Keys",
                style={"fontSize": "0.85rem", "fontWeight": "600", "marginLeft": "4px", "color": "#888"},
            ),
            style={"cursor": "pointer", "display": "flex", "alignItems": "center", "userSelect": "none"},
        ),
        rx.el.form(
            rx.el.div(
                _api_key_field("Gemini (required)", "gemini_key", AgentState.settings_gemini_placeholder),
                _api_key_field("OpenAI (optional, adds GPT researcher)", "openai_key", AgentState.settings_openai_placeholder),
                _api_key_field("Anthropic (optional, adds Claude researcher)", "anthropic_key", AgentState.settings_anthropic_placeholder),
                rx.el.button(
                    fomantic_icon("save", size=13),
                    " Save",
                    type="submit",
                    class_name="ui mini button",
                    style={"width": "100%", "marginTop": "4px", "boxSizing": "border-box"},
                ),
                style={"paddingTop": "10px", "width": "100%", "boxSizing": "border-box", "overflow": "hidden"},
            ),
            on_submit=AgentState.save_api_keys,
            reset_on_submit=True,
        ),
        style={
            "padding": "8px 12px",
            "border": "1px solid #e8e8e8",
            "borderRadius": "4px",
            "backgroundColor": "#fafafa",
            "marginTop": "4px",
        },
    )


# ============================================================================
# LEFT PANEL — Sources + Editing Slot
# ============================================================================

def modules_left_panel() -> rx.Component:
    """Left panel: editing slot (top), then module sources (bottom)."""
    return rx.el.div(

        # Editing Slot — fixed at top so sources list growth doesn't push it down
        editing_slot(),

        # Register button — pushes slot contents down into module sources
        _register_button(),

        # Module Sources section
        rx.el.div(
            rx.el.div(
                fomantic_icon("database", size=16, color="#2185d0"),
                rx.el.span(
                    " Module Sources",
                    style={"fontSize": "0.95rem", "fontWeight": "600", "marginLeft": "4px", "color": "#2185d0"},
                ),
                style={"display": "flex", "alignItems": "center", "marginBottom": "10px"},
            ),
            rx.foreach(UploadState.repo_info_list, repo_source_card),
            class_name="ui segment",
            style={"padding": "12px", "marginBottom": "10px", "border": "1px solid #c5daf5", "backgroundColor": "#f4f8fe"},
        ),

        # Settings (collapsed by default)
        _settings_pane(),

        id="modules-left-panel",
    )


# ============================================================================
# AGENT CHAT COMPONENTS
# ============================================================================

_EVENT_LABEL_STYLE: dict = {
    "fontSize": "0.78rem",
    "color": "#7c6c9a",
    "display": "flex",
    "alignItems": "center",
    "gap": "5px",
}

_EVENT_DETAIL_STYLE: dict = {
    "fontSize": "0.72rem",
    "background": "#f0e8ff",
    "color": "#4a3a6a",
    "padding": "6px 8px",
    "borderRadius": "4px",
    "overflowX": "auto",
    "whiteSpace": "pre-wrap",
    "wordBreak": "break-word",
    "marginTop": "4px",
    "maxHeight": "160px",
    "overflowY": "auto",
}


def agent_event_item(event: rx.Var[dict]) -> rx.Component:
    """Render a single agent run event — collapsible when it has detail.

    Done events (type ends with _done) show a green check icon; active/info
    events show a cog or info-circle icon.
    """
    label = event["label"].to(str)
    detail = event["detail"].to(str)
    ev_type = event["type"].to(str)
    is_done = ev_type.contains("_done")
    is_tool = ev_type.contains("tool")

    icon = rx.cond(
        is_done,
        rx.el.i("", class_name="check circle icon", style={"color": "#21ba45", "fontSize": "0.75rem"}),
        rx.cond(
            is_tool,
            rx.el.i("", class_name="cog icon", style={"opacity": "0.7", "fontSize": "0.75rem"}),
            rx.el.i("", class_name="info circle icon", style={"opacity": "0.5", "fontSize": "0.75rem"}),
        ),
    )

    return rx.cond(
        detail != "",
        rx.el.details(
            rx.el.summary(icon, label, style={**_EVENT_LABEL_STYLE, "cursor": "pointer"}),
            rx.el.pre(detail, style=_EVENT_DETAIL_STYLE),
            style={"marginBottom": "3px"},
        ),
        rx.el.div(icon, label, style={**_EVENT_LABEL_STYLE, "marginBottom": "3px"}),
    )


def agent_message_bubble(msg: rx.Var[dict]) -> rx.Component:
    """Render a single chat message (user, agent, or status)."""
    role = msg["role"].to(str)
    return rx.el.div(
        rx.match(
            role,
            ("user", rx.el.div(
                msg["content"].to(str),
                style={
                    "backgroundColor": "#00b5ad",
                    "color": "#fff",
                    "padding": "10px 14px",
                    "borderRadius": "12px 12px 2px 12px",
                    "maxWidth": "80%",
                    "fontSize": "0.9rem",
                    "lineHeight": "1.4",
                    "marginLeft": "auto",
                    "whiteSpace": "pre-wrap",
                },
            )),
            ("status", rx.el.div(
                rx.el.i("", class_name="info circle icon", style={"marginRight": "6px", "opacity": "0.7"}),
                msg["content"].to(str),
                style={
                    "backgroundColor": "#f8f4ff",
                    "color": "#7c6c9a",
                    "padding": "6px 12px",
                    "borderRadius": "8px",
                    "maxWidth": "90%",
                    "fontSize": "0.8rem",
                    "lineHeight": "1.3",
                    "marginRight": "auto",
                    "fontStyle": "italic",
                    "border": "1px solid #e8dff5",
                    "display": "flex",
                    "alignItems": "center",
                },
            )),
            rx.el.div(
                rx.markdown(msg["content"].to(str)),
                style={
                    "backgroundColor": "#f1f1f1",
                    "color": "#333",
                    "padding": "10px 14px",
                    "borderRadius": "12px 12px 12px 2px",
                    "maxWidth": "85%",
                    "fontSize": "0.9rem",
                    "lineHeight": "1.5",
                    "marginRight": "auto",
                },
            ),
        ),
        style={
            "display": "flex",
            "marginBottom": "10px",
        },
    )


def agent_chat_panel() -> rx.Component:
    """Full chat panel for the Module Creator agent."""
    return rx.el.div(
        # Header
        rx.el.div(
            fomantic_icon("dna", size=22, color="#fff"),
            rx.el.span(
                rx.cond(
                    AgentState.agent_use_team,
                    " Module Creator Team",
                    " Module Creator",
                ),
                style={"fontSize": "1.1rem", "fontWeight": "600", "marginLeft": "8px", "color": "#fff", "flex": "1"},
            ),
            rx.el.button(
                fomantic_icon("trash-2", size=14, color="#fff"),
                " Clear",
                on_click=AgentState.clear_agent_chat,
                class_name="ui mini inverted button",
                style={"padding": "4px 10px", "flexShrink": "0"},
            ),
            style={
                "display": "flex",
                "alignItems": "center",
                "padding": "14px 16px",
                "marginBottom": "16px",
                "background": "linear-gradient(135deg, #a333c8, #6435c9)",
                "color": "#fff",
                "borderRadius": "6px",
                "width": "100%",
            },
        ),

        # Messages area (scrollable)
        rx.el.div(
            rx.foreach(AgentState.agent_messages, agent_message_bubble),
            rx.cond(
                AgentState.agent_processing | (AgentState.agent_events.length() > 0),
                rx.el.div(
                    # Status row: spinner while running, checkmark when done
                    rx.cond(
                        AgentState.agent_processing,
                        rx.el.div(
                            rx.el.i("", class_name="spinner loading icon", style={"fontSize": "1.2rem", "color": "#a333c8"}),
                            rx.el.span(
                                rx.cond(
                                    AgentState.agent_status != "",
                                    AgentState.agent_status,
                                    "Agent is thinking... this may take a minute.",
                                ),
                                style={"marginLeft": "8px", "color": "#888", "fontSize": "0.9rem"},
                            ),
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        rx.el.div(
                            rx.el.i("", class_name="check circle icon", style={"fontSize": "1rem", "color": "#21ba45"}),
                            rx.el.span(
                                "Run complete — expand entries to inspect",
                                style={"marginLeft": "6px", "color": "#5a7a5a", "fontSize": "0.85rem"},
                            ),
                            style={"display": "flex", "alignItems": "center"},
                        ),
                    ),
                    # Events list
                    rx.cond(
                        AgentState.agent_events.length() > 0,
                        rx.el.div(
                            rx.foreach(AgentState.agent_events, agent_event_item),
                            style={
                                "marginTop": "10px",
                                "paddingTop": "8px",
                                "borderTop": "1px solid #e8dff5",
                                "maxHeight": "260px",
                                "overflowY": "auto",
                            },
                        ),
                        rx.fragment(),
                    ),
                    style={
                        "padding": "14px",
                        "backgroundColor": "#f8f6ff",
                        "borderRadius": "8px",
                        "marginBottom": "10px",
                    },
                ),
                rx.fragment(),
            ),
            rx.cond(
                (AgentState.agent_messages.length() == 0) & ~AgentState.agent_processing,
                rx.el.div(
                    fomantic_icon("zap", size=40, color="#d6c4e8"),
                    rx.el.div(
                        "Describe your annotation module",
                        style={"color": "#888", "marginTop": "10px", "fontSize": "1rem", "fontWeight": "500"},
                    ),
                    rx.el.div(
                        "Attach up to 5 files (PDF/CSV/MD/TXT) with the ",
                        fomantic_icon("paperclip", size=14, color="#aaa"),
                        " button, then tell the agent what module to create.",
                        style={"color": "#aaa", "marginTop": "6px", "fontSize": "0.85rem", "maxWidth": "340px", "lineHeight": "1.4"},
                    ),
                    style={"textAlign": "center", "padding": "30px 16px"},
                ),
                rx.fragment(),
            ),
            id="agent-messages-area",
            style={
                "flex": "1",
                "overflowY": "auto",
                "padding": "8px 4px",
                "marginBottom": "12px",
                "minHeight": "200px",
                "maxHeight": "500px",
            },
        ),

        # Input bar with attach + file chip + send
        rx.el.div(
            # Mode toggle
            rx.el.div(
                rx.el.label(
                    rx.el.input(
                        type="checkbox",
                        checked=AgentState.agent_use_team,
                        on_change=AgentState.set_agent_use_team,
                        disabled=AgentState.agent_processing,
                        style={"marginRight": "6px", "cursor": "pointer", "accentColor": "#a333c8"},
                    ),
                    rx.cond(
                        AgentState.agent_use_team,
                        "Research team (multi-agent)",
                        "Single agent",
                    ),
                    style={
                        "fontSize": "0.8rem",
                        "color": "#888",
                        "cursor": "pointer",
                        "userSelect": "none",
                        "display": "flex",
                        "alignItems": "center",
                    },
                ),
                style={"marginBottom": "6px"},
            ),
            # Attachment row — separate from input so textarea gets full width
            rx.el.div(
                rx.upload(
                    rx.el.div(
                        fomantic_icon("paperclip", size=16, color=rx.cond(
                            AgentState.agent_uploaded_files.length() > 0, "#a333c8", "#888",
                        )),
                        rx.el.span(
                            "Attach",
                            style={
                                "fontSize": "0.82rem",
                                "fontWeight": "500",
                                "marginLeft": "4px",
                                "color": rx.cond(
                                    AgentState.agent_uploaded_files.length() > 0, "#a333c8", "#888",
                                ),
                            },
                        ),
                        style={
                            "display": "flex",
                            "alignItems": "center",
                            "cursor": "pointer",
                            "padding": "0 10px",
                            "height": "32px",
                            "border": "1px solid #ddd",
                            "borderRadius": "6px",
                            "backgroundColor": rx.cond(
                                AgentState.agent_uploaded_files.length() > 0, "#faf6ff", "#fff",
                            ),
                            "boxSizing": "border-box",
                            "whiteSpace": "nowrap",
                            "flexShrink": "0",
                        },
                        title="Attach PDF, CSV, or text file",
                    ),
                    id="agent_file_upload",
                    multiple=True,
                    accept={
                        "application/pdf": [".pdf"],
                        "text/csv": [".csv"],
                        "text/markdown": [".md"],
                        "text/plain": [".txt"],
                    },
                    on_drop=AgentState.upload_agent_file(rx.upload_files(upload_id="agent_file_upload")),
                    style={"display": "contents"},
                ),
                rx.cond(
                    AgentState.agent_uploaded_files.length() > 0,
                    rx.el.div(
                        rx.foreach(
                            AgentState.agent_uploaded_files,
                            lambda fname: rx.el.div(
                                fomantic_icon("file-text", size=12, color="#a333c8"),
                                rx.el.span(
                                    fname,
                                    style={
                                        "fontSize": "0.78rem",
                                        "color": "#a333c8",
                                        "marginLeft": "3px",
                                        "fontWeight": "500",
                                        # Ellipsis on long names; flex:1 + minWidth:0 allows shrink
                                        "flex": "1",
                                        "minWidth": "0",
                                        "overflow": "hidden",
                                        "textOverflow": "ellipsis",
                                        "whiteSpace": "nowrap",
                                    },
                                ),
                                rx.el.button(
                                    fomantic_icon("circle-x", size=11, color="#999"),
                                    on_click=AgentState.remove_agent_file(fname),
                                    style={
                                        "background": "none",
                                        "border": "none",
                                        "cursor": "pointer",
                                        "padding": "0 0 0 4px",
                                        "display": "flex",
                                        "alignItems": "center",
                                        "flexShrink": "0",  # never clip the × button
                                    },
                                ),
                                style={
                                    "display": "flex",
                                    "alignItems": "center",
                                    "padding": "0 6px 0 8px",
                                    "border": "1px solid #d6c4e8",
                                    "borderRadius": "12px",
                                    "backgroundColor": "#faf6ff",
                                    "height": "32px",
                                    "boxSizing": "border-box",
                                    "maxWidth": "200px",
                                },
                            ),
                        ),
                        rx.el.button(
                            "Clear all",
                            on_click=AgentState.clear_agent_file,
                            style={
                                "height": "32px",
                                "padding": "0 10px",
                                "border": "1px solid #ddd",
                                "borderRadius": "6px",
                                "backgroundColor": "#fff",
                                "fontSize": "0.82rem",
                                "fontWeight": "500",
                                "color": "#888",
                                "cursor": "pointer",
                                "flexShrink": "0",
                                "boxSizing": "border-box",
                            },
                        ),
                        style={
                            "display": "flex",
                            "alignItems": "center",
                            "gap": "6px",
                            "flexWrap": "wrap",
                        },
                    ),
                    rx.fragment(),
                ),
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "gap": "8px",
                    "marginBottom": "8px",
                    "flexWrap": "wrap",
                },
            ),
            # Textarea + Send row
            rx.el.div(
                rx.el.textarea(
                    id="agent-chat-input",
                    key=AgentState._agent_input_key,
                    default_value=AgentState.agent_input,
                    on_change=AgentState.set_agent_input,
                    placeholder="Describe the module you want to create...\n(Shift+Enter for new line)",
                    disabled=AgentState.agent_processing,
                    rows=2,
                    style={
                        "flex": "1",
                        "padding": "10px 14px",
                        "border": "1px solid #ddd",
                        "borderRadius": "6px",
                        "fontSize": "0.95rem",
                        "minHeight": "44px",
                        "maxHeight": "200px",
                        "resize": "none",
                        "overflowY": "auto",
                        "lineHeight": "1.4",
                        "boxSizing": "border-box",
                        "fontFamily": "inherit",
                    },
                ),
                rx.el.button(
                    rx.cond(
                        AgentState.agent_processing,
                        rx.el.i("", class_name="spinner loading icon"),
                        fomantic_icon("play", size=16),
                    ),
                    " Send",
                    id="agent-send-btn",
                    on_click=AgentState.send_agent_message,
                    disabled=AgentState.agent_processing | (AgentState.agent_input == ""),
                    class_name="ui purple button",
                    style={
                        "marginLeft": "0",
                        "height": "44px",
                        "boxSizing": "border-box",
                        "alignSelf": "flex-end",
                        "paddingTop": "0",
                        "paddingBottom": "0",
                        "display": "inline-flex",
                        "alignItems": "center",
                        "flexShrink": "0",
                    },
                ),
                style={"display": "flex", "alignItems": "flex-end", "gap": "12px"},
            ),
            rx.el.div(
                "Enter to send \u00b7 Shift+Enter for new line",
                style={"fontSize": "0.72rem", "color": "#bbb", "marginTop": "4px", "textAlign": "right"},
            ),
        ),
        # JS: Enter-to-send (Shift+Enter for newline) + auto-resize textarea
        rx.script(
            """
            (function() {
                document.addEventListener('keydown', function(e) {
                    if (e.target && e.target.id === 'agent-chat-input'
                        && e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        var btn = document.getElementById('agent-send-btn');
                        if (btn && !btn.disabled) btn.click();
                    }
                });
                document.addEventListener('input', function(e) {
                    if (e.target && e.target.id === 'agent-chat-input') {
                        e.target.style.height = 'auto';
                        e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
                    }
                });
            })();
            """
        ),

        style={"display": "flex", "flexDirection": "column", "height": "100%", "padding": "0"},
    )


# ============================================================================
# MAIN PAGE
# ============================================================================

@rx.page(route="/modules", on_load=UploadState.on_load)
def modules_page() -> rx.Component:
    """Module Manager page — sources, editing slot, and AI agent chat."""
    return template(
        two_column_layout(
            left=modules_left_panel(),
            right=agent_chat_panel(),
        ),
    )
