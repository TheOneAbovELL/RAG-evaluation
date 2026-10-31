import json
from datetime import timedelta

import pytest
from conftest import REAL_DATASET, REAL_PDF

from rag_workbench.cli import main
from rag_workbench.config import load_settings
from rag_workbench.maintenance import backup_store, rerun_config, run_doctor, select_prunable
from rag_workbench.models import RunConfig, RunRecord, utcnow
from rag_workbench.runner import EvaluationRunner
from rag_workbench.services import open_context
from rag_workbench.storage import RunStore, StorageError


def by_name(checks):
    return {c.name: c for c in checks}


def record(run_id, *, age_days=0.0, status="completed"):
    return RunRecord(id=run_id, name=run_id, status=status, created_at=utcnow() - timedelta(days=age_days),
                     config={}, n_cases=0)


# ------------------------------------------------------------------ doctor
def test_doctor_passes_on_a_healthy_installation(settings, store):
    checks = by_name(run_doctor(settings))
    assert {c.status for c in checks.values()} == {"ok"}
    assert "schema v3" in checks["run store"].detail and "integrity ok" in checks["run store"].detail
    assert "honeybees" in checks["default data"].detail


def test_doctor_reports_an_unwritable_data_directory(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    checks = by_name(run_doctor(load_settings({"RAGWB_DATA_DIR": str(blocker / "data")}, dotenv=False)))
    assert checks["data directory"].status == "fail"


def test_doctor_detects_a_corrupt_store(settings, store):
    settings.db_path.write_bytes(b"this is not a sqlite database" * 100)
    assert by_name(run_doctor(settings))["run store"].status == "fail"


def test_doctor_warns_about_abandoned_runs(settings, store):
    store.create_run(record("old", age_days=2, status="running"))
    check = by_name(run_doctor(settings))["run store"]
    assert check.status == "warn" and "abandoned" in check.detail


@pytest.mark.parametrize("address,password,expected", [
    ('"localhost"', None, "ok"), ('"127.0.0.1"', None, "ok"),
    ('"0.0.0.0"', None, "fail"), ('"0.0.0.0"', "hunter2-hunter2", "warn"),
])
def test_doctor_checks_network_exposure(tmp_path, address, password, expected):
    config = tmp_path / "config.toml"
    config.write_text(f"[server]\naddress = {address}\n", encoding="utf-8")
    env = {"RAGWB_DATA_DIR": str(tmp_path / "d")} | ({"RAGWB_APP_PASSWORD": password} if password else {})
    check = by_name(run_doctor(load_settings(env, dotenv=False), config_file=config))["network exposure"]
    assert check.status == expected


def test_doctor_fails_when_no_address_is_set_and_there_is_no_password(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("[server]\nheadless = true\n", encoding="utf-8")
    check = by_name(run_doctor(load_settings({"RAGWB_DATA_DIR": str(tmp_path / "d")}, dotenv=False),
                               config_file=config))["network exposure"]
    assert check.status == "fail" and "all interfaces" in check.detail


def test_the_projects_own_streamlit_config_is_localhost_only(settings):
    assert by_name(run_doctor(settings))["network exposure"].status == "ok"


def test_doctor_never_prints_secrets(settings):
    keyed = load_settings({"OPENAI_API_KEY": "sk-not-a-real-key-for-tests-123456", "RAGWB_APP_PASSWORD": "pw-secret-value",
                           "RAGWB_DATA_DIR": str(settings.data_dir)}, dotenv=False)
    text = " ".join(f"{c.name} {c.detail}" for c in run_doctor(keyed))
    assert "sk-not-a-real" not in text and "pw-secret-value" not in text and "configured" in text


# ------------------------------------------------------------------ backup
def test_backup_is_a_consistent_verified_copy(settings, store, offline_config, tmp_path):
    run = EvaluationRunner(settings, store).run(offline_config())
    target = backup_store(settings.db_path, tmp_path / "backups")
    assert target.parent == tmp_path / "backups" and target.name.startswith("runs-")
    copy = RunStore(target)
    assert [r.id for r in copy.list_runs()] == [run.id]
    assert copy.get_case_results(run.id) == store.get_case_results(run.id)


def test_backup_without_a_store_and_with_a_corrupt_store_fails_cleanly(tmp_path):
    with pytest.raises(StorageError, match="No run store"):
        backup_store(tmp_path / "missing.db", tmp_path / "b")
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"garbage" * 200)
    with pytest.raises(StorageError):
        backup_store(bad, tmp_path / "b")
    assert not list((tmp_path / "b").glob("*.db"))  # no half-written backup left behind


# ------------------------------------------------------------------ prune
def test_prune_policies():
    runs = [record("new", age_days=1), record("mid", age_days=10), record("old", age_days=40),
            record("older", age_days=90)]
    assert [r.id for r in select_prunable(runs, keep_last=2)] == ["old", "older"]
    assert [r.id for r in select_prunable(runs, older_than_days=30)] == ["old", "older"]
    assert [r.id for r in select_prunable(runs, keep_last=3, older_than_days=30)] == ["older"]
    assert select_prunable(runs, keep_last=10) == []
    with pytest.raises(ValueError, match="refusing"):
        select_prunable(runs)


def test_prune_never_selects_a_run_that_may_still_be_executing():
    runs = [record("live", age_days=0.001, status="running"), record("dead", age_days=3, status="running"),
            record("done", age_days=60)]
    assert {r.id for r in select_prunable(runs, older_than_days=0)} == {"dead", "done"}


# ------------------------------------------------------------------ rerun
def test_rerun_reproduces_an_offline_run_exactly(settings, store):
    runner = EvaluationRunner(settings, store)
    original = runner.run(RunConfig(name="orig", dataset_path=str(REAL_DATASET), document_path=str(REAL_PDF), k=2,
                                    metrics=["token_f1", "context_recall"], notes="first try"))
    config = rerun_config(original)
    assert config.name == "orig-rerun" and config.k == 2 and config.notes == f"Re-run of {original.id}. first try"
    again = runner.run(config)

    def snapshot(run):
        return [(c.answer, {m: r.score for m, r in c.metrics.items()}) for c in store.get_case_results(run.id)]

    assert snapshot(again) == snapshot(original) and again.id != original.id


def test_rerun_resolves_relative_paths_from_bundles(settings, store, tmp_path):
    from rag_workbench.reporting import export_json

    runner = EvaluationRunner(settings, store)
    run = runner.run(RunConfig(name="r", dataset_path=str(REAL_DATASET), document_path=str(REAL_PDF),
                               metrics=["token_f1"], limit=2))
    payload = json.loads(export_json(run, store.get_case_results(run.id)))
    assert payload["run"]["config"]["dataset_path"] == "examples/datasets/honeybees.jsonl"
    portable = RunRecord.model_validate(payload["run"])
    config = rerun_config(portable, project_root=settings.project_root)
    assert config.dataset_path == str(settings.project_root / "examples/datasets/honeybees.jsonl")


# ------------------------------------------------------------------ CLI
def test_cli_doctor_exit_codes(capsys, tmp_path, monkeypatch):
    assert main(["doctor"]) == 0
    assert "0 failure(s)" in capsys.readouterr().out
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setenv("RAGWB_DATA_DIR", str(blocker / "data"))
    assert main(["doctor"]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_cli_doctor_survives_invalid_configuration(capsys, monkeypatch):
    monkeypatch.setenv("RAGWB_MAX_RETRIES", "many")
    assert main(["doctor"]) == 1  # reported as an error, not a traceback
    assert "RAGWB_MAX_RETRIES" in capsys.readouterr().err


def test_cli_backup_prune_rerun_and_version(capsys, settings):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0 and capsys.readouterr().out.startswith("ragwb ")
    assert main(["run", "--name", "one", "--limit", "2", "--quiet"]) == 0
    assert main(["run", "--name", "two", "--limit", "2", "--quiet"]) == 0
    capsys.readouterr()
    assert main(["backup"]) == 0 and "Backup written and verified" in capsys.readouterr().out
    assert list(settings.backups_dir.glob("runs-*.db"))

    assert main(["prune", "--keep-last", "1"]) == 0  # dry run
    out = capsys.readouterr().out
    assert "would be deleted" in out
    ctx = open_context(settings, console_logging=False)
    assert len(ctx.store.list_runs()) == 2
    assert main(["prune", "--keep-last", "1", "--yes"]) == 0
    remaining = ctx.store.list_runs()
    assert [r.name for r in remaining] == ["two"]
    assert main(["prune"]) == 1  # needs a policy

    assert main(["rerun", remaining[0].id, "--quiet", "--name", "two-again"]) == 0
    assert "re-run of" in capsys.readouterr().out
    assert main(["rerun", "no-such-run"]) == 1


def test_json_log_format_redacts_secrets():
    import logging

    from rag_workbench.logging_setup import RedactingJsonFormatter, RedactSecretsFilter

    formatter = RedactingJsonFormatter(RedactSecretsFilter(["pw-secret-value"]))
    try:
        raise RuntimeError("boom pw-secret-value")
    except RuntimeError:
        import sys

        record_ = logging.LogRecord("rag_workbench.x", logging.ERROR, "", 0, "failed for %s", ("pw-secret-value",),
                                    sys.exc_info())
    line = formatter.format(record_)
    payload = json.loads(line)
    assert payload["level"] == "ERROR" and payload["logger"] == "rag_workbench.x"
    assert "pw-secret-value" not in line and "***" in payload["message"] and "boom ***" in payload["exc"]
