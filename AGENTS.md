# Agent Guidelines

This document outlines the coding standards and practices for **just-dna-lite**.

---

## Repository Layout (uv workspace)

This repo is a **uv workspace** with two member projects:

- `just-dna-pipelines/`: pipeline/CLI library (Python package: `just-dna-pipelines`)
- `webui/`: Reflex Web UI (Python package: `webui`)

Shared, repo-level folders live at the workspace root (e.g. `data/`, `docs/`, `logs/`, `notebooks/`).

We sometimes (for example purposes) add prepare-annotations to the workspace. This folder is READ-ONLY you are not allowed to make changes in it!

### Running the App

The recommended way to start the application is from the repo root:

- `uv run start` - Starts the Reflex Web UI development server.

---

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
- **Eliot**: Used for structured logging and action tracking.
- **No placeholders**: Never use `/my/custom/path/` in code.
- **No legacy support**: Refactor aggressively; do not keep old API functions.
- **Dependency Management**: Use `uv sync` and `uv add`. NEVER use `uv pip install`.
- **Versions**: Do not hardcode versions in `__init__.py`; use `project.toml`.
- **Avoid __all__**: Avoid `__init__.py` with `__all__` as it confuses where things are located.

---

## Dagster Pipeline

For any Dagster-related changes, see **[docs/DAGSTER_GUIDE.md](docs/DAGSTER_GUIDE.md)** and **[docs/PERFORMANCE.md](docs/PERFORMANCE.md)**.

### Project-Specific Patterns

- **Auto-configuration**: Dagster config is automatically created on first run. See **[docs/CLEAN_SETUP.md](docs/CLEAN_SETUP.md)**.
- **Declarative Assets**: We prioritize Software-Defined Assets (SDA) over imperative ops.
- **IO Managers**: Reference assets (Ensembl, ClinVar, etc.) use `annotation_cache_io_manager` → stored in `~/.cache/just-dna-pipelines/`.
- **User assets** use `user_asset_io_manager` → stored in `data/output/users/{user_name}/`.
- **Lazy materialization**: Assets check if cache exists before downloading.
- **Start UI**: `uv run dagster-ui` or `uv run start`.

### Asset Return Types

| Asset Returns | IO Manager | Use Case |
|---------------|------------|----------|
| `pl.LazyFrame` | `polars_parquet_io_manager` | Small parquet, schema visibility |
| `Path` | Custom IO manager | Large data, DuckDB joins, file uploads |
| `dict` | Default | API responses, upload results |

### Key Rules

- **dagster-polars**: Use `PolarsParquetIOManager` for `LazyFrame` assets → automatic schema/row count in UI
- **Path assets**: Add `"dagster/column_schema": polars_schema_to_table_schema(path)` for schema visibility
- **Asset checks**: Use `@asset_check` for validation; include via `AssetSelection.checks_for_assets(...)`
- **Streaming**: Use `lazy_frame.sink_parquet()`, never `.collect().write_parquet()` on large data
- **DuckDB**: Use for large joins (out-of-core); set `memory_limit` and `temp_directory`
- **Concurrency**: Use `op_tags={"dagster/concurrency_key": "name"}` to limit parallel execution

### Dynamic Partitions Pattern

1. Create partition def: `PARTS = DynamicPartitionsDefinition(name="files")`
2. Discovery asset registers partitions: `context.instance.add_dynamic_partitions(PARTS.name, keys)`
3. Partitioned assets use: `partitions_def=PARTS`, access `context.partition_key`
4. Collector depends on partitioned output via `deps=[partitioned_asset]`, scans filesystem for results

### Execution

- **Python API only**: `defs.resolve_job_def(name)` + `job.execute_in_process(instance=instance)`
- **Same DAGSTER_HOME** for UI and execution: `dagster dev -m module.definitions`
- **All assets in `Definitions(assets=[...])`** for lineage visibility in UI

### Anti-Patterns

- `dagster job execute` CLI (deprecated)
- Hardcoded asset names; use `defs.get_all_asset_specs()`
- Config for unselected assets (validation errors)
- Suspended jobs holding DuckDB file locks

---

## Test Generation Guidelines

- **Real data + ground truth**: Use actual source data, auto-download if needed, and compute expected values at runtime.
- **Deterministic coverage**: Use fixed seeds or explicit filters; include representative and edge cases.
- **Meaningful assertions**: Prefer relationships and aggregates over existence-only checks.
- **Verbosity**: Run `pytest -vvv`.
- **Docs**: Put all new markdown files (except README/AGENTS) in `docs/`.

### What to Validate

- **Counts & aggregates**: Row counts, sums/min/max/means, distinct counts, and distributions.
- **Joins**: Pre/post counts, key coverage, cardinality expectations, nulls introduced by outer joins, and a few spot-checks.
- **Transformations**: Round-trip survival, subset/superset semantics, value mapping, key preservation.
- **Data quality**: Format/range checks, outliers, malformed entries, duplicates, referential integrity.

### Avoiding LLM "Reward Hacking" in Tests

- **Runtime ground truth**: Query source data at test time instead of hardcoding expectations.
- **Seeded sampling**: Validate random records with a fixed seed, not just known examples.
- **Negative & boundary tests**: Ensure invalid inputs fail; probe min/max, empty, unicode.
- **Derived assertions**: Test relationships (e.g., input vs output counts), not magic numbers.
- **Allow expected failures**: Use `pytest.mark.xfail` for known data quality issues with a clear reason.

### Test Structure Best Practices

- **Parameterize over duplicate**: If testing the same logic on multiple outputs, use `@pytest.mark.parametrize` instead of copy-pasting tests.
- **Set equality over counts**: Prefer `assert set_a == set_b` over `assert len(set_a) == 270` - set comparison catches both missing and extra values.
- **Delete redundant tests**: If test A (e.g., set equality) fully covers test B (e.g., count check), keep only test A.
- **Domain constants are OK**: Hardcoding expected enum values or well-known constants from specs is fine; hardcoding row counts or unique counts derived from data inspection is not.

### Verifying Bug-Catching Claims

When claiming a test "would have caught" a bug, **demonstrate it**:

1. **Isolate the buggy logic** in a test or script
2. **Run it and show failure** against correct expectations
3. **Then show the fix passes** the same test

Never claim "tests would have caught this" without running the buggy code against the test.

### Anti-Patterns to Avoid

- Testing only "happy path" with trivial data
- Hardcoding expected values that drift from source (use derived ground truth)
- Mocking data transformations instead of running real pipelines
- Ignoring edge cases (nulls, empty strings, boundary values, unicode, malformed data)
- **Claiming tests "would catch bugs" without demonstrating failure on buggy code**

**Meaningless Tests to Avoid** (common AI-generated anti-patterns):

```python
# BAD: Existence-only checks as the sole validation
assert "name" in df.columns
assert len(df) > 0

# BAD: Hardcoded counts derived from data inspection
assert len(source_ids) == 270  # will break when source changes

# BAD: Redundant with set equality test
assert len(output_cats) == 12  # already covered by subset check

# ACCEPTABLE: Required columns as prerequisites
required_cols = {"id", "name", "value"}
assert required_cols.issubset(df.columns)

# GOOD: Set equality from source data
source_ids = set(source_df["id"].unique().drop_nulls().to_list())
output_ids = set(output_df["id"].unique().drop_nulls().to_list())
assert source_ids == output_ids

# GOOD: Domain knowledge constants (from spec, not data inspection)
assert valid_states == {"active", "inactive", "pending"}  # from API spec
```

---

## Design System

For UI/frontend changes, see **[docs/DESIGN.md](docs/DESIGN.md)**.

Key principles:
- **"Chunky & Tactile"** aesthetic with high affordance
- **DaisyUI + Tailwind** component classes
- **Oversized icons** (min 2rem), **large buttons** (`btn-lg`), **generous spacing** (`gap-8`)
- **Semantic colors**: `bg-success` (benign), `bg-error` (pathogenic), `bg-info` (VUS)
