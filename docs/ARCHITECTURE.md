# Architecture Overview: The Just-DNA Ecosystem

This document provides a high-level architectural overview of the `just-dna-lite` ecosystem and its interconnected components. If you are a contributor looking to understand how everything fits together or where to make specific changes, this guide will orient you.

## High-Level Architecture

The ecosystem is designed to take raw genomic data (VCF files), normalize it, and annotate it using curated biological knowledge and Polygenic Risk Scores (PRS). The architecture strictly separates **data preparation** (upstream) from **data consumption** (local client).

The core philosophy is **local-first privacy**: while reference datasets are downloaded from the cloud, the user's actual genome never leaves their computer. All computationally intensive joins and scoring happen locally using Polars and DuckDB.

```mermaid
graph TD
    subgraph "Upstream Data Preparation (Cloud / CI)"
        PA[prepare-annotations\nDagster Pipeline]
        PRSP[just-prs/prs-pipeline\nDagster Pipeline]
        
        RawEnsembl[(Raw Ensembl VCF)] --> PA
        RawOakVar[(OakVar Modules)] --> PA
        RawClinVar[(Raw ClinVar)] --> PA
        
        RawPGS[(Raw PGS Catalog FTP)] --> PRSP
        RefPanel[(1000G / HGDP Reference)] --> PRSP
    end

    subgraph "Hugging Face Hub (CDN)"
        HF_Mods[(just-dna-seq/annotators\nModule Parquets)]
        HF_PGS[(just-dna-seq/polygenic_risk_scores\nCleaned Metadata)]
        HF_Perc[(just-dna-seq/prs-percentiles\nReference Distributions)]
        
        PA -- Publishes --> HF_Mods
        PRSP -- Publishes --> HF_PGS
        PRSP -- Publishes --> HF_Perc
    end

    subgraph "External Knowledge Bases"
        BioContext[BioContext KB MCP\n(Ensembl, PubMed, UniProt)]
    end

    subgraph "Local Client (User's Machine)"
        JDL[just-dna-lite\nDagster + Web UI]
        JPRS[just-prs\nCore Library]
        PRSUI[prs-ui\nReflex Components]
        RMDG[reflex-mui-datagrid\nUI Components]
        
        AIAgent[AI Module Manager\nAgno Solo or Team]
        
        UserVCF[(User's Raw VCF)] --> JDL
        Research[(Research PDF / CSV)] --> AIAgent
        BioContext -. Tools .-> AIAgent
        
        AIAgent -- Compiles Custom Module --> JDL
        
        HF_Mods -- Downloads via fsspec --> JDL
        HF_PGS -- Downloads via fsspec --> JPRS
        HF_Perc -- Downloads via fsspec --> JPRS
        
        JPRS --> JDL
        PRSUI --> JDL
        RMDG --> JDL
        RMDG --> PRSUI
        
        JDL -- Polars / DuckDB Join --> Annotated[(Annotated Local Parquet)]
        JDL -- Generates --> Report[Interactive Web / PDF Report]
        PRSUI -- Computes --> PRSResults[PRS Scores & Percentiles]
        
        PRSResults -. Displayed In .-> JDL
    end
```

The ecosystem consists of four main projects:
1. **`just-dna-lite`**: The main user-facing application (pipelines + web UI) with AI module creation.
2. **`just-prs`**: The engine and UI components for Polygenic Risk Scores.
3. **`prepare-annotations`**: The upstream data preparation pipelines.
4. **`reflex-mui-datagrid`**: The core UI component library for rendering large genomic datasets.
5. **AI Module Manager (Agno Agents)**: An agentic pipeline that turns arbitrary input (articles, CSVs) into compiled modules.

---

## 1. `just-dna-lite` (The Main Application)
*Repository: `just-dna-lite`*

This is the primary workspace and the entry point for end users. It acts as the orchestrator that brings all other components together.

- **`just-dna-pipelines`**: A Dagster-based pipeline library. It handles VCF ingestion, normalization (stripping `chr` prefixes, quality filtering), and the actual annotation. It downloads reference datasets from Hugging Face and performs fast, memory-efficient joins (using Polars or DuckDB) against the user's normalized VCF. The final outputs of these pipelines are **annotated Parquet files** and rich, structured **HTML/PDF reports**.
- **`webui`**: A [Reflex](https://reflex.dev/)-based web frontend. It provides the interface for users to upload VCF files, select annotation modules, trigger Dagster jobs, and view the resulting **annotated data** and **visual reports**. It also houses the **AI Module Manager** (see [AI Module Creation](AI_MODULE_CREATION.md)), an agentic chat interface to create custom annotation modules from research papers.

**Role in Ecosystem:** 
- The central orchestrator that users interact with.
- Merges user data with curated knowledge to generate **interactive HTML/PDF reports** and **annotated Parquet files** for downstream analysis.

---

## 2. `just-prs` (Polygenic Risk Scores)
*Repository: `just-prs` (included as a workspace member in `just-dna-lite`)*

A dedicated suite for computing Polygenic Risk Scores from the [PGS Catalog](https://www.pgscatalog.org/). It acts as a pure Python alternative to tools like PLINK2.

- **`just_prs` (Core Library)**: Parses scoring files, normalizes variants, and computes scores using `pgenlib`, Polars, and NumPy.
- **`prs-ui`**: Reusable Reflex components (`PRSComputeStateMixin`, `prs_section()`) that provide the UI for browsing the PGS Catalog and computing scores. `just-dna-lite` embeds these components directly.
- **`prs-pipeline`**: A Dagster pipeline that computes reference distributions (percentiles) by scoring thousands of PGS IDs against population panels (like 1000 Genomes).

**Role in Ecosystem:**
- Provides the heavy-lifting logic for calculating Polygenic Risk Scores locally.
- Provides embeddable UI components for interacting with the PGS Catalog.
- Computes and surfaces **PRS results and population percentiles** alongside traditional annotations in the `just-dna-lite` UI.

---

## 3. `prepare-annotations` (Upstream Data Preparation)
*Repository: `prepare-annotations`*

This is a separate, upstream repository. It is a Dagster project dedicated to downloading massive, messy public datasets (Ensembl, ClinVar, OakVar modules) and converting them into clean, standardized Parquet files.

**The Unified Schema:**
It converts various knowledge sources into three standard tables:
- `annotations.parquet`: Variant-level facts (gene, phenotype).
- `studies.parquet`: Literature evidence (PubMed IDs, p-values).
- `weights.parquet`: Curator-defined scoring (genotype-specific weights).

**Role in Ecosystem:**
- Processes large, messy upstream biological datasets (Ensembl, ClinVar, OakVar) and standardizes them into Parquet format.
- Publishes these datasets to Hugging Face Hub for consumption by `just-dna-lite`.

---

## 4. `reflex-mui-datagrid` (UI Component Library)
*Repository: `reflex-mui-datagrid`*

A standalone Reflex wrapper for the MUI X DataGrid React component.

- It is heavily optimized for rendering genomic data.
- It natively supports Polars `LazyFrame` and integrates with `polars-bio` to render VCFs directly without fully loading them into memory.
- It provides server-side pagination, sorting, and filtering via the `LazyFrameGridMixin`.

**Role in Ecosystem:**
- Handles the UI challenge of visualizing multi-million row Parquet/VCF files smoothly in the browser.
- Used across the web apps (`just-dna-lite` and `prs-ui`) to display data grids.

---

## 5. AI Module Manager (Agentic Architecture)
*Location: `just-dna-pipelines/src/just_dna_pipelines/agents` within `just-dna-lite`*

See [AI Module Creation](AI_MODULE_CREATION.md) for full documentation of the DSL and agent prompts.

We actively encourage users to build their own AI-based annotation modules rather than relying strictly on upstream curators. The ecosystem includes an agentic architecture (powered by Agno) that transforms arbitrary unstructured inputs—such as a PDF research article, a CSV, or a natural language description—into a fully functional annotation module.

**The Workflow:**
1. **Agent(s):** A user submits a query and optionally attaches research files. The agent parses the text, extracts variants (resolving them via Ensembl if necessary), assigns weights/conclusions, and outputs a structured Domain Specific Language (DSL) consisting of `module_spec.yaml` and CSV files.
2. **Compiler:** A deterministic Python function takes the DSL, validates it against schemas, resolves missing positions, normalizes genotypes, and generates Parquet files (`weights.parquet`, `annotations.parquet`, `studies.parquet`).
3. **Registry:** The compiled Parquet files are written to disk and registered in the `modules.yaml` configuration, making the new custom module instantly available in the Dagster pipeline and web UI.

**Solo vs. Team Mode:**
- **Solo Mode:** A single agent (powered by Gemini) utilizes all tools (compile, validate, register) and queries the knowledge base to build the module from start to finish.
- **Team Mode (Research Team):** A Principal Investigator (PI) coordinates a multi-agent team.
  - **Researchers:** 1-3 agents (can be a mix of Gemini, Claude, and OpenAI depending on available API keys) that research specific variants using the knowledge base.
  - **Reviewer:** A quality-control agent equipped with Google Search to fact-check the drafted module.
  - **Principal Investigator (PI):** Coordinates the researchers and reviewer, handles the deterministic compilation tools, and produces the final module.

**BioContext KB MCP:**
The AI agents are supercharged by a hosted Model Context Protocol (MCP) server named `BioContext KB`. When building modules, researchers and solo agents query this MCP server to fetch real-time variant details from Ensembl, literature references from EuropePMC, pathway data from Reactome, and protein data from UniProt. This completely eliminates hallucinations regarding genetic positions and reference alleles.

**Role in Ecosystem:**
- Democratizes the creation of genetic interpretation modules.
- Allows rapid integration of newly published research without waiting for centralized curation.

---

## Data Flow & Hugging Face Assets

A critical part of the architecture is how data moves from the upstream preparation pipelines to the local client. To avoid distributing massive flat files or querying slow APIs at runtime, the ecosystem relies heavily on **Hugging Face Hub** as a CDN for Parquet files.

### Assets Produced by Pipelines

1. **Annotation Modules (`prepare-annotations`)**
   - The `prepare-annotations` pipelines publish standardized modules (e.g., `longevitymap`, `lipidmetabolism`, `coronary`) to the Hugging Face dataset: [just-dna-seq/annotators](https://huggingface.co/datasets/just-dna-seq/annotators).
   - Each module contains the unified `annotations.parquet`, `studies.parquet`, and `weights.parquet` files.

2. **PGS Catalog Metadata (`just-prs`)**
   - The `just-prs` cleanup pipeline processes raw EBI FTP data and publishes cleaned, snake_case Parquet files to: [just-dna-seq/polygenic_risk_scores](https://huggingface.co/datasets/just-dna-seq/polygenic_risk_scores).

3. **PRS Reference Percentiles (`just-prs`)**
   - The `prs-pipeline` scores the 1000 Genomes panel to generate statistical distributions for every PGS score, allowing the app to tell a user what percentile they fall into. These distributions are published to: [just-dna-seq/prs-percentiles](https://huggingface.co/datasets/just-dna-seq/prs-percentiles).

### Consumption in `just-dna-lite`

When a user runs an annotation job in `just-dna-lite`:
1. The local Dagster pipeline (`just-dna-pipelines`) discovers available modules via `modules.yaml`.
2. It uses `fsspec` (via `HfFileSystem`) or direct `hf://` Polars URIs to download the required Parquet files from Hugging Face.
3. These files are cached locally in the user's `~/.cache/just-dna-pipelines/` directory to avoid redundant downloads.
4. The pipeline performs a fast, local join between the downloaded weights/annotations and the user's normalized VCF.

---

## How to Update the System

The system is designed to gracefully handle updates at various levels—whether it's adding entirely new annotation modules, updating the Ensembl reference genome, or importing the latest Polygenic Risk Scores from the PGS Catalog.

### 1. Updating Annotation Modules

**What it means:** A module (e.g., `longevitymap`, `superhuman`) needs to be refreshed from a new underlying dataset, or a user wants to create a new one using the AI Module Manager.

**How to update:**
- **Pre-curated / Upstream Modules:**
  1. Open the `prepare-annotations` repository.
  2. If the data source has been updated (e.g., a new release from OakVar), run the corresponding Dagster pipeline (e.g., `uv run prepare longevitymap`).
  3. The pipeline will automatically fetch the new data, convert it to the unified Parquet schema (`annotations.parquet`, `studies.parquet`, `weights.parquet`), and publish the new versions to the Hugging Face `just-dna-seq/annotators` dataset.
  4. Local clients running `just-dna-lite` will automatically pull the updated Parquet files the next time they run an annotation job (provided their local cache is invalidated or updated).
- **Custom AI Modules:**
  1. In the `just-dna-lite` web UI, open the **Module Manager**.
  2. The user interacts with the AI agents to define a new module (or update an existing one) based on research papers or prompt inputs.
  3. Once the AI finalizes the module, the user clicks **Register Module**. This compiles the generated annotations into Parquet format and saves it locally.
  4. The module is immediately available for selection in the main annotation pipeline without needing to touch Hugging Face.

### 2. Updating Reference Annotations (e.g., Ensembl, ClinVar)

**What it means:** A new release of the Ensembl reference database (e.g., v111 -> v112) or ClinVar is available.

**How to update:**
1. Open the `prepare-annotations` repository.
2. In the `prepare-annotations` pipeline configuration, update the target release version (e.g., Ensembl release number or ClinVar FTP URL).
3. Run the Ensembl/ClinVar Dagster pipeline (`uv run dagster-ensembl`).
4. This pipeline is heavy. It will download the massive VCFs, split them by chromosome, parse them into Parquet format, and upload the partitioned dataset to Hugging Face.
5. In `just-dna-lite`, update the Ensembl reference pointer in the `modules.yaml` configuration to point to the newly published dataset version, so local pipelines know to fetch the latest reference chunks.

### 3. Updating Polygenic Risk Scores (PRS)

For deep details on PRS, see the `just-prs` documentation or the [Architecture Overview](ARCHITECTURE.md#3-just-prs-polygenic-risk-scores).

**What it means:** The PGS Catalog has published new scoring files, or the underlying reference panels (1000G, HGDP) used to calculate percentiles need to be refreshed.

**How to update:**
1. Open the `just-prs` repository.
2. To update the **PGS Catalog Metadata** (the searchable list of all scores and their performance metrics):
   - Run the cleanup pipeline: `prs catalog bulk clean-metadata`.
   - This downloads the latest bulk FTP data from EBI, cleans up genome builds and metric strings, and produces `scores.parquet`, `performance.parquet`, and `best_performance.parquet`.
   - Push the new metadata to Hugging Face: `prs push-hf`.
3. To update **Reference Percentiles** (the statistical distributions that determine a user's percentile for a given score):
   - Run the batch scoring pipeline using the CLI: `prs reference score-batch` (or launch the `prs-pipeline` Dagster UI).
   - The engine uses DuckDB and Polars to score all ~5,000+ PGS IDs against the reference panel (`.pgen` files).
   - This computes the mean, standard deviation, and full distribution metrics for every score across different ancestries, producing `{panel}_distributions.parquet`.
   - The resulting percentiles data is pushed to the `just-dna-seq/prs-percentiles` Hugging Face repository.
4. When users launch the `prs-ui` or run `just-dna-lite`, the `PRSCatalog` class will automatically pull the updated metadata and percentile Parquets from Hugging Face into their local cache.