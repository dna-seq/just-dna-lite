# Just-DNA-Lite: an AI-Powered Open-Source Modular Platform for Personal Genome Annotation

**Authors:** Kulaga Anton^1,2,4, Usanov Nikolay^3,4, Borysova Olga^4, Karmazin Alexey^4, Koval Maria^4, Fedorova Alina^4, Pushkareva Malvina^4, Evfratov Sergey^4, Ryangguk Kim^8, Fuellen Georg^1,*, Tacutu Robi^2,*

**Affiliations:**

1. Institute for Biostatistics and Informatics in Medicine and Ageing Research, Rostock University Medical Center, Rostock, Germany
2. Institute of Biochemistry of the Romanian Academy
3. HEALES (Healthy Life Extension Society)
4. SecvADN SRL
5. CellFabrik SRL
6. MitoSpace
7. M. Glushkov Institute of Cybernetics of National Academy of Sciences of Ukraine
8. Oak Bioinformatics, LLC

The contribution of these authors is considered to be equal.

\* Co-supervising authors.

---

## Abstract

Whole genome sequencing has become affordable for individuals, yet the tools available for annotating personal genomic data remain either proprietary, opaque in their methodology, or too complex for researchers without bioinformatics training. Commercial platforms present curated subsets of findings without disclosing all considered variants and their selection logic. Centralized storage of genetic data by commercial providers also carries serious privacy risks, as demonstrated by the 2023 breach at 23andMe that exposed the genetic ancestry information of approximately 6.9 million users (Doffman, 2023; Alteri et al., 2024). Furthermore, the pace of genetic discovery now far outstrips what any single team can manually curate: thousands of new variant-trait associations are published each year, and manually maintained annotation databases inevitably lag behind the literature. Neither existing proprietary nor academic approaches give researchers full, transparent, secure, and up-to-date tools for genomic annotation.

We present Just-DNA-Lite, an open-source modular platform for personal genome annotation designed for research and educational use. Just-DNA-Lite runs entirely on a personal computer, processes a whole-genome VCF in under 40 seconds, and produces annotated reports across user-selected modules. The platform is built on a no-code module system: annotation modules consist of a YAML specification and a CSV variant table, with no programming required. Modules are auto-discovered from any fsspec-compatible source (HuggingFace, GitHub, S3, or HTTP), enabling a growing ecosystem of community-contributed annotations.

A key contribution is an AI-assisted module creation system built on the Agno agentic framework. In simple mode, a single agent reads a research paper, queries biomedical databases, and produces a validated annotation module in approximately two minutes. In research team mode, a coordinated swarm of agents (Principal Investigator, up to three Researcher agents using different large language models, and a Reviewer with web search access) independently extract and cross-validate variant data, producing consensus-based modules in seven to eight minutes. Both modes output a deterministic specification that can be registered with one click.

The platform ships with expert-curated default modules covering several trait domains (longevity-associated variants, cardiovascular-related variants, lipid metabolism, VO2 max, and athletic performance) as a starting point, alongside over 5,000 polygenic risk scores from the PGS Catalog computed via the just-prs library with Pearson r = 0.9999 concordance against PLINK2 and 5.7--12.3x speedup. Because manual curation cannot keep pace with the volume of new genetic discoveries, the platform is designed around AI-aided module creation and community extension: users and researchers can generate new annotation modules from published papers within minutes and share them through any fsspec-compatible repository, so the annotation catalogue grows with the literature rather than waiting for a central team to update it.

All data stays local. The platform is open-source (AGPL v3), GDPR-friendly by design, and aligned with the principle that individuals have the right to explore their own genomic data. The platform does not perform clinical interpretation, does not generate diagnoses, and is not intended for medical decision-making. It is a research tool for variant annotation, not a clinical pipeline.

---

## 1. Introduction

Whole genome sequencing costs have fallen from billions of dollars to under a thousand since the completion of the Human Genome Project in 2003, and several companies now offer direct-to-consumer sequencing services (Whitley et al., 2020). Yet the gap between sequencing accessibility and variant annotation remains wide. Researchers and individuals receive raw variant files (VCFs) containing millions of variants but lack accessible tools to annotate them against published databases without specialized bioinformatics expertise.

Existing solutions occupy two extremes. Commercial platforms such as Nebula Genomics and Dante Labs provide curated reports, but the curation is opaque: users cannot verify which polymorphisms contributed to a score, whether the methodology is appropriate for their ancestry, or how findings were weighted. At the other end, research-grade tools like PLINK, ANNOVAR, and VEP are powerful but demand command-line proficiency and significant setup effort. There is no open-source platform that combines comprehensive variant annotation with ease of use, transparency, and extensibility.

The genetics of longevity illustrates the need for extensible annotation tools. The field is rapidly evolving: traditional twin studies placed the heritability of lifespan at 20--25%, but a recent study published in *Science* by Shenhar et al. (2025) estimates the intrinsic heritability at approximately 50% after correcting for extrinsic mortality confounders across Danish, Swedish, and SATSA twin cohorts. GWAS studies have identified candidate loci including APOE and FOXO3 as consistently associated with longevity across populations (Broer et al., 2014; Caruso et al., 2022), and the catalogue of longevity-associated variants continues to grow (Lin et al., 2021; Gonzalez, 2023). Databases such as LongevityMap within the Human Ageing Genomic Resources (HAGR) (Tacutu et al., 2017) have compiled thousands of variant-trait associations, but no existing tool makes it straightforward to annotate a personal VCF against these databases in a transparent and extensible way. This exemplifies a broader pattern: variant-trait associations are published faster than any single curation team can integrate them, motivating a platform where new annotation modules can be created rapidly -- either by hand or with AI assistance.

A platform for personal genome annotation must therefore solve three problems simultaneously: it must be easy to use (web interface, no bioinformatics training), transparent in its methods (open-source, auditable scoring), and extensible (researchers should be able to add new annotation modules as the literature evolves, without writing code). Furthermore, privacy is a first-order concern: genomic data is among the most sensitive personal information, and uploading it to third-party servers introduces risks that many individuals and regulatory frameworks (such as the GDPR and the European Health Data Space) seek to avoid.

To address these needs, we developed Just-DNA-Lite, a ground-up rewrite of the earlier Just-DNA-Seq platform. The original system (referred to hereafter as Generation I) was built on top of OakVar, a Python-based variant analysis framework. While functional, it suffered from long processing times (approximately two hours per whole-genome VCF), a complex dependency chain, and a module system that required Python programming to extend. Just-DNA-Lite (Generation II) replaces the OakVar dependency entirely with a standalone pipeline based on Dagster, Polars, and DuckDB, reducing annotation time to under 40 seconds on the same hardware -- a 172-fold speedup. The module format is simplified to a no-code YAML and CSV specification. And a new AI-assisted module creation system allows researchers to generate annotation modules directly from published papers, using an agentic pipeline that queries biomedical databases, extracts variants, and validates the output without human intervention. Generation I is described in detail in Supplementary File S1.

**Scope.** This paper presents a software platform and its computational methods. Just-DNA-Lite annotates user variants against published variant-trait association databases and computes standard polygenic risk scores; it does not perform clinical interpretation, generate diagnoses, or draw novel inferences between specific genes and diseases. The variant-trait associations surfaced by the platform are those already published in the source databases (LongevityMap, PGS Catalog, Ensembl Variation, etc.). The platform's contribution is computational -- speed, extensibility, privacy, and AI-assisted module creation -- not the discovery or clinical validation of gene-trait associations.

---

## 2. Platform Architecture

Just-DNA-Lite is structured as a uv workspace containing two Python packages: `just-dna-pipelines` (Dagster assets, VCF processing, annotation logic, and CLI tools) and `webui` (a Reflex-based web interface). The platform requires Python 3.13+ and is installed and run with a single command (`uv run start`). All computation happens locally; no data leaves the user's machine.

### 2.1 Annotation Pipeline

The core annotation pipeline is built on Dagster with Software-Defined Assets, providing automatic data lineage tracking and resource monitoring (CPU usage, peak memory, and duration for every pipeline step). A typical annotation workflow proceeds as follows:

1. **VCF ingestion.** The user uploads a VCF or VCF.gz file through the web interface. The file is read using polars-bio, which provides a Polars-native VCF reader.
2. **Normalization.** The raw VCF undergoes quality filtering (configurable via `modules.yaml`): only variants passing specified FILTER values (by default, PASS and ".") are retained, with optional minimum depth (DP >= 10) and quality (QUAL >= 20) thresholds. Chromosome prefixes ("chr") are stripped for consistency with annotation databases. The normalized data is written as a Parquet file, which serves as the shared input for all downstream annotation.
3. **Module annotation.** For each selected annotation module, the pipeline performs a streaming join between the normalized VCF Parquet and the module's precomputed weights Parquet. Joins are performed by rsID (default) or genomic position. Polars streaming joins (`sink_parquet`) keep peak memory low; for datasets too large to fit in memory, DuckDB handles out-of-core joins with configurable memory limits.
4. **Ensembl annotation (optional).** When enabled, the pipeline joins the normalized VCF against the Ensembl Variation database (cached locally as chromosome-level Parquet files downloaded from HuggingFace via fsspec). This provides clinical significance labels, consequence types, and cross-references for each variant.
5. **Report generation.** Annotated results are written as Parquet files and rendered as downloadable PDF/HTML reports. All outputs are available for downstream analysis in Python, R, or any tool that reads Apache Arrow.

The annotation data for reference databases and modules is prepared upstream by the prepare-annotations pipeline ([github.com/dna-seq/prepare-annotations](https://github.com/dna-seq/prepare-annotations)), which converts source databases into columnar Parquet format optimized for fast lookups.

### 2.2 Modular Plugin System

The central design principle of Just-DNA-Lite is that annotation modules are data, not code. A module consists of a directory containing two files:

- `module_spec.yaml` -- metadata including the module name, version, title, description, icon, colour, and genome build.
- `variants.csv` -- a table of variants with columns for rsID, genotype (slash-separated, alphabetically sorted), effect weight (negative for risk, positive for protective), state (risk/protective/neutral), a brief clinical conclusion, and gene symbol.

Optional files include `studies.csv` (linking variants to PubMed IDs), `MODULE.md` (human-readable documentation), and `logo.png` (thumbnail image). No Python code is required from the module author. The annotation engine loads modules via Polars LazyFrames; no code from the module is executed.

Module discovery is automatic. The platform reads a list of sources from `modules.yaml` at the project root. Each source can be any fsspec-compatible URL:

- `org/repo` or `hf://datasets/org/repo` for HuggingFace datasets
- `github://org/repo` for GitHub repositories
- `https://...` for HTTP/HTTPS servers
- `s3://...` or `gcs://...` for cloud storage
- Local filesystem paths

The loader auto-detects whether a source is a single module (contains `weights.parquet` at root) or a collection (subfolders each containing `weights.parquet`). Display metadata (titles, icons, colours) can be overridden in `modules.yaml` without modifying the module itself. New modules added to any configured source are discovered on the next startup or manual refresh.

By default, curated modules are published to the [just-dna-seq](https://huggingface.co/just-dna-seq) organization on HuggingFace, though Zenodo and other online sources are equally supported.

### 2.3 Web Interface and Self-Exploration

The web interface is built with Reflex, a Python-based framework that compiles to React. The entire UI is written in Python; no JavaScript is required. The interface provides:

- **File management.** Upload VCF files, select which modules to apply, and launch annotation jobs.
- **Module selection.** Browse available modules with their descriptions, icons, and version information. Toggle Ensembl Variation annotation on or off.
- **Results preview.** View annotated variants in a sortable, filterable data grid directly in the browser.
- **Report download.** Download PDF/HTML reports for each module's findings.
- **Self-exploration.** Even without selecting a specific module, users can browse their full variant table with sorting, filtering, and search. When Ensembl annotation is enabled, variants are cross-referenced against Ensembl for clinical significance labels, consequence types, and known phenotype associations. All data can be exported as Parquet for downstream analysis in Python, R, DuckDB, or any Arrow-compatible tool.

Just-DNA-Lite annotation interface

**Figure 1.** The Just-DNA-Lite web interface showing the annotation results view with module selection, variant data grid, and report download options.

### 2.4 Performance Characteristics

Just-DNA-Lite was designed with a "runs on a laptop" philosophy, prioritizing memory efficiency over raw throughput. On a server with an Intel Xeon E5-2667 v4 CPU and 128 GB RAM (with HDD storage -- a conservative lower bound), the platform annotates a whole-genome VCF (6.1 million variant records) against the default module set in approximately 39 seconds on a warm run, with peak RAM under 750 MB. Even a cold start (first run requiring cache initialization) completes in approximately 203 seconds. By comparison, the Generation I OakVar-based system required approximately 6,705 seconds (nearly two hours) on the same hardware, representing a 172-fold speedup. Detailed benchmark results are presented in Section 6.

---

## 3. AI-Assisted Module Creation

Building annotation modules by hand is labour-intensive: it requires reading the primary literature, identifying relevant variants, looking up rsIDs and genomic positions, assigning effect weights based on study quality and replication, and formatting the output. Just-DNA-Lite includes an AI-assisted module creation system that automates this process, turning a research paper (or a free-text description) into a validated, deployable annotation module.

### 3.1 Simple Mode (Solo Agent)

In simple mode, a single AI agent handles the entire module creation workflow. The user provides a free-text prompt in a chat interface and optionally attaches up to five files (PDF, CSV, Markdown, or plain text). The agent is built on the Agno framework and uses Google Gemini Pro as its primary model (overridable via environment variable).

The agent has access to two categories of tools. First, biomedical database tools via the BioContext MCP (Model Context Protocol) server: EuropePMC for literature search, Open Targets for variant-disease associations, BioRxiv for preprint metadata, and Ensembl for variant annotations. Second, module-writing tools: `write_spec_files` (writes `module_spec.yaml`, `variants.csv`, and `studies.csv` to disk), `validate_spec` (checks schema compliance and data integrity), `register_module` (compiles CSVs to Parquet and adds the module to `modules.yaml`), `write_module_md` (generates documentation), and `generate_logo` (creates an AI-generated thumbnail via Imagen 3).

The agent operates in a loop of up to 10 iterations. It reads the attached documents, queries external databases to confirm and enrich variant information, writes the module specification, and validates the output. If validation fails, the error is fed back into the agent's context for self-correction. A typical run on a single research paper completes in approximately two minutes.

### 3.2 Research Team Mode (Multi-Agent Swarm)

For more complex tasks spanning multiple papers or large variant sets, the system supports a multi-agent research team mode with three to five agents depending on available API keys:

- **PI (Principal Investigator) Agent** -- the team coordinator. Receives the user's request, delegates research tasks to Researcher agents in parallel, synthesizes their findings by consensus, incorporates Reviewer feedback, and writes the final module. Uses Gemini Pro.
- **Researcher Agents** (up to 3) -- independent literature researchers. Each receives the same task and independently queries biomedical databases and extracts variant information from attached documents. Researcher 1 uses Gemini Pro (always present), Researcher 2 uses OpenAI GPT (present if `OPENAI_API_KEY` is configured), and Researcher 3 uses Claude Sonnet (present if `ANTHROPIC_API_KEY` is configured). Using different LLMs introduces model diversity, reducing the risk of systematic blind spots in literature interpretation.
- **Reviewer Agent** -- quality reviewer. Receives the PI's synthesized draft and checks variant integrity (rsID format, genotype sorting, wild-type presence), weight and state consistency, provenance (how many researchers confirmed each variant), and scientific accuracy (spot-checking PMIDs via Google Search). Returns a structured report of errors, warnings, and confirmations. Uses Gemini Flash.

The consensus mechanism works as follows. Variants confirmed by two or more researchers are included as high-confidence findings. Variants identified by only a single researcher are scrutinized and omitted unless supported by at least two strong PMIDs. Weight disagreements between researchers are resolved by taking the median. This cross-model agreement requirement substantially reduces hallucination compared to single-agent approaches.

A minimum team (Gemini API key only) consists of the PI, one Researcher, and the Reviewer (3 agents). A full team with all three API keys provides 5 agents. A typical team run completes in seven to eight minutes.

### 3.3 Output Format and Editing Workflow

Both modes produce a deterministic set of output files:

- `module_spec.yaml` -- module metadata (name, version, title, description, icon, colour, genome build)
- `variants.csv` -- per-variant annotation table with rsID, genotype, weight, state, conclusion, gene, phenotype, and category
- `studies.csv` -- evidence table linking variants to PubMed IDs with population, p-value, and study design
- `MODULE.md` -- human-readable documentation including design decisions and a changelog
- `logo.png` -- AI-generated thumbnail image
- Timestamped creation/edit log

After generation, the module is loaded into an editing slot in the web UI. The user can review all files, download them as a ZIP archive, make manual edits, or send follow-up messages in the same chat to request modifications. The team reads the existing module context and extends it to a new version, preserving prior content while integrating new data. When satisfied, the user clicks "Register Module as source" to compile the CSVs to Parquet and add the module to the platform's configuration, making it immediately available for annotation.

AI Module Creator - Step 1

**Figure 2.** The AI Module Creator interface. The user attaches a research paper PDF and describes the desired module in a chat prompt. The system shows real-time progress of agent tool calls.

AI Module Creator - Step 2

**Figure 3.** After completion, the generated module appears in the editing slot with all files (module_spec.yaml, variants.csv, studies.csv, MODULE.md, logo). The user can review, edit, and register the module with one click.

### 3.4 Example Walkthrough

To illustrate the system in practice, we present three scenarios that were executed end-to-end with real biomedical literature. All generated modules required no manual corrections.

**Scenario 1 -- Solo Agent Creation.** A user uploaded a single PDF (Putter et al., 2025, a preprint reporting longevity-associated variants in multigenerational Dutch families) and issued the prompt: "I want you to create a module based on the attached articles." A single Gemini Pro agent processed the paper in approximately 107 seconds. The agent queried Open Targets for variant annotations on the CGAS gene, searched EuropePMC for supporting literature on cGAS-STING signalling, fetched preprint metadata from bioRxiv, ran a second literature search for linkage-analysis variants (SH2D3A, RARS2, SLC27A3), wrote the module specification, validated it, and generated documentation. The resulting `familial_longevity` module contained 12 variant rows across 4 genes, with weights derived from the source paper's reported effect sizes and functional evidence.

**Scenario 2 -- Multi-Agent Team Creation.** The user switched to Research Team mode and uploaded two PDFs: the Putter et al. longevity variants paper (peer-reviewed version, PMID 41427385) and Sheikholmolouki et al. (2025), a study on SIRT6 rs117385980 and its reported antagonistic pleiotropic association with frailty and longevity (PMID 41249831). The system assembled a four-role team (PI, three Researchers using Gemini/GPT/Claude, and a Reviewer) and completed in approximately 461 seconds. In the parallel research phase (~136 s), all three researchers independently queried biomedical databases. The PI then synthesized findings by consensus (~98 s): cGAS rs200818241 and SIRT6 rs117385980 were confirmed by all researchers as high-confidence, while linkage variants received conservative weights per the Reviewer's recommendation. The PI wrote the module (~227 s), producing 34 variant rows across 8 genes in two categories. The system correctly captured opposite directionalities for different variants as reported in the source papers, demonstrating that the consensus mechanism preserves nuanced effect directions from the literature.

**Scenario 3 -- Iterative Module Update.** With `latest_longevity` v1 loaded, the user uploaded a third paper (Dinh et al., 2025, a multivariate GWAS identifying shared cardiometabolic trait associations) along with its supplementary CSV containing approximately 260 lead SNPs. The team re-assembled in editing mode (~418 s), the PI selected the five most pleiotropic and well-characterised SNPs from the candidates (rs964184/ZNF259, rs12740374/SORT1, rs7310615/SH2B3, rs28601761/TRIB1, rs6547692/GCKR), the Reviewer confirmed all five as well-documented in GWAS literature, and the PI wrote v2: 49 total variant rows (all 34 from v1 retained, plus 15 new rows in a new "mvARD" category). The existing logo was correctly reused without regeneration.

**Table 1.** Comparison of AI module creation scenarios.


| Dimension                 | Solo agent   | Team creation (v1)                | Team edit (v2)              |
| ------------------------- | ------------ | --------------------------------- | --------------------------- |
| Input                     | 1 PDF        | 2 PDFs                            | 1 PDF + 1 CSV (~260 rows)   |
| Duration                  | ~107 s       | ~461 s                            | ~418 s                      |
| Agents involved           | 1            | 5 (PI + 3 Researchers + Reviewer) | 5 (same team)               |
| Variant rows produced     | 12 (4 genes) | 34 (8 genes, 2 categories)        | 49 (13 genes, 3 categories) |
| External database queries | 4            | 7+ per researcher                 | 8+ per researcher           |
| Manual edits required     | None         | None                              | None                        |


The single-agent mode offers a fast path suitable for straightforward tasks from a single source, while the multi-agent team provides deeper coverage through cross-model consensus. The editing workflow demonstrates that the system can extend an existing module incrementally, preserving prior content while integrating new data sources, mirroring the iterative nature of real research curation.

---

## 4. Default Module Set

Just-DNA-Lite ships with a set of expert-curated annotation modules developed by geneticist Olga Borysova, illustrating the platform's module system across several trait domains. These modules represent the default set; the platform is designed so that users, researchers within the ROGEN consortium, and the broader community can easily add their own modules going forward, either by hand or with AI assistance (Section 3). The modules annotate user variants against published variant-trait association databases; they do not perform clinical interpretation or generate diagnoses.

**Table 2.** Default annotation modules shipped with Just-DNA-Lite.


| Module                            | Description                                                                                | Curator                  |
| --------------------------------- | ------------------------------------------------------------------------------------------ | ------------------------ |
| Longevity Map                     | Variant-trait associations from the LongevityMap database                                  | Expert (Olga Borysova)   |
| Coronary Artery Disease           | Variants associated with cardiovascular traits from GWAS literature                        | Expert                   |
| Lipid Metabolism                  | Variants associated with lipid metabolism traits                                           | Expert                   |
| VO2 Max                           | Variants associated with oxygen uptake capacity from exercise genomics literature          | Expert                   |
| Superhuman / Athletic Performance | Variants associated with elite athletic performance traits                                 | Expert                   |
| Longevity Variants 2026           | Variants from recent familial longevity and multimorbidity GWAS studies                    | AI-generated (team mode) |


### 4.1 Longevity Variants Module

The Longevity Variants module illustrates how existing variant-trait association databases can be wrapped into the platform's no-code module format. It builds upon the LongevityMap database (Tacutu et al., 2017), which contains 3,144 variant-trait associations in 884 genes. Our contribution is not re-annotation or re-validation of these variants, but rather: (1) curation and expansion with post-2017 literature, adding 50 new entries and editing 876 existing records with 4 additional fields each; (2) assignment of weighted scores based on study quality, replication across populations, and statistical significance; and (3) pathway-based categorization for structured browsing.

The module's weighting scheme assigns two independent weight components whose product yields the displayed score. The first component, the SNP weight (*w*_SNP), is an integrative parameter reflecting the strength of statistical evidence for a given variant-trait association. It incorporates the number of independent studies reporting statistical significance, the p-values reported, and the number of populations in which the association was replicated. Higher values indicate more robust statistical evidence.

The second component, the genotype weight (*w*_genotype), captures the direction and magnitude of the reported association for a specific genotype at that locus:

- *w*_genotype = 0 for the reference (typically homozygous reference) genotype
- *w*_genotype = +0.5 or +1.0 for heterozygous or homozygous carriers of the positively associated allele
- *w*_genotype = -0.5 or -1.0 for heterozygous or homozygous carriers of the negatively associated allele

When the association was observed only for heterozygous carriers, the weight was assigned solely to the heterozygous genotype, with all other genotypes receiving a value of zero. The score displayed for a given variant and genotype is:

> *W*_display = *w*_SNP x *w*_genotype

Positive values indicate alleles positively associated with the trait; negative values indicate negative associations. Within each pathway category, variants are sorted by the absolute value of their displayed weight.

For structured browsing, variants are grouped into 12 functional pathway categories (lipid transfer, insulin/IGF-1 signalling, antioxidant defence, mitochondrial function, sirtuins, mTOR, tumour suppressors, renin-angiotensin system, heat-shock proteins, inflammation, genome maintenance, and other pathways), covering genes from APOE and FOXO3 to IL6 and WRN. The full list of genes per category is available in the module's documentation. This categorization scheme demonstrates how the module format supports structured presentation of variant annotations without requiring code.

[FIGURE: Replace with updated Just-DNA-Lite UI screenshot showing the Longevity Variants report interface with pathway categorization, SNP table, and coloured weights. This replaces Figure 3 from the original manuscript.]

### 4.2 Polygenic Risk Scores

Polygenic risk scores (PRS) aggregate the effects of many common variants into a single weighted sum, providing a population-relative measure for a given trait. PRS computation is a standard bioinformatics operation used extensively in research (Lambert et al., 2021). We developed the just-prs library ([github.com/dna-seq/just-prs](https://github.com/dna-seq/just-prs)) as the PRS computation engine for Just-DNA-Lite, and released it as a standalone tool so that it can be used independently as a CLI, a Python library, or integrated into other platforms. just-prs provides access to all 5,000+ scoring files in the PGS Catalog.

Unlike the Generation I approach, which used Monte Carlo sampling (10,000 iterations with gnomAD allele frequencies) to estimate percentile distributions, just-prs uses precomputed percentile distributions derived from the 1000 Genomes Project phase 3 dataset. Percentiles are computed against five superpopulations: African (AFR), Ad Mixed American (AMR), East Asian (EAS), European (EUR), and South Asian (SAS). Users select the reference population closest to their ancestry, and the percentile reflects their position within that specific distribution.

The just-prs library provides three interchangeable computation engines:

- **DuckDB** -- SQL-based scoring with out-of-core processing; 12.3x faster than PLINK2 at median, with less than 1 MB of heap allocation per typical scoring call.
- **Polars** -- pure Python scoring via LazyFrame joins; 5.7x faster than PLINK2, easily parallelisable across scoring files.
- **PLINK2** -- the established reference tool in genomics, included for cross-validation purposes.

All three engines produce numerically equivalent results (Pearson r = 1.0 between DuckDB and Polars; r = 0.9999 between just-prs and PLINK2). Benchmark results are detailed in Section 6.2.

In the Just-DNA-Lite web interface, users browse the PGS Catalog in a searchable data grid, select one or more scores, and click "Compute." Results are displayed with the score sum, the number of matched variants, and the percentile within the selected 1000 Genomes superpopulation.

[FIGURE: Replace with updated just-prs PRS report screenshot showing 1000 Genomes population percentiles. This replaces Figure 4 from the original manuscript.]

### 4.3 Additional Trait Annotation Modules

The platform includes several additional modules that annotate variants against published GWAS and meta-analysis databases for specific trait domains:

**Cardiovascular-associated variants.** This module annotates variants reported in GWAS studies of cardiovascular traits. Inclusion criteria for selected SNPs are based on p-values from meta-studies and the number of replicated studies across populations.

**Lipid metabolism.** Variants reported in GWAS studies of lipid metabolism traits. The module uses the same evidence-based inclusion criteria.

**VO2 max and athletic performance.** Variants reported in exercise genomics studies of oxygen uptake capacity (VO2 max) and athletic performance traits.

All modules work by joining the user's VCF against curated variant-trait databases, adding annotation columns (weight, state, gene, conclusion) to matching variants. The modules do not calculate individual risk, generate diagnoses, or make clinical recommendations.

### 4.4 Growing the Module Ecosystem

The default modules described above represent the initial curated set. The platform's value proposition, however, lies in its extensibility. The no-code module format (Section 2.2) and AI-assisted creation tools (Section 3) lower the barrier to contribution to the point where any researcher with domain knowledge can create a new module -- either by preparing a YAML and CSV file by hand or by uploading a research paper and letting the AI handle the extraction and formatting.

The platform supports both manual and AI-assisted module creation. For manual creation, a researcher only needs to prepare a CSV or Parquet table of variants following minimal column requirements (rsID, genotype, weight, state, conclusion, gene) and a short YAML metadata file -- no programming is involved. Alternatively, the AI module creator (Section 3) can generate a complete module from a research paper in minutes; the generated output is then loaded into an editing slot where the user can manually review, correct, and refine it before registration. In all cases, modules can be edited, versioned, and shared through any fsspec-compatible repository. Planned directions for ecosystem growth are discussed in Section 6.5.

---

## 5. Benchmarking and Validation

### 5.1 Annotation Speed

We benchmarked Just-DNA-Lite against the Generation I OakVar-based system on the same hardware. The input was a personal whole-genome VCF containing 6,138,868 variant records (4,729,824 SNPs and 1,414,226 indels), produced by DeepVariant v1.4.0 against the GRCh38 reference genome at approximately 162x mean coverage. The personal genome data is not publicly available; however, the pipeline can be reproduced with any standard whole-genome VCF, and the benchmark scripts are provided in the repository.

**Table 3.** Annotation speed benchmark: Just-DNA-Lite vs OakVar (Generation I).


| Run type                   | *n* | Mean +/- SEM (s) | SD (s) | Speedup vs OakVar |
| -------------------------- | --- | ---------------- | ------ | ----------------- |
| **Just-DNA-Lite (normal)** | 11  | **38.9 +/- 3.3** | 10.9   | **~172x**         |
| Just-DNA-Lite (cold start) | 3   | 203.3 +/- 9.0    | 15.5   | ~33x              |
| Just-DNA-Lite (GVCF)       | 1   | 868              | --     | ~7.7x             |
| OakVar (Gen I)             | 3   | 6705 +/- 583     | ~1010  | 1x (ref.)         |


**Table 4.** Resource consumption during Just-DNA-Lite annotation.


| Run type         | Duration (s) | Peak RAM (MB) | Avg CPU (%) |
| ---------------- | ------------ | ------------- | ----------- |
| GVCF (longest)   | 868          | 748           | 182         |
| Cold start       | 216          | 644           | 278         |
| Normal (average) | 39           | 400--600      | --          |


**Table 5.** Benchmark hardware and input specifications.


| Parameter      | Value                                      |
| -------------- | ------------------------------------------ |
| CPU            | Intel Xeon E5-2667 v4 @ 3.20 GHz (8C/16T)  |
| RAM            | 128 GB                                     |
| Storage        | HDD JBOD array                             |
| OS             | Linux 6.8.0                                |
| Input VCF      | 6,138,868 records (4.7M SNPs, 1.4M indels) |
| Variant caller | DeepVariant v1.4.0                         |
| Genome build   | GRCh38                                     |
| Coverage       | ~162x mean                                 |


The 172-fold speedup was achieved with memory-optimised settings on HDD storage, representing a conservative lower bound. SSD or NVMe storage and module-level parallelisation would yield further gains. The pipeline was optimised for memory efficiency ("runs on a laptop" paradigm): speed gains come from Polars streaming joins and Parquet column-pruned reads, and peak RAM stays under 750 MB for default modules on a whole genome.

### 5.2 PRS Computation

We benchmarked the three computation engines in just-prs on 100 consecutive PGS Catalog IDs (PGS000006--PGS000106) scored against the same personal whole-genome VCF (4,661,444 biallelic variants, GRCh38). The benchmark is fully reproducible via `uv run python just-prs/benchmarks/benchmark_engines.py`.

**Table 6.** Runtime comparison of PRS computation engines. Median and mean wall-clock time per PGS ID scoring call (seconds). "Excl. large" excludes 7 PGS IDs with >= 1M variants.


| Engine     | *N* scored | Median (all) | Mean (all) | Median (excl. large) | Mean (excl. large) | Speedup vs PLINK2 |
| ---------- | ---------- | ------------ | ---------- | -------------------- | ------------------ | ----------------- |
| **DuckDB** | 100        | **0.049**    | 0.394      | 0.048                | 0.059              | **12.3x**         |
| **Polars** | 100        | 0.106        | 0.466      | 0.105                | 0.117              | 5.7x              |
| PLINK2     | 96^a       | 0.603        | 0.703      | 0.603                | 0.640              | 1x (ref.)         |


^a PLINK2 failed on 4 genome-wide PGS IDs (6.6--6.9M variants) due to 4-part ID matching constraints; just-prs engines scored all 100.

**Table 7.** Memory usage per PRS scoring call. DuckDB and Polars report Python heap allocation via `tracemalloc`; PLINK2 reports subprocess peak RSS via `psutil` (sampled at 100 ms intervals).


| Engine     | Median peak | Mean peak | Max peak | Measurement method |
| ---------- | ----------- | --------- | -------- | ------------------ |
| **DuckDB** | **0.2 MB**  | 139 MB    | 2,594 MB | `tracemalloc` heap |
| **Polars** | **0.2 MB**  | 139 MB    | 2,594 MB | `tracemalloc` heap |
| PLINK2     | 590 MB      | 595 MB    | 974 MB   | Subprocess RSS     |


For typical PGS IDs (< 500K variants), DuckDB and Polars allocate less than 1 MB of heap per call. The elevated mean and maximum values are driven by 7 genome-wide scores containing 6--7 million variants. PLINK2 has a near-constant ~590 MB floor because it reloads the compressed genotype files for each invocation.

**Table 8.** Score concordance between engines. Pearson correlation coefficient and maximum absolute score difference across scored PGS IDs.

| Engine pair | *N* PGS | Pearson *r* | Max |Delta score| |
|---|---|---|---|
| DuckDB <-> Polars | 100 | **1.000000** | < 1.1 x 10^-13 |
| DuckDB <-> PLINK2 | 96 | 0.999859 | 21.4 |
| Polars <-> PLINK2 | 96 | 0.999859 | 21.4 |

The near-zero difference between DuckDB and Polars confirms identical algorithm implementation (position-based join, genotype dosage, weighted sum). The absolute difference versus PLINK2 arises from variant-matching scope: PLINK2 requires exact 4-part `chr:pos:ref:alt` ID matching while just-prs uses position-based matching with allele orientation detection, leading to 1--3 extra variants included or excluded per genome-wide score. The Pearson r = 0.9999 confirms that individual risk rankings are effectively identical.

**Table 9.** Benchmark setup summary.


| Parameter          | Value                                                      |
| ------------------ | ---------------------------------------------------------- |
| Input VCF          | Personal whole-genome, single individual (Zenodo 18370498) |
| Biallelic variants | 4,661,444                                                  |
| Genome build       | GRCh38                                                     |
| PGS IDs scored     | 100 (PGS000006--PGS000106; 5 warm-up IDs excluded)         |
| Scoring file sizes | 77 -- 6,917,436 variants                                   |
| OS                 | Linux 6.8.0                                                |
| CPU                | 32 logical cores                                           |
| RAM                | 94 GB                                                      |
| Python             | 3.13.5                                                     |
| PLINK2             | v2.0 (2026-01-10)                                          |
| Variant match rate | ~50--54% across engines                                    |


The PLINK2 comparison directly addresses the reviewer concern regarding lack of validation and benchmarking: it provides a quantitative concordance metric (r = 0.9999) against the established reference tool, demonstrating that just-prs produces effectively identical risk rankings while running 5.7--12.3x faster with dramatically lower memory requirements.

[TODO: The benchmark shows approximately 50--54% variant match rate across engines. This warrants discussion: what drives the unmatched ~50%? Likely factors include indels, multiallelic sites, and build coordinate shifts. Anton to confirm whether this should be discussed in the manuscript.]

### 5.3 Module Accuracy

The accuracy of annotation modules depends on the quality of their underlying data sources. Expert-curated modules (Section 4) draw from peer-reviewed databases: LongevityMap (Tacutu et al., 2017) for longevity-associated variants, the PGS Catalog (Lambert et al., 2021) for polygenic risk scores, and Ensembl Variation for variant annotations. The platform does not discover or validate variant-trait associations; it annotates user variants against these existing databases.

AI-generated modules represent a different category of reliability. They are automated first drafts produced by reading and synthesizing published literature. While the cross-model consensus mechanism in team mode and the Reviewer's fact-checking via web search provide quality controls, AI-generated modules should be treated as starting points that benefit from expert review. The platform makes this distinction visible: each module's metadata includes a `curator` field indicating whether it was created by a human expert or an AI agent.

[TODO: Consider adding a concordance comparison with a commercial service (e.g., comparing variant annotations on the same VCF) if data is available.]

---

## 6. Discussion

### 6.1 Limitations of Variant Annotation

Variant annotation tools surface statistical associations from published literature, and several inherent limitations apply to any such system.

Heritability is a population-level statistic, not individual determinism. When a trait is described as "70% heritable," this measures how much of the variation between people in a specific study is associated with genetic differences. Heritability estimates change depending on the environment, study design, and cohort composition.

A polygenic risk score is a weighted sum that reflects where an individual falls in a reference population's distribution. The model is linear; real biology is not. Gene-gene interactions (epistasis), gene-environment interactions, feedback loops, developmental windows, and compensatory mechanisms are not captured by a linear weighted sum. Most PGS Catalog scoring files were derived from predominantly European cohorts; for individuals with different ancestry, the statistical associations may not transfer.

Most variants surfaced by annotation modules are statistical associations identified through GWAS, not established causal mechanisms. Many GWAS hits are tagging SNPs that are correlated with a nearby causal variant but are not themselves causal. Effect sizes consistently shrink in replication studies; estimates from the original GWAS tend to be inflated.

AI-generated modules carry additional uncertainty. They are automated drafts produced by language models reading published papers, and they will contain mistakes. The cross-model consensus mechanism reduces but does not eliminate errors. Users should treat AI-generated modules as lower confidence than expert-curated ones and review the underlying evidence.

Just-DNA-Lite is a research annotation tool, not a clinical pipeline. Raw VCFs contain false positives, and automated annotations have inherent error rates. The platform joins the user's variants against published databases and annotation modules, adding contextual information from those sources; it does not interpret the results in a clinical context.

### 6.2 Data Privacy and GDPR Compliance

Just-DNA-Lite processes all data locally. The VCF file never leaves the user's machine; annotation databases are cached locally after initial download; and results are stored on the local filesystem. No genomic data is transmitted to external servers during normal operation. This architecture is GDPR-friendly by design: the data controller is the user themselves, and no third-party data processing occurs.

This local-first approach addresses a significant concern in personal genomics. Commercial platforms require users to upload their genomic data to company servers, creating privacy risks that are difficult to mitigate retroactively. The open-source nature of Just-DNA-Lite (AGPL v3 licence) allows users and institutions to audit every line of code that touches their data.

### 6.3 Platform Philosophy

Just-DNA-Lite is designed around the principle that researchers and individuals should have transparent, privacy-preserving tools for annotating their own genomic data. In the spirit of global open data initiatives such as the European Health Data Space (EHDS), we believe individuals should have access to tools that let them explore their genomic information locally. The platform provides access to the full annotation stack -- all modules, all 5,000+ PRS scoring files from the PGS Catalog, the complete variant table cross-referenced against Ensembl -- as a research and educational resource. Understanding the limitations described in Section 6.1 is essential for any downstream use of the annotations.

### 6.4 Limitations

**Population stratification.** The 1000 Genomes-based percentile distributions in just-prs provide population-specific reference points (AFR, AMR, EAS, EUR, SAS), but most annotation modules and PGS scoring files were derived from predominantly European cohorts. The transferability of these statistical associations to non-European populations is a known limitation of the underlying source data, not specific to this platform.

[TODO: Is ancestry estimation implemented in just-prs now? If yes, describe how. If no, describe timeline and planned approach.]

**Scope.** Just-DNA-Lite is a research and educational annotation tool. It annotates the user's VCF by joining it against published variant-trait databases and annotation modules. It does not perform clinical interpretation, generate diagnoses, or provide medical recommendations.

**Input format.** The platform currently supports VCF files from whole genome sequencing (WGS) and whole exome sequencing (WES) aligned to GRCh38. GRCh37/hg19 files, T2T reference genomes, and microarray data (23andMe, AncestryDNA) are not yet supported.

**Module quality variation.** Expert-curated modules are subject to the same limitations as their underlying source databases (publication bias, population bias, evolving evidence base). AI-generated modules have additional variability in annotation quality and require user review.

[TODO: Clarify LongevityMap curation status. When was it last updated? What are the plans to extend it?]

### 6.5 Future Directions

Several extensions are planned. Support for GRCh37/hg19 VCF files will broaden compatibility with older sequencing pipelines. T2T (Telomere-to-Telomere) reference genome support will enable annotation of variants in regions that were previously unresolvable. Microarray data support (23andMe, AncestryDNA) will open the platform to a much larger user base. Multi-species support is under consideration for comparative genomics applications. Within the ROGEN consortium, work is underway to develop population-calibrated polygenic risk scores and to apply the platform to the 5,000-individual Romanian genomic cohort.

---

## 7. Conclusion

Just-DNA-Lite demonstrates that personal genome annotation can be fast, transparent, and extensible without sacrificing privacy. By replacing the OakVar dependency with a purpose-built pipeline based on Dagster, Polars, and DuckDB, annotation time drops from hours to seconds. By simplifying the module format to a no-code YAML and CSV specification, the barrier to creating new annotation modules drops from "write Python code" to "describe what you want." And by introducing an AI-assisted module creation system with cross-model consensus, the platform can keep pace with the rapidly expanding genetics literature.

The platform ships with expert-curated modules covering several trait domains alongside over 5,000 polygenic risk scores with validated concordance against PLINK2. All data stays local, the code is open-source, and the design is GDPR-friendly. The platform annotates user variants by joining them against published databases and community-contributed modules, enabling researchers and individuals to explore their genomic data transparently.

---

## Contribution Statements

- **Kulaga Anton** -- co-founded the project, bioinformatic pipeline development, Just-DNA-Lite architecture (Dagster/Polars/DuckDB pipeline, uv workspace), just-prs library development and benchmarking, web UI development, team management, article writing
- **Usanov Nikolay** -- co-founded the project, AI agentic module creation system (PI/Researcher/Reviewer agent swarm, simple mode, Agno framework integration, BioContext MCP), Just-DNA-Lite platform development, fundraising
- **Borysova Olga** -- modules and report content (longevity variants, cardiovascular traits, lipid metabolism, VO2 max, athletic performance, pharmacogenomics), LongevityMap database curation and expansion, pathway categorization, developing the report structure, data collection and analysis
- **Karmazin Alexey** -- lead architect of the Generation I report system, OakVar report modules and preparation utilities, PRS modules
- **Maria Koval** -- report modules, report template, trait annotation modules (thrombophilia-associated variants, cardiovascular trait variants)
- **Fedorova Alina** -- bioinformatic utilities, scientific literature exploration
- **Pushkareva Malvina** -- software development and testing
- **Evfratov Sergey** -- pharmacogenomics (drug) module development
- **Ryangguk Kim** -- created and maintained OakVar, extended OakVar with additional features required for the Generation I Just-DNA-Seq platform
- **Fuellen Georg** -- co-supervision, valuable suggestions and comments
- **Tacutu Robi** -- bioinformatics and ageing research advising, LongevityMap database

**Acknowledgments:**

- Livia Zaharia for beta-testing and providing her genome for tests
- Volodymir Semenuik for help with documentation

---

## Funding

This work was partially supported by the ROGEN project (*Dezvoltarea cercetarii genomice in Romania* / Development of Genomic Research in Romania), project code 324809, funded by the European Regional Development Fund and the Romanian national budget through the Health Programme (PS/272/PS_P5/OP1/RSO1.1/PS_P5_RSO1.1_A9), coordinated by the "Carol Davila" University of Medicine and Pharmacy, Bucharest (implementation period: December 2024 -- December 2029). A.K. and R.T. received funding through this project.

[TODO: Check whether ROGEN requires a specific mandatory acknowledgment text beyond what is stated above. EU co-funded projects often have required language.]

---

## Code Availability

**GitHub Organization:** [https://github.com/dna-seq](https://github.com/dna-seq)

**Table 10.** Software repositories.


| Repository                                                            | Description                                                                     | Generation |
| --------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ---------- |
| [just-dna-lite](https://github.com/dna-seq/just-dna-lite)             | Main platform -- standalone genomic annotation with AI module creation          | Gen II      |
| [just-prs](https://github.com/dna-seq/just-prs)                       | PRS computation library/CLI/UI -- developed for Just-DNA-Lite, released as standalone tool | Gen II      |
| [prepare-annotations](https://github.com/dna-seq/prepare-annotations) | Pipelines converting annotation databases to Parquet format for fast lookups    | Gen II      |
| [reflex-mui-datagrid](https://github.com/dna-seq/reflex-mui-datagrid) | Reflex wrapper for MUI DataGrid component, used for variant browsing in the UI  | Gen II      |
| [just-biomarkers](https://github.com/dna-seq/just-biomarkers)         | Methylation and other biomarker analysis tools                                  | Gen II      |
| [dna-seq](https://github.com/dna-seq/dna-seq)                         | Original DNA-Seq pipeline                                                       | Gen I      |
| oakvar-longevity (and sub-modules)                                    | Original OakVar-based annotation modules                                        | Gen I      |


Annotation modules and reference datasets are published to the [just-dna-seq](https://huggingface.co/just-dna-seq) organization on HuggingFace, which serves as the default source for module auto-discovery. Other fsspec-compatible sources (GitHub, S3, HTTP, Zenodo) are equally supported.

**Table 11.** HuggingFace datasets and models published by the project.


| Resource | Type | Description |
| --- | --- | --- |
| [just-dna-seq/annotators](https://huggingface.co/datasets/just-dna-seq/annotators) | Dataset | Annotation modules in Parquet format (default module source for auto-discovery) |
| [just-dna-seq/ensembl\_variations](https://huggingface.co/datasets/just-dna-seq/ensembl_variations) | Dataset | Ensembl human genetic variations converted to chromosome-level Parquet files (~1.1B rows) |
| [just-dna-seq/clinvar](https://huggingface.co/datasets/just-dna-seq/clinvar) | Dataset | ClinVar variant annotations in Parquet format |
| [just-dna-seq/pgs-catalog](https://huggingface.co/datasets/just-dna-seq/pgs-catalog) | Dataset | PGS Catalog scoring files converted to Parquet for fast PRS computation |
| [just-dna-seq/prs-percentiles](https://huggingface.co/datasets/just-dna-seq/prs-percentiles) | Dataset | Precomputed PRS percentile distributions from 1000 Genomes phase 3 (5 superpopulations) |
| [just-dna-seq/polygenic\_risk\_scores](https://huggingface.co/datasets/just-dna-seq/polygenic_risk_scores) | Dataset | Legacy PRS data from Generation I (Monte Carlo-based percentiles) |
| [just-dna-seq/GenNet](https://huggingface.co/just-dna-seq/GenNet) | Model | GenNet neural network model for genomic prediction |

All projects use uv for dependency management. Tool versions are pinnable via `pyproject.toml` and `uv.lock`.

---

## Competing Interests

- Ryangguk Kim is a co-founder of OakVar Inc., which provides additional services on top of the open-source OakVar platform.
- Anton Kulaga, Olga Borysova, Maria Koval, Nikolay Usanov, and Alex Karmazin are co-founders of SecvADN SRL, a company that provides additional services on top of the open-source modules.

---

## Bibliography

Alteri, E., et al. (2024). The 23andMe data breach: Lessons for genomic data governance and consumer genetic testing. *European Journal of Human Genetics*, 32(11), 1317-1320.

Broer, L., et al. (2014). GWAS of longevity in CHARGE consortium confirms APOE and FOXO3 candidacy. *The Journals of Gerontology: Series A*, 70(1), 110-118.

Caruso, C., et al. (2022). How important are genes to achieve longevity? *International Journal of Molecular Sciences*, 23(10), 5635.

Deelen, J., et al. (2019). A meta-analysis of genome-wide association studies identifies multiple longevity genes. *Nature Communications*, 10(1).

Doffman, Z. (2023). 23andMe confirms 6.9 million user records stolen in data breach. *Forbes*, December 4, 2023.

Gonzalez, A. (2023). Novel variants in nuclear-encoded mitochondrial genes associated with longevity. [TODO: Add complete citation with journal, volume, pages, and DOI.]

Lambert, S. A., et al. (2021). The Polygenic Score Catalog as an open database for reproducibility and systematic evaluation. *Nature Genetics*, 53(4), 420-425.

Landrum, M. J., et al. (2017). ClinVar: improving access to variant interpretations and supporting evidence. *Nucleic Acids Research*, 46(D1), D1062-D1067.

Lin, J.-R., et al. (2021). Rare genetic coding variants associated with human longevity and protection against age-related diseases. *Nature Aging*, 1(9), 783-794.

Lunetta, K. L., et al. (2007). Genetic correlates of longevity and selected age-related phenotypes. *Human Genetics*, 120(6), 732-745.

Pilling, L. C., et al. (2016). Gene-by-gene contributions to human longevity. *Aging Cell*, 15(5), 941-947.

Pilling, L. C., et al. (2017). Human longevity: 25 novel genetic loci associated in 389,166 UK biobank participants. *Aging*, 9(12), 2504-2520.

Revelas, M., et al. (2018). Review and meta-analysis of genetic polymorphisms associated with exceptional human longevity. *Mechanisms of Ageing and Development*, 175, 24-34.

Sebastiani, P., & Perls, T. T. (2012). The genetics of extreme longevity: lessons from the New England centenarian study. *Frontiers in Genetics*, 3.

Shenhar, B., Pridham, G., Lopes De Oliveira, T., Yang, Y., Raz, N., Deelen, J., Hägg, S., & Alon, U. (2025). Heritability of human lifespan is about 50% when confounding factors are addressed. *Science*. https://doi.org/10.1126/science.adz1187

Sebastiani, P., et al. (2012). Genetic signatures of exceptional longevity in humans. *PLoS ONE*, 7(1).

Tacutu, R., et al. (2017). Human Ageing Genomic Resources: New and updated databases. *Nucleic Acids Research*, 46(D1), D1083-D1090.

Tesi, N., et al. (2020). Polygenic risk score of longevity predicts longer survival across an older cohort. *The Journals of Gerontology: Series A*, 76(5), 750-759.

van den Berg, N., et al. (2019). Longevity defined as top 10% survivors and beyond is transmitted as a quantitative genetic trait. *Nature Communications*, 10(1).

Whirl-Carrillo, M., et al. (2021). An evidence-based framework for evaluating pharmacogenomics knowledge for personalized medicine. *Clinical Pharmacology & Therapeutics*, 110(3), 563-572.

Whitley, K. V., et al. (2020). Direct-to-consumer genetic testing: an updated systematic review of healthcare professionals' knowledge and views, and ethical and legal concerns. *European Journal of Human Genetics*, 28(8), 1063-1074.

Yashin, A. I., et al. (2010). Joint influence of small-effect genetic variants on human longevity. *Aging*, 2(9), 612-620.

Yashin, A. I., et al. (2015). Genetics of human longevity from incomplete data: new findings from the long life family study. *The Journals of Gerontology: Series A*, 70(12), 1531-1540.

Zeng, Y., et al. (2016). Novel loci and pathways significantly associated with longevity. *Scientific Reports*, 6, 21243.

Zhang, Z. D., et al. (2020). Genetics of extreme human longevity to guide drug discovery for healthy ageing. *Nature Metabolism*, 2(8), 663-672.

[TODO: Update bibliography with 2022--2026 publications. Anton to provide >= 5 key references with DOIs.]

---

## Supplementary Material

### S1. Generation I: OakVar-Based Just-DNA-Seq Platform

The original Just-DNA-Seq platform (Generation I) was built on OakVar, a Python-based genomic variant analysis platform forked from OpenCRAVAT. This section describes the Generation I architecture, pipeline, and module internals for historical reference.

**Architecture.** Just-DNA-Seq operated as a set of custom OakVar modules (annotators, post-aggregators, and reporters). The platform depended on OakVar's built-in integration with dbSNP (rsID resolution), ClinVar (clinical significance), OMIM (Mendelian inheritance), NCBI Gene (general annotation), PubMed (article information), and gnomAD (population allele frequencies). Functional impact prediction was provided by SIFT, PolyPhen, and CADD scores.

**Pipeline.** Users uploaded VCF files through OakVar's web interface or command line. OakVar performed variant annotation against its built-in databases, after which Just-DNA-Seq's custom post-aggregators computed longevity scores, polygenic risk scores, drug interactions, and disease risk assessments. Results were displayed through OakVar's viewer or exported as reports.

**Module types.** Four categories of modules were provided: (1) Longevity Variants -- a weighted list of longevity-associated SNPs from LongevityMap with manual curation, (2) Polygenic Risk Scores -- Monte Carlo sampling with gnomAD frequencies, (3) Longevity Drugs -- pharmacogenetic information from PharmGKB, and (4) Health Risks -- filter-based and table-based modules for thrombophilia, cardiovascular disease, coronary artery disease, cancer risk, and lipid metabolism.

**Repository table.**


| Repository           | Description                                            |
| -------------------- | ------------------------------------------------------ |
| oakvar-longevity     | All modules and longevity reporter                     |
| longevity2reporter   | Genome analysis related to longevity and disease risks |
| just_longevitymap    | Longevity map post-aggregator                          |
| just_prs             | Polygenic risk score post-aggregator                   |
| just_drugs           | Drugs post-aggregator                                  |
| just_cancer          | Cancer post-aggregator                                 |
| just_cardio          | Cardiovascular disease post-aggregator                 |
| just_coronary        | Coronary disease post-aggregator                       |
| just_lipidmetabolism | Lipid metabolism post-aggregator                       |
| just_thrombophilia   | Thrombophilia risks post-aggregator                    |


### S2. Generation I vs Generation II Speed Comparison

Just-DNA-Lite (Generation II) provides a 172-fold speedup over OakVar (Generation I) on the same hardware and input VCF. The following table provides the individual OakVar benchmark runs for reference.


| Date         | OakVar runtime (s) | tagsampler (s) |
| ------------ | ------------------ | -------------- |
| 2023-02-17   | 5,651              | 322            |
| 2023-02-19   | 6,803              | 268            |
| 2023-05-07   | 7,662              | 328            |
| Mean +/- SEM | 6,705 +/- 583      |                |


The speedup is attributable to three architectural changes: (1) replacing OakVar's SQLite-based annotation pipeline with Polars streaming joins against Parquet files, (2) eliminating the dependency on OakVar's multi-step annotator pipeline (converter, mapper, annotators, aggregator, post-aggregators), and (3) using DuckDB for large joins with predicate pushdown and column pruning.

### S3. Runtime on Large PRS Scoring Files

For the 7 genome-wide PGS IDs with >= 1M variants, the following runtimes were observed:


| PGS ID    | Variants  | Polars (s) | DuckDB (s) | PLINK2 |
| --------- | --------- | ---------- | ---------- | ------ |
| PGS000014 | 6,917,436 | 6.72       | 6.42       | Failed |
| PGS000017 | 6,907,112 | 6.77       | 6.42       | Failed |
| PGS000016 | 6,730,541 | 6.65       | 6.28       | Failed |
| PGS000013 | 6,630,150 | 6.71       | 6.42       | Failed |
| PGS000039 | 3,225,583 | 4.12       | 3.84       | 1.79   |
| PGS000027 | 2,100,302 | 2.48       | 2.28       | 1.71   |
| PGS000018 | 1,745,179 | 2.32       | 2.23       | 1.41   |


PLINK2 failed on the four largest scoring files because these genome-wide files contain variants without a matching 4-part `chr:pos:ref:alt` ID in the autosomes-only pgen. For the three files where PLINK2 succeeded, it was faster due to compiled C++ SIMD operations on pre-indexed data.

[TODO: Supplementary file to be prepared separately as a standalone document.]