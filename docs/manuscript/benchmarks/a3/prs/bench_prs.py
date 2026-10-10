#!/usr/bin/env python3
"""A3 PRS benchmark: just-prs (Polars, DuckDB) vs PLINK2 on one genome, per PGS ID.

The engines, the memory measurement and PLINK2's score input are just-prs's own
`benchmarks/benchmark_engines.py` at tag v0.10.1, imported unchanged from a clone of that tag
(--upstream). What this harness changes:

  * the PGS IDs come from a committed list instead of "the first N that download";
  * every PLINK2 call keeps its .log, stdout+stderr and exit code, so a failure has a cause;
  * PLINK2's score-input preparation is timed as its own column (`prep_sec`). Upstream starts
    PLINK2's clock after that step, while the Polars/DuckDB clocks include parsing the file;
  * --config fixed removes the two benchmark-input defects found on 2026-10-10
    (r-gap REPORT.md, causes B and D) and the liftover duplicates that abort PLINK2:
      - the pgen is built from PASS records only (--vcf-filter), like the just-prs input;
      - every `/`-separated hm_inferOtherAllele candidate gives an ID, not only the first;
      - IDs that two scoring rows share (GRCh37 liftover collisions) have their weights summed,
        which is what just-prs computes when it scores both rows against one genotype.
    --config original builds both exactly as upstream does.

Usage (from a uv environment with just-prs 0.10.1):
  bench_prs.py --config original --vcf antonkulaga.vcf --upstream /data/a3-bench/just-prs \\
      --plink2 /data/a3-bench/prs/plink2/plink2 --work /data/a3-bench/prs --out a3/prs/original
"""

import argparse
import gzip
import hashlib
import io
import json
import os
import platform
import re
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path

import polars as pl
import psutil

A3_PRS = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", choices=["original", "fixed"], required=True)
    parser.add_argument("--vcf", type=Path, required=True)
    parser.add_argument("--upstream", type=Path, required=True, help="just-prs clone at v0.10.1")
    parser.add_argument("--plink2", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True, help="large intermediates")
    parser.add_argument("--out", type=Path, required=True, help="committed results")
    parser.add_argument("--ids", type=Path, default=A3_PRS / "pgs_ids.txt")
    parser.add_argument("--warmup-ids", type=Path, default=A3_PRS / "warmup_ids.txt")
    parser.add_argument("--limit", type=int, default=0, help="first N IDs only (smoke test)")
    return parser.parse_args()


ARGS = parse_args()
sys.path.insert(0, str(ARGS.upstream / "just-prs" / "benchmarks"))
import benchmark_engines as up  # noqa: E402  (the upstream script, imported from the pinned clone)
from just_prs.normalize import VcfFilterConfig, normalize_vcf  # noqa: E402
from just_prs.prs import _normalize_scoring_columns  # noqa: E402
from just_prs.scoring import download_scoring_file, parse_scoring_file  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_ids(path: Path) -> list[str]:
    return [line.split("#")[0].strip() for line in path.read_text().splitlines() if line.split("#")[0].strip()]


def build_pgen(config: str, vcf: Path, plink2: Path, work: Path, out: Path) -> Path:
    """The pgen PLINK2 scores against: upstream's command, plus --vcf-filter when fixed."""
    prefix = work / f"pgen_{config}" / "benchmark_pgen"
    prefix.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(plink2), "--vcf", str(vcf)]
    if config == "fixed":
        cmd.append("--vcf-filter")
    cmd += ["--set-all-var-ids", "@:#:$r:$a", "--new-id-max-allele-len", "10000",
            "--chr", "1-22", "--make-pgen", "--out", str(prefix), "--threads", "4"]
    if not Path(str(prefix) + ".pgen").exists():
        t0 = time.perf_counter()
        result = subprocess.run(cmd, capture_output=True, text=True)
        (out / "pgen_build.json").write_text(json.dumps({
            "cmd": cmd, "exit": result.returncode, "seconds": round(time.perf_counter() - t0, 3),
        }, indent=1) + "\n")
        (out / "pgen_build.stdout").write_text(result.stdout + result.stderr)
        if result.returncode != 0:
            sys.exit(f"pgen build failed, see {out / 'pgen_build.stdout'}")
    log = Path(str(prefix) + ".log")
    (out / "pgen_build.log").write_text(log.read_text())
    return prefix


def fixed_score_input(scoring_file: Path, pgs_id: str, tmp_dir: Path) -> Path | None:
    """PLINK2 --score input with every inferred other allele and liftover duplicates merged."""
    with gzip.open(scoring_file, "rt") as fh:
        body = "".join(line for line in fh if not line.startswith("#"))
    df = pl.read_csv(io.StringIO(body), separator="\t", infer_schema_length=10000,
                     schema_overrides={"chr_name": pl.Utf8, "chr_position": pl.Utf8,
                                       "hm_chr": pl.Utf8, "hm_pos": pl.Utf8})
    other = "other_allele" if "other_allele" in df.columns else "hm_inferOtherAllele"
    if other not in df.columns or "hm_chr" not in df.columns:
        return None
    df = df.filter(
        pl.col("effect_allele").is_not_null() & pl.col("effect_weight").is_not_null()
        & pl.col("hm_chr").is_not_null() & pl.col("hm_pos").is_not_null()
        & pl.col(other).is_not_null() & (pl.col(other).cast(pl.Utf8).str.len_chars() > 0)
    ).with_row_index("row").with_columns(
        pl.col("hm_chr").str.replace("(?i)^chr", "").alias("c"),
        pl.col(other).cast(pl.Utf8).str.split("/").alias("o"),
    ).explode("o", empty_as_null=True)
    ids = pl.concat([
        df.select("row", (pl.col("c") + ":" + pl.col("hm_pos") + ":" + pl.col("o") + ":"
                          + pl.col("effect_allele")).alias("variant_id"), "effect_allele", "effect_weight"),
        df.select("row", (pl.col("c") + ":" + pl.col("hm_pos") + ":" + pl.col("effect_allele") + ":"
                          + pl.col("o")).alias("variant_id"), "effect_allele", "effect_weight"),
    ])
    merged = (
        ids.unique(subset=["row", "variant_id"], maintain_order=True)
        .group_by("variant_id", "effect_allele", maintain_order=True)
        .agg(pl.col("effect_weight").cast(pl.Float64).sum())
    )
    if merged.height == 0:
        return None
    path = tmp_dir / f"{pgs_id}_score_input.txt"
    merged.write_csv(path, separator="\t")
    return path


def score_plink2_kept(config: str, pgs_id: str, scoring_file: Path, pgen: Path, plink2: Path,
                      run_dir: Path) -> dict:
    """Upstream's PLINK2 call and memory sampling, keeping every file it writes."""
    total = _normalize_scoring_columns(parse_scoring_file(scoring_file)).collect().height
    run_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    if config == "original":
        score_input = up._prepare_plink2_score_input(scoring_file, pgs_id, run_dir)
    else:
        score_input = fixed_score_input(scoring_file, pgs_id, run_dir)
    prep = time.perf_counter() - t0
    row = {"pgs_id": pgs_id, "engine": "plink2", "variants_total": total, "prep_sec": round(prep, 4),
           "memory_method": "subprocess_peak_rss_100ms"}
    if score_input is None:
        return {**row, "error": "no score input"}
    out_prefix = run_dir / pgs_id
    cmd = [str(plink2), "--pfile", str(pgen), "--score", str(score_input), "1", "2", "3", "header",
           "no-mean-imputation", "cols=scoresums", "--out", str(out_prefix), "--threads", "4"]
    with (run_dir / f"{pgs_id}.stdout").open("w") as stdout:
        t0 = time.perf_counter()
        proc = subprocess.Popen(cmd, stdout=stdout, stderr=subprocess.STDOUT)
        peak = up._track_subprocess_peak_memory(proc.pid)
        proc.wait()
        elapsed = time.perf_counter() - t0
    row.update(elapsed_sec=round(elapsed, 4), peak_memory_mb=round(peak, 2), plink2_exit=proc.returncode)
    sscore = Path(str(out_prefix) + ".sscore")
    log_text = Path(str(out_prefix) + ".log").read_text() if Path(str(out_prefix) + ".log").exists() else ""
    errors = [line for line in log_text.splitlines() if line.startswith("Error")]
    if proc.returncode != 0 or not sscore.exists():
        return {**row, "error": errors[0] if errors else f"exit {proc.returncode}"}
    df = pl.read_csv(sscore, separator="\t")
    column = next(c for c in df.columns if "SCORE" in c.upper() and "SUM" in c.upper())
    matched = 0
    for pattern in (r"--score:\s+(\d+)\s+valid predictor", r"--score:\s+(\d+)\s+variant"):
        found = re.search(pattern, log_text)
        if found:
            matched = int(found.group(1))
            break
    return {**row, "score": float(df[column][0]), "variants_matched": matched}


def score_in_process(engine: str, fn) -> dict:
    (score, matched, total), elapsed, peak = up.measure_engine(fn)
    return {"engine": engine, "elapsed_sec": round(elapsed, 4), "peak_memory_mb": round(peak, 2),
            "score": score, "variants_matched": matched, "variants_total": total,
            "memory_method": "process_rss_delta_10ms"}


def main() -> None:
    args = ARGS
    args.out.mkdir(parents=True, exist_ok=True)
    args.work.mkdir(parents=True, exist_ok=True)
    ids = read_ids(args.ids)
    warmup = read_ids(args.warmup_ids)
    if args.limit:
        ids = ids[: args.limit]

    # Inputs, all recorded before any timing.
    scores_dir = args.work / "scores"
    downloads = []
    for pgs_id in warmup + ids:
        try:
            path = download_scoring_file(pgs_id, scores_dir, genome_build=up.GENOME_BUILD)
            downloads.append({"pgs_id": pgs_id, "file": path.name, "sha256": sha256(path), "error": None})
        except Exception as exc:  # recorded per ID, as upstream skips an unavailable file
            downloads.append({"pgs_id": pgs_id, "file": None, "sha256": None, "error": str(exc)})
    pl.DataFrame(downloads).write_csv(args.out / "scoring_files.csv")
    available = {d["pgs_id"]: scores_dir / d["file"] for d in downloads if d["file"]}

    normalized = args.work / "vcf" / (args.vcf.stem + "_normalized.parquet")
    if not normalized.exists():
        normalized.parent.mkdir(parents=True, exist_ok=True)
        normalize_vcf(args.vcf, normalized, config=VcfFilterConfig(pass_filters=["PASS", "."]))
    genotypes_lf = pl.scan_parquet(normalized)
    pgen = build_pgen(args.config, args.vcf, args.plink2, args.work, args.out)
    plink_dir = args.out / "plink2_runs"

    meta = {
        "config": args.config, "vcf": str(args.vcf), "vcf_sha256": sha256(args.vcf),
        "normalized_rows": genotypes_lf.select(pl.len()).collect().item(),
        "plink2": str(args.plink2), "plink2_sha256": sha256(args.plink2),
        "plink2_version": subprocess.run([str(args.plink2), "--version"], capture_output=True,
                                         text=True).stdout.strip(),
        "just_prs": version("just-prs"), "polars": version("polars"), "duckdb": version("duckdb"),
        "upstream_script": str(args.upstream / "just-prs/benchmarks/benchmark_engines.py"),
        "upstream_commit": subprocess.run(["git", "-C", str(args.upstream), "rev-parse", "HEAD"],
                                          capture_output=True, text=True).stdout.strip(),
        "python": sys.version.split()[0], "platform": platform.platform(),
        "warmup_ids": warmup, "ids": ids, "load1_start": round(os.getloadavg()[0], 2),
    }

    for pgs_id in warmup:
        if pgs_id in available:
            sf = available[pgs_id]
            up.score_polars(pgs_id, sf, genotypes_lf)
            up.score_duckdb(pgs_id, sf, normalized)
            score_plink2_kept(args.config, pgs_id, sf, pgen, args.plink2, args.work / "warmup")

    rows = []
    for index, pgs_id in enumerate(ids, 1):
        if pgs_id not in available:
            rows.append({"pgs_id": pgs_id, "engine": "all", "error": "scoring file unavailable"})
            continue
        sf = available[pgs_id]
        for engine, fn in (
            ("polars", lambda: up.score_polars(pgs_id, sf, genotypes_lf)),
            ("duckdb", lambda: up.score_duckdb(pgs_id, sf, normalized)),
        ):
            try:
                rows.append({"pgs_id": pgs_id, **score_in_process(engine, fn)})
            except Exception as exc:  # recorded, as upstream does
                rows.append({"pgs_id": pgs_id, "engine": engine, "error": repr(exc)})
        rows.append(score_plink2_kept(args.config, pgs_id, sf, pgen, args.plink2, plink_dir))
        last = rows[-3:]
        print(f"[{index}/{len(ids)}] {pgs_id} " + " ".join(
            f"{r['engine']}={r.get('elapsed_sec')}" + ("!" if r.get("error") else "") for r in last), flush=True)

    meta["load1_end"] = round(os.getloadavg()[0], 2)
    meta["ram_gb"] = round(psutil.virtual_memory().total / 2**30, 1)
    pl.DataFrame(rows, infer_schema_length=None).write_csv(args.out / "benchmark_results.csv")
    (args.out / "metadata.json").write_text(json.dumps(meta, indent=1) + "\n")
    # Keep PLINK2's own logs and outputs small enough to commit: drop the score inputs.
    for path in plink_dir.glob("*_score_input.txt"):
        path.unlink()


if __name__ == "__main__":
    main()
