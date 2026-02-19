# Dagster in just-dna-lite

This repo uses Dagster for one reason: make data products (reference caches and per-user outputs) explicit, reproducible, and inspectable.

If you're coming from Prefect/Airflow/scripts, the main shift is: dependencies are expressed as data assets, not task wiring.

| Feature | Prefect / Airflow | Dagster |
|---------|-------------------|---------|
| Core unit | Task / op (imperative) | Asset (declarative) |
| Focus | How to run a function | What data should exist |
| **Lineage** | Manual / Task dependencies | Automatic / Data dependencies |
| Storage | You handle file paths | IO managers handle storage |
| State | External database | Built-in asset catalog |

In Prefect, you might write `task_a >> task_b`. In Dagster, `asset_b` simply declares that it takes `asset_a` as an input. Dagster then knows it must materialize `asset_a` before `asset_b`.

## Why Dagster for a genomic app store

For a platform where users install annotation modules (ClinVar, gnomAD, custom panels, …), Dagster's asset-centric model maps well:

- Each module ships as a `Definitions` bundle; the platform merges them into one graph.
- Lineage answers "which Ensembl snapshot + module version produced this output?" without custom logging.
- Dynamic partitions model "user/sample" so backfills and deletions are scoped per-user.
- IO managers enforce storage contracts; modules don't fight over paths.
- Auto-materialize policies can trigger downstream annotation when a new reference is ingested.

Prefect would require manually layering these concerns (asset catalog, path conventions, partition logic) on top of its run-centric core.

## Key concepts used here

### Software-Defined Assets (SDA)
Most pipeline outputs are assets. An asset is a function that produces a persistent data product (file / dataset).

- `ensembl_annotations`: reference cache under `JUST_DNA_PIPELINES_CACHE_DIR` (default is your user cache).
- `user_annotated_vcf`: per-user result under `data/output/users/` (or `JUST_DNA_PIPELINES_OUTPUT_DIR`).

### IO Managers: No More Manual Paths
In this codebase, assets don't hardcode output locations. IO managers decide where assets live on disk:

1. An asset returns a value (usually a `Path`).
2. An IO manager writes it to the configured location.
3. Downstream assets load via the same IO manager.

### Dynamic Partitions
For multi-user support, we use **Dynamic Partitions**. Each partition key (e.g., `anton/my_sample`) represents a separate instance of an asset. This allows us to track, materialize, and delete data for one user without touching others.

---

## Annotation Pipelines

Our annotation logic (`just-dna-pipelines/src/just_dna_pipelines/annotation/`) provides two annotation systems:

### 1. Ensembl Annotations (Legacy)

Position-based annotation using Ensembl variation database.

**Asset Graph:**
1. `ensembl_hf_dataset`: External HuggingFace dataset source
2. `ensembl_annotations`: Local cache from HuggingFace
3. `user_vcf_source`: Partitioned source for input VCFs
4. `user_annotated_vcf`: Annotated output (Polars-based)
5. `user_annotated_vcf_duckdb`: Alternative DuckDB-based annotation

### 2. HuggingFace Module Annotations (Recommended)

Self-contained annotation modules auto-discovered from configured sources (see `modules.yaml` at the project root, or `just-dna-pipelines/src/just_dna_pipelines/modules.yaml` as fallback). The default source is [just-dna-seq/annotators](https://huggingface.co/datasets/just-dna-seq/annotators), but any fsspec-compatible URL (GitHub, HTTP, S3, etc.) can be added.

**Available Modules** (auto-discovered, run `uv run pipelines list-modules` for current list):
- `longevitymap`: Longevity-associated variants
- `lipidmetabolism`: Lipid metabolism and cardiovascular risk
- `vo2max`: Athletic performance variants
- `superhuman`: Elite performance variants
- `coronary`: Coronary artery disease associations

Module display metadata (titles, icons, colors) is configured in `modules.yaml` (at the project root). New modules added to any configured source are auto-discovered without code changes.

**Asset Graph:**
1. `hf_annotators_dataset`: External HuggingFace modules source
2. `user_vcf_source`: Partitioned source for input VCFs (metadata: path, size, upload date)
3. `user_vcf_normalized`: Normalized VCF as parquet (strip chr prefix, id→rsid, genotype); **required** before HF annotation
4. `user_hf_module_annotations`: Partitioned annotation output (one parquet per module)
5. `user_longevity_report`: HTML report generated from annotated parquets (depends on `user_hf_module_annotations`)

**Execution order:** For each partition (e.g. `anonymous/other_livia`), Dagster runs: `user_vcf_normalized` → `user_hf_module_annotations` → `user_longevity_report`. The HF annotation asset **requires** `user_vcf_normalized` as input; if the parquet does not exist, the IO manager raises `FileNotFoundError`.

**Key Features:**
- No Ensembl join required (modules are self-contained)
- Position-based joining (works with VCFs without rsids)
- Genotype-aware scoring (matches on sorted allele lists)
- Memory-efficient streaming with lazy Polars
- Supports local VCF files or Zenodo URLs as input source
- **Report generation**: HTML reports from annotated parquets with expandable variant details

See [HF_MODULES.md](HF_MODULES.md) for detailed documentation.

### 3. Report Generation

Report assets depend on annotation outputs and produce self-contained HTML reports.

**Asset Graph:**
1. `user_hf_module_annotations` → `user_longevity_report`

**Implementation:**
- `report_logic.py`: Reads annotated parquets, enriches with HF annotations/studies tables, builds data structures
- `report_assets.py`: Dagster asset definition with partition support
- `templates/longevity_report.html.j2`: Jinja2 template for the HTML report

**Report structure:**
- **Longevity variants** grouped by 12 pathway categories (lipids, insulin, antioxidant, mitochondria, sirtuin, mTOR, tumor-suppressor, renin-angiotensin, heat-shock, inflammation, genome maintenance, other)
- **Other modules** (lipidmetabolism, coronary, vo2max, superhuman) as flat variant tables
- Summary statistics (total/positive/negative variants, net weight)
- Expandable detail rows with study evidence from PubMed

**Output:**
```
data/output/users/{user}/{sample}/reports/longevity_report.html
```

### 4. VCF Normalization (user_vcf_normalized)

Before HF module annotation, the raw VCF is normalized and persisted as parquet. This avoids re-parsing the VCF for the UI preview and for the annotation pipeline.

**Normalization steps:**
1. Strip `chr` prefix from chromosome column (case-insensitive: `chr1` → `1`, `CHR1` → `1`)
2. Rename `id` column to `rsid`
3. Compute genotype column from GT + REF + ALT as `List[String]` sorted alphabetically

**Output path:**
```
data/output/users/{partition_key}/user_vcf_normalized.parquet
```
Example: `data/output/users/anonymous/other_livia/user_vcf_normalized.parquet`

**Jobs:**
- `normalize_vcf_job`: Normalize only (runs automatically on upload in the Web UI)
- `annotate_and_report_job`: Full pipeline (normalize → annotate → report)

**When normalize runs:**
- On upload: The Web UI runs `normalize_vcf_job` in-process after each VCF upload.
- With full pipeline: `annotate_and_report_job` materializes `user_vcf_normalized` first, then downstream assets.

**If normalized parquet is missing:**
- `user_hf_module_annotations` will fail with `FileNotFoundError` when loading via IO manager (no silent fallback in the pipeline).
- Web UI preview: Should show an error or explicit fallback notice — **never silently display raw VCF as if it were normalized**. See "Avoid silent fallbacks" in AGENTS.md.

**Running normalize manually (CLI):**
```bash
# From workspace root, with DAGSTER_HOME set
uv run dg asset materialize --select user_vcf_normalized --partition "user_id/sample_name"
```
Or use a small script that calls `job_def.execute_in_process()` with the correct run config and partition tag (see `webui/state.py` `_normalize_vcf_sync` for the pattern).

**Known quirk (polars-bio) — FIXED:** The `ALLELE_ID` INFO field (Number=R, common in DRAGEN VCFs) triggers a Rust panic in `OptionalField::append_array_string_iter` when REF has value `.` (e.g. `ALLELE_ID=.,NM_000157.4:c.1604G>A`). We exclude `ALLELE_ID` from auto-detected INFO fields in `io.get_info_fields()` via `_VCF_INFO_BLOCKLIST`. If you see similar panics with other fields, add them to the blocklist in `just_dna_pipelines/io.py`.

**Report jobs:**
- `generate_longevity_report_job`: Generate report only (requires prior annotation materialization)
- `annotate_and_report_job`: Full pipeline — normalize + annotate VCF + generate report in one run

### Why both assets and jobs?

You'll see `assets.py` plus `ops.py` / `jobs.py`:

- `assets.py`: the main, declarative pipeline (best for tracking and automation).
- `ops.py` / `jobs.py`: job-style entry points used by the UI for ad-hoc runs with parameters that don't always fit the asset-partition model.

---

## Performance & Engine Optimization

We provide two distinct engines for the annotation join, selectable via configuration.

| Engine | Implementation | Best For |
| :--- | :--- | :--- |
| **Polars (Default)** | `user_annotated_vcf` | Fast when the join fits in RAM. |
| **DuckDB (Streaming)** | `user_annotated_vcf_duckdb` | Low-memory / large joins; streams from disk. |

### Polars
*   **Logic**: `annotate_vcf_with_ensembl`
*   **Implementation**: Polars LazyFrames + streaming Parquet writes.
*   **Trade-off**: Fastest when the join fits in RAM; may OOM on join explosion or in low-RAM environments.

### DuckDB
*   **Logic**: `annotate_vcf_with_duckdb`
*   **Implementation**: DuckDB views over Parquet + `COPY ... TO ... (FORMAT PARQUET)` for streaming.
*   **Trade-off**: Low memory usage; slightly slower for small/medium files.

#### DuckDB Memory Optimizations
The DuckDB engine is tuned for out-of-core processing:
1.  **Views instead of tables**: We create views that reference Parquet files directly without copying data into DuckDB.
2.  **Auto-config**: Detects system RAM and CPU count to set DuckDB's `memory_limit` and `threads` (defaults to 75% of system resources).
3.  **Direct streaming**: The join result streams from `Input Parquet -> DuckDB Join -> Output Parquet` without being collected in Python.

---

## Hugging Face Integration & Authentication

The pipeline pulls reference data (like Ensembl shards) from Hugging Face Hub. This data is prepared and maintained using the [dna-seq/prepare-annotations](https://github.com/dna-seq/prepare-annotations) upstream repository.

### Authentication
If the dataset is private or you encounter rate limits, set your Hugging Face token:
```bash
export HF_TOKEN="your_token_here"
```

### Resource Caching
The `ensembl_annotations` asset downloads reference shards into a local cache.
*   **Default Location**: Your OS user cache for `just-dna-pipelines`.
*   **Override**: Set `JUST_DNA_PIPELINES_CACHE_DIR`.

---

## Monitoring & Metrics

Each run in our Dagster setup automatically tracks:
*   **Resource Usage**: CPU% and peak RAM via `resource_tracker`.
*   **File Metadata**: Output size, row count, and column schema.
*   **Lineage**: Which reference cache was used for a given user output.

---

## Developer workflow

### Adding a new data module
Modules are discovered via the registry in `registry.py`. A module typically provides a Dagster `Definitions` object.

---

## Commands

*   Start everything: `uv run start`
*   Start Dagster UI: `uv run dagster-ui`
*   Materialize an asset (CLI):
    ```bash
    uv run dg asset materialize --select ensembl_annotations
    ```
*   Add partitions (CLI):
    ```bash
    uv run dg instance add-dynamic-partitions user_vcf_files "user1/sample1"
    ```
*   **Normalize VCF (when parquet missing):**
    Run `normalize_vcf_job` for a partition so the Web UI preview and HF annotation use normalized data:
    ```bash
    # Ensure DAGSTER_HOME is set (default: data/interim/dagster)
    uv run dg asset materialize --select user_vcf_normalized --partition "user_id/sample_name"
    ```
    Partition key format: `{user_id}/{sample_name}` (e.g. `anonymous/other_livia`). Sample name is filename stem (e.g. `other_livia.vcf.gz` → `other_livia`).
*   **Annotate with HF modules (CLI):**
    ```bash
    # Local VCF
    uv run pipelines annotate-modules --vcf /path/to/sample.vcf --user myuser

    # From Zenodo (Recommended for personal health data)
    uv run pipelines annotate-modules \
        --zenodo https://zenodo.org/records/18370498 \
        --user antonkulaga

    # From HuggingFace
    uv run pipelines annotate-modules \
        --hf-source some-repo/data/sample.vcf \
        --user someuser

    # Specific modules only
    uv run pipelines annotate-modules --vcf /path/to/vcf --user myuser --modules longevitymap,coronary
    ```
*   **List available modules:**
    ```bash
    uv run pipelines list-modules
    ```

---

## Environment variables

*   `DAGSTER_HOME`: Dagster instance storage (default: `data/interim/dagster/`).
*   `JUST_DNA_PIPELINES_CACHE_DIR`: base directory for reference caches.
*   `JUST_DNA_PIPELINES_OUTPUT_DIR`: base directory for user outputs.
*   `JUST_DNA_PIPELINES_INPUT_DIR`: base directory for user inputs.
*   `HF_TOKEN`: Hugging Face token (needed for private datasets).

---

For more details:
*   `docs/CLEAN_SETUP.md`
*   `docs/HF_MODULES.md`
*   `docs/DESIGN.md`
