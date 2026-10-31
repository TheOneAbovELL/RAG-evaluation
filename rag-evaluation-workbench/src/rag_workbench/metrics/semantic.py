"""Optional offline semantic metrics, computed with a local sentence-embedding model.

Lexical metrics reward shared words, so a correct paraphrase can score low. These two metrics compare *meaning* with
embeddings instead, still without any API call:

``semantic_similarity``      cosine similarity between the answer and the reference answer;
``semantic_context_recall``  the best cosine similarity between the reference answer and any retrieved chunk
                             (did retrieval bring back text that says what the reference says?).

They are **optional** because they need a model the base install does not contain. Install the ``fastembed`` package
(``uv pip install fastembed``); the first use downloads the configured model (``RAGWB_LOCAL_EMBEDDING_MODEL``,
default ``BAAI/bge-small-en-v1.5``) from its public hub. Only the model is fetched; no project data leaves the
machine. Without the package, the metrics are listed as unavailable and selecting one is refused with that hint.

Honest limits: cosine similarity of sentence embeddings is a graded, model-dependent proxy. Related-but-wrong text
scores high (a sentence about the right topic with the wrong number), and the scale differs between models, so the
0.7 default threshold is a starting point to calibrate against human labels (``ragwb calibrate``), not a
standard. The metric code is tested here with a deterministic stand-in embedder; it has not been run against a real
model in this project's environment.
"""

from __future__ import annotations

import importlib.util
import math
import threading
from collections.abc import Callable, Sequence
from functools import lru_cache
from typing import Protocol

from ..config import ConfigError
from .base import Metric, MetricInput, MetricSpec

INSTALL_HINT = (
    "The semantic metrics and local retrievers need the optional 'fastembed' package: run "
    "`uv sync --extra semantic` (or `uv pip install fastembed`); the first use then downloads the embedding model.")


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


def semantic_available() -> bool:
    return importlib.util.find_spec("fastembed") is not None


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity in [-1, 1]; 0.0 when either vector is all zeros."""
    if len(a) != len(b):
        raise ValueError(f"embedding sizes differ ({len(a)} vs {len(b)})")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class FastEmbedEmbedder:
    """The real embedder: a local ONNX model through ``fastembed`` (imported lazily)."""

    def __init__(self, model_name: str, cache_dir: str | None = None):
        if not semantic_available():
            raise ConfigError(INSTALL_HINT)
        from fastembed import TextEmbedding

        # cache_dir keeps the downloaded model inside the project's data folder instead of a system temp folder.
        self._model = TextEmbedding(model_name=model_name, cache_dir=cache_dir)
        self._lock = threading.Lock()  # one ONNX session shared by the worker threads

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        with self._lock:
            return [[float(x) for x in vector] for vector in self._model.embed(list(texts))]


@lru_cache(maxsize=2)
def local_embedder(model_name: str, cache_dir: str | None = None) -> Embedder:
    return FastEmbedEmbedder(model_name, cache_dir)


class SemanticMetric(Metric):
    """A metric that scores with embeddings. ``embedder_factory`` is called once, on first use."""

    def __init__(self, spec: MetricSpec, kind: str, embedder_factory: Callable[[], Embedder]):
        super().__init__(spec)
        self._kind = kind
        self._factory = embedder_factory
        self._embedder: Embedder | None = None
        self._lock = threading.Lock()

    def _get_embedder(self) -> Embedder:
        with self._lock:
            if self._embedder is None:
                self._embedder = self._factory()
            return self._embedder

    def score(self, inp: MetricInput, threshold: float) -> tuple[float, str]:
        embedder = self._get_embedder()
        reference = inp.expected_answer or ""
        if self._kind == "similarity":
            answer_vec, reference_vec = embedder.embed([inp.answer, reference])
            cos = cosine(answer_vec, reference_vec)
            return max(0.0, min(1.0, cos)), f"cosine similarity {cos:.3f} between answer and reference"
        vectors = embedder.embed([reference, *inp.contexts])
        sims = [cosine(vectors[0], v) for v in vectors[1:]]
        best = max(range(len(sims)), key=sims.__getitem__)
        return max(0.0, min(1.0, sims[best])), (
            f"best cosine {sims[best]:.3f} with retrieved chunk {best + 1} of {len(sims)}")


SEMANTIC_SPECS: dict[str, MetricSpec] = {
    "semantic_similarity": MetricSpec(
        "semantic_similarity", "Semantic similarity (local model)", "semantic",
        "Embedding cosine similarity between answer and reference (optional, needs fastembed)", 0.7,
        requires_reference=True, requires_local_model=True),
    "semantic_context_recall": MetricSpec(
        "semantic_context_recall", "Semantic context recall (local model)", "semantic",
        "Best embedding similarity between the reference and any retrieved chunk (optional, needs fastembed)", 0.7,
        requires_reference=True, requires_context=True, requires_local_model=True),
}


def local_model_error(model_name: str, cache_dir: str | None, exc: BaseException) -> ConfigError:
    """One clear message for a model that cannot be loaded (usually: not downloaded yet and no network)."""
    where = cache_dir or "the fastembed cache"
    return ConfigError(
        f"The local embedding model {model_name!r} could not be loaded ({type(exc).__name__}: {str(exc)[:200]}). "
        f"The first use downloads it (about 70 MB, needs network access once) into {where}; "
        "after that it works offline. Check the network or pre-download the model "
        "(see Local embeddings in BUILD_AND_RUN.md).")



def build_semantic_metric(name: str, *, model_name: str, embedder_factory: Callable[[], Embedder] | None = None,
                          cache_dir: str | None = None) -> SemanticMetric:
    kind = "similarity" if name == "semantic_similarity" else "context"
    if embedder_factory is None:
        # Load now, so a model that cannot be loaded stops the run before any case, not after a timeout per case.
        try:
            embedder = local_embedder(model_name, cache_dir)
        except ConfigError:
            raise
        except Exception as exc:
            raise local_model_error(model_name, cache_dir, exc) from exc
        embedder_factory = lambda: embedder  # noqa: E731
    return SemanticMetric(SEMANTIC_SPECS[name], kind, embedder_factory)
