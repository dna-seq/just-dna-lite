# **Just-DNA-Lite: a Local-First, Open-Source Platform for Personal Genome Annotation and Polygenic Risk Scoring**

> **Draft v0.2 (Paper 1 of 2).** This is the platform paper: the local-first platform and the compute engines it runs (annotation pipeline, the just-prs computation library, the no-code module format, the web UI, `just-dna-format`, and `just-dna-marketplace`). The *agentic layer* — exposing and orchestrating these operations for AI assistants, plus AI-assisted module creation and its quantitative evaluation — is described in the companion preprint *just-dna-agents: an Agentic Toolkit for Evidence-Grounded Personal Genomics Research* (Usanov et al., 2026, in preparation; DOI to be assigned). See `docs/manuscript/v0.2/manuscript-strategy-v0.2.md`.

**Authors:** Kulaga Anton^1,2,4^, Usanov Nikolay^3,4^, Borysova Olga^4^, Karmazin Alexey^4^, Koval Maria^4^, Fedorova Alina^4^, Pushkareva Malvina^4^, Evfratov Sergey^4^, Ryangguk Kim^8^, Zaharia Livia^3^, Fuellen Georg^1,\*^, Tacutu Robi^2,9,\*^

**Affiliations:**

1. Institute for Biostatistics and Informatics in Medicine and Ageing Research, Rostock University Medical Center, Rostock, Germany
2. Institute of Biochemistry of the Romanian Academy
3. HEALES (Healthy Life Extension Society)
4. SecvADN SRL
5. CellFabrik SRL
6. MitoSpace
7. M. Glushkov Institute of Cybernetics of National Academy of Sciences of Ukraine
8. Oak Bioinformatics, LLC
9. Romanian Bioinformatics Cluster (CRB), Târgu Mureș, Romania

The contribution of these authors is considered to be equal. \* Co-supervising authors.

---

## **Abstract**

Whole genome sequencing has become affordable for individuals, yet the tools available for annotating personal genomic data remain either proprietary, opaque in their methodology, or too complex for researchers without bioinformatics training. Commercial platforms present curated subsets of findings without disclosing all considered variants and their selection logic, and centralized storage of genetic data carries serious privacy risks, as demonstrated by the 2023 breach at 23andMe that exposed the genetic ancestry information of approximately 6.9 million users (Doffman, 2023; Alteri et al., 2024).

We present Just-DNA-Lite, an open-source, local-first modular platform for personal genome analysis designed for research and educational use, combining two capabilities: variant annotation against curated variant-trait databases, and polygenic risk score (PRS) computation. Just-DNA-Lite runs entirely on a personal computer, processes a whole-genome VCF in under 40 seconds — a 172-fold speedup over the earlier OakVar-based Generation I system on the same hardware — and produces annotated reports across user-selected modules. The platform is built on a no-code module ecosystem in which annotation modules consist of a declarative YAML specification and variant table (CSV or Parquet), formalized in the standalone `just-dna-format` schema/manifest contract and distributed through fsspec-compatible sources or a dedicated `just-dna-marketplace` catalog API, enabling community-contributed annotations without custom code.

The platform ships with expert-curated default modules covering several trait domains (longevity-associated variants, cardiovascular-related variants, lipid metabolism, VO2 max, and athletic performance) as worked examples of the module format, alongside over 5,000 polygenic risk scores from the PGS Catalog computed via the just-prs library with Pearson r = 0.9999 concordance against PLINK2 and a 5.7–12.3× speedup. Beyond the graphical application, the same validated engines are additionally exposed to AI assistants for interactive and programmatic use — and can be extended with new AI-created annotation modules — through the companion just-dna-agents toolkit (the `dna-agents` package), described in a separate preprint; this paper treats those agentic capabilities as an availability pointer and focuses on the local platform, its engines, and their benchmarks.

All data stays local. The platform is open-source (AGPL v3), GDPR-friendly by design, and aligned with the principle that individuals have the right to explore their own genomic data. The platform does not perform clinical interpretation or generate diagnoses and is not intended for medical decision-making; an optional, user-initiated AI explanation of results is general and non-prescriptive, not clinical advice. It is a research and educational tool, not a clinical pipeline.

## **1. Introduction**

Whole genome sequencing costs have fallen from billions of dollars to under a thousand since the completion of the Human Genome Project in 2003, and several companies now offer direct-to-consumer sequencing services (Whitley et al., 2020). Yet the gap between sequencing accessibility and variant annotation remains wide. Researchers and individuals receive raw variant files (VCFs) containing millions of variants but lack accessible tools to annotate them against published databases without specialized bioinformatics expertise.

Existing solutions occupy two extremes. Commercial platforms such as DNA Complete (formerly Nebula Genomics) and Dante Labs provide curated reports, but the curation is opaque: users cannot verify which polymorphisms contributed to a score, whether the methodology is appropriate for their ancestry, or how findings were weighted. At the other end, research-grade tools like PLINK, ANNOVAR, and VEP are powerful but demand command-line proficiency and significant setup effort. There is no open-source platform that combines comprehensive variant annotation with ease of use, transparency, and extensibility.

The genetics of longevity illustrates the need for extensible annotation tools. The field is rapidly evolving: traditional twin studies placed the heritability of lifespan at 20–25%, but a recent study in *Science* by Shenhar et al. (2025) estimates the intrinsic heritability at approximately 50% after correcting for extrinsic mortality confounders. GWAS studies have identified candidate loci including APOE and FOXO3 as consistently associated with longevity across populations (Broer et al., 2014; Caruso et al., 2022), and the catalogue of longevity-associated variants continues to grow. Databases such as LongevityMap within the Human Ageing Genomic Resources (HAGR) (Tacutu et al., 2017) have compiled thousands of variant-trait associations, but no existing tool makes it straightforward to annotate a personal VCF against these databases transparently and extensibly. This exemplifies a broader pattern: variant-trait associations are published faster than any single curation team can integrate them, motivating a platform where new annotation modules can be created rapidly.

A platform for personal genome annotation must therefore solve three problems simultaneously: it must be easy to use (web interface, no bioinformatics training), transparent in its methods (open-source, auditable scoring), and extensible (researchers should be able to add new annotation modules as the literature evolves, without writing code). Furthermore, privacy is a first-order concern: genomic data is among the most sensitive personal information, and uploading it to third-party servers introduces risks that many individuals and regulatory frameworks (such as the GDPR and the European Health Data Space) seek to avoid.

To address these needs, we developed Just-DNA-Lite, a ground-up rewrite of the earlier Just-DNA-Seq platform. The original system (Generation I) was built on top of OakVar, a Python-based variant analysis framework, and is described in a separate preprint (Kulaga et al., 2024, arXiv:2403.19087). While functional, it suffered from long processing times (approximately two hours per whole-genome VCF), a complex dependency chain, and a module system that required Python programming to extend. Just-DNA-Lite (Generation II) replaces the OakVar dependency entirely with a standalone pipeline based on Dagster, Polars, and DuckDB, reducing annotation time to under 40 seconds on the same hardware — a 172-fold speedup — and turns modules into declarative data artifacts governed by a separate format contract (`just-dna-format`) and discoverable through local, fsspec, and marketplace sources. Generation I is described in detail in Supplementary File S1.

**Scope.** This paper presents a software platform and its computational methods. Just-DNA-Lite annotates user variants against published variant-trait databases and computes standard polygenic risk scores; the associations it surfaces are those already reported in the underlying databases and literature (LongevityMap, PGS Catalog, Ensembl Variation, etc.). Its contribution is computational — speed, structural privacy, and an extensible no-code module ecosystem — not the discovery or clinical validation of gene-trait associations. The platform's engines are additionally reachable by AI assistants, and can be extended with AI-created modules, through a companion agentic toolkit; that agentic layer, its multi-agent module-creation engine, and its quantitative evaluation are the subject of a companion preprint (Usanov et al., 2026, *just-dna-agents*), and are referenced here only as availability. It is a research and educational tool, not a clinical pipeline; we discuss its intended use and limitations in Section 6.

## **2. Platform Architecture**

The requirements set out above — ease of use, transparency, extensibility, and privacy — translate into a small set of design principles that recur throughout the system. *Privacy is structural, not promised*: everything runs on the user's own machine, so the genome never leaves it. *Modules are data, not code*, so the annotation catalogue can grow with the literature without anyone writing software. *The platform is built to run on a laptop*, prioritizing memory efficiency over raw throughput, because the typical user is an individual or a small lab rather than a compute cluster. *The whole stack is open and auditable* (AGPL v3), so anyone can inspect every line that touches genomic data. And the platform is designed to *meet users where they already work* — primarily through a graphical web application, and, for those who work inside AI assistants, through the companion just-dna-agents toolkit (described separately).

Concretely, Just-DNA-Lite is structured as a uv workspace containing two Python packages: just-dna-pipelines (Dagster assets, VCF processing, annotation logic, and CLI tools) and webui (a Reflex-based web interface). The platform requires Python 3.13+ and is installed and run with a single command (`uv run serve`). All computation happens locally; no data leaves the user's machine.

### **2.1 Annotation Pipeline**

The core annotation pipeline is built on Dagster with Software-Defined Assets, providing automatic data lineage tracking and resource monitoring (CPU usage, peak memory, and duration for every pipeline step). A typical annotation workflow proceeds as follows:

1. **VCF ingestion.** The user provides a VCF or VCF.gz file through the web interface. This is the annotated variant file users typically already have — supplied by a sequencing provider, downloaded from a public genome repository, or produced by their own bioinformatic pipeline; Just-DNA-Lite starts from this VCF and does not itself perform sequencing, alignment, or variant calling. The file is read using polars-bio, a Polars-native VCF reader.
2. **Normalization.** The raw VCF undergoes quality filtering (configurable via `modules.yaml`): only variants passing specified FILTER values (by default, PASS and ".") are retained, with optional minimum depth (DP ≥ 10) and quality (QUAL ≥ 20) thresholds. Chromosome prefixes ("chr") are stripped for consistency with annotation databases. The normalized data is written as a Parquet file, which serves as the shared input for all downstream annotation.
3. **Module annotation.** For each selected annotation module, the pipeline performs a streaming join between the normalized VCF Parquet and the module's precomputed weights Parquet. Joins are performed by rsID (default) or genomic position. Polars streaming joins keep peak memory low; for datasets too large to fit in memory, DuckDB handles out-of-core joins with configurable memory limits.
4. **Ensembl annotation (optional).** When enabled, the pipeline joins the normalized VCF against the Ensembl Variation database (cached locally as chromosome-level Parquet files downloaded from HuggingFace via fsspec), providing clinical significance labels, consequence types, and cross-references for each variant.
5. **Report generation.** Annotated results are written as Parquet files and rendered as downloadable PDF/HTML reports. All outputs are available for downstream analysis in Python, R, or any tool that reads Apache Arrow.

The annotation data for reference databases and modules is prepared upstream by the prepare-annotations pipeline (github.com/dna-seq/prepare-annotations), which converts source databases into columnar Parquet format optimized for fast lookups.

### **2.2 Modular Plugin System**

The central design principle of Just-DNA-Lite is that annotation modules are data, not code. The module contract is factored into the standalone `just-dna-format` project, which defines the authored specification, compiled manifest, integrity digests, identity/versioning rules, and reference compiler. A module consists of a directory containing two core authored files:

- `module_spec.yaml` — metadata including the module name, version, title, description, icon, colour, and genome build.
- `variants.csv` — a table of variants with columns for rsID, genotype (slash-separated, alphabetically sorted), effect weight (negative for risk, positive for protective), state (risk/protective/neutral), a brief conclusion, and gene symbol.

The variant table may be authored as CSV for convenience, but the platform also accepts it as Parquet, and on registration a CSV is compiled to columnar artifacts (`weights.parquet`, annotations, studies, and a manifest) for fast loading and integrity verification. Optional files include `studies.csv` (linking variants to PubMed IDs), `MODULE.md` (documentation), and `logo.png` (thumbnail). No Python code is required from the module author; the annotation engine loads modules via Polars LazyFrames and executes no code from the module.

Module discovery is automatic. The platform reads a list of sources from `modules.yaml` at the project root. Each source can be any fsspec-compatible URL: HuggingFace datasets (`hf://datasets/org/repo`), GitHub repositories (`github://org/repo`), HTTP/HTTPS servers, cloud storage (`s3://`, `gcs://`), or local filesystem paths. The loader auto-detects whether a source is a single module or a collection, and display metadata can be overridden in `modules.yaml` without modifying the module itself. New modules added to any configured source are discovered on the next startup or manual refresh. By default, curated modules are published to the just-dna-seq organization on HuggingFace, though Zenodo and other online sources are equally supported. For a larger community catalogue, the dedicated `just-dna-marketplace` service provides a REST API for browsing, searching, publishing, yanking, downloading, and integrity-verifying annotation module versions; its SQLite catalog is a rebuildable projection of each version's manifest rather than the source of truth.

### **2.3 Web Interface and Self-Exploration**

The web interface is built with Reflex, a Python framework that compiles to React; the entire UI is written in Python, with no JavaScript required. The interface provides file management (upload VCFs, select modules, launch annotation), module selection (browse modules, toggle Ensembl annotation), a results preview (sortable, filterable data grid in the browser), report download (PDF/HTML per module), and self-exploration: even without selecting a specific module, users can browse their full variant table with sorting, filtering, and search, cross-referenced against Ensembl for clinical significance labels, consequence types, and known phenotype associations when Ensembl annotation is enabled. All data can be exported as Parquet for downstream analysis in Python, R, DuckDB, or any Arrow-compatible tool.

**Figure 1.** The Just-DNA-Lite web interface showing the annotation results view with module selection, variant data grid, and report download options.

### **2.4 Performance Characteristics**

Consistent with the "runs on a laptop" principle, Just-DNA-Lite prioritizes memory efficiency over raw throughput: peak RAM stays low enough for a personal computer, and warm-run annotation of a whole genome completes in tens of seconds. Detailed speed and memory benchmarks — including the comparison against the Generation I OakVar-based system — are presented in Section 5.1.

## **3. Default Module Set**

Just-DNA-Lite ships with a set of expert-curated annotation modules developed by geneticist Olga Borysova, illustrating the platform's module system across several trait domains. These modules represent the default set; the platform is designed so that users, researchers within the ROGEN consortium, and the broader community can easily add their own modules, either by hand or with AI assistance (Section 4). The modules annotate user variants against published variant-trait association databases; they do not perform clinical interpretation or generate diagnoses.

These default modules originate in the first generation of the platform, the OakVar-based Just-DNA-Seq (Kulaga et al., 2024). That system was built around longevity and longevity-associated traits, which is why the default set centres on that domain; for the second generation we ported most modules largely unchanged, to serve as worked examples of the no-code module format rather than as a definitive trait catalogue.

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

Unlike the Generation I approach, which used Monte Carlo sampling to estimate percentile distributions, just-prs uses precomputed percentile distributions derived from the 1000 Genomes Project phase 3 dataset, against five superpopulations (AFR, AMR, EAS, EUR, SAS). Users select the reference population closest to their ancestry, and the percentile reflects their position within that distribution.

The library provides three interchangeable computation engines: **DuckDB** (SQL-based, out-of-core scoring; 12.3× faster than PLINK2 at median), **Polars** (pure-Python LazyFrame joins; 5.7× faster than PLINK2), and **PLINK2** (the established reference tool, included for cross-validation). All three produce numerically equivalent results (Pearson r = 1.0 between DuckDB and Polars; r = 0.9999 between just-prs and PLINK2). Benchmarks are detailed in Section 5.2. In the web interface, users browse the PGS Catalog in a searchable grid, select scores, and click "Compute"; results show the score sum, matched-variant count, and percentile within the selected superpopulation.

**Figure 3. PRS results in Just-DNA-Lite (just-prs trait view).** For a selected trait, all associated PGS Catalog models are computed and shown together as a consensus distribution with the user's percentile against a 1000 Genomes reference population, alongside per-model variant match rates and quality tiers. Showing the models together — including where they disagree — is deliberate (see Section 6.3).

### **3.2.1 Access beyond the web interface**

just-prs is released as a standalone component so that it can also be used outside the graphical application — as a Python library, a command-line tool, or a lightweight standalone PRS web app. In addition, the same validated engine is exposed to AI assistants (and can be orchestrated together with annotation and other operations in a single conversation) through the companion just-dna-agents toolkit, which also renders explanatory charts and assembles structured, caveat-aware interpretation prompts for computed scores. That agentic access layer — its server, agent skills, orchestration, graphics, and LLM-interpretation prompts — is described in the companion preprint (Usanov et al., 2026, *just-dna-agents*) and is not detailed here; regardless of entry point, results are numerically identical because they are backed by the identical DuckDB/Polars scoring engine described above.

### **3.3 Additional Trait Annotation Modules**

The platform includes several additional modules that annotate variants against published GWAS and meta-analysis databases: **cardiovascular-associated variants** (SNPs selected on meta-study p-values and cross-population replication), **lipid metabolism** (same evidence-based inclusion criteria), and **VO2 max and athletic performance** (exercise genomics literature). All modules work by joining the user's VCF against curated variant-trait databases, adding annotation columns (weight, state, gene, conclusion) to matching variants. They do not calculate individual risk, generate diagnoses, or make clinical recommendations.

### **3.4 Growing the Module Ecosystem**

The default modules represent the initial curated set; the platform's value proposition lies in its extensibility. The no-code module format (Section 2.2) lowers the barrier to contribution to the point where any researcher with domain knowledge can create a new module by preparing a CSV/Parquet table of variants and a short YAML metadata file — no programming involved. The `just-dna-format` contract makes these artifacts portable across the web application, compiler, marketplace, and downstream clients, while `just-dna-marketplace` adds a catalog layer for publishing, searching, downloading, and verifying module versions. Alternatively, the AI-assisted module creator (Section 4) can generate a complete module from a research paper in minutes; the generated output is loaded into an editing slot where the user reviews, corrects, and refines it before registration. In all cases, modules can be edited, versioned, and shared through fsspec-compatible repositories or the marketplace API. Planned directions for ecosystem growth are discussed in Section 6.5.

## **4. AI-Assisted Module Creation (platform feature)**

Building annotation modules by hand is labour-intensive: it requires reading the primary literature, identifying relevant variants, looking up rsIDs and genomic positions, assigning effect weights based on study quality and replication, and formatting the output. Just-DNA-Lite integrates an AI-assisted module-creation capability directly in the web interface, so that the platform can grow its own annotation content: a user can create a new module from within the app, without external tooling. The user provides a free-text prompt in a chat interface and optionally attaches source documents; the system researches the variants against biomedical databases, drafts the module specification, and returns it for review.

The capability is offered in two modes — a fast single-agent mode suitable for a single source, and a research-team mode that coordinates several agents for broader coverage across multiple papers. Both modes emit the platform's standard, deterministic module artifacts (`module_spec.yaml`, `variants.csv`, `studies.csv`, `MODULE.md`, and a thumbnail), which are loaded into an editing slot in the UI where the user can review every file, make manual edits, iterate through follow-up messages, and then register the module with one click.

Importantly, generated modules enter the platform through exactly the same path as hand-authored ones: they are deterministic specification files that are checked by the module validator (schema compliance, genotype sorting, weight/state consistency, wild-type presence) and compiled to Parquet before they can be registered. Provenance is made explicit — each module's metadata carries a `curator` field distinguishing expert-curated from AI-generated content — so that AI-generated modules are surfaced to users as automated first drafts that benefit from expert review rather than as validated findings (see Section 6.1).

This paper deliberately treats AI-assisted creation as a platform feature and makes no claim here about its accuracy, its effect on hallucination, or its performance relative to a baseline. The underlying engine — its multi-agent architecture, the models used, the cross-model consensus mechanism, its access from external assistants (Claude Code, Cursor, Codex, Antigravity), and its quantitative evaluation on ground-truth fixtures — is described and benchmarked in the companion preprint (Usanov et al., 2026, *just-dna-agents*; DOI to be assigned).

**Figure 4.** The in-app AI Module Creator: the user attaches a research paper and describes the desired module; the generated module then appears in the editing slot with all files for review and one-click registration.

## **5. Benchmarking and Validation**

### **5.1 Annotation Speed**

We benchmarked Just-DNA-Lite against the Generation I OakVar-based system on the same hardware. The input was a single whole-genome VCF containing 6,138,868 variant records (4,729,824 SNPs and 1,414,226 indels), produced by DeepVariant v1.4.0 against GRCh38 at ~162× mean coverage. This is the co-author genome released publicly on Zenodo (record 18370498, CC0) — the same genome used for the PRS benchmark in Section 5.2 — so the benchmark is fully reproducible end-to-end; the benchmark scripts are provided in the repository, and the pipeline can equally be run on any standard whole-genome VCF.

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

The 172-fold speedup was achieved with memory-optimised settings on HDD storage, representing a conservative lower bound; SSD/NVMe storage and module-level parallelisation would yield further gains. Speed gains come from Polars streaming joins and Parquet column-pruned reads, and peak RAM stays under 750 MB for default modules on a whole genome.

### **5.2 PRS Computation**

We benchmarked the three computation engines in just-prs on 100 consecutive PGS Catalog IDs (PGS000006–PGS000106) scored against a personal whole-genome VCF (4,661,444 biallelic variants, GRCh38; Zenodo 18370498). The benchmark is fully reproducible via `uv run python just-prs/benchmarks/benchmark_engines.py`.

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

The near-zero difference between DuckDB and Polars confirms identical algorithm implementation. The absolute difference versus PLINK2 arises from variant-matching scope: PLINK2 requires exact 4-part chr:pos:ref:alt ID matching while just-prs uses position-based matching with allele-orientation detection, leading to 1–3 extra variants included or excluded per genome-wide score. The Pearson r = 0.9999 confirms that individual risk rankings are effectively identical. Memory use is dramatically lower for the just-prs engines (median heap < 1 MB per typical scoring call) than for PLINK2 (~590 MB floor from reloading genotype files per invocation); full memory and large-file runtime tables are given in Supplementary S3.

Across engines, roughly 50–54% of each scoring file's variants were matched in this single personal genome — expected rather than anomalous: the unmatched fraction is dominated by variants absent from (or not called in) this genome, together with indels, multiallelic sites, and strand/allele-orientation and build-coordinate differences. Because all engines ran on the same VCF, the match rate is comparable across them and does not affect the concordance comparison. This benchmark directly addresses the standard concern regarding validation: it provides a quantitative concordance metric (r = 0.9999) against the established reference tool, demonstrating that just-prs produces effectively identical risk rankings while running 5.7–12.3× faster with far lower memory requirements.

Annotation-module accuracy is inherited from the underlying data sources: expert-curated modules draw from peer-reviewed databases (LongevityMap, PGS Catalog, Ensembl Variation); the platform annotates user variants against these existing databases rather than discovering or validating associations. The reliability of AI-generated modules and their systematic evaluation are treated in the companion preprint.

## **6. Discussion**

### **6.1 Limitations of Variant Annotation**

Variant annotation tools surface statistical associations from published literature, and several inherent limitations apply. Heritability is a population-level statistic, not individual determinism, and estimates change with environment, study design, and cohort. A polygenic risk score is a linear weighted sum that reflects where an individual falls in a reference population's distribution; real biology is not linear, and gene-gene and gene-environment interactions, feedback loops, developmental windows, and compensatory mechanisms are not captured. Most PGS Catalog scoring files were derived from predominantly European cohorts, so associations may not transfer to other ancestries (Section 6.4). Most variants surfaced are statistical associations from GWAS, not established causal mechanisms; many GWAS hits are tagging SNPs, and effect sizes typically shrink in replication.

AI-generated modules carry additional uncertainty: they are automated drafts produced by language models reading published papers, and they will contain mistakes; users should treat them as lower confidence than expert-curated modules and review the underlying evidence. Just-DNA-Lite is a research tool, not a clinical pipeline. Raw VCFs contain false positives, and automated annotations have inherent error rates. The platform joins the user's variants against published databases and computes polygenic risk scores, adding contextual information from those sources; it does not interpret results in a clinical context.

### **6.2 Data Privacy and GDPR Compliance**

Just-DNA-Lite processes all data locally: the VCF never leaves the user's machine, annotation databases are cached locally after initial download, and results are stored on the local filesystem. No genomic data is transmitted to external servers during normal operation. This architecture is GDPR-friendly by design — the data controller is the user themselves, and no third-party data processing occurs. Commercial platforms, by contrast, require users to upload their genomic data to company servers, creating privacy risks that are difficult to mitigate retroactively. The AGPL v3 licence allows users and institutions to audit every line of code that touches their data.

### **6.3 Platform Philosophy: Transparency and the Right to Read Your Own Genome**

Just-DNA-Lite is built on a simple conviction: people have the right to read and explore their own genomic data, and researchers have the right to work with public genomes without a gatekeeper's permission. The GDPR's right of access (Article 15) already entitles individuals to obtain a copy of their personal data, and the emerging European Health Data Space is designed to give people access to and control over their own health information. A tool that runs locally and shows you everything in your own genome is, in this light, an instrument of an existing right.

We take seriously the opposing concern — that genomic information can be misinterpreted, cause anxiety, or provide false reassurance, and that some direct-to-consumer claims have outrun their evidence (Tandy-Connor et al., 2018; Manrai et al., 2016; Annas & Elias, 2014). Our design attacks that risk directly rather than by withholding information: for traits where the published evidence is contradictory, we show every available model alongside quality tiers, discrimination metrics, variant match-rates, ancestry context, and a consensus view marking where models agree and where they scatter, and we pair results with educational material on misinterpretation. We are also skeptical that prohibition is an effective remedy (Green & Farahany, 2014; Bloss et al., 2011), noting that outright bans tend to push activity offshore rather than prevent it (STAT News, 2019) while openness has historically widened access (Association for Molecular Pathology v. Myriad Genetics, 2013). Education is part of the project: we maintain a tutorial channel and have run hands-on workshops introducing non-specialists to local, privacy-preserving genome exploration.

*(This section is intentionally shortened relative to the single-manuscript draft; the fuller argument is preserved for the Discussion or a supplement, per the strategy review's recommendation to make the ethical argument shorter and less confrontational in the main text.)*

### **6.4 Limitations**

**Population stratification.** The 1000 Genomes-based percentile distributions provide population-specific reference points (AFR, AMR, EAS, EUR, SAS), but most modules and PGS scoring files derive from predominantly European cohorts; transferability to non-European populations is a known limitation of the source data, not specific to this platform. **Ancestry selection.** Automatic ancestry inference from the VCF is not yet implemented; users select the closest reference superpopulation. **Input format.** The platform supports WGS and WES VCFs; GRCh38 is the primary build, with GRCh37/hg19 handled via liftover; consumer microarray data is supported experimentally (with far lower coverage, which the platform surfaces to users); T2T references are not yet supported. **Module quality variation.** Expert-curated modules inherit the limitations of their source databases; AI-generated modules have additional variability and require user review.

### **6.5 Future Directions**

Several extensions are underway or planned: GRCh37/hg19 liftover (added), experimental consumer-microarray support, and eventual T2T reference support. Multi-species support (companion-animal genomics) is a compelling direction. We are also considering methylation and transcriptomic ageing clocks, among the analyses users most frequently request. Within the ROGEN consortium, work is underway on population-calibrated polygenic risk scores and application to a 5,000-individual Romanian genomic cohort. Beyond technical extensions, the larger experiment is social: we encourage the community to build and share modules, and by design do not vet what others publish. This openness has an unavoidable consequence — community- and AI-generated modules will contain mistakes — which the platform mitigates not by gatekeeping but by making provenance visible (the `curator` field, the explicit expert-versus-AI distinction) so that trust can be calibrated. How best to curate and validate a large, decentralized ecosystem of genomic annotations is not yet known; Just-DNA-Lite is offered both as a usable platform and as a testbed for that question.

## **7. Conclusion**

Just-DNA-Lite delivers on a simple core value: people should be able to explore their own genomes — transparently and privately. It is a self-contained local web application that annotates a whole genome and computes polygenic risk scores in tens of seconds, built on a no-code module system in which anyone can turn a YAML file and a variant table into an annotation module, so the annotation catalogue can grow with the literature. These capabilities rest on a foundation that matches the project's philosophy: all computation is local and the code is open-source (AGPL v3), so privacy is structural rather than promised; the platform shows the full picture rather than a curated verdict; and the performance holds up, with whole-genome annotation in tens of seconds and PRS computation validated at Pearson r = 0.9999 against PLINK2 while running several times faster and using a fraction of the memory. The same engines are additionally reachable by AI assistants — and extensible with AI-created modules — through the companion just-dna-agents toolkit described separately. Just-DNA-Lite is a research and educational tool, not a clinical pipeline, and it is explicit about that boundary.

## **Contribution Statements**

- **Kulaga Anton** — co-founded the project, bioinformatic pipeline development, Just-DNA-Lite architecture (Dagster/Polars/DuckDB pipeline, uv workspace), just-prs library development and benchmarking, web UI development, team management, article writing
- **Usanov Nikolay** — co-founded the project, Just-DNA-Lite platform development, integration of the AI module-creation capability into the web interface, fundraising *(the agentic toolkit is the subject of the companion preprint)*
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

This work was partially supported by the ROGEN project (*Dezvoltarea cercetării genomice în România*), project code 324809, funded by the European Regional Development Fund and the Romanian national budget through the Health Programme (PS/272/PS_P5/OP1/RSO1.1/PS_P5_RSO1.1_A9), coordinated by the "Carol Davila" University of Medicine and Pharmacy, Bucharest (implementation December 2024 – December 2029). A.K. and R.T. received funding through this project. *[TODO: confirm ROGEN mandatory acknowledgment text.]*

## **Code Availability**

**GitHub Organization:** https://github.com/dna-seq

**Table 7.** Software repositories.

| Repository | Description | Generation |
|---|---|---|
| [just-dna-lite](https://github.com/dna-seq/just-dna-lite) | Main platform — standalone genomic annotation | Gen II |
| [just-prs](https://github.com/dna-seq/just-prs) | PRS computation library/CLI/UI | Gen II |
| [just-dna-format](https://github.com/dna-seq/just-dna-format) | Annotation module schema, manifest/integrity contract, and reference compiler | Gen II |
| [just-dna-marketplace](https://github.com/dna-seq/just-dna-marketplace) | Catalog, publish, download, and integrity-verification REST API for annotation modules | Gen II |
| [just-prs-mcp](https://github.com/dna-seq/just-prs-mcp) | MCP server exposing just-prs to Claude, Cursor, Codex, Antigravity, and other AI agents | Gen II |
| [prepare-annotations](https://github.com/dna-seq/prepare-annotations) | Pipelines converting annotation databases to Parquet | Gen II |
| [reflex-mui-datagrid](https://github.com/dna-seq/reflex-mui-datagrid) | Reflex wrapper for MUI DataGrid | Gen II |
| [just-biomarkers](https://github.com/dna-seq/just-biomarkers) | Methylation and other biomarker analysis tools | Gen II |
| [dna-agents](https://github.com/dna-seq/dna-agents) | just-dna-agents: agentic toolkit exposing/orchestrating the platform's engines and creating annotation modules (see companion preprint) | Gen II |
| [dna-seq](https://github.com/dna-seq/dna-seq) | Original DNA-Seq pipeline | Gen I |

Annotation modules and reference datasets are published to the just-dna-seq organization on HuggingFace (annotators, ensembl_variations, clinvar, pgs-catalog, prs-percentiles), which serves as the default source for module auto-discovery. Other fsspec-compatible sources are equally supported.

## **Competing Interests**

- Ryangguk Kim is a co-founder of OakVar Inc.
- Anton Kulaga, Olga Borysova, Maria Koval, Nikolay Usanov, and Alex Karmazin are co-founders of SecvADN SRL, which provides additional services on top of the open-source modules.

## **Bibliography**

*(Carried over from the combined manuscript; to be finalized with 2022–2026 additions.)*

Alteri, E., et al. (2024). The 23andMe data breach. *European Journal of Human Genetics*, 32(11), 1317–1320.
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
