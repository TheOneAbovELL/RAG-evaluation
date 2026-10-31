"""Data contracts shared by every layer (pipeline, metrics, storage, UI)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from .config import PipelineMode, ProviderName, RetrieverName

RunStatus = Literal["running", "completed", "partial", "failed", "cancelled", "interrupted", "imported"]
CaseStatus = Literal["ok", "error"]
MetricStatus = Literal["ok", "skipped", "error"]
ContextSource = Literal["retriever", "agent_tool"]


def utcnow() -> datetime:
    return datetime.now(UTC)


class EvalCase(BaseModel):
    """One dataset row: a question, an optional reference answer and free-form metadata."""

    id: str
    question: str
    expected_answer: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    """A unit of the source document that can be retrieved."""

    id: str
    text: str
    page: int
    source: str


class RetrievedChunk(BaseModel):
    """A chunk returned by a retriever for one query, with its score and 1-based rank."""

    chunk_id: str
    text: str
    page: int
    score: float
    rank: int


class Generation(BaseModel):
    """What a pipeline produced for one question."""

    answer: str
    contexts: list[RetrievedChunk]
    context_source: ContextSource = "retriever"
    model: str
    latency_ms: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    retrieval_queries: list[str] = Field(default_factory=list)
    model_context_claim: str | None = None  # the agent's self-reported context, kept for audit only

    @property
    def total_tokens(self) -> int | None:
        if self.prompt_tokens is None and self.completion_tokens is None:
            return None
        return (self.prompt_tokens or 0) + (self.completion_tokens or 0)


class MetricResult(BaseModel):
    """Outcome of one metric on one case. ``score`` is None unless ``status == 'ok'``."""

    name: str
    status: MetricStatus
    score: float | None = None
    threshold: float | None = None
    passed: bool | None = None
    reason: str | None = None
    cost_usd: float | None = None  # judge-model cost reported by the metric library, when available

    @field_validator("score")
    @classmethod
    def _bounded(cls, value: float | None) -> float | None:
        if value is not None and not 0.0 <= value <= 1.0:
            raise ValueError(f"metric score {value} outside [0, 1]")
        return value


class CaseResult(BaseModel):
    """Everything recorded for one dataset case within a run."""

    case_id: str
    position: int
    question: str
    expected_answer: str | None
    status: CaseStatus
    metadata: dict[str, Any] = Field(default_factory=dict)  # the dataset row's metadata, for per-slice summaries
    answer: str | None = None
    contexts: list[RetrievedChunk] = Field(default_factory=list)
    context_source: ContextSource | None = None
    latency_ms: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None
    attempts: int = 1
    error: str | None = None
    metrics: dict[str, MetricResult] = Field(default_factory=dict)

    def score(self, metric: str) -> float | None:
        result = self.metrics.get(metric)
        return result.score if result else None


class RunConfig(BaseModel):
    """Everything needed to reproduce a run. Contains no secrets."""

    started_by: str | None = Field(default=None, max_length=64)  # signed-in user who started it (web app)

    name: str = Field(min_length=1, max_length=120)
    dataset_path: str
    document_path: str
    provider: ProviderName = "offline"
    pipeline: PipelineMode = "rag"
    retriever: RetrieverName = "bm25"
    k: int = Field(default=3, ge=1, le=50)
    metrics: list[str] = Field(min_length=1)
    thresholds: dict[str, float] = Field(default_factory=dict)
    generator_model: str | None = None
    embedding_model: str | None = None
    judge_model: str | None = None
    max_workers: int = Field(default=1, ge=1, le=32)
    max_retries: int = Field(default=3, ge=0, le=10)
    request_timeout_s: float = Field(default=60.0, gt=0)
    case_timeout_s: float = Field(default=600.0, gt=0)  # wall-clock limit for one case (generation + scoring)
    max_answer_sentences: int = Field(default=2, ge=1, le=10)
    min_evidence: float = Field(default=0.0, ge=0.0, le=1.0)  # extractive baseline: abstain below this evidence share
    skip_headings: bool = False  # drop heading-like blocks (e.g. the document title) from the retrievable chunks
    limit: int | None = Field(default=None, ge=1)
    notes: str | None = None
    # Failure injection for the offline provider (exercising error handling in demos/tests).
    offline_failure_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    seed: int = 0

    @field_validator("metrics")
    @classmethod
    def _unique_metrics(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("metrics must not contain duplicates")
        return value


class MetricSummary(BaseModel):
    """Aggregate of one metric across a run's cases."""

    name: str
    n_scored: int
    n_skipped: int
    n_error: int
    mean: float | None
    median: float | None
    std: float | None
    min: float | None
    max: float | None
    ci_low: float | None
    ci_high: float | None
    threshold: float | None
    n_passed: int
    pass_rate: float | None


class RunSummary(BaseModel):
    n_cases: int
    n_ok: int
    n_error: int
    metrics: dict[str, MetricSummary]
    mean_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    total_prompt_tokens: int | None = None
    total_completion_tokens: int | None = None
    total_cost_usd: float | None = None
    total_judge_cost_usd: float | None = None


class RunRecord(BaseModel):
    id: str
    name: str
    status: RunStatus
    created_at: datetime
    finished_at: datetime | None = None
    config: dict[str, Any]
    dataset_sha256: str | None = None
    document_sha256: str | None = None
    n_cases: int = 0
    summary: RunSummary | None = None
    environment: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
