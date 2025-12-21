<div align="center">
  <img src="webui/assets/just_dna_seq.jpg" alt="just-dna-lite logo" width="200px">

# just-dna-lite: Personalized Genomics Platform 🧬
</div>

A unified personalized genomics platform for downloading, converting, processing, and annotating genomic data. It provides both a powerful engine for genomic pipelines and a modern user interface.

## Project Structure

This is a **uv workspace** containing two primary components:

- **`webui/`**: A modern Reflex-based web interface for managing genomic data. For details, see [webui/README.md](webui/README.md).
- **`genobear/`**: The core pipeline and CLI library that powers the platform's genomic processing capabilities. For details, see [genobear/README.md](genobear/README.md).

Shared, repo-level folders live at the workspace root (e.g., `data/`, `docs/`, `logs/`, `notebooks/`).

## Getting Started

### Prerequisites

Ensure you have [uv](https://github.com/astral-sh/uv) installed.

### Quick Start

To start the Web UI:

```bash
uv run start
```

For more details on managing the UI, see [webui/README.md](webui/README.md).

### Pipeline CLI

The core engine `genobear` provides CLI tools for data preparation and annotation. For details, see [genobear/README.md](genobear/README.md).

## Features

- **Integrated Platform**: A unified interface for both CLI-based pipelines and a modern Web UI.
- **High-Performance Engine**: Powered by `genobear` for fast VCF processing using Polars and lazy-join annotations.
- **Automated Data Management**: Streamlined downloading and conversion of major genomic databases (Ensembl, ClinVar, etc.).
- **Job Tracking & Visualization**: Monitor long-running tasks and visualize results through the Web UI.
- **Cloud Ready**: Built-in support for HuggingFace Hub integration.

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
