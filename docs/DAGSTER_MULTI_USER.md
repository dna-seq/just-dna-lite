# Dagster Multi-User Architecture

This document explains how the Dagster pipeline handles multiple users and data storage.

## Storage Architecture

### Dagster Home

Dagster stores its internal data (run history, event logs, schedules) in:

```
data/interim/dagster/
```

This is set via `DAGSTER_HOME` environment variable (automatically configured by the CLI).

**Configuration File**: On first run, the CLI automatically creates `data/interim/dagster/dagster.yaml` with:
- Auto-materialization enabled for assets with `AutoMaterializePolicy`
- Minimum interval of 60 seconds between auto-materializations

You can customize this config by modifying the file. See `dagster.yaml.template` in the repo root for all available options.

### Three IO Managers

| Storage Type | Location | IO Manager | Purpose |
|-------------|----------|------------|---------|
| **Source Metadata** | In-memory only | `source_metadata_io_manager` | Lightweight VCF source tracking |
| **Annotation Cache** | `~/.cache/just-dna-pipelines/` | `annotation_cache_io_manager` | Reference data (Ensembl, ClinVar, etc.) |
| **User Output** | `data/output/users/{user_name}/{sample_name}/` | `user_asset_io_manager` | Per-user annotated VCFs |

You can override these paths with environment variables:
- `DAGSTER_HOME` → Dagster internal storage (default: `data/interim/dagster/`)
- `JUST_DNA_PIPELINES_CACHE_DIR` → Custom cache location
- `JUST_DNA_PIPELINES_OUTPUT_DIR` → Custom output location

### Reference Assets (Cache)

Reference data like Ensembl annotations are stored in the cache folder:

```
~/.cache/just-dna-pipelines/
├── ensembl_variations/
│   └── splitted_variants/
│       └── SNV/
│           ├── snp-chr1.parquet
│           ├── snp-chr2.parquet
│           └── ...
├── clinvar/          # Future
└── dbsnp/            # Future
```

**Lazy Materialization**: If the cache already exists, the asset skips download.

### User Assets (Output)

User-specific annotated VCFs are organized by username and sample name:

```
data/output/users/
├── anton/
│   ├── sample1/
│   │   └── user_annotated_vcf.parquet
│   └── sample2/
│       └── user_annotated_vcf.parquet
├── maria/
│   └── genome/
│       └── user_annotated_vcf.parquet
└── john/
    └── wgs/
        └── user_annotated_vcf.parquet
```

**Partition Keys**: `{user_name}/{sample_name}` (e.g., `anton/sample1`)

## Assets

### `ensembl_hf_dataset` (External Source Asset)

External HuggingFace dataset that serves as the **source of truth**. This is an `AssetSpec` that:
- Represents the remote HuggingFace repository in the asset graph
- Establishes clear data lineage for downstream assets

```
Data Lineage: HF Repo (source) → Local Cache → User Analysis
```

### `user_vcf_source` (Source Asset)

Materializable source asset that tracks VCF files in the input directory.

**Storage**: Metadata only (no disk persistence via `source_metadata_io_manager`)
**Partitions**: Dynamic (`user_vcf_files` partition definition)
**Partition Key**: `{user_name}/{sample_name}` (e.g., `antonkulaga/antonkulaga`)

**Auto-discovery**: A sensor (`discover_user_vcf_sensor`) scans `data/input/users/` every minute and automatically creates partitions for any VCF files found.

**Input structure:**
```
data/input/users/
├── antonkulaga/
│   ├── antonkulaga.vcf      → Partition: antonkulaga/antonkulaga
│   └── sample2.vcf          → Partition: antonkulaga/sample2
└── maria/
    └── genome.vcf           → Partition: maria/genome
```

### `ensembl_annotations` (Reference Asset)

Downloads and caches Ensembl variation database from HuggingFace. **Depends on `ensembl_hf_dataset`** for data lineage.

```python
# Materialization: Downloads if not cached, skips if exists
defs.get_job_def("__ASSET_JOB").execute_in_process(
    asset_selection=[AssetKey("ensembl_annotations")]
)
```

**Metadata displayed in UI:**
- `cache_path` - Where data is stored
- `num_files` - Number of parquet files
- `total_size_gb` - Total dataset size
- `status` - "cached" or "downloaded"

### `user_annotated_vcf` (Partitioned User Asset)

Dynamically partitioned asset for per-user VCF annotations.

**Partition Key**: `{user_name}/{sample_name}` (e.g., `antonkulaga/antonkulaga`)

**Configuration:**

```python
class AnnotationConfig(Config):
    vcf_path: str           # Path to user's VCF file
    user_name: str = None   # Optional: User identifier (defaults to partition_key)
    variant_type: str = "SNV"
    compression: str = "zstd"
    output_path: str = None  # Optional: Custom output path
```

**Metadata displayed in UI:**
- `user_name` - User identifier
- `partition_key` - Dagster partition key
- `source_vcf` - Input VCF path
- `output_file` - Output parquet path
- `file_size_mb` - Output file size
- `duration_sec`, `cpu_percent`, `peak_memory_mb` - Resource metrics

## Sensors

### `discover_user_vcf_sensor`

Automatically scans `data/input/users/` for VCF files and creates partitions.

- **Frequency**: Every 60 seconds
- **Partition naming**: `{user_name}/{sample_name}` where:
  - `user_name` = directory name under `data/input/users/`
  - `sample_name` = VCF filename without extension
- **Action**: Creates new partitions for any discovered VCF files

**Example**: If you add `data/input/users/john/wgs.vcf`, the sensor will automatically create partition `john/wgs`.

## Jobs

### `annotate_vcf_job`

Simple job for ad-hoc annotation without partition tracking.

**Launch via UI:**
1. Go to Jobs → `annotate_vcf_job`
2. Click "Launchpad"
3. Configure:

```yaml
ops:
  annotate_user_vcf_op:
    config:
      vcf_path: "/path/to/user.vcf"
      user_name: "anton"  # Organizes output in data/output/users/anton/
```

4. Click "Launch Run"

## Usage Examples

### Start Dagster UI

```bash
uv run dagster dev -f just-dna-pipelines/src/just_dna_pipelines/annotation/definitions.py -p 3005
```

### Add a New User Partition (Automatic)

**Recommended**: Just place your VCF file in the correct location and let the sensor discover it:

```bash
# Place VCF in user directory
mkdir -p data/input/users/anton
cp /path/to/my-sample.vcf data/input/users/anton/

# Wait up to 60 seconds for the sensor to run
# Check Dagster UI → Sensors → discover_user_vcf_sensor
# The partition "anton/my-sample" will be created automatically
```

### Add a New User Partition (Manual - Legacy)

If you need to add partitions programmatically without the sensor:

```python
from dagster import DagsterInstance

instance = DagsterInstance.get()
instance.add_dynamic_partitions("user_vcf_files", ["anton/sample1", "maria/genome", "john/wgs"])
```

### Materialize User Asset

```python
from just_dna_pipelines.annotation.definitions import defs
from dagster import AssetKey

result = defs.get_job_def("__ASSET_JOB").execute_in_process(
    partition_key="anton/my-sample",  # Updated format: user_name/sample_name
    asset_selection=[AssetKey("user_annotated_vcf")],
    run_config={
        "ops": {
            "user_annotated_vcf": {
                "config": {
                    "vcf_path": "data/input/users/anton/my-sample.vcf",
                    "user_name": "anton",
                    "sample_name": "my-sample"
                }
            }
        }
    }
)
```

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                       DAGSTER DEFINITIONS                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  SOURCE ASSETS (External)                                           │
│  └── ensembl_hf_dataset  ◄─────── HuggingFace Hub (source of truth) │
│      (AssetSpec)                   just-dna-seq/ensembl_variations  │
│                    │                                                │
│                    ▼ (depends on)                                   │
│  ASSETS                                                             │
│  ├── ensembl_annotations  ─────────► ~/.cache/just-dna-pipelines/            │
│  │   (io: annotation_cache_io_manager)    (lazy download)          │
│  │                                                                  │
│  └── user_annotated_vcf  ─────────► data/output/users/{user}/      │
│      (io: user_asset_io_manager)                                    │
│      (partitioned by user_name)                                     │
│                                                                     │
│  JOBS                                                               │
│  └── annotate_vcf_job  ─────────► data/output/users/{user}/        │
│      (for ad-hoc annotation)                                        │
│                                                                     │
│  IO MANAGERS                                                        │
│  ├── annotation_cache_io_manager  (reference data in cache)        │
│  └── user_asset_io_manager        (user data in output)            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Benefits

1. **Clear Data Separation**
   - Reference data → Cache (shared, downloaded once)
   - User data → Output (organized by user)

2. **Lazy Loading**
   - Skip download if cache exists
   - Fast restarts

3. **Persistence**
   - Data survives Dagster restarts
   - No Dagster internal storage pollution

4. **Environment Override**
   - `DAGSTER_HOME` for Dagster internal storage
   - `JUST_DNA_PIPELINES_CACHE_DIR` for custom cache
   - `JUST_DNA_PIPELINES_OUTPUT_DIR` for custom output

5. **Clear Data Lineage**
   - HuggingFace repos represented as external source assets
   - Visible lineage in Dagster UI: `HF Repo → Local Cache → User Analysis`
