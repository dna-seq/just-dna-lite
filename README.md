<div align="center">
  <img src="webui/assets/just_dna_seq.jpg" alt="just-dna-lite logo" width="200px">

# just-dna-lite
</div>

Personal genomics workflows (pipelines + UI) for turning VCFs into annotated Parquet outputs.

## Project Structure

This repository is a uv workspace with two member projects:

- `webui/`: Pure-Python [Reflex](https://reflex.dev/) Web UI.
- `just-dna-pipelines/`: Declarative [Dagster](https://dagster.io/) pipeline library and CLI.

Shared, repo-level folders live at the workspace root (e.g., `data/`, `docs/`, `logs/`, `notebooks/`).

### Why Dagster & Reflex?

We selected these tools to prioritize **data lineage** and **developer velocity**:

- **[Dagster](https://dagster.io/) for Pipelines**: Unlike traditional task-based orchestrators, Dagster treats data as the first-class citizen. It uses **Software-Defined Assets (SDA)** to model what data should exist rather than just how to run code. This gives us automatic lineage (knowing exactly which reference version produced a user result), built-in storage management, and easy engine swapping (e.g., Polars vs DuckDB).
  - *See [docs/DAGSTER_GUIDE.md](docs/DAGSTER_GUIDE.md) for a deep dive into our pipeline philosophy.*
- **[Reflex](https://reflex.dev/) for Web UI**: We chose Reflex because it allows building a modern, reactive full-stack web application in **pure Python**. This eliminates the need for separate frontend/backend stacks (like React/FastAPI) and allows us to share models and logic directly between the UI and the pipelines. It perfectly fits our ["Chunky & Tactile"](docs/DESIGN.md) design system.

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
- CLI: `uv run pipelines --help`

If you add files under `data/input/users/`, you can register them as Dagster partitions:

```bash
uv run pipelines sync-vcf-partitions
```

## Features

### Pipeline Features
- VCF ingestion from `data/input/users/{user}/` and annotation outputs under `data/output/users/{user}/`.
- Two join engines: Polars (default) and DuckDB (streaming, low memory).
- Reference data assets cached under a per-user cache directory (see `JUST_DNA_PIPELINES_CACHE_DIR`).
- Resource tracking (time / CPU / peak memory) surfaced in Dagster materializations.

### Web UI Features
- **File Management**: Upload VCF files with drag-and-drop, view file library with status badges.
- **Sample Metadata**: 
  - Species selection using Latin scientific names (Homo sapiens, Mus musculus, Rattus norvegicus, etc.)
  - Reference genome selection (GRCh38, T2T-CHM13v2.0, GRCh37 for humans)
  - Editable fields: Subject ID, Study Name, Notes
  - **Custom Fields**: Add any metadata field with custom name (e.g., Batch ID, Sequencer, Library Prep)
- **Run-Centric Layout**: View outputs, run history, and start new analyses in a unified interface.
- **Real-time Monitoring**: Live status updates and log streaming from Dagster jobs.
- **Output Downloads**: Download annotated parquet files directly from the browser.

## Configuration

### Module Sources

Annotation module sources are configured in **`modules.yaml`** at the project root. Modules are auto-discovered from any fsspec-compatible URL (HuggingFace, GitHub, HTTP, S3, etc.). To add a new source, edit the `sources:` list in the YAML. Display metadata (titles, icons, colors) can be overridden under `module_metadata:`.

The loader also checks `just-dna-pipelines/src/just_dna_pipelines/modules.yaml` as a fallback, but the root-level file takes priority.

### Environment Variables

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
- [Performance & Engines](docs/DAGSTER_GUIDE.md#performance--engine-optimization)
- [Hugging Face Integration](docs/DAGSTER_GUIDE.md#hugging-face-integration--authentication)
- [Annotation Modules](docs/HF_MODULES.md)
- [Web UI Status](docs/WEBUI_STATUS.md) - Current implementation status and architecture
- [Design System](docs/DESIGN.md) - Fomantic UI patterns and component styling
- [Agent Guidelines](AGENTS.md)

## Connected Repositories

- [dna-seq/prepare-annotations](https://github.com/dna-seq/prepare-annotations): Upstream repository used to download, process, and upload the Ensembl and module annotations used by this project.

## License

MIT License - see [LICENSE](LICENSE) file for details.
