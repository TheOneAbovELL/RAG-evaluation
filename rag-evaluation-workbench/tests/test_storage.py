import sqlite3

import pytest

from rag_workbench.models import CaseResult, MetricResult, RunRecord, utcnow
from rag_workbench.storage import RunStore, StorageError


def record(run_id="r1", status="running"):
    return RunRecord(id=run_id, name="Run ü", status=status, created_at=utcnow(), config={"k": 3, "note": "蜂蜜"},
                     n_cases=2, environment={"python": "3.12"})


def result(case_id="c1", position=1):
    return CaseResult(case_id=case_id, position=position, question="Où ?", expected_answer="Là", status="ok",
                      answer="Là-bas", metrics={"m": MetricResult(name="m", status="ok", score=0.5, threshold=0.5,
                                                                  passed=True)})


def test_round_trip_preserves_unicode_and_order(store):
    store.create_run(record())
    store.add_case_result("r1", result("c2", 2))
    store.add_case_result("r1", result("c1", 1))
    run = store.get_run("r1")
    assert run.name == "Run ü" and run.config["note"] == "蜂蜜"
    assert [c.case_id for c in store.get_case_results("r1")] == ["c1", "c2"]
    assert store.get_case_results("r1")[0].metrics["m"].score == 0.5
    assert store.count_case_results("r1") == 2


def test_duplicates_and_missing_runs_are_errors(store):
    store.create_run(record())
    with pytest.raises(StorageError, match="already exists"):
        store.create_run(record())
    store.add_case_result("r1", result())
    with pytest.raises(StorageError, match="already recorded"):
        store.add_case_result("r1", result())
    with pytest.raises(StorageError):
        store.add_case_result("missing-run", result())
    with pytest.raises(StorageError, match="not found"):
        store.finish_run("missing-run", "completed", None)


def test_finish_list_delete_cascade(store):
    store.create_run(record("a"))
    store.create_run(record("b"))
    store.add_case_result("a", result())
    store.finish_run("a", "completed", None)
    assert store.get_run("a").status == "completed" and store.get_run("a").finished_at is not None
    assert {r.id for r in store.list_runs()} == {"a", "b"}
    assert store.delete_run("a") is True
    assert store.delete_run("a") is False
    with sqlite3.connect(store.path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM case_results WHERE run_id = 'a'").fetchone()[0] == 0


def test_recover_interrupted_only_touches_stale_runs(store):
    store.create_run(record("dead"))
    store.create_run(record("live"))
    store.create_run(record("done", status="completed"))
    with sqlite3.connect(store.path) as conn:  # simulate a process that died an hour ago
        conn.execute("UPDATE runs SET heartbeat_at = '2000-01-01T00:00:00+00:00' WHERE id = 'dead'")
    assert store.recover_interrupted() == 1
    assert store.get_run("dead").status == "interrupted"
    assert store.get_run("live").status == "running"  # fresh heartbeat: another process may be running it
    assert store.get_run("done").status == "completed"


def test_case_commits_refresh_the_heartbeat(store):
    store.create_run(record("r"))
    with sqlite3.connect(store.path) as conn:
        conn.execute("UPDATE runs SET heartbeat_at = '2000-01-01T00:00:00+00:00'")
    store.add_case_result("r", result())
    assert store.recover_interrupted() == 0


def test_schema_v1_store_is_migrated(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:  # the version-1 layout: no heartbeat column
        conn.executescript("""
            CREATE TABLE runs (id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
                finished_at TEXT, config_json TEXT NOT NULL, dataset_sha256 TEXT, document_sha256 TEXT,
                n_cases INTEGER NOT NULL DEFAULT 0, summary_json TEXT, environment_json TEXT NOT NULL DEFAULT '{}',
                notes TEXT);
            INSERT INTO runs (id, name, status, created_at, config_json) VALUES
                ('old', 'old', 'running', '2000-01-01T00:00:00+00:00', '{}');
            PRAGMA user_version = 1;""")
    store = RunStore(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 3
        assert {r[1] for r in conn.execute("PRAGMA table_info(runs)")} >= {"heartbeat_at", "tags_json"}
    assert store.get_run("old").tags == []
    assert store.recover_interrupted() == 1  # no heartbeat: falls back to created_at
    store.create_run(record("new"))


def test_sqlite_errors_become_storage_errors(store):
    with sqlite3.connect(store.path) as conn:
        conn.execute("DROP TABLE case_results")
    with pytest.raises(StorageError, match="Run store error"):
        store.get_case_results("anything")


def test_newer_schema_is_refused(tmp_path):
    path = tmp_path / "runs.db"
    RunStore(path)
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA user_version = 99")
    with pytest.raises(StorageError, match="newer version"):
        RunStore(path)


def test_unwritable_location_reports_storage_error(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    with pytest.raises((StorageError, OSError)):
        RunStore(blocker / "runs.db")  # parent is a file, not a directory
