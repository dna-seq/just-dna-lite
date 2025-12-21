# just-dna-lite: Personalized Genomics Platform 🧬

A unified personalized genomics platform for downloading, converting, processing, and annotating genomic data. It provides both a powerful engine for genomic pipelines and a modern user interface.

## Project Structure

This is a **uv workspace** containing two primary components:

- **`webui/`**: A modern Reflex-based web interface for managing genomic data, running jobs, and visualizing analysis.
- **`genobear/`**: The core pipeline and CLI library that powers the platform's genomic processing capabilities. For more details on the library, its Python API, and its CLI, see [genobear/README.md](genobear/README.md).

Shared, repo-level folders live at the workspace root (e.g., `data/`, `docs/`, `logs/`, `notebooks/`).

## Getting Started

### Prerequisites

Ensure you have [uv](https://github.com/astral-sh/uv) installed.

### Running the Web UI

To start the development server for the web interface:

```bash
uv run start
```

### Using the CLI

The platform's processing engine, `genobear`, provides several CLI tools for data preparation and annotation. See [genobear/README.md](genobear/README.md#cli-usage) for more detailed CLI documentation.

```bash
cd genobear
uv run prepare --help    # Data preparation pipelines (download/convert)
uv run annotate --help   # VCF annotation pipelines
```

## Features

- **Personalized Analysis**: Web UI for individual genomic file analysis and tracking.
- **Download genomic databases**: Automated retrieval of Ensembl, ClinVar, dbSNP, gnomAD.
- **Convert VCF to Parquet**: Efficient columnar storage using Polars for high-performance processing.
- **Annotate VCF files**: Fast, lazy-join based annotation with reference datasets.
- **Job Tracking**: Integrated UI for monitoring long-running genomic processing tasks.
- **Parallel processing**: Multi-threaded downloads and data processing with granular controls.
- **HuggingFace integration**: Seamlessly upload processed datasets to the Hub.

## Configuration

The platform uses environment variables for configuration. Create a `.env` file in your project root:

```bash
export GENOBEAR_FOLDER="~/genobear"                  # Base folder for all cache/data
export GENOBEAR_DOWNLOAD_WORKERS="8"                 # Number of parallel download workers
export GENOBEAR_PARQUET_WORKERS="4"                  # Number of workers for parquet operations
export GENOBEAR_WORKERS="4"                          # Number of workers for general processing
```

## Development

### Setup
```bash
git clone git@github.com:dna-seq/just-dna-lite.git
cd just-dna-lite
uv sync
```

### Testing
```bash
# Run all tests
uv run pytest

# Run only library tests
uv run pytest genobear/tests/
```

## Documentation

- [Data Preparation Guide](docs/UPLOAD_HF.md)
- [VCF Annotation Guide](docs/ANNOTATION.md)
- [Agent Guidelines](AGENTS.md)

## License

MIT License - see LICENSE file for details.
