"""Accumulate exact round-trip deltas between the published (0.3.x) annotation modules
and what just-dna-compiler 0.5.1 emits from the same data.

Mirrors test_module_roundtrip.py's pipeline (download -> reverse_module -> compile_module)
but records the numbers instead of asserting on them. Writes JSON for follow-up work.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import polars as pl

from just_dna_pipelines.module_compiler import compile_module, reverse_module, validate_spec

HF_REPO = "just-dna-seq/annotators"
TABLES = ("weights", "annotations", "studies")

MODULE_METADATA = {
    "lipidmetabolism": ("Lipid Metabolism", "Lipid metabolism and cardiovascular risk variants",
                        "Lipid Metabolism", "droplets", "#fbbd08"),
    "vo2max": ("VO2 Max", "Athletic performance and oxygen uptake capacity variants",
               "VO2max / Athletic Performance", "activity", "#2185d0"),
    "superhuman": ("Superhuman", "Elite performance and rare beneficial variants",
                   "Superhuman / Elite Performance", "zap", "#00b5ad"),
    "coronary": ("Coronary", "Coronary artery disease risk associations",
                 "Coronary Artery Disease", "heart", "#db2828"),
    "longevitymap": ("Longevity Map", "Longevity-associated genetic variants from LongevityMap database",
                     "Longevity Variants", "heart-pulse", "#21ba45"),
}

root = Path(tempfile.mkdtemp(prefix="module_audit_"))
report: dict = {"repo": HF_REPO, "modules": {}}

for mod, (title, desc, report_title, icon, color) in MODULE_METADATA.items():
    entry: dict = {"tables": {}, "errors": []}
    print(f"\n=== {mod} ===", flush=True)

    # 1. published artifact
    pub_dir = root / "published" / mod
    pub_dir.mkdir(parents=True)
    published: dict[str, pl.DataFrame] = {}
    for table in TABLES:
        try:
            df = pl.read_parquet(f"hf://datasets/{HF_REPO}/data/{mod}/{table}.parquet")
            df.write_parquet(pub_dir / f"{table}.parquet")
            published[table] = df
        except Exception as exc:
            entry["errors"].append(f"download {table}: {type(exc).__name__}: {exc}")

    if "weights" not in published:
        entry["errors"].append("no weights.parquet — skipped")
        report["modules"][mod] = entry
        continue

    # 2. reverse to spec, 3. validate, 4. recompile
    spec_dir = root / "spec" / mod
    out_dir = root / "compiled" / mod
    try:
        reverse_module(parquet_dir=pub_dir, output_dir=spec_dir, module_name=mod,
                       title=title, description=desc, report_title=report_title,
                       icon=icon, color=color)
    except Exception as exc:
        entry["errors"].append(f"reverse_module: {type(exc).__name__}: {exc}")
        report["modules"][mod] = entry
        continue

    vres = validate_spec(spec_dir)
    entry["validate"] = {"valid": bool(vres.valid), "errors": list(vres.errors),
                         "warnings": list(vres.warnings)[:10], "stats": dict(vres.stats or {})}

    cres = compile_module(spec_dir, out_dir)
    entry["compile"] = {"success": bool(cres.success), "errors": list(cres.errors),
                        "warnings": list(getattr(cres, "warnings", []) or [])[:10]}
    if not cres.success:
        report["modules"][mod] = entry
        continue

    # 5. per-table deltas
    for table in TABLES:
        pub = published.get(table)
        new_path = out_dir / f"{table}.parquet"
        if pub is None or not new_path.exists():
            entry["tables"][table] = {"published": pub is not None, "recompiled": new_path.exists()}
            continue
        new = pl.read_parquet(new_path)
        pc, nc = set(pub.columns), set(new.columns)
        entry["tables"][table] = {
            "published_rows": pub.height, "recompiled_rows": new.height,
            "row_delta": new.height - pub.height,
            "published_cols": len(pc), "recompiled_cols": len(nc),
            "added_columns": sorted(nc - pc),
            "removed_columns": sorted(pc - nc),
        }
        t = entry["tables"][table]
        print(f"  {table:12} rows {t['published_rows']:>6} -> {t['recompiled_rows']:<6}"
              f" cols {t['published_cols']:>3} -> {t['recompiled_cols']:<3}"
              f" +{len(t['added_columns'])}/-{len(t['removed_columns'])}", flush=True)

    report["modules"][mod] = entry

out = Path(os.getenv("MODULE_AUDIT_OUT", "data/interim/module_audit.json"))
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2))
print(f"\nwrote {out}")
