import httpx
import openai
import pytest

from rag_workbench.config import ConfigError, load_settings
from rag_workbench.metrics import METRIC_SPECS, MetricInput, build_metrics, validate_metric_names
from rag_workbench.metrics.base import Metric, MetricSpec
from rag_workbench.metrics.judge import JUDGE_SPECS, JudgeMetric, build_judge_metric
from rag_workbench.metrics.lexical import LEXICAL_METRICS
from rag_workbench.metrics.semantic import SEMANTIC_SPECS


def inp(answer="", expected="", contexts=None, question="q?"):
    return MetricInput(question=question, answer=answer, expected_answer=expected, contexts=contexts or [])


def score(name, **kwargs):
    return LEXICAL_METRICS[name].evaluate(inp(**kwargs))


def test_exact_match():
    assert score("exact_match", answer="The Nectar!", expected="nectar").score == 1.0
    result = score("exact_match", answer="pollen", expected="nectar")
    assert result.score == 0.0 and result.passed is False


def test_token_f1_hand_computed():
    # pred tokens: bees collect nectar pollen (4); gold: bees collect nectar (3); overlap 3
    r = score("token_f1", answer="Bees collect nectar and pollen", expected="Bees collect nectar")
    # "and" is kept (SQuAD keeps stop words): pred = 5 tokens -> P = 3/5, R = 1 -> F1 = 0.75
    assert r.score == pytest.approx(0.75)
    assert score("token_f1", answer="wax", expected="nectar").score == 0.0
    assert score("token_f1", answer="!!!", expected="nectar").score == 0.0


def test_token_f1_counts_multiset_overlap():
    r = score("token_f1", answer="pollen pollen pollen", expected="pollen nectar")
    # overlap = min(3, 1) = 1; P = 1/3, R = 1/2 -> F1 = 0.4
    assert r.score == pytest.approx(0.4)


def test_rouge_l_hand_computed():
    # pred: bees really collect nectar (4); gold: bees collect nectar (3); LCS = 3
    r = score("rouge_l", answer="Bees really collect nectar", expected="Bees collect nectar")
    p, rec = 3 / 4, 1.0
    assert r.score == pytest.approx(2 * p * rec / (p + rec))
    assert score("rouge_l", answer="nectar collect bees", expected="bees collect nectar").score == pytest.approx(1 / 3)


def test_context_recall_and_groundedness():
    ctx = ["Bees collect nectar and water."]
    r = score("context_recall", expected="Bees collect nectar and pollen", contexts=ctx)
    assert r.score == pytest.approx(3 / 4)  # bee, collect, nectar found; pollen missing
    assert "pollen" in r.reason
    g = score("groundedness", answer="Bees collect nectar and wax", contexts=ctx)
    assert g.score == pytest.approx(3 / 4) and "wax" in g.reason


def test_skips_are_not_zero():
    assert score("token_f1", answer="x", expected=None).status == "skipped"
    assert score("context_recall", expected="nectar", contexts=[]).status == "skipped"
    abst = score("groundedness", answer="The PDF does not provide enough information to answer the question.",
                 contexts=["x"])
    assert abst.status == "skipped" and abst.score is None and "abstained" in abst.reason
    assert score("context_recall", expected="the of and", contexts=["x"]).status == "skipped"
    unanswerable = score("context_recall", contexts=["The PDF has information about bees."],
                         expected="The PDF does not provide enough information to answer the question.")
    assert unanswerable.status == "skipped" and "unanswerable" in unanswerable.reason


def test_custom_threshold_and_errors_are_captured():
    r = LEXICAL_METRICS["token_f1"].evaluate(inp(answer="nectar", expected="nectar pollen"), threshold=0.9)
    assert r.threshold == 0.9 and r.passed is False

    def boom(_):
        raise RuntimeError("bad input")

    broken = Metric(MetricSpec("broken", "Broken", "lexical", "", 0.5), boom)
    result = broken.evaluate(inp(answer="a"))
    assert result.status == "error" and "bad input" in result.reason and result.score is None


def test_registry_and_validation():
    assert set(METRIC_SPECS) == set(LEXICAL_METRICS) | set(SEMANTIC_SPECS) | set(JUDGE_SPECS)
    with pytest.raises(ConfigError, match="Unknown metric"):
        validate_metric_names(["nope"])
    with pytest.raises(ConfigError, match="at least one"):
        validate_metric_names([])
    with pytest.raises(ConfigError, match="need OPENAI_API_KEY"):
        validate_metric_names(["token_f1", "faithfulness"], load_settings({}, dotenv=False))
    keyed = load_settings({"OPENAI_API_KEY": "sk-test-123456789"}, dotenv=False)
    metrics = build_metrics(["token_f1", "correctness"], keyed, judge_model="gpt-judge")
    assert [m.name for m in metrics] == ["token_f1", "correctness"]
    assert isinstance(metrics[1], JudgeMetric)


class FakeDeepEvalMetric:
    def __init__(self, threshold, outcome):
        self.threshold = threshold
        self.outcome = outcome
        self.score = None
        self.reason = None
        self.seen = None

    def measure(self, test_case):
        self.seen = test_case
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        self.score, self.reason = self.outcome


def test_judge_metric_uses_fresh_metric_and_threshold():
    made = []

    def factory(threshold):
        made.append(FakeDeepEvalMetric(threshold, (0.82, " supported ")))
        return made[-1]

    metric = JudgeMetric(JUDGE_SPECS["faithfulness"], factory)
    result = metric.evaluate(inp(answer="a", contexts=["c1", "c2"]), threshold=0.9)
    assert (result.status, result.score, result.passed, result.reason) == ("ok", 0.82, False, "supported")
    assert made[0].threshold == 0.9 and made[0].seen.retrieval_context == ["c1", "c2"]
    metric.evaluate(inp(answer="a", contexts=["c"]))
    assert len(made) == 2 and made[1].threshold == 0.7


def test_judge_metric_requirements_and_failures():
    rate = openai.RateLimitError("429", response=httpx.Response(429, request=httpx.Request("POST", "https://x")),
                                 body=None)
    metric = JudgeMetric(JUDGE_SPECS["correctness"], lambda t: FakeDeepEvalMetric(t, rate))
    assert metric.evaluate(inp(answer="a", expected=None)).status == "skipped"
    failed = metric.evaluate(inp(answer="a", expected="b"))
    assert failed.status == "error" and "RateLimitError" in failed.reason
    none_score = JudgeMetric(JUDGE_SPECS["answer_relevancy"], lambda t: FakeDeepEvalMetric(t, (None, None)))
    assert none_score.evaluate(inp(answer="a")).status == "error"


def test_build_judge_metric_constructs_deepeval_objects_without_network():
    metric = build_judge_metric("correctness", model="gpt-4o", api_key="sk-test-123456789")
    deepeval_metric = metric._factory(0.6)
    assert deepeval_metric.threshold == 0.6
    assert type(deepeval_metric).__name__ == "GEval"
    for name in ("answer_relevancy", "faithfulness", "context_relevancy"):
        assert build_judge_metric(name, model="gpt-4o", api_key="sk-test-123456789")._factory(0.7).threshold == 0.7
    with pytest.raises(KeyError):
        build_judge_metric("token_f1", model="m", api_key="k")


def test_out_of_range_scores_are_errors_but_float_noise_is_absorbed():
    too_big = Metric(MetricSpec("bad", "Bad", "lexical", "", 0.5), lambda _: (5.0, "oops"))
    result = too_big.evaluate(inp(answer="a"))
    assert result.status == "error" and result.score is None and "outside [0, 1]" in result.reason
    noisy = Metric(MetricSpec("noisy", "Noisy", "lexical", "", 0.5), lambda _: (1.0000000000000002, "ok"))
    assert noisy.evaluate(inp(answer="a")).score == 1.0


def _rate_limit():
    return openai.RateLimitError("429", response=httpx.Response(429, request=httpx.Request("POST", "https://x")),
                                 body=None)


class SequencedDeepEvalMetric:
    """Fake DeepEval metric whose successive measure() calls follow a script of outcomes."""

    def __init__(self, script, cost=None):
        self.script, self.cost, self.calls = list(script), cost, 0
        self.score = self.reason = None
        self.evaluation_cost = cost

    def measure(self, test_case):
        self.calls += 1
        step = self.script.pop(0)
        if isinstance(step, BaseException):
            raise step
        self.score, self.reason = step


def test_judge_retries_transient_errors_with_backoff():
    sleeps = []
    shared = SequencedDeepEvalMetric([_rate_limit(), _rate_limit(), (0.9, "fine")], cost=0.002)
    metric = JudgeMetric(JUDGE_SPECS["faithfulness"], lambda t: shared, max_retries=2, retry_base_delay_s=1.0,
                         sleep=sleeps.append)
    result = metric.evaluate(inp(answer="a", contexts=["c"]))
    assert result.status == "ok" and result.score == 0.9 and result.cost_usd == 0.002
    assert shared.calls == 3 and len(sleeps) == 2
    assert 1 <= sleeps[0] <= 2 and 2 <= sleeps[1] <= 3  # 1*2^0 + jitter, 1*2^1 + jitter


def test_judge_gives_up_after_the_retry_budget_and_does_not_retry_permanent_errors():
    sleeps = []
    always = SequencedDeepEvalMetric([_rate_limit()] * 5)
    metric = JudgeMetric(JUDGE_SPECS["faithfulness"], lambda t: always, max_retries=2, retry_base_delay_s=0,
                         sleep=sleeps.append)
    failed = metric.evaluate(inp(answer="a", contexts=["c"]))
    assert failed.status == "error" and "RateLimitError" in failed.reason and always.calls == 3

    auth = openai.AuthenticationError("bad key", response=httpx.Response(401, request=httpx.Request("POST", "https://x")),
                                      body=None)
    permanent = SequencedDeepEvalMetric([auth])
    result = JudgeMetric(JUDGE_SPECS["faithfulness"], lambda t: permanent, max_retries=2,
                         sleep=sleeps.append).evaluate(inp(answer="a", contexts=["c"]))
    assert result.status == "error" and permanent.calls == 1


def test_judge_cost_is_aggregated_per_run():
    from rag_workbench.aggregate import summarize_run
    from rag_workbench.models import CaseResult, MetricResult

    def case(i, cost):
        return CaseResult(case_id=f"c{i}", position=i, question=f"Q{i}", expected_answer="x", status="ok", answer="a",
                          metrics={"faithfulness": MetricResult(name="faithfulness", status="ok", score=1.0,
                                                                threshold=0.7, passed=True, cost_usd=cost)})

    assert summarize_run([case(1, 0.01), case(2, 0.02)], ["faithfulness"], {}).total_judge_cost_usd == pytest.approx(0.03)
    assert summarize_run([case(1, None)], ["faithfulness"], {}).total_judge_cost_usd is None
