# **Just-DNA-Lite Manuscript Strategy (v0.2 — post-split)**

**Supersedes:** the v0.1 "Just-DNA-Lite Manuscript Strategy" (single-manuscript assessment).
**What changed:** the single manuscript has been split into two companion preprints. This document restates the strategy around that split. The v0.1 journal analysis is retained where still valid and re-mapped to the two papers.

## **Executive Verdict**

The v0.1 review's central finding was that the manuscript's largest weakness was **scope**: it tried to be a software paper, a PRS methods paper, an AI-agent paper, an ethics essay, a longevity paper, and a platform manifesto at once, and its top-priority fixes were (1) choose one lead claim and (2) harden the AI claims into a measured pipeline with precision/recall, expert adjudication, and solo-vs-team ablation.

We now resolve both by splitting into two companion manuscripts that cross-reference each other through public preprint/archive records. The chosen sequence is: post both as preprints, make the Paper 2 preprint available first so it can be cited, then submit Paper 1 first to a journal while referencing Paper 2 as the companion preprint.

- **Paper 1 — Just-DNA-Lite (platform).** *Just-DNA-Lite: a Local-First, Open-Source Platform for Personal Genome Annotation and Polygenic Risk Scoring.* The local platform and its ecosystem infrastructure: annotation pipeline, just-prs computation library, web UI, no-code module format, separate module-format/compiler contract (`just-dna-format`), and module marketplace/catalog API (`just-dna-marketplace`). Submitted **first to a journal**, after Paper 2 exists as a preprint citation.
- **Paper 2 — just-dna-agents (`dna-agents` package).** *just-dna-agents: an Agentic Toolkit for Evidence-Grounded Personal Genomics Research.* The agentic layer over those engines: `just-prs-mcp` folds in, so it exposes and orchestrates annotation, PRS, and other models for AI assistants and additionally creates validated modules. Posted **first as a citable preprint/archive record**; full journal version follows after evaluation is strengthened.

**Boundary (updated):** because `just-prs-mcp` merges into `dna-agents`, *all* MCP/agentic access consolidates into Paper 2. Paper 1 = the local platform + compute engines; Paper 2 = the agentic toolkit that orchestrates and extends them. This supersedes the earlier "creation vs. access" wording.

The heavy AI-benchmarking demand — the single biggest source of remaining work — moves entirely to Paper 2 and off Paper 1's critical path. Paper 1 keeps only its already-strong, mature evidence.

After reviewing the actual v0.2 drafts, the split is still the right strategy, but the drafts have drifted from the strategy in two ways:

1. **Paper 1 still contains too much agentic material.** The abstract, architecture section, PRS access subsection, and a full AI-module-creation section repeatedly point to AI assistants and MCP. That makes the platform paper look like it is still trying to carry the AI paper's novelty, even while deferring the evidence.
2. **Paper 2 is promising a broader unified agentic toolkit than the current evidence supports.** Its deterministic compiler/validator story is strong, but the creation-accuracy table is still pending, and several access-surface claims should only remain if the repository and demo can show them.

Updated readiness: Paper 1 readiness is **Medium-High**, not High, until AI content is reduced and factual/support claims are tightened. Paper 2 readiness is **Medium-Low for journal submission** and **Medium for an honest preprint**, provided all pending evaluation placeholders are either filled or explicitly converted into an evaluation plan. Scope-control risk is **Medium**, because the split works on paper but Paper 1 currently violates the boundary in execution.

## **New criticism from the v0.2 drafts**

### Paper 1 — Just-DNA-Lite

**Main concern: the platform paper still reads partly like an AI-agent paper.** Paper 1 should be able to stand without Paper 2. Right now it mentions AI assistants in the abstract, scope paragraph, architecture design principles, PRS access subsection, module-ecosystem section, AI module-creation section, conclusion, contribution statements, and code-availability table. This repetition reintroduces the original scope problem and invites reviewers to ask for AI validation inside Paper 1.

**Adjustment:** keep one short "availability pointer" to the companion toolkit in the abstract or discussion, one brief feature-level paragraph in the platform section if the in-app creator is already demonstrable, and move the rest to Paper 2. Delete or heavily compress Paper 1 §3.2.1 and §4 unless the paper is being deliberately submitted as a broader ecosystem paper rather than a platform paper.

**Do not treat newly added support as a blocker.** The v0.2 draft's support-status claims are current: `uv run serve` exists as the single-process production/server command; GRCh37/hg19 liftover support has been added; consumer microarray support exists experimentally; and the module ecosystem may include AI-generated modules such as "Longevity Variants 2026" alongside expert-curated modules. These are not blockers.

**Adjustment:** keep the manuscript precise about support levels rather than downgrading implemented work. Say GRCh38 is the primary supported build; GRCh37/hg19 is handled via liftover; consumer microarray support is experimental and lower-coverage; T2T remains not yet supported unless implementation evidence changes. Keep AI-generated modules explicitly labelled as AI-generated research-use drafts requiring review.

**Novelty risk is now more manageable if the marketplace and format contract are included.** Once agentic access moves out, Paper 1's novelty must be defended as a coherent platform architecture, not as "we used Polars/DuckDB/Dagster." The addition of `just-dna-format` and `just-dna-marketplace` strengthens this: Paper 1 is no longer only a local app, but an extensible annotation ecosystem with a formal module contract, reference compiler/integrity layer, and catalog/publish/download API. The draft still needs a compact state-of-the-art comparison showing what combination is missing from VEP, ANNOVAR, OpenCRAVAT/OakVar, Galaxy, PRSice, and PGS Catalog tooling.

**Adjustment:** add a small comparison table before submission. The columns should be concrete: local-first GUI, WGS VCF annotation, PRS computation, no-code module creation/registration, formal module schema/manifest contract, module catalog/marketplace, fsspec module discovery, transparent per-variant outputs, reproducible benchmarks, and research-use disclaimers.

**BioRxiv/medRxiv risk remains.** The prior rejections make it risky to depend on bioRxiv/medRxiv for companion DOI mechanics. Paper 1 is safest when framed as a bioinformatics methods/software paper, not as a personal genomic medicine or gene-disease interpretation paper.

**Adjustment:** avoid any preprint strategy that requires bioRxiv/medRxiv acceptance. Use arXiv for rapid public posting and Zenodo/OSF for DOI-style archival citation if a DOI is needed before journal submission.

### Paper 2 — just-dna-agents

**Main concern: the abstract overpromises relative to the pending evidence.** The paper claims a unified toolkit for PRS, annotation, graphics, interpretation prompts, orchestration, and module creation. That can be a strong paper, but only if those surfaces exist in `dna-agents`/`dna-agents-mcp` and are documented, runnable, and demoable. Otherwise reviewers will see a roadmap mixed with results.

**Adjustment:** split Paper 2 claims into "implemented and evaluated," "implemented but not yet benchmarked," and "planned integration." Only the first category should appear in the abstract as a result. If `just-prs-mcp` folding into `dna-agents` is not complete, describe it as planned consolidation, not current architecture.

**The evaluation section is the paper's gate.** Compiler round-trip validation is complete and credible, but creation accuracy is still a placeholder. A table with pending recall / PMID precision / weight-sign accuracy cannot go into a submission draft except as an explicit protocol. The three illustrative runs are useful, but anecdotal.

**Adjustment:** before any journal submission, run the fixture evals and report at least variant recall, genotype completeness, PMID precision, weight-sign accuracy, runtime, and manual correction count for solo vs. team. If results are not ready, publish a lean preprint as a toolkit/protocol paper with no quantitative creation-performance claims.

**The consensus mechanism must stay hypothesis-level until measured.** The draft correctly says consensus is intended to reduce errors, but a few phrasings still imply effectiveness. Multi-model agreement is a design precaution; it is not a result until solo-vs-team and cross-model ablations are executed.

**Adjustment:** phrase consensus as "designed to test whether model diversity reduces errors" until the ablation table exists. Do not say it "reduces hallucination" without measured evidence.

**Paper 2's durable contribution should be narrower and stronger.** The most defensible contribution is: a deterministic genetics-module DSL/compiler with Ensembl-backed validation, exposed to agents, plus an evaluation framework for AI-generated module creation. The broader MCP orchestration layer is valuable, but it should not dilute the paper unless it is mature.

**Adjustment:** if the unified MCP layer is not fully ready, make the journal Paper 2 a "validated module creation" paper and keep "unified personal-genomics agent toolkit" as the ecosystem framing. If it is ready, keep the current title but add an executable demonstration workflow and tool-schema appendix.

## **Why the split resolves the v0.1 criticisms**

| v0.1 criticism | How the split addresses it |
|---|---|
| Too many centerpieces (platform + PRS + AI + ethics + longevity) | Paper 1 has one lead claim (local platform + compute engines). Agentic access and AI creation are pointers/features only, not pillars. Longevity is demoted to an example module. Ethics section shortened. |
| AI module validation too thin; needs eval set, precision/recall, expert adjudication, solo-vs-team ablation | This entire burden moves to Paper 2, which is built around exactly that evaluation framework (fixtures `mthfr_nad`, `cyp_panel`; variant recall / PMID precision / weight accuracy; solo-vs-team). |
| Clinical/regulatory sensitivity of the right-to-read section | Shortened and made empirical in Paper 1 §6.3; fuller argument reserved for supplement. |
| AI/MCP content ages fast | Isolated in Paper 2, which can be posted quickly and anchors on durable ideas (validation-gated toolkit, consensus design, eval framework), keeping model names in the repo docs. |
| Novelty risk ("just integration of Polars/DuckDB/Dagster") | With agentic access moved to Paper 2, Paper 1's novelty rests on modules-as-data + formal module contract (`just-dna-format`) + marketplace/catalog API (`just-dna-marketplace`) + fsspec ecosystem + structural local privacy + reproducible benchmarks. Mitigate with a state-of-the-art comparison table. |

## **The split boundary (local platform vs. agentic layer)**

Because `just-prs-mcp` folds into `dna-agents`, *all* MCP/agentic access lives in Paper 2. (This supersedes the earlier "creation vs. access / engine vs. front door" framing.)

- Paper 1 keeps: platform, annotation pipeline, web UI, the just-prs **computation** engine and its concordance benchmarks, the no-code module format and separate `just-dna-format` schema/compiler contract, the `just-dna-marketplace` catalog/publish/download API, mature annotation-speed benchmarks, default modules as examples, privacy/philosophy (shortened). It mentions agentic access only as a **one-line pointer** to the companion toolkit.
- Paper 1 mentions AI module creation only as a feature: what it does, that outputs are deterministic specs validated/compiled before registration, the `curator` provenance field, and a deferral. **No AI performance claims** (no accuracy numbers, no "reduces hallucination", no "outperforms").
- Paper 2 owns: the unified MCP toolkit (annotation + PRS via folded-in `just-prs-mcp` + other models), agent orchestration, graphics/interpretation prompts, the Agno creation engine + consensus, the deterministic compiler, cross-client access, and all creation-side evaluation.

Two-layers-of-one-system framing (local platform + engines vs. the agentic toolkit that orchestrates/extends them) is what makes this two papers rather than salami-slicing: distinct contributions, distinct audiences (local/graphical user vs. assistant-driven power user).

## **Claims discipline (the rule that makes deferral defensible)**

Claims in Paper 1 must not exceed the evidence retained in Paper 1. Defer the AI benchmarks *and* the AI performance claims together. Paper 1 may reassure that generated modules are checked before registration; it may not quantify creation accuracy. Paper 1 should also avoid relying on the companion paper for its central novelty. A companion citation can support availability and architecture, but the platform paper must be publishable from its own software contribution: local execution, transparent annotation joins, no-code modules, formal module specification/integrity manifests, marketplace/catalog API, PRS concordance, and reproducible performance.

Claims in Paper 2 must be separated by maturity:

- **Can be claimed as results now:** deterministic spec validation/compilation, round-trip tests, module format, CLI/Python/MCP compiler tools, if these are documented and reproducible.
- **Can be claimed only after execution:** creation accuracy, solo-vs-team advantage, cross-model consensus benefit, hallucination reduction, PMID precision, weight-direction accuracy.
- **Should be framed as roadmap unless implemented:** fully unified PRS + annotation + graphics + interpretation orchestration across all MCP clients.

## **Cross-reference mechanics**

- **Chosen sequence:** post the Paper 2 `dna-agents` manuscript first as a lean but honest preprint/archive record. Then submit Paper 1 first to a journal, citing Paper 2 as the companion preprint for the agentic layer and AI module-creation details. Paper 1 must not depend on Paper 2 for its core empirical claims.
- **Preprint venue caution:** do not depend on bioRxiv/medRxiv acceptance for the citation chain. Use arXiv for rapid public citability, and create a Zenodo/OSF archival record if a DOI-like citation is needed before journal submission.
- **Paper 2 journal timing:** expand Paper 2 into its journal version after fixture evals, solo-vs-team ablations, and repository documentation are complete.
- Write shared background (privacy, right-to-read, module format) *fresh* in each paper — cross-reference, never copy — to avoid self-similarity flags.

## **Journal targets**

### Paper 1 — Just-DNA-Lite (platform)

Unchanged from v0.1's core recommendation, but Paper 1 needs cleanup before it fully earns this positioning.

| Journal | Recent JIF | Fit | Positioning |
|---|---|---|---|
| **Bioinformatics** | 5.4 | **Best realistic fit** | Lead with system-level novelty (no-code modules-as-data, formal module contract, marketplace/catalog API, fsspec ecosystem, structural local privacy, fast benchmarked PRS/annotation) as one coherent local-first architecture. |
| GigaScience | 3.9 | Strong open-science fit | Verify editorial stability; prepare an exceptional FAIR/reproducibility package. |
| BMC Bioinformatics | 3.3 | Safest software-paper fit | Fallback if speed/fit matter more than prestige. |
| Genome Biology | 9.4 | Reach | Only with broader validation and a compact state-of-the-art comparison table. |
| PLOS Computational Biology | 3.6 | Strong open-source fit | Frame as open-source infrastructure; ship test data + exact reproducibility commands. |

If IF > 5 is mandatory: Bioinformatics first, Genome Biology as reach. If IF > 3 is acceptable: GigaScience → PLOS Comp Biol → BMC Bioinformatics → Bioinformatics.

### Paper 2 — just-dna-agents (agentic toolkit / validated module creation)

| Journal | Fit | Positioning |
|---|---|---|
| BMC Bioinformatics | Safe software/methods fit | Lead with deterministic validation/compilation, agent-assisted module creation, and the evaluation protocol/results. |
| Bioinformatics | Good if evals are strong | Position as a validated agentic bioinformatics workflow only if fixture results and ablations are complete. |
| AI-in-science / agents venue (e.g. an applied-ML or reproducibility venue) | Alternative | Emphasize the durable contribution: validation-gated agents for literature-to-module generation, with measured consensus/solo comparisons. |

Anchor Paper 2 on durable ideas; keep model names/versions in the repo, not as load-bearing claims. Do not force the full benchmark program before Paper 1 can move, but do not submit the journal version with placeholder evaluation numbers.

## **Remaining pre-submission work**

**Paper 1 (medium-high readiness after cleanup):**
- Cut agentic-access mentions to a single companion-toolkit pointer plus, at most, one feature-level in-app creator paragraph.
- Remove or compress Paper 1 §3.2.1 and §4; move operational details, MCP clients, orchestration, graphics, interpretation prompts, and evaluation to Paper 2.
- Keep support-status claims precise: `uv run serve` is valid, GRCh37/hg19 liftover is added, microarray support is experimental, and AI-generated modules must be labelled as such.
- Add Paper 1 sections or subsections for `just-dna-format` (schema, manifest, integrity contract, reference compiler) and `just-dna-marketplace` (catalog, publish/download API, validation/recompile boundary, yanking/versioning).
- Add a compact state-of-the-art comparison table vs. VEP/ANNOVAR/OpenCRAVAT/OakVar/Galaxy/PRSice/PGS Catalog tooling to pre-empt the novelty objection.
- Resolve residual TODOs carried from the combined manuscript: ROGEN acknowledgment text, bibliography 2022–2026 additions, and missing screenshots/figures.

**Paper 2 (preprint possible; journal needs eval execution):**
- Audit `dna-agents` and `dna-agents-mcp` against every abstract claim; downgrade anything not runnable to planned work.
- Execute fixture evals and fill Table 2 with variant recall, genotype completeness, PMID precision, weight-sign accuracy, runtime, and manual correction count.
- Add solo-vs-team and cross-model ablations before claiming any consensus benefit.
- Update `dna-agents` README/AGENTS.md to document the Agno swarm and the actual MCP surface after migration lands.
- Decide authorship order (engine led by N. Usanov).
- Expand fixtures and add an adversarial set for the journal version.

## **Open items**

- [ ] Confirm Agno migration from just-dna-lite into dna-agents complete.
- [ ] Post Paper 2 first as a lean, honest preprint/archive record.
- [ ] Submit Paper 1 first to a journal, citing the Paper 2 preprint.
- [ ] Decide arXiv/Zenodo/OSF citation path; do not depend on bioRxiv/medRxiv.
- [ ] Trim Paper 1 AI/agent sections to match the boundary.
- [ ] Keep Paper 1 support-status wording precise without treating added support as planned/future work.
- [ ] Add `just-dna-format` and `just-dna-marketplace` to Paper 1's architecture/contribution and code-availability sections.
- [ ] Run Paper 2 evals; fill placeholder tables.
- [ ] Reword shared background separately in each paper.
- [ ] Add state-of-the-art comparison table for Paper 1.
