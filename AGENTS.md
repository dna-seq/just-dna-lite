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

## Coding Standards

- **Avoid nested try-catch**: Minimize try-catch blocks, especially inside eliot actions.
- **Type hints**: Mandatory for all Python code.
- **Pathlib**: Always use pathlib when dealing with file pathes.
- **No relative imports**: Always use absolute imports.
- **Prefer Polars**: Use Polars over Pandas for all data processing tasks. Prefer lazyframes with active use of polars expressions as they are fast
- **Memory Efficiency**: Use lazy APIs (`scan_parquet`) and streaming (`sink_parquet`) where possible. 
- **Memory efficient joins**: Be careful about polars joins, as often joins materialize whole dataframes, try to pre-filter when possible before joining.
- **Data Pattern**: Use `data/input`, `data/interim`, `data/output` for local data management.
- **Eliot Logging**: Use `with start_action(...) as action` for structured logging.
- **Typer CLI**: Use Typer for all command-line interfaces.
- **Pydantic 2**: Use Pydantic version 2 for data classes and validation.
- **No placeholders**: Do not put placeholders like /my/custom/path/ in real code
- **No redundant legacy API support**: we are a new rapidly developing project, if you refactor the code do not create additional functions just to support legacy ways of doing stuff.
- **no uv pip install**: avoid using stupid uv pip install. We have uv sync to resolve dependencies and uv add to add new ones



## Documentation

- **Use docs folder**: when you generate markdowns and they are not readme or agents.md please put them to docs folder

## Testing

- **Integration tests**: Use real requests and data. Do not mock unless dealing with multi-gigabyte files.
- **Verbosity**: Run `pytest` with `-vvv` by default.
- **Assertions**: Include explanatory messages in all assertion statements.

## Dependency Management

- **Use `uv`**: Always manage dependencies via `uv sync` and `uv add`.
- **No hardcoded versions**: Do not put versions in `__init__.py`; use `project.toml`.
