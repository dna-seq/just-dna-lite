"""`manuscript rounds-diff` on the real Paper 1 rounds.

Later rounds are built at test time from the v0.3 text by edits whose position is known, so the expected
label of every word is computed here, not read from the output.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from just_dna_lite.manuscript.cli import app
from just_dna_lite.manuscript.ledger import read_source, strip_markers
from just_dna_lite.manuscript.rounds_diff import WORD, plain, rounds_diff

ROOT = Path(__file__).resolve().parents[1]
V03 = ROOT / "docs/manuscript/v0.3/paper1-just-dna-lite.md"
REAL_ROUNDS = [(v, ROOT / f"docs/manuscript/{v}/paper1-just-dna-lite.md") for v in ("v0.3", "v0.4", "v0.5", "v0.6")]


def _base() -> str:
    return strip_markers(read_source(V03))


def _sentences(text: str) -> list[re.Match[str]]:
    """Plain prose sentences of the base: no markup, long enough to be unique."""
    found = [m for m in re.finditer(r"(?<=[.!?] )[A-Z][a-z][^.\n*`|^\[\]#]{60,200}\.(?= [A-Z])", text)]
    return [m for m in found if text.count(m.group()) == 1]


def _write(tmp_path: Path, rounds: list[tuple[str, str]]) -> list[tuple[str, Path]]:
    paths = []
    for name, text in rounds:
        path = tmp_path / f"{name}.md"
        path.write_text(text, encoding="utf-8")
        paths.append((name, path))
    return paths


def _labelled_words(result) -> dict[str, list[str]]:
    words: dict[str, list[str]] = {}
    for span in result.spans:
        words.setdefault(span.round, []).extend(w for w in WORD.findall(span.markdown) if re.match(r"\w", w))
    return words


def test_identical_rounds_mark_nothing(tmp_path: Path) -> None:
    base = _base()
    result = rounds_diff(_write(tmp_path, [("a", base), ("b", base), ("c", base)]))
    assert result.spans == [] and result.deletions == []
    assert result.unchanged_words == result.words == len([w for w in WORD.findall(base) if re.match(r"\w", w)])


def test_a_changed_sentence_takes_the_round_that_last_changed_it(tmp_path: Path) -> None:
    base = _base()
    rng = random.Random(7)
    first, second = rng.sample(_sentences(base), 2)
    v1 = base.replace(first.group(), "Inserted in round one alone.")
    v2 = v1.replace(second.group(), "Rewritten in round two.")
    v3 = v2.replace("Inserted in round one alone.", "Inserted in round three instead.")
    result = rounds_diff(_write(tmp_path, [("r0", base), ("r1", v1), ("r2", v2), ("r3", v3)]))
    words = _labelled_words(result)
    # r3 kept "Inserted in round" from r1 and replaced the rest, so those words stay r1's.
    assert words["r1"] == ["Inserted", "in", "round"]
    assert set(words["r2"]) == {"Rewritten", "in", "round", "two"}
    assert words["r3"] == ["three", "instead"]
    assert not {"one", "alone"} & {w for ws in words.values() for w in ws}
    assert result.unchanged_words + sum(result.words_by_round.values()) == result.words


def test_a_pure_deletion_is_anchored_where_it_stood(tmp_path: Path) -> None:
    base = _base()
    gone = _sentences(base)[3]
    newer = base[:gone.start()] + base[gone.end():]
    result = rounds_diff(_write(tmp_path, [("r0", base), ("r1", newer)]))
    assert result.spans == []
    # The matcher may align the removed run one token over (". X ... 0" for "X ... 0."), never further.
    [deletion] = result.deletions
    assert sorted(WORD.findall(deletion.removed)) == sorted(WORD.findall(plain(gone.group())))
    assert abs(deletion.at - gone.start()) <= 2


def test_spans_are_slices_of_the_newest_clean_text() -> None:
    result = rounds_diff(REAL_ROUNDS)
    newest = strip_markers(read_source(REAL_ROUNDS[-1][1]))
    assert result.spans, "v0.3 to v0.6 changed text"
    for span in result.spans:
        assert newest[span.start:span.end] == span.markdown
    starts = [s.start for s in result.spans]
    assert starts == sorted(starts) and all(a.end <= b.start for a, b in zip(result.spans, result.spans[1:]))
    assert set(result.words_by_round) == {"v0.4", "v0.5", "v0.6"}
    assert result.unchanged_words + sum(result.words_by_round.values()) == result.words


@pytest.mark.parametrize("item", ["v0.3", "v0.3=does/not/exist.md"])
def test_the_cli_refuses_a_bad_round(tmp_path: Path, item: str) -> None:
    out = tmp_path / "diff.json"
    run = CliRunner().invoke(app, ["rounds-diff", item, f"v0.4={REAL_ROUNDS[1][1]}", "--out", str(out)])
    assert run.exit_code != 0 and not out.exists()


def test_the_cli_writes_the_spans(tmp_path: Path) -> None:
    out = tmp_path / "diff.json"
    args = [f"{name}={path}" for name, path in REAL_ROUNDS[:2]]
    run = CliRunner().invoke(app, ["rounds-diff", *args, "--out", str(out)])
    assert run.exit_code == 0, run.output
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["base"] == "v0.3" and data["rounds"] == ["v0.4"]
    assert {span["round"] for span in data["spans"]} == {"v0.4"}
