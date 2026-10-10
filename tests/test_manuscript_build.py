"""`manuscript build`: Markdown master → clean twin → pandoc LaTeX → tectonic PDF.

Ported from just-module-creator's manuscript tests, where LaTeX is the master. Conversion runs on the
real paper text. The tectonic failure paths use a stand-in binary; the real render is skipped with a
reason when no tectonic is resolvable or its bundle cache would land in ~/.cache.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from just_dna_lite.manuscript.build import (
    TECTONIC_ENV_VAR,
    build_paths,
    latex_to_pdf,
    markdown_to_latex,
    missing_characters,
    page_count,
    resolve_tectonic,
    write_clean_twin,
)
from just_dna_lite.manuscript.cli import app
from just_dna_lite.manuscript.ledger import read_source, strip_markers
from just_dna_pipelines.runtime import load_env

ROOT = Path(__file__).resolve().parents[1]
PAPER1 = ROOT / "docs/manuscript/v0.3/paper1-just-dna-lite.md"
CORRELATION = "Correlation with PLINK2 across the 96 scores completed by all engines was Pearson r = 0.999859."


def stand_in_tectonic(tmp_path: Path, script: str) -> Path:
    binary = tmp_path / "bin" / "tectonic-stand-in"
    binary.parent.mkdir(exist_ok=True)
    binary.write_text(f"#!/bin/sh\n{script}\n", encoding="utf-8")
    binary.chmod(0o755)
    return binary


def marked_copy(tmp_path: Path) -> tuple[Path, str]:
    """Paper 1 with one ledger segment, in a scratch directory so no build lands in docs/."""
    original = strip_markers(read_source(PAPER1))  # the paper carries review markers of its own
    marked = original.replace(
        CORRELATION, f"<!-- @rev C3 rounds=1 by=robi:2026-09-25 -->{CORRELATION}<!-- @/rev C3 -->", 1
    )
    assert marked != original
    source = tmp_path / "paper" / PAPER1.name
    source.parent.mkdir()
    source.write_bytes(marked.encode("utf-8"))
    return source, original


def test_the_cli_exposes_build_beside_the_ledger() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "build" in result.output
    assert "ledger" in result.output


def test_outputs_default_to_a_build_directory_beside_the_source(tmp_path: Path) -> None:
    paths = build_paths(PAPER1)
    assert {p.parent for p in (paths.clean, paths.tex, paths.pdf, paths.log)} == {PAPER1.parent / "build"}
    assert paths.clean.name == "paper1-just-dna-lite.clean.md"
    assert paths.pdf.name == "paper1-just-dna-lite.pdf"
    assert build_paths(PAPER1, tmp_path).tex == tmp_path / "paper1-just-dna-lite.tex"


def test_the_latex_carries_every_heading_and_no_marker(tmp_path: Path) -> None:
    source, original = marked_copy(tmp_path)
    paths = build_paths(source, tmp_path / "out")
    write_clean_twin(source, paths.clean)
    assert paths.clean.read_bytes() == original.encode("utf-8")
    markdown_to_latex(paths.clean, paths.tex, source.parent)
    tex = paths.tex.read_text(encoding="utf-8")

    # One `#` title, `##` sections, `###` subsections: shifted by one level in the LaTeX.
    assert len(re.findall(r"(?m)^# ", original)) == 1
    assert "\\title{" in tex and "Just-DNA-Lite" in tex[tex.index("\\title{") :][:300]
    assert len(re.findall(r"\\section\{", tex)) == len(re.findall(r"(?m)^## ", original))
    assert len(re.findall(r"\\subsection\{", tex)) == len(re.findall(r"(?m)^### ", original))
    assert "@rev" not in tex
    assert "Pearson r = 0.999859" in tex
    assert "\\setmainfont" in tex and "DejaVuSerif" in tex


def test_a_venue_template_replaces_the_default(tmp_path: Path) -> None:
    source, _ = marked_copy(tmp_path)
    paths = build_paths(source, tmp_path / "out")
    write_clean_twin(source, paths.clean)
    template = tmp_path / "venue.latex"
    template.write_text("% VENUE TEMPLATE\n\\title{$title$}\n$body$\n", encoding="utf-8")
    markdown_to_latex(paths.clean, paths.tex, source.parent, template)
    tex = paths.tex.read_text(encoding="utf-8")
    assert tex.startswith("% VENUE TEMPLATE")
    assert "\\documentclass" not in tex
    with pytest.raises(FileNotFoundError):
        markdown_to_latex(paths.clean, paths.tex, source.parent, tmp_path / "absent.latex")


def test_the_tectonic_binary_can_be_overridden_from_the_environment(tmp_path: Path, monkeypatch) -> None:
    """The `tecto` wheel's binary needs a recent glibc; a static musl build must be able to replace it."""
    stand_in = stand_in_tectonic(tmp_path, "exit 0")
    monkeypatch.setenv(TECTONIC_ENV_VAR, str(stand_in))
    assert resolve_tectonic() == stand_in

    monkeypatch.setenv(TECTONIC_ENV_VAR, str(tmp_path / "absent"))
    with pytest.raises(FileNotFoundError):
        resolve_tectonic()

    # Unset, the venv's own binary (the `tecto` dev dependency) is found, not the stand-in.
    monkeypatch.delenv(TECTONIC_ENV_VAR, raising=False)
    assert resolve_tectonic() != stand_in


@pytest.mark.parametrize(
    ("script", "message"),
    [
        ('echo "! LaTeX Error: something broke" > "$3/paper1-just-dna-lite.log"; exit 1', "something broke"),
        ("exit 0", "did not produce"),
    ],
    ids=["tectonic-fails", "tectonic-writes-nothing"],
)
def test_a_failed_render_reports_and_removes_the_old_pdf(
    script: str, message: str, tmp_path: Path, monkeypatch
) -> None:
    """The LaTeX is written, the failure is reported, and no earlier PDF is left to pass as current."""
    source, _ = marked_copy(tmp_path)
    out = tmp_path / "out"
    paths = build_paths(source, out)
    out.mkdir()
    paths.pdf.write_bytes(b"%PDF-1.5 an earlier build")
    monkeypatch.setenv(TECTONIC_ENV_VAR, str(stand_in_tectonic(tmp_path, script)))

    result = CliRunner().invoke(app, ["build", str(source), "--out", str(out)])
    assert result.exit_code == 1
    assert message in result.output
    assert paths.tex.is_file()
    assert paths.clean.is_file()
    assert not paths.pdf.exists()


def test_no_pdf_stops_at_the_latex_and_flags_an_older_pdf(tmp_path: Path, monkeypatch) -> None:
    source, _ = marked_copy(tmp_path)
    out = tmp_path / "out"
    paths = build_paths(source, out)
    out.mkdir()
    paths.pdf.write_bytes(b"%PDF-1.5 an earlier build")
    os.utime(paths.pdf, (1_000_000_000, 1_000_000_000))
    monkeypatch.setenv(TECTONIC_ENV_VAR, str(tmp_path / "never-called"))

    result = CliRunner().invoke(app, ["build", str(source), "--out", str(out), "--no-pdf"])
    assert result.exit_code == 0, result.output
    assert paths.tex.is_file()
    assert "earlier build" in result.output
    assert paths.pdf.read_bytes() == b"%PDF-1.5 an earlier build"


def test_a_ledger_error_stops_the_build_before_any_output(tmp_path: Path) -> None:
    source, _ = marked_copy(tmp_path)
    source.write_bytes(read_source(source).replace("<!-- @/rev C3 -->", "", 1).encode("utf-8"))
    out = tmp_path / "out"
    result = CliRunner().invoke(app, ["build", str(source), "--out", str(out), "--no-pdf"])
    assert result.exit_code == 1
    assert "unclosed" in result.output
    assert not out.exists()


def test_page_count_and_missing_characters_read_the_tex_log(tmp_path: Path) -> None:
    log = tmp_path / "x.log"
    assert page_count(log) is None
    assert missing_characters(log) == {}
    log.write_text(
        "Missing character: There is no ≥ (U+2265) in font [lmroman10-regular]:mapping=tex-text;!\n"
        "Missing character: There is no ≥ (U+2265) in font [lmroman10-regular]:mapping=tex-text;!\n"
        "Missing character: There is no ↔ (U+2194) in font [lmroman10-regular]:mapping=tex-text;!\n"
        "Output written on x.xdv (22 pages, 123456 bytes).\n",
        encoding="utf-8",
    )
    assert page_count(log) == 22
    assert missing_characters(log) == {"U+2265 ≥": 2, "U+2194 ↔": 1}


def test_the_real_paper_renders_to_pdf_with_every_character(tmp_path: Path) -> None:
    load_env()
    try:
        resolve_tectonic()
    except FileNotFoundError as exc:
        pytest.skip(f"no tectonic to render with: {exc}")
    if not os.environ.get("TECTONIC_CACHE_DIR"):
        pytest.skip("TECTONIC_CACHE_DIR is unset; the TeX bundle would be downloaded into ~/.cache")
    source, _ = marked_copy(tmp_path)
    paths = build_paths(source, tmp_path / "out")
    write_clean_twin(source, paths.clean)
    markdown_to_latex(paths.clean, paths.tex, source.parent)
    result = latex_to_pdf(paths, source.parent)
    assert result.pdf.read_bytes().startswith(b"%PDF")
    assert result.pages is not None and result.pages > 1
    assert result.missing_characters == {}
