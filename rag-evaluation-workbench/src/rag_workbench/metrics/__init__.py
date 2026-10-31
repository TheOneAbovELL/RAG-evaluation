"""Metric registry: lexical (offline) and LLM-judge (DeepEval, OpenAI) metrics."""

from __future__ import annotations

from ..config import ConfigError, Settings
from .base import Metric, MetricInput, MetricSkipped, MetricSpec
from .judge import JUDGE_SPECS, build_judge_metric
from .lexical import LEXICAL_METRICS
from .semantic import INSTALL_HINT, SEMANTIC_SPECS, build_semantic_metric, semantic_available

METRIC_SPECS: dict[str, MetricSpec] = {**{n: m.spec for n, m in LEXICAL_METRICS.items()}, **SEMANTIC_SPECS,
                                       **JUDGE_SPECS}

DEFAULT_OFFLINE_METRICS = ["token_f1", "rouge_l", "context_recall", "groundedness"]
DEFAULT_JUDGE_METRICS = list(JUDGE_SPECS)


def validate_metric_names(names: list[str], settings: Settings | None = None) -> None:
    """Raise :class:`ConfigError` for unknown metrics, or judge metrics without an API key."""
    unknown = [n for n in names if n not in METRIC_SPECS]
    if unknown:
        raise ConfigError(f"Unknown metric(s): {', '.join(unknown)}. Available: {', '.join(METRIC_SPECS)}")
    if not names:
        raise ConfigError("Select at least one metric")
    local = [n for n in names if METRIC_SPECS[n].requires_local_model]
    if local and not semantic_available():
        raise ConfigError(f"Metric(s) {', '.join(local)} are unavailable. {INSTALL_HINT}")
    if settings is not None and not settings.has_openai_key:
        judges = [n for n in names if METRIC_SPECS[n].requires_openai]
        if judges:
            raise ConfigError(f"Metric(s) {', '.join(judges)} use an OpenAI judge model and need OPENAI_API_KEY.")


def build_metrics(names: list[str], settings: Settings, *, judge_model: str | None = None,
                  timeout_s: float | None = None, max_retries: int | None = None) -> list[Metric]:
    validate_metric_names(names, settings)
    metrics: list[Metric] = []
    for name in names:
        if name in LEXICAL_METRICS:
            metrics.append(LEXICAL_METRICS[name])
        elif name in SEMANTIC_SPECS:
            metrics.append(build_semantic_metric(name, model_name=settings.local_embedding_model,
                                                   cache_dir=str(settings.local_model_dir)))
        else:
            metrics.append(build_judge_metric(
                name, model=judge_model or settings.judge_model, api_key=settings.require_openai_key(),
                base_url=settings.openai_base_url, timeout_s=timeout_s or settings.request_timeout_s,
                max_retries=settings.max_retries if max_retries is None else max_retries,
                retry_base_delay_s=settings.retry_base_delay_s,
                max_requests_per_minute=settings.max_requests_per_minute))
    return metrics


__all__ = [
    "DEFAULT_JUDGE_METRICS", "DEFAULT_OFFLINE_METRICS", "METRIC_SPECS", "Metric", "MetricInput", "MetricSkipped",
    "MetricSpec", "build_metrics", "validate_metric_names",
]
