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

## Annotation pipeline in this repo

Our annotation logic (`just-dna-pipelines/src/just_dna_pipelines/annotation/`) uses these concepts to provide a robust, multi-user system.

### The Asset Graph
1. `ensembl_hf_dataset`: external asset representing the Hugging Face dataset.
2. `ensembl_annotations`: local cache materialized from the external source.
3. `user_vcf_source`: partitioned source asset for input VCFs.
4. `user_annotated_vcf`: join of reference + input into an annotated Parquet.

### Why both assets and jobs?
You’ll see `assets.py` plus `ops.py` / `jobs.py`:

- `assets.py`: the main, declarative pipeline (best for tracking and automation).
- `ops.py` / `jobs.py`: job-style entry points used by the UI for ad-hoc runs with parameters that don't always fit the asset-partition model.

---

## Performance: Polars vs DuckDB

We provide two engines for annotation. This is a great example of Dagster's flexibility:

| Engine | Implementation | Best For |
|--------|----------------|----------|
| Polars | `user_annotated_vcf` | Fast when the join fits in RAM. |
| DuckDB | `user_annotated_vcf_duckdb` | Low-memory / large joins; streams from disk. |

DuckDB uses VIEWs over Parquet and writes the join result directly to Parquet, so it doesn't need to hold the join output in a Python object.

---

## Developer workflow

### Adding a new data module
Modules are discovered via the registry in `registry.py`. A module typically provides a Dagster `Definitions` object.

### Monitoring & Metrics
Each run in our Dagster setup automatically tracks:
* CPU% and peak RAM (via `resource_tracker`)
* file metadata (output size, row count)
* lineage (which reference cache was used for a given user output)

## Commands

* Start everything: `uv run start`
* Start Dagster UI: `uv run dagster-ui`
* Materialize an asset (CLI):
    ```bash
    uv run dagster asset materialize --select ensembl_annotations
    ```
* Add partitions (CLI):
    ```bash
    uv run dagster instance add-dynamic-partitions user_vcf_files "user1/sample1"
    ```

## Environment variables

* `DAGSTER_HOME`: Dagster instance storage (default: `data/interim/dagster/`).
* `JUST_DNA_PIPELINES_CACHE_DIR`: base directory for reference caches.
* `JUST_DNA_PIPELINES_OUTPUT_DIR`: base directory for user outputs.
* `JUST_DNA_PIPELINES_INPUT_DIR`: base directory for user inputs.
* `HF_TOKEN`: Hugging Face token (needed for private datasets).

---

For more details:

* `docs/PERFORMANCE.md`
* `docs/CLEAN_SETUP.md`

