"""Answer generators: turn a question plus retrieved passages into an answer.

* :class:`ExtractiveGenerator` — offline, deterministic baseline. It is *not* a language model:
  it returns the passage sentences that best match the question (IDF-weighted term overlap), or the
  standard abstention answer when no sentence shares a content term with the question. It exists so
  the whole system can be run and tested without network access or cost, and as a lower-bound
  baseline against which LLM pipelines can be compared.
* :class:`OpenAIChatGenerator` — an OpenAI chat model via LangChain, temperature 0.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Protocol

from pydantic import SecretStr

from .errors import ProviderError, classify_openai_error
from .prompts import ABSTAIN_ANSWER, RAG_SYSTEM_PROMPT, rag_user_prompt
from .text import content_tokens, split_sentences


@dataclass
class GeneratorOutput:
    answer: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class Generator(Protocol):
    model: str

    def generate(self, question: str, passages: list[str]) -> GeneratorOutput: ...


class ExtractiveGenerator:
    """Selects up to ``max_sentences`` best-matching sentences, kept in their original order.

    ``min_evidence`` (0 to 1, default 0 = off) makes the baseline able to abstain: the selected sentences must
    together contain at least that share of the question's content terms, weighted by inverse document frequency,
    otherwise the abstention sentence is returned. It is a crude proxy for "the passages answer this question".
    """

    model = "offline-extractive"

    def __init__(self, idf: dict[str, float], *, max_sentences: int = 2, failure_rate: float = 0.0,
                 seed: int = 0, min_evidence: float = 0.0):
        if max_sentences < 1:
            raise ValueError("max_sentences must be >= 1")
        if not 0.0 <= min_evidence <= 1.0:
            raise ValueError("min_evidence must be between 0 and 1")
        self.min_evidence = min_evidence
        self.idf = idf
        self.default_idf = max(idf.values(), default=1.0)  # unseen terms are treated as rare
        self.max_sentences = max_sentences
        self.failure_rate = failure_rate
        self.seed = seed

    def _maybe_fail(self, question: str) -> None:
        if self.failure_rate <= 0:
            return
        # Deterministic per (seed, question) so a rerun fails on the same cases. Raised as a
        # non-transient error: retrying a deterministic failure would only add back-off delay.
        if random.Random(f"{self.seed}:{question}").random() < self.failure_rate:
            raise ProviderError("Injected offline failure (offline_failure_rate > 0)")

    def generate(self, question: str, passages: list[str]) -> GeneratorOutput:
        self._maybe_fail(question)
        q_terms = set(content_tokens(question))
        candidates: list[tuple[float, int, str, set[str]]] = []
        order = 0
        for passage in passages:
            for sentence in split_sentences(passage):
                overlap = q_terms & set(content_tokens(sentence))
                weight = sum(self.idf.get(t, self.default_idf) for t in overlap)
                candidates.append((weight, order, sentence, overlap))
                order += 1
        best = sorted((c for c in candidates if c[0] > 0), key=lambda c: (-c[0], c[1]))[: self.max_sentences]
        if not best:
            return GeneratorOutput(answer=ABSTAIN_ANSWER)
        if self.min_evidence > 0:
            wanted = sum(self.idf.get(t, self.default_idf) for t in q_terms)
            covered = sum(self.idf.get(t, self.default_idf) for t in set().union(*(c[3] for c in best)))
            if wanted <= 0 or covered / wanted < self.min_evidence:
                return GeneratorOutput(answer=ABSTAIN_ANSWER)
        answer = " ".join(sentence for _, _, sentence, _ in sorted(best, key=lambda c: c[1]))
        return GeneratorOutput(answer=answer)


class OpenAIChatGenerator:
    """Retrieve-then-generate answering with an OpenAI chat model."""

    def __init__(self, *, model: str, api_key: str, base_url: str | None = None, timeout_s: float = 60.0):
        from langchain_openai import ChatOpenAI

        self.model = model
        # Retries are handled by the runner (one place, observable attempt counts), so the
        # client's own retry loop is disabled.
        self._llm = ChatOpenAI(model=model, temperature=0, api_key=SecretStr(api_key), base_url=base_url,
                               timeout=timeout_s, max_retries=0)

    def generate(self, question: str, passages: list[str]) -> GeneratorOutput:
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [SystemMessage(content=RAG_SYSTEM_PROMPT), HumanMessage(content=rag_user_prompt(question, passages))]
        try:
            response = self._llm.invoke(messages)
        except Exception as exc:
            mapped = classify_openai_error(exc)
            if mapped is not None:
                raise mapped from exc
            raise
        text = response.content if isinstance(response.content, str) else str(response.content)
        usage = getattr(response, "usage_metadata", None) or {}
        if not text.strip():
            raise ProviderError("Model returned an empty answer")
        return GeneratorOutput(answer=text.strip(), prompt_tokens=usage.get("input_tokens"),
                               completion_tokens=usage.get("output_tokens"))
