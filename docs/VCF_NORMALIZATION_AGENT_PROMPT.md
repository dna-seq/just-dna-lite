# AI Agent Prompt: VCF Normalization (Standalone, No Dagster)

Use this prompt in another project when you need to implement VCF normalization with the same requirements as just-dna-lite, but without Dagster. Copy the full prompt below the separator and paste it into your AI agent.

---

## Your Task

Implement a VCF normalization pipeline that reads raw VCF files (.vcf or .vcf.gz), applies normalization transforms, applies configurable quality filters, and outputs parquet. No Dagster or workflow orchestration — plain functions/CLI only.

### Tech Stack Requirements

- **Python** with type hints
- **Polars** — use LazyFrame and `sink_parquet()` for memory-efficient processing
- **polars-bio** — for VCF reading via `scan_vcf()`
- **Pydantic 2** — for config models
- **Pathlib** — for all file paths
- **Typer** — if exposing a CLI

### Normalization Steps (Order Matters)

1. **Read VCF** into a Polars LazyFrame using polars-bio `scan_vcf()`.
   - Support both `.vcf` and `.vcf.gz`.
   - Extract FORMAT fields (at least GT, and optionally DP, GQ, AD, etc.) — required for genotype computation.
   - Use `info_fields=None` for auto-detection from header, or allow override.
   - polars-bio API note: `thread_num` was removed in 0.23+; use `concurrent_fetches` instead.

2. **Chromosome column: strip `chr` prefix (case-insensitive)**
   - If the chromosome column is named `chrom` (or configurable name):
     - `"chr1"` / `"CHR1"` → `"1"`
     - `"1"` → `"1"` (unchanged)
     - `NULL` / empty → leave as `NULL`
   - Use Polars expressions:
     - `pl.col(chrom_col).cast(pl.Utf8).str.strip_chars()`
     - When `str.to_lowercase().str.starts_with("chr")` → `str.slice(3)`, else keep as-is.

3. **Rename `id` → `rsid`**
   - If schema has `id` and does NOT have `rsid`, rename: `lf.rename({"id": "rsid"})`.

4. **Compute genotype column from GT + REF + ALT**
   - Genotype must be `List[String]` with alleles sorted alphabetically.
   - Map GT indices (e.g. `"0/1"`, `"1|1"`) to actual alleles:
     - Index 0 = REF, index 1 = first ALT, index 2 = second ALT, etc.
   - Multi-allelic ALT: polars-bio may emit `"G|T"` (pipe) or `"G,T"` (comma). Handle both for robustness.
   - Build alleles array: `[REF, ALT1, ALT2, ...]` then gather by GT indices.
   - For `"./."` or missing GT → produce empty list `[]`.
   - Polars expression approach:
     - Extract numeric indices from GT: `str.extract_all(r"\d+")` then cast to Int64.
     - `alleles = pl.concat_list(pl.col("ref").str.split("|"), pl.col("alt").str.split("|"))` (polars-bio uses `|`).
     - `alleles.list.gather(gt_indices).list.sort().alias("genotype")`.

5. **Apply quality filters** (from config, e.g. YAML or Pydantic)

   Filters must be optional (if config absent or fields null/0, no filtering).

   | Filter       | Config Key      | VCF Column (case-tolerant) | Behavior                                                                 |
   |-------------|-----------------|----------------------------|---------------------------------------------------------------------------|
   | FILTER pass | `pass_filters`  | `filter`, `Filter`, `FILTER` | Keep only rows where value is in the list (e.g. `["PASS", "."]`)         |
   | Min depth   | `min_depth`     | `DP`, `Dp`, `dp`           | Keep rows where `DP >= min_depth`; cast to Int64 before comparison        |
   | Min quality | `min_qual`      | `qual`, `Qual`, `QUAL`     | Keep rows where `QUAL >= min_qual`; cast to Float64 before comparison     |

   - Column name detection: search for `(filter, Filter, FILTER)`, `(DP, Dp, dp)`, `(qual, Qual, QUAL)` — use first match.
   - All conditions are ANDed.
   - **gVCF support**: `FILTER=RefCall` (reference blocks) should be excluded when `pass_filters` is `["PASS", "."]`, since RefCall is not in that list. This intentionally drops gVCF reference blocks.

6. **Optional: chrY warning for female-labeled samples**
   - If `sex="Female"` (or configurable) is set, log a warning when chrY variants are found, e.g.:
     - `"WARNING: N chrY variants found in female-labeled sample. These are likely sequencing noise but are NOT removed."`
   - **Never remove chrY** based on sex — informational only. Avoid sex-based chromosome filtering to prevent data loss for XXY, XYY, etc.

7. **Output**
   - Write normalized LazyFrame to parquet via `lf.sink_parquet(path, compression="zstd")` (or configurable).
   - Optionally track metadata: `rows_before_filter`, `rows_after_filter`, `quality_filters_hash` for reproducibility.

### Quality Filters Config Model

```python
# Pydantic 2
class QualityFilters(BaseModel):
    pass_filters: Optional[list[str]] = None   # e.g. ["PASS", "."]; null = disable
    min_depth: Optional[int] = None           # e.g. 10; null or 0 = disable
    min_qual: Optional[float] = None          # e.g. 20.0; null or 0 = disable

    def config_hash(self) -> str:
        """SHA256 hex digest (first 16 chars) of canonical JSON for staleness tracking."""
        import hashlib, json
        canonical = json.dumps(self.model_dump(), sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]
```

### Example YAML Config

```yaml
quality_filters:
  pass_filters: ["PASS", "."]
  min_depth: 10
  min_qual: 20
```

- Set any field to `null` or `0` to disable that filter.
- If `quality_filters` section is absent, no filtering (all default to None).

### Input/Output

- **Input**: Path to VCF (`.vcf` or `.vcf.gz`).
- **Output**: Path to parquet (e.g. `output_dir/normalized.parquet`).
- **Compression**: zstd (default), or configurable.

### Anti-Patterns to Avoid

- Do not bypass quality filters in downstream steps — all annotation should read from the normalized parquet.
- Do not use sex-based chromosome removal — only log chrY warning for female samples.
- Do not assume column names are exact — use case-tolerant lookup (filter/Filter/FILTER, etc.).
- Cast DP and QUAL to numeric before comparison — parquet may store them as strings.
- Use LazyFrame + `sink_parquet` for large VCFs; avoid `collect().write_parquet()`.

### Dependencies

```
polars>=0.20
polars-bio
pydantic>=2
typer  # if CLI
pyyaml # if YAML config
```

### Reference Implementation

The reference implementation lives in:
- `just-dna-pipelines/src/just_dna_pipelines/io.py` — `read_vcf_file`, `_compute_genotype_expr`
- `just-dna-pipelines/src/just_dna_pipelines/module_config.py` — `QualityFilters`, `build_quality_filter_expr`, `_find_column`
- `just-dna-pipelines/src/just_dna_pipelines/annotation/chromosomes.py` — `rewrite_chromosome_column_strip_chr_prefix`
- `just-dna-pipelines/src/just_dna_pipelines/annotation/assets.py` — `user_vcf_normalized` (Dagster asset; extract the core logic)

You can adapt the logic from these modules into standalone functions without Dagster or assets.
