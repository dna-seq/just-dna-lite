# Web UI Implementation Status

## Current State

**Single-page genomic annotation app** with a 3-column layout using Fomantic UI styling + CSS flexbox.

### What's Working

1. **3-column layout** - Files (left), Modules (center), Results (right) - side-by-side with independent scrolling
2. **Horizontal top menu** - Logo, nav links (Annotate, Analysis), external buttons (Dagster, Fork on GitHub)
3. **File management** - Upload zone, file library with status badges, delete buttons
4. **Module selection** - 5 modules with checkboxes, icons, titles, descriptions, Select All/None buttons
5. **Fomantic UI checkboxes** - Properly styled using Fomantic structure (not rx.checkbox)
6. **Module icons** - Dynamic icons via `rx.match()` (heart, droplets, heart-pulse, zap, activity)
7. **Status polling** - Background polling for run status updates

### Known Issues (TODO)

1. ~~**Job config error**~~ - **FIXED**: Changed `"assets"` to `"ops"` in config

2. **Selected file persists after deletion** - When a file is deleted, `selected_file` should be cleared

3. **Granian websocket errors** - Still occurring occasionally, use `REFLEX_USE_GRANIAN=false`

### Architecture

```
webui/
├── src/webui/
│   ├── components/
│   │   └── layout.py          # topbar(), template(), three_column_layout()
│   ├── pages/
│   │   ├── annotate.py        # Main 3-column page components
│   │   ├── index.py           # Home page (uses annotate components)
│   │   ├── analysis.py        # Analysis page (placeholder)
│   │   └── dashboard.py       # Old dashboard (not used)
│   ├── state.py               # UploadState, AuthState, Dagster API calls
│   └── app.py                 # Reflex app setup
└── rxconfig.py                # Fomantic UI CSS/JS via CDN
```

### Key Design Decisions

1. **Flexbox instead of Fomantic Grid** - Fomantic UI grid doesn't work reliably in Reflex (columns stack vertically)
2. **Fomantic checkbox structure** - Must use `rx.el.div(rx.el.input(type="checkbox"), rx.el.label(), class_name="ui checkbox")` not `rx.checkbox()`
3. **Dynamic icons via rx.match()** - `rx.icon()` requires static string names, use `rx.match()` for dynamic selection

### Dagster API Gotchas (Discovered)

```python
# Timestamps on RunRecord, not DagsterRun
records = instance.get_run_records(limit=10)
started = datetime.fromtimestamp(record.start_time)

# Partition key via tags
run = instance.create_run_for_job(job_def=job, tags={"dagster/partition": pk})

# submit_run without workspace_snapshot (removed in newer Dagster)
instance.submit_run(run.run_id)  # NOT: workspace_snapshot=None

# Run logs via all_logs
events = instance.all_logs(run_id)
```

### Files Modified in This Session

| File | Changes |
|------|---------|
| `webui/src/webui/components/layout.py` | Flexbox topbar, 3-column layout with scroll |
| `webui/src/webui/pages/annotate.py` | Module cards with icons, Fomantic checkboxes |
| `webui/src/webui/pages/index.py` | Uses new annotate components |
| `webui/src/webui/state.py` | Removed `workspace_snapshot=None`, added `running` flag |
| `docs/DESIGN.md` | Fomantic UI + Reflex patterns (flexbox, checkbox structure) |
| `AGENTS.md` | Fomantic UI gotchas, Dagster API updates |

### How to Run

```bash
cd /home/antonkulaga/sources/just-dna-lite
REFLEX_USE_GRANIAN=false uv run start
```

- Web UI: http://localhost:3000
- Dagster UI: http://localhost:3005

### Next Steps

1. ~~**Fix job config**~~ - **DONE**: Changed `"assets"` to `"ops"` in `start_annotation_run`
2. **Clear selected_file on delete** - In `delete_file`, set `self.selected_file = ""` if matching
3. **Add run history display** - Show actual run history for selected file in Results column
4. **Console output** - Populate console with real-time logs during run
5. **Test full annotation flow** - Verify HF module annotation completes successfully
