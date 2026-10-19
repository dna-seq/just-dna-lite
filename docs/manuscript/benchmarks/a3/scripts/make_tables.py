#!/usr/bin/env python3
"""Generate every benchmark table of Paper 1 (Tables 2-5, S2, S3, S6) from the committed A3 files.

Inputs, all in docs/manuscript/benchmarks/a3/: runs.csv, inputs.json, env.json, historical.csv,
oakvar/steps-*.tsv, oakvar/installed-2.13.1.json, prs/results-*/{fixed,original}/benchmark_results.csv,
prs/sexchr-*/benchmark_{per_pgs,metadata}.csv (just-prs's own benchmark with X, Y, PAR and MT, copied in).
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
    "primary": "Anton Kulaga, published call set (Zenodo 18370498)",
    "second_caller": "Livia Zaharia (Zenodo 19487816)",
    "community_reference": "Community reference (HG002, DeepVariant case study)",
    "calibration": "Anton Kulaga, 2023 call set (unpublished)",
}


def short(g: str) -> str:
    """The genome's name without its source, for table cells."""
    return GENOME_LABEL[g].split(" (")[0]
JDL_TYPES = ("warm", "full", "cold")
RUN_LABEL = {
    "warm": "Generation II, warm",
    "full": "Generation II, full",
    "cold": "Generation II, cold",
    "ensembl": "Generation II, full + Ensembl (annotate_all_job)",
    "oakvar": "Generation I (OakVar 2.13.1), full",
    "dbsnp_only": "Generation I (OakVar 2.13.1), dbSNP only",
}
# Night 2 timed both generations against a whole-genome reference database: OakVar with its dbSNP annotator
# alone, Generation II with Ensembl on. Neither series had a warm-up run, and the first run of each read its
# database from disk for the first time (OakVar's annotator step took about six times as long), so the first
# run is dropped as the warm-up: the author's call after the runs (PROTOCOL.md, night 2). Both series ran on
# the same night, so the pair compares like with like; the night-1 Ensembl run is left out of it.
PAIR_SERIES = "/series/20261013T0200/"
PAIR = {"jdl": ("jdl", "primary", "ensembl"), "oakvar": ("oakvar", "primary", "dbsnp_only")}
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


# Runs that did not finish, by run directory, with the cause found in their logs. A failed run without an
# entry here stops the script, so that no failure goes unexplained.
FAILED = {
    "/data/a3-bench/series/20261013T0200/oakvar/second_caller-3/00_full1":
        "killed after 1,277.8 s when a system update (docker-ce and containerd, 17:29 UTC) restarted the Docker "
        "daemon at 17:34:08 UTC",
}


def load_runs() -> dict[tuple[str, str, str], list[dict]]:
    groups = defaultdict(list)
    for r in csv.DictReader((A3 / "runs.csv").open()):
        if r["exit"] != "0":
            assert r["run_dir"] in FAILED, r
            continue
        groups[(r["tool"], r["genome"], r["run_type"])].append(r)
    return groups


def failed_runs() -> list[dict]:
    return [r for r in csv.DictReader((A3 / "runs.csv").open()) if r["exit"] != "0"]


def col(rows: list[dict], name: str) -> list[float]:
    return [float(r[name]) for r in rows if r[name] not in ("", "None")]


def in_pair_series(r: dict) -> bool:
    return PAIR_SERIES in r["run_dir"] and r["run_type"] in ("ensembl", "dbsnp_only")


def pair_runs(runs, tool: str) -> list[dict]:
    """The runs of one side of the reference-database pair, its warm-up (the series' first run) dropped."""
    return [r for r in runs[PAIR[tool]] if in_pair_series(r) and r["order"] != "0"]


def load_steps() -> list[dict]:
    """OakVar's own step and module times, every series."""
    return [r for path in sorted(A3.glob("oakvar/steps-*.tsv"))
            for r in csv.DictReader(path.open(), delimiter="\t")]


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
    oak = summary(col(pair_runs(runs, "oakvar"), "cli_wall_s"))
    jdl = summary(col(pair_runs(runs, "jdl"), "cli_wall_s"))
    ratios["pair"] = oak["median"] / jdl["median"]
    out_rows += [
        [f"**{short('primary')}, against a whole-genome reference database (first run of each dropped)**", "", "", "", "", ""],
        ["Generation II, full + Ensembl", *time_cells(jdl), f"{ratios['pair']:,.0f}×"],
        [RUN_LABEL["dbsnp_only"], *time_cells(oak), "1× (ref.)"],
    ]
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
            rows.append([short(g), RUN_LABEL[t], str(len(rs)),
                         med("normalize_s"), med("annotate_s"), med("report_s"),
                         ensembl_cell(rs) if t == "ensembl" else "—", med("job_wall_s"),
                         f"{f(st.median(pk), 0)} ({f(max(pk), 0)})", med("mean_rss_mb", 0),
                         med("cpu_pct", 0)])
        oak = runs.get(("oakvar", g, "full"))
        if oak:
            pk = col(oak, "peak_rss_mb")
            rows.append([short(g), RUN_LABEL["oakvar"], str(len(oak)),
                         "—", "—", "—", "—", "—", f"{f(st.median(pk), 0)} ({f(max(pk), 0)})",
                         f(st.median(col(oak, "mean_rss_mb")), 0), "not measured"])
    return table(["Genome", "Run", "*n*", "Normalize, s", "Annotate, s", "Report, s", "Ensembl, s",
                  "Job, s", "Peak RSS, MB: median (max)", "Mean RSS, MB", "CPU, %"], rows)


def table_s6() -> str:
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


def table4(config: str) -> str:
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


def table5(config: str) -> str:
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


# just-prs's own benchmark with X, Y, PAR and MT (copied from just-prs benchmarks/results/2026-10-13-sexchr). The
# sample is marked male in PLINK2 and given as XY to just-prs. Two codings of a man's non-PAR X: one copy
# (just-prs default) against PLINK2 --xchr-model 1, and 0..2 against --xchr-model 2.
SEXCHR_PAIRS = (("duckdb", "polars", "copies"), ("duckdb_dc", "polars_dc", "0..2"),
                ("polars", "plink2", "copies vs --xchr-model 1"), ("polars_dc", "plink2_xchr2", "0..2 vs --xchr-model 2"))


def load_sexchr() -> tuple[list[dict], dict[str, str]]:
    d = next(A3.glob("prs/sexchr-*"))
    rows = list(csv.DictReader((d / "benchmark_per_pgs.csv").open()))
    meta = {r["key"]: r["value"] for r in csv.DictReader((d / "benchmark_metadata.csv").open())}
    return rows, meta


def table_sexchr() -> str:
    rows, meta = load_sexchr()
    out = []
    for a, b, coding in SEXCHR_PAIRS:
        ok = [r for r in rows if r[f"score_{a}"] not in ("", "None") and r[f"score_{b}"] not in ("", "None")]
        xa = [float(r[f"score_{a}"]) for r in ok]
        xb = [float(r[f"score_{b}"]) for r in ok]
        diff = [abs(p - q) for p, q in zip(xa, xb)]
        k = max(range(len(ok)), key=lambda i: diff[i])
        out.append([f"{a} ↔ {b}", coding, str(len(ok)), f"{pearson(xa, xb):.8f}",
                    f"{diff[k]:.3g} ({ok[k]['pgs_id']}, score {xb[k]:.1f})", str(sum(x <= 1e-3 for x in diff))])
    # A het call on a man's non-PAR X is a no-call in just-prs and half a copy (model 1) or one copy (model 2) in
    # PLINK2, so its share of the model-2 difference is twice its share of the model-1 one: 2*d1 - d2 is the rest.
    rest = [(abs(2 * (float(r["score_polars"]) - float(r["score_plink2"]))
                 - (float(r["score_polars_dc"]) - float(r["score_plink2_xchr2"]))), r["pgs_id"]) for r in rows]
    worst_rest = max(rest)
    note = (f"just-prs {meta['just_prs_version']} ({meta['just_prs_git_commit'][:7]}); {meta['plink2_version']}; "
            f"{int(meta['genotype_records']):,} records; karyotype given {meta['sample_karyotype_given']}, inferred "
            f"{meta['sample_karyotype_inferred']}. Difference left after removing the part that doubles from model 1 "
            f"to model 2 (2·Δ₁ − Δ₂): at most {worst_rest[0]:.2g} ({worst_rest[1]}).")
    return table(["Engine pair", "Coding of a man's non-PAR X", "*N* PGS", "Pearson *r*", "Max \\|Δ score\\| (ID)",
                  "IDs within 10⁻³"], out) + f"\n\n{note}"


def s2(runs) -> str:
    hist = list(csv.DictReader((A3 / "historical.csv").open()))
    rows = []
    for h in hist:
        if h["tool"] == "oakvar":
            rows.append(["2023 (old workstation)", short("calibration"), "full", h["date"], h["value_s"], "—", "—", "—"])
    for g, t in (("primary", "full"), ("calibration", "full"), ("second_caller", "full"), ("primary", "dbsnp_only")):
        for r in sorted(runs.get(("oakvar", g, t), []), key=lambda r: r["started_at"]):
            used = "warm-up, dropped" if in_pair_series(r) and r["order"] == "0" else "Table 2"
            rows.append(["2026 (this machine)", short(g), t, r["started_at"][:16].replace("T", " ") + " UTC",
                         f(float(r["cli_wall_s"])), f(float(r["peak_rss_mb"]), 0), r["load1_before"], used])
    for r in failed_runs():
        rows.append(["2026 (this machine)", short(r["genome"]), r["run_type"], r["started_at"][:16].replace("T", " ") + " UTC",
                     f"failed (exit {r['exit']})", "—", r["load1_before"], FAILED[r["run_dir"]]])
    runs_table = table(["Series", "Genome", "Mode", "Started", "Wall time, s", "Peak RSS, MB", "Load before",
                        "Used in"], rows)

    steps = load_steps()
    step_rows = []
    for kind, name in [(r["kind"], r["name"]) for r in steps if r["genome"] == "primary" and r["run"].startswith("00_")]:
        vals = [float(r["seconds"]) for r in steps if r["genome"] == "primary" and r["kind"] == kind and r["name"] == name]
        total = [float(r["seconds"]) for r in steps if r["genome"] == "primary" and r["kind"] == "total"]
        if kind == "step" or kind == "total":
            step_rows.append([name, f(st.median(vals)), f"{100 * st.median(vals) / st.median(total):.1f}%"])
        else:
            step_rows.append([f"  {name}", f(st.median(vals)), ""])
    steps_table = table([f"OakVar step / module ({short('primary')}, median of 3)", "Seconds", "Share"], step_rows)

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
    factor_table = table([short("calibration"), "Old workstation, s", "This machine (median), s", "Old ÷ new"], factor_rows)

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
        rows.append([short(g), "Generation II, full", str(len(rs)),
                     *(f(st.median(col(rs, c))) for c in ("normalize_s", "annotate_s", "report_s")),
                     f(st.median(pk), 0), f(max(pk), 0), f(st.median(col(rs, "cpu_pct")), 0)])
        oak = runs.get(("oakvar", g, "full"))
        if oak:
            pk = col(oak, "peak_rss_mb")
            rows.append([short(g), "Generation I", str(len(oak)), "—", "—", "—",
                         f(st.median(pk), 0), f(max(pk), 0), "—"])
    return table(["Genome", "Run", "*n* (runs)", "Normalize (s)", "Annotate (s)", "Report (s)",
                  "Peak RAM, median (MB)", "Peak RAM, max (MB)", "CPU (%)"], rows)


def paper_table_s6() -> str:
    env = json.loads((A3 / "env.json").read_text())
    m, c = env["machine"], env["code"]
    disk = m["data_mount"]["disk"]
    inputs = json.loads((A3 / "inputs.json").read_text())
    rows = [
        ["CPU", f"{m['cpu_model'].replace(' 8-Core Processor', '')} ({m['cores']} cores, {m['threads']} threads)"],
        ["RAM", f"{m['ram_bytes'] / 2**30:.0f} GiB"],
        ["Storage", f"{'HDD' if disk['rotational'] else 'SATA SSD'}, NTFS through the Linux {m['data_mount']['fstype']} driver (data, caches and outputs)"],
        # The paper states the kernel series only (the user's call, 2026-10-17): a patch release of the same series is not
        # a different machine for these timings. The exact build stays in env.json and Table S6 of tables.md.
        ["OS", f"Linux {'.'.join(m['kernel'].split('-')[0].split('.')[:2])}"],
        ["Generation II", f"Just-DNA-Lite {c['packages']['just-dna-lite']}, {len(env['modules'])} modules (versions and digests as in Table S4)"],
        ["Generation I", f"OakVar {env['generation_i']['oakvar']} in Docker (Table S2)"],
    ]
    for g in GENOMES:
        d = inputs[g]
        caller = next((h.split("=", 1)[1] for h in d["caller_headers"] if h.startswith("##DeepVariant_version=")), None)
        caller = f"DeepVariant {caller}" if caller else "DRAGEN " + next(
            h.split('Version="SW: ')[1].split(",")[0] for h in d["caller_headers"] if "ID=dragen," in h)
        rows.append([f"Input: {short(g)}",
                     f"{d['records']:,} records ({d['snv_records']:,} SNVs), {caller}, GRCh38"])
    return table(["Parameter", "Value"], rows)


def paper_table5() -> str:
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
                         f"{pearson(xa, xb):.6f}", f"{diff:.3g}"])
    return table(["Engine pair", "PLINK2 input", "*N* PGS", "Pearson *r*", "Max \\|Δ score\\|"], rows)


def paper_table_s2() -> str:
    """The Generation I modules that ran (OakVar store), beside each dna-seq repo's GitHub versions."""
    installed = {m["name"]: m for m in json.loads((A3 / "oakvar" / "installed-2.13.1.json").read_text())}
    heads = {}
    for name in ("modules-current.tsv", "modules.tsv"):
        heads[name] = {r["name"]: r for r in csv.DictReader((A3 / "oakvar" / name).open(), delimiter="\t")}
    order = ("converter", "mapper", "annotator", "postaggregator", "reporter")
    used = {"vcf-converter", "gencode", "dbsnp", "clinvar", "omim", "ncbigene", "pubmed", "gnomad", "sift",
            "cardioboost", "vcfinfo", "longevity2reporter"}

    def gh(name: str, tsv: str) -> str:
        r = heads[tsv].get(name)
        return "—" if r is None else f"{r['version']} ({r['commit_date'][:10]})"

    rows = [[m["name"], m["type"], m["version"], str(m.get("data_source") or "—"),
             gh(m["name"], "modules-current.tsv"), gh(m["name"], "modules.tsv")]
            for m in sorted((m for m in installed.values()
                             if m["type"] in order and (m["name"] in used or m["name"].startswith("just_"))),
                            key=lambda m: (order.index(m["type"]), m["name"]))]
    return table(["OakVar module", "Type", "Version that ran (store)", "Data", "GitHub head, 2026-10-11",
                  "GitHub, last commit by 2023-05-07"], rows)


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
            f"- {short(g)}: Generation I median {f(oak)} s; Generation II full median {f(med(('jdl', g, 'full')))} s, "
            f"cold {f(med(('jdl', g, 'cold')))} s, warm {f(med(('jdl', g, 'warm')))} s; ratios full "
            f"{oak / med(('jdl', g, 'full')):.0f}×, cold {oak / med(('jdl', g, 'cold')):.0f}×, "
            f"warm {oak / med(('jdl', g, 'warm')):.0f}× (warm is not like-for-like)",
        ]
    full_pk = [x for g in GENOMES for x in col(runs[("jdl", g, "full")], "peak_rss_mb")]
    prim_pk = [x for t in JDL_TYPES for x in col(runs[("jdl", "primary", t)], "peak_rss_mb")]
    lines += [
        f"- Generation II peak RAM, {short('primary')}, all warm/full/cold runs: {f(min(prim_pk), 0)}–{f(max(prim_pk), 0)} MB",
        f"- Generation II peak RAM, every full run on every genome: max {f(max(full_pk), 0)} MB",
        f"- Generation II peak RAM, every warm/full/cold run on every genome: max "
        f"{f(max(x for g in GENOMES for t in JDL_TYPES for x in col(runs[('jdl', g, t)], 'peak_rss_mb')), 0)} MB",
        f"- Generation I peak RAM, {short('primary')}: max {f(max(col(runs[('oakvar', 'primary', 'full')], 'peak_rss_mb')), 0)} MB",
        f"- Generation I peak RAM, every run: max "
        f"{f(max(x for k, rs in runs.items() if k[0] == 'oakvar' for x in col(rs, 'peak_rss_mb')), 0)} MB",
        f"- Generation II peak RAM with Ensembl on, every run: "
        f"{f(min(col(runs[PAIR['jdl']], 'peak_rss_mb')), 0)}–{f(max(col(runs[PAIR['jdl']], 'peak_rss_mb')), 0)} MB "
        f"(n={len(runs[PAIR['jdl']])})",
    ]
    second = runs.get(("oakvar", "second_caller", "full"))
    if second:
        oak = med(("oakvar", "second_caller", "full"))
        lines.append(f"- {short('second_caller')}: Generation I median {f(oak)} s (n={len(second)}); ratio full "
                     f"{oak / med(('jdl', 'second_caller', 'full')):.0f}×, cold {oak / med(('jdl', 'second_caller', 'cold')):.0f}×")
    oak_p, jdl_p = (col(pair_runs(runs, k), "cli_wall_s") for k in ("oakvar", "jdl"))
    full_ratio = med(("oakvar", "primary", "full")) / med(("jdl", "primary", "full"))
    pair_ratio = st.median(oak_p) / st.median(jdl_p)
    lines += [
        f"- Reference-database pair ({short('primary')}, first run dropped): Generation I dbSNP only median {f(st.median(oak_p))} s "
        f"(n={len(oak_p)}, {f(min(oak_p))}–{f(max(oak_p))}); Generation II full + Ensembl median {f(st.median(jdl_p))} s "
        f"(n={len(jdl_p)}, {f(min(jdl_p))}–{f(max(jdl_p))}); ratio of medians {pair_ratio:.0f}×; ratio range over "
        f"run pairs {min(oak_p) / max(jdl_p):.0f}–{max(oak_p) / min(jdl_p):.0f}×",
        f"- The full-run ratio on {short('primary')} ({full_ratio:.0f}×) is {full_ratio / pair_ratio:.1f} times the pair's",
    ]
    for tool, key in PAIR.items():
        first = next(r for r in runs[key] if in_pair_series(r) and r["order"] == "0")
        lines.append(f"- Pair warm-up dropped, {tool}: {f(float(first['cli_wall_s']))} s")
    ann = {r["run"]: float(r["seconds"]) for r in load_steps()
           if r["genome"] == "primary-dbsnp" and r["kind"] == "step" and r["name"] == "annotator"}
    lines.append("- OakVar annotator step, dbSNP-only runs: "
                 + ", ".join(f"{run} {f(s)} s" for run, s in sorted(ann.items())))
    joins = [(r["order"], json.loads(r["steps_json"])["user_annotated_vcf_duckdb"]["seconds"])
             for r in runs[PAIR["jdl"]] if in_pair_series(r)]
    lines.append("- Generation II Ensembl join step, night-2 runs in order: "
                 + ", ".join(f"{f(s)} s" for _, s in sorted(joins)))
    every = [(k, x) for k, rs in runs.items() if k[2] != "warmup" for x in col(rs, "cli_wall_s")]
    g2 = [x for k, x in every if k[0] == "jdl" and k[2] in ("full", "cold")]
    g1 = [x for k, x in every if k[0] == "oakvar" and k[2] == "full"]
    lines += [
        f"- Every Generation II full or cold run: {f(min(g2))}–{f(max(g2))} s; with Ensembl, pair runs: "
        f"{f(min(jdl_p))}–{f(max(jdl_p))} s",
        f"- Every Generation I full run: {f(min(g1))}–{f(max(g1))} s ({min(g1) / 3600:.1f}–{max(g1) / 3600:.1f} h); "
        f"dbSNP only, pair runs: {f(min(oak_p))}–{f(max(oak_p))} s",
    ]
    three = [med(("oakvar", g, "full")) / med(("jdl", g, "full")) for g in ("primary", "calibration", "second_caller")]
    lines.append(f"- Full-run ratio over the three genomes Generation I ran on: {min(three):.0f}–{max(three):.0f}×, "
                 f"mean {st.mean(three):.0f}×")
    for g in ("primary", "calibration", "second_caller"):
        w = col(runs[("jdl", g, "full")], "cli_wall_s")
        cpu = col(runs[("jdl", g, "full")], "cpu_pct")
        lines.append(f"- Generation II full runs, {short(g)}: n={len(w)}, {f(min(w))}–{f(max(w))} s "
                     f"(slowest {max(w) / min(w):.1f}× the fastest), CPU {min(cpu):.0f}–{max(cpu):.0f}%")
    for g in ("primary", "calibration", "second_caller"):
        rs = runs.get(("oakvar", g, "full"), [])
        w = col(rs, "cli_wall_s")
        lines.append(f"- Generation I full runs, {short(g)}: n={len(rs)}, dates "
                     + ", ".join(sorted({r['started_at'][:10] for r in rs}))
                     + f"; slowest is {100 * (max(w) / min(w) - 1):.0f}% slower than fastest")
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
        "## Table S6. Machine and inputs", table_s6(),
    ]
    for config, label in (("fixed", "fixed benchmark inputs (primary)"), ("original", "original benchmark inputs")):
        parts += [f"## Table 4 ({label}). PRS runtime per PGS ID", table4(config),
                  f"## Table 5 ({label}). Score concordance", table5(config)]
    parts += ["## S2. Generation I runs, steps, hardware factor and module versions", s2(runs)]
    for config in ("fixed", "original"):
        parts += [f"## S3 ({config}). Large scoring files: time and memory", s3(config)]
    parts += [f"## PRS with X, Y, PAR and MT: score concordance (just-prs benchmark, {short('primary')})", table_sexchr()]
    parts += ["# As printed in the paper",
              "## Paper Table 2", t2,
              "## Paper Table 3", paper_table3(runs),
              "## Paper Table S6", paper_table_s6(),
              "## Paper Table 4", table4("fixed"),
              "## Paper Table 5", paper_table5(),
              "## Paper Table S2", paper_table_s2(),
              "## Numbers quoted in the text", quoted(runs)]
    (A3 / "tables.md").write_text("\n\n".join(parts) + "\n")


if __name__ == "__main__":
    main()
