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
- Two PRS jobs on purpose (agreed with the plan's session): `25-a3-prs.sh` measures the **shipped**
  just-prs 0.10.1 (what just-dna-lite users run today, original and fixed benchmark inputs) and
  writes to `a3/prs/results-<stamp>/`; `20-just-prs-engines.sh` (just-prs's session) measures the
  **fixed** engines from its working tree, which the paper reports once that version is released and
  pinned. Each records the just-prs version and commit it ran.

### Power cut during the first night run (2026-10-11, about 03:58)

- The queue started at 03:00:13 (load 0.27). **29** `jdl-series-primary` finished at 03:31 (exit 0):
  all 21 primary rows are in `runs.csv`.
- **30** `jdl-series-second_caller` was in its 11th timed run (cold 2) when a storm power surge cut
  the machine at about 03:58. Its log ends mid-run and it has no `protocol.jsonl` line. The ten rows
  it had written are moved, unchanged, to `runs-aborted.csv` and are not used: a series is reported
  whole or not at all, so second_caller runs again from its warm-up in a new series directory.
- The queue timer was a transient systemd unit, so it did not survive the reboot; jobs 20 and 25 had
  not started.
- After the reboot all four input VCFs still match their md5 in `inputs.json`.
- The user asked for the annotation series to run after the PRS jobs, so the job is renamed
  `30-jdl-annotation.sh` and runs only `second_caller community_reference calibration`
  (`run_jdl_series.sh` now takes genome names). Order at that point: 20 → 25 → 30, OakVar last. The old job
  file and its log are kept in `/data/bench-queue/aborted/`.
- just-prs's session renamed its job to `40-just-prs-engines.sh` (the user: the just-dna-lite bench
  runs first), so the order is 25 → 30 → 40, OakVar after that.
- Re-armed the same way for **05:00 the same night** (`--on-calendar='2026-10-11 05:00:00'`); the
  load gates hold each job until the machine is quiet.

### Generation I: 2023 code, 2026 annotation data (2026-10-11)

The OakVar image pins the code to May 2023, but the annotator databases are downloaded from today's
OakVar store; most of OakVar's runtime is lookups in them. The paper labels the run "2023 code, 2026
annotation data" and reports the annotator versions installed (recorded at install time) next to its
timing. The user notes the `just_*` modules changed little since 2023 (bug fixes only).

### Generation I switched to the current OakVar (2026-10-11, 04:50)

- The user ruled: run the **current** OakVar first, and step down to a 2025, 2024 or 2023 release
  only if the `just_*` modules fail on it ("OakVar is frail as it is"). The May 2023 build stays in
  the Dockerfile as that fallback.
- Before that, a probe of `store.oakvar.com` showed the 2.9.15 client's endpoints still answer
  (`/account/login`, `/fetch_summary`, `/fetch_versions`, `/fetch_conf/…`, `/urls/…` all reply
  "not logged in" or name the missing login field, none 404). The 2.9.15 login attempt failed only
  because that store account was not yet verified.
- **31** `build-oakvar-image-2.13.1`: OakVar 2.13.1 (published 2026-08-30, latest on 2026-10-11),
  dependencies resolved as of 2026-08-31 (`--exclude-newer`). Resolving as of the build day pulled
  polars 2.0.0 (released 2026-10-06), a major version OakVar was never released against, so the
  cut-off is OakVar's own release date, the same rule as the 2023 build. Resolved: polars 1.44.1,
  duckdb 1.5.5, numpy 2.2.6, mako 1.4.1.
- Modules: [`oakvar/modules-current.tsv`](oakvar/modules-current.tsv), each repo's latest commit on
  2026-10-11. The current `longevity2reporter` (0.4.3) also requires `just_vo2max`, so the current
  set is the reporter plus 9 postaggregators; the 2023 set ([`oakvar/modules.tsv`](oakvar/modules.tsv))
  had 8. Annotators they require: dbsnp, clinvar, omim, ncbigene, pubmed, gnomad, sift, cardioboost
  (only the current `just_cardio`), and vcfinfo.
- A fresh OakVar home for this version, `/data/a3-bench/oakvar/home-2.13.1`, so nothing written by
  the 2.9.15 login attempt mixes in.
- The paper labels the run with the OakVar version and module commits that actually ran.

### OakVar store login and install plan (2026-10-11, 05:00–05:15)

- The store account the user first tried was never verified, and a second address had no account;
  OakVar 2.13.1's `system setup` then loops on "User not found" with no way out but stopping the
  container (`--init` added to the interactive commands so Ctrl+C reaches `ov`). The user then
  registered a new store account, verified it and logged in with
  `system setup -f /oakvar/setup-login-only.yml` into `/data/a3-bench/oakvar/home-2.13.1`. The
  credential lives only in that volume, never in the image or the repo.
- Setup fetched the store index (5 parts) and, with `base_modules: []`, installed nothing.
- The store index lists every module the run needs, `longevity2reporter` and all nine `just_*`
  postaggregators included, so Generation I is installed **from the store**, the way a user would,
  rather than from GitHub tarballs (fewer moving parts). `modules-current.tsv` stays as the record of
  each repo's head on the same day; the versions that actually ran are taken from `ov module ls`
  after install. Store versions on 2026-10-11 (latest of each):

  | module | type | code / data version | download |
  |---|---|---|---|
  | dbsnp | annotator | 156.0.1 / 156.0.1 | 24.5 GB |
  | gnomad | annotator | 2.2.0 / 2.2.0 | 7.8 GB |
  | sift | annotator | 1.3.0 / 1.1.0 | 4.4 GB |
  | gencode | mapper | 46.1.1 / 46.1.0 | 0.5 GB |
  | clinvar | annotator | 2026.10.01 | 0.2 GB |
  | ncbigene, omim, pubmed, cardioboost | annotators | 2026.10.01, 1.1.1, 1.1.5, 1.0.0 | small |
  | vcf-converter, vcfinfo | converter, postaggregator | 4.2.1, 3.2.0 | small |
  | longevity2reporter | reporter | 0.4.3 | small |

- The 37 GB download waits until the night queue has finished, so it does not overlap timed runs.
- `bench_annotation.py` now defaults to the 2.13.1 image and its home.

### Night queue, second start (2026-10-11, 05:00–07:02)

All three jobs exited 0 (`/data/bench-queue/logs/run-queue.log`):

- **32** `prs-original` and **33** `prs-fixed` (job 25, 05:00–05:22): 100 PGS IDs each, results in
  [`prs/results-20261011T0500/`](prs/results-20261011T0500/) with every PLINK2 log and stdout.
- **34–36** `jdl-series-second_caller`, `-community_reference`, `-calibration` (job 30,
  05:22–06:56). With primary's step 29, `runs.csv` now holds the full series for all four genomes
  (warm-up, 3 cold, 11 warm, 5 full each, plus primary's Ensembl run), every row exit 0.
- Job 40 (just-prs's session, 06:56–07:02) wrote to the just-prs repository
  (`just-prs/benchmarks/results/2026-10-11/`), committed there as just-prs 64000d1 and written up in
  just-prs `docs/benchmarks.md` (median time: duckdb 0.082 s, polars 0.309 s, PLINK2 0.602 s;
  polars vs PLINK2 r = 0.99999996, every residual attributed).
- The user then asked for Generation I to follow straight away instead of waiting for the next
  03:00 window, so the OakVar install (step 37) started at 07:03, once the queue was idle.

### Generation I install, the dbsnp import fix and the smoke test (2026-10-11, 07:03–08:10)

- **37** `oakvar-install-modules` (58 min): the annotators, `vcf-converter`, `gencode` and the ten
  Longevity2 modules from the store. OakVar pulled `hg38wgs` and the `wg*` widgets as
  dependencies, and pip-installed `mako` 1.4.3 into the volume's user site on its own (the image has
  1.4.1). **38–39** `oakvar-module-ls`, `-ls-json`: the installed set is in
  [`oakvar/installed-2.13.1.json`](oakvar/installed-2.13.1.json) (30 modules, 95.4 GB). OakVar's
  `--fmt json` prints a Python literal, so the file is that output converted with `ast.literal_eval`.
- **40** `oakvar-smoke-5000` (exit 3): `tagsampler` missing. The login file had `base_modules: []`,
  so **41** installed OakVar's default base modules (`vcfreporter` pip-installed PyVCF3 on its own).
- **42** `oakvar-smoke-5000` (exit 0, but wrong): on the first 5,000 records of the primary VCF,
  the store's **dbsnp 156.0.1** failed to load (`from cravat.util import get_ucsc_bins,
  reverse_complement`: ImportError), and its `ModuleLoadingError` took the annotator step down, so
  sift, ncbigene and pubmed never ran either. Every `just_*` module then failed on every variant
  (`'dbsnp__rsid'`; `just_cardio` on `'base__hugo'`, which OakVar adds only when a gene-level input
  such as `ncbigene__ncbi_desc` exists).
- Diagnosis, from the PyPI source archives of OakVar 2.9.15, 2.9.99, 2.10.4, 2.11.10, 2.11.26,
  2.12.6, 2.12.22, 2.12.25 and 2.13.1: **no release exports `reverse_complement` from its `cravat`
  compatibility module** (2.9.15 has no `cravat.util` at all; tested in the 2.9.15 image:
  `ModuleNotFoundError`). OakVar defines it in `oakvar.lib.util.seq`. dbsnp 154.0.2, the version
  current in 2023, has the same import (its download, **43**, was stopped partway and its partial
  files removed; 156.0.1 stayed installed). So stepping OakVar down cannot fix this, and the user's
  downgrade ladder does not apply: it is a store-module/OakVar mismatch, not our modules.
- Fix: the Dockerfile appends `from oakvar.lib.util.seq import reverse_complement` to the image's
  `cravat/util.py`. The store's module files stay byte-for-byte as installed. **44** rebuilt the
  2.13.1 image with it (its exit 2 is a redundant last check of mine with a shell syntax error; the
  image built and the import test printed `GTT`); the dependency freeze is identical to step 31's.
  Every other `cravat` import in the installed modules was tested in the image and resolves.
- **45** `oakvar-smoke-5000-shim` (exit 0, 8.1 s): all 8 annotators present (`dbsnp__`, `sift__` …
  in the variant table, `ncbigene__`, `pubmed__` in the gene table), every `just_*` module wrote
  output, no `err.just_*` line. The 2,171 `vcf-converter` skips are DeepVariant RefCall records
  (`No alternate allele`); Generation II drops the same records through its quality filter.
- **46** `oakvar-smoke-5000-gz` (exit 0): the same on a gzipped VCF (calibration genome's head).
- The paper should say: OakVar 2.13.1 with a one-line compatibility re-export, because the store's
  dbsnp annotator imports a name no OakVar release exports. Worth reporting upstream (the user's
  call: outbound).
- Timed runs: [`queue/50-oakvar-annotation.sh`](queue/50-oakvar-annotation.sh), 3 runs on the
  primary genome then 1 on the calibration genome, each a fresh job directory, no cache drop
  (`full`), started straight after this check at the user's request rather than at 03:00.

### Generation I timed runs (2026-10-11, 08:10–14:50)

- Queue unit `bench-queue-oakvar` (started 08:10:19 at load 0.53 by the same `run-queue.sh`, which
  skipped 25/30/40 as done) ran [`queue/50-oakvar-annotation.sh`](queue/50-oakvar-annotation.sh),
  image `jdl-bench-oakvar:2.13.1` (`sha256:5d17f590f6f3…`), exit 0 at 14:50:08.
- **47** `oakvar-series-primary` (4 h 59 min): 3 `full` runs, each a fresh job directory: 6,005.4 s,
  6,068.5 s, 5,889.3 s (load before: 0.53, 1.28, 1.28). Peak RSS of the container's process tree
  4,610 MB in all three.
- **48** `oakvar-series-calibration` (1 h 40 min): 1 `full` run, 5,995.5 s (load 1.60 at first, so the
  driver waited, then started at 1.03). Peak RSS 3,838 MB.
- Every run ended `finished normally`. No traceback. The only `err.` lines are `vcf-converter`'s
  `No alternate allele` skips of DeepVariant RefCall records (1,418,835 on the primary genome, the
  same on every run); Generation II drops the same records through `pass_filters`. All 9 `just_*`
  postaggregators ran on every run. Each primary run log contains "error" about 1,760 times and
  "failed" 820 times, all inside the converter's row dumps of RefSeq gene descriptions ("an inborn error of …").
- Output, identical across the three primary runs: 4,727,413 variants and 54,465 genes in the result
  database (calibration: 4,804,600 and 54,395).
- The reporter logs `No module just_prs`: the Longevity2 reporter reads Generation I's PRS
  postaggregator when present. It was not in the run's module set (nor installed), so the report has
  no PRS section; Generation II's annotation series has no PRS step either (PRS is benchmarked apart,
  job 25), so the comparison stays like-for-like. The reporter step is 0.25 s because it renders from
  the postaggregators' own databases.
- Step and module timings, from OakVar's own log lines, are in
  [`oakvar/steps-20261011T0810.tsv`](oakvar/steps-20261011T0810.tsv), extracted by
  [`oakvar/extract_steps.sh`](oakvar/extract_steps.sh) (the 6-million-line container logs stay in
  `/data/a3-bench/series/20261011T0810/oakvar/`, not committed). On the primary genome about 40% of
  the time is the postaggregator step (the `just_*` modules and tagsampler/vcfinfo), 28% the
  annotators, 17% the mapper, 8% the converter and 7% the aggregator.
- Loads 1.0–1.3 during the day runs are above the night series' typical idle level; they stayed under
  the 1.5 gate. Treat the three primary runs' spread (SD about 90 s, 1.5%) as including that.

### Analysis (2026-10-11, after the timed runs)

- [`scripts/make_env.py`](scripts/make_env.py) writes [`env.json`](env.json) from the committed logs
  only: the machine from step 1's snapshot, the code from the worktree commit (step 2) and the
  package versions from step 3's `uv sync`, the Generation II module versions and digests from the
  registry downloads (steps 14–23), the OakVar image id from step 44 and the PRS tool versions from
  each `metadata.json`. The `uv.lock` hash is that of commit `bb4b294`, which the worktree used
  unmodified; step 1 hashed the main checkout's lock, which held another session's uncommitted edit
  at that moment.
- [`scripts/make_tables.py`](scripts/make_tables.py) writes [`tables.md`](tables.md) (Tables 2–6,
  S2, S3) from `runs.csv`, `inputs.json`, `env.json`, `historical.csv`, the OakVar step TSV and the
  PRS results. [`historical.csv`](historical.csv) holds the v0.3 paper's 2023 numbers (OakVar's three
  runs from S2, Generation II's "normal" and "cold start" summaries from Table 2) with their source;
  they are not reproducible, only carried.
- The `ensembl` run is labelled `full + Ensembl` in the tables: it runs `annotate_all_job`, which
  normalizes again (15.4 s) and verifies the Ensembl cache (34.3 s) before the join (29.0 s), so it
  is not a warm-state run as the driver's docstring says.
- Two `full` runs were slow (primary #1, 50.8 s; second_caller #5, 81.0 s): annotation and report took
  about twice as long at lower CPU% (250–270% against about 345–385%), normalization barely changed. A
  transient contention, not a code path; the tables give the median and range per the plan.
- The paper's Sections 4.1, 4.2, S2, S3 and one Conclusion clause were rewritten from `tables.md`
  (commit 4a77f7b and the fix after it). Tables 2–6 are pasted from its "As printed in the paper"
  section and checked equal to it; every number in the new prose appears in `tables.md`,
  `inputs.json` or `env.json` (memory is quoted in MB for that reason). `@rev` ids: B22–B25, B27–B32,
  C22, C23, C26, C27, and A3a–A3c for text no review comment covers. B26 is moot (no single cold-start
  row remains). Table 4 stays, since C24 (delete it) is still the user's decision. The ten Generation
  II modules match Table S4 in version and digest.

### Claim validation (2026-10-12)

- Five independent validators (Sonnet subagents, read-only) checked every claim of Sections 4.1,
  4.2, S2, S3 and the Conclusion clause against these files, the just-prs 0.10.1 source, PyPI and
  Zenodo. `tables.md` and `env.json` regenerate byte-identical; every table and number in the text
  recomputes from `runs.csv`, the PRS results and the OakVar step TSV.
- Wording fixed in the paper (rounds bumped to 2): Generation I ran nine postaggregators on two
  genomes with no warm-up, and its run is the counterpart of a full run, not the same computation;
  "public data" is scoped to the three public genomes plus an OakVar store account; the RSS method
  can both overstate (shared pages) and miss sub-100 ms peaks; the PRS input is FILTER PASS or unset,
  PLINK2 runs on autosomes only (`--chr 1-22`), and the original PLINK2 input carries both allele
  orders of the first candidate; just-prs compares multi-allelic ALTs as one string, does not check
  the other allele and ran without reference-homozygote restoration; match rates are for the fixed
  input; the S3 memory medians are the fixed input's; the Conclusion names the OakVar-based system
  measured, not "the earlier configuration". Table 4 names the NTFS (`ntfs3`) disk.
- Table S2 (new, `make_tables.py:paper_table_s2`) lists every OakVar module that ran, with the store
  version beside each Just-DNA-Seq repo's GitHub version on 2026-10-11 and at its last commit by
  2023-05-07. Store and GitHub differ for `just_longevitymap` and `just_thrombophilia` (0.1.2 against
  0.2.0) and `just_lipidmetabolism` (0.1.2 against 0.1.1).
- Not changed, recorded here: the harness's PLINK2 count regex `valid predictor` matches no log line;
  the count used is the fallback `--score: N variants processed`. The two just-prs engines read
  haploid and half-called genotypes differently (Polars: no-call; DuckDB: dosage), which this genome
  does not exercise.

### Night 2 queue (scheduled 2026-10-12 23:27 for 2026-10-13 02:00)

- The user asked for more Generation I runs for an error estimate (calibration ×2, second caller ×3)
  and for a fairer pair beside the 183×: Generation II with the whole Ensembl join against OakVar
  with dbSNP only. "Like-for-like" was already dropped from the text; this pair measures it.
- Driver (`scripts/bench_annotation.py`): `--ensembl N` appends N Ensembl runs (`--ensembl-extra` is
  `--ensembl 1`), and `--full-label` names Generation I's full runs, here `dbsnp_only` (`-a dbsnp
  -t vcf`: no postaggregators, the VCF reporter). The docstring's "warm-state" note for `ensembl` is
  corrected. The Generation II pair still runs its ten modules and report on top, so the pair errs
  in OakVar's favour.
- Smoke tests: `oakvar-smoke-5000-dbsnp-only` (exit 0, 39.0 s on the primary's first 5,000 records;
  output `.vcf` and `.sqlite`) and `oakvar-smoke-5000-second-caller` (exit 0, 36.2 s on the DRAGEN
  VCF's first 5,000 records, every annotator and postaggregator finished, report written).
- Queue (`queue/60`–`65`, series under `/data/a3-bench/series/20261013T0200/`), in this order:
  `60` OakVar calibration ×2 (full), `61` OakVar primary ×3 (dbsnp_only), `62` Generation II primary
  ×3 (ensembl, no warm-up), `63`–`65` OakVar second caller ×1 each. The second-caller runs come last
  and are one job each, so if the user starts the app stack in the morning, the port check refuses
  the next run instead of timing beside it. Estimated end: about 12:00–13:00.
- Timer: `systemd-run --user --on-calendar='2026-10-13 02:00:00' --unit=bench-queue-2`.

### Night 2 results so far, and two decisions (2026-10-13, 16:00)

- Queue start 02:00:23 at load 11.1; the load gate held job 60 until 03:35. Jobs 60–63 exited 0
  (logs `051`–`054`); `64` is running, `65` queued (each about 3 h). The just-prs session's jobs
  `69`, `70` and `80` follow in the same queue and time nothing of ours.
- OakVar ran slower on night 2: calibration 7,785.3 and 8,281.0 s against 5,995.5 s on night 1. Its
  own step times put it in the I/O-bound steps (annotator 2,750 and 3,196 s against 1,741 s;
  aggregator and mapper slower too; postaggregator about the same), consistent with a colder page
  cache under the user's daytime work. **Decision (user):** pool all three calibration runs (n=3,
  median 7,785.3 s, 235×). The point of the extra runs is the spread a real machine shows between
  hot and cold caches and load, not a single reproducible number.
- The first run of each night-2 reference-database series was slow: OakVar dbSNP-only 7,041.5 s
  (annotator step 3,520.3 s, against 608.1 and 574.8 s after it) and Generation II with Ensembl
  229.7 s (join step 97.8 s, then 61.3 and 32.1 s). Neither series had a warm-up run.
  **Decision (user):** drop the first run of each as its warm-up; it also overlapped the user's
  coding. The pair is then 3,537.2 s against 103.1 s, 34× (24–57× over run pairs), a fifth of the
  183× with the report modules. The paper gives both ratios, says the larger one is consistent with
  modules compiled in advance into join-keyed tables without isolating it, and puts them in user
  terms: about one to three hours against half a minute to two and a half minutes.
- Correction to the night-2 queue note above: "the pair errs in OakVar's favour" is not established.
  Generation II also runs its modules and report, but OakVar's dbSNP-only run includes its GENCODE
  mapper (1,076–1,391 s), which Generation II has no counterpart of. The paper says the two are not
  the same computation.
- `make_tables.py`: Table 2 gains the pair section (`PAIR_SERIES`, `pair_runs`); S2 lists every
  OakVar run with its mode and whether Table 2 uses it; step times read every `oakvar/steps-*.tsv`
  (night 2: `steps-20261013T0200.tsv`, partial until `65` ends); new quoted lines for the pair, the
  warm-ups, Generation I's spread and the run ranges. Paper v0.4: B24, C22, C23 (Table 3), A3a and
  B28 updated, rounds bumped. After `65`: regenerate, update the second-caller row and counts.
- **Decision (user, ~16:30):** pool the nights. Same machine and specs; night 2 differs by light
  desktop use, which is the everyday condition, and OakVar slowing under it is OakVar's behaviour, not
  a method fault. The text reports roughly 200× with its spread for the report modules. Because the
  calibration and second-caller ratios divided night-2 OakVar by night-1 Generation II, Generation II
  is measured in the same light-use condition too: job `65` now starts with Generation II warm-up + 5
  full runs on the primary, calibration and second-caller genomes (series `…/20261013T0200/jdl/*-day2`),
  then its OakVar run. Edited before `65` started (the queue expands its job list once, so a new file
  would not run); not run at once because OakVar job `64` was being timed.

### Night 2 end (2026-10-13, 19:34)

- Job `64` exited 0 (second caller run 2, 8,337.6 s). Job `65`: the 18 Generation II light-use runs
  (warm-up + 5 full on primary, calibration and second caller; logs `056`–`058`) exited 0. Its OakVar
  run (log `059`) was killed after 1,277.8 s: the user's PackageKit update (19:29 CEST) upgraded
  docker-ce and containerd, and the daemon restarted at 19:34:08, ending the container (exit 125,
  "Error waiting for container … context canceled"). The row stays in `runs.csv`; `make_tables.py`
  skips it only because `FAILED` names its cause, and S2 lists it.
- The update also installed kernel 7.2.9-2; every run so far is on 7.2.9-1 (Table 4). A reboot before
  any further run changes the kernel, which Table 4 would then have to say.
- Pooled (user's decision above): full-run ratio 181× primary, 231× calibration, 146× second caller
  (n=2 OakVar), 146–231×, mean 186×. Generation II slowed more than OakVar in light use (calibration
  33.0–105.0 s, CPU down to 122% from ~375%), since it uses several cores. Paper v0.4 B24, A3a, B28,
  Tables 2 and 3 updated from `tables.md`.

### Second-caller run 3 again (queued 2026-10-15, ~13:40)

- The user re-queued the killed OakVar run as job `66` (`queue/66-oakvar-second-caller-3-rerun.sh`),
  OakVar only: job `65`'s Generation II runs had finished. Series directory
  `…/oakvar/second_caller-3-rerun`; the failed `second_caller-3` stays, listed in S2.
- It starts when the just-prs reference rescore (`81`, untimed, no load gate, ETA ~23:00) exits, then
  waits for the default load gate (1.5, at most 4 h). Run outside `run-queue.sh`, which would rerun
  `65` in full. Same kernel (7.2.9-1, not rebooted); Docker is now 29.9.0 (runs 1 and 2: 29.8.2), which
  the preflight line records.
- After it: regenerate `tables.md`, then update the second-caller ratio (n=3) and the pooled range in
  paper v0.4 (B24, A3a, B28, Tables 2 and 3).
