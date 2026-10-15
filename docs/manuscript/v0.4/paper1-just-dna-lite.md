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

<!-- @rev C2a rounds=3 by=robi:2026-09-25,claude:2026-10-10,claude:2026-10-13 -->
**Motivation:** As genome sequencing becomes increasingly available, personal genome analysis requires tools that make published variant associations accessible while allowing users to inspect the methods and retain control of their data.
<!-- @/rev C2a -->

<!-- @rev C2b rounds=3 by=robi:2026-09-25,claude:2026-10-10,claude:2026-10-13 -->
**Results:** We present Just-DNA-Lite, an open-source platform that combines local variant annotation and polygenic risk score (PRS) computation in a web interface. Annotation modules are declarative, versioned packages of variant-trait tables and their sources, allowing researchers to extend the catalogue without writing code. A registry distributes modules, and the platform applies them to the user's genome to produce downloadable reports. The just-prs library provides scoring through web, command-line, Python, and Model Context Protocol interfaces.
<!-- @/rev C2b -->
<!-- @rev C2c rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->
Reports list each matched variant with its reported effect and sources. Polygenic scores are shown as percentiles within a reference population matched to the genome's inferred ancestry, with all models for a trait shown together. New modules can also be drafted with general-purpose AI assistants through a plugin, and pass the same validation as hand-written ones.
<!-- @/rev C2c -->
<!-- @rev J1 rounds=1 by=claude:2026-10-13 -->
Core annotation and scoring run locally, with reference datasets downloaded and cached on the user's machine; optional external AI services introduce a separate data-sharing boundary. The platform is meant for research and education and does not provide diagnoses or establish clinical validity for the associations it reports.
<!-- @/rev J1 -->

<!-- @rev J2 rounds=1 by=claude:2026-10-13 -->
**Availability and implementation:** Just-DNA-Lite (AGPL-3.0) and just-prs (MIT) are written in Python and run on Linux, macOS and Windows. Source code: https://github.com/dna-seq/just-dna-lite and https://github.com/dna-seq/just-prs. The two co-author genomes used in the benchmarks are public on Zenodo (records 18370498 and 19487816).

**Contact:** fuellen@uni-rostock.de, robi.tacutu@gmail.com

**Supplementary information:** Supplementary data are available at *Bioinformatics* online.
<!-- @/rev J2 -->
<!-- AUTHOR TODO: add the archive DOI (Zenodo or Software Heritage) of the submitted software version and test data to the Availability paragraph before submission. -->

## **1. Introduction**

<!-- @rev C3 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->
By 2025, manufacturers listed the sequencing consumables for a human genome at US$80 to US$200 (Illumina, 2023; Ultima Genomics, 2025), and studies that count the full cost, including labour, equipment and analysis, put a genome at a few thousand dollars (Mordaunt et al., 2024; Ehman et al., 2025), against an estimated $500 million to $1 billion for the first one (NHGRI, 2021). Several companies now offer direct-to-consumer sequencing services (O'Daniel et al., 2025).<!-- @/rev C3 --> Yet the gap between sequencing accessibility and variant annotation remains wide. Researchers and individuals receive raw variant files (VCFs) containing millions of variants <!-- @rev C4 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->but often lack accessible means to annotate them against published databases without specialized bioinformatics expertise, a learning curve that takes time away from the questions they set out to answer (Nelson et al., 2019; Chen et al., 2023; O'Daniel et al., 2025).<!-- @/rev C4 -->

<!-- @rev R3 rounds=2 by=robi:2026-09-25,claude:2026-10-13 -->
Existing solutions generally belong to two extremes. Commercial platforms such as DNA Complete (formerly Nebula Genomics) and Dante Labs provide curated reports, but the curation is opaque: users cannot verify which polymorphisms contributed to a score, whether the methodology is appropriate for their ancestry, or how findings were weighted. At the other end, research-grade tools like PLINK, ANNOVAR, and VEP are powerful but demand command-line proficiency and significant setup effort. <!-- @rev C36a rounds=2 by=robi:2026-09-25,claude:2026-10-13 -->Open-source projects between these extremes each cover part of the task, such as local annotation with installable modules, ancestry-normalized scoring of PGS Catalog models, or access to a genome from an AI assistant. Table S7 compares the documented features of 22 tools for personal-genome annotation, polygenic scoring and AI-assisted interpretation; none of them documents a graphical interface, annotation sets added without code, PGS Catalog scoring and ancestry-matched percentiles together.<!-- @/rev C36a -->
<!-- @/rev R3 -->

<!-- @rev R4 rounds=2 by=robi:2026-09-25,claude:2026-10-13 -->
The recent progress in the genetics of longevity illustrates the need for such extensible annotation tools. After correction for extrinsic mortality, the intrinsic heritability of lifespan has been estimated at about 50%, against 20–25% in twin studies (Shenhar et al., 2025), and GWAS have repeatedly linked loci such as APOE and FOXO3 to longevity (Broer et al., 2014; Caruso et al., 2022). Databases such as LongevityMap within the Human Ageing Genomic Resources (HAGR) (Tacutu et al., 2017) have compiled thousands of variant-trait associations, but no existing tool makes it straightforward to annotate a personal VCF against these databases transparently and extensibly. This brings to focus a broader pattern: variant-trait associations are published faster than any single curation team can integrate them, supporting the need for platforms where new annotation modules can be added rapidly.
<!-- @/rev R4 -->

<!-- @rev J3 rounds=1 by=claude:2026-10-13 -->
Such a platform has to be easy to use, transparent in its methods and extensible without code, and it has to protect privacy: genomic data are among the most sensitive personal information, and uploading them to third-party servers carries risks that individuals and regulations such as the GDPR seek to avoid.
<!-- @/rev J3 -->

<!-- @rev R5 rounds=1 by=robi:2026-09-25 -->
<!-- @rev C5 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->
Just-DNA-Lite is a local, open-source platform for annotating a personal genome and computing polygenic scores. We developed it as a ground-up rewrite of Just-DNA-Seq (Kulaga et al., 2024), whose first generation (Generation I) was a set of annotation and report modules for OakVar, a Python variant-analysis framework derived from OpenCRAVAT. Just-DNA-Lite removes the OakVar dependency entirely and replaces it with our own standalone annotation engine, built with Dagster for workflow orchestration, polars-bio, a genomics library with a Polars interface (Wiewiórka et al., 2025), for VCF reading, Polars for columnar processing, and DuckDB for out-of-core joins. It also replaces Python annotation plugins with declarative modules discoverable from configured sources (Section 2.2). Supplementary File S1 describes Generation I.
<!-- @/rev C5 -->
<!-- @/rev R5 -->

<!-- @rev C6 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->
This paper presents the standalone annotation engine, the reusable just-prs scoring library, the web interfaces, and MCP interfaces for calling these tools programmatically from AI assistants. Together, these components let users discover annotation content, apply it to a genome, compute published polygenic scores, and inspect reports.
<!-- @/rev C6 -->

## **2. Platform Architecture**

<!-- @rev J4 rounds=1 by=claude:2026-10-13 -->
The architecture separates local computation, annotation content and user interfaces. The pipeline reads modules as data artifacts, so the catalogue can change independently of the application code, and columnar storage with streaming operations limits memory use. A web application is the main interface, and typed MCP tools serve AI assistants (Section 3.2.1).
<!-- @/rev J4 -->

### **2.1 Annotation Pipeline**

<!-- @rev J5 rounds=1 by=claude:2026-10-13 -->
The pipeline is built from Dagster software-defined assets, which record data lineage and the CPU time, peak memory and duration of every step. An annotation run proceeds as follows:
<!-- @/rev J5 -->

1. <!-- @rev J6 rounds=1 by=claude:2026-10-13 -->**VCF ingestion.** The user supplies a VCF or VCF.gz file, as delivered by a sequencing provider, downloaded from a public genome repository or produced by their own pipeline; Just-DNA-Lite does not perform sequencing, alignment or variant calling.<!-- @/rev J6 --> <!-- @rev N5 rounds=2 by=claude:2026-10-10,claude:2026-10-13 -->The file is read with polars-bio, "a Python library that enables fast, parallel and out-of-core operations on large genomic interval datasets" (Wiewiórka et al., 2025).<!-- @/rev N5 -->
<!-- @rev R6 rounds=1 by=robi:2026-09-25 -->
2. **Normalization.** The raw VCF undergoes quality filtering (configurable via `modules.yaml`): only variants passing specified FILTER values (by default, PASS and ".") are retained, with optional minimum depth (DP ≥ 10) and quality (QUAL ≥ 20) thresholds. <!-- @rev N4 rounds=1 by=claude:2026-10-10 -->Chromosome names are normalized ("chr7" becomes "7", "chrM" becomes "MT") for consistency with annotation databases.<!-- @/rev N4 --> The normalized data is written as a Parquet file, which serves as the shared input for all downstream annotations.
<!-- @/rev R6 -->
3. <!-- @rev J19 rounds=1 by=claude:2026-10-13 -->**Module annotation.** For each selected annotation module, the pipeline performs a streaming join between the normalized VCF Parquet and the module's lead table (for most modules, `weights.parquet`): by position, with the reference allele required to agree where the module states one, or by rsID for older modules without coordinates.<!-- @/rev J19 --> Polars streaming joins keep peak memory low; for datasets too large to fit in memory, DuckDB handles out-of-core joins with configurable memory limits.
4. **Ensembl annotation (optional).** When enabled, the pipeline joins the normalized VCF against the Ensembl Variation database (cached locally as chromosome-level Parquet files downloaded from HuggingFace via fsspec), providing clinical significance labels, consequence types, and cross-references for each variant.
5. **Report generation.** Annotated results are written as Parquet files and rendered as downloadable PDF/HTML reports.

### **2.2 Modular Plugin System**

<!-- @rev R7 rounds=2 by=robi:2026-09-25,claude:2026-10-13 -->
For the purpose of Just-DNA-Lite, annotation modules are viewed as data, not executable plugins. The annotation engine reads published Parquet tables directly. A typical weighted-association module contains `weights.parquet`, with accompanying `annotations.parquet` and `studies.parquet` when available; other module families can use different primary tables.
<!-- @/rev R7 -->

<!-- @rev J7 rounds=1 by=claude:2026-10-13 -->
The `just-dna-format` library defines the authored specification and the manifest, integrity and versioning contract of compiled artifacts. Discovery reads a module's declared files from its manifest, or finds the tables directly in older Parquet modules that have none.
<!-- @/rev J7 -->

<!-- @rev R8 rounds=1 by=robi:2026-09-25 -->
For researchers creating new modules, a separate authoring route accepts `module_spec.yaml` and CSV tables such as `variants.csv` and `studies.csv`. The `just-dna-compiler` library validates and compiles these specifications into Parquet artifacts and a manifest during custom-module registration. Documentation and thumbnails may accompany the module. This route lets authors prepare annotation content <!-- @rev C10 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->without writing Python code. CSV files are used only for authoring: at runtime the platform reads the compiled Parquet tables, so existing Parquet modules need no CSV files.<!-- @/rev C10 -->
<!-- @/rev R8 -->

<!-- @rev R9 rounds=2 by=robi:2026-09-25,claude:2026-10-13 -->
Module discovery uses sources configured in `modules.yaml`, with repository defaults and a local working copy for runtime changes. Sources may include HuggingFace datasets, GitHub repositories, HTTP/HTTPS servers, cloud storage, or local paths accessible through fsspec. The `just-dna-registry` service provides a catalogue for browsing and retrieving versioned modules. Artifact manifests provide identity and integrity information; of note - integrity verification establishes that downloaded content matches the recorded artifact, not that its scientific claims are correct.
<!-- @/rev R9 -->

### **2.3 Web Interface and Self-Exploration**

<!-- @rev R10 rounds=3 by=robi:2026-09-25,claude:2026-10-13,claude:2026-10-13 -->
The web interface is built with Reflex, a Python framework that compiles to React; the whole interface is written in Python. The interface covers file management, module selection (including the optional Ensembl annotation), a sortable and filterable results grid, report download (PDF/HTML per module), and self-exploration. Users can browse the full variant table with sorting, filtering, and search, cross-referenced against Ensembl for clinical significance labels, consequence types, and known phenotype associations. All data can be exported as Parquet for downstream analysis in Python, R, DuckDB, or any Arrow-compatible tool.
<!-- @/rev R10 -->

**Figure 1.** The Just-DNA-Lite web interface showing the annotation results view with module selection, variant data grid, and report download options.

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
| Coronary Artery Disease | Coronary artery disease risk associations from published studies, ported from the Generation I module: 27 variants in 22 genes, citing 59 papers (sources in Table S4) | <!-- @rev C12a rounds=2 by=robi:2026-09-24,claude:2026-10-13 -->Expert (Olga Borysova)<!-- @/rev C12a --> |
| Lipid Metabolism | Lipid metabolism and cardiovascular risk variants from published studies: 15 variants in 12 genes, citing 37 papers (sources in Table S4) | <!-- @rev C12b rounds=2 by=robi:2026-09-24,claude:2026-10-13 -->Expert (Olga Borysova)<!-- @/rev C12b --> |
| VO2 Max | Published studies of the oxygen-uptake response to exercise training: 13 variants in 12 genes, citing 7 papers (sources in Table S4) | <!-- @rev C12c rounds=2 by=robi:2026-09-24,claude:2026-10-13 -->Expert (Olga Borysova)<!-- @/rev C12c --> |
| Superhuman (protective alleles) | Rare protective and enhancing alleles from the Church laboratory's list, checked against the primary literature: 74 variants in 28 genes, citing 29 papers (sources in Table S4) | <!-- @rev C12d rounds=2 by=robi:2026-09-24,claude:2026-10-13 -->Expert (Olga Borysova)<!-- @/rev C12d --> |
| Thrombophilia | Inherited blood-clotting risk variants (Factor V Leiden, prothrombin and related loci) from published studies: 8 variants in 8 genes, citing 24 papers (sources in Table S4) | <!-- @rev C12e rounds=2 by=robi:2026-09-24,claude:2026-10-13 -->Expert (Olga Borysova)<!-- @/rev C12e --> |
| Cardio | Pathogenic and likely pathogenic variants from ClinVar (release 2026-06-27, review status of at least one star) in 297 cardiac-disease genes (sources in Table S4) | Database-derived (ClinVar) |
| Cancer | Pathogenic and likely pathogenic variants from ClinVar (release 2026-06-27, at least one star) in 298 cancer-predisposition genes (sources in Table S4) | Database-derived (ClinVar) |
| Pathogenic | Genome-wide flag for ClinVar pathogenic and likely pathogenic variants (release 2026-06-27, at least one star) across 4,793 genes (sources in Table S4) | Database-derived (ClinVar) |
| Pharmacogenomics | Drug response by genotype from the ClinPGx (PharmGKB) clinical annotations at evidence levels 1A to 2B (release 2025-07-05): 240 annotations, 65 drugs, 35 genes (sources in Table S4) | Database-derived (ClinPGx) |
<!-- @/rev C13b -->

### **3.1 Longevity Variants Module (example)**

The Longevity Variants module illustrates how existing variant-trait association databases can be wrapped into the platform's no-code module format. It builds upon the LongevityMap database (Tacutu et al., 2017), which contains 3,144 variant-trait associations in 884 genes. Our contribution here is not re-annotation or re-validation of these variants, but (1) curation and expansion with post-2017 literature, adding 50 new entries and editing 876 existing records; (2) assignment of weighted scores based on study quality, replication across populations, and statistical significance; and (3) pathway-based categorization for structured browsing.

<!-- @rev J8 rounds=1 by=claude:2026-10-13 -->
The module's weighting scheme assigns two independent weight components whose product yields the displayed score. The SNP weight (*w*_SNP) is an integrative parameter reflecting the strength of statistical evidence for a variant-trait association (number of independent significant studies, reported p-values, number of replicating populations). The genotype weight (*w*_genotype) captures the direction and magnitude of the reported association for a specific genotype: 0 for the reference genotype, ±0.5 or ±1.0 for heterozygous or homozygous carriers of the positively or negatively associated allele. The displayed score is *W*_display = *w*_SNP × *w*_genotype. Variants are grouped into 12 functional pathway categories, such as insulin/IGF-1 signalling, mTOR, sirtuins and genome maintenance, which the report uses to group its findings (Figure 2).
<!-- @/rev J8 -->

**Figure 2.** Just-DNA-Lite UI: the Longevity Variants report, showing pathway categorization, the per-variant SNP table, and colour-coded weights.

### **3.2 Polygenic Risk Scores**

<!-- @rev J9 rounds=1 by=claude:2026-10-13 -->
Polygenic risk scores (PRS) aggregate the effects of many common variants into a single weighted sum, providing a population-relative measure for a given trait (Lambert et al., 2021). We developed the just-prs library (github.com/dna-seq/just-prs) as the PRS computation engine for Just-DNA-Lite; it is a separable component that can also be used on its own (Section 3.2.1). just-prs scores the harmonized scoring files of the PGS Catalog (Lambert et al., 2021): of the 6,991 scores in its September 2026 release, 6,910 can be scored as specified, 76 only approximately and 5 not at all (Table S5).
<!-- @/rev J9 -->

<!-- @rev C16 rounds=4 by=robi:2026-09-25,claude:2026-10-10,validator:2026-10-10,claude:2026-10-13 -->
Generation I derived its PRS percentiles by simulating 10,000 genotypes from pooled gnomAD allele frequencies and fitting a normal distribution to the simulated scores. just-prs instead scores the 3,202 individuals of the 1000 Genomes reference panel with each model, summarises the observed scores as a mean and standard deviation for each of five superpopulations (AFR, AMR, EAS, EUR, SAS), and places a user's score on the corresponding normal distribution, so the reference reflects real genotypes and their linkage structure rather than simulated ones.<!-- @/rev C16 --> The reference superpopulation is inferred from the genome and the user can choose another; the percentile is the user's position within that distribution.

<!-- @rev R13 rounds=3 by=robi:2026-09-25,claude:2026-10-13,claude:2026-10-13 -->
just-prs provides two scoring engines: **DuckDB** (SQL-based, out-of-core scoring) and **Polars** (LazyFrame joins). <!-- @rev C17 rounds=3 by=robi:2026-09-25,claude:2026-10-10,validator:2026-10-10 -->For diploid genotypes both engines compute the same score. They join the scoring file to the genome by chromosome and position, match the effect allele to the reference or alternate allele of the genotype record, take its dosage (0, 1 or 2), and sum dosage times effect weight. No strand flipping is applied, so an effect allele that matches neither allele contributes a dosage of 0; missing genotypes contribute nothing. The engines differ in how the join runs. DuckDB runs it as SQL, joining large scoring files in chunks of 250,000 to 2,000,000 variants sized from available memory, under a memory limit of 75% of RAM by default. Polars runs it as a single lazy in-memory dataframe join.<!-- @/rev C17 --> <!-- @rev A3f rounds=1 by=claude:2026-10-15 -->On the sex chromosomes and the mitochondrial genome, both engines count copies of the effect allele. just-prs infers the sample's karyotype from the share of heterozygous calls on the non-pseudoautosomal part of X, relative to the autosomes, and from calls on the non-pseudoautosomal part of Y. For a man it counts a homozygous call there as one copy and treats a heterozygous call as a no-call, since a single X cannot be heterozygous. The pseudoautosomal regions count as two copies in either sex and the mitochondrial genome as one; when the karyotype cannot be inferred, X and Y are scored as written.<!-- @/rev A3f --> PLINK2 serves only as an external comparator in the benchmark (Section 4.2); it is not a just-prs engine.
<!-- @/rev R13 -->

<!-- @rev J10 rounds=1 by=claude:2026-10-13 -->
For variant-only whole-genome VCFs, just-prs can optionally count absent scoring loci as homozygous reference, using a reference-allele dataset. This raises coverage for many scores, assuming those loci were callable; it is off by default and not applied to gVCF input.

For consumer arrays (23andMe, AncestryDNA), precomputed linkage disequilibrium (LD) proxy tables estimate untyped scoring variants from typed ones where suitable tables exist. Coverage, and the assumption used to recover each missing locus, remain part of the result's interpretation.
<!-- @/rev J10 -->

**Figure 3. PRS results in Just-DNA-Lite (just-prs trait view).** For a selected trait, all associated PGS Catalog models are computed and shown together as a consensus distribution with the user's percentile against a 1000 Genomes reference population, alongside per-model variant match rates and quality tiers. Showing the models together, including where they disagree, is deliberate (see Section 5.3).

<!-- AUTHOR TODO: Replace the existing images/just_prs_trait_consensus.jpg with a current screenshot for Figure 3. The existing image shows an absolute-risk percentage for intelligence and inconsistent quality labels. Capture a current trait view with the reference population, model IDs, coverage, and settings visible, then embed it here and align the caption with the final image. -->

### **3.2.1 Standalone PRS Use and MCP Access**

just-prs serves both as a component of Just-DNA-Lite and as an independent tool. Users who only want polygenic scores can use its Python API, command-line interface, dedicated web UI, or `just-prs-mcp` server without running the annotation-module workflow.

<!-- @rev J11 rounds=1 by=claude:2026-10-13 -->
Just-DNA-Lite also has its own MCP server for the full workflow (samples, modules, annotation jobs and their results), while `just-prs-mcp` covers PRS alone; both let AI assistants call the software through typed tools rather than write their own analysis code. The PRS tools cover catalogue search, model metadata, genome-build and ancestry detection, scoring, reference-population comparison and result-quality assessment.
<!-- @/rev J11 -->

<!-- @rev R14 rounds=1 by=robi:2026-09-25 -->
The tools return PGS IDs, variant-match rates, model quality tiers, reference populations, percentiles, and agreement or disagreement amongst models for a trait. These fields provide the assistant with computational context, however, their presence does not ensure that an assistant will explain them correctly. The server runs locally, but a remotely hosted assistant may receive tool outputs containing genomic results. Local scoring and private conversational processing therefore require separate consideration (Section 5.2).
<!-- @/rev R14 -->

<!-- @rev J13 rounds=1 by=claude:2026-10-13 -->
All these interfaces share one scoring implementation, and equivalent inputs, reference data and settings give equivalent results; the engine benchmark in Section 4.2 does not test each interface separately, nor the accuracy of assistant-generated explanations.
<!-- @/rev J13 -->

### **3.3 Additional Trait Annotation Modules**

<!-- @rev C18 rounds=4 by=robi:2026-09-25,claude:2026-10-10,validator:2026-10-10,claude:2026-10-13 -->
The platform includes several additional modules curated by hand from the published literature: **coronary artery disease** (SNPs selected on meta-study p-values and the number of studies across populations), **lipid metabolism** (selected by the same criteria), **VO2 max** (published studies of the oxygen-uptake response to exercise training, mostly candidate-gene and cohort studies) and **Superhuman** (rare protective alleles from the Church laboratory's Protective and Enhancing Alleles list, checked against the primary literature). Table S4 gives each module's curation and every source it cites.<!-- @/rev C18 --> All modules work by joining the user's VCF against curated variant-trait databases, adding annotation columns (weight, state, gene, conclusion) to matching variants.

### **3.4 Growing the Module Ecosystem**

<!-- @rev J14 rounds=1 by=claude:2026-10-13 -->
Because modules are data, new content reaches users through configured repositories or `just-dna-registry` without changes to the annotation engine or a new application release, while evidence review and scientific curation stay with module contributors. <!-- @rev D1 rounds=1 by=claude:2026-10-10 -->Rather than embedding its own assistant, the platform exposes its operations to the AI assistants authors already use. Modules can be drafted in such an assistant through the just-module-creator plugin (github.com/dna-seq/just-module-creator); the result is the same artifact, validated and compiled the same way, and its curator field marks it as AI-generated. Through the platform's MCP server, the assistant can then install the draft, annotate a genome with it and inspect the result (Section 3.2.1).<!-- @/rev D1 -->
<!-- @/rev J14 -->

## **4. Benchmarking and Validation**

### **4.1 Annotation Speed**

<!-- @rev B22 rounds=4 by=claude:2026-10-11,claude:2026-10-12,claude:2026-10-13,claude:2026-10-13 -->
We benchmarked Just-DNA-Lite against the Generation I OakVar-based system on one workstation (<!-- @rev C24b rounds=2 by=robi:2026-09-25,claude:2026-10-13 -->Table S6<!-- @/rev C24b -->). The main input was the public whole-genome VCF of one of the co-authors (Zenodo record 18370498, CC0), also used for the PRS benchmark in Section 4.2. Three more inputs vary the caller and the size: a second co-author's public genome, called with DRAGEN (Zenodo record 19487816, CC-BY-4.0), the HG002 output of the DeepVariant 1.0.0 whole-genome case study, and the private genome on which the earlier Generation I times were measured (Supplementary S2).<!-- @rev B27 rounds=2 by=claude:2026-10-11,claude:2026-10-13 --> The benchmark scripts, the record of every run and the script that generates every benchmark table from them are in the repository (`docs/manuscript/benchmarks/a3/`),<!-- @/rev B27 --> so the benchmark can be reproduced on the three public genomes, for Generation I given an OakVar store account (Table S2).
<!-- @/rev B22 -->

<!-- @rev B24 rounds=4 by=claude:2026-10-11,claude:2026-10-12,claude:2026-10-13,claude:2026-10-13 -->
Generation II annotated each genome with the ten modules of Table 1, with Ensembl annotation off, in three modes: *warm* runs reuse the sample's quality-filtered table, so the VCF is not read again; *full* runs start from a fresh instance and read the VCF, as every OakVar run does, so they are the counterpart of an OakVar run (same VCF and same kind of report, not the same computation); *cold* runs are full runs after the operating system's page cache has been dropped. Generation I, OakVar 2.13.1 with its modules and annotation databases installed from the OakVar store, ran three times on the primary genome and once on the calibration genome with the machine idle. Both systems were also timed on a second day with the desktop in light use (Generation I on the calibration and second-caller genomes), and Generation I with its dbSNP annotator alone was timed against Generation II with Ensembl annotation on. Supplementary S2 gives the run order and the Generation I setup.
<!-- @/rev B24 -->

<!-- @rev C22 rounds=2 by=claude:2026-10-11,claude:2026-10-13 -->
**Table 2.** Annotation wall time, from command start to report written: Just-DNA-Lite (Generation II) vs OakVar (Generation I). *n*, number of repeated runs. The last column divides the median Generation I time by the median of the row; a warm run does not read the VCF, so it is not compared. In the last section, the reference is Generation I with its dbSNP annotator alone, and the first run of each series is dropped as its warm-up.

| Genome / run | *n* | Median (min–max), s | Mean ± SEM, s | SD, s | Generation I ÷ this (medians) |
|---|---|---|---|---|---|
| **Primary (public, Zenodo 18370498)** |  |  |  |  |  |
| Generation II, warm | 11 | 16.3 (16.2–17.2) | 16.4 ± 0.1 | 0.3 | — |
| Generation II, full | 10 | 33.2 (31.9–50.8) | 35.2 ± 1.8 | 5.7 | 181× |
| Generation II, cold | 3 | 35.9 (35.6–36.0) | 35.9 ± 0.1 | 0.2 | 167× |
| Generation I (OakVar 2.13.1), full | 3 | 6,005.4 (5,889.3–6,068.5) | 5,987.7 ± 52.5 | 90.9 | 1× (ref.) |
| **Second caller (public, Zenodo 19487816)** |  |  |  |  |  |
| Generation II, warm | 11 | 20.2 (20.1–20.8) | 20.3 ± 0.1 | 0.2 | — |
| Generation II, full | 10 | 65.1 (62.0–107.6) | 72.7 ± 5.0 | 15.8 | 146× |
| Generation II, cold | 3 | 65.6 (65.3–65.7) | 65.5 ± 0.1 | 0.2 | 145× |
| Generation I (OakVar 2.13.1), full | 2 | 9,482.6 (8,337.6–10,627.7) | 9,482.6 ± 1,145.1 | 1,619.4 | 1× (ref.) |
| **Community reference (HG002, DeepVariant case study)** |  |  |  |  |  |
| Generation II, warm | 11 | 17.0 (16.9–17.2) | 17.0 ± 0.0 | 0.1 | — |
| Generation II, full | 5 | 38.4 (38.2–38.5) | 38.3 ± 0.1 | 0.1 | — |
| Generation II, cold | 3 | 41.9 (41.7–42.0) | 41.8 ± 0.1 | 0.2 | — |
| **Calibration (private, the 2023 benchmark file)** |  |  |  |  |  |
| Generation II, warm | 11 | 16.2 (16.1–16.4) | 16.2 ± 0.0 | 0.1 | — |
| Generation II, full | 10 | 33.7 (33.0–105.0) | 54.4 ± 9.2 | 29.2 | 231× |
| Generation II, cold | 3 | 36.7 (36.7–36.9) | 36.7 ± 0.1 | 0.1 | 212× |
| Generation I (OakVar 2.13.1), full | 3 | 7,785.3 (5,995.5–8,281.0) | 7,353.9 ± 694.1 | 1,202.2 | 1× (ref.) |
| **Primary, against a whole-genome reference database (first run of each dropped)** |  |  |  |  |  |
| Generation II, full + Ensembl | 2 | 103.1 (64.2–142.0) | 103.1 ± 38.9 | 55.0 | 34× |
| Generation I (OakVar 2.13.1), dbSNP only | 2 | 3,537.2 (3,446.8–3,627.5) | 3,537.2 ± 90.3 | 127.8 | 1× (ref.) |
<!-- @/rev C22 -->

<!-- @rev C23 rounds=2 by=claude:2026-10-11,claude:2026-10-13 -->
**Table 3.** Stage times and resources of the full runs (medians unless stated).<!-- @rev B25 rounds=2 by=claude:2026-10-11,claude:2026-10-12 --> Peak RAM is the resident memory summed over the whole process tree (for Generation I, the container's processes), sampled ten times a second; pages shared between processes count once per process, which overstates the total, while a peak shorter than the sampling interval can be missed.<!-- @/rev B25 --> CPU is user plus system time divided by wall time; it was not recorded for Generation I, which ran inside Docker. Warm and cold runs are in the repository's generated tables.

| Genome | Run | *n* (runs) | Normalize (s) | Annotate (s) | Report (s) | Peak RAM, median (MB) | Peak RAM, max (MB) | CPU (%) |
|---|---|---|---|---|---|---|---|---|
| Primary | Generation II, full | 10 | 15.7 | 10.2 | 1.9 | 2,235 | 2,270 | 375 |
| Primary | Generation I | 3 | — | — | — | 4,610 | 4,611 | — |
| Second caller | Generation II, full | 10 | 43.4 | 14.6 | 1.8 | 4,436 | 4,514 | 335 |
| Second caller | Generation I | 2 | — | — | — | 4,508 | 4,529 | — |
| Community reference | Generation II, full | 5 | 20.9 | 10.6 | 1.8 | 2,893 | 2,925 | 363 |
| Calibration | Generation II, full | 10 | 16.8 | 9.6 | 2.2 | 2,250 | 2,296 | 370 |
| Calibration | Generation I | 3 | — | — | — | 3,837 | 3,838 | — |
<!-- @/rev C23 -->

<!-- @rev A3a rounds=3 by=claude:2026-10-11,claude:2026-10-13,claude:2026-10-13 -->
On the primary genome, the median full run took 33.2 s against 6,005.4 s for Generation I, an approximately 181-fold speedup; across the three genomes Generation I ran on, it was 146- to 231-fold. Against a whole-genome reference database the gap narrows: Generation II with Ensembl annotation on took a median of 103.1 s and Generation I with dbSNP alone 3,537.2 s, about 34-fold. These ratios apply to these configurations and these inputs, rather than to OakVar generally. A warm run, which reuses the sample's quality-filtered table, took 16.3 s. The benchmark used SSD storage and a workstation with 63 GiB RAM; it does not directly establish performance on a laptop or on rotational disks. Peak memory of a Just-DNA-Lite run with Ensembl off was 2,054 to 2,270 MB on the primary genome and at most 4,525 MB on any genome, against at most 4,611 MB for Generation I (Table 3); with Ensembl annotation on it was 5,568 to 5,750 MB.
<!-- @/rev A3a -->

### **4.2 PRS Computation**

<!-- @rev B29 rounds=4 by=claude:2026-10-11,claude:2026-10-12,claude:2026-10-13,claude:2026-10-13 -->
We benchmarked just-prs's DuckDB and Polars engines against the external tool PLINK2 on 100 PGS Catalog scores (listed in Supplementary S3) using the primary whole-genome VCF of Section 4.1 (4,661,444 records with FILTER PASS or unset, GRCh38; Zenodo 18370498). Engines, timing and memory measurement are those of the benchmark script of just-prs 0.10.1, run through a harness described in Supplementary S3; each observation is a different scoring model applied to the same individual.
<!-- @/rev B29 -->

<!-- @rev A3b rounds=3 by=claude:2026-10-11,claude:2026-10-12,claude:2026-10-13 -->
PLINK2 was given two inputs, described in Supplementary S3: the *original* input that the just-prs benchmark script builds, and a *fixed* input built from the same records just-prs reads, with identifiers for every candidate other allele. Table 4 reports the fixed input; Table 5 reports both. PLINK2's time excludes preparing its score file, as in the just-prs script; including it moves PLINK2's median from 0.602 s to 0.604 s (Table 4).
<!-- @/rev A3b -->

<!-- @rev B30 rounds=2 by=claude:2026-10-11,claude:2026-10-13 -->
**Table 4.** Runtime of PRS computation engines (seconds per PGS ID), fixed PLINK2 input. "Excl." excludes the 7 PGS IDs with ≥ 1M variants. The speedup is PLINK2's median divided by the engine's; the median of the per-score ratios is shown beside it. With the original input, PLINK2 stopped on the four largest scores (Supplementary S3).

| Engine | *N* scored | Median (all), s | Mean (all), s | Median (excl. 7 with ≥ 1M variants), s | PLINK2 median ÷ engine median | Median per-ID PLINK2 ÷ engine |
|---|---|---|---|---|---|---|
| just-prs DuckDB | 100 | 0.081 | 0.188 | 0.081 | 7.4× | 7.4× (n=100) |
| just-prs Polars | 100 | 0.305 | 0.371 | 0.301 | 2.0× | 2.0× (n=100) |
| PLINK2 | 100 | 0.602 | 0.754 | 0.602 | 1.0× | 1.0× (n=100) |
| PLINK2 + score-file preparation | 100 | 0.604 | 1.555 | 0.604 | — | — |
<!-- @/rev B30 -->

<!-- @rev C26 rounds=1 by=claude:2026-10-11 -->
**Table 5.** Score concordance between engines, with both PLINK2 inputs. *r* is computed across the scores of one genome, so the largest scores dominate it.

| Engine pair | PLINK2 input | *N* PGS | Pearson *r* | Max \|Δ score\| |
|---|---|---|---|---|
| just-prs DuckDB ↔ just-prs Polars | fixed | 100 | 1.000000 | 5.68e-14 |
| just-prs DuckDB ↔ PLINK2 | fixed | 100 | 0.999997 | 0.501 |
| just-prs Polars ↔ PLINK2 | fixed | 100 | 0.999997 | 0.501 |
| just-prs DuckDB ↔ PLINK2 | original | 96 | 0.999859 | 21.4 |
| just-prs Polars ↔ PLINK2 | original | 96 | 0.999859 | 21.4 |
<!-- @/rev C26 -->

<!-- @rev C27 rounds=5 by=claude:2026-10-11,claude:2026-10-12,claude:2026-10-13,claude:2026-10-13,claude:2026-10-13 -->
DuckDB and Polars agreed to within 5.68 × 10⁻¹⁴ on this input. Both apply the same dosage rule and weighted sum and differ mainly in how the join runs, so their agreement checks the implementation, not the method. With the fixed input, scores agreed closely with the external PLINK2 comparator (Pearson r = 0.999997; maximum absolute score difference 0.501); with the original input, in which PLINK2 lost every candidate other allele but the first and counted reference-call records, r was 0.999859 and the maximum difference 21.4. The workflows differ in variant identification: just-prs joins on chromosome and position and counts the effect allele if it equals the reference or alternate allele, with no strand flipping and with restoration off, while PLINK2 matches exact chr:pos:ref:alt identifiers. The two can therefore include different variants (chrX, which the PLINK2 runs leave out; multi-allelic sites; positions where the alleles disagree), and scores can differ despite the same weighted-sum calculation. This concerns this PLINK2 configuration, not a general limitation of the tool. Supplementary S3 reports memory.
<!-- @/rev C27 -->

<!-- @rev B31 rounds=4 by=claude:2026-10-11,claude:2026-10-12,claude:2026-10-13,claude:2026-10-13 -->
With the fixed input, the median share of a score's variants that were matched was 53% for just-prs (range 22 to 79%) and 51% for PLINK2 (range 22 to 78%); the counts are not the same measure (scoring rows with a called genotype at their position for just-prs, variants processed and matched by identifier for PLINK2). These values describe the benchmark configuration rather than the maximum coverage of just-prs: reference-homozygote restoration, off here, and the LD-proxy estimation of the array workflow (Section 3.2) can raise coverage, and this comparison measures neither. The reported speedups are ratios of median runtimes over the same 100 scores; the medians of the per-score ratios agree with them to the precision shown (Table 4).
<!-- @/rev B31 -->

<!-- @rev A3g rounds=1 by=claude:2026-10-15 -->
The comparison above covers chromosomes 1 to 22. The just-prs project's own benchmark (just-prs 0.10.4) scored 195 PGS Catalog scores on the same genome with X, Y, the pseudoautosomal regions and the mitochondrial genome included: the 100 above and further scores with rows on those chromosomes. The sample was marked male in PLINK2, and just-prs inferred it as male (XY). Against PLINK2 with its X model 1 (half a copy for a heterozygous call on a man's X), Pearson *r* was 0.99999847 and 114 of the 195 scores agreed to within 10⁻³. The largest difference, 2.95 on a score of 854.9 (PGS001108), comes from heterozygous calls on the non-pseudoautosomal part of X, which just-prs treats as no-calls; removing that share leaves a largest difference of 0.14. DuckDB and Polars agreed to within 2.27 × 10⁻¹³. This run is not used for timing.
<!-- @/rev A3g -->


## **5. Discussion**

### **5.1 Limitations of Variant Annotation**

<!-- @rev R17 rounds=2 by=robi:2026-09-25,claude:2026-10-13 -->
Variant annotation tools <!-- @rev C30 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->are based on<!-- @/rev C30 --> statistical associations from published literature, and several inherent limitations apply. Heritability is a population-level statistic, not individual determinism, and estimates change with environment, study design, and cohort. A polygenic risk score is a linear weighted sum that reflects where an individual is situated in a reference population's distribution. However, biology is not linear, and gene-gene and gene-environment interactions, feedback loops, developmental windows, and compensatory mechanisms are not always captured by a polygenic score. Moreover, most PGS Catalog scoring files were derived from predominantly European cohorts, so associations may not transfer to other ancestries (Section 5.4). Additionally, most variants reported are statistical associations from GWAS, not established causal mechanisms; many GWAS hits are tagging SNPs, and effect sizes typically shrink in replication.
<!-- @/rev R17 -->

<!-- @rev R18 rounds=2 by=robi:2026-09-25,claude:2026-10-13 -->
AI-generated modules carry additional uncertainty: they are automated drafts produced by language models reading published papers, and they will contain mistakes. Users should treat them as lower confidence than expert-curated modules and review the underlying evidence. Just-DNA-Lite is a research tool, not a clinical pipeline. Raw VCFs contain false positives, and automated annotations have inherent error rates. It does not interpret results in a clinical context.
<!-- @/rev R18 -->

### **5.2 Local Processing and Data Privacy**

<!-- @rev R19 rounds=1 by=robi:2026-09-25 -->
Core annotation and PRS computation use local genome files, cached reference datasets, and local result storage. Downloading reference data does not require uploading the user's genome. This architecture reduces the need to disclose genomic data to a hosted analysis service, however, local execution is not a guarantee against disclosure through other parts of the workflow. More precisely, optional AI explanations and MCP clients, for example, require a separate assessment: when an assistant uses an external model provider, prompts and tool outputs may transmit sensitive results even if the raw VCF remains local. Privacy therefore depends on the deployment, the selected services, and the information shared with them. The platform's local architecture alone does not establish regulatory compliance.
<!-- @/rev R19 -->

### **5.3 Platform Philosophy: Transparency and the Right to Read Your Own Genome**

<!-- @rev R20 rounds=1 by=robi:2026-09-25 -->
Just-DNA-Lite is built on a simple conviction: people have the right to read and explore their own genomic data, and well-intended researchers have the right to work with public genomes without a gatekeeper's permission. The GDPR's right of access (Article 15) already entitles individuals to obtain a copy of their personal data, and the emerging European Health Data Space is designed to give people access to and control over their own health information. A tool that runs locally and shows users useful information in their own genome is, in this light, an instrument of an existing right.
<!-- @/rev R20 -->

<!-- @rev R21 rounds=2 by=robi:2026-09-25,claude:2026-10-13 -->
Genomic findings can be misinterpreted or provide false reassurance, particularly when analytical errors and ancestry differences are overlooked (Tandy-Connor et al., 2018; Manrai et al., 2016). The interface presents model provenance, variant-match rates, ancestry context, and differences among scores to make these limitations inspectable. However, the platform is not intended to provide medical advice. Displaying this information is a design choice; whether it improves user understanding requires a usability study.
<!-- @/rev R21 -->

### **5.4 Limitations**

<!-- @rev R22 rounds=3 by=robi:2026-09-25,claude:2026-10-13,claude:2026-10-13 -->
**Population stratification.** The 1000 Genomes-based percentile distributions provide population-specific reference points (AFR, AMR, EAS, EUR, SAS), but most modules and PGS scoring files derive from predominantly European cohorts; transferability to non-European populations is a known limitation of the source data, not specific to this platform. **Ancestry selection.** The reference superpopulation is inferred from the genome and can be changed by the user, but five continental superpopulations do not represent admixed or finer-scale ancestry. **Input format.** The platform supports WGS and WES VCFs on GRCh38, and consumer microarray data experimentally (with far lower coverage, which the platform shows to users). The just-prs library can score a GRCh37 sample against the PGS Catalog's harmonized GRCh37 files, but annotation is GRCh38-only and the web interface currently treats every sample as GRCh38; T2T references are not supported. <!-- @rev C2d rounds=3 by=robi:2026-09-25,claude:2026-10-10,claude:2026-10-13 -->**Benchmark scope.** Annotation runtime was measured on four genomes, three of them public, and score agreement on one. They describe computational performance; they do not establish predictive accuracy or agreement in rankings across individuals.<!-- @/rev C2d --> <!-- @rev C28 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->They also measure speed and agreement between scoring engines, not whether annotations are correct. Correctness depends on two things they do not test: whether the cited studies are right, and whether each module records their findings faithfully (which variant, allele and genotype, and what the report says about it).<!-- @/rev C28 -->
<!-- @/rev R22 -->

### **5.5 Future Directions**

<!-- @rev R23 rounds=3 by=robi:2026-09-25,claude:2026-10-13,claude:2026-10-13 -->
Several extensions are underway or planned: GRCh37/hg19 support across annotation and the web interface, fuller consumer-microarray support, and T2T reference support. Multi-species support (companion-animal genomics) and methylation or transcriptomic ageing clocks, among the analyses users most often request, are under consideration. Within the ROGEN consortium, population-calibrated polygenic risk scores are planned for a Romanian genomic cohort of approximately 5,000 individuals; that cohort is currently being sequenced, and none of the work reported here uses cohort data. <!-- @rev C35 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->We encourage the community to build and share modules. Modules published by others are not treated as accurate by default: community- and AI-generated modules will contain mistakes, and the platform mitigates this<!-- @/rev C35 --> not by gatekeeping but by making provenance visible (the `curator` field, the explicit expert-versus-AI distinction) so that trust can be calibrated. How best to curate and validate a large, decentralized ecosystem of genomic annotations is not yet known; Just-DNA-Lite is offered both as a usable platform and as a testbed for that question.
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
- **Borysova Olga** — <!-- @rev C12g rounds=2 by=robi:2026-09-24,claude:2026-10-13 -->module curation<!-- @/rev C12g --> and report content (<!-- @rev C12f rounds=2 by=robi:2026-09-24,claude:2026-10-13 -->longevity variants, cardiovascular traits, lipid metabolism, thrombophilia, VO2 max, athletic performance, pharmacogenomics, and the Superhuman module, built from George Church's Protective and Enhancing Alleles list<!-- @/rev C12f -->), LongevityMap database curation and expansion, pathway categorization, report structure, data collection and analysis
- **Karmazin Alexey** — lead architect of the <!-- @rev C37 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->report system of Generation I (the OakVar-based Just-DNA-Seq)<!-- @/rev C37 -->, OakVar report modules and preparation utilities, PRS modules
- **Koval Maria** — report modules, report template, <!-- @rev C12h rounds=2 by=robi:2026-09-24,claude:2026-10-13 -->code of the trait annotation modules (thrombophilia, cardiovascular)<!-- @/rev C12h -->
- **Fedorova Alina** — bioinformatic utilities, scientific literature exploration
- **Pushkareva Malvina** — software development and testing
- **Evfratov Sergey** — pharmacogenomics (drug) module development
- **Ryangguk Kim** — created and maintained OakVar, extended it for the Generation I platform
- **Zaharia Livia** — beta-testing, provided her whole genome for testing and benchmarking
- **Fuellen Georg** — co-supervision, valuable suggestions and comments
- **Tacutu Robi** — <!-- @rev C38 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->co-supervision,<!-- @/rev C38 --> bioinformatics and ageing research advising, LongevityMap database

**Acknowledgments:** Volodymir Semenuik for help with documentation.

## **Funding**

<!-- @rev R26 rounds=2 by=robi:2026-09-25,claude:2026-10-13 -->
The research carried out by A.K. and R.T. was supported by The Ministry of Investments and European Projects, through the Managing Authority for the Health Program, PS/272/PS_P5/OP1/RSO1.1/PS_P5_RSO1.1_A9–ROGEN Project (MySMIS 324809). R.T. was also supported by The Romanian Academy.
<!-- @/rev R26 -->

## **Code Availability**

<!-- @rev J15 rounds=1 by=claude:2026-10-13 -->
**GitHub organization:** https://github.com/dna-seq; Table S8 lists the repositories of both generations.
<!-- @/rev J15 -->

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
**S2. Generation I vs Generation II Speed Comparison.** The individual 2026 Generation I runs (OakVar 2.13.1 on the workstation of Table S6): on the primary genome 6,005.4, 6,068.5 and 5,889.3 s on the first night; on the calibration genome 5,995.5 s on the first night and 7,785.3 and 8,281.0 s on the second day; on the second-caller genome 10,627.7 and 8,337.6 s, a third run having been stopped after 1,277.8 s when a system update restarted the Docker daemon; and with dbSNP alone on the primary genome 7,041.5 s (the warm-up), 3,627.5 and 3,446.8 s; with peak memory of 3,832 to 4,611 MB; OakVar's own step times (on the primary genome, as medians of the three runs, the postaggregator step, which runs the Generation I modules, takes 38.9% of a run, the annotators 28.7% and the mapper 17.1%); and the installed OakVar modules, among them dbSNP 156.0.1, ClinVar 2026.10.01, gnomAD 2.2.0 (data v2.1), SIFT 1.3.0, GENCODE 46.1.1 and the nine Generation I postaggregators, 0.1.0 to 0.1.2 (Table S2). It also keeps the earlier Generation I runs on the calibration genome, made on another workstation with the OakVar and module versions of the time (2023-02-17: 5,651 s; 2023-02-19: 6,803 s; 2023-05-07: 7,662 s), reported in earlier drafts. The speedup reflects the architectural differences described in the main text; this comparison does not isolate their individual contributions. All of it is generated into `docs/manuscript/benchmarks/a3/tables.md`.
<!-- @/rev B28 -->

<!-- @rev J16 rounds=2 by=claude:2026-10-13,claude:2026-10-13 -->
Run protocol. After one warm-up run, the Generation II runs of each genome were interleaved in a seeded random order, with the machine idle. On a second day, with the desktop in light use, Generation II made five more full runs, after a warm-up, on each of the three genomes Generation I ran on, and Generation I ran twice more on the calibration genome and twice on the second-caller genome; the two systems' runs were not interleaved with each other. The dbSNP-only Generation I series and the Ensembl Generation II series had no warm-up, so the first run of each, which read its database from disk for the first time (OakVar's annotator step took 3,520.3 s, against 608.1 and 574.8 s in the next two runs), is dropped as the warm-up; both first runs are in the repository's record of runs. Generation I ran with no warm-up, using its nine postaggregator modules (it has no counterpart of the Pathogenic module), with OakVar 2.13.1, the latest release at the time (published 2026-08-30), and the Generation I modules and annotation databases installed from the OakVar store in October 2026, in a Docker image that adds one compatibility line for the store's dbSNP annotator. Some store versions of the Generation I modules differ from those on GitHub; Table S2 lists the versions that ran beside both. All 2026 runs, Generation I included, used the same workstation.
<!-- @/rev J16 -->

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

<!-- @rev B32 rounds=3 by=claude:2026-10-11,claude:2026-10-12,claude:2026-10-13 -->
**S3. Runtime and Memory on Large PRS Scoring Files.** Runtimes and memory for the 7 genome-wide PGS IDs (1.7 to 6.9M variants) with both PLINK2 inputs; with the original input PLINK2 failed on the four largest (PGS000013, PGS000014, PGS000016 and PGS000017) because a variant appeared twice in its score file ("ALT1 allele … appears multiple times"), the liftover duplicates that the fixed input merges; logs are in the repository. Memory is measured differently per engine: for DuckDB and Polars, the growth of the benchmark process's resident memory during the call, sampled every 10 ms (median over all 100 scores with the fixed input, 5.4 MB and 1,061.2 MB); for PLINK2, the peak resident memory of its own process, sampled every 100 ms (median 511.6 MB, fixed input). The two measures are not directly comparable. The 100 scores are PGS000006 to PGS000106, excluding PGS000085; PGS000001 to PGS000003 ran first as a warm-up. The benchmark harness fixes the list of scores, calls PLINK2 with the same command line as the just-prs script but keeps its log for every score, and includes PLINK2 in the warm-up (`docs/manuscript/benchmarks/a3/prs/`). PLINK2's two inputs: the *original* input is the one the just-prs benchmark script builds, a genotype file from every record, reference calls included, and variant identifiers (in both allele orders) built from each scoring row's first candidate other allele only; the *fixed* input builds the genotype file from the records just-prs reads (FILTER PASS or unset), gives identifiers for every candidate other allele, and sums the weights of identifiers that two scoring rows share after liftover. Both inputs restrict PLINK2 to the autosomes, while just-prs reads every chromosome. just-prs compares a multi-allelic record's alternate alleles as one string and does not check the other allele.
<!-- @/rev B32 -->

<!-- @rev C13c rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->
**S4. Module sources.** For each annotation module the project publishes in the module registry (https://module-registry.just-dna.life, namespace `just-dna-seq`), as of 2026-10-10 18:00 UTC: version, publication date, artifact digest, curator type, how the module was curated, the source databases with their release, and every paper its rows cite (first author, year, PMID, DOI) with the number of rows citing it. Read from the modules' own published files; later versions may differ. Files: `S4_module_sources.md`, `S4_module_sources.csv`, `S4_module_citations.csv`.
<!-- @/rev C13c -->

<!-- @rev J17 rounds=1 by=claude:2026-10-13 -->
**S5. PGS Catalog coverage of just-prs.** For every score of the PGS Catalog release of 2026-09-17 (6,991 scores), the harmonized GRCh38 scoring file was read in full and each row classified by whether just-prs can place and match it. 6,910 files are scored as specified, 76 only approximately (for example, at least 10% of the absolute weight on rows it cannot place or match, or dominant or recessive coding that it applies additively) and 5 cannot be scored. Method, rules, threshold sensitivity and per-file values are in Table S5 (`S5_pgs_coverage.md`, `S5_pgs_coverage.csv`).
<!-- @/rev J17 -->

<!-- @rev C24a rounds=2 by=robi:2026-09-25,claude:2026-10-13 -->
**S6. Benchmark hardware and inputs.** The workstation, software versions and input genomes of the annotation benchmark in Section 4.1, recorded at run time (Table S6).
<!-- @/rev C24a -->

<!-- @rev B23 rounds=2 by=claude:2026-10-11,claude:2026-10-12 -->
**Table S6.** Benchmark hardware and inputs, recorded at run time (October 2026).

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


<!-- @rev C36b rounds=2 by=robi:2026-09-25,claude:2026-10-13 -->
**S7. Comparison with other tools.** The features that Just-DNA-Lite and 22 tools for personal-genome annotation, polygenic scoring and AI-assisted interpretation document for themselves, read on 10 October 2026 from each project's own documentation, README or paper; the evidence for every cell, with links, is in the repository (`docs/manuscript/v0.4/c36-tool-comparison-draft.md`).

**Table S7.** Documented features of Just-DNA-Lite and tools for personal-genome annotation, polygenic scoring and AI-assisted interpretation, as of 10 October 2026. Feature comparison only; no cell is a claim about accuracy, speed or usability.

| Tool | Runs locally (no upload) | Graphical interface | Add annotation sets without code | PRS (PGS Catalog) | Ancestry-aware percentiles | Human-readable report | AI-assistant (MCP) access | Open source (licence) | Last release (date) | Reference |
|---|---|---|---|---|---|---|---|---|---|---|
| **Just-DNA-Lite** | Yes | Yes (local web UI) | Yes | Yes | Yes | Yes | Yes | Yes (AGPL-3.0) | v0.3.18 (2026-08-16) | this work |
| *Variant annotation engines* | | | | | | | | | | |
| Ensembl VEP | Yes (also hosted) | Hosted web form only^a^ | Yes | No | n/a | Partial^b^ | No^c^ | Yes (Apache-2.0) | 116.3 (2026-10-09) | McLaren et al., 2016 |
| ANNOVAR | Yes (also hosted: wANNOVAR) | Hosted web form only^a^ | Yes | No | n/a | No | No | No (free for non-commercial use) | ? (2025-03-02)^d^ | Wang et al., 2010 |
| SnpEff / SnpSift | Yes | No | Yes | No | n/a | Partial^b^ | No | Yes (MIT) | 5.4c (2026-02-23) | Cingolani et al., 2012a, 2012b |
| vcfanno | Yes | No | Yes | No | n/a | No | No | Yes (MIT) | 0.3.9 (2026-06-16) | Pedersen et al., 2016 |
| echtvar | Yes | No | Yes | No | n/a | No | No | Yes (MIT) | 0.2.4 (2026-04-30) | Pedersen & de Ridder, 2023 |
| *Personal-genome platforms and reports* | | | | | | | | | | |
| OpenCRAVAT | Yes (also hosted) | Yes (local web UI; also hosted) | Partial^cc^ | No | n/a | Partial^dd^ | Partial^ee^ | Yes (MIT) | 3.2.1 (2026-10-08) | Pagel et al., 2020 |
| OakVar^e^ | Yes | Yes (local web UI) | Partial^cc^ | ?^ff^ | ?^ff^ | Partial^dd^ | No | No (proprietary; free for non-commercial use after registration) | 2.13.1 (2026-08-30) | no paper (GitHub) |
| GenomeChronicler | Yes | No | ? | No | n/a | Yes (PDF) | No | ?^gg^ | 0.91 (2019-10-26); fixes merged 2026-07-09 | Guerra-Assunção et al., 2020 |
| SNPedia / Promethease | No (upload to paid service) | Hosted web form | No | ? | ? | Yes (interactive HTML) | ? | No (closed service; SNPedia content CC BY-NC-SA 3.0) | n/a (service operating 2026-10-10)^hh^ | Cariaso & Lennon, 2012 |
| impute.me (discontinued 2022) | Partial (hosted; local Docker route documented) | Hosted web form | ? | Partial^ii^ | Yes (Z-scores per 1000 Genomes superpopulation) | Partial | n/a | Yes (LGPL-3.0; code no longer on GitHub) | 1.0.7 (2021-11-02)^jj^ | Folkersen et al., 2020 |
| VCFshiny | Yes | Yes (local web UI) | Partial^f^ | No | n/a | Partial^g^ | No | Yes (MIT) | none tagged; last code commit 2024-10-16 | Chen et al., 2023 |
| PharmCAT | Yes | No | Partial^h^ | No | n/a | Yes | No | Yes (MPL-2.0) | 3.4.0 (2026-07-14) | Sangkuhl et al., 2020; Li et al., 2023 |
| ACVI-Med | Yes (self-hosted) | Yes (local web UI) | Partial^i^ | ? | n/a | Partial^g^ | No | Yes (MIT) | none tagged; last commit 2026-05-28 | Stadler et al., 2026 |
| Personal-Genome-Pipeline | Yes | No | Partial^j^ | Yes | Yes | Yes | No | Yes (GPL-3.0-or-later) | 0.8.2 (2026-07-01) | no paper (GitHub) |
| *Polygenic score tools* | | | | | | | | | | |
| PLINK 2 | Yes | No | n/a^k^ | Partial^l^ | ? | ? | No | Yes (GPL-3.0) | 2.0.0-a.7.11 (2026-10-01) | Chang et al., 2015 |
| PRSice-2 | Yes | No | n/a^k^ | No^m^ | ? | Partial^n^ | No | Yes (GPL-3.0) | 2.3.5 (2021-09-20)^o^ | Choi & O'Reilly, 2019 |
| pgsc_calc | Yes | No | n/a^k^ | Yes^p^ | Yes (optional) | Partial^q^ | No | Yes (Apache-2.0) | 2.3.0 (2026-06-03) | Lambert et al., 2024 |
| GenoPred | Yes | No | n/a^k^ | Yes | Partial^r^ | Yes | No | Yes (GPL-3.0) | 2.3.3 (2025-11-27) | Pain et al., 2024 |
| Imputation Server PGS / pgs-calc | Yes (pgs-calc; server requires upload) | Hosted web form only^a^ | n/a^k^ | Yes | No^s^ | Partial^q^ | No | Yes (MIT) | pgs-calc 1.6.2 (2025-10-28) | Forer et al., 2024 |
| PRSKB | Yes (CLI; web version computes in the browser) | Yes (web page, in-browser) | n/a^k^ | Partial^t^ | Partial^u^ | Partial^v^ | No | No (free for academic use) | 1.0.0 (2022-06-23); last commit 2024-08-22 | Page et al., 2022 |
| PGS Browser / pgsb-cli | Yes (scoring); interpretation hosted | Partial^w^ | n/a^k^ | Yes | Partial^x^ | Partial^v^ | No | No (CC BY-NC-ND 4.0) | none tagged; last commit 2026-05-14 | Kolosov et al., 2026 |
| *AI-assistant and LLM interpretation* | | | | | | | | | | |
| GeneChat MCP | Yes^y^ | No | No | Yes (4 bundled scores) | No | Partial^z^ | Yes | Yes (MIT) | none tagged; last commit 2026-04-13 | no paper (GitHub) |
| DeepRare | Partial^aa^ | Hosted web app (by request) | ? | No | n/a | Yes (hosted app) | No^bb^ | No (CC BY-NC 4.0) | none tagged; last commit 2026-04-14 | Zhao et al., 2026 |

**Column definitions.** *Runs locally*: the core analysis runs on the user's machine without uploading the genome to a third-party server; "also hosted" marks tools that additionally offer an upload service. *Graphical interface*: a GUI for the core analysis, either local or hosted (stated). *Add annotation sets without code*: a user adds a new annotation source by supplying data files and configuration, without writing program code (n/a for tools that do not annotate variants). *PRS (PGS Catalog)*: computes scores from PGS Catalog scoring files; Partial when only generic user-formatted weights are accepted. *Ancestry-aware percentiles*: places the score against a reference population matched to, or chosen for, the sample's ancestry. *Human-readable report*: output meant to be read by a person (narrative or interpreted summary), beyond an annotated VCF or table; Partial for run statistics, QC dashboards or interactive tables without interpretation. *AI-assistant access*: an MCP server (or documented LLM tool interface) from the project itself. *Last release*: latest tagged release on GitHub or the official download page; where none exists, the last commit.

**Table notes.**

^a^ The local version is command-line only; the graphical interface requires uploading data to the hosted service.

^b^ HTML run summary with variant-consequence statistics and charts; no interpretation of individual findings.

^c^ No Ensembl MCP server; third-party wrappers exist (e.g. VEPmcp), which call the Ensembl REST API rather than a local VEP.

^d^ The 2025-03-02 software update is announced without a version label.

^e^ OakVar is a fork of OpenCRAVAT; Generation I of Just-DNA-Seq was built on it, and its author is a co-author of this paper.

^f^ Users select from ANNOVAR's database list in the interface; adding an own source is not documented.

^g^ Interactive tables and plots (VCFshiny) or ACMG-guided tiering for clinicians (ACVI-Med); no exported narrative report described.

^h^ Custom named-allele definitions (JSON) for pharmacogene diplotype calling only.

^i^ Additional sources are added at the VEP annotation step (`--custom`); the importer then indexes any INFO/CSQ field without code.

^j^ A PGS Catalog score is added by one line in a configuration table; the annotation databases are a fixed set.

^k^ Not a variant-annotation tool.

^l^ Generic score files (variant, allele, weight); the documentation does not mention the PGS Catalog format, which needs column mapping.

^m^ Computes PRS from GWAS summary statistics by clumping and thresholding; precomputed weights can be supplied (`--no-clump`) but the PGS Catalog is not mentioned.

^n^ Plots of model fit across a cohort, not a per-person result.

^o^ No release since 2021; occasional fixes to 2026-04-10, and the site states the software is being rebuilt.

^p^ The README states that whole-genome sequencing VCFs are not currently supported directly (gVCF conversion suggested).

^q^ HTML report of score distributions and variant-matching QC across samples, not a per-person narrative.

^r^ Scores are standardised against an ancestry-matched reference (PC projection); percentiles are not described.

^s^ Ancestry is estimated, but used only to warn about or exclude mismatched samples.

^t^ Uses NHGRI-EBI GWAS Catalog associations, not PGS Catalog scoring files; user summary statistics accepted.

^u^ Percentile against a user-chosen cohort (UK Biobank by default; 1000 Genomes superpopulations available), not matched automatically.

^v^ Tabular output with standardised scores or percentiles; interactive web views (PGS Browser) or website plots limited to precomputed data (PRSKB).

^w^ A hosted Shiny application that takes the locally computed percentile, sex and age; the genome never reaches it, and scoring itself is command line.

^x^ Scores adjusted for the first five genetic principal components; the reference distribution is FinnGen.

^y^ The VCF stays local, but tool responses (genotypes, interpretations) go to the user's LLM provider unless a local model is used; the same boundary applies to Just-DNA-Lite's MCP server.

^z^ A structured genome summary tool; narrative text comes from the client's language model.

^aa^ Exomiser runs on the VCF locally; the reasoning tier calls a commercial LLM API unless the code is adapted, and the authors recommend their hosted application.

^bb^ The paper describes the agent architecture as "inspired by" MCP; no MCP server is offered to outside clients.

^cc^ Prebuilt annotation modules install from a store through the interface; authoring a new annotator requires editing a Python file.

^dd^ Interactive result viewer and tabular, Excel or VCF reporters; no narrative report described in the core documentation.

^ee^ An official MCP server (Oct 2025) hosted at mcp.opencravat.org, which annotates single variants through public OpenCRAVAT services; it has no access to a user's local genome or jobs.

^ff^ Not mentioned in OakVar's own documentation. An OakVar module from the authors' Generation I Just-DNA-Seq (Kulaga et al., 2024) computed PGS Catalog scores as percentiles against simulated gnomAD-frequency genotypes, without ancestry matching.

^gg^ No licence file in the repository; the paper describes the pipeline as "fully open source".

^hh^ Promethease has been owned by MyHeritage since 2019; reports cost US$25. SNPedia editing has been sparse since 2023.

^ii^ Scores from GWAS summary statistics and LDpred weights for 1,859 GWAS and 634 UK Biobank traits; the PGS Catalog is not mentioned.

^jj^ The site redirects to a commercial service (Nucleus Genomics) since June 2022; the repository now holds only a README.

**Cell convention.** "No" means the project's documentation or paper, read in full, describes the tool's scope without the feature; "?" means the material available did not settle it.

**References for Table S7.**

Cariaso, M., & Lennon, G. (2012). SNPedia: a wiki supporting personal genome annotation, interpretation and analysis. *Nucleic Acids Research*, 40(D1), D1308–D1312. doi:10.1093/nar/gkr798.

Chang, C. C., Chow, C. C., Tellier, L. C. A. M., Vattikuti, S., Purcell, S. M., & Lee, J. J. (2015). Second-generation PLINK: rising to the challenge of larger and richer datasets. *GigaScience*, 4, 7. doi:10.1186/s13742-015-0047-8.

† Chen, T., et al. (2023). VCFshiny: an R/Shiny application for interactively analyzing and visualizing genetic variants. *Bioinformatics Advances*, 3(1), vbad107. doi:10.1093/bioadv/vbad107. (Already in the v0.3 reference additions.)

Choi, S. W., & O'Reilly, P. F. (2019). PRSice-2: Polygenic Risk Score software for biobank-scale data. *GigaScience*, 8(7), giz082. doi:10.1093/gigascience/giz082.

Cingolani, P., Platts, A., Wang, L. L., Coon, M., Nguyen, T., Wang, L., Land, S. J., Lu, X., & Ruden, D. M. (2012a). A program for annotating and predicting the effects of single nucleotide polymorphisms, SnpEff: SNPs in the genome of *Drosophila melanogaster* strain w1118; iso-2; iso-3. *Fly*, 6(2), 80–92. doi:10.4161/fly.19695.

Cingolani, P., Patel, V. M., Coon, M., Nguyen, T., Land, S. J., Ruden, D. M., & Lu, X. (2012b). Using *Drosophila melanogaster* as a model for genotoxic chemical mutational studies with a new program, SnpSift. *Frontiers in Genetics*, 3, 35. doi:10.3389/fgene.2012.00035. (Crossref gives no article number; 35 is taken from the DOI suffix.)

Folkersen, L., Pain, O., Ingason, A., Werge, T., Lewis, C. M., & Austin, J. (2020). Impute.me: an open-source, non-profit tool for using data from direct-to-consumer genetic testing to calculate and interpret polygenic risk scores. *Frontiers in Genetics*, 11, 578. doi:10.3389/fgene.2020.00578.

† Forer, L., Taliun, D., LeFaive, J., Smith, A. V., Boughton, A. P., Coassin, S., Lamina, C., Kronenberg, F., Fuchsberger, C., & Schönherr, S. (2024). Imputation Server PGS: an automated approach to calculate polygenic risk scores on imputation servers. *Nucleic Acids Research*, 52(W1), W70–W77. doi:10.1093/nar/gkae331.

Guerra-Assunção, J. A., Conde, L., Moghul, I., Webster, A. P., Ecker, S., Chervova, O., Chatzipantsiou, C., Prieto, P. P., Beck, S., & Herrero, J. (2020). GenomeChronicler: the Personal Genome Project UK genomic report generator pipeline. *Frontiers in Genetics*, 11, 518644. doi:10.3389/fgene.2020.518644.

† Kolosov, N., Reeve, M. P., Della Briotta Parolo, P., Kurki, M. I., Llorens, V., Sipilä, T. P., Herman, A., Molotkov, I., Aavikko, M., Ripatti, S., Palotie, A., Daly, M. J., & Artomov, M. (2026). PGS Browser: a public platform for personalized polygenic score analysis and interpretation. *Nature Communications*, 17, 7806. doi:10.1038/s41467-026-74461-7.

† Lambert, S. A., Wingfield, B., Gibson, J. T., et al. (2024). Enhancing the Polygenic Score Catalog with tools for score calculation and ancestry normalization. *Nature Genetics*, 56(10), 1989–1994. doi:10.1038/s41588-024-01937-x.

† Li, B., Sangkuhl, K., Keat, K., Whaley, R. M., Woon, M., Verma, S., Dudek, S., Tuteja, S., Verma, A., Whirl-Carrillo, M., Ritchie, M. D., & Klein, T. E. (2023). How to run the Pharmacogenomics Clinical Annotation Tool (PharmCAT). *Clinical Pharmacology & Therapeutics*, 113(5), 1036–1047. doi:10.1002/cpt.2790.

McLaren, W., Gil, L., Hunt, S. E., Riat, H. S., Ritchie, G. R. S., Thormann, A., Flicek, P., & Cunningham, F. (2016). The Ensembl Variant Effect Predictor. *Genome Biology*, 17, 122. doi:10.1186/s13059-016-0974-4.

Page, M. L., Vance, E. L., Cloward, M. E., et al. (2022). The Polygenic Risk Score Knowledge Base offers a centralized online repository for calculating and contextualizing polygenic risk scores. *Communications Biology*, 5, 899. doi:10.1038/s42003-022-03795-x.

Pagel, K. A., Kim, R., Moad, K., Busby, B., Zheng, L., Tokheim, C., Ryan, M., & Karchin, R. (2020). Integrated informatics analysis of cancer-related variants. *JCO Clinical Cancer Informatics*, 4, 310–317. doi:10.1200/CCI.19.00132.

† Pain, O., Al-Chalabi, A., & Lewis, C. M. (2024). The GenoPred pipeline: a comprehensive and scalable pipeline for polygenic scoring. *Bioinformatics*, 40(10), btae551. doi:10.1093/bioinformatics/btae551.

Pedersen, B. S., Layer, R. M., & Quinlan, A. R. (2016). Vcfanno: fast, flexible annotation of genetic variants. *Genome Biology*, 17, 118. doi:10.1186/s13059-016-0973-5.

† Pedersen, B. S., & de Ridder, J. (2023). Echtvar: compressed variant representation for rapid annotation and filtering of SNPs and indels. *Nucleic Acids Research*, 51(1), e3. doi:10.1093/nar/gkac931.

Sangkuhl, K., Whirl-Carrillo, M., Whaley, R. M., et al. (2020). Pharmacogenomics Clinical Annotation Tool (PharmCAT). *Clinical Pharmacology & Therapeutics*, 107(1), 203–210. doi:10.1002/cpt.1568.

† Stadler, M., Gansberger, S., Borik-Heil, L., Griss, J., Okamoto, I., Weninger, W. P., & Wielscher, M. (2026). ACVI-Med, an open source variant interpretation tool for medical genomics. *BMC Bioinformatics*, 27, 85. doi:10.1186/s12859-026-06414-2.

Wang, K., Li, M., & Hakonarson, H. (2010). ANNOVAR: functional annotation of genetic variants from high-throughput sequencing data. *Nucleic Acids Research*, 38(16), e164. doi:10.1093/nar/gkq603.

† Zhao, W., Wu, C., Fan, Y., et al. (2026). An agentic system for rare disease diagnosis with traceable reasoning. *Nature*, 651(8106), 775–784. doi:10.1038/s41586-025-10097-9.

Software without a paper (cite as software, accessed 10 October 2026):

† Costello, N. (2026). GeneChat MCP server [software]. https://github.com/natecostello/genechat-mcp.

† GeiserX (2026). Personal-Genome-Pipeline, version 0.8.2 [software]. https://github.com/GeiserX/Personal-Genome-Pipeline.

† KarchinLab (2025). OpenCRAVAT MCP server [software]. https://github.com/KarchinLab/oc-mcp.

† Oak Bioinformatics (2026). OakVar, version 2.13.1 [software]. https://github.com/rkimoakbioinformatics/oakvar.
<!-- @/rev C36b -->

<!-- @rev J18 rounds=1 by=claude:2026-10-13 -->
**S8. Software repositories.**

**Table S8.** Software repositories of both generations.

| Repository | Description | Generation |
|---|---|---|
| [just-dna-lite](https://github.com/dna-seq/just-dna-lite) | Main platform: standalone genomic annotation | Gen II |
| [just-prs](https://github.com/dna-seq/just-prs) | PRS computation library/CLI/UI | Gen II |
| [just-dna-compiler](https://github.com/dna-seq/just-dna-compiler) | Annotation module schema (just-dna-format), manifest/integrity contract, and reference compiler | Gen II |
| [just-dna-registry](https://github.com/dna-seq/just-dna-registry) | Catalogue and versioned distribution of annotation modules | Gen II |
| [just-prs-mcp](https://github.com/dna-seq/just-prs-mcp) | MCP server exposing just-prs to Claude, Cursor, Codex, Antigravity, and other AI agents, with trait-panel graphics and interpretation prompts | Gen II |
| [prepare-annotations](https://github.com/dna-seq/prepare-annotations) | Pipelines converting annotation databases to Parquet | Gen II |
| [reflex-mui-datagrid](https://github.com/dna-seq/reflex-mui-datagrid) | Reflex wrapper for MUI DataGrid | Gen II |
| [just-biomarkers](https://github.com/dna-seq/just-biomarkers) | Methylation and other biomarker analysis tools | Gen II |
| [just-module-creator](https://github.com/dna-seq/just-module-creator) | Authoring plugin (MCP tools and skills) for drafting, checking, compiling, and publishing annotation modules inside AI coding assistants | Gen II |
| [dna-seq](https://github.com/dna-seq/dna-seq) | Original DNA-Seq pipeline | Gen I |
<!-- @/rev J18 -->
