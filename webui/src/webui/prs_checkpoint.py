"""The PRS checkpoint: a sample's PRS rows in a file beside it, indexed by a small Dagster event.

Lives apart from `webui.state` so a spawned `webui.compute` worker can import it without Reflex:
the web UI writes and reads checkpoints through `checkpoint_in_worker` / `restore_in_worker`,
never on the event loop (Dagster calls are never made from a thread of the ASGI process either).
"""

from __future__ import annotations

import importlib.metadata
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Literal

from dagster import AssetKey, AssetMaterialization, AssetRecordsFilter, DagsterInstance, MetadataValue
from pydantic import BaseModel

from webui.dagster_env import get_dagster_instance

logger = logging.getLogger(__name__)


def _prs_results_version() -> str:
    """Version tag for stored PRS results.

    Both libraries shape a stored row: prs-ui builds it, just-prs computes and
    enriches it (0.10.4 picks the percentile curve by karyotype), so either release
    makes a checkpoint stale.
    """
    return f"prs-ui={importlib.metadata.version('prs-ui')};just-prs={importlib.metadata.version('just-prs')}"




# The PRS checkpoint keeps its rows in a file beside the sample and only an index entry in
# Dagster. Rows used to ride in the materialization metadata (~10 MB per compute), and
# runless events can never be deleted, so the event log grew to 30 GB (issue #35). JSON,
# not parquet: `risk_estimates_by_method` is a dict keyed by method name, which a struct
# column would widen to every key seen in any row.
PRS_CHECKPOINT_FILENAME = "prs_results.json"
PRS_RESULTS_ASSET_KEY = "prs_results"


class PrsCheckpoint(BaseModel):
    """What the restore path found for one sample's partition."""

    status: Literal["restored", "stale", "absent"]
    rows: list[dict[str, Any]] = []
    sample_type: str = ""
    row_count: int = 0


def _prs_partition_key(parquet_path: str) -> str:
    """``{user}/{sample}`` for a sample's normalized parquet."""
    p = Path(parquet_path)
    return f"{p.parent.parent.name}/{p.parent.name}"


def _write_prs_checkpoint_file(sample_dir: Path, rows: list[dict[str, Any]]) -> Path:
    """Write *rows* to the sample's checkpoint file, replacing it atomically.

    A per-write temp name in the same directory, then ``os.replace``: two tabs on one
    sample must not read each other's half-written file.
    """
    payload = json.dumps(rows)
    sample_dir.mkdir(parents=True, exist_ok=True)
    final_path = sample_dir / PRS_CHECKPOINT_FILENAME
    fd, tmp_name = tempfile.mkstemp(dir=sample_dir, prefix=f".{PRS_CHECKPOINT_FILENAME}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(payload)
    tmp_path.chmod(0o644)  # mkstemp creates 0600; match the sample's other outputs
    os.replace(tmp_path, final_path)
    return final_path


def _read_prs_checkpoint_file(path: Path) -> list[dict[str, Any]] | None:
    """Rows from a checkpoint file, or ``None`` when it is missing or unreadable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("PRS checkpoint %s unreadable, recomputing: %s", path, exc)
        return None
    if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
        logger.warning("PRS checkpoint %s is not a list of rows, recomputing", path)
        return None
    return data


def checkpoint_prs_results(
    instance: DagsterInstance,
    parquet_path: str,
    rows: list[dict[str, Any]],
    genome_build: str,
    ancestry: str,
    sample_type: str,
) -> Path:
    """Write *rows* beside the sample and index them with a small Dagster event."""
    final_path = _write_prs_checkpoint_file(Path(parquet_path).parent, rows)
    pgs_ids = [r.get("pgs_id", "") for r in rows]
    instance.report_runless_asset_event(
        AssetMaterialization(
            asset_key=PRS_RESULTS_ASSET_KEY,
            partition=_prs_partition_key(parquet_path),
            metadata={
                "path": MetadataValue.path(str(final_path)),
                "pgs_ids": MetadataValue.text(json.dumps(pgs_ids)),
                "genome_build": MetadataValue.text(genome_build),
                "ancestry": MetadataValue.text(ancestry),
                "sample_type": MetadataValue.text(sample_type),
                "row_count": MetadataValue.int(len(rows)),
                "format_version": MetadataValue.text(_prs_results_version()),
            },
        )
    )
    return final_path


def _metadata_text(metadata: dict[str, Any], key: str) -> str:
    entry = metadata.get(key)
    return str(entry.value) if entry is not None and hasattr(entry, "value") else ""


def restore_prs_checkpoint(instance: DagsterInstance, partition_key: str) -> PrsCheckpoint:
    """Read the newest checkpoint for *partition_key*.

    An event without a ``path`` (written before issue #35) or a missing or unreadable
    file counts as no checkpoint, so the caller recomputes.
    """
    result = instance.fetch_materializations(
        records_filter=AssetRecordsFilter(
            asset_key=AssetKey(PRS_RESULTS_ASSET_KEY),
            asset_partitions=[partition_key],
        ),
        limit=1,
    )
    if not result.records:
        return PrsCheckpoint(status="absent")
    mat = result.records[0].asset_materialization
    if not mat or not mat.metadata:
        return PrsCheckpoint(status="absent")
    if _metadata_text(mat.metadata, "format_version") != _prs_results_version():
        return PrsCheckpoint(status="stale")
    path_text = _metadata_text(mat.metadata, "path")
    if not path_text:
        return PrsCheckpoint(status="absent")
    rows = _read_prs_checkpoint_file(Path(path_text))
    if rows is None:
        return PrsCheckpoint(status="absent")
    rows = [row for row in rows if not str(row.get("sample") or "")]
    count_text = _metadata_text(mat.metadata, "row_count")
    return PrsCheckpoint(
        status="restored",
        rows=rows,
        sample_type=_metadata_text(mat.metadata, "sample_type"),
        row_count=int(count_text) if count_text else len(rows),
    )




def checkpoint_in_worker(
    parquet_path: str,
    rows: list[dict[str, Any]],
    genome_build: str,
    ancestry: str,
    sample_type: str,
) -> str:
    """`checkpoint_prs_results` on this process's instance; run through `webui.compute.pool`."""
    return str(checkpoint_prs_results(get_dagster_instance(), parquet_path, rows, genome_build, ancestry, sample_type))


def restore_in_worker(partition_key: str) -> PrsCheckpoint:
    """`restore_prs_checkpoint` on this process's instance; run through `webui.compute.pool`."""
    return restore_prs_checkpoint(get_dagster_instance(), partition_key)
