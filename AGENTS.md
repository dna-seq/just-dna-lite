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
- **Pay attention to terminal warnings**: Always check terminal output for warnings, especially deprecation ones. AI knowledge of APIs can be outdated; these warnings are critical hints to update code to the current version.
- **No placeholders**: Never use `/my/custom/path/` in code.
- **No legacy support**: Refactor aggressively; do not keep old API functions.
- **Dependency Management**: Use `uv sync` and `uv add`. NEVER use `uv pip install`.
- **Versions**: Do not hardcode versions in `__init__.py`; use `project.toml`.
- **Avoid __all__**: Avoid `__init__.py` with `__all__` as it confuses where things are located.
- **Cross-Project Knowledge**: We sometimes add `prepare-annotations` to the workspace. This folder is **READ-ONLY**. You MUST check `@prepare-annotations/AGENTS.md` for shared Dagster patterns, resource tracking, and best practices. If you find a superior pattern there that is applicable to `just-dna-lite`, you should adopt it and update this file.
- **Self-Correction**: If you make an API mistake that leads to a system error (e.g. a crash or a major logic failure due to outdated knowledge), you MUST update this file (`AGENTS.md`) with the correct API usage or pattern. This ensures future agents don't repeat the same mistake.

---

## Dagster Pipeline

For any Dagster-related changes, see **[docs/DAGSTER_GUIDE.md](docs/DAGSTER_GUIDE.md)**.

### Resource Tracking (MANDATORY)

**Always track CPU and RAM consumption** for all compute-heavy assets using `resource_tracker` from `just_dna_pipelines.runtime`:

```python
from just_dna_pipelines.runtime import resource_tracker

@asset
def my_asset(context: AssetExecutionContext) -> Output[Path]:
    with resource_tracker("my_asset", context=context):
        # ... compute-heavy code ...
        pass
```

**Important:** Always pass `context=context` to enable Dagster UI charts. Without it, metrics only go to Eliot logs.
This automatically logs to Dagster UI: `duration_sec`, `cpu_percent`, `peak_memory_mb`, `memory_delta_mb`.

### Run-Level Resource Summaries (MANDATORY)

All jobs must include the `resource_summary_hook` from `just_dna_pipelines.annotation.utils` to provide aggregated resource metrics at the run level:

```python
from just_dna_pipelines.annotation.utils import resource_summary_hook

my_job = define_asset_job(
    name="my_job",
    selection=AssetSelection.assets(...),
    hooks={resource_summary_hook},  # Note: must be a set, not a list
)
```

This hook logs a summary at the end of each successful run: Total Duration, Max Peak Memory, and Top memory consumers.

### Dagster Version Notes (1.12.x)

**API differences from newer versions (MANDATORY reference):**
- `get_dagster_context()` does NOT exist - you must pass `context` explicitly.
- `context.log.info()` does NOT accept a `metadata` keyword argument - use `context.add_output_metadata()` separately.
- `EventRecordsFilter` does NOT have `run_ids` parameter - use `instance.all_logs(run_id, of_type=...)` instead.
- For asset materializations, use `EventLogEntry.asset_materialization` (returns `Optional[AssetMaterialization]`), not `DagsterEvent.asset_materialization`.
- `hooks` parameter in `define_asset_job` must be a `set`, not a list: `hooks={my_hook}`.
- Use `defs.resolve_all_asset_specs()` instead of deprecated `defs.get_all_asset_specs()`.

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

### API Gotchas

**Timestamps are on `RunRecord`, not `DagsterRun`:**

```python
# WRONG - DagsterRun has no start_time/end_time
runs = instance.get_runs(limit=10)
for run in runs:
    print(run.start_time)  # AttributeError!

# CORRECT - Use get_run_records() to access timestamps
records = instance.get_run_records(limit=10)
for record in records:
    run = record.dagster_run
    # record.start_time and record.end_time are Unix timestamps (floats)
    # record.create_timestamp is a datetime object
    started = datetime.fromtimestamp(record.start_time) if record.start_time else None
```

**Partition keys via tags, not direct parameter:**

```python
# WRONG - create_run_for_job doesn't accept partition_key
run = instance.create_run_for_job(job_def=job, partition_key=pk)

# CORRECT - pass partition via tags
run = instance.create_run_for_job(
    job_def=job,
    run_config=config,
    tags={"dagster/partition": pk},
)
```

**Prefer `execute_in_process` over `submit_run` for CLI/UI:**

Using `submit_run` requires a daemon running with matching workspace context, which is fragile (location name mismatches, daemon coordination). For CLI tools and web UIs, use `execute_in_process` instead:

```python
# RECOMMENDED - execute_in_process (no daemon required, runs synchronously)
job_def = defs.resolve_job_def(job_name)

# Ensure partition exists (for dynamic partitions)
existing = instance.get_dynamic_partitions(partition_def.name)
if partition_key not in existing:
    instance.add_dynamic_partitions(partition_def.name, [partition_key])

result = job_def.execute_in_process(
    run_config=run_config,
    instance=instance,
    tags={"dagster/partition": partition_key},
)
if result.success:
    print("Job completed successfully")
else:
    print(f"Job failed: {result.all_events}")
```

**Avoid `submit_run` unless running via Dagster UI daemon:**

`submit_run` requires matching workspace context between the caller and the daemon. This is error-prone when the UI/CLI creates runs with a different location name than what the daemon loads. If you must use `submit_run`, see the Dagster 1.12+ API notes above about `WorkspaceProcessContext`.

**Asset job config uses "ops" key, not "assets":**

```python
# WRONG - "assets" key causes DagsterInvalidConfigError
run_config = {
    "assets": {"user_hf_module_annotations": {"config": {...}}}
}

# CORRECT - use "ops" key for asset job config
run_config = {
    "ops": {"user_hf_module_annotations": {"config": {...}}}
}
```

**Run logs via `all_logs`, not `EventRecordsFilter`:**

```python
# WRONG - EventRecordsFilter doesn't have run_ids
records = instance.get_event_records(EventRecordsFilter(run_ids=[run_id]))

# CORRECT - use all_logs(run_id)
events = instance.all_logs(run_id)
```

### Anti-Patterns

- `dagster job execute` CLI (deprecated)
- Hardcoded asset names; use `defs.get_all_asset_specs()`
- Config for unselected assets (validation errors)
- Suspended jobs holding DuckDB file locks
- **Accessing `run.start_time` on DagsterRun** - use RunRecord instead

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

## Reflex UI Framework

The webui uses **Reflex** (Python-based React framework). See **[docs/DESIGN.md](docs/DESIGN.md)** for visual design.

- **Check terminal for frontend errors**: Reflex often displays frontend/compilation errors and warnings directly in the terminal where `uv run start` or `reflex run` is running. Always monitor the terminal for these issues when working on the UI.

### Critical Reflex Patterns

**1. Icons require STATIC strings:**

```python
# CRASHES - rx.icon() cannot accept rx.Var
rx.icon(module["icon_name"], size=24)

# WORKS - use rx.match for dynamic icons
rx.match(
    module["name"],
    ("heart", rx.icon("heart", size=24)),
    ("star", rx.icon("star", size=24)),
    rx.icon("database", size=24),  # default
)
```

**2. Icon naming - use HYPHENATED Lucide names:**

| Wrong | Correct |
| :--- | :--- |
| `check-circle` | `circle-check` |
| `check_circle` | `circle-check` |
| `upload_cloud` | `cloud-upload` |
| `alert-circle` | `circle-alert` |
| `play-circle` | `circle-play` |

Verified icons: `circle-check`, `circle-x`, `circle-alert`, `circle-play`, `cloud-upload`, `upload`, `download`, `file-text`, `files`, `dna`, `heart`, `heart-pulse`, `activity`, `zap`, `droplets`, `pill`, `loader-circle`, `refresh-cw`, `external-link`, `terminal`, `database`, `boxes`, `inbox`, `history`, `chart-bar`, `play`.

**3. Use `rx.cond()` for reactive styling:**

```python
# GOOD - reactive
class_name=rx.cond(is_active, "ui primary button", "ui button")

# BAD - not reactive, evaluated once at compile time
class_name="ui primary button" if is_active else "ui button"
```

**4. rx.foreach with dictionaries:**

Values from dicts in `rx.foreach` are typed as `Any`. This can cause type errors in components that expect specific types (e.g. `rx.checkbox` expecting `bool`). Cast when needed using `.to()`:

```python
# Cast to int for text/formatting
rx.text(item["count"].to(int))

# Cast to bool for control props
rx.checkbox(checked=item["is_checked"].to(bool))
```

**5. Use `class_name` not `class`:**

Reflex uses `class_name` for CSS classes. Using `class` will cause a Python `SyntaxError` as it is a reserved keyword.

```python
# GOOD
rx.box(class_name="ui segment")

# BAD - SyntaxError
rx.box(class="ui segment")
```

### Reflex Anti-Patterns

- **Dynamic icon names** - Will crash with "Icon name must be a string"
- **Underscore icon names** - Use hyphens: `heart-pulse` not `heart_pulse`
- **Wrong icon order** - It's `circle-check` not `check-circle`
- **Python conditionals for state** - Use `rx.cond()` instead
- **Missing `.to()` casts in foreach** - Can cause type errors

### Fomantic UI + Reflex Gotchas

**1. Fomantic UI Grid does NOT work reliably in Reflex:**

```python
# UNRELIABLE - columns may stack vertically instead of side-by-side
rx.el.div(
    rx.el.div(..., class_name="five wide column"),
    rx.el.div(..., class_name="six wide column"),
    class_name="ui grid",
)

# GOOD - use CSS flexbox for multi-column layouts
rx.el.div(
    rx.el.div(left, style={"flex": "0 0 30%"}),
    rx.el.div(center, style={"flex": "0 0 40%"}),
    rx.el.div(right, style={"flex": "1 1 30%"}),
    style={"display": "flex", "flexDirection": "row"},
)
```

**2. Fomantic UI Menu may not render horizontally:**

Use flexbox for reliable horizontal menus instead of `ui fixed menu`.

**3. Fomantic UI Checkbox requires specific HTML structure:**

```python
# BAD - rx.checkbox() doesn't use Fomantic styling
rx.checkbox(checked=is_checked)

# GOOD - proper Fomantic checkbox structure
rx.el.div(
    rx.el.input(type="checkbox", checked=is_checked, read_only=True),
    rx.el.label("Label"),
    on_click=handler,
    class_name=rx.cond(is_checked, "ui checked checkbox", "ui checkbox"),
)
```

**4. What DOES work from Fomantic UI in Reflex:**
- `ui segment`, `ui raised segment` - work well
- `ui button`, `ui primary button` - work well
- `ui label`, `ui mini label`, `ui green label` - work well
- `ui divider` - works well
- `ui message` - works well

**5. What does NOT work reliably:**
- `ui grid` with column widths - use flexbox instead
- `ui fixed menu` - use flexbox instead
- `ui accordion` - may need JS initialization
- Native `rx.checkbox()` styling - use Fomantic structure instead

---

## Design System

For UI/frontend changes, see **[docs/DESIGN.md](docs/DESIGN.md)**.

Key principles:
- **"Chunky & Tactile"** aesthetic with high affordance
- **Fomantic UI** component classes (segments, buttons, labels work best)
- **CSS Flexbox** for layouts (not Fomantic grid)
- **Oversized icons** (min 2rem), **large buttons**, **generous spacing**
- **Semantic colors**: `success` (benign), `error` (pathogenic), `info` (VUS)
