# AI Module Creator — Walkthrough & Examples

This document covers the Module Creator system end-to-end through three concrete, documented scenarios. For the technical spec (DSL format, compiler, registry API, agent architecture), see [AI_MODULE_CREATION.md](AI_MODULE_CREATION.md).

---

## How it works in practice

The Module Creator is a chat interface in the **Module Manager** tab. You type a description or upload research papers (PDF, CSV, Markdown, plain text — up to 5 files), pick a mode, and hit Send. The system writes a validated annotation module and loads it into an editing slot. You review it, optionally iterate via follow-up messages, and click **Register** when you're satisfied.

Two modes are available:

### Simple mode — single agent, ~2 minutes

A single Gemini Pro agent handles everything: queries biomedical databases (EuropePMC, Open Targets, BioRxiv, Ensembl), extracts variants with per-genotype weights, validates the output, writes `module_spec.yaml` + `variants.csv` + `studies.csv` + `MODULE.md`, and optionally generates a logo. If validation fails, the agent self-corrects and retries up to 10 iterations.

Good for: single well-defined papers, quick iteration, simple trait panels.

### Research team mode — multi-agent, ~7–8 minutes

A coordinated team of agents:

| Agent | Role | Model |
|-------|------|-------|
| PI (Principal Investigator) | Delegates tasks, synthesizes consensus, writes the final module, calls all write/validate/register tools | Gemini Pro |
| Researcher 1 | Independent literature research via BioContext MCP. Always present. | Gemini Pro |
| Researcher 2 | Same role, different LLM — model diversity reduces systematic blind spots. Present if `OPENAI_API_KEY` is set. | GPT |
| Researcher 3 | Same role, third perspective. Present if `ANTHROPIC_API_KEY` is set. | Claude Sonnet |
| Reviewer | Checks variant integrity, provenance, weight consistency, PMID validity via Google Search. | Gemini Flash |

Minimum team (Gemini key only): PI + 1 Researcher + Reviewer = 3 agents.  
Maximum team (all three keys): PI + 3 Researchers + Reviewer = 5 agents.

The PI dispatches all Researchers simultaneously. Each independently queries the databases. The PI then synthesises by consensus:
- Variants confirmed by ≥2 researchers → high confidence → include
- Variants from only one researcher → scrutinise; omit unless ≥2 strong PMIDs support them
- Weight disagreements → use median estimate

The synthesised draft goes to the Reviewer, which fact-checks via Google Search and returns a structured `ERRORS / WARNINGS / OK` report. The PI fixes all errors, addresses warnings, then writes and registers the module.

There are no human-approve/reject steps between phases. After completion, the module is in the editing slot and you can iterate via follow-up chat.

Good for: complex topics spanning multiple papers, large variant sets from GWAS supplementaries, cases where you want cross-model validation.

---

## Scenario 1 — Solo agent: `familial_longevity`

**Source:** Putter et al. (2025), "Rare longevity-associated variants including a reduced-function mutation in cGAS, identified in multigenerational long-lived families" (bioRxiv, DOI: 10.1101/2025.12.04.689698)

**User input:**
```
I want you to create a module based on the attached articles
```
(with `Putter_longevity_variants_21.pdf` attached, single agent mode selected)

**Total runtime: ~107 seconds**

### What the agent did

| Time | Action | Detail |
|------|--------|--------|
| 0.0s | Start | Gemini Pro agent + BioContext MCP (30+ tools) + 5 module-writer tools loaded |
| 12.7s | `query_open_targets_graphql` | Queried Open Targets for variant–disease associations on CGAS gene |
| 23.0s | `get_europepmc_articles` | Searched EuropePMC for supporting cGAS-STING and cellular senescence literature |
| 28.9s | `get_biorxiv_preprint_details` | Fetched full preprint metadata (DOI, authors, abstract) |
| 56.4s | `get_europepmc_articles` | Second search for linkage variants: SH2D3A, RARS2, SLC27A3 |
| 79.5s | `write_spec_files` | Wrote `module_spec.yaml` + `variants.csv` (11 rows, 4 genes) + `studies.csv` |
| 85.0s | `validate_spec` | **VALID** — 11 variant rows, 10 unique rsids, 2 categories |
| 93.8s | `write_module_md` | Wrote `MODULE.md` with design decisions and changelog |
| 106.5s | `generate_logo` | Attempted logo generation (API error — model unavailable; noted in log) |
| ~107s | **Complete** | Module in editing slot |

### Key decisions the agent made

- Identified **cGAS rs200818241** (D452V missense) as the primary variant. Assigned +0.8 (heterozygous) and +1.2 (homozygous) based on functional evidence that the T→A mutation destabilises the cGAS protein and dampens cGAS-STING innate immune signalling, delaying cellular senescence.
- Added three supporting rare variants from Leiden Longevity Study linkage analysis (**SH2D3A rs146711285**, **RARS2 rs1209730474**, **SLC27A3 rs535256255**) with more conservative weights (+0.5/+1.0) reflecting co-segregation signal without individual functional validation.
- Chose `heart-pulse` icon and teal (`#00b5ad`) colour — appropriate for longevity/protective traits.

### Final output

`module_spec.yaml`:
```yaml
name: familial_longevity
version: 1
title: "Familial Longevity & cGAS-STING Signalling"
description: "Rare protective variants in cGAS and other genes associated with familial longevity and delayed cellular senescence."
icon: heart-pulse
color: "#00b5ad"
genome_build: GRCh38
```

`variants.csv` (excerpt):
```csv
rsid,genotype,weight,state,conclusion,gene,phenotype,category
rs200818241,T/T,0,neutral,"Typical cGAS activity.",CGAS,Longevity,Familial Longevity
rs200818241,A/T,0.8,protective,"CGAS D452V heterozygote; reduced cGAS-STING signalling, delayed cellular senescence.",CGAS,Longevity,Familial Longevity
rs200818241,A/A,1.2,protective,"CGAS D452V homozygote; significantly dampened innate immune activity, strong longevity association.",CGAS,Longevity,Familial Longevity
```

12 rows total across 4 genes (CGAS, SH2D3A, RARS2, SLC27A3), 3 genotype rows per variant. **No manual edits required.**

---

## Scenario 2 — Research team: `latest_longevity` v1

**Sources:**
- Putter et al. (2025) — cGAS longevity variant and linkage panel (PMID 41427385)
- Sheikholmolouki et al. (2025) — SIRT6 rs117385980 and its antagonistic pleiotropic relationship with frailty and extreme longevity (PMID 41249831)

**User input:**
```
Create a latest_longevity module, based on the attached articles. Let the module icon contain year 2025.
```
(two PDFs attached, Research Team mode selected)

**Total runtime: ~461 seconds (~7.7 minutes)**

### Phase 1 — Parallel research (0–136s)

The PI dispatched identical research tasks to all three Researchers simultaneously at t=21.5s. Each researcher independently queried EuropePMC, Open Targets, and BioRxiv:

| Time | Actor | Action |
|------|-------|--------|
| 21.5s | PI | `delegate_task_to_member → researcher-1` (Gemini) |
| 21.5s | PI | `delegate_task_to_member → researcher-2` (GPT-4.1) |
| 21.5s | PI | `delegate_task_to_member → researcher-3` (Claude Sonnet) |
| 23.5s | R1, R2, R3 | All three spin up BioContext MCP tool stacks in parallel |
| 72.7s | R1 | `get_europepmc_articles` — searched for SIRT6 rs117385980 literature |
| 74.6s | R1 | Confirmed PMID 41249831 (SIRT6 frailty study) |
| ~52–110s | R2, R3 | Parallel queries on Putter et al. variants |
| 136.5s | PI | All three researcher tasks complete |

### Phase 2 — Consensus synthesis and review (136–234s)

The PI compared outputs and applied consensus rules:
- **High confidence** (≥2 researchers agreed): cGAS rs200818241, SIRT6 rs117385980, linkage variants (NUP210L, SLC27A3, CD1A, IBTK, RARS2, SH2D3A)
- **Weight decisions**: cGAS het +0.8/hom +1.2 (functional evidence); SIRT6 het −0.5/hom −1.0 (inverse association with extreme age, stop-gained variant — antagonistic pleiotropy); linkage variants ±0.4–0.5 (conservative, no individual functional validation)

At t=175.7s, the draft went to the Reviewer. The Reviewer used Google Search and returned:
- Confirmed cGAS rs200818241 as well-supported across multiple sources
- Confirmed SIRT6 rs117385980 antagonistic pleiotropy interpretation
- Flagged linkage variants (NUP210L, SLC27A3, CD1A, IBTK, RARS2, SH2D3A) as single-study findings — recommended conservative weights, which the PI retained

### Phase 3 — Output generation (234–461s)

| Time | Actor | Action |
|------|-------|--------|
| 275.6s | PI | `write_spec_files` — 34 variant rows, 8 genes, 2 categories |
| 280.1s | PI | `validate_spec` — **VALID** |
| 288.9s | PI | `write_module_md`, `generate_logo`, `register_module` — launched in parallel |
| 461.3s | PI | All complete. Logo: 2025 genetics motif, teal/green. Module registered. |

### Final output

`module_spec.yaml`:
```yaml
name: latest_longevity
version: 1
title: "Latest Longevity"
description: "Latest rare and protective variants linked to extreme longevity and frailty in 2025."
icon: heart-pulse
color: "#21ba45"
genome_build: GRCh38
```

`variants.csv`: 34 rows across 8 genes in 2 categories:
- *Familial Longevity* (7 genes × 3 genotypes): CGAS, NUP210L, SLC27A3 (×2 variants), CD1A, IBTK (×2 variants), RARS2 (×2 variants), SH2D3A
- *Frailty and Longevity* (1 gene × 3 genotypes): SIRT6

Note on SIRT6: rs117385980 is a stop-gained variant showing **antagonistic pleiotropy** — associated with frailty risk in the general population but enriched in centenarians. The agent correctly assigned negative weights (−0.5 het, −1.0 hom) reflecting its inverse association with extreme longevity.

**No manual edits required.**

---

## Scenario 3 — Research team: `latest_longevity` v2 (iterative update)

With `latest_longevity v1` loaded in the editing slot, the user uploaded a third paper and its large supplementary data:

**Sources:**
- Dinh et al. (2025), "Genetic links between multimorbidity and human aging" — multivariate GWAS identifying shared cardiometabolic liability (mvARD) inversely correlated with extreme longevity
- Supplementary CSV with ~260 lead SNPs from the mvARD GWAS

**User input:**
```
I want now to update the module based on this article and supplementary materials for it (contains ~260 rsids).
```

**Total runtime: ~418 seconds (~7 minutes)**

### What the team did

The same 5-agent team re-assembled with the v1 module files in context. The PI dispatched all three researchers at t=31.6s with identical tasks focused on identifying the most pleiotropic and well-characterised SNPs from the ~260 candidates.

After consensus synthesis and Reviewer confirmation, the PI selected the **five most pleiotropic SNPs**:

| rsid | Locus | Signal |
|------|-------|--------|
| rs964184 | ZNF259/APOA5 | Triglycerides and metabolic syndrome |
| rs12740374 | SORT1 | LDL cholesterol — protective allele |
| rs7310615 | SH2B3 | Blood pressure and inflammation |
| rs28601761 | TRIB1 | Hepatic fat and cardiometabolic risk |
| rs6547692 | GCKR | Triglyceride elevation and metabolic syndrome |

The Reviewer confirmed all five as well-documented in GWAS literature and accepted the weighting approach for inverse longevity correlation.

### Final output: v2

- **49 variant rows** total: all 34 from v1 retained, plus 15 new rows (5 mvARD SNPs × 3 genotypes each) in a new **"mvARD"** category
- `studies.csv`: 16 rows — all 11 from v1 plus 5 new entries linking mvARD SNPs to Dinh et al. 2025
- `MODULE.md` updated with new data source and v2 changelog
- Logo correctly **reused from v1** — the agent detected it existed and the module theme was unchanged

**No manual edits required.**

---

## Comparison across all three scenarios

| | Scenario 1 (Solo) | Scenario 2 (Team, new) | Scenario 3 (Team, edit) |
|---|---|---|---|
| Mode | Single agent | Research team | Research team |
| Input | 1 PDF | 2 PDFs | 1 PDF + 1 CSV (~260 rows) |
| Prompt | "Create a module from the attached article" | "Create a latest_longevity module…" | "Update the module based on this article…" |
| Duration | ~107s | ~461s | ~418s |
| Researchers | — (agent self-researches) | 3 parallel (Gemini + GPT + Claude) | 3 parallel (same) |
| Reviewer | — | Yes (Google Search) | Yes (Google Search) |
| Variant rows | 12 (4 genes) | 34 (8 genes, 2 categories) | 49 (13 genes, 3 categories) |
| External DB calls | 4 | 7+ per researcher | 8+ per researcher |
| Manual edits needed | None | None | None |
| Logo generated | Attempted (API error) | Yes (2025 genetics motif) | Skipped (reused v1) |

### Patterns

**Single agent is fast and good enough for focused sources.** If you have one well-defined paper and want a module in 2 minutes, solo mode is the right choice.

**Team mode provides depth and cross-model validation.** Using different LLMs for each Researcher (Gemini, GPT, Claude) introduces model diversity — each brings different strengths in literature interpretation, reducing systematic blind spots. The majority-vote consensus and Reviewer fact-checking act as built-in quality filters.

**Iterative editing works cleanly.** Scenario 3 demonstrates that the system can extend an existing module incrementally, preserving all prior content and reusing assets (logo) when appropriate. This mirrors how real research curation works.

---

## Example: AI-generated module from a prompt (no paper)

You don't need a PDF. A text description is enough for well-studied variants:

**Prompt:**
```
Create a module for MTHFR methylation variants. Include rs1801133 (C677T) and rs1801131 (A1298C). Focus on homocysteine metabolism and cardiovascular risk.
```

**Resulting `module_spec.yaml`:**
```yaml
schema_version: "1.0"
module:
  name: mthfr_methylation
  version: 1
  title: "MTHFR Methylation Variants"
  description: "MTHFR variants affecting homocysteine metabolism and cardiovascular risk."
  report_title: "Methylation & Cardiovascular Risk"
  icon: dna
  color: "#21ba45"
defaults:
  curator: ai-module-creator
  method: literature-review
  priority: medium
genome_build: GRCh38
```

**Resulting `variants.csv`:**
```csv
rsid,genotype,weight,state,conclusion,gene,phenotype,category
rs1801133,C/C,0,neutral,"Typical MTHFR C677T activity; normal homocysteine metabolism.",MTHFR,Homocysteine Metabolism,Methylation
rs1801133,C/T,-0.6,risk,"MTHFR C677T heterozygote; ~35% reduced enzyme activity; mildly elevated homocysteine risk.",MTHFR,Homocysteine Metabolism,Methylation
rs1801133,T/T,-1.1,risk,"MTHFR C677T homozygote; ~70% reduced enzyme activity; significantly elevated cardiovascular risk.",MTHFR,Homocysteine Metabolism,Methylation
rs1801131,A/A,0,neutral,"Typical MTHFR A1298C activity.",MTHFR,Homocysteine Metabolism,Methylation
rs1801131,A/C,-0.4,risk,"MTHFR A1298C heterozygote; mildly reduced enzyme activity.",MTHFR,Homocysteine Metabolism,Methylation
rs1801131,C/C,-0.8,risk,"MTHFR A1298C homozygote; compound effect when combined with C677T.",MTHFR,Homocysteine Metabolism,Methylation
```

---

## Agent flow diagrams

### Simple mode

```
User types prompt
      │
[optional] Attach PDF/CSV
      │
Solo Agent (Gemini Pro)
  ├── BioContext MCP (variant lookup, EuropePMC, Open Targets, Ensembl, BioRxiv)
  ├── write_spec_files
  ├── validate_spec ──→ [errors?] ──→ self-correct (up to 10 iterations)
  ├── write_module_md
  └── generate_logo
      │
Module in Editing Slot
      │
User: Register / Download / Iterate via chat
```

### Research team mode

```
User types prompt + optional attachments
      │
PI (Gemini Pro) receives task
      │ delegates simultaneously
      ┌────────────┬────────────┬────────────┐
      ▼            ▼            ▼
Researcher 1    Researcher 2    Researcher 3
(Gemini Pro)    (GPT, optional) (Claude, optional)
      │            │            │
  variant list  variant list  variant list
      └────────────┴────────────┘
                   │
      PI synthesises consensus
      (majority vote on variants; median weights)
                   │
          Draft CSV → Reviewer (Gemini Flash)
          checks: provenance, rsid format, weights, PMIDs
          returns: ERRORS / WARNINGS / OK
                   │
          PI fixes errors & addresses warnings
                   │
  write_spec_files → validate_spec → write_module_md → generate_logo → register_module
                   │
          Module in Editing Slot
                   │
      User: Register / Download / Iterate via chat
```

---

## Limitations

- **Max 5 file attachments** per message. Supported formats: PDF, CSV, Markdown, plain text. No DOCX or HTML.
- **BioContext MCP budget**: each Researcher is limited to 9 tool calls to prevent context overflow. Very large variant sets may be truncated.
- **No human-in-the-loop** between PI→Researcher→Reviewer phases. If the PI misinterprets the task, use a follow-up chat message to correct it.
- **Gemini key required.** OpenAI and Anthropic keys add Researchers but are optional.
- **Only GRCh38 and GRCh37** genome builds in `module_spec.yaml`.
- **Only SNPs/indels** — structural and copy-number variants are not supported.
- **No persistent audit trail** — intermediate researcher outputs are visible in the chat session only and are not saved across page reloads.
- **Logo generation** requires Gemini API; silently skipped if the API call fails.

---

## Further reading

- [AI_MODULE_CREATION.md](AI_MODULE_CREATION.md) — DSL spec, compiler internals, registry API, Agno agent architecture
- [HF_MODULES.md](HF_MODULES.md) — module discovery from HuggingFace and other remote sources
- [ARCHITECTURE.md](ARCHITECTURE.md) — overall pipeline and data flow
