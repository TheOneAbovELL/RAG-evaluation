import math
import random
from collections import Counter

import pytest

from rag_workbench.models import Chunk
from rag_workbench.retrieval import BM25_B, BM25_K1, BM25Retriever
from rag_workbench.text import content_tokens

WORDS = [
    "queen", "worker", "drone", "hive", "nectar", "pollen", "wax", "honey", "comb", "brood", "larva", "swarm", "foraging",
    "dance", "scout", "winter", "cluster", "varroa", "mite", "colony", "royal", "jelly", "propolis", "cell", "apiary",
    "frame", "super", "smoker", "veil",
]


def reference_scores(chunks, query, k1=BM25_K1, b=BM25_B):
    """The textbook definition, written the obvious way: every chunk against every query term, in order."""
    docs = [Counter(content_tokens(c.text)) for c in chunks]
    lengths = [sum(d.values()) for d in docs]
    avg = (sum(lengths) / len(chunks)) or 1.0
    df: Counter = Counter()
    for d in docs:
        df.update(d.keys())
    n = len(chunks)
    idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
    out = []
    for tokens, length in zip(docs, lengths, strict=True):
        total = 0.0
        for term in content_tokens(query):
            tf = tokens.get(term, 0)
            if not tf:
                continue
            total += idf[term] * (tf * (k1 + 1) / (tf + k1 * (1 - b + b * length / avg)))
        out.append(total)
    return out


def corpus(rng, n, empty_every=0):
    chunks = []
    for i in range(n):
        words = [] if empty_every and i % empty_every == 0 else rng.choices(WORDS, k=rng.randint(1, 40))
        chunks.append(Chunk(id=f"c{i}", text=" ".join(words) or "...", page=1, source="t"))
    return chunks


@pytest.mark.parametrize("seed", range(8))
def test_scores_are_bit_for_bit_identical_to_the_reference_definition(seed):
    rng = random.Random(seed)
    chunks = corpus(rng, rng.randint(1, 60), empty_every=7 if seed % 2 else 0)
    retriever = BM25Retriever(chunks)
    for _ in range(25):
        query = " ".join(rng.choices([*WORDS, "unseen", "absent"], k=rng.randint(1, 9)))
        assert retriever.score(query) == reference_scores(chunks, query)  # exact float equality, not approx


def test_repeated_query_terms_count_each_time_as_in_the_reference():
    chunks = [Chunk(id="a", text="queen queen honey", page=1, source="t"), Chunk(id="b", text="honey wax", page=1, source="t")]
    retriever = BM25Retriever(chunks)
    assert retriever.score("queen queen queen") == reference_scores(chunks, "queen queen queen")
    assert retriever.score("queen") != retriever.score("queen queen")


def test_custom_parameters_are_respected():
    rng = random.Random(3)
    chunks = corpus(rng, 20)
    retriever = BM25Retriever(chunks, k1=2.2, b=0.4)
    assert retriever.score("queen honey wax") == reference_scores(chunks, "queen honey wax", k1=2.2, b=0.4)


def test_query_with_no_known_terms_scores_zero_everywhere():
    retriever = BM25Retriever(corpus(random.Random(1), 10))
    assert retriever.score("zzzz qqqq") == [0.0] * 10 and retriever.score("") == [0.0] * 10


def test_ranking_and_ties_are_unchanged():
    chunks = [Chunk(id=f"c{i}", text="queen honey", page=1, source="t") for i in range(5)]  # identical chunks: a five-way tie
    hits = BM25Retriever(chunks).retrieve("queen", 3)
    assert [h.chunk_id for h in hits] == ["c0", "c1", "c2"]  # ties break by document order
