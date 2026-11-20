"""Keep Dagster's shared SQLite databases open while the stack runs, so their WAL files stay put.

Dagster opens a fresh connection per query (`NullPool`). In WAL mode, whenever the last connection
to a database closes, SQLite checkpoints and deletes `-wal` and `-shm`, and the next connection
must rebuild them while holding an exclusive lock. With the daemon's six threads, the webserver,
the web UI, its compute workers and the MCP server all on `history/runs.db`, that churn never
stops, and every query that lands on a rebuild fails with "database is locked". The daemons log
each one with a full stack. Dagster gives its event-log connections a 30 s busy timeout, but its run
and schedule storage (daemon heartbeats among them) connect with SQLite's 5 s default.

Measured 2026-11-20 on the stack (DAGSTER_HOME on the NTFS `/data` disk): over 10 s, `-shm` was
missing in 2 of 36 samples and 5 of 36 read-only queries hit the lock; over 20 s with one idle
connection held open, `-shm` stayed in 199 of 199 samples and 0 of 199 queries hit the lock.

The launcher holds one read-only connection per database. It holds no transaction, so it never
blocks a writer or a checkpoint; it only keeps SQLite from deleting the WAL files under everyone.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

# Relative to DAGSTER_HOME: run storage plus the event-log index, and schedule storage.
SHARED_DATABASES = ("history/runs.db", "schedules/schedules.db")
# A fresh instance has no databases until Dagster creates them; look again this often.
RETRY_SECONDS = 2.0


def open_idle_connection(db_path: Path) -> sqlite3.Connection | None:
    """A read-only connection that has read once (attaching the WAL index) and holds no transaction.

    None when the database does not exist yet or cannot be opened; read-only mode never creates it.
    """
    if not db_path.is_file():
        return None
    try:
        conn = sqlite3.connect(
            f"{db_path.resolve().as_uri()}?mode=ro",
            uri=True,
            isolation_level=None,
            check_same_thread=False,
            timeout=30,
        )
        conn.execute("SELECT count(*) FROM sqlite_master").fetchall()
    except sqlite3.Error:
        return None
    return conn


class DagsterDatabaseKeepalive:
    """Hold Dagster's shared databases open until `close()`; databases created later are picked up."""

    def __init__(self, dagster_home: Path, databases: tuple[str, ...] = SHARED_DATABASES) -> None:
        self._paths = [Path(dagster_home) / name for name in databases]
        self._connections: dict[Path, sqlite3.Connection] = {}
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._open_missing()
        self._thread: threading.Thread | None = None
        if len(self._connections) < len(self._paths):
            self._thread = threading.Thread(target=self._retry, name="dagster-sqlite-keepalive", daemon=True)
            self._thread.start()

    @property
    def held(self) -> list[Path]:
        with self._lock:
            return sorted(self._connections)

    def _open_missing(self) -> None:
        for path in self._paths:
            with self._lock:
                if path in self._connections or self._stop.is_set():
                    continue
            conn = open_idle_connection(path)
            if conn is None:
                continue
            with self._lock:
                if self._stop.is_set():
                    conn.close()
                    return
                self._connections[path] = conn

    def _retry(self) -> None:
        while not self._stop.wait(RETRY_SECONDS):
            self._open_missing()
            with self._lock:
                if len(self._connections) == len(self._paths):
                    return

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=RETRY_SECONDS * 2)
        with self._lock:
            connections, self._connections = list(self._connections.values()), {}
        for conn in connections:
            conn.close()

    def __enter__(self) -> DagsterDatabaseKeepalive:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
