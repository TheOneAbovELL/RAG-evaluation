import contextlib
import os
import sqlite3
import subprocess
import sys
from datetime import timedelta

import pytest
from conftest import REAL_DATASET, REAL_PDF

from rag_workbench.cli import main
from rag_workbench.config import PROJECT_ROOT
from rag_workbench.maintenance import backup_store, restore_store
from rag_workbench.models import RunConfig, RunRecord, utcnow
from rag_workbench.runner import EvaluationRunner
from rag_workbench.storage import SCHEMA_VERSION, RunStore, StorageError


def make_run(settings, store, name):
    config = RunConfig(name=name, dataset_path=str(REAL_DATASET), document_path=str(REAL_PDF),
                       metrics=["token_f1"], limit=3)
    return EvaluationRunner(settings, store).run(config)


# ------------------------------------------------------------------ restore
def test_restore_round_trip_with_a_safety_copy(settings, store, tmp_path):
    first = make_run(settings, store, "kept")
    backup = backup_store(settings.db_path, tmp_path / "backups")
    second = make_run(settings, store, "added-after-backup")
    assert {r.id for r in store.list_runs()} == {first.id, second.id}

    restored, safety = restore_store(backup, settings.db_path, tmp_path / "safety")
    assert restored == settings.db_path and safety is not None and safety.name.startswith("pre-restore-")
    fresh = RunStore(settings.db_path)
    assert [r.id for r in fresh.list_runs()] == [first.id]  # the run made after the backup is gone...
    assert len(fresh.get_case_results(first.id)) == 3
    # ...but the safety copy can bring it back: a restore is itself reversible.
    restore_store(safety, settings.db_path, tmp_path / "safety2")
    assert {r.id for r in RunStore(settings.db_path).list_runs()} == {first.id, second.id}


def test_restore_refuses_bad_backups_and_changes_nothing(settings, store, tmp_path):
    make_run(settings, store, "keep")
    before = settings.db_path.read_bytes()
    with pytest.raises(StorageError, match="not found"):
        restore_store(tmp_path / "missing.db", settings.db_path, tmp_path / "s")
    garbage = tmp_path / "garbage.db"
    garbage.write_bytes(b"this is not sqlite" * 50)
    with pytest.raises(StorageError, match=r"not a readable run store|integrity"):
        restore_store(garbage, settings.db_path, tmp_path / "s")
    other = tmp_path / "other.db"
    with contextlib.closing(sqlite3.connect(other)) as conn, conn:
        conn.execute("CREATE TABLE unrelated (x)")
    with pytest.raises(StorageError, match="not a run store"):
        restore_store(other, settings.db_path, tmp_path / "s")
    newer = tmp_path / "newer.db"
    backup = backup_store(settings.db_path, tmp_path / "b")
    newer.write_bytes(backup.read_bytes())
    with contextlib.closing(sqlite3.connect(newer)) as conn, conn:
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 5}")
    with pytest.raises(StorageError, match="newer version"):
        restore_store(newer, settings.db_path, tmp_path / "s")
    assert settings.db_path.read_bytes() == before  # every refusal left the live store untouched


def test_restore_refuses_while_a_run_is_active_unless_forced(settings, store, tmp_path):
    make_run(settings, store, "done")
    backup = backup_store(settings.db_path, tmp_path / "b")
    store.create_run(RunRecord(id="live", name="live", status="running", created_at=utcnow(), config={}, n_cases=1))
    with pytest.raises(StorageError, match="still active"):
        restore_store(backup, settings.db_path, tmp_path / "s")
    restore_store(backup, settings.db_path, tmp_path / "s", force=True)
    assert [r.name for r in RunStore(settings.db_path).list_runs()] == ["done"]


def test_a_run_that_stopped_heartbeating_does_not_block_a_restore(settings, store, tmp_path):
    backup = backup_store(settings.db_path, tmp_path / "b")
    old = utcnow() - timedelta(hours=3)
    store.create_run(RunRecord(id="dead", name="dead", status="running", created_at=old, config={}, n_cases=1))
    with contextlib.closing(sqlite3.connect(settings.db_path)) as conn, conn:
        conn.execute("UPDATE runs SET heartbeat_at = ? WHERE id = 'dead'", (old.isoformat(),))
    restore_store(backup, settings.db_path, tmp_path / "s")  # not refused: the run is long dead


def test_restore_migrates_an_older_schema(settings, tmp_path):
    old = tmp_path / "v1.db"
    with contextlib.closing(sqlite3.connect(old)) as conn, conn:
        conn.executescript("""
            CREATE TABLE runs (id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
                finished_at TEXT, config_json TEXT NOT NULL, dataset_sha256 TEXT, document_sha256 TEXT,
                n_cases INTEGER NOT NULL DEFAULT 0, summary_json TEXT, environment_json TEXT NOT NULL DEFAULT '{}',
                notes TEXT);
            CREATE TABLE case_results (run_id TEXT NOT NULL, case_id TEXT NOT NULL, position INTEGER NOT NULL,
                status TEXT NOT NULL, data_json TEXT NOT NULL, PRIMARY KEY (run_id, case_id));
            INSERT INTO runs (id, name, status, created_at, config_json) VALUES
                ('old', 'old', 'completed', '2000-01-01T00:00:00+00:00', '{}');
            PRAGMA user_version = 1;""")
    restore_store(old, settings.db_path, tmp_path / "s")
    run = RunStore(settings.db_path).get_run("old")
    assert run is not None and run.tags == []


def test_cli_restore_requires_confirmation(settings, store, tmp_path, capsys):
    make_run(settings, store, "one")
    assert main(["backup", "--out-dir", str(tmp_path / "bk")]) == 0
    backup = next((tmp_path / "bk").glob("runs-*.db"))
    capsys.readouterr()
    assert main(["restore", str(backup)]) == 1
    assert "--yes" in capsys.readouterr().err
    assert main(["restore", str(backup), "--yes"]) == 0
    out = capsys.readouterr().out
    assert "Restored" in out and "Previous store saved as" in out
    assert main(["restore", str(tmp_path / "nope.db"), "--yes"]) == 1


# ------------------------------------------------------------------ concurrency
def test_several_processes_can_use_one_store_at_the_same_time(tmp_path):
    """Four CLI processes run evaluations against the same data directory while a fifth keeps reading it."""
    data = tmp_path / "shared"
    env = {**os.environ, "RAGWB_DATA_DIR": str(data), "OPENAI_API_KEY": "", "DEEPEVAL_TELEMETRY_OPT_OUT": "1"}
    cmd = [sys.executable, "-m", "rag_workbench"]
    workers = [subprocess.Popen([*cmd, "run", "--name", f"p{i}", "--limit", "8", "--quiet"], env=env, cwd=PROJECT_ROOT,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(4)]
    reader_errors = []
    while any(w.poll() is None for w in workers):
        proc = subprocess.run([*cmd, "list"], env=env, cwd=PROJECT_ROOT, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            reader_errors.append(proc.stderr[-300:])
    outputs = [(w.wait(), *w.communicate()) for w in workers]
    assert all(code == 0 for code, _, _ in outputs), [o[2][-400:] for o in outputs]
    assert not reader_errors, reader_errors[:2]
    store = RunStore(data / "runs.db")
    runs = store.list_runs()
    assert sorted(r.name for r in runs) == ["p0", "p1", "p2", "p3"]
    assert all(r.status == "completed" and store.count_case_results(r.id) == 8 for r in runs)
    with contextlib.closing(sqlite3.connect(data / "runs.db")) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_restore_repairs_an_unreadable_store_and_keeps_a_raw_copy(settings, store, tmp_path, capsys):
    """The case the runbook sends operators to: the live runs.db is damaged, so no command that opens it can work."""
    make_run(settings, store, "precious")
    backup = backup_store(settings.db_path, tmp_path / "bk")
    damaged = b"not a database at all " * 100
    settings.db_path.write_bytes(damaged)
    assert main(["list"]) == 1  # every normal command fails on the damaged store
    capsys.readouterr()
    assert main(["restore", str(backup), "--yes"]) == 0
    out = capsys.readouterr().out
    assert "Restored" in out and "pre-restore-damaged-" in out
    kept = next(settings.backups_dir.glob("pre-restore-damaged-*.db"))
    assert kept.read_bytes() == damaged  # the damaged file was preserved, not lost
    assert [r.name for r in RunStore(settings.db_path).list_runs()] == ["precious"]


def test_two_backups_in_the_same_second_do_not_collide(settings, store, tmp_path):
    make_run(settings, store, "x")
    paths = {backup_store(settings.db_path, tmp_path / "bk") for _ in range(5)}
    assert len(paths) == 5


def test_restore_reports_a_store_held_open_by_another_process(settings, store, tmp_path, monkeypatch):
    make_run(settings, store, "x")
    backup = backup_store(settings.db_path, tmp_path / "b")
    before = settings.db_path.read_bytes()

    def locked(src, dst):
        raise PermissionError(13, "The process cannot access the file")

    monkeypatch.setattr("rag_workbench.maintenance.os.replace", locked)
    with pytest.raises(StorageError, match="in use by another process"):
        restore_store(backup, settings.db_path, tmp_path / "s", force=True)
    assert settings.db_path.read_bytes() == before and not settings.db_path.with_suffix(".restoring").exists()


def test_backup_names_stay_unique_even_when_the_clock_does_not_move(settings, store, tmp_path, monkeypatch):
    """Found by the final verification run: a coarse clock gave two quick backups the same timestamp."""
    from datetime import datetime

    frozen = datetime(2026, 1, 2, 3, 4, 5, 678901)
    monkeypatch.setattr("rag_workbench.maintenance.utcnow", lambda: frozen)
    make_run(settings, store, "x")
    paths = [backup_store(settings.db_path, tmp_path / "bk") for _ in range(4)]
    assert len({p.name for p in paths}) == 4 and all(p.is_file() for p in paths)
    assert paths[0].name == "runs-20260102-030405-678901.db" and paths[1].name.endswith("-2.db")
