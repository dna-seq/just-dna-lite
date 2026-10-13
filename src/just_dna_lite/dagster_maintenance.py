"""Bounded growth for the Dagster event log under ``data/interim/dagster``.

Two kinds of history accumulate there, and only one of them is reachable through
Dagster's own APIs.

Runs are the easy half: ``instance.delete_run`` drops a run's rows from
``history/runs/index.db`` and removes its per-run ``{run_id}.db``.  Those files are
small (a few hundred kilobytes each).

The half that actually fills a disk is runless asset events.  The web UI
checkpoints PRS results with ``instance.report_runless_asset_event``, which writes
rows carrying an empty ``run_id``: they belong to no run, so no amount of run
deletion ever touches them, and Dagster keeps every one forever even though only
the newest per partition is ever read back.  Before issue #35 each one carried the
whole results table, ~10 MB per event and 15.9 GB per database on the machine that
hit it; the rows now live in a file beside the sample, but the events still pile up.

``prune_runless_materializations`` is therefore a direct SQLite operation that
keeps the newest materialization per ``(asset_key, partition)`` and deletes the
rest.  Keeping the newest is what preserves the restore path.  It only runs against
a schema it recognises.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dagster import DagsterInstance, RunsFilter
from dagster._core.instance.ref import InstanceRef
from pydantic import BaseModel

# Dagster's SqliteEventLogStorage layout.  ``.db`` with an empty stem is not a
# Dagster file name: it is what a storage instance writes when it is handed an
# empty run id, and it mirrors the whole index.  Treat it as prunable junk.
HISTORY_DIR = Path("history")
RUNS_DIR = HISTORY_DIR / "runs"
INDEX_DB = RUNS_DIR / "index.db"
STRAY_INDEX_DB = RUNS_DIR / ".db"
RUNS_DB = HISTORY_DIR / "runs.db"

MATERIALIZATION_EVENT = "ASSET_MATERIALIZATION"

# VACUUM rebuilds the database beside the original, so it needs room for a second
# copy.  Ask for a margin on top before attempting one.
VACUUM_FREE_SPACE_MARGIN = 1.3
# Below this share of reclaimable pages a VACUUM costs more than it returns.
VACUUM_MIN_FREE_FRACTION = 0.1


class DatabaseSizes(BaseModel):
    """Bytes on disk for each part of the event log."""

    index_db: int = 0
    stray_index_db: int = 0
    runs_db: int = 0
    per_run_dbs: int = 0
    per_run_count: int = 0

    @property
    def total(self) -> int:
        return self.index_db + self.stray_index_db + self.runs_db + self.per_run_dbs


class PruneReport(BaseModel):
    """What a prune pass found and what it removed."""

    dagster_home: Path
    before: DatabaseSizes
    after: DatabaseSizes
    deleted_runs: list[str] = []
    orphan_run_dbs: list[str] = []
    runless_rows_deleted: int = 0
    runless_bytes_deleted: int = 0
    stray_index_removed: bool = False
    vacuumed: list[str] = []
    skipped: list[str] = []
    dry_run: bool = False

    @property
    def bytes_freed(self) -> int:
        return max(self.before.total - self.after.total, 0)


def resolve_dagster_home(root: Path) -> Path:
    """The instance directory the launchers use, honouring ``DAGSTER_HOME``."""
    configured = os.getenv("DAGSTER_HOME")
    if configured:
        home = Path(configured)
        return home if home.is_absolute() else (root / home).resolve()
    return (root / "data" / "interim" / "dagster").resolve()


def _file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def _per_run_databases(runs_dir: Path) -> Iterator[Path]:
    """The ``{run_id}.db`` files, excluding the shared index and the stray one.

    ``Path.glob`` matches dotfiles, so a bare ``.db`` comes back from ``*.db``
    too; counting it here as well as a stray would double its bytes and delete
    it as an orphaned run.
    """
    if not runs_dir.is_dir():
        return
    for path in sorted(runs_dir.glob("*.db")):
        if path.name in {INDEX_DB.name, STRAY_INDEX_DB.name}:
            continue
        yield path


def _unlink_database(path: Path) -> None:
    """Remove a SQLite database with its write-ahead log and shared-memory file."""
    for suffix in ("", "-shm", "-wal"):
        path.with_name(f"{path.name}{suffix}").unlink(missing_ok=True)


def measure(dagster_home: Path) -> DatabaseSizes:
    """Size every event-log file under ``dagster_home``."""
    runs_dir = dagster_home / RUNS_DIR
    per_run = list(_per_run_databases(runs_dir))
    return DatabaseSizes(
        index_db=_file_size(dagster_home / INDEX_DB),
        stray_index_db=_file_size(dagster_home / STRAY_INDEX_DB),
        runs_db=_file_size(dagster_home / RUNS_DB),
        per_run_dbs=sum(_file_size(p) for p in per_run),
        per_run_count=len(per_run),
    )


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    return row is not None


def prune_runless_materializations(db_path: Path, dry_run: bool = False) -> tuple[int, int]:
    """Keep the newest runless materialization per asset and partition.

    Returns ``(rows_deleted, bytes_freed_from_rows)``.  The byte figure is the
    summed length of the deleted event payloads, which is what the pages held; the
    file itself only shrinks once it is vacuumed.
    """
    if not db_path.exists():
        return (0, 0)

    connection = sqlite3.connect(db_path)
    if not _table_exists(connection, "event_logs"):
        connection.close()
        return (0, 0)

    columns = _columns(connection, "event_logs")
    if not {"id", "run_id", "event", "dagster_event_type", "asset_key"} <= columns:
        connection.close()
        return (0, 0)

    # Older schemas have no partition column; grouping by asset alone is then the
    # correct reading of "the newest one", because there is only one series.
    group_key = "asset_key, partition" if "partition" in columns else "asset_key"
    superseded = (
        "SELECT id FROM event_logs"
        " WHERE dagster_event_type = ?"
        "   AND (run_id IS NULL OR run_id = '')"
        "   AND asset_key IS NOT NULL"
        f"  AND id NOT IN (SELECT MAX(id) FROM event_logs"
        "                  WHERE dagster_event_type = ?"
        "                    AND (run_id IS NULL OR run_id = '')"
        "                    AND asset_key IS NOT NULL"
        f"                 GROUP BY {group_key})"
    )
    params = (MATERIALIZATION_EVENT, MATERIALIZATION_EVENT)

    measured = connection.execute(
        f"SELECT COUNT(*), COALESCE(SUM(LENGTH(event)), 0) FROM event_logs WHERE id IN ({superseded})",
        params,
    ).fetchone()
    rows, payload_bytes = int(measured[0]), int(measured[1])

    if rows and not dry_run:
        if _table_exists(connection, "asset_event_tags") and "event_id" in _columns(
            connection, "asset_event_tags"
        ):
            connection.execute(
                f"DELETE FROM asset_event_tags WHERE event_id IN ({superseded})", params
            )
        connection.execute(f"DELETE FROM event_logs WHERE id IN ({superseded})", params)
        connection.commit()

    connection.close()
    return (rows, payload_bytes)


def vacuum(db_path: Path) -> str:
    """Rebuild ``db_path`` if it has enough free pages and the disk has room.

    Returns an empty string when the vacuum ran, else the reason it did not.
    """
    if not db_path.exists():
        return "missing"

    connection = sqlite3.connect(db_path)
    page_size = connection.execute("PRAGMA page_size").fetchone()[0]
    page_count = connection.execute("PRAGMA page_count").fetchone()[0]
    freelist = connection.execute("PRAGMA freelist_count").fetchone()[0]

    if page_count and freelist / page_count < VACUUM_MIN_FREE_FRACTION:
        connection.close()
        return f"only {freelist}/{page_count} pages reclaimable"

    live_bytes = (page_count - freelist) * page_size
    free_bytes = shutil.disk_usage(db_path.parent).free
    if free_bytes < live_bytes * VACUUM_FREE_SPACE_MARGIN:
        connection.close()
        return f"needs {human_bytes(int(live_bytes * VACUUM_FREE_SPACE_MARGIN))} free, has {human_bytes(free_bytes)}"

    # A locked database is the expected failure here: someone started the stack
    # mid-prune.  Everything else is a real fault and must surface.
    try:
        connection.execute("VACUUM")
    except sqlite3.OperationalError as exc:
        connection.close()
        return str(exc)
    connection.close()
    return ""


def human_bytes(num_bytes: int) -> str:
    """``1536`` -> ``1.5 KB``."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TB"


def _prune_runs(
    instance: DagsterInstance,
    dagster_home: Path,
    max_age_days: int,
    dry_run: bool,
    dagster_running: bool,
    report: PruneReport,
) -> None:
    """Delete aged runs, then per-run databases and the stray index no run owns."""
    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
    for record in instance.get_run_records(filters=RunsFilter(), limit=10_000):
        run_id = record.dagster_run.run_id
        created = record.create_timestamp
        if created is None:
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        if created < cutoff:
            report.deleted_runs.append(run_id)

    if not dry_run:
        for run_id in report.deleted_runs:
            instance.delete_run(run_id)

    # Ask run storage about each file rather than diffing against a page of
    # records: a run past that page would otherwise read as orphaned and have
    # its event log unlinked while it is still live.
    for per_run in _per_run_databases(dagster_home / RUNS_DIR):
        if instance.get_run_by_id(per_run.stem) is not None:
            continue
        report.orphan_run_dbs.append(per_run.name)
        if not dry_run and not dagster_running:
            _unlink_database(per_run)

    stray = dagster_home / STRAY_INDEX_DB
    if stray.exists():
        report.stray_index_removed = True
        if not dry_run and not dagster_running:
            _unlink_database(stray)


def prune_history(
    dagster_home: Path,
    max_age_days: int = 30,
    prune_runless: bool = True,
    run_vacuum: bool = True,
    dry_run: bool = False,
    dagster_running: bool = False,
) -> PruneReport:
    """Delete aged runs, superseded runless materializations and orphan files.

    ``dagster_running`` narrows the pass rather than cancelling it. Deleting rows
    is a transaction SQLite arbitrates, so it is safe against a live daemon and
    is the part that reclaims the space. Unlinking a database the daemon holds
    open is not: the writer keeps its descriptor, so nothing is returned to the
    filesystem and the daemon writes on into an unlinked inode. The file
    removals and the vacuum are therefore deferred to a pass with the stack down,
    and the reason is reported rather than passed over in silence.
    """
    report = PruneReport(
        dagster_home=dagster_home,
        before=measure(dagster_home),
        after=measure(dagster_home),
        dry_run=dry_run,
    )

    # Opened from the directory, not via ``DAGSTER_HOME``: setting the variable here
    # would leak into the rest of the process (every later test, in a pytest run).
    with DagsterInstance.from_ref(InstanceRef.from_dir(str(dagster_home))) as instance:
        _prune_runs(instance, dagster_home, max_age_days, dry_run, dagster_running, report)

    if dagster_running and (report.orphan_run_dbs or report.stray_index_removed):
        report.stray_index_removed = False
        report.skipped.append(
            "file removals: Dagster holds these databases open; rerun with the stack stopped"
        )

    if prune_runless:
        # A live daemon writing an event can hold the write lock. That is the one
        # expected failure here; anything else is a fault and must surface.
        try:
            rows, payload = prune_runless_materializations(dagster_home / INDEX_DB, dry_run=dry_run)
        except sqlite3.OperationalError as exc:
            report.skipped.append(f"runless asset events: {exc}")
        else:
            report.runless_rows_deleted = rows
            report.runless_bytes_deleted = payload

    if run_vacuum and not dry_run and dagster_running:
        report.skipped.append("vacuum index.db: Dagster is running")
    elif run_vacuum and not dry_run:
        reason = vacuum(dagster_home / INDEX_DB)
        if reason:
            report.skipped.append(f"vacuum {INDEX_DB.name}: {reason}")
        else:
            report.vacuumed.append(INDEX_DB.name)

    report.after = measure(dagster_home)
    return report
