import logging
import subprocess
import sys

import pytest
from conftest import REAL_DATASET, write_jsonl

from rag_workbench.cli import main
from rag_workbench.config import load_settings
from rag_workbench.logging_setup import RedactSecretsFilter
from rag_workbench.services import list_files, open_context, save_upload


def test_cli_run_list_show_compare_export(capsys, settings, tmp_path):
    assert main(["run", "--name", "cli-a", "-k", "2", "--limit", "5", "--quiet"]) == 0
    assert main(["run", "--name", "cli-b", "-k", "4", "--limit", "5", "--quiet"]) == 0
    out = capsys.readouterr().out
    assert "completed" in out and "Token F1" in out
    ctx = open_context(settings, console_logging=False)
    ids = [r.id for r in ctx.store.list_runs() if r.name.startswith("cli-")]
    assert all(ctx.store.get_run(i).config["judge_model"] is None for i in ids)  # no judge metric ran
    assert main(["list"]) == 0 and "cli-a" in capsys.readouterr().out
    assert main(["show", ids[0]]) == 0
    assert main(["compare", ids[1], ids[0]]) == 0
    assert "paired_cases" in capsys.readouterr().out
    assert main(["export", ids[0], "--format", "json", "--out-dir", str(tmp_path)]) == 0
    assert (tmp_path / f"{ids[0]}.json").is_file()


def test_cli_errors_are_reported_not_raised(capsys, tmp_path):
    assert main(["run", "--provider", "openai"]) == 1
    assert "OPENAI_API_KEY" in capsys.readouterr().err
    assert main(["run", "--metrics", "made_up"]) == 1
    assert main(["run", "-k", "0"]) == 1
    assert main(["show", "nope"]) == 1
    assert main(["run", "--threshold", "token_f1=high"]) == 1
    bad = write_jsonl(tmp_path / "bad.jsonl", [{"question": ""}])
    assert main(["validate", str(bad)]) == 1
    assert main(["validate", str(REAL_DATASET)]) == 0
    assert main(["run", "--name", "to-delete", "--limit", "1", "--quiet"]) == 0
    victim = next(r.id for r in open_context(load_settings(), console_logging=False).store.list_runs()
                  if r.name == "to-delete")
    assert main(["delete", victim]) == 1  # requires --yes
    assert main(["delete", victim, "--yes"]) == 0
    assert main(["delete", victim, "--yes"]) == 1  # already gone
    assert main(["import", str(tmp_path / "missing.json")]) == 1
    assert main(["metrics"]) == 0


def test_injected_failures_give_partial_run_exit_code(capsys):
    assert main(["run", "--inject-failures", "1.0", "--limit", "2", "--quiet"]) == 2
    assert "failed" in capsys.readouterr().out


def test_module_entry_point_runs_in_a_subprocess(tmp_path):
    env = {"RAGWB_DATA_DIR": str(tmp_path / "d"), "OPENAI_API_KEY": "", "DEEPEVAL_TELEMETRY_OPT_OUT": "1",
           "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""), "RAGWB_NO_DOTENV": "1"}
    proc = subprocess.run([sys.executable, "-m", "rag_workbench", "metrics"], cwd=tmp_path, env=env,
                          capture_output=True, text=True, timeout=120, check=False)
    assert proc.returncode == 0, proc.stderr
    assert "token_f1" in proc.stdout


def test_save_upload_sanitises_names(settings):
    path = save_upload(settings, "../../evil name.jsonl", b'{"question": "q"}', allowed_suffixes={".jsonl"},
                       max_bytes=100)
    assert path.parent == settings.uploads_dir.resolve()
    assert ".." not in path.name and " " not in path.name and path.name.endswith("-evil_name.jsonl")
    assert save_upload(settings, "x.jsonl", b'{"question": "q"}', allowed_suffixes={".jsonl"}, max_bytes=100) \
        .name.split("-")[0] == path.name.split("-")[0]  # content-addressed
    with pytest.raises(ValueError, match="not allowed"):
        save_upload(settings, "run.exe", b"x", allowed_suffixes={".jsonl"}, max_bytes=100)
    with pytest.raises(ValueError, match="limit"):
        save_upload(settings, "big.jsonl", b"x" * 101, allowed_suffixes={".jsonl"}, max_bytes=100)
    files = list_files(settings, {".jsonl"}, [REAL_DATASET])
    assert files[0] == REAL_DATASET and path in [f.resolve() for f in files]


def test_redacting_formatter_covers_tracebacks():
    from rag_workbench.logging_setup import RedactingFormatter

    formatter = RedactingFormatter("%(message)s", RedactSecretsFilter(["my-secret-value-123"]))
    try:
        raise RuntimeError("boom with my-secret-value-123")
    except RuntimeError:
        record = logging.LogRecord("x", logging.ERROR, "", 0, "failed", None, sys.exc_info())
    text = formatter.format(record)
    assert "my-secret-value-123" not in text and "boom with ***" in text


def test_secret_redaction_filter():
    f = RedactSecretsFilter(["my-secret-value-123"])
    record = logging.LogRecord("x", logging.INFO, "", 0, "key=%s other=sk-abcdefghijklmnop", ("my-secret-value-123",),
                               None)
    f.filter(record)
    assert record.getMessage() == "key=*** other=sk-***"


def test_import_command(capsys, tmp_path):
    assert main(["run", "--name", "bundle-me", "--limit", "2", "--quiet"]) == 0
    run_id = next(r.id for r in open_context(load_settings(), console_logging=False).store.list_runs()
                  if r.name == "bundle-me")
    assert main(["export", run_id, "--format", "json", "--out-dir", str(tmp_path)]) == 0
    capsys.readouterr()
    assert main(["import", str(tmp_path / f"{run_id}.json")]) == 0
    assert "already present" in capsys.readouterr().out
    assert main(["delete", run_id, "--yes"]) == 0
    assert main(["import", str(tmp_path / f"{run_id}.json")]) == 0
    assert "imported as" in capsys.readouterr().out


def test_score_command(capsys):
    assert main(["score", "--question", "What do forager bees collect?", "--answer", "Bees collect nectar and pollen.",
                 "--expected", "Bees collect nectar, pollen and water.", "--context", "Bees collect nectar, pollen and water.",
                 "--metrics", "exact_match,token_f1,groundedness"]) == 0
    out = capsys.readouterr().out
    assert "Exact match" in out and "fail" in out and "Groundedness (lexical)" in out and "1.000" in out
    assert main(["score", "--question", "q", "--answer", "a", "--metrics", "faithfulness"]) == 1
    assert "OPENAI_API_KEY" in capsys.readouterr().err
