"""
FAQ page — loads content from docs/FAQ.md and renders it as markdown.

Shown in all modes (normal and immutable) via the topbar nav tab.
Accessible at /faq.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

import reflex as rx

from webui.components.layout import template, fomantic_icon
from webui.state import UploadState


class _TocEntry(NamedTuple):
    anchor: str
    title: str


def _slug(text: str) -> str:
    """Convert heading text to a URL-friendly anchor slug."""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s]+", "-", s)
    return s


def _load_faq_markdown() -> tuple[str, list[_TocEntry]]:
    """Read docs/FAQ.md, strip the H1 title, and extract H2 headings for a TOC."""
    root = Path(__file__).resolve().parents[4]
    faq_path = root / "docs" / "FAQ.md"
    if not faq_path.exists():
        return "FAQ content not found. Please check that `docs/FAQ.md` exists.", []

    raw = faq_path.read_text(encoding="utf-8")

    lines = raw.split("\n")
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    content = "\n".join(lines).lstrip("\n")

    toc: list[_TocEntry] = []
    for line in lines:
        m = re.match(r"^##\s+(.+)$", line)
        if m:
            title = m.group(1).strip()
            toc.append(_TocEntry(anchor=_slug(title), title=title))

    return content, toc


_FAQ_CONTENT, _FAQ_TOC = _load_faq_markdown()

_FAQ_CSS = """
.faq-toc {
    background: #f8f9fb;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 16px 24px;
    margin-bottom: 28px;
}
.faq-toc-title {
    font-size: 1rem;
    font-weight: 600;
    color: #333;
    margin-bottom: 10px;
}
.faq-toc ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 8px 20px;
}
.faq-toc li a {
    color: #2185d0;
    text-decoration: none;
    font-size: 0.95rem;
    line-height: 1.8;
}
.faq-toc li a:hover {
    text-decoration: underline;
}
.faq-body h2 {
    border-bottom: 2px solid #2185d0;
    padding-bottom: 8px;
    margin-top: 40px;
    margin-bottom: 20px;
    color: #1a1a1a;
    font-size: 1.4rem;
}
.faq-body h3 {
    margin-top: 28px;
    margin-bottom: 8px;
    color: #333;
    font-size: 1.1rem;
}
.faq-body p {
    line-height: 1.7;
    color: #444;
    margin-bottom: 12px;
}
.faq-body a {
    color: #2185d0;
    text-decoration: none;
}
.faq-body a:hover {
    text-decoration: underline;
}
.faq-body ul, .faq-body ol {
    padding-left: 24px;
    margin-bottom: 12px;
}
.faq-body li {
    margin-bottom: 6px;
    line-height: 1.6;
}
.faq-body code {
    background-color: #f0f0f0;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.9em;
}
.faq-body pre {
    background-color: #f5f5f5;
    padding: 12px 16px;
    border-radius: 6px;
    overflow-x: auto;
    margin-bottom: 16px;
}
.faq-body hr {
    border: none;
    border-top: 1px solid #e0e0e0;
    margin: 32px 0;
}
.faq-body strong {
    color: #222;
}
"""


def _toc_component() -> rx.Component:
    """Table of contents linking to each FAQ section."""
    if not _FAQ_TOC:
        return rx.fragment()
    items = [
        rx.el.li(rx.el.a(entry.title, href=f"#{entry.anchor}"))
        for entry in _FAQ_TOC
    ]
    return rx.el.nav(
        rx.el.div("Contents", class_name="faq-toc-title"),
        rx.el.ul(*items),
        class_name="faq-toc",
    )


def _faq_content() -> rx.Component:
    """Main FAQ content rendered from markdown."""
    return rx.el.div(
        rx.el.style(_FAQ_CSS),
        rx.el.div(
            fomantic_icon("help circle", size=40, color="#2185d0"),
            rx.el.h1(
                "Frequently Asked Questions",
                class_name="ui huge header",
                style={"marginTop": "10px"},
            ),
            style={"textAlign": "center", "marginBottom": "20px"},
        ),
        _toc_component(),
        rx.el.div(
            rx.markdown(
                _FAQ_CONTENT,
                rehype_plugins=[
                    rx.markdown.plugin("rehype-slug@6.0.0", "rehypeSlug"),
                ],
            ),
            class_name="faq-body",
        ),
        style={"maxWidth": "860px", "margin": "0 auto", "padding": "40px 20px"},
    )


@rx.page(route="/faq", title="FAQ | Just DNA Lite", on_load=UploadState.on_load)
def faq_page() -> rx.Component:
    """FAQ page."""
    return template(_faq_content())
