"""Text normalisation shared by BM25 retrieval, the extractive generator and lexical metrics.

All functions are deterministic and Unicode-aware (``\\w`` matches letters in any script).
"""

from __future__ import annotations

import re
import string
import unicodedata

# A compact English stop-word list. It is used only for *content-token* measures
# (BM25, groundedness, context recall); SQuAD-style F1/EM keep stop words, as in the
# original SQuAD evaluation script.
STOPWORDS: frozenset[str] = frozenset([
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "as", "at",
    "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "can", "could",
    "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from", "further", "had", "has",
    "have", "having", "he", "her", "here", "hers", "herself", "him", "himself", "his", "how", "i", "if", "in",
    "into", "is", "it", "its", "itself", "just", "me", "more", "most", "my", "myself", "no", "nor", "not",
    "now", "of", "off", "on", "once", "only", "or", "other", "our", "ours", "ourselves", "out", "over", "own",
    "same", "she", "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom", "why",
    "will", "with", "would", "you", "your", "yours", "yourself", "yourselves", "also", "may", "might", "must",
    "shall", "us",
])

# A word may contain apostrophes between letters ("queen's", "can't"); they are removed so the word stays whole.
_WORD_RE = re.compile(r"\w+(?:['’ʼ]\w+)*", re.UNICODE)
_APOSTROPHES = str.maketrans("", "", "'’ʼ")
_ARTICLES_RE = re.compile(r"\b(a|an|the)\b", re.UNICODE)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9])")
_PUNCT_TABLE = str.maketrans("", "", string.punctuation + "‘’ʼ")  # apostrophes of any style: deleted

ABSTENTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bdoes not (provide|contain) enough information\b", re.I),
    re.compile(r"\b(not|n't) (enough|sufficient) information\b", re.I),
    re.compile(r"\bcannot (be )?answer(ed)?\b", re.I),
    re.compile(r"\bno (relevant )?information\b", re.I),
)


def normalize_whitespace(text: str) -> str:
    """Collapse all runs of whitespace (including line breaks) into single spaces."""
    return " ".join(text.split())


def tokenize(text: str) -> list[str]:
    """Lower-cased word tokens after Unicode NFKC normalisation; apostrophes inside words are dropped.

    ``"The queen's cells can't wait"`` gives ``["the", "queens", "cells", "cant", "wait"]``: possessives and
    contractions stay one token instead of leaving a stray ``s`` or ``t``.
    """
    return [w.translate(_APOSTROPHES) for w in _WORD_RE.findall(unicodedata.normalize("NFKC", text).lower())]


def stem(token: str) -> str:
    """Very light, conservative suffix stripping so plural/singular forms match.

    Deliberately minimal (no Porter stemmer) to keep behaviour predictable:
    ``workers → worker``, ``colonies → colony``, ``boxes → box``; words ending in ``ss``/``us``/``is``
    are left alone (``grass``, ``status``, ``analysis``).
    """
    if len(token) <= 3 or token.isdigit():
        return token
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith(("sses", "shes", "ches", "xes", "zes")):
        return token[:-2]
    if token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def content_tokens(text: str) -> list[str]:
    """Stemmed tokens with stop words removed."""
    return [stem(t) for t in tokenize(text) if t not in STOPWORDS]


def squad_normalize(text: str) -> str:
    """SQuAD v1.1 answer normalisation (punctuation extended to Unicode): lower-case, drop punctuation and articles."""
    text = unicodedata.normalize("NFKC", text).lower().translate(_PUNCT_TABLE)
    # Also drop non-ASCII punctuation (curly quotes, dashes, ellipses), which string.punctuation does not cover.
    text = "".join(" " if unicodedata.category(ch).startswith("P") else ch for ch in text)
    text = _ARTICLES_RE.sub(" ", text)
    return normalize_whitespace(text)


def split_sentences(text: str) -> list[str]:
    """Split prose into sentences on terminal punctuation followed by a capital/digit."""
    text = normalize_whitespace(text)
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]


def is_abstention(answer: str) -> bool:
    """True when the answer declines to answer (the pipeline's 'not enough information' reply)."""
    return any(p.search(answer) for p in ABSTENTION_PATTERNS)
