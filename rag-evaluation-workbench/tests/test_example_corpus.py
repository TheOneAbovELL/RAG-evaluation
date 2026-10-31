"""Static checks on the bundled example documents and datasets (no evaluation is run)."""

from __future__ import annotations

import pytest

from rag_workbench.config import PROJECT_ROOT
from rag_workbench.datasets import validate_file
from rag_workbench.documents import load_chunks
from rag_workbench.prompts import ABSTAIN_ANSWER

NAMES = ["volcanoes", "coffee", "lighthouses"]
DOCUMENTS = PROJECT_ROOT / "examples" / "documents"
DATASETS = PROJECT_ROOT / "examples" / "datasets"
METADATA_KEYS = {"type", "difficulty", "topic"}


@pytest.mark.parametrize("name", NAMES)
def test_dataset_validates(name):
    report = validate_file(DATASETS / f"{name}.jsonl")
    assert report.ok, report.errors


@pytest.mark.parametrize("name", NAMES)
def test_document_yields_one_chunk_per_paragraph(name):
    blocks = [b for b in (DOCUMENTS / f"{name}.md").read_text(encoding="utf-8").split("\n\n") if b.strip()]
    expected = len(blocks)  # the title line is a block of its own
    assert expected - 1 >= 10
    assert len(load_chunks(DOCUMENTS / f"{name}.md")) == expected
    assert len(load_chunks(DOCUMENTS / f"{name}.pdf")) == expected


@pytest.mark.parametrize("name", NAMES)
def test_dataset_rows(name):
    cases = validate_file(DATASETS / f"{name}.jsonl").cases
    assert len(cases) == 30
    assert len({c.id for c in cases}) == 30
    assert all(set(c.metadata) >= METADATA_KEYS for c in cases)
    assert all(c.metadata["difficulty"] in {"easy", "medium", "hard"} for c in cases)
    assert all(c.metadata["type"] in {"factual", "numeric", "list", "why", "unanswerable"} for c in cases)
    unanswerable = [c for c in cases if c.metadata["type"] == "unanswerable"]
    assert len(unanswerable) >= 5
    assert all(c.expected_answer == ABSTAIN_ANSWER for c in unanswerable)
    assert all(c.expected_answer and c.expected_answer.strip() for c in cases if c not in unanswerable)
