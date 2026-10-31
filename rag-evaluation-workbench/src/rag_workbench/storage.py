"""SQLite persistence for runs and per-case results.

Design notes
------------
* One short-lived connection per operation: safe to call from Streamlit reruns and worker threads.
* Each case result is committed as soon as it is produced, so an interrupted run keeps its progress.
* Every committed case refreshes the run's ``heartbeat_at``. Runs still ``running`` whose heartbeat is older
  than :data:`STALE_AFTER_S` are marked ``interrupted`` by :meth:`RunStore.recover_interrupted` (called at
  start-up). A run that is genuinely executing in another process keeps a fresh heartbeat and is left alone.
* ``sqlite3`` errors are translated to :class:`StorageError` in one place (:meth:`RunStore._connect`).
* Rows store pydantic models as JSON; indexed columns duplicate the fields used for filtering.
* Schema version is tracked in ``PRAGMA user_version`` for future migrations.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from .models import CaseResult, RunRecord, RunStatus, RunSummary, utcnow

SCHEMA_VERSION = 3
# A running run with no committed case for this long is considered dead. Generous on purpose: one slow case can
# take several timeouts plus back-off (4 attempts x 60 s + delays is about 5 minutes with default settings).
STALE_AFTER_S = 15 * 60

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    status          TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    finished_at     TEXT,
    config_json     TEXT NOT NULL,
    dataset_sha256  TEXT,
    document_sha256 TEXT,
    n_cases         INTEGER NOT NULL DEFAULT 0,
    summary_json    TEXT,
    environment_json TEXT NOT NULL DEFAULT '{}',
    notes           TEXT,
    heartbeat_at    TEXT,
    tags_json       TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS case_results (
    run_id    TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    case_id   TEXT NOT NULL,
    position  INTEGER NOT NULL,
    status    TEXT NOT NULL,
    data_json TEXT NOT NULL,
    PRIMARY KEY (run_id, case_id)
);
CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at);
"""


class StorageError(RuntimeError):
    """Raised when the run store cannot be read or written."""


class RunStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as conn:
                conn.executescript(_SCHEMA)
                version = conn.execute("PRAGMA user_version").fetchone()[0]
                if version > SCHEMA_VERSION:
                    raise StorageError(f"{self.path} was created by a newer version (schema {version})")
                # Migrations add whatever a store created by an older version lacks (v1: heartbeat, v2: tags).
                columns = {row["name"] for row in conn.execute("PRAGMA table_info(runs)")}
                if "heartbeat_at" not in columns:
                    conn.execute("ALTER TABLE runs ADD COLUMN heartbeat_at TEXT")
                if "tags_json" not in columns:
                    conn.execute("ALTER TABLE runs ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'")
                if version < SCHEMA_VERSION:
                    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        except (sqlite3.Error, OSError) as exc:
            raise StorageError(f"Cannot open run store {self.path}: {exc}") from exc

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:  # commits on success, rolls back on exception
                yield conn
        except sqlite3.IntegrityError:
            raise  # callers translate constraint violations into specific messages
        except sqlite3.Error as exc:
            raise StorageError(f"Run store error ({self.path.name}): {exc}") from exc
        finally:
            conn.close()

    # ----------------------------------------------------------------- writes
    def create_run(self, record: RunRecord) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO runs (id, name, status, created_at, finished_at, config_json, dataset_sha256,"
                    " document_sha256, n_cases, summary_json, environment_json, notes, heartbeat_at, tags_json)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (record.id, record.name, record.status, record.created_at.isoformat(),
                     record.finished_at.isoformat() if record.finished_at else None,
                     json.dumps(record.config, ensure_ascii=False), record.dataset_sha256, record.document_sha256,
                     record.n_cases, record.summary.model_dump_json() if record.summary else None,
                     json.dumps(record.environment, ensure_ascii=False), record.notes, utcnow().isoformat(),
                     json.dumps(record.tags, ensure_ascii=False)))
        except sqlite3.IntegrityError as exc:
            raise StorageError(f"A run with id {record.id!r} already exists") from exc

    def add_case_result(self, run_id: str, result: CaseResult) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO case_results (run_id, case_id, position, status, data_json) VALUES (?, ?, ?, ?, ?)",
                    (run_id, result.case_id, result.position, result.status, result.model_dump_json()))
                conn.execute("UPDATE runs SET heartbeat_at = ? WHERE id = ?", (utcnow().isoformat(), run_id))
        except sqlite3.IntegrityError as exc:
            raise StorageError(f"Case {result.case_id!r} already recorded for run {run_id!r} (or run missing)") from exc

    def finish_run(self, run_id: str, status: RunStatus, summary: RunSummary | None,
                   finished_at: datetime | None = None) -> None:
        with self._connect() as conn:
            updated = conn.execute(
                "UPDATE runs SET status = ?, summary_json = ?, finished_at = ? WHERE id = ?",
                (status, summary.model_dump_json() if summary else None,
                 (finished_at or utcnow()).isoformat(), run_id)).rowcount
        if not updated:
            raise StorageError(f"Run {run_id!r} not found")

    def set_tags(self, run_id: str, tags: list[str]) -> None:
        with self._connect() as conn:
            updated = conn.execute("UPDATE runs SET tags_json = ? WHERE id = ?",
                                   (json.dumps(tags, ensure_ascii=False), run_id)).rowcount
        if not updated:
            raise StorageError(f"Run {run_id!r} not found")

    def set_notes(self, run_id: str, notes: str | None) -> None:
        with self._connect() as conn:
            updated = conn.execute("UPDATE runs SET notes = ? WHERE id = ?", (notes, run_id)).rowcount
        if not updated:
            raise StorageError(f"Run {run_id!r} not found")

    def delete_run(self, run_id: str) -> bool:
        with self._connect() as conn:
            return conn.execute("DELETE FROM runs WHERE id = ?", (run_id,)).rowcount > 0

    def recover_interrupted(self, stale_after_s: float = STALE_AFTER_S) -> int:
        """Mark ``running`` runs with no heartbeat for ``stale_after_s`` seconds as ``interrupted``.

        Returns the number of runs changed. Runs another process is still executing are not touched; if a run
        is wrongly marked (no case finished within the window), its own ``finish_run`` still sets the final status.
        """
        now = utcnow()
        cutoff = (now - timedelta(seconds=stale_after_s)).isoformat()
        with self._connect() as conn:
            return conn.execute(
                "UPDATE runs SET status = 'interrupted', finished_at = ? "
                "WHERE status = 'running' AND COALESCE(heartbeat_at, created_at) < ?",
                (now.isoformat(), cutoff)).rowcount

    # ------------------------------------------------------------------ reads
    def heartbeat(self, run_id: str) -> datetime | None:
        """When a case of this run was last committed (or the run was created), or ``None`` if unknown."""
        with self._connect() as conn:
            row = conn.execute("SELECT heartbeat_at FROM runs WHERE id = ?", (run_id,)).fetchone()
        return datetime.fromisoformat(row["heartbeat_at"]) if row and row["heartbeat_at"] else None

    def get_run(self, run_id: str) -> RunRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return _row_to_run(row) if row else None

    def list_runs(self) -> list[RunRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC, id").fetchall()
        return [_row_to_run(r) for r in rows]

    def get_case_results(self, run_id: str) -> list[CaseResult]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data_json FROM case_results WHERE run_id = ? ORDER BY position",
                                (run_id,)).fetchall()
        return [CaseResult.model_validate_json(r["data_json"]) for r in rows]

    def count_case_results(self, run_id: str) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM case_results WHERE run_id = ?", (run_id,)).fetchone()[0]


def _row_to_run(row: sqlite3.Row) -> RunRecord:
    return RunRecord(
        id=row["id"], name=row["name"], status=row["status"], created_at=datetime.fromisoformat(row["created_at"]),
        finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
        config=json.loads(row["config_json"]), dataset_sha256=row["dataset_sha256"],
        document_sha256=row["document_sha256"], n_cases=row["n_cases"],
        summary=RunSummary.model_validate_json(row["summary_json"]) if row["summary_json"] else None,
        environment=json.loads(row["environment_json"] or "{}"), notes=row["notes"],
        tags=json.loads(row["tags_json"] or "[]"),
    )
