# **Just-DNA-Lite: a Local-First, Open-Source Platform for Personal Genome Annotation and Polygenic Risk Scoring**

> **Draft v0.3 (Paper 1 of 2).** This is the platform paper: the local-first platform and the compute engines it runs — the annotation pipeline, the just-prs computation library **and its `just-prs-mcp` access layer**, the no-code module format, the web UI, `just-dna-format`, and the module registry. The boundary with the companion paper is *consuming* versus *authoring*: this paper covers how a compiled module or a published score is discovered, computed against a genome, and reported, including from an AI assistant that calls these operations as typed tools. The companion paper covers the other direction — an assistant *producing* new annotation content: the authoring plugin, the enrichment and compilation toolchain, and how modules are published and versioned. It is *Creating and Sharing Genomic Annotation Modules with AI: The Just-DNA Ecosystem* (in review at EASRP 2026; `paper2-just-module-creator.md`). See `docs/manuscript/v0.3/manuscript-strategy-v0.3.md`.

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
By 2025, manufacturers listed the sequencing consumables for a human genome at US$80 to US$200 (Illumina, 2023; Ultima Genomics, 2025), and studies that count the full cost, including labour, equipment and analysis, put a genome at a few thousand dollars (Mordaunt et al., 2024; Ehman et al., 2025), against an estimated $500 million to $1 billion for the first one (NHGRI, 2021). Several companies now offer direct-to-consumer sequencing services (Whitley et al., 2020; O'Daniel et al., 2025).<!-- @/rev C3 --> Yet the gap between sequencing accessibility and variant annotation remains wide. Researchers and individuals receive raw variant files (VCFs) containing millions of variants <!-- @rev C4 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->but often lack accessible means to annotate them against published databases without specialized bioinformatics expertise, a learning curve that takes time away from the questions they set out to answer (Nelson et al., 2019; Chen et al., 2023; O'Daniel et al., 2025).<!-- @/rev C4 -->

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
Just-DNA-Lite ships with a set of expert-curated annotation modules, illustrating the platform's module system across several trait domains. These modules represent the default set. The platform is designed so that researchers from the scientific community (eg: bioinformaticians, geneticists, etc.) can easily add their own modules, either by hand or with AI assistance (Section 3.4). The modules annotate user variants against published variant-trait association databases; they do not perform clinical interpretation or generate diagnoses.
<!-- @/rev R11 -->

<!-- @rev R12 rounds=1 by=robi:2026-09-25 -->
The default modules originate in the first generation of the platform, the OakVar-based Just-DNA-Seq (Kulaga et al., 2024). That system was built around longevity and longevity-associated traits, which is why the default set centres on that domain; for the second generation, most modules were ported, largely unchanged, to serve as worked examples of the no-code module format rather than as a definitive trait catalogue.
<!-- @/rev R12 -->

**Table 1.** Default annotation modules shipped with Just-DNA-Lite.

| Module | Description | Curator |
|---|---|---|
| Longevity Map | Variant-trait associations from the LongevityMap database | Expert (Olga Borysova) |
| Coronary Artery Disease | Variants associated with cardiovascular traits from GWAS literature | Expert |
| Lipid Metabolism | Variants associated with lipid metabolism traits | Expert |
| VO2 Max | Variants associated with oxygen uptake capacity from exercise genomics literature | Expert |
| Superhuman / Athletic Performance | Variants associated with elite athletic performance traits | Expert |
| Longevity Variants 2026 | Variants from recent familial longevity and multimorbidity GWAS studies | AI-generated |

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

The platform includes several additional modules that annotate variants against published GWAS and meta-analysis databases: **cardiovascular-associated variants** (SNPs selected on meta-study p-values and cross-population replication), **lipid metabolism** (same evidence-based inclusion criteria), and **VO2 max and athletic performance** (exercise genomics literature). All modules work by joining the user's VCF against curated variant-trait databases, adding annotation columns (weight, state, gene, conclusion) to matching variants. They do not calculate individual risk, generate diagnoses, or make clinical recommendations.

### **3.4 Growing the Module Ecosystem**

The default set is extensible through the same module contract used by the application and registry. Researchers can prepare variant tables and metadata, compile them into portable artifacts, and distribute versions through configured repositories or `just-dna-registry`. Users can then select the resulting modules without modifying the annotation engine. This separates content updates from application releases, while leaving evidence review and scientific curation with module contributors. <!-- @rev D1 rounds=1 by=claude:2026-10-10 -->Rather than embedding its own assistant, the platform exposes its operations to the AI assistants authors already use. Modules can be drafted in such an assistant through the just-module-creator plugin (github.com/dna-seq/just-module-creator); the result is the same artifact, validated and compiled the same way, and its curator field marks it as AI-generated. Through the platform's MCP server, the assistant can then install the draft, annotate a genome with it and inspect the result (Section 3.2.1).<!-- @/rev D1 -->

## **4. Benchmarking and Validation**

### **4.1 Annotation Speed**

<!-- @rev R15 rounds=1 by=robi:2026-09-25 -->
We benchmarked Just-DNA-Lite against the Generation I OakVar-based system on the same hardware. The input was a single whole-genome VCF containing 6,138,868 variant records (4,729,824 SNPs and 1,414,226 indels), produced by DeepVariant v1.4.0 against GRCh38 at ~162× mean coverage. This is the genome of one of the co-authors, released publicly on Zenodo (record 18370498, CC0) — the same genome used for the PRS benchmark in Section 4.2 — so the benchmark is fully reproducible end-to-end; the benchmark scripts are provided in the repository, and the pipeline can equally be run on any standard whole-genome VCF.
<!-- @/rev R15 -->

**Table 2.** Annotation speed benchmark: Just-DNA-Lite vs OakVar (Generation I).

| Run type | *n* | Mean ± SEM (s) | SD (s) | Speedup vs OakVar |
|---|---|---|---|---|
| **Just-DNA-Lite (normal)** | 11 | **38.9 ± 3.3** | 10.9 | **~172×** |
| Just-DNA-Lite (cold start) | 3 | 203.3 ± 9.0 | 15.5 | ~33× |
| Just-DNA-Lite (GVCF) | 1 | 868 | — | ~7.7× |
| OakVar (Gen I) | 3 | 6705 ± 583 | ~1010 | 1× (ref.) |

**Table 3.** Resource consumption during Just-DNA-Lite annotation.

| Run type | Duration (s) | Peak RAM (MB) | Avg CPU (%) |
|---|---|---|---|
| GVCF (longest) | 868 | 748 | 182 |
| Cold start | 216 | 644 | 278 |
| Normal (average) | 39 | 400–600 | — |

**Table 4.** Benchmark hardware and input specifications.

| Parameter | Value |
|---|---|
| CPU | Intel Xeon E5-2667 v4 @ 3.20 GHz (8C/16T) |
| RAM | 128 GB |
| Storage | HDD JBOD array |
| OS | Linux 6.8.0 |
| Input VCF | 6,138,868 records (4.7M SNPs, 1.4M indels); public genome, Zenodo 18370498 (CC0) |
| Variant caller | DeepVariant v1.4.0 |
| Genome build | GRCh38 |
| Coverage | ~162× mean |

The approximately 172-fold speedup is the ratio of the reported mean Generation I runtime to the mean warm-run Just-DNA-Lite runtime. It applies to these configurations and this input, rather than to OakVar generally. The benchmark used HDD storage and a workstation with 128 GB RAM; it does not directly establish performance on a laptop or the gains from SSD storage. Reported peak memory remained below 750 MB for the runs in Table 3. Streaming joins and column-pruned reads are architectural differences, but this comparison does not isolate their individual contributions to runtime.

### **4.2 PRS Computation**

We benchmarked just-prs's DuckDB and Polars engines against the external tool PLINK2 on 100 PGS Catalog scores using a personal whole-genome VCF (4,661,444 biallelic variants, GRCh38; Zenodo 18370498). The benchmark script is `benchmarks/benchmark_engines.py` in the just-prs repository. Each observation represents a different scoring model applied to the same individual.

**Table 5.** Runtime comparison of PRS computation engines (seconds per PGS ID). "Excl. large" excludes 7 PGS IDs with ≥ 1M variants.

| Engine | *N* scored | Median (all) | Mean (all) | Median (excl. large) | Speedup vs PLINK2 |
|---|---|---|---|---|---|
| **DuckDB** | 100 | **0.049** | 0.394 | 0.048 | **12.3×** |
| **Polars** | 100 | 0.106 | 0.466 | 0.105 | 5.7× |
| PLINK2 | 96^a^ | 0.603 | 0.703 | 0.603 | 1× (ref.) |

^a^ PLINK2 failed on 4 genome-wide PGS IDs (6.6–6.9M variants) due to 4-part ID matching constraints; just-prs engines scored all 100.

**Table 6.** Score concordance between engines.

| Engine pair | *N* PGS | Pearson *r* | Max \|Δ score\| |
|---|---|---|---|
| DuckDB ↔ Polars | 100 | **1.000000** | < 1.1 × 10⁻¹³ |
| DuckDB ↔ PLINK2 | 96 | 0.999859 | 21.4 |
| Polars ↔ PLINK2 | 96 | 0.999859 | 21.4 |

DuckDB and Polars agreed to within 1.1 × 10⁻¹³ on this input. Scores closely agreed with the external PLINK2 comparator (Pearson r = 0.999859; maximum absolute score difference 21.4). The workflows differ in variant identification: just-prs resolves scoring variants by genomic position with allele-orientation handling, whereas the PLINK2 benchmark used exact chr:pos:ref:alt identifiers. This allows just-prs to match variants that the benchmark's exact-identifier route misses and explains why score differences can remain despite the same weighted-sum calculation. The comparison concerns this PLINK2 configuration, not a general limitation of the tool. Correlation here measures agreement across scores for one genome; it does not measure rankings across individuals. Supplementary S3 distinguishes per-call Python heap measurements from PLINK2 process memory.

Reported variant-match rates in this benchmark were approximately 50 to 54%. These values describe the benchmark configuration, rather than the maximum coverage supported by just-prs. Reference-homozygote restoration can recover eligible absent loci for many scores, and the array workflow supports LD-proxy estimation (Section 3.2); their coverage gains are not quantified by this engine comparison. Missingness and allele matching also affect comparison with reference distributions. The reported speedups are ratios of engine-level median runtimes, with 100 completed scores for DuckDB and Polars and 96 for PLINK2.

<!-- @rev R16 rounds=1 by=robi:2026-09-25 -->
Annotation reliability depends on both the source evidence and its representation in the module. Generally, published associations do not by themselves validate data extraction, allele orientation, genotype matching, or report wording. The present benchmarks measure runtime and score agreement; they do not constitute a systematic accuracy evaluation of the annotation modules.
<!-- @/rev R16 -->

## **5. Discussion**

### **5.1 Limitations of Variant Annotation**

<!-- @rev R17 rounds=1 by=robi:2026-09-25 -->
Variant annotation tools surface statistical associations from published literature, and several inherent limitations apply. Heritability is a population-level statistic, not individual determinism, and estimates change with environment, study design, and cohort. A polygenic risk score is a linear weighted sum that reflects where an individual is situated in a reference population's distribution. However, biology is not linear, and gene-gene and gene-environment interactions, feedback loops, developmental windows, and compensatory mechanisms are not always captured by a polygenic score. Moreover, most PGS Catalog scoring files were derived from predominantly European cohorts, so associations may not transfer to other ancestries (Section 5.4). Additionally, most variants surfaced are statistical associations from GWAS, not established causal mechanisms; many GWAS hits are tagging SNPs, and effect sizes typically shrink in replication.
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
**Population stratification.** The 1000 Genomes-based percentile distributions provide population-specific reference points (AFR, AMR, EAS, EUR, SAS), but most modules and PGS scoring files derive from predominantly European cohorts; transferability to non-European populations is a known limitation of the source data, not specific to this platform. **Ancestry selection.** Automatic ancestry inference from the VCF is not yet implemented; users have to select the closest reference superpopulation. **Input format.** The platform supports WGS and WES VCFs; GRCh38 is the primary build, with GRCh37/hg19 handled via liftover; consumer microarray data is supported experimentally (with far lower coverage, which the platform surfaces to users); T2T references are not yet supported. **Module quality variation.** Expert-curated modules inherit the limitations of their source databases; AI-generated modules have additional variability and require user review. <!-- @rev C2d rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->**Benchmark scope.** Runtime and score agreement were measured on one public genome. They describe computational performance; they do not establish predictive accuracy or agreement in rankings across individuals.<!-- @/rev C2d -->
<!-- @/rev R22 -->

### **5.5 Future Directions**

<!-- @rev R23 rounds=1 by=robi:2026-09-25 -->
Several extensions are underway or planned: GRCh37/hg19 liftover (added, but still under testing), experimental consumer-microarray support, and T2T reference support. Multi-species support (companion-animal genomics) is a compelling direction. We are also considering methylation and transcriptomic ageing clocks, among the analyses users most frequently request. Within the ROGEN consortium, population-calibrated polygenic risk scores are planned for a Romanian genomic cohort of approximately 5,000 individuals; that cohort is currently being sequenced, and none of the work reported here uses cohort data. Beyond technical extensions, the larger experiment is social: we encourage the community to build and share modules, and by design do not vet what others publish. This openness has an unavoidable consequence — community- and AI-generated modules will contain mistakes — which the platform mitigates not by gatekeeping but by making provenance visible (the `curator` field, the explicit expert-versus-AI distinction) so that trust can be calibrated. How best to curate and validate a large, decentralized ecosystem of genomic annotations is not yet known; Just-DNA-Lite is offered both as a usable platform and as a testbed for that question.
<!-- @/rev R23 -->

## **6. Conclusion**

<!-- @rev R24 rounds=1 by=robi:2026-09-25 -->
Just-DNA-Lite integrates local variant annotation, polygenic scoring, and inspectable reports with a portable annotation-module contract and versioned content discovery. Typed MCP tools make the PRS engine available to AI assistants. Albeit tested only on one public genome, the reported benchmarks show faster annotation than the earlier Just-DNA-Seq configuration and close numerical agreement between scoring engines. Evaluation across individuals, reference populations, and matched-variant sets remains necessary to establish the broader reliability of these workflows. The platform provides infrastructure for research and education, without establishing clinical validity for the findings it reports.
<!-- @/rev R24 -->

## **Contribution Statements**

- **Kulaga Anton** — co-founded the project, bioinformatic pipeline development, Just-DNA-Lite architecture (Dagster/Polars/DuckDB pipeline, uv workspace), just-prs library development and benchmarking, web UI development, team management, article writing
<!-- @rev R25 rounds=1 by=robi:2026-09-25 -->
- **Usanov Nikolay** — co-founded the project, Just-DNA-Lite platform development, <!-- @rev D3 rounds=2 by=claude:2026-10-10,usanov:2026-10-10 -->the module system, the population ancestry discriminator (detection and algorithm), AI-assisted module authoring<!-- @/rev D3 -->, fundraising
<!-- @/rev R25 -->
- **Borysova Olga** — modules and report content (longevity variants, cardiovascular traits, lipid metabolism, VO2 max, athletic performance, pharmacogenomics), LongevityMap database curation and expansion, pathway categorization, report structure, data collection and analysis
- **Karmazin Alexey** — lead architect of the Generation I report system, OakVar report modules and preparation utilities, PRS modules
- **Maria Koval** — report modules, report template, trait annotation modules (thrombophilia, cardiovascular)
- **Fedorova Alina** — bioinformatic utilities, scientific literature exploration
- **Pushkareva Malvina** — software development and testing
- **Evfratov Sergey** — pharmacogenomics (drug) module development
- **Ryangguk Kim** — created and maintained OakVar, extended it for the Generation I platform
- **Zaharia Livia** — beta-testing, provided her whole genome for testing and benchmarking
- **Fuellen Georg** — co-supervision, valuable suggestions and comments
- **Tacutu Robi** — bioinformatics and ageing research advising, LongevityMap database

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
Whitley, K. V., et al. (2020). Direct-to-consumer genetic testing: an updated systematic review. *European Journal of Human Genetics*, 28(8), 1063–1074.

## **Supplementary Material**

**S1. Generation I: OakVar-Based Just-DNA-Seq Platform.** Architecture, pipeline, module types, and repository table for the OakVar-based Generation I system (see combined-manuscript supplement for full detail).

**S2. Generation I vs Generation II Speed Comparison.** Individual OakVar benchmark runs (2023-02-17: 5,651 s; 2023-02-19: 6,803 s; 2023-05-07: 7,662 s; mean 6,705 ± 583 s). The 172× speedup is attributable to Polars streaming joins against Parquet, elimination of the multi-step OakVar annotator pipeline, and DuckDB for large joins with predicate pushdown and column pruning.

**S3. Runtime and Memory on Large PRS Scoring Files.** Per-call memory (DuckDB/Polars median heap 0.2 MB; PLINK2 ~590 MB) and runtimes for the 7 genome-wide PGS IDs (1.7–6.9M variants); PLINK2 failed on the four largest due to 4-part ID matching constraints.
