# A3 bench protocol

The running record of the A3 benchmark re-run ([plan](../a3_benchmark_rerun_plan.md)): every decision
in the order it was taken, with the command that carried it out. Commands run through
[`scripts/bp`](scripts/bp), which keeps each one's full output in `logs/NNN_<slug>.log` and a
machine-readable line in [`protocol.jsonl`](protocol.jsonl). Step numbers below are those `NNN`.

Large data (inputs, OakVar home, Dagster homes, outputs) lives outside the repo under
`/data/a3-bench/`; only scripts, logs and result tables are committed.

## Decisions before the run (2026-10-10)

- **OakVar is re-run**, overriding the plan's "historical only" section. The user asked for it. The
  2023 configuration and logs are on a remote server that is not reachable from here, so the Gen-I
  run is **reconstructed** from the published `just_*` modules, and labelled a reconstruction. The
  2023 numbers stay in the paper as their own labelled historical row.
- **OakVar runs in a Docker image** built for this purpose (OakVar installs Python packages at
  module-install time, so it stays out of the host environment). The Dockerfile is committed under
  `oakvar/` so the image can be rebuilt and published. Older OakVar releases are tried if the latest
  cannot run the 2023-era modules; each attempt is logged here.
- **Cold runs drop the OS page cache** through a privileged container
  (`docker run --rm --privileged … sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'`), since sudo needs
  a password. Each drop is verified by `buff/cache` before and after.
- **Timed runs need a quiet machine.** At the start, 1-minute load was ~12 (another session's test
  suite and long-running workers). Setup proceeds; timed runs refuse to start above a load gate, and
  every row records the load just before it.

## Log

### Setup

- **1** `env-snapshot`: lscpu, uname, memory, disks, governor, uv/docker versions. `/data` is
  `/dev/sda1`, an Intenso SATA SSD (ROTA 0), ntfs3. Governor `performance`. Load 12.3 at the time.
- **2–3** `worktree`, `uv-sync`: the checkout had uncommitted changes from a parallel session
  (`pyproject.toml`, `uv.lock`), so the benchmark runs from a **detached git worktree** at
  `bb4b294` in `/data/a3-bench/jdl`, with its own `uv sync`. No `.env` there: `load_env` falls back
  to `.env.template`, so no local secret or setting reaches the run.
- **4–5** `dl-anton`, `dl-livia`: both public genomes downloaded from the Zenodo API into their own
  empty directories. (Run in parallel, these two first shared step number 4; `bp` now allocates
  numbers under `flock`, and the second was renumbered 5.)
- **6** `copy-calibration`: the calibration genome copied from the krypton CIFS share to the local SSD,
  so no timed run reads over the network.
- **7** `inputs-check`: [`inputs.json`](inputs.json). All three match the plan: primary md5
  `21598da4…`, 6,079,744 records, `DeepVariant_version=1.1.0`; second caller DRAGEN 4.4.4,
  5,064,598 records, md5 `43afb27d…` (matches Zenodo); calibration 6,138,868 records,
  `DeepVariant_version=1.3.0`.

### Generation I reconstruction (OakVar)

- The 2023 runs went through the OakVar web GUI on agingkills with the `longevity2reporter` report
  (Just-DNA-Seq docs, *Getting started*). The reporter's `requires:` list defines the module set, and
  it changed between the runs: at 2023-05-07 it was `749a1ce` (0.4.0, which added lipidmetabolism
  and thrombophilia), and `just_vo2max` did not exist yet. The February runs therefore had fewer
  modules than the May run. The reconstruction targets **the May 2023 run**: the reporter and each
  `just_*` postaggregator at its last commit on or before 2023-05-07 ([`oakvar/modules.tsv`](oakvar/modules.tsv)),
  and OakVar **2.9.15**, the release current that day (published 2023-05-06).
- The 8 postaggregators need these store annotators: dbsnp, clinvar, omim, ncbigene, pubmed, gnomad,
  sift, vcfinfo. They come from the OakVar store at whatever version it serves today; each installed
  version is recorded.
- **8–11** `pull-base`, `pull-uv`, `build-oakvar-image`: [`oakvar/Dockerfile`](oakvar/Dockerfile), image
  `jdl-bench-oakvar:2.9.15`. Base `python:3.10-slim-bookworm@sha256:5be5aaec…`, uv 0.12.23 by digest.
  Dependencies resolved with `uv pip install --exclude-newer 2023-05-08`, so a rebuild gets the 2023
  versions (polars 0.17.12, duckdb 0.7.1, numpy 1.24.3; full list in `/pip-freeze.txt` in the image
  and in log 010). `pip`/`setuptools`/`wheel`/`packaging` come from the base image, not the 2023
  resolution. Step 11 rebuilt it with `OV_ROOT_DIR=/oakvar/ov`, so the whole OakVar home (store
  login, annotator data, modules, jobs) sits on the mounted volume `/data/a3-bench/oakvar/home`.
- **12–13** `pull-alpine`, `verify-cache-drop`: the privileged drop works. buff/cache went from
  30,194 MB to 6,654 MB; what remains is shared memory and tmpfs, which a cache drop cannot free.

### Generation II module set

- The worktree's default discovery reads the HuggingFace mirror, which has 9 modules (no
  `superhuman`) and older builds of cancer, cardio and pathogenic than the registry. The plan names
  the **S4 snapshot**, so:
- **14–23** `registry-dl-*`: the 10 S4 module versions downloaded from
  `https://module-registry.just-dna.life` (namespace `just-dna-seq`) into `/data/a3-bench/modules/`.
  Each manifest's `artifact.digest` equals the one in S4 (checked by script, 10 of 10 match).
- [`jdl/modules.yaml`](jdl/modules.yaml) is the repo's `modules.yaml` at `bb4b294` with `sources` replaced by
  that one directory. It is placed in `/data/a3-bench/jdl-root/` with a copy of `.env.template`, and the
  driver sets `JUST_DNA_PIPELINES_ROOT` there, so the pinned worktree itself stays unmodified.
  `pipelines list-modules` then reports exactly the 10 modules and `Sources: /data/a3-bench/modules`.

### Driver

- [`scripts/bench_annotation.py`](scripts/bench_annotation.py): one row per run in `runs.csv`. Run types `warmup`
  (excluded), `cold` (fresh instance, page cache dropped), `warm` (warm state: the normalized parquet
  is reused, so the VCF is **not** read), `full` (fresh instance, page cache not dropped: the whole
  pipeline with warm OS caches) and one `ensembl`. `full` was added at the user's request after a
  review note: a warm run skips normalization while every OakVar run reads the whole VCF, so the
  like-for-like pairs are cold or full against OakVar, and `normalize_s` from the full runs is the
  offset that turns a warm time into a full one.
- Order: warm-up first, then cold/warm/full shuffled with seed 20261010; `prev_run_type` is kept on
  each row because a page-cache drop before a cold run also evicts the warm state.
- Timing: CLI wall time, the Dagster run record (creation to end) and each step from the run's event
  log ([`scripts/dagster_stage_times.py`](scripts/dagster_stage_times.py), read after the run). Memory: RSS
  summed over the process tree at 10 Hz. CPU: `wait4` rusage of the command and every descendant it
  reaped, over wall time. Each row also records the annotated-variant count.
- Smoke test on `data/input/tests/antku_small.vcf` (792 chr1 records; outside `runs.csv`): all five run
  types complete, the warm run uses `annotate_modules_and_report_job` (no normalize step), the cold
  run's drop is recorded. All modules annotated 0 variants on this 792-record file; the full-genome
  warm-up is the real check that the module set matches anything.

### Community reference genome (HG002)

- Chosen by a search agent that listed the whole `gs://deepvariant/case-study-outputs/` bucket
  (versions 1.0.0 to 1.10.0). From 1.1.0 on, Google's single-sample Illumina WGS case study uses
  HG003; HG002 Illumina WGS output exists only as the **DeepVariant 1.0.0** run and as DeepTrio child
  calls (a trio caller, so not comparable). Chosen: DeepVariant 1.0.0, HG002, Illumina NovaSeq
  PCR-free 35x, GRCh38 no-alt (`HG002.novaseq.pcr-free.35x.dedup.grch38_no_alt.bam`, per the run
  script and log in the bucket). It declares PASS / RefCall / LowQual.
- **Licence:** none is stated for the bucket's outputs. DeepVariant's code is BSD-3-Clause; NIST says
  GIAB data are "publicly available without publication embargo" and the trio was chosen as
  "consented for commercial redistribution". So the paper links to the file and does not re-host it.
- **26** `dl-hg002`: md5 `29d00cf5…` equals Google's `x-goog-hash`. **27** `inputs-check-hg002`: 7,753,721 records, `DeepVariant_version=1.0.0`, 25 contigs.

### PRS harness

- **24** `clone-just-prs`: just-prs cloned at tag **v0.10.1** (`b1a6d60`) into `/data/a3-bench/just-prs`, the version the
  bench worktree's `uv.lock` resolves. The sibling checkout `/data/sources/just-prs` had uncommitted
  changes from another session, so it is not used.
- **25** `dl-plink2`: PLINK2 **v2.0.0-a.6.33LM (28 Feb 2026)**, the build `benchmark_engines.py` pins, downloaded from
  `s3.amazonaws.com/plink2-assets/alpha6/`; binary sha256 `f87f8be0…`, equal to the gap report's.
- [`prs/bench_prs.py`](prs/bench_prs.py) imports the upstream script's engines and memory measurement
  unchanged and adds: the committed ID lists ([`prs/pgs_ids.txt`](prs/pgs_ids.txt): PGS000006–PGS000106 without
  PGS000085; [`prs/warmup_ids.txt`](prs/warmup_ids.txt): PGS000001–3), PLINK2's `.log`/stdout/exit kept per ID,
  PLINK2's score-input preparation timed separately (`prep_sec`; upstream starts PLINK2's clock after
  it, while the Polars/DuckDB times include parsing), and `--config original|fixed`. *Fixed* builds
  the pgen with `--vcf-filter`, writes an ID for every `hm_inferOtherAllele` candidate, and sums the
  weights of IDs two scoring rows share (liftover collisions), which is what just-prs computes.
- Smoke test, 3 IDs, both configurations: *original* reproduces the published PLINK2 scores
  (PGS000006–8: −0.0038, −0.7342, −0.7906) and *fixed* reproduces the gap report's counterfactual
  run (−0.1464, −0.797, −0.8558) exactly.

### Rescheduled to the night queue (2026-10-10, 23:40)

- **28** `jdl-series-primary` was launched at 23:20 and **stopped at 23:42 before timing anything**:
  other sessions held the 1-minute load between 3 and 27 (an S5 scan with 6 workers, a just-prs test
  suite), so the warm-up never passed the load gate. No `runs.csv` row was written; its log ends
  without an exit line and it has no `protocol.jsonl` entry.
- The user then ruled (relayed by the session that wrote the plan): no timed runs in the evening;
  every benchmark goes into one queue at **03:00**, one job after another. This session owns the
  queue runner. Copies of the queue files are in [`queue/`](queue/):
  - `/data/bench-queue/run-queue.sh` runs every other `*.sh` there in lexical order, logs to
    `logs/<name>.log`, and marks `done/<name>` or `failed/<name>` (holding the exit code); a failure
    does not stop the queue.
  - `10-jdl-annotation.sh`: refuses to run if anything listens on 3000/3005/3006 (the app stack),
    proves the privileged page-cache drop works, then runs `scripts/run_jdl_series.sh` (each launch
    now gets its own dated series directory).
  - `25-a3-prs.sh`: `prs/bench_prs.py`, original then fixed, each behind the same load gate.
  - just-prs's own session adds `20-just-prs-engines.sh`.
- Timer: `systemd-run --user --on-calendar='2026-10-11 03:00:00' --unit=bench-queue`, so
  `bench-queue.timer` → `bench-queue.service`. A test unit under the same user manager reached Docker
  (29.8.2) and uv (0.12.23). The user has `Linger=no`, so the timer needs the desktop session to stay
  logged in.
