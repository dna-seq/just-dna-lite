# Generation-I Module Parity Plan

This document maps every Generation-I (Gen I) Just-DNA-Seq annotation module to its port status in
the current (Gen II) `just-dna-format`, and lays out what's needed to reach full feature parity.

Gen-I modules were OakVar *postaggregators*, one `just_*` repo per module in the
[`dna-seq`](https://github.com/dna-seq) GitHub org, each shipping a small curated SQLite/TSV/txt data
file. Stage 1 (see `just_dna_pipelines.v1_port` and `data/interim/v1_port/`) reproducibly ports the
variant-backed modules from that canonical source; this plan covers the rest.

**As of 2026-08-09 every Gen-I module has a Gen-II counterpart.** The two that were on hold —
`lnewco` (APOE diplotype) and `drugs` (PharmGKB) — are resolved differently: `drugs` is superseded by
the new `pharmgkb` module on the ClinPGx surface, and `lnewco` is now *unblocked* rather than done
(0.5 shipped the diplotype tables it needed; see item 5).

## Where they're published

The **module registry** (`https://module-registry.just-dna.life`, namespace `just-dna-seq`, server
`just-dna-registry 0.11.0`) is the primary store; publish via `pipelines marketplace publish
just-dna-seq <name> <version> data/interim/v1_port/<name>`. The HuggingFace collection
(`just-dna-seq/annotators`) is **legacy** and kept in sync via `pipelines v1-port publish <name>`.

**All nine were published on 2026-07-09 and the registry has since been wiped** — `marketplace list`
now returns only `eric-mods/lactose_tolerance`. So every module below needs republishing, not just
the rebuilt ones. The pre-wipe versions and changelogs are preserved in
[MODULE_RELEASE_0_5.md](MODULE_RELEASE_0_5.md) so the history stays continuous.

Build and release commands for all ten modules: **[MODULE_RELEASE_0_5.md](MODULE_RELEASE_0_5.md)**.

## Status overview

| Gen-I repo | Module | Data | Built by | Was (wiped) | Republish as | Parity |
|---|---|---|---|---|---|---|
| `just_coronary` | coronary | `coronary.sqlite` | `v1-port port` | 1.0.0 | 1.1.0 | **full** — 27 rsids |
| `just_vo2max` | vo2max | `vo2max.sqlite` | `v1-port port` | 1.0.0 | 1.1.0 | **full** — 13 rsids |
| `just_lipidmetabolism` | lipidmetabolism | `lipid_metabolism.sqlite` | `v1-port port` | 1.0.0 | 1.1.0 | **full** — 15 rsids |
| `just_longevitymap` | longevitymap | `longevitymap.sqlite` | `v1-port port` | 1.1.0 | 1.2.0 | **full** — 528 rsids (4 unmatchable rows pruned, see below) |
| `just_thrombophilia` | thrombophilia | `thrombophilia.sqlite` | `v1-port port` | 1.0.0 | 1.1.0 | **full** — 9 rsids |
| `just_superhuman` | superhuman | `superhuman.sqlite` | `v1-port port` | 2.3.0 | 2.4.0 | **full** — v2 curated, 101 rsids / 37 genes, all PMID-grounded |
| `just_cardio` | cardio | `genes.txt` | `v1-port clinvar` | 1.0.0 | **2.0.0** | **rebuilt on 0.5** — ClinVar snapshot route |
| `just_cancer` | cancer | `genes.txt` | `v1-port clinvar` | 1.0.0 | **2.0.0** | **rebuilt on 0.5** |
| `just_pathogenic` | pathogenic | (derived from ClinVar) | `v1-port clinvar` | 1.0.0 | **2.0.0** | **rebuilt on 0.5** — genome-wide flag |
| `just_drugs` | **pharmgkb** | `annotation_tab.tsv` | `v1-port pharmgkb` | — | 1.0.0 | **superseded** — ClinPGx clinical annotations, 1,482 rows / 219 annotations / 55 drugs |
| `just_lnewco` | lnewco (APOE) | `metabolic_genotype.sqlite` | — | — | ❌ | **unblocked, not built** — 0.5 has the diplotype tables (item 5) |

The panels take a **major** because the rebuild changed what they contain, not just how it is
compiled — see [MODULE_RELEASE_0_5.md](MODULE_RELEASE_0_5.md) § The republish.

## Work items

### 1. Publish `thrombophilia` — ✅ done (2026-07)
Published via `pipelines v1-port publish thrombophilia`; `module_metadata.thrombophilia` added to
`modules.yaml`. Auto-discovered and part of the default module set.

### 2. Close the longevitymap het-allele gap — ✅ done (2026-07-07)
Root cause was **not** Ensembl coverage but a genotype-reconstruction bug: heterozygous genotypes were
built by concatenating the Ensembl `ref` + `alt` columns, and `alt` is a `|`-joined **multiallelic**
list (e.g. `A|G`), yielding invalid genotypes for 284 rows. The fix (`_longevitymap_genotype`) pairs
the module's own curated **effect allele** with its single complement and reads `spec`-state rows whose
`allele` field spells the het genotype out directly. Result: **1043 rows / 528 rsids, zero skips**.
Covered by `test_longevitymap_genotype_reconstruction` and
`test_longevitymap_reconstructs_every_source_rsid`.

### 3. Ground `superhuman` with real PMIDs — ✅ v2 curation done (publish pending)
Executed per `docs/SUPERHUMAN_REFRESH_PLAN.md`, verification-gated (every PMID fetched and
title-verified via NCBI E-utilities). Frozen in a tracked CSV
(`just-dna-pipelines/.../v1_port/data/superhuman_pmid_curation.csv`) and merged by `adapt_superhuman`:
narrowed to **101 named protective alleles across 37 genes**, all grounded, plus the March-2026
additions (TPH2, COMT, BDNF, CETP, APOE Christchurch). This curation shipped as **2.3.0** before the
registry wipe; the 0.5 rebuild republishes it as **2.4.0** with the curation unchanged.

### 4. The ClinVar modules — ✅ rebuilt on the 0.5 enricher route (2026-08-09)
`cardio`, `cancer` and `pathogenic` carry no per-variant weights: they select ClinVar pathogenic
variants. The Generation-I re-port scanned the raw ClinVar VCF and baked coordinates into
`variants.csv`; that route (`v1_port/clinvar.py` + the `gene_panel` adapter) is **superseded** by
`v1_port/clinvar_panel.py`, which drives `just_dna_enricher.clinvar_draft.draft_gene_panel` over the
published ClinVar **parquet snapshot**. Five things change:

1. **Authored by identity.** rsID, or the whole coordinate when an rsID names more than one allele at
   its locus. `just-dna-enricher enrich` fills `resolution.csv` from the same snapshot, so the compile
   is offline and reproducible and Ensembl is not involved at all.
2. **Typed `clin_sig`** from the closed `VALID_CLIN_SIG` vocabulary, so the module is checkable
   against the source it was built from (`enrich --verify-clinsig`).
3. **A stated review-status floor.** `MIN_REVIEW_STARS = 1` drops the 0★ "no assertion criteria
   provided" submissions Gen-I mixed in silently. (The enricher's own default is 2 — better for a
   clinical panel, but it discards ~72% of ClinVar's pathogenic set, and these are flags.)
4. **Per-variant grounding** from ClinVar's own literature links (up to 3 each), instead of one
   blanket citation of the ClinVar resource paper for every row. Variants ClinVar links no paper to
   still fall back to it.
5. **`sources.csv`** records ClinVar's terms, and `module_spec.yaml` carries a `panel:` block
   (`GenePanelSpec`) pinning `clinvar_file_date` and `source_sha256`.

**The one judgement the port makes.** `draft_gene_panel` deliberately leaves `genotype` as a
`<<REPLACE>>` placeholder — ClinVar publishes alleles, and whether carrying one is a carrier state or
an affected one follows from the condition's inheritance mode, which the source does not state. A
genome-wide panel cannot be curated row by row, so `fill_genotypes` expands each stub into the **two
genotypes a diploid caller can emit** (heterozygous `ref/alt`, homozygous `alt/alt`) and says which in
the conclusion. That is a transcription of zygosity, not a claim about its consequence, and it is the
same shape the Gen-I modules had.

Two upstream defects were worked around and reported to the format repo (see
`just-dna-format/docs/ROADMAP.md`): the provider's own study drafting raises on ClinVar's
PubMedCentral/malformed citation ids, so the panel drafts its own `studies.csv` with a PMID filter;
and `cache pull` writes where `resolve_*` does not look.

**Publishing stays the maintainer's call.** Built under `data/interim/v1_port/`, not pushed. These
three were live at 1.0.0 before the registry wipe; the rebuild makes them 2.0.0 rather than a
re-publish of the same number, because the selection and the grounding both changed.

### 5. APOE diplotype (`lnewco`) — 🟡 unblocked by 0.5, not yet built
`lnewco` keys conclusions on an APOE diplotype spanning `rs7412`+`rs429358` (e.g. `e4/e4`), which the
single-rsid `VariantRow` cannot express. **0.5 shipped the tables it needed** — `haplotypes.csv` +
`diplotypes.csv`, with `reference_examples/apoe_epsilon/` as a worked example of exactly this locus.
The remaining work is an adapter that reads `metabolic_genotype.sqlite` and emits those two tables;
no schema decision is outstanding. This is the only Gen-I module with no Gen-II counterpart.

### 6. PharmGKB pharmacogenomics (`drugs`) — ✅ superseded by `pharmgkb` (2026-08-09)
Gen-I `just_drugs` shipped 1,063 PharmGKB **variant** annotations — one row per published study
finding, no evidence grading, `Significance: no` rows mixed in. There was no schema for drug response,
so it was never migrated.

0.5 supplies both halves, and `v1_port/pharmgkb.py` uses them: `pharm_variants.csv`
(`PharmVariantRow`) models a drug-response row keyed by
`(variant, drug, genotype, phenotype_category, annotation_id)`, and the enricher builds a snapshot of
the ClinPGx **clinical** annotations — PharmGKB's aggregated, evidence-levelled reading of all the
studies behind a variant/drug pair.

The module is every clinical annotation at **evidence level 1A/1B/2A/2B** that is keyed to an rsID:
**1,482 rows / 219 annotations / 147 variants / 55 drugs / 33 genes**. Level 3 (single study,
13,631 rows) and 4 (case reports) are excluded — Gen-I drew no such line, and drawing it is most of
the upgrade. Conclusions are ClinPGx's own published sentences, transcribed rather than summarized.

**It is not sellable, and says so.** ClinPGx is CC BY-SA 4.0 *plus* a contractual bar on sale, so
`sources.csv` records `commercial_use=false` / `declared_use=non_commercial` and the compiler refuses
to build without that declaration.

**It publishes to HuggingFace like any other module.** It is led by `pharm_variants.parquet` and has
no `weights.parquet`; discovery probes every family in `module_config.LEAD_TABLES`, so the lead table
is whichever one the module actually has. Two things follow from the shape rather than from the
route. The compiler materializes the 0.4 families verbatim from their authored CSV and applies
`resolution.csv` to `weights.parquet` only, so every `pharm_variants` row reaches us with `chrom` and
`start` null — annotation therefore joins it on **rsid + genotype**, and a VCF carrying no rsIDs in
its `ID` column will match nothing from this module. And having no weights, its report rows sort by
ClinPGx evidence level (1A strongest) rather than by effect size.

### 7. `pathogenic` (all-ClinVar) — ✅ folded into item 4
`just_pathogenic` had no gene list. Its gene set is now derived from the snapshot itself
(`panel_genes()` — every gene in the pathogenic selection), and `GenePanelSpec.genes` is left empty,
which the model documents as "no gene filter". That is what the module is.

## Findings from the 0.5 rebuild

Things the new surfaces caught that the old route did not:

- **Four longevitymap rows can never match a VCF.** The registry's strict pre-publish check
  (`POST /api/v1/modules/{ns}/{name}/check`) reports `rs699 A/T` and `T/T` against a locus that is
  `A/G`, `rs1207362 C/C` against `G/T`, and `rs2107538 A/A` against `C/T`. This is Gen-I curation
  following a paper's strand rather than the reference's, and it is **not** a reverse-complement away
  — `rs699`'s authored pair mixes one forward-strand allele with one reverse-strand one. The port
  drops such rows (named in `v1_port.log`) and the repair is curation against the original papers.
- **Malformed gene cells.** `ABCG8, ABCG5` and `BIRC7, YTHDF1` are two genes in one cell;
  `CXCL12 (LINC02881)` parenthesises a second identifier. `normalize_genes` splits and resolves them
  against NCBI `gene_info`. `GUCYA3` (rs7692387) and `SERPINE` (rs1799889) are one-character
  truncations the variant settles unambiguously, so they are in a small curated map with the reason;
  `FLJ44450` (rs4952535) resolves to nothing and is reported, never guessed.
- **Orphan study rows** citing rsIDs the module does not weight, pruned and counted.

## Suggested sequencing
1. ✅ `thrombophilia` published. 2. ✅ `longevitymap` full parity. 3. ✅ `superhuman` v2 curated
(publish as 2.0.0). 4. ✅ `cardio`/`cancer`/`pathogenic` rebuilt on the 0.5 ClinVar route.
5. ✅ `pharmgkb` built. 6. ⏸ Decisions left to the maintainer: publish the four unpublished modules,
republish the six under 0.5 (every digest moves), and build `lnewco` on the diplotype tables.
