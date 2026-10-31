"""Aggregation of per-case results into run summaries, and paired comparison of two runs.

Missing values (skipped or errored metrics, failed cases) are excluded from every statistic and
reported as counts; they are never imputed as zero. Confidence intervals are percentile bootstrap
intervals of the mean with a fixed seed, so the same results always give the same interval.
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Mapping
from dataclasses import dataclass

from .models import CaseResult, MetricSummary, RunSummary

BOOTSTRAP_RESAMPLES = 2_000
CONFIDENCE = 0.95
BOOTSTRAP_SEED = 12345


def bootstrap_ci(values: list[float], *, resamples: int = BOOTSTRAP_RESAMPLES, confidence: float = CONFIDENCE,
                 seed: int = BOOTSTRAP_SEED) -> tuple[float, float] | tuple[None, None]:
    """Percentile bootstrap CI of the mean. Needs at least two values."""
    if len(values) < 2:
        return None, None
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choices(values, k=n)) / n for _ in range(resamples))
    alpha = (1 - confidence) / 2
    low = means[max(0, math.floor(alpha * resamples))]
    high = means[min(resamples - 1, math.ceil((1 - alpha) * resamples) - 1)]
    return low, high


def percentile(values: list[float], q: float) -> float | None:
    """Linear-interpolation percentile (q in [0, 100])."""
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q / 100
    lower, upper = math.floor(pos), math.ceil(pos)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (pos - lower)


def summarize_metric(name: str, results: list[CaseResult], threshold: float | None) -> MetricSummary:
    scores: list[float] = []
    n_skipped = n_error = n_passed = 0
    for case in results:
        metric = case.metrics.get(name)
        if case.status == "error" or metric is None:
            n_error += 1 if case.status == "error" else 0
            n_skipped += 1 if case.status != "error" else 0
            continue
        if metric.status == "ok" and metric.score is not None:
            scores.append(metric.score)
            n_passed += bool(metric.passed)
        elif metric.status == "skipped":
            n_skipped += 1
        else:
            n_error += 1
    ci_low, ci_high = bootstrap_ci(scores)
    return MetricSummary(
        name=name, n_scored=len(scores), n_skipped=n_skipped, n_error=n_error,
        mean=statistics.fmean(scores) if scores else None,
        median=statistics.median(scores) if scores else None,
        std=statistics.stdev(scores) if len(scores) > 1 else None,
        min=min(scores) if scores else None, max=max(scores) if scores else None,
        ci_low=ci_low, ci_high=ci_high, threshold=threshold, n_passed=n_passed,
        pass_rate=n_passed / len(scores) if scores else None,
    )


def summarize_run(results: list[CaseResult], metric_names: list[str],
                  thresholds: Mapping[str, float | None]) -> RunSummary:
    ok = [r for r in results if r.status == "ok"]
    latencies = [r.latency_ms for r in ok if r.latency_ms is not None]
    prompt = [r.prompt_tokens for r in ok if r.prompt_tokens is not None]
    completion = [r.completion_tokens for r in ok if r.completion_tokens is not None]
    costs = [r.cost_usd for r in ok if r.cost_usd is not None]
    judge_costs = [m.cost_usd for r in ok for m in r.metrics.values() if m.cost_usd is not None]
    return RunSummary(
        n_cases=len(results), n_ok=len(ok), n_error=len(results) - len(ok),
        metrics={name: summarize_metric(name, results, thresholds.get(name)) for name in metric_names},
        mean_latency_ms=statistics.fmean(latencies) if latencies else None,
        p95_latency_ms=percentile(latencies, 95),
        total_prompt_tokens=sum(prompt) if prompt else None,
        total_completion_tokens=sum(completion) if completion else None,
        total_cost_usd=sum(costs) if costs else None,
        total_judge_cost_usd=sum(judge_costs) if judge_costs else None,
    )


MISSING_SLICE = "(missing)"


@dataclass
class SliceRow:
    """Summary of one metadata value (a "slice") of a run: how the system does on, say, ``type = unanswerable``."""

    value: str
    n_cases: int
    n_ok: int
    metrics: dict[str, MetricSummary]


def metadata_keys(results: list[CaseResult]) -> list[str]:
    """Metadata keys present on at least one case, sorted."""
    return sorted({key for case in results for key in case.metadata})


def slice_results(results: list[CaseResult], key: str, metric_names: list[str],
                  thresholds: Mapping[str, float | None]) -> list[SliceRow]:
    """Group cases by ``metadata[key]`` and summarise each group like a run.

    Cases without the key form a ``(missing)`` slice (listed last). Values are compared as text, so ``1`` and ``"1"``
    share a slice. Slices of a handful of cases have wide intervals: read ``n_cases`` before trusting a mean.
    """
    groups: dict[str, list[CaseResult]] = {}
    for case in results:
        value = case.metadata.get(key)
        groups.setdefault(MISSING_SLICE if value is None else str(value), []).append(case)
    ordered = sorted(groups, key=lambda v: (v == MISSING_SLICE, v))
    return [SliceRow(value=v, n_cases=len(groups[v]), n_ok=sum(c.status == "ok" for c in groups[v]),
                     metrics={m: summarize_metric(m, groups[v], thresholds.get(m)) for m in metric_names})
            for v in ordered]


@dataclass
class PairedComparison:
    """Per-metric comparison of run B against run A on the cases both runs scored."""

    metric: str
    n_pairs: int
    mean_a: float | None
    mean_b: float | None
    mean_diff: float | None  # mean of (B - A) over paired cases
    ci_low: float | None
    ci_high: float | None
    wins: int    # cases where B > A
    ties: int
    losses: int  # cases where B < A

    @property
    def significant(self) -> bool:
        """True when the bootstrap CI of the paired difference excludes zero."""
        return self.ci_low is not None and self.ci_high is not None and (self.ci_low > 0 or self.ci_high < 0)


def _case_key(case: CaseResult) -> str:
    return " ".join(case.question.lower().split())


def _scores_by_question(results: list[CaseResult], metric: str) -> dict[str, float]:
    scores: dict[str, float] = {}
    for case in results:
        value = case.score(metric)
        if value is not None:
            scores[_case_key(case)] = value
    return scores


def paired_comparison(results_a: list[CaseResult], results_b: list[CaseResult], metric: str,
                      *, tie_tolerance: float = 1e-9) -> PairedComparison:
    """Pair cases by normalised question text (robust to differing case ids across datasets)."""
    a_scores = _scores_by_question(results_a, metric)
    b_scores = _scores_by_question(results_b, metric)
    keys = sorted(a_scores.keys() & b_scores.keys())
    diffs = [b_scores[k] - a_scores[k] for k in keys]
    ci_low, ci_high = bootstrap_ci(diffs)
    return PairedComparison(
        metric=metric, n_pairs=len(keys),
        mean_a=statistics.fmean(a_scores[k] for k in keys) if keys else None,
        mean_b=statistics.fmean(b_scores[k] for k in keys) if keys else None,
        mean_diff=statistics.fmean(diffs) if diffs else None, ci_low=ci_low, ci_high=ci_high,
        wins=sum(d > tie_tolerance for d in diffs), ties=sum(abs(d) <= tie_tolerance for d in diffs),
        losses=sum(d < -tie_tolerance for d in diffs),
    )
