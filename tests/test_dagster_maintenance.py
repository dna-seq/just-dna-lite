"""The event-log prune, exercised against a real Dagster sqlite instance.

The bug this guards is specific: ``report_runless_asset_event`` writes rows with
an empty ``run_id``, so they survive every run deletion Dagster offers, and the
web UI's PRS checkpoint wrote one ~10 MB row per compute.  The tests below build
the same shape with a real ``DagsterInstance`` rather than a handcrafted schema,
so a Dagster upgrade that renames a column fails here instead of silently
pruning nothing in production.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path

import pytest
from dagster import (
    AssetKey,
    AssetMaterialization,
    DagsterInstance,
    MetadataValue,
    job,
    op,
)
from webui.state import (
    _prs_partition_key,
    checkpoint_prs_results,
    restore_prs_checkpoint,
)

from just_dna_lite.dagster_maintenance import (
    INDEX_DB,
    STRAY_INDEX_DB,
    measure,
    prune_history,
    prune_runless_materializations,
    resolve_dagster_home,
    vacuum,
)

ASSET = "prs_results"
PAYLOAD_KB = 64


@op
def _noop_op() -> None:
    """A body for the job the paging test needs a real run of."""


@job
def _a_job() -> None:
    _noop_op()


def _checkpoint(instance: DagsterInstance, partition: str, marker: str) -> None:
    """Write one runless materialization the size of a real PRS checkpoint."""
    instance.report_runless_asset_event(
        AssetMaterialization(
            asset_key=ASSET,
            partition=partition,
            metadata={
                "results": MetadataValue.json({"rows": [marker] * (PAYLOAD_KB * 16)}),
                "marker": MetadataValue.text(marker),
            },
        )
    )


@pytest.fixture
def instance_home(tmp_path: Path) -> Path:
    home = tmp_path / "dagster"
    home.mkdir()
    return home


def _event_log(home: Path) -> Path:
    return home / INDEX_DB


def _markers(home: Path) -> list[str]:
    """The ``marker`` metadata of every runless materialization still stored."""
    with DagsterInstance.from_ref(DagsterInstance.local_temp(str(home)).get_ref()) as instance:
        records = instance.fetch_materializations(AssetKey(ASSET), limit=1000).records
        found = []
        for record in records:
            materialization = record.asset_materialization
            if materialization is None:
                continue
            marker = materialization.metadata.get("marker")
            found.append(str(marker.value) if marker is not None else "")
        return found


def test_prune_keeps_the_newest_checkpoint_per_partition(instance_home: Path) -> None:
    with DagsterInstance.local_temp(str(instance_home)) as instance:
        for marker in ("first", "second", "third"):
            _checkpoint(instance, "public/sampleA", marker)
        _checkpoint(instance, "public/sampleB", "only-b")

    rows, payload = prune_runless_materializations(_event_log(instance_home))

    # Two of sampleA's three go; sampleB's single checkpoint is its newest.
    assert rows == 2
    assert payload > 0
    assert sorted(_markers(instance_home)) == ["only-b", "third"]


def test_prune_is_idempotent(instance_home: Path) -> None:
    with DagsterInstance.local_temp(str(instance_home)) as instance:
        for marker in ("a", "b", "c"):
            _checkpoint(instance, "public/sample", marker)

    first_rows, _ = prune_runless_materializations(_event_log(instance_home))
    second_rows, second_payload = prune_runless_materializations(_event_log(instance_home))

    assert first_rows == 2
    assert (second_rows, second_payload) == (0, 0)
    assert _markers(instance_home) == ["c"]


def test_dry_run_changes_nothing(instance_home: Path) -> None:
    with DagsterInstance.local_temp(str(instance_home)) as instance:
        for marker in ("a", "b", "c"):
            _checkpoint(instance, "public/sample", marker)

    before = _event_log(instance_home).stat().st_size
    rows, payload = prune_runless_materializations(_event_log(instance_home), dry_run=True)

    assert rows == 2
    assert payload > 0
    assert _event_log(instance_home).stat().st_size == before
    assert sorted(_markers(instance_home)) == ["a", "b", "c"]


def test_run_scoped_events_are_never_pruned(instance_home: Path) -> None:
    """Rows belonging to a run are the run's to delete, not this prune's."""
    with DagsterInstance.local_temp(str(instance_home)) as instance:
        _checkpoint(instance, "public/sample", "runless")

    event_log = _event_log(instance_home)
    connection = sqlite3.connect(event_log)
    connection.execute(
        "INSERT INTO event_logs (run_id, event, dagster_event_type, timestamp, asset_key, partition)"
        " SELECT 'a-real-run-id', event, dagster_event_type, timestamp, asset_key, partition"
        " FROM event_logs WHERE asset_key IS NOT NULL LIMIT 1"
    )
    connection.commit()
    owned_before = connection.execute(
        "SELECT COUNT(*) FROM event_logs WHERE run_id = 'a-real-run-id'"
    ).fetchone()[0]
    connection.close()

    prune_runless_materializations(event_log)

    connection = sqlite3.connect(event_log)
    owned_after = connection.execute(
        "SELECT COUNT(*) FROM event_logs WHERE run_id = 'a-real-run-id'"
    ).fetchone()[0]
    connection.close()
    assert owned_before == owned_after == 1


def test_vacuum_returns_the_freed_pages_to_the_filesystem(instance_home: Path) -> None:
    with DagsterInstance.local_temp(str(instance_home)) as instance:
        for index in range(12):
            _checkpoint(instance, "public/sample", f"checkpoint-{index}")

    event_log = _event_log(instance_home)
    grown = event_log.stat().st_size
    prune_runless_materializations(event_log)
    pruned = event_log.stat().st_size

    # Deleting rows frees pages inside the file; only VACUUM shrinks the file.
    assert pruned == grown
    assert vacuum(event_log) == ""
    assert event_log.stat().st_size < grown


def test_vacuum_refuses_when_the_disk_cannot_hold_a_second_copy(
    instance_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with DagsterInstance.local_temp(str(instance_home)) as instance:
        for index in range(12):
            _checkpoint(instance, "public/sample", f"checkpoint-{index}")
    event_log = _event_log(instance_home)
    prune_runless_materializations(event_log)

    monkeypatch.setattr(
        shutil, "disk_usage", lambda _: type("Usage", (), {"free": 1024})()
    )
    reason = vacuum(event_log)

    assert "needs" in reason
    assert event_log.exists()


def test_measure_counts_the_stray_index_written_for_an_empty_run_id(instance_home: Path) -> None:
    """``.db`` has no run id in its name, so it must not pass as a per-run file."""
    with DagsterInstance.local_temp(str(instance_home)) as instance:
        _checkpoint(instance, "public/sample", "a")

    stray = instance_home / STRAY_INDEX_DB
    stray.write_bytes(b"x" * 4096)
    sizes = measure(instance_home)

    assert sizes.stray_index_db == 4096
    assert sizes.total >= sizes.index_db + 4096


def test_dagster_home_env_var_wins_over_the_repo_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DAGSTER_HOME", str(tmp_path / "elsewhere"))
    assert resolve_dagster_home(tmp_path) == tmp_path / "elsewhere"

    monkeypatch.delenv("DAGSTER_HOME")
    assert resolve_dagster_home(tmp_path) == tmp_path / "data" / "interim" / "dagster"


def test_a_running_dagster_prunes_rows_but_leaves_the_files_alone(instance_home: Path) -> None:
    """Unlinking a database the daemon holds open frees nothing and keeps nothing safe."""
    with DagsterInstance.local_temp(str(instance_home)) as instance:
        for marker in ("a", "b", "c"):
            _checkpoint(instance, "public/sample", marker)

    stray = instance_home / STRAY_INDEX_DB
    assert stray.exists(), "a runless event should have produced the empty-run-id database"

    report = prune_history(instance_home, dagster_running=True)

    assert report.runless_rows_deleted == 2
    assert stray.exists()
    assert not report.stray_index_removed
    assert any("file removals" in reason for reason in report.skipped)
    assert any("vacuum" in reason for reason in report.skipped)
    assert _markers(instance_home) == ["c"]


def test_a_stopped_dagster_removes_the_stray_index(instance_home: Path) -> None:
    with DagsterInstance.local_temp(str(instance_home)) as instance:
        _checkpoint(instance, "public/sample", "a")

    report = prune_history(instance_home, dagster_running=False)

    assert report.stray_index_removed
    assert not (instance_home / STRAY_INDEX_DB).exists()
    # The restore path still answers from the index that remains.
    assert _markers(instance_home) == ["a"]


def test_a_run_outside_the_queried_page_keeps_its_event_log(
    instance_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Orphan detection asks run storage per file, so paging cannot delete a live run."""
    with DagsterInstance.local_temp(str(instance_home)) as instance:
        _checkpoint(instance, "public/sample", "a")
        run = instance.create_run_for_job(_a_job, run_config={})
        run_id = run.run_id

    per_run = instance_home / INDEX_DB.parent / f"{run_id}.db"
    per_run.write_bytes(b"x" * 4096)

    # Stand in for a run storage larger than one page: the record listing returns
    # nothing, while the run itself is still very much there.
    monkeypatch.setattr(DagsterInstance, "get_run_records", lambda self, **kwargs: [])

    report = prune_history(instance_home, dagster_running=False)

    assert run_id not in report.orphan_run_dbs
    assert per_run.exists()


def test_the_ui_restore_survives_a_prune(instance_home: Path, tmp_path: Path) -> None:
    """The real checkpoint writer and restore path, with a prune between them."""
    sample_dir = tmp_path / "users" / "public" / "sampleA"
    sample_dir.mkdir(parents=True)
    parquet_path = str(sample_dir / "user_vcf_normalized.parquet")
    with DagsterInstance.local_temp(str(instance_home)) as instance:
        for score in (1.0, 2.0, 3.0):
            checkpoint_prs_results(
                instance,
                parquet_path,
                [{"pgs_id": "PGS000001", "score": score}],
                genome_build="GRCh38",
                ancestry="EUR",
                sample_type="wgs",
            )

    report = prune_history(instance_home, dagster_running=False)

    assert report.runless_rows_deleted == 2
    with DagsterInstance.from_ref(DagsterInstance.local_temp(str(instance_home)).get_ref()) as instance:
        restored = restore_prs_checkpoint(instance, _prs_partition_key(parquet_path))
    assert restored.status == "restored"
    assert restored.rows == [{"pgs_id": "PGS000001", "score": 3.0}]


def test_prune_does_not_set_dagster_home(instance_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A leaked DAGSTER_HOME would point every later instance in the process at this one."""
    monkeypatch.delenv("DAGSTER_HOME", raising=False)
    with DagsterInstance.local_temp(str(instance_home)) as instance:
        _checkpoint(instance, "public/sample", "a")

    prune_history(instance_home, dagster_running=False)

    assert "DAGSTER_HOME" not in os.environ
