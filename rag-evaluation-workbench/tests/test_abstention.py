import pytest
from conftest import REAL_PDF

from rag_workbench.abstention import (
    THRESHOLDS,
    Confusion,
    Setting,
    format_report,
    should_abstain,
    split_cases,
    tune,
)
from rag_workbench.cli import main
from rag_workbench.config import PROJECT_ROOT
from rag_workbench.models import EvalCase
from rag_workbench.prompts import ABSTAIN_ANSWER

UNANSWERABLE = PROJECT_ROOT / "examples" / "datasets" / "honeybees_unanswerable.jsonl"


def case(case_id, expected):
    return EvalCase(id=case_id, question="q " + case_id, expected_answer=expected)


def test_confusion_arithmetic_and_balanced_accuracy():
    c = Confusion(tp=3, fn=1, fp=2, tn=6)
    assert c.n_unanswerable == 4 and c.n_answerable == 8
    assert c.abstain_recall == pytest.approx(0.75) and c.answer_rate == pytest.approx(0.75)
    assert c.balanced_accuracy == pytest.approx(0.75)
    assert Confusion().balanced_accuracy is None  # nothing to measure: undefined, not zero
    assert Confusion(tp=1, fn=0).balanced_accuracy is None  # no answerable questions
    assert (c + c).tp == 6


def test_should_abstain_follows_the_reference_answer():
    assert should_abstain(case("a", ABSTAIN_ANSWER))
    assert not should_abstain(case("b", "Queens lay eggs."))
    assert not should_abstain(case("c", None))


def test_split_is_deterministic_disjoint_and_roughly_even():
    cases = [case(f"q{i}", "x") for i in range(200)]
    dev, test = split_cases(cases, salt="doc")
    assert (dev, test) == split_cases(cases, salt="doc")
    assert {c.id for c in dev}.isdisjoint(c.id for c in test) and len(dev) + len(test) == 200
    assert 70 <= len(dev) <= 130
    assert split_cases(cases, salt="other")[0] != dev  # the salt changes the split


def test_tuning_reports_a_held_out_half_and_is_reproducible(settings):
    first = tune(settings, [(UNANSWERABLE, REAL_PDF)], thresholds=(0.0, 0.5, 0.9))
    again = tune(settings, [(UNANSWERABLE, REAL_PDF)], thresholds=(0.0, 0.5, 0.9))
    assert first.chosen == again.chosen and first.test_chosen == again.test_chosen
    assert first.n_dev + first.n_test == 6  # every question lands in exactly one half
    assert first.chosen in first.dev_scores and Setting(0.0, False) in first.dev_scores
    # The default never abstains, so it declines none of the unanswerable questions.
    assert first.test_baseline.tp == 0 and first.test_baseline.fp == 0
    assert any("fewer than 30" in n for n in first.notes)
    text = format_report(first)
    assert "Held-out test half" in text and "(default)" in text and "(tuned)" in text


def test_default_grid_covers_zero_to_point_nine():
    assert THRESHOLDS[0] == 0.0 and THRESHOLDS[-1] == 0.9 and len(THRESHOLDS) == 10


def test_cli_tune_abstention(capsys):
    assert main(["tune-abstention", "--dataset", str(UNANSWERABLE), "--document", str(REAL_PDF)]) == 0
    assert "Held-out test half" in capsys.readouterr().out
    assert main(["tune-abstention", "--dataset", str(UNANSWERABLE)]) == 1  # unmatched pair
    assert "same number" in capsys.readouterr().err
