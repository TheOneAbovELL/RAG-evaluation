import pytest
from conftest import REAL_DATASET, REAL_PDF

from rag_workbench.calibration import DEFAULT_SWEEP, best_threshold, calibrate, sweep_thresholds
from rag_workbench.cli import main
from rag_workbench.models import CaseResult, MetricResult, RunConfig
from rag_workbench.runner import EvaluationRunner


def case(case_id, score, status="ok"):
    metrics = {"m": MetricResult(name="m", status=status, score=score if status == "ok" else None, threshold=0.5,
                                 passed=(score >= 0.5) if status == "ok" else None)}
    return CaseResult(case_id=case_id, position=1, question=f"q {case_id}", expected_answer="x", status="ok",
                      answer="a", metrics=metrics)


# scores separate the classes at 0.5: humans pass the high scores, fail the low ones
CASES = [case(f"p{i}", 0.6 + i * 0.03) for i in range(8)] + [case(f"f{i}", 0.1 + i * 0.04) for i in range(6)]
LABELS = {**{f"p{i}": True for i in range(8)}, **{f"f{i}": False for i in range(6)}}


def test_sweep_has_one_row_per_threshold_and_is_perfect_between_the_classes():
    rows = sweep_thresholds(CASES, LABELS, "m")
    assert [t for t, _ in rows] == list(DEFAULT_SWEEP) and DEFAULT_SWEEP[0] == 0.1 and DEFAULT_SWEEP[-1] == 0.95
    by_t = dict(rows)
    assert by_t[0.45].accuracy == pytest.approx(1.0) and by_t[0.45].kappa == pytest.approx(1.0)  # gap: 0.30..0.60
    assert by_t[0.10].accuracy < 1.0  # passes everything: the failing answers are wrongly passed
    assert by_t[0.95].accuracy < 1.0  # passes nothing
    assert by_t[0.10].kappa == pytest.approx(0.0) or by_t[0.10].kappa is None


def test_the_row_at_the_stored_threshold_matches_calibrate():
    row = dict(sweep_thresholds(CASES, LABELS, "m"))[0.5]
    plain = calibrate(CASES, LABELS, "m")
    assert (row.tp, row.fp, row.fn, row.tn) == (plain.tp, plain.fp, plain.fn, plain.tn)


def test_best_threshold_prefers_the_highest_kappa_then_the_lowest_threshold():
    rows = sweep_thresholds(CASES, LABELS, "m")
    best = best_threshold(rows)
    assert best is not None and dict(rows)[best].kappa == pytest.approx(1.0)
    perfect = [t for t, a in rows if a.kappa == pytest.approx(1.0)]
    assert best == min(perfect)  # ties go to the lowest threshold


def test_best_threshold_is_none_when_there_is_nothing_to_compare():
    assert best_threshold([]) is None
    rows = sweep_thresholds([], {}, "m")
    assert best_threshold(rows) is None  # no cases: every kappa is undefined


def test_unscored_and_unknown_cases_are_excluded_not_zeroed():
    cases = [case("a", 0.9), case("b", 0.1), case("c", None, status="error")]
    rows = sweep_thresholds(cases, {"a": True, "b": False, "c": True, "ghost": True}, "m")
    a = dict(rows)[0.5]
    assert a.n_compared == 2 and a.n_unscored == 1 and a.n_unknown == 1


# ------------------------------------------------------------------ CLI
@pytest.fixture
def run_and_labels(settings, store, tmp_path):
    run = EvaluationRunner(settings, store).run(RunConfig(
        name="cal", dataset_path=str(REAL_DATASET), document_path=str(REAL_PDF), metrics=["token_f1"], limit=12))
    cases = store.get_case_results(run.id)
    labels = tmp_path / "labels.csv"
    rows = ["case_id,human_pass"] + [f"{c.case_id},{'pass' if (c.score('token_f1') or 0) >= 0.3 else 'fail'}" for c in cases]
    labels.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return run, labels


def test_cli_sweep_prints_the_table_and_the_warning(run_and_labels, capsys):
    run, labels = run_and_labels
    assert main(["calibrate", run.id, "--labels", str(labels), "--metric", "token_f1", "--sweep"]) == 0
    out = capsys.readouterr().out
    assert "threshold sweep" in out and "0.30" in out and "optimistic" in out and "<- best" in out


def test_cli_rescore_computes_an_offline_metric_from_stored_answers(run_and_labels, capsys):
    run, labels = run_and_labels
    assert main(["calibrate", run.id, "--labels", str(labels), "--metric", "rouge_l"]) == 1  # not in the run
    assert "--rescore" in capsys.readouterr().err
    assert main(["calibrate", run.id, "--labels", str(labels), "--metric", "rouge_l", "--rescore"]) == 0
    assert "compared: 12" in capsys.readouterr().out


def test_cli_rescore_refuses_judge_metrics_and_unknown_metrics(run_and_labels, capsys):
    run, labels = run_and_labels
    assert main(["calibrate", run.id, "--labels", str(labels), "--metric", "faithfulness", "--rescore"]) == 1
    assert "judge metric" in capsys.readouterr().err
    assert main(["calibrate", run.id, "--labels", str(labels), "--metric", "nope", "--rescore"]) == 1
    assert "Unknown metric" in capsys.readouterr().err
