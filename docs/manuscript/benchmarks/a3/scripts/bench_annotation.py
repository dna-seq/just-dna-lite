#!/usr/bin/env python3
"""A3 annotation benchmark driver: time `uv run annotate` (Generation II) or an OakVar container
(Generation I) on one genome, one row per run in runs.csv.

Standard library plus psutil. It never imports the pipelines package, so the measuring process
stays out of the measured tree and off the Polars fork path.

Run types:
  warmup  first run of a series; fills the module cache and the warm state; excluded from results
  cold    fresh DAGSTER_HOME and output directory, OS page cache dropped right before
  warm    repeat run on the warm state (the normalized parquet is reused, so the VCF is not read)
  full    fresh DAGSTER_HOME and output directory, page cache NOT dropped: the whole pipeline,
          normalization included, with warm OS caches. Its normalize_s is the offset that turns a
          warm time into a full one, and it is the like-for-like counterpart of an OakVar run.
  ensembl run with --ensembl (Generation II only), appended after the series (--ensembl N). It runs
          annotate_all_job, which normalizes again, so it is a full run plus the Ensembl join, on the
          series' shared Dagster instance.
  Generation I runs are `full` unless --full-label names them otherwise (dbsnp_only: OakVar with
  the dbSNP annotator and the VCF reporter only, the counterpart of a Generation II ensembl run).

Measurement per run:
  cli_wall_s   wall time of the whole command (includes Python start-up and module discovery)
  job_wall_s   Dagster run record, creation to end: "job submission to report written"
  <step>_s     each Dagster step, STEP_START to STEP_SUCCESS/FAILURE
  peak/mean_rss_mb  sum of RSS over the process tree, sampled at 10 Hz (psutil, children recursive;
               shared pages count once per process, so this is an upper bound)
  cpu_pct      user+system CPU of the command and every descendant it reaped (wait4 rusage) / wall
"""

import argparse
import csv
import json
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

SCRIPTS = Path(__file__).resolve().parent
A3 = SCRIPTS.parent
DROP_CACHES_IMAGE = (
    "alpine:3.20@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc"
)
STEP_COLUMNS = {
    "user_vcf_normalized": "normalize_s",
    "user_hf_module_annotations": "annotate_s",
    "user_longevity_report": "report_s",
    "user_annotated_vcf": "ensembl_s",
    "user_annotated_vcf_duckdb": "ensembl_duckdb_s",
}
FIELDS = [
    "tool", "genome", "run_type", "index", "order", "seed", "prev_run_type", "started_at",
    "load1_before", "cache_dropped", "buffcache_before_mb", "buffcache_after_mb",
    "cli_wall_s", "job_wall_s", *STEP_COLUMNS.values(), "peak_rss_mb", "mean_rss_mb", "cpu_pct",
    "samples", "exit", "variants_annotated", "run_id", "job_name", "steps_json", "run_dir",
]


def buffcache_mb() -> float:
    vm = psutil.virtual_memory()
    return round((vm.buffers + vm.cached) / 2**20, 1)


def drop_page_cache() -> tuple[float, float]:
    """Drop the host page cache through a privileged container (sudo needs a password here)."""
    before = buffcache_mb()
    subprocess.run(
        ["docker", "run", "--rm", "--privileged", DROP_CACHES_IMAGE,
         "sh", "-c", "sync; echo 3 > /proc/sys/vm/drop_caches"],
        check=True,
    )
    return before, buffcache_mb()


def wait_for_quiet(gate: float, max_wait_s: float) -> float:
    """Block until the 1-minute load average is under the gate; return the load at start."""
    waited = 0.0
    while os.getloadavg()[0] > gate:
        if waited >= max_wait_s:
            sys.exit(f"load {os.getloadavg()[0]:.2f} stayed above {gate} for {max_wait_s:.0f}s")
        print(f"  load {os.getloadavg()[0]:.2f} > {gate}, waiting", flush=True)
        time.sleep(30)
        waited += 30
    return round(os.getloadavg()[0], 2)


class TreeSampler(threading.Thread):
    """Sum RSS over a process and all its descendants at a fixed rate."""

    def __init__(self, root_pid_fn, hz: float = 10.0) -> None:
        super().__init__(daemon=True)
        self.root_pid_fn = root_pid_fn
        self.period = 1.0 / hz
        self.stop = threading.Event()
        self.samples: list[int] = []

    def run(self) -> None:
        while not self.stop.is_set():
            pid = self.root_pid_fn()
            if pid:
                total = 0
                try:
                    root = psutil.Process(pid)
                    procs = [root, *root.children(recursive=True)]
                except psutil.NoSuchProcess:
                    procs = []
                for proc in procs:
                    try:
                        total += proc.memory_info().rss
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                if total:
                    self.samples.append(total)
            self.stop.wait(self.period)


def run_measured(cmd: list[str], env: dict, cwd: Path, log_path: Path) -> dict:
    """Run cmd, sampling its tree; return wall, rusage CPU, RSS stats, exit and captured stdout."""
    with log_path.open("w", encoding="utf-8") as log:
        t0 = time.monotonic()
        proc = subprocess.Popen(cmd, env=env, cwd=cwd, stdout=log, stderr=subprocess.STDOUT)
        sampler = TreeSampler(lambda: proc.pid)
        sampler.start()
        _, status, rusage = os.wait4(proc.pid, 0)
        wall = time.monotonic() - t0
        sampler.stop.set()
        sampler.join()
    proc.returncode = os.waitstatus_to_exitcode(status)
    cpu = rusage.ru_utime + rusage.ru_stime
    samples = sampler.samples
    return {
        "cli_wall_s": round(wall, 3),
        "cpu_pct": round(100 * cpu / wall, 1) if wall else None,
        "peak_rss_mb": round(max(samples) / 2**20, 1) if samples else None,
        "mean_rss_mb": round(sum(samples) / len(samples) / 2**20, 1) if samples else None,
        "samples": len(samples),
        "exit": proc.returncode,
    }


def stage_times(jdl: Path, dagster_home: Path, run_id: str) -> dict:
    env = {**os.environ, "DAGSTER_HOME": str(dagster_home)}
    out = subprocess.run(
        ["uv", "run", "--no-sync", "python", "-I", str(SCRIPTS / "dagster_stage_times.py"), run_id],
        cwd=jdl, env=env, check=True, capture_output=True, text=True,
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def jdl_run(args, run_type: str, run_dir: Path, warm_state: Path) -> dict:
    """One Generation II run. Cold runs get their own instance; the rest share the warm state."""
    state = run_dir if run_type in ("cold", "full") else warm_state
    dagster_home = state / "dagster"
    output_dir = state / "output"
    dagster_home.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "DAGSTER_HOME": str(dagster_home),
        "JUST_DNA_PIPELINES_OUTPUT_DIR": str(output_dir),
        "JUST_DNA_PIPELINES_INPUT_DIR": str(args.input_dir),
        "JUST_DNA_PIPELINES_CACHE_DIR": str(args.cache_dir),
        # Its modules.yaml (a3/jdl/modules.yaml) names the S4 module set as the only source.
        "JUST_DNA_PIPELINES_ROOT": str(args.jdl_root),
    }
    cmd = ["uv", "run", "--no-sync", "annotate", str(args.vcf), "--user", "bench"]
    for name in args.modules:
        cmd += ["-m", name]
    if run_type == "ensembl":
        cmd.append("--ensembl")
    result = run_measured(cmd, env, args.jdl, run_dir / "cli.log")
    log_text = (run_dir / "cli.log").read_text(encoding="utf-8", errors="replace")
    match = re.findall(r"run_id=([0-9a-f-]{36})", log_text)
    result["run_id"] = match[-1] if match else None
    # A fast run that annotated nothing measures nothing; keep the count beside the time.
    annotated = re.findall(r"Variants annotated: (\d+)", log_text)
    result["variants_annotated"] = int(annotated[-1]) if annotated else None
    if result["run_id"]:
        timing = stage_times(args.jdl, dagster_home, result["run_id"])
        result["job_name"] = timing["job_name"]
        if timing["end_time"]:
            result["job_wall_s"] = round(timing["end_time"] - timing["create_timestamp"], 3)
        for step, info in timing["steps"].items():
            column = STEP_COLUMNS.get(step)
            if column:
                result[column] = info["seconds"]
        result["steps_json"] = json.dumps(timing["steps"], sort_keys=True)
    return result


def oakvar_run(args, run_type: str, run_dir: Path, warm_state: Path) -> dict:
    """One Generation I run in the OakVar container. Every run writes a fresh job directory."""
    job_dir = run_dir / "job"
    job_dir.mkdir(parents=True, exist_ok=True)
    name = f"a3-ov-{args.genome}-{run_dir.name}"
    cmd = [
        "docker", "run", "--rm", "--name", name, "--user", f"{os.getuid()}:{os.getgid()}",
        "-v", f"{args.oakvar_home}:/oakvar", "-v", f"{args.vcf.parent}:/input:ro",
        "-v", f"{job_dir}:/job", args.oakvar_image,
        "run", f"/input/{args.vcf.name}", "-l", "hg38", "-d", "/job", *args.oakvar_args,
    ]

    def container_pid() -> int | None:
        out = subprocess.run(["docker", "inspect", "-f", "{{.State.Pid}}", name],
                             capture_output=True, text=True)
        pid = out.stdout.strip()
        return int(pid) if out.returncode == 0 and pid not in ("", "0") else None

    cached: dict[str, int | None] = {"pid": None}

    def root_pid() -> int | None:
        if cached["pid"] is None or not psutil.pid_exists(cached["pid"]):
            cached["pid"] = container_pid()
        return cached["pid"]

    with (run_dir / "cli.log").open("w", encoding="utf-8") as log:
        t0 = time.monotonic()
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        sampler = TreeSampler(root_pid)
        sampler.start()
        proc.wait()
        wall = time.monotonic() - t0
        sampler.stop.set()
        sampler.join()
    samples = sampler.samples
    result = {
        "cli_wall_s": round(wall, 3),
        "peak_rss_mb": round(max(samples) / 2**20, 1) if samples else None,
        "mean_rss_mb": round(sum(samples) / len(samples) / 2**20, 1) if samples else None,
        "samples": len(samples),
        "exit": proc.returncode,
        "job_name": "ov run " + " ".join(args.oakvar_args),
    }
    # OakVar writes its own per-stage timings into <job>/<input>.log; keep the whole job log.
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tool", choices=["jdl", "oakvar"], required=True)
    parser.add_argument("--genome", required=True, help="label written to every row")
    parser.add_argument("--vcf", type=Path, required=True)
    parser.add_argument("--series-dir", type=Path, required=True)
    parser.add_argument("--cold", type=int, default=3)
    parser.add_argument("--warm", type=int, default=11)
    parser.add_argument("--full", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20261010)
    parser.add_argument("--no-warmup", action="store_true")
    parser.add_argument("--ensembl-extra", action="store_true", help="same as --ensembl 1")
    parser.add_argument("--ensembl", type=int, default=0, help="Ensembl runs appended to the series")
    parser.add_argument("--full-label", default="full",
                        help="run_type written for the full runs (Generation I only)")
    parser.add_argument("--load-gate", type=float, default=1.5)
    parser.add_argument("--max-wait", type=float, default=4 * 3600)
    parser.add_argument("--out", type=Path, default=A3 / "runs.csv")
    parser.add_argument("--dry-run", action="store_true", help="print the schedule and exit")
    # Generation II
    parser.add_argument("--jdl", type=Path, default=Path("/data/a3-bench/jdl"))
    parser.add_argument("--jdl-root", type=Path, default=Path("/data/a3-bench/jdl-root"))
    parser.add_argument("--input-dir", type=Path, default=Path("/data/a3-bench/jdl-input"))
    parser.add_argument("--cache-dir", type=Path, default=Path("/data/just-dna-cache"))
    parser.add_argument("-m", "--module", dest="modules", action="append", default=[])
    # Generation I
    parser.add_argument("--oakvar-image", default="jdl-bench-oakvar:2.13.1")
    parser.add_argument("--oakvar-home", type=Path, default=Path("/data/a3-bench/oakvar/home-2.13.1"))
    parser.add_argument("--oakvar-args", nargs=argparse.REMAINDER, default=[])
    args = parser.parse_args()

    if args.full_label != "full" and args.tool != "oakvar":
        sys.exit("--full-label is for Generation I runs only")
    order = ["cold"] * args.cold + ["warm"] * args.warm + [args.full_label] * args.full
    random.Random(args.seed).shuffle(order)
    schedule = ([] if args.no_warmup else ["warmup"]) + order
    schedule += ["ensembl"] * max(args.ensembl, int(args.ensembl_extra))
    print(f"schedule ({args.tool}, {args.genome}, seed {args.seed}): {' '.join(schedule)}", flush=True)
    if args.dry_run:
        return
    if args.tool == "jdl":
        if not args.modules:
            sys.exit("pass the module set explicitly with -m")
        # Place the VCF once, outside any timed run; annotate then uses it where it is.
        placed = args.input_dir / "users" / "bench" / args.vcf.name
        if not placed.exists():
            placed.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(args.vcf, placed)
        args.vcf = placed

    warm_state = args.series_dir / "warm_state"
    write_header = not args.out.exists()
    counters: dict[str, int] = {}
    prev = None
    for position, run_type in enumerate(schedule):
        counters[run_type] = counters.get(run_type, 0) + 1
        run_dir = args.series_dir / f"{position:02d}_{run_type}{counters[run_type]}"
        if run_dir.exists():
            sys.exit(f"{run_dir} exists; a series directory is used once")
        run_dir.mkdir(parents=True)
        load1 = wait_for_quiet(args.load_gate, args.max_wait)
        dropped = (None, None)
        if run_type == "cold":
            dropped = drop_page_cache()
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        print(f"[{position}] {run_type}{counters[run_type]} load={load1} start={started}", flush=True)
        runner = jdl_run if args.tool == "jdl" else oakvar_run
        result = runner(args, run_type, run_dir, warm_state)
        row = {
            "tool": args.tool, "genome": args.genome, "run_type": run_type,
            "index": counters[run_type], "order": position, "seed": args.seed,
            "prev_run_type": prev, "started_at": started, "load1_before": load1,
            "cache_dropped": run_type == "cold",
            "buffcache_before_mb": dropped[0], "buffcache_after_mb": dropped[1],
            "run_dir": str(run_dir), **result,
        }
        (run_dir / "row.json").write_text(json.dumps(row, indent=1) + "\n")
        with args.out.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
            if write_header:
                writer.writeheader()
                write_header = False
            writer.writerow(row)
        print(f"    exit={row['exit']} cli={row['cli_wall_s']}s job={row.get('job_wall_s')}s "
              f"peak={row['peak_rss_mb']}MB cpu={row.get('cpu_pct')}%", flush=True)
        prev = run_type
        if row["exit"] != 0:
            sys.exit(f"run failed, see {run_dir / 'cli.log'}")


if __name__ == "__main__":
    main()
