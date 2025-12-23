<div align="center">
  <img src="webui/assets/just_dna_seq.jpg" alt="just-dna-lite logo" width="200px">

# just-dna-lite
</div>

Personal genomics workflows (pipelines + UI) for turning VCFs into annotated Parquet outputs.

## Project Structure

This repository is a uv workspace with two member projects:

- `webui/`: Reflex Web UI. See `webui/README.md`.
- `just-dna-pipelines/`: pipeline library used by Dagster and CLI. See `just-dna-pipelines/README.md`.

Shared, repo-level folders live at the workspace root (e.g., `data/`, `docs/`, `logs/`, `notebooks/`).

## Getting Started

### Prerequisites

Ensure you have [uv](https://github.com/astral-sh/uv) installed.

### Quick Start
Install dependencies and start the full stack (Web UI + Dagster):

```bash
uv sync
uv run start
```

### Individual Components

You can also run components separately:

- Dagster UI: `uv run dagster-ui`
- Web UI: `uv run ui`
- CLI: `uv run just-dna-lite --help`

If you add files under `data/input/users/`, you can register them as Dagster partitions:

```bash
uv run just-dna-lite sync-vcf-partitions
```

## Features

- VCF ingestion from `data/input/users/{user}/` and annotation outputs under `data/output/users/{user}/`.
- Two join engines: Polars (default) and DuckDB (streaming, low memory).
- Reference data assets cached under a per-user cache directory (see `JUST_DNA_PIPELINES_CACHE_DIR`).
- Resource tracking (time / CPU / peak memory) surfaced in Dagster materializations.

## Configuration

The stack is configured via environment variables (a `.env` in the repo root is fine):

```bash
export JUST_DNA_PIPELINES_CACHE_DIR="$HOME/.cache/just-dna-pipelines"
export JUST_DNA_PIPELINES_OUTPUT_DIR="$PWD/data/output/users"
export JUST_DNA_PIPELINES_INPUT_DIR="$PWD/data/input/users"

export JUST_DNA_PIPELINES_DOWNLOAD_WORKERS="8"
export JUST_DNA_PIPELINES_PARQUET_WORKERS="4"
export JUST_DNA_PIPELINES_WORKERS="4"
```

## Development

### Setup

```bash
git clone git@github.com:dna-seq/just-dna-lite.git
cd just-dna-lite
uv sync
```

On first run, `uv run start` / `uv run dagster-ui` will create `data/interim/dagster/dagster.yaml` if it doesn't exist.

### Testing

```bash
# Run all tests
uv run pytest

# Run only library tests
uv run pytest just-dna-pipelines/tests/
```

## Documentation

- [Clean setup](docs/CLEAN_SETUP.md)
- [Dagster guide](docs/DAGSTER_GUIDE.md)
- [Performance notes](docs/PERFORMANCE.md)
- [Hugging Face datasets](docs/UPLOAD_HF.md)
- [Agent Guidelines](AGENTS.md)

## License

MIT License - see LICENSE file for details.
