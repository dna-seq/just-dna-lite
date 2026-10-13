# **Just-DNA-Lite: a Local-First, Open-Source Platform for Personal Genome Annotation and Polygenic Risk Scoring**

> **Draft v0.4 (Paper 1 of 2).** This is the platform paper: the local-first platform and the compute engines it runs — the annotation pipeline, the just-prs computation library **and its `just-prs-mcp` access layer**, the no-code module format, the web UI, `just-dna-format`, and the module registry. The boundary with the companion paper is *consuming* versus *authoring*: this paper covers how a compiled module or a published score is discovered, computed against a genome, and reported, including from an AI assistant that calls these operations as typed tools. The companion paper covers the other direction — an assistant *producing* new annotation content: the authoring plugin, the enrichment and compilation toolchain, and how modules are published and versioned. It is *Creating and Sharing Genomic Annotation Modules with AI: The Just-DNA Ecosystem* (in review at EASRP 2026; `paper2-just-module-creator.md`). See `docs/manuscript/v0.3/manuscript-strategy-v0.3.md`.

**Authors:** Kulaga Anton^1,2,4^, Usanov Nikolay^3,4^, Borysova Olga^4^, Karmazin Alexey^4^, Koval Maria^4^, Fedorova Alina^4^, Pushkareva Malvina^4^, Evfratov Sergey^4^, Ryangguk Kim^8^, Zaharia Livia^3^, Fuellen Georg^1,\*^, Tacutu Robi^2,9,\*^

**Affiliations:**

1. Institute for Biostatistics and Informatics in Medicine and Ageing Research, Rostock University Medical Center, Rostock, Germany
<!-- @rev R1 rounds=1 by=robi:2026-09-25 -->
2. Institute of Biochemistry of the Romanian Academy, Bucharest, Romania
<!-- @/rev R1 -->
3. HEALES (Healthy Life Extension Society)
4. SecvADN SRL
5. CellFabrik SRL
6. MitoSpace
7. M. Glushkov Institute of Cybernetics of National Academy of Sciences of Ukraine
8. Oak Bioinformatics, LLC
<!-- @rev R2 rounds=1 by=robi:2026-09-25 -->
9. Romanian Bioinformatics Cluster, Târgu Mureș, Romania
<!-- @/rev R2 -->

The contribution of these authors is considered to be equal. \* Co-supervising authors.

---

## **Abstract**

<!-- @rev C2a rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->
As genome sequencing becomes increasingly available, personal genome analysis requires tools that make published variant associations accessible while allowing users to inspect the methods and retain control of their data.
<!-- @/rev C2a -->

<!-- @rev C2b rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->
We present Just-DNA-Lite, an open-source platform that combines local variant annotation and polygenic risk score (PRS) computation in a web interface. Annotation modules are declarative, versioned packages of variant-trait tables and their sources, allowing researchers to extend the catalogue without writing code. A registry distributes modules, and the platform applies them to the user's genome to produce downloadable reports. The just-prs library provides scoring through web, command-line, Python, and Model Context Protocol interfaces.
<!-- @/rev C2b -->

<!-- @rev C2c rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->
Reports list each matched variant with its reported effect and sources. Polygenic scores are shown as percentiles within a reference population matched to the genome's inferred ancestry, with all models for a trait shown together. New modules can also be drafted with general-purpose AI assistants through a plugin, and pass the same validation as hand-written ones.
<!-- @/rev C2c -->

Core annotation and scoring run locally, with reference datasets downloaded and cached on the user's machine. Optional external AI services introduce a separate data-sharing boundary. Just-DNA-Lite is released under AGPL v3 for research and education; it does not provide diagnoses or establish clinical validity for the associations it reports.

## **1. Introduction**

<!-- @rev C3 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->
By 2025, manufacturers listed the sequencing consumables for a human genome at US$80 to US$200 (Illumina, 2023; Ultima Genomics, 2025), and studies that count the full cost, including labour, equipment and analysis, put a genome at a few thousand dollars (Mordaunt et al., 2024; Ehman et al., 2025), against an estimated $500 million to $1 billion for the first one (NHGRI, 2021). Several companies now offer direct-to-consumer sequencing services (O'Daniel et al., 2025).<!-- @/rev C3 --> Yet the gap between sequencing accessibility and variant annotation remains wide. Researchers and individuals receive raw variant files (VCFs) containing millions of variants <!-- @rev C4 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->but often lack accessible means to annotate them against published databases without specialized bioinformatics expertise, a learning curve that takes time away from the questions they set out to answer (Nelson et al., 2019; Chen et al., 2023; O'Daniel et al., 2025).<!-- @/rev C4 -->

<!-- @rev R3 rounds=1 by=robi:2026-09-25 -->
Existing solutions generally belong to two extremes. Commercial platforms such as DNA Complete (formerly Nebula Genomics) and Dante Labs provide curated reports, but the curation is opaque: users cannot verify which polymorphisms contributed to a score, whether the methodology is appropriate for their ancestry, or how findings were weighted. At the other end, research-grade tools like PLINK, ANNOVAR, and VEP are powerful but demand command-line proficiency and significant setup effort. There is no open-source platform that combines comprehensive variant annotation with ease of use, transparency, and extensibility.
<!-- @/rev R3 -->

<!-- @rev R4 rounds=1 by=robi:2026-09-25 -->
The recent progress in the genetics of longevity illustrates the need for such extensible annotation tools. The field is rapidly evolving: traditional twin studies placed the heritability of lifespan at 20–25%, but a recent study in *Science* by Shenhar et al. (2025) estimates the intrinsic heritability at approximately 50% after correcting for extrinsic mortality confounders. GWAS studies have identified candidate loci including APOE and FOXO3 as consistently associated with longevity across populations (Broer et al., 2014; Caruso et al., 2022), and the catalogue of longevity-associated variants continues to grow. Databases such as LongevityMap within the Human Ageing Genomic Resources (HAGR) (Tacutu et al., 2017) have compiled thousands of variant-trait associations, but no existing tool makes it straightforward to annotate a personal VCF against these databases transparently and extensibly. This brings to focus a broader pattern: variant-trait associations are published faster than any single curation team can integrate them, supporting the need for platforms where new annotation modules can be added rapidly.
<!-- @/rev R4 -->

A platform for personal genome annotation must therefore solve three problems simultaneously: it must be easy to use (web interface, no bioinformatics training), transparent in its methods (open-source, auditable scoring), and extensible (researchers should be able to add new annotation modules as the literature evolves, without writing code). Furthermore, privacy is a first-order concern: genomic data is among the most sensitive personal information, and uploading it to third-party servers introduces risks that many individuals and regulatory frameworks (such as the GDPR and the European Health Data Space) seek to avoid.

<!-- @rev R5 rounds=1 by=robi:2026-09-25 -->
<!-- @rev C5 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->
Just-DNA-Lite is a local, open-source platform for annotating a personal genome and computing polygenic scores. We developed it as a ground-up rewrite of Just-DNA-Seq (Kulaga et al., 2024), whose first generation (Generation I) was a set of annotation and report modules for OakVar, a Python variant-analysis framework derived from OpenCRAVAT. Just-DNA-Lite removes the OakVar dependency entirely and replaces it with our own standalone annotation engine, built with Dagster for workflow orchestration, polars-bio, a genomics library with a Polars interface (Wiewiórka et al., 2025), for VCF reading, Polars for columnar processing, and DuckDB for out-of-core joins. It also replaces Python annotation plugins with declarative modules discoverable from configured sources (Section 2.2). Supplementary File S1 describes Generation I.
<!-- @/rev C5 -->
<!-- @/rev R5 -->

<!-- @rev C6 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->
This paper presents the standalone annotation engine, the reusable just-prs scoring library, the web interfaces, and MCP interfaces for calling these tools programmatically from AI assistants. Together, these components let users discover annotation content, apply it to a genome, compute published polygenic scores, and inspect reports.
<!-- @/rev C6 -->

## **2. Platform Architecture**

The architecture separates local computation, annotation content, and user interfaces. The annotation pipeline reads modules as data artifacts, allowing the catalogue to change independently of the application code. Columnar storage and streaming operations limit memory use. A graphical web application provides the main interface, while typed MCP tools expose the PRS engine to AI assistants (Section 3.2.1). Local execution avoids requiring genome uploads for core analysis; optional external services have a separate privacy boundary (Section 5.2).

Just-DNA-Lite is structured as a uv workspace containing two Python packages: just-dna-pipelines (Dagster assets, VCF processing, annotation logic, and CLI tools) and webui (a Reflex-based web interface). The platform requires Python 3.13+; from a configured checkout, `uv run serve` starts the application. Core annotation and scoring execute on the host machine.

### **2.1 Annotation Pipeline**

The core annotation pipeline is built on Dagster with Software-Defined Assets, providing automatic data lineage tracking and resource monitoring (CPU usage, peak memory, and duration for every pipeline step). A typical annotation workflow proceeds as follows:

1. **VCF ingestion.** The user provides a VCF or VCF.gz file through the web interface. This is the annotated variant file users typically already have — supplied by a sequencing provider, downloaded from a public genome repository, or produced by their own bioinformatic pipeline; Just-DNA-Lite starts from this VCF and does not itself perform sequencing, alignment, or variant calling. <!-- @rev N5 rounds=1 by=claude:2026-10-10 -->The file is read using polars-bio, "a Python library that enables fast, parallel and out-of-core operations on large genomic interval datasets", whose "main components are implemented in Rust, using the Apache DataFusion query engine and Apache Arrow for efficient data representation" (Wiewiórka et al., 2025).<!-- @/rev N5 -->
<!-- @rev R6 rounds=1 by=robi:2026-09-25 -->
2. **Normalization.** The raw VCF undergoes quality filtering (configurable via `modules.yaml`): only variants passing specified FILTER values (by default, PASS and ".") are retained, with optional minimum depth (DP ≥ 10) and quality (QUAL ≥ 20) thresholds. <!-- @rev N4 rounds=1 by=claude:2026-10-10 -->Chromosome names are normalized ("chr7" becomes "7", "chrM" becomes "MT") for consistency with annotation databases.<!-- @/rev N4 --> The normalized data is written as a Parquet file, which serves as the shared input for all downstream annotations.
<!-- @/rev R6 -->
3. **Module annotation.** For each selected annotation module, the pipeline performs a streaming join between the normalized VCF Parquet and the module's precomputed weights Parquet. Joins are performed by rsID (default) or genomic position. Polars streaming joins keep peak memory low; for datasets too large to fit in memory, DuckDB handles out-of-core joins with configurable memory limits.
4. **Ensembl annotation (optional).** When enabled, the pipeline joins the normalized VCF against the Ensembl Variation database (cached locally as chromosome-level Parquet files downloaded from HuggingFace via fsspec), providing clinical significance labels, consequence types, and cross-references for each variant.
5. **Report generation.** Annotated results are written as Parquet files and rendered as downloadable PDF/HTML reports. All outputs are available for downstream analysis in Python, R, or any tool that reads Apache Arrow.

The annotation data for reference databases and modules is prepared upstream by the prepare-annotations pipeline (github.com/dna-seq/prepare-annotations), which converts source databases into columnar Parquet format optimized for fast lookups.

### **2.2 Modular Plugin System**

<!-- @rev R7 rounds=1 by=robi:2026-09-25 -->
For the purpose of Just-DNA-Lite, annotation modules are viewed as data, not executable plugins. The annotation engine reads published Parquet tables directly. A typical weighted-association module contains `weights.parquet`, with accompanying `annotations.parquet` and `studies.parquet` when available; other module families can use different primary tables. Existing Parquet modules can be discovered and used without supplying YAML/CSV authoring files or recompiling them.
<!-- @/rev R7 -->

The `just-dna-format` library defines the authored specification and the manifest, integrity, and versioning contract for compiled artifacts. When a published module supplies a manifest, discovery uses its declared artifact files. For older Parquet modules without a manifest, the loader discovers the available tables directly.

<!-- @rev R8 rounds=1 by=robi:2026-09-25 -->
For researchers creating new modules, a separate authoring route accepts `module_spec.yaml` and CSV tables such as `variants.csv` and `studies.csv`. The `just-dna-compiler` library validates and compiles these specifications into Parquet artifacts and a manifest during custom-module registration. Documentation and thumbnails may accompany the module. This route lets authors prepare annotation content <!-- @rev C10 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->without writing Python code. CSV files are used only for authoring: at runtime the platform reads the compiled Parquet tables, so existing Parquet modules need no CSV files.<!-- @/rev C10 -->
<!-- @/rev R8 -->

<!-- @rev R9 rounds=1 by=robi:2026-09-25 -->
Module discovery uses sources configured in `modules.yaml`, with repository defaults and a local working copy for runtime changes. Sources may include HuggingFace datasets, GitHub repositories, HTTP/HTTPS servers, cloud storage, or local paths accessible through fsspec. The loader detects single modules and collections, and configuration can override display metadata without changing an artifact. The `just-dna-registry` service provides a catalogue for browsing and retrieving versioned modules. Artifact manifests provide identity and integrity information; of note - integrity verification establishes that downloaded content matches the recorded artifact, not that its scientific claims are correct.
<!-- @/rev R9 -->

### **2.3 Web Interface and Self-Exploration**

<!-- @rev R10 rounds=1 by=robi:2026-09-25 -->
The web interface is built with Reflex, a Python framework that compiles to React; the entire UI is written in Python, with no JavaScript required. The interface provides file management (upload VCFs, select modules, launch annotation), module selection (browse modules, toggle Ensembl annotation), a results preview (sortable, filterable data grid in the browser), report download (PDF/HTML per module), and self-exploration. Users can browse the full variant table with sorting, filtering, and search, cross-referenced against Ensembl for clinical significance labels, consequence types, and known phenotype associations. All data can be exported as Parquet for downstream analysis in Python, R, DuckDB, or any Arrow-compatible tool.
<!-- @/rev R10 -->

**Figure 1.** The Just-DNA-Lite web interface showing the annotation results view with module selection, variant data grid, and report download options.

### **2.4 Performance Characteristics**

Consistent with the "runs on a laptop" principle, Just-DNA-Lite prioritizes memory efficiency over raw throughput: peak RAM stays low enough for a personal computer, and warm-run annotation of a whole genome completes in tens of seconds. Detailed speed and memory benchmarks — including the comparison against the Generation I OakVar-based system — are presented in Section 4.1.

## **3. Annotation Modules and Polygenic Scoring**

<!-- @rev R11 rounds=1 by=robi:2026-09-25 -->
Just-DNA-Lite ships with a set of annotation modules, <!-- @rev C13a rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->either curated by experts from the published literature or derived from public databases (ClinVar, ClinPGx)<!-- @/rev C13a -->, illustrating the platform's module system across several trait domains. These modules represent the default set. The platform is designed so that researchers from the scientific community (eg: bioinformaticians, geneticists, etc.) can easily add their own modules, either by hand or with AI assistance (Section 3.4). The modules annotate user variants against published variant-trait association databases; they do not perform clinical interpretation or generate diagnoses.
<!-- @/rev R11 -->

<!-- @rev R12 rounds=1 by=robi:2026-09-25 -->
The default modules originate in the first generation of the platform, the OakVar-based Just-DNA-Seq (Kulaga et al., 2024). That system was built around longevity and longevity-associated traits, which is why the default set centres on that domain; for the second generation, most modules were ported, largely unchanged, to serve as worked examples of the no-code module format rather than as a definitive trait catalogue.
<!-- @/rev R12 -->

<!-- @rev C13b rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->
**Table 1.** Annotation modules published by the Just-DNA-Lite project in the module registry (namespace `just-dna-seq`), as of 2026-10-10 18:00 UTC. Later versions may differ; versions, digests and every source are listed in Table S4.

| Module | Description | Curator |
|---|---|---|
| Longevity Map | Longevity-associated variants from the LongevityMap database, ported from the Generation I module: 528 variants in 272 genes, citing 126 papers (sources in Table S4) | Expert (Olga Borysova) |
| Coronary Artery Disease | Coronary artery disease risk associations from published studies, ported from the Generation I module: 27 variants in 22 genes, citing 59 papers (sources in Table S4) | Expert |
| Lipid Metabolism | Lipid metabolism and cardiovascular risk variants from published studies: 15 variants in 12 genes, citing 37 papers (sources in Table S4) | Expert |
| VO2 Max | Published studies of the oxygen-uptake response to exercise training: 13 variants in 12 genes, citing 7 papers (sources in Table S4) | Expert |
| Superhuman (protective alleles) | Rare protective and enhancing alleles from the Church laboratory's list, checked against the primary literature: 74 variants in 28 genes, citing 29 papers (sources in Table S4) | Expert |
| Thrombophilia | Inherited blood-clotting risk variants (Factor V Leiden, prothrombin and related loci) from published studies: 8 variants in 8 genes, citing 24 papers (sources in Table S4) | Expert |
| Cardio | Pathogenic and likely pathogenic variants from ClinVar (release 2026-06-27, review status of at least one star) in 297 cardiac-disease genes (sources in Table S4) | Database-derived (ClinVar) |
| Cancer | Pathogenic and likely pathogenic variants from ClinVar (release 2026-06-27, at least one star) in 298 cancer-predisposition genes (sources in Table S4) | Database-derived (ClinVar) |
| Pathogenic | Genome-wide flag for ClinVar pathogenic and likely pathogenic variants (release 2026-06-27, at least one star) across 4,793 genes (sources in Table S4) | Database-derived (ClinVar) |
| Pharmacogenomics | Drug response by genotype from the ClinPGx (PharmGKB) clinical annotations at evidence levels 1A to 2B (release 2025-07-05): 240 annotations, 65 drugs, 35 genes (sources in Table S4) | Database-derived (ClinPGx) |
<!-- @/rev C13b -->

### **3.1 Longevity Variants Module (example)**

The Longevity Variants module illustrates how existing variant-trait association databases can be wrapped into the platform's no-code module format. It builds upon the LongevityMap database (Tacutu et al., 2017), which contains 3,144 variant-trait associations in 884 genes. Our contribution here is not re-annotation or re-validation of these variants, but (1) curation and expansion with post-2017 literature, adding 50 new entries and editing 876 existing records; (2) assignment of weighted scores based on study quality, replication across populations, and statistical significance; and (3) pathway-based categorization for structured browsing.

The module's weighting scheme assigns two independent weight components whose product yields the displayed score. The SNP weight (*w*_SNP) is an integrative parameter reflecting the strength of statistical evidence for a variant-trait association (number of independent significant studies, reported p-values, number of replicating populations). The genotype weight (*w*_genotype) captures the direction and magnitude of the reported association for a specific genotype: 0 for the reference genotype, ±0.5 or ±1.0 for heterozygous or homozygous carriers of the positively or negatively associated allele. The displayed score is *W*_display = *w*_SNP × *w*_genotype. For structured browsing, variants are grouped into 12 functional pathway categories (lipid transfer, insulin/IGF-1 signalling, antioxidant defence, mitochondrial function, sirtuins, mTOR, tumour suppressors, renin-angiotensin system, heat-shock proteins, inflammation, genome maintenance, and other pathways). This categorization demonstrates how the module format supports structured presentation of variant annotations without requiring code.

**Figure 2.** Just-DNA-Lite UI: the Longevity Variants report, showing pathway categorization, the per-variant SNP table, and colour-coded weights.

### **3.2 Polygenic Risk Scores**

Polygenic risk scores (PRS) aggregate the effects of many common variants into a single weighted sum, providing a population-relative measure for a given trait (Lambert et al., 2021). We developed the just-prs library (github.com/dna-seq/just-prs) as the PRS computation engine for Just-DNA-Lite. Although it powers PRS inside the platform, just-prs is a self-contained, separable component: it can equally be used on its own as a Python library, a command-line tool, an MCP server and agent skill (Section 3.2.1), or as a lightweight standalone PRS web application. just-prs provides access to all 5,000+ scoring files in the PGS Catalog.

<!-- @rev C16 rounds=3 by=robi:2026-09-25,claude:2026-10-10,validator:2026-10-10 -->
Generation I derived its PRS percentiles by simulating 10,000 genotypes from pooled gnomAD allele frequencies and fitting a normal distribution to the simulated scores. just-prs instead scores the 3,202 individuals of the 1000 Genomes reference panel with each model, summarises the observed scores as a mean and standard deviation for each of five superpopulations (AFR, AMR, EAS, EUR, SAS), and places a user's score on the corresponding normal distribution, so the reference reflects real genotypes and their linkage structure rather than simulated ones.<!-- @/rev C16 --> Users select the reference population closest to their ancestry, and the percentile reflects their position within that distribution.

<!-- @rev R13 rounds=1 by=robi:2026-09-25 -->
just-prs provides two scoring engines: **DuckDB** (SQL-based, out-of-core scoring) and **Polars** (LazyFrame joins). <!-- @rev C17 rounds=3 by=robi:2026-09-25,claude:2026-10-10,validator:2026-10-10 -->For diploid genotypes both engines compute the same score. They join the scoring file to the genome by chromosome and position, match the effect allele to the reference or alternate allele of the genotype record, take its dosage (0, 1 or 2), and sum dosage times effect weight. No strand flipping is applied, so an effect allele that matches neither allele contributes a dosage of 0; missing genotypes contribute nothing. The engines differ in how the join runs. DuckDB runs it as SQL, joining large scoring files in chunks of 250,000 to 2,000,000 variants sized from available memory, under a memory limit of 75% of RAM by default. Polars runs it as a single lazy in-memory dataframe join.<!-- @/rev C17 --> PLINK2 is used only as an external benchmark comparator to assess agreement with an established tool; it is not provided as a just-prs scoring engine. Section 4.2 reports runtime and numerical agreement. In the web interface, users browse the PGS Catalog in a searchable grid, select scores, and click "Compute"; results show the score sum, matched-variant count, and percentile within the selected superpopulation.
<!-- @/rev R13 -->

For variant-only whole-genome VCFs, just-prs offers optional reference-homozygote restoration. A reference-allele dataset resolves otherwise unscorable absent loci, allowing them to contribute as homozygous reference when the user selects this mode. This can increase scoring-file coverage for many scores, under the assumption that the absent loci were callable and homozygous reference. Restoration is off by default; it is not applied to gVCF inputs, and array restoration is restricted to eligible chip positions with matching reference data.

The consumer-array workflow accepts formats such as 23andMe and AncestryDNA and uses precomputed linkage disequilibrium (LD) proxy tables to estimate untyped scoring variants from typed proxies where suitable tables are available. LD-based estimation and reference-homozygote restoration address different sources of missingness: the former uses correlations between loci, while the latter assigns reference genotypes to eligible absent loci. Coverage and the assumptions used to recover missing information remain part of the result's interpretation.

**Figure 3. PRS results in Just-DNA-Lite (just-prs trait view).** For a selected trait, all associated PGS Catalog models are computed and shown together as a consensus distribution with the user's percentile against a 1000 Genomes reference population, alongside per-model variant match rates and quality tiers. Showing the models together — including where they disagree — is deliberate (see Section 5.3).

<!-- AUTHOR TODO: Replace the existing images/just_prs_trait_consensus.jpg with a current screenshot for Figure 3. The existing image shows an absolute-risk percentage for intelligence and inconsistent quality labels. Capture a current trait view with the reference population, model IDs, coverage, and settings visible, then embed it here and align the caption with the final image. -->

### **3.2.1 Standalone PRS Use and MCP Access**

just-prs serves both as a component of Just-DNA-Lite and as an independent tool. Users who only want polygenic scores can use its Python API, command-line interface, dedicated web UI, or `just-prs-mcp` server without running the annotation-module workflow. These entry points reuse the library's scoring, catalogue, and reference-panel logic.

The platform also provides an MCP interface for calling Just-DNA-Lite's broader genome-analysis workflow programmatically. This interface serves users working with the full platform, while `just-prs-mcp` provides independent access to PRS operations. Both let AI assistants call the underlying software through typed tools rather than write their own analysis routines.

The PRS tools support catalogue search, model-metadata inspection, genome-build and ancestry detection, input normalization, scoring, reference-population comparison, and result-quality assessment. Trait reports bring multiple models together with their identifiers, variant coverage, and population context. This gives users a report they can inspect alongside the assistant's explanation.

<!-- @rev R14 rounds=1 by=robi:2026-09-25 -->
The tools return PGS IDs, variant-match rates, model quality tiers, reference populations, percentiles, and agreement or disagreement amongst models for a trait. These fields provide the assistant with computational context, however, their presence does not ensure that an assistant will explain them correctly. The server runs locally, but a remotely hosted assistant may receive tool outputs containing genomic results. Local scoring and private conversational processing therefore require separate consideration (Section 5.2).
<!-- @/rev R14 -->

The web application, Python library, command line, standalone PRS interface, and MCP client share the scoring implementation. Equivalent inputs, engine selection, reference data, and settings are required for equivalent results; the engine benchmark in Section 4.2 does not independently test every interface or the accuracy of assistant-generated explanations.

### **3.3 Additional Trait Annotation Modules**

<!-- @rev C18 rounds=3 by=robi:2026-09-25,claude:2026-10-10,validator:2026-10-10 -->
The platform includes several additional modules curated by hand from the published literature: **coronary artery disease** (SNPs selected on meta-study p-values and the number of studies across populations), **lipid metabolism** (selected by the same criteria), **VO2 max** (published studies of the oxygen-uptake response to exercise training, mostly candidate-gene and cohort studies) and **Superhuman** (rare protective alleles from the Church laboratory's Protective and Enhancing Alleles list, checked against the primary literature). Table S4 gives each module's curation and every source it cites.<!-- @/rev C18 --> All modules work by joining the user's VCF against curated variant-trait databases, adding annotation columns (weight, state, gene, conclusion) to matching variants. They do not calculate individual risk, generate diagnoses, or make clinical recommendations.

### **3.4 Growing the Module Ecosystem**

The default set is extensible through the same module contract used by the application and registry. Researchers can prepare variant tables and metadata, compile them into portable artifacts, and distribute versions through configured repositories or `just-dna-registry`. Users can then select the resulting modules without modifying the annotation engine. This separates content updates from application releases, while leaving evidence review and scientific curation with module contributors. <!-- @rev D1 rounds=1 by=claude:2026-10-10 -->Rather than embedding its own assistant, the platform exposes its operations to the AI assistants authors already use. Modules can be drafted in such an assistant through the just-module-creator plugin (github.com/dna-seq/just-module-creator); the result is the same artifact, validated and compiled the same way, and its curator field marks it as AI-generated. Through the platform's MCP server, the assistant can then install the draft, annotate a genome with it and inspect the result (Section 3.2.1).<!-- @/rev D1 -->

## **4. Benchmarking and Validation**

### **4.1 Annotation Speed**

<!-- @rev B22 rounds=2 by=claude:2026-10-11,claude:2026-10-12 -->
We benchmarked Just-DNA-Lite against the Generation I OakVar-based system on the same workstation (Table 4). The main input was the whole-genome VCF of one of the co-authors, released publicly on Zenodo (record 18370498, CC0; 6,079,744 records called with DeepVariant 1.1.0 against GRCh38), the same genome used for the PRS benchmark in Section 4.2. Three more inputs vary the caller and the size: a second co-author's public genome, called with DRAGEN (Zenodo record 19487816, CC-BY-4.0), the HG002 output of the DeepVariant 1.0.0 whole-genome case study, and the private genome on which the earlier Generation I times were measured, on another workstation (Supplementary S2). The benchmark is therefore reproducible on the three public genomes, Generation I given an OakVar store account (the store serves its current module versions, recorded in Table S2);<!-- @rev B27 rounds=1 by=claude:2026-10-11 --> the benchmark scripts, the record of every run and the script that generates Tables 2 to 6 from them are in the repository (`docs/manuscript/benchmarks/a3/`),<!-- @/rev B27 --> and the pipeline can equally be run on any standard whole-genome VCF.
<!-- @/rev B22 -->

<!-- @rev B24 rounds=3 by=claude:2026-10-11,claude:2026-10-12,claude:2026-10-13 -->
Generation II annotated each genome with the ten modules of Table 1, with Ensembl annotation off, in three modes. A *warm* run repeats the analysis of a sample whose quality-filtered table already exists, so the VCF is not read again. A *full* run starts from a fresh instance and reads the VCF, as every OakVar run does, so it is the counterpart of an OakVar run (same VCF and same kind of report, not the same computation). A *cold* run is a full run after the operating system's page cache has been dropped. After one warm-up run, the Generation II runs of each genome were interleaved in a seeded random order. Generation I ran with no warm-up, using its nine postaggregator modules (it has no counterpart of the Pathogenic module): three times on the primary genome and once on the calibration genome on one night, and twice more on the calibration genome and once on the second-caller genome on a second night, so that its spread includes the differences in page cache and machine load between nights. To compare annotation against a whole-genome reference database, Generation I also ran three times on the primary genome with its dbSNP annotator alone and a VCF report, and Generation II three times with Ensembl annotation on; the two are not the same computation, since Generation II also ran its ten modules and wrote its report, and OakVar's run includes its GENCODE gene mapper. Neither of these two series had a warm-up, and the first run of each, which read its database from disk for the first time (OakVar's annotator step took 3,520.3 s, against 608.1 and 574.8 s in the next two runs), is dropped as the warm-up; both first runs are in the repository's record of runs. It ran OakVar 2.13.1, the latest release at the time (published 2026-08-30), with the Generation I modules and annotation databases installed from the OakVar store in October 2026, in a Docker image that adds one compatibility line for the store's dbSNP annotator. Some store versions of the Generation I modules differ from those on GitHub; Table S2 lists the versions that ran beside both. All 2026 runs, Generation I included, used the same workstation.
<!-- @/rev B24 -->

<!-- @rev C22 rounds=2 by=claude:2026-10-11,claude:2026-10-13 -->
**Table 2.** Annotation wall time, from command start to report written: Just-DNA-Lite (Generation II) vs OakVar (Generation I). *n*, number of repeated runs. The last column divides the median Generation I time by the median of the row; a warm run does not read the VCF, so it is not compared. In the last section, the reference is Generation I with its dbSNP annotator alone, and the first run of each series is dropped as its warm-up.

| Genome / run | *n* | Median (min–max), s | Mean ± SEM, s | SD, s | Generation I ÷ this (medians) |
|---|---|---|---|---|---|
| **Primary (public, Zenodo 18370498)** |  |  |  |  |  |
| Generation II, warm | 11 | 16.3 (16.2–17.2) | 16.4 ± 0.1 | 0.3 | — |
| Generation II, full | 5 | 32.7 (31.9–50.8) | 36.8 ± 3.6 | 8.1 | 183× |
| Generation II, cold | 3 | 35.9 (35.6–36.0) | 35.9 ± 0.1 | 0.2 | 167× |
| Generation I (OakVar 2.13.1), full | 3 | 6,005.4 (5,889.3–6,068.5) | 5,987.7 ± 52.5 | 90.9 | 1× (ref.) |
| **Second caller (public, Zenodo 19487816)** |  |  |  |  |  |
| Generation II, warm | 11 | 20.2 (20.1–20.8) | 20.3 ± 0.1 | 0.2 | — |
| Generation II, full | 5 | 62.1 (62.0–81.0) | 65.9 ± 3.8 | 8.4 | 171× |
| Generation II, cold | 3 | 65.6 (65.3–65.7) | 65.5 ± 0.1 | 0.2 | 162× |
| Generation I (OakVar 2.13.1), full | 1 | 10,627.7 | — | — | 1× (ref.) |
| **Community reference (HG002, DeepVariant case study)** |  |  |  |  |  |
| Generation II, warm | 11 | 17.0 (16.9–17.2) | 17.0 ± 0.0 | 0.1 | — |
| Generation II, full | 5 | 38.4 (38.2–38.5) | 38.3 ± 0.1 | 0.1 | — |
| Generation II, cold | 3 | 41.9 (41.7–42.0) | 41.8 ± 0.1 | 0.2 | — |
| **Calibration (private, the 2023 benchmark file)** |  |  |  |  |  |
| Generation II, warm | 11 | 16.2 (16.1–16.4) | 16.2 ± 0.0 | 0.1 | — |
| Generation II, full | 5 | 33.1 (33.0–33.3) | 33.1 ± 0.1 | 0.1 | 235× |
| Generation II, cold | 3 | 36.7 (36.7–36.9) | 36.7 ± 0.1 | 0.1 | 212× |
| Generation I (OakVar 2.13.1), full | 3 | 7,785.3 (5,995.5–8,281.0) | 7,353.9 ± 694.1 | 1,202.2 | 1× (ref.) |
| **Primary, against a whole-genome reference database (first run of each dropped)** |  |  |  |  |  |
| Generation II, full + Ensembl | 2 | 103.1 (64.2–142.0) | 103.1 ± 38.9 | 55.0 | 34× |
| Generation I (OakVar 2.13.1), dbSNP only | 2 | 3,537.2 (3,446.8–3,627.5) | 3,537.2 ± 90.3 | 127.8 | 1× (ref.) |
<!-- @/rev C22 -->

<!-- @rev C23 rounds=2 by=claude:2026-10-11,claude:2026-10-13 -->
**Table 3.** Stage times and resources of the full runs (medians unless stated).<!-- @rev B25 rounds=2 by=claude:2026-10-11,claude:2026-10-12 --> Peak RAM is the resident memory summed over the whole process tree (for Generation I, the container's processes), sampled ten times a second; pages shared between processes count once per process, which overstates the total, while a peak shorter than the sampling interval can be missed.<!-- @/rev B25 --> CPU is user plus system time divided by wall time; it was not measured for Generation I. Warm and cold runs are in the repository's generated tables.

| Genome | Run | *n* (runs) | Normalize (s) | Annotate (s) | Report (s) | Peak RAM, median (MB) | Peak RAM, max (MB) | CPU (%) |
|---|---|---|---|---|---|---|---|---|
| Primary | Generation II, full | 5 | 15.4 | 10.4 | 1.8 | 2,224 | 2,270 | 376 |
| Primary | Generation I | 3 | — | — | — | 4,610 | 4,611 | — |
| Second caller | Generation II, full | 5 | 41.6 | 13.7 | 1.8 | 4,465 | 4,514 | 345 |
| Second caller | Generation I | 1 | — | — | — | 4,529 | 4,529 | — |
| Community reference | Generation II, full | 5 | 20.9 | 10.6 | 1.8 | 2,893 | 2,925 | 363 |
| Calibration | Generation II, full | 5 | 16.6 | 9.4 | 2.1 | 2,274 | 2,296 | 376 |
| Calibration | Generation I | 3 | — | — | — | 3,837 | 3,838 | — |
<!-- @/rev C23 -->

<!-- @rev B23 rounds=2 by=claude:2026-10-11,claude:2026-10-12 -->
**Table 4.** Benchmark hardware and inputs, recorded at run time (October 2026).

| Parameter | Value |
|---|---|
| CPU | AMD Ryzen 7 3800X (8 cores, 16 threads) |
| RAM | 63 GiB |
| Storage | SATA SSD, NTFS through the Linux ntfs3 driver (data, caches and outputs) |
| OS | Linux 7.2.9 |
| Generation II | Just-DNA-Lite 0.3.25, 10 modules (versions and digests as in Table S4) |
| Generation I | OakVar 2.13.1 in Docker (Table S2) |
| Input: primary | 6,079,744 records (4,616,002 SNVs), DeepVariant 1.1.0, GRCh38 |
| Input: second caller | 5,064,598 records (4,104,611 SNVs), DRAGEN 13.021.779.4.4.4, GRCh38 |
| Input: community reference | 7,753,721 records (6,476,847 SNVs), DeepVariant 1.0.0, GRCh38 |
| Input: calibration | 6,138,868 records (4,724,429 SNVs), DeepVariant 1.3.0, GRCh38 |
<!-- @/rev B23 -->

<!-- @rev A3a rounds=2 by=claude:2026-10-11,claude:2026-10-13 -->
On the primary genome, the median full run took 32.7 s against 6,005.4 s for Generation I, an approximately 183-fold speedup (235-fold on the calibration genome and 171-fold on the second-caller genome). These ratios carry Generation I's own spread: on the calibration genome its slowest run took 38% longer than its fastest, the two having run on different nights. Against a whole-genome reference database the gap narrows: Generation II with Ensembl annotation on took a median of 103.1 s and Generation I with dbSNP alone 3,537.2 s, about 34-fold, a fifth of the gap with the report modules. The larger gap with the report modules is consistent with their being compiled in advance into tables keyed for the join (Section 2.1), but this comparison does not isolate that contribution. In practice, a whole-genome run that took Generation I about one to three hours took Generation II between half a minute and two and a half minutes. These ratios apply to these configurations and these inputs, rather than to OakVar generally. A warm run, which reuses the sample's quality-filtered table, took 16.3 s. The benchmark used SSD storage and a workstation with 63 GiB RAM; it does not directly establish performance on a laptop or on rotational disks. Peak memory of a Just-DNA-Lite run with Ensembl off was 2,054 to 2,270 MB on the primary genome and at most 4,525 MB on any genome, against at most 4,611 MB for Generation I (Table 3); with Ensembl annotation on it was 5,568 to 5,750 MB. Streaming joins and column-pruned reads are architectural differences, but this comparison does not isolate their individual contributions to runtime.
<!-- @/rev A3a -->

### **4.2 PRS Computation**

<!-- @rev B29 rounds=2 by=claude:2026-10-11,claude:2026-10-12 -->
We benchmarked just-prs's DuckDB and Polars engines against the external tool PLINK2 on 100 PGS Catalog scores (PGS000006 to PGS000106, excluding PGS000085; PGS000001 to PGS000003 ran first as a warm-up) using the primary whole-genome VCF of Section 4.1 (4,661,444 records with FILTER PASS or unset, GRCh38; Zenodo 18370498). The engines, timing and memory measurement are those of `benchmarks/benchmark_engines.py` in just-prs 0.10.1, run through a harness that fixes the list of scores, calls PLINK2 with the same command line but keeps its log for every score, and includes PLINK2 in the warm-up (`docs/manuscript/benchmarks/a3/prs/`). Each observation represents a different scoring model applied to the same individual.
<!-- @/rev B29 -->

<!-- @rev A3b rounds=2 by=claude:2026-10-11,claude:2026-10-12 -->
PLINK2's input was built in two ways. The *original* input is the one the just-prs benchmark script builds: a genotype file from every record, reference calls included, and variant identifiers (in both allele orders) built from each scoring row's first candidate other allele only. The *fixed* input builds the genotype file from the records just-prs reads (FILTER PASS or unset), gives identifiers for every candidate other allele, and sums the weights of identifiers that two scoring rows share after liftover. Both inputs restrict PLINK2 to the autosomes, while just-prs reads every chromosome. Table 5 reports the fixed input; Table 6 reports both. PLINK2's time excludes preparing its score file, as in the just-prs script; including it moves PLINK2's median from 0.602 s to 0.604 s (Table 5).
<!-- @/rev A3b -->

<!-- @rev B30 rounds=1 by=claude:2026-10-11 -->
**Table 5.** Runtime of PRS computation engines (seconds per PGS ID), fixed PLINK2 input. "Excl." excludes the 7 PGS IDs with ≥ 1M variants. The speedup is PLINK2's median divided by the engine's; the median of the per-score ratios is shown beside it. With the original input, PLINK2 stopped on the four largest scores (PGS000013, PGS000014, PGS000016 and PGS000017) because a variant appeared twice in its score file ("ALT1 allele … appears multiple times"), the liftover duplicates that the fixed input merges; logs are in the repository.

| Engine | *N* scored | Median (all), s | Mean (all), s | Median (excl. 7 with ≥ 1M variants), s | PLINK2 median ÷ engine median | Median per-ID PLINK2 ÷ engine |
|---|---|---|---|---|---|---|
| just-prs DuckDB | 100 | 0.081 | 0.188 | 0.081 | 7.4× | 7.4× (n=100) |
| just-prs Polars | 100 | 0.305 | 0.371 | 0.301 | 2.0× | 2.0× (n=100) |
| PLINK2 | 100 | 0.602 | 0.754 | 0.602 | 1.0× | 1.0× (n=100) |
| PLINK2 + score-file preparation | 100 | 0.604 | 1.555 | 0.604 | — | — |
<!-- @/rev B30 -->

<!-- @rev C26 rounds=1 by=claude:2026-10-11 -->
**Table 6.** Score concordance between engines, with both PLINK2 inputs. *r* is computed across the scores of one genome, so the largest scores dominate it.

| Engine pair | PLINK2 input | *N* PGS | Pearson *r* | Max \|Δ score\| |
|---|---|---|---|---|
| just-prs DuckDB ↔ just-prs Polars | fixed | 100 | 1.000000 | 5.68e-14 |
| just-prs DuckDB ↔ PLINK2 | fixed | 100 | 0.999997 | 0.501 |
| just-prs Polars ↔ PLINK2 | fixed | 100 | 0.999997 | 0.501 |
| just-prs DuckDB ↔ PLINK2 | original | 96 | 0.999859 | 21.4 |
| just-prs Polars ↔ PLINK2 | original | 96 | 0.999859 | 21.4 |
<!-- @/rev C26 -->

<!-- @rev C27 rounds=2 by=claude:2026-10-11,claude:2026-10-12 -->
DuckDB and Polars agreed to within 5.68 × 10⁻¹⁴ on this input. Because both engines apply the same dosage rule and weighted sum and differ mainly in how the join is executed, their agreement checks the implementation, not the method. With the fixed input, scores agreed closely with the external PLINK2 comparator (Pearson r = 0.999997; maximum absolute score difference 0.501); with the original input, in which PLINK2 lost every candidate other allele but the first and counted reference-call records, r was 0.999859 and the maximum difference 21.4. The workflows differ in variant identification. just-prs joins on chromosome and position and counts the effect allele if it equals the reference or alternate allele, otherwise a dosage of zero, with no strand flipping; it compares a multi-allelic record's alternate alleles as one string, does not check the other allele, and ran with reference-homozygote restoration off; PLINK2 matches exact chr:pos:ref:alt identifiers. The routes can therefore include different variants (chrX, which the PLINK2 runs leave out; multi-allelic sites; positions where the alleles disagree), so score differences can remain despite the same weighted-sum calculation. The comparison concerns this PLINK2 configuration, not a general limitation of the tool. Correlation here measures agreement across scores for one genome; it does not measure rankings across individuals. Supplementary S3 reports each engine's memory, which is measured differently for the in-process engines and for PLINK2.
<!-- @/rev C27 -->

<!-- @rev B31 rounds=2 by=claude:2026-10-11,claude:2026-10-12 -->
With the fixed input, the share of a score's variants that were matched had a median of 53% for just-prs (range 22 to 79%) and 51% for PLINK2 (range 22 to 78%). The two counts are not the same measure: just-prs counts scoring rows with a called genotype at their position, PLINK2 the variants it processed, matched by identifier. These values describe the benchmark configuration, rather than the maximum coverage supported by just-prs. Reference-homozygote restoration can recover eligible absent loci for many scores, and the array workflow supports LD-proxy estimation (Section 3.2); their coverage gains are not quantified by this engine comparison. Missingness and allele matching also affect comparison with reference distributions. The reported speedups are ratios of median runtimes over the same 100 scores; the medians of the per-score ratios agree with them to the precision shown (Table 5).
<!-- @/rev B31 -->


## **5. Discussion**

### **5.1 Limitations of Variant Annotation**

<!-- @rev R17 rounds=1 by=robi:2026-09-25 -->
Variant annotation tools <!-- @rev C30 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->are based on<!-- @/rev C30 --> statistical associations from published literature, and several inherent limitations apply. Heritability is a population-level statistic, not individual determinism, and estimates change with environment, study design, and cohort. A polygenic risk score is a linear weighted sum that reflects where an individual is situated in a reference population's distribution. However, biology is not linear, and gene-gene and gene-environment interactions, feedback loops, developmental windows, and compensatory mechanisms are not always captured by a polygenic score. Moreover, most PGS Catalog scoring files were derived from predominantly European cohorts, so associations may not transfer to other ancestries (Section 5.4). Additionally, most variants surfaced are statistical associations from GWAS, not established causal mechanisms; many GWAS hits are tagging SNPs, and effect sizes typically shrink in replication.
<!-- @/rev R17 -->

<!-- @rev R18 rounds=1 by=robi:2026-09-25 -->
AI-generated modules carry additional uncertainty: they are automated drafts produced by language models reading published papers, and they will contain mistakes. Users should treat them as lower confidence than expert-curated modules and review the underlying evidence. Just-DNA-Lite is a research tool, not a clinical pipeline. Raw VCFs contain false positives, and automated annotations have inherent error rates. The platform joins the user's variants against published databases and computes polygenic risk scores, adding contextual information from those sources; it does not interpret results in a clinical context.
<!-- @/rev R18 -->

### **5.2 Local Processing and Data Privacy**

<!-- @rev R19 rounds=1 by=robi:2026-09-25 -->
Core annotation and PRS computation use local genome files, cached reference datasets, and local result storage. Downloading reference data does not require uploading the user's genome. This architecture reduces the need to disclose genomic data to a hosted analysis service, however, local execution is not a guarantee against disclosure through other parts of the workflow. More precisely, optional AI explanations and MCP clients, for example, require a separate assessment: when an assistant uses an external model provider, prompts and tool outputs may transmit sensitive results even if the raw VCF remains local. Privacy therefore depends on the deployment, the selected services, and the information shared with them. The platform's local architecture alone does not establish regulatory compliance.
<!-- @/rev R19 -->

### **5.3 Platform Philosophy: Transparency and the Right to Read Your Own Genome**

<!-- @rev R20 rounds=1 by=robi:2026-09-25 -->
Just-DNA-Lite is built on a simple conviction: people have the right to read and explore their own genomic data, and well-intended researchers have the right to work with public genomes without a gatekeeper's permission. The GDPR's right of access (Article 15) already entitles individuals to obtain a copy of their personal data, and the emerging European Health Data Space is designed to give people access to and control over their own health information. A tool that runs locally and shows users useful information in their own genome is, in this light, an instrument of an existing right.
<!-- @/rev R20 -->

<!-- @rev R21 rounds=1 by=robi:2026-09-25 -->
Genomic findings can be misinterpreted or provide false reassurance, particularly when analytical errors and ancestry differences are overlooked (Tandy-Connor et al., 2018; Manrai et al., 2016). The interface presents model provenance, variant-match rates, ancestry context, and differences among scores to make these limitations inspectable. However, the platform is not intended to provide medical advice. Displaying this information is a design choice; whether it improves user understanding requires a usability study. The project also maintains tutorials and has run hands-on workshops for non-specialists.
<!-- @/rev R21 -->

### **5.4 Limitations**

<!-- @rev R22 rounds=1 by=robi:2026-09-25 -->
**Population stratification.** The 1000 Genomes-based percentile distributions provide population-specific reference points (AFR, AMR, EAS, EUR, SAS), but most modules and PGS scoring files derive from predominantly European cohorts; transferability to non-European populations is a known limitation of the source data, not specific to this platform. **Ancestry selection.** Automatic ancestry inference from the VCF is not yet implemented; users have to select the closest reference superpopulation. **Input format.** The platform supports WGS and WES VCFs; GRCh38 is the primary build, with GRCh37/hg19 handled via liftover; consumer microarray data is supported experimentally (with far lower coverage, which the platform surfaces to users); T2T references are not yet supported. **Module quality variation.** Expert-curated modules inherit the limitations of their source databases; AI-generated modules have additional variability and require user review. <!-- @rev C2d rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->**Benchmark scope.** Runtime and score agreement were measured on one public genome. They describe computational performance; they do not establish predictive accuracy or agreement in rankings across individuals.<!-- @/rev C2d --> <!-- @rev C28 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->They also measure speed and agreement between scoring engines, not whether annotations are correct. Correctness depends on two things they do not test: whether the cited studies are right, and whether each module records their findings faithfully (which variant, allele and genotype, and what the report says about it).<!-- @/rev C28 -->
<!-- @/rev R22 -->

### **5.5 Future Directions**

<!-- @rev R23 rounds=1 by=robi:2026-09-25 -->
Several extensions are underway or planned: GRCh37/hg19 liftover (added, but still under testing), experimental consumer-microarray support, and T2T reference support. Multi-species support (companion-animal genomics) is a compelling direction. We are also considering methylation and transcriptomic ageing clocks, among the analyses users most frequently request. Within the ROGEN consortium, population-calibrated polygenic risk scores are planned for a Romanian genomic cohort of approximately 5,000 individuals; that cohort is currently being sequenced, and none of the work reported here uses cohort data. <!-- @rev C35 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->We encourage the community to build and share modules. Modules published by others are not treated as accurate by default: community- and AI-generated modules will contain mistakes, and the platform mitigates this<!-- @/rev C35 --> not by gatekeeping but by making provenance visible (the `curator` field, the explicit expert-versus-AI distinction) so that trust can be calibrated. How best to curate and validate a large, decentralized ecosystem of genomic annotations is not yet known; Just-DNA-Lite is offered both as a usable platform and as a testbed for that question.
<!-- @/rev R23 -->

## **6. Conclusion**

<!-- @rev R24 rounds=1 by=robi:2026-09-25 -->
Just-DNA-Lite integrates local variant annotation, polygenic scoring, and inspectable reports with a portable annotation-module contract and versioned content discovery. Typed MCP tools make the PRS engine available to AI assistants. Albeit tested on<!-- @rev A3c rounds=2 by=claude:2026-10-11,claude:2026-10-12 --> four genomes for annotation and one for scoring, the reported benchmarks show faster annotation than the OakVar-based Generation I system run on the same machine<!-- @/rev A3c --> and close numerical agreement between scoring engines. Evaluation across individuals, reference populations, and matched-variant sets remains necessary to establish the broader reliability of these workflows. The platform provides infrastructure for research and education, without establishing clinical validity for the findings it reports.
<!-- @/rev R24 -->

## **Contribution Statements**

- **Kulaga Anton** — co-founded the project, bioinformatic pipeline development, Just-DNA-Lite architecture (Dagster/Polars/DuckDB pipeline, uv workspace), just-prs library development and benchmarking, web UI development, team management, article writing
<!-- @rev R25 rounds=1 by=robi:2026-09-25 -->
- **Usanov Nikolay** — co-founded the project, Just-DNA-Lite platform development, <!-- @rev D3 rounds=2 by=claude:2026-10-10,usanov:2026-10-10 -->the module system, the population ancestry discriminator (detection and algorithm), AI-assisted module authoring<!-- @/rev D3 -->, fundraising
<!-- @/rev R25 -->
- **Borysova Olga** — modules and report content (longevity variants, cardiovascular traits, lipid metabolism, VO2 max, athletic performance, pharmacogenomics), LongevityMap database curation and expansion, pathway categorization, report structure, data collection and analysis
- **Karmazin Alexey** — lead architect of the <!-- @rev C37 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->report system of Generation I (the OakVar-based Just-DNA-Seq)<!-- @/rev C37 -->, OakVar report modules and preparation utilities, PRS modules
- **Maria Koval** — report modules, report template, trait annotation modules (thrombophilia, cardiovascular)
- **Fedorova Alina** — bioinformatic utilities, scientific literature exploration
- **Pushkareva Malvina** — software development and testing
- **Evfratov Sergey** — pharmacogenomics (drug) module development
- **Ryangguk Kim** — created and maintained OakVar, extended it for the Generation I platform
- **Zaharia Livia** — beta-testing, provided her whole genome for testing and benchmarking
- **Fuellen Georg** — co-supervision, valuable suggestions and comments
- **Tacutu Robi** — <!-- @rev C38 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->co-supervision,<!-- @/rev C38 --> bioinformatics and ageing research advising, LongevityMap database

**Acknowledgments:** Volodymir Semenuik for help with documentation.

## **Funding**

<!-- @rev R26 rounds=1 by=robi:2026-09-25 -->
The research carried out by A.K. and R.T. was supported by The Ministry of Investments and European Projects, through the Managing Authority for the Health Program, PS/272/PS_P5/OP1/RSO1.1/PS_P5_RSO1.1_A9–ROGEN Project (MySMIS 324809).
<!-- @/rev R26 -->

## **Code Availability**

**GitHub Organization:** https://github.com/dna-seq

**Table 7.** Software repositories.

| Repository | Description | Generation |
|---|---|---|
| [just-dna-lite](https://github.com/dna-seq/just-dna-lite) | Main platform — standalone genomic annotation | Gen II |
| [just-prs](https://github.com/dna-seq/just-prs) | PRS computation library/CLI/UI | Gen II |
| [just-dna-format](https://github.com/dna-seq/just-dna-format) | Annotation module schema, manifest/integrity contract, and reference compiler | Gen II |
| [just-dna-registry](https://github.com/dna-seq/just-dna-registry) | Catalogue and versioned distribution of annotation modules | Gen II |
| [just-prs-mcp](https://github.com/dna-seq/just-prs-mcp) | MCP server exposing just-prs to Claude, Cursor, Codex, Antigravity, and other AI agents, with trait-panel graphics and interpretation prompts | Gen II |
| [prepare-annotations](https://github.com/dna-seq/prepare-annotations) | Pipelines converting annotation databases to Parquet | Gen II |
| [reflex-mui-datagrid](https://github.com/dna-seq/reflex-mui-datagrid) | Reflex wrapper for MUI DataGrid | Gen II |
| [just-biomarkers](https://github.com/dna-seq/just-biomarkers) | Methylation and other biomarker analysis tools | Gen II |
| [just-module-creator](https://github.com/dna-seq/just-module-creator) | Authoring plugin (MCP tools and skills) for drafting, checking, compiling, and publishing annotation modules inside AI coding assistants — the subject of the companion paper | Gen II |
| [dna-seq](https://github.com/dna-seq/dna-seq) | Original DNA-Seq pipeline | Gen I |

Annotation modules and reference datasets are published to the just-dna-seq organization on HuggingFace (annotators, ensembl_variations, clinvar, pgs-catalog, prs-percentiles), which serves as the default source for module auto-discovery. Other fsspec-compatible sources are equally supported.

## **Competing Interests**

- Ryangguk Kim is a co-founder of OakVar Inc.
- Anton Kulaga, Olga Borysova, Maria Koval, Nikolay Usanov, and Alex Karmazin are co-founders of SecvADN SRL, which provides additional services on top of the open-source modules.

## **Bibliography**

*(Carried over from the combined manuscript; to be finalized with 2022–2026 additions.)*

Alteri, E., et al. (2024). The 23andMe data breach. *European Journal of Human Genetics*, 32(11), 1317–1320.

<!-- @rev C3r rounds=1 by=claude:2026-10-10 -->
Added in the v0.3 revision (to be merged into the list above): Chen, T., et al. (2023). VCFshiny: an R/Shiny application for interactively analyzing and visualizing genetic variants. *Bioinformatics Advances*, 3(1), vbad107. doi:10.1093/bioadv/vbad107. Ehman, M., et al. (2025). The cost and cost trajectory of genome sequencing and bioinformatics analysis for Indigenous children with suspected rare diseases. *Genetics in Medicine*, 27(11), 101568. doi:10.1016/j.gim.2025.101568. Illumina (2023). Press release, 4 April 2023 ("$200 per genome", sequencing consumables only, 100 Gb per genome); NovaSeq X product page, https://www.illumina.com/systems/sequencing-platforms/novaseq-x-plus/applications/broad-sequencing.html (accessed 10 October 2026). Mordaunt, D. A., et al. (2024). The cost of proband and trio exome and genome analysis in rare disease: a micro-costing study. *Genetics in Medicine*, 26(4), 101058. doi:10.1016/j.gim.2023.101058. National Human Genome Research Institute (2021). The Cost of Sequencing a Human Genome. https://www.genome.gov/about-genomics/fact-sheets/Sequencing-Human-Genome-cost (accessed 10 October 2026). Nelson, S. C., et al. (2019). Third-Party Genetic Interpretation Tools: A Mixed-Methods Study of Consumer Motivation and Behavior. *American Journal of Human Genetics*, 105(1), 122–131. doi:10.1016/j.ajhg.2019.05.014. O'Daniel, J. M., et al. (2025). Direct-to-Consumer Genetic Testing. *NEJM Evidence*, 4(11), EVIDra2400455. doi:10.1056/EVIDra2400455. Ultima Genomics (2025). Ultima Genomics increases output by over 50% and lowers sequencing costs by a further 20% with the introduction of UG 100 Solaris. PR Newswire, 24 February 2025. Wiewiórka, M., Khamutou, P., Zbysiński, M., & Gambin, T. (2025). polars-bio: fast, scalable, and out-of-core operations on large genomic interval datasets. *Bioinformatics*, 41(12), btaf640. doi:10.1093/bioinformatics/btaf640.
<!-- @/rev C3r -->
Annas, G. J., & Elias, S. (2014). 23andMe and the FDA. *NEJM*, 370(11), 985–988.
Association for Molecular Pathology v. Myriad Genetics, Inc., 569 U.S. 576 (2013).
Bloss, C. S., Schork, N. J., & Topol, E. J. (2011). Effect of direct-to-consumer genomewide profiling to assess disease risk. *NEJM*, 364(6), 524–534.
Broer, L., et al. (2014). GWAS of longevity in CHARGE consortium confirms APOE and FOXO3 candidacy. *J Gerontol A*, 70(1), 110–118.
Caruso, C., et al. (2022). How important are genes to achieve longevity? *IJMS*, 23(10), 5635.
Doffman, Z. (2023). 23andMe confirms 6.9 million user records stolen. *Forbes*.
Green, R. C., & Farahany, N. A. (2014). Regulation: The FDA is overcautious on consumer genomics. *Nature*, 505(7483), 286–287.
Kulaga, A., et al. (2024). Just-DNA-Seq, open-source personal genomics platform. *arXiv*:2403.19087.
Lambert, S. A., et al. (2021). The Polygenic Score Catalog. *Nature Genetics*, 53(4), 420–425.
Manrai, A. K., et al. (2016). Genetic misdiagnoses and the potential for health disparities. *NEJM*, 375(7), 655–665.
Shenhar, B., et al. (2025). Heritability of human lifespan is about 50% when confounding factors are addressed. *Science*.
Tacutu, R., et al. (2017). Human Ageing Genomic Resources: New and updated databases. *NAR*, 46(D1), D1083–D1090.
Tandy-Connor, S., et al. (2018). False-positive results released by direct-to-consumer genetic tests. *Genetics in Medicine*, 20(12), 1515–1521.

## **Supplementary Material**

**S1. Generation I: OakVar-Based Just-DNA-Seq Platform.** Architecture, pipeline, module types, and repository table for the OakVar-based Generation I system (see combined-manuscript supplement for full detail).

<!-- @rev B28 rounds=3 by=claude:2026-10-11,claude:2026-10-12,claude:2026-10-13 -->
**S2. Generation I vs Generation II Speed Comparison.** The individual 2026 Generation I runs (OakVar 2.13.1 on the workstation of Table 4): on the primary genome 6,005.4, 6,068.5 and 5,889.3 s on the first night; on the calibration genome 5,995.5 s on the first night and 7,785.3 and 8,281.0 s on the second; on the second-caller genome 10,627.7 s; and with dbSNP alone on the primary genome 7,041.5 s (the warm-up), 3,627.5 and 3,446.8 s; with peak memory of 3,832 to 4,611 MB; OakVar's own step times (on the primary genome, as medians of the three runs, the postaggregator step, which runs the Generation I modules, takes 38.9% of a run, the annotators 28.7% and the mapper 17.1%); and the installed OakVar modules, among them dbSNP 156.0.1, ClinVar 2026.10.01, gnomAD 2.2.0 (data v2.1), SIFT 1.3.0, GENCODE 46.1.1 and the nine Generation I postaggregators, 0.1.0 to 0.1.2 (Table S2). It also keeps the earlier Generation I runs on the calibration genome, made on another workstation with the OakVar and module versions of the time (2023-02-17: 5,651 s; 2023-02-19: 6,803 s; 2023-05-07: 7,662 s), reported in earlier drafts. The speedup reflects the architectural differences described in the main text; this comparison does not isolate their individual contributions. All of it is generated into `docs/manuscript/benchmarks/a3/tables.md`.
<!-- @/rev B28 -->

<!-- @rev A3d rounds=1 by=claude:2026-10-12 -->
**Table S2.** The OakVar modules that ran in the 2026 Generation I runs, as installed from the OakVar store on 2026-10-11, beside the version of each Just-DNA-Seq repository on GitHub on the same day and at its last commit by 2023-05-07 (date of the last commit in brackets). Modules not maintained by the Just-DNA-Seq project have no GitHub column. Widget modules, which do not run during annotation, are omitted.

| OakVar module | Type | Version that ran (store) | Data | GitHub head, 2026-10-11 | GitHub, last commit by 2023-05-07 |
|---|---|---|---|---|---|
| vcf-converter | converter | 4.2.1 | — | — | — |
| gencode | mapper | 46.1.1 | — | — | — |
| cardioboost | annotator | 1.0.0 | v2.1 | — | — |
| clinvar | annotator | 2026.10.01 | 2026.10.01 | — | — |
| dbsnp | annotator | 156.0.1 | v156 | — | — |
| gnomad | annotator | 2.2.0 | v2.1 | — | — |
| ncbigene | annotator | 2026.10.01 | 2026.10.01 | — | — |
| omim | annotator | 1.1.1 | v4.1 | — | — |
| pubmed | annotator | 1.1.5 | — | — | — |
| sift | annotator | 1.3.0 | SIFT4G 2016-02-22 | — | — |
| just_cancer | postaggregator | 0.1.0 | — | 0.1.0 (2026-04-11) | 0.1.0 (2023-01-31) |
| just_cardio | postaggregator | 0.1.1 | — | 0.1.1 (2026-04-11) | 0.1.1 (2023-01-31) |
| just_coronary | postaggregator | 0.1.2 | — | 0.1.2 (2024-10-31) | 0.1.1 (2023-01-31) |
| just_drugs | postaggregator | 0.1.0 | — | 0.1.0 (2024-10-31) | 0.1.0 (2023-01-31) |
| just_lipidmetabolism | postaggregator | 0.1.2 | — | 0.1.1 (2024-10-31) | 0.1.0 (2023-03-24) |
| just_longevitymap | postaggregator | 0.1.2 | — | 0.2.0 (2025-03-05) | 0.1.1 (2023-03-11) |
| just_superhuman | postaggregator | 0.1.0 | — | 0.1.0 (2024-11-13) | 0.1.0 (2023-03-26) |
| just_thrombophilia | postaggregator | 0.1.2 | — | 0.2.0 (2026-04-11) | 0.1.0 (2023-03-24) |
| just_vo2max | postaggregator | 0.1.2 | — | 0.1.2 (2024-10-31) | — |
| vcfinfo | postaggregator | 1.4.0 | — | — | — |
| longevity2reporter | reporter | 0.4.3 | — | 0.4.3 (2025-03-05) | 0.4.0 (2023-04-28) |
<!-- @/rev A3d -->

<!-- @rev B32 rounds=2 by=claude:2026-10-11,claude:2026-10-12 -->
**S3. Runtime and Memory on Large PRS Scoring Files.** Runtimes and memory for the 7 genome-wide PGS IDs (1.7 to 6.9M variants) with both PLINK2 inputs; with the original input PLINK2 failed on the four largest (Table 5). Memory is measured differently per engine: for DuckDB and Polars, the growth of the benchmark process's resident memory during the call, sampled every 10 ms (median over all 100 scores with the fixed input, 5.4 MB and 1,061.2 MB); for PLINK2, the peak resident memory of its own process, sampled every 100 ms (median 511.6 MB, fixed input). The two measures are not directly comparable.
<!-- @/rev B32 -->

<!-- @rev C13c rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->
**S4. Module sources.** For each annotation module the project publishes in the module registry (https://module-registry.just-dna.life, namespace `just-dna-seq`), as of 2026-10-10 18:00 UTC: version, publication date, artifact digest, curator type, how the module was curated, the source databases with their release, and every paper its rows cite (first author, year, PMID, DOI) with the number of rows citing it. Read from the modules' own published files; later versions may differ. Files: `S4_module_sources.md`, `S4_module_sources.csv`, `S4_module_citations.csv`.
<!-- @/rev C13c -->
