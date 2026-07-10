"""
Module Registry page — browse the remote catalog, install/uninstall modules,
and inspect the local registry cross-referenced against the catalog.

Left panel:  fixed selected-module details card (status-aware controls) + narrow local list.
Right panel: two tabs — Catalog (download+register) and Publication (deferred stub).
"""
from __future__ import annotations

import reflex as rx

from webui.components.layout import template, two_column_layout, fomantic_icon
from webui.crawler_assets import page_image_url, page_meta
from webui.state import RegistryState


# ============================================================================
# LEFT PANEL — selected module details + local list
# ============================================================================

def _status_badge() -> rx.Component:
    """Colored pill reflecting the selected module's install/catalog status."""
    return rx.el.span(
        RegistryState.sel_status_label,
        style={
            "display": "inline-block",
            "fontSize": "0.72rem",
            "fontWeight": "700",
            "padding": "2px 10px",
            "borderRadius": "10px",
            "color": "#fff",
            "backgroundColor": RegistryState.sel_status_color,
        },
    )


def _gate_banner() -> rx.Component:
    """Confirm/cancel banner shown before a destructive/replacing action."""
    return rx.cond(
        RegistryState.has_pending,
        rx.el.div(
            rx.el.div(
                fomantic_icon("exclamation triangle", size=14, color="#b58105"),
                rx.el.span(
                    RegistryState.pending_warn,
                    style={"fontSize": "0.82rem", "color": "#7a5c00", "marginLeft": "6px"},
                ),
                style={"display": "flex", "alignItems": "flex-start"},
            ),
            rx.el.div(
                rx.el.button(
                    "Proceed",
                    on_click=RegistryState.confirm_pending,
                    class_name="ui mini red button",
                    style={"marginRight": "6px"},
                ),
                rx.el.button(
                    "Cancel",
                    on_click=RegistryState.cancel_pending,
                    class_name="ui mini button",
                ),
                style={"marginTop": "8px"},
            ),
            style={
                "backgroundColor": "#fff8e1",
                "border": "1px solid #f0d17a",
                "borderRadius": "6px",
                "padding": "10px 12px",
                "marginBottom": "10px",
            },
        ),
        rx.fragment(),
    )


def _version_selector() -> rx.Component:
    return rx.el.div(
        rx.el.label(
            "Version",
            style={"fontSize": "0.75rem", "color": "#888", "fontWeight": "600", "marginRight": "8px"},
        ),
        rx.el.select(
            rx.foreach(
                RegistryState.selected_versions,
                lambda v: rx.el.option(v, value=v),
            ),
            value=RegistryState.selected_version,
            on_change=RegistryState.set_selected_version,
            style={
                "padding": "4px 8px",
                "border": "1px solid #ddd",
                "borderRadius": "4px",
                "fontSize": "0.82rem",
                "minWidth": "100px",
            },
        ),
        style={"display": "flex", "alignItems": "center", "marginTop": "10px"},
    )


def _action_buttons() -> rx.Component:
    """Status-driven action row. Download only when not-installed; local actions when installed."""
    return rx.el.div(
        # Download (remote present + local absent)
        rx.cond(
            RegistryState.show_download,
            rx.el.button(
                rx.cond(
                    RegistryState.action_busy,
                    rx.el.i("", class_name="spinner loading icon"),
                    fomantic_icon("download", size=13),
                ),
                " Get from catalog",
                on_click=RegistryState.request_download,
                disabled=RegistryState.action_busy,
                class_name="ui small primary button",
                style={"flex": "1"},
            ),
            rx.fragment(),
        ),
        # Local actions
        rx.cond(
            RegistryState.show_local_actions,
            rx.fragment(
                rx.el.button(
                    fomantic_icon("edit", size=13),
                    " Edit",
                    on_click=RegistryState.edit_selected,
                    disabled=~RegistryState.edit_enabled,
                    class_name="ui small button",
                    style={"flex": "1"},
                    title="Load into the Module Manager editing slot",
                ),
                rx.el.a(
                    fomantic_icon("download", size=13),
                    " Export",
                    href=RegistryState.export_url,
                    class_name="ui small teal button",
                    style={"flex": "1", "textAlign": "center"},
                ),
                rx.el.button(
                    fomantic_icon("trash alternate", size=13),
                    " Uninstall",
                    on_click=RegistryState.request_uninstall,
                    disabled=RegistryState.action_busy,
                    class_name="ui small red button",
                    style={"flex": "1"},
                ),
            ),
            rx.fragment(),
        ),
        style={"display": "flex", "gap": "6px", "marginTop": "12px", "flexWrap": "wrap"},
    )


def _upload_import_button(upload_id: str) -> rx.Component:
    """Import a local module spec into the registry (gated if it overwrites an unmirrored copy)."""
    return rx.upload(
        rx.el.button(
            fomantic_icon("upload", size=13),
            " Upload / import a local module",
            class_name="ui tiny fluid button",
            style={"cursor": "pointer", "marginTop": "8px"},
        ),
        id=upload_id,
        multiple=True,
        accept={
            "text/yaml": [".yaml", ".yml"],
            "text/csv": [".csv"],
            "application/zip": [".zip"],
        },
        on_drop=RegistryState.upload_import(rx.upload_files(upload_id=upload_id)),
        style={"display": "contents"},
    )


def _selected_card() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            fomantic_icon("box", size=18, color="#a333c8"),
            rx.el.span(
                " Selected Module",
                style={"fontSize": "0.9rem", "fontWeight": "600", "marginLeft": "4px", "color": "#555"},
            ),
            style={"display": "flex", "alignItems": "center", "marginBottom": "10px"},
        ),
        _gate_banner(),
        rx.cond(
            RegistryState.has_selection,
            rx.el.div(
                # Title + status
                rx.el.div(
                    rx.cond(
                        RegistryState.selected_logo_url != "",
                        rx.el.img(
                            src=RegistryState.selected_logo_url,
                            style={"width": "22px", "height": "22px", "objectFit": "contain",
                                   "borderRadius": "3px", "marginRight": "6px"},
                        ),
                        rx.fragment(),
                    ),
                    rx.el.span(
                        RegistryState.selected_title,
                        style={"fontSize": "1rem", "fontWeight": "700", "color": "#333", "flex": "1"},
                    ),
                    _status_badge(),
                    style={"display": "flex", "alignItems": "center", "gap": "8px"},
                ),
                rx.el.div(
                    RegistryState.selected_name,
                    rx.cond(
                        RegistryState.selected_namespace != "",
                        rx.el.span(
                            " · ", RegistryState.selected_namespace,
                            style={"color": "#a333c8"},
                        ),
                        rx.fragment(),
                    ),
                    style={"fontSize": "0.78rem", "color": "#999", "fontFamily": "monospace", "marginTop": "2px"},
                ),
                rx.cond(
                    RegistryState.selected_author != "",
                    rx.el.div(
                        fomantic_icon("user", size=11, color="#888"),
                        rx.el.span(" ", RegistryState.selected_author, style={"marginLeft": "3px"}),
                        style={"fontSize": "0.78rem", "color": "#888", "marginTop": "4px", "display": "flex", "alignItems": "center"},
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    RegistryState.selected_description != "",
                    rx.el.div(
                        RegistryState.selected_description,
                        style={"fontSize": "0.8rem", "color": "#666", "marginTop": "6px", "lineHeight": "1.4"},
                    ),
                    rx.fragment(),
                ),
                # Stats
                rx.el.div(
                    rx.el.span(RegistryState.selected_variant_count, " variants", class_name="ui mini label"),
                    rx.el.span(RegistryState.selected_gene_count, " genes", class_name="ui mini label", style={"marginLeft": "4px"}),
                    rx.cond(
                        RegistryState.selected_clinvar_count > 0,
                        rx.el.span(
                            RegistryState.selected_pathogenic_count, " path / ",
                            RegistryState.selected_benign_count, " benign",
                            class_name="ui mini red label", style={"marginLeft": "4px"},
                            title="ClinVar pathogenic / benign variants",
                        ),
                        rx.fragment(),
                    ),
                    style={"marginTop": "8px"},
                ),
                _version_selector(),
                _action_buttons(),
                rx.cond(
                    RegistryState.action_message != "",
                    rx.el.div(
                        RegistryState.action_message,
                        style={"fontSize": "0.75rem", "color": "#777", "marginTop": "8px"},
                    ),
                    rx.fragment(),
                ),
            ),
            # Empty state
            rx.el.div(
                fomantic_icon("hand point up outline", size=26, color="#ccc"),
                rx.el.div(
                    "Select a module from the catalog or the list below.",
                    style={"color": "#999", "fontSize": "0.85rem", "marginTop": "8px"},
                ),
                style={"textAlign": "center", "padding": "12px 8px"},
            ),
        ),
        class_name="ui segment",
        style={"padding": "12px", "marginBottom": "12px", "border": "1px solid #d6c4e8", "backgroundColor": "#faf6ff"},
    )


def _local_list_item(mod: rx.Var[dict]) -> rx.Component:
    name = mod["name"].to(str)
    return rx.el.div(
        fomantic_icon("box", size=13, color="#2185d0"),
        rx.el.span(
            mod["title"].to(str),
            style={"flex": "1", "marginLeft": "6px", "fontSize": "0.82rem", "overflow": "hidden",
                   "textOverflow": "ellipsis", "whiteSpace": "nowrap"},
        ),
        rx.el.span(
            "v", mod["version"].to(str),
            style={"fontSize": "0.72rem", "color": "#999", "marginRight": "6px"},
        ),
        rx.cond(
            mod["in_catalog"].to(bool),
            rx.el.span("catalog", class_name="ui mini green label"),
            rx.el.span("local", class_name="ui mini label"),
        ),
        on_click=lambda: RegistryState.select_local(name),
        class_name=rx.cond(
            RegistryState.selected_name == name,
            "registry-local-item registry-local-item-active",
            "registry-local-item",
        ),
        style={
            "display": "flex", "alignItems": "center", "padding": "6px 8px",
            "borderRadius": "4px", "cursor": "pointer", "marginBottom": "2px",
        },
    )


def _local_list() -> rx.Component:
    return rx.el.div(
        rx.el.style(
            ".registry-local-item:hover { background-color: #f0f4fb; }"
            " .registry-local-item-active { background-color: #e8f0fe; box-shadow: inset 3px 0 0 #2185d0; }"
        ),
        rx.el.div(
            fomantic_icon("folder open", size=15, color="#2185d0"),
            rx.el.span(
                " Installed modules",
                style={"fontSize": "0.9rem", "fontWeight": "600", "marginLeft": "4px", "color": "#2185d0"},
            ),
            rx.el.span(
                RegistryState.local_modules.length(),
                class_name="ui mini label",
                style={"marginLeft": "auto"},
            ),
            style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
        ),
        rx.cond(
            RegistryState.local_modules.length() > 0,
            rx.foreach(RegistryState.local_modules, _local_list_item),
            rx.el.div(
                "No modules installed yet.",
                style={"fontSize": "0.8rem", "color": "#aaa", "padding": "6px 4px"},
            ),
        ),
        class_name="ui segment",
        style={"padding": "10px 12px", "border": "1px solid #c5daf5", "backgroundColor": "#f8fbff"},
    )


def registry_left_panel() -> rx.Component:
    return rx.el.div(
        _selected_card(),
        # Upload/import sits between the details pane and the list, separating them.
        rx.el.div(
            _upload_import_button("registry_import"),
            style={"margin": "4px 0 14px"},
        ),
        _local_list(),
        id="registry-left-panel",
    )


# ============================================================================
# RIGHT PANEL — Catalog + Publication tabs
# ============================================================================

_TAB_STYLE: dict = {
    "cursor": "pointer", "display": "flex", "alignItems": "center", "gap": "8px",
    "fontSize": "1rem", "fontWeight": "600", "padding": "12px 18px",
}


def _tab_menu() -> rx.Component:
    return rx.el.div(
        rx.el.a(
            fomantic_icon("book", size=16,
                          color=rx.cond(RegistryState.registry_active_tab == "catalog", "#00b5ad", "#888")),
            " Browse",
            class_name=rx.cond(RegistryState.registry_active_tab == "catalog", "active item", "item"),
            on_click=lambda: RegistryState.switch_registry_tab("catalog"),
            style=_TAB_STYLE,
        ),
        rx.el.a(
            fomantic_icon("upload", size=16,
                          color=rx.cond(RegistryState.registry_active_tab == "publication", "#2185d0", "#888")),
            " Publication",
            class_name=rx.cond(RegistryState.registry_active_tab == "publication", "active item", "item"),
            on_click=lambda: RegistryState.switch_registry_tab("publication"),
            style=_TAB_STYLE,
        ),
        class_name="ui top attached tabular menu",
        style={"marginBottom": "0"},
        id="registry-tab-menu",
    )


def _catalog_card(card: rx.Var[dict]) -> rx.Component:
    namespace = card["namespace"].to(str)
    name = card["name"].to(str)
    latest = card["latest_version"].to(str)
    installed = card["installed"].to(bool)
    return rx.el.div(
        # Header
        rx.el.div(
            rx.cond(
                card["logo_full"].to(str) != "",
                rx.el.img(
                    src=card["logo_full"].to(str),
                    style={"width": "20px", "height": "20px", "objectFit": "contain", "borderRadius": "3px"},
                ),
                fomantic_icon("box", size=16, color="#6435c9"),
            ),
            rx.el.span(
                card["title"].to(str),
                style={"fontWeight": "700", "fontSize": "0.9rem", "marginLeft": "6px", "flex": "1",
                       "overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap"},
            ),
            rx.cond(
                card["featured"].to(bool),
                rx.el.span("★", style={"color": "#fbbd08", "marginLeft": "4px"}),
                rx.fragment(),
            ),
            style={"display": "flex", "alignItems": "center"},
        ),
        rx.el.div(
            namespace, " · v", latest,
            style={"fontSize": "0.72rem", "color": "#999", "fontFamily": "monospace", "marginTop": "2px"},
        ),
        rx.el.div(
            card["description"].to(str),
            style={"fontSize": "0.78rem", "color": "#666", "marginTop": "6px", "lineHeight": "1.35",
                   "height": "2.7em", "overflow": "hidden"},
        ),
        rx.el.div(
            rx.el.span(card["variant_count"].to(int), " variants", class_name="ui mini label"),
            rx.el.span(card["downloads"].to(int), " ↓", class_name="ui mini label", style={"marginLeft": "4px"}),
            rx.cond(
                card["clinvar_count"].to(int) > 0,
                rx.el.span(
                    card["pathogenic_count"].to(int), " path",
                    class_name="ui mini red label", style={"marginLeft": "4px"},
                    title="ClinVar pathogenic variants",
                ),
                rx.fragment(),
            ),
            style={"marginTop": "6px"},
        ),
        # Actions
        rx.el.div(
            rx.el.button(
                "Details",
                on_click=lambda: RegistryState.select_catalog(namespace, name),
                class_name="ui tiny button",
                style={"flex": "1"},
            ),
            rx.cond(
                installed,
                rx.el.button(
                    "Installed",
                    disabled=True,
                    class_name="ui tiny button",
                    style={"flex": "1", "opacity": "0.6"},
                ),
                rx.el.button(
                    fomantic_icon("download", size=12),
                    " Get",
                    on_click=lambda: RegistryState.quick_install(namespace, name, latest),
                    disabled=RegistryState.action_busy,
                    class_name="ui tiny primary button",
                    style={"flex": "1"},
                ),
            ),
            style={"display": "flex", "gap": "6px", "marginTop": "10px"},
        ),
        style={
            "border": "1px solid #e2e2e2", "borderRadius": "8px", "padding": "12px",
            "backgroundColor": "#fff", "width": "260px", "boxSizing": "border-box",
            "boxShadow": "0 1px 3px rgba(0,0,0,0.06)",
        },
    )


def _catalog_toolbar() -> rx.Component:
    return rx.el.div(
        # Group + namespace filters — on top of the search row.
        rx.el.div(
            fomantic_icon("filter", size=13, color="#888"),
            rx.el.label(
                "Show",
                style={"fontSize": "0.78rem", "color": "#888", "fontWeight": "600", "margin": "0 8px"},
            ),
            # 0.8.0 listing groups (server presets). Default hides test/sandbox namespaces.
            rx.el.select(
                rx.el.option("All modules", value=""),
                rx.el.option("Featured", value="featured"),
                rx.el.option("Curated", value="curated"),
                rx.el.option("Popular", value="popular"),
                rx.el.option("New", value="new"),
                rx.el.option("Test / sandbox", value="test"),
                value=RegistryState.group_filter,
                on_change=RegistryState.set_group_filter,
                style={"padding": "5px 8px", "border": "1px solid #ddd", "borderRadius": "6px",
                       "fontSize": "0.85rem", "flex": "1"},
            ),
            fomantic_icon("sitemap", size=13, color="#888", style={"marginLeft": "12px"}),
            rx.el.label(
                "Namespace",
                style={"fontSize": "0.78rem", "color": "#888", "fontWeight": "600", "margin": "0 8px"},
            ),
            rx.el.select(
                rx.el.option("All namespaces", value=""),
                rx.foreach(
                    RegistryState.namespace_options,
                    lambda ns: rx.el.option(ns, value=ns),
                ),
                value=RegistryState.namespace_filter,
                on_change=RegistryState.set_namespace_filter,
                style={"padding": "5px 8px", "border": "1px solid #ddd", "borderRadius": "6px",
                       "fontSize": "0.85rem", "flex": "1"},
            ),
            style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
        ),
        # Search + sort row.
        rx.el.div(
            rx.el.div(
                fomantic_icon("search", size=14, color="#999"),
                rx.el.input(
                    placeholder="Search modules…",
                    default_value=RegistryState.query,
                    on_change=RegistryState.set_query,
                    on_blur=RegistryState.search,
                    style={"border": "none", "outline": "none", "flex": "1", "fontSize": "0.9rem", "marginLeft": "6px"},
                ),
                rx.el.button(
                    "Search",
                    on_click=RegistryState.search,
                    class_name="ui tiny primary button",
                ),
                style={"display": "flex", "alignItems": "center", "border": "1px solid #ddd",
                       "borderRadius": "6px", "padding": "4px 8px", "flex": "1"},
            ),
            rx.el.select(
                rx.el.option("Name", value="name"),
                rx.el.option("Downloads", value="downloads"),
                rx.el.option("Recent", value="recent"),
                rx.el.option("Popular", value="popular"),
                value=RegistryState.sort,
                on_change=RegistryState.set_sort,
                style={"padding": "6px 8px", "border": "1px solid #ddd", "borderRadius": "6px", "fontSize": "0.85rem"},
            ),
            style={"display": "flex", "alignItems": "center", "gap": "8px"},
        ),
        style={"marginBottom": "12px"},
    )


def _wip_hf_notice() -> rx.Component:
    """Transitional notice: catalog modules that duplicate the built-in HF ones are the same."""
    return rx.el.div(
        fomantic_icon("info circle", size=15, color="#2185d0"),
        rx.el.div(
            rx.el.strong("The module catalog is a work in progress. "),
            "Modules here that share a name with the built-in Hugging Face annotators "
            "(e.g. coronary, longevitymap, superhuman) are ",
            rx.el.strong("the same module"),
            " — the duplication is intentional during the transition, and you don't need to "
            "install them. Installed copies are kept separate (namespaced) so they won't clash "
            "with the built-in ones.",
            style={"marginLeft": "8px", "fontSize": "0.82rem", "lineHeight": "1.45", "color": "#3a5a78"},
        ),
        style={"display": "flex", "alignItems": "flex-start", "backgroundColor": "#eef6fd",
               "border": "1px solid #b8daff", "borderRadius": "6px", "padding": "10px 12px",
               "marginBottom": "12px"},
    )


def _catalog_tab() -> rx.Component:
    return rx.el.div(
        _wip_hf_notice(),
        _catalog_toolbar(),
        rx.cond(
            RegistryState.catalog_error != "",
            rx.el.div(
                fomantic_icon("exclamation circle", size=14, color="#db2828"),
                rx.el.span(" ", RegistryState.catalog_error, style={"marginLeft": "4px"}),
                class_name="ui small warning message",
                style={"display": "block"},
            ),
            rx.fragment(),
        ),
        rx.cond(
            RegistryState.catalog_loading,
            rx.el.div(
                rx.el.i("", class_name="spinner loading icon"),
                " Loading catalog…",
                style={"padding": "20px", "color": "#888"},
            ),
            rx.cond(
                RegistryState.cards.length() > 0,
                rx.el.div(
                    rx.foreach(RegistryState.cards, _catalog_card),
                    style={"display": "flex", "flexWrap": "wrap", "gap": "12px"},
                ),
                rx.el.div(
                    "No modules found.",
                    style={"padding": "20px", "color": "#aaa", "textAlign": "center"},
                ),
            ),
        ),
        # Pagination
        rx.el.div(
            rx.el.button(
                "‹ Prev",
                on_click=RegistryState.prev_page,
                disabled=~RegistryState.can_prev,
                class_name="ui tiny button",
            ),
            rx.el.span(
                "Page ", RegistryState.page,
                style={"fontSize": "0.82rem", "color": "#777", "margin": "0 10px"},
            ),
            rx.el.button(
                "Next ›",
                on_click=RegistryState.next_page,
                disabled=~RegistryState.can_next,
                class_name="ui tiny button",
            ),
            style={"display": "flex", "alignItems": "center", "justifyContent": "center", "marginTop": "16px"},
        ),
        style={"padding": "4px 2px"},
    )


_INPUT_STYLE: dict = {
    "width": "100%", "padding": "6px 9px", "border": "1px solid #ddd", "borderRadius": "5px",
    "fontSize": "0.85rem", "boxSizing": "border-box",
}


# ---- Account pane ---------------------------------------------------------

def _profile_form() -> rx.Component:
    return rx.el.form(
        rx.el.label("Display name", style={"fontSize": "0.75rem", "fontWeight": "600", "color": "#555"}),
        rx.el.input(
            name="display_name", default_value=RegistryState.display_name,
            placeholder="e.g. anton_k", auto_complete="off", style=_INPUT_STYLE,
        ),
        rx.el.div(
            "letters, digits, underscore · 2–32 chars · used to derive your account handle",
            style={"fontSize": "0.68rem", "color": "#aaa", "margin": "2px 0 8px"},
        ),
        rx.el.label("Email (optional)", style={"fontSize": "0.75rem", "fontWeight": "600", "color": "#555"}),
        rx.el.input(
            name="email", type="email", default_value=RegistryState.email,
            placeholder="you@example.com", auto_complete="off",
            style={**_INPUT_STYLE, "marginBottom": "8px"},
        ),
        rx.el.button(
            fomantic_icon("save", size=12), " Save profile",
            type="submit", class_name="ui tiny primary button", style={"width": "100%"},
        ),
        on_submit=RegistryState.save_profile,
        style={"marginBottom": "6px"},
    )


def _avatar_block() -> rx.Component:
    return rx.el.div(
        rx.cond(
            RegistryState.avatar_local != "",
            rx.el.img(src=RegistryState.avatar_local,
                      style={"width": "52px", "height": "52px", "borderRadius": "50%",
                             "objectFit": "cover", "border": "2px solid #d6c4e8"}),
            rx.el.div(fomantic_icon("user", size=24, color="#c9b3e6"),
                      style={"width": "52px", "height": "52px", "borderRadius": "50%",
                             "background": "#f3eeff", "display": "flex", "alignItems": "center",
                             "justifyContent": "center", "border": "2px solid #d6c4e8"}),
        ),
        rx.upload(
            rx.el.span("Picture", style={"fontSize": "0.72rem", "color": "#6435c9", "cursor": "pointer"}),
            id="reg_avatar", multiple=False,
            accept={"image/png": [".png"], "image/jpeg": [".jpg", ".jpeg"]},
            on_drop=RegistryState.set_avatar(rx.upload_files(upload_id="reg_avatar")),
            style={"display": "contents"},
        ),
        rx.el.span(" local only", style={"fontSize": "0.66rem", "color": "#bbb"}),
        style={"display": "flex", "alignItems": "center", "gap": "8px", "marginBottom": "10px"},
    )


def _token_row() -> rx.Component:
    return rx.el.div(
        rx.el.div("API token", style={"fontSize": "0.72rem", "fontWeight": "600", "color": "#888"}),
        rx.el.div(
            rx.el.code(RegistryState.token_display,
                       style={"flex": "1", "fontSize": "0.72rem", "overflow": "hidden",
                              "textOverflow": "ellipsis", "whiteSpace": "nowrap"}),
            rx.el.button(fomantic_icon("eye", size=12), on_click=RegistryState.toggle_token,
                         class_name="ui mini icon button", title="Reveal / hide",
                         style={"background": "none", "padding": "2px 5px"}),
            rx.el.button(fomantic_icon("copy", size=12),
                         on_click=rx.set_clipboard(RegistryState.token),
                         class_name="ui mini icon button", title="Copy token",
                         style={"background": "none", "padding": "2px 5px"}),
            style={"display": "flex", "alignItems": "center", "gap": "4px",
                   "border": "1px solid #eee", "borderRadius": "5px", "padding": "3px 6px",
                   "background": "#fafafa"},
        ),
        rx.el.div("one token for all your namespaces — back it up",
                  style={"fontSize": "0.66rem", "color": "#bbb", "marginTop": "2px"}),
        style={"marginBottom": "10px"},
    )


def _namespaces_list() -> rx.Component:
    return rx.el.div(
        rx.el.div("Namespaces", style={"fontSize": "0.72rem", "fontWeight": "600", "color": "#888",
                                       "marginBottom": "4px"}),
        rx.foreach(
            RegistryState.roles,
            lambda r: rx.el.div(
                fomantic_icon("hashtag", size=11, color="#a333c8"),
                rx.el.span(r["namespace"], style={"flex": "1", "marginLeft": "5px", "fontSize": "0.82rem",
                                                  "fontFamily": "monospace"}),
                rx.el.span(r["role"], class_name="ui mini label", style={"fontSize": "0.62rem"}),
                on_click=lambda: RegistryState.set_publish_namespace(r["namespace"].to(str)),
                class_name=rx.cond(RegistryState.publish_namespace == r["namespace"],
                                   "reg-ns-item reg-ns-item-active", "reg-ns-item"),
                style={"display": "flex", "alignItems": "center", "padding": "4px 6px",
                       "borderRadius": "4px", "cursor": "pointer", "marginBottom": "2px"},
            ),
        ),
        style={"marginBottom": "10px"},
    )


def _stats_block() -> rx.Component:
    _stat = lambda label, key: rx.el.div(
        rx.el.div(RegistryState.account_stats[key].to(int),
                  style={"fontSize": "1.1rem", "fontWeight": "700", "color": "#6435c9"}),
        rx.el.div(label, style={"fontSize": "0.64rem", "color": "#999"}),
        style={"textAlign": "center", "flex": "1"},
    )
    return rx.el.div(
        _stat("modules", "modules"), _stat("downloads", "downloads"),
        _stat("stars", "stars"), _stat("reviews", "reviews"),
        style={"display": "flex", "gap": "6px", "padding": "8px", "background": "#faf6ff",
               "borderRadius": "6px", "border": "1px solid #eee"},
    )


def _account_pane() -> rx.Component:
    return rx.el.div(
        rx.el.style(
            ".reg-ns-item:hover{background:#f4eefe}"
            " .reg-ns-item-active{background:#efe6fd;box-shadow:inset 3px 0 0 #a333c8}"
        ),
        rx.el.div(
            fomantic_icon("user circle", size=16, color="#a333c8"),
            rx.el.span(" Account", style={"fontSize": "0.95rem", "fontWeight": "700",
                                          "marginLeft": "4px", "color": "#a333c8"}),
            style={"display": "flex", "alignItems": "center", "marginBottom": "10px"},
        ),
        _avatar_block(),
        rx.cond(
            RegistryState.is_registered,
            rx.el.div(
                rx.el.div("Handle", style={"fontSize": "0.72rem", "fontWeight": "600", "color": "#888"}),
                rx.el.code(RegistryState.account,
                           style={"fontSize": "0.82rem", "color": "#a333c8", "display": "block",
                                  "marginBottom": "10px"}),
            ),
            rx.fragment(),
        ),
        _profile_form(),
        rx.cond(
            RegistryState.profile_message != "",
            rx.el.div(RegistryState.profile_message,
                      style={"fontSize": "0.72rem", "color": "#777", "marginBottom": "8px"}),
            rx.fragment(),
        ),
        rx.cond(
            RegistryState.is_registered,
            rx.el.div(_token_row(), _namespaces_list(), _stats_block()),
            rx.el.div("Not registered yet — set a display name, then create your first namespace "
                      "to register and get a token.",
                      style={"fontSize": "0.75rem", "color": "#aaa", "lineHeight": "1.4"}),
        ),
        class_name="ui segment",
        style={"flex": "0 0 300px", "minWidth": "260px", "padding": "12px",
               "border": "1px solid #d6c4e8", "backgroundColor": "#fdfbff"},
    )


# ---- Publish pane ---------------------------------------------------------

def _create_namespace_form() -> rx.Component:
    _hint = rx.match(
        RegistryState.ns_available,
        ("checking", rx.el.span("checking…", style={"color": "#999", "fontSize": "0.72rem"})),
        ("yes", rx.el.span("✓ available", style={"color": "#21ba45", "fontSize": "0.72rem"})),
        ("no", rx.el.span("✗ taken", style={"color": "#db2828", "fontSize": "0.72rem"})),
        ("invalid", rx.el.span("invalid name", style={"color": "#f2711c", "fontSize": "0.72rem"})),
        rx.el.span(""),
    )
    return rx.el.form(
        rx.el.div("Create a namespace", style={"fontSize": "0.8rem", "fontWeight": "600", "color": "#555"}),
        rx.el.div("up to 5 per account · lowercase, digits, hyphens",
                  style={"fontSize": "0.68rem", "color": "#aaa", "margin": "2px 0 6px"}),
        rx.el.div(
            rx.el.input(
                name="new_namespace", default_value=RegistryState.new_namespace,
                placeholder="my-namespace", auto_complete="off",
                on_change=RegistryState.set_new_namespace,
                on_blur=RegistryState.check_namespace, style={**_INPUT_STYLE, "flex": "1"},
            ),
            rx.el.button(fomantic_icon("plus", size=12), " Create", type="submit",
                         disabled=~RegistryState.can_create_namespace | RegistryState.publish_busy,
                         class_name="ui tiny primary button", style={"flexShrink": "0"}),
            style={"display": "flex", "gap": "6px", "alignItems": "center"},
        ),
        _hint,
        rx.cond(
            RegistryState.namespaces_full,
            rx.el.div("Namespace limit reached (5).", style={"fontSize": "0.7rem", "color": "#f2711c"}),
            rx.fragment(),
        ),
        on_submit=RegistryState.create_namespace,
        style={"padding": "10px 12px", "border": "1px dashed #c9b3e6", "borderRadius": "8px",
               "background": "#faf6ff", "marginBottom": "12px"},
    )


def _publish_preview() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.cond(
                RegistryState.selected_logo_url != "",
                rx.el.img(src=RegistryState.selected_logo_url,
                          style={"width": "28px", "height": "28px", "objectFit": "contain",
                                 "borderRadius": "4px"}),
                fomantic_icon("box", size=20, color="#6435c9"),
            ),
            rx.el.div(
                rx.el.div(RegistryState.selected_title,
                          style={"fontWeight": "700", "fontSize": "0.95rem"}),
                rx.el.code(RegistryState.publish_namespace + "/" + RegistryState.selected_catalog_name
                           + "@" + RegistryState.publish_version,
                           style={"fontSize": "0.74rem", "color": "#6435c9"}),
                style={"marginLeft": "8px"},
            ),
            style={"display": "flex", "alignItems": "center"},
        ),
        rx.el.div(
            "Will appear publicly as ",
            rx.el.strong(RegistryState.publish_namespace + "/" + RegistryState.selected_catalog_name),
            ", authored by ", rx.el.strong(RegistryState.account), ".",
            style={"fontSize": "0.76rem", "color": "#777", "marginTop": "8px", "lineHeight": "1.4"},
        ),
        rx.el.div(
            rx.el.span(RegistryState.selected_variant_count, " variants", class_name="ui mini label"),
            rx.el.span(RegistryState.selected_gene_count, " genes", class_name="ui mini label",
                       style={"marginLeft": "4px"}),
            style={"marginTop": "6px"},
        ),
        style={"padding": "12px", "border": "1px solid #d6c4e8", "borderRadius": "8px",
               "background": "linear-gradient(135deg,#faf6ff,#f4f8fe)", "marginBottom": "10px"},
    )


def _publish_controls() -> rx.Component:
    return rx.el.div(
        # New / new-version → publish enabled
        rx.cond(
            RegistryState.can_publish,
            rx.el.div(
                rx.el.div(
                    rx.match(
                        RegistryState.publish_state,
                        ("new", "This publishes the module to the catalog."),
                        ("new_version", "Adds this version on top; existing versions stay published."),
                        "",
                    ),
                    style={"fontSize": "0.76rem", "color": "#777", "marginBottom": "6px"},
                ),
                rx.el.button(
                    rx.cond(RegistryState.publish_busy,
                            rx.el.i("", class_name="spinner loading icon"),
                            fomantic_icon("cloud upload", size=13)),
                    " Publish " + RegistryState.publish_version,
                    on_click=RegistryState.publish_selected,
                    disabled=RegistryState.publish_busy,
                    class_name="ui primary button", style={"width": "100%"},
                ),
            ),
            rx.fragment(),
        ),
        # Already published (identical or yanked) → immutability + yank/unyank
        rx.cond(
            RegistryState.publish_is_published,
            rx.el.div(
                rx.el.div(
                    fomantic_icon("lock", size=12, color="#888"),
                    rx.el.span(" Published & immutable", style={"marginLeft": "4px", "fontWeight": "600"}),
                    style={"fontSize": "0.8rem", "color": "#555", "marginBottom": "4px"},
                ),
                rx.el.code(RegistryState.published_digest,
                           style={"fontSize": "0.68rem", "color": "#999", "wordBreak": "break-all",
                                  "display": "block", "marginBottom": "6px"}),
                rx.el.div(
                    rx.match(
                        RegistryState.publish_state,
                        ("conflict", "Your local copy differs from the published bytes. Bump the version "
                                     "(Edit) to publish changes — published versions never change."),
                        "This exact version is published. To publish changes, bump the version (Edit) — "
                        "a published version's bytes never change.",
                    ),
                    style={"fontSize": "0.74rem", "color": "#777", "lineHeight": "1.4", "marginBottom": "8px"},
                ),
                rx.el.button("Publish (locked)", disabled=True, class_name="ui button",
                             style={"width": "100%", "marginBottom": "6px", "opacity": "0.5"}),
                rx.cond(
                    RegistryState.show_yank,
                    rx.el.button(fomantic_icon("ban", size=12), " Yank this version",
                                 on_click=RegistryState.yank_selected,
                                 disabled=RegistryState.publish_busy,
                                 class_name="ui red button", style={"width": "100%"}),
                    rx.fragment(),
                ),
                rx.cond(
                    RegistryState.show_unyank,
                    rx.el.div(
                        rx.el.div("This version is yanked (hidden from listings).",
                                  style={"fontSize": "0.74rem", "color": "#f2711c", "marginBottom": "4px"}),
                        rx.el.button(fomantic_icon("undo", size=12), " Unyank",
                                     on_click=RegistryState.unyank_selected,
                                     disabled=RegistryState.publish_busy,
                                     class_name="ui orange button", style={"width": "100%"}),
                    ),
                    rx.fragment(),
                ),
            ),
            rx.fragment(),
        ),
    )


def _meta_section() -> rx.Component:
    return rx.cond(
        RegistryState.can_update_meta,
        rx.el.div(
            rx.el.div(
                fomantic_icon("edit", size=12, color="#2185d0"),
                rx.el.span(" Update metadata", style={"marginLeft": "4px", "fontWeight": "600"}),
                style={"fontSize": "0.82rem", "color": "#2185d0", "marginTop": "14px", "marginBottom": "4px"},
            ),
            rx.el.div("Release notes and logo are out-of-digest — updating them needs no version bump.",
                      style={"fontSize": "0.72rem", "color": "#999", "marginBottom": "6px"}),
            rx.el.form(
                rx.el.textarea(name="changelog", placeholder="Release notes for this version…",
                               rows="3", style={**_INPUT_STYLE, "resize": "vertical", "fontFamily": "inherit"}),
                rx.el.button(fomantic_icon("save", size=12), " Update release notes", type="submit",
                             class_name="ui tiny button", style={"marginTop": "6px"}),
                on_submit=RegistryState.update_meta,
            ),
            rx.upload(
                rx.el.span(fomantic_icon("image", size=12), " Replace logo",
                           style={"fontSize": "0.76rem", "color": "#2185d0", "cursor": "pointer"}),
                id="reg_logo", multiple=False,
                accept={"image/png": [".png"], "image/jpeg": [".jpg", ".jpeg"]},
                on_drop=RegistryState.update_logo(rx.upload_files(upload_id="reg_logo")),
                style={"display": "contents"},
            ),
            style={"borderTop": "1px solid #eee", "paddingTop": "6px"},
        ),
        rx.fragment(),
    )


def _publish_pane() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            fomantic_icon("cloud upload", size=16, color="#6435c9"),
            rx.el.span(" Publish", style={"fontSize": "0.95rem", "fontWeight": "700",
                                          "marginLeft": "4px", "color": "#6435c9"}),
            style={"display": "flex", "alignItems": "center", "marginBottom": "10px"},
        ),
        rx.cond(
            ~RegistryState.has_selection,
            rx.el.div(
                fomantic_icon("hand point left outline", size=24, color="#ccc"),
                rx.el.div("Select a module on the left to publish it.",
                          style={"color": "#999", "fontSize": "0.85rem", "marginTop": "8px"}),
                style={"textAlign": "center", "padding": "30px 16px"},
            ),
            rx.cond(
                ~RegistryState.display_name_valid,
                rx.el.div(
                    fomantic_icon("arrow left", size=18, color="#a333c8"),
                    rx.el.span(" Set a valid display name in the Account pane to start publishing.",
                               style={"marginLeft": "6px", "fontSize": "0.85rem", "color": "#777"}),
                    style={"padding": "20px 8px"},
                ),
                rx.el.div(
                    _create_namespace_form(),
                    rx.cond(
                        RegistryState.namespaces.length() > 0,
                        rx.el.div(
                            rx.el.label("Publish to namespace",
                                        style={"fontSize": "0.72rem", "fontWeight": "600", "color": "#888"}),
                            rx.el.select(
                                rx.foreach(RegistryState.namespaces,
                                           lambda ns: rx.el.option(ns, value=ns)),
                                value=RegistryState.publish_namespace,
                                on_change=RegistryState.set_publish_namespace,
                                style={**_INPUT_STYLE, "marginBottom": "10px"},
                            ),
                            _publish_preview(),
                            _publish_controls(),
                            _meta_section(),
                        ),
                        rx.fragment(),
                    ),
                ),
            ),
        ),
        rx.cond(
            RegistryState.publish_message != "",
            rx.el.div(RegistryState.publish_message,
                      style={"fontSize": "0.76rem", "color": "#555", "marginTop": "10px",
                             "padding": "6px 8px", "background": "#f8f8f8", "borderRadius": "5px"}),
            rx.fragment(),
        ),
        class_name="ui segment",
        style={"flex": "1 1 380px", "minWidth": "320px", "padding": "12px",
               "border": "1px solid #c5daf5", "backgroundColor": "#fdfdff"},
    )


def _publication_tab() -> rx.Component:
    """Two panes: Account (identity/namespaces/stats) + Publish (create-namespace + publish flow)."""
    return rx.el.div(
        _account_pane(),
        _publish_pane(),
        style={"display": "flex", "gap": "16px", "flexWrap": "wrap", "alignItems": "flex-start"},
    )


def _incompatible_banner() -> rx.Component:
    """Prominent banner when the registry server's contract is newer than this client."""
    return rx.cond(
        RegistryState.server_incompatible,
        rx.el.div(
            fomantic_icon("exclamation triangle", size=16, color="#9f3a38"),
            rx.el.span(
                " Catalog server is newer than this app — update just-dna-lite to browse or install.",
                style={"marginLeft": "6px"},
            ),
            class_name="ui small error message",
            style={"display": "block", "marginBottom": "10px"},
        ),
        rx.fragment(),
    )


def registry_right_panel() -> rx.Component:
    return rx.el.div(
        _incompatible_banner(),
        _tab_menu(),
        rx.el.div(
            rx.match(
                RegistryState.registry_active_tab,
                ("catalog", _catalog_tab()),
                ("publication", _publication_tab()),
                _catalog_tab(),
            ),
            class_name="ui bottom attached segment",
            style={"padding": "16px", "minHeight": "400px"},
        ),
    )


# ============================================================================
# MAIN PAGE
# ============================================================================

@rx.page(
    route="/registry",
    title="Module Catalog | Just DNA Lite",
    on_load=RegistryState.load_registry,
    meta=page_meta("/registry"),
    image=page_image_url(),
)
def registry_page() -> rx.Component:
    """Module Registry — catalog browse/install + local registry management."""
    return template(
        two_column_layout(
            left=registry_left_panel(),
            right=registry_right_panel(),
        ),
    )
