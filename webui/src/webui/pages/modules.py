"""
Module Manager Page — manage module sources, upload custom DSL modules,
and interact with the Paper-to-Module AI agent.

Left Panel:  Module sources tree, DSL upload, agent file upload
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
    """Compact card showing a module source. Local sources list individual modules with remove buttons."""
    is_local = repo["is_local"].to(bool)

    return rx.el.div(
        # Header row
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
        # For local sources: list each module with a remove button
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


def custom_module_upload() -> rx.Component:
    """Upload component for adding a custom DSL module (module_spec.yaml + variants.csv)."""
    return rx.el.div(
        rx.el.div(
            fomantic_icon("upload", size=16, color="#a333c8"),
            rx.el.span(
                " Upload Custom Module Files",
                style={"fontSize": "0.9rem", "fontWeight": "600", "marginLeft": "4px", "color": "#555"},
            ),
            style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
        ),
        # Module name preview banner (shown immediately after file drop)
        rx.cond(
            UploadState.pending_module_name != "",
            rx.el.div(
                fomantic_icon("dna", size=14, color="#a333c8"),
                rx.el.span(
                    " Module: ",
                    style={"fontSize": "0.82rem", "color": "#888", "marginLeft": "6px"},
                ),
                rx.el.strong(
                    UploadState.pending_module_name,
                    style={"color": "#a333c8", "fontSize": "0.88rem"},
                ),
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "padding": "5px 10px",
                    "marginBottom": "6px",
                    "border": "1px solid #d6c4e8",
                    "borderRadius": "4px",
                    "backgroundColor": "#f3eaff",
                },
            ),
            rx.fragment(),
        ),
        # Inline preview validation error (before clicking Add)
        rx.cond(
            UploadState.pending_module_preview_error != "",
            rx.el.div(
                fomantic_icon("circle-alert", size=13, color="#9f3a38"),
                rx.el.span(
                    " ",
                    UploadState.pending_module_preview_error,
                    style={"fontSize": "0.82rem", "color": "#9f3a38", "marginLeft": "4px"},
                ),
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "padding": "5px 10px",
                    "marginBottom": "6px",
                    "border": "1px solid #e0b4b4",
                    "borderRadius": "4px",
                    "backgroundColor": "#fff6f6",
                },
            ),
            rx.fragment(),
        ),
        rx.upload(
            rx.el.div(
                fomantic_icon("file-text", size=14, color="#a333c8"),
                rx.cond(
                    rx.selected_files("module_upload").length() > 0,
                    rx.el.span(
                        rx.selected_files("module_upload").join(", "),
                        style={"marginLeft": "6px", "color": "#a333c8", "fontSize": "0.82rem", "fontWeight": "500"},
                    ),
                    rx.el.span(
                        "Select module_spec.yaml + variants.csv (or .zip)",
                        style={"marginLeft": "6px", "color": "#888", "fontSize": "0.82rem"},
                    ),
                ),
                style={"display": "flex", "alignItems": "center"},
            ),
            id="module_upload",
            multiple=True,
            accept={
                "text/yaml": [".yaml", ".yml"],
                "text/csv": [".csv"],
                "application/zip": [".zip"],
            },
            on_drop=UploadState.preview_module_upload(
                rx.upload_files(upload_id="module_upload"),
            ),
            style={
                "padding": "6px 10px",
                "border": "1px solid #d6c4e8",
                "borderRadius": "4px",
                "backgroundColor": "#fff",
                "cursor": "pointer",
            },
        ),
        rx.el.button(
            rx.cond(
                UploadState.custom_module_adding,
                rx.el.i("", class_name="spinner loading icon"),
                fomantic_icon("plus", size=14),
            ),
            " Add",
            on_click=UploadState.commit_module_upload,
            disabled=UploadState.custom_module_adding
                | (UploadState.pending_module_name == "")
                | (UploadState.pending_module_preview_error != ""),
            class_name="ui purple small button",
            style={"marginTop": "8px", "width": "100%", "boxSizing": "border-box"},
        ),
        rx.el.div(
            "Required: module_spec.yaml, variants.csv. Optional: studies.csv. Also accepts .zip",
            style={"fontSize": "0.75rem", "color": "#999", "marginTop": "4px"},
        ),
        rx.cond(
            UploadState.custom_module_error != "",
            rx.el.div(
                UploadState.custom_module_error,
                class_name="ui mini negative message",
                style={"marginTop": "6px", "padding": "8px 10px", "fontSize": "0.85rem"},
            ),
            rx.fragment(),
        ),
        style={
            "padding": "10px 12px",
            "border": "1px dashed #d6c4e8",
            "borderRadius": "4px",
            "backgroundColor": "#faf6ff",
            "marginBottom": "6px",
        },
    )


# ============================================================================
# LEFT PANEL — Sources + Uploads
# ============================================================================

def modules_left_panel() -> rx.Component:
    """Left panel: module sources, custom DSL upload."""
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

        # Custom DSL upload — collapsible (advanced)
        rx.el.details(
            rx.el.summary(
                fomantic_icon("upload", size=14, color="#767676"),
                rx.el.span(
                    " Upload custom module files (advanced)",
                    style={"fontSize": "0.85rem", "color": "#666", "marginLeft": "4px", "cursor": "pointer"},
                ),
                style={"display": "flex", "alignItems": "center", "padding": "8px 12px", "listStyle": "none"},
            ),
            rx.el.div(
                custom_module_upload(),
                style={"padding": "0 12px 12px 12px"},
            ),
            class_name="ui segment",
            style={"padding": "0", "marginBottom": "12px"},
        ),

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

        # Result actions (register module when spec is ready)
        rx.cond(
            AgentState.has_agent_spec,
            rx.el.div(
                rx.el.div(
                    fomantic_icon("circle-check", size=16, color="#21ba45"),
                    rx.el.span(
                        " Module spec ready: ",
                        style={"marginLeft": "6px", "fontSize": "0.9rem"},
                    ),
                    rx.el.strong(
                        AgentState.agent_spec_name,
                        style={"color": "#a333c8"},
                    ),
                    style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
                ),
                # File list
                rx.el.div(
                    rx.foreach(
                        AgentState.agent_spec_files,
                        lambda fname: rx.el.span(
                            fomantic_icon("file-text", size=11, color="#666"),
                            rx.el.span(fname, style={"marginLeft": "3px"}),
                            style={
                                "display": "inline-flex",
                                "alignItems": "center",
                                "fontSize": "0.8rem",
                                "color": "#555",
                                "marginRight": "10px",
                            },
                        ),
                    ),
                    style={"marginBottom": "10px"},
                ),
                # Action buttons row
                rx.el.div(
                    rx.el.button(
                        fomantic_icon("plus-circle", size=16),
                        " Register Module",
                        on_click=AgentState.register_agent_result,
                        class_name="ui green button",
                        style={"flex": "1"},
                    ),
                    rx.el.a(
                        fomantic_icon("download", size=16, color="#fff"),
                        " Download .zip",
                        href=AgentState.agent_spec_zip_url,
                        class_name="ui purple button",
                        style={"marginLeft": "8px", "flex": "0 0 auto"},
                    ),
                    style={"display": "flex", "alignItems": "center"},
                ),
                rx.el.div(
                    "Auto-saved to data/module_specs/generated/",
                    style={"fontSize": "0.72rem", "color": "#999", "marginTop": "6px"},
                ),
                class_name="ui green segment",
                style={"padding": "12px", "marginBottom": "12px"},
            ),
            rx.fragment(),
        ),

        # Input bar with attach + file chip + send (no form — JS handles Enter)
        rx.el.div(
            # Row: attach + file chip + textarea + send
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
                "Enter to send · Shift+Enter for new line",
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
    """Module Manager page — sources, uploads, and AI agent chat."""
    return template(
        two_column_layout(
            left=modules_left_panel(),
            right=agent_chat_panel(),
        ),
    )
