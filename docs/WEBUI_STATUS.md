# Web UI Implementation Status

## Current State

**Functional genomic annotation app** with a 2-panel run-centric layout using Fomantic UI styling + CSS flexbox. The UI is integrated with Dagster for running and monitoring annotation jobs.

### What's Working

1. **2-Panel Run-Centric Layout**:
   - **Files (Left Panel)**: Upload zone for VCF files, file library with status badges (`ready`, `running`, `completed`, `error`), and file deletion.
   - **Right Panel (Three Collapsible Sections)**:
     - **Outputs Section** (teal segment, top): Inline display of output files for the selected sample with type icons, module labels, file sizes, and download buttons. Shows "No outputs yet" with a prompt to run analysis when empty.
     - **Run History** (green segment, middle): Unified timeline of all runs for the selected file. The most recent run is highlighted with a "latest" badge and includes Re-run/Modify action buttons. Each run expands to show modules, run ID, and Dagster link.
     - **New Analysis Section** (blue segment, bottom): Collapsible module selection grid with "Select All/None" controls and Start Analysis button.

2. **Dagster Integration**:
   - **Real-time Status Polling**: Uses `rx.moment` to poll Dagster for run status updates every 3 seconds.
   - **Live Logs**: Fetches and displays the last 50 events from the Dagster event log for the active run.
   - **Run Submission**: Submits runs to Dagster daemon with automatic fallback to in-process execution if needed.
   - **History Persistence**: Persists run history by querying the Dagster instance on load.
   - **Materialization Tracking**: Queries Dagster for asset materializations to determine file annotation status.

3. **Design System**:
   - **Fomantic UI**: Uses segments, buttons, labels, and messages for a "chunky & tactile" look.
   - **Lucide Icons**: Dynamic icon rendering via `rx.match` (Lucide names like `heart`, `droplets`, `dna`).
   - **Responsive Flexbox**: Column layout and top menu implemented with flexbox for reliability (avoiding Fomantic Grid issues).

4. **File Management**:
   - Files are saved to `data/input/users/{user_id}/`.
   - Automatic registration of uploaded files as Dagster assets (`user_vcf_source`).
   - Cleanup of state and filesystem on file deletion.
   - **Sample Metadata**:
     - Species selection using Latin scientific names (Homo sapiens, Mus musculus, etc.)
     - Reference genome selection (GRCh38, T2T-CHM13v2.0, GRCh37 for humans)
     - Editable fields: Subject ID, Study Name, Notes
     - **Custom Fields**: User-defined key-value metadata (add any field with custom name)

5. **Output Files**:
   - Annotation outputs are stored at `data/output/users/{user_id}/{sample_name}/modules/`.
   - File types:
     - `{module}_weights.parquet` - Genotype-specific scores
     - `{module}_annotations.parquet` - Variant facts (optional)
     - `{module}_studies.parquet` - Literature evidence (optional)
   - Inline outputs section shows files with type icons (scale/file-text/book-open), module labels, file sizes, and download buttons.
   - Empty state shows "No outputs yet" with prompt to run analysis.

### Architecture

```
webui/
├── src/webui/
│   ├── components/
│   │   └── layout.py          # Navbar, two_column_layout container
│   ├── pages/
│   │   ├── annotate.py        # 2-panel run-centric layout
│   │   ├── index.py           # Main landing page (aliases annotate)
│   │   └── analysis.py        # Analysis page (placeholder)
│   ├── state.py               # Main UploadState: Uploads, Dagster API, Run state, Output files
│   └── app.py                 # Reflex app setup, routing & download API endpoint
└── rxconfig.py                # Configuration & Fomantic UI CDN
```

### UI-Dagster Integration Architecture

The Web UI connects to Dagster directly via the Python API (not HTTP). Both run in the same process when using `uv run start`.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           User Browser                                   │
│                        http://localhost:3000                             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Reflex Web UI (Python)                              │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  state.py - UploadState                                          │    │
│  │  ├── get_dagster_instance() → DagsterInstance                    │    │
│  │  ├── Files: upload, delete, list                                 │    │
│  │  ├── Runs: submit, poll status, fetch logs                       │    │
│  │  ├── Run History: last_run_for_file, filtered_runs               │    │
│  │  └── Outputs: scan parquet files from filesystem                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
┌──────────────────────────────┐    ┌──────────────────────────────────────┐
│   Dagster Instance (Python)  │    │         Filesystem                    │
│   DAGSTER_HOME/              │    │  data/                                │
│   ├── storage/ (run history) │    │  ├── input/users/{user}/ (VCF files) │
│   ├── schedules/             │    │  └── output/users/{user}/{sample}/   │
│   └── event_log.db           │    │      └── modules/*.parquet           │
└──────────────────────────────┘    └──────────────────────────────────────┘
```

**What the UI loads FROM Dagster:**

| Data | Dagster API | When Loaded |
|------|-------------|-------------|
| Run history | `instance.get_run_records(filters=RunsFilter(job_name=...))` | On page load (`on_load`) |
| Run status | `instance.get_run_by_id(run_id)` | Every 3s while running (`poll_run_status`) |
| Run logs | `instance.all_logs(run_id)` | Every 3s while running, or on timeline expand |
| Asset materializations | `instance.fetch_materializations(records_filter=...)` | On page load (to check file status) |
| Dynamic partitions | `instance.get_dynamic_partitions(partition_def.name)` | Before run submission |

**What the UI sends TO Dagster:**

| Action | Dagster API | Triggered By |
|--------|-------------|--------------|
| Register partition | `instance.add_dynamic_partitions(name, [keys])` | File upload |
| Report asset event | `instance.report_runless_asset_event(AssetMaterialization(...))` | File upload |
| Create run | `instance.create_run_for_job(job_def, run_config, tags)` | Start Analysis button |
| Submit run | `instance.submit_run(run_id)` | Start Analysis button |
| Execute in-process | `job_def.execute_in_process(run_config, instance, tags)` | Fallback if daemon unavailable |

**Connection flow:**

1. **Initialization**: `get_dagster_instance()` in `state.py` creates a `DagsterInstance` using `DAGSTER_HOME` environment variable
2. **Shared storage**: Both UI and Dagster daemon read/write to the same SQLite database in `DAGSTER_HOME`
3. **No HTTP needed**: The UI imports Dagster Python API directly, avoiding REST/GraphQL complexity
4. **File-based outputs**: Output parquet files are written to filesystem by Dagster jobs, UI reads them directly

### Run-Centric UI Components

The right panel uses a run-centric design with three collapsible sections:

**State variables in `UploadState`:**
- `filtered_runs` - Computed var returning all runs for the selected file (sorted by date, newest first)
- `latest_run_id` - Computed var returning the run_id of the most recent run
- `output_files` - List of output file metadata for the selected sample
- `outputs_expanded` - Boolean controlling the outputs section collapse state
- `run_history_expanded` - Boolean controlling the run history section collapse state
- `new_analysis_expanded` - Boolean controlling the new analysis section collapse state
- `expanded_run_id` - Which run in the timeline is expanded to show details
- `file_metadata` - Dict mapping filenames to metadata (species, reference_genome, subject_id, study_name, notes, custom_fields)
- `current_custom_fields` - Computed var returning custom fields for the selected file
- `backend_api_url` - Computed var returning the backend API URL for downloads

**Component functions in `annotate.py`:**
- `outputs_section()` - Collapsible section showing output files with download buttons
- `output_file_card()` - Individual output file card with type icon, labels, and download
- `run_timeline_card()` - Individual run card with expand/collapse (latest run highlighted)
- `run_timeline()` - Unified scrollable list of all runs
- `new_analysis_section()` - Collapsible module selection and run button
- `right_panel_run_view()` - Main right panel combining all three sections
- `_collapsible_header()` - Reusable header component for foldable sections

**Layout Order (top to bottom):**
```
┌─────────────────────────────────────┐
│  Outputs (teal segment)             │  ← Results first - what users want
│  - File list with download buttons  │
│  - Empty state: "No outputs yet"    │
├─────────────────────────────────────┤
│  Run History (green segment)        │  ← Context - how results were made
│  - Latest run highlighted (blue)    │
│  - Re-run/Modify buttons on latest  │
│  - All runs in unified timeline     │
├─────────────────────────────────────┤
│  New Analysis (blue segment)        │  ← Action - start new work
│  - Module selection grid            │
│  - Start Analysis button            │
└─────────────────────────────────────┘
```

### Download API

File downloads are served via FastAPI endpoint at `{backend_api_url}/api/download/{user_id}/{sample_name}/{filename}`:
- **Backend URL**: Downloads use the full backend URL (default `http://localhost:8000`) since the frontend runs on port 3000 but the API is on port 8000
- Only parquet files are allowed
- Path traversal is prevented via input validation
- Uses `api_transformer` parameter in `rx.App()` to mount custom FastAPI routes
- Returns `FileResponse` for browser download

### Sample Metadata System

Each uploaded VCF file has associated metadata stored in `UploadState.file_metadata`:

| Field | Type | Description |
|-------|------|-------------|
| `species` | Dropdown | Latin scientific name (Homo sapiens, Mus musculus, etc.) |
| `reference_genome` | Dropdown | Assembly name based on species (GRCh38, T2T-CHM13v2.0, GRCh37) |
| `subject_id` | Text input | Patient/sample identifier |
| `study_name` | Text input | Project or study name |
| `notes` | Textarea | Free-form notes |
| `custom_fields` | Dict[str, str] | User-defined key-value pairs |

**Reference Genomes by Species:**
- **Homo sapiens**: GRCh38, T2T-CHM13v2.0, GRCh37
- **Mus musculus**: GRCm39, GRCm38
- **Rattus norvegicus**: mRatBN7.2, Rnor_6.0
- **Canis lupus familiaris**: ROS_Cfam_1.0, CanFam3.1
- **Felis catus**: Felis_catus_9.0, Felis_catus_8.0
- **Danio rerio**: GRCz11, GRCz10

### Key Design Decisions

1. **Run-Centric vs Tab-Based**: Replaced tab-based layout with run-centric view that shows the relationship between input files, runs, and outputs.
2. **Results First**: Outputs section at the top of the right panel - users care most about results, then context (runs), then actions (new analysis).
3. **Unified Run History**: Merged "Last Run" and "Run History" into a single timeline. The latest run is visually highlighted with a blue segment and "latest" badge.
4. **Inline Outputs vs Modal**: Outputs are displayed inline in a collapsible section rather than a modal dialog - no disruptive popups, always visible when expanded.
5. **In-Process Execution vs Daemon**: Prefers `instance.submit_run` for immediate Run ID feedback, with `execute_in_process` logic for robust execution without daemon dependency in local dev.
6. **Fomantic Checkboxes**: Uses raw HTML structure with `ui checkbox` classes to avoid `rx.checkbox` styling conflicts.
7. **Reactive Styling**: Uses `rx.cond` and `rx.match` for all state-dependent UI changes (colors, icons, visibility).
8. **Collapsible Sections**: All three right panel sections use the same `_collapsible_header()` pattern with chevron icons and right-aligned badges.

### Dagster API Patterns Used

- **Run Records**: Uses `instance.get_run_records` to access `start_time` and `end_time`.
- **Event Logs**: Uses `instance.all_logs(run_id)` for log retrieval.
- **Dynamic Partitions**: Registers user/sample combinations as dynamic partitions in Dagster.
- **Run Config**: Uses the `"ops"` key for asset job configuration.

### Known Issues & Fixed Items

- ~~**Job config error**~~: Fixed by using `"ops"` instead of `"assets"` in run config.
- ~~**Selected file persists after deletion**~~: Fixed in `UploadState.delete_file`.
- ~~**Download Link not working**~~: Fixed by using full backend URL (`http://localhost:8000/api/download/...`) instead of relative paths, since frontend (port 3000) and backend API (port 8000) are on different ports.
- ~~**Run history showing unknown filename**~~: Fixed by reading config from `"ops"` key instead of `"assets"`.
- **Log Scrolling**: Log container doesn't always auto-scroll to bottom on new entries.
- **ASGI "Connection already upgraded"**: When using Granian (`REFLEX_USE_GRANIAN=true` or `uv run start --granian`), the backend may log `RuntimeError: ASGI flow error: Connection already upgraded` during WebSocket handshake. This is a known Reflex+Granian interaction: the server tries to send an HTTP response after the connection was already upgraded to WebSocket. The app usually continues to work; if it causes problems, run without Granian (default `uv run start` uses the built-in server).

### How to Run

```bash
# Start both Web UI and Dagster
uv run start
```

- Web UI: http://localhost:3000
- Dagster UI: http://localhost:3005

### Next Steps

1. **Implement Auto-scroll for Logs**: Ensure the log window follows the latest output.
2. **Advanced Filtering**: Add ability to filter files by upload date or status.
3. **Analysis Page**: Implement the `analysis` page to visualize annotation results (plots, stats).
4. **Output File Preview**: Add ability to preview parquet file contents (first N rows) in the UI.
