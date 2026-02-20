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
    """Single custom module entry with a remove button."""
    return rx.el.div(
        fomantic_icon("dna", size=14, color="#a333c8"),
        rx.el.span(name, style={"flex": "1", "marginLeft": "6px", "fontSize": "0.85rem"}),
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
        fomantic_icon("inbox", size=28, color="#ccc"),
        rx.el.div(
            "No module loaded",
            style={"color": "#999", "fontSize": "0.9rem", "marginTop": "6px"},
        ),
        rx.el.div(
            "Upload files or use the agent to create a module",
            style={"color": "#bbb", "fontSize": "0.78rem", "marginTop": "2px"},
        ),
        style={"textAlign": "center", "padding": "18px 8px"},
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
    """Upload / Add / Clear / Download button row for the editing slot."""
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
        # Add to registry
        rx.el.button(
            rx.cond(
                AgentState.slot_adding,
                rx.el.i("", class_name="spinner loading icon"),
                fomantic_icon("plus", size=13),
            ),
            " Add",
            on_click=AgentState.add_slot_module,
            disabled=~AgentState.slot_is_populated | AgentState.slot_adding,
            class_name="ui mini purple button",
            style={"flex": "1"},
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
        # Content: empty or populated
        rx.cond(
            AgentState.slot_is_populated,
            _slot_populated_state(),
            _slot_empty_state(),
        ),
        # Button bar (always visible)
        _slot_button_bar(),
        rx.el.div(
            "Upload: module_spec.yaml + variants.csv (.zip OK). Add: register to system.",
            style={"fontSize": "0.72rem", "color": "#aaa", "marginTop": "6px"},
        ),
        class_name="ui segment",
        style={"padding": "12px", "marginBottom": "12px", "border": "1px solid #d6c4e8", "backgroundColor": "#faf6ff"},
    )


# ============================================================================
# LEFT PANEL — Sources + Editing Slot
# ============================================================================

def modules_left_panel() -> rx.Component:
    """Left panel: module sources, editing slot."""
    return rx.el.div(
        # Header
        rx.el.div(
            fomantic_icon("boxes", size=22, color="#a333c8"),
            rx.el.span(
                " Module Manager",
                style={"fontSize": "1.15rem", "fontWeight": "600", "marginLeft": "8px"},
            ),
            style={"display": "flex", "alignItems": "center", "marginBottom": "16px"},
        ),

        # Module Sources section
        rx.el.div(
            rx.el.div(
                fomantic_icon("database", size=16, color="#767676"),
                rx.el.span(
                    " Module Sources",
                    style={"fontSize": "0.95rem", "fontWeight": "600", "marginLeft": "4px", "color": "#555"},
                ),
                style={"display": "flex", "alignItems": "center", "marginBottom": "10px"},
            ),
            rx.foreach(UploadState.repo_info_list, repo_source_card),
            class_name="ui segment",
            style={"padding": "12px", "marginBottom": "12px"},
        ),

        # Editing Slot
        editing_slot(),

        id="modules-left-panel",
    )


# ============================================================================
# AGENT CHAT COMPONENTS
# ============================================================================

def agent_message_bubble(msg: rx.Var[dict]) -> rx.Component:
    """Render a single chat message (user or agent)."""
    is_user = msg["role"].to(str) == "user"
    return rx.el.div(
        rx.cond(
            is_user,
            rx.el.div(
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
            ),
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
                " Module Creator Agent",
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
                AgentState.agent_processing,
                rx.el.div(
                    rx.el.div(
                        rx.el.i("", class_name="spinner loading icon", style={"fontSize": "1.2rem", "color": "#a333c8"}),
                        rx.el.span(
                            " Agent is thinking... this may take a minute.",
                            style={"marginLeft": "8px", "color": "#888", "fontSize": "0.9rem"},
                        ),
                        style={"display": "flex", "alignItems": "center"},
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
                        "Attach a research paper (PDF) or data file (CSV) with the ",
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
            rx.el.div(
                # Attach button (upload trigger)
                rx.upload(
                    rx.el.div(
                        fomantic_icon("paperclip", size=16, color=rx.cond(
                            AgentState.agent_uploaded_file != "", "#a333c8", "#888",
                        )),
                        rx.el.span(
                            "Attach",
                            style={
                                "fontSize": "0.82rem",
                                "fontWeight": "500",
                                "marginLeft": "4px",
                                "color": rx.cond(
                                    AgentState.agent_uploaded_file != "", "#a333c8", "#888",
                                ),
                            },
                        ),
                        style={
                            "display": "flex",
                            "alignItems": "center",
                            "cursor": "pointer",
                            "padding": "0 10px",
                            "height": "40px",
                            "border": "1px solid #ddd",
                            "borderRadius": "6px",
                            "backgroundColor": rx.cond(
                                AgentState.agent_uploaded_file != "", "#faf6ff", "#fff",
                            ),
                            "boxSizing": "border-box",
                            "whiteSpace": "nowrap",
                            "marginRight": "6px",
                            "flex": "0 0 auto",
                        },
                        title="Attach PDF, CSV, or text file",
                    ),
                    id="agent_file_upload",
                    multiple=False,
                    accept={
                        "application/pdf": [".pdf"],
                        "text/csv": [".csv"],
                        "text/markdown": [".md"],
                        "text/plain": [".txt"],
                    },
                    on_drop=AgentState.upload_agent_file(rx.upload_files(upload_id="agent_file_upload")),
                    style={
                        "display": "contents",
                    },
                ),
                # Attached file chip
                rx.cond(
                    AgentState.agent_uploaded_file != "",
                    rx.el.div(
                        fomantic_icon("file-text", size=12, color="#a333c8"),
                        rx.el.span(
                            AgentState.agent_uploaded_file,
                            style={"fontSize": "0.78rem", "color": "#a333c8", "marginLeft": "3px", "fontWeight": "500"},
                        ),
                        rx.el.button(
                            fomantic_icon("circle-x", size=11, color="#999"),
                            on_click=AgentState.clear_agent_file,
                            style={
                                "background": "none",
                                "border": "none",
                                "cursor": "pointer",
                                "padding": "0 0 0 4px",
                                "display": "flex",
                                "alignItems": "center",
                            },
                        ),
                        style={
                            "display": "flex",
                            "alignItems": "center",
                            "padding": "0 8px",
                            "marginRight": "6px",
                            "border": "1px solid #d6c4e8",
                            "borderRadius": "12px",
                            "backgroundColor": "#faf6ff",
                            "flexShrink": "0",
                            "maxWidth": "180px",
                            "overflow": "hidden",
                            "height": "40px",
                            "boxSizing": "border-box",
                        },
                    ),
                    rx.fragment(),
                ),
                rx.el.textarea(
                    id="agent-chat-input",
                    value=AgentState.agent_input,
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
                        "marginLeft": "8px",
                        "height": "39px",
                        "boxSizing": "border-box",
                        "alignSelf": "flex-end",
                        "paddingTop": "0",
                        "paddingBottom": "0",
                        "display": "inline-flex",
                        "alignItems": "center",
                        "flexShrink": "0",
                    },
                ),
                style={"display": "flex", "alignItems": "flex-end", "gap": "0"},
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
