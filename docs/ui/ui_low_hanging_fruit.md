# UI review: findings and a low-hanging fruit set

Second pass after [ui_analysis.md](ui_analysis.md). Reviewed live at `localhost:3000` with
`antonkulaga.vcf` at desktop width and in a 390 x 844 emulated viewport, then cross-checked
against `webui/src/webui/pages/annotate.py`, `components/layout.py`, `state.py` and `grid.py`.
No code was changed for this review. Date: 2026-09-20.

## Where the first review holds up

The structural points stand. The two fixed-height panels in `two_column_layout` require
320 px + 500 px before padding, so at phone width the nav is clipped and the workspace is off
screen. The Add Sample form is permanent sidebar furniture. Reports are listed as filenames.
The PRS tab leads with engine and cache controls.

What I would change is the order of work. Most of the visible pain is fixable in a few dozen
lines per item, and doing those first shows what a larger redesign actually needs to solve.
The "sample overview plus Results regrouping" proposal is worth doing, but after the list below.

## Findings the first review did not catch

### Report metadata is wrong, not only ugly

All four reports for Anton show the same run id (`bdd4d5d5`) and the same date
(`2026-08-31 03:47:45`). In `state.py` (around line 2465) every report is stamped with the run
id of the *latest* report materialization and dated by file mtime, then the list is sorted by
that mtime. With identical mtimes the order is arbitrary and three of four run badges point at
the wrong run. The real timestamp is already in the filename (`report_20260820_043216.html`)
and the real title is already in the HTML (`<title>` in `longevity_report.html.j2`, line 8).

### Report links point at another project's domain

`just_dna_pipelines.runtime.load_env` calls `find_dotenv(usecwd=True)`, which walks up from the
working directory. This checkout has no `.env`, so it finds `~/sources/.env` (from the
sugar-sugar project), which sets `DEPLOY_URL=https://sugar-sugar.study`. Every
`/api/report/...` and download link is then built on that host. The fix is to stop the search
at the project root, or to load only `<repo>/.env`.

### Six installed catalog modules are missing from Analysis Tools

The module grid shows the 10 HuggingFace modules while the last run reports 16. The gitignored
working copy `data/interim/modules.yaml` has been rewritten at some point: the source path is
`/home/author-A/sources/just-dna-lite/data/interim/registered_modules`, metadata keys are
`author-A__*`, and the public genome labels read "Anonymous Author" and "Anonymous Contributor
F". Those labels are what the sidebar shows. This is a local data problem rather than a UI
defect, but any judgement of the module grid or the "Try a public genome" box made against this
state is judging broken input. Fix the path (or delete the working copy and reinstall the six
modules) before evaluating those screens.

### Delete is one unconfirmed click

The trash icon sits about 40 px from the row you click to select a sample, and there is no
confirmation. `delete_file` (`state.py` around line 2619) only unlinks the input VCF; the
normalized parquet, annotations and reports stay on disk.

### The right-panel tabs are not tabs

They are `div`s with `on_click` (`_tab_item` in `annotate.py`). They do not appear in the
accessibility tree at all and cannot be reached by keyboard. The drag-to-reorder handlers are
attached, but `role`, `tabIndex` and `aria-selected` are not.

### The tissue placeholder is saved as data

The tissue `<select>` defaults to the literal string "Sample tissue", and the upload path writes
it through (`state.py` lines 158, 467, 807, 841). Anton's metadata card reads
`Tissue: Sample tissue`.

### Smaller things seen live

- Tab strip overflows at 1024 px: the sixth item is clipped, and the Input badge reads
  `4257537 rows` unformatted.
- `grid.py` line 315 publishes `offset=0 +500 rows loaded=500 / 669 4ms (replace)` as
  `lf_grid_stats`, so the debug line shows on every grid (Input, output preview, PRS traits).
- The latest-run card prints `2026-08-20T04:30:56.115288`.
- Start Analysis sits below ten module cards and is not visible without scrolling.
- Catalog card titles are cut at one line and descriptions are cut mid-sentence with no
  ellipsis. The Installed list shows `antonkulaga__aggression_anger_snps` style keys.
- The sample status "uploaded" actually means "normalized, not yet annotated".
- The welcome screen shows two red disclaimers (topbar label plus message box).

## Low-hanging fruit

Each item is a contained change, mostly in `annotate.py` and `state.py`, roughly an hour or two
of work. Ordered by value.

1. **Default tab by sample state** (`state.py` line 2235, `commit_selected_file`). Every
   selection currently lands on Input, a 4.2 million row grid. If reports exist open Reports;
   else if the sample is normalized open Analysis Tools; else Input. About five lines. This
   delivers most of what the "sample overview" proposal was for.

2. **Readable report cards** (`report_file_card`, and the report scan in `state.py`). Title from
   `<title>` or from `report_title_for_modules` via the run manifest; date parsed from the
   filename stem; filename demoted to grey secondary text; sort newest first; a "Latest" label
   on the first card. Drop the run badge unless it is genuinely per file. This also fixes the
   wrong-metadata bug above.

3. **Keep Start Analysis in view** (`new_analysis_section`). `position: sticky; bottom: 0` on
   the run row inside the scrolling right column, with the selected-module count beside it.

4. **Tab strip** (`_tab_item`, `_right_panel_tab_menu`). Rename "Polygenic Risk Scores" to
   "PRS" with the full name as `title`; format the row badge as `4.26M`; `flexWrap: wrap` on
   the menu; add `role="tab"`, `tab_index=0` and `aria-selected` to each item.

5. **Remove the debug string** (`grid.py` line 315). Publish "Showing 500 of 669" and keep the
   detailed form in the existing `print`.

6. **Format timestamps.** One helper applied to the latest-run card, the run timeline and the
   sample list. Relative time ("31 days ago") with the absolute value as `title` works well.

7. **Collapse Add Sample** behind an "Add sample" button once at least one sample exists
   (`file_column_content`). One boolean state var and an `rx.cond`. The public-genome hint
   moves inside it. This is also the first step toward a phone layout.

8. **Confirm delete.** Two-step button or `rx.alert_dialog`, and state what is removed. Decide
   whether outputs should go with the input file.

9. **Fix `load_env`** so it does not climb above the project root. *Done 2026-09-20:*
   `runtime.load_env` now resolves the workspace root (env var, then the checkout this package
   lives in, then the cwd's enclosing workspace) and loads `<root>/.env`, falling back to
   `<root>/.env.template` on a clean clone. The four bare `load_dotenv()` call sites were
   switched to it. Pinned by `tests/test_load_env_bounded.py`.

10. **Tissue sentinel.** Treat "Sample tissue" as empty on write and mark the first `<option>`
    `disabled`.

11. **Catalog cards** (`pages/registry.py`). `-webkit-line-clamp: 2` on titles and `3` on
    descriptions with an ellipsis; display titles rather than internal keys in the Installed
    list; render "Installed" as a label, not a button that looks disabled.

12. **Sample status wording.** "Not analyzed" and "Annotated" instead of "uploaded" and
    "completed".

13. **Header.** Hide the GitHub corner below about 900 px (there is already a media query
    block in `github_corner`) and keep only one red disclaimer on the welcome screen.

## The cheap first step toward mobile

Not a redesign. One afternoon in `layout.py`: a media query that switches `#two-column-layout`
to `flexDirection: column` below about 900 px, removes the `calc(100vh - 104px)` column heights
and the `overflow: hidden` on the template so the page scrolls normally, and drops the left
`minWidth`. With items 4 and 7 above this gives a usable phone layout (sample list, then
workspace) without touching state.

That is the point at which the fuller proposal in `ui_analysis.md` (sample selector, compact
header, card-based results) becomes worth designing, because by then it is clear which tables
and controls actually break on a small screen.

## Mobile: what was done and what to cut (2026-09-20, after the first stacked test)

The stacked layout above is in (`layout.py`, `_RESPONSIVE_CSS`, breakpoint 900 px). Testing it
at 390 px showed that stacking alone is not enough, because the workspace sits *below* the sample
list and a tap on a sample changes nothing on screen. The state now knows the viewport
(`UploadState.viewport_width`, reported by `rx.call_script("window.innerWidth")` from the page
`on_load`; `is_mobile` is a computed var) and a handful of defaults key on it. Desktop behaviour
is unchanged by construction: `viewport_width == 0` or anything above the breakpoint is desktop.

Phone-only defaults in place:

- Add Sample form and the public-genome box fold behind one "Add sample" button once the library
  has a sample (`show_add_sample_form`).
- A "Tap a sample to open its results below" line sits above the list until something is selected,
  and the workspace banner says "Tap a sample above" instead of "Start in the left panel".
- On tap the list folds to the selected sample with a "Show all N samples" row under it
  (`visible_sample_files`, `toggle_samples_list`), the tab lands on Reports when the sample has
  any and on Analysis Tools otherwise (`_mobile_default_tab`), and the page scrolls so the
  selected sample and the workspace are on screen together.
- The Input tab keeps the quality-filter summary and hides the 4M-row grid behind "Show the
  variant table" (`show_vcf_preview_table`).
- Panels clip horizontal overflow so a wide MUI grid scrolls inside its box rather than widening
  the page (PRS was 441 px wide on a 390 px screen before this).

What each tab looks like at 390 px now, and what I would cut there. "Cut" means hide on the phone
by default behind a disclosure, not remove; every item stays reachable.

**Sample list.** Fine once folded. The trash icon next to every row is the one thing I would
still hide on the phone; deletion belongs behind the row's Edit/details view, not one tap away
in a 40 px target.

**Reports.** Usable and the right landing tab. Filenames wrap onto three lines and the run badge
plus materialization date add two more rows per card. Cut: the run badge, the size in KB, and
the "report" label; keep title, date, View. This is the same change as item 2 in the desktop
list and matters more here.

**Analysis Tools.** The module grid is 3,937 px tall for 16 modules because every card renders its
full description (several are whole paragraphs from the registry) plus a source badge showing a
local absolute path. Cut: clamp descriptions to two lines with tap-to-expand, drop the source
badge on the phone (or reduce it to "local" / "HuggingFace"), and make Start Analysis sticky at
the bottom of the viewport. Without the sticky button a user scrolls four screens to find the
one action the tab exists for.

**Annotated Files.** The weakest screen. Parquet names like
`antonkulaga__aggression_anger_snps_weights.parquet` break across three lines, the "Produced by"
line runs underneath the eye and download buttons, and there are 16 cards before the preview
grid. This tab is for people who want the raw tables; on a phone almost nobody does. Cut: on the
phone show one row per module (module title, file type label, download), no filenames, no run
badge, no materialization date, and fold the whole tab under a single "Data files (16)"
disclosure. Alternatively demote it out of the tab strip on the phone entirely and reach it from
the Reports tab footer.

**PRS.** The prs-ui workbench brings engine selector, "Include harmonized scores", "Recover absent
loci", "Refresh reference/audit cache", the grid debug line, and the 1000G cohort explainer
before the trait table. On a phone that is two screens of controls before the first trait. Cut:
everything above the By Trait / By PRS tabs except the sample row, and everything between those
tabs and the trait table except the search box; move the four controls into an "Advanced"
disclosure. These live in `prs_workbench_mode_panel` (prs-ui), so this is either an upstream
option or a CSS override in `PRS_ALIGNMENT_CSS` keyed on the breakpoint. The trait grid itself is
readable at one column (Trait) and should hide N Models and EFO id on the phone.

**Tab strip.** Five tabs wrap to three rows (157 px). Two-per-row is the fallback in place. Better
on the phone: a horizontally scrolling single row with short labels (Input, PRS, Files, Reports,
Analyze), which needs the label text to be responsive rather than only the layout.

**Header.** Wraps to two rows and is sticky, so it costs about 100 px of every screen. Cut: the
"Medical Disclaimer / RUO" label (the welcome message already carries the disclaimer, and it can
move to the FAQ nav item on the phone), and make the header scroll away rather than stick, or
stick only the nav row.

**Welcome page.** The sequencing journey diagram and the "Inside Just-DNA-Lite" schematic are
desktop artwork; at 390 px their labels are unreadable. Cut both on the phone and keep the two
sentences above them plus the Core Philosophy list.

**What can be done differently on the phone rather than trimmed.** The list above is the
"disclosure" approach: same components, phone defaults. The alternative is to treat the phone as
a two-screen app: screen one is the sample list (with Add sample), screen two is one sample with
Reports first, PRS second, and everything else under "More". Both screens already exist as
components (`file_column_content`, `right_panel_run_view`); what changes is that on the phone
only one is mounted at a time and a back button swaps them, instead of stacking both. That is a
day of work on top of what is here and would remove the scroll-to-workspace choreography
entirely. I would do the disclosure cuts first because each one is also a desktop improvement,
then decide on the two-screen model with real phone use.

## Medium items to leave for later

- Merge Annotated Files and Reports into one Results tab.
- Hide the PRS engine and cache controls. They come from prs-ui's `prs_workbench_mode_panel`,
  so this is either an upstream change or a CSS override in `PRS_ALIGNMENT_CSS`.
- Make the "Module Manager" box in the welcome diagram conditional on
  `MODULE_CREATOR_ENABLED`; it is drawn even when the page does not exist.
- A proper sample overview page.

## How to reproduce the review

Start the app with `uv run start`, select `antonkulaga` in the left panel, and step through
the five tabs. For the phone view use Chrome DevTools device emulation at 390 x 844. The
report-link domain can be checked with a DOM query for `a[href*="/api/report/"]`; the
missing-module count by comparing `#module-cards-grid` children against the "N modules" label
on the latest-run card.
