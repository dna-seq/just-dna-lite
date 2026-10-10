# Manuscript tools

`uv run manuscript` holds the tools for the manuscript sources in this folder.

## Revision ledger

The manuscript sources (`v0.3/paper1-just-dna-lite.md`, `v0.3/paper2-just-module-creator.md`) record,
inside the text, which segments were rewritten in answer to a review and how many rounds each went
through. The record is a pair of HTML comments around the segment, so GitHub, editors and pandoc show
nothing. `manuscript ledger strip` writes a clean twin without them for any build that should never
see them.

### Syntax

```markdown
<!-- @rev C3 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->
The rewritten paragraph.
<!-- @/rev C3 -->
```

- **Id**: the comment it answers. `C1` to `C39` are Robi Tacutu's v0.3 comments in paper order,
  `N1` to `N5` our own findings. The pattern is capital letters, digits, and an optional lowercase
  letter: `C3`, `N1`, `C3a`.
- **Ids are unique per file.** When one comment changed text in several places, give each place a
  letter: `C3a`, `C3b`. Reports group them back under `C3`. Uniqueness lets `bump C3a` name exactly
  one segment, and catches a marker pair copied along with its text by mistake.
- **`rounds=`**: how many times the segment was rewritten and checked, a whole number of at least 1.
- **`by=`**: who did each round and when, comma-separated `name:YYYY-MM-DD`. Lint warns (does not fail)
  when the number of entries differs from `rounds`.
- Both keys are required; any other key is an error. The closing marker carries the id and nothing else.
- Segments nest when their ids differ (a sentence rewritten for `N2` inside a paragraph rewritten for
  `C5`). Crossed pairs and a segment inside itself are errors, and so is a segment with no text.
- Markers inside fenced code blocks or inline code are examples, not markers (as in this file).

### Where a marker goes

Two placements, and `strip` is the exact inverse of each:

1. **On its own line** (only spaces around it). `strip` removes the whole line with its line break.
   Use this for whole paragraphs, headings and list blocks. At the very end of a file that has no
   final line break, write the closing marker as a new last line; `strip` then removes the line break
   before it, so the twin ends where the original did.
2. **Inline**, glued to the text with no added space: `sentence.<!-- @rev C4 ... -->Next sentence.<!-- @/rev C4 -->`.
   `strip` removes only the comment, so every space beside an inline marker is text. Use this for a
   sentence, a phrase or a table cell. Lint warns when an inline marker has a space on both sides
   (one of them was probably added) and when one starts a line: CommonMark renderers turn such a line
   into raw HTML, so put the marker on its own line instead.

Following these two rules, `strip` returns the file byte for byte as it was before the markers went
in, including CRLF line endings and other HTML comments such as `AUTHOR TODO` notes.

### Commands

```bash
uv run manuscript ledger lint docs/manuscript/v0.3/paper1-just-dna-lite.md   # exit 1 on any error
uv run manuscript ledger lint --strict docs/manuscript/v0.3/*.md              # warnings fail too
uv run manuscript ledger strip docs/manuscript/v0.3/paper1-just-dna-lite.md  # writes paper1-just-dna-lite.clean.md beside it
uv run manuscript ledger strip docs/manuscript/v0.3/paper1-just-dna-lite.md --check   # exit 1 if the twin is missing or stale
uv run manuscript ledger report docs/manuscript/v0.3/paper1-just-dna-lite.md --html /tmp/heat.html
uv run manuscript ledger bump docs/manuscript/v0.3/paper1-just-dna-lite.md C3 --by robi:2026-10-12
```

- `report` prints one row per segment (id, rounds, reviewers, line, first words) and totals. With
  `--html` it also writes a single self-contained page: the document text with each segment shaded
  by its rounds (1 to 5+), a hover note naming the reviewers, and the table linked to each segment.
- `bump` adds one to `rounds` and appends `--by NAME[:DATE]` (date defaults to today). It rewrites
  that one opening marker and leaves every other byte alone.
- `strip`, `report` and `bump` refuse to run while lint reports an error, so a half-written marker can
  never leak into the twin.

### The clean twin

`strip` writes `<stem>.clean.md` next to the source (`--out` to put it elsewhere). It is the source
minus the markers and nothing else, so a downstream build (the LaTeX/tectonic pipeline lives outside
this repository) can read it without knowing the ledger exists. It is rewritten only when its content
changes, which keeps make-style builds from rebuilding for nothing.

The twin is derived, so `*.clean.md` is gitignored: regenerate it with `strip` right before a build.
If a build ever needs it from a clone of this repository, commit it deliberately and add
`strip --check` to that build so a stale copy fails instead of shipping.

Code: `src/just_dna_lite/manuscript/ledger.py`. Tests: `tests/test_manuscript_ledger.py`, which
inserts markers into the real paper text and checks the round trip.
