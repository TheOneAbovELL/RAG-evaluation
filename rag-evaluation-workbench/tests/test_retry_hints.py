import httpx
import openai
import tenacity

from rag_workbench.errors import (
    MAX_RETRY_AFTER_S,
    ProviderError,
    TransientProviderError,
    backoff_delay,
    classify_openai_error,
)
from rag_workbench.metrics.base import MetricInput, MetricSpec
from rag_workbench.metrics.judge import JudgeMetric


def rate_limit(retry_after=None):
    headers = {"retry-after": retry_after} if retry_after is not None else {}
    response = httpx.Response(429, headers=headers, request=httpx.Request("POST", "https://example.invalid/v1"))
    return openai.RateLimitError("slow down", body=None, response=response)


def wrapped_in_retry_error(inner):
    """What DeepEval raises after its own retries: tenacity wraps the last failed attempt."""
    future = tenacity.Future(1)
    future.set_exception(inner)
    return tenacity.RetryError(future)


def test_retry_after_header_is_carried_on_the_classified_error():
    mapped = classify_openai_error(rate_limit("12"))
    assert isinstance(mapped, TransientProviderError) and mapped.retry_after_s == 12.0
    assert classify_openai_error(rate_limit()).retry_after_s is None
    assert classify_openai_error(rate_limit("soon")).retry_after_s is None  # unparseable hint is ignored
    assert classify_openai_error(rate_limit("0")).retry_after_s is None


def test_a_rate_limit_hidden_inside_a_tenacity_retry_error_is_recognised_as_transient():
    mapped = classify_openai_error(wrapped_in_retry_error(rate_limit("7")))
    assert isinstance(mapped, TransientProviderError)
    assert "RateLimitError" in str(mapped) and mapped.retry_after_s == 7.0  # not an opaque "RetryError[<Future ...>]"


def test_a_raise_from_chain_is_unwrapped_too():
    try:
        try:
            raise rate_limit()
        except openai.RateLimitError as inner:
            raise RuntimeError("judge failed") from inner
    except RuntimeError as outer:
        assert isinstance(classify_openai_error(outer), TransientProviderError)


def test_a_connection_error_caused_by_a_transport_error_is_still_transient():
    """Found in a live run: the SDK error's own __cause__ (an httpx error) must not be unwrapped past the SDK error."""
    request = httpx.Request("POST", "https://example.invalid/v1")
    try:
        try:
            raise httpx.ConnectError("network unreachable", request=request)
        except httpx.ConnectError as transport:
            raise openai.APIConnectionError(request=request) from transport
    except openai.APIConnectionError as sdk_error:
        mapped = classify_openai_error(sdk_error)
        assert isinstance(mapped, TransientProviderError) and "APIConnectionError" in str(mapped)
        assert isinstance(classify_openai_error(wrapped_in_retry_error(sdk_error)), TransientProviderError)


def test_unrelated_wrapped_errors_are_not_classified():
    assert classify_openai_error(wrapped_in_retry_error(ValueError("bad json"))) is None
    assert classify_openai_error(RuntimeError("plain")) is None


def test_permanent_errors_stay_permanent_when_wrapped():
    auth = openai.AuthenticationError("no", body=None, response=httpx.Response(
        401, request=httpx.Request("POST", "https://example.invalid/v1")))
    mapped = classify_openai_error(wrapped_in_retry_error(auth))
    assert isinstance(mapped, ProviderError) and not isinstance(mapped, TransientProviderError)


def test_backoff_follows_the_hint_but_is_capped():
    no_jitter = lambda low, high: 0.0  # noqa: E731
    assert backoff_delay(1.0, 1, None, jitter=no_jitter) == 1.0
    assert backoff_delay(1.0, 3, None, jitter=no_jitter) == 4.0  # exponential without a hint
    assert backoff_delay(1.0, 1, TransientProviderError("x", 20.0), jitter=no_jitter) == 20.0  # waits as told
    assert backoff_delay(1.0, 5, TransientProviderError("x", 2.0), jitter=no_jitter) == 16.0  # never shorter than backoff
    assert backoff_delay(1.0, 1, TransientProviderError("x", 9999.0), jitter=no_jitter) == MAX_RETRY_AFTER_S


def test_judge_waits_for_the_providers_retry_after_before_retrying():
    sleeps, calls = [], []

    class Flaky(JudgeMetric):
        def _measure(self, inp, threshold):
            calls.append(1)
            if len(calls) == 1:
                raise TransientProviderError("rate limited", retry_after_s=25.0)
            return 0.9, "fine", None

    metric = Flaky(MetricSpec("m", "M", "llm_judge", "d", 0.7), lambda t: None, max_retries=2,
                   retry_base_delay_s=1.0, sleep=sleeps.append)
    result = metric.evaluate(MetricInput("q", "a", "r", ["c"]))
    assert result.status == "ok" and len(calls) == 2
    assert sleeps and sleeps[0] >= 25.0
