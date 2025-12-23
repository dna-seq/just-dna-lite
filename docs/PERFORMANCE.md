# Performance and Resource Tracking

Notes on performance tuning and how to read the metrics emitted by the annotation pipeline.

## 1. Resource Tracking
Many pipeline operations are wrapped in `resource_tracker` to capture basic system metrics.

### What is tracked
- Duration (wall clock)
- CPU% (can exceed 100% on multi-core)
- Peak RAM
- Output file metadata (size / rows / columns)

### Where to view it
In Dagster UI, open an asset materialization (or op) and check the Metadata tab.

---

## 2. Engines: Polars vs. DuckDB

We provide two distinct engines for the annotation join.

### Polars (Default)
- Logic: `annotate_vcf_with_ensembl`
- Implementation: Polars LazyFrames + streaming Parquet writes
- Trade-off: fastest when the join fits in RAM; may OOM on join explosion / low-RAM environments

### DuckDB (Streaming)
- Logic: `annotate_vcf_with_duckdb`
- Implementation: DuckDB views over Parquet + `COPY ... TO ... (FORMAT PARQUET)` for streaming
- Trade-off: low memory usage; slightly slower for small/medium files

---

## 3. DuckDB Memory Optimizations

The DuckDB engine is tuned for out-of-core (larger than RAM) processing:

1.  Views instead of tables: we don't copy Parquet data into DuckDB. We create views that reference the files directly. DuckDB uses Parquet metadata for efficient filtering.
2.  Auto-config: we detect system RAM and CPU count to set DuckDB's `memory_limit` and `threads`.
    - Default: 75% of system resources, clamped to sane bounds (e.g., 8GB - 128GB).
3.  Direct streaming: the join result is never collected into a Python object. It streams from `Input Parquet -> DuckDB Join -> Output Parquet`.

---

## 4. When to Use Which?

| Scenario | Recommended Engine |
|----------|--------------------|
| Standard user VCF (WGS/WES) | Polars |
| Low-RAM VPS / Docker | DuckDB |
| Joining 5+ different databases | DuckDB |
| Massive cohort analysis | DuckDB |

## 5. Benchmarking
To run your own benchmarks, you can use the provided test:
```bash
uv run pytest just-dna-pipelines/tests/test_duckdb_memory.py -vvv
```
This test verifies that the DuckDB engine stays within memory bounds and correctly uses streaming VIEWs.

