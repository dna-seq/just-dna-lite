# A2 — Annotation Speed Benchmark (Just-DNA-Lite vs OakVar)

## Summary

Whole-genome annotation benchmarks comparing **Just-DNA-Lite** (Gen 2, Ensembl Variation + parquet) against **OakVar** (Gen 1), on the same hardware. Just-DNA-Lite delivers a **~172× speedup** on normal runs — roughly two orders of magnitude.

---

## Just-DNA-Lite (Gen 2)

| Run type | n | Mean ± SEM (s) | SD (s) | CV (%) | Notes |
|---|---|---|---|---|---|
| **Normal** | 11 | **38.9 ± 3.3** | 10.9 | 28.0 | Higher CV driven by early ~26 s cluster vs later ~47–55 s runs (possible cold container effect or job size variance) |
| **Cold start** | 3 | **203.3 ± 9.0** | 15.5 | 7.6 | Tighter spread — cold start overhead dominated by fixed init cost |
| **GVCF** | 1 | **868** | — | — | Single replicate; estimated error ±66 s (cold_start CV) to ±243 s (normal CV) |

## OakVar (Gen 1)

| Run type | n | Mean ± SEM (s) | SD (s) | CV (%) | Notes |
|---|---|---|---|---|---|
| **Standard** | 3 | **6705 ± 583** | ~1010 | 15.1 | Feb 17 run ~1000 s faster than others (input size or load variation) |

### Individual OakVar runs (from logs)

| Date | Runtime (s) | tagsampler (s) |
|---|---|---|
| 2023-02-17 | 5651.1 | 322.1 |
| 2023-02-19 | 6803.2 | 268.0 |
| 2023-05-07 | 7662.0 | 328.1 |

---

## Speedup Summary

| Comparison | Speedup | Calculation |
|---|---|---|
| Normal vs OakVar | **~172×** | 6705 / 38.9 |
| Cold start vs OakVar | **~33×** | 6705 / 203.3 |
| GVCF vs OakVar | **~7.7×** | 6705 / 868 |

---

## Notes for Manuscript

- **Headline number for main text:** Just-DNA-Lite annotates a whole-genome VCF in **~39 seconds** (warm) vs **~112 minutes** with OakVar — a **~172× speedup** on the same hardware.
- **Cold start context:** Even with cold container initialization (~203 s), the pipeline is **~33× faster** than OakVar.
- **GVCF handling:** Larger GVCF inputs take ~14.5 min, still **~7.7× faster** than OakVar on standard VCF.
- **Error estimates for GVCF:** Recommend reporting ±66 s (7.6% CV from cold_start) as the primary estimate, with ±243 s (28% normal CV) as a conservative bound.
- The detailed OakVar run logs and full Gen 1 vs Gen 2 comparison should go in the **supplementary file**; only the headline speedup belongs in the main text.

## Resource Metrics (Just-DNA-Lite)

| Run type | Duration (s) | Peak RAM (MB) | Avg CPU (%) | Top consumer |
|---|---|---|---|---|
| **GVCF** (longest) | 868.4 | 747.6 | 182.1 | user_hf_module_annotations |
| **Cold start** | 215.5 | 644.4 | 277.7 | user_hf_module_annotations |
| **Normal** (avg) | 38.9 | 400–600 | — | user_hf_module_annotations |
| **With custom modules** (unoptimized) | 9.9 | 1619.8 | 144.5 | user_hf_module_annotations |

> **Design philosophy:** The pipeline was optimized for **memory efficiency** ("runs on a laptop" paradigm), not raw throughput. The speed gains come from Polars streaming joins and parquet column-pruned reads — ML-optimized libraries for tabular operations. Peak RAM stays under 750 MB for default modules on a whole genome; even unoptimized custom modules stay under 1.6 GB.

**OakVar peak RAM:** Not measured in the original runs. Re-measuring would require additional time; likely not critical for the manuscript since the key comparison is speed, and OakVar is the established baseline tool.

---

## Hardware

| Component | Specification |
|---|---|
| **CPU** | Intel Xeon E5-2667 v4 @ 3.20 GHz (Broadwell-EP, 8C/16T) |
| **RAM** | 128 GB (125 GiB usable) |
| **Swap** | 8 GB |
| **OS / Uptime** | Linux, 49 days uptime at time of benchmarking |

## Parallelism & Architecture Notes

The pipeline uses a **fan-out topology** from a shared normalization step. Key characteristics:
- **Polars streaming joins** — `sink_parquet(engine="streaming")` keeps peak RAM low; Polars uses all CPU cores internally for joins
- **DuckDB** — well-configured (75% of CPU threads, object cache for parquet metadata, predicate pushdown into parquet column reads)
- **Application-level sequential** — VCF parsing (polars-bio `concurrent_fetches=1`) and per-module annotation loop are single-threaded at Python level; parallelizing these would give further speedup but was deprioritized in favor of memory efficiency
- **Disk I/O is a bottleneck** on HDD — SSD/NVMe would likely improve further
- **Multi-user isolation** works well via Dagster dynamic partitions

> **For the manuscript:** Emphasize that the ~172× speedup was achieved with memory-optimized settings on HDD storage, with room for further gains from SSD and module-level parallelization. This strengthens the "runs on a personal laptop" narrative — the benchmarks represent a conservative lower bound on a server with spinning disks.

---

## Input Data

**VCF source:** Personal whole-genome sequencing data, variant-called with **DeepVariant**. The VCF and GVCF represent a typical real-world personal genomics use case. The personal genome cannot be published, but the input characteristics should be documented for reproducibility:

- [x] ~~Variant count~~ — **6,138,868** records (4,729,824 SNPs; 1,414,226 indels)
- [ ] Number of variants in the GVCF
- [x] ~~Genome build~~ — **GRCh38**
- [x] ~~DeepVariant version~~ — **v1.4.0**
- [x] ~~Coverage~~ — **~162×** mean (estimated with 150 bp read length; good-faith estimate, may vary slightly due to soft-clipping)

> **For the manuscript methods:** "Benchmarks were performed on a personal whole-genome VCF (6,138,868 variant records; 4,729,824 SNPs and 1,414,226 indels) produced by DeepVariant v1.4.0 against the GRCh38 reference genome at ~162× mean coverage. The personal genome data is not publicly available; however, the pipeline can be reproduced with any standard whole-genome VCF, and the benchmark scripts are provided in the repository."

---

## Checklist

- [x] ~~Confirm hardware specs~~ — **done**
- [x] ~~Peak RAM and CPU usage~~ — **done** (see resource metrics above)
- [x] ~~Disk type~~ — **done** (HDD, JBOD array; same for both old and new runs)
- [x] ~~Input data source~~ — **done** (personal WGS, DeepVariant; not publishable)
- [x] ~~Fill in VCF characteristics~~ — **done** (6.1M variants, GRCh38, DeepVariant v1.4.0, ~162×)
- [ ] GVCF variant count (if relevant for the GVCF benchmark row)
