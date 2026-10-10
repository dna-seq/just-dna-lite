"""Build a manuscript PDF from its Markdown master.

The chain is: ledger strip (`<stem>.clean.md`) → pandoc → LaTeX (`<stem>.tex`) → tectonic → PDF.
The Markdown is the master here; the LaTeX is derived and never edited by hand. Ported from the
just-module-creator manuscript CLI, where the direction is the reverse (LaTeX master, Markdown derived).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

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


class BuildPaths(BaseModel):
    model_config = ConfigDict(frozen=True)

    clean: Path
    tex: Path
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
    if pypandoc is None:
        raise RuntimeError("pypandoc is not installed; run `uv sync` (it is in the dev dependency group)")
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

