"""Which words of the newest round changed in which round, back to a base round.

The `@rev` ledger marks a whole segment once anything in it was rewritten, so a paragraph that kept nine
sentences of ten still reads as rewritten. This compares the clean text of consecutive rounds word by word
and gives every word of the newest round the round that last introduced it; words carried unchanged from
the base round get no round. The spans are what a reader of the newest Doc would colour.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from just_dna_lite.manuscript.ledger import read_source, strip_markers

# Words and punctuation apart, so a changed superscript or comma does not colour the word beside it.
WORD = re.compile(r"\w+|[^\w\s]")
# Markdown syntax that never reaches the rendered Doc: emphasis, code ticks, sub/superscript, link targets,
# image and attribute blocks. Applied to a span's text only, never to what is compared.
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_ATTRS = re.compile(r"\{[^}]*\}")
_MARKUP = re.compile(r"(\*\*|\*|__|`|\^|~|\\(?=[\[\]*_#.\-]))")
_HEADING = re.compile(r"^#+\s+(.*)$", re.MULTILINE)


class Token(BaseModel):
    word: str
    start: int
    end: int


class Span(BaseModel):
    """A run of consecutive words introduced in one round, as offsets into the newest clean text."""

    round: str
    start: int
    end: int
    markdown: str
    text: str
    before: str
    after: str
    section: Optional[str]
    words: int


class Deletion(BaseModel):
    """Words a round removed with nothing put in their place, anchored where they stood in the newest text."""

    round: str
    at: int
    removed: str
    before: str
    after: str
    section: Optional[str]


class RoundsDiff(BaseModel):
    base: str
    rounds: list[str]
    words: int
    unchanged_words: int
    words_by_round: dict[str, int]
    spans: list[Span]
    deletions: list[Deletion]


def tokens(text: str) -> list[Token]:
    return [Token(word=m.group(), start=m.start(), end=m.end()) for m in WORD.finditer(text)]


def plain(markdown: str) -> str:
    """A span as the rendered Doc shows it, for finding it there: link text kept, syntax dropped."""
    text = _LINK.sub(r"\1", markdown)
    text = _ATTRS.sub("", text)
    text = _HEADING.sub(r"\1", text)
    return _MARKUP.sub("", text)


def carry_rounds(previous: list[Token], labels: list[Optional[str]], current: list[Token], name: str,
                 previous_text: str) -> tuple[list[Optional[str]], list[tuple[int, str]]]:
    """Labels for `current`: a word matched to `previous` keeps its label, any other word gets `name`.

    Also returns each pure deletion as (index in `current` where it stood, the removed words).
    """
    matcher = SequenceMatcher(None, [t.word for t in previous], [t.word for t in current], autojunk=False)
    out: list[Optional[str]] = [name] * len(current)
    removed: list[tuple[int, str]] = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            out[j1:j2] = labels[i1:i2]
        elif op == "delete":
            removed.append((j1, previous_text[previous[i1].start:previous[i2 - 1].end]))
    return out, removed


def _section_at(text: str, offset: int) -> Optional[str]:
    heading = None
    for match in _HEADING.finditer(text):
        if match.start() > offset:
            break
        heading = plain(match.group(1)).strip()
    return heading


def _context(text: str, toks: list[Token], i: int, j: int, n: int = 8) -> tuple[str, str]:
    """Up to `n` words on each side of tokens [i, j), as the Doc shows them."""
    left = toks[max(0, i - n):i]
    right = toks[j:j + n]
    before = plain(text[left[0].start:left[-1].end]) if left else ""
    after = plain(text[right[0].start:right[-1].end]) if right else ""
    return before, after


def rounds_diff(masters: list[tuple[str, Path]]) -> RoundsDiff:
    """`masters` are (round name, Markdown master) from the base round to the newest, in order."""
    if len(masters) < 2:
        raise ValueError("give the base round and at least one later round")
    texts = [(name, strip_markers(read_source(path))) for name, path in masters]
    base_name, base_text = texts[0]
    prev_tokens = tokens(base_text)
    prev_text = base_text
    labels: list[Optional[str]] = [None] * len(prev_tokens)
    pending: list[tuple[str, int, str]] = []  # (round, index in that round's tokens, removed text)
    for name, text in texts[1:]:
        cur = tokens(text)
        new_labels, removed = carry_rounds(prev_tokens, labels, cur, name, prev_text)
        # A deletion from an earlier round is re-anchored onto this round's tokens through the same matcher.
        matcher = SequenceMatcher(None, [t.word for t in prev_tokens], [t.word for t in cur], autojunk=False)
        moved: list[tuple[str, int, str]] = []
        for rnd, index, gone in pending:
            moved.append((rnd, _map_index(matcher, index), gone))
        pending = moved + [(name, index, gone) for index, gone in removed]
        prev_tokens, labels, prev_text = cur, new_labels, text

    newest = prev_text
    spans: list[Span] = []
    i = 0
    while i < len(prev_tokens):
        label = labels[i]
        j = i + 1
        while j < len(prev_tokens) and labels[j] == label:
            j += 1
        if label is not None:
            start, end = prev_tokens[i].start, prev_tokens[j - 1].end
            before, after = _context(newest, prev_tokens, i, j)
            md = newest[start:end]
            spans.append(Span(round=label, start=start, end=end, markdown=md, text=plain(md), before=before,
                              after=after, section=_section_at(newest, start),
                              words=sum(1 for t in prev_tokens[i:j] if re.match(r"\w", t.word))))
        i = j
    deletions = []
    for rnd, index, gone in pending:
        at = prev_tokens[index].start if index < len(prev_tokens) else len(newest)
        before, after = _context(newest, prev_tokens, index, index)
        deletions.append(Deletion(round=rnd, at=at, removed=plain(gone), before=before, after=after,
                                  section=_section_at(newest, at)))
    is_word = [bool(re.match(r"\w", t.word)) for t in prev_tokens]
    by_round = {name: sum(w for w, label in zip(is_word, labels) if label == name) for name, _ in texts[1:]}
    return RoundsDiff(base=base_name, rounds=[name for name, _ in texts[1:]], words=sum(is_word),
                      unchanged_words=sum(w for w, label in zip(is_word, labels) if label is None),
                      words_by_round=by_round,
                      spans=spans, deletions=sorted(deletions, key=lambda d: d.at))


def _map_index(matcher: SequenceMatcher, index: int) -> int:
    """Where position `index` of the old sequence lands in the new one: inside an equal block it moves with
    the block, otherwise it lands just after the last equal block that ends before it."""
    landed = 0
    for block in matcher.get_matching_blocks():
        if block.a <= index <= block.a + block.size and block.size:
            return block.b + (index - block.a)
        if block.a + block.size <= index:
            landed = block.b + block.size
    return landed
