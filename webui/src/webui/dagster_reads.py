"""What the dashboard reads from Dagster, gathered in one `webui.compute` worker call.

The ASGI process never calls Dagster on the event loop (a page load spent 0.5 to 0.8 s there,
freezing every client) nor from a thread of its own (pyo3 panics). `dashboard_snapshot` runs in a
spawned pool worker and returns plain data; `UploadState.on_load` applies it. This module imports
no Reflex, so the worker loads it cheaply.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from dagster import AssetKey, AssetRecordsFilter, DagsterRunStatus, RunsFilter
from pydantic import BaseModel

from just_dna_pipelines.annotation.assets import user_vcf_partitions
from just_dna_pipelines.annotation.resources import get_user_output_dir
from webui.dagster_env import get_dagster_instance

# Jobs whose runs the dashboard lists as analyses. `annotate_modules_and_report_job` is the one
# Start Analysis picks when the normalized parquet is current; it was missing, so those runs never
# appeared in the list.
ANNOTATION_JOB_NAMES = (
    "annotate_and_report_job",
    "annotate_modules_and_report_job",
    "annotate_all_job",
    "annotate_ensembl_only_job",
    "annotate_with_hf_modules_job",
)
RECENT_RUNS_LIMIT = 20

_RUN_STATUS_LABELS = {
    DagsterRunStatus.QUEUED: "QUEUED",
    DagsterRunStatus.NOT_STARTED: "QUEUED",
    DagsterRunStatus.STARTING: "STARTING",
    DagsterRunStatus.STARTED: "RUNNING",
    DagsterRunStatus.SUCCESS: "SUCCESS",
    DagsterRunStatus.FAILURE: "FAILURE",
    DagsterRunStatus.CANCELED: "CANCELED",
    DagsterRunStatus.CANCELING: "CANCELING",
}

# `user_vcf_source` metadata keys copied as they are into a file's info (`description` becomes `notes`).
_PLAIN_METADATA_KEYS = (
    "filename",
    "sample_name",
    "species",
    "reference_genome",
    "subject_id",
    "sex",
    "tissue",
    "study_name",
    "path",
    "size_mb",
    "upload_date",
    "source",
    "zenodo_url",
    "zenodo_license",
)


class DashboardSnapshot(BaseModel):
    """Plain data for one page load: sample metadata, annotated samples, recent runs."""

    vcf_source_info: dict[str, dict[str, Any]] = {}
    annotated_partitions: list[str] = []
    runs: list[dict[str, Any]] = []


def run_status_label(status: DagsterRunStatus) -> str:
    """The status word the dashboard shows for a Dagster run status."""
    return _RUN_STATUS_LABELS.get(status, "UNKNOWN")


def _plain(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def file_info_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """A file's info from `user_vcf_source` materialization metadata, as plain Python values."""
    file_info: dict[str, Any] = {key: _plain(metadata[key]) for key in _PLAIN_METADATA_KEYS if key in metadata}
    if "description" in metadata:
        file_info["notes"] = _plain(metadata["description"])
    if "custom_metadata" in metadata:
        custom = _plain(metadata["custom_metadata"])
        if isinstance(custom, dict):
            file_info["custom_fields"] = custom
    else:
        custom_fields = {key[len("custom/") :]: _plain(value) for key, value in metadata.items() if key.startswith("custom/")}
        if custom_fields:
            file_info["custom_fields"] = custom_fields
    return file_info


def _run_info(record: Any, default_user: str) -> dict[str, Any]:
    run = record.dagster_run
    ops = (run.run_config or {}).get("ops", {})
    hf_config = ops.get("user_hf_module_annotations", {}).get("config", {})
    duckdb_config = ops.get("user_annotated_vcf_duckdb", {}).get("config", {})
    norm_config = ops.get("user_vcf_normalized", {}).get("config", {})
    vcf_path = hf_config.get("vcf_path") or duckdb_config.get("vcf_path") or norm_config.get("vcf_path", "")
    sample_name = hf_config.get("sample_name") or duckdb_config.get("sample_name", "")
    modules = hf_config.get("modules", [])
    if duckdb_config and not modules:
        modules = ["ensembl"]
    output_path = None
    if run.status == DagsterRunStatus.SUCCESS and sample_name:
        user_name = hf_config.get("user_name") or duckdb_config.get("user_name", default_user)
        output_dir = get_user_output_dir() / user_name / sample_name / "modules"
        if output_dir.exists():
            output_path = str(output_dir)
    return {
        "run_id": run.run_id,
        "filename": Path(vcf_path).name if vcf_path else "unknown",
        "sample_name": sample_name,
        "modules": modules or [],
        "include_ensembl": bool(duckdb_config),
        "status": run_status_label(run.status),
        "started_at": datetime.fromtimestamp(record.start_time).isoformat() if record.start_time else None,
        "ended_at": datetime.fromtimestamp(record.end_time).isoformat() if record.end_time else None,
        "output_path": output_path,
    }


def dashboard_snapshot(safe_user_id: str, partition_keys: list[str]) -> DashboardSnapshot:
    """Read what a page load needs; runs in a `webui.compute` worker.

    `partition_keys` are the `{user}/{sample}` keys of the files on disk, checked for a
    `user_hf_module_annotations` materialization.
    """
    instance = get_dagster_instance()

    vcf_source_info: dict[str, dict[str, Any]] = {}
    if safe_user_id:
        prefix = f"{safe_user_id}/"
        for partition_key in instance.get_dynamic_partitions(user_vcf_partitions.name):
            if not partition_key.startswith(prefix):
                continue
            records = instance.fetch_materializations(
                records_filter=AssetRecordsFilter(asset_key=AssetKey("user_vcf_source"), asset_partitions=[partition_key]),
                limit=1,
            ).records
            mat = records[0].asset_materialization if records else None
            if mat and mat.metadata:
                vcf_source_info[partition_key] = file_info_from_metadata(mat.metadata)

    annotated = [
        pk
        for pk in partition_keys
        if instance.fetch_materializations(
            records_filter=AssetRecordsFilter(asset_key=AssetKey("user_hf_module_annotations"), asset_partitions=[pk]),
            limit=1,
        ).records
    ]

    records = [
        record
        for job_name in ANNOTATION_JOB_NAMES
        for record in instance.get_run_records(filters=RunsFilter(job_name=job_name), limit=RECENT_RUNS_LIMIT)
    ]
    records.sort(key=lambda r: r.start_time or 0, reverse=True)
    runs = [_run_info(record, safe_user_id) for record in records[:RECENT_RUNS_LIMIT]]

    return DashboardSnapshot(vcf_source_info=vcf_source_info, annotated_partitions=annotated, runs=runs)


def delete_orphaned_not_started_runs() -> int:
    """Delete runs left `NOT_STARTED` by a daemon submission that failed; runs in a worker at server start.

    Only at start: on every page load (as before) it could delete a run Start Analysis had just
    created in another tab, before its submission moved it on.
    """
    instance = get_dagster_instance()
    records = instance.get_run_records(filters=RunsFilter(statuses=[DagsterRunStatus.NOT_STARTED]), limit=100)
    for record in records:
        instance.delete_run(record.dagster_run.run_id)
    return len(records)
