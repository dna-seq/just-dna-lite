# Agent Guidelines

This document outlines the coding standards and practices for **just-dna-lite**.

## Repository layout (uv workspace)

This repo is a **uv workspace** with two member projects:

- `genobear/`: pipeline/CLI library (Python package: `genobear`)
- `webui/`: Reflex Web UI (Python package: `webui`)

Shared, repo-level folders live at the workspace root (e.g. `data/`, `docs/`, `logs/`, `notebooks/`).

### Running the App

The recommended way to start the application is from the repo root:

- `uv run start` - Starts the Reflex Web UI development server.

### Pipeline and CLI Development

- `cd genobear`
- `uv run annotate ...` - Run annotation pipelines
- `uv run prepare ...` - Run data preparation pipelines
- `uv run pytest` - Run the test suite

## Coding Standards

- **Avoid nested try-catch**: Minimize try-catch blocks, especially inside eliot actions.
- **Type hints**: Mandatory for all Python code.
- **No relative imports**: Always use absolute imports.
- **Prefer Polars**: Use Polars over Pandas for all data processing tasks.
- **Memory Efficiency**: Use lazy APIs (`scan_parquet`) and streaming (`sink_parquet`) where possible.
- **Data Pattern**: Use `data/input`, `data/interim`, `data/output` for local data management.
- **Eliot Logging**: Use `with start_action(...) as action` for structured logging.
- **Typer CLI**: Use Typer for all command-line interfaces.
- **Pydantic 2**: Use Pydantic version 2 for data validation.

## Testing

- **Integration tests**: Use real requests and data. Do not mock unless dealing with multi-gigabyte files.
- **Verbosity**: Run `pytest` with `-vvv` by default.
- **Assertions**: Include explanatory messages in all assertion statements.

## Dependency Management

- **Use `uv`**: Always manage dependencies via `uv sync` and `uv add`.
- **No hardcoded versions**: Do not put versions in `__init__.py`; use `project.toml`.
