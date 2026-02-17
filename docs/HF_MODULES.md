# Annotation Modules

This document describes the annotation pipeline and data schema for VCF files using modules auto-discovered from configured sources.

---

## Overview

The module annotation pipeline provides a high-performance way to annotate genomic variants with curated evidence:

1.  **Reads** a user's VCF file (local, from HuggingFace, or from Zenodo).
2.  **Computes** genotypes from the GT field as sorted `List[String]`.
3.  **Joins** with each annotation module on position + genotype (or rsid).
4.  **Outputs** standardized Parquet files with annotation scores and evidence.

The modules are **self-contained**—they include all annotation data (gene symbols, phenotypes, conclusions) and don't require external Ensembl joins.

## Module Sources Configuration

Module sources are configured in `just-dna-pipelines/src/just_dna_pipelines/modules.yaml`. Sources can be any fsspec-compatible URL:

- **HuggingFace** (default): `just-dna-seq/annotators`
- **GitHub**: `github://org/repo`
- **HTTP/HTTPS**: `https://example.com/data`
- **S3/GCS**: `s3://bucket/path`, `gcs://bucket/path`

Modules are **auto-discovered** by scanning each source for `weights.parquet` files. Display metadata (titles, icons, colors) can be optionally overridden in the YAML under `module_metadata:`.

## Data Provenance

The annotation modules and Ensembl reference data are prepared and uploaded using the [dna-seq/prepare-annotations](https://github.com/dna-seq/prepare-annotations) toolkit. This upstream repository handles the complex pipelines for downloading raw genomic data, converting it to standardized Parquet schemas, and managing the HuggingFace Hub distribution.

---

## Available Modules

Modules are auto-discovered from configured sources. Run `uv run pipelines list-modules` to see the current list. The default source ([just-dna-seq/annotators](https://huggingface.co/datasets/just-dna-seq/annotators)) currently provides:

| Module | Description |
| :--- | :--- |
| `longevitymap` | Longevity-associated variants from LongevityMap database |
| `lipidmetabolism` | Lipid metabolism and cardiovascular risk variants |
| `vo2max` | Athletic performance and VO2max-associated variants |
| `superhuman` | Elite performance and rare beneficial variants |
| `coronary` | Coronary artery disease associations |
| `drugs` | Pharmacogenomic annotations (PharmGKB) |

---

## Repository & Table Schema

Each module in the [just-dna-seq/annotators](https://huggingface.co/datasets/just-dna-seq/annotators) repository contains three standardized Parquet tables:

### 1. `weights.parquet` (Curator Scores)
**Purpose**: Genotype-specific weights for variant interpretation. Joined with VCF on `rsid` (or position) + `genotype`.

| Column | Type | Description |
| :--- | :--- | :--- |
| `rsid` | String | Variant identifier (e.g., "rs7412") |
| `genotype` | List[String] | Normalized genotype (sorted allele list) |
| `weight` | Float64 | Numeric weight/score |
| `state` | String | Effect direction: `risk`, `protective`, `neutral` |
| `conclusion` | String | Human-readable interpretation |
| `priority` | String | Priority level (module-specific) |

### 2. `annotations.parquet` (Variant Facts)
**Purpose**: Variant-level facts—what each variant is associated with (Gene, Phenotype).

| Column | Type | Description |
| :--- | :--- | :--- |
| `rsid` | String | Variant identifier |
| `gene` | String | Curated gene symbol |
| `phenotype` | String | Trait or phenotype affected |
| `category` | String | Category within the module |

### 3. `studies.parquet` (Literature Evidence)
**Purpose**: Per-study evidence and literature references.

| Column | Type | Description |
| :--- | :--- | :--- |
| `rsid` | String | Variant identifier |
| `pmid` | String | PubMed ID |
| `population` | String | Study population (e.g., "European") |
| `p_value` | String | Statistical significance |
| `conclusion` | String | Study-specific conclusion text |

---

## Data Conventions

### Genotype Normalization
Genotypes are stored and matched as **alphabetically sorted lists of alleles**:
*   `0/1` (A/G) → `["A", "G"]`
*   `1/0` (G/A) → `["A", "G"]`
*   `1/1` (T/T) → `["T", "T"]`

This ensures consistent matching regardless of phasing or VCF representation.

### State Semantic Values
*   `risk`: Increases disease/negative outcome risk.
*   `protective`: Decreases risk.
*   `neutral`: No significant effect.
*   `significant`: Statistically significant (used by drugs module).

---

## CLI Usage

The `pipelines` command-line tool provides access to the annotation pipeline.

### List Available Modules
```bash
uv run pipelines list-modules
```

### Annotate a Local VCF
```bash
uv run pipelines annotate-modules \
    --vcf /path/to/sample.vcf \
    --user myuser \
    --sample sample1
```

### Annotate from Zenodo (Recommended for personal health data)
```bash
uv run pipelines annotate-modules \
    --zenodo https://zenodo.org/records/18370498 \
    --user antonkulaga \
    --sample genome
```

### Annotate from HuggingFace
```bash
uv run pipelines annotate-modules \
    --hf-source some-repo/data/sample.vcf \
    --user someuser \
    --sample sample1
```

---

## Dagster Integration

### Asset: `user_hf_module_annotations`
A partitioned asset that annotates user VCF files. It produces one Parquet file per module under `data/output/users/{user}/{sample}/modules/` and a `manifest.json`.

### Consumption via Polars
Polars supports reading directly from Hugging Face using the `hf://` protocol.

```python
import polars as pl

# Load any module's weights
weights = pl.read_parquet("hf://datasets/just-dna-seq/annotators/data/longevitymap/weights.parquet")
```

---

## Memory Efficiency & Performance

The pipeline is optimized for processing large VCFs:
1.  **Lazy Polars**: Uses `LazyFrame` with streaming to keep memory usage low.
2.  **Position Pre-filtering**: VCFs are pre-filtered to only include positions present in the modules.
3.  **Streaming Sink**: Results are written directly to Parquet (`sink_parquet`).
4.  **Join Strategy**: Supports both **Position-Based** (chrom + start) and **RSID-Based** (rsid) joins.

For very large VCFs (>10GB), the pipeline can process ~1M rows/second with minimal memory overhead.
