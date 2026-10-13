#!/usr/bin/env python3
"""Assemble env.json from the committed protocol logs, so every machine and software fact in Table S6
comes from what was recorded at run time, not from the machine as it is when this script runs.

Standard library only. Run from anywhere inside the repository:

    python3 -I docs/manuscript/benchmarks/a3/scripts/make_env.py
"""

import hashlib
import json
import re
import subprocess
from pathlib import Path

A3 = Path(__file__).resolve().parent.parent
LOGS = A3 / "logs"
ENV_LOG = LOGS / "001_env-snapshot.log"
WORKTREE_LOG = LOGS / "002_worktree.log"
SYNC_LOG = LOGS / "003_uv-sync.log"
MODULE_LOGS = sorted(LOGS.glob("0[12][0-9]_registry-dl-*.log"))
OAKVAR_IMAGE_LOG = LOGS / "044_build-oakvar-image-2.13.1-shim.log"
PACKAGES = (
    "just-dna-lite", "just-dna-pipelines", "just-dna-format", "just-dna-compiler",
    "just-dna-enricher", "just-dna-registry", "just-prs", "prs-ui", "polars", "polars-bio",
    "duckdb", "pyarrow", "dagster", "reflex", "psutil",
)


def sections(text: str) -> dict[str, str]:
    """Split a `set -x` log into {command: output}."""
    out: dict[str, str] = {}
    current = None
    for line in text.splitlines():
        if line.startswith("+ "):
            current = line[2:].strip()
            out[current] = ""
        elif current is not None and not line.startswith("# "):
            out[current] += line + "\n"
    return out


def lscpu_field(block: str, name: str) -> str:
    return re.search(rf"^{re.escape(name)}:\s+(.+)$", block, re.M).group(1).strip()


def machine() -> dict:
    text = ENV_LOG.read_text()
    sec = sections(text)
    cpu = sec["lscpu"]
    mem = sec["free -b"].split("\n")[1].split()
    swap = sec["free -b"].split("\n")[2].split()
    mount = sec["findmnt -T /data"].split("\n")[1].split()
    disks = {}
    for row in sec["lsblk -d -o NAME,ROTA,MODEL,SIZE"].strip().split("\n")[1:]:
        name, rota, *model, size = row.split()
        disks[name] = {"rotational": rota == "1", "model": " ".join(model), "size": size}
    data_dev = Path(mount[1]).name.rstrip("0123456789")
    return {
        "snapshot_at": re.search(r"^# start: (.+)$", text, re.M).group(1),
        "snapshot_log": str(ENV_LOG.relative_to(A3)),
        "cpu_model": lscpu_field(cpu, "Model name"),
        "cores": int(lscpu_field(cpu, "Core(s) per socket")) * int(lscpu_field(cpu, "Socket(s)")),
        "threads": int(lscpu_field(cpu, "CPU(s)")),
        "cpu_max_mhz": float(lscpu_field(cpu, "CPU max MHz")),
        "l3_cache": lscpu_field(cpu, "L3 cache"),
        "frequency_boost": lscpu_field(cpu, "Frequency boost"),
        "governor": sec["cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"].strip(),
        "ram_bytes": int(mem[1]),
        "swap_bytes": int(swap[1]),
        "kernel": sec["uname -a"].split()[2],
        "uname": sec["uname -a"].strip(),
        "data_mount": {"target": mount[0], "device": mount[1], "fstype": mount[2],
                       "disk": disks[data_dev]},
        "disks": disks,
        "load_at_snapshot": sec["uptime"].split("load average:")[1].strip(),
        "docker": sec["docker --version"].strip(),
        "uv": sec["uv --version"].strip(),
    }


def code() -> dict:
    commit = re.search(r"worktree add --detach \S+ (\S+)", WORKTREE_LOG.read_text()).group(1)
    full = subprocess.run(["git", "rev-parse", commit], capture_output=True, text=True,
                          check=True, cwd=A3).stdout.strip()
    lock = subprocess.run(["git", "show", f"{full}:uv.lock"], capture_output=True, check=True,
                          cwd=A3).stdout
    sync = SYNC_LOG.read_text()
    versions = dict(re.findall(r"^ \+ ([A-Za-z0-9_.-]+)==(\S+)", sync, re.M))
    return {
        "just_dna_lite_commit": full,
        "worktree": "/data/a3-bench/jdl (git worktree add --detach, step 2)",
        "uv_lock_sha256": hashlib.sha256(lock).hexdigest(),
        "uv_lock_note": (
            "sha256 of uv.lock at that commit, which the worktree used unmodified. The env "
            "snapshot (step 1) hashed the main checkout's uv.lock, which held another session's "
            "uncommitted edit at that moment; that hash is not the benchmarked lock."
        ),
        "python": re.search(r"Using CPython (\S+)", sync).group(1),
        "packages": {p: versions[p] for p in PACKAGES if p in versions},
        "sync_log": str(SYNC_LOG.relative_to(A3)),
    }


def modules() -> list[dict]:
    out = []
    for log in MODULE_LOGS:
        text = log.read_text()
        m = re.search(r"verified (\S+)/(\S+)@(\S+) ", text)
        digest = re.search(r"digest (sha256:[0-9a-f]+)", text).group(1)
        out.append({"namespace": m.group(1), "name": m.group(2), "version": m.group(3),
                    "digest": digest, "log": str(log.relative_to(A3))})
    return sorted(out, key=lambda r: r["name"])


def oakvar() -> dict:
    installed = json.loads((A3 / "oakvar" / "installed-2.13.1.json").read_text())
    image = re.search(r"exporting manifest list (sha256:[0-9a-f]{64})", OAKVAR_IMAGE_LOG.read_text())
    return {
        "oakvar": "2.13.1",
        "image": "jdl-bench-oakvar:2.13.1",
        "image_id": image.group(1),
        "build": "oakvar/Dockerfile (dependencies resolved with --exclude-newer 2026-08-31; "
                 "one-line re-export of reverse_complement in cravat/util.py)",
        "modules": [{k: m.get(k) for k in ("name", "type", "version", "data_source", "size")}
                    for m in installed],
    }


def prs() -> dict:
    out = {}
    for meta in sorted(A3.glob("prs/results-*/*/metadata.json")):
        d = json.loads(meta.read_text())
        out[str(meta.parent.relative_to(A3))] = {
            k: d.get(k) for k in ("config", "just_prs", "polars", "duckdb", "plink2_version",
                                  "plink2_sha256", "upstream_commit", "python", "normalized_rows")
        }
    return out


def main() -> None:
    env = {"machine": machine(), "code": code(), "modules": modules(), "generation_i": oakvar(),
           "prs": prs()}
    (A3 / "env.json").write_text(json.dumps(env, indent=1) + "\n")


if __name__ == "__main__":
    main()
