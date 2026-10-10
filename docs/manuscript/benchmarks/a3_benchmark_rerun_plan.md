# A3: Benchmark re-run plan for Paper 1 (annotation and PRS)

To be carried out by one dedicated session on this machine, end to end. Written on 2026-10-10 after
the v0.3 review found that the published benchmark numbers cannot be reproduced from what the paper
cites (review items B22–B32 and C22–C27 in the fix list).

## Why the benchmarks are re-run

- **Annotation (Section 4.1)** was timed on `newtonwinter.GRCh38.ens106.deep.vcf.gz`, an unpublished
  co-author genome (6,138,868 records, DeepVariant **1.3.0**). The paper names Anton Kulaga's public
  Zenodo genome (6,079,744 records, DeepVariant 1.1.0) and says "v1.4.0". No per-run times, run
  script or hardware log were committed.
- **PRS (Section 4.2)** used the public genome, but no per-score results, PLINK2 logs or exact ID list
  survive, so Tables 5 and 6 cannot be recomputed. The PLINK2 failures were never logged.
- **Table 4's "Linux 6.8.0"** came from the PRS machine, not the annotation machine.

The rule for this run: every number in Sections 4.1, 4.2 and S2–S3 comes from a file committed with
it, produced by a committed script, on inputs anyone can download.

## Inputs

| Role | File | Source | Check before use |
|---|---|---|---|
| Primary (public) | `antonkulaga.vcf` | Zenodo 18370498, CC0 | md5 `21598da4f77d8237577662ab89e8a55d`; 6,079,744 records; `##DeepVariant_version=1.1.0` |
| Second caller (public) | `SIMHIFQTILQ.hard-filtered.vcf.gz` | Zenodo 19487816, CC-BY-4.0 (Livia Zaharia, DRAGEN) | record the md5 and record count; DRAGEN exercises the `JDP` and targeted-caller filter path |
| Community reference (public) | an HG002 **caller output** VCF on GRCh38 (not the GIAB truth set, which has no RefCall or FILTER structure) | to choose: a published DeepVariant HG002 call set | verify the URL, licence and caller version before use; record all three |
| Hardware calibration (private) | `newtonwinter.GRCh38.ens106.deep.vcf.gz` | `/mnt/krypton/Genomes/newton/consensus/variants/deepvariant/` | must have 6,138,868 records and DeepVariant 1.3.0 (measured 2026-10-10) |

The calibration run repeats the 2026 annotation measurement on the same file on this machine. The
ratio between the old and new times gives the hardware and environment factor (the error estimate is
done elsewhere). It is not reported as a result on its own.

## Machine (record, do not assume)

Measured on 2026-10-10: AMD Ryzen 7 3800X (8 cores, 16 threads), 62 GB RAM, SATA SSDs plus a
rotational HDD array, Linux 7.2.9-1-liquorix. This is **not** the Xeon E5-2667 v4 / 128 GB workstation
of the old tables. At the start of the run, write `env.json` with:

- `lscpu`, `uname -a`, `free -b`, and `lsblk -d -o NAME,ROTA,MODEL` for the disk the data and cache
  sit on;
- the `git rev-parse HEAD` of just-dna-lite, the sha256 of `uv.lock`, and the just-prs and polars
  versions;
- the module versions and digests in use (the S4 snapshot format);
- the CPU governor.

Close the user's running app stack first, or use another `DAGSTER_HOME`. Never start a second stack
beside a live one (repo memory: duplicate Dagster daemons fight).

## Annotation benchmark (Section 4.1)

**Definitions, stated in the paper and recorded with every row:**
- **Cold:** a fresh `DAGSTER_HOME` and output directory, with the module and Ensembl caches present
  on disk but the OS page cache dropped
  (`sync; echo 3 | sudo tee /proc/sys/vm/drop_caches`). If sudo is not available, record "page cache
  not dropped" and say so in the paper.
- **Warm:** a repeat run on the same sample with caches present.
- **Timed boundary:** from job submission to the report written. Normalization, module annotation
  and report are timed separately, from the Dagster asset events.
- **Modules:** the default set, by name and version from the S4 snapshot, identical for every genome.
- **Ensembl:** off in the main runs; one extra run with it on.

**Runs per genome:** 3 cold and 11 warm, alternated with a fixed seed so that drift does not line up
with the run type. Calibration genome: the same counts.

**Entry point:** the CLI path `uv run annotate`, which uses the same runner as the web UI
(`annotation_runner.run_annotation`), so the web server is not timed.

**Memory:** sample peak resident memory of the whole process tree at 10 Hz (psutil over the process
and all its children), not the current start/end RSS of one process. Record peak, mean and CPU% per
run. State the method in the Table 3 legend.

**Outputs to commit** (`docs/manuscript/benchmarks/a3/`): `runs.csv` with one row per run (genome,
run type, index, wall seconds per stage, peak RSS, CPU%, exit status, Dagster run id), `env.json`,
`inputs.json` (md5, records, caller version for each file), and the script itself
(`scripts/bench_annotation.py`, committed with the results).

**Paper numbers come from `runs.csv` only:** mean, SD, SEM, median, min and max per genome and run
type. If the warm runs fall into two clusters (the old notes saw about 26 s and 47–55 s), report the
median and the range, not just the mean.

## Generation I (OakVar) comparison

It is not re-run. It stays as a **historical** comparison, labelled truthfully: three OakVar runs in
2023 on the calibration genome (6,138,868 records, DeepVariant 1.3.0), with no memory record and no
surviving hardware log. Its ratio to the calibration genome's 2026 warm time on the old workstation
is the only like-for-like ratio that exists. The new public-genome runs are not divided by the OakVar
time.

## PRS benchmark (Section 4.2)

Re-run `just-prs/benchmarks/benchmark_engines.py` (just-prs is read-only from just-dna-lite; run it
from a separate checkout or through `uv run --no-sync` here) on the primary genome, with:

- the exact ID list committed: PGS000006 to PGS000106 excluding PGS000085, plus warm-up IDs, all
  recorded;
- the PLINK2 build pinned and recorded (binary sha256), with **its stderr and `.log` kept** for every
  ID, so that failures have a cause;
- `benchmark_results.csv` (per ID and engine: seconds, matched, total, score, memory method) committed
  under `a3/prs/`;
- a paired speed comparison on the IDs every engine finished, beside the unpaired medians;
- the per-variant difference analysis, rerun on the new results. The 2026-10-10 investigation already
  explains the old gap with zero residual: 71.4% from the benchmark using only the first inferred
  other-allele candidate, 15.7% from building the pgen without `--vcf-filter` (RefCall counted), 9.5%
  from just-prs's position-only join, 1.4% from unsplit multi-allelic ALTs and 1.9% from chrX. PLINK2
  failed on 4 scores because of liftover duplicate IDs. Deliverables and scripts:
  `/data/just-dna-cache/r-gap/deliverables/` (`run_all.sh`). Commit the per-variant tables as
  supplementary data.
- **fix the two benchmark-input defects first** (all candidate alleles; `--vcf-filter` for PASS
  records only; deduplicate liftover duplicates), or report both configurations. Fixed, agreement
  rose to r = 0.999997 (max |Δ| 0.50).

## After the run

1. Regenerate Tables 2–6 and S2–S3 from the committed files. No number is typed by hand.
2. Rewrite 4.1 and 4.2 with `@rev` markers (B22–B32, C22–C27), and update Table 4 from `env.json`.
3. Remove "benchmark scripts are provided in the repository" unless it is now true. It should be.
