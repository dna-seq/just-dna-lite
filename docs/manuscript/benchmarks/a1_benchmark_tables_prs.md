# A1 — Camera-Ready Benchmark Tables (just-prs)

These tables are formatted for direct inclusion in the revised manuscript. All data comes from the reproducible benchmark at [just-prs/docs/benchmarks.md](https://github.com/dna-seq/just-prs/blob/main/docs/benchmarks.md), run on 100 consecutive PGS Catalog IDs (PGS000006–PGS000106) scored against a single personal whole-genome VCF (4.66 M biallelic variants, GRCh38; Zenodo 18370498). System: Linux 6.8.0, 32 cores, 94 GB RAM, Python 3.13.5, PLINK2 v2.0.

---

## Table 1. Runtime comparison of PRS computation engines

Median and mean wall-clock time per PGS ID scoring call (seconds). "Excl. large" excludes 7 PGS IDs with ≥ 1 M variants. Speedup is relative to PLINK2 median.

| Engine | *N* scored | Median (all) | Mean (all) | Median (excl. large) | Mean (excl. large) | Speedup vs PLINK2 |
|---|---|---|---|---|---|---|
| **DuckDB** | 100 | **0.049** | 0.394 | 0.048 | 0.059 | **12.3×** |
| **Polars** | 100 | 0.106 | 0.466 | 0.105 | 0.117 | 5.7× |
| PLINK2 | 96^a^ | 0.603 | 0.703 | 0.603 | 0.640 | 1× (ref.) |

^a^ PLINK2 failed on 4 genome-wide PGS IDs (6.6–6.9 M variants) due to 4-part ID matching constraints; just-prs engines scored all 100.

---

## Table 2. Memory usage per PRS scoring call

Peak memory per individual PGS scoring invocation. DuckDB and Polars report Python heap allocation via `tracemalloc`; PLINK2 reports subprocess peak RSS via `psutil` (sampled at 100 ms intervals). These measures are not directly comparable in scale but each captures the incremental cost per scoring run.

| Engine | Median peak | Mean peak | Max peak | Measurement method |
|---|---|---|---|---|
| **DuckDB** | **0.2 MB** | 139 MB | 2,594 MB | `tracemalloc` heap |
| **Polars** | **0.2 MB** | 139 MB | 2,594 MB | `tracemalloc` heap |
| PLINK2 | 590 MB | 595 MB | 974 MB | Subprocess RSS |

For typical PGS IDs (< 500 K variants), DuckDB and Polars allocate < 1 MB of heap per call. The high mean/max values are driven by 7 genome-wide scores (6–7 M variants). PLINK2 has a near-constant ~590 MB floor because it reloads the compressed pgen/pvar/psam files for each invocation.

---

## Table 3. Score concordance between engines

Pearson correlation coefficient and maximum absolute score difference across scored PGS IDs. PLINK2 pairs use *N* = 96 (4 IDs failed); DuckDB–Polars uses *N* = 100.

| Engine pair | *N* PGS | Pearson *r* | Max |Δ score| |
|---|---|---|---|
| DuckDB ↔ Polars | 100 | **1.000000** | < 1.1 × 10⁻¹³ |
| DuckDB ↔ PLINK2 | 96 | 0.999859 | 21.4 |
| Polars ↔ PLINK2 | 96 | 0.999859 | 21.4 |

The near-zero difference between DuckDB and Polars confirms identical algorithm implementation (position-based join, GT dosage, weighted sum). The absolute difference vs PLINK2 arises from variant-matching scope: PLINK2 requires exact 4-part `chr:pos:ref:alt` ID matching while just-prs uses position-based matching with allele orientation detection, leading to 1–3 extra variants included or excluded per genome-wide score. The Pearson *r* ≈ 0.9999 confirms that individual risk rankings are effectively identical.

---

## Table 4. Runtime on large scoring files (≥ 1 M variants)

These 7 genome-wide PGS IDs represent atypical workloads with very large scoring files.

| PGS ID | Variants | Polars (s) | DuckDB (s) | PLINK2 |
|---|---|---|---|---|
| PGS000014 | 6,917,436 | 6.72 | 6.42 | Failed |
| PGS000017 | 6,907,112 | 6.77 | 6.42 | Failed |
| PGS000016 | 6,730,541 | 6.65 | 6.28 | Failed |
| PGS000013 | 6,630,150 | 6.71 | 6.42 | Failed |
| PGS000039 | 3,225,583 | 4.12 | 3.84 | 1.79 |
| PGS000027 | 2,100,302 | 2.48 | 2.28 | 1.71 |
| PGS000018 | 1,745,179 | 2.32 | 2.23 | 1.41 |

PLINK2 failed on the four largest scoring files (≈ 6.6–6.9 M variants each) because these genome-wide files contain variants without a matching 4-part `chr:pos:ref:alt` ID in the autosomes-only pgen. For the three files where PLINK2 succeeded, it was faster due to compiled C++ SIMD operations on pre-indexed data.

---

## Table 5. Benchmark setup summary

| Parameter | Value |
|---|---|
| Input VCF | Personal whole-genome, single individual (Zenodo 18370498) |
| Biallelic variants | 4,661,444 |
| Genome build | GRCh38 |
| PGS IDs scored | 100 (PGS000006–PGS000106; 5 warm-up IDs excluded) |
| Scoring file sizes | 77 – 6,917,436 variants |
| OS | Linux 6.8.0 (lowlatency) |
| CPU | 32 logical cores |
| RAM | 94 GB |
| Python | 3.13.5 |
| PLINK2 | v2.0 (2026-01-10) |
| Variant match rate | ~50–54% across engines |
| Reproducibility | `uv run python just-prs/benchmarks/benchmark_engines.py` |

---

## Notes for manuscript integration

- **Tables 1–3** are the primary tables for the main text (Section 6.2 in the proposed outline).
- **Table 4** can go in the main text or supplementary, depending on space.
- **Table 5** is for the Methods section or supplementary.
- Table captions above are drafts — refine wording to match journal style.
- Scatter plot (concordance) and bar chart (median runtime) should accompany Tables 1 and 3 — these require generating figures from `benchmark_results.csv`.
- The footnote on memory measurement methodology (tracemalloc vs RSS) should appear in the Methods section to preempt reviewer questions about the comparison.
