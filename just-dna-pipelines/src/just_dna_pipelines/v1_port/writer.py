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

def _authored_columns(model: type) -> list[str]:
    """The columns an author may write: every model field except the compiler-managed ones.

    0.4 added ``variant_key`` and ``authored_ident`` to ``VariantRow`` as *derived* identity, tagged
    ``compiler_managed`` in their schema extra. Emitting them from a port would author values the
    compiler computes — and `variant_key` is frozen at load, so an authored one is not overwritten.
    """
    columns: list[str] = []
    for name, field in model.model_fields.items():
        extra = field.json_schema_extra or {}
        if isinstance(extra, dict) and extra.get("compiler_managed"):
            continue
        columns.append(name)
    return columns


_VARIANT_COLUMNS = _authored_columns(VariantRow)
_STUDY_COLUMNS = _authored_columns(StudyRow)

#: How a multi-valued cell is spelled. The authored models split on ``[,;|]``; a semicolon is the
#: separator that never collides with prose in a `conclusion`-adjacent column.
_MULTI_JOIN = ";"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _flatten(value: object) -> object:
    """A list cell becomes its separator-joined CSV spelling; everything else passes through.

    Polars refuses to write a nested column ("CSV format does not support nested data"), and the
    authored models re-split the joined string on load, so this is the round-trip, not a lossy cast.
    """
    if isinstance(value, (list, tuple)):
        return _MULTI_JOIN.join(str(v) for v in value) or None
    return value


def _write_csv(rows: list, columns: list[str], path: Path) -> None:
    records = [
        {k: _flatten(v) for k, v in r.model_dump(include=set(columns)).items()} for r in rows
    ]
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
