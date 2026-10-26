"""`manuscript build` → `<stem>.docx`: tables that stay readable in Word, LibreOffice and Google Docs.

Both v0.5 masters are converted once per session. Every expectation is derived at test time: the
tables, their columns and their group-heading rows from pandoc's own reading of the clean twin, the
token widths from the Arial font file (the table font), so the checks follow the masters as they
change. The rendering itself (LibreOffice to PDF, pages looked at) is the manual release step.
"""

from __future__ import annotations

import json
import re
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path
from typing import Any, Optional

import pytest
from matplotlib.font_manager import FontProperties, findfont
from matplotlib.ft2font import FT2Font, LoadFlags
from pydantic import BaseModel, ConfigDict

from just_dna_lite.manuscript import build
from just_dna_lite.manuscript.build import (
    A4_HEIGHT_TWIPS,
    A4_WIDTH_TWIPS,
    CELL_MARGIN_TWIPS,
    DOCX_MARGIN_TWIPS,
    DOCX_TABLE_FILTER,
    FIGURE_IMAGE_STYLE,
    TABLE_FONT,
    TABLE_FONT_PT,
    TABLE_HEADING_STYLE,
    TABLE_CODE_STYLE,
    TABLE_TEXT_STYLE,
    TABLE_TITLE_STYLE,
    build_paths,
    markdown_to_docx,
    write_clean_twin,
)

pytestmark = pytest.mark.skipif(build.pypandoc is None, reason="pypandoc (dev dependency group) is not installed")

ROOT = Path(__file__).resolve().parents[1]
ROUND = ROOT / "docs/manuscript/v0.6"
PAPER = ROUND / "paper1-just-dna-lite.md"
SUPPLEMENT = ROUND / "paper1-just-dna-lite-supplementary.md"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
PIC = "{http://schemas.openxmlformats.org/drawingml/2006/picture}"
EMU_PER_POINT = 12700
PORTRAIT_TEXT_WIDTH = A4_WIDTH_TWIPS - 2 * DOCX_MARGIN_TWIPS
LANDSCAPE_TEXT_WIDTH = A4_HEIGHT_TWIPS - 2 * DOCX_MARGIN_TWIPS
SCRIPT_SCALE = 0.65  # superscripts are set at about two thirds of the text size
_FIGURE_CAPTION_RE = re.compile(r"(?m)^\*\*Figure S?[0-9]+\.")
_CAPTION_RE = re.compile(r"^(?:Table S?|Box )[0-9]+\.")


class SourceTable(BaseModel):
    """A table as pandoc's Markdown reader sees it: the expectation, independent of the filter."""

    model_config = ConfigDict(frozen=True)

    caption: Optional[str]
    columns: int
    group_labels: list[str]


class DocxTable(BaseModel):
    """A top-level table in document.xml, with the section (page) it sits in."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    caption: Optional[str]
    element: Any
    orientation: str
    text_width: int
    previous: Any  # the body element before the table (its caption, when there is one)
    before_previous: Any


# --- reading the source with pandoc -------------------------------------------------------------


def plain_text(node: Any) -> str:
    """The words of a pandoc JSON node: Str contents and spaces (attributes and URLs are skipped)."""
    if isinstance(node, dict):
        kind = node.get("t")
        if kind == "Str":
            return node["c"]
        if kind in ("Space", "SoftBreak", "LineBreak"):
            return " "
        if kind == "Code":
            return node["c"][1]
        return plain_text(node.get("c", []))
    if isinstance(node, list):
        return "".join(plain_text(child) for child in node)
    return ""


def caption_label(text: str) -> Optional[str]:
    """"Table S7." for a paragraph that opens with that label, else None."""
    found = _CAPTION_RE.match(text.strip())
    return None if found is None else found.group(0)


def source_tables(clean: Path) -> list[SourceTable]:
    document = json.loads(build.pypandoc.convert_file(str(clean), "json", format="markdown"))
    tables: list[SourceTable] = []
    previous: Optional[dict] = None
    for block in document["blocks"]:
        if block["t"] == "Table":
            _attr, _caption, colspecs, _head, bodies, _foot = block["c"]
            labels = []
            for _body_attr, _row_head_columns, _intermediate, rows in bodies:
                for _row_attr, cells in rows:
                    texts = [plain_text(cell[4]).strip() for cell in cells]
                    if len(texts) > 1 and texts[0] and not any(texts[1:]):
                        labels.append(texts[0])
            caption = caption_label(plain_text(previous)) if previous is not None and previous["t"] == "Para" else None
            tables.append(SourceTable(caption=caption, columns=len(colspecs), group_labels=labels))
        previous = block
    return tables


# --- reading the .docx --------------------------------------------------------------------------


def read_part(docx: Path, name: str) -> ET.Element:
    with zipfile.ZipFile(docx) as archive:
        return ET.fromstring(archive.read(name))


def text_of(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.iter(f"{W}t"))


def paragraph_style(paragraph: ET.Element) -> Optional[str]:
    style = paragraph.find(f"{W}pPr/{W}pStyle")
    return None if style is None else style.get(f"{W}val")


def section_of(element: ET.Element) -> Optional[ET.Element]:
    if element.tag == f"{W}sectPr":
        return element
    if element.tag == f"{W}p":
        return element.find(f"{W}pPr/{W}sectPr")
    return None


def docx_tables(docx: Path) -> list[DocxTable]:
    body = read_part(docx, "word/document.xml").find(f"{W}body")
    assert body is not None
    children = list(body)
    pending: list[dict] = []
    tables: list[DocxTable] = []
    for index, child in enumerate(children):
        if child.tag == f"{W}tbl":
            previous = children[index - 1] if index > 0 else None
            pending.append(
                {
                    "caption": caption_label(text_of(previous)) if previous is not None and previous.tag == f"{W}p" else None,
                    "element": child,
                    "previous": previous,
                    "before_previous": children[index - 2] if index > 1 else None,
                }
            )
            continue
        section = section_of(child)
        if section is None:
            continue
        size, margins = section.find(f"{W}pgSz"), section.find(f"{W}pgMar")
        assert size is not None and margins is not None
        width = int(size.get(f"{W}w")) - int(margins.get(f"{W}left")) - int(margins.get(f"{W}right"))
        orientation = size.get(f"{W}orient", "portrait")
        tables.extend(DocxTable(orientation=orientation, text_width=width, **table) for table in pending)
        pending = []
    assert not pending, "tables after the document's last section"
    return tables


def grid(table: ET.Element) -> list[int]:
    return [int(column.get(f"{W}w")) for column in table.findall(f"{W}tblGrid/{W}gridCol")]


def cells(row: ET.Element) -> list[ET.Element]:
    return row.findall(f"{W}tc")


def span(cell: ET.Element) -> int:
    found = cell.find(f"{W}tcPr/{W}gridSpan")
    return 1 if found is None else int(found.get(f"{W}val"))


# --- token widths from the font file ------------------------------------------------------------


class FontMetrics:
    """Advance widths in points per point of size, read from the installed Arial (or its metric twin
    Liberation Sans): the ground truth the filter's built-in estimate must not undercut."""

    def __init__(self) -> None:
        paths = self._find()
        self._fonts = {bold: FT2Font(str(path)) for bold, path in paths.items()}
        for font in self._fonts.values():
            font.set_size(1, 72)

    @staticmethod
    def _find() -> dict[bool, Path]:
        for family in (TABLE_FONT, "Liberation Sans"):
            try:
                regular = findfont(FontProperties(family=family), fallback_to_default=False)
                bold = findfont(FontProperties(family=family, weight="bold"), fallback_to_default=False)
            except ValueError:
                continue
            return {False: Path(regular), True: Path(bold)}
        pytest.skip(f"neither {TABLE_FONT} nor Liberation Sans is installed to measure table text with")

    def advance(self, character: str, bold: bool) -> float:
        glyph = self._fonts[bold].load_char(ord(character), flags=LoadFlags.NO_HINTING)
        return glyph.linearHoriAdvance / 65536


class StyleSheet:
    """Size and bold of a paragraph style, following `basedOn` down to the document defaults."""

    def __init__(self, docx: Path) -> None:
        root = read_part(docx, "word/styles.xml")
        self._styles = {style.get(f"{W}styleId"): style for style in root.iter(f"{W}style")}
        default = root.find(f"{W}docDefaults/{W}rPrDefault/{W}rPr/{W}sz")
        self._default_size = 10.0 if default is None else int(default.get(f"{W}val")) / 2

    def _lookup(self, style_id: Optional[str], path: str) -> Optional[ET.Element]:
        while style_id is not None and style_id in self._styles:
            style = self._styles[style_id]
            found = style.find(path)
            if found is not None:
                return found
            based_on = style.find(f"{W}basedOn")
            style_id = None if based_on is None else based_on.get(f"{W}val")
        return None

    def size(self, style_id: Optional[str]) -> float:
        found = self._lookup(style_id, f"{W}rPr/{W}sz")
        return self._default_size if found is None else int(found.get(f"{W}val")) / 2

    def bold(self, style_id: Optional[str]) -> bool:
        return is_on(self._lookup(style_id, f"{W}rPr/{W}b"))


def is_on(toggle: Optional[ET.Element]) -> bool:
    return toggle is not None and toggle.get(f"{W}val", "true") not in ("0", "false")


def widest_token_twips(cell: ET.Element, metrics: FontMetrics, sheet: StyleSheet) -> float:
    """The widest run of text in *cell* with no line-break opportunity, in twips, at the size and
    weight the docx asks for (run properties over the paragraph style).

    Breaks: whitespace, paragraph ends, after an en or em dash, after a hyphen not followed by a
    digit (the same rule the filter uses; LibreOffice also breaks inside dates, which only helps).
    """
    widest = 0.0
    for paragraph in cell.iter(f"{W}p"):
        style = paragraph_style(paragraph)
        characters: list[tuple[str, float]] = []
        for run in paragraph.iter(f"{W}r"):
            properties = run.find(f"{W}rPr")
            if properties is None:
                properties = ET.Element(f"{W}rPr")
            bold = is_on(properties.find(f"{W}b")) or sheet.bold(style)
            size = properties.find(f"{W}sz")
            points = sheet.size(style) if size is None else int(size.get(f"{W}val")) / 2
            align = properties.find(f"{W}vertAlign")
            if align is not None and align.get(f"{W}val") in ("superscript", "subscript"):
                points *= SCRIPT_SCALE
            for node in run.iter(f"{W}t"):
                characters.extend((c, metrics.advance(c, bold) * points) for c in node.text or "")
        token = 0.0
        for index, (character, width) in enumerate(characters):
            if character.isspace():
                token = 0.0
                continue
            token += width
            widest = max(widest, token)
            following = characters[index + 1][0] if index + 1 < len(characters) else ""
            if character in "–—" or (character == "-" and not following.isdigit()):
                token = 0.0
    return widest * 20


# --- fixtures -----------------------------------------------------------------------------------


@pytest.fixture(scope="session", params=[PAPER, SUPPLEMENT], ids=["paper", "supplementary"])
def built(request, tmp_path_factory) -> tuple[Path, Path]:
    """(clean twin, .docx) of one real v0.5 master, read fresh: the masters keep changing."""
    source: Path = request.param
    paths = build_paths(source, tmp_path_factory.mktemp(source.stem))
    write_clean_twin(source, paths.clean)
    markdown_to_docx(paths.clean, paths.docx, source.parent)
    return paths.clean, paths.docx


def tiny_png(path: Path, width: int, height: int) -> Path:
    """A valid grey PNG of the given pixel size, written without an imaging library."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    rows = b"".join(b"\x00" + b"\x80" * width for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
    return path


# --- tests --------------------------------------------------------------------------------------


def test_the_filter_ships_inside_the_package() -> None:
    assert DOCX_TABLE_FILTER.is_file()
    assert DOCX_TABLE_FILTER.parent.parent == Path(build.__file__).parent


def test_every_source_table_arrives_with_a_grid_of_its_columns(built: tuple[Path, Path]) -> None:
    clean, docx = built
    expected, found = source_tables(clean), docx_tables(docx)
    assert expected, f"{clean.name} has no tables to check"
    assert [t.columns for t in expected] == [len(grid(t.element)) for t in found]
    assert [t.caption for t in expected] == [t.caption for t in found]
    for table in found:
        properties = table.element.find(f"{W}tblPr")
        width = properties.find(f"{W}tblW")
        assert width.get(f"{W}type") == "dxa"
        assert int(width.get(f"{W}w")) == sum(grid(table.element)) <= table.text_width
        for row in table.element.findall(f"{W}tr"):
            assert row.find(f"{W}trPr/{W}cantSplit") is not None
            column = 0
            for cell in cells(row):
                cell_width = int(cell.find(f"{W}tcPr/{W}tcW").get(f"{W}w"))
                assert cell_width == sum(grid(table.element)[column : column + span(cell)])
                column += span(cell)
            assert column == len(grid(table.element))


def test_no_column_is_narrower_than_its_widest_word(built: tuple[Path, Path]) -> None:
    """The bug: equal columns broke "Generation II" and "(16.2–17.2)" mid-word."""
    _clean, docx = built
    metrics, sheet = FontMetrics(), StyleSheet(docx)
    for table in docx_tables(docx):
        columns = grid(table.element)
        for row_index, row in enumerate(table.element.findall(f"{W}tr")):
            column = 0
            for cell in cells(row):
                if span(cell) == 1:
                    needed = widest_token_twips(cell, metrics, sheet) + 2 * CELL_MARGIN_TWIPS
                    assert columns[column] >= needed, (
                        f"{table.caption} row {row_index} column {column + 1}: grid {columns[column]} twips, "
                        f"the widest word of {text_of(cell)!r} needs {needed:.0f}"
                    )
                column += span(cell)


def test_group_heading_rows_span_the_table(built: tuple[Path, Path]) -> None:
    clean, docx = built
    expected, found = source_tables(clean), docx_tables(docx)
    assert any(t.group_labels for t in expected), f"{clean.name} has no group-heading rows to check"
    for source, table in zip(expected, found):
        spanning = [
            text_of(row).strip()
            for row in table.element.findall(f"{W}tr")
            if len(cells(row)) == 1 and span(cells(row)[0]) == source.columns
        ]
        assert spanning == source.group_labels, table.caption


def test_only_the_tables_too_wide_for_portrait_turn_the_page(built: tuple[Path, Path]) -> None:
    """Table S7 (11 columns) gets landscape pages with its caption; every other table, and every
    page before and after it, stays portrait."""
    clean, docx = built
    tables = docx_tables(docx)
    landscape = {t.caption for t in tables if t.orientation == "landscape"}
    assert landscape == ({"Table S7."} if clean.name.startswith(SUPPLEMENT.stem) else set())
    for table in tables:
        expected_width = LANDSCAPE_TEXT_WIDTH if table.orientation == "landscape" else PORTRAIT_TEXT_WIDTH
        assert table.text_width == expected_width
        assert table.caption is not None, "every manuscript table has a bold caption directly above it"
        assert paragraph_style(table.previous) == TABLE_TITLE_STYLE
        if table.orientation == "landscape":
            # The caption opens the landscape section: the paragraph above it ends a portrait one.
            before = section_of(table.before_previous)
            assert before is not None and before.find(f"{W}pgSz").get(f"{W}orient") is None
    body = read_part(docx, "word/document.xml").find(f"{W}body")
    final = body.find(f"{W}sectPr/{W}pgSz")
    assert (int(final.get(f"{W}w")), int(final.get(f"{W}h")), final.get(f"{W}orient")) == (
        A4_WIDTH_TWIPS,
        A4_HEIGHT_TWIPS,
        None,
    )


def test_cells_use_the_table_paragraph_styles(built: tuple[Path, Path]) -> None:
    _clean, docx = built
    for table in docx_tables(docx):
        for row in table.element.findall(f"{W}tr"):
            header = row.find(f"{W}trPr/{W}tblHeader") is not None
            styles = {paragraph_style(p) for p in row.iter(f"{W}p")}
            assert styles == {TABLE_HEADING_STYLE if header else TABLE_TEXT_STYLE}, (table.caption, text_of(row))


def test_the_reference_styles_carry_borders_font_and_bold(built: tuple[Path, Path]) -> None:
    _clean, docx = built
    styles = {s.get(f"{W}styleId"): s for s in read_part(docx, "word/styles.xml").iter(f"{W}style")}
    sides = ("top", "left", "bottom", "right", "insideH", "insideV")
    style_borders = styles["Table"].find(f"{W}tblPr/{W}tblBorders")
    assert style_borders is not None
    assert {side: style_borders.find(f"{W}{side}").get(f"{W}val") for side in sides} == dict.fromkeys(sides, "single")
    text = styles[TABLE_TEXT_STYLE]
    assert text.find(f"{W}rPr/{W}sz").get(f"{W}val") == str(TABLE_FONT_PT * 2)
    assert text.find(f"{W}rPr/{W}rFonts").get(f"{W}ascii") == TABLE_FONT
    assert text.find(f"{W}pPr/{W}spacing").get(f"{W}after") == "0"
    assert styles[TABLE_HEADING_STYLE].find(f"{W}rPr/{W}b") is not None
    assert styles[TABLE_TITLE_STYLE].find(f"{W}pPr/{W}keepNext") is not None
    # Importers that ignore table styles still see the borders: each table repeats them.
    for table in docx_tables(docx):
        direct = table.element.find(f"{W}tblPr/{W}tblBorders")
        assert direct is not None and {direct.find(f"{W}{s}").get(f"{W}val") for s in sides} == {"single"}


def test_every_figure_caption_has_its_image(built: tuple[Path, Path]) -> None:
    clean, docx = built
    figures = len(_FIGURE_CAPTION_RE.findall(clean.read_text(encoding="utf-8")))
    extents = [int(e.get("cx")) for e in read_part(docx, "word/document.xml").iter(f"{WP}extent")]
    assert len(list(read_part(docx, "word/document.xml").iter(f"{PIC}pic"))) == figures == len(extents)
    assert all(cx <= PORTRAIT_TEXT_WIDTH / 20 * EMU_PER_POINT for cx in extents)


def test_every_figure_stays_on_the_page_of_its_caption(built: tuple[Path, Path]) -> None:
    """The bug: v0.5's Figure 1 ended one page and its caption opened the next."""
    clean, docx = built
    body = list(read_part(docx, "word/document.xml").find(f"{W}body"))
    with_image = [i for i, block in enumerate(body) if block.find(f".//{PIC}pic") is not None]
    assert len(with_image) == len(_FIGURE_CAPTION_RE.findall(clean.read_text(encoding="utf-8")))
    for index in with_image:
        assert paragraph_style(body[index]) == FIGURE_IMAGE_STYLE
        assert re.match(r"Figure S?\d+\.", text_of(body[index + 1]).strip()), text_of(body[index + 1])
    styles = {s.get(f"{W}styleId"): s for s in read_part(docx, "word/styles.xml").iter(f"{W}style")}
    assert styles[FIGURE_IMAGE_STYLE].find(f"{W}pPr/{W}keepNext") is not None


@pytest.mark.parametrize(
    ("pixels", "fills_the_text_width"),
    [(1200, True), (300, False)],
    ids=["wider-than-the-text", "smaller-than-the-text"],
)
def test_a_full_width_image_spans_the_text_width(pixels: int, fills_the_text_width: bool, tmp_path: Path) -> None:
    """`{width=100%}` is the text width for any figure at least that wide. Pandoc's docx writer
    treats a percentage as a cap and never enlarges: a PNG with no resolution counts at 72 dpi, so a
    300 px image stays 300 pt wide. The masters' figures are all far wider than the text."""
    source = tmp_path / "paper.md"
    (tmp_path / "figures").mkdir()
    tiny_png(tmp_path / "figures/x.png", pixels, 100)
    source.write_text("# Title\n\nText.\n\n![](figures/x.png){width=100%}\n\n**Figure 1.** A grey box.\n", encoding="utf-8")
    paths = build_paths(source, tmp_path / "out")
    write_clean_twin(source, paths.clean)
    markdown_to_docx(paths.clean, paths.docx, source.parent)
    (extent,) = list(read_part(paths.docx, "word/document.xml").iter(f"{WP}extent"))
    width, height = int(extent.get("cx")), int(extent.get("cy"))
    text_width = PORTRAIT_TEXT_WIDTH / 20 * EMU_PER_POINT
    if fills_the_text_width:
        assert abs(width - text_width) <= EMU_PER_POINT  # pandoc rounds the text width to whole points
    else:
        assert width == pixels * EMU_PER_POINT < text_width
    assert width / height == pytest.approx(pixels / 100, rel=0.01)


WIDE_HEADER = "| " + " | ".join(f"Column heading {i}" for i in range(12)) + " |"
WIDE_TABLE = f"{WIDE_HEADER}\n|{'---|' * 12}\n| " + " | ".join(f"value-{i} token{i}" for i in range(12)) + " |"


def build_synthetic(tmp_path: Path, markdown: str) -> tuple[Path, list[ET.Element]]:
    """(.docx, body children) of a small Markdown document built the way `manuscript build` does."""
    source = tmp_path / "synthetic.md"
    source.write_text(markdown, encoding="utf-8")
    paths = build_paths(source, tmp_path / "out")
    write_clean_twin(source, paths.clean)
    markdown_to_docx(paths.clean, paths.docx, source.parent)
    return paths.docx, list(read_part(paths.docx, "word/document.xml").find(f"{W}body"))


def orientations(body: list[ET.Element]) -> list[str]:
    """Each section's orientation, in order, the body's final section last."""
    sections = [section_of(child) for child in body]
    return [s.find(f"{W}pgSz").get(f"{W}orient", "portrait") for s in sections if s is not None]


def test_tables_sized_on_a_synthetic_document(tmp_path: Path) -> None:
    """Boundaries the masters do not show: a narrow table keeps its natural width, an empty cell and
    inline code are styled, two wide tables in a row share one landscape section, a heading goes
    with the wide table it introduces, and the text after them returns to portrait."""
    docx, body = build_synthetic(
        tmp_path,
        "# Synthetic\n\nIntro.\n\n"
        "**Table 1.** Narrow.\n\n| A | B |\n|---|---|\n|  | `code` |\n| *Group* |  |\n\n"
        f"**Table 2.** Wide.\n\n{WIDE_TABLE}\n\n"
        f"## Heading of the next wide table\n\n{WIDE_TABLE}\n\n"
        "After.\n",
    )
    narrow, first, second = docx_tables(docx)
    assert narrow.orientation == "portrait"
    assert sum(grid(narrow.element)) < PORTRAIT_TEXT_WIDTH / 2
    rows = narrow.element.findall(f"{W}tr")
    assert [len(cells(r)) for r in rows] == [2, 2, 1]  # header, a row with an empty cell, a group row
    assert {paragraph_style(p) for p in rows[1].iter(f"{W}p")} == {TABLE_TEXT_STYLE}
    code_styles = {style.get(f"{W}val") for style in rows[1].iter(f"{W}rStyle")}
    assert code_styles == {TABLE_CODE_STYLE}
    assert (first.orientation, second.orientation) == ("landscape", "landscape")
    assert orientations(body) == ["portrait", "landscape", "portrait"]  # no empty section between them
    heading = next(i for i, child in enumerate(body) if text_of(child) == "Heading of the next wide table")
    tables = [i for i, child in enumerate(body) if child.tag == f"{W}tbl"]
    assert tables[1] < heading < tables[2]  # in the landscape section, not stranded on a portrait page
    after = [i for i, child in enumerate(body) if child.tag == f"{W}p" and text_of(child) == "After."]
    assert len(after) == 1 and after[0] > tables[2]


def test_a_document_ending_on_a_wide_table_ends_in_landscape(tmp_path: Path) -> None:
    """No empty portrait section (a blank last page) after a closing landscape table."""
    docx, body = build_synthetic(tmp_path, f"# Synthetic\n\nIntro.\n\n## Last\n\n{WIDE_TABLE}\n")
    (table,) = docx_tables(docx)
    assert table.orientation == "landscape"
    assert orientations(body) == ["portrait", "landscape"]
    assert body[-1].tag == f"{W}sectPr"
    assert [child.tag for child in body if child.tag != f"{W}bookmarkEnd"][-2] == f"{W}tbl"
