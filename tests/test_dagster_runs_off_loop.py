"""Registering samples, starting runs and polling them happen in `webui.compute` workers.

`start_annotation_run` built the job snapshot and wrote the run on the event loop (0.31 s measured),
`poll_run_status` read the run and its logs there on every tick of every client's timer, and the
upload handlers wrote the sample's materialization there. The worker functions run here against a
real temporary instance; one test drives them through the real spawn pool with a loop ticker, and
`poll_run_status` is driven on a real `UploadState` with the worker call done in-process.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from dagster import AssetKey, AssetMaterialization, DagsterInstance, MetadataValue

from just_dna_pipelines.annotation.assets import user_vcf_partitions
from webui import state as webui_state
from webui.compute.pool import run_in_compute, start_pool, stop_pool
from webui.dagster_reads import (
    NormalizationStats,
    normalization_stats,
    output_materialization_info,
    poll_run,
    run_log_lines,
)
from webui.dagster_runs import create_webui_run, register_vcf_source, submit_or_discard_run
from webui.state import UploadState

PARTITION = "tester/sample_ü"
JOB = "normalize_vcf_job"
RUN_CONFIG = {"ops": {"user_vcf_normalized": {"config": {"vcf_path": "/nowhere/sample_ü.vcf"}}}}
MAX_LOOP_GAP_S = 0.2


@pytest.fixture
def instance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DagsterInstance:
    monkeypatch.setenv("DAGSTER_HOME", str(tmp_path / "dagster_home"))
    (tmp_path / "dagster_home").mkdir()
    return DagsterInstance.get()


def _materialize(instance: DagsterInstance, asset: str, metadata: dict[str, Any] | None = None) -> None:
    instance.report_runless_asset_event(AssetMaterialization(asset_key=asset, partition=PARTITION, metadata=metadata or {}))


# --------------------------------------------------------------------------- writes


def test_registering_adds_the_partition_once_and_keeps_metadata_types(instance: DagsterInstance) -> None:
    metadata = {
        "path": MetadataValue.path("/data/in/sample_ü.vcf"),
        "zenodo_url": MetadataValue.url("https://zenodo.org/records/1"),
        "size_bytes": 12,
        "species": "Homo sapiens",
    }
    register_vcf_source(PARTITION, metadata)
    register_vcf_source(PARTITION, {**metadata, "species": "Mus musculus"})

    assert instance.get_dynamic_partitions(user_vcf_partitions.name).count(PARTITION) == 1
    records = instance.fetch_materializations(AssetKey("user_vcf_source"), limit=10).records
    assert len(records) == 2
    latest = records[0].asset_materialization.metadata
    assert latest["path"] == MetadataValue.path("/data/in/sample_ü.vcf")
    assert latest["zenodo_url"] == MetadataValue.url("https://zenodo.org/records/1")
    assert latest["species"].value == "Mus musculus"


def test_a_run_is_created_tagged_and_a_refused_submission_deletes_it(instance: DagsterInstance) -> None:
    run_id = create_webui_run(JOB, RUN_CONFIG, PARTITION)
    run = instance.get_run_by_id(run_id)
    assert run.job_name == JOB
    assert run.tags["dagster/partition"] == PARTITION and run.tags["source"] == "webui"
    assert run.run_config == RUN_CONFIG

    # No daemon or code location here: the submission is refused, as in a UI without the daemon.
    submitted, error = submit_or_discard_run(run_id)
    assert submitted is False and error
    assert instance.get_run_by_id(run_id) is None


# --------------------------------------------------------------------------- reads


def test_normalization_stats_read_the_latest_materialization(instance: DagsterInstance) -> None:
    assert normalization_stats(PARTITION) is None
    _materialize(instance, "user_vcf_normalized", {"rows_before_filter": 10, "rows_after_filter": 7, "rows_removed": 3, "quality_filters_hash": "abc"})
    _materialize(instance, "user_vcf_normalized", {"rows_before_filter": 20, "rows_after_filter": 18, "rows_removed": 2, "quality_filters_hash": "def"})
    assert normalization_stats(PARTITION) == NormalizationStats(rows_before=20, rows_after=18, rows_removed=2, filters_hash="def")


def test_an_output_older_than_its_upstream_needs_materialization(instance: DagsterInstance) -> None:
    never = output_materialization_info(PARTITION)
    assert all(entry["needs_materialization"] and entry["timestamp"] == 0.0 for entry in never.values())

    _materialize(instance, "user_vcf_normalized")
    _materialize(instance, "user_hf_module_annotations")
    _materialize(instance, "user_longevity_report")
    info = output_materialization_info(PARTITION)
    assert info["user_hf_module_annotations"]["needs_materialization"] is False
    assert info["user_longevity_report"]["needs_materialization"] is False
    assert info["user_annotated_vcf_duckdb"]["needs_materialization"] is True  # never materialized

    _materialize(instance, "user_vcf_normalized")  # normalized again: annotations are now stale
    info = output_materialization_info(PARTITION)
    assert info["user_hf_module_annotations"]["needs_materialization"] is True
    assert info["user_longevity_report"]["needs_materialization"] is False  # its upstream did not move


def test_a_poll_reads_status_and_logs_and_discovers_the_childs_run(instance: DagsterInstance) -> None:
    placeholder = create_webui_run(JOB, RUN_CONFIG, PARTITION)
    instance.delete_run(placeholder)
    since = time.time()

    assert poll_run(placeholder, PARTITION, since, placeholder).found is False  # child not started yet

    real = create_webui_run(JOB, RUN_CONFIG, PARTITION)
    instance.report_engine_event("step ünïcode started", instance.get_run_by_id(real))
    poll = poll_run(placeholder, PARTITION, since, placeholder)
    assert (poll.discovered_run_id, poll.found, poll.status, poll.terminal) == (real, True, "QUEUED", False)
    assert any("step ünïcode started" in line for line in poll.logs)
    assert poll.logs == run_log_lines(real)

    instance.report_run_failed(instance.get_run_by_id(real))
    done = poll_run(real)
    assert (done.discovered_run_id, done.status, done.terminal, done.succeeded) == ("", "FAILURE", True, False)
    assert poll_run("no-such-run").found is False


def test_log_lines_keep_the_last_fifty(instance: DagsterInstance) -> None:
    run_id = create_webui_run(JOB, RUN_CONFIG, PARTITION)
    run = instance.get_run_by_id(run_id)
    for n in range(60):
        instance.report_engine_event(f"event {n}", run)
    lines = run_log_lines(run_id)
    assert len(lines) == 50
    assert lines[-1].endswith("event 59")


# --------------------------------------------------------------------------- through the pool


@pytest.fixture
def pool(instance: DagsterInstance) -> Iterator[None]:
    stop_pool()
    start_pool()  # after DAGSTER_HOME is set: spawned workers inherit it
    yield
    stop_pool()


def test_start_analysis_steps_run_in_workers_while_the_loop_keeps_answering(instance: DagsterInstance, pool: None) -> None:
    async def scenario() -> tuple[str, tuple[bool, str], float]:
        await run_in_compute(normalization_stats, PARTITION)  # a warm worker
        gaps: list[float] = []
        done = asyncio.Event()

        async def ticker() -> None:
            last = time.perf_counter()
            while not done.is_set():
                await asyncio.sleep(0.01)
                now = time.perf_counter()
                gaps.append(now - last)
                last = now

        tick = asyncio.create_task(ticker())
        run_id = await run_in_compute(create_webui_run, JOB, RUN_CONFIG, PARTITION)
        submitted = await run_in_compute(submit_or_discard_run, run_id)
        done.set()
        await tick
        return run_id, submitted, max(gaps)

    run_id, (submitted, _error), max_gap = asyncio.run(scenario())
    assert submitted is False and instance.get_run_by_id(run_id) is None
    assert max_gap < MAX_LOOP_GAP_S, f"the loop stalled {max_gap:.3f}s"


# --------------------------------------------------------------------------- poll_run_status on the state


@pytest.fixture
def in_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """The worker call made in this process: what is under test is the handler's use of the result."""

    async def call(fn: Any, *args: Any, timeout: float | None = None) -> Any:
        return fn(*args)

    monkeypatch.setattr(webui_state, "run_in_compute", call)


def _upload_state(run_id: str, *, discovering: bool) -> UploadState:
    state = UploadState()
    state.safe_user_id = "tester"
    state.polling_active = True
    state.running = True
    state.active_run_id = run_id
    state.runs = [{"run_id": run_id, "status": "RUNNING", "sample_name": "sample_ü", "dagster_url": ""}]
    if discovering:
        state._inproc_discover_partition = PARTITION
        state._inproc_discover_since = time.time()
        state._inproc_original_run_id = run_id
    return state


def test_polling_swaps_in_the_discovered_run_and_stops_at_its_end(instance: DagsterInstance, in_process: None) -> None:
    placeholder = create_webui_run(JOB, RUN_CONFIG, PARTITION)
    instance.delete_run(placeholder)
    state = _upload_state(placeholder, discovering=True)

    assert asyncio.run(state.poll_run_status()) is None  # nothing to discover yet
    assert state.active_run_id == placeholder and state.polling_active

    real = create_webui_run(JOB, RUN_CONFIG, PARTITION)
    asyncio.run(state.poll_run_status())
    assert state.active_run_id == real and state._inproc_discover_partition == ""
    assert state.runs[0]["run_id"] == real and state.runs[0]["status"] == "QUEUED"

    instance.report_run_failed(instance.get_run_by_id(real))
    events = asyncio.run(state.poll_run_status())
    assert state.runs[0]["status"] == "FAILURE" and state.runs[0]["ended_at"]
    assert (state.polling_active, state.running, state.last_run_success) == (False, False, False)
    assert len(events) == 2  # refresh the output files, and the failure toast


def test_a_run_that_disappeared_stops_polling(instance: DagsterInstance, in_process: None) -> None:
    state = _upload_state("gone-run", discovering=False)
    asyncio.run(state.poll_run_status())
    assert state.polling_active is False


def test_a_finished_child_ends_discovery_without_reading_dagster(instance: DagsterInstance, monkeypatch: pytest.MonkeyPatch) -> None:
    async def must_not_run(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("polled Dagster after the child had reported back")

    monkeypatch.setattr(webui_state, "run_in_compute", must_not_run)
    state = _upload_state("placeholder", discovering=True)
    state.runs = [{**state.runs[0], "status": "SUCCESS"}]
    asyncio.run(state.poll_run_status())
    assert state._inproc_discover_partition == "" and state._inproc_original_run_id == ""
