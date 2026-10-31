"""Metric contract and the shared evaluation wrapper.

Every metric returns a :class:`~rag_workbench.models.MetricResult` with one of three statuses:

``ok``       a score in [0, 1] was computed (``passed`` = ``score >= threshold``);
``skipped``  a required input was absent (no reference answer, no retrieved context, abstained answer);
``error``    the computation raised (e.g. the judge model call failed). The error text is kept.

Skipped and errored results are excluded from means, never counted as zero.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from ..models import MetricResult

log = logging.getLogger(__name__)

SCORE_TOLERANCE = 1e-9  # e.g. GEval can return 1.0000000000000002

Family = Literal["lexical", "semantic", "llm_judge"]


@dataclass(frozen=True)
class MetricInput:
    question: str
    answer: str
    expected_answer: str | None
    contexts: list[str]


@dataclass(frozen=True)
class MetricSpec:
    name: str
    label: str
    family: Family
    description: str
    default_threshold: float
    requires_reference: bool = False
    requires_context: bool = False
    requires_openai: bool = False
    requires_local_model: bool = False


class MetricSkipped(Exception):
    """Raised inside a metric function to report a 'skipped' result with a reason."""


# A scorer returns (score, reason).
Scorer = Callable[[MetricInput], tuple[float, str]]
ScoreOutcome = tuple[float, str] | tuple[float, str, float | None]


class Metric:
    """A named scorer plus its requirements. Subclasses or plain scorers both fit."""

    def __init__(self, spec: MetricSpec, scorer: Scorer | None = None):
        self.spec = spec
        self._scorer = scorer

    @property
    def name(self) -> str:
        return self.spec.name

    def score(self, inp: MetricInput, threshold: float) -> ScoreOutcome:
        """Compute ``(score, reason)`` or ``(score, reason, cost_usd)``. Subclasses without a plain scorer override."""
        if self._scorer is None:
            raise NotImplementedError(f"metric {self.name} has no scorer")
        return self._scorer(inp)

    def evaluate(self, inp: MetricInput, threshold: float | None = None) -> MetricResult:
        threshold = self.spec.default_threshold if threshold is None else threshold
        if self.spec.requires_reference and not inp.expected_answer:
            return MetricResult(name=self.name, status="skipped", threshold=threshold,
                                reason="no expected_answer for this case")
        if self.spec.requires_context and not inp.contexts:
            return MetricResult(name=self.name, status="skipped", threshold=threshold,
                                reason="no retrieved context for this case")
        try:
            outcome = self.score(inp, threshold)
        except MetricSkipped as skip:
            return MetricResult(name=self.name, status="skipped", threshold=threshold, reason=str(skip))
        except Exception as exc:  # recorded per case; one failing metric must not abort the run
            log.warning("Metric %s failed: %s", self.name, exc)
            return MetricResult(name=self.name, status="error", threshold=threshold,
                                reason=f"{type(exc).__name__}: {exc}"[:500])
        score, reason = float(outcome[0]), outcome[1]
        cost = outcome[2] if len(outcome) == 3 else None
        if not -SCORE_TOLERANCE <= score <= 1 + SCORE_TOLERANCE:  # a scorer bug, not a low/high score
            return MetricResult(name=self.name, status="error", threshold=threshold,
                                reason=f"score {score!r} outside [0, 1]")
        score = min(1.0, max(0.0, score))  # absorb floating-point noise only
        return MetricResult(name=self.name, status="ok", score=score, threshold=threshold,
                            passed=score >= threshold, reason=reason, cost_usd=cost)
