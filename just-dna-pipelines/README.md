# Just DNA Pipelines

Just DNA Pipelines is a Python library used by `just-dna-lite` for downloading reference data and running annotation pipelines.

## Features

- Downloads and manages reference datasets (Ensembl, ClinVar, ...)
- VCF -> Parquet conversion and annotation (Polars; optional DuckDB streaming)
- Dagster assets with resource tracking metadata
- Hugging Face downloads for reference caches (e.g. Ensembl Parquet shards)

## Installation

Just DNA Pipelines is part of the `just-dna-lite` workspace. To set it up for development:

```bash
git clone git@github.com:dna-seq/just-dna-lite.git
cd just-dna-lite
uv sync
```

## CLI Usage

This workspace exposes a CLI entry point related to this package:

- `uv run dagster-ui`: start Dagster for annotation and asset tracking

## VCF Annotation (via Dagster)

We use **Dagster** as our orchestration engine because it treats data assets as first-class citizens. Unlike traditional task-based orchestrators (like Prefect or Airflow), Dagster focuses on **Software-Defined Assets (SDA)**—functions that declare what data they produce and what they depend on.

### Key Dagster Concepts used here:

- **Software-Defined Assets (SDA)**: Our pipelines (e.g., `ensembl_annotations`, `user_annotated_vcf`) are modeled as assets. This provides automatic lineage (knowing exactly which reference version produced a user result) and makes the state of your data products explicit and inspectable.
- **Dynamic Partitions**: We use partitions to handle multi-user/multi-sample workflows. This allows us to track, materialize, and delete data for one user (e.g., `anton/sample1`) without touching others.
- **IO Managers**: Our assets don't hardcode file paths. IO managers enforce storage contracts, handling where Parquet and VCF files live on disk based on our configuration.

To run the pipelines:
1. Start Dagster: `uv run dagster-ui` (or `uv run start`)
2. Open `http://localhost:3005`
3. Materialize the relevant assets (e.g. `ensembl_annotations`, then `user_annotated_vcf` partitions).

For a complete breakdown of our pipeline philosophy, see **[docs/DAGSTER_GUIDE.md](../docs/DAGSTER_GUIDE.md)**.

## Architecture

Just DNA Pipelines' architecture is built around three core concepts:
1. **Pipeline Functions**: Atomic, typed functions for specific genomic tasks.
2. **Workflow Definition**: Composable genomic workflows using Dagster or custom CLI runners.
3. **Runtime**: Environment-aware executor that manages parallelism and resources.

## Configuration

### Module Sources

Annotation module sources are configured in `src/just_dna_pipelines/modules.yaml`. Modules are auto-discovered from configured sources (HuggingFace, GitHub, HTTP, S3, or any fsspec URL). See `src/just_dna_pipelines/module_config.py` for the Pydantic models and loader.

### Environment Variables

Configure Just DNA Pipelines using environment variables:

- `JUST_DNA_PIPELINES_CACHE_DIR`: base cache directory (reference data)
- `JUST_DNA_PIPELINES_OUTPUT_DIR`: base output directory (user results)
- `JUST_DNA_PIPELINES_INPUT_DIR`: base input directory (user VCFs)
- `JUST_DNA_PIPELINES_DOWNLOAD_WORKERS`: parallel download workers
- `JUST_DNA_PIPELINES_PARQUET_WORKERS`: parquet workers
- `JUST_DNA_PIPELINES_WORKERS`: general workers

## Testing

Run the test suite using `pytest`:
```bash
uv run pytest
```

Note: Some tests require large downloads and are skipped by default. Run them with `uv run pytest -m large_download`.
