"""
Serialize adapter output into a module spec directory.

Writes ``module_spec.yaml`` + ``variants.csv`` + ``studies.csv`` (the compiler's mandatory inputs)
plus a ``v1_port.log`` provenance record. CSVs are written with Polars; ``None`` becomes an empty
cell, which the compiler's ``csv.DictReader`` reader maps back to ``None``.
"""

import hashlib
from pathlib import Path
from typing import Optional

import polars as pl
import yaml

from just_dna_pipelines.module_compiler.models import (
    ModuleSpecConfig,
    StudyRow,
    VariantRow,
)

_VARIANT_COLUMNS = list(VariantRow.model_fields.keys())
_STUDY_COLUMNS = list(StudyRow.model_fields.keys())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(rows: list, columns: list[str], path: Path) -> None:
    records = [r.model_dump() for r in rows]
    if not records:
        # Header-only file so the shape is explicit even when a module yields no rows.
        path.write_text(",".join(columns) + "\n", encoding="utf-8")
        return
    frame = pl.DataFrame(records).select(columns)
    frame.write_csv(path)


def write_spec_dir(
    spec: ModuleSpecConfig,
    variants: list[VariantRow],
    studies: list[StudyRow],
    out_dir: Path,
    *,
    source_repo: str,
    source_file: Optional[Path],
    warnings: list[str],
) -> Path:
    """Write module_spec.yaml, variants.csv, studies.csv, and v1_port.log into ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "module_spec.yaml").write_text(
        yaml.safe_dump(spec.model_dump(exclude_none=False), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    _write_csv(variants, _VARIANT_COLUMNS, out_dir / "variants.csv")
    _write_csv(studies, _STUDY_COLUMNS, out_dir / "studies.csv")

    warning_lines = [f"  - {w}" for w in warnings] if warnings else ["  (none)"]
    log_lines = [
        f"module: {spec.module.name}",
        f"source_repo: dna-seq/{source_repo}",
        f"source_file: {source_file.name if source_file else '(derived from ClinVar)'}",
        f"source_sha256: sha256:{_sha256(source_file) if source_file else '(n/a)'}",
        f"variant_rows: {len(variants)}",
        f"study_rows: {len(studies)}",
        "warnings:",
        *warning_lines,
    ]
    (out_dir / "v1_port.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    return out_dir
