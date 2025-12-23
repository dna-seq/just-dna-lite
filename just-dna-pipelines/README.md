# Just DNA Pipelines 🧬

Just DNA Pipelines is a powerful Python library and CLI for managing genomic databases and running high-performance annotation pipelines. It serves as the engine for the `just-dna-lite` personalized genomics platform.

## Features

- **Automated Database Management**: Download and manage Ensembl, ClinVar, dbSNP, and gnomAD.
- **High-Performance Processing**: Powered by Polars for fast VCF to Parquet conversion and lazy-join based annotation.
- **Composable Pipelines**: Define and execute complex genomic workflows with built-in resource tracking.
- **Granular Parallelism**: Separate controls for download workers and processing workers.
- **HuggingFace Hub Support**: Tools for uploading processed genomic datasets.

## Installation

Just DNA Pipelines is part of the `just-dna-lite` workspace. To set it up for development:

```bash
git clone git@github.com:dna-seq/just-dna-lite.git
cd just-dna-lite
uv sync
```

## CLI Usage

Just DNA Pipelines provides several entry points for common tasks:

- `uv run prepare`: Download and convert genomic databases.
- `uv run modules`: Manage genomic database modules.
- `uv run dagster`: Start the Dagster UI for VCF annotation and asset tracking.

Example:
```bash
uv run prepare download-clinvar --dest-dir ./data
```

## VCF Annotation (via Dagster)

VCF annotation is handled via Dagster assets and jobs. To annotate VCF files:

1. Start Dagster: `uv run start` (or `uv run dagster`)
2. Navigate to `http://localhost:3005`
3. Launch the `annotate_vcf_job` with appropriate configuration.

See `docs/ANNOTATION.md` for more details.

## Architecture

Just DNA Pipelines' architecture is built around three core concepts:
1. **Pipeline Functions**: Atomic, typed functions for specific genomic tasks.
2. **Workflow Definition**: Composable genomic workflows using Dagster or custom CLI runners.
3. **Runtime**: Environment-aware executor that manages parallelism and resources.

## Configuration

Configure Just DNA Pipelines using environment variables:

- `JUST_DNA_PIPELINES_FOLDER`: Base directory for cache and data.
- `JUST_DNA_PIPELINES_DOWNLOAD_WORKERS`: Number of parallel downloads.
- `JUST_DNA_PIPELINES_PARQUET_WORKERS`: Number of parallel parquet operations.
- `JUST_DNA_PIPELINES_WORKERS`: Number of general processing workers.

## Testing

Run the test suite using `pytest`:
```bash
uv run pytest
```

Note: Some tests require large downloads and are skipped by default. Run them with `uv run pytest -m large_download`.
