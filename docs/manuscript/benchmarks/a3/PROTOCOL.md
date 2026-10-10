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
