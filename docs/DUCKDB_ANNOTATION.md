# DuckDB-Based Annotation

This document describes the DuckDB-based annotation assets, which provide an alternative to the Polars-based annotation pipeline.

## Overview

The DuckDB annotation approach offers several potential benefits:

- **Better join optimization** for large-scale genomic data
- **More predictable memory usage** for out-of-core processing
- **Native support for interval/range joins** (for future enhancements)
- **Easier multi-source annotation** (ClinVar + Ensembl + dbSNP + etc.)

## Assets

### `ensembl_duckdb`

Creates an indexed DuckDB database from Ensembl Parquet files.

**Dependencies:**
- `ensembl_annotations` (must be materialized first)

**Output:**
- `~/.cache/just-dna-pipelines/ensembl_annotations/ensembl_variations.duckdb`

**Features:**
- Creates separate tables for SNV and INDEL variants
- Builds indexes on `chrom` and `(chrom, start, ref, alt)` for faster joins
- Runs VACUUM and ANALYZE for optimization

### `user_annotated_vcf_duckdb`

Annotates user VCF files using DuckDB's join engine.

**Dependencies:**
- `ensembl_duckdb`
- `user_vcf_source` (partition-aware)

**Output:**
- `data/output/users/{user_name}/{sample_name}/{vcf_name}_annotated_duckdb.parquet`

## Usage

### 1. Build the DuckDB Database

First, ensure you have the Ensembl Parquet annotations:

```bash
# Start Dagster UI
uv run dagster dev -f just-dna-pipelines/src/just_dna_pipelines/annotation/definitions.py -p 3005
```

Then in the UI:

1. Navigate to **Assets**
2. Find and materialize `ensembl_annotations` (if not already done)
3. Find and materialize `ensembl_duckdb`

Alternatively, use the job:

1. Navigate to **Jobs** → `build_ensembl_duckdb_job`
2. Click **Launch Run**

### 2. Annotate User VCFs with DuckDB

Once the DuckDB database is built, you can annotate user VCFs:

1. Navigate to **Assets**
2. Find `user_annotated_vcf_duckdb`
3. Click **Materialize** and select the partition (user/sample)
4. Provide the required config in the launchpad

**Example Config:**

```yaml
resources:
  io_manager:
    config: {}
ops:
  user_annotated_vcf_duckdb:
    config:
      vcf_path: "data/input/users/antonkulaga/antonkulaga.vcf"
      user_name: "antonkulaga"
      sample_name: null
      variant_type: "SNV"
      reference_genome: "GRCh38"
      species: "homo_sapiens"
      sequencing_type: "WGS"
```

## Performance Comparison

To compare Polars vs DuckDB performance, materialize both assets for the same user:

1. `user_annotated_vcf` (Polars-based)
2. `user_annotated_vcf_duckdb` (DuckDB-based)

Compare the metadata:
- **Duration** (`duration_sec`)
- **Peak Memory** (`peak_memory_mb`)
- **File Size** (`file_size_mb`)
- **CPU Usage** (`cpu_percent`)

## When to Use DuckDB

Consider using DuckDB annotation if:

- You're processing **very large VCF files** (millions of variants)
- You're running on **memory-constrained systems**
- You plan to add **multiple annotation sources** (not just Ensembl)
- You need **interval/range joins** (variant in gene/exon/regulatory region)

## Implementation Details

### Database Schema

The DuckDB database contains tables:
- `ensembl_snv`: SNV variants from Ensembl
- `ensembl_indel`: INDEL variants from Ensembl

### Indexes

Each table has indexes on:
- `chrom`: Single-column index for chromosome filtering
- `(chrom, start, ref, alt)`: Composite index for exact variant matching

### Join Strategy

The annotation uses a LEFT JOIN to preserve all input variants:

```sql
SELECT 
    v.*,
    e.* EXCLUDE (chrom, start, ref, alt)
FROM input_vcf v
LEFT JOIN ensembl_{variant_type} e
    ON v.chrom = e.chrom 
    AND v.start = e.start 
    AND v.ref = e.ref 
    AND v.alt = e.alt
```

This ensures:
- All input variants are retained (even if not annotated)
- No duplicate join columns in the output
- Efficient index usage for large-scale joins

## Maintenance

### Rebuilding the Database

To rebuild the DuckDB database (e.g., after updating Ensembl annotations):

1. Delete the existing database: `rm ~/.cache/just-dna-pipelines/ensembl_annotations/ensembl_variations.duckdb`
2. Re-materialize the `ensembl_duckdb` asset

### Database Size

The DuckDB database is typically **smaller** than the original Parquet files due to:
- Compression (DuckDB uses efficient column encoding)
- Index overhead (adds ~10-20% to size)

Expect the database to be **70-90%** of the Parquet size.


