import hashlib
import math

import pytest
from conftest import REAL_DATASET, REAL_PDF

from rag_workbench import metrics as metrics_pkg
from rag_workbench.config import ConfigError
from rag_workbench.metrics import MetricInput, build_metrics, validate_metric_names
from rag_workbench.metrics import semantic as sem
from rag_workbench.models import RunConfig
from rag_workbench.runner import EvaluationRunner


class BagEmbedder:
    """Deterministic stand-in: hashed bag-of-words vectors, so shared words mean similar vectors."""

    def __init__(self, dim=64):
        self.dim = dim
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        out = []
        for text in texts:
            vec = [0.0] * self.dim
            for word in text.lower().split():
                vec[int(hashlib.sha256(word.encode()).hexdigest(), 16) % self.dim] += 1.0
            out.append(vec)
        return out


def metric(name, embedder=None):
    embedder = embedder or BagEmbedder()
    return sem.build_semantic_metric(name, model_name="fake", embedder_factory=lambda: embedder), embedder


def test_cosine_basics():
    assert sem.cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert sem.cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert sem.cosine([1, 0], [-1, 0]) == pytest.approx(-1.0)
    assert sem.cosine([0, 0], [1, 1]) == 0.0  # zero vector: defined as no similarity, not a division error
    assert sem.cosine([3, 4], [3, 4]) == pytest.approx(1.0) and math.isfinite(sem.cosine([1e-200, 0], [1e-200, 0]))
    with pytest.raises(ValueError, match="sizes differ"):
        sem.cosine([1], [1, 2])


def test_similarity_is_high_for_shared_words_and_low_for_unrelated():
    m, _ = metric("semantic_similarity")
    same = m.evaluate(MetricInput("q", "queens lay eggs daily", "queens lay eggs daily", []))
    other = m.evaluate(MetricInput("q", "volcanoes erupt lava", "queens lay eggs daily", []))
    assert same.status == "ok" and same.score == pytest.approx(1.0) and same.passed is True
    assert other.status == "ok" and other.score < 0.3 and other.passed is False
    assert "cosine similarity" in same.reason


def test_context_recall_uses_the_best_chunk():
    m, _ = metric("semantic_context_recall")
    result = m.evaluate(MetricInput("q", "a", "queens lay eggs daily",
                                    ["volcanoes erupt lava", "queens lay eggs daily in spring"]))
    assert result.status == "ok" and result.score > 0.8 and "chunk 2 of 2" in result.reason


def test_requirements_are_enforced_by_the_shared_wrapper():
    sim, _ = metric("semantic_similarity")
    assert sim.evaluate(MetricInput("q", "a", None, [])).status == "skipped"  # no reference
    ctx, _ = metric("semantic_context_recall")
    assert ctx.evaluate(MetricInput("q", "a", "ref", [])).status == "skipped"  # no context


def test_embedder_failure_is_an_error_result_not_a_crash():
    class Broken:
        def embed(self, texts):
            raise RuntimeError("model file corrupt")

    m, _ = metric("semantic_similarity", Broken())
    result = m.evaluate(MetricInput("q", "a", "b", []))
    assert result.status == "error" and "model file corrupt" in (result.reason or "")


def test_the_embedder_is_created_once_and_lazily():
    created = []
    embedder = BagEmbedder()
    m = sem.build_semantic_metric("semantic_similarity", model_name="x",
                                  embedder_factory=lambda: created.append(1) or embedder)
    assert created == []  # nothing loaded at construction
    for _ in range(3):
        m.evaluate(MetricInput("q", "a b", "a b", []))
    assert created == [1]


def test_selecting_a_semantic_metric_without_fastembed_is_refused(monkeypatch):
    monkeypatch.setattr(metrics_pkg, "semantic_available", lambda: False)
    with pytest.raises(ConfigError, match="fastembed"):
        validate_metric_names(["token_f1", "semantic_similarity"])


def test_full_run_with_semantic_metrics_through_the_runner(settings, store, monkeypatch):
    fake = BagEmbedder()
    monkeypatch.setattr(metrics_pkg, "semantic_available", lambda: True)
    monkeypatch.setattr(sem, "local_embedder", lambda name, cache_dir=None: fake)
    config = RunConfig(name="sem", dataset_path=str(REAL_DATASET), document_path=str(REAL_PDF),
                       metrics=["token_f1", "semantic_similarity", "semantic_context_recall"], limit=6)
    run = EvaluationRunner(settings, store).run(config)
    assert run.status == "completed"
    for name in ("semantic_similarity", "semantic_context_recall"):
        stats = run.summary.metrics[name]
        assert stats.n_scored == 6 and stats.mean is not None and 0.0 <= stats.mean <= 1.0
    assert fake.calls >= 12


def test_real_loader_refuses_without_the_package(monkeypatch):
    monkeypatch.setattr(sem, "semantic_available", lambda: False)
    with pytest.raises(ConfigError, match="uv pip install fastembed"):
        sem.FastEmbedEmbedder("any")


def test_build_metrics_wires_the_configured_model(settings, monkeypatch):
    monkeypatch.setattr(metrics_pkg, "semantic_available", lambda: True)
    seen = []
    monkeypatch.setattr(sem, "local_embedder", lambda name, cache_dir=None: seen.append(name) or BagEmbedder())
    [m] = build_metrics(["semantic_similarity"], settings.model_copy(update={"local_embedding_model": "my/model"}))
    m.evaluate(MetricInput("q", "a", "a", []))
    assert seen == ["my/model"]
