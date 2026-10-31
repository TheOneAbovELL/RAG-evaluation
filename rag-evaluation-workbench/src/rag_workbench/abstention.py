"""Choosing the offline generator's abstention threshold on data it was not tuned on.

The extractive baseline can decline to answer when its chosen sentences cover too little of the question
(``min_evidence``). A threshold chosen by looking at the same questions it is then scored on would flatter itself, so
this module splits the questions into a *development* half and a *test* half (deterministically, by a hash of the
question id), picks the setting that does best on the development half, and reports that setting on the test half
next to the untuned baseline.

A question "should abstain" when its reference answer is itself an abstention (see ``text.is_abstention``); every
other question should be answered. The objective is balanced accuracy: the mean of the share of unanswerable
questions it declined and the share of answerable questions it answered. Ties go to the lower threshold, and to not
skipping headings, so the tuned setting is the least intrusive one that does as well.

Limits worth stating next to any result: the bundled datasets hold only a handful of unanswerable questions per
document, so the test half is small and the figures are wide-interval estimates, and a threshold tuned on these
documents says little about a different corpus. Retrieval is BM25 over the document in every case.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .config import Settings
from .datasets import load_dataset
from .documents import load_chunks
from .models import EvalCase, RunConfig
from .pipeline import build_pipeline
from .text import is_abstention

THRESHOLDS = tuple(round(i / 10, 1) for i in range(10))  # 0.0 (never abstain) ... 0.9
MIN_RELIABLE_UNANSWERABLE = 30


@dataclass(frozen=True)
class Setting:
    min_evidence: float
    skip_headings: bool

    def label(self) -> str:
        return f"min_evidence={self.min_evidence:.1f}" + (", skip_headings" if self.skip_headings else "")


@dataclass(frozen=True)
class Confusion:
    """Abstention decisions against what should have happened (positive = abstained)."""

    tp: int = 0  # unanswerable, declined
    fn: int = 0  # unanswerable, answered anyway
    fp: int = 0  # answerable, declined (a missed answer)
    tn: int = 0  # answerable, answered

    @property
    def n_unanswerable(self) -> int:
        return self.tp + self.fn

    @property
    def n_answerable(self) -> int:
        return self.fp + self.tn

    @property
    def abstain_recall(self) -> float | None:
        return self.tp / self.n_unanswerable if self.n_unanswerable else None

    @property
    def answer_rate(self) -> float | None:
        return self.tn / self.n_answerable if self.n_answerable else None

    @property
    def balanced_accuracy(self) -> float | None:
        a, b = self.abstain_recall, self.answer_rate
        return (a + b) / 2 if a is not None and b is not None else None

    def __add__(self, other: Confusion) -> Confusion:
        return Confusion(self.tp + other.tp, self.fn + other.fn, self.fp + other.fp, self.tn + other.tn)


@dataclass
class TuningReport:
    chosen: Setting
    baseline: Setting
    dev_scores: dict[Setting, Confusion]
    test_chosen: Confusion
    test_baseline: Confusion
    n_dev: int
    n_test: int
    notes: list[str] = field(default_factory=list)


def should_abstain(case: EvalCase) -> bool:
    return bool(case.expected_answer) and is_abstention(case.expected_answer or "")


def split_cases(cases: Sequence[EvalCase], salt: str = "") -> tuple[list[EvalCase], list[EvalCase]]:
    """Deterministic 50/50 split by hash parity of ``salt + id`` (stable across runs and platforms)."""
    dev: list[EvalCase] = []
    test: list[EvalCase] = []
    for case in cases:
        digest = hashlib.sha256(f"{salt}:{case.id}".encode()).digest()
        (dev if digest[0] % 2 == 0 else test).append(case)
    return dev, test


def _decisions(settings: Settings, document: Path, cases: Sequence[EvalCase], setting: Setting) -> Confusion:
    config = RunConfig(name="tune", dataset_path=str(document), document_path=str(document), provider="offline",
                       retriever="bm25", k=3, metrics=["token_f1"], min_evidence=setting.min_evidence,
                       skip_headings=setting.skip_headings)
    pipeline = build_pipeline(config, settings, load_chunks(document))
    tp = fn = fp = tn = 0
    for case in cases:
        abstained = is_abstention(pipeline.answer(case.question).answer)
        if should_abstain(case):
            tp, fn = (tp + 1, fn) if abstained else (tp, fn + 1)
        else:
            fp, tn = (fp + 1, tn) if abstained else (fp, tn + 1)
    return Confusion(tp, fn, fp, tn)


def tune(settings: Settings, pairs: Sequence[tuple[Path, Path]], *,
         thresholds: Sequence[float] = THRESHOLDS) -> TuningReport:
    """Tune on the development halves of every (dataset, document) pair; report on the test halves."""
    halves = []
    for dataset, document in pairs:
        dev, test = split_cases(load_dataset(dataset, max_cases=settings.max_cases), salt=Path(document).name)
        halves.append((Path(document), dev, test))
    settings_grid = [Setting(t, h) for h in (False, True) for t in thresholds]
    dev_scores: dict[Setting, Confusion] = {}
    for setting in settings_grid:
        total = Confusion()
        for document, dev, _ in halves:
            total += _decisions(settings, document, dev, setting)
        dev_scores[setting] = total

    def key(s: Setting) -> tuple[float, float, int]:  # best score first; then the lowest threshold, no skipping
        return (-(dev_scores[s].balanced_accuracy or 0.0), s.min_evidence, int(s.skip_headings))

    chosen = min(settings_grid, key=key)
    baseline = Setting(0.0, False)
    test_chosen, test_baseline = Confusion(), Confusion()
    for document, _, test in halves:
        test_chosen += _decisions(settings, document, test, chosen)
        test_baseline += _decisions(settings, document, test, baseline)
    notes = []
    if test_chosen.n_unanswerable < MIN_RELIABLE_UNANSWERABLE:
        notes.append(f"Only {test_chosen.n_unanswerable} unanswerable test questions (fewer than "
                     f"{MIN_RELIABLE_UNANSWERABLE}): treat the test figures as rough.")
    if (dev_scores[chosen].balanced_accuracy or 0) <= (dev_scores[baseline].balanced_accuracy or 0):
        notes.append("No setting beat never abstaining on the development half; the baseline is the right default.")
    return TuningReport(chosen=chosen, baseline=baseline, dev_scores=dev_scores, test_chosen=test_chosen,
                        test_baseline=test_baseline,
                        n_dev=sum(len(d) for _, d, _ in halves), n_test=sum(len(t) for _, _, t in halves), notes=notes)


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def format_report(report: TuningReport) -> str:
    lines = [f"Development questions: {report.n_dev} | test questions: {report.n_test}",
             f"Chosen on the development half: {report.chosen.label()}", "",
             f"{'setting':<34}{'declined unanswerable':>23}{'answered answerable':>21}{'balanced acc.':>15}"]

    def row(name: str, c: Confusion) -> str:
        return (f"{name:<34}{f'{c.tp}/{c.n_unanswerable} ({_fmt(c.abstain_recall)})':>23}"
                f"{f'{c.tn}/{c.n_answerable} ({_fmt(c.answer_rate)})':>21}{_fmt(c.balanced_accuracy):>15}")

    lines.append("Held-out test half:")
    lines.append(row("  " + report.baseline.label() + " (default)", report.test_baseline))
    lines.append(row("  " + report.chosen.label() + " (tuned)", report.test_chosen))
    lines += ["", "Development half, every setting (best five):"]
    ranked = sorted(report.dev_scores, key=lambda s: (-(report.dev_scores[s].balanced_accuracy or 0), s.min_evidence,
                                                        s.skip_headings))
    lines += [row("  " + s.label(), report.dev_scores[s]) for s in ranked[:5]]
    lines += ["", *report.notes]
    return "\n".join(lines)
