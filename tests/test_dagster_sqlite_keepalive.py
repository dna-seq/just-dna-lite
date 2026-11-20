"""The launcher keeps Dagster's shared SQLite files open so their WAL files are not deleted between queries.

Dagster connects per query; when the last connection to a WAL database closes, SQLite deletes
`-wal`/`-shm`, and the next connection rebuilds them under an exclusive lock, which every other
process on the stack met as "database is locked". See `just_dna_lite.dagster_sqlite`.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from dagster import DagsterInstance

from just_dna_lite import dagster_sqlite
from just_dna_lite.dagster_sqlite import SHARED_DATABASES, DagsterDatabaseKeepalive, open_idle_connection

DB = "history/runs.db"


def _wal_files(db: Path) -> tuple[bool, bool]:
    return Path(f"{db}-wal").exists(), Path(f"{db}-shm").exists()


def _write_once(db: Path, value: str) -> None:
    """One short writer connection, as Dagster's NullPool opens per query."""
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO t VALUES (?)", (value,))
    conn.commit()
    conn.close()


@pytest.fixture
def home(tmp_path: Path) -> Iterator[Path]:
    db = tmp_path / DB
    db.parent.mkdir(parents=True)
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE t (v TEXT)")
    conn.commit()
    conn.close()
    yield tmp_path


def test_without_a_held_connection_each_close_deletes_the_wal_files(home: Path) -> None:
    db = home / DB
    _write_once(db, "x")
    assert _wal_files(db) == (False, False)


def test_a_held_connection_keeps_the_wal_files_across_writers(home: Path) -> None:
    db = home / DB
    with DagsterDatabaseKeepalive(home, databases=(DB,)) as keepalive:
        assert keepalive.held == [db]
        for n in range(5):
            _write_once(db, f"ünïcode {n}")
            assert _wal_files(db) == (True, True)
    _write_once(db, "after close")
    assert _wal_files(db) == (False, False)  # released: the last close cleans up again


def test_the_held_connection_holds_no_transaction(home: Path) -> None:
    db = home / DB
    with DagsterDatabaseKeepalive(home, databases=(DB,)):
        _write_once(db, "x")
        writer = sqlite3.connect(db, timeout=1)
        writer.execute("BEGIN IMMEDIATE")  # a write lock is available at once
        writer.execute("INSERT INTO t VALUES ('y')")
        writer.commit()
        busy, _log, _done = writer.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        writer.close()
        assert busy == 0  # a reader holding a snapshot would block the truncating checkpoint
        assert Path(f"{db}-wal").stat().st_size == 0


def test_read_only_never_creates_a_database(tmp_path: Path) -> None:
    with DagsterDatabaseKeepalive(tmp_path) as keepalive:
        assert keepalive.held == []
    assert not any(tmp_path.rglob("*.db*"))
    assert open_idle_connection(tmp_path / "missing.db") is None


def test_a_database_created_after_start_is_picked_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dagster_sqlite, "RETRY_SECONDS", 0.05)
    db = tmp_path / DB
    with DagsterDatabaseKeepalive(tmp_path, databases=(DB,)) as keepalive:
        assert keepalive.held == []
        db.parent.mkdir(parents=True)
        conn = sqlite3.connect(db)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE t (v TEXT)")
        conn.commit()
        conn.close()
        deadline = time.monotonic() + 5
        while keepalive.held != [db] and time.monotonic() < deadline:
            time.sleep(0.05)
        assert keepalive.held == [db]
        _write_once(db, "x")
        assert _wal_files(db) == (True, True)


def test_the_paths_are_where_dagster_puts_its_shared_databases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAGSTER_HOME", str(tmp_path))
    instance = DagsterInstance.get()
    instance.get_run_records(limit=1)
    instance.get_daemon_heartbeats()
    with DagsterDatabaseKeepalive(tmp_path) as keepalive:
        assert keepalive.held == sorted(tmp_path / name for name in SHARED_DATABASES)
        assert instance.get_run_records(limit=1) == []
