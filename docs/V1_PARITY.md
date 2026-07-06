# Generation-I Module Parity Plan

This document maps every Generation-I (Gen I) Just-DNA-Seq annotation module to its port status in
the current (Gen II) `just-dna-format`, and lays out what's needed to reach full feature parity.

Gen-I modules were OakVar *postaggregators*, one `just_*` repo per module in the
[`dna-seq`](https://github.com/dna-seq) GitHub org, each shipping a small curated SQLite/TSV/txt data
file. Stage 1 (see `just_dna_pipelines.v1_port` and `data/interim/v1_port/`) reproducibly ports the
variant-backed modules from that canonical source; this plan covers the rest.

## Where they're published

The **module marketplace** (`https://module-marketplace.just-dna.life`, namespace `just-dna-seq`) is
now the primary store; publish via `pipelines marketplace publish just-dna-seq <name> <version>
data/interim/v1_port/<name>`. The HuggingFace collection (`just-dna-seq/annotators`) is **legacy** and
will be retired after the marketplace migration; it's kept in sync for now via `pipelines v1-port
publish <name>`. All six variant-backed modules are live on both at **1.0.0**.

## Status overview

| Gen-I repo | Module | Data | Ported to `v1_port/`? | Published (marketplace + HF) | Parity |
|---|---|---|---|---|---|
| `just_coronary` | coronary | `coronary.sqlite` | ✅ compiled | ✅ 1.0.0 | **full** — 27/27 rsids match HF |
| `just_vo2max` | vo2max | `vo2max.sqlite` | ✅ compiled | ✅ 1.0.0 | **full** — 13/13 match HF |
| `just_lipidmetabolism` | lipidmetabolism | `lipid_metabolism.sqlite` | ✅ compiled | ✅ 1.0.0 | **full** — 15/15 match HF |
| `just_longevitymap` | longevitymap | `longevitymap.sqlite` | ✅ compiled | ✅ 1.0.0 | **full** — 528/528 rsids, 1043/1043 rows (het gap closed 2026-07-07) |
| `just_thrombophilia` | thrombophilia | `thrombophilia.sqlite` | ✅ compiled | ✅ 1.0.0 | **full** — newly published (2026-07) |
| `just_superhuman` | superhuman | `superhuman.sqlite` | ✅ compiled (v2, narrowed) | ✅ 1.0.0 live; 2.0.0 ready to publish | **full** — v2 curated: 99/99 named protective alleles grounded on human-verified PMIDs (37 genes) + Mar-2026 refresh |
| `just_cardio` | cardio | `genes.txt` | ✅ compiled (ClinVar gene-panel) | ⏸ built, not published (decision) | **reference impl** — 123,020 rows / 304 genes (10 aliases resolved) |
| `just_cancer` | cancer | `genes.txt` | ✅ compiled (ClinVar gene-panel) | ⏸ built, not published (decision) | **reference impl** — 145,467 rows / 319 genes (10 aliases resolved) |
| `just_pathogenic` | pathogenic | (derived from ClinVar) | ✅ compiled (genome-wide ClinVar) | ⏸ built, not published (decision) | **reference impl** — 674,426 rows / 5,540 genes |
| `just_lnewco` | lnewco (APOE) | `metabolic_genotype.sqlite` | ❌ | ❌ | **on hold** — diplotype schema needed (ROADMAP #8) |
| `just_drugs` | drugs | `annotation_tab.tsv` | ❌ | ❌ | **on hold** — PharmGKB domain (ROADMAP #9) |

The five modules previously on HuggingFace now have a **reproducible source-of-truth port**
re-derived from their Gen-I repos, and the reproduction matches the published artifacts almost exactly
— validating both the port and the legacy HF data. thrombophilia was newly added; superhuman v2
(full PMID grounding + Mar-2026 refresh) is curated and ready to publish as 2.0.0.

## Work items to reach parity

### 1. Publish `thrombophilia` — ✅ done (2026-07)
Published to `just-dna-seq/annotators/data/thrombophilia/` via `pipelines v1-port publish
thrombophilia`; `module_metadata.thrombophilia` added to `modules.yaml`. It is now auto-discovered and
part of the default module set. Re-publish (or publish other readied modules) with the same command.

### 2. Close the longevitymap het-allele gap — ✅ done (2026-07-07)
Root cause was **not** Ensembl coverage (all 528 rsids are present in the cache) but a genotype-
reconstruction bug: heterozygous genotypes were built by concatenating the Ensembl `ref` + `alt`
columns, and `alt` is a `|`-joined **multiallelic** list (e.g. `A|G`), yielding invalid genotypes for
284 rows. The fix (`_longevitymap_genotype`) pairs the module's own curated **effect allele** with
its single complement (the Ensembl reference when the effect is an alt), and reads `spec`-state rows
whose `allele` field spells the het genotype out directly (e.g. `CT` → `C/T`). Result: **1043/1043
rows, 528/528 rsids, zero skips** — full parity, no external API/dbSNP build needed. Covered by
`test_longevitymap_genotype_reconstruction` + `test_longevitymap_reconstructs_every_source_rsid`.

### 3. Ground `superhuman` with real PMIDs — ✅ v2 curation DONE (publish pending)
Executed per `docs/SUPERHUMAN_REFRESH_PLAN.md` (supervised, verification-gated; every PMID fetched +
title-verified via NCBI E-utilities, no fabrication). The reviewed result is frozen in a tracked CSV
(`just-dna-pipelines/.../v1_port/data/superhuman_pmid_curation.csv`) and merged by `adapt_superhuman`:

- **Narrowed to named protective alleles**: 1,243 dbSNP variants → **136 genotype rows / 99 rsids /
  37 genes**, with **all 99 rsids grounded** (102 study rows). Unnamed whole-gene SNP dumps dropped.
- **LOF dump genes** (NTRK1 8696348, RIMS1 35022694, SCN9A 17167479): kept as deletion/indel-class
  variants only, grounded gene-level.
- **March-2026 refresh additions** (single-rsid, verified): TPH2 rs4570625 (28342337), COMT rs4680
  (12595695), BDNF rs6265 (12553913), CETP rs5882 (14559957), APOE Christchurch rs121918393 (31686034).
  Gene-therapy/transgenic, haplotype, private/rsid-less and VNTR AREP entries excluded (see GAPS.md).
- **Flag fixes**: APOA2 rs5082 relabeled (BMI/diet, not coronary); FAAH rs324420 → FAAH-OUT; CCR5 →
  founding Δ32 paper.

`validate_spec` passes; studies non-empty; all PMIDs digit-only; all study rsids present in weights.
**Publish as `2.0.0`** (`v1-port publish superhuman` + `marketplace publish just-dna-seq superhuman
2.0.0 …`) — left to the maintainer (publishing is out of scope for the curation agent).

### 4. ClinVar gene-panel (`cardio`, `cancer`, `pathogenic`) — 🟡 reference implementation built (2026-07-07)
These carry no per-variant weights — they select ClinVar pathogenic variants. An **app-level
reference implementation** now ships (`just_dna_pipelines.v1_port.clinvar` + the `gene_panel`
adapter, `pipelines v1-port port --module cardio|cancer|pathogenic`):
- Reads the Gen-I `data/genes.txt` gene list (cardio/cancer), scans the local ClinVar VCF
  (`/data/just-dna-cache/clinvar/clinvar_GRCh38.vcf.gz`, ~190 MB, GRCh38 — hauled once), and keeps
  `Pathogenic`/`Likely_pathogenic` variants whose `GENEINFO` gene is in the panel. `pathogenic` has
  no gene list — it keeps *every* pathogenic ClinVar variant (a genome-wide flag).
- **Gene-symbol reconciliation** (`symbols.py`): panel symbols are resolved against NCBI
  `Homo_sapiens.gene_info` (`/data/just-dna-cache/ncbi_gene/`) so legacy aliases map to the current
  symbols ClinVar uses (cardio: `CCDC114→ODAD1`, `TAZ→TAFAZZIN`, …; cancer: `MRE11A→MRE11`,
  `PARK2→PRKN`, `MYST3→KAT6A`, …). HGNC `MT-*` symbols pass through as-is. Genuine source typos
  (cancer: `ATK1`, `SF381`, `RADS1`, `KDMSC`, … — 13 of them) are **reported, never guessed**.
- Emits both het (`ref/alt`) and hom-alt (`alt/alt`) **risk**-state carrier rows, `weight=None`
  (no invented effect size), `clinvar=pathogenic=True`, conclusion from ClinVar `CLNDN`.
- Every variant is grounded to the **ClinVar resource paper** (PMID `29165669`, PubMed-verified) —
  the honest citation for the data source; per-submission citations are a future enhancement.
- SNVs and short ACGT indels (≤ `MAX_ALLELE_LEN=50`) are kept; multi-kb structural alleles and
  symbolic alleles are skipped (unmatchable as a two-allele genotype) and counted in the log.
- Compiles **cardio** (123,020 rows / 304 genes), **cancer** (145,467 rows / 319 genes), and
  **pathogenic** (674,426 rows / 5,540 genes; ClinVar release pinned in the provenance log). All
  skip Ensembl resolution (`needs_ensembl=False`) since ClinVar already supplies positions.

**Publishing is on hold** (the user's outward decision): the modules are built under
`data/interim/v1_port/` but not pushed to the marketplace/HF. The clean long-term home is a native
**`GenePanelSpec`** in `just-dna-format` (a gene set + pathogenicity predicate, materialized at
compile time) — see `just-dna-format/docs/ROADMAP.md` **item 7**; this app-level adapter is the
intended upstream reference.

### 5. APOE diplotype (`lnewco`) — ⏸ on hold (needs your decision)
`lnewco` keys conclusions on an APOE diplotype spanning `rs7412`+`rs429358` (e.g. `e4/e4`). The DSL's
single-rsid `VariantRow` can't express a multi-locus genotype. Parity requires a haplotype/diplotype
extension to the schema, documented as **ROADMAP item 8** in `just-dna-format`. Blocked on the schema
decision (and worth designing generally, since star-allele PGx loci reuse the same shape).

### 6. PharmGKB pharmacogenomics (`drugs`) — ⏸ on hold (needs your decision)
`just_drugs` is drug-response annotation (PharmGKB `annotation_tab.tsv`) — a different domain from the
variant-weight modules and never migrated from Gen I. Needs a PharmGKB adapter plus new fields (drug,
response, evidence level), documented as **ROADMAP item 9**. Largest effort; scope separately.

### 7. `pathogenic` (all-ClinVar) — 🟡 reference implementation built (2026-07-07)
`just_pathogenic` had no gene list — it flagged *every* ClinVar pathogenic variant. Resolved by
running the same `gene_panel` adapter with no gene filter (`db=None`): it keeps all pathogenic /
likely-pathogenic ClinVar variants → **674,426 rows across 5,540 genes**, grounded to the ClinVar
resource paper, ClinVar release pinned in the provenance log (`source_sha256`). Built under
`data/interim/v1_port/pathogenic/`; **publishing on hold** (it's a large genome-wide flag — confirm
it's a shape you want before pushing). This resolved the "no gene list" blocker by deriving the set
from ClinVar itself.

## Suggested sequencing
1. ✅ `thrombophilia` published. 2. ✅ `longevitymap` full parity (528/528). 3. 🟡 `cardio`/`cancer`/
`pathogenic` gene-panel reference implementation built with gene-symbol reconciliation (publishing on
hold). 4. ✅ `superhuman` v2 PMID back-fill + Mar-2026 refresh curated (publish as 2.0.0 pending).
5. ⏸ Decisions: publish gene panels + pathogenic? then `lnewco` diplotype (ROADMAP #8) and PharmGKB
`drugs` (ROADMAP #9) remain the only unported modules.
