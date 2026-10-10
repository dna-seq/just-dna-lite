"""`manuscript ledger` on the real v0.3 manuscript.

The paper is read at test time and markers are inserted around its own sentences and paragraphs,
so the round trip is checked against the text the ledger will actually be used on. The paper file
itself is never written.
"""

from __future__ import annotations

import random
import re
import tomllib
from datetime import date
from importlib import import_module
from pathlib import Path

import pytest
from typer.testing import CliRunner

from just_dna_lite.manuscript.cli import app
from just_dna_lite.manuscript.ledger import (
    IssueCode,
    LedgerError,
    ReviewEntry,
    bump_segment,
    clean_twin_path,
    parse_ledger,
    parse_review_entry,
    read_source,
    blind_spots,
    paragraphs,
    render_heatmap,
    report_totals,
    strip_markers,
)

ROOT = Path(__file__).resolve().parents[1]
PAPERS = [
    ROOT / "docs/manuscript/v0.3/paper1-just-dna-lite.md",
    ROOT / "docs/manuscript/v0.3/paper2-just-module-creator.md",
]
# Sentence-pinned tests read a frozen copy of paper 1 as it stood before the v0.3 review edits, so
# editing the live paper never breaks them. The live papers are still linted and round-tripped above.
PAPER1 = ROOT / "tests/data/manuscript/v0.3-review-baseline/paper1-just-dna-lite.md"
BY = "robi:2026-09-25,claude:2026-10-10"
SEED = 20261010


def open_marker(segment_id: str, rounds: int = 2, by: str = BY) -> str:
    return f"<!-- @rev {segment_id} rounds={rounds} by={by} -->"


def close_marker(segment_id: str) -> str:
    return f"<!-- @/rev {segment_id} -->"


def paper_baseline(path: Path) -> str:
    """The paper as it stands, minus any markers the fixes may have added since."""
    return strip_markers(read_source(path))


def wrap_inline(text: str, start: int, end: int, segment_id: str, rounds: int = 2, by: str = BY) -> str:
    """Glue a marker pair to text[start:end] without adding any whitespace."""
    return text[:start] + open_marker(segment_id, rounds, by) + text[start:end] + close_marker(segment_id) + text[end:]


def wrap_lines(text: str, start: int, end: int, segment_id: str, newline: str = "\n") -> str:
    """Put the markers on lines of their own around the whole lines text[start:end].

    *start* is a line start; *end* is just past a line terminator, or the end of a file that has no
    final terminator. That last case gets `newline + close`, the only way to add a line there.
    """
    assert start == 0 or text[start - 1] == "\n"
    opening = open_marker(segment_id) + newline
    if end == len(text) and not text.endswith("\n"):
        closing = newline + close_marker(segment_id)
    else:
        assert text[end - 1] == "\n"
        closing = close_marker(segment_id) + newline
    return text[:start] + opening + text[start:end] + closing + text[end:]


def line_span(text: str, needle: str) -> tuple[int, int]:
    """Offsets of the whole line(s) containing *needle*, terminator included."""
    at = text.index(needle)
    start = text.rfind("\n", 0, at) + 1
    newline = text.find("\n", at + len(needle))
    return start, len(text) if newline == -1 else newline + 1


def span(text: str, needle: str) -> tuple[int, int]:
    at = text.index(needle)
    return at, at + len(needle)


# Real sentences of paper 1, picked by content so a later edit fails loudly here rather than
# silently testing something else.
ABSTRACT_OPENING = "Personal genome analysis requires tools that make published variant associations accessible"
CORRELATION = "Correlation with PLINK2 across the 96 scores completed by all engines was Pearson r = 0.999859."
UNICODE_CELL = "Târgu Mureș"
TABLE_CELL = "Variant-trait associations from the LongevityMap database"
INTRO_EXTREMES = "Existing solutions occupy two extremes."


@pytest.mark.parametrize("path", PAPERS, ids=lambda p: p.name)
def test_the_papers_lint_clean_and_strip_to_themselves_before_any_marker(path: Path) -> None:
    """Ordinary comments (paper 1's AUTHOR TODO, paper 2's opening block) are text, not markers."""
    text = paper_baseline(path)
    ledger = parse_ledger(text)
    assert ledger.errors == ()
    assert "<!--" in text
    assert ledger.clean_text() == text


def test_hand_placed_markers_round_trip_byte_for_byte() -> None:
    original = paper_baseline(PAPER1)
    marked = original
    # Inline first, then own-line around a different paragraph; offsets are recomputed each time.
    marked = wrap_inline(marked, *span(marked, CORRELATION), "C3")
    marked = wrap_inline(marked, *span(marked, UNICODE_CELL), "N1")
    marked = wrap_inline(marked, *span(marked, TABLE_CELL), "C12")
    marked = wrap_lines(marked, *line_span(marked, ABSTRACT_OPENING), "C2")
    # A whole paragraph rewritten for C5 containing a sentence also rewritten for N2.
    intro = INTRO_EXTREMES
    marked = wrap_inline(marked, *span(marked, intro), "N2")
    marked = wrap_lines(marked, *line_span(marked, intro), "C5")

    ledger = parse_ledger(marked)
    assert ledger.errors == ()
    assert {s.id for s in ledger.segments} == {"C3", "N1", "C12", "C2", "N2", "C5"}
    assert {s.id: s.depth for s in ledger.segments}["N2"] == 1
    assert next(s for s in ledger.segments if s.id == "N1").text == UNICODE_CELL
    assert next(s for s in ledger.segments if s.id == "C3").text == CORRELATION
    assert strip_markers(marked).encode("utf-8") == original.encode("utf-8")


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
@pytest.mark.parametrize("final_newline", [True, False], ids=["final-newline", "no-final-newline"])
def test_seeded_random_markers_round_trip(newline: str, final_newline: bool) -> None:
    """Many segments on random lines and sentences of the paper, both placements, nested too."""
    original = paper_baseline(PAPER1).replace("\n", newline)
    if not final_newline:
        original = original.rstrip("\r\n")
    rng = random.Random(SEED)
    line_starts = [0] + [m.end() for m in re.finditer("\n", original)]
    lines = [
        (start, original.find("\n", start) + 1 if original.find("\n", start) != -1 else len(original))
        for start in line_starts
        if start < len(original)
    ]
    prose = [(start, end) for start, end in lines if original[start:end].strip()]
    # The last line always gets own-line markers (index 0), so the end-of-file rule is exercised.
    chosen = [prose[-1], *rng.sample(prose[:-1], 39)]
    # Work from the end of the file so earlier offsets stay valid.
    marked = original
    expected: set[str] = set()
    for index, (start, end) in sorted(enumerate(chosen), key=lambda item: -item[1][0]):
        line = original[start:end]
        # A sentence outside inline code: a marker inside backticks is an example, not a marker.
        sentence = next(
            (m for m in re.finditer(r"[A-Z][^.!?\r\n`]{12,}[.!?]", line) if line[: m.start()].count("`") % 2 == 0),
            None,
        )
        if index % 3 != 0 and sentence is not None:
            inner_id = f"C{index + 1}"
            marked = wrap_inline(marked, start + sentence.start(), start + sentence.end(), inner_id)
            expected.add(inner_id)
            if index % 3 == 2:
                # The same line also rewritten as a whole, around the inline pair.
                growth = len(open_marker(inner_id)) + len(close_marker(inner_id))
                marked = wrap_lines(marked, start, end + growth, f"N{index + 1}", newline)
                expected.add(f"N{index + 1}")
        else:
            marked = wrap_lines(marked, start, end, f"C{index + 1}", newline)
            expected.add(f"C{index + 1}")
    if not final_newline:
        assert not marked.endswith("\n")

    ledger = parse_ledger(marked)
    assert ledger.errors == ()
    assert {s.id for s in ledger.segments} == expected
    assert len(ledger.segments) == len(expected) > 40
    assert any(s.depth == 1 for s in ledger.segments)
    assert strip_markers(marked).encode("utf-8") == original.encode("utf-8")


def snippet() -> str:
    """Two real sentences from paper 1 to build the lint cases on."""
    text = paper_baseline(PAPER1)
    return text[slice(*line_span(text, ABSTRACT_OPENING))] + "\n" + text[slice(*line_span(text, CORRELATION))]


def lint_case(kind: str) -> str:
    body = snippet()
    a, b = ABSTRACT_OPENING, CORRELATION
    match kind:
        case "unbalanced-open":
            return open_marker("C1") + "\n" + body
        case "unbalanced-close":
            return body + close_marker("C1") + "\n"
        case "crossed":
            # <C1> a <C2> ... </C1> b </C2>
            crossed = body.replace(a, a + open_marker("C2"), 1).replace(b, close_marker("C1") + b, 1)
            return open_marker("C1") + "\n" + crossed + close_marker("C2") + "\n"
        case "self-nested":
            return open_marker("C1") + "\n" + body.replace(a, open_marker("C1") + a + close_marker("C1"), 1) + close_marker("C1") + "\n"
        case "duplicate-id":
            return body.replace(a, open_marker("C1") + a + close_marker("C1"), 1).replace(
                b, open_marker("C1") + b + close_marker("C1"), 1
            )
        case "rounds-zero":
            return open_marker("C1", rounds=0) + "\n" + body + close_marker("C1") + "\n"
        case "rounds-word":
            return body.replace(a, f"<!-- @rev C1 rounds=two by={BY} -->" + a + close_marker("C1"), 1)
        case "rounds-negative":
            return body.replace(a, f"<!-- @rev C1 rounds=-1 by={BY} -->" + a + close_marker("C1"), 1)
        case "date-month-13":
            return body.replace(a, open_marker("C1", 1, "robi:2026-13-01") + a + close_marker("C1"), 1)
        case "date-feb-30":
            return body.replace(a, open_marker("C1", 1, "robi:2026-02-30") + a + close_marker("C1"), 1)
        case "date-european":
            return body.replace(a, open_marker("C1", 1, "robi:25.09.2026") + a + close_marker("C1"), 1)
        case "date-compact":
            return body.replace(a, open_marker("C1", 1, "robi:20260925") + a + close_marker("C1"), 1)
        case "reviewer-without-date":
            return body.replace(a, open_marker("C1", 1, "robi") + a + close_marker("C1"), 1)
        case "unknown-key":
            return body.replace(a, f"<!-- @rev C1 rounds=1 by=robi:2026-09-25 note=x -->" + a + close_marker("C1"), 1)
        case "missing-key":
            return body.replace(a, "<!-- @rev C1 rounds=1 -->" + a + close_marker("C1"), 1)
        case "duplicate-key":
            return body.replace(a, f"<!-- @rev C1 rounds=1 rounds=1 by={BY} -->" + a + close_marker("C1"), 1)
        case "bad-id":
            return body.replace(a, open_marker("c1") + a + "<!-- @/rev c1 -->", 1)
        case "unterminated":
            return body.replace(a, "<!-- @rev C1 rounds=1 by=robi:2026-09-25 " + a, 1)
        case "multiline-marker":
            return "<!-- @rev C1\nrounds=1 by=robi:2026-09-25 -->\n" + body + close_marker("C1") + "\n"
        case "close-with-attributes":
            return body.replace(a, open_marker("C1") + a + "<!-- @/rev C1 rounds=1 -->", 1)
        case "empty-inline":
            return body.replace(a, open_marker("C1") + close_marker("C1") + a, 1)
        case "empty-own-line":
            return open_marker("C1") + "\n" + close_marker("C1") + "\n" + body
        case "whitespace-only":
            return body.replace(a, open_marker("C1") + "   " + close_marker("C1") + a, 1)
        case "unicode-inside":
            text = paper_baseline(PAPER1)
            line = text[slice(*line_span(text, UNICODE_CELL))]
            return line.replace(UNICODE_CELL, open_marker("C1") + UNICODE_CELL + close_marker("C1"), 1)
        case "marker-at-file-start":
            return open_marker("C1") + "\n" + body + close_marker("C1") + "\n"
        case "marker-at-file-end":
            return open_marker("C1") + "\n" + body.rstrip("\n") + "\n" + close_marker("C1")
        case "nested-distinct-ids":
            return open_marker("C1") + "\n" + body.replace(b, open_marker("N2") + b + close_marker("N2"), 1) + close_marker("C1") + "\n"
        case "example-in-code-fence":
            return body + "\n```markdown\n" + open_marker("C1") + "\n```\n"
        case "example-in-inline-code":
            return body + "\nWrite `" + close_marker("C1") + "` after the segment.\n"
    raise AssertionError(kind)


ERROR_CASES = {
    "unbalanced-open": IssueCode.UNCLOSED,
    "unbalanced-close": IssueCode.UNOPENED,
    "crossed": IssueCode.CROSSED,
    "self-nested": IssueCode.SELF_NESTED,
    "duplicate-id": IssueCode.DUPLICATE_ID,
    "rounds-zero": IssueCode.BAD_ROUNDS,
    "rounds-word": IssueCode.BAD_ROUNDS,
    "rounds-negative": IssueCode.BAD_ROUNDS,
    "date-month-13": IssueCode.BAD_DATE,
    "date-feb-30": IssueCode.BAD_DATE,
    "date-european": IssueCode.BAD_DATE,
    "date-compact": IssueCode.BAD_DATE,
    "reviewer-without-date": IssueCode.BAD_REVIEWER,
    "unknown-key": IssueCode.UNKNOWN_KEY,
    "missing-key": IssueCode.MISSING_KEY,
    "duplicate-key": IssueCode.DUPLICATE_KEY,
    "bad-id": IssueCode.BAD_ID,
    "unterminated": IssueCode.MALFORMED,
    "multiline-marker": IssueCode.MALFORMED,
    "close-with-attributes": IssueCode.MALFORMED,
    "empty-inline": IssueCode.EMPTY_SEGMENT,
    "empty-own-line": IssueCode.EMPTY_SEGMENT,
    "whitespace-only": IssueCode.EMPTY_SEGMENT,
}

VALID_CASES = {
    "unicode-inside": 1,
    "marker-at-file-start": 1,
    "marker-at-file-end": 1,
    "nested-distinct-ids": 2,
    "example-in-code-fence": 0,
    "example-in-inline-code": 0,
}


@pytest.mark.parametrize(("kind", "code"), ERROR_CASES.items(), ids=list(ERROR_CASES))
def test_lint_names_each_malformed_case(kind: str, code: IssueCode, tmp_path: Path) -> None:
    text = lint_case(kind)
    ledger = parse_ledger(text)
    assert code in {issue.code for issue in ledger.errors}, ledger.issues
    with pytest.raises(LedgerError):
        strip_markers(text)
    source = tmp_path / "paper.md"
    source.write_bytes(text.encode("utf-8"))
    result = CliRunner().invoke(app, ["ledger", "lint", str(source)])
    assert result.exit_code == 1
    assert str(code) in result.output
    # strip refuses rather than leaking a half-recognised marker into the twin.
    assert CliRunner().invoke(app, ["ledger", "strip", str(source)]).exit_code == 1
    assert not clean_twin_path(source).exists()


@pytest.mark.parametrize(("kind", "segments"), VALID_CASES.items(), ids=list(VALID_CASES))
def test_lint_accepts_valid_placements_and_strip_leaves_only_markers_out(kind: str, segments: int) -> None:
    text = lint_case(kind)
    ledger = parse_ledger(text)
    assert ledger.errors == ()
    assert len(ledger.segments) == segments
    clean = ledger.clean_text()
    assert "@rev" not in clean or "`" in clean  # code examples are text and stay
    if segments == 0:
        assert clean == text
    if kind == "unicode-inside":
        assert ledger.segments[0].text == UNICODE_CELL
    if kind in ("marker-at-file-start", "marker-at-file-end"):
        assert clean == snippet().rstrip("\n") + ("\n" if kind == "marker-at-file-start" else "")


def test_rounds_and_reviewer_count_disagreeing_is_only_a_warning() -> None:
    text = snippet().replace(CORRELATION, open_marker("C1", 3) + CORRELATION + close_marker("C1"), 1)
    ledger = parse_ledger(text)
    assert ledger.errors == ()
    assert [issue.code for issue in ledger.warnings] == [IssueCode.ROUNDS_REVIEWERS_MISMATCH]


def test_an_inline_marker_between_two_spaces_is_flagged() -> None:
    """Strip cannot know which space was there before; lint points at the spot."""
    text = snippet().replace(" " + CORRELATION, " " + open_marker("C1") + " " + CORRELATION + close_marker("C1"), 1)
    codes = [issue.code for issue in parse_ledger(text).warnings]
    assert IssueCode.AMBIGUOUS_SPACE in codes


def marked_paper() -> tuple[str, str]:
    original = paper_baseline(PAPER1)
    marked = wrap_inline(original, *span(original, CORRELATION), "C3")
    marked = wrap_inline(marked, *span(marked, UNICODE_CELL), "N1", rounds=1, by="claude:2026-10-10")
    marked = wrap_lines(marked, *line_span(marked, ABSTRACT_OPENING), "C2")
    return original, marked


def test_report_counts_equal_the_marked_segments(tmp_path: Path) -> None:
    _, marked = marked_paper()
    ledger = parse_ledger(marked)
    totals = report_totals(ledger)
    assert {key: totals[key] for key in ("segments", "rounds", "comments", "max rounds")} == {
        "segments": 3, "rounds": 5, "comments": 3, "max rounds": 2
    }

    source = tmp_path / "paper1.md"
    source.write_bytes(marked.encode("utf-8"))
    heatmap = tmp_path / "heat.html"
    result = CliRunner().invoke(app, ["ledger", "report", str(source), "--html", str(heatmap)])
    assert result.exit_code == 0, result.output
    table_rows = [line for line in result.output.splitlines() if re.match(r"^[CN][0-9]+ ", line)]
    assert sorted(row.split()[0] for row in table_rows) == ["C2", "C3", "N1"]
    assert {row.split()[0]: row.split()[1] for row in table_rows} == {"C2": "2", "C3": "2", "N1": "1"}

    page = heatmap.read_text(encoding="utf-8")
    assert len(re.findall(r"<mark ", page)) == page.count("</mark>") == totals["segments"]
    assert set(re.findall(r'data-id="([^"]+)"', page)) == {"C2", "C3", "N1"}
    assert re.search(r"<(script|link|img|iframe)\b|url\(|(src|href)=\"https?:", page) is None
    assert "@rev" not in page
    assert UNICODE_CELL in page


def test_the_heatmap_body_is_the_clean_text() -> None:
    original, marked = marked_paper()
    page = render_heatmap(parse_ledger(marked), "paper1.md")
    body = page[page.index('<div class="doc">') + len('<div class="doc">') : page.rindex("</div>\n</main>")]
    unescaped = re.sub(r"</?mark[^>]*>", "", body)
    assert unescaped.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#x27;", "'").replace(
        "&amp;", "&"
    ) == original


def test_bump_changes_exactly_one_marker(tmp_path: Path) -> None:
    original, marked = marked_paper()
    source = tmp_path / "paper1.md"
    source.write_bytes(marked.encode("utf-8"))
    before = parse_ledger(marked)

    result = CliRunner().invoke(app, ["ledger", "bump", str(source), "C3", "--by", "anton:2026-10-11"])
    assert result.exit_code == 0, result.output
    after_text = read_source(source)
    after = parse_ledger(after_text)

    changed = {
        b.id
        for b, a in zip(before.segments, after.segments, strict=True)
        if b.attributes != a.attributes
    }
    assert changed == {"C3"}
    c3_before, c3_after = before.segment("C3"), after.segment("C3")
    assert c3_after.rounds == c3_before.rounds + 1
    assert c3_after.attributes.by == (*c3_before.attributes.by, ReviewEntry(name="anton", on=date(2026, 10, 11)))
    # Outside the one marker, not a byte moved.
    assert after_text[: c3_after.open.start] == marked[: c3_before.open.start]
    assert after_text[c3_after.open.end :] == marked[c3_before.open.end :]
    assert strip_markers(after_text) == original


def test_bump_defaults_to_today_and_refuses_unknown_ids(tmp_path: Path) -> None:
    _, marked = marked_paper()
    assert parse_review_entry("anton", date(2026, 10, 12)) == ReviewEntry(name="anton", on=date(2026, 10, 12))
    with pytest.raises(KeyError):
        bump_segment(marked, "C99", ReviewEntry(name="anton", on=date(2026, 10, 12)))
    source = tmp_path / "paper1.md"
    source.write_bytes(marked.encode("utf-8"))
    assert CliRunner().invoke(app, ["ledger", "bump", str(source), "C99", "--by", "anton"]).exit_code == 1
    assert CliRunner().invoke(app, ["ledger", "bump", str(source), "C3", "--by", "anton:10/11/2026"]).exit_code != 0
    assert read_source(source) == marked


def test_strip_writes_the_clean_twin_beside_the_source_and_check_detects_staleness(tmp_path: Path) -> None:
    original, marked = marked_paper()
    source = tmp_path / "paper1-just-dna-lite.md"
    source.write_bytes(marked.encode("utf-8"))
    twin = tmp_path / "paper1-just-dna-lite.clean.md"
    runner = CliRunner()

    assert runner.invoke(app, ["ledger", "strip", str(source), "--check"]).exit_code == 1
    assert runner.invoke(app, ["ledger", "strip", str(source)]).exit_code == 0
    assert twin.read_bytes() == original.encode("utf-8")
    assert runner.invoke(app, ["ledger", "strip", str(source), "--check"]).exit_code == 0

    source.write_bytes(marked.replace(CORRELATION, CORRELATION.replace("Pearson", "Pearson's")).encode("utf-8"))
    assert runner.invoke(app, ["ledger", "strip", str(source), "--check"]).exit_code == 1
    assert runner.invoke(app, ["ledger", "strip", str(twin)]).exit_code == 1

    elsewhere = tmp_path / "out" / "x.md"
    elsewhere.parent.mkdir()
    assert runner.invoke(app, ["ledger", "strip", str(source), "--out", str(elsewhere)]).exit_code == 0
    assert "Pearson's" in elsewhere.read_text(encoding="utf-8")


def test_lint_cli_passes_marked_paper_and_strict_fails_on_warnings(tmp_path: Path) -> None:
    _, marked = marked_paper()
    source = tmp_path / "paper1.md"
    source.write_bytes(marked.encode("utf-8"))
    ok = CliRunner().invoke(app, ["ledger", "lint", str(source)])
    assert ok.exit_code == 0, ok.output
    assert "3 segment(s), 0 error(s)" in ok.output
    source.write_bytes(marked.replace("rounds=1", "rounds=2", 1).encode("utf-8"))
    assert CliRunner().invoke(app, ["ledger", "lint", str(source)]).exit_code == 0
    assert CliRunner().invoke(app, ["ledger", "lint", "--strict", str(source)]).exit_code == 1


def test_the_root_pyproject_installs_the_command() -> None:
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
    module_name, attribute = scripts["manuscript"].split(":")
    assert getattr(import_module(module_name), attribute) is app
    result = CliRunner().invoke(app, ["ledger", "--help"])
    assert result.exit_code == 0
    for command in ("lint", "strip", "report", "bump"):
        assert command in result.output


def test_blind_spots_are_exactly_the_uncovered_paragraphs() -> None:
    baseline = paper_baseline(PAPER1)
    unmarked = parse_ledger(baseline)
    every = paragraphs(unmarked)
    assert every, "the paper has prose"
    assert [p.line for p in blind_spots(unmarked)] == [p.line for p in every]

    _, marked = marked_paper()
    ledger = parse_ledger(marked)
    found = paragraphs(ledger)
    covered = [p for p in found if p.covered]
    spots = blind_spots(ledger)
    totals = report_totals(ledger)
    assert len(covered) + len(spots) == len(found) == totals["paragraphs"]
    assert totals["blind spots"] == len(spots)
    assert covered, "each marked segment covers at least one paragraph"
    for paragraph in covered:
        assert any(
            s.open.start < paragraph.end and paragraph.start < s.close.end for s in ledger.segments
        )
    assert not any(p.text.startswith("#") or "@rev" in p.text and p.text.startswith("<!--") for p in found)


def test_marking_a_blind_paragraph_removes_exactly_that_one() -> None:
    baseline = paper_baseline(PAPER1)
    before = blind_spots(parse_ledger(baseline))
    target = before[len(before) // 2]
    lines = baseline.splitlines(keepends=True)
    lines.insert(target.line, close_marker("N9") + "\n")
    lines.insert(target.line - 1, open_marker("N9", rounds=1, by="claude:2026-10-10") + "\n")
    after = blind_spots(parse_ledger("".join(lines)))
    assert len(after) == len(before) - 1
    assert target.text not in {p.text for p in after}
    assert {p.text for p in after} == {p.text for p in before} - {target.text}


def test_report_blind_flag_lists_the_blind_spots(tmp_path: Path) -> None:
    _, marked = marked_paper()
    source = tmp_path / "paper1.md"
    source.write_bytes(marked.encode("utf-8"))
    result = CliRunner().invoke(app, ["ledger", "report", str(source), "--blind"])
    assert result.exit_code == 0, result.output
    spots = blind_spots(parse_ledger(marked))
    header = next(line for line in result.output.splitlines() if line.startswith("BLIND SPOTS"))
    assert f"({len(spots)} of" in header
    listed = result.output.split(header, 1)[1].strip().splitlines()
    assert [int(line.split()[0]) for line in listed] == [spot.line for spot in spots]
