"""RAG pipelines and the factory that assembles one from a :class:`RunConfig`.

Two modes are offered:

``rag`` (default)
    Retrieve the top-k chunks for the question, then generate an answer from exactly those chunks.
    The chunks recorded for evaluation are, by construction, the chunks the generator saw.

``agent``
    A LangChain tool-calling agent decides when and with what query to call the ``collecting_info``
    retrieval tool. Every chunk the tool returns is captured per call (no global state), and *those*
    chunks are recorded as the evaluation context. The agent's self-reported ``context`` field is
    stored separately as ``model_context_claim`` for auditing and is never used for scoring: a model's
    description of its evidence is not evidence.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from pydantic import SecretStr

from .config import ConfigError, Settings
from .documents import drop_headings, load_chunks
from .errors import ProviderError, classify_openai_error
from .metrics.semantic import INSTALL_HINT, local_embedder, local_model_error, semantic_available
from .models import Chunk, Generation, RetrievedChunk, RunConfig
from .prompts import AGENT_SYSTEM_PROMPT
from .providers import ExtractiveGenerator, Generator, OpenAIChatGenerator
from .retrieval import BM25Retriever, EmbeddingRetriever, HybridRetriever, LocalEmbeddingRetriever, Retriever


class Pipeline(Protocol):
    @property
    def model(self) -> str: ...

    def answer(self, question: str) -> Generation: ...


@dataclass
class RAGPipeline:
    retriever: Retriever
    generator: Generator
    k: int

    @property
    def model(self) -> str:
        return self.generator.model

    def answer(self, question: str) -> Generation:
        start = time.perf_counter()
        contexts = self.retriever.retrieve(question, self.k)
        output = self.generator.generate(question, [c.text for c in contexts])
        return Generation(answer=output.answer, contexts=contexts, context_source="retriever", model=self.model,
                          latency_ms=(time.perf_counter() - start) * 1000, prompt_tokens=output.prompt_tokens,
                          completion_tokens=output.completion_tokens, retrieval_queries=[question])


class AgentRAGPipeline:
    """Tool-calling agent pipeline with the real retrieved context captured per question."""

    def __init__(self, retriever: Retriever, *, k: int, model: str, api_key: str, base_url: str | None = None,
                 timeout_s: float = 60.0):
        from langchain_openai import ChatOpenAI

        self.retriever = retriever
        self.k = k
        self.model = model
        self._llm = ChatOpenAI(model=model, temperature=0, api_key=SecretStr(api_key), base_url=base_url,
                               timeout=timeout_s, max_retries=0)

    def answer(self, question: str) -> Generation:
        from langchain.agents import create_agent
        from langchain.tools import tool
        from langchain_core.messages import AIMessage, HumanMessage
        from pydantic import BaseModel, Field

        captured: list[RetrievedChunk] = []
        queries: list[str] = []

        @tool
        def collecting_info(query: str) -> str:
            """Search the PDF knowledge base and return relevant information for the user's question."""
            hits = self.retriever.retrieve(query, self.k)
            queries.append(query)
            known = {c.chunk_id for c in captured}
            captured.extend(h for h in hits if h.chunk_id not in known)
            return "\n\n".join(h.text for h in hits)

        class Answer(BaseModel):
            answer: str = Field(description="the answer that is needed for the user question")
            context: str = Field(description="this is the context that the agent used to reply to the user question")

        agent = create_agent(model=self._llm, tools=[collecting_info], system_prompt=AGENT_SYSTEM_PROMPT,
                             response_format=Answer)
        start = time.perf_counter()
        try:
            result = agent.invoke({"messages": [HumanMessage(content=question)]})
        except Exception as exc:
            mapped = classify_openai_error(exc)
            if mapped is not None:
                raise mapped from exc
            raise
        latency_ms = (time.perf_counter() - start) * 1000
        structured = result.get("structured_response")
        if structured is None or not structured.answer.strip():
            raise ProviderError("Agent returned no structured answer")
        prompt_tokens = completion_tokens = 0
        saw_usage = False
        for message in result.get("messages", []):
            usage = getattr(message, "usage_metadata", None) if isinstance(message, AIMessage) else None
            if usage:
                saw_usage = True
                prompt_tokens += usage.get("input_tokens", 0)
                completion_tokens += usage.get("output_tokens", 0)
        for rank, chunk in enumerate(captured, start=1):
            chunk.rank = rank
        return Generation(answer=structured.answer.strip(), contexts=captured, context_source="agent_tool",
                          model=self.model, latency_ms=latency_ms,
                          prompt_tokens=prompt_tokens if saw_usage else None,
                          completion_tokens=completion_tokens if saw_usage else None,
                          retrieval_queries=queries, model_context_claim=structured.context)


def build_retriever(config: RunConfig, chunks: list[Chunk], settings: Settings) -> Retriever:
    if config.retriever == "bm25":
        return BM25Retriever(chunks)
    if config.retriever in ("local", "hybrid-local"):
        if not semantic_available():
            raise ConfigError(INSTALL_HINT)
        model = config.embedding_model or settings.local_embedding_model
        cache_dir = str(settings.local_model_dir)
        try:  # load now: a model that cannot be loaded must stop the run before any case, not cost each case a timeout
            embedder = local_embedder(model, cache_dir)
        except ConfigError:
            raise
        except Exception as exc:
            raise local_model_error(model, cache_dir, exc) from exc
        local = LocalEmbeddingRetriever(chunks, model=model, embedder_factory=lambda: embedder)
        return local if config.retriever == "local" else HybridRetriever(BM25Retriever(chunks), local)
    _require_key(settings, f"the {config.retriever} retriever")
    dense = EmbeddingRetriever(chunks, model=config.embedding_model or settings.embedding_model,
                               api_key=settings.require_openai_key(), base_url=settings.openai_base_url,
                               timeout_s=config.request_timeout_s, max_retries=config.max_retries)
    if config.retriever == "hybrid":
        return HybridRetriever(BM25Retriever(chunks), dense)
    return dense


def build_pipeline(config: RunConfig, settings: Settings, chunks: list[Chunk] | None = None) -> Pipeline:
    """Assemble the pipeline a run config describes. Raises :class:`ConfigError` for invalid combinations."""
    if chunks is None:
        chunks = load_chunks(config.document_path, max_bytes=settings.max_document_bytes)
    if config.skip_headings:
        chunks = drop_headings(chunks)
    retriever = build_retriever(config, chunks, settings)

    if config.provider == "offline":
        if config.pipeline == "agent":
            raise ConfigError(
                "The agent pipeline needs a tool-calling LLM; choose provider 'openai' or pipeline 'rag'.")
        idf = retriever.idf if isinstance(retriever, BM25Retriever) else BM25Retriever(chunks).idf
        generator = ExtractiveGenerator(idf, max_sentences=config.max_answer_sentences,
                                        failure_rate=config.offline_failure_rate, seed=config.seed,
                                        min_evidence=config.min_evidence)
        return RAGPipeline(retriever=retriever, generator=generator, k=config.k)

    _require_key(settings, "the OpenAI provider")
    key = settings.require_openai_key()
    model = config.generator_model or settings.generator_model
    if config.pipeline == "agent":
        return AgentRAGPipeline(retriever, k=config.k, model=model, api_key=key, base_url=settings.openai_base_url,
                                timeout_s=config.request_timeout_s)
    chat_generator = OpenAIChatGenerator(model=model, api_key=key, base_url=settings.openai_base_url,
                                         timeout_s=config.request_timeout_s)
    return RAGPipeline(retriever=retriever, generator=chat_generator, k=config.k)


def _require_key(settings: Settings, what: str) -> None:
    if not settings.has_openai_key:
        raise ConfigError(f"OPENAI_API_KEY is not set; it is required for {what}. "
                          "Add it to .env or use the offline provider with the BM25 retriever.")
