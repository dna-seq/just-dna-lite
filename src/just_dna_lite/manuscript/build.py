"""Build a manuscript PDF and .docx from its Markdown master.

The chain is: ledger strip (`<stem>.clean.md`) → pandoc → LaTeX (`<stem>.tex`) → tectonic → PDF, and
from the same clean twin pandoc → `<stem>.docx` (the copy co-authors comment on in Google Docs).
The Markdown is the master here; everything else is derived and never edited by hand. Ported from the
just-module-creator manuscript CLI, where the direction is the reverse (LaTeX master, Markdown derived).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Optional
from xml.dom import minidom

from pydantic import BaseModel, ConfigDict

try:  # dev dependency group; `manuscript ledger` must keep working without it
    import pypandoc
except ImportError:
    pypandoc = None

from just_dna_lite.manuscript.ledger import CLEAN_SUFFIX, read_source, strip_markers

TECTONIC_ENV_VAR = "MANUSCRIPT_TECTONIC"
BUILD_DIR_NAME = "build"
LOG_TAIL_LINES = 40
TECTONIC_MISSING = (
    f"tectonic not found. Install the dev dependencies with `uv sync` (the `tecto` wheel ships it), "
    f"or set {TECTONIC_ENV_VAR} to a working binary."
)
# The paper opens with its title as the one `#` heading and uses `##` for sections. Shifting by -1
# makes pandoc lift that heading into the title block and the `##` sections into \section.
PANDOC_ARGS = ("--standalone", "--wrap=preserve", "--shift-heading-level-by=-1")
# Latin Modern, pandoc's default, has no ≥, ↔ or superscript minus, and XeTeX drops a missing glyph
# with only a log line: paper 1 lost eight characters that way. DejaVu (in tectonic's bundle) has them.
# Passed as template variables, so a venue template that sets its own fonts simply ignores them.
_DEJAVU_FACES = "Extension=.ttf, UprightFont=*, BoldFont=*-Bold, ItalicFont=*-Italic, BoldItalicFont=*-BoldItalic"
FONT_VARIABLES = (
    "mainfont=DejaVuSerif",
    f"mainfontoptions={_DEJAVU_FACES}",
    "monofont=DejaVuSansMono",
    f"monofontoptions={_DEJAVU_FACES.replace('*-Italic', '*-Oblique').replace('*-BoldItalic', '*-BoldOblique')}",
)
_PAGES_RE = re.compile(r"Output written on .*? \((?P<pages>[0-9]+) pages?")
_MISSING_CHAR_RE = re.compile(r"Missing character: There is no (?P<char>.) \(U\+(?P<code>[0-9A-F]+)\)")

# The .docx: A4 portrait with 2 cm margins, tables in 9 pt Arial (the filter's width estimates use
# Arial metrics, and Word, LibreOffice and Google Docs all have Arial or a metric twin). Lengths are
# twips (1/20 pt); 1 cm = 567 twips.
DOCX_TABLE_FILTER = Path(__file__).parent / "filters" / "docx_tables.lua"
A4_WIDTH_TWIPS = 11906
A4_HEIGHT_TWIPS = 16838
DOCX_MARGIN_TWIPS = 1134
TABLE_FONT = "Arial"
TABLE_FONT_PT = 9
CELL_MARGIN_TWIPS = 85  # left and right
CELL_MARGIN_VERTICAL_TWIPS = 28
TABLE_TEXT_STYLE = "TableText"
TABLE_HEADING_STYLE = "TableHeading"
TABLE_TITLE_STYLE = "TableTitle"  # the bold "Table X." paragraph, kept with its table
TABLE_CODE_STYLE = "TableCode"  # inline code in a cell; pandoc's Verbatim Char is 11 pt
FIGURE_IMAGE_STYLE = "FigureImage"  # an image paragraph, kept with the "Figure N." caption below it
_PCT_FULL = 5000  # OOXML `pct` widths are fiftieths of a percent
_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_TABLE_STYLE_RE = re.compile(r'<w:style w:type="table" w:default="1" w:styleId="Table">.*?</w:style>', re.DOTALL)
_SECT_PR_RE = re.compile(r"<w:sectPr>.*?</w:sectPr>", re.DOTALL)
_BORDER = 'w:val="single" w:sz="4" w:space="0" w:color="auto"'
_TABLE_BORDERS = (
    "<w:tblBorders>"
    + "".join(f"<w:{side} {_BORDER}/>" for side in ("top", "left", "bottom", "right", "insideH", "insideV"))
    + "</w:tblBorders>"
)
_CELL_MARGINS = (
    "<w:tblCellMar>"
    f'<w:top w:w="{CELL_MARGIN_VERTICAL_TWIPS}" w:type="dxa"/>'
    f'<w:left w:w="{CELL_MARGIN_TWIPS}" w:type="dxa"/>'
    f'<w:bottom w:w="{CELL_MARGIN_VERTICAL_TWIPS}" w:type="dxa"/>'
    f'<w:right w:w="{CELL_MARGIN_TWIPS}" w:type="dxa"/>'
    "</w:tblCellMar>"
)
_REFERENCE_TABLE_STYLE = (
    '<w:style w:type="table" w:default="1" w:styleId="Table">'
    '<w:name w:val="Table"/><w:basedOn w:val="TableNormal"/><w:qFormat/>'
    f'<w:tblPr><w:tblInd w:w="0" w:type="dxa"/>{_TABLE_BORDERS}{_CELL_MARGINS}</w:tblPr>'
    '<w:tblStylePr w:type="firstRow"><w:rPr><w:b/><w:bCs/></w:rPr>'
    '<w:tcPr><w:vAlign w:val="bottom"/></w:tcPr></w:tblStylePr>'
    "</w:style>"
)
_TABLE_FONT_RPR = (
    f'<w:rFonts w:ascii="{TABLE_FONT}" w:hAnsi="{TABLE_FONT}" w:cs="{TABLE_FONT}"/>'
    f'<w:sz w:val="{TABLE_FONT_PT * 2}"/><w:szCs w:val="{TABLE_FONT_PT * 2}"/>'
)
# Paragraph styles outrank a table style's run properties in Word, so the font and the header's
# bold live here, where every cell paragraph takes them, not in the table style. "Table Title" keeps
# a "Table X." caption with its table; "Table Code" sets inline code in a cell at the table size.
_REFERENCE_TABLE_STYLES = (
    f'<w:style w:type="paragraph" w:customStyle="1" w:styleId="{TABLE_TEXT_STYLE}">'
    '<w:name w:val="Table Text"/><w:basedOn w:val="Normal"/><w:qFormat/>'
    '<w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
    f"<w:rPr>{_TABLE_FONT_RPR}</w:rPr></w:style>"
    f'<w:style w:type="paragraph" w:customStyle="1" w:styleId="{TABLE_HEADING_STYLE}">'
    f'<w:name w:val="Table Heading"/><w:basedOn w:val="{TABLE_TEXT_STYLE}"/><w:qFormat/>'
    "<w:pPr><w:keepNext/></w:pPr><w:rPr><w:b/><w:bCs/></w:rPr></w:style>"
    f'<w:style w:type="paragraph" w:customStyle="1" w:styleId="{TABLE_TITLE_STYLE}">'
    '<w:name w:val="Table Title"/><w:basedOn w:val="BodyText"/><w:qFormat/>'
    "<w:pPr><w:keepNext/><w:keepLines/></w:pPr></w:style>"
    f'<w:style w:type="character" w:customStyle="1" w:styleId="{TABLE_CODE_STYLE}">'
    '<w:name w:val="Table Code"/><w:basedOn w:val="VerbatimChar"/>'
    f'<w:rPr><w:sz w:val="{TABLE_FONT_PT * 2}"/><w:szCs w:val="{TABLE_FONT_PT * 2}"/></w:rPr></w:style>'
    f'<w:style w:type="paragraph" w:customStyle="1" w:styleId="{FIGURE_IMAGE_STYLE}">'
    '<w:name w:val="Figure Image"/><w:basedOn w:val="BodyText"/><w:qFormat/>'
    '<w:pPr><w:keepNext/><w:keepLines/><w:jc w:val="center"/></w:pPr></w:style>'
)
_REFERENCE_SECT_PR = (
    f'<w:sectPr><w:pgSz w:w="{A4_WIDTH_TWIPS}" w:h="{A4_HEIGHT_TWIPS}"/>'
    f'<w:pgMar w:top="{DOCX_MARGIN_TWIPS}" w:right="{DOCX_MARGIN_TWIPS}" w:bottom="{DOCX_MARGIN_TWIPS}" '
    f'w:left="{DOCX_MARGIN_TWIPS}" w:header="567" w:footer="567" w:gutter="0"/></w:sectPr>'
)
# Read by docx_tables.lua, which removes them before the writer runs.
_FILTER_METADATA = {
    "docx-page-width": A4_WIDTH_TWIPS,
    "docx-page-height": A4_HEIGHT_TWIPS,
    "docx-margin": DOCX_MARGIN_TWIPS,
    "docx-table-font-size": TABLE_FONT_PT,
    "docx-cell-margin": CELL_MARGIN_TWIPS,
}


class BuildPaths(BaseModel):
    model_config = ConfigDict(frozen=True)

    clean: Path
    tex: Path
    docx: Path
    pdf: Path
    log: Path


class PdfResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    pdf: Path
    pages: Optional[int]
    missing_characters: dict[str, int]


def build_paths(source: Path, out_dir: Optional[Path] = None) -> BuildPaths:
    """Where each artifact of *source* goes: `<source dir>/build/` unless *out_dir* is given."""
    directory = out_dir if out_dir is not None else source.parent / BUILD_DIR_NAME
    stem = source.stem
    return BuildPaths(
        clean=directory / f"{stem}{CLEAN_SUFFIX}",
        tex=directory / f"{stem}.tex",
        docx=directory / f"{stem}.docx",
        pdf=directory / f"{stem}.pdf",
        log=directory / f"{stem}.log",
    )


def write_clean_twin(source: Path, dest: Path) -> Path:
    """The marker-free Markdown; raises `LedgerError` if the ledger markers do not lint."""
    clean = strip_markers(read_source(source)).encode("utf-8")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.is_file() or dest.read_bytes() != clean:
        dest.write_bytes(clean)
    return dest


def markdown_to_latex(clean: Path, tex: Path, resource_dir: Path, template: Optional[Path] = None) -> Path:
    """Convert the clean Markdown to standalone LaTeX with pandoc.

    *template* is the hook for a venue template (Bioinformatics/OUP and the like): a pandoc LaTeX
    template, see `pandoc -D latex` for the variables it receives. None uses pandoc's own article.
    """
    _require_pypandoc()
    if template is not None and not template.is_file():
        raise FileNotFoundError(f"template {template} not found")
    args = [*PANDOC_ARGS, f"--resource-path={resource_dir.resolve()}"]
    for variable in FONT_VARIABLES:
        args.extend(["-V", variable])
    if template is not None:
        args.append(f"--template={template.resolve()}")
    tex.parent.mkdir(parents=True, exist_ok=True)
    pypandoc.convert_file(str(clean), "latex", format="markdown", outputfile=str(tex), extra_args=args)
    return tex


def _require_pypandoc() -> None:
    if pypandoc is None:
        raise RuntimeError("pypandoc is not installed; run `uv sync` (it is in the dev dependency group)")


def markdown_to_docx(clean: Path, docx: Path, resource_dir: Path) -> Path:
    """Convert the clean Markdown to .docx with readable tables (see `filters/docx_tables.lua`).

    Same heading shift and resource path as the LaTeX. The reference document is generated for the
    build from pandoc's default, and the tables are pinned to absolute widths afterwards. The previous
    .docx is deleted first, so a failed conversion never leaves an old one that reads as current.
    """
    _require_pypandoc()
    docx.unlink(missing_ok=True)
    docx.parent.mkdir(parents=True, exist_ok=True)
    args = [*PANDOC_ARGS, f"--resource-path={resource_dir.resolve()}", f"--lua-filter={DOCX_TABLE_FILTER}"]
    args.extend(f"--metadata={key}={value}" for key, value in _FILTER_METADATA.items())
    with tempfile.TemporaryDirectory(prefix="manuscript-docx-") as scratch:
        reference = write_reference_docx(Path(scratch) / "reference.docx")
        args.append(f"--reference-doc={reference}")
        pypandoc.convert_file(str(clean), "docx", format="markdown", outputfile=str(docx), extra_args=args)
    finish_docx_layout(docx)
    return docx


def write_reference_docx(dest: Path) -> Path:
    """Pandoc's default reference.docx, patched; generated per build so no binary is committed.

    A4 portrait with 2 cm margins in the final section; the "Table" style gets thin single borders on
    every side and between cells, and modest cell margins; "Table Text" (9 pt Arial, no space after,
    single spacing), "Table Heading" (the same, bold), "Table Title" (keep with next) and "Table Code"
    (9 pt code) are added for the filter's cells and captions.
    """
    _require_pypandoc()
    default = subprocess.run(
        [pypandoc.get_pandoc_path(), "--print-default-data-file", "reference.docx"],
        check=True,
        capture_output=True,
    ).stdout
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(default)
    _rewrite_zip_members(dest, {"word/styles.xml": _patch_reference_styles, "word/document.xml": _patch_reference_section})
    return dest


def _patch_reference_styles(xml: str) -> str:
    patched, count = _TABLE_STYLE_RE.subn(_REFERENCE_TABLE_STYLE, xml)
    if count != 1 or "</w:styles>" not in patched:
        raise RuntimeError("pandoc's default reference.docx no longer has one default \"Table\" style to replace")
    return patched.replace("</w:styles>", f"{_REFERENCE_TABLE_STYLES}</w:styles>")


def _patch_reference_section(xml: str) -> str:
    patched, count = _SECT_PR_RE.subn(_REFERENCE_SECT_PR, xml)
    if count != 1:
        raise RuntimeError(f"pandoc's default reference.docx has {count} sections, expected 1")
    return patched


def _rewrite_zip_members(path: Path, edits: dict[str, Callable[[str], str]]) -> None:
    """Rewrite the named UTF-8 members of a zip in place, keeping every other member and the order."""
    with zipfile.ZipFile(path) as source:
        members = [(info, source.read(info)) for info in source.infolist()]
    missing = set(edits) - {info.filename for info, _ in members}
    if missing:
        raise RuntimeError(f"{path} has no {', '.join(sorted(missing))}")
    partial = path.with_name(f"{path.name}.part")
    with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as target:
        for info, data in members:
            edit = edits.get(info.filename)
            target.writestr(info, data if edit is None else edit(data.decode("utf-8")).encode("utf-8"))
    partial.replace(path)


def finish_docx_layout(docx: Path) -> None:
    """Make every top-level table's widths, borders and cell margins direct formatting, and drop an
    empty last page.

    Pandoc writes a table's width as a percentage and scales its grid to a fixed 5.5-inch text width,
    so the grid alone undersizes every column, and Google Docs reads the grid. Here each grid column
    and cell gets its width in twips of the text width of the section the table sits in (portrait or
    landscape), and the "Table" style's borders and cell margins are repeated on the table, for
    importers that ignore table styles. Rows are marked `cantSplit`, so no row is cut across a page
    break. A document that ends on a landscape table would end with an empty portrait section (a
    blank page); its last section takes the landscape properties instead.
    """
    _rewrite_zip_members(docx, {"word/document.xml": _finish_layout})


def _finish_layout(xml: str) -> str:
    dom = minidom.parseString(xml.encode("utf-8"))
    body = _child(dom.documentElement, "w:body")
    if body is None:
        raise RuntimeError("document.xml has no w:body")
    _close_trailing_section(body)
    pending: list[minidom.Element] = []
    for child in _children(body):
        if child.tagName == "w:tbl":
            pending.append(child)
            continue
        section = child if child.tagName == "w:sectPr" else _paragraph_section(child)
        if section is None:
            continue
        width = _section_text_width(section)
        for table in pending:
            _pin_table(dom, table, width)
        pending = []
    if pending:
        raise RuntimeError("document.xml has tables after its last section properties")
    return dom.toxml(encoding="UTF-8").decode("utf-8")


def _close_trailing_section(body: minidom.Element) -> None:
    """When an empty section-break paragraph is the last thing before the body's own sectPr, the
    final section holds nothing: move the break's properties to the end and drop the paragraph.
    Bookmark ends (pandoc closes a heading's bookmark at the end of its section) do not count."""
    children = [c for c in _children(body) if c.tagName != "w:bookmarkEnd"]
    if len(children) < 2 or children[-1].tagName != "w:sectPr":
        return
    last_paragraph = children[-2]
    section = _paragraph_section(last_paragraph)
    if section is None or _children(last_paragraph, "w:r"):
        return
    body.replaceChild(section, children[-1])
    body.removeChild(last_paragraph)


def _children(node: minidom.Node, tag: Optional[str] = None) -> list[minidom.Element]:
    return [c for c in node.childNodes if c.nodeType == c.ELEMENT_NODE and (tag is None or c.tagName == tag)]


def _child(node: minidom.Node, tag: str) -> Optional[minidom.Element]:
    found = _children(node, tag)
    return found[0] if found else None


def _paragraph_section(node: minidom.Element) -> Optional[minidom.Element]:
    """The sectPr a paragraph carries in its pPr: it ends a section and describes the pages above it."""
    if node.tagName != "w:p":
        return None
    properties = _child(node, "w:pPr")
    return None if properties is None else _child(properties, "w:sectPr")


def _section_text_width(section: minidom.Element) -> int:
    size, margins = _child(section, "w:pgSz"), _child(section, "w:pgMar")
    if size is None or margins is None:
        raise RuntimeError("a section in document.xml states no page size or margins")
    return int(size.getAttribute("w:w")) - int(margins.getAttribute("w:left")) - int(margins.getAttribute("w:right"))


def _fragment(dom: minidom.Document, xml: str) -> minidom.Element:
    parsed = minidom.parseString(f'<root xmlns:w="{_W_NS}">{xml}</root>').documentElement.firstChild
    return dom.importNode(parsed, True)


def _insert_before_first(parent: minidom.Element, node: minidom.Element, successors: tuple[str, ...]) -> None:
    """Insert *node* before the first child named in *successors* (OOXML fixes the child order)."""
    for existing in _children(parent, node.tagName):
        parent.removeChild(existing)
    following = next((c for c in _children(parent) if c.tagName in successors), None)
    parent.insertBefore(node, following)


def _pin_table(dom: minidom.Document, table: minidom.Element, text_width: int) -> None:
    properties, grid = _child(table, "w:tblPr"), _child(table, "w:tblGrid")
    if properties is None or grid is None:
        raise RuntimeError("a table in document.xml has no w:tblPr or w:tblGrid")
    _insert_before_first(
        properties,
        _fragment(dom, _TABLE_BORDERS),
        ("w:shd", "w:tblLayout", "w:tblCellMar", "w:tblLook", "w:tblCaption", "w:tblDescription"),
    )
    _insert_before_first(properties, _fragment(dom, _CELL_MARGINS), ("w:tblLook", "w:tblCaption", "w:tblDescription"))
    for row in _children(table, "w:tr"):  # a row is never split across two pages
        row_properties = _child(row, "w:trPr")
        if row_properties is None:
            row_properties = dom.createElement("w:trPr")
            exceptions = _child(row, "w:tblPrEx")
            row.insertBefore(row_properties, row.firstChild if exceptions is None else exceptions.nextSibling)
        _insert_before_first(row_properties, dom.createElement("w:cantSplit"), ())
    table_width, columns = _child(properties, "w:tblW"), _children(grid, "w:gridCol")
    if table_width is None or table_width.getAttribute("w:type") != "pct" or not columns:
        return  # pandoc's auto layout: no widths to pin
    share = int(table_width.getAttribute("w:w")) / _PCT_FULL
    weights = [int(column.getAttribute("w:w")) for column in columns]
    twips = [int(text_width * share * weight / sum(weights)) for weight in weights]
    for column, width in zip(columns, twips):
        column.setAttribute("w:w", str(width))
    table_width.setAttribute("w:type", "dxa")
    table_width.setAttribute("w:w", str(sum(twips)))
    for row in _children(table, "w:tr"):
        index = 0
        for cell in _children(row, "w:tc"):
            cell_properties = _child(cell, "w:tcPr")
            if cell_properties is None:
                cell_properties = dom.createElement("w:tcPr")
                cell.insertBefore(cell_properties, cell.firstChild)
            span = _child(cell_properties, "w:gridSpan")
            columns_spanned = int(span.getAttribute("w:val")) if span is not None else 1
            cell_width = dom.createElement("w:tcW")
            cell_width.setAttribute("w:w", str(sum(twips[index : index + columns_spanned])))
            cell_width.setAttribute("w:type", "dxa")
            successors = tuple(c.tagName for c in _children(cell_properties) if c.tagName != "w:cnfStyle")
            _insert_before_first(cell_properties, cell_width, successors)
            index += columns_spanned


def resolve_tectonic() -> Path:
    """Find a tectonic to run, letting `MANUSCRIPT_TECTONIC` override the venv's.

    The override exists because the wheel's binary is not portable: `tecto` publishes one manylinux
    build that needs a recent glibc, with nothing older on PyPI. The same release also ships a static
    musllinux build that runs anywhere; on such a host point the variable at that one.
    """
    override = os.environ.get(TECTONIC_ENV_VAR)
    if override:
        candidate = Path(override).expanduser()
        if not candidate.is_file():
            raise FileNotFoundError(f"{TECTONIC_ENV_VAR}={override} is not a file")
        return candidate
    venv_bin = Path(sys.executable).parent
    for name in ("tectonic", "tecto"):
        candidate = venv_bin / name
        if candidate.is_file():
            return candidate
    found = shutil.which("tectonic") or shutil.which("tecto")
    if found is None:
        raise FileNotFoundError(TECTONIC_MISSING)
    return Path(found)


def latex_to_pdf(paths: BuildPaths, resource_dir: Path) -> PdfResult:
    """Compile `paths.tex` with tectonic. Raises RuntimeError with the log tail on failure.

    The previous PDF is deleted first, so a failed build never leaves an old PDF that reads as the
    current one. `TECTONIC_CACHE_DIR` (read by tectonic itself) says where the TeX bundle is cached.
    """
    tectonic = resolve_tectonic()
    paths.pdf.unlink(missing_ok=True)
    proc = subprocess.run(
        [
            str(tectonic),
            "--keep-logs",
            "--outdir",
            str(paths.pdf.parent.resolve()),
            "-Z",
            f"search-path={resource_dir.resolve()}",
            paths.tex.name,
        ],
        cwd=paths.tex.parent,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(_tectonic_error(paths, proc))
    if not paths.pdf.is_file():
        raise RuntimeError(f"tectonic exited 0 but did not produce {paths.pdf}")
    return PdfResult(pdf=paths.pdf, pages=page_count(paths.log), missing_characters=missing_characters(paths.log))


def page_count(log: Path) -> Optional[int]:
    """Pages typeset, from the TeX log's `Output written on … (N pages` line; None if absent."""
    if not log.is_file():
        return None
    found = _PAGES_RE.search(log.read_text(encoding="utf-8", errors="replace"))
    return int(found.group("pages")) if found else None


def missing_characters(log: Path) -> dict[str, int]:
    """Characters the fonts lacked, `U+2265 ≥` → count. XeTeX leaves a gap in the PDF for each."""
    if not log.is_file():
        return {}
    counts: dict[str, int] = {}
    for found in _MISSING_CHAR_RE.finditer(log.read_text(encoding="utf-8", errors="replace")):
        key = f"U+{found.group('code')} {found.group('char')}"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _tectonic_error(paths: BuildPaths, proc: subprocess.CompletedProcess[str]) -> str:
    if paths.log.is_file():
        lines = paths.log.read_text(encoding="utf-8", errors="replace").splitlines()
        tail = "\n".join(lines[-LOG_TAIL_LINES:])
    else:
        tail = (proc.stderr or proc.stdout or "").strip()
    return f"tectonic failed for {paths.tex.name}\n{tail}"


def stale_pdf_note(paths: BuildPaths) -> Optional[str]:
    """With --no-pdf, say so when a PDF from an earlier build sits beside the new LaTeX."""
    if paths.pdf.is_file() and paths.pdf.stat().st_mtime < paths.tex.stat().st_mtime:
        return f"{paths.pdf} is from an earlier build and does not reflect this source"
    return None

