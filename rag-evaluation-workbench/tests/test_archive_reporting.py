import csv
import io
import json

import pytest
from conftest import REAL_DATASET, REAL_PDF

from rag_workbench.archive import BundleError, import_bundle, load_bundle
from rag_workbench.models import CaseResult, MetricResult, RunConfig
from rag_workbench.reporting import (
    comparison_dataframe,
    export_csv,
    export_json,
    export_markdown,
    export_run,
    safe_filename,
    summary_dataframe,
    write_export,
)
from rag_workbench.runner import EvaluationRunner
from rag_workbench.storage import RunStore


@pytest.fixture
def two_runs(settings, store):
    """Two real offline runs over the example data (k=1 and k=3)."""
    runner = EvaluationRunner(settings, store)

    def make(k: int) -> RunConfig:
        return RunConfig(name=f"bm25-k{k}", dataset_path=str(REAL_DATASET), document_path=str(REAL_PDF), k=k,
                         metrics=["token_f1", "rouge_l", "context_recall", "groundedness"])

    return runner.run(make(1)), runner.run(make(3))


@pytest.fixture
def bundle(two_runs, store, tmp_path):
    run = two_runs[1]
    path = tmp_path / "bundle.json"
    path.write_bytes(export_json(run, store.get_case_results(run.id)))
    return path


def test_export_import_round_trip(two_runs, store, bundle, tmp_path):
    other = RunStore(tmp_path / "other.db")
    run_id = two_runs[1].id
    assert import_bundle(other, bundle) == run_id
    assert other.get_case_results(run_id) == store.get_case_results(run_id)
    imported = other.get_run(run_id)
    assert imported.status == "imported" and imported.config["original_status"] == "completed"
    assert imported.summary.metrics["context_recall"].mean == pytest.approx(
        two_runs[1].summary.metrics["context_recall"].mean)
    assert import_bundle(other, bundle) is None  # idempotent


@pytest.mark.parametrize("content,fragment", [
    ("not json", "not valid UTF-8 JSON"),
    ('{"format": "other"}', "is not a 'rag-workbench-run' bundle"),
    ('{"format": "rag-workbench-run", "version": 99}', "unsupported bundle version"),
    ('{"format": "rag-workbench-run", "version": 1, "run": {"id": 1}}', "failed validation"),
])
def test_invalid_bundles_are_rejected(tmp_path, bundle, content, fragment):
    path = tmp_path / "bad.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(BundleError, match=fragment):
        load_bundle(path)
    with pytest.raises(BundleError, match="not found"):
        load_bundle(tmp_path / "missing.json")
    with pytest.raises(BundleError, match="larger than"):
        load_bundle(bundle, max_bytes=10)


def test_duplicate_case_ids_rejected(bundle, tmp_path):
    payload = json.loads(bundle.read_text(encoding="utf-8"))
    payload["cases"][1]["case_id"] = payload["cases"][0]["case_id"]
    path = tmp_path / "dup.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(BundleError, match="duplicate case ids"):
        load_bundle(path)


def test_bundle_summary_is_recomputed_not_trusted(two_runs, bundle, tmp_path):
    payload = json.loads(bundle.read_text(encoding="utf-8"))
    payload["run"]["summary"]["metrics"]["token_f1"]["mean"] = 0.999  # tampered
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    other = RunStore(tmp_path / "other.db")
    import_bundle(other, path)
    assert other.get_run(two_runs[1].id).summary.metrics["token_f1"].mean == pytest.approx(
        two_runs[1].summary.metrics["token_f1"].mean)


def test_exported_bundles_contain_no_absolute_paths(store, offline_config, settings):
    run = EvaluationRunner(settings, store).run(offline_config(limit=1))
    payload = json.loads(export_json(run, store.get_case_results(run.id)))
    for key in ("dataset_path", "document_path"):
        value = payload["run"]["config"][key]
        assert not value.startswith(("/", "\\")) and ":" not in value, value  # tmp files: name only
    assert payload["run"]["config"]["dataset_path"] == "small.jsonl"


def test_example_paths_become_project_relative(two_runs, bundle):
    config = json.loads(bundle.read_text(encoding="utf-8"))["run"]["config"]
    assert config["dataset_path"] == "examples/datasets/honeybees.jsonl"
    assert config["document_path"] == "examples/documents/honeybees.pdf"


def make_results():
    return [
        CaseResult(case_id="c1", position=1, question="=HYPERLINK(\"http://evil\")", expected_answer="a",
                   status="ok", answer="+1 cmd|' /C calc'!A0", metrics={
                       "token_f1": MetricResult(name="token_f1", status="ok", score=0.25, threshold=0.5,
                                                passed=False, reason="P | R")}),
        CaseResult(case_id="c2", position=2, question="Where?", expected_answer=None, status="error",
                   error="timeout\nretry"),
    ]


def test_csv_export_neutralises_formulas(two_runs):
    run = two_runs[0].model_copy(update={"config": {"metrics": ["token_f1"]}})
    rows = list(csv.DictReader(io.StringIO(export_csv(run, make_results()).decode("utf-8-sig"))))
    assert rows[0]["question"].startswith("'=") and rows[0]["answer"].startswith("'+")
    assert rows[0]["token_f1"] == "0.25" and rows[1]["status"] == "error"


def test_json_and_markdown_exports(two_runs, store):
    run = two_runs[1]
    results = store.get_case_results(run.id)
    payload = json.loads(export_json(run, results))
    assert payload["format"] == "rag-workbench-run" and payload["run"]["id"] == run.id
    assert len(payload["cases"]) == 20
    md = export_markdown(run, results)
    assert "# Evaluation report: bm25-k3" in md
    assert "| Token F1 |" in md and "Lowest Context recall (lexical)" in md
    warned = run.model_copy(update={"config": {**run.config, "provenance_warnings": ["scores re-entered by hand"]}})
    assert "Provenance warning:** scores re-entered by hand" in export_markdown(warned, results)
    md_err = export_markdown(run.model_copy(update={"config": {"metrics": ["token_f1"]}}), make_results())
    assert "## Failed cases" in md_err and "timeout retry" in md_err and "P \\| R" in md_err
    with pytest.raises(ValueError):
        export_run(run, results, "xlsx")


def test_write_export_and_safe_filenames(two_runs, store, tmp_path):
    run = two_runs[0]
    path = write_export(run, store.get_case_results(run.id), "md", tmp_path / "out")
    assert path.parent == tmp_path / "out" and path.name == f"{run.id}.md" and path.stat().st_size > 0
    assert safe_filename("../../etc/passwd") == "etc_passwd"
    assert safe_filename("...") == "export"
    assert "/" not in safe_filename("a/b\\c:d")


def test_summary_and_comparison_frames(two_runs, store):
    a, b = two_runs
    df = summary_dataframe(store.list_runs())
    assert set(df["run_id"]) == {a.id, b.id}
    cmp = comparison_dataframe(a, store.get_case_results(a.id), b, store.get_case_results(b.id))
    row = cmp.set_index("metric").loc["context_recall"]
    assert row["paired_cases"] == 20
    assert row["diff_b_minus_a"] == pytest.approx(b.summary.metrics["context_recall"].mean
                                                  - a.summary.metrics["context_recall"].mean)
