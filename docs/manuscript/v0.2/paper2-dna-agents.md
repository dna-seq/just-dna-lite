# **just-dna-agents: an Agentic Toolkit for Evidence-Grounded Personal Genomics Research**

> **Naming:** `just-dna-agents` is the paper/product name; the software package and repository remain `dna-agents` (with the `dna-agents-mcp` server). Both names refer to the same system.

> **Draft v0.2 (Paper 2 of 2).** Companion to *Just-DNA-Lite: a Local-First, Open-Source Platform for Personal Genome Annotation and Polygenic Risk Scoring* (Kulaga et al., 2026; DOI to be assigned). Just-DNA-Lite is the local platform and the compute engines (annotation pipeline, the just-prs computation library, the no-code module format, the web UI, `just-dna-format`, and `just-dna-marketplace`); this paper is the **agentic layer over them** — a toolkit that connects the platform's code repositories, upstream MCP services, and agent-native integrations for Claude Code, Cursor, Antigravity, Codex, and similar environments so AI assistants can run validated genomic operations and create reviewable annotation modules. See `docs/manuscript/v0.2/manuscript-strategy-v0.2.md`.
>
> **Note on evaluation:** the creation-side evaluation reported here is deliberately **preliminary**. The compiler round-trip validation is complete; the creation-accuracy metrics (variant recall, PMID precision, weight accuracy) are reported on a small number of ground-truth fixtures, with a larger benchmark suite marked as in progress. Numbers flagged *[pending]* are to be filled from executed eval runs before submission.
>
> **Note on authorship:** author order to be decided; the toolkit was led by N. Usanov. Placeholder byline below.

**Authors:** Usanov Nikolay^1,2^, Kulaga Anton^2,3,4^, Borysova Olga^2^, [others TBD], Fuellen Georg^3,\*^, Tacutu Robi^4,\*^

**Affiliations:** 1. HEALES; 2. SecvADN SRL; 3. Institute for Biostatistics and Informatics in Medicine and Ageing Research, Rostock University Medical Center; 4. Institute of Biochemistry of the Romanian Academy. \* Co-supervising authors. *(Full affiliation list to be aligned with Paper 1.)*

---

## **Abstract**

Genome analysis is an iterative workflow — ask, select data, score, annotate, inspect, and revise — and it is increasingly done inside AI assistants rather than fixed graphical interfaces. In practice, users now work through Claude Code, Cursor, Antigravity, Codex, and similar agentic environments, not only through standalone web apps or MCP clients. But general-purpose language models are unreliable when used directly for genomics: they improvise unvalidated code, confuse genome builds or strands, misassign effect directions, and fabricate variant identifiers or citations. We present **just-dna-agents**, an open-source agentic workflow that keeps validated domain tools, not the language model, in charge of the science. The system grew out of practical experience with Just-DNA-Seq and Just-DNA-Lite and serves both as the agentic engine called from the Just-DNA-Lite web UI and as an integration layer for Claude Code, Cursor, Antigravity, Codex, and other repository- or MCP-aware assistants.

Through MCP servers, repo-native agent instructions, pre-built agent workflows, CLI commands, and Python APIs, an assistant orchestrates benchmarked genomics operations — polygenic risk scoring, variant annotation, explanatory graphics, and structured access to literature and variant databases — as constrained tool calls rather than improvised scripts. just-dna-agents is deliberately built across multiple upstream codebases and services: Just-DNA-Lite, just-prs, just-dna-format, just-dna-marketplace, biomedical MCP services such as BioContext KB, and, under active integration, just-biomarkers for methylation clocks and other biomarker models. This architecture lets reference annotation, polygenic scores, and domain-specific model outputs be combined in one workflow while each numerical result remains delegated to its validated engine.

The toolkit also expands annotation content. From a paper, variant list, or free-text description, single- and multi-agent modes draft genetic annotation modules that must pass deterministic checks — schema validity, allele and genotype consistency, provenance, genome build, and identifier resolution — before use. AI output is kept as a reviewable draft, not treated as a finding. We evaluate module creation using variant recall, citation precision, and effect-direction accuracy. just-dna-agents is open-source and for research use only.

## **1. Introduction**

Two trends are reshaping how people work with personal genomes. First, a fast-growing population of researchers and individuals now explores genomic data through AI coding assistants rather than dedicated applications — but a general-purpose assistant asked to "score this genome" or "extract the SNPs from this paper" improvises analysis code and literature extraction, and the results are frequently wrong in silent, consequential ways: fabricated rsIDs, reverse-strand or inverted alleles, mismatched effect directions, invented PMIDs, or subtly incorrect scoring math. Second, the annotation content that gives a genome-analysis platform its value — curated variant-trait associations — is published far faster than any team can hand-curate.

just-dna-agents addresses both by inserting a validation-gated, benchmarked layer between the assistant and the genome. Its design reflects lessons from Just-DNA-Seq and Just-DNA-Lite: users need transparent local computation, but they also need a more flexible way to ask follow-up questions, create modules, and connect validated tools into workflows. Its guiding principle is that **reliability comes from deterministic tools and validators, not from the language model**: an agent may drive a workflow or draft a module, but the numbers come from benchmarked engines and nothing enters the platform until it passes machine-checkable rules. It is developed as an integration layer over multiple upstream code repositories, MCP services, command-line tools, Python APIs, and agent-environment conventions, not as a claim that all biomedical knowledge or computation lives inside one agent. On this foundation, just-dna-agents unifies two capabilities:

- **A unified agent-facing toolkit.** just-dna-agents exposes the validated engines of the Just-DNA-Lite platform (Kulaga et al., 2026) — PRS computation (via `just-prs-mcp`, now folded into `dna-agents`), variant annotation, explanatory graphics, and structured interpretation — through MCP tools, agent skills, repository instructions, CLI commands, and Python APIs, and lets an assistant *orchestrate* multi-step workflows across them. The same toolkit is also called by the Just-DNA-Lite web interface for in-app agentic features, so external assistants and the UI share one agentic engine rather than separate implementations.
- **Validated module creation.** just-dna-agents turns a paper, a variant list, or a description into a validated, compiled annotation module, so the catalogue can grow with the literature — via a single agent for straightforward sources or a multi-agent research team that uses model diversity and cross-validation to reduce the systematic blind spots of any one model.

just-dna-agents is the agentic layer of the just-dna-seq ecosystem. The Just-DNA-Lite platform paper (Kulaga et al., 2026) describes the local application and the compute engines it wraps — the annotation pipeline, the just-prs computation library and its concordance benchmarks, the no-code module format, and the web UI — and is not repeated here. This paper describes the toolkit architecture (Section 2), the agent-facing access surfaces and orchestration (Section 3), the module specification and its deterministic validation and compilation (Section 4), the agentic module-creation layer and its consensus mechanism (Section 5), the access surfaces across Claude Code, Cursor, Antigravity, Codex, MCP clients, CLI, and Python API (Section 6), and a preliminary evaluation with the framework for the fuller benchmark suite (Section 7). We discuss reliability, provenance, and the fast-aging nature of agent tooling in Section 8.

## **2. System Overview**

just-dna-agents is organized around a sharp boundary between deterministic and agentic components, and surfaces everything through one agent-facing interface.

**Deterministic core.** Pure, reproducible operations with no dependence on any language model: the benchmarked genomic engines it wraps (PRS scoring, annotation joins — described in Kulaga et al., 2026) and the module compiler (validation, Ensembl coordinate resolution, compilation to Parquet). Given the same inputs, these always produce the same output. This is what guarantees that whatever an agent requests or drafts is computed by a benchmarked engine and checked before use.

**Agentic layer.** Agents that *drive* the deterministic core: at inference time they select and chain tools to fulfil a natural-language request (orchestration), and, for module creation, they research variants, extract genotype-level annotations, collect study references, write spec files, and iterate against the validator's error messages. The agentic layer is built on the Agno framework and is model-agnostic; individual agent roles can be assigned to different underlying models.

**One toolkit, many clients.** The same functions are surfaced through the `dna-agents-mcp` server, repo-native agent instructions (`AGENTS.md`, `CLAUDE.md`), pre-built Claude Code agents and workflows, agent skills, a CLI, and a Python API. The identical toolkit therefore drives (i) the in-app experience in the Just-DNA-Lite web interface and (ii) external assistants such as Claude Code, Cursor, Codex, Antigravity, and other MCP- or repository-aware agents. The entry point changes; the validation guarantees and the compiled/benchmarked outputs do not.

**Figure 1.** just-dna-agents architecture: agent-facing interfaces expose benchmarked genomic engines (PRS, annotation, graphics, interpretation) and the module compiler; agents orchestrate multi-step workflows and draft modules against the deterministic validator; the same toolkit drives the Just-DNA-Lite UI and external assistants (Claude Code, Cursor, Codex, Antigravity).

## **3. Unified Agent Access to Genomic Operations**

The first capability of just-dna-agents is to make the platform's validated operations available to an assistant as typed tools, so that an agent obtains results from benchmarked engines instead of improvising. All paths are backed by the identical engines described in Kulaga et al. (2026), so results are numerically identical regardless of entry point.

### **3.1 Polygenic risk scoring over MCP (`just-prs-mcp`, folded in)**

just-dna-agents consolidates the `just-prs-mcp` server, exposing the PRS toolbox as typed tool schemas: load or download a genome, normalize the VCF, search the PGS Catalog by trait or gene, compute scores with the DuckDB/Polars engine, and place a result within a 1000 Genomes reference-population distribution. MCP-aware assistants can launch it without cloning a repository (e.g. `uvx` invocation for Claude Code, or the equivalent server entry for Cursor, Codex, and Antigravity), while repository-aware agents can use the same documented commands, skills, and instructions directly. A lightweight agent skill (a `/prs` slash command) is also provided for quick conversational sessions, where a separate MCP server is unnecessary; the MCP server is preferred when an agent needs programmatic, typed tool invocation inside a larger pipeline.

### **3.2 Annotation and other models**

Beyond PRS, the toolkit exposes variant annotation against curated modules and reference databases, and is the integration point for additional models in the ecosystem. In particular, integration work is underway with `just-biomarkers` (github.com/dna-seq/just-biomarkers), a methylation biomarker workspace whose core library computes epigenetic clock scores from methylation matrices. Exposing these biomarker models alongside PRS and variant annotation behind one interface is what enables cross-operation orchestration (Section 3.4), while keeping each numeric result delegated to its domain-specific engine.

### **3.3 Explanatory graphics and interpretation prompts**

The toolkit renders the same chart types available in the platform UI — single-model bell curves with the user's score marked, multi-ancestry overlays across the five 1000 Genomes superpopulations, trait-grouped z-score scatter plots coloured by quality tier, and percentile strip charts — exportable as interactive HTML, Vega-Lite JSON, or static PNG/SVG, so an agent can produce a publication-quality figure directly in the conversation. It also assembles a structured, caveat-aware interpretation prompt for each result, consolidating trait, percentile and method, raw score, model coverage (fraction of the model's markers found in the genome), quality tier and discrimination metrics, absolute-risk context where available, ancestry, heritability, and source links. The prompt deliberately foregrounds the limitations (low model coverage, liftover uncertainty, European-cohort bias of most scoring files) so that automated explanations communicate uncertainty rather than false precision.

### **3.4 Orchestration**

Because PRS, annotation, and other operations are exposed behind one typed interface, an assistant can chain them autonomously from a single plain-language request — for example, *"normalize this genome, compute the type-2-diabetes polygenic risk score, and annotate longevity-associated variants"* — with each step executed by a validated engine and its output feeding the next. This is the key difference from an assistant improvising a bespoke script: the workflow is assembled from benchmarked, typed operations, so the failure modes of free-form code generation are removed from the numeric path.

## **4. Module Specification, Validation, and Compilation**

The second capability of just-dna-agents is validated module creation, whose deterministic backbone is described here and whose agentic layer follows in Section 5.

### **4.1 Specification format**

A module is a directory of three files (plus optional documentation and thumbnail):

- **`module_spec.yaml`** — metadata: `name` (lowercase, underscores), `version`, `title`, `description`, `report_title`, `icon` (from a fixed catalogue), `color` (from a fixed palette), `defaults` (curator, method ∈ {literature-review, gwas, clinvar-review, expert-curation}, priority), and `genome_build` (must be `GRCh38`).
- **`variants.csv`** — one row per (rsID, genotype): `rsid`, optional `chrom`/`start`/`ref`/`alts`, `genotype` (slash-separated, alphabetically sorted alleles, e.g. A/G not G/A), `weight` (positive = protective, negative = risk, 0 = neutral), `state` ∈ {neutral, ref, risk, protective, significant, alt}, `conclusion`, `gene` (HGNC symbol), `phenotype`, `category`.
- **`studies.csv`** (mandatory) — one row per (rsID, PMID): `rsid`, `pmid` (a real PubMed ID — never invented), and optional `population`, `p_value`, `conclusion`, `study_design`.

This format is intentionally identical to the hand-authored module format consumed by Just-DNA-Lite: an AI-generated module and a human-authored one are indistinguishable to the platform except for the `curator` field, and both pass through the same validator.

### **4.2 Validation rules**

The validator (`validate_spec`) enforces, among others: YAML structure and required fields; CSV well-formedness; alphabetically sorted, slash-separated genotypes; presence of a wild-type (ref/ref, weight 0) row for each variant; weight within the permitted range and sign-consistent with `state`; genotype alleles drawn from {ref, alt}; GRCh38-only coordinates and forward-strand alleles; and a **mandatory, non-empty `studies.csv`** with well-formed PMIDs. A module with no study references is rejected. Validation errors are returned as structured messages, which the agentic layer feeds back into its own context for self-correction.

### **4.3 Coordinate resolution and compilation**

The compiler resolves the rsID↔coordinate mapping automatically against a local Ensembl Variations DuckDB cache (GRCh38): the author supplies only one of {rsID} or {chrom, start, ref} per variant, and the compiler fills in the other. It searches for the cache via an explicit flag, an environment variable, a default location, or an auto-build from the pipelines package, and skips resolution with a warning if none is available. Compilation (`compile_module`) then emits the weights/annotations/studies Parquet files the platform loads. Because this layer is deterministic, the same specification always compiles to the same artifacts — a prerequisite for reproducible evaluation (Section 7).

## **5. Agentic Module Creation**

### **5.1 Single-agent mode**

In the fast path, a single agent handles the entire workflow: it reads attached documents (PDF/CSV/Markdown/text), queries biomedical databases to confirm and enrich variant information, writes the specification, and validates it, iterating up to a bounded number of times on validation errors. It has two tool categories: **biomedical-database tools** via the BioContext KB MCP server (EuropePMC for literature, Open Targets for variant-disease associations, bioRxiv for preprint metadata, Ensembl for variant annotations, and more), and **module-writing tools** (`write_spec_files`, `validate_spec`, `compile_module`/`register_module`, `write_module_md`, `generate_logo`). A typical single-source run completes in roughly two minutes.

### **5.2 Multi-agent research-team mode**

For multiple papers or larger variant sets, just-dna-agents assembles a team of three to five agents:

- **PI (Principal Investigator) agent** — coordinator. Delegates research to researcher agents in parallel, synthesizes findings by consensus, incorporates reviewer feedback, and writes the final specification.
- **Researcher agents (up to 3)** — independent literature researchers, each receiving the same task and independently querying biomedical databases and extracting variant data. Crucially, researchers are assigned to **different underlying models** (e.g. one Gemini, one GPT, one Claude, subject to configured API keys), so model diversity reduces the risk of a shared, systematic misreading of the literature.
- **Reviewer agent** — quality control. Checks variant integrity (rsID format, genotype sorting, wild-type presence), weight/state consistency, provenance (how many researchers independently confirmed each variant), and scientific accuracy (spot-checking PMIDs via web search), returning a structured report of errors, warnings, and confirmations.

A minimum team (one model's API key) is PI + one researcher + reviewer (3 agents); a full team is 5 agents. A typical team run completes in roughly seven to eight minutes.

### **5.3 Consensus mechanism**

The consensus rule trades recall for precision on uncertain items: variants confirmed by two or more researchers are included as high-confidence; variants identified by a single researcher are omitted unless supported by at least two strong PMIDs; and weight disagreements are resolved by taking the median. Requiring cross-model agreement is intended to reduce — not eliminate — the fabrications and mis-extractions a single model can produce; quantifying this (team vs. solo) is a primary aim of the evaluation in Section 7, and no reduction is claimed beyond what those measurements support.

### **5.4 Output and editing workflow**

Both modes emit the deterministic artifact set (`module_spec.yaml`, `variants.csv`, `studies.csv`, `MODULE.md`, thumbnail, and a timestamped creation/edit log). In the Just-DNA-Lite UI the module loads into an editing slot for review, manual correction, download, or follow-up conversational edits; the team can read an existing module's context and extend it to a new version, preserving prior content while integrating new data. Registration compiles the CSVs to Parquet and makes the module available for annotation.

## **6. Access Surfaces**

just-dna-agents is usable several ways, all backed by the same toolkit.

**As an MCP server.** `dna-agents-mcp` (into which `just-prs-mcp` is consolidated) exposes both the genomic operations of Section 3 and the compiler tools — `validate_spec`, `compile_module`, `get_spec_format`, `list_icons`, `list_colors` — that any MCP-capable assistant can call without cloning the repository (`uvx dna-agents-mcp serve --transport stdio`, or an entry in the client's MCP configuration). Configuration examples for Claude Code, Claude Desktop, Cursor, Codex, and Antigravity are provided in the repository. For variant research, the BioContext KB MCP server is added alongside, supplying Ensembl, EuropePMC, Open Targets, UniProt, Reactome, and related tools. An `AGENTS.md` at the repository root carries the full spec-format reference and critical rules, and is read automatically by Codex, Cursor, Windsurf, and Aider, so those tools receive the same context even without the MCP server.

**As pre-built Claude Code agents and workflows.** The repository ships agent definitions — `@paper-scout` (finds and triages papers suitable for module creation, filtering out reviews, PRS-only, and expression-only studies and flagging supplementary data), `@module-creator` (solo creation), `@researcher`, and `@reviewer` — and a multi-agent `create-module` workflow that orchestrates the research team.

**As a CLI and Python library.** `dna-agents validate` and `dna-agents compile` operate on spec directories from the terminal, and the `dna_agents` Python package exposes `validate_spec` and `compile_module` programmatically, including Ensembl-based resolution.

**Guidance for non-biologists.** Because module quality depends on choosing extractable source material, the system pairs the `@paper-scout` agent with documented guidance on paper taxonomy: candidate-gene studies and pharmacogenomics guidelines are well suited; reviews contain no original variant data; PRS/polygenic-score studies belong in the PRS engine rather than a discrete module; expression/epigenetics papers contain no DNA variants; and GWAS papers are often suitable but frequently carry the per-SNP data in supplementary tables that must be attached.

## **7. Evaluation (Preliminary)**

We separate two questions: does the deterministic compiler faithfully preserve module content (Section 7.1), and how accurate is agentic creation against ground truth (Section 7.2)? (The PRS/annotation engines exposed in Section 3 are benchmarked in Kulaga et al., 2026, and are not re-benchmarked here.)

### **7.1 Compiler round-trip validation (complete)**

The compiler is validated by a round-trip suite: deployed modules are downloaded from the `just-dna-seq/annotators` HuggingFace repository, reverse-engineered back to the spec DSL, recompiled, and compared against the originals on schema, row counts, rsID sets, genotypes, weights, states, and study PMIDs. This comprises 52 round-trip tests across deployed modules, alongside 61 unit/integration tests covering the Pydantic models, YAML/CSV parsing, validation rules, weight/state consistency, and Ensembl resolution. These establish that a valid specification compiles to platform-faithful artifacts deterministically — the property the accuracy evaluation relies on.

### **7.2 Creation accuracy against ground-truth fixtures (preliminary)**

We evaluate agentic creation with ground-truth fixtures: complete, expert-checked module specs an agent should reproduce from a natural-language description. Each provides a `freeform_input.md` prompt and the ground-truth `module_spec.yaml`, `variants.csv`, and `studies.csv`.

**Table 1.** Evaluation fixtures.

| Fixture | Topic | Variants | Studies | Freeform input |
|---|---|---|---|---|
| `mthfr_nad` | MTHFR & NAD+ metabolism | 24 rows (8 rsIDs) | 12 PMIDs | Methylation cycle + NAD+ biosynthesis genetics |
| `cyp_panel` | CYP drug metabolism | 21 rows (7 rsIDs) | 12 PMIDs | Pharmacogenomics panel (CYP2C19, CYP2D6, CYP2C9, CYP3A4) |

Each `freeform_input.md` is fed to the agent, its output is compiled, and it is scored against ground truth on: **variant recall** (fraction of ground-truth (rsID, genotype) rows recovered), **PMID precision** (fraction of cited PMIDs that are real and topically correct — guarding against fabricated or mismatched citations), and **weight accuracy** (agreement of effect direction and magnitude). We report these for single-agent vs. research-team mode (the consensus ablation of Section 5.3) and across model assignments within team mode.

**Table 2.** Preliminary creation-accuracy results. *[pending execution of eval runs — to be completed before submission]*

| Mode | Fixture | Variant recall | PMID precision | Weight-sign accuracy | Runtime |
|---|---|---|---|---|---|
| Solo agent | `mthfr_nad` | *[pending]* | *[pending]* | *[pending]* | *[pending]* |
| Team | `mthfr_nad` | *[pending]* | *[pending]* | *[pending]* | *[pending]* |
| Solo agent | `cyp_panel` | *[pending]* | *[pending]* | *[pending]* | *[pending]* |
| Team | `cyp_panel` | *[pending]* | *[pending]* | *[pending]* | *[pending]* |

### **7.3 Illustrative end-to-end runs**

As qualitative evidence pending the systematic results above, three runs were executed end-to-end against real biomedical literature:

- **Solo (≈107 s):** from a single preprint on longevity-associated variants in multigenerational Dutch families, a single agent queried Open Targets, EuropePMC, and bioRxiv, wrote and validated the spec, and produced a 12-row module across 4 genes.
- **Team, v1 (≈461 s):** from two papers (a longevity-variants paper and a SIRT6 rs117385980 study), a 5-role team produced a 34-row module across 8 genes in two categories, with cGAS rs200818241 and SIRT6 rs117385980 confirmed by all researchers as high-confidence and the opposite effect directions of different variants preserved as reported.
- **Team edit, v2 (≈418 s):** with v1 loaded, a GWAS paper plus a ~260-SNP supplementary table was added; the PI selected five well-characterised pleiotropic SNPs, the reviewer confirmed them, and v2 retained all 34 v1 rows and added 15 in a new category.

In these three illustrative cases the generated modules required no manual corrections. This is anecdotal across three runs, not a systematic accuracy result; the fixture-based evaluation in Section 7.2 is the basis for any quantitative claim.

### **7.4 Error taxonomy and limitations**

The evaluation is scoped to two fixtures and a small number of runs; expanding fixture coverage (more trait domains, larger variant sets, adversarial "trap" papers) and reporting variance across repeated runs is the main journal-version work. Known error classes the framework is designed to surface include fabricated or topically-mismatched PMIDs, effect-direction inversions, strand/allele-orientation errors, wild-type omissions, and over-inclusion of single-researcher variants. Agentic behaviour also depends on the underlying models, which change over time; results should be read as characterising the system's *design* (validation-gated, consensus-based) rather than fixed capabilities of any particular model version.

## **8. Discussion**

**Reliability comes from validation and benchmarked tools, not automation.** The central commitment of just-dna-agents is that neither an orchestrated workflow nor a generated module is trusted on the model's word: numeric results come from benchmarked engines, and no generated module reaches the platform until the deterministic validator and compiler confirm it is structurally sound, uses GRCh38 forward-strand alleles, includes wild-type rows, and carries well-formed, mandatory study references. The agentic layer is a productivity and accessibility layer on top of that guarantee; the consensus mechanism is a further, empirically-testable precaution rather than a claim of correctness.

**Provenance and expert review.** Generated modules are automated first drafts. just-dna-agents makes AI provenance explicit (the `curator` field propagated into module metadata) so downstream users can calibrate trust, and the editing workflow is built around human review rather than one-click trust — consistent with the platform's broader stance (Kulaga et al., 2026) of surfacing uncertainty rather than concealing it.

**Fast-aging tooling.** Agent frameworks, model names, and MCP conventions evolve quickly. We anchor the contribution on the durable elements — a validation-gated toolkit unifying benchmarked genomic operations, the module specification, the cross-model consensus design, and the evaluation framework — and keep volatile implementation details (specific model identifiers, client configuration syntax) in the repository documentation rather than as load-bearing claims.

**Future work.** The immediate priority is the full benchmark suite: more fixtures, repeated runs with variance reporting, solo-vs-team and cross-model ablations, and an adversarial set probing fabrication and effect-direction errors. Further directions include tighter integration of `@paper-scout` triage into the creation loop, expanded biomedical-tool coverage, and completing `just-biomarkers` integration so methylation clocks and other biomarker models can be orchestrated through the same agentic toolkit.

## **9. Conclusion**

just-dna-agents lets an AI assistant work with a personal genome reliably: it exposes the Just-DNA-Lite platform's validated, benchmarked operations — PRS, annotation, graphics, and interpretation — as typed tools an agent can orchestrate, and it lets a researcher (or a non-biologist with the right source material) turn a paper into a validated, compiled annotation module, all from within the web interface or agent environments such as Claude Code, Cursor, Codex, Antigravity, and MCP-capable clients. Its contribution is a system in which reliability is enforced by benchmarked engines and a deterministic validator, agentic orchestration and generation are a productivity and accessibility layer above that guarantee, and multi-model consensus is an explicit, testable precaution against the characteristic failure modes of single-model work. Coupled with the companion platform paper, it completes the picture of how an open, local-first genome-annotation ecosystem can be used and grown through AI assistants — while keeping AI provenance visible and expert review in the loop. just-dna-agents is open-source and for research use only.

## **Code and Data Availability**

- **dna-agents** — https://github.com/dna-seq/dna-agents (core library `dna_agents` + `dna-agents-mcp` server, into which `just-prs-mcp` is consolidated; MIT). Includes `AGENTS.md`, `CLAUDE.md`, `.claude/agents/`, `.claude/workflows/create-module.js`, and eval fixtures under `tests/fixtures/evals/`.
- **Just-DNA-Lite** — https://github.com/dna-seq/just-dna-lite (companion platform paper).
- **just-prs** — https://github.com/dna-seq/just-prs (PRS computation library benchmarked in the companion paper; its MCP surface is exposed via dna-agents).
- **just-biomarkers** — https://github.com/dna-seq/just-biomarkers (methylation biomarker and epigenetic clock scoring workspace; integration with dna-agents is underway).
- **BioContext KB** — https://biocontext-kb.fastmcp.app (multi-database MCP server used for variant research).
- **Deployed modules** — https://huggingface.co/datasets/just-dna-seq/annotators (round-trip test source).
- **Ensembl Variations** — used for GRCh38 rsID/position resolution.
- **Test genomes** — public WGS VCFs on Zenodo: Anton Kulaga's genome (CC0, record 18370498) and Livia Zaharia's genome (CC-BY-4.0, record 19487816), usable as `--vcf anton` / `--vcf livia` aliases.

## **Research Use Only**

These annotation modules are for research use only. They summarize published genetic association findings and are not clinical-grade evidence. The system enforces the language conventions "associated with", "may contribute to", "has been linked to" and forbids "causes"/"guarantees"; makes no individual-level predictions from population data; and requires all study references to be real PMIDs.

## **Competing Interests**

Anton Kulaga, Olga Borysova, and Nikolay Usanov are co-founders of SecvADN SRL, which provides additional services on top of the open-source modules. *(Full statement to be aligned with Paper 1.)*

## **Contribution Statements** *(to be finalized)*

- **Usanov Nikolay** — AI agentic toolkit (agent-facing integrations, MCP surface, orchestration, PI/Researcher/Reviewer agent swarm, single-agent mode, Agno framework integration, BioContext MCP integration), toolkit design and implementation.
- **Kulaga Anton** — compiler/validation library, Ensembl resolver, just-prs engine wrapped by the toolkit, evaluation harness, benchmarking, article writing.
- **Borysova Olga** — ground-truth fixtures and expert adjudication of evaluation modules.
- **Fuellen Georg**, **Tacutu Robi** — co-supervision.
