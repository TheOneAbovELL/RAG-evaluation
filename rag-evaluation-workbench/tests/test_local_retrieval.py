import hashlib
import os

import pytest
from conftest import REAL_DATASET, REAL_PDF

from rag_workbench import metrics as metrics_pkg
from rag_workbench import pipeline as pipeline_mod
from rag_workbench.config import ConfigError
from rag_workbench.documents import load_chunks
from rag_workbench.metrics import semantic as sem
from rag_workbench.models import RunConfig
from rag_workbench.pipeline import build_pipeline, build_retriever
from rag_workbench.retrieval import BM25Retriever, HybridRetriever, LocalEmbeddingRetriever
from rag_workbench.runner import EvaluationRunner


class BagEmbedder:
    """Deterministic hashed bag-of-words vectors: shared words mean similar vectors."""

    def __init__(self, dim=128):
        self.dim = dim
        self.batches = 0

    def embed(self, texts):
        self.batches += 1
        out = []
        for text in texts:
            vec = [0.0] * self.dim
            for word in text.lower().split():
                vec[int(hashlib.sha256(word.encode()).hexdigest(), 16) % self.dim] += 1.0
            out.append(vec)
        return out


@pytest.fixture
def chunks():
    return load_chunks(REAL_PDF)


def test_local_retriever_ranks_by_similarity_and_is_deterministic(chunks):
    retriever = LocalEmbeddingRetriever(chunks, model="fake", embedder_factory=BagEmbedder)
    first = retriever.retrieve("How many eggs does the queen lay each day?", 3)
    assert [r.rank for r in first] == [1, 2, 3]
    assert first == retriever.retrieve("How many eggs does the queen lay each day?", 3)
    assert first[0].score >= first[1].score >= first[2].score
    assert "queen" in first[0].text.lower()


def test_the_index_is_built_once_and_lazily(chunks):
    embedder = BagEmbedder()
    built = []
    retriever = LocalEmbeddingRetriever(chunks, model="fake", embedder_factory=lambda: built.append(1) or embedder)
    assert built == [] and embedder.batches == 0  # constructing loads nothing
    retriever.retrieve("queen", 2)
    retriever.retrieve("varroa mites", 2)
    assert built == [1]
    assert embedder.batches == 3  # one batch for the chunks, one per query


def test_local_retriever_validates_its_inputs(chunks):
    with pytest.raises(ValueError, match="at least one chunk"):
        LocalEmbeddingRetriever([], model="fake", embedder_factory=BagEmbedder)
    with pytest.raises(ValueError, match="k must be"):
        LocalEmbeddingRetriever(chunks, model="fake", embedder_factory=BagEmbedder).retrieve("q", 0)


def test_pipeline_builds_local_and_hybrid_local_without_any_key(settings, chunks, monkeypatch):
    monkeypatch.setattr(pipeline_mod, "semantic_available", lambda: True)
    monkeypatch.setattr(pipeline_mod, "local_embedder", lambda name, cache_dir=None: BagEmbedder())
    base = {"name": "t", "dataset_path": str(REAL_DATASET), "document_path": str(REAL_PDF), "metrics": ["token_f1"]}
    assert not settings.has_openai_key
    local = build_retriever(RunConfig(retriever="local", **base), chunks, settings)
    hybrid = build_retriever(RunConfig(retriever="hybrid-local", **base), chunks, settings)
    assert isinstance(local, LocalEmbeddingRetriever)
    assert isinstance(hybrid, HybridRetriever) and isinstance(hybrid.lexical, BM25Retriever)
    assert isinstance(hybrid.dense, LocalEmbeddingRetriever)
    pipe = build_pipeline(RunConfig(retriever="hybrid-local", **base), settings)
    assert pipe.answer("What do queens do?").contexts


def test_local_retrievers_are_refused_with_an_install_hint_when_the_package_is_missing(settings, chunks, monkeypatch):
    monkeypatch.setattr(pipeline_mod, "semantic_available", lambda: False)
    config = RunConfig(name="t", dataset_path=str(REAL_DATASET), document_path=str(REAL_PDF), retriever="local",
                       metrics=["token_f1"])
    with pytest.raises(ConfigError, match="fastembed"):
        build_retriever(config, chunks, settings)


def test_full_offline_run_with_hybrid_local_retrieval(settings, store, monkeypatch):
    monkeypatch.setattr(pipeline_mod, "semantic_available", lambda: True)
    monkeypatch.setattr(pipeline_mod, "local_embedder", lambda name, cache_dir=None: BagEmbedder())
    config = RunConfig(name="hl", dataset_path=str(REAL_DATASET), document_path=str(REAL_PDF), retriever="hybrid-local",
                       k=3, metrics=["token_f1", "context_recall"], limit=8, embedding_model="fake")
    run = EvaluationRunner(settings, store).run(config)
    assert run.status == "completed" and run.summary.n_error == 0
    assert run.config["retriever"] == "hybrid-local" and run.summary.metrics["context_recall"].n_scored == 8


def test_model_cache_lives_under_the_data_dir(settings):
    assert settings.local_model_dir == settings.data_dir / "models"


# Real model: only when explicitly enabled, because the first use downloads about 70 MB.
@pytest.mark.skipif(os.environ.get("RAGWB_MODEL_TESTS") != "1" or not sem.semantic_available(),
                    reason="set RAGWB_MODEL_TESTS=1 (and install fastembed) to run tests with the real local model")
def test_real_model_ranks_a_paraphrase_above_an_unrelated_sentence(tmp_path):
    embedder = sem.FastEmbedEmbedder("BAAI/bge-small-en-v1.5", cache_dir=str(tmp_path / "models"))
    a, b, c = embedder.embed(["Queens lay eggs daily.", "A queen bee lays many eggs each day.", "Volcanoes erupt lava."])
    assert sem.cosine(a, b) > sem.cosine(a, c) + 0.2 and len(a) == 384


def test_metrics_package_exports_still_resolve():
    assert callable(metrics_pkg.build_metrics)
