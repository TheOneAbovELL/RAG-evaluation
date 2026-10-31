"""How much does a judge metric disagree with itself?

An LLM judge scores the same answer differently from one call to the next. The bootstrap intervals in a run summary
reflect which *questions* were sampled, not this call-to-call noise, so a difference between two runs can be smaller
than the judge's own jitter. This module re-scores the stored answers of a run several times and reports, per metric:

``within SD``       the average, over cases, of the standard deviation of repeated scores for the same case;
``between SD``      the standard deviation of the per-case mean scores (how much cases genuinely differ);
``noise / signal``  within SD divided by between SD (above about 0.5 the judge's jitter is comparable to real
                    differences);
``verdict flips``   cases whose pass/fail verdict changed between repeats.

It re-uses the run's stored answers and contexts, so retrieval and generation are not repeated; only the judge is called
(``repeats x cases x metrics`` measurements, each of which can make several API calls).
"""

from __future__ import annotations

import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .metrics.base import Metric, MetricInput
from .models import CaseResult

MIN_RELIABLE_CASES = 10


@dataclass(frozen=True)
class NoiseRow:
    metric: str
    n_cases: int  # cases with at least two successful repeats
    repeats: int
    within_sd: float | None
    between_sd: float | None
    verdict_flips: int
    n_errors: int  # individual measurements that failed (excluded, never counted as zero)
    n_skipped_cases: int

    @property
    def noise_to_signal(self) -> float | None:
        if self.within_sd is None or not self.between_sd:
            return None
        return self.within_sd / self.between_sd

    @property
    def small_sample(self) -> bool:
        return self.n_cases < MIN_RELIABLE_CASES


def estimate_operations(cases: Sequence[CaseResult], n_metrics: int, repeats: int) -> int:
    return sum(1 for c in cases if c.status == "ok" and c.answer) * n_metrics * repeats


def measure_noise(cases: Sequence[CaseResult], metrics: Sequence[Metric], thresholds: dict[str, float], repeats: int,
                  *, progress: Callable[[str], None] | None = None) -> list[NoiseRow]:
    if repeats < 2:
        raise ValueError("repeats must be at least 2 to measure disagreement")
    usable = [c for c in cases if c.status == "ok" and c.answer]
    rows = []
    for metric in metrics:
        per_case_sds: list[float] = []
        per_case_means: list[float] = []
        flips = errors = skipped = 0
        for case in usable:
            inp = MetricInput(question=case.question, answer=case.answer or "", expected_answer=case.expected_answer,
                              contexts=[c.text for c in case.contexts])
            scores: list[float] = []
            verdicts: set[bool] = set()
            for _ in range(repeats):
                result = metric.evaluate(inp, thresholds.get(metric.name))
                if result.status == "skipped":
                    skipped += 1
                    break
                if result.status == "error" or result.score is None:
                    errors += 1
                    continue
                scores.append(result.score)
                if result.passed is not None:
                    verdicts.add(result.passed)
            if progress:
                progress(f"{metric.name} {case.case_id}")
            if len(scores) >= 2:
                per_case_sds.append(statistics.stdev(scores))
                per_case_means.append(statistics.fmean(scores))
                flips += len(verdicts) > 1
        rows.append(NoiseRow(
            metric=metric.name, n_cases=len(per_case_sds), repeats=repeats,
            within_sd=statistics.fmean(per_case_sds) if per_case_sds else None,
            between_sd=statistics.stdev(per_case_means) if len(per_case_means) >= 2 else None,
            verdict_flips=flips, n_errors=errors, n_skipped_cases=skipped))
    return rows


def format_noise(rows: Sequence[NoiseRow]) -> str:
    def f(v: float | None) -> str:
        return "n/a" if v is None else f"{v:.3f}"

    lines = [f"{'metric':<20}{'cases':>6}{'repeats':>8}{'within SD':>11}{'between SD':>12}{'noise/signal':>14}"
             f"{'flips':>7}{'errors':>8}"]
    for r in rows:
        lines.append(f"{r.metric:<20}{r.n_cases:>6}{r.repeats:>8}{f(r.within_sd):>11}{f(r.between_sd):>12}"
                     f"{f(r.noise_to_signal):>14}{r.verdict_flips:>7}{r.n_errors:>8}")
    notes = []
    if any(r.small_sample for r in rows):
        notes.append(f"Fewer than {MIN_RELIABLE_CASES} cases with usable repeats for some metrics: treat those rows "
                     "as rough.")
    if any(r.noise_to_signal is not None and r.noise_to_signal > 0.5 for r in rows):
        notes.append("noise/signal above 0.5: the judge's jitter is comparable to real differences between cases, so "
                     "small score differences between runs for that metric are not meaningful.")
    if any(r.n_errors for r in rows):
        notes.append("Failed measurements were excluded, not counted as zero.")
    if any(r.between_sd == 0 for r in rows):
        notes.append("between SD of 0 means every case scored the same: noise/signal cannot be computed for that "
                     "metric.")
    return "\n".join([*lines, *(["", *notes] if notes else [])])
