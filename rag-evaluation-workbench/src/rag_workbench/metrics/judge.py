"""LLM-as-a-judge metrics backed by DeepEval: answer relevancy, faithfulness, context relevancy, correctness.

Each case gets fresh DeepEval metric objects (they hold per-measurement state, so sharing them
across threads would be unsafe) and is measured synchronously so failures are attributable to a
single case. The judge model is explicit and recorded in the run configuration.

Judge scores are model opinions under a rubric, not ground truth: they vary between judge models
and, to a lesser degree, between repeated calls. Treat small differences between runs with care.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from ..errors import TransientProviderError, backoff_delay, classify_openai_error
from ..ratelimit import RateLimiter, limiter_for
from .base import Metric, MetricInput, MetricSpec, ScoreOutcome

log = logging.getLogger(__name__)

# GEval criteria: the judge compares the answer with the reference answer for factual agreement.
CORRECTNESS_CRITERIA = "Determine whether the actual output is factually correct based on the expected output"

JUDGE_SPECS: dict[str, MetricSpec] = {
    "answer_relevancy": MetricSpec(
        "answer_relevancy", "Answer relevancy (judge)", "llm_judge",
        "Share of answer statements the judge considers relevant to the question (DeepEval AnswerRelevancyMetric)",
        0.7, requires_openai=True),
    "faithfulness": MetricSpec(
        "faithfulness", "Faithfulness (judge)", "llm_judge",
        "Share of answer claims the judge finds supported by the retrieved context (DeepEval FaithfulnessMetric)",
        0.7, requires_context=True, requires_openai=True),
    "context_relevancy": MetricSpec(
        "context_relevancy", "Context relevancy (judge)", "llm_judge",
        "Share of retrieved-context statements the judge considers relevant to the question "
        "(DeepEval ContextualRelevancyMetric)",
        0.7, requires_context=True, requires_openai=True),
    "correctness": MetricSpec(
        "correctness", "Correctness (judge)", "llm_judge",
        "GEval rubric score of factual agreement between answer and reference", 0.7,
        requires_reference=True, requires_openai=True),
}


class JudgeMetric(Metric):
    """A DeepEval metric; ``factory(threshold)`` returns a fresh DeepEval metric object.

    Transient provider errors (rate limits, timeouts, 5xx) are retried with exponential back-off and jitter, up to
    ``max_retries`` extra attempts; DeepEval may apply its own retry policy underneath. Permanent errors are not
    retried. A failure after the last attempt is recorded by :meth:`Metric.evaluate` as an ``error`` result.
    """

    def __init__(self, spec: MetricSpec, factory: Callable[[float], Any], *, max_retries: int = 2,
                 retry_base_delay_s: float = 1.0, sleep: Callable[[float], None] = time.sleep,
                 limiter: RateLimiter | None = None):
        super().__init__(spec)
        self._limiter = limiter
        self._factory = factory
        self.max_retries = max_retries
        self.retry_base_delay_s = retry_base_delay_s
        self._sleep = sleep

    def score(self, inp: MetricInput, threshold: float) -> ScoreOutcome:
        attempt = 0
        while True:
            try:
                if self._limiter is not None:
                    self._limiter.acquire()
                return self._measure(inp, threshold)
            except TransientProviderError as exc:
                attempt += 1
                if attempt > self.max_retries:
                    raise
                delay = backoff_delay(self.retry_base_delay_s, attempt, exc)
                log.info("Judge %s: transient error (%s); retry %d/%d in %.1fs", self.name, exc, attempt,
                         self.max_retries, delay)
                self._sleep(delay)

    def _measure(self, inp: MetricInput, threshold: float) -> tuple[float, str, float | None]:
        from deepeval.test_case import LLMTestCase

        test_case = LLMTestCase(input=inp.question, actual_output=inp.answer, expected_output=inp.expected_answer,
                                retrieval_context=list(inp.contexts) if inp.contexts else None)
        metric = self._factory(threshold)
        try:
            metric.measure(test_case)
        except Exception as exc:
            mapped = classify_openai_error(exc)
            if mapped is not None:
                raise mapped from exc
            raise
        if metric.score is None:
            raise RuntimeError("judge returned no score")
        cost = getattr(metric, "evaluation_cost", None)
        return (float(metric.score), (metric.reason or "").strip()[:2000],
                float(cost) if isinstance(cost, int | float) else None)


def build_judge_metric(name: str, *, model: str, api_key: str, base_url: str | None = None,
                       timeout_s: float = 60.0, max_retries: int = 2,
                       retry_base_delay_s: float = 1.0, max_requests_per_minute: float | None = None) -> JudgeMetric:
    """Create a judge metric. The DeepEval model object is created per measurement."""
    if name not in JUDGE_SPECS:
        raise KeyError(name)

    def judge_model() -> Any:
        from deepeval.models import OpenAIModel

        kwargs: dict[str, Any] = {"model": model, "api_key": api_key, "temperature": 0, "timeout": timeout_s}
        if base_url:
            kwargs["base_url"] = base_url
        return OpenAIModel(**kwargs)

    def factory(threshold: float) -> Any:
        from deepeval import metrics as dm
        from deepeval.test_case import SingleTurnParams

        common: dict[str, Any] = {"threshold": threshold, "model": judge_model(), "async_mode": False,
                                  "include_reason": True}
        if name == "answer_relevancy":
            return dm.AnswerRelevancyMetric(**common)
        if name == "faithfulness":
            return dm.FaithfulnessMetric(**common)
        if name == "context_relevancy":
            return dm.ContextualRelevancyMetric(**common)
        common.pop("include_reason")
        return dm.GEval(name="Correctness", criteria=CORRECTNESS_CRITERIA,
                        evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.EXPECTED_OUTPUT],
                        **common)

    return JudgeMetric(JUDGE_SPECS[name], factory, max_retries=max_retries, retry_base_delay_s=retry_base_delay_s,
                       limiter=limiter_for(max_requests_per_minute))
