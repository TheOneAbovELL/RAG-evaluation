import itertools

import pytest
from conftest import REAL_DATASET, REAL_PDF

from rag_workbench import cli
from rag_workbench.cli import main
from rag_workbench.judge_noise import (
    MIN_RELIABLE_CASES,
    estimate_operations,
    format_noise,
    measure_noise,
)
from rag_workbench.metrics.base import Metric, MetricSkipped, MetricSpec
from rag_workbench.models import CaseResult, RunConfig
from rag_workbench.runner import EvaluationRunner

SPEC = MetricSpec("jm", "Judge metric", "llm_judge", "stand-in", 0.5, requires_openai=True)


class Scripted(Metric):
    """Returns the scripted scores in order for each call, per case (keyed by the question)."""

    def __init__(self, script):
        super().__init__(SPEC)
        self._iters = {q: itertools.cycle(v) for q, v in script.items()}

    def score(self, inp, threshold):
        value = next(self._iters[inp.question])
        if value is None:
            raise RuntimeError("judge call failed")
        if value == "skip":
            raise MetricSkipped("nothing to judge")
        return value, "scripted"


def case(question, status="ok", answer="an answer"):
    return CaseResult(case_id=question, position=1, question=question, expected_answer="ref", status=status,
                      answer=answer if status == "ok" else None)


def test_steady_judge_has_zero_within_sd_and_flips():
    cases = [case(f"q{i}") for i in range(12)]
    script = {f"q{i}": [0.2 + i * 0.05] for i in range(12)}  # same score every time
    [row] = measure_noise(cases, [Scripted(script)], {"jm": 0.5}, repeats=3)
    assert row.within_sd == pytest.approx(0.0) and row.verdict_flips == 0 and row.n_cases == 12
    assert row.between_sd > 0 and row.noise_to_signal == pytest.approx(0.0) and not row.small_sample


def test_noisy_judge_is_measured_and_flips_are_counted():
    cases = [case("a"), case("b"), case("c")]
    script = {"a": [0.4, 0.6, 0.4, 0.6], "b": [0.9, 0.9], "c": [0.1, 0.1]}
    [row] = measure_noise(cases, [Scripted(script)], {"jm": 0.5}, repeats=4)
    assert row.verdict_flips == 1  # only case a crosses the 0.5 threshold between repeats
    assert row.within_sd == pytest.approx((0.11547005 + 0 + 0) / 3, abs=1e-6)  # sample SD of [.4,.6,.4,.6] is 0.1155
    assert row.small_sample  # 3 cases < MIN_RELIABLE_CASES


def test_failed_measurements_are_excluded_not_zeroed():
    cases = [case("a"), case("b")]
    script = {"a": [0.8, None, 0.8], "b": [None]}  # case b never succeeds
    [row] = measure_noise(cases, [Scripted(script)], {"jm": 0.5}, repeats=3)
    assert row.n_errors == 4 and row.n_cases == 1  # a: 2 usable repeats; b: none
    assert row.within_sd == pytest.approx(0.0)


def test_skipped_and_failed_cases_are_not_judged():
    cases = [case("a"), case("failed", status="error"), case("noanswer", answer="")]
    assert estimate_operations(cases, n_metrics=2, repeats=3) == 6  # only case a counts
    [row] = measure_noise(cases, [Scripted({"a": ["skip"]})], {"jm": 0.5}, repeats=2)
    assert row.n_skipped_cases == 1 and row.n_cases == 0 and row.within_sd is None


def test_repeats_must_be_at_least_two():
    with pytest.raises(ValueError, match="at least 2"):
        measure_noise([case("a")], [Scripted({"a": [0.5]})], {}, repeats=1)


def test_report_explains_what_the_numbers_mean():
    rows = measure_noise([case("a"), case("b")], [Scripted({"a": [0.1, 0.9], "b": [0.5, 0.52]})], {"jm": 0.5}, repeats=2)
    text = format_noise(rows)
    assert "within SD" in text and "noise/signal" in text
    assert f"Fewer than {MIN_RELIABLE_CASES}" in text
    assert "not meaningful" in text  # a very noisy judge is called out


# ------------------------------------------------------------------ CLI
@pytest.fixture
def judged_run(settings, store):
    config = RunConfig(name="jn", dataset_path=str(REAL_DATASET), document_path=str(REAL_PDF),
                       metrics=["token_f1"], limit=6)
    return EvaluationRunner(settings, store).run(config)


def test_cli_requires_confirmation_for_many_calls_and_runs_with_a_stand_in_judge(judged_run, monkeypatch, capsys):
    monkeypatch.setattr(cli, "build_metrics", lambda names, settings, **kw: [Metric(
        MetricSpec(n, n, "llm_judge", "d", 0.5, requires_openai=True), lambda inp: (0.5, "x")) for n in names])
    assert main(["judge-noise", judged_run.id, "--metrics", "faithfulness,correctness", "--repeats", "3"]) == 1
    assert "re-run with --yes" in capsys.readouterr().err  # 6 cases x 2 metrics x 3 repeats = 36 > 30
    assert main(["judge-noise", judged_run.id, "--metrics", "faithfulness", "--repeats", "2"]) == 0
    out = capsys.readouterr().out
    assert "12 judge measurements" in out and "faithfulness" in out and "within SD" in out


def test_cli_without_judge_metrics_explains_what_to_do(judged_run, capsys):
    assert main(["judge-noise", judged_run.id]) == 1
    assert "no judge metrics" in capsys.readouterr().err
    assert main(["judge-noise", judged_run.id, "--metrics", "faithfulness"]) == 1  # no API key in tests
    assert "OPENAI_API_KEY" in capsys.readouterr().err
    assert main(["judge-noise", "nope"]) == 1
