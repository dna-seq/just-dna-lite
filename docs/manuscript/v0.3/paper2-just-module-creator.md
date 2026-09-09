<!--
  MIRROR — do not edit here.

  Source of truth: just-module-creator/docs/manuscript/manuscript.tex
  (+ references.bib, mirrored beside this file as paper2-references.bib).
  Copied 2026-09-09 from that repo's manuscript.md, which is itself a pandoc
  rendering of the .tex. The rendering drops \cite keys, so citation markers
  appear as stray commas and periods in the prose below — read the upstream
  .tex when a citation matters. Edits belong upstream; re-copy to refresh.
-->

# **Creating and Sharing Genomic Annotation Modules with AI: The Just-DNA Ecosystem**

> **Paper 2 of 2.** Target venue: EASRP 2026 (European AI Summer Research Paper),
> anonymous 8-page A4 main text. Companion to *Just-DNA-Lite: a Local-First,
> Open-Source Platform for Personal Genome Annotation and Polygenic Risk Scoring*
> (Paper 1, `paper1-just-dna-lite.md`). Authors are withheld upstream for
> anonymous review. See `manuscript-strategy-v0.3.md` for the split boundary.

---

## Abstract

Genome analysis is an iterative workflow—ask, select data, score, annotate, inspect, and revise—and it is increasingly done inside AI coding assistants rather than fixed graphical interfaces. But general-purpose language models are unreliable when used directly for genomics: they fabricate variant identifiers, misassign effect directions, and attach real PMIDs to the wrong paper. The Just-DNA ecosystem redirects these assistants from generating disposable code to producing structured, versioned data: *genomic annotation modules* where every variant is linked to its genotype, evidence, effect size, and a verbatim passage from the source paper. The output is an editable data artifact, not generated analysis code, and a domain expert can review it in a spreadsheet without specialized tools.

This paper presents the plugin ecosystem that makes this possible. The authoring plugin, **just-module-creator**, runs inside the AI coding assistants that bioinformaticians and developers already use daily, so module authoring requires no new infrastructure. The underlying toolchain validates authored files against a live schema, checks identifiers against reference databases, and compiles modules into a portable artifact. A shared registry lets independent authors publish, version, and exchange modules—the package-registry pattern applied to genomic annotation knowledge. Once installed, a module can be applied to a genome in under a minute; the annotation consumer, Just-DNA-Lite, is the subject of a companion paper . The software is open-source and available at <https://anonymous.4open.science/r/just-dna-registry> (anonymized for review).

# Introduction

Genomic annotation connects variant calls to the knowledge that gives them meaning: trait associations, clinical classifications, effect sizes, and the evidence behind each claim. This knowledge is scattered across papers, databases, and preprints, and it changes as new studies appear. Turning it into something a computational pipeline can use requires structured, validated records with unambiguous variant identifiers, genome-build coordinates, and traceable citations.

Researchers increasingly use AI coding assistants such as Claude Code and Codex for this kind of work. These tools are powerful, but when asked to analyze variants they typically generate a script: code that may fabricate identifiers , attach a real PMID to the wrong paper , reverse an allele, or bypass established filters. Each session may produce slightly different code, and the result must be reviewed for correctness, efficiency, and security before it can be trusted. The output is a one-off answer tied to one session, not a reusable resource.

This paper presents the Just-DNA ecosystem, which gives these same assistants a different job. Instead of generating code, the assistant produces structured data: a *module* of editable CSV tables where each variant is linked to its studies, citations, effect sizes, and supporting passages. The input can be anything the assistant can read, from a single sentence describing a trait to a collection of papers or a summary from another model. Every variant is verified against reference databases such as dbSNP; dedicated checking tools validate gene symbols against HGNC, trait identifiers against ontology services, and flag decisions that require domain expertise. Once compiled to Parquet, Just-DNA-Lite joins the module to a genome . Modules are versioned and shareable: they can be kept locally, rehearsed in a test registry, or published for others to install and use. The same files can also be written or edited entirely by hand.

This paper makes four contributions:

1.  It describes the module contract shared by manual editors, AI-assisted authoring tools, versioned stores, and the genome-analysis consumer.

2.  It presents `just-module-creator`, an authoring plugin that exposes the public capabilities of `just-dna-format`, `just-dna-compiler`, `just-dna-enricher`, and `just-dna-registry` as typed Model Context Protocol (MCP) tools . The plugin reads the installed schema instead of carrying a copy.

3.  It defines how modules move between a local store, a test registry whose publications can be deleted, and the public catalog while preserving provenance and decisions that still require review.

4.  It defines an evaluation protocol for variant recovery, citation identity, and effect-direction agreement, and reports catalog statistics from the first eight published modules across three independent namespaces.

# Related work

#### Genome annotation and catalogs.

A variant call records what differs between a sample and a reference genome. Annotation adds information about that call, such as its predicted consequence, known clinical classification, reported trait association, or the conclusion assigned to a particular genotype. VEP, ANNOVAR, and OpenCRAVAT/OakVar perform this kind of lookup by joining a callset to established resources . ClinVar and the GWAS Catalog publish records that can supply annotation content , HGMD derives variant–disease associations from the literature through manual review , ClinGen provides expert curation within the ACMG/AMP framework , and ClinPGx consolidates PharmGKB, CPIC and PharmCAT into one pharmacogenomic resource . CIViC crowdsources cancer variant interpretation, anchoring every evidence item to a source publication ; its releases are database-wide rather than installable per-topic units, which makes it a source this ecosystem consumes rather than an alternative to it. The GA4GH Genomic Knowledge Standards define interoperable representations for variant annotations . The problem addressed here begins before the join: selected evidence must be turned into a reviewable, machine-checkable collection that can be distributed and applied consistently.

Table <a href="#tab:comparison" data-reference-type="ref" data-reference="tab:comparison">1</a> narrows the comparison to systems adjacent to the authoring task: annotation engines, extension-based annotation platforms, expert-curated knowledgebases, structured literature extraction, unconstrained model drafting, and `just-module-creator`.

<div id="tab:comparison">

| System | Kind / primary task |  |  |  |  |  |
|:---|:---|:--:|:--:|:--:|:--:|:--:|
| Ensembl VEP / ANNOVAR | annotation engine / consequence prediction against a callset | – | – | – | – |  |
| OpenCRAVAT / OakVar | annotation platform / user-supplied annotation extensions |  |  | – | – |  |
| CIViC | curated knowledgebase / expert-crowdsourced clinical interpretation | – |  |  | – |  |
| PubMind-DB | text-mined database / LLM extraction of variant–disease–pathogenicity records | – |  |  |  |  |
| Raw LLM | general-purpose model / unconstrained drafting | – | – | – |  | – |
| just-module-creator | authoring plugin / create, review, and publish installable modules |  |  |  |  |  |

Qualitative comparison of systems adjacent to annotation authoring. The rows have different primary tasks; the capability columns compare how their structured outputs are created, checked, and shared. Runtime annotation speed is outside this comparison and is covered in the companion platform paper .

</div>

<div class="minipage">

*Criteria.* *Versioned modules*: user-installable or distributable annotation units with explicit versions. *Schema validation*: structured records are checked against a declared machine-readable schema. *Provenance tracking*: record- or module-level source links travel with the output. *AI-assisted authoring*: a language model participates directly in creating or revising the structured output. *Shared catalog*: outputs or extensions are discoverable through a shared service. A dash means the capability is not part of the system’s core public workflow, not that no related function can be added around it.

</div>

#### Biomedical text mining and variant extraction.

Conventional named entity recognition systems such as tmVar3 and PubTator3 have improved gene and variant tagging in biomedical text . LitVar 2 links literature paragraphs with variant records from external databases, accelerating knowledge retrieval . However, these tools are largely limited to entity-level extraction and do not recover relational information such as variant-specific pathogenicity across disease contexts or the experimental evidence supporting a classification. PubMind applies instruction-tuned LLMs to extract variant–disease–pathogenicity associations directly from over 41 million PubMed abstracts and 5.4 million full-text articles, producing a database of approximately 1.3 million unique variants with contextual annotations . These systems demonstrate that LLM-based literature mining can recover structured variant knowledge at scale, but their output is a flat database rather than a versioned, schema-validated module that an annotation consumer can install and apply to a genome.

#### Factuality and tool use.

Language models can produce fluent text around a false identifier or citation . Benchmarks on genomic question-answering show that models hallucinate gene names, variant identifiers, and functional annotations . Retrieval-augmented approaches and tool use reduce the need to improvise when a model can call a typed operation instead . The Model Context Protocol provides a standard for connecting models to external tools . Biomedical MCP services can search literature, ontologies, and variant databases. just-module-creator uses the same general approach, then carries the result into module files that the rest of the Just-DNA pipeline can inspect and reuse.

#### Agent orchestration.

Many scientific-agent systems assign research and review to several model instances . The plugin described here does not require its own orchestration runtime. Claude Code or Codex supplies the agent, while the plugin supplies the tools and the written workflow. This paper evaluates that authoring path, not a particular choice of language model or agent-team topology.

# Method

## The module artifact

At the artifact boundary, a just-dna annotation module is an editable directory. It always contains `module_spec.yaml` and at least one recognized table. The table records the thing being annotated, such as a genotype, a diplotype, or a measured quantity. Evidence and machine-produced sidecars are stored separately. Compilation converts this human-readable directory into machine-readable Parquet files and a content-addressed `manifest.json` . The compiled artifact is what a consumer installs and joins to a genome.

The authored files are ordinary YAML, CSV, Markdown, and optional image files. A domain expert can open them in a spreadsheet to review and correct an AI draft without special tools. just-module-creator operates on this same directory rather than introducing a separate format for AI-produced content. The module describes how a genotype or measurement should be interpreted if a consumer encounters it. Just-DNA-Lite, or another compatible consumer, supplies the genome or measurement later.

The author does not need to supply this directory, or any CSV file, at the start of a session. Figure <a href="#fig:conversation-to-module" data-reference-type="ref" data-reference="fig:conversation-to-module">1</a> shows how a conversation entry—which can range from a trait name to a collection of papers—moves through routing, scaffolding, and review to a compiled module. The `/create-module` router identifies the appropriate entry point and stage.

<figure id="fig:conversation-to-module" data-latex-placement="ht">

<figcaption>From conversation to a usable module. Module files are intermediate artifacts created by the workflow, not required user inputs. Authored claims remain distinct from derived source records inside the editable workspace.</figcaption>
</figure>

Different claim types—variant associations, study evidence, pharmacogenomic diplotypes, copy-number ranges—belong to separate tables, each with its own schema. The plugin reads column definitions from the installed schema, so an author always sees the version accepted by the current compiler.

## Architecture and lifecycle

Module authoring and sample analysis remain separate until Just-DNA-Lite joins a compiled module to a local genome. On the authoring path, a person may edit the files directly or use an AI assistant to draft them. Both routes then pass through the same enrichment and compilation steps before the module enters a local or shared store. Figure <a href="#fig:architecture" data-reference-type="ref" data-reference="fig:architecture">2</a> shows the two paths and the boundary between them.

<figure id="fig:architecture" data-latex-placement="ht">

<figcaption>The two paths of the Just-DNA ecosystem.</figcaption>
</figure>

On the sample path (Figure <a href="#fig:architecture" data-reference-type="ref" data-reference="fig:architecture">2</a>), Just-DNA-Lite converts VCF input to Parquet and joins it with compiled modules using DuckDB, producing annotated reports and enriched data that the user can filter. A whole-genome VCF is annotated in under 40 seconds; the companion paper  describes the sample path and polygenic risk score computation in detail.

Within `just-module-creator` the language model participates only in the knowledge path: it searches, reads and drafts. VCF filtering, module joins and polygenic scoring remain ordinary software steps with explicit inputs and repeatable code.

Table <a href="#tab:packages" data-reference-type="ref" data-reference="tab:packages">2</a> lists each component’s responsibility and boundary.

<div id="tab:packages">

| Component | Responsibility | Does not |
|:---|:---|:---|
| `just-module-creator` | research and authoring workflow | process a genome |
| `just-dna-format` | schema and identity rules | access the network |
| `just-dna-compiler` | validate, compile, reverse, and sign | access the network |
| `just-dna-enricher` | resolve, draft, and cross-check | decide scientific meaning |
| `just-dna-registry` | publish, discover, and download modules | author module rows |
| Just-DNA-Lite | filter VCFs, join annotations, and produce reports | define module schema or compiler rules |

Responsibilities across the Just-DNA ecosystem.

</div>

## Determinism, evidence, and responsibility

The compiler establishes structural validity and reproducibility: schema conformance, coordinate resolution, and a deterministic content signature . What it does not establish is whether the authored claims agree with the literature. A false association in valid syntax compiles perfectly. Three properties keep the evidence chain auditable.

First, authored values and their checks are kept independent: a value filled from the source that will later check it makes the check compare the source with itself. The design test is: *could this check have failed?* If not, it measured nothing (Section <a href="#sec:checks" data-reference-type="ref" data-reference="sec:checks">4</a>).

Second, disagreements with reference archives are preserved rather than silently resolved. ClinVar may lag a retraction; when the authored value should remain, `record_override` logs the difference and the reason.

Third, a check has three answers, not two: it passed, it failed, or it never ran. The third is recorded as a null, and a null is not a *no*. The identifier check writes an attestation to `verification.json` so a reviewer can tell an empty report from one with no findings.

The assistant may locate a verbatim `provenance_quote` from retrieved full text and follow citations into supplementary tables to find per-variant statistics. A `curator` field records who located each quote—a name or model identifier—so a reviewer can direct scrutiny where it is most needed. Attribution does not transfer responsibility: the human author holds accountability regardless.

Curation follows drafting because a drafted row may still carry decisions the source cannot make—genotype, weight interpretation, conclusion wording—and these are surfaced for domain experts rather than resolved silently.

## Local and shared module stores

A compiled module can reach a consumer through three routes (Figure <a href="#fig:architecture" data-reference-type="ref" data-reference="fig:architecture">2</a>): local installation into a Just-DNA-Lite checkout for testing with a VCF, publication to the test registry for a deletable rehearsal, or publication to the immutable public catalog. The registry runs its own enrichment and strict compilation on publish, so the stored artifact is the one the server produced, not a locally claimed digest. Inclusion in either catalog distributes a module; it is not scientific review, clinical validation, or endorsement.

## Evaluation dimensions

The plugin includes a scorer. It evaluates variant recall over rsID–genotype pairs, citation identity (each PMID must resolve to the intended paper, not merely exist as a valid identifier), and effect-direction agreement. The reference standard is a human curation. Scoring modules against a module the same system authored would measure agreement with itself.

Two measurement choices are load-bearing. Recall is reported at two grains, because recovering the right variant with wrong genotypes and recovering half the variants exactly are distinct failures that partial credit averages away. *Decoy rate* replaces precision: a variant absent from one curation may still be correct, whereas a decoy is one an expert designated non-associated.

<div id="tab:scores">

| Run | rsID recall | Pair recall | Decoy rate | Citation recall | Direction |
|:----|------------:|------------:|-----------:|----------------:|----------:|
| 1   |        1.00 |        0.67 |       0.00 |            1.00 |      1.00 |
| 2   |        1.00 |        1.00 |       0.00 |            1.00 |      1.00 |
| 3   |        1.00 |        1.00 |       0.00 |            1.00 |      1.00 |

Three runs of one prompt scored against an expert-curated reference module, plugin version fixed.

</div>

Table <a href="#tab:scores" data-reference-type="ref" data-reference="tab:scores">3</a> reports three runs of one prompt on one paper. All three recovered the variant the paper supports, cited both it and the earlier study it replicates, agreed on effect direction, and introduced no decoy. Two matched the reference on every genotype row, including a homozygous row that asserts nothing because neither cohort observed a carrier. All three declined to propagate the seed paper’s description of the variant as stop-gained, which the study it cites classifies as intronic at the same coordinate.

The one divergence is a significance verdict at $`p \approx 0.07`$, read as *suggestive* by two runs and *not significant* by the third, which an aggregate score would have hidden. Agreement also measures the guidance and not only the runs: the validator names the missing genotype and a written rule states that a zero weight is a claim where a blank is not, so convergence shows the workflow is prescriptive, not that its output is confirmed.

Scoring does not require a reference curation. A module can be evaluated by reading what its cells claim against what they withhold. That reading corrected a prediction of ours: we expected a paper reporting no association test to produce no variant rows, yet one run produced sixty. Each recorded the observed allele but withheld effect direction and statistical significance. The blanks are honest: with no association test, there was nothing to report. Row count is therefore not part of the score; whether the filled cells claim more than the source supports is.

# Results

The plugin can be installed from its GitHub repository in a single command (`/install-plugin` in Claude Code, or a repository URL in the Codex plugin marketplace). Once installed, the assistant gains access to 60 typed MCP tools (Appendix <a href="#app:tools" data-reference-type="ref" data-reference="app:tools">9</a>) and 20 skills—written workflow instructions that teach the assistant when to call which tool. In both Claude Code and Codex, skills marked as commands can be invoked directly by typing `/name` in the prompt.

With the plugin active, the assistant calls typed tools instead of generating code (Figure <a href="#fig:conversation-to-module" data-reference-type="ref" data-reference="fig:conversation-to-module">1</a>): enrichment adds coordinates and derived sidecars, compilation validates against the live schema, and the compiled artifact can be published to the registry and immediately applied to a genome. The checks described in Section 3.3 catch citation misattributions, identifier drift, and schema violations in practice—a measurement across 33 published `studies.csv` files (44,342 rows) found 3,668 rows where the `provenance_quote` was the article’s title, a passage that always matches its own full text and evidences nothing.

## Command menu

Seven of the 20 skills are user-invocable commands (Table <a href="#tab:skills-commands" data-reference-type="ref" data-reference="tab:skills-commands">15</a>), exposing the workflow through intentions rather than internal stages. `/create-module` is the entry point: it reads where the author is actually standing—a trait, a handed bundle, a directory somebody else left—and routes to the stage that owns the work. The remaining thirteen skills are guides, which a router loads by naming their path when the assistant reaches the corresponding lifecycle stage. A guide is deliberately not matched from its own description: that is what keeps thirteen documents out of every session’s prompt, and it is why a guide nothing links to is unreachable rather than merely quiet.

## Production catalog

At the time of writing, the public catalog holds eight published modules across 19 versions and three independent namespaces. Table <a href="#tab:catalog" data-reference-type="ref" data-reference="tab:catalog">4</a> summarizes the published modules.

<div id="tab:catalog">

| Module                  | Variants | Studies | Genes | Versions        |
|:------------------------|---------:|--------:|------:|:----------------|
| big_five_personality    |      330 |     390 |   185 | 4               |
| risk_impulsivity        |      474 |       – |   325 | 1               |
| cognitive_intelligence  |       32 |       – |    31 | 1               |
| aggression_anger        |       28 |       – |    22 | 1               |
| bodybuilding            |       13 |       – |    13 | 1               |
| placebo_response (v2)   |        3 |       – |     3 | 2               |
| placebo_response_claude |        3 |       – |     3 | 1               |
| lactose_tolerance       |        2 |       8 |     1 | 2               |
| **Total**               |  **885** |         |       | **19 versions** |

Modules published to the public catalog as of August 2026. All modules target GRCh38 and were compiled with strict resolution.

</div>

Two of the three namespaces belong to authors outside the development team, and four of the eight modules are theirs. Module sizes range from 2 to 474 variants. Four versions of `big_five_personality_snps` show that iterative revision works in practice. Two modules on the same trait (`placebo_response` via Codex, `placebo_response_claude` via Claude Code) were created by the same author to compare the two assistants; both compiled against the same schema and are published side by side.

# Discussion

Genomic data is becoming personally accessible, and people already use AI assistants—coding tools such as Claude Code and Codex, or plain chat applications such as ChatGPT—to interpret their results . Restricting this is not viable, so the more effective response is to make the work happen in the open, where domain professionals can review what others publish and the tools enforce structure. A module is visible, reviewable, and correctable; a one-off chat session is none of these.

The safety concern is real but cuts deeper than AI. Candidate-gene studies have failed to replicate , GWAS effect sizes routinely shrink in independent cohorts , direct-to-consumer tests have produced false-positive rates above 40% , and variant reclassifications have led to genetic misdiagnoses . The ecosystem is therefore explicitly research-only: a module that faithfully reflects a study which later fails to replicate is not wrong on its own terms, but a user acting on it may be harmed all the same.

The registry turns individual effort into shared infrastructure, and the plugin’s MCP tools are listed on a public directory so other agent platforms can use them independently. What travels through it is genomic-data-agnostic knowledge: a module carries no individual-level data.

#### Limitations.

The module system launched in August 2026. We are developing mechanisms to involve genetic counselors and domain-expert agents in quality evaluation, and to communicate to citizen scientists that many modules reflect early-stage research rather than clinical-grade evidence. Every run scored here used one model through one host, so the results say nothing about model or host sensitivity. Free-text conclusions are not scored at all, and the assistant’s judgement about whether a source supports a claim remains a reviewer’s question. Coordinates are declared rather than translated: `module_spec.yaml` names a `genome_build` and the toolchain refuses to infer one. Liftover belongs to the source or the consumer; the PGS Catalog already distributes per-assembly positions . Runtime benchmarks are in the companion paper .

# Conclusion

Annotation knowledge that lives in a chat session dies with it. The Just-DNA ecosystem gives an AI assistant a different job—producing a versioned, schema-validated module instead of a script—so the work survives review, correction and reuse by someone else. What makes that more than a file format is what a module keeps separate: authored claims stay distinct from derived records, a check that could not run says so, and every published module carries the evidence for its own rows. Eight modules from three namespaces, half of them from authors outside the development team, show the path is functional today.

The software is open-source and intended for research use only.

# Code and data availability

- **just-dna-format, just-dna-compiler, and just-dna-enricher**: <https://anonymous.4open.science/r/just-dna-compiler> (schema, reference compiler, and enricher).

- **just-module-creator**: <https://anonymous.4open.science/r/just-dna-registry> (MCP server, Claude Code and Codex plugin manifests, skills; MIT).

- **Just-DNA-Lite**: <https://anonymous.4open.science/r/just-dna-lite> (local VCF processing, annotation, and reporting; described in the companion paper ).

- The public catalog and the test registry are live at URLs provided in the anonymized repositories.

# Appendix

# Research use only

Annotation modules summarize published association findings. They are not clinical-grade evidence. The authoring plugin does not make individual-level predictions and does not open a genome. Just-DNA-Lite and `just-prs` process sample data for research and educational use; their reports and scores are not diagnoses or medical advice. Language that implies causation, such as “causes” or “guarantees,” is outside the scope of a module written with this plugin.

# Plugin surface: tools and skills

A Claude Code or Codex plugin is a bundle of two kinds of asset. **MCP tools** are typed operations the assistant can call—each has a name, typed inputs, and a structured return value. **Skills** are written instructions loaded into the assistant’s context on demand; they teach the workflow that the tools serve, including when to call which tool and what to do with the result.

## Tools (60)

The tools are organized into a core set (always listed) and nine optional groups that a session can reveal incrementally via `toolbox`. Table <a href="#tab:tools-core" data-reference-type="ref" data-reference="tab:tools-core">5</a> lists the 18 core and meta tools; Tables <a href="#tab:tools-evidence" data-reference-type="ref" data-reference="tab:tools-evidence">6</a>–<a href="#tab:tools-closing" data-reference-type="ref" data-reference="tab:tools-closing">14</a> list the nine groups. Registry writes require a token obtained through `authenticate`. Literature and enrichment requests share a single pacing gate, including the NCBI budget.

<div id="tab:tools-core">

| Tool | Purpose |
|:---|:---|
| `list_tables` | List authorable table kinds and what each row represents |
| `describe_table` | Describe one table kind: every column, type, vocabulary, and pick-list |
| `table_requirements` | The three shapes of requiredness for a table kind |
| `describe_machine_table` | Describe a machine-written sidecar: columns, types, vocabulary |
| `get_template` | Get a CSV template (header only, or header plus stub rows) |
| `scaffold_module` | Create `module_spec.yaml` plus stub CSVs; never overwrites |
| `lint_rows` | Lint CSV text against a table kind (writes nothing) |
| `validate_module` | Pre-flight a spec directory (writes nothing) |
| `compile_module` | Compile a spec directory into Parquet plus `manifest.json` |
| `draft_from_clinvar` | Draft `variants.csv` and `studies.csv` from ClinVar |
| `enrich_module` | Resolve rsIDs to coordinates and mint VRS identifiers |
| `literature_search` | Find papers behind a row; confirm a PMID names the intended paper |
| `lookup_citation` | Check a PMID or DOI and read back which paper it names |
| `lookup_variant` | Look up one variant: loci, alleles, ClinVar calls, rsID currency |
| `record_override` | Log that an authored value deliberately outranks a source |
| `registry_register` | Create a registry account and mint its API key |
| `authenticate` | Provide a registry token to unlock write tools for this session |
| `toolbox` | List optional tool groups and reveal them to the session |

Core tools (always listed) and the meta-tool.

</div>

<div id="tab:tools-evidence">

| Tool | Purpose |
|:---|:---|
| `lookup_open_access` | Where a paper may legally be read, and on what terms |
| `fetch_fulltext` | Retrieve a paper’s text so the assistant can read and quote it |
| `paper_citations` | Papers that cite this one, or the papers it cites |
| `list_supplementary` | Inventory the supplementary files attached to a paper |
| `fetch_supplementary` | Download one supplementary file to the cache |
| `describe_supplementary` | Sheets in a downloaded workbook and their column names |

Evidence group: read a paper, its citations, and its supplementary tables.

</div>

<div id="tab:tools-identifiers">

| Tool | Purpose |
|:---|:---|
| `check_identifiers` | Check every gene symbol (HGNC) and trait CURIE (OLS4) in a spec |
| `lookup_identifier` | Check one gene symbol or trait CURIE |

Identifiers group: check gene symbols and ontology CURIEs.

</div>

<div id="tab:tools-pgx">

| Tool | Purpose |
|:---|:---|
| `draft_from_cpic` | Draft haplotypes, allele function, and diplotypes from CPIC |
| `draft_from_clinpgx` | Draft `pharm_variants.csv` from a ClinPGx snapshot |

Pharmacogenomics (PGx) group: draft from curated PGx sources.

</div>

<div id="tab:tools-passes">

| Tool | Purpose |
|:---|:---|
| `enrich_facts` | Fill frequency, constraint, and dosage sidecars |
| `enrich_literature_pass` | Resolve every citation in `studies.csv` into `literature.csv` |
| `enrich_gwas_effects` | Record the GWAS Catalog’s published effect sizes for the module’s rsIDs |
| `refresh_sidecar` | Re-derive one sidecar against its source, keeping curated rows |

Passes group: fill or re-derive machine-written sidecars.

</div>

<div id="tab:tools-review">

| Tool | Purpose |
|:---|:---|
| `audit_module` | Ask what a curation pass would ask (offline, reads only) |
| `review_queue` | Rank the rows where somebody overruled a source |
| `review_logs` | Show what is in the module’s logs (publishing them is permanent) |
| `study_facts` | Per-study facts the GWAS pass wrote into `gwas_effects.csv` |

Review group: read a module back and surface decisions.

</div>

<div id="tab:tools-integrity">

| Tool | Purpose |
|:---|:---|
| `compare_modules` | What moved between two spec directories (offline) |
| `compare_to_published` | Is local data ahead of the catalog, and how? |
| `module_signature` | Content signature of raw authored data (no compile, no network) |
| `verify_artifact` | Re-hash every file in a compiled artifact and recompute the digest |
| `reverse_module` | Turn a compiled artifact back into an authored spec directory |

Integrity group: compare, sign, verify, and reverse modules.

</div>

<div id="tab:tools-catalog">

| Tool | Purpose |
|:---|:---|
| `registry_search` | Search published modules (read-only, no token) |
| `registry_get_module` | Fetch one module’s full record: card, readme, versions, manifest |
| `registry_health` | Is this registry instance up, and which instance is it? |
| `registry_is_published` | Has this authored data been published under any name? |
| `registry_namespace_available` | Check whether a namespace is legal and unclaimed |
| `registry_download` | Download and integrity-verify a published module version |

Catalog group: read the registry.

</div>

<div id="tab:tools-publish">

| Tool | Purpose |
|:---|:---|
| `registry_whoami` | Confirm the token is accepted and report the account |
| `registry_validate` | Validate a spec on the registry without publishing |
| `registry_check` | Full publish dry run: validation plus network checks |
| `registry_publish` | Publish a spec directory as a module version |
| `registry_amend_readme` | Replace a published version’s readme (no version bump) |
| `registry_claim_namespace` | Claim a publishing namespace (irreversible on production) |
| `registry_yank` | Stop recommending a version (stays fetchable for pinned users) |
| `registry_unyank` | Restore a yanked version to listings |
| `registry_delete_version` | Hard-delete one rehearsed version from the polygon |
| `registry_delete_module` | Hard-delete all rehearsed versions from the polygon |

Publish group: write to the registry (token required).

</div>

<div id="tab:tools-closing">

| Tool | Purpose |
|:---|:---|
| `close_module` | Declare authoring finished, bound to its authored bytes |
| `describe_spec_file` | Describe `module_spec.yaml`: every key and block it carries |
| `authoring_reference` | The complete generated description of the authoring DSL as JSON |

Closing group: finish and describe.

</div>

## Skills (20)

Skills are markdown documents loaded into the assistant’s context when needed. Seven are **commands**—user-invocable via `/name` in the assistant’s prompt—and thirteen are **guides**, which a router loads by naming their path when the assistant reaches the corresponding stage.

<div id="tab:skills-commands">

| Command | Purpose |
|:---|:---|
| `/create-module` | Router: begin or continue creating a module from any starting point |
| `/module-status` | Inspect a directory and identify the next decision |
| `/module-revise` | Begin another pass over an existing module |
| `/find-evidence` | Find and read evidence for a row |
| `/module-publish` | Rehearse on the polygon, then publish to the catalog |
| `/module-symptom` | Explain a message from the toolchain |
| `/module-install-local` | Install a compiled module into Just-DNA-Lite locally |

User-invocable commands (7). Each is typed as `/name` in the assistant prompt.

</div>

<div id="tab:skills-guides">

| Guide | Purpose |
|:---|:---|
| `module-101` | High-level map: what a module is, what the plugin can and cannot do |
| `module-start` | Stage 0–1: triage, licence, the spec |
| `module-draft` | Stage 2: draft rows from evidence or a provider |
| `module-curate` | Stage 3: curate scientific decisions |
| `module-enrich` | Stage 4: enrich with coordinates, identifiers, and sidecars |
| `module-check` | Stage 5: cross-check against reference databases |
| `module-compile` | Stage 6: validate and compile to Parquet |
| `module-close` | Stage 6b: declare authoring finished and bind to authored bytes |
| `module-refresh` | Re-run anything that already ran |
| `module-diff` | What moved, and the reading that means a source changed its answer |
| `module-tables` | Which table kind, where every file sits, the three on-disk shapes |
| `module-weights` | The weight column everyone fills and nobody declares |
| `module-consumer` | The annotation consumer’s side of the seam |

Guides (13). Each is loaded by a router or a preceding skill rather than invoked by the user directly.

</div>
