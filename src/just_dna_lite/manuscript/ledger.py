"""`manuscript ledger`: a revision ledger kept inside the manuscript's markdown source.

Each rewritten segment is wrapped in a pair of HTML comments, which markdown renderers and pandoc
drop from the output:

    <!-- @rev C3 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->
    The rewritten text.
    <!-- @/rev C3 -->

`strip` writes a clean twin (`<stem>.clean.md`) that is the source minus the markers, byte for
byte, so a downstream build never sees them. The full rules are in `docs/manuscript/README.md`.
"""

from __future__ import annotations

import html
import re
from bisect import bisect_left
from datetime import date
from enum import StrEnum
from pathlib import Path
from string import ascii_lowercase
from typing import Annotated, Optional

import typer
from pydantic import BaseModel, ConfigDict, Field

ID_PATTERN = r"[A-Z]+[0-9]+[a-z]?"
NAME_PATTERN = r"[A-Za-z][A-Za-z0-9_.-]*"
CLEAN_SUFFIX = ".clean.md"
HEAT_LEVELS = 5
FIRST_WORDS = 8

_ID_RE = re.compile(rf"^{ID_PATTERN}$")
_NAME_RE = re.compile(rf"^{NAME_PATTERN}$")
_ISO_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_KEY_VALUE_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_-]*)=(?P<value>.*)$")
_ROUNDS_RE = re.compile(r"^[0-9]+$")
# A marker candidate is any HTML comment whose body opens with `@rev` or `@/rev`. Anything else
# (`<!-- AUTHOR TODO … -->`) is ordinary text and survives `strip` untouched.
_CANDIDATE_START_RE = re.compile(r"<!--[ \t\r\n]*@/?rev\b")
_FENCE_OPEN_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})")
_INLINE_CODE_RE = re.compile(r"(?<!`)(?P<ticks>`+)(?!`)(?:(?!\n[ \t]*\n).)+?(?<!`)(?P=ticks)(?!`)", re.S)
_KNOWN_KEYS = ("rounds", "by")


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class IssueCode(StrEnum):
    MALFORMED = "malformed"
    BAD_ID = "bad-id"
    MISSING_KEY = "missing-key"
    UNKNOWN_KEY = "unknown-key"
    DUPLICATE_KEY = "duplicate-key"
    BAD_ROUNDS = "bad-rounds"
    BAD_REVIEWER = "bad-reviewer"
    BAD_DATE = "bad-date"
    UNCLOSED = "unclosed"
    UNOPENED = "unopened"
    CROSSED = "crossed"
    SELF_NESTED = "self-nested"
    DUPLICATE_ID = "duplicate-id"
    EMPTY_SEGMENT = "empty-segment"
    ROUNDS_REVIEWERS_MISMATCH = "rounds-reviewers-mismatch"
    AMBIGUOUS_SPACE = "ambiguous-space"
    INLINE_AT_LINE_START = "inline-at-line-start"


class MarkerKind(StrEnum):
    OPEN = "open"
    CLOSE = "close"


class Issue(BaseModel):
    model_config = ConfigDict(frozen=True)

    severity: Severity
    code: IssueCode
    line: int
    message: str


class ReviewEntry(BaseModel):
    """One `name:YYYY-MM-DD` item of a marker's `by=` list."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(pattern=rf"^{NAME_PATTERN}$")
    on: date

    def render(self) -> str:
        return f"{self.name}:{self.on.isoformat()}"


class RevAttributes(BaseModel):
    """The validated content of an opening marker."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=rf"^{ID_PATTERN}$")
    rounds: int = Field(ge=1)
    by: tuple[ReviewEntry, ...] = Field(min_length=1)

    @property
    def comment_id(self) -> str:
        """The reviewer comment this segment answers: `C3a` and `C3b` both answer `C3`."""
        return self.id.rstrip(ascii_lowercase)

    def render(self) -> str:
        by = ",".join(entry.render() for entry in self.by)
        return f"<!-- @rev {self.id} rounds={self.rounds} by={by} -->"


class Marker(BaseModel):
    """One marker comment found in the source, with its offsets into the decoded text."""

    model_config = ConfigDict(frozen=True)

    kind: MarkerKind
    id: str
    start: int
    end: int
    line: int
    own_line: bool
    attributes: Optional[RevAttributes] = None


class Segment(BaseModel):
    """A balanced open/close pair with valid attributes."""

    model_config = ConfigDict(frozen=True)

    attributes: RevAttributes
    open: Marker
    close: Marker
    depth: int
    text: str

    @property
    def id(self) -> str:
        return self.attributes.id

    @property
    def rounds(self) -> int:
        return self.attributes.rounds

    @property
    def first_words(self) -> str:
        words = self.text.split()
        head = " ".join(words[:FIRST_WORDS])
        return f"{head} …" if len(words) > FIRST_WORDS else head


class Ledger(BaseModel):
    """Everything `parse_ledger` learned about one document."""

    model_config = ConfigDict(frozen=True)

    text: str
    markers: tuple[Marker, ...]
    segments: tuple[Segment, ...]
    issues: tuple[Issue, ...]
    removals: tuple[tuple[int, int], ...]

    @property
    def errors(self) -> tuple[Issue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == Severity.ERROR)

    @property
    def warnings(self) -> tuple[Issue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == Severity.WARNING)

    def clean_text(self) -> str:
        return _cut(self.text, self.removals)

    def segment(self, segment_id: str) -> Optional[Segment]:
        return next((segment for segment in self.segments if segment.id == segment_id), None)


class _Candidate(BaseModel):
    kind: MarkerKind
    id: str
    start: int
    end: int
    attributes: Optional[RevAttributes]


# ---------------------------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------------------------


def _code_ranges(text: str) -> list[tuple[int, int]]:
    """Fenced code blocks and inline code spans: a marker shown there is an example, not a marker."""
    ranges: list[tuple[int, int]] = []
    prose: list[tuple[int, int]] = []
    offset = 0
    fence: Optional[str] = None
    fence_start = 0
    prose_start = 0
    for line in text.splitlines(keepends=True):
        if fence is None:
            opened = _FENCE_OPEN_RE.match(line)
            if opened:
                fence = opened.group("fence")
                fence_start = offset
                prose.append((prose_start, offset))
        elif re.match(rf"^ {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}[ \t]*\r?\n?$", line):
            fence = None
            ranges.append((fence_start, offset + len(line)))
            prose_start = offset + len(line)
        offset += len(line)
    if fence is None:
        prose.append((prose_start, len(text)))
    else:
        ranges.append((fence_start, len(text)))
    for start, end in prose:
        ranges.extend((start + m.start(), start + m.end()) for m in _INLINE_CODE_RE.finditer(text[start:end]))
    return ranges


def _in_ranges(offset: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= offset < end for start, end in ranges)


def _parse_by(value: str, line: int, issues: list[Issue]) -> Optional[tuple[ReviewEntry, ...]]:
    entries: list[ReviewEntry] = []
    for item in value.split(","):
        name, sep, day = item.partition(":")
        if not sep or not _NAME_RE.match(name):
            issues.append(
                _error(IssueCode.BAD_REVIEWER, line, f"reviewer entry {item!r} is not name:YYYY-MM-DD")
            )
            return None
        on = _iso_date(day)
        if on is None:
            issues.append(_error(IssueCode.BAD_DATE, line, f"{day!r} in {item!r} is not an ISO date (YYYY-MM-DD)"))
            return None
        entries.append(ReviewEntry(name=name, on=on))
    return tuple(entries)


def _iso_date(day: str) -> Optional[date]:
    """A strict YYYY-MM-DD date, or None. `fromisoformat` alone also takes `20260925` and week dates."""
    if not _ISO_DATE_RE.match(day):
        return None
    try:
        return date.fromisoformat(day)
    except ValueError:  # 2026-02-30, 2026-13-01
        return None


def _error(code: IssueCode, line: int, message: str) -> Issue:
    return Issue(severity=Severity.ERROR, code=code, line=line, message=message)


def _warning(code: IssueCode, line: int, message: str) -> Issue:
    return Issue(severity=Severity.WARNING, code=code, line=line, message=message)


def _parse_candidate(text: str, start: int, line: int, issues: list[Issue]) -> Optional[_Candidate]:
    end_body = text.find("-->", start + 4)
    if end_body == -1:
        issues.append(_error(IssueCode.MALFORMED, line, "marker comment is never closed with -->"))
        return None
    end = end_body + 3
    body = text[start + 4 : end_body]
    if "\n" in body:
        issues.append(_error(IssueCode.MALFORMED, line, "a marker must sit on one line"))
        return None
    tokens = body.split()
    if tokens[0] not in ("@rev", "@/rev"):
        issues.append(_error(IssueCode.MALFORMED, line, f"unknown marker word {tokens[0]!r}"))
        return None
    kind = MarkerKind.OPEN if tokens[0] == "@rev" else MarkerKind.CLOSE
    if len(tokens) < 2:
        issues.append(_error(IssueCode.MALFORMED, line, f"{tokens[0]} needs a segment id"))
        return None
    segment_id = tokens[1]
    if not _ID_RE.match(segment_id):
        issues.append(
            _error(IssueCode.BAD_ID, line, f"id {segment_id!r} does not match {ID_PATTERN} (C3, N1, C3a)")
        )
        return None
    if kind == MarkerKind.CLOSE:
        if len(tokens) != 2:
            issues.append(_error(IssueCode.MALFORMED, line, f"closing marker takes only the id, got {body.strip()!r}"))
            return None
        return _Candidate(kind=kind, id=segment_id, start=start, end=end, attributes=None)

    values: dict[str, str] = {}
    valid = True
    for token in tokens[2:]:
        pair = _KEY_VALUE_RE.match(token)
        if pair is None:
            issues.append(_error(IssueCode.MALFORMED, line, f"{token!r} is not key=value"))
            valid = False
            continue
        key = pair.group("key")
        if key not in _KNOWN_KEYS:
            issues.append(_error(IssueCode.UNKNOWN_KEY, line, f"unknown key {key!r} (known: rounds, by)"))
            valid = False
        elif key in values:
            issues.append(_error(IssueCode.DUPLICATE_KEY, line, f"key {key!r} given twice"))
            valid = False
        else:
            values[key] = pair.group("value")
    for key in _KNOWN_KEYS:
        if key not in values:
            issues.append(_error(IssueCode.MISSING_KEY, line, f"{segment_id}: missing {key}="))
            valid = False
    rounds = values.get("rounds")
    if rounds is not None and (not _ROUNDS_RE.match(rounds) or int(rounds) < 1):
        issues.append(_error(IssueCode.BAD_ROUNDS, line, f"rounds={rounds!r} must be a whole number of at least 1"))
        valid = False
    by = _parse_by(values["by"], line, issues) if "by" in values else None
    if not valid or by is None or rounds is None:
        return _Candidate(kind=kind, id=segment_id, start=start, end=end, attributes=None)
    attributes = RevAttributes(id=segment_id, rounds=int(rounds), by=by)
    if attributes.rounds != len(attributes.by):
        issues.append(
            _warning(
                IssueCode.ROUNDS_REVIEWERS_MISMATCH,
                line,
                f"{segment_id}: rounds={attributes.rounds} but {len(attributes.by)} reviewer entries",
            )
        )
    return _Candidate(kind=kind, id=segment_id, start=start, end=end, attributes=attributes)


def _line_bounds(text: str, offset: int) -> tuple[int, int, int]:
    """(line start, end of line content, end including the terminator) around *offset*."""
    start = text.rfind("\n", 0, offset) + 1
    newline = text.find("\n", offset)
    if newline == -1:
        return start, len(text), len(text)
    content_end = newline - 1 if newline > start and text[newline - 1] == "\r" else newline
    return start, content_end, newline + 1


def _removals(text: str, candidates: list[_Candidate]) -> tuple[list[tuple[int, int]], set[int]]:
    """Ranges `strip` deletes, and the starts of markers that own their whole line.

    A line holding nothing but markers and spaces goes with its terminator. When such lines end the
    file without a final terminator, the terminator before them goes instead, so the file does not
    gain or lose a newline. Any other marker is cut exactly, whitespace beside it is text.
    """
    by_line: dict[int, list[_Candidate]] = {}
    for candidate in candidates:
        by_line.setdefault(_line_bounds(text, candidate.start)[0], []).append(candidate)
    ranges: list[tuple[int, int]] = []
    own_line: set[int] = set()
    eof_block = False
    for line_start, members in by_line.items():
        _, content_end, line_end = _line_bounds(text, line_start)
        rest = text[line_start:content_end]
        for member in sorted(members, key=lambda c: c.start, reverse=True):
            rest = rest[: member.start - line_start] + rest[member.end - line_start :]
        if rest.strip(" \t") == "":
            ranges.append((line_start, line_end))
            own_line.update(member.start for member in members)
            eof_block = eof_block or (line_end == len(text) and not text.endswith("\n"))
        else:
            ranges.extend((member.start, member.end) for member in members)
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    if eof_block and merged and merged[-1][1] == len(text) and merged[-1][0] > 0:
        start = merged[-1][0]
        start -= 2 if text[max(0, start - 2) : start] == "\r\n" else 1
        merged[-1] = (start, len(text))
    return merged, own_line


def _cut(text: str, ranges: tuple[tuple[int, int], ...] | list[tuple[int, int]]) -> str:
    pieces: list[str] = []
    cursor = 0
    for start, end in ranges:
        pieces.append(text[cursor:start])
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def parse_ledger(text: str) -> Ledger:
    """Find every marker, pair them, and report what is wrong. Never raises on bad markers."""
    newlines = [i for i, ch in enumerate(text) if ch == "\n"]

    def line_of(offset: int) -> int:
        return bisect_left(newlines, offset) + 1

    code = _code_ranges(text)
    issues: list[Issue] = []
    candidates: list[_Candidate] = []
    for match in _CANDIDATE_START_RE.finditer(text):
        if _in_ranges(match.start(), code):
            continue
        candidate = _parse_candidate(text, match.start(), line_of(match.start()), issues)
        if candidate is not None:
            candidates.append(candidate)

    removals, own_line = _removals(text, candidates)
    markers = [
        Marker(
            kind=c.kind,
            id=c.id,
            start=c.start,
            end=c.end,
            line=line_of(c.start),
            own_line=c.start in own_line,
            attributes=c.attributes,
        )
        for c in candidates
    ]

    seen_ids: dict[str, int] = {}
    for marker in markers:
        if marker.kind != MarkerKind.OPEN:
            continue
        if marker.id in seen_ids:
            issues.append(
                _error(
                    IssueCode.DUPLICATE_ID,
                    marker.line,
                    f"{marker.id} is already used on line {seen_ids[marker.id]}; give each place its own"
                    f" id ({marker.id.rstrip(ascii_lowercase)}a, …b)",
                )
            )
        else:
            seen_ids[marker.id] = marker.line

    stack: list[Marker] = []
    segments: list[Segment] = []
    for marker in markers:
        if marker.kind == MarkerKind.OPEN:
            if any(open_.id == marker.id for open_ in stack):
                issues.append(_error(IssueCode.SELF_NESTED, marker.line, f"{marker.id} opens inside itself"))
            stack.append(marker)
            continue
        if stack and stack[-1].id == marker.id:
            opened = stack.pop()
            inner = _cut(
                text[opened.end : marker.start],
                [
                    (r[0] - opened.end, r[1] - opened.end)
                    for r in _clip(removals, opened.end, marker.start)
                ],
            )
            if inner.strip() == "":
                issues.append(_error(IssueCode.EMPTY_SEGMENT, opened.line, f"{opened.id} wraps no text"))
            elif opened.attributes is not None:
                segments.append(
                    Segment(attributes=opened.attributes, open=opened, close=marker, depth=len(stack), text=inner)
                )
            continue
        open_index = next((i for i in range(len(stack) - 1, -1, -1) if stack[i].id == marker.id), None)
        if open_index is None:
            issues.append(_error(IssueCode.UNOPENED, marker.line, f"@/rev {marker.id} closes nothing"))
            continue
        inner_open = stack[-1]
        issues.append(
            _error(
                IssueCode.CROSSED,
                marker.line,
                f"@/rev {marker.id} closes while {inner_open.id} (line {inner_open.line}) is still open",
            )
        )
        del stack[open_index]
    for marker in stack:
        issues.append(_error(IssueCode.UNCLOSED, marker.line, f"@rev {marker.id} is never closed"))

    for marker in markers:
        if marker.own_line:
            continue
        before = text[marker.start - 1] if marker.start > 0 else ""
        after = text[marker.end] if marker.end < len(text) else ""
        if before in (" ", "\t") and after in (" ", "\t"):
            issues.append(
                _warning(
                    IssueCode.AMBIGUOUS_SPACE,
                    marker.line,
                    f"inline marker for {marker.id} has a space on both sides; strip keeps both",
                )
            )
        if before in ("", "\n"):
            issues.append(
                _warning(
                    IssueCode.INLINE_AT_LINE_START,
                    marker.line,
                    f"inline marker for {marker.id} opens the line; CommonMark renders that line as raw HTML,"
                    " put the marker on its own line instead",
                )
            )

    issues.sort(key=lambda issue: (issue.line, issue.severity != Severity.ERROR))
    segments.sort(key=lambda segment: segment.open.start)
    return Ledger(
        text=text,
        markers=tuple(markers),
        segments=tuple(segments),
        issues=tuple(issues),
        removals=tuple(removals),
    )


def _clip(ranges: list[tuple[int, int]] | tuple[tuple[int, int], ...], lo: int, hi: int) -> list[tuple[int, int]]:
    return [(max(start, lo), min(end, hi)) for start, end in ranges if end > lo and start < hi]


# ---------------------------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------------------------


class LedgerError(Exception):
    """The document has marker errors; the operation refused to run."""

    def __init__(self, issues: tuple[Issue, ...]) -> None:
        super().__init__(f"{len(issues)} marker error(s)")
        self.issues = issues


def read_source(path: Path) -> str:
    """Decode without newline translation, so CRLF and a BOM survive the round trip."""
    return path.read_bytes().decode("utf-8")


def clean_twin_path(path: Path) -> Path:
    return path.with_name(f"{path.stem}{CLEAN_SUFFIX}")


def strip_markers(text: str) -> str:
    """The source minus its markers and the whitespace they alone introduced."""
    ledger = parse_ledger(text)
    if ledger.errors:
        raise LedgerError(ledger.errors)
    return ledger.clean_text()


def bump_segment(text: str, segment_id: str, entry: ReviewEntry) -> str:
    """Add one round to *segment_id* and append *entry*; nothing else in *text* changes."""
    ledger = parse_ledger(text)
    if ledger.errors:
        raise LedgerError(ledger.errors)
    segment = ledger.segment(segment_id)
    if segment is None:
        known = ", ".join(s.id for s in ledger.segments) or "none"
        raise KeyError(f"no segment {segment_id!r} (known: {known})")
    attributes = segment.attributes.model_copy(
        update={"rounds": segment.rounds + 1, "by": (*segment.attributes.by, entry)}
    )
    return text[: segment.open.start] + attributes.render() + text[segment.open.end :]


def parse_review_entry(value: str, today: date) -> ReviewEntry:
    """`NAME` or `NAME:YYYY-MM-DD`, the `--by` option of `bump`."""
    name, sep, day = value.partition(":")
    if not _NAME_RE.match(name):
        raise ValueError(f"reviewer name {name!r} must match {NAME_PATTERN}")
    if not sep:
        return ReviewEntry(name=name, on=today)
    on = _iso_date(day)
    if on is None:
        raise ValueError(f"{day!r} is not an ISO date (YYYY-MM-DD)")
    return ReviewEntry(name=name, on=on)


def report_rows(ledger: Ledger) -> list[dict[str, str]]:
    return [
        {
            "id": segment.id,
            "rounds": str(segment.rounds),
            "reviewers": ", ".join(entry.render() for entry in segment.attributes.by),
            "line": str(segment.open.line),
            "first words": segment.first_words,
        }
        for segment in ledger.segments
    ]


def report_totals(ledger: Ledger) -> dict[str, int]:
    return {
        "segments": len(ledger.segments),
        "rounds": sum(segment.rounds for segment in ledger.segments),
        "comments": len({segment.attributes.comment_id for segment in ledger.segments}),
        "max rounds": max((segment.rounds for segment in ledger.segments), default=0),
    }


def format_report(ledger: Ledger) -> str:
    rows = report_rows(ledger)
    headers = ["id", "rounds", "reviewers", "line", "first words"]
    widths = {h: max([len(h), *(len(row[h]) for row in rows)]) for h in headers[:-1]}
    lines = ["  ".join([*(h.upper().ljust(widths[h]) for h in headers[:-1]), headers[-1].upper()])]
    for row in rows:
        cells = [row[h].rjust(widths[h]) if h in ("rounds", "line") else row[h].ljust(widths[h]) for h in headers[:-1]]
        lines.append("  ".join([*cells, row["first words"]]))
    totals = report_totals(ledger)
    lines.append("")
    lines.append(", ".join(f"{key}: {value}" for key, value in totals.items()))
    return "\n".join(lines) + "\n"


_HEATMAP_CSS = """
:root {
  --bg: #fbfaf7; --fg: #1d1c1a; --muted: #6b675f; --rule: #dedad2;
  --h1: #fdf1c7; --h2: #fbdc8e; --h3: #f6b866; --h4: #ee8d4f; --h5: #dd5f3f;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1a1917; --fg: #ece9e2; --muted: #a39e94; --rule: #3a3833;
    --h1: #3d3520; --h2: #5a4520; --h3: #77501f; --h4: #94511f; --h5: #b0472a;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.6 Georgia, "Times New Roman", serif; }
header, main { max-width: 52rem; margin: 0 auto; padding: 1.5rem 16px; }
h1 { font-size: 1.4rem; margin: 0 0 .25rem; }
.meta { color: var(--muted); margin: 0 0 1rem; font-size: .95rem; }
.legend { display: flex; gap: .5rem; flex-wrap: wrap; margin: 0 0 1rem; font-size: .9rem; }
.legend span { padding: .1rem .6rem; border-radius: 3px; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: .9rem; }
th, td { text-align: left; padding: .3rem .5rem; border-bottom: 1px solid var(--rule); vertical-align: top; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
.doc { white-space: pre-wrap; overflow-wrap: anywhere; border-top: 1px solid var(--rule); padding-top: 1rem; }
mark { color: inherit; border-radius: 2px; }
.h1 { background: var(--h1); } .h2 { background: var(--h2); } .h3 { background: var(--h3); }
.h4 { background: var(--h4); } .h5 { background: var(--h5); }
a { color: inherit; }
"""


def render_heatmap(ledger: Ledger, title: str) -> str:
    """A self-contained HTML page: the clean text with each segment shaded by its rounds."""
    opening = {segment.open.start: segment for segment in ledger.segments}
    closing = {segment.close.start for segment in ledger.segments}
    body: list[str] = []
    cursor = 0
    for start, end in ledger.removals:
        body.append(html.escape(ledger.text[cursor:start]))
        for marker in ledger.markers:
            if not start <= marker.start < end:
                continue
            if marker.start in opening:
                segment = opening[marker.start]
                reviewers = ", ".join(f"{e.name} {e.on.isoformat()}" for e in segment.attributes.by)
                tip = f"{segment.id}: {segment.rounds} round(s); {reviewers}"
                level = min(segment.rounds, HEAT_LEVELS)
                body.append(
                    f'<mark id="seg-{segment.id}" class="h{level}" data-id="{segment.id}"'
                    f' data-rounds="{segment.rounds}" title="{html.escape(tip)}">'
                )
            elif marker.start in closing:
                body.append("</mark>")
        cursor = end
    body.append(html.escape(ledger.text[cursor:]))

    rows = "\n".join(
        f'<tr><td><a href="#seg-{html.escape(row["id"])}">{html.escape(row["id"])}</a></td>'
        f'<td class="num">{row["rounds"]}</td><td>{html.escape(row["reviewers"])}</td>'
        f'<td class="num">{row["line"]}</td><td>{html.escape(row["first words"])}</td></tr>'
        for row in report_rows(ledger)
    )
    totals = ", ".join(f"{key}: {value}" for key, value in report_totals(ledger).items())
    legend = "".join(
        f'<span class="h{level}">{level}{"+" if level == HEAT_LEVELS else ""} round{"s" if level > 1 else ""}</span>'
        for level in range(1, HEAT_LEVELS + 1)
    )
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>Revision heat map</title>\n<style>{_HEATMAP_CSS}</style>\n</head>\n<body>\n"
        f"<header>\n<h1>Revision heat map</h1>\n<p class=\"meta\">{html.escape(title)} · {totals}</p>\n"
        f'<div class="legend">{legend}</div>\n'
        '<div class="table-wrap"><table>\n<thead><tr><th>ID</th><th>Rounds</th><th>Reviewers</th>'
        f"<th>Line</th><th>First words</th></tr></thead>\n<tbody>\n{rows}\n</tbody>\n</table></div>\n"
        f'</header>\n<main>\n<div class="doc">{"".join(body)}</div>\n</main>\n</body>\n</html>\n'
    )


# ---------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------

ledger_app = typer.Typer(
    help="Track rewritten manuscript segments in marker comments and write a marker-free twin.",
    no_args_is_help=True,
)

PathArg = Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True, help="Markdown source")]


def _print_issues(path: Path, issues: tuple[Issue, ...]) -> None:
    for issue in issues:
        typer.echo(f"{path}:{issue.line}: {issue.severity} {issue.code}: {issue.message}", err=True)


def _load_clean(path: Path) -> Ledger:
    """Parse *path*, print its issues, and exit 1 if any of them is an error."""
    ledger = parse_ledger(read_source(path))
    _print_issues(path, ledger.issues)
    if ledger.errors:
        raise typer.Exit(1)
    return ledger


@ledger_app.command()
def lint(
    paths: Annotated[list[Path], typer.Argument(exists=True, dir_okay=False, readable=True, help="Markdown sources")],
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as errors")] = False,
) -> None:
    """Check marker syntax and pairing. Exit 1 on any error (or warning with --strict)."""
    failed = False
    for path in paths:
        ledger = parse_ledger(read_source(path))
        _print_issues(path, ledger.issues)
        failed = failed or bool(ledger.errors) or (strict and bool(ledger.warnings))
        typer.echo(
            f"{path}: {len(ledger.segments)} segment(s), {len(ledger.errors)} error(s),"
            f" {len(ledger.warnings)} warning(s)"
        )
    if failed:
        raise typer.Exit(1)


@ledger_app.command()
def strip(
    path: PathArg,
    out: Annotated[Optional[Path], typer.Option("--out", "-o", help="Default: <stem>.clean.md beside PATH")] = None,
    check: Annotated[bool, typer.Option("--check", help="Write nothing; exit 1 if the twin is missing or stale")] = False,
) -> None:
    """Write the clean twin: PATH minus its markers, otherwise byte-identical."""
    if path.name.endswith(CLEAN_SUFFIX):
        typer.echo(f"{path} is already a clean twin; strip its source instead", err=True)
        raise typer.Exit(1)
    target = out if out is not None else clean_twin_path(path)
    clean = _load_clean(path).clean_text().encode("utf-8")
    current = target.read_bytes() if target.is_file() else None
    if check:
        if current != clean:
            typer.echo(f"{target} is {'stale' if current is not None else 'missing'}", err=True)
            raise typer.Exit(1)
        typer.echo(f"{target} is current")
        return
    if current != clean:
        target.write_bytes(clean)
    typer.echo(f"wrote {target}")


@ledger_app.command()
def report(
    path: PathArg,
    html_out: Annotated[Optional[Path], typer.Option("--html", help="Also write a self-contained heat map")] = None,
) -> None:
    """List every segment with its rounds and reviewers, then totals."""
    ledger = _load_clean(path)
    typer.echo(format_report(ledger), nl=False)
    if html_out is not None:
        html_out.write_bytes(render_heatmap(ledger, path.name).encode("utf-8"))
        typer.echo(f"wrote {html_out}")


@ledger_app.command()
def bump(
    path: PathArg,
    segment_id: Annotated[str, typer.Argument(metavar="ID", help="Segment id, e.g. C3 or C3a")],
    by: Annotated[str, typer.Option("--by", help="NAME or NAME:YYYY-MM-DD (default date: today)")],
) -> None:
    """Add one round to a segment and append the reviewer to its `by` list."""
    try:
        entry = parse_review_entry(by, date.today())
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--by") from exc
    text = _load_clean(path).text
    try:
        updated = bump_segment(text, segment_id, entry)
    except KeyError as exc:
        typer.echo(str(exc.args[0]), err=True)
        raise typer.Exit(1) from exc
    path.write_bytes(updated.encode("utf-8"))
    segment = parse_ledger(updated).segment(segment_id)
    typer.echo(f"{segment_id}: rounds={segment.rounds if segment else '?'}")
