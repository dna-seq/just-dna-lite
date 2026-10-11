#!/usr/bin/env python3
"""Generate every benchmark table of Paper 1 (Tables 2-6, S2, S3) from the committed A3 files.

Inputs, all in docs/manuscript/benchmarks/a3/: runs.csv, inputs.json, env.json, historical.csv,
oakvar/steps-*.tsv, oakvar/installed-2.13.1.json, prs/results-*/{fixed,original}/benchmark_results.csv.
Output: tables.md beside them. No number in the paper's Sections 4.1, 4.2 or S2-S3 is typed by hand;
each one is in tables.md.

Standard library only:

    python3 -I docs/manuscript/benchmarks/a3/scripts/make_tables.py
"""

import csv
import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

A3 = Path(__file__).resolve().parent.parent
GENOMES = ("primary", "second_caller", "community_reference", "calibration")
GENOME_LABEL = {
    "primary": "Primary (public, Zenodo 18370498)",
    "second_caller": "Second caller (public, Zenodo 19487816)",
    "community_reference": "Community reference (HG002, DeepVariant case study)",
    "calibration": "Calibration (private, the 2023 benchmark file)",
}
JDL_TYPES = ("warm", "full", "cold")
RUN_LABEL = {
    "warm": "Generation II, warm",
    "full": "Generation II, full",
    "cold": "Generation II, cold",
    "ensembl": "Generation II, full + Ensembl (annotate_all_job)",
    "oakvar": "Generation I (OakVar 2.13.1), full",
}
LARGE_SCORE = 1_000_000
ENGINES = ("duckdb", "polars", "plink2")
ENGINE_LABEL = {"duckdb": "just-prs DuckDB", "polars": "just-prs Polars", "plink2": "PLINK2"}


def summary(xs: list[float]) -> dict:
    n = len(xs)
    sd = st.stdev(xs) if n > 1 else None
    return {
        "n": n, "mean": st.mean(xs), "sd": sd, "sem": sd / math.sqrt(n) if sd is not None else None,
        "median": st.median(xs), "min": min(xs), "max": max(xs),
    }


def f(x: float | None, digits: int = 1) -> str:
    return "—" if x is None else f"{x:,.{digits}f}"


def table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def time_cells(s: dict, digits: int = 1) -> list[str]:
    rng = f"{f(s['median'], digits)} ({f(s['min'], digits)}–{f(s['max'], digits)})"
    if s["n"] == 1:
        rng = f(s["median"], digits)
    mean = f"{f(s['mean'], digits)} ± {f(s['sem'], digits)}" if s["sem"] is not None else "—"
    return [str(s["n"]), rng, mean, f(s["sd"], digits)]


def load_runs() -> dict[tuple[str, str, str], list[dict]]:
    groups = defaultdict(list)
    for r in csv.DictReader((A3 / "runs.csv").open()):
        assert r["exit"] == "0", r
        groups[(r["tool"], r["genome"], r["run_type"])].append(r)
    return groups


def col(rows: list[dict], name: str) -> list[float]:
    return [float(r[name]) for r in rows if r[name] not in ("", "None")]


def table2(runs) -> tuple[str, dict]:
    out_rows = []
    ratios = {}
    for g in GENOMES:
        oak = runs.get(("oakvar", g, "full"))
        oak_med = st.median(col(oak, "cli_wall_s")) if oak else None
        out_rows.append([f"**{GENOME_LABEL[g]}**", "", "", "", "", ""])
        for t in JDL_TYPES:
            s = summary(col(runs[("jdl", g, t)], "cli_wall_s"))
            ratio = "—"
            if oak_med is not None and t in ("full", "cold"):
                ratios[(g, t)] = oak_med / s["median"]
                ratio = f"{ratios[(g, t)]:,.0f}×"
            out_rows.append([RUN_LABEL[t], *time_cells(s), ratio])
        if oak:
            out_rows.append([RUN_LABEL["oakvar"], *time_cells(summary(col(oak, "cli_wall_s"))),
                             "1× (ref.)"])
    text = table(["Genome / run", "*n*", "Median (min–max), s", "Mean ± SEM, s", "SD, s",
                  "Generation I ÷ this (medians)"], out_rows)
    return text, ratios


def ensembl_cell(rs: list[dict]) -> str:
    """The Ensembl join, plus the cache verification step that annotate_all_job runs before it."""
    steps = [json.loads(r["steps_json"]) for r in rs]
    join = st.median(s["user_annotated_vcf_duckdb"]["seconds"] for s in steps)
    check = st.median(s["ensembl_annotations"]["seconds"] for s in steps)
    return f"{f(join)} (+ {f(check)} cache check)"


def table3(runs) -> str:
    rows = []
    for g in GENOMES:
        for t in (*JDL_TYPES, "ensembl"):
            rs = runs.get(("jdl", g, t))
            if not rs:
                continue
            def med(c: str, digits: int = 1) -> str:
                return f(st.median(col(rs, c)), digits) if col(rs, c) else "—"

            pk = col(rs, "peak_rss_mb")
            rows.append([GENOME_LABEL[g].split(" (")[0], RUN_LABEL[t], str(len(rs)),
                         med("normalize_s"), med("annotate_s"), med("report_s"),
                         ensembl_cell(rs) if t == "ensembl" else "—", med("job_wall_s"),
                         f"{f(st.median(pk), 0)} ({f(max(pk), 0)})", med("mean_rss_mb", 0),
                         med("cpu_pct", 0)])
        oak = runs.get(("oakvar", g, "full"))
        if oak:
            pk = col(oak, "peak_rss_mb")
            rows.append([GENOME_LABEL[g].split(" (")[0], RUN_LABEL["oakvar"], str(len(oak)),
                         "—", "—", "—", "—", "—", f"{f(st.median(pk), 0)} ({f(max(pk), 0)})",
                         f(st.median(col(oak, "mean_rss_mb")), 0), "not measured"])
    return table(["Genome", "Run", "*n*", "Normalize, s", "Annotate, s", "Report, s", "Ensembl, s",
                  "Job, s", "Peak RSS, MB: median (max)", "Mean RSS, MB", "CPU, %"], rows)


def table4() -> str:
    env = json.loads((A3 / "env.json").read_text())
    m, c = env["machine"], env["code"]
    disk = m["data_mount"]["disk"]
    machine_rows = [
        ["CPU", f"{m['cpu_model']} ({m['cores']} cores, {m['threads']} threads, boost {m['frequency_boost']}, governor {m['governor']})"],
        ["RAM", f"{m['ram_bytes'] / 2**30:.0f} GiB"],
        ["Storage (data and caches)", f"{disk['model']} ({'HDD' if disk['rotational'] else 'SATA SSD'}), {m['data_mount']['fstype']}"],
        ["OS kernel", m["kernel"]],
        ["Generation II", f"just-dna-lite {c['packages']['just-dna-lite']} (commit {c['just_dna_lite_commit'][:7]}), Python {c['python']}, Polars {c['packages']['polars']}, polars-bio {c['packages']['polars-bio']}, DuckDB {c['packages']['duckdb']}, Dagster {c['packages']['dagster']}"],
        ["Generation I", f"OakVar {env['generation_i']['oakvar']} in Docker ({env['docker'] if 'docker' in env else m['docker']})"],
        ["Modules (Generation II)", ", ".join(f"{x['name']} {x['version']}" for x in env["modules"])],
    ]
    inputs = json.loads((A3 / "inputs.json").read_text())
    in_rows = []
    for g in GENOMES:
        d = inputs[g]
        caller = next((h.split("=", 1)[1] for h in d["caller_headers"] if h.startswith("##DeepVariant_version=")), None)
        caller = f"DeepVariant {caller}" if caller else "DRAGEN " + next(
            h.split('Version="SW: ')[1].split(",")[0] for h in d["caller_headers"] if "ID=dragen," in h)
        in_rows.append([GENOME_LABEL[g], f"{d['records']:,}", f"{d['snv_records']:,}", f"{d['other_records']:,}",
                        caller, d["md5"]])
    return (table(["Parameter", "Value"], machine_rows) + "\n\n"
            + table(["Input VCF", "Records", "SNV records", "Other records", "Caller", "md5"], in_rows))


def load_prs(config: str) -> dict[str, dict[str, dict]]:
    path = next(A3.glob(f"prs/results-*/{config}/benchmark_results.csv"))
    by_id: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in csv.DictReader(path.open()):
        by_id[r["pgs_id"]][r["engine"]] = r
    return by_id


def scored(r: dict) -> bool:
    return r["score"] not in ("", "None") and r.get("plink2_exit") in ("", "0", None)


def table5(config: str) -> str:
    by_id = load_prs(config)
    done = {e: [i for i, d in by_id.items() if e in d and scored(d[e])] for e in ENGINES}
    paired = sorted(set.intersection(*(set(v) for v in done.values())))
    plink_med = st.median(float(by_id[i]["plink2"]["elapsed_sec"]) for i in done["plink2"])
    rows = []
    for e in ENGINES:
        t = [float(by_id[i][e]["elapsed_sec"]) for i in done[e]]
        small = [float(by_id[i][e]["elapsed_sec"]) for i in done[e]
                 if int(by_id[i][e]["variants_total"]) < LARGE_SCORE]
        per_id = [float(by_id[i]["plink2"]["elapsed_sec"]) / float(by_id[i][e]["elapsed_sec"]) for i in paired]
        rows.append([ENGINE_LABEL[e], str(len(t)), f(st.median(t), 3), f(st.mean(t), 3), f(st.median(small), 3),
                     f"{plink_med / st.median(t):.1f}×", f"{st.median(per_id):.1f}× (n={len(paired)})"])
    prep = [float(by_id[i]["plink2"]["elapsed_sec"]) + float(by_id[i]["plink2"]["prep_sec"]) for i in done["plink2"]]
    prep_small = [float(by_id[i]["plink2"]["elapsed_sec"]) + float(by_id[i]["plink2"]["prep_sec"]) for i in done["plink2"]
                  if int(by_id[i]["plink2"]["variants_total"]) < LARGE_SCORE]
    rows.append(["PLINK2 + score-file preparation", str(len(prep)), f(st.median(prep), 3), f(st.mean(prep), 3),
                 f(st.median(prep_small), 3), "—", "—"])
    failed = sorted(i for i, d in by_id.items() if "plink2" in d and not scored(d["plink2"]))
    note = (f"PLINK2 failed on {len(failed)} ({', '.join(failed)})." if failed else "Every engine scored every ID.")
    n_large = sum(1 for d in by_id.values() if int(d["duckdb"]["variants_total"]) >= LARGE_SCORE)
    return (table(["Engine", "*N* scored", "Median (all), s", "Mean (all), s",
                   f"Median (excl. {n_large} with ≥ 1M variants), s", "PLINK2 median ÷ engine median",
                   "Median per-ID PLINK2 ÷ engine"], rows) + f"\n\n{note}")


def pearson(xs: list[float], ys: list[float]) -> float:
    return st.correlation(xs, ys)


def table6(config: str) -> str:
    by_id = load_prs(config)
    rows = []
    for a, b in (("duckdb", "polars"), ("duckdb", "plink2"), ("polars", "plink2")):
        ids = sorted(i for i, d in by_id.items() if a in d and b in d and scored(d[a]) and scored(d[b]))
        xa = [float(by_id[i][a]["score"]) for i in ids]
        xb = [float(by_id[i][b]["score"]) for i in ids]
        diff = [abs(p - q) for p, q in zip(xa, xb)]
        worst = max(range(len(ids)), key=lambda k: diff[k])
        rows.append([f"{ENGINE_LABEL[a]} ↔ {ENGINE_LABEL[b]}", str(len(ids)), f"{pearson(xa, xb):.6f}",
                     f"{diff[worst]:.3g} ({ids[worst]})", f"{st.median(diff):.3g}"])
    return table(["Engine pair", "*N* PGS", "Pearson *r*", "Max \\|Δ score\\| (ID)", "Median \\|Δ score\\|"], rows)


def s2(runs) -> str:
    hist = list(csv.DictReader((A3 / "historical.csv").open()))
    rows = []
    for h in hist:
        if h["tool"] == "oakvar":
            rows.append(["2023 (old workstation)", "calibration", h["date"], h["value_s"], "—", "—"])
    for g in ("primary", "calibration"):
        for r in runs.get(("oakvar", g, "full"), []):
            rows.append(["2026 (this machine)", g, r["started_at"][:10], f(float(r["cli_wall_s"])),
                         f(float(r["peak_rss_mb"]), 0), r["load1_before"]])
    runs_table = table(["Series", "Genome", "Date", "Wall time, s", "Peak RSS, MB", "Load before"], rows)

    steps = list(csv.DictReader(next(A3.glob("oakvar/steps-*.tsv")).open(), delimiter="\t"))
    step_rows = []
    for kind, name in [(r["kind"], r["name"]) for r in steps if r["genome"] == "primary" and r["run"].startswith("00_")]:
        vals = [float(r["seconds"]) for r in steps if r["genome"] == "primary" and r["kind"] == kind and r["name"] == name]
        total = [float(r["seconds"]) for r in steps if r["genome"] == "primary" and r["kind"] == "total"]
        if kind == "step" or kind == "total":
            step_rows.append([name, f(st.median(vals)), f"{100 * st.median(vals) / st.median(total):.1f}%"])
        else:
            step_rows.append([f"  {name}", f(st.median(vals)), ""])
    steps_table = table(["OakVar step / module (primary genome, median of 3)", "Seconds", "Share"], step_rows)

    old_oak = [float(h["value_s"]) for h in hist if h["tool"] == "oakvar"]
    old_jdl = next(h for h in hist if h["tool"] == "jdl" and h["run_type"] == "normal")
    new_oak = st.median(col(runs[("oakvar", "calibration", "full")], "cli_wall_s"))
    new_warm = st.median(col(runs[("jdl", "calibration", "warm")], "cli_wall_s"))
    new_full = st.median(col(runs[("jdl", "calibration", "full")], "cli_wall_s"))
    factor_rows = [
        ["Generation I, full", f"{f(st.mean(old_oak))} (mean of {len(old_oak)}, 2023)", f(new_oak),
         f"{st.mean(old_oak) / new_oak:.2f}"],
        ["Generation II, 'normal' (2023 tables) vs warm (2026)", f"{old_jdl['mean_s']} (mean of {old_jdl['n']})",
         f(new_warm), f"{float(old_jdl['mean_s']) / new_warm:.2f}"],
        ["Generation II, 'normal' (2023 tables) vs full (2026)", f"{old_jdl['mean_s']} (mean of {old_jdl['n']})",
         f(new_full), f"{float(old_jdl['mean_s']) / new_full:.2f}"],
    ]
    factor_table = table(["Calibration genome", "Old workstation, s", "This machine (median), s", "Old ÷ new"], factor_rows)

    installed = json.loads((A3 / "oakvar" / "installed-2.13.1.json").read_text())
    used = {"dbsnp", "clinvar", "omim", "ncbigene", "pubmed", "gnomad", "sift", "cardioboost", "vcf-converter",
            "gencode", "vcfinfo", "tagsampler", "longevity2reporter"}
    mod_rows = [[m["name"], m["type"], m["version"], str(m.get("data_source") or "—")]
                for m in sorted(installed, key=lambda m: (m["type"], m["name"]))
                if m["name"] in used or m["name"].startswith("just_")]
    mod_table = table(["OakVar module", "Type", "Version", "Data source"], mod_rows)
    return "\n\n".join([runs_table, steps_table, factor_table, mod_table])


def s3(config: str) -> str:
    by_id = load_prs(config)
    large = sorted((i for i, d in by_id.items() if int(d["duckdb"]["variants_total"]) >= LARGE_SCORE),
                   key=lambda i: int(by_id[i]["duckdb"]["variants_total"]))
    rows = []
    for i in large:
        d = by_id[i]
        cells = [i, f"{int(d['duckdb']['variants_total']):,}"]
        for e in ENGINES:
            r = d[e]
            cells.append(f"{f(float(r['elapsed_sec']), 2)} / {f(float(r['peak_memory_mb']), 0)}"
                         if scored(r) else f"failed (exit {r['plink2_exit']})")
        rows.append(cells)
    mem_rows = []
    for e in ENGINES:
        ms = [float(d[e]["peak_memory_mb"]) for d in by_id.values() if e in d and scored(d[e])]
        method = {d[e]["memory_method"] for d in by_id.values() if e in d}
        mem_rows.append([ENGINE_LABEL[e], ", ".join(sorted(method)), f(st.median(ms), 1), f(max(ms), 0)])
    return (table(["PGS ID", "Variants", *(f"{ENGINE_LABEL[e]}: s / MB" for e in ENGINES)], rows) + "\n\n"
            + table(["Engine", "Memory method", "Median, MB (all IDs)", "Max, MB"], mem_rows))


def paper_table3(runs) -> str:
    """Table 3 as printed in the paper: the full runs (like-for-like with OakVar) and Generation I."""
    rows = []
    for g in GENOMES:
        rs = runs[("jdl", g, "full")]
        pk = col(rs, "peak_rss_mb")
        rows.append([GENOME_LABEL[g].split(" (")[0], "Generation II, full", str(len(rs)),
                     *(f(st.median(col(rs, c))) for c in ("normalize_s", "annotate_s", "report_s")),
                     f(st.median(pk), 0), f(max(pk), 0), f(st.median(col(rs, "cpu_pct")), 0)])
        oak = runs.get(("oakvar", g, "full"))
        if oak:
            pk = col(oak, "peak_rss_mb")
            rows.append([GENOME_LABEL[g].split(" (")[0], "Generation I", str(len(oak)), "—", "—", "—",
                         f(st.median(pk), 0), f(max(pk), 0), "—"])
    return table(["Genome", "Run", "*n* (runs)", "Normalize (s)", "Annotate (s)", "Report (s)",
                  "Peak RAM, median (MB)", "Peak RAM, max (MB)", "CPU (%)"], rows)


def paper_table4() -> str:
    env = json.loads((A3 / "env.json").read_text())
    m, c = env["machine"], env["code"]
    disk = m["data_mount"]["disk"]
    inputs = json.loads((A3 / "inputs.json").read_text())
    rows = [
        ["CPU", f"{m['cpu_model'].replace(' 8-Core Processor', '')} ({m['cores']} cores, {m['threads']} threads)"],
        ["RAM", f"{m['ram_bytes'] / 2**30:.0f} GiB"],
        ["Storage", f"{'HDD' if disk['rotational'] else 'SATA SSD'} (data, caches and outputs)"],
        ["OS", f"Linux {m['kernel'].split('-')[0]}"],
        ["Generation II", f"Just-DNA-Lite {c['packages']['just-dna-lite']}, {len(env['modules'])} modules (Table S2)"],
        ["Generation I", f"OakVar {env['generation_i']['oakvar']} in Docker (Table S2)"],
    ]
    for g in GENOMES:
        d = inputs[g]
        caller = next((h.split("=", 1)[1] for h in d["caller_headers"] if h.startswith("##DeepVariant_version=")), None)
        caller = f"DeepVariant {caller}" if caller else "DRAGEN " + next(
            h.split('Version="SW: ')[1].split(",")[0] for h in d["caller_headers"] if "ID=dragen," in h)
        rows.append([f"Input: {GENOME_LABEL[g].split(' (')[0].lower()}",
                     f"{d['records']:,} records ({d['snv_records']:,} SNVs), {caller}, GRCh38"])
    return table(["Parameter", "Value"], rows)


def paper_table6() -> str:
    rows = []
    for config in ("fixed", "original"):
        by_id = load_prs(config)
        for a, b in (("duckdb", "polars"), ("duckdb", "plink2"), ("polars", "plink2")):
            if config == "original" and a == "duckdb" and b == "polars":
                continue
            ids = sorted(i for i, d in by_id.items() if scored(d[a]) and scored(d[b]))
            xa = [float(by_id[i][a]["score"]) for i in ids]
            xb = [float(by_id[i][b]["score"]) for i in ids]
            diff = max(abs(p - q) for p, q in zip(xa, xb))
            rows.append([f"{ENGINE_LABEL[a]} ↔ {ENGINE_LABEL[b]}", config, str(len(ids)),
                         f"{pearson(xa, xb):.6f}", f"{diff:.2g}"])
    return table(["Engine pair", "PLINK2 input", "*N* PGS", "Pearson *r*", "Max \\|Δ score\\|"], rows)


def plink2_failures(config: str) -> list[tuple[str, str]]:
    out = []
    for i, d in sorted(load_prs(config).items()):
        if not scored(d["plink2"]):
            log = next(A3.glob(f"prs/results-*/{config}/plink2_runs/{i}.log")).read_text()
            err = " ".join(log.split("Error:", 1)[1].split())[:90]
            out.append((i, err))
    return out


def quoted(runs) -> str:
    """Every number the paper's prose quotes, with where it comes from."""
    med = lambda k: st.median(col(runs[k], "cli_wall_s"))  # noqa: E731
    lines = []
    for g in ("primary", "calibration"):
        oak = med(("oakvar", g, "full"))
        lines += [
            f"- {g}: Generation I median {f(oak)} s; Generation II full median {f(med(('jdl', g, 'full')))} s, "
            f"cold {f(med(('jdl', g, 'cold')))} s, warm {f(med(('jdl', g, 'warm')))} s; ratios full "
            f"{oak / med(('jdl', g, 'full')):.0f}×, cold {oak / med(('jdl', g, 'cold')):.0f}×, "
            f"warm {oak / med(('jdl', g, 'warm')):.0f}× (warm is not like-for-like)",
        ]
    full_pk = [x for g in GENOMES for x in col(runs[("jdl", g, "full")], "peak_rss_mb")]
    prim_pk = [x for t in JDL_TYPES for x in col(runs[("jdl", "primary", t)], "peak_rss_mb")]
    lines += [
        f"- Generation II peak RAM, primary genome, all warm/full/cold runs: {f(min(prim_pk), 0)}–{f(max(prim_pk), 0)} MB",
        f"- Generation II peak RAM, every full run on every genome: max {f(max(full_pk), 0)} MB",
        f"- Generation II peak RAM, every warm/full/cold run on every genome: max "
        f"{f(max(x for g in GENOMES for t in JDL_TYPES for x in col(runs[('jdl', g, t)], 'peak_rss_mb')), 0)} MB",
        f"- Generation I peak RAM, primary: max {f(max(col(runs[('oakvar', 'primary', 'full')], 'peak_rss_mb')), 0)} MB",
        f"- Ensembl run (primary): wall {f(col(runs[('jdl', 'primary', 'ensembl')], 'cli_wall_s')[0])} s, "
        f"peak {f(col(runs[('jdl', 'primary', 'ensembl')], 'peak_rss_mb')[0], 0)} MB",
    ]
    for config in ("fixed", "original"):
        by_id = load_prs(config)
        for e in ENGINES:
            fr = [int(d[e]["variants_matched"]) / int(d[e]["variants_total"]) for d in by_id.values() if scored(d[e])]
            lines.append(f"- PRS {config}, {e}: matched / total per ID, median {100 * st.median(fr):.0f}% "
                         f"(range {100 * min(fr):.0f}–{100 * max(fr):.0f}%), n={len(fr)}")
        for i, err in plink2_failures(config):
            lines.append(f"- PRS {config}: PLINK2 failed on {i}: {err}")
    meta = json.loads(next(A3.glob("prs/results-*/fixed/metadata.json")).read_text())
    lines.append(f"- PRS input: {meta['normalized_rows']:,} PASS records; just-prs {meta['just_prs']}; "
                 f"{meta['plink2_version']}; {len(meta['ids'])} IDs, warm-up {', '.join(meta['warmup_ids'])}")
    return "\n".join(lines)


def main() -> None:
    runs = load_runs()
    t2, ratios = table2(runs)
    parts = [
        "# A3 benchmark tables (generated)",
        "Generated by `scripts/make_tables.py` from the committed files in this directory. Do not edit by hand; "
        "rerun the script.",
        "Wall time is `cli_wall_s`: the whole command, from start to report written, for both generations "
        "(Generation II: `uv run annotate`; Generation I: `docker run … oakvar run`). Warm: the normalized "
        "parquet is reused, so the VCF is not read. Full: a fresh instance and output directory with warm OS "
        "caches, normalization included, the like-for-like counterpart of an OakVar run. Cold: as full, with "
        "the OS page cache dropped right before.",
        "## Table 2. Annotation wall time", t2,
        "## Table 3. Generation II stage times and resources (medians)",
        "RSS is the sum over the command's whole process tree (Generation I: the container's processes), sampled "
        "at 10 Hz with psutil; pages shared between processes count once per process, so it is an upper bound. "
        "CPU is user + system time of the command and every descendant it reaped, divided by wall time; it was "
        "not measured for Generation I (the container's processes are not the driver's children).",
        table3(runs),
        "## Table 4. Machine and inputs", table4(),
    ]
    for config, label in (("fixed", "fixed benchmark inputs (primary)"), ("original", "original benchmark inputs")):
        parts += [f"## Table 5 ({label}). PRS runtime per PGS ID", table5(config),
                  f"## Table 6 ({label}). Score concordance", table6(config)]
    parts += ["## S2. Generation I runs, steps, hardware factor and module versions", s2(runs)]
    for config in ("fixed", "original"):
        parts += [f"## S3 ({config}). Large scoring files: time and memory", s3(config)]
    parts += ["# As printed in the paper",
              "## Paper Table 2", t2,
              "## Paper Table 3", paper_table3(runs),
              "## Paper Table 4", paper_table4(),
              "## Paper Table 5", table5("fixed"),
              "## Paper Table 6", paper_table6(),
              "## Numbers quoted in the text", quoted(runs)]
    (A3 / "tables.md").write_text("\n\n".join(parts) + "\n")


if __name__ == "__main__":
    main()
