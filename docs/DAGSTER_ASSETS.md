# Dagster Assets vs Ops: Ensembl Annotations

## ✅ What Changed

You were absolutely right! The **Ensembl reference data** should be modeled as a **Dagster Asset**, not just an op output.

### Before (Op-based):
```python
@op
def download_ensembl_annotations_op(config) -> Path:
    # Downloads data, but treated as ephemeral
    ...
```

### After (Asset-based):
```python
@asset
def ensembl_annotations(config) -> Output[Path]:
    # Persistent data product that can be materialized and tracked
    ...
```

## 🎯 Why Assets for Reference Data?

### Assets are for Data Products:
- **Persistent**: Ensembl data lives on disk and is reused across runs
- **Versioned**: Dagster tracks when it was last materialized
- **Cacheable**: Only re-download if forced or stale
- **Observable**: View metadata (size, file count) in the UI
- **Dependencies**: Other jobs/assets can depend on it

### Ops are for Transformations:
- **Ephemeral**: Process data and pass results
- **Per-run**: Execute every time a job runs
- **Transient**: Outputs aren't tracked as persistent data products

## 📊 What You Get in Dagster UI

### 1. Assets Tab
Navigate to **Assets** → **ensembl_annotations**

You'll see:
- ✅ **Materialization history**: When was it last downloaded?
- ✅ **Metadata**:
  - `cache_path`: Where the data lives
  - `num_files`: How many parquet files
  - `total_size_gb`: Total dataset size
  - `download_duration_sec`: How long it took
  - `download_cpu_percent`: Resource usage
- ✅ **Status**: `cached` or `downloaded`
- ✅ **Lineage**: What jobs/assets depend on this

### 2. Materialize the Asset
- Click **Materialize** button
- Dagster will:
  1. Check if cache exists
  2. Skip download if present (unless `force_download=true`)
  3. Track the materialization with metadata

### 3. Use in Jobs
The job `annotate_vcf_with_ensembl_job` can now reference the asset:
- If asset is already materialized → Use cached data
- If not materialized → Dagster can auto-materialize it

## 🚀 How to Use

### Option 1: Materialize Asset First (Recommended)
```bash
uv run dagster-ui
```

1. Go to **Assets** tab
2. Select **ensembl_annotations**
3. Click **Materialize**
4. View metadata after completion

### Option 2: Run Job (Legacy)
The old job-based flow still works:
1. Go to **Jobs** → **annotate_vcf_with_ensembl_job**
2. Click **Launchpad** → Launch
3. Job will download Ensembl data as part of execution

### Option 3: Programmatic
```python
from dagster import materialize

# Materialize the asset
result = materialize([ensembl_annotations])
```

## 📦 Architecture

```
┌─────────────────────────────────────┐
│  ensembl_annotations (Asset)        │
│  - Persistent reference data        │
│  - Materialized once, reused many   │
│  - Tracked with metadata            │
└──────────────┬──────────────────────┘
               │ depends on
               ▼
┌─────────────────────────────────────┐
│  annotate_vcf_with_ensembl_job      │
│  (Job)                              │
│  - Uses the asset                   │
│  - Processes VCF files              │
│  - Creates annotated output         │
└─────────────────────────────────────┘
```

## 🔄 Future: Full Asset Pipeline

The next evolution would be to make the **annotated VCF** an asset too:

```python
@asset(deps=[ensembl_annotations])
def annotated_vcf(ensembl_annotations: Path, vcf_path: str):
    # Join VCF with Ensembl annotations
    # Return annotated parquet
    ...
```

This way, Dagster tracks both:
- **Input**: ensembl_annotations (reference)
- **Output**: annotated_vcf (result)

And you get full data lineage!

