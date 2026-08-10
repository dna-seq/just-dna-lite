# Superhuman module — PMID backfill + March 2026 refresh (execution plan)

**For a supervised (foreground) agent — not a background job.** Phases 2–3 require literature
judgment and web access; a background agent could hallucinate PMIDs or drift. Run it interactively
with the two human checkpoints below.

## The debt

`superhuman` is the one ported Generation-I module that can't be published: its evidence column
(`references`) holds **dbSNP URLs, not PubMed IDs**, so it has zero grounded studies and fails the
mandatory-grounding rule (and the ROADMAP 0.2 digit-only `pmid` rule). This is old backlog — the
protective-allele citations were meant to be filled in by hand (underpaid link-filling) and never
were. The canonical source list is the Church-lab **Protective Alleles** page
(`https://arep.med.harvard.edu/gmc/protect.html`), but it itself only links a PMID for **6** of its
89 entries — so most citations must be researched and **verified**, not scraped. Separately: refresh
the module with protective-allele findings published up to **March 2026**.

## Inputs (already prepared on disk — deterministic)

Under `data/interim/v1_port/_sources/` (gitignored; regenerate by re-downloading the URL above):
- `arep_protect.html` — raw snapshot of the source page (22,915 bytes).
- `arep_protective_alleles.csv` — 92 rows: `gene, genotype, protective_effect, potential_negatives,
  arep_pmids`. Only 6 rows carry a PMID (APOE, ARHGAP11B, FBXO32, PDE4B, TPH2, TRIM63).
- `superhuman_genes.csv` — superhuman's **33 genes** with variant counts (1,243 variants total).
- `superhuman.sqlite` (`just_superhuman__superhuman.sqlite`) — source table: `rsid, gene, genotype,
  zygosity, superability, adverse_effects, references(URLs)`.

Current ported spec: `data/interim/v1_port/superhuman/` (`module_spec.yaml`, `variants.csv` with
1,243 rows, `studies.csv` empty).

The 33 superhuman genes: NTRK1, SCN9A, RIMS1, MSTN, HBB, GHR, CFTR, PCSK9, APOL1, CCR5, ABCC11,
SLC30A8, PRNP, PDE10A, NPSR1, LRP5, IL23R, IFNL4, IFIH1, HSD17B13, GLUK4, FUT2, FAAH, EPOR, EPAS1,
EGLN1, BHLHE41, BDKRB2, APP, APOE, APOA2, ANGPTL3, ADRB1. Most have famous founding papers
(PCSK9 LOF→low LDL, CCR5-Δ32→HIV resistance, MSTN→muscle, SCN9A→pain insensitivity, etc.).

## Guardrails (MANDATORY — the reason this is supervised)

1. **Never fabricate a PMID.** Every PMID must be fetched and confirmed via PubMed E-utilities:
   `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=<PMID>&retmode=json`
   (exists + title), and `efetch` (abstract) to confirm the paper actually supports the **gene +
   protective phenotype**. Record the fetched title with each PMID.
2. **No real PMID → leave ungrounded.** If a gene/variant has no verifiable citation, drop it from
   `studies.csv` and log it. Do not invent, and do not reuse the dbSNP URL as a "pmid".
3. **digit-only PMIDs** (`^\d+$`) — the ROADMAP 0.2 rule; enforced by a final check.
4. **Freeze the research into a version-controlled CSV** so the build is reproducible afterward (see
   Phase 4). The one-time, non-deterministic lookup happens once, is human-reviewed, then never re-run.
5. **Two human checkpoints** (after Phase 2 and Phase 3) before anything is compiled or published.

## Phase 1 — deterministic grounding from AREP
Parse `arep_protective_alleles.csv`; for the 6 rows with `arep_pmids`, verify each PMID (guardrail 1)
and attach. Join AREP↔superhuman by gene symbol, normalizing case and trailing spaces (e.g.
`'BHLHE41 '`). Only `APOE` overlaps directly — so this phase alone grounds ~1 gene; that's expected.

## Phase 2 — per-gene literature curation (supervised, web access required)
For each of the 33 superhuman genes without a verified PMID, find the **primary founding paper** for
the protective phenotype (use the `superability`/`protective_effect` text as the phenotype). Verify
each candidate against PubMed (guardrail 1). Prefer: (a) AREP-linked PMID → (b) primary/founding
paper → (c) authoritative review. Produce a table `gene → [PMID, title, why-it-supports]`.
**► HUMAN CHECKPOINT A: review the gene→PMID table before continuing.**

## Phase 3 — March 2026 refresh (supervised)
Search for protective-allele findings published through March 2026: (a) newer/better citations for
the 33 existing genes, and (b) new protective genes/variants (including AREP entries not yet in
superhuman, and anything post-dating the module). For each addition, obtain rsid(s) from dbSNP/Ensembl
and a verified PMID. Keep additions conservative and cited.
**► HUMAN CHECKPOINT B: review additions (new genes/variants/PMIDs) before continuing.**

## Phase 4 — freeze curation, rebuild spec (deterministic after this point)
Write the reviewed result to a **tracked** CSV, e.g.
`just-dna-pipelines/src/just_dna_pipelines/v1_port/data/superhuman_pmid_curation.csv` with columns:
`gene, rsid (optional/blank=all rsids for gene), pmid, population, p_value, conclusion, study_design,
source (arep|primary|review), verified_title`. Then extend the superhuman adapter (`adapters.py`
`adapt_superhuman`) to **merge this curation**: for each variant whose gene (or rsid) has verified
PMIDs, emit one `StudyRow(rsid, pmid, …)` per PMID. Variants with no curated PMID stay ungrounded
(omitted from studies). This keeps `pipelines v1-port port --module superhuman` fully reproducible —
the non-deterministic research is now a frozen, auditable input, not a live search.

## Phase 5 — compile, verify, publish
1. `uv run pipelines v1-port port --module superhuman --compile` → produces the parquets + manifest.
2. Verify: `validate_spec` passes; `studies.csv` non-empty; every `pmid` matches `^\d+$`; studies
   reference rsids present in `variants.csv`. Report grounded-vs-total variant counts.
3. Publish (both stores, matching the other five):
   - HF: `uv run pipelines v1-port publish superhuman`
   - Marketplace: `export MARKETPLACE_URL=https://module-registry.just-dna.life; uv run pipelines
     marketplace publish just-dna-seq superhuman <version> data/interim/v1_port/superhuman`
4. Update the gap notes: mark superhuman resolved in `data/interim/v1_port/GAPS.md` and
   `docs/V1_PARITY.md`.

## Open decisions (confirm with the user before Phase 5)
- **Version:** `1.1.0` if this is only backfill; `2.0.0` if the March 2026 refresh adds genes/variants
  (recommended, since it changes the variant set). The other five modules are at `1.0.0`.
- **Variant scope:** superhuman currently lists **all dbSNP variants in 33 genes** (1,243), so a
  gene-level PMID would ground every variant in a gene — scientifically loose. Consider restricting
  to the specific protective alleles AREP names (e.g. PCSK9 LOF variants, MSTN `-/-`) during the
  refresh. Recommend narrowing; confirm with the user.
- **Agent web access:** Phases 2–3 require PubMed/web access; ensure the executing agent has it.

## Why not a background agent
Phases 2–3 are judgment- and web-dependent (is this the right paper? does it support the claim?). A
background agent can't be checkpointed and is prone to inventing plausible-looking PMIDs — exactly
the failure this plan guards against. Run it foreground with checkpoints A and B; everything before
Phase 2 and after Phase 4 is deterministic.
