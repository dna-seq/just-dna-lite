"""
Module Marketplace page — browse the remote catalog, install/uninstall modules,
and inspect the local registry cross-referenced against the catalog.

Left panel:  fixed selected-module details card (status-aware controls) + narrow local list.
Right panel: two tabs — Catalog (download+register) and Publication (deferred stub).
"""
from __future__ import annotations

import reflex as rx

from webui.components.layout import template, two_column_layout, fomantic_icon
from webui.crawler_assets import page_image_url, page_meta
from webui.state import MarketplaceState


# ============================================================================
# LEFT PANEL — selected module details + local list
# ============================================================================

def _status_badge() -> rx.Component:
    """Colored pill reflecting the selected module's install/catalog status."""
    return rx.el.span(
        MarketplaceState.sel_status_label,
        style={
            "display": "inline-block",
            "fontSize": "0.72rem",
            "fontWeight": "700",
            "padding": "2px 10px",
            "borderRadius": "10px",
            "color": "#fff",
            "backgroundColor": MarketplaceState.sel_status_color,
        },
    )


def _gate_banner() -> rx.Component:
    """Confirm/cancel banner shown before a destructive/replacing action."""
    return rx.cond(
        MarketplaceState.has_pending,
        rx.el.div(
            rx.el.div(
                fomantic_icon("exclamation triangle", size=14, color="#b58105"),
                rx.el.span(
                    MarketplaceState.pending_warn,
                    style={"fontSize": "0.82rem", "color": "#7a5c00", "marginLeft": "6px"},
                ),
                style={"display": "flex", "alignItems": "flex-start"},
            ),
            rx.el.div(
                rx.el.button(
                    "Proceed",
                    on_click=MarketplaceState.confirm_pending,
                    class_name="ui mini red button",
                    style={"marginRight": "6px"},
                ),
                rx.el.button(
                    "Cancel",
                    on_click=MarketplaceState.cancel_pending,
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
                MarketplaceState.selected_versions,
                lambda v: rx.el.option(v, value=v),
            ),
            value=MarketplaceState.selected_version,
            on_change=MarketplaceState.set_selected_version,
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
            MarketplaceState.show_download,
            rx.el.button(
                rx.cond(
                    MarketplaceState.action_busy,
                    rx.el.i("", class_name="spinner loading icon"),
                    fomantic_icon("download", size=13),
                ),
                " Get from marketplace",
                on_click=MarketplaceState.request_download,
                disabled=MarketplaceState.action_busy,
                class_name="ui small primary button",
                style={"flex": "1"},
            ),
            rx.fragment(),
        ),
        # Local actions
        rx.cond(
            MarketplaceState.show_local_actions,
            rx.fragment(
                rx.el.button(
                    fomantic_icon("edit", size=13),
                    " Edit",
                    on_click=MarketplaceState.edit_selected,
                    disabled=~MarketplaceState.edit_enabled,
                    class_name="ui small button",
                    style={"flex": "1"},
                    title="Load into the Module Manager editing slot",
                ),
                rx.el.a(
                    fomantic_icon("download", size=13),
                    " Export",
                    href=MarketplaceState.export_url,
                    class_name="ui small teal button",
                    style={"flex": "1", "textAlign": "center"},
                ),
                rx.el.button(
                    fomantic_icon("trash alternate", size=13),
                    " Uninstall",
                    on_click=MarketplaceState.request_uninstall,
                    disabled=MarketplaceState.action_busy,
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
        on_drop=MarketplaceState.upload_import(rx.upload_files(upload_id=upload_id)),
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
            MarketplaceState.has_selection,
            rx.el.div(
                # Title + status
                rx.el.div(
                    rx.cond(
                        MarketplaceState.selected_logo_url != "",
                        rx.el.img(
                            src=MarketplaceState.selected_logo_url,
                            style={"width": "22px", "height": "22px", "objectFit": "contain",
                                   "borderRadius": "3px", "marginRight": "6px"},
                        ),
                        rx.fragment(),
                    ),
                    rx.el.span(
                        MarketplaceState.selected_title,
                        style={"fontSize": "1rem", "fontWeight": "700", "color": "#333", "flex": "1"},
                    ),
                    _status_badge(),
                    style={"display": "flex", "alignItems": "center", "gap": "8px"},
                ),
                rx.el.div(
                    MarketplaceState.selected_name,
                    rx.cond(
                        MarketplaceState.selected_namespace != "",
                        rx.el.span(
                            " · ", MarketplaceState.selected_namespace,
                            style={"color": "#a333c8"},
                        ),
                        rx.fragment(),
                    ),
                    style={"fontSize": "0.78rem", "color": "#999", "fontFamily": "monospace", "marginTop": "2px"},
                ),
                rx.cond(
                    MarketplaceState.selected_author != "",
                    rx.el.div(
                        fomantic_icon("user", size=11, color="#888"),
                        rx.el.span(" ", MarketplaceState.selected_author, style={"marginLeft": "3px"}),
                        style={"fontSize": "0.78rem", "color": "#888", "marginTop": "4px", "display": "flex", "alignItems": "center"},
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    MarketplaceState.selected_description != "",
                    rx.el.div(
                        MarketplaceState.selected_description,
                        style={"fontSize": "0.8rem", "color": "#666", "marginTop": "6px", "lineHeight": "1.4"},
                    ),
                    rx.fragment(),
                ),
                # Stats
                rx.el.div(
                    rx.el.span(MarketplaceState.selected_variant_count, " variants", class_name="ui mini label"),
                    rx.el.span(MarketplaceState.selected_gene_count, " genes", class_name="ui mini label", style={"marginLeft": "4px"}),
                    rx.cond(
                        MarketplaceState.selected_clinvar_count > 0,
                        rx.el.span(
                            MarketplaceState.selected_pathogenic_count, " path / ",
                            MarketplaceState.selected_benign_count, " benign",
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
                    MarketplaceState.action_message != "",
                    rx.el.div(
                        MarketplaceState.action_message,
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
        on_click=lambda: MarketplaceState.select_local(name),
        class_name=rx.cond(
            MarketplaceState.selected_name == name,
            "marketplace-local-item marketplace-local-item-active",
            "marketplace-local-item",
        ),
        style={
            "display": "flex", "alignItems": "center", "padding": "6px 8px",
            "borderRadius": "4px", "cursor": "pointer", "marginBottom": "2px",
        },
    )


def _local_list() -> rx.Component:
    return rx.el.div(
        rx.el.style(
            ".marketplace-local-item:hover { background-color: #f0f4fb; }"
            " .marketplace-local-item-active { background-color: #e8f0fe; box-shadow: inset 3px 0 0 #2185d0; }"
        ),
        rx.el.div(
            fomantic_icon("folder open", size=15, color="#2185d0"),
            rx.el.span(
                " Installed modules",
                style={"fontSize": "0.9rem", "fontWeight": "600", "marginLeft": "4px", "color": "#2185d0"},
            ),
            rx.el.span(
                MarketplaceState.local_modules.length(),
                class_name="ui mini label",
                style={"marginLeft": "auto"},
            ),
            style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
        ),
        rx.cond(
            MarketplaceState.local_modules.length() > 0,
            rx.foreach(MarketplaceState.local_modules, _local_list_item),
            rx.el.div(
                "No modules installed yet.",
                style={"fontSize": "0.8rem", "color": "#aaa", "padding": "6px 4px"},
            ),
        ),
        class_name="ui segment",
        style={"padding": "10px 12px", "border": "1px solid #c5daf5", "backgroundColor": "#f8fbff"},
    )


def marketplace_left_panel() -> rx.Component:
    return rx.el.div(
        _selected_card(),
        # Upload/import sits between the details pane and the list, separating them.
        rx.el.div(
            _upload_import_button("marketplace_import"),
            style={"margin": "4px 0 14px"},
        ),
        _local_list(),
        id="marketplace-left-panel",
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
            fomantic_icon("shopping bag", size=16,
                          color=rx.cond(MarketplaceState.marketplace_active_tab == "catalog", "#00b5ad", "#888")),
            " Catalog",
            class_name=rx.cond(MarketplaceState.marketplace_active_tab == "catalog", "active item", "item"),
            on_click=lambda: MarketplaceState.switch_marketplace_tab("catalog"),
            style=_TAB_STYLE,
        ),
        rx.el.a(
            fomantic_icon("upload", size=16,
                          color=rx.cond(MarketplaceState.marketplace_active_tab == "publication", "#2185d0", "#888")),
            " Publication",
            class_name=rx.cond(MarketplaceState.marketplace_active_tab == "publication", "active item", "item"),
            on_click=lambda: MarketplaceState.switch_marketplace_tab("publication"),
            style=_TAB_STYLE,
        ),
        class_name="ui top attached tabular menu",
        style={"marginBottom": "0"},
        id="marketplace-tab-menu",
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
                on_click=lambda: MarketplaceState.select_catalog(namespace, name),
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
                    on_click=lambda: MarketplaceState.quick_install(namespace, name, latest),
                    disabled=MarketplaceState.action_busy,
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
                value=MarketplaceState.group_filter,
                on_change=MarketplaceState.set_group_filter,
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
                    MarketplaceState.namespace_options,
                    lambda ns: rx.el.option(ns, value=ns),
                ),
                value=MarketplaceState.namespace_filter,
                on_change=MarketplaceState.set_namespace_filter,
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
                    default_value=MarketplaceState.query,
                    on_change=MarketplaceState.set_query,
                    on_blur=MarketplaceState.search,
                    style={"border": "none", "outline": "none", "flex": "1", "fontSize": "0.9rem", "marginLeft": "6px"},
                ),
                rx.el.button(
                    "Search",
                    on_click=MarketplaceState.search,
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
                value=MarketplaceState.sort,
                on_change=MarketplaceState.set_sort,
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
            rx.el.strong("Marketplace is a work in progress. "),
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
            MarketplaceState.catalog_error != "",
            rx.el.div(
                fomantic_icon("exclamation circle", size=14, color="#db2828"),
                rx.el.span(" ", MarketplaceState.catalog_error, style={"marginLeft": "4px"}),
                class_name="ui small warning message",
                style={"display": "block"},
            ),
            rx.fragment(),
        ),
        rx.cond(
            MarketplaceState.catalog_loading,
            rx.el.div(
                rx.el.i("", class_name="spinner loading icon"),
                " Loading catalog…",
                style={"padding": "20px", "color": "#888"},
            ),
            rx.cond(
                MarketplaceState.cards.length() > 0,
                rx.el.div(
                    rx.foreach(MarketplaceState.cards, _catalog_card),
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
                on_click=MarketplaceState.prev_page,
                disabled=~MarketplaceState.can_prev,
                class_name="ui tiny button",
            ),
            rx.el.span(
                "Page ", MarketplaceState.page,
                style={"fontSize": "0.82rem", "color": "#777", "margin": "0 10px"},
            ),
            rx.el.button(
                "Next ›",
                on_click=MarketplaceState.next_page,
                disabled=~MarketplaceState.can_next,
                class_name="ui tiny button",
            ),
            style={"display": "flex", "alignItems": "center", "justifyContent": "center", "marginTop": "16px"},
        ),
        style={"padding": "4px 2px"},
    )


def _publication_tab() -> rx.Component:
    """Deferred: message when nothing selected, WIP pane when a module is selected."""
    return rx.cond(
        MarketplaceState.has_selection,
        rx.el.div(
            fomantic_icon("wrench", size=32, color="#d6c4e8"),
            rx.el.div(
                "Publication — work in progress",
                style={"fontSize": "1rem", "fontWeight": "600", "color": "#6435c9", "marginTop": "10px"},
            ),
            rx.el.div(
                rx.el.span("Selected: "),
                rx.el.strong(MarketplaceState.selected_title),
                style={"fontSize": "0.85rem", "color": "#777", "marginTop": "6px"},
            ),
            # Roles / connection (0.7.1 namespace membership)
            rx.cond(
                MarketplaceState.account != "",
                rx.el.div(
                    fomantic_icon("user", size=12, color="#21ba45"),
                    rx.el.span(" Connected as ", MarketplaceState.account,
                               " · can publish to: ", MarketplaceState.namespaces.join(", "),
                               style={"marginLeft": "4px"}),
                    style={"fontSize": "0.8rem", "color": "#21ba45", "marginTop": "8px",
                           "display": "flex", "alignItems": "center", "justifyContent": "center"},
                ),
                rx.el.div(
                    "Not connected — account onboarding (install-id → register → claim namespace) "
                    "lands here. Owner and contributor roles will gate publishing.",
                    style={"fontSize": "0.78rem", "color": "#aaa", "marginTop": "8px", "maxWidth": "420px",
                           "lineHeight": "1.4"},
                ),
            ),
            rx.el.div(
                "Publishing this module to the marketplace (onboarding, namespace claim, upload) "
                "will land here in a future update.",
                style={"fontSize": "0.82rem", "color": "#999", "marginTop": "8px", "maxWidth": "420px",
                       "lineHeight": "1.4"},
            ),
            style={"textAlign": "center", "padding": "40px 16px"},
        ),
        rx.el.div(
            fomantic_icon("hand point left outline", size=28, color="#ccc"),
            rx.el.div(
                "Select a module on the left to publish it.",
                style={"color": "#999", "fontSize": "0.9rem", "marginTop": "10px"},
            ),
            style={"textAlign": "center", "padding": "40px 16px"},
        ),
    )


def _incompatible_banner() -> rx.Component:
    """Prominent banner when the marketplace server's contract is newer than this client."""
    return rx.cond(
        MarketplaceState.server_incompatible,
        rx.el.div(
            fomantic_icon("exclamation triangle", size=16, color="#9f3a38"),
            rx.el.span(
                " Marketplace server is newer than this app — update just-dna-lite to browse or install.",
                style={"marginLeft": "6px"},
            ),
            class_name="ui small error message",
            style={"display": "block", "marginBottom": "10px"},
        ),
        rx.fragment(),
    )


def marketplace_right_panel() -> rx.Component:
    return rx.el.div(
        _incompatible_banner(),
        _tab_menu(),
        rx.el.div(
            rx.match(
                MarketplaceState.marketplace_active_tab,
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
    route="/marketplace",
    title="Module Marketplace | Just DNA Lite",
    on_load=MarketplaceState.load_marketplace,
    meta=page_meta("/marketplace"),
    image=page_image_url(),
)
def marketplace_page() -> rx.Component:
    """Module Marketplace — catalog browse/install + local registry management."""
    return template(
        two_column_layout(
            left=marketplace_left_panel(),
            right=marketplace_right_panel(),
        ),
    )
