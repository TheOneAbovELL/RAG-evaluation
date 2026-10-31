import itertools
import threading
import time

import pytest

from rag_workbench.config import load_settings
from rag_workbench.metrics.base import MetricInput, MetricSpec
from rag_workbench.metrics.judge import JudgeMetric
from rag_workbench.ratelimit import RateLimiter, limiter_for


class FakeClock:
    def __init__(self):
        self.now = 100.0
        self.sleeps: list[float] = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def limiter(per_minute):
    clock = FakeClock()
    return RateLimiter(per_minute, clock=clock, sleep=clock.sleep), clock


def test_no_limit_never_waits():
    lim, clock = limiter(None)
    assert [lim.acquire() for _ in range(5)] == [0.0] * 5 and clock.sleeps == []


def test_calls_are_spaced_evenly():
    lim, clock = limiter(30)  # one every 2 seconds
    waits = [lim.acquire() for _ in range(4)]
    assert waits == [0.0, 2.0, 2.0, 2.0] and clock.sleeps == [2.0, 2.0, 2.0]


def test_idle_time_does_not_bank_a_burst():
    lim, clock = limiter(60)  # one per second
    lim.acquire()
    clock.now += 30  # a long idle period
    assert lim.acquire() == 0.0  # the first call after idling is free...
    assert lim.acquire() == pytest.approx(1.0)  # ...but there is no burst of 30 allowed calls


def test_invalid_limits_are_rejected():
    with pytest.raises(ValueError, match="positive"):
        RateLimiter(0)
    with pytest.raises(ValueError, match="positive"):
        RateLimiter(-5)


def test_threads_share_one_budget():
    lim = RateLimiter(60_000)  # one per millisecond: real time, but quick
    stamps: list[float] = []
    lock = threading.Lock()

    def worker():
        for _ in range(10):
            lim.acquire()
            with lock:
                stamps.append(time.monotonic())

    threads = [threading.Thread(target=worker) for _ in range(4)]
    start = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.monotonic() - start
    assert len(stamps) == 40 and elapsed >= 0.035  # 40 operations cannot finish faster than ~39 intervals


def test_limiter_for_returns_one_shared_instance_per_setting():
    assert limiter_for(12.5) is limiter_for(12.5)
    assert limiter_for(12.5) is not limiter_for(25.0)
    assert limiter_for(None).acquire() == 0.0


def test_setting_is_read_from_the_environment_and_validated():
    assert load_settings({"RAGWB_MAX_REQUESTS_PER_MINUTE": "20"}, dotenv=False).max_requests_per_minute == 20
    assert load_settings({}, dotenv=False).max_requests_per_minute is None
    from rag_workbench.config import ConfigError

    with pytest.raises(ConfigError, match="RAGWB_MAX_REQUESTS_PER_MINUTE"):
        load_settings({"RAGWB_MAX_REQUESTS_PER_MINUTE": "0"}, dotenv=False)


def test_judge_metric_waits_for_its_slot_before_each_measurement():
    lim, clock = limiter(30)
    calls: list[float] = []

    class Counted(JudgeMetric):
        def _measure(self, inp, threshold):
            calls.append(clock.now)
            return 0.9, "ok", None

    metric = Counted(MetricSpec("m", "M", "llm_judge", "d", 0.7), lambda t: None, limiter=lim)
    for _ in range(3):
        assert metric.evaluate(MetricInput("q", "a", "r", ["c"])).status == "ok"
    assert [round(b - a, 1) for a, b in itertools.pairwise(calls)] == [2.0, 2.0]
