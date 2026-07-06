# Generation-I Module Parity Plan

This document maps every Generation-I (Gen I) Just-DNA-Seq annotation module to its port status in
the current (Gen II) `just-dna-format`, and lays out what's needed to reach full feature parity.

Gen-I modules were OakVar *postaggregators*, one `just_*` repo per module in the
[`dna-seq`](https://github.com/dna-seq) GitHub org, each shipping a small curated SQLite/TSV/txt data
file. Stage 1 (see `just_dna_pipelines.v1_port` and `data/interim/v1_port/`) reproducibly ports the
variant-backed modules from that canonical source; this plan covers the rest.

## Status overview

| Gen-I repo | Module | Data | Ported to `v1_port/`? | On HuggingFace? | Parity |
|---|---|---|---|---|---|
| `just_coronary` | coronary | `coronary.sqlite` | ✅ compiled | ✅ | **full** — 27/27 rsids match HF |
| `just_vo2max` | vo2max | `vo2max.sqlite` | ✅ compiled | ✅ | **full** — 13/13 match HF |
| `just_lipidmetabolism` | lipidmetabolism | `lipid_metabolism.sqlite` | ✅ compiled | ✅ | **full** — 15/15 match HF |
| `just_longevitymap` | longevitymap | `longevitymap.sqlite` | ✅ compiled | ✅ | **near-full** — 518/528 rsids (10 het-only rsids unresolved, below) |
| `just_thrombophilia` | thrombophilia | `thrombophilia.sqlite` | ✅ compiled | ✅ (published 2026-07) | **full** — newly published to the collection |
| `just_superhuman` | superhuman | `superhuman.sqlite` | ✅ compiled (subset) | ✅ (marketplace v1.0.0) | **partial** — v1 grounded on the 2 in-source verified PMIDs; full curation + refresh = v2 |
| `just_lnewco` | lnewco (APOE) | `metabolic_genotype.sqlite` | ❌ | ❌ | **gap** — diplotype schema needed |
| `just_cardio` | cardio | `genes.txt` | ❌ | ❌ | **gap** — ClinVar gene-panel type |
| `just_cancer` | cancer | `genes.txt` | ❌ | ❌ | **gap** — ClinVar gene-panel type |
| `just_pathogenic` | pathogenic | (none) | ❌ | ❌ | **gap** — ClinVar pathogenicity type |
| `just_drugs` | drugs | `annotation_tab.tsv` | ❌ | ❌ | **gap** — PharmGKB domain |

The five modules already on HuggingFace (`just-dna-seq/annotators`) now have a **reproducible
source-of-truth port** re-derived from their Gen-I repos, and the reproduction matches the published
artifacts almost exactly — validating both the port and the HF data.

## Work items to reach parity

### 1. Publish `thrombophilia` — ✅ done (2026-07)
Published to `just-dna-seq/annotators/data/thrombophilia/` via `pipelines v1-port publish
thrombophilia`; `module_metadata.thrombophilia` added to `modules.yaml`. It is now auto-discovered and
part of the default module set. Re-publish (or publish other readied modules) with the same command.

### 2. Close the longevitymap het-allele gap (10 rsids)
284 `allele_weights` rows were skipped, dropping 10 rsids that appear only as heterozygous entries
whose ref/alt pair wasn't found in the Ensembl cache (novel/merged/multiallelic rsids). Options:
- query an additional/newer dbSNP build for the missing rsids, or
- carry the original module's runtime ref lookup forward.
Low value relative to effort — 518/528 already reproduced. Track, don't block.

### 3. Ground `superhuman` with real PMIDs — v1 subset published; v2 pending
Most of the source's `references` are dbSNP URLs, but a subset are real PubMed links. **v1.0.0** is
published to the marketplace grounded on those 2 in-source, rsid-specific, PubMed-verified citations
(APOA2 `rs5082`→17446329, APOE `rs7412`→16603077); the other 755 variants are ungrounded. The full
literature backfill (per-gene founding PMIDs) + **March 2026 refresh** is **v2** — see
`docs/SUPERHUMAN_REFRESH_PLAN.md` (supervised, verification-gated, never fabricates PMIDs).

### 4. New module type: ClinVar gene-panel (`cardio`, `cancer`, `pathogenic`)
These three don't carry per-variant weights — they select ClinVar pathogenic variants (by gene list
for cardio/cancer; directly for pathogenic). Parity requires:
- a **ClinVar reference** (NCBI `clinvar.vcf.gz`, ~200 MB, GRCh38) provisioned like the Ensembl cache
  — note the Ensembl variations parquets already carry `CLIN_*` columns
  (`CLIN_pathogenic`, `CLIN_likely_pathogenic`, `CLIN_benign`, …), so a gene-panel module could be
  built as a filter over the existing cache without a separate ClinVar download;
- a **gene-panel module type** in `just-dna-format` (a module defined by a gene set + a
  pathogenicity predicate, rather than an enumerated variant table). This is a schema proposal for
  the format repo (leave a note in `just-dna-format/docs/ROADMAP.md`).

### 5. New module shape: APOE diplotype (`lnewco`)
`lnewco` keys conclusions on an APOE diplotype spanning `rs7412`+`rs429358` (e.g. `e4/e4`). The DSL's
single-rsid `VariantRow` can't express a multi-locus genotype. Parity requires a haplotype/diplotype
extension to the schema — a `just-dna-format` proposal.

### 6. PharmGKB pharmacogenomics (`drugs`)
`just_drugs` is drug-response annotation (PharmGKB `annotation_tab.tsv`) — a different domain from the
variant-weight modules and never migrated from Gen I. Parity requires a PharmGKB adapter plus likely
new fields (drug, response, evidence level). Largest effort; scope separately.

## Suggested sequencing
1. Publish `thrombophilia` (hours). 2. `superhuman` PMID back-fill (depends on curation capacity).
3. ClinVar gene-panel type covering `cardio`/`cancer`/`pathogenic` in one mechanism (schema + one
adapter). 4. APOE diplotype schema for `lnewco`. 5. PharmGKB `drugs` (separate project).
