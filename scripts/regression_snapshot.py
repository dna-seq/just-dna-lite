"""Regression gate for the native (weights- / pharm-led) annotation modules.

The compound-phenotype work adds a *second* engine path (a diplotype caller reached only
from the branch that today raises ``UnsupportedLeadTable``). This script proves that path
does not perturb the modules that already work: it captures, per (sample, module), the
things a phenotype module could plausibly disturb — the manifest counts, the weights
parquet's schema and per-column content hash, and the rendered report — and later asserts
they are byte-for-byte unchanged.

Usage::

    uv run python scripts/regression_snapshot.py snapshot --out data/interim/regression_baseline
    uv run python scripts/regression_snapshot.py compare  data/interim/regression_baseline data/interim/regression_current

``compare`` exits non-zero on any difference. The only difference the compound-phenotype
change is allowed to introduce is a new, separate "Phenotypes" report section that appears
*only* when a phenotype module is selected — which this gate never selects, so here the
answer must be "identical".
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Annotated, Optional

import polars as pl
import typer
from rich.console import Console

from just_dna_pipelines.annotation.configs import HfModuleAnnotationConfig
from just_dna_pipelines.annotation.hf_logic import annotate_vcf_with_all_modules
from just_dna_pipelines.annotation.report_logic import generate_longevity_report
from just_dna_pipelines.runtime import load_env

console = Console()
app = typer.Typer(add_completion=False, help=__doc__)

# The four modules the plan puts on the gate, each for a stated reason (see the plan's
# "Modules under the regression gate" table). Kept here rather than as a CLI arg so the
# baseline and the comparison always cover the same set.
GATE_MODULES = ["longevitymap", "thrombophilia", "coronary", "pharmgkb"]

# Samples that have a normalized parquet on this machine. Anton is a WGS genome with no
# rsIDs (pharmgkb → 0 rows / skipped); M8UBMVNLH carries rsIDs (pharmgkb annotates), so the
# two together exercise both routing outcomes of the pharm path.
DEFAULT_SAMPLES = ["antonkulaga", "M8UBMVNLH.hard-filtered"]

# Order the weights rows deterministically before hashing. Only the columns that exist are
# used; a list-typed genotype is stringified for a stable sort and for hashing.
SORT_KEYS = ["chrom", "start", "variant_key", "rsid", "genotype"]


def _user_output_root() -> Path:
    """The configured per-user output root (env ``JUST_DNA_PIPELINES_OUTPUT_DIR``)."""
    from just_dna_pipelines.annotation.resources import get_user_output_dir

    return get_user_output_dir()


def _normalized_parquet(sample: str, user: str) -> Path:
    return _user_output_root() / user / sample / "user_vcf_normalized.parquet"


def _stringify_lists(df: pl.DataFrame) -> pl.DataFrame:
    """Cast every List column to a stable string so it can be sorted and hashed.

    The inner elements are cast to Utf8 first: a genotype list is ``list[str]`` but other
    list columns (e.g. an authored-identity list) can be ``list[i32]``, which ``list.join``
    refuses.
    """
    casts = [
        pl.col(name)
        .list.eval(pl.element().cast(pl.Utf8, strict=False))
        .list.join(",")
        .alias(name)
        for name, dtype in df.schema.items()
        if isinstance(dtype, pl.List)
    ]
    return df.with_columns(casts) if casts else df


def _weights_signature(parquet_path: Path) -> dict:
    if not parquet_path.exists():
        return {"exists": False}
    df = pl.read_parquet(parquet_path)
    flat = _stringify_lists(df)
    sort_by = [k for k in SORT_KEYS if k in flat.columns]
    if sort_by:
        flat = flat.sort(sort_by, maintain_order=True)
    column_hashes: dict[str, str] = {}
    for name in flat.columns:
        buf = io.BytesIO()
        flat.select(name).write_ipc(buf, compression="uncompressed")
        column_hashes[name] = hashlib.sha256(buf.getvalue()).hexdigest()
    return {
        "exists": True,
        "height": df.height,
        "schema": {name: str(dtype) for name, dtype in df.schema.items()},
        "column_hashes": column_hashes,
    }


def _manifest_signature(modules_dir: Path, module: str) -> dict:
    manifest_path = modules_dir / "manifest.json"
    if not manifest_path.exists():
        return {"manifest_present": False}
    manifest = json.loads(manifest_path.read_text())
    entry = next(
        (m for m in manifest.get("modules", []) if m.get("module") == module),
        None,
    )
    return {
        "manifest_present": True,
        "lead_table": entry.get("lead_table") if entry else None,
        "in_modules": entry is not None,
        "skipped": manifest.get("skipped_modules", {}).get(module),
        "failed": manifest.get("failed_modules", {}).get(module),
        "total_variants_annotated": manifest.get("total_variants_annotated"),
        "total_variants_restored": manifest.get("total_variants_restored"),
        "restored_this_module": manifest.get("restored_variants", {}).get(module, 0),
    }


# Volatile bits of a report that legitimately change between runs and must be stripped
# before hashing: the generation timestamp and any absolute filesystem path.
_ISO_TS = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:?\d{2}|Z)?")
_ABS_PATH = re.compile(r"/[\w./-]+/(?:modules|reports)/[\w./-]+")
_PREVIEW_ROW = re.compile(r"data-preview-row")


def _report_signature(report_path: Optional[Path]) -> dict:
    if report_path is None or not report_path.exists():
        return {"exists": False}
    html = report_path.read_text()
    normalized = _ISO_TS.sub("<TS>", html)
    normalized = _ABS_PATH.sub("<PATH>", normalized)
    return {
        "exists": True,
        "preview_row_count": len(_PREVIEW_ROW.findall(html)),
        "html_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
    }


def _run_one(sample: str, module: str, user: str, work_root: Path) -> dict:
    """Annotate one sample with one module into a scratch dir and snapshot the result."""
    normalized = _normalized_parquet(sample, user)
    if not normalized.exists():
        return {"sample": sample, "module": module, "error": f"no normalized parquet: {normalized}"}

    out_dir = work_root / sample / module
    modules_dir = out_dir / "modules"
    reports_dir = out_dir / "reports"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    modules_dir.mkdir(parents=True)
    reports_dir.mkdir(parents=True)

    logger = logging.getLogger("regression_snapshot")
    config = HfModuleAnnotationConfig(
        vcf_path=str(normalized),
        user_name=user,
        modules=[module],
        output_dir=str(modules_dir),
    )
    annotate_vcf_with_all_modules(
        logger,
        vcf_path=normalized,
        config=config,
        user_name=user,
        sample_name=sample,
        normalized_parquet_path=normalized,
    )

    report_path: Optional[Path] = None
    # A skipped module still produces a report (the "Modules not read" section), so render
    # regardless; the report signature captures whatever was produced.
    generate_longevity_report(
        modules_dir=modules_dir,
        output_path=reports_dir / "report.html",
        module_names=[module],
        user_name=user,
        sample_name=sample,
    )
    htmls = sorted(reports_dir.glob("*.html"))
    if htmls:
        report_path = max(htmls, key=lambda p: p.stat().st_mtime)

    return {
        "sample": sample,
        "module": module,
        "manifest": _manifest_signature(modules_dir, module),
        "weights": _weights_signature(modules_dir / f"{module}_weights.parquet"),
        "report": _report_signature(report_path),
    }


@app.command()
def snapshot(
    out: Annotated[Path, typer.Option(help="Directory to write per-(sample,module) JSON snapshots.")],
    user: Annotated[str, typer.Option(help="User id whose normalized parquets to read.")] = "anonymous",
    samples: Annotated[Optional[list[str]], typer.Option(help="Sample dir name(s); repeatable.")] = None,
    work: Annotated[
        Optional[Path],
        typer.Option(help="Scratch dir for annotation outputs (default: <out>/_work)."),
    ] = None,
) -> None:
    """Run every (sample, module) pair and write one JSON signature each."""
    load_env()
    out.mkdir(parents=True, exist_ok=True)
    work_root = work or (out / "_work")
    work_root.mkdir(parents=True, exist_ok=True)
    sample_list = samples or DEFAULT_SAMPLES

    written = 0
    for sample in sample_list:
        for module in GATE_MODULES:
            console.print(f"[cyan]snapshot[/cyan] {sample} × {module}")
            sig = _run_one(sample, module, user, work_root)
            target = out / f"{sample}__{module}.json"
            target.write_text(json.dumps(sig, indent=2, sort_keys=True))
            written += 1
            if "error" in sig:
                console.print(f"  [yellow]{sig['error']}[/yellow]")
    console.print(f"[green]Wrote {written} snapshots to {out}[/green]")


@app.command()
def compare(
    baseline: Annotated[Path, typer.Argument(help="Baseline snapshot directory.")],
    current: Annotated[Path, typer.Argument(help="Current snapshot directory.")],
) -> None:
    """Diff two snapshot directories; exit non-zero on any difference."""
    baseline_files = {p.name for p in baseline.glob("*.json")}
    current_files = {p.name for p in current.glob("*.json")}

    problems: list[str] = []
    only_baseline = baseline_files - current_files
    only_current = current_files - baseline_files
    for name in sorted(only_baseline):
        problems.append(f"missing in current: {name}")
    for name in sorted(only_current):
        problems.append(f"unexpected in current: {name}")

    for name in sorted(baseline_files & current_files):
        b = json.loads((baseline / name).read_text())
        c = json.loads((current / name).read_text())
        for diff in _diff(b, c, path=name):
            problems.append(diff)

    if problems:
        console.print(f"[bold red]REGRESSION: {len(problems)} difference(s)[/bold red]")
        for p in problems:
            console.print(f"  [red]•[/red] {p}")
        raise typer.Exit(1)
    console.print(f"[bold green]IDENTICAL[/bold green] — {len(baseline_files)} snapshots match")


def _diff(b, c, path: str) -> list[str]:
    """Recursively diff two JSON-like values, yielding a message per leaf mismatch."""
    out: list[str] = []
    if isinstance(b, dict) and isinstance(c, dict):
        for key in sorted(set(b) | set(c)):
            if key not in b:
                out.append(f"{path}.{key}: added ({c[key]!r})")
            elif key not in c:
                out.append(f"{path}.{key}: removed (was {b[key]!r})")
            else:
                out.extend(_diff(b[key], c[key], f"{path}.{key}"))
    elif b != c:
        out.append(f"{path}: {b!r} -> {c!r}")
    return out


if __name__ == "__main__":
    app()
