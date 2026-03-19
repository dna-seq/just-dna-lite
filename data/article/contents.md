# Article Materials: AI-Assisted Genomic Module Creation

This folder contains screenshots, logs, and output artifacts documenting four
end-to-end demonstrations of the just-dna-lite **Module Creator** system.
Together they form the evidence base for **Section 4.3** of the manuscript.

---

## Folder Structure

```
article/
├── contents.md                      ← this file
│
├── Single agent_0.png               ← Scenario 1, step 0: user types prompt
├── Single agent_1_wip_.png          ← Scenario 1, step 1: agent working
├── Single agent_2.png               ← Scenario 1, step 2: module loaded in sidebar
├── Single agent_3_complete.png      ← Scenario 1, step 3: full agent trace expanded
│
├── Team_0.png                       ← Scenario 2, step 0: user types prompt (team mode)
├── Team_1_in_progress.png           ← Scenario 2, step 1: PI dispatches researchers
├── Team_2_complete_v1.png           ← Scenario 2, step 2: team finished, v1 summary
├── Team_4_complete_v1_call_entries.png ← Scenario 2, step 3: full call trace visible
├── Team_4_in_progress_v2.png        ← Scenario 3, step 0: user requests module edit
├── Team_5_complete.png              ← Scenario 3, step 1: team finishes v2 edit
│
├── Screenshots_fullHD/              ← High-resolution screenshots (Scenario 4)
│   ├── Screenshot from 2026-03-19 22-43-34.png  ← S4 step 0: team mode, prompt entered
│   ├── Screenshot from 2026-03-19 22-43-48.png  ← S4 step 1: send clicked, run starting
│   ├── Screenshot from 2026-03-19 22-49-11.png  ← S4 step 2: v1 complete, summary visible
│   ├── Screenshot from 2026-03-19 22-49-32.png  ← S4 step 3: reviewer feedback expanded
│   ├── Screenshot from 2026-03-19 22-50-16.png  ← S4 step 4: full call trace (v1)
│   ├── Screenshot from 2026-03-19 22-51-38.png  ← S4 step 5: user attaches edit article
│   ├── Screenshot from 2026-03-19 22-51-45.png  ← S4 step 6: edit request sent, run starting
│   ├── Screenshot from 2026-03-19 23-54-34.png  ← S4 step 7: v2 complete, mvARD summary
│   ├── Screenshot from 2026-03-19 23-56-19.png  ← S4 step 8: call trace (v2, 4 reviewer cycles)
│   ├── Screenshot from 2026-03-20 00-05-27.png  ← S4 step 9: module registered as source
│   └── Screenshot from 2026-03-20 00-06-23.png  ← S4 step 10: module active in Annotation tab
│
├── familial_longevity/              ← Output: Scenario 1 (Solo Agent)
│   ├── module_spec.yaml
│   ├── variants.csv
│   ├── studies.csv
│   ├── MODULE.md
│   └── familial_longevity_v1.log
│
└── latest_longevity/                ← Output: Scenarios 2 & 3 (Team)
    ├── v1/                          ← Scenario 2 output (team creation, v1)
    │   ├── module_spec.yaml
    │   ├── variants.csv
    │   ├── studies.csv
    │   ├── MODULE.md
    │   ├── logo.png
    │   └── v1.log
    └── v2/                          ← Scenario 3 output (team edit, v2)
        ├── module_spec.yaml
        ├── variants.csv
        ├── studies.csv
        ├── MODULE.md
        ├── logo.png
        └── v2.log
```

---

## Screenshots at a Glance (Scenarios 1–3)

| File | What it shows |
|------|--------------|
| `Single agent_0.png` | Module Manager UI — user has attached `Putter_longevity_variants_21.pdf` and typed **"I want you to create a module based on the attached articles"**. The "Single agent" checkbox is ticked. |
| `Single agent_1_wip_.png` | Agent mid-run: completed `validate_spec`, `get_europepmc_articles` (×2), `get_europepmc_preprints`, `write_spec_files`, `validate_spec`. Spinner still active. |
| `Single agent_2.png` | Run complete. Left sidebar shows the **familial_longevity v1** module loaded in the editing slot. Chat panel shows the agent's summary (cGAS D452V + SH2D3A + RARS2 + SLC27A3). |
| `Single agent_3_complete.png` | Same state with call-entry log expanded: every tool call visible in sequence — BioRxiv preprint fetch, EuropePMC searches, Open Targets query, write, validate, MODULE.md, logo generation. |
| `Team_0.png` | Module Manager UI — "Research Team (multi-agent)" mode selected. Two PDFs attached. Prompt: **"Create a latest_longevity module, based on the attached articles. Let the module icon contain year 2025"**. |
| `Team_1_in_progress.png` | Team mid-run: PI has dispatched all three researchers simultaneously. Researcher 1 has already returned a EuropePMC result. |
| `Team_2_complete_v1.png` | Team run complete, v1 created. Sidebar shows `latest_longevity v1`. Chat summary lists cGAS-STING, SIRT6, and 9 linkage variants. |
| `Team_4_complete_v1_call_entries.png` | Same state with call trace expanded: PI → researcher-1/2/3, PI → reviewer, PI: write_spec_files, PI: validate_spec, PI: write_module_md, PI: generate_logo, PI: register_module. All green. |
| `Team_4_in_progress_v2.png` | User sends a second message with two new attachments (Dinh ARDs paper + supplementary CSV with ~260 rsids). Spinner just started. |
| `Team_5_complete.png` | v2 complete. Sidebar shows `latest_longevity v2`. Chat summary lists 5 new mvARD pleiotropic SNPs added (ZNF259, SORT1, SH2B3, TRIB1, GCKR). |

---

## Scenario 1 — Solo Agent: `familial_longevity`

### Overview

A single Gemini 3 Pro agent (no sub-team) reads a bioRxiv preprint PDF, queries
external databases, and produces a validated annotation module in one pass.

**Source paper:** Putter et al. (2025), "Rare longevity-associated variants,
including a reduced-function mutation in cGAS, identified in multigenerational
long-lived families" (bioRxiv preprint, DOI: 10.1101/2025.12.04.689698).
Uploaded as `Putter_longevity_variants_21.pdf`.

### User Actions

1. Opened the **Module Manager** tab → selected **Module Creator** (single agent mode).
2. Clicked **Attach** and uploaded `Putter_longevity_variants_21.pdf`.
3. Typed the prompt: *"I want you to create a module based on the attached articles"*
4. Clicked **Send**.
5. Waited approximately **~107 seconds** while watching tool calls stream in.
6. Inspected the generated module in the left sidebar (familial_longevity v1 loaded automatically).

### What the Agent Did (from `familial_longevity_v1.log`)

| Time | Action | Detail |
|------|--------|--------|
| 0.0s | Startup | Initialized Gemini 3 Pro agent; loaded BioContext MCP (30+ tools) + 5 PI tools |
| 2.1s | PDF attached | `Putter_longevity_variants_21.pdf` passed as file context |
| 12.7s | `query_open_targets_graphql` | Queried Open Targets for variant–disease associations on CGAS gene |
| 23.0s | `get_europepmc_articles` | Searched EuropePMC for supporting cGAS-STING literature |
| 28.9s | `get_biorxiv_preprint_details` | Fetched full preprint metadata |
| 56.4s | `get_europepmc_articles` | Second EuropePMC search for linkage variants (SH2D3A, RARS2, SLC27A3) |
| 79.5s | `write_spec_files` | Wrote `module_spec.yaml` + `variants.csv` (11 rows) + `studies.csv` |
| 85.0s | `validate_spec` | **VALID** — 11 variant rows, 10 unique rsids, 2 categories |
| 93.8s | `write_module_md` | Wrote `MODULE.md` |
| 106.5s | `generate_logo` | Attempted logo generation (API error — model unavailable) |
| ~107s | **Complete** | Module ready |

### Final Output: `familial_longevity`

**`module_spec.yaml`:**
```yaml
name: familial_longevity
version: 1
title: "Familial Longevity & cGAS-STING Signalling"
description: "Rare protective variants in cGAS and other genes associated with familial longevity and delayed cellular senescence."
icon: heart-pulse
color: "#00b5ad"
genome_build: GRCh38
```

**`variants.csv`:** 12 rows across 4 genes (CGAS, SH2D3A, RARS2, SLC27A3).

**`studies.csv`:** 1 row — rs200818241 linked to PMID 37532932.

---

## Scenario 2 — Team Creation: `latest_longevity` v1

### Overview

A four-agent team (PI + 3 Researchers + Reviewer) works in parallel to create
a new module from two research PDFs.

**Source papers:**
- Putter et al. (2025) — cGAS longevity variant and linkage panel (PMID 41427385).
- Sheikholmolouki et al. (2025) — SIRT6 rs117385980 frailty/longevity study (PMID 41249831).

### What the Team Did (from `latest_longevity/v1/v1.log`)

**Phase 1 — PI dispatches all researchers simultaneously (t=0–136s)**

| Time | Actor | Action |
|------|-------|--------|
| 0.0s | System | Team: PI (Gemini 3 Pro) + R1 (Gemini) + R2 (GPT-4.1) + R3 (Claude Sonnet) + Reviewer (Gemini Flash + Google Search) |
| 21.5s | PI | `delegate_task_to_member → researcher-1/2/3` simultaneously |
| 72.7s | R1 | `get_europepmc_articles` — searched for SIRT6 rs117385980 |
| ~52–110s | R2, R3 | Parallel queries on Putter et al. variants |
| 136.5s | PI | All three researcher tasks complete |

**Phase 2 — PI synthesizes + calls Reviewer (t=136–234s)**

| Time | Actor | Action |
|------|-------|--------|
| 175.7s | PI | `delegate_task_to_member → reviewer` — sent draft variants.csv |
| 234.7s | PI | Reviewer response received; conservative weights retained |

**Phase 3 — PI writes (t=234–461s)**

| Time | Actor | Action |
|------|-------|--------|
| 275.6s | PI | `write_spec_files` — 34 rows, 8 genes |
| 280.1s | PI | `validate_spec` — **VALID** |
| 288.9s | PI | `write_module_md`, `generate_logo`, `register_module` |
| 461.3s | PI | Complete |

### Final Output: `latest_longevity` v1

**`variants.csv`:** 34 rows across 8 genes in 2 categories: *Familial Longevity* and *Frailty and Longevity*.

**`studies.csv`:** 11 rows linking all variants to PMID 41427385 and PMID 41249831.

---

## Scenario 3 — Team Edit: `latest_longevity` v2

### Overview

With `latest_longevity v1` in the editing slot, the user provides a second paper
(Dinh et al. 2025, GeroScience) plus a large supplementary CSV (~260 rsids). The
team reads the existing module and extends it to v2 with 5 new mvARD variants.

**Source materials:**
- Dinh et al. (2025) "Genetic links between multimorbidity and human aging". Uploaded as `Dink_ARDs_5.pdf`.
- Supplementary Table with ~260 lead SNPs. Uploaded as `11357_2025_2044_MOESM2_ESM_5.csv`.

### What the Team Did (from `latest_longevity/v2/v2.log`)

**Phase 1 — PI reads existing module + dispatches researchers (t=0–210s)**

| Time | Actor | Action |
|------|-------|--------|
| 31.6s | PI | `delegate_task_to_member → researcher-1/2/3` simultaneously |
| ~38–55s | R1 | `query_open_targets_graphql` ×5 (ZNF259, SORT1, SH2B3, TRIB1, GCKR), then EuropePMC ×3 |
| ~42–45s | R2 | `get_europepmc_articles` ×6 |
| ~210s | PI | All researcher tasks complete |

**Phase 2 — PI synthesizes + calls Reviewer (t=210–311s)**

PI selected the top 5 most pleiotropic SNPs: rs964184 (ZNF259/APOA5), rs12740374 (SORT1),
rs7310615 (SH2B3), rs28601761 (TRIB1), rs6547692 (GCKR).

| Time | Actor | Action |
|------|-------|--------|
| 248.6s | PI | `delegate_task_to_member → reviewer` |
| 311.1s | PI | Reviewer confirmed all 5 SNPs; accepted weighting approach |

**Phase 3 — PI writes v2 (t=311–418s)**

| Time | Actor | Action |
|------|-------|--------|
| 398.5s | PI | `write_spec_files` — 49 rows total, studies.csv updated (16 rows), version bumped to 2 |
| 404.0s | PI | `validate_spec` — **VALID** |
| 408.8s | PI | `register_module` |
| 418.3s | PI | Complete |

### Final Output: `latest_longevity` v2

**`variants.csv`:** 49 rows — all 34 from v1 + 15 new rows (5 mvARD SNPs × 3 genotypes) in a new **"mvARD"** category.

**`studies.csv`:** 16 rows — all 11 from v1 + 5 new rows linking mvARD SNPs to Dinh et al. 2025.

---

## Scenario 4 — Team Creation + Edit + Annotation: `longevity_variants_2026`

### Overview

This scenario demonstrates the complete end-to-end workflow in high-resolution: a
**Research Team** creates a new module from a single preprint (v1 in ~284s), then
iteratively **edits** it with a second article's findings (v2 in ~762s), **registers**
the result as a local annotation source, and immediately **uses** it to annotate a
real WGS sample alongside five other modules — all within a single session.

This is the recommended demonstration for Section 4.3 because it explicitly shows
the **editing slot pattern**, the **custom module source**, and the **transition from
creation to active annotation**.

**Team composition (from logs):**
- PI: Gemini 3 Pro Preview
- Researcher 1: Gemini 3 Pro Preview
- Researcher 2: GPT-4.1 (OpenAI)
- Researcher 3: Claude Sonnet-4.5 (Anthropic)
- Reviewer: Gemini Flash Preview + Google Search

**Source papers:**
- Putter et al. (2025) — rare familial longevity variants (cGAS D452V + linkage loci).
  Uploaded as `Putter_longevity_variants_28.pdf`.
- Dinh et al. (2025), *GeroScience* (PMID 41405793) — multivariate GWAS of
  age-related disease multimorbidity (mvARD); 6 lead pleiotropic loci inversely
  correlated with extreme longevity. Uploaded as `Dink_ARDs_6.pdf`.

---

### Screenshots at a Glance (Scenario 4)

| File | What it shows |
|------|--------------|
| `22-43-34.png` | Module Manager in **Research team (multi-agent)** mode. Editing slot is empty ("No module loaded"). One PDF attached (`Putter_longevity_variants_...`). User has typed **"Please create a module named longevity_variants 2026, based on the attached"**. Send button is active. |
| `22-43-48.png` | Immediately after Send: user message appears green; status line reads **"Last team run event: TeamModelRequestStarted"** with a spinner. Editing slot still empty — creation has begun but not yet complete. |
| `22-49-11.png` | Run complete (~284s later). Editing slot shows **`longevity_variants_2026 v1`** with description ("Rare protective genetic variants associated with familial longevity, including a reduced-function mutation in cGAS"). All spec files listed: MODULE.md, module_spec.yaml, studies.csv, v1.log, variants.csv. Chat panel displays the PI's full module summary. |
| `22-49-32.png` | Same state with **"expand entries to inspect"** open. Purple reviewer block visible: **"High Confidence: The lead variant rs200818241 (CGAS) is supported by extensive functional evidence…"** with PMIDs 38155014 and 28592602. `PI: write_spec_files ✓` shown at the bottom. |
| `22-50-16.png` | Full **call trace** for v1: `Researcher 2: get_europepmc_articles` (×2), `Researcher 1: get_europepmc_articles` (×6 across phases), `Researcher 3: get_europepmc_articles` (×3 batched), then `PI → reviewer ✓`, then `PI: write_spec_files ✓`. |
| `22-51-38.png` | User has attached **`Dink_ARDs_6.pdf`** and typed **"Now, I want to add this other article's findings to the module"**. The editing slot still shows `longevity_variants_2026 v1` — the team will read the existing module and extend it. |
| `22-51-45.png` | Edit request sent; spinner started ("TeamModelRequestStarted"). The previous v1 chat summary (scoring logic, GRCh38 build) is still on screen. The transition from creation to editing is a single follow-up message in the same thread. |
| `23-54-34.png` | Edit complete (~762s). Editing slot shows **`longevity_variants_2026 v2`** with updated description ("…and shared genetic risks for age-related multimorbidity"). Both `v1.log` and `v2.log` are linked. Chat summary: **"Added 6 New Variants"** — rs1788785 (NPC1), rs10931284 (TFPI), rs6505080 (BPTF), rs72887634 (GPD1L), rs16959812 (LINC02512), rs9430037 (ABO). Negative weights −0.2 het / −0.4 hom for risk alleles. |
| `23-56-19.png` | v2 **call trace** expanded. Shows the sequential final phase: `Researcher 3: get_europepmc_articles ✓`, `PI → researcher-2 ✓` (follow-up delegation for UniProt), `Researcher 2: get_uniprot_protein_info ✓`, then four `PI → reviewer` cycles (Google Search used to look up GRCh38 REF/ALT alleles for the 6 new SNPs and verify the paper's PMID), then `PI: write_spec_files ✓`. |
| `00-05-27.png` | User clicked **Register Module as source**. Confirmation message: **"Module longevity_variants_2026 registered successfully! (48 variants) — now available for annotation."** A new **Custom Modules** section has appeared under Module Sources with `longevity_variants_2026` listed alongside the HuggingFace source. |
| `00-06-23.png` | User switched to the **Annotation** tab. The **New Analysis** panel shows **6 modules selected**, including a `Longevity Variants 2026` card with green icon (the newly registered module, source path `data/interim/registered_modules`). A WGS sample (`newtonwinter_12382_bwa_ys`, GRCh38) is loaded. **Start Analysis** button is ready. |

---

### What the Team Did (from `v1.log` and `v2.log`)

#### Phase A: Create v1 — t=0 to 284s (`v1.log`, started 2026-03-19 22:43:42)

| Time | Actor | Action |
|------|-------|--------|
| 0.0s | System | Team assembled: PI (Gemini 3 Pro) + R1 (Gemini) + R2 (GPT-4.1) + R3 (Claude Sonnet-4.5) + Reviewer (Gemini Flash + Google Search) |
| 18.3s | PI | `delegate_task_to_member → researcher-1/2/3` simultaneously |
| 28.0s | R2 | `get_europepmc_articles` ×2 |
| 31.9s | R3 | `get_europepmc_articles` ×3 (batched) |
| 43.7s | R1 | `get_europepmc_articles` (first of 5 total EuropePMC calls) |
| 105.3s | R1 | Final `get_europepmc_articles` call completes |
| 150.5s | PI | All three researcher tasks complete |
| 189.5s | PI | `delegate_task_to_member → reviewer` (single QC cycle) |
| 232.0s | Reviewer | High-confidence verdict for cGAS rs200818241 with PMIDs 38155014 + 28592602 |
| 250.8s | PI | `write_spec_files` ✓ |
| 254.7s | PI | `validate_spec` ✓ |
| 263.0s | PI | `write_module_md` ✓ |
| 267.6s | PI | `generate_logo` ✓ |
| 283.9s | PI | **v1 complete** |

**v1 output:** 30 variant rows across 10 rsids in 6 categories (Inflammation / Cellular signaling /
Nuclear function / Metabolism / Immunity / Mitochondrial function) covering CGAS, SH2D3A, NUP210L,
SLC27A3 (×2 variants), CD1A, IBTK (×2 variants), RARS2 (×2 variants).

#### Phase B: Edit to v2 — t=0 to 762s (`v2.log`, started 2026-03-19 22:51:39)

| Time | Actor | Action |
|------|-------|--------|
| 0.0s | System | Same team; PI given existing v1 files + `Dink_ARDs_6.pdf` |
| 21.9s | PI | `delegate_task_to_member → researcher-1/2/3` simultaneously |
| 31.8s | R2 | `get_europepmc_articles` ×3 (batched) |
| 38.4s | R1 | `query_open_targets_graphql` (first query) |
| 41.3s | R3 | `get_europepmc_articles` ×3 (batched) |
| 43.9s | R2 | `get_europepmc_articles` ×3 (second batch) |
| 46.7s | R1 | `query_open_targets_graphql` ×5 in parallel (one per mvARD gene locus) |
| 52.5s | R1 | `get_europepmc_articles` ×3 |
| 78.2s | R3 | `get_europepmc_articles` ×3 (final batch) |
| 161.7s | PI | All 3 researcher tasks complete |
| 182.0s | PI | `delegate_task_to_member → researcher-2` (follow-up: UniProt lookup) |
| 227.8s | R2 | `get_uniprot_protein_info` (protein details for NPC1, TFPI, BPTF loci) |
| 238.2s | PI | researcher-2 follow-up complete |
| 243.1s | PI | **Reviewer cycle 1**: ask Reviewer to look up REF/ALT alleles for 6 new SNPs via Google Search |
| 409.3s | Reviewer | Returns partial allele info (first attempt) |
| 416.6s | PI | **Reviewer cycle 2**: refined query — REF/ALT alleles + mapped genes for all 6 SNPs |
| 535.3s | Reviewer | Returns full SNP table: NPC1 (rs1788785), TFPI (rs10931284), BPTF (rs6505080), GPD1L (rs72887634), LINC02512 (rs16959812), ABO (rs9430037); all alleles confirmed GRCh38 |
| 550.0s | PI | **Reviewer cycle 3**: ask Reviewer to find the PMID for Dinh et al. 2025 |
| 567.4s | Reviewer | Returns PMID **41405793** (DOI: 10.1007/s11357-025-02044-3) |
| 592.3s | PI | **Reviewer cycle 4**: final QC of the complete draft CSV (all v1 rows + 18 new rows) |
| 681.2s | Reviewer | **ERRORS: None. WARNINGS: single-study provenance (acceptable; N > 400,000 multivariate GWAS). OK: GRCh38 alleles, genotype sorting, weights, PMID, formatting.** |
| 723.2s | PI | `write_spec_files` ✓ |
| 726.5s | PI | `validate_spec` ✓ |
| 743.8s | PI | `write_module_md` ✓ |
| 748.5s | PI | `generate_logo` ✓ |
| 761.9s | PI | **v2 complete** |

**The four reviewer cycles serve distinct purposes:**

1. **Cycles 1 & 2 — Allele lookup oracle.** The PI uses the Reviewer's Google Search
   access to obtain verified GRCh38 REF/ALT alleles for the 6 new SNPs. The first
   attempt returned partial results; the PI immediately re-delegated with a more
   specific query. This avoids re-spinning a full researcher task for a simple
   factual lookup.
2. **Cycle 3 — PMID resolution.** The article was uploaded as a PDF without a
   machine-readable PMID; the Reviewer found PMID 41405793 via Google Search.
3. **Cycle 4 — Standard QC.** Final review of the complete draft CSV. The only
   warning was single-study provenance, which the Reviewer itself deemed acceptable
   given the study design (multivariate GWAS, N > 400,000, published in GeroScience).

**v2 output:** 48 variant rows total — 30 retained from v1 + 18 new rows (6 mvARD SNPs
× 3 genotypes each) in a new **"Multimorbidity"** category:

| rsid | Gene | Risk allele logic |
|------|------|-------------------|
| rs1788785 | NPC1 | Alt T increases shared liability for CVD/metabolic multimorbidity |
| rs10931284 | TFPI | Alt T increases mvARD |
| rs6505080 | BPTF | Alt T increases mvARD |
| rs72887634 | GPD1L | Alt T increases mvARD |
| rs16959812 | LINC02512 | Alt A; novel locus with no prior univariate GWAS signal |
| rs9430037 | ABO | Alt C; ABO locus linked to inflammation and mvARD |

All 6 new SNPs carry negative weights (−0.2 het, −0.4 hom) because they increase
age-related multimorbidity liability, which is inversely correlated with extreme longevity.
`studies.csv` adds 6 rows for PMID 41405793.

---

### Workflow Steps in Detail

**Step 1 — Open Module Manager, select Research Team mode**

The user navigates to **Module Manager** and confirms **Research team (multi-agent)**
is active (`22-43-34.png`). The Gemini key is pre-configured; the optional OpenAI
key enables the GPT-4.1 researcher. The editing slot is empty.

**Step 2 — Attach PDF and submit creation prompt**

The user attaches `Putter_longevity_variants_28.pdf` and types the prompt with the
module name embedded. Clicking Send dispatches the task to the PI (`22-43-48.png`).

**Step 3 — Team creates module v1 (parallel research → consensus → review → write)**

At t=18.3s the PI dispatches all three researchers simultaneously. They make a
combined ~11 EuropePMC queries in parallel. The PI synthesizes by consensus and
calls a single Reviewer cycle (t=189.5s). After a high-confidence QC verdict, the
PI writes all spec files. The module appears as `longevity_variants_2026 v1`
(`22-49-11.png`).

**Step 4 — Inspect the call trace and reviewer feedback**

The user expands the call trace (`22-50-16.png`). The purple reviewer block
(`22-49-32.png`) shows the PMIDs confirming cGAS-STING ageing biology. No manual
edits are needed.

**Step 5 — Attach second article and submit edit prompt**

Without leaving Module Manager, the user attaches `Dink_ARDs_6.pdf` and types a
follow-up message (`22-51-38.png`). The editing slot still holds `v1` — the team
receives both the existing module files and the new article as context for the edit.

**Step 6 — Team edits to v2 (research + Reviewer as lookup oracle → write)**

Researchers make ~20 parallel database queries (EuropePMC, Open Targets, UniProt).
The PI then uses the Reviewer's Google Search access for three sequential fact-lookups:
GRCh38 REF/ALT alleles for the 6 new SNPs (2 cycles) and the paper's PMID (1 cycle).
A final QC review (cycle 4) clears the draft with no errors. The PI writes the
updated spec with 18 new rows in a "Multimorbidity" category. The editing slot
updates to `longevity_variants_2026 v2` (`23-54-34.png`).

**Step 7 — Register the module as an annotation source**

The user clicks **Register Module as source**. The module is written to
`data/interim/registered_modules/` and a **Custom Modules** entry appears in Module
Sources (`00-05-27.png`). 48 variants are now available to the annotation pipeline.

**Step 8 — Use the module in annotation**

The user switches to the **Annotation** tab. The `Longevity Variants 2026` card
appears alongside 5 curated modules from the remote HuggingFace source
(`00-06-23.png`). With a WGS sample loaded, the user clicks **Start Analysis**.

---

### Updated Team Workflow Flowchart

```
User types prompt + optional attachments (PDF / CSV / MD / TXT)
      │
      ▼
PI (Gemini Pro) receives task + [existing module if in editing slot]
      │
      ├─────────────────────────────────────────────────────────────┐
      │  NEW MODULE path                                            │
      │    PI delegates identical research task in parallel:        │
      │                                                             │
      │    Researcher 1      Researcher 2      Researcher 3         │
      │   (Gemini Pro)      (GPT-4.1,          (Claude,             │
      │                      optional)          optional)           │
      │         │                 │                  │              │
      │         ▼                 ▼                  ▼              │
      │    EuropePMC        Open Targets        UniProt /           │
      │    literature       variant–disease     BioRxiv             │
      │    searches         associations        protein info        │
      │         │                 │                  │              │
      │         └─────────────────┴──────────────────┘              │
      │                           │                                 │
      │                           ▼                                 │
      │              PI synthesises consensus                       │
      │          (majority vote; median weights)                    │
      └─────────────────────────────────────────────────────────────┘
      │
      ├─────────────────────────────────────────────────────────────┐
      │  EDIT path  (module already in editing slot)                │
      │    PI reads existing module_spec.yaml + variants.csv        │
      │    PI delegates targeted research on new article only       │
      │    PI may follow-up with individual researchers             │
      │    PI merges new rows into existing CSV                     │
      └─────────────────────────────────────────────────────────────┘
      │
      ▼
PI → Reviewer (Gemini Flash + Google Search)
      │
      │  Reviewer may be called multiple times for:
      │    1. Lookup oracle  — REF/ALT alleles for new SNPs
      │    2. PMID lookup    — find correct citation for uploaded PDF
      │    3. QC review      — provenance, weights, genome build
      │
      ├── ERRORS   → PI corrects and re-submits to Reviewer
      ├── WARNINGS → PI addresses (may accept if evidence is strong)
      └── OK ──────────────────────────────────────────────────────┐
                                                                   │
                                                                   ▼
                          write_spec_files → validate_spec
                                 │
                          write_module_md → generate_logo
                                 │
                          ┌──────▼─────────────────────────┐
                          │     Module in Editing Slot     │
                          │  (version auto-incremented     │
                          │   on each edit)                │
                          └──────┬─────────────────────────┘
                                 │
              ┌──────────────────┼──────────────────────┐
              ▼                  ▼                       ▼
       Register as         Download .zip           Iterate
       annotation          (spec files            (send new
       source              for sharing)            message
              │                                    with new
              ▼                                    article)
  Module Sources →
  Custom Modules list
              │
              ▼
  Annotation tab →
  module card in selection grid
              │
              ▼
  Start Analysis → module participates in VCF annotation run
```

---

## Comparison Across All Scenarios

| Dimension | Scenario 1 (Solo) | Scenario 2 (Team, new) | Scenario 3 (Team, edit) | Scenario 4 (Team, create+edit) |
|-----------|------------------|----------------------|------------------------|-------------------------------|
| Module created | `familial_longevity` | `latest_longevity` | `latest_longevity` v2 | `longevity_variants_2026` |
| Mode | Single agent | Research team | Research team | Research team |
| Input | 1 PDF | 2 PDFs | 1 PDF + 1 CSV (~260 rows) | 1 PDF (v1) + 1 PDF (v2 edit) |
| Duration | ~107s | ~461s | ~418s | ~284s (v1) + ~762s (v2) |
| Researchers | — (self-researches) | 3 parallel (Gemini + GPT-4.1 + Claude) | 3 parallel (same) | 3 parallel (Gemini + GPT-4.1 + Claude Sonnet-4.5) |
| Reviewer cycles | — | 1 | 1 | 1 (v1) + 4 (v2) |
| Reviewer role | — | QC | QC | QC + lookup oracle (REF/ALT + PMID) |
| Variant rows produced | 12 (4 genes) | 34 (8 genes, 2 categories) | +15 new → 49 total | 30 (v1) + 18 new → 48 total (v2) |
| Database calls | 4 (OT, PMC ×2, BioRxiv) | 7+ per researcher | 8+ per researcher | PMC ×11 + OT ×6 (v1); PMC ×15 + OT ×6 + UniProt (v2) |
| Manual edits | None | None | None | None |
| Logo generated | Attempted (API error) | Yes (2025 genetics motif) | Skipped (existing reused) | Yes (v1); Yes (v2) |
| Post-creation step shown | — | Register implied | Register implied | **Register + Annotation tab** |

---

## Interpreting the Logs

The `.log` files are machine-generated by the `RunLog` class in `module_creator.py`.
Each line has the format:

```
[ elapsed_s]  >> tool_name       ← tool call started
[ elapsed_s]  DONE tool_name ✓   ← tool call completed
[ elapsed_s] [agno_run_log.team] message  ← internal Agno framework message
```

For team runs, tool calls from member agents appear as:
```
Researcher N: get_europepmc_articles    ← member tool call
PI → reviewer                           ← delegation
PI: write_spec_files                    ← PI tool call
```

The logs preserve intermediate outputs in full (up to 2000 chars per tool call),
including raw JSON from BioContext KB and CSV drafts passed to the Reviewer.

---

## Selected Modules for Section 4.3

**Primary demonstration — Scenario 4 (`longevity_variants_2026`, `Screenshots_fullHD/`):**

The high-resolution Scenario 4 screenshots are the recommended primary evidence because
they show the **full closed loop** in a single session: creation → iterative edit →
registration → annotation. Unique advantages:

1. The **editing slot pattern** is unambiguous: `v1` is in the sidebar before the
   edit prompt is sent; `v2` replaces it afterwards in the same chat thread.
2. The **dual-role Reviewer** in v2 (4 cycles) shows the system self-resolving
   factual lookups (REF/ALT alleles via Google Search, PMID resolution) without any
   user intervention.
3. The **Custom Modules** panel in `00-05-27.png` shows a user-created module
   integrating seamlessly alongside the remote HuggingFace catalogue.
4. The **Annotation tab** in `00-06-23.png` closes the loop: the AI-generated
   module participates in a real WGS analysis run with 6 modules selected.
5. Both runs are **fully machine-logged** (`v1.log` 284s; `v2.log` 762s) with
   every tool call, model identity, token count, and Reviewer response preserved.

**Companion — Scenarios 2 & 3 (`latest_longevity`):**

Demonstrates a three-researcher team (Gemini + GPT-4.1 + Claude) processing a
large GWAS supplementary CSV (~260 rsids). The Reviewer's single-study provenance
warnings are documented verbatim, illustrating the quality-control layer.

**Single-agent baseline — Scenario 1 (`familial_longevity`):**

Shows the same output quality is achievable with a solo agent at ~107s — appropriate
for users with only a Gemini API key.
