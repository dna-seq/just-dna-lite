# GenoBear 🐻

GenoBear is a powerful Python library and CLI for managing genomic databases and running high-performance annotation pipelines. It serves as the engine for the `just-dna-lite` personalized genomics platform.

## Features

- **Automated Database Management**: Download and manage Ensembl, ClinVar, dbSNP, and gnomAD.
- **High-Performance Processing**: Powered by Polars for fast VCF to Parquet conversion and lazy-join based annotation.
- **Composable Pipelines**: Uses **Prefect 3.x** to define and execute complex genomic workflows with built-in resource tracking.
- **Granular Parallelism**: Separate controls for download workers and processing workers.
- **HuggingFace Hub Support**: Tools for uploading processed genomic datasets.

## Installation

GenoBear is part of the `just-dna-lite` workspace. To set it up for development:

```bash
git clone git@github.com:dna-seq/just-dna-lite.git
cd just-dna-lite
uv sync
```

## CLI Usage

GenoBear provides several entry points for common tasks:

- `uv run prepare`: Download and convert genomic databases.
- `uv run annotate`: Annotate VCF files with reference data.
- `uv run modules`: Manage genomic database modules.
- `uv run convert-vortex`: Convert data to Vortex format.

Example:
```bash
uv run prepare download-clinvar --dest-dir ./data
```

## Python API

### VCF Annotation
```python
from genobear import annotate_vcf
from pathlib import Path

results = annotate_vcf(
    vcf_path=Path("sample.vcf.gz"),
    output_path=Path("annotated.parquet"),
    variant_type="SNV"
)
```

### Data Preparation Pipelines
```python
import genobear as gb

# Download and split Ensembl chromosome files
results = gb.PreparationPipelines.download_ensembl(with_splitting=True)
```

## Architecture

GenoBear's architecture is built around three core concepts:
1. **Pipeline Functions**: Atomic, typed functions for specific genomic tasks.
2. **Pipelines**: Composable workflows using **Prefect 3.x**.
3. **Runtime**: Environment-aware executor that manages parallelism and resources.

## Configuration

Configure GenoBear using environment variables:

- `GENOBEAR_FOLDER`: Base directory for cache and data.
- `GENOBEAR_DOWNLOAD_WORKERS`: Number of parallel downloads.
- `GENOBEAR_PARQUET_WORKERS`: Number of parallel parquet operations.
- `GENOBEAR_WORKERS`: Number of general processing workers.

## Testing

Run the test suite using `pytest`:
```bash
uv run pytest
```

Note: Some tests require large downloads and are skipped by default. Run them with `uv run pytest -m large_download`.
