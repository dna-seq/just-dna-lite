# Audit of the Generation I Longevity Map module and its LongevityMap source

This folder produces the longevitymap part of Supplementary Table S14
(`docs/manuscript/v0.7/supplementary/S14_generation1_longevitymap_audit.md` and `.csv`). It was run on 2026-11-03.

Each v1.2.0 row is traced through six layers:
1. the source paper;
2. the HAGR LongevityMap record;
3. the Generation I import (`data/modules/just_longevitymap/longevitymap.sqlite`, table `variant`);
4. the Generation I curation (`data/longevity_map.tsv`);
5. the aggregation into one weight table (`allele_weights`);
6. the v1.2.0 port (`data/interim/registered_modules/just_dna_seq__longevitymap/`).

| Script (in `scripts/`) | Step |
|---|---|
| `lineage.py` | joins the layers and runs the mechanical checks |
| `fetch_refs.py`, `scrape_all.py` | look up Ensembl VEP and variation records; read the HAGR entry pages |
| `hagr_cmp.py`, `hagr_full.py` | compare the HAGR pages with the Generation I database |
| `ens_checks.py` | check gene labels and the named-variant → rsID translations |
| `build_inputs.py` | write the per-study inputs for the paper reading (`evidence/verify_*.csv`) |
| `consolidate.py` (+ `patch_cons.py`), `per_rsid.py` | merge paper verdicts with mechanical findings and attribute each to a layer |
| `gen_s14.py` (+ `patch_gen.py`) | write the supplementary markdown and CSV |

The paper-level verdicts (`evidence/paper_verification_*.csv`) were made by AI agents reading each paper: full text where
open access, otherwise the abstract. Each verdict carries a short quotation and is provisional until a human curator
checks it.

To reproduce, run the scripts with uv from a working directory that holds `longevity.csv`, the HAGR Build 3 download.
