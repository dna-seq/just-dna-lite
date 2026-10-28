# Manuscript figures

The master embeds these files; keep standalone copies for submission. Figure 2 is a reconstruction of selected fields from an actual report, not an interface screenshot. Its source extract is `../supplementary/S13_worked_report_row.json`; regenerate it with `uv run python scripts/manuscript_report_figure.py` from the repository root.

| Figure | File | Source | Status |
|---|---|---|---|
| 1 | figure-1-catalog-and-report.png | Captured at https://lite.just-dna.life/ on 2026-10-26 (see below) | (a) Module Catalog with Longevity Map selected; (b) Longevity Variants section of `report_20260927_120929.html` for Anton Kulaga's public genome, FOXO3 rs2802292 row expanded |
| 2 | figure-2-worked-annotation.png and .svg | S13 report extract; author-supplied annotation report | Called FOXO3 genotype, recorded annotation and five study records |
| 3 | figure-3-prs-ldl-trait-view.png | Captured at https://lite.just-dna.life/ on 2026-10-26 (see below) | PRS trait report for LDL cholesterol on Anton Kulaga's public genome |
| S1 | figure-2-module-domains.jpg | images/longevity_risks.jpg | Historical Generation I overview, retained in Supplementary S1 |

The author's separate PRS reports summarize a computational run of approximately 4,000 scores followed by selection and summary of interesting findings. They are not evidence that PRS calculation was manual. Their provenance is described in Supplementary S13; they do not supply the model-level metadata needed to reproduce every percentile.

## How Figures 1 and 3 were captured

Both are screenshots of the public demonstration, taken on 26 October 2026 with Playwright driving Google
Chrome at a device scale factor of 2, so the PNGs are twice the CSS pixel size. Nothing outside the public
genomes is in either figure: the sample list in the left panel, which on that day also held four other uploaded files, is
cropped out. v0.5's Figure 1 (`../../v0.5/figures/figure-1-annotation-interface.jpg`) showed
other people's sample names and is not used again.

- **Figure 1a**: `/registry` at a 1440 × 900 viewport; Details opened on Longevity Map, the card grid scrolled
  to the Lactose Tolerance row; cropped to the page header, the selected-module panel and the first card row.
  No module was installed.
- **Figure 1b**: `/api/report/anonymous/antonkulaga/report_20260927_120929.html` at a 1200-pixel-wide
  viewport, the FOXO3 rs2802292 row opened with its `+` control and the floating back-to-top button hidden.
  Two clips (the section's summary cards; the table from its header to the end of the second linked study)
  are stacked under the panel.
- **Figure 3**: the Polygenic Risk Scores tab for Anton Kulaga's public genome, trait "low density lipoprotein
  cholesterol measurement" found with the trait search, selected with *Select Filtered* and computed with
  *Compute PRS for Selected Traits* (DuckDB engine, harmonized scores included, absent-locus recovery off);
  the result row then selected in *PRS Results*. The demo scored all 101 models in the background (about an
  hour, 15:00 to 15:39 UTC). The report card renders in an iframe; the clip is that card down to the start of
  its "How to read Quality" note.

The panels were assembled with Pillow (labels in DejaVu Sans Bold); the capture and assembly scripts are not
kept in the repository.
