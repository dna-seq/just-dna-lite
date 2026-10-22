# Manuscript figures

The master embeds these files; keep standalone copies for submission. Figure 2 is a reconstruction of selected fields from an actual report, not an interface screenshot. Its source extract is `../supplementary/S13_worked_report_row.json`; regenerate it with `uv run python scripts/manuscript_report_figure.py` from the repository root.

| Figure | File | Source | Status |
|---|---|---|---|
| 1 | figure-1-annotation-interface.jpg | images/just_dna_lite_annotations.jpg | Existing annotation interface screenshot |
| 2 | figure-2-worked-annotation.png and .svg | S13 report extract; author-supplied annotation report | Called FOXO3 genotype, recorded annotation and five study records |
| 3 | figure-3-prs-trait-view.jpg | images/just_prs_trait_consensus.jpg | Existing draft illustration; requires replacement because it displays an absolute-risk value for intelligence and inconsistent quality labels |
| S1 | figure-2-module-domains.jpg | images/longevity_risks.jpg | Historical Generation I overview, retained in Supplementary S1 |

The author's separate PRS reports summarize a computational run of approximately 4,000 scores followed by selection and summary of interesting findings. They are not evidence that PRS calculation was manual. Their provenance is described in Supplementary S13; they do not supply the model-level metadata needed to reproduce every percentile.
