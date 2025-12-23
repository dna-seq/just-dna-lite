# Just DNA Pipelines Annotation Pipeline

## Overview

The Just DNA Pipelines annotation pipeline allows you to annotate VCF files with reference genomic data from Ensembl variations. The pipeline is built using **Dagster** for efficient parallel processing and lazy evaluation with Polars.

## Key Features

- **Automatic cache management**: Downloads reference data from HuggingFace Hub only when needed
- **Lazy evaluation**: Uses Polars LazyFrames for memory-efficient processing
- **Parallel annotation**: Processes multiple chromosomes in parallel
- **Asset-based orchestration**: Built on **Dagster** for clear data lineage, asset tracking, and resource monitoring.

## Installation

```bash
uv sync
```

## Running Annotation

Annotation is handled via the Dagster UI or CLI.

### 1. Start Dagster

```bash
# Start the full stack (recommended)
uv run start

# Or start only Dagster
uv run dagster
```

Navigate to `http://localhost:3005` to view the asset graph.

### 2. Annotate a VCF

To annotate a VCF file:

1. Go to the **Assets** or **Jobs** tab in Dagster.
2. Select `annotate_vcf_job`.
3. Provide the configuration in the **Launchpad**:
   - `vcf_path`: Path to your input VCF file.
   - `user_name`: Your identifier.
   - `sample_name`: Sample technical identifier.
4. Click **Launch Run**.

The pipeline will:
1. Check if `ensembl_variations` cache exists.
2. Download reference data if not cached.
3. Parse the VCF to identify chromosomes.
4. Perform lazy joins with reference data.
5. Save the annotated result to `data/output/users/{user_name}/{sample_name}/`.

## Architecture

The annotation pipeline is built on modern Dagster assets and ops:

### 1. Ensembl Annotations Dagster (`definitions.py`)
- **Assets**: Represent persistent data products (HF Repo, Local Cache, Annotated VCF)
- **IO Managers**: Handle storage of reference data in cache and user data in output folders
- **Resource Tracking**: Monitors CPU and memory usage during materialization
- **Lazy Materialization**: Skips download if cache already exists

### 2. Multi-User Support
- Uses dynamic partitions to track annotations per-user
- Organizes output in `data/output/users/{user_name}/`

## Cache Structure

The reference data is organized by variant type. By default, data is cached at:
- Linux: `~/.cache/just-dna-pipelines/ensembl_variations/splitted_variants/`
- macOS: `~/Library/Caches/just-dna-pipelines/ensembl_variations/splitted_variants/`
- Windows: `%LOCALAPPDATA%\just-dna-pipelines\Cache\ensembl_variations\splitted_variants\`

## Join Strategy

The annotation pipeline uses a **left join** strategy to preserve all variants from the input VCF:

```python
join_columns = ["chrom", "start", "ref", "alt"]
```

## Environment Variables

- `DAGSTER_HOME`: Dagster internal storage (default: `data/interim/dagster/`)
- `JUST_DNA_PIPELINES_CACHE_DIR`: Override the base cache directory
- `JUST_DNA_PIPELINES_OUTPUT_DIR`: Custom output location
- `HF_TOKEN`: HuggingFace API token for accessing datasets
