# Agent Guidelines

This document outlines the coding standards and practices for **just-dna-lite**.

## Repository layout (uv workspace)

This repo is a **uv workspace** with two member projects:

- `just-dna-pipelines/`: pipeline/CLI library (Python package: `just-dna-pipelines`)
- `webui/`: Reflex Web UI (Python package: `webui`)

Shared, repo-level folders live at the workspace root (e.g. `data/`, `docs/`, `logs/`, `notebooks/`).

### Running the App

The recommended way to start the application is from the repo root:

- `uv run start` - Starts the Reflex Web UI development server.

## Coding Standards

- **Avoid nested try-catch**: try catch often just hide errors, put them only when errors is what we consider unavoidable in the use-case
- **Type hints**: Mandatory for all Python code.
- **Pathlib**: Always use for all file paths.
- **No relative imports**: Always use absolute imports.
- **Polars**: Prefer over Pandas. Use lazyframes (`scan_parquet`) and streaming (`sink_parquet`) for efficiency.
- **Memory efficient joins**: Pre-filter dataframes before joining to avoid materialization.
- **Data Pattern**: Use `data/input`, `data/interim`, `data/output`.
- **Typer CLI**: Mandatory for all CLI tools.
- **Pydantic 2**: Mandatory for data classes.
- **No placeholders**: Never use `/my/custom/path/` in code.
- **No legacy support**: Refactor aggressively; do not keep old API functions.
- **Dependency Management**: Use `uv sync` and `uv add`. NEVER use `uv pip install`.
- **Versions**: Do not hardcode versions in `__init__.py`; use `project.toml`.

## Testing & Docs

- **Integration tests**: Use real requests/data. Mock only for multi-GB files.
- **Verbosity**: Run `pytest -vvv`.
- **Docs**: Put all new markdown files (except README/AGENTS) in `docs/`.

## Dagster Pipeline

For any Dagster-related changes, see **[docs/DAGSTER_MULTI_USER.md](docs/DAGSTER_MULTI_USER.md)**.

Key patterns:
- **Auto-configuration**: Dagster config is automatically created on first run. See **[docs/CLEAN_SETUP.md](docs/CLEAN_SETUP.md)**.
- **Reference assets** (Ensembl, ClinVar, etc.) use `annotation_cache_io_manager` → stored in `~/.cache/just-dna-pipelines/`
- **User assets** use `user_asset_io_manager` → stored in `data/output/users/{user_name}/`
- **Lazy materialization**: Assets check if cache exists before downloading
- **Start UI**: `uv run dagster` or `uv run dagster dev -f just-dna-pipelines/src/just_dna_pipelines/annotation/definitions.py -p 3005`

## Design System

For UI/frontend changes, see **[docs/DESIGN.md](docs/DESIGN.md)**.

Key principles:
- **"Chunky & Tactile"** aesthetic with high affordance
- **DaisyUI + Tailwind** component classes
- **Oversized icons** (min 2rem), **large buttons** (`btn-lg`), **generous spacing** (`gap-8`)
- **Semantic colors**: `bg-success` (benign), `bg-error` (pathogenic), `bg-info` (VUS)
