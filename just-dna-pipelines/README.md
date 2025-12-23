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

This workspace exposes two CLI entry points related to this package:

- `uv run modules`: manage OakVar modules
- `uv run dagster-ui`: start Dagster for annotation and asset tracking

## VCF Annotation (via Dagster)

VCF annotation is handled via Dagster assets and jobs. To annotate VCF files:

1. Start Dagster: `uv run dagster-ui` (or `uv run start`)
2. Open `http://localhost:3005`
3. Materialize the relevant assets (e.g. `ensembl_annotations`, then `user_annotated_vcf` partitions).

See `docs/DAGSTER_GUIDE.md` for more details.

## Architecture

Just DNA Pipelines' architecture is built around three core concepts:
1. **Pipeline Functions**: Atomic, typed functions for specific genomic tasks.
2. **Workflow Definition**: Composable genomic workflows using Dagster or custom CLI runners.
3. **Runtime**: Environment-aware executor that manages parallelism and resources.

## Configuration

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
