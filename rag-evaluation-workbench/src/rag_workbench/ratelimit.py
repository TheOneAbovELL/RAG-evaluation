"""Client-side pacing for providers with request-rate limits (free tiers, shared keys).

Retries that honour ``Retry-After`` (see :mod:`rag_workbench.errors`) recover from a rate limit *after* it is hit;
pacing avoids hitting it. ``RAGWB_MAX_REQUESTS_PER_MINUTE`` spaces model operations evenly: one *operation* is one
answer generation or one judge-metric measurement. A judge measurement can itself make several API calls (DeepEval's
faithfulness metric extracts claims, then verifies them), so set the limit below the provider's request quota divided
by that fan-out; if the provider limits *tokens* per minute instead, tune it down until runs stop hitting 429s.

One limiter is shared by every thread of the process, so several workers cannot exceed the budget together.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class RateLimiter:
    """Evenly spaces :meth:`acquire` calls so that at most ``max_per_minute`` happen per minute."""

    def __init__(self, max_per_minute: float | None, *, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        if max_per_minute is not None and max_per_minute <= 0:
            raise ValueError("max_per_minute must be positive")
        self.interval = 60.0 / max_per_minute if max_per_minute else 0.0
        self._clock = clock
        self._sleep = sleep
        self._next_slot = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> float:
        """Block until this caller's slot; return how long it waited (seconds)."""
        if not self.interval:
            return 0.0
        with self._lock:
            now = self._clock()
            slot = max(now, self._next_slot)
            self._next_slot = slot + self.interval
        wait = slot - now
        if wait > 0:
            self._sleep(wait)
        return max(wait, 0.0)


_registry: dict[float | None, RateLimiter] = {}
_registry_lock = threading.Lock()


def limiter_for(max_per_minute: float | None) -> RateLimiter:
    """The process-wide limiter for this setting (generation and judge metrics share it)."""
    with _registry_lock:
        if max_per_minute not in _registry:
            _registry[max_per_minute] = RateLimiter(max_per_minute)
        return _registry[max_per_minute]
