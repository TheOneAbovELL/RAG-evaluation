"""Shared fixtures. Every test runs offline with an isolated data directory and no API key."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "1"
os.environ["DEEPEVAL_DISABLE_DOTENV"] = "1"  # DeepEval would otherwise load a real .env on import
os.environ["RAGWB_NO_DOTENV"] = "1"  # a real .env (with a key) must never influence a test, nor child processes

from rag_workbench.config import PROJECT_ROOT, load_settings
from rag_workbench.models import Chunk, Generation, RetrievedChunk, RunConfig
from rag_workbench.storage import RunStore

REAL_DATASET = PROJECT_ROOT / "examples" / "datasets" / "honeybees.jsonl"
REAL_PDF = PROJECT_ROOT / "examples" / "documents" / "honeybees.pdf"


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """No real key, no project .env influence, data written under tmp_path."""
    monkeypatch.setenv("OPENAI_API_KEY", "")  # blank = unset; also stops .env from supplying one
    monkeypatch.setenv("RAGWB_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("RAGWB_RETRY_BASE_DELAY_S", "0")
    for var in ("RAGWB_PRICE_INPUT_PER_MTOK", "RAGWB_PRICE_OUTPUT_PER_MTOK", "RAGWB_DATASET",
                "RAGWB_DOCUMENT", "OPENAI_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    yield


@pytest.fixture
def settings():
    return load_settings()


@pytest.fixture
def store(settings):
    return RunStore(settings.db_path)


@pytest.fixture
def chunks() -> list[Chunk]:
    texts = [
        "Honeybees live in colonies with a single queen. Workers do most of the work in the hive.",
        "Forager bees collect nectar, pollen and water. They fly out of the hive to find flowers.",
        "In winter the bees cluster together and shiver to stay warm.",
        "Varroa mites and pesticides threaten many honeybee colonies.",
    ]
    return [Chunk(id=f"p1-b{i}", text=t, page=1, source="test.txt") for i, t in enumerate(texts, start=1)]


def write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def small_dataset(tmp_path) -> Path:
    return write_jsonl(tmp_path / "small.jsonl", [
        {"id": "q1", "question": "What do forager bees collect?", "expected_answer": "Forager bees collect nectar, pollen and water."},
        {"id": "q2", "question": "How many queens does a colony have?", "expected_answer": "A single queen."},
        {"id": "q3", "question": "How do bees stay warm in winter?", "expected_answer": "They cluster together and shiver."},
        {"id": "q4", "question": "What threatens honeybee colonies?"},
    ])


@pytest.fixture
def small_document(tmp_path, chunks) -> Path:
    path = tmp_path / "bees.txt"
    path.write_text("\n\n".join(c.text for c in chunks), encoding="utf-8")
    return path


@pytest.fixture
def offline_config(small_dataset, small_document):
    def make(**overrides) -> RunConfig:
        values = {"name": "test-run", "dataset_path": str(small_dataset), "document_path": str(small_document),
                      "metrics": ["token_f1", "rouge_l", "context_recall", "groundedness"], "k": 2}
        values.update(overrides)
        return RunConfig(**values)
    return make


class FakePipeline:
    """Pipeline double: scripted answers or exceptions per question, counting calls."""

    model = "fake-model"

    def __init__(self, behaviour=None, contexts=None):
        self.behaviour = behaviour or {}
        self.calls: dict[str, int] = {}
        self.contexts = contexts if contexts is not None else [
            RetrievedChunk(chunk_id="c1", text="Forager bees collect nectar, pollen and water.", page=1, score=1.0, rank=1)]

    def answer(self, question: str) -> Generation:
        self.calls[question] = self.calls.get(question, 0) + 1
        action = self.behaviour.get(question)
        if callable(action):
            action = action(self.calls[question])
        if isinstance(action, BaseException):
            raise action
        return Generation(answer=action or "Forager bees collect nectar, pollen and water.", contexts=self.contexts,
                          model=self.model, latency_ms=1.0, prompt_tokens=10, completion_tokens=5)


@pytest.fixture
def fake_pipeline_cls():
    return FakePipeline
