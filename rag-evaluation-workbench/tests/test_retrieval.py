import math

import pytest

from rag_workbench.models import Chunk
from rag_workbench.retrieval import BM25Retriever, EmbeddingRetriever


def make_chunks(*texts):
    return [Chunk(id=f"c{i}", text=t, page=1, source="t") for i, t in enumerate(texts, start=1)]


def test_bm25_score_matches_hand_computation():
    # Two docs; query term "nectar" appears once in doc 1 only.
    chunks = make_chunks("nectar pollen", "wax")
    r = BM25Retriever(chunks)
    n, df = 2, 1
    idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
    avg_len = (2 + 1) / 2
    tf, length = 1, 2
    expected = idf * tf * (1.5 + 1) / (tf + 1.5 * (1 - 0.75 + 0.75 * length / avg_len))
    scores = r.score("nectar")
    assert scores[0] == pytest.approx(expected)
    assert scores[1] == 0.0


def test_bm25_ranks_relevant_chunk_first(chunks):
    r = BM25Retriever(chunks)
    hits = r.retrieve("What do forager bees collect?", 2)
    assert hits[0].chunk_id == "p1-b2"
    assert [h.rank for h in hits] == [1, 2]
    assert hits[0].score >= hits[1].score


def test_bm25_is_deterministic_with_ties():
    r = BM25Retriever(make_chunks("alpha", "beta", "gamma"))
    hits = r.retrieve("unrelated words", 3)
    assert [h.chunk_id for h in hits] == ["c1", "c2", "c3"]  # all zero: document order


def test_k_larger_than_corpus_and_invalid_k(chunks):
    r = BM25Retriever(chunks)
    assert len(r.retrieve("bees", 50)) == len(chunks)
    with pytest.raises(ValueError):
        r.retrieve("bees", 0)
    with pytest.raises(ValueError):
        BM25Retriever([])


def test_embedding_retriever_is_lazy_and_maps_ids(monkeypatch, chunks):
    from langchain_core.embeddings import DeterministicFakeEmbedding

    created = []

    def fake_embeddings(**kwargs):
        created.append(kwargs)
        return DeterministicFakeEmbedding(size=16)

    monkeypatch.setattr("langchain_openai.OpenAIEmbeddings", fake_embeddings)
    r = EmbeddingRetriever(chunks, model="m", api_key="sk-test")
    assert created == []  # nothing built at construction time
    hits = r.retrieve(chunks[2].text, 2)
    assert len(created) == 1 and created[0]["model"] == "m"
    assert hits[0].chunk_id == "p1-b3"  # identical text embeds identically
    assert {h.chunk_id for h in hits} <= {c.id for c in chunks}
    r.retrieve("again", 1)
    assert len(created) == 1  # index reused


def test_embedding_errors_are_classified_for_retry(monkeypatch, chunks):
    import httpx
    import openai

    from rag_workbench.errors import TransientProviderError

    class FailingEmbeddings:
        def __init__(self, **kwargs):
            pass

        def embed_documents(self, texts):
            raise openai.RateLimitError("slow down", body=None,
                                        response=httpx.Response(429, request=httpx.Request("POST", "https://x")))

    monkeypatch.setattr("langchain_openai.OpenAIEmbeddings", FailingEmbeddings)
    with pytest.raises(TransientProviderError, match="RateLimitError"):
        EmbeddingRetriever(chunks, model="m", api_key="sk-test").retrieve("q", 1)


def test_real_client_classes_accept_the_parameters_we_pass(chunks):
    """Construct the real LangChain OpenAI clients (no request is made) to catch parameter-name drift."""
    retriever = EmbeddingRetriever(chunks, model="text-embedding-3-large", api_key="sk-not-a-real-key-for-tests",
                                   base_url="http://localhost:9", timeout_s=7, max_retries=1)
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from pydantic import SecretStr

    embeddings = OpenAIEmbeddings(model=retriever.model, api_key=SecretStr("sk-not-a-real-key-for-tests"),
                                  base_url="http://localhost:9", timeout=7, max_retries=1)
    assert embeddings.request_timeout == 7 and embeddings.max_retries == 1
    chat = ChatOpenAI(model="gpt-4o", temperature=0, api_key=SecretStr("sk-not-a-real-key-for-tests"),
                      base_url="http://localhost:9", timeout=7, max_retries=0)
    assert chat.request_timeout == 7 and chat.max_retries == 0
