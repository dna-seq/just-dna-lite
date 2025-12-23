# Dagster Resource Metrics - What You'll See

## ✅ What's Now Available in Dagster UI

When you run your annotation job through `uv run dagster-ui`, you'll now see **rich metadata** on each operation:

### 📊 Op Output Metadata (in the UI)

For the `annotate_lazyframe_with_ensembl_op` step, you'll see:

```yaml
output_file: /path/to/data/output/antku_small_annotated.parquet
file_size_mb: 0.03
num_columns: 45
compression: zstd

# 🆕 NEW RESOURCE METRICS:
duration_sec: 9.98
cpu_percent: 2803.7
peak_memory_mb: 19899.46
memory_delta_mb: +150.23
```

### 📝 Logs (in the terminal/UI logs tab)

You'll still see the detailed resource reports in logs:

```
📊 Resource Report [Download Ensembl Reference]: Duration: 0.02s, CPU: 46.1%, Peak RAM: 257.87MB
📊 Resource Report [Load VCF]: Duration: 0.04s, CPU: 146.6%, Peak RAM: 327.47MB  
📊 Resource Report [Annotate with Ensembl]: Duration: 9.98s, CPU: 2803.7%, Peak RAM: 19899.46MB
```

## 🎯 Key Benefits

1. **File Metadata**: See output path, size, columns directly in UI
2. **Resource Tracking**: CPU%, memory usage, duration for each step
3. **No Data Collection**: All metrics computed without `.collect()` on large data
4. **Historical Tracking**: Dagster stores this for all runs, so you can compare performance

## 🚀 How to View in UI

1. Start Dagster: `uv run dagster-ui`
2. Navigate to http://localhost:3005
3. Go to **Jobs** → **annotate_vcf_with_ensembl_job**
4. Click **Launchpad** → Configure & Launch
5. After run completes, click on the run
6. Click on each op → **Metadata** tab

You'll see all the metrics beautifully formatted!

