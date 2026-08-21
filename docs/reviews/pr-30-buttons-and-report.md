# Review — PR #30: Completed-analysis actions & report redesign

**Author:** ksuhaster · **Branch:** `codex/buttons-and-report` · **Base:** `main`
**Verdict: merged**, after four fixes pushed onto the branch. One of them was merge-blocking.

Two independent changes in one PR:

1. **webui** — the "Start Analysis" button stops pretending to be a status light and becomes a
   pair of real actions once a run finishes (open the report / regenerate), plus focus-and-preview
   plumbing from a run card to its output parquet.
2. **reports** — a full redesign of `longevity_report.html.j2`, a derived report title and
   filename, and four prompt-prefill "AI explain" links on every rsID row.

Both are good work. The report redesign in particular is a real improvement: the old template's
`collapseExpandAll` heuristic (pick expandable rows by `children.length > 3`) was a booby trap that
the CLAUDE.md had to document in prose, and replacing it with an explicit `data-preview-row`
attribute is the right call. Same for routing the report's identity through the module's curated
`report_title` instead of a hardcoded "Longevity Report" on a report that may contain no longevity
module at all.

---

## 1. Fixed: the rename breaks `.ci/verify_annotation.py`

**Correction to an earlier draft of this review:** I first called this merge-blocking. It is not.
The job that runs this script — `integration` in `nix.yml` — is gated on
`github.event_name == 'schedule' || 'workflow_dispatch'`, so it does not run on push or PR. The
break would have surfaced in the Monday 06:00 UTC scheduled run, not at merge time. Still a real
break, still worth fixing before merge; just not a gate.

`report_assets.py` moved the report filename from `longevity_report_{ts}.html` to
`{stem}_{ts}.html`. Three consumers were updated (`cli_annotate`, the webui's report sort, the
`app.py` docstring). One was not:

```python
# .ci/verify_annotation.py:31 — before
reports = list((SAMPLE_DIR / "reports").glob("longevity_report_*.html"))
assert len(reports) >= 1, "No longevity_report_*.html found"
```

`nix.yml`'s `integration` job annotates `antku_small.vcf` with `-m longevitymap` and then runs that
script. Under this PR the run writes `longevity_variants_<ts>.html`, the glob matches nothing, and
the assert fires. Two things hid it: that job only runs on the weekly schedule, and all three
workflows on this branch were sitting at `action_required` (first-time-contributor approval), so
nothing had run against these commits at all. `mergeStateStatus` read `UNSTABLE` for the second
reason, which is easy to mistake for "flaky, ignore it".

**Fixed** by globbing `*.html` and picking the newest by mtime, which is also what `cli_annotate`
now does. The general rule, now written into CLAUDE.md: once a filename is derived, nothing may
glob for a fixed name.

> Worth internalising: a rename is not done when the tests pass. It is done when you have grepped
> the *whole repo* — `.ci/`, `.github/`, `docs/` included — for every spelling of the old name.
> `grep -rn longevity_report --include='*.py' --include='*.yml' .` would have taken five seconds.

## 2. Fixed: the AI icons were inlined once per row (~1 MB of a 2 MB report)

`ai_assistant_icon()` emitted the assistant's full SVG path data inside every link, so a report with
206 variants carried 824 copies of four glyphs. Measured on a real run
(`NG112J7C24`, longevitymap only):

| | main | PR as submitted | PR after fix |
|---|---|---|---|
| single-module report | 0.58 MB | 3.04 MB | **2.13 MB** |
| all-modules report | — | 3.84 MB | **2.70 MB** |

**Fixed** by defining each glyph once in a `<symbol>` block emitted at the top of `<body>` and
referencing it per row with `<use href="#ai-icon-…">`. Structurally verified on the regenerated
reports: every `<use>` resolves, no duplicate element ids, `colspan` still matches the header, all
`aria-controls` targets exist.

The remaining ~1.0 MB is the four URLs themselves: the same ~1.2 kB prompt is percent-encoded once
per assistant per row. That is inherent to using real `<a href>` links (which is the right choice —
they survive middle-click and work without JS), so it stays, but it is now documented as the
report's dominant cost. If it ever needs to come down, the move is to store the prompt once per row
in a `data-` attribute and build the URL on click. `prs-ui` also caps its prompts per provider
(`PRS_AI_CHATGPT_MAX_CHARS`, default 3000); our longest measured URL is 2036 characters, so we are
inside that envelope today, but a variant with a very long study list is the case to watch.

## 3. Fixed: the template's markup↔JS contract comment was deleted, not replaced

The old template carried a comment block stating the invariants the inline JS imposes on the
markup, and CLAUDE.md restated them. The redesign changed all of those invariants and removed the
comment, leaving CLAUDE.md actively wrong (it still described `collapseExpandAll` and a
`children.length > 3` heuristic that no longer exist, and `colspan` 8 where it is now 9).

**Fixed** — the comment is back above `variant_rows`, stating the four current constraints, and the
CLAUDE.md section is rewritten to match. This matters more than it looks: those invariants are
exactly the kind that a reasonable-looking edit silently breaks, and nothing fails loudly when it
happens.

## 4. Fixed: the ten-row preview limit was written down in five places

`TABLE_PREVIEW_ROWS = 10` in the JS, and the literal `10` in four Jinja guards plus the toolbar
text. Change one, and the table pre-collapses at a different row than the toggle restores to — with
no error anywhere.

**Fixed** — `report_logic.TABLE_PREVIEW_ROWS` is now the single definition, passed into the
template as `preview_row_limit` and read by both the markup and the JS constant. The tests derive
their expectations from it too, so `range(TABLE_PREVIEW_ROWS + 2)` replaces a hardcoded `range(12)`.

## 5. Added: a plain-language note about what the AI buttons send

The report gained four buttons per row that put the reader's genotype at that position into a URL
and hand it to a third party. That is a genuinely useful feature and it is per-click, but a
genomics report should say so in its own words rather than leave the reader to infer it from a
hostname. One short paragraph now sits with the other reading instructions in the intro card:

> The buttons in the **AI explain** column open an external assistant with a prompt about that one
> row already filled in. That prompt contains your genotype at that position, so it leaves this
> file and goes to whichever assistant you pick. It is sent only when you click a button; opening
> this report sends nothing anywhere.

---

## Things I checked and found correct

- **`_output_path_for_run` cannot land on an older run's parquet.** It matches on run id *and* on
  the module set recorded for that run, which is the right belt-and-braces given that every parquet
  in `output_files` inherits the same `annotations_mat` run id.
- **`latest_report_url` correctly hides itself for a report-less run.** Every entry in
  `report_files` carries the *report asset's* run id, so an Ensembl-only latest run leaves the id
  mismatched and the button falls back to the disabled "Analysis completed" state. Nice.
- **Sorting `report_files` by `materialized_at` rather than by name** is not cosmetic — it is
  required now that names no longer share a sortable prefix. Good catch by the author.
- **`rerun_with_same_modules` now filters against `available_modules`** and restores the Ensembl
  toggle from the run record, so a rerun of an Ensembl-only run no longer silently drops to nothing.
  `include_ensembl` is threaded through both the optimistic run dict and `_load_runs`.
- **A latent `NameError` was fixed in passing.** `PRSState.compute_selected_prs` referenced an
  undefined `vcf_path` on the falsy branch of `self.prs_initialized_for_file or vcf_path`; it now
  reads `self.prs_genotypes_path`. Unrelated to this PR's subject, but correct.
- **All nine authored axes still reach the HTML.** `test_a_populated_0_5_axis_reaches_the_html`
  passes against the new template, so the render-if-present contract survived the redesign.
- **`colspan="9"` matches the nine `<th>`**, on all 263 detail rows of the all-modules report.

## Non-blocking nits, left as they are

- `report_assets.py` derives the filename stem from `config.modules` (what was *requested*) while
  the heading comes from `available_modules` (what was actually *found on disk*). A run that asks
  for one module whose parquet is missing gets a file named after that module and a generic
  heading. Timestamped filenames make this harmless, and closing it properly means
  `generate_longevity_report` returning the modules it used.
- `datetime.now().astimezone()` in the timestamp is a no-op for the `%Y%m%d_%H%M%S` format.
- `id=rx.cond(is_focused, "focused-annotated-file", "")` puts `id=""` on every output card that is
  not focused. Browsers tolerate it and `getElementById("")` returns null, so nothing misbehaves,
  but Reflex has no way to omit an attribute conditionally and this is the cost.

## Verification performed

- Full suite in a clean worktree: **498 passed, 9 skipped** after the fixes. The two initial failures
  (`test_agent_smoke`, `test_v1_port::test_longevitymap_reconstructs_every_source_rsid`) were the
  worktree missing `.env`; both pass once it is present, and both pass on `main` under the same
  conditions.
- Reports regenerated end-to-end from real annotated parquets (single-module and all-modules) and
  checked structurally, not just for size.
- Every changed Reflex component constructed, plus the whole `annotate_page()` tree (225 kB of
  rendered component), to catch API errors that only surface at compile time.
