"""A regression gate: is a candidate run measurably worse than a baseline run?

Used after changing a prompt, retriever or model::

    ragwb rerun BASELINE_ID --name candidate        # same configuration, today's code
    ragwb regress BASELINE_ID CANDIDATE_ID          # exit 0 ok, 3 regression, 4 nothing could be judged

A metric counts as a **regression** only when the drop is both large (more than ``max_drop``) and statistically
distinguishable from noise (the bootstrap interval of the paired per-question difference lies entirely below zero).
A large drop whose interval still contains zero is reported as a **possible** regression and does not fail the gate:
with a small dataset that is the honest reading. Metrics with fewer than ``min_pairs`` paired questions cannot be
judged and are reported as such, and if *no* metric could be judged the gate does not pass (exit 4), because an empty
check must never look like a clean one.

The error rate is gated too: more failed cases than the baseline had (beyond ``max_error_increase``) is a regression
even when the surviving cases score the same.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .aggregate import paired_comparison
from .models import CaseResult, RunRecord
from .reporting import run_metrics

Verdict = Literal["regression", "possible", "ok", "improved", "insufficient"]
EXIT_OK, EXIT_REGRESSION, EXIT_UNJUDGED = 0, 3, 4


@dataclass(frozen=True)
class Finding:
    metric: str
    verdict: Verdict
    n_pairs: int
    mean_baseline: float | None
    mean_candidate: float | None
    diff: float | None
    ci_low: float | None
    ci_high: float | None


@dataclass(frozen=True)
class RegressionReport:
    findings: list[Finding]
    baseline_error_rate: float
    candidate_error_rate: float
    error_regression: bool
    max_drop: float
    min_pairs: int

    @property
    def exit_code(self) -> int:
        if self.error_regression or any(f.verdict == "regression" for f in self.findings):
            return EXIT_REGRESSION
        if not any(f.verdict != "insufficient" for f in self.findings):
            return EXIT_UNJUDGED
        return EXIT_OK


def _error_rate(results: list[CaseResult]) -> float:
    return sum(r.status == "error" for r in results) / len(results) if results else 0.0


def check_regression(baseline: RunRecord, baseline_cases: list[CaseResult], candidate: RunRecord,
                     candidate_cases: list[CaseResult], *, max_drop: float = 0.02, min_pairs: int = 10,
                     max_error_increase: float = 0.05, metrics: list[str] | None = None) -> RegressionReport:
    shared = [m for m in run_metrics(baseline) if m in run_metrics(candidate)]
    wanted = shared if metrics is None else [m for m in metrics if m in shared]
    findings = []
    for metric in wanted:
        c = paired_comparison(baseline_cases, candidate_cases, metric)
        if c.n_pairs < min_pairs or c.mean_diff is None:
            verdict: Verdict = "insufficient"
        elif c.mean_diff < -max_drop:
            verdict = "regression" if c.significant else "possible"
        elif c.significant and c.mean_diff > 0:
            verdict = "improved"
        else:
            verdict = "ok"
        findings.append(Finding(metric, verdict, c.n_pairs, c.mean_a, c.mean_b, c.mean_diff, c.ci_low, c.ci_high))
    base_err, cand_err = _error_rate(baseline_cases), _error_rate(candidate_cases)
    return RegressionReport(findings, base_err, cand_err, cand_err > base_err + max_error_increase, max_drop,
                            min_pairs)


def format_regression(report: RegressionReport) -> str:
    def num(v: float | None, signed: bool = False) -> str:
        return "n/a" if v is None else (f"{v:+.3f}" if signed else f"{v:.3f}")

    lines = [f"{'metric':<22}{'verdict':<14}{'pairs':>6}{'baseline':>10}{'candidate':>11}{'diff':>9}  95% CI of diff"]
    for f in report.findings:
        lines.append(f"{f.metric:<22}{f.verdict:<14}{f.n_pairs:>6}{num(f.mean_baseline):>10}"
                     f"{num(f.mean_candidate):>11}{num(f.diff, True):>9}  "
                     f"[{num(f.ci_low, True)}, {num(f.ci_high, True)}]")
    lines.append(f"error rate: baseline {report.baseline_error_rate:.1%}, candidate {report.candidate_error_rate:.1%}"
                 + ("  -> REGRESSION" if report.error_regression else ""))
    code = report.exit_code
    lines.append({0: "PASS: no significant regression.",
                  3: "FAIL: regression detected.",
                  4: f"NOT JUDGED: no metric had at least {report.min_pairs} paired questions; nothing was verified."
                  }[code])
    if any(f.verdict == "possible" for f in report.findings):
        lines.append(f"Note: a 'possible' drop is larger than {report.max_drop} but its interval includes zero; "
                     "gather more questions before trusting either reading.")
    return "\n".join(lines)
