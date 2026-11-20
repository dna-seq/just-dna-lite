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

from just_dna_pipelines.annotation.annotation_runner import (
    FULL_JOB,
    REUSE_NORMALIZED_JOB,
    normalized_parquet_is_current,
)
from just_dna_pipelines.annotation.assets import user_vcf_partitions
from just_dna_pipelines.annotation.resources import get_user_input_dir, get_user_output_dir
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


def normalize_run_config_if_stale(
    safe_user_id: str, selected_file: str, partition_key: str
) -> dict | None:
    """Return a ``normalize_vcf_job`` run config if normalization is needed, else None.

    Only the *decision* happens here — Dagster metadata plus a parquet footer read, both
    cheap.  Running the job is the caller's job, via ``webui.compute.jobs``, so the
    normalization pipeline never executes inside the ASGI process.

    Runs in a `webui.compute` worker (`run_in_compute`), like everything here.
    """
    sample_name = selected_file.replace(".vcf.gz", "").replace(".vcf", "")
    normalized_path = get_user_output_dir() / safe_user_id / sample_name / "user_vcf_normalized.parquet"
    if normalized_parquet_is_current(get_dagster_instance(), partition_key, normalized_path):
        return None

    vcf_path = get_user_input_dir() / safe_user_id / selected_file
    if not vcf_path.exists():
        return None

    return {
        "ops": {
            "user_vcf_normalized": {
                "config": {"vcf_path": str(vcf_path.absolute())}
            }
        }
    }


def analysis_job_name(
    partition_key: str, has_hf_modules: bool, has_ensembl: bool
) -> str:
    """The job an analysis runs: skip normalization when the normalized parquet is current.

    Every analysis job used to normalize again, even right after the select-time normalization
    had written a current parquet: minutes of work per click on a whole genome, and a second
    writer of the same sample while that first pass was still running. The staleness test is
    the runner's (`normalized_parquet_is_current`), so the UI, `uv run annotate` and the MCP
    worker agree on when a parquet can be reused. The Ensembl jobs have no reuse variant.

    Runs in a `webui.compute` worker (`run_in_compute`).
    """
    if has_ensembl:
        return "annotate_all_job" if has_hf_modules else "annotate_ensembl_only_job"
    normalized_path = get_user_output_dir() / partition_key / "user_vcf_normalized.parquet"
    if has_hf_modules and normalized_parquet_is_current(
        get_dagster_instance(), partition_key, normalized_path
    ):
        return REUSE_NORMALIZED_JOB
    return FULL_JOB


class NormalizationStats(BaseModel):
    """Quality-filter counts recorded on the sample's latest `user_vcf_normalized` materialization."""

    rows_before: int = 0
    rows_after: int = 0
    rows_removed: int = 0
    filters_hash: str = ""


def _int_value(metadata: dict[str, Any], key: str) -> int:
    value = metadata.get(key)
    return int(value.value) if value is not None and hasattr(value, "value") else 0


def _str_value(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key)
    return str(value.value) if value is not None and hasattr(value, "value") else ""


def _latest_materialization(instance: Any, asset_name: str, partition_key: str) -> Any:
    records = instance.fetch_materializations(
        records_filter=AssetRecordsFilter(asset_key=AssetKey(asset_name), asset_partitions=[partition_key]),
        limit=1,
    ).records
    return records[0] if records else None


def normalization_stats(partition_key: str) -> NormalizationStats | None:
    """The sample's normalization counts, or None when it was never normalized."""
    record = _latest_materialization(get_dagster_instance(), "user_vcf_normalized", partition_key)
    mat = record.asset_materialization if record else None
    if not mat or not mat.metadata:
        return None
    return NormalizationStats(
        rows_before=_int_value(mat.metadata, "rows_before_filter"),
        rows_after=_int_value(mat.metadata, "rows_after_filter"),
        rows_removed=_int_value(mat.metadata, "rows_removed"),
        filters_hash=_str_value(mat.metadata, "quality_filters_hash"),
    )


# Each output asset and the asset it is computed from: newer upstream means "needs materialization".
OUTPUT_ASSET_UPSTREAM = {
    "user_hf_module_annotations": "user_vcf_normalized",
    "user_longevity_report": "user_hf_module_annotations",
    "user_annotated_vcf_duckdb": "user_vcf_normalized",
    "user_vcf_exports": "user_hf_module_annotations",
}


def output_materialization_info(partition_key: str) -> dict[str, dict[str, Any]]:
    """For each output asset: when it was last materialized, by which run, and whether it is stale.

    Keyed by asset name, each with ``materialized_at`` (str), ``needs_materialization`` (bool),
    ``timestamp`` (float) and ``run_id`` (str).
    """
    instance = get_dagster_instance()
    timestamps: dict[str, float] = {}
    run_ids: dict[str, str] = {}
    for asset_name in ("user_vcf_normalized", *OUTPUT_ASSET_UPSTREAM):
        record = _latest_materialization(instance, asset_name, partition_key)
        timestamps[asset_name] = record.timestamp if record else 0.0
        run_ids[asset_name] = (record.run_id or "") if record else ""
    info: dict[str, dict[str, Any]] = {}
    for asset_name, upstream in OUTPUT_ASSET_UPSTREAM.items():
        ts = timestamps[asset_name]
        info[asset_name] = {
            "materialized_at": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "",
            "needs_materialization": ts == 0.0 or timestamps[upstream] > ts,
            "timestamp": ts,
            "run_id": run_ids[asset_name],
        }
    return info


class SampleDagsterState(BaseModel):
    """What showing a selected sample reads from Dagster, in one worker call."""

    norm_stats: NormalizationStats | None = None
    outputs: dict[str, dict[str, Any]] = {}


def sample_dagster_state(partition_key: str) -> SampleDagsterState:
    return SampleDagsterState(norm_stats=normalization_stats(partition_key), outputs=output_materialization_info(partition_key))


TERMINAL_STATUSES = frozenset({DagsterRunStatus.SUCCESS, DagsterRunStatus.FAILURE, DagsterRunStatus.CANCELED})
RUN_LOG_LINES = 50


def run_log_lines(run_id: str, last: int = RUN_LOG_LINES) -> list[str]:
    """The run's last *last* events as ``[HH:MM:SS] message`` lines."""
    lines = []
    for event in get_dagster_instance().all_logs(run_id)[-last:]:
        timestamp = datetime.fromtimestamp(event.timestamp).strftime("%H:%M:%S")
        message = event.message or (event.dagster_event.event_type_value if event.dagster_event else "Event")
        lines.append(f"[{timestamp}] {message}")
    return lines


class RunPoll(BaseModel):
    """One poll of the active run: a run discovered for a compute-child job, its status and logs."""

    discovered_run_id: str = ""
    found: bool = False
    status: str = ""
    terminal: bool = False
    succeeded: bool = False
    logs: list[str] = []


def poll_run(run_id: str, discover_partition: str = "", discover_since: float = 0.0, placeholder_run_id: str = "") -> RunPoll:
    """Read the active run's status and recent logs.

    With *discover_partition* set, *run_id* is a deleted placeholder: the job runs in a compute
    child, which creates the real run. It is the newest web UI run on that partition created since
    *discover_since* (5 s of slack); until it appears, ``found`` stays False.
    """
    instance = get_dagster_instance()
    discovered = ""
    if discover_partition:
        for record in instance.get_run_records(limit=20):
            run = record.dagster_run
            if (
                run.tags.get("dagster/partition") == discover_partition
                and run.tags.get("source") == "webui"
                and run.run_id != placeholder_run_id
                and record.create_timestamp.timestamp() >= discover_since - 5
            ):
                discovered = run.run_id
                break
        if not discovered:
            return RunPoll()
        run_id = discovered
    run = instance.get_run_by_id(run_id) if run_id else None
    if run is None:
        return RunPoll(discovered_run_id=discovered)
    return RunPoll(
        discovered_run_id=discovered,
        found=True,
        status=run_status_label(run.status),
        terminal=run.status in TERMINAL_STATUSES,
        succeeded=run.status == DagsterRunStatus.SUCCESS,
        logs=run_log_lines(run_id),
    )
