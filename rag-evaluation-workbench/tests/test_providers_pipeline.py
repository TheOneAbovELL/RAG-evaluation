import httpx
import openai
import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from rag_workbench.config import ConfigError, load_settings
from rag_workbench.errors import ProviderError, TransientProviderError, classify_openai_error
from rag_workbench.pipeline import AgentRAGPipeline, RAGPipeline, build_pipeline
from rag_workbench.prompts import ABSTAIN_ANSWER
from rag_workbench.providers import ExtractiveGenerator, OpenAIChatGenerator
from rag_workbench.retrieval import BM25Retriever

REQUEST = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")


def test_extractive_generator_selects_matching_sentences_in_order(chunks):
    gen = ExtractiveGenerator(BM25Retriever(chunks).idf, max_sentences=2)
    out = gen.generate("What do forager bees collect?", [chunks[1].text, chunks[0].text])
    assert out.answer.startswith("Forager bees collect nectar, pollen and water.")
    assert out.prompt_tokens is None  # no tokens: not a language model


def test_extractive_generator_abstains_without_overlap(chunks):
    gen = ExtractiveGenerator(BM25Retriever(chunks).idf)
    assert gen.generate("Quantum chromodynamics?", [chunks[0].text]).answer == ABSTAIN_ANSWER
    assert gen.generate("anything", []).answer == ABSTAIN_ANSWER


def test_failure_injection_is_deterministic(chunks):
    idf = BM25Retriever(chunks).idf
    always = ExtractiveGenerator(idf, failure_rate=1.0)
    with pytest.raises(ProviderError, match="Injected") as info:
        always.generate("q", ["text"])
    assert type(info.value) is ProviderError  # permanent: retrying a deterministic failure only adds delay
    some = ExtractiveGenerator(idf, failure_rate=0.5, seed=3)
    outcomes = []
    for _ in range(2):
        row = []
        for i in range(20):
            try:
                some.generate(f"question {i}", ["question text"])
                row.append(True)
            except ProviderError:
                row.append(False)
        outcomes.append(row)
    assert outcomes[0] == outcomes[1] and 0 < sum(outcomes[0]) < 20


def test_classify_openai_errors():
    rate = openai.RateLimitError("slow down", response=httpx.Response(429, request=REQUEST), body=None)
    assert isinstance(classify_openai_error(rate), TransientProviderError)
    assert isinstance(classify_openai_error(openai.APITimeoutError(request=REQUEST)), TransientProviderError)
    auth = openai.AuthenticationError("bad key sk-abc", response=httpx.Response(401, request=REQUEST), body=None)
    mapped = classify_openai_error(auth)
    assert type(mapped) is ProviderError and "OPENAI_API_KEY" in str(mapped)
    assert "sk-abc" not in str(mapped)
    assert classify_openai_error(ValueError("x")) is None


class ScriptedLLM:
    def __init__(self, result):
        self.result = result
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def test_openai_generator_records_tokens_and_prompt():
    gen = OpenAIChatGenerator(model="gpt-test", api_key="sk-test")
    gen._llm = ScriptedLLM(AIMessage(content=" Nectar. ", usage_metadata={"input_tokens": 50, "output_tokens": 3,
                                                                         "total_tokens": 53}))
    out = gen.generate("What do forager bees collect?", ["Bees collect nectar."])
    assert (out.answer, out.prompt_tokens, out.completion_tokens) == ("Nectar.", 50, 3)
    assert "[1] Bees collect nectar." in gen._llm.messages[1].content


def test_openai_generator_errors():
    gen = OpenAIChatGenerator(model="gpt-test", api_key="sk-test")
    gen._llm = ScriptedLLM(AIMessage(content="   "))
    with pytest.raises(ProviderError, match="empty answer"):
        gen.generate("q", ["c"])
    gen._llm = ScriptedLLM(openai.APITimeoutError(request=REQUEST))
    with pytest.raises(TransientProviderError):
        gen.generate("q", ["c"])


def test_rag_pipeline_evaluates_exactly_the_retrieved_chunks(chunks):
    retriever = BM25Retriever(chunks)
    pipeline = RAGPipeline(retriever, ExtractiveGenerator(retriever.idf), k=2)
    gen = pipeline.answer("What do forager bees collect?")
    assert [c.chunk_id for c in gen.contexts] == [c.chunk_id for c in retriever.retrieve("What do forager bees collect?", 2)]
    assert gen.context_source == "retriever"
    assert gen.latency_ms >= 0 and gen.model == "offline-extractive"


def test_build_pipeline_validation(offline_config, settings, chunks):
    assert isinstance(build_pipeline(offline_config(), settings, chunks), RAGPipeline)
    with pytest.raises(ConfigError, match="agent pipeline"):
        build_pipeline(offline_config(pipeline="agent"), settings, chunks)
    with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
        build_pipeline(offline_config(provider="openai"), settings, chunks)
    with pytest.raises(ConfigError, match="embedding retriever"):
        build_pipeline(offline_config(retriever="embedding"), settings, chunks)


def test_build_openai_pipelines_with_key(offline_config, chunks):
    keyed = load_settings({"OPENAI_API_KEY": "sk-test-123456789"}, dotenv=False)
    rag = build_pipeline(offline_config(provider="openai", generator_model="gpt-x"), keyed, chunks)
    assert isinstance(rag, RAGPipeline) and rag.model == "gpt-x"
    agent = build_pipeline(offline_config(provider="openai", pipeline="agent"), keyed, chunks)
    assert isinstance(agent, AgentRAGPipeline) and agent.model == keyed.generator_model


class ToolCallingFake(GenericFakeChatModel):
    """Scripted chat model that accepts bind_tools (needed by create_agent)."""

    def bind_tools(self, tools, **kwargs):
        return self


def test_agent_pipeline_captures_real_tool_output_not_self_report(chunks):
    retriever = BM25Retriever(chunks)
    pipeline = AgentRAGPipeline(retriever, k=1, model="fake", api_key="sk-test")
    pipeline._llm = ToolCallingFake(messages=iter([
        AIMessage(content="", tool_calls=[{"name": "collecting_info", "args": {"query": "forager collect nectar"},
                                           "id": "call-1"}],
                  usage_metadata={"input_tokens": 100, "output_tokens": 10, "total_tokens": 110}),
        AIMessage(content="", tool_calls=[{"name": "Answer", "args": {"answer": "Nectar, pollen and water.",
                                                                     "context": "I invented this context."},
                                           "id": "call-2"}],
                  usage_metadata={"input_tokens": 150, "output_tokens": 20, "total_tokens": 170}),
    ]))
    gen = pipeline.answer("What do forager bees collect?")
    assert gen.answer == "Nectar, pollen and water."
    assert gen.context_source == "agent_tool"
    assert [c.chunk_id for c in gen.contexts] == ["p1-b2"]  # what the tool really returned
    assert gen.model_context_claim == "I invented this context."
    assert gen.retrieval_queries == ["forager collect nectar"]
    assert (gen.prompt_tokens, gen.completion_tokens) == (250, 30)
