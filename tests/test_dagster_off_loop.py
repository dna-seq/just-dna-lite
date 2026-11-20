"""Dagster reads and writes the web UI makes run in `webui.compute` workers, off the event loop.

`UploadState.on_load` read Dagster on the event loop (0.5 to 0.8 s per page load, every client
frozen) and deleted NOT_STARTED runs on each load; the PRS checkpoint opened an instance under the
state lock. These tests run the worker functions against a real temporary instance, in-process and
through the real spawn pool, and check the loop keeps ticking while the pool works.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from dagster import AssetMaterialization, DagsterInstance, DagsterRunStatus, MetadataValue
from dagster._core.storage.dagster_run import DagsterRun
from dagster._core.utils import make_new_run_id

from just_dna_pipelines.annotation.assets import user_vcf_partitions
from webui.compute.pool import run_in_compute, start_pool, stop_pool
from webui.dagster_reads import (
    ANNOTATION_JOB_NAMES,
    DashboardSnapshot,
    dashboard_snapshot,
    delete_orphaned_not_started_runs,
    file_info_from_metadata,
    run_status_label,
)
from webui.prs_checkpoint import _prs_partition_key, restore_in_worker
from webui.state import _write_prs_checkpoint

USER = "tester"
ANNOTATED = f"{USER}/annotated_sample"
UPLOADED = f"{USER}/uploaded_sample"
OTHER_USER = "someone_else/their_sample"
# The loop must answer within Reflex's own warning threshold while a worker reads Dagster.
LOOP_TICK_S = 0.01
MAX_LOOP_GAP_S = 0.2


@pytest.fixture
def dagster_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    home = tmp_path / "dagster_home"
    home.mkdir()
    monkeypatch.setenv("DAGSTER_HOME", str(home))
    yield home


@pytest.fixture
def seeded(dagster_home: Path) -> dict[str, Any]:
    """An instance with two of the user's samples, one of another user's, and runs in each status."""
    instance = DagsterInstance.get()
    instance.add_dynamic_partitions(user_vcf_partitions.name, [ANNOTATED, UPLOADED, OTHER_USER])
    source_metadata = {
        "filename": MetadataValue.text("annotated_sample.vcf.gz"),
        "species": MetadataValue.text("Homo sapiens"),
        "reference_genome": MetadataValue.text("GRCh38"),
        "description": MetadataValue.text("Ünïcödé notes"),
        "custom/cohort": MetadataValue.text("pilot"),
    }
    instance.report_runless_asset_event(
        AssetMaterialization(asset_key="user_vcf_source", partition=ANNOTATED, metadata=source_metadata)
    )
    instance.report_runless_asset_event(
        AssetMaterialization(
            asset_key="user_vcf_source",
            partition=OTHER_USER,
            metadata={"filename": MetadataValue.text("their_sample.vcf")},
        )
    )
    instance.report_runless_asset_event(AssetMaterialization(asset_key="user_hf_module_annotations", partition=ANNOTATED))

    runs: dict[str, tuple[str, DagsterRunStatus]] = {}
    for job_name in (*ANNOTATION_JOB_NAMES, "normalize_vcf_job"):
        for status in (DagsterRunStatus.SUCCESS, DagsterRunStatus.NOT_STARTED):
            run_id = make_new_run_id()
            instance.add_run(
                DagsterRun(
                    job_name=job_name,
                    run_id=run_id,
                    run_config={"ops": {"user_hf_module_annotations": {"config": {"vcf_path": "/x/annotated_sample.vcf.gz", "sample_name": "annotated_sample"}}}},
                    status=status,
                )
            )
            runs[run_id] = (job_name, status)
    return {"metadata": source_metadata, "runs": runs}


def test_the_snapshot_reads_the_users_samples_annotations_and_analysis_runs(seeded: dict[str, Any]) -> None:
    snapshot = dashboard_snapshot(USER, [ANNOTATED, UPLOADED])

    assert set(snapshot.vcf_source_info) == {ANNOTATED}  # the other user's sample stays out
    assert snapshot.vcf_source_info[ANNOTATED] == file_info_from_metadata(seeded["metadata"])
    assert snapshot.vcf_source_info[ANNOTATED]["notes"] == "Ünïcödé notes"
    assert snapshot.vcf_source_info[ANNOTATED]["custom_fields"] == {"cohort": "pilot"}
    assert set(snapshot.annotated_partitions) == {ANNOTATED}

    expected = {
        run_id: run_status_label(status)
        for run_id, (job_name, status) in seeded["runs"].items()
        if job_name in ANNOTATION_JOB_NAMES
    }
    assert {run["run_id"]: run["status"] for run in snapshot.runs} == expected
    assert all(run["filename"] == "annotated_sample.vcf.gz" for run in snapshot.runs)


def test_a_reuse_run_is_listed(seeded: dict[str, Any]) -> None:
    """Start Analysis's reuse job was missing from the list, so its runs never showed."""
    listed_jobs = {seeded["runs"][run["run_id"]][0] for run in dashboard_snapshot(USER, []).runs}
    assert "annotate_modules_and_report_job" in listed_jobs


def test_no_user_reads_no_sample_metadata(seeded: dict[str, Any]) -> None:
    assert dashboard_snapshot("", [ANNOTATED]).vcf_source_info == {}


def test_the_snapshot_crosses_a_process_boundary(seeded: dict[str, Any]) -> None:
    snapshot = dashboard_snapshot(USER, [ANNOTATED, UPLOADED])
    assert DashboardSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot


def test_orphan_cleanup_deletes_only_not_started_runs(seeded: dict[str, Any]) -> None:
    instance = DagsterInstance.get()
    not_started = {rid for rid, (_job, status) in seeded["runs"].items() if status == DagsterRunStatus.NOT_STARTED}

    assert delete_orphaned_not_started_runs() == len(not_started)

    remaining = {record.dagster_run.run_id for record in instance.get_run_records()}
    assert remaining == set(seeded["runs"]) - not_started
    assert delete_orphaned_not_started_runs() == 0


def _rows() -> list[dict[str, Any]]:
    return [
        {"pgs_id": "PGS000001", "score": 1.25, "risk_estimates_by_method": {"AUROC model": "0.7%"}, "trait": "Ωmega"},
        {"pgs_id": "PGS000002", "score": None, "risk_estimates_by_method": {}, "trait": ""},
    ]


async def _max_loop_gap_while(work: Any) -> tuple[Any, float]:
    """Await *work* while a ticker measures the longest stretch the loop did not answer."""
    gaps: list[float] = []
    done = asyncio.Event()

    async def ticker() -> None:
        last = time.perf_counter()
        while not done.is_set():
            await asyncio.sleep(LOOP_TICK_S)
            now = time.perf_counter()
            gaps.append(now - last)
            last = now

    tick_task = asyncio.create_task(ticker())
    try:
        result = await work
    finally:
        done.set()
        await tick_task
    return result, max(gaps, default=0.0)


@pytest.fixture
def pool(dagster_home: Path) -> Iterator[None]:
    stop_pool()
    start_pool()  # after DAGSTER_HOME is set: spawned workers inherit the environment
    yield
    stop_pool()


def test_page_load_reads_run_in_a_worker_while_the_loop_keeps_answering(seeded: dict[str, Any], pool: None) -> None:
    async def scenario() -> tuple[DashboardSnapshot, float]:
        await run_in_compute(dashboard_snapshot, USER, [])  # a warm worker, as at server start
        return await _max_loop_gap_while(run_in_compute(dashboard_snapshot, USER, [ANNOTATED, UPLOADED]))

    snapshot, max_gap = asyncio.run(scenario())

    assert snapshot == dashboard_snapshot(USER, [ANNOTATED, UPLOADED])
    assert max_gap < MAX_LOOP_GAP_S, f"the loop stalled {max_gap:.3f}s"


def test_the_prs_checkpoint_round_trips_through_workers(dagster_home: Path, tmp_path: Path, pool: None) -> None:
    sample_dir = tmp_path / "users" / USER / "sampleA"
    sample_dir.mkdir(parents=True)
    parquet_path = str(sample_dir / "user_vcf_normalized.parquet")
    rows = _rows()

    async def scenario() -> tuple[Any, float]:
        await run_in_compute(restore_in_worker, _prs_partition_key(parquet_path))  # warm a worker
        _, write_gap = await _max_loop_gap_while(
            _write_prs_checkpoint((parquet_path, rows, "GRCh38", "EUR", "wgs"))
        )
        restored = await run_in_compute(restore_in_worker, _prs_partition_key(parquet_path))
        return restored, write_gap

    restored, write_gap = asyncio.run(scenario())

    assert restored.status == "restored"
    assert restored.rows == rows
    assert restored.sample_type == "wgs"
    assert write_gap < MAX_LOOP_GAP_S, f"the loop stalled {write_gap:.3f}s"


def test_no_checkpoint_args_writes_nothing(dagster_home: Path) -> None:
    asyncio.run(_write_prs_checkpoint(None))
    assert not (dagster_home / "history").exists()
