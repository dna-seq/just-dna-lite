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

## Module Configuration (`modules.yaml`)

Annotation module sources and display metadata are configured in **`modules.yaml`**. The loader checks two locations (first found wins):

1. **Project root** (`./modules.yaml`) — preferred, easy for users to find and edit
2. **Package directory** (`just-dna-pipelines/src/just_dna_pipelines/modules.yaml`) — bundled fallback

This is the single source of truth for:

1. **Sources** to scan for modules (any fsspec-compatible URL: HuggingFace, GitHub, HTTP, S3, etc.)
2. **Display metadata** overrides (title, description, icon, color, report_title) for known modules
3. **Ensembl reference dataset** (`ensembl_source.repo_id`) — the HuggingFace dataset used for Ensembl variation annotation

**Modules are always auto-discovered** from the configured sources. The YAML only provides optional display overrides. Modules not listed in `module_metadata` get auto-generated defaults (titlecased name, generic icon, default color).

### Key files

- **`modules.yaml`**: Declares sources, Ensembl reference, quality filters, and optional metadata overrides
- **`module_config.py`**: Pydantic models (`Source`, `ModuleMetadata`, `EnsemblSource`, `ModulesConfig`), YAML loader, helper functions (`get_module_meta()`, `build_module_metadata_dict()`, etc.)
- **`annotation/hf_modules.py`**: Discovery logic — scans sources via fsspec, builds `MODULE_INFOS` and `DISCOVERED_MODULES`

### Adding a new module source

1. Upload data to any fsspec-accessible location (HF repo, GitHub, HTTP server, S3, etc.)
2. Add the source URL to `modules.yaml` under `sources:`
3. Optionally add display metadata under `module_metadata:`
4. Modules are auto-discovered on next startup

### Source types (auto-detected from URL)

- `org/repo` (shorthand) or `hf://datasets/org/repo` → HuggingFace
- `github://org/repo` → GitHub via fsspec
- `https://...` → HTTP/HTTPS via fsspec
- `s3://...`, `gcs://...` → cloud storage via fsspec

### Module vs Collection

Each source can be a single module or a collection:
- **Auto-detect** (default): `weights.parquet` at root = single module; subfolders with `weights.parquet` = collection
- **Override**: `kind: module` or `kind: collection` in the YAML source entry

### Important patterns

- **Never hardcode module lists or metadata in Python files** — always use `get_module_meta()` or `build_module_metadata_dict()` from `module_config`
- **Never hardcode HF repo URLs** — use `DEFAULT_REPOS` or `MODULES_CONFIG.sources` from `module_config`
- **Never hardcode Ensembl repo ID** — `EnsemblAnnotationsConfig.repo_id` defaults to `MODULES_CONFIG.ensembl_source.repo_id`
- `HF_DEFAULT_REPOS`, `HF_REPO_ID` in `hf_modules.py` are backward-compatible aliases sourced from the YAML

---

## VCF Quality Filtering

Quality filters are configured in `modules.yaml` under `quality_filters:` and applied during normalization (`user_vcf_normalized` asset). All downstream assets receive filtered data.

### Configuration (`modules.yaml`)

```yaml
quality_filters:
  pass_filters: ["PASS", "."]  # FILTER column values to keep (null to disable)
  min_depth: 10                 # Minimum DP (null/0 to disable)
  min_qual: 20                  # Minimum QUAL (null/0 to disable)
```

- **gVCF support**: Reference blocks (`FILTER=RefCall`, `GT=0/0`) are correctly dropped by `pass_filters` since `RefCall` is not in `["PASS", "."]`. This is intentional — ref blocks have no alt allele and would never match annotation module weights.
- **Backward compatible**: If `quality_filters` is absent from YAML, no filtering occurs (all fields default to `None`).

### Config Asset Pattern

A non-partitioned `quality_filters_config` asset materializes the current filter settings from `modules.yaml`. `user_vcf_normalized` depends on it.

**When `modules.yaml` changes:**
1. Re-materialize `quality_filters_config` (its `DataVersion` is a hash of the filter config)
2. Dagster marks `user_vcf_normalized` partitions as stale
3. Re-materialize stale partitions to apply new filters

### Key files

- **`modules.yaml`**: `quality_filters` section (single source of truth)
- **`module_config.py`**: `QualityFilters` model, `build_quality_filter_expr()` helper
- **`annotation/assets.py`**: `quality_filters_config` asset, filter application in `user_vcf_normalized`

### chrY Warning for Female Samples

When `sex="Female"` is set in `NormalizeVcfConfig`, the normalization asset logs a warning if chrY variants are found (e.g., `"WARNING: 1200 chrY variants found in female-labeled sample"`) but **never removes them**. This is informational only — QC filters (FILTER, depth, qual) handle the actual cleanup. We deliberately avoid sex-based chromosome filtering to prevent data loss for XXY, XYY, and other karyotype variations.

### Important patterns

- **Never bypass quality filters** — all VCF annotation paths should read from the normalized (and filtered) parquet, not raw VCF
- **Column name detection is case-tolerant** — `build_quality_filter_expr()` searches for `(filter, Filter, FILTER)`, `(DP, Dp, dp)`, `(qual, Qual, QUAL)` to handle different VCF parser conventions
- **Cast before comparison** — DP and QUAL columns are cast to numeric types before threshold comparison to handle string-typed parquet columns

---

## Dagster Pipeline

**For any Dagster-related changes, architecture, or troubleshooting, see [docs/DAGSTER_GUIDE.md](docs/DAGSTER_GUIDE.md).** The guide explains the full pipeline (VCF normalization → HF annotation + optional Ensembl → reports), output paths, jobs, and known quirks (e.g. polars-bio non-fatal Rust panic).

**Shared normalization**: Both HF module annotation and Ensembl annotation read from `user_vcf_normalized` (quality-filtered, chr-stripped parquet). Ensembl assets (`user_annotated_vcf`, `user_annotated_vcf_duckdb`) depend on `user_vcf_normalized` — they do NOT re-parse the raw VCF.

**Jobs:**
- `annotate_and_report_job`: normalize → HF modules → report (default)
- `annotate_all_job`: normalize → HF modules + Ensembl DuckDB → report (when Ensembl toggle is on in UI)
- `annotate_ensembl_only_job`: normalize → Ensembl DuckDB only (no HF modules, no report)
- `normalize_vcf_job`: normalize only (auto-runs on upload)

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
- **Ensembl cache layout**: Flat chromosome parquets at `~/.cache/just-dna-pipelines/ensembl_variations/data/homo_sapiens-chr*.parquet`. Downloaded via fsspec (`HfFileSystem`). The repo is configured in `modules.yaml` under `ensembl_source:`. DuckDB creates a single `ensembl_variations` VIEW over all files.
- **Lazy materialization**: Assets check if cache exists before downloading.
- **Start UI**: `uv run start` (full stack) or `uv run dagster` (pipelines only).

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
- **Same DAGSTER_HOME** for UI and execution: `dg dev -m module.definitions`
- **All assets in `Definitions(assets=[...])`** for lineage visibility in UI

### API Gotchas

**Never use `huggingface_hub.snapshot_download` for large datasets:**

`snapshot_download` duplicates data into HuggingFace's own blob store (`~/.cache/huggingface/`) and then copies/links to `local_dir`. This wastes disk space and is unreliable. Instead, use **fsspec** via `HfFileSystem` for direct file-by-file downloads into our cache:

```python
# WRONG - duplicates data in HF blob store, unreliable local_dir population
from huggingface_hub import snapshot_download
snapshot_download(repo_id="org/repo", local_dir=cache_dir, ...)

# CORRECT - direct download via fsspec, files land exactly where we want
from huggingface_hub import HfFileSystem, get_token
fs = HfFileSystem(token=get_token())
for remote_path in fs.ls("datasets/org/repo/data", detail=False):
    if remote_path.endswith(".parquet"):
        fs.get(remote_path, str(local_path))
```

This pattern is also future-proof: swapping `HfFileSystem` for any other fsspec backend (S3, GCS, HTTP) requires minimal changes.

**polars-bio `scan_vcf` API changed (0.23+):**

- `IOOperations.scan_vcf()` no longer accepts `thread_num`.
- Use `concurrent_fetches` instead.
- In `just_dna_pipelines.io.read_vcf_file()`, keep `thread_num` only as backward-compatible API and map it to `concurrent_fetches`.

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

**Web UI Job Execution Pattern (TRY-DAEMON-WITH-FALLBACK):**

For the Reflex Web UI, we use a hybrid approach: try daemon-based execution first, but fall back to `execute_in_process` if submission fails. **Critical: Keep business logic outside exception handlers.**

```python
# RECOMMENDED PATTERN - Separate business logic from exception handling

# 1. Create run
job_def = defs.resolve_job_def(job_name)
run = instance.create_run_for_job(
    job_def=job_def,
    run_config=run_config,
    tags={"dagster/partition": partition_key},
)
run_id = run.run_id

# 2. Try daemon submission (register failure, don't process it)
daemon_success, daemon_error = self._try_submit_to_daemon(instance, run_id)

# 3. Handle success/failure outside exception handler
if daemon_success:
    # Poll status asynchronously via poll_run_status()
    yield rx.toast.info("Job started")
else:
    # Fall back to execute_in_process as background task (non-blocking)
    self._add_log(f"Daemon failed: {daemon_error}")
    yield rx.toast.info("Running in-process - please wait...")
    
    # Launch in thread pool without awaiting (keeps UI responsive)
    # CRITICAL: Use run_in_executor, NOT asyncio.create_task or asyncio.to_thread
    # Those cause pyo3 panics with Dagster objects
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        None,  # Use default executor
        self._execute_inproc_with_state_update,
        instance, job_name, run_config, partition_key, run_id, sample_name
    )
    # Background task will update state when complete

# Helper methods (separate concerns):
def _try_submit_to_daemon(self, instance, run_id) -> tuple[bool, str]:
    """Try daemon submission. Returns (success, error_message)."""
    try:
        instance.submit_run(run_id, workspace=None)
        return (True, "")
    except Exception as e:
        return (False, str(e))

def _execute_inproc_with_state_update(self, ...) -> None:
    """Execute in-process and update state. Called from thread pool via run_in_executor."""
    try:
        # Execute synchronously (caller handles threading via run_in_executor)
        result = self._execute_job_in_process(...)
        # Update UI state with result (self.running = False, etc.)
        self.running = False
        self.last_run_success = result.success
    except Exception as e:
        # Update UI state for failure
        self.running = False
        self.last_run_success = False
```

**Why this pattern is better:**
- ✅ Business logic outside exception handlers (cleaner separation of concerns)
- ✅ Exception handlers only register failures, don't process them
- ✅ Control flow is linear and easy to follow
- ✅ Each method has single responsibility
- ✅ **UI stays responsive** - Background task doesn't block event handler

**Critical: UI Responsiveness and Python/Rust Thread Safety**

NEVER await long-running operations in Reflex event handlers - it blocks the entire UI. Also, be careful with threading when using Dagster (which has Rust/pyo3 internals):

```python
# BAD - Blocks UI until job completes (minutes!)
fallback_result = await self._execute_inproc_with_state_update(...)
if fallback_result["success"]:
    yield rx.toast.success("Done")

# BAD - asyncio.to_thread() with Dagster objects causes pyo3 panic:
# "Cannot drop pointer into Python heap without the thread being attached"
result = await asyncio.to_thread(self._execute_job_in_process, ...)

# BAD - asyncio.create_task() on sync function
asyncio.create_task(self._execute_inproc_with_state_update(...))  # Not async!

# GOOD - Use run_in_executor for thread-safe background execution
loop = asyncio.get_event_loop()
loop.run_in_executor(None, self._execute_inproc_with_state_update, ...)
# UI remains responsive, thread-safe, no pyo3 panics
```

**Why run_in_executor works:** It properly manages the Python GIL when moving objects between threads, unlike `asyncio.to_thread()` which can cause pyo3 (Python/Rust bridge) panics with Dagster objects.

**Why `submit_run(workspace=None)` fails in web UIs:**

Daemon-based execution requires `ExternalPipelineOrigin` which needs workspace context. Web UI state doesn't have easy access to workspace context, so `submit_run(run_id, workspace=None)` fails with "Expected non-None value: External pipeline origin must be set for submitted runs". The fallback to `execute_in_process` handles this reliably.

**Critical: Per-file running state (not global)**

Button enable logic must check if the **selected file** is running, not if **any** job is running globally. This allows concurrent jobs on different files:

```python
# BAD - blocks ALL files when ANY file is running
@rx.var
def can_run_annotation(self) -> bool:
 return bool(self.selected_file) and len(self.selected_modules) > 0 and not self.running

# GOOD - only blocks the selected file if it's running
@rx.var
def can_run_annotation(self) -> bool:
 if not self.selected_file or not self.selected_modules:
 return False
 
 # Check if SELECTED file has a running job
 for run in self.runs:
 if run.get("filename") == self.selected_file:
 if run.get("status") in ("RUNNING", "QUEUED", "STARTING"):
 return False
 
 return True

# Helper computed var for UI elements
@rx.var
def selected_file_is_running(self) -> bool:
 """Check if the currently selected file has a running job."""
 if not self.selected_file:
 return False
 for run in self.runs:
 if run.get("filename") == self.selected_file:
 if run.get("status") in ("RUNNING", "QUEUED", "STARTING"):
 return True
 return False
```

Use `selected_file_is_running` for UI elements (button text, icons, spinners) instead of global `self.running` flag.

**Critical: Orphaned Run Cleanup (execute_in_process survival)**

When using `execute_in_process` in web UIs, runs are abandoned (stuck in STARTED status) on server restart. Implement these safeguards:

1. **Startup cleanup** - Clean up NOT_STARTED runs (daemon submission failures):

```python
def _cleanup_orphaned_runs(self) -> int:
 """Clean up NOT_STARTED runs on startup (daemon submission failures)."""
 instance = get_dagster_instance()
 not_started_records = instance.get_run_records(
 filters=RunsFilter(statuses=[DagsterRunStatus.NOT_STARTED]),
 limit=100,
 )
 cleaned_count = 0
 for record in not_started_records:
 run = record.dagster_run
 instance.report_run_canceled(run, message="Orphaned run from daemon submission failure")
 cleaned_count += 1
 return cleaned_count

async def on_load(self):
 """Load state and clean up orphaned runs."""
 cleaned = self._cleanup_orphaned_runs()
 if cleaned > 0:
 self._add_log(f"🧹 Cleaned up {cleaned} orphaned run(s) from previous session")
 # ... rest of on_load logic
```

2. **Track active in-process runs** - Use class variable to track which runs are executing in-process:

```python
class MyState(rx.State):
 # Class variable shared across all instances
 _active_inproc_runs: Dict[str, str] = {} # {run_id: partition_key}
 
 def _execute_inproc_with_state_update(self, ...):
 actual_run_id = None
 try:
 result = self._execute_job_in_process(...)
 actual_run_id = result.run_id
 # Track this run
 MyState._active_inproc_runs[actual_run_id] = partition_key
 # ... process result
 finally:
 # Clean up tracker
 if actual_run_id and actual_run_id in MyState._active_inproc_runs:
 del MyState._active_inproc_runs[actual_run_id]
```

3. **SIGTERM handler** - Mark STARTED runs as CANCELED on shutdown (in app.py):

```python
import signal
import atexit

def cleanup_active_runs():
 """Mark all active in-process runs as CANCELED on shutdown."""
 try:
 from my_app.state import MyState
 from dagster import DagsterInstance
 
 active_runs = MyState._active_inproc_runs.copy()
 if not active_runs:
 return
 
 instance = DagsterInstance.get()
 for run_id in active_runs:
 run = instance.get_run_by_id(run_id)
 if run:
 instance.report_run_canceled(
 run,
 message="Web server shutdown - in-process execution terminated"
 )
 except Exception as e:
 print(f"Warning: Failed to cleanup active runs: {e}")

# Register cleanup handlers
signal.signal(signal.SIGTERM, lambda sig, frame: (cleanup_active_runs(), sys.exit(0)))
signal.signal(signal.SIGINT, lambda sig, frame: (cleanup_active_runs(), sys.exit(0)))
atexit.register(cleanup_active_runs)
```

4. **CLI cleanup command** - Manual cleanup for orphaned runs:

```bash
# Clean up NOT_STARTED runs (daemon failures)
uv run pipelines cleanup-runs

# Clean up STARTED runs (abandoned in-process executions)
uv run pipelines cleanup-runs --status STARTED

# Dry-run to see what would be cleaned
uv run pipelines cleanup-runs --status STARTED --dry-run
```

**For CLI Tools: Direct `execute_in_process`**

CLI tools can use `execute_in_process` directly (no fallback needed):

```python
# For CLI tools - execute_in_process (no daemon required, runs synchronously)
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

**Trade-offs of try-daemon-with-fallback pattern:**

✅ **Benefits:**
- UI responsive when daemon works (job runs in daemon, not blocking web server)
- Reliable when daemon fails (falls back to execute_in_process)
- Background threading keeps execute_in_process from blocking UI

❌ **Limitations:**
- Runs created via execute_in_process fallback cannot be re-executed from Dagster UI (missing `remote_job_origin`)
- Execute_in_process runs in web server process (mitigated by background threading via `asyncio.to_thread`)

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

**`submit_run()` with workspace context - use try/fallback pattern:**

```python
# Web UI pattern: Try daemon submission, fall back to execute_in_process
try:
    instance.submit_run(run_id, workspace=None)
    # Success: daemon will run the job, poll status via poll_run_status()
except Exception as e:
    # Daemon rejected run (needs ExternalPipelineOrigin/workspace context)
    # Fall back to execute_in_process which runs reliably without workspace context
    result = await asyncio.to_thread(
        self._execute_job_in_process,
        instance, job_name, run_config, partition_key
    )
    # Update UI state with result immediately (no polling needed)
```

**Critical discovery:** Wrong parameter `workspace_process_context=None` caused TypeError → triggered fallback → job ran successfully via `execute_in_process`. The "correct" `workspace=None` is worse because it doesn't error immediately - daemon accepts submission but then rejects run with "External pipeline origin must be set", leaving run stuck in NOT_STARTED.

### Anti-Patterns

- `dagster job execute` CLI (deprecated)
- Hardcoded asset names; use `defs.get_all_asset_specs()`
- **Silent fallbacks when primary data is missing** — If normalized parquet does not exist (e.g. user_vcf_normalized), do NOT silently fall back to raw VCF and display it as if it were normalized. Users will not know the data source differs. Either show an explicit error ("Run normalization first") or a very prominent banner ("Using raw VCF — normalize job has not run"). See [docs/DAGSTER_GUIDE.md](docs/DAGSTER_GUIDE.md) § VCF Normalization.
- **Ensembl assets bypassing user_vcf_normalized** — `user_annotated_vcf` and `user_annotated_vcf_duckdb` MUST depend on `user_vcf_normalized` and pass the normalized parquet via `normalized_parquet=` parameter. Never read the raw VCF directly in annotation assets.
- Config for unselected assets (validation errors)
- Suspended jobs holding DuckDB file locks
- **Accessing `run.start_time` on DagsterRun** - use RunRecord instead
- **Using `submit_run(run_id, workspace=None)` without fallback in web UIs** - daemon rejects run, leaves it stuck in NOT_STARTED; always implement fallback to `execute_in_process`
- **Using global `self.running` flag for button enable logic** - blocks ALL files when ANY file is running; use per-file running state instead
- **Expecting Dagster UI re-execution to work for `execute_in_process` runs** - not supported, but acceptable trade-off

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

### UI Change Verification Workflow (MANDATORY)

When making significant UI changes, follow this workflow:

1. **Make changes** to UI code (state.py, annotate.py, layout.py, etc.)
2. **Check terminal for compile errors**: Run `uv run start` and monitor the terminal output for:
   - `ImportError` - Missing or renamed imports
   - `AttributeError` - Wrong API usage (e.g., `App.api_route` doesn't exist)
   - `Warning: Invalid icon tag` - Wrong icon names (use hyphenated Lucide names)
   - Traceback errors during "Compiling" phase
3. **Verify app starts successfully**: Look for "App running at: http://localhost:3000"
4. **Check browser**: Navigate to http://localhost:3000 and verify:
   - Page loads without blank screen
   - Key UI elements are visible (tabs, buttons, panels)
   - Interactive elements work (tab switching, file selection, etc.)
5. **Fix any issues** before considering the task complete

**Common compile-time errors:**
- `ModuleNotFoundError` - Add missing dependency with `uv add <package>`
- `ImportError: cannot import name 'X'` - Function was renamed/removed, update imports
- `AttributeError: 'App' object has no attribute 'Y'` - Wrong Reflex API, check docs

**Terminal monitoring tip**: Reflex hot-reloads on file changes. After editing, wait for "Compiling: 100%" message before checking the browser.

**Note on worker warnings**: During hot reload, Reflex may show `[WARNING] Killing worker-0 after it refused to gracefully stop`. This is normal behavior when the worker is busy processing a request during reload. It does not indicate a Dagster issue or data corruption.

### Critical Reflex Patterns

**1. Use `fomantic_icon()` instead of `rx.icon()`:**

Lucide icons (via `rx.icon()`) often fail to load or trigger terminal warnings in this environment. Use the `fomantic_icon()` helper from `webui.components.layout` instead. It maps common Lucide names to Fomantic UI equivalents.

```python
from webui.components.layout import fomantic_icon

# GOOD - consistent and reliable
fomantic_icon("dna", size=24, color="#2185d0")

# BAD - triggers "Invalid icon tag" warnings
fomantic_icon("dna", size=24)
```

**2. Icons require STATIC strings:**

Even with `fomantic_icon()`, you cannot pass a dynamic `rx.Var` as the name. Use `rx.match` for dynamic selection.

```python
# CRASHES
fomantic_icon(module["icon_name"], size=24)

# WORKS
rx.match(
    module["name"],
    ("heart", fomantic_icon("heart", size=24)),
    ("star", fomantic_icon("star", size=24)),
    fomantic_icon("database", size=24),  # default
)
```

**3. Icon naming:**

`fomantic_icon()` handles mapping for common names, but generally use Fomantic UI icon names (space-separated) or common hyphenated names which the helper will map.

Verified icons (mapped by helper): `circle-check`, `circle-x`, `circle-alert`, `circle-play`, `cloud-upload`, `upload`, `download`, `file-text`, `files`, `dna`, `heart`, `heart-pulse`, `activity`, `zap`, `droplets`, `pill`, `loader-circle`, `refresh-cw`, `external-link`, `terminal`, `database`, `boxes`, `inbox`, `history`, `chart-bar`, `play`.

**4. Use `rx.cond()` for reactive styling:**

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
- **Awaiting long-running tasks in event handlers** - Blocks entire UI; use `loop.run_in_executor()` for background execution
- **Using `asyncio.to_thread()` with Dagster objects** - Causes pyo3 panic "Cannot drop pointer into Python heap"; use `run_in_executor()` instead
- **Business logic in exception handlers** - Makes code hard to follow; separate concerns with dedicated methods

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
- `ui top attached tabular menu` + `ui bottom attached segment` - works well for tabs (with state-based class toggling)

**5. What does NOT work reliably:**
- `ui grid` with column widths - use flexbox instead
- `ui fixed menu` - use flexbox instead
- `ui accordion` - may need JS initialization
- Native `rx.checkbox()` styling - use Fomantic structure instead

**6. Fomantic UI Tabs (state-based, no jQuery):**

```python
# Tab menu - use state-based class toggling
def tab_menu() -> rx.Component:
    return rx.el.div(
        rx.el.a(
            "Tab 1",
            class_name=rx.cond(MyState.active_tab == "tab1", "active item", "item"),
            on_click=lambda: MyState.switch_tab("tab1"),
        ),
        rx.el.a(
            "Tab 2",
            class_name=rx.cond(MyState.active_tab == "tab2", "active item", "item"),
            on_click=lambda: MyState.switch_tab("tab2"),
        ),
        class_name="ui top attached tabular menu",
    )

# Tab content - use rx.match for dynamic content
rx.el.div(
    rx.match(
        MyState.active_tab,
        ("tab1", tab1_content()),
        ("tab2", tab2_content()),
        tab1_content(),  # default
    ),
    class_name="ui bottom attached segment",
)
```

**7. Custom API endpoints with api_transformer:**

```python
from fastapi import FastAPI
from fastapi.responses import FileResponse

# Create FastAPI app for custom routes
api = FastAPI()

@api.get("/api/download/{filename}")
async def download_file(filename: str) -> FileResponse:
    return FileResponse(path=file_path, filename=filename)

# Pass to Reflex app
app = rx.App(
    theme=None,
    api_transformer=api,  # Mounts custom routes
)
```

---

## PRS Integration (Polygenic Risk Scores)

The web UI integrates the `prs-ui` PyPI package for polygenic risk score computation using PGS Catalog data.

### Dependencies

- **`just-prs>=0.3.1`**: Core library — PRS computation, PGS Catalog client, scoring file parsing
- **`prs-ui>=0.1.1`**: Reusable Reflex components — `PRSComputeStateMixin`, `prs_section()`, score grid, results table

Both are added to `webui/pyproject.toml`.

### Architecture

`PRSState` is an independent `rx.State` subclass (not a substate of `UploadState`) with its own `LazyFrameGridMixin` for the PGS Catalog scores DataGrid. This parallels `OutputPreviewState`.

```python
from prs_ui import PRSComputeStateMixin

class PRSState(PRSComputeStateMixin, LazyFrameGridMixin, rx.State):
    genome_build: str = "GRCh38"
    cache_dir: str = str(resolve_cache_dir())  # ~/.cache/just-prs/
    status_message: str = ""
    prs_expanded: bool = False
```

### Data flow

1. User selects a VCF file in the left panel
2. `UploadState.select_file()` returns `PRSState.initialize_prs_for_file(parquet_path, genome_build)`
3. `PRSState` creates a `pl.scan_parquet()` LazyFrame from the normalized parquet and calls `set_prs_genotypes_lf(lf)` (preferred input method — lazy, memory-efficient)
4. PGS Catalog scores are loaded into the MUI DataGrid for selection
5. User selects scores and clicks Compute — `PRSComputeStateMixin.compute_selected_prs()` runs
6. Results with quality assessment, percentiles, and effect sizes are displayed

### Genome build mapping

`current_reference_genome` from file metadata maps directly to PRS genome builds:
- `"GRCh38"`, `"T2T-CHM13v2.0"` → `"GRCh38"` (default)
- `"GRCh37"`, `"hg19"` → `"GRCh37"`

### Key files

| File | What it does |
|------|-------------|
| `webui/src/webui/state.py` (`PRSState`) | PRS computation state, inherits `PRSComputeStateMixin` + `LazyFrameGridMixin` |
| `webui/src/webui/pages/annotate.py` | Collapsible PRS section between VCF Preview and Outputs |

### Important patterns

- **LazyFrame is the preferred input** — `set_prs_genotypes_lf(pl.scan_parquet(path))` avoids redundant I/O. The parquet path is also set as string fallback.
- **`PRSState` needs `genome_build`, `cache_dir`, `status_message`** — these are vars on the state itself (not inherited from `UploadState`), because `PRSComputeStateMixin` reads them via `self.genome_build` etc.
- **`prs_section()` uses Radix components** (`rx.hstack`, `rx.badge`, `rx.table`) which render without Radix theming in our `theme=None` app. Functional but unstyled. Future work: Fomantic-styled wrappers.
- **Independent `LazyFrameGridMixin`** — `PRSState` gets its own grid vars, completely separate from `UploadState`'s VCF grid and `OutputPreviewState`'s output grid.

### Anti-patterns

- **Never make PRSState a substate of UploadState** — it needs its own `LazyFrameGridMixin` instance; mixing into UploadState would create MRO conflicts.
- **Never pass UploadState's internal LazyFrame across states** — Reflex states are isolated; create a new `pl.scan_parquet()` LazyFrame from the shared parquet path instead.

---

## Design System

For UI/frontend changes, see **[docs/DESIGN.md](docs/DESIGN.md)**.

Key principles:
- **"Chunky & Tactile"** aesthetic with high affordance
- **Fomantic UI** component classes (segments, buttons, labels work best)
- **CSS Flexbox** for layouts (not Fomantic grid)
- **Oversized icons** (min 2rem), **large buttons**, **generous spacing**
- **Semantic colors**: `success` (benign), `error` (pathogenic), `info` (VUS)
