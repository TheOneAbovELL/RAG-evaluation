"""Exception hierarchy for model/provider calls and the mapping from OpenAI SDK errors."""

from __future__ import annotations

import random
from collections.abc import Callable


class ProviderError(RuntimeError):
    """A model call failed in a way that retrying will not fix (bad key, invalid request...)."""


class TransientProviderError(ProviderError):
    """A model call failed in a way that may succeed on retry (rate limit, timeout, 5xx).

    ``retry_after_s`` is the provider's own hint (the ``Retry-After`` header) when it sent one.
    """

    def __init__(self, message: str, retry_after_s: float | None = None):
        super().__init__(message)
        self.retry_after_s = retry_after_s


MAX_RETRY_AFTER_S = 60.0


def backoff_delay(base_s: float, attempt: int, exc: BaseException | None = None, *,
                  jitter: Callable[[float, float], float] = random.uniform) -> float:
    """Exponential back-off with jitter, stretched to the provider's ``Retry-After`` hint (capped at a minute)."""
    delay = base_s * 2 ** (attempt - 1) + jitter(0, base_s)
    hint = getattr(exc, "retry_after_s", None)
    if hint:
        delay = max(delay, min(float(hint), MAX_RETRY_AFTER_S))
    return delay


def classify_openai_error(exc: BaseException) -> ProviderError | None:
    """Translate an OpenAI SDK exception into our hierarchy; ``None`` if it is not an OpenAI error.

    The message never includes request headers, so API keys cannot leak through it.
    """
    try:
        import openai
    except ImportError:  # pragma: no cover - openai is a hard dependency
        return None
    exc = _unwrap(exc)
    name = type(exc).__name__
    if isinstance(exc, (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError,
                        openai.InternalServerError)):
        return TransientProviderError(f"OpenAI-compatible API {name}: {_short(exc)}", _retry_after(exc))
    if isinstance(exc, openai.AuthenticationError):
        return ProviderError("OpenAI rejected the API key (AuthenticationError). Check OPENAI_API_KEY.")
    if isinstance(exc, openai.OpenAIError):
        return ProviderError(f"OpenAI {name}: {_short(exc)}")
    return None


def _unwrap(exc: BaseException) -> BaseException:
    """The first OpenAI SDK error in ``exc``'s chain, or ``exc`` itself if there is none.

    Wrappers such as tenacity's ``RetryError`` (used by DeepEval) and ``raise ... from`` chains hide the SDK error; the
    search stops at the *first* SDK error so that its own ``__cause__`` (for example an httpx connection error) is not
    mistaken for the thing to classify.
    """
    import openai

    current: BaseException | None = exc
    for _ in range(8):
        if current is None:
            break
        if isinstance(current, openai.OpenAIError):
            return current
        last_attempt = getattr(current, "last_attempt", None)  # tenacity.RetryError
        inner = last_attempt.exception() if last_attempt is not None and hasattr(last_attempt, "exception") else None
        current = inner or current.__cause__
    return exc


def _retry_after(exc: BaseException) -> float | None:
    """Seconds from a ``Retry-After`` response header, if the SDK error carries one."""
    try:
        value = exc.response.headers.get("retry-after")  # type: ignore[attr-defined]
        seconds = float(value)
    except (AttributeError, TypeError, ValueError):
        return None
    return seconds if seconds > 0 else None


def _short(exc: BaseException, limit: int = 300) -> str:
    text = str(exc).strip() or type(exc).__name__
    return text if len(text) <= limit else text[: limit - 3] + "..."
