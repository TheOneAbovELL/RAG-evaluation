import pytest

from rag_workbench.cli import main
from rag_workbench.models import CaseResult, MetricResult, RunRecord, utcnow
from rag_workbench.regression import (
    EXIT_OK,
    EXIT_REGRESSION,
    EXIT_UNJUDGED,
    check_regression,
    format_regression,
)


def run(run_id, metrics=("m",)):
    return RunRecord(id=run_id, name=run_id, status="completed", created_at=utcnow(),
                     config={"metrics": list(metrics)}, n_cases=0)


def cases(scores, status="ok", metric="m"):
    out = []
    for i, score in enumerate(scores):
        metrics = {metric: MetricResult(name=metric, status="ok", score=score, threshold=0.5, passed=score >= 0.5)}
        out.append(CaseResult(case_id=f"c{i}", position=i, question=f"Question number {i}?", expected_answer="x", status=status,
                              answer="a", metrics=metrics if status == "ok" else {}))
    return out


BASE = [0.3 + (i % 5) * 0.1 for i in range(30)]  # varied scores so paired differences have a spread


def verdict(base_scores, cand_scores, **kw):
    report = check_regression(run("b"), cases(base_scores), run("c"), cases(cand_scores), **kw)
    return report, report.findings[0].verdict


def test_clear_drop_is_a_regression():
    report, v = verdict(BASE, [s - 0.2 + (i % 3) * 0.01 for i, s in enumerate(BASE)])
    assert v == "regression" and report.exit_code == EXIT_REGRESSION
    assert "FAIL" in format_regression(report)


def test_identical_runs_pass():
    report, v = verdict(BASE, BASE)
    assert v == "ok" and report.exit_code == EXIT_OK and "PASS" in format_regression(report)


def test_clear_gain_is_reported_as_improved_and_passes():
    report, v = verdict(BASE, [s + 0.1 + (i % 3) * 0.01 for i, s in enumerate(BASE)])
    assert v == "improved" and report.exit_code == EXIT_OK


def test_noisy_drop_is_possible_not_a_failure():
    base = [0.5] * 12
    cand = [0.8] * 6 + [0.1] * 6  # mean falls by 0.05 but the paired differences are wildly spread
    report, v = verdict(base, cand, max_drop=0.02)
    assert v == "possible" and report.exit_code == EXIT_OK
    assert "possible" in format_regression(report)


def test_drop_inside_the_tolerance_is_ok():
    _, v = verdict(BASE, [s - 0.01 for s in BASE], max_drop=0.05)
    assert v == "ok"


def test_too_few_pairs_means_not_judged_and_does_not_pass():
    report, v = verdict(BASE[:5], BASE[:5])
    assert v == "insufficient" and report.exit_code == EXIT_UNJUDGED
    assert "NOT JUDGED" in format_regression(report)


def test_no_shared_metrics_is_not_judged():
    report = check_regression(run("b", ["x"]), cases(BASE, metric="x"), run("c", ["y"]), cases(BASE, metric="y"))
    assert report.findings == [] and report.exit_code == EXIT_UNJUDGED


def test_more_failures_is_a_regression_even_if_scores_match():
    candidate = cases(BASE) + cases([0.0] * 6, status="error")
    report = check_regression(run("b"), cases(BASE), run("c"), candidate, max_error_increase=0.05)
    assert report.error_regression and report.exit_code == EXIT_REGRESSION
    assert report.candidate_error_rate == pytest.approx(6 / 36)
    relaxed = check_regression(run("b"), cases(BASE), run("c"), candidate, max_error_increase=0.5)
    assert not relaxed.error_regression


def test_metric_filter_limits_what_is_gated():
    base = cases(BASE, metric="m")
    for case, other in zip(base, cases(BASE, metric="n"), strict=True):
        case.metrics["n"] = other.metrics["n"]
    report = check_regression(run("b", ["m", "n"]), base, run("c", ["m", "n"]), base, metrics=["n", "zzz"])
    assert [f.metric for f in report.findings] == ["n"]


def test_cli_regress_exit_codes(capsys):
    assert main(["run", "--name", "wide", "-k", "3", "--quiet"]) == 0
    assert main(["run", "--name", "narrow", "-k", "1", "--quiet"]) == 0
    from rag_workbench.config import load_settings
    from rag_workbench.services import open_context

    by_name = {r.name: r.id for r in open_context(load_settings(), console_logging=False).store.list_runs()}
    capsys.readouterr()
    assert main(["regress", by_name["wide"], by_name["wide"]]) == 0
    assert "PASS" in capsys.readouterr().out
    assert main(["regress", by_name["wide"], by_name["narrow"], "--min-pairs", "500"]) == EXIT_UNJUDGED
    assert main(["regress", by_name["narrow"], by_name["wide"], "--metrics", "token_f1"]) == EXIT_REGRESSION
    assert "token_f1" in capsys.readouterr().out
    assert main(["regress", "nope", by_name["wide"]]) == 1
