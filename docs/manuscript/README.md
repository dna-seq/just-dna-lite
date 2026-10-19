# Manuscript tools

`uv run manuscript` holds the tools for the manuscript sources in this folder: the revision ledger
(`manuscript ledger …`), the PDF build (`manuscript build …`) and Supplementary Tables S4
(`manuscript s4 …`) and S5 (`manuscript s5 …`). The Markdown files are the master;
the LaTeX and the PDF are derived from them and never edited by hand.

Each `vX.Y/` folder is one round. `v0.3/` holds Paper 1 as Robi Tacutu reviewed it (the Google Doc,
his suggestions not applied) and stays frozen; `v0.4/` holds the revision that answers the review,
with its supplementary tables. A file that has not changed since its round stays in that round's folder.

## Revision ledger

The manuscript sources (`v0.4/paper1-just-dna-lite.md`, `v0.3/paper2-just-module-creator.md`) record,
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
uv run manuscript ledger lint docs/manuscript/v0.4/paper1-just-dna-lite.md   # exit 1 on any error
uv run manuscript ledger lint --strict docs/manuscript/v0.3/*.md              # warnings fail too
uv run manuscript ledger strip docs/manuscript/v0.4/paper1-just-dna-lite.md  # writes paper1-just-dna-lite.clean.md beside it
uv run manuscript ledger strip docs/manuscript/v0.4/paper1-just-dna-lite.md --check   # exit 1 if the twin is missing or stale
uv run manuscript ledger report docs/manuscript/v0.4/paper1-just-dna-lite.md --html /tmp/heat.html
uv run manuscript ledger bump docs/manuscript/v0.4/paper1-just-dna-lite.md C3 --by robi:2026-10-12
```

- `report` prints one row per segment (id, rounds, reviewers, line, first words) and totals. With
  `--html` it also writes a single self-contained page: the document text with each segment shaded
  by its rounds (1 to 5+), a hover note naming the reviewers, and the table linked to each segment.
- **Blind spots.** The ledger exists to find text nobody has looked at, not to gate edits. Every
  prose line (paragraph, list item, table row; headings, rulers and comment-only lines excluded) that
  no segment overlaps is a blind spot. Totals always count `paragraphs` and `blind spots`;
  `report --blind` lists them by line, and the heat map lists them and leaves them unshaded. A whole
  paragraph a reviewer touched carries its own segment (Robi's accepted v0.3 suggestions are `R1` to
  `R26`), so a paragraph he read but left alone still counts as a blind spot.
- `bump` adds one to `rounds` and appends `--by NAME[:DATE]` (date defaults to today). It rewrites
  that one opening marker and leaves every other byte alone.
- `strip`, `report` and `bump` refuse to run while lint reports an error, so a half-written marker can
  never leak into the twin.

### The clean twin

`strip` writes `<stem>.clean.md` next to the source (`--out` to put it elsewhere). It is the source
minus the markers and nothing else, so a build (`manuscript build` below, or any other) can read it
without knowing the ledger exists. It is rewritten only when its content
changes, which keeps make-style builds from rebuilding for nothing.

The twin is derived, so `*.clean.md` is gitignored: regenerate it with `strip` right before a build.
If a build ever needs it from a clone of this repository, commit it deliberately and add
`strip --check` to that build so a stale copy fails instead of shipping.

Code: `src/just_dna_lite/manuscript/ledger.py`. Tests: `tests/test_manuscript_ledger.py`, which
inserts markers into the real paper text and checks the round trip.

## Building the PDF

```bash
uv sync                                                                          # dev group: pypandoc-binary, tecto
uv run manuscript build docs/manuscript/v0.4/paper1-just-dna-lite.md            # → docs/manuscript/v0.4/build/
uv run manuscript build docs/manuscript/v0.4/paper1-just-dna-lite.md --no-pdf   # stop at the LaTeX
uv run manuscript build PATH --out /tmp/paper --template venue.latex            # elsewhere, venue template
```

The chain is: ledger strip → `<stem>.clean.md` → pandoc → `<stem>.tex` → tectonic → `<stem>.pdf`, all
in `build/` beside the source (gitignored) unless `--out` names another directory. The build stops
with the lint errors if the ledger markers are broken, before writing anything.

- **Layout.** The paper's single `#` heading becomes the title and `##` headings become sections
  (pandoc's `--shift-heading-level-by=-1`). Pandoc's default LaTeX article is used for now.
- **Venue template.** `--template FILE` takes a pandoc LaTeX template (start from `pandoc -D latex`),
  which is where a journal's class (Bioinformatics/OUP and the like) goes when we pick one.
- **Fonts.** The default is DejaVu Serif and DejaVu Sans Mono from tectonic's bundle. Pandoc's
  default, Latin Modern, has no ≥, ↔ or superscript minus, and XeTeX leaves a blank for a missing
  glyph with only a log line: paper 1 lost eight characters that way. The build prints a warning for
  every character still missing, so check its output, not only the PDF.
- **Tectonic.** The `tecto` wheel's binary needs a recent glibc. On an older host, point
  `MANUSCRIPT_TECTONIC` at the static musllinux build of the same release. Set `TECTONIC_CACHE_DIR`
  (for example `/data/tectonic-cache`) so the TeX bundle is not cached under `~/.cache`. Both can go
  in `.env` (see `.env.template`); an exported value wins. The first build downloads the bundle and
  takes a few minutes; later builds take seconds.
- **No stale PDF.** The previous PDF is deleted before tectonic runs, so a failed render leaves the
  LaTeX and a reported error, never an old PDF that looks current. `--no-pdf` keeps an existing PDF but
  says when it is older than the LaTeX just written.
- **Page count.** The build reports the pages typeset (from the TeX log). just-module-creator's
  `page_budget.py` was not ported: it projects a page count from LaTeX source against a committed
  anchor PDF because that host could not render. Here the Markdown is the master and the PDF builds,
  so the count is measured directly. It is the count for pandoc's default layout, not a venue's.

Code: `src/just_dna_lite/manuscript/build.py`, `cli.py`. Tests: `tests/test_manuscript_build.py`
(the real render is skipped, with the reason, when no tectonic resolves or `TECTONIC_CACHE_DIR` is
unset).

## Supplementary Table S4 (module sources)

S4 lists, for every module the project publishes in the registry, its version, publication time,
artifact digest, curator type, source databases with their release, and every paper its rows cite. The
registry is a live catalogue, so the table is a snapshot with a recorded cutoff. Two steps:

```bash
uv run manuscript s4 snapshot /data/s4-work                    # read-only: list, download, record the UTC time
uv run manuscript s4 render /data/s4-work -o docs/manuscript/v0.4/supplementary --fetch-bibliography
uv run manuscript s4 render data/interim/v1_port -o /tmp/s4 --as-of 2026-10-10   # local builds, no registry
```

- **`snapshot`** uses `default_registry_store()` (or `--store KEY`) and `--namespace` (default
  `just-dna-seq`). It sends no token and makes public reads only: the namespace listing, each module's
  versions, and a verified download of the latest non-yanked version with its build logs. It also reads
  the legacy HuggingFace mirror's manifests (`--no-mirror` skips that). It writes `snapshot.json` beside
  the downloads; keep the work directory outside the repo.
- **`render`** reads every value from the module files (`manifest.json`, `sources.parquet`,
  `studies.parquet`, the lead table, `literature.parquet`, the build log) and refuses when a directory's
  version or digest disagrees with `snapshot.json`. It writes `S4_module_sources.md`,
  `S4_module_sources.csv` (one row per module) and `S4_module_citations.csv` (one row per module and
  PMID, including the database-derived panels' ClinVar links). `S4_registry_snapshot.json` is the
  committed copy of the snapshot the current table was rendered from.
- **Curator type** comes from provenance, never a guess: a database on the licence sidecar's
  `annotation` layer makes it *Database-derived*; else manifest method `expert-curated` makes it
  *Expert*; an AI-only authorship with a stated (non-default) method makes it *AI-generated*; anything
  else is *Undetermined*. A spec that states no `defaults:` block gets the format's `ai-module-creator`
  / `literature-review`, which is not a statement (the published pharmgkb 1.1.0 is such a case; its
  build now states `just-dna-seq` / `clinpgx-aggregate`). The `authorship_kinds` column copies the
  manifests: the published cancer, cardio, pathogenic and pharmacogenomics modules say `ai;human`, a
  default the port scripts wrote. They are Generation I modules designed by Olga Borysova and coded by
  Alex (Alexey) Karmazin and Maria Koval (`v1_port.sources.GENERATION_I_PANEL_AUTHORSHIP`); S4 shows that once
  they are republished and the snapshot is retaken.
- **Curation notes** are the one hand-written part: `S4_curation.yaml`, beside the output, says how each
  Generation I literature module chose its variants, every note citing keys of its own `references`
  map. `render` prints them as each module's *Curation* line plus a References section, and refuses a
  note for a module not in the render or a cited key that is not defined. The paper's text points to S4
  for module provenance instead of citing per module.
- **First author and year** are not in any module file. `--fetch-bibliography` asks PubMed esummary for
  the literature-curated modules' PMIDs not yet in `S4_bibliography.json` and caches them there; the
  request carries no contact email and no NCBI key. Without the flag the render is offline.

Code: `src/just_dna_lite/manuscript/s4.py`, `s4_snapshot.py`, `cli.py`. Tests:
`tests/test_manuscript_s4.py` (offline, on `data/interim/v1_port/`; skipped with the reason when absent).

## Supplementary Table S5 (PGS Catalog coverage of just-prs)

S5 says, for every scoring file in one PGS Catalog release, how much of it just-prs scores as the
Catalog specifies it, how much it approximates, how much it drops, and which files it cannot score at
all. Section 3.2 of Paper 1 quotes its counts. Two steps:

```bash
uv run manuscript s5 scan /data/just-dna-cache/s5/work --cache-dir /data/just-dna-cache/s5/GRCh38
uv run manuscript s5 render /data/just-dna-cache/s5/work -o docs/manuscript/v0.4/supplementary
```

- **`scan`** records the release from the Catalog REST API (`/rest/info`, `/rest/score/all`) with the
  UTC listing time in `s5_catalog.json`, downloads every harmonized scoring file of `--build`
  (default GRCh38, about 78 GB) into `--cache-dir`, and reads each one in full: no sampling, no size
  cut-off. One JSON line per file goes to `s5_measures.jsonl`, so an interrupted scan resumes; a
  resumed scan refuses if the Catalog has released since. Keep both directories outside the repo.
- **`render`** is offline. It sorts every row of every file into one class (no position;
  non-nucleotide effect allele; effect allele equal to the other allele; scored), weighs each class by
  absolute weight, and classifies the file by the rules in `s5.RULES`, each naming the just-prs code it
  mirrors. Every rule is read from the file's columns or the Catalog's score metadata
  (`variants_interactions`, `weight_type`); none is a hand-kept list of IDs. `--threshold` (default
  0.10) is the share of absolute weight that makes a file approximated; the table also gives the
  counts at 1%, 10%, 25%, 50% and any nonzero share. It writes `S5_pgs_coverage.md`,
  `S5_pgs_coverage.csv` (one row per PGS ID) and `S5_unplaceable_weight_histogram.svg`/`.png`
  (matplotlib, in the dev group).

Code: `src/just_dna_lite/manuscript/s5.py`, `cli.py`. Tests: `tests/test_manuscript_s5.py` (offline,
on real scoring files in `tests/data/manuscript/s5/`).

## Pre-submission checks and journal choice

The [manuscript-skills](https://github.com/dna-seq/manuscript-skills) plugin
(`claude plugin install manuscript-skills@dna-seq`) reviews and adapts the manuscript.
`manuscript-integrity-check` checks a draft against what journal desks and preprint servers reject:
references that do not resolve, point to a different work or were retracted, chatbot leftovers and TODOs,
missing declarations and venue length limits. `manuscript-journal-select` compares venues, and
`manuscript-journal-adapt` turns the chosen journal's rules into edits and statements, under a guard that
checks no number, citation or hedge changed. Venue choice and status are in `manuscript_journal_strategy.md`
("Venues, October 2026"). The plugin's policy data was read on 2026-10-15; re-check the venue's live page
before submission.
