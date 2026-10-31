import csv
import io

import pytest
from conftest import REAL_DATASET, REAL_PDF

from rag_workbench.calibration import (
    Agreement,
    LabelsError,
    calibrate,
    cohen_kappa,
    interpret_kappa,
    labelling_sheet,
    load_labels,
    parse_label,
)
from rag_workbench.cli import main
from rag_workbench.models import CaseResult, MetricResult, RunConfig
from rag_workbench.runner import EvaluationRunner


def result(case_id, passed, status="ok"):
    metrics = {"m": MetricResult(name="m", status=status, score=0.9 if passed else 0.1, threshold=0.5,
                                 passed=passed if status == "ok" else None)}
    return CaseResult(case_id=case_id, position=1, question=f"Q {case_id}", expected_answer="x", status="ok",
                      answer="a", metrics=metrics)


# ------------------------------------------------------------------ kappa
def test_kappa_hand_computed():
    # 50 cases: tp 20, fp 5, fn 10, tn 15. observed = 35/50 = 0.7; metric pass 25/50, human pass 30/50
    # expected = (25*30 + 25*20) / 2500 = 0.5; kappa = (0.7 - 0.5) / 0.5 = 0.4
    assert cohen_kappa(20, 5, 10, 15) == pytest.approx(0.4)
    assert cohen_kappa(10, 0, 0, 10) == pytest.approx(1.0)  # perfect agreement
    assert cohen_kappa(0, 10, 10, 0) == pytest.approx(-1.0)  # perfect disagreement
    assert cohen_kappa(5, 5, 5, 5) == pytest.approx(0.0)  # chance level


def test_kappa_is_undefined_when_a_rater_never_varies():
    assert cohen_kappa(0, 0, 0, 0) is None
    assert cohen_kappa(10, 0, 0, 0) is None  # both raters say "pass" for everything: expected agreement is 1


@pytest.mark.parametrize("value,label", [
    (None, "undefined"), (-0.2, "poor (worse than chance)"), (0.0, "poor (worse than chance)"), (0.1, "slight"),
    (0.3, "fair"), (0.5, "moderate"), (0.7, "substantial"), (0.9, "almost perfect"),
])
def test_kappa_bands(value, label):
    assert interpret_kappa(value) == label


def test_agreement_properties():
    a = Agreement(metric="m", n_compared=50, n_labelled=50, n_unscored=0, n_unknown=0, tp=20, fp=5, fn=10, tn=15)
    assert a.accuracy == pytest.approx(0.7) and a.precision == pytest.approx(0.8) and a.recall == pytest.approx(2 / 3)
    assert a.metric_pass_rate == pytest.approx(0.5) and a.human_pass_rate == pytest.approx(0.6)
    assert not a.small_sample
    empty = Agreement(metric="m", n_compared=0, n_labelled=0, n_unscored=0, n_unknown=0, tp=0, fp=0, fn=0, tn=0)
    assert empty.accuracy is None and empty.precision is None and empty.recall is None and empty.small_sample


# ------------------------------------------------------------------ comparison
def test_calibrate_counts_each_cell_and_reports_what_could_not_be_compared():
    results = [result("c1", True), result("c2", True), result("c3", False), result("c4", False),
               result("c5", True, status="error"), result("c6", True)]
    labels = {"c1": True, "c2": False, "c3": True, "c4": False, "c5": True, "ghost": True}  # c6 unlabelled
    a = calibrate(results, labels, "m")
    assert (a.tp, a.fp, a.fn, a.tn) == (1, 1, 1, 1)
    assert a.n_compared == 4 and a.n_labelled == 5 and a.n_unscored == 1 and a.n_unknown == 1
    assert calibrate(results, {}, "m").n_compared == 0
    assert calibrate(results, labels, "no-such-metric").n_compared == 0


# ------------------------------------------------------------------ labels files
@pytest.mark.parametrize("raw,expected", [
    ("pass", True), ("PASS", True), ("Yes", True), ("1", True), (True, True), (" correct ", True),
    ("fail", False), ("No", False), ("0", False), (False, False), ("wrong", False),
    ("", None), ("  ", None), (None, None),
])
def test_parse_label(raw, expected):
    assert parse_label(raw) is expected


def test_parse_label_rejects_unknown_values():
    with pytest.raises(ValueError, match="unrecognised label 'maybe'"):
        parse_label("maybe")


def test_load_labels_csv_jsonl_and_blanks(tmp_path):
    (tmp_path / "l.csv").write_text("case_id,human_pass,note\nq1,pass,ok\nq2,FAIL,\nq3,,undecided\n", encoding="utf-8")
    assert load_labels(tmp_path / "l.csv") == {"q1": True, "q2": False}  # blank = unlabelled
    (tmp_path / "l.jsonl").write_text('{"case_id": "q1", "human_pass": true}\n\n{"case_id": "q2", "human_pass": "no"}\n',
                                      encoding="utf-8")
    assert load_labels(tmp_path / "l.jsonl") == {"q1": True, "q2": False}


@pytest.mark.parametrize("name,content,fragment", [
    ("l.csv", "id,label\nq1,pass\n", "header must contain case_id and human_pass"),
    ("l.csv", "case_id,human_pass\nq1,maybe\n", "line 2: unrecognised label"),
    ("l.csv", "case_id,human_pass\nq1,pass\nq1,fail\n", "duplicate case_id 'q1'"),
    ("l.csv", "case_id,human_pass\n,pass\n", "missing case_id"),
    ("l.jsonl", "{not json}\n", "invalid JSON"),
    ("l.jsonl", "[1, 2]\n", "expected a JSON object"),
    ("l.txt", "x", "Unsupported labels file type"),
])
def test_load_labels_errors_name_the_line(tmp_path, name, content, fragment):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    with pytest.raises(LabelsError, match=fragment):
        load_labels(path)


def test_load_labels_file_level_errors(tmp_path):
    with pytest.raises(LabelsError, match="not found"):
        load_labels(tmp_path / "missing.csv")
    (tmp_path / "bin.csv").write_bytes(b"\xff\xfe\x00\x00")
    with pytest.raises(LabelsError, match="UTF-8"):
        load_labels(tmp_path / "bin.csv")


# ------------------------------------------------------------------ end to end
def test_labelling_sheet_round_trips_through_calibration(settings, store):
    run = EvaluationRunner(settings, store).run(RunConfig(
        name="cal", dataset_path=str(REAL_DATASET), document_path=str(REAL_PDF),
        metrics=["token_f1", "context_recall"]))
    cases = store.get_case_results(run.id)
    rows = list(csv.DictReader(io.StringIO(labelling_sheet(run, cases).decode("utf-8-sig"))))
    assert [r["case_id"] for r in rows] == [c.case_id for c in cases]
    assert {"question", "expected_answer", "answer", "token_f1_score", "context_recall_score", "human_pass",
            "note"} <= set(rows[0])
    assert all(r["human_pass"] == "" for r in rows)

    # A "human" that agrees with context_recall on every case except the first.
    flipped = {c.case_id: bool(c.metrics["context_recall"].passed) for c in cases}
    flipped[cases[0].case_id] = not flipped[cases[0].case_id]
    a = calibrate(cases, flipped, "context_recall")
    assert a.n_compared == 20 and a.accuracy == pytest.approx(19 / 20) and a.kappa is not None and a.small_sample


def test_labelling_sheet_neutralises_spreadsheet_formulas(settings, store):
    from rag_workbench.models import RunRecord, utcnow

    run = RunRecord(id="r", name="r", status="completed", created_at=utcnow(), config={}, n_cases=1)
    hostile = CaseResult(case_id="c1", position=1, question="=SUM(A1)", expected_answer="+1", status="ok", answer="@x")
    text = labelling_sheet(run, [hostile]).decode("utf-8-sig")
    assert "'=SUM(A1)" in text and "'+1" in text and "'@x" in text


def test_cli_labels_template_and_calibrate(capsys, tmp_path):
    assert main(["run", "--name", "cal", "--metrics", "token_f1,context_recall", "--quiet"]) == 0
    from rag_workbench.config import load_settings
    from rag_workbench.services import open_context

    ctx = open_context(load_settings(), console_logging=False)
    run = next(r for r in ctx.store.list_runs() if r.name == "cal")
    sheet = tmp_path / "sheet.csv"
    assert main(["labels-template", run.id, "--out", str(sheet)]) == 0
    assert main(["labels-template", run.id, "--out", str(sheet)]) == 1  # refuses to overwrite
    assert "already exists" in capsys.readouterr().err
    assert main(["labels-template", run.id, "--out", str(sheet), "--force"]) == 0

    rows = list(csv.DictReader(io.StringIO(sheet.read_text(encoding="utf-8-sig"))))
    for i, row in enumerate(rows):
        row["human_pass"] = "pass" if float(row["context_recall_score"]) >= 0.7 else "fail"
        if i == 0:
            row["human_pass"] = "fail" if row["human_pass"] == "pass" else "pass"
    with sheet.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    capsys.readouterr()
    assert main(["calibrate", run.id, "--labels", str(sheet), "--metric", "context_recall"]) == 0
    out = capsys.readouterr().out
    assert "compared: 20" in out and "agreement 0.950" in out and "kappa" in out and "fewer than 30" in out
    assert main(["calibrate", run.id, "--labels", str(sheet), "--metric", "nope"]) == 1
    assert "Available:" in capsys.readouterr().err
    empty = tmp_path / "empty.csv"
    empty.write_text("case_id,human_pass\nq01,\n", encoding="utf-8")
    assert main(["calibrate", run.id, "--labels", str(empty), "--metric", "context_recall"]) == 1  # nothing to compare
