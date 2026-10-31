"""Retrievers: map a query to the top-k document chunks.

* :class:`BM25Retriever` — Okapi BM25 over content tokens. Fully offline and deterministic.
* :class:`EmbeddingRetriever` — OpenAI embeddings + LangChain ``InMemoryVectorStore`` (cosine
  similarity). The index is built lazily on the
  first query, so constructing the object never calls the API.
* :class:`LocalEmbeddingRetriever` — the same idea with a local sentence-embedding model (no API, no key). Also lazy.
* :class:`HybridRetriever` — reciprocal-rank fusion of BM25 with either dense retriever.
"""

from __future__ import annotations

import math
import threading
from collections import Counter
from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

from pydantic import SecretStr

from .errors import classify_openai_error
from .metrics.semantic import Embedder, cosine
from .models import Chunk, RetrievedChunk
from .text import content_tokens

if TYPE_CHECKING:
    from langchain_core.vectorstores import InMemoryVectorStore

# Standard Okapi BM25 parameters (Robertson & Zaragoza, 2009).
BM25_K1 = 1.5
BM25_B = 0.75


class Retriever(Protocol):
    name: str

    def retrieve(self, query: str, k: int) -> list[RetrievedChunk]: ...


class BM25Retriever:
    """Okapi BM25 with the non-negative IDF variant ``ln(1 + (N - n + 0.5) / (n + 0.5))``."""

    name = "bm25"

    def __init__(self, chunks: list[Chunk], *, k1: float = BM25_K1, b: float = BM25_B):
        if not chunks:
            raise ValueError("BM25Retriever needs at least one chunk")
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        doc_tokens = [Counter(content_tokens(c.text)) for c in chunks]
        self._doc_len = [sum(t.values()) for t in doc_tokens]
        self._avg_len = (sum(self._doc_len) / len(chunks)) or 1.0
        # Inverted index: term -> [(chunk index, term frequency)], so a query touches only the chunks that contain
        # one of its terms instead of every chunk. Per-chunk length normalisation is computed once.
        self._postings: dict[str, list[tuple[int, int]]] = {}
        for index, tokens in enumerate(doc_tokens):
            for term, tf in tokens.items():
                self._postings.setdefault(term, []).append((index, tf))
        self._len_norm = [k1 * (1 - b + b * length / self._avg_len) for length in self._doc_len]
        n = len(chunks)
        self.idf = {term: math.log(1 + (n - len(postings) + 0.5) / (len(postings) + 0.5))
                    for term, postings in self._postings.items()}

    def score(self, query: str) -> list[float]:
        """BM25 score of every chunk for ``query`` (0.0 for chunks sharing no term with it).

        Terms are accumulated in query order, chunk by chunk, so the floating-point sums are identical to scoring each
        chunk against the whole query in turn (the straightforward definition used as the reference in the tests).
        """
        scores = [0.0] * len(self.chunks)
        for term in content_tokens(query):
            postings = self._postings.get(term)
            if not postings:
                continue
            idf = self.idf[term]
            for index, tf in postings:
                scores[index] += idf * (tf * (self.k1 + 1) / (tf + self._len_norm[index]))
        return scores

    def retrieve(self, query: str, k: int) -> list[RetrievedChunk]:
        if k < 1:
            raise ValueError("k must be >= 1")
        scores = self.score(query)
        # Ties broken by document order so results are fully deterministic.
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))[:k]
        return [
            RetrievedChunk(chunk_id=self.chunks[i].id, text=self.chunks[i].text, page=self.chunks[i].page,
                           score=round(scores[i], 6), rank=rank)
            for rank, i in enumerate(order, start=1)
        ]


class HybridRetriever:
    """Fuses a lexical and a dense retriever with reciprocal rank fusion (RRF).

    Each retriever contributes ``1 / (rrf_k + rank)`` for every chunk it returns in its top ``pool`` results; the
    chunk's fused score is the sum, so a chunk both retrievers like outranks one only a single retriever likes,
    without having to compare BM25 scores with cosine similarities (Cormack, Clarke & Buettcher, 2009).
    """

    name = "hybrid"

    def __init__(self, lexical: Retriever, dense: Retriever, *, rrf_k: int = 60, pool_factor: int = 3):
        if rrf_k < 1 or pool_factor < 1:
            raise ValueError("rrf_k and pool_factor must be >= 1")
        self.lexical, self.dense = lexical, dense
        self.rrf_k, self.pool_factor = rrf_k, pool_factor

    def retrieve(self, query: str, k: int) -> list[RetrievedChunk]:
        if k < 1:
            raise ValueError("k must be >= 1")
        pool = max(k * self.pool_factor, 10)
        fused: dict[str, float] = {}
        best: dict[str, RetrievedChunk] = {}
        first_seen: dict[str, int] = {}
        for retriever in (self.lexical, self.dense):
            for hit in retriever.retrieve(query, pool):
                fused[hit.chunk_id] = fused.get(hit.chunk_id, 0.0) + 1.0 / (self.rrf_k + hit.rank)
                best.setdefault(hit.chunk_id, hit)
                first_seen.setdefault(hit.chunk_id, len(first_seen))
        order = sorted(fused, key=lambda cid: (-fused[cid], first_seen[cid]))[:k]
        return [RetrievedChunk(chunk_id=cid, text=best[cid].text, page=best[cid].page, score=round(fused[cid], 6),
                               rank=rank) for rank, cid in enumerate(order, start=1)]


class EmbeddingRetriever:
    """Dense retrieval with OpenAI embeddings. Requires ``OPENAI_API_KEY``."""

    name = "embedding"

    def __init__(self, chunks: list[Chunk], *, model: str, api_key: str, base_url: str | None = None,
                 timeout_s: float = 60.0, max_retries: int = 3):
        if not chunks:
            raise ValueError("EmbeddingRetriever needs at least one chunk")
        self.chunks = chunks
        self.model = model
        self._api_key = api_key
        self._base_url = base_url
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._store: InMemoryVectorStore | None = None
        self._lock = threading.Lock()
        self._by_id = {c.id: c for c in chunks}

    def _ensure_index(self) -> InMemoryVectorStore:
        with self._lock:
            if self._store is None:
                from langchain_core.vectorstores import InMemoryVectorStore
                from langchain_openai import OpenAIEmbeddings

                # `api_key`, `base_url` and `timeout` are the client's public parameter names (aliases).
                embeddings = OpenAIEmbeddings(model=self.model, api_key=SecretStr(self._api_key),
                                              base_url=self._base_url, timeout=self._timeout_s,
                                              max_retries=self._max_retries)
                store = InMemoryVectorStore(embeddings)
                store.add_texts([c.text for c in self.chunks], metadatas=[{"chunk_id": c.id} for c in self.chunks],
                                ids=[c.id for c in self.chunks])
                self._store = store
            return self._store

    def retrieve(self, query: str, k: int) -> list[RetrievedChunk]:
        if k < 1:
            raise ValueError("k must be >= 1")
        try:  # index build and query both call the embeddings API
            store = self._ensure_index()
            hits = store.similarity_search_with_score(query, k=k)
        except Exception as exc:
            mapped = classify_openai_error(exc)  # rate limits / timeouts become retryable for the runner
            if mapped is not None:
                raise mapped from exc
            raise
        results = []
        for rank, (doc, score) in enumerate(hits, start=1):
            chunk = self._by_id[doc.metadata["chunk_id"]]
            results.append(RetrievedChunk(chunk_id=chunk.id, text=chunk.text, page=chunk.page,
                                          score=round(float(score), 6), rank=rank))
        return results


class LocalEmbeddingRetriever:
    """Dense retrieval with a local embedding model: cosine similarity between the query and every chunk.

    The chunk vectors are computed once, on the first query (constructing the object loads nothing). Ties go to the
    earlier chunk, so results are deterministic for a given model.
    """

    name = "local"

    def __init__(self, chunks: list[Chunk], *, model: str, embedder_factory: Callable[[], Embedder]):
        if not chunks:
            raise ValueError("LocalEmbeddingRetriever needs at least one chunk")
        self.chunks = chunks
        self.model = model
        self._factory = embedder_factory
        self._embedder: Embedder | None = None
        self._vectors: list[list[float]] | None = None
        self._lock = threading.Lock()

    def _index(self) -> tuple[Embedder, list[list[float]]]:
        with self._lock:
            if self._embedder is None or self._vectors is None:
                embedder = self._factory()
                self._vectors = embedder.embed([c.text for c in self.chunks])
                self._embedder = embedder
            return self._embedder, self._vectors

    def retrieve(self, query: str, k: int) -> list[RetrievedChunk]:
        if k < 1:
            raise ValueError("k must be >= 1")
        embedder, vectors = self._index()
        [query_vector] = embedder.embed([query])
        scored = sorted(((cosine(query_vector, v), i) for i, v in enumerate(vectors)), key=lambda t: (-t[0], t[1]))
        return [RetrievedChunk(chunk_id=self.chunks[i].id, text=self.chunks[i].text, page=self.chunks[i].page,
                               score=round(score, 6), rank=rank)
                for rank, (score, i) in enumerate(scored[:k], start=1)]
