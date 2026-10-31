import statistics

import pytest

from rag_workbench.aggregate import bootstrap_ci, paired_comparison, percentile, summarize_run
from rag_workbench.models import CaseResult, MetricResult


def case(i, scores, status="ok", question=None):
    metrics = {}
    for name, value in scores.items():
        if value == "skip":
            metrics[name] = MetricResult(name=name, status="skipped", threshold=0.5)
        elif value == "err":
            metrics[name] = MetricResult(name=name, status="error", threshold=0.5)
        else:
            metrics[name] = MetricResult(name=name, status="ok", score=value, threshold=0.5, passed=value >= 0.5)
    return CaseResult(case_id=f"c{i}", position=i, question=question or f"Question {i}", expected_answer="x",
                      status=status, answer="a", latency_ms=10.0 * i, prompt_tokens=10, completion_tokens=2,
                      metrics=metrics if status == "ok" else {})


def test_missing_values_are_excluded_not_zeroed():
    results = [case(1, {"m": 1.0}), case(2, {"m": 0.0}), case(3, {"m": "skip"}), case(4, {"m": "err"}),
               case(5, {}, status="error")]
    s = summarize_run(results, ["m"], {"m": 0.5})
    m = s.metrics["m"]
    assert (m.n_scored, m.n_skipped, m.n_error) == (2, 1, 2)
    assert m.mean == 0.5 and m.pass_rate == 0.5 and m.n_passed == 1
    assert m.std == pytest.approx(statistics.stdev([1.0, 0.0]))
    assert (s.n_cases, s.n_ok, s.n_error) == (5, 4, 1)
    assert s.total_prompt_tokens == 40 and s.mean_latency_ms == pytest.approx(25.0)


def test_empty_summary():
    s = summarize_run([], ["m"], {"m": 0.5})
    assert s.metrics["m"].mean is None and s.metrics["m"].pass_rate is None
    assert s.mean_latency_ms is None and s.total_prompt_tokens is None


def test_bootstrap_is_deterministic_and_brackets_mean():
    values = [0.1, 0.4, 0.5, 0.9, 1.0, 0.7]
    assert bootstrap_ci(values) == bootstrap_ci(values)
    low, high = bootstrap_ci(values)
    assert low <= statistics.fmean(values) <= high
    assert bootstrap_ci([1.0]) == (None, None)
    assert bootstrap_ci([0.5] * 10) == (0.5, 0.5)


def test_percentile():
    assert percentile([], 95) is None
    assert percentile([1, 2, 3, 4, 5], 50) == 3
    assert percentile([0, 10], 95) == pytest.approx(9.5)


def test_paired_comparison_matches_by_question_text():
    a = [case(1, {"m": 0.5}, question="Where?"), case(2, {"m": 0.5}, question="Why?"),
         case(3, {"m": 0.2}, question="Only in A?")]
    b = [case(9, {"m": 1.0}, question="  where? "), case(8, {"m": 0.5}, question="WHY?"),
         case(7, {"m": "skip"}, question="Only in A?")]
    c = paired_comparison(a, b, "m")
    assert c.n_pairs == 2
    assert c.mean_diff == pytest.approx(0.25)
    assert (c.wins, c.ties, c.losses) == (1, 1, 0)


def test_paired_comparison_significance_flag():
    a = [case(i, {"m": 0.2}) for i in range(10)]
    b = [case(i, {"m": 0.8}) for i in range(10)]
    assert paired_comparison(a, b, "m").significant
    assert not paired_comparison(a, a, "m").significant
