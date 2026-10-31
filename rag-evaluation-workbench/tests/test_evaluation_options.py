import csv
import io
import json

import pytest
from conftest import REAL_PDF

from rag_workbench.aggregate import MISSING_SLICE, metadata_keys, slice_results
from rag_workbench.cli import main
from rag_workbench.config import ConfigError, load_settings
from rag_workbench.documents import drop_headings, is_heading, load_chunks
from rag_workbench.models import CaseResult, Chunk, MetricResult, RetrievedChunk, RunConfig
from rag_workbench.pipeline import build_pipeline
from rag_workbench.providers import ExtractiveGenerator
from rag_workbench.reporting import export_csv, export_json
from rag_workbench.retrieval import BM25Retriever, HybridRetriever
from rag_workbench.runner import EvaluationRunner
from rag_workbench.text import ABSTENTION_PATTERNS, content_tokens, is_abstention, tokenize

UNANSWERABLE = "examples/datasets/honeybees_unanswerable.jsonl"


# ------------------------------------------------------------------ tokenisation
def test_apostrophes_inside_words_do_not_leave_stray_tokens():
    assert tokenize("The queen's cells can't wait") == ["the", "queens", "cells", "cant", "wait"]
    assert tokenize("The bees’ dance, workers' jobs, oʼclock") == ["the", "bees", "dance", "workers", "jobs", "oclock"]
    assert content_tokens("the queen's cells") == ["queen", "cell"]  # possessive matches the plain plural/singular
    assert tokenize("'quoted' text") == ["quoted", "text"]  # leading/trailing quote marks are not part of words


# ------------------------------------------------------------------ headings
@pytest.mark.parametrize("text,expected", [
    ("Honeybees: Life Inside the Colony", True), ("Chapter 3", True),
    ("A short sentence.", False), ("Is this a question?", False), ("Note: see below:", False),
    ("a " * 30, False),  # long block
    ("", False),
])
def test_heading_heuristic(text, expected):
    assert is_heading(text) is expected


def test_drop_headings_keeps_everything_if_all_blocks_look_like_headings():
    chunks = [Chunk(id=f"c{i}", text=t, page=1, source="s") for i, t in
              enumerate(["Title Here", "A real sentence about bees.", "Another Heading"], start=1)]
    assert [c.id for c in drop_headings(chunks)] == ["c2"]
    only_headings = [chunks[0], chunks[2]]
    assert drop_headings(only_headings) == only_headings


def test_example_document_title_is_dropped_but_content_is_kept():
    chunks = load_chunks(REAL_PDF)
    kept = drop_headings(chunks)
    assert chunks[0].text.startswith("Honeybees: Life") and len(kept) == len(chunks) - 1
    assert kept[0].id == "p1-b2"


# ------------------------------------------------------------------ evidence threshold
def make_generator(**kwargs):
    chunks = [Chunk(id="a", text="Bees collect nectar. Queens lay eggs.", page=1, source="s"),
              Chunk(id="b", text="Winter clusters keep the hive warm.", page=1, source="s")]
    return ExtractiveGenerator(BM25Retriever(chunks).idf, **kwargs), [c.text for c in chunks]


def test_min_evidence_zero_always_answers_when_a_term_matches():
    generator, passages = make_generator()
    assert not is_abstention(generator.generate("Why do bees sing in winter?", passages).answer)


def test_min_evidence_abstains_when_too_little_of_the_question_is_covered():
    strict, passages = make_generator(min_evidence=0.6)
    answer = strict.generate("Why do bees sing opera in winter?", passages).answer  # only "bees"/"winter" covered
    assert any(p.search(answer) for p in ABSTENTION_PATTERNS)
    assert not is_abstention(strict.generate("What do bees collect?", passages).answer)  # fully covered


@pytest.mark.parametrize("bad", [-0.1, 1.5])
def test_min_evidence_is_validated(bad):
    with pytest.raises(ValueError, match="min_evidence"):
        ExtractiveGenerator({}, min_evidence=bad)
    with pytest.raises(ValueError):
        RunConfig(name="x", dataset_path="d", document_path="p", metrics=["token_f1"], min_evidence=bad)


def test_the_options_reach_the_pipeline_and_change_the_run(settings, store):
    runner = EvaluationRunner(settings, store)

    def run(**opts):
        return runner.run(RunConfig(name="o", dataset_path=str(settings.project_root / UNANSWERABLE),
                                    document_path=str(REAL_PDF), metrics=["token_f1", "groundedness"], **opts))

    def abstentions(r):
        return {c.case_id for c in store.get_case_results(r.id) if is_abstention(c.answer or "")}

    assert abstentions(run()) == set()
    assert {"u1", "u2"} <= abstentions(run(min_evidence=0.5))
    with_titles = run(k=3)
    without = run(k=3, skip_headings=True)

    def title_first(r):
        return sum(c.contexts[0].chunk_id == "p1-b1" for c in store.get_case_results(r.id))

    assert title_first(with_titles) >= 1 and title_first(without) == 0


# ------------------------------------------------------------------ hybrid retrieval
class Stub:
    def __init__(self, ids):
        self.ids = ids

    def retrieve(self, query, k):
        return [RetrievedChunk(chunk_id=i, text=f"text {i}", page=1, score=0.0, rank=r)
                for r, i in enumerate(self.ids[:k], start=1)]


def test_rrf_fusion_matches_the_formula_and_prefers_agreement():
    hybrid = HybridRetriever(Stub(["a", "b", "c"]), Stub(["c", "b", "d"]), rrf_k=60)
    hits = hybrid.retrieve("q", 4)
    scores = {h.chunk_id: h.score for h in hits}
    assert scores["b"] == pytest.approx(1 / 62 + 1 / 62, abs=1e-6)
    assert scores["a"] == pytest.approx(1 / 61, abs=1e-6)
    assert scores["c"] == pytest.approx(1 / 63 + 1 / 61, abs=1e-6)
    assert [h.chunk_id for h in hits][:2] == ["c", "b"]  # both retrievers rank c and b; a and d are single votes
    assert [h.rank for h in hits] == [1, 2, 3, 4]
    assert [h.chunk_id for h in hybrid.retrieve("q", 2)] == ["c", "b"]


def test_hybrid_validation():
    with pytest.raises(ValueError):
        HybridRetriever(Stub([]), Stub([]), rrf_k=0)
    with pytest.raises(ValueError):
        HybridRetriever(Stub([]), Stub([])).retrieve("q", 0)


def test_hybrid_pipeline_needs_a_key_and_works_with_a_fake_embedding_model(monkeypatch, offline_config, chunks):
    with pytest.raises(ConfigError, match="hybrid retriever"):
        build_pipeline(offline_config(retriever="hybrid"), load_settings({}, dotenv=False), chunks)

    from langchain_core.embeddings import DeterministicFakeEmbedding

    monkeypatch.setattr("langchain_openai.OpenAIEmbeddings", lambda **kw: DeterministicFakeEmbedding(size=16))
    keyed = load_settings({"OPENAI_API_KEY": "sk-not-a-real-key-for-tests-123"}, dotenv=False)
    pipeline = build_pipeline(offline_config(retriever="hybrid", k=2), keyed, chunks)
    generation = pipeline.answer("What do bees collect?")
    assert len(generation.contexts) == 2 and generation.context_source == "retriever"
    assert {c.chunk_id for c in generation.contexts} <= {c.id for c in chunks}


# ------------------------------------------------------------------ slices / metadata
def case(i, kind, score, status="ok"):
    return CaseResult(case_id=f"c{i}", position=i, question=f"Q{i}", expected_answer="x", status=status,
                      metadata={} if kind is None else {"type": kind, "n": i},
                      metrics={} if status == "error" else {"m": MetricResult(
                          name="m", status="ok", score=score, threshold=0.5, passed=score >= 0.5)})


def test_slices_group_by_metadata_and_keep_missing_last():
    results = [case(1, "easy", 1.0), case(2, "easy", 0.0), case(3, "hard", 0.5), case(4, None, 0.2),
               case(5, "hard", 0.0, status="error")]
    assert metadata_keys(results) == ["n", "type"]
    rows = slice_results(results, "type", ["m"], {"m": 0.5})
    assert [r.value for r in rows] == ["easy", "hard", MISSING_SLICE]
    easy, hard, missing = rows
    assert (easy.n_cases, easy.metrics["m"].mean, easy.metrics["m"].pass_rate) == (2, 0.5, 0.5)
    assert (hard.n_cases, hard.n_ok, hard.metrics["m"].n_scored) == (2, 1, 1)
    assert missing.n_cases == 1 and missing.metrics["m"].mean == 0.2
    # c4 has no metadata at all, so it is the only case without "n"; its slice is listed last
    assert [r.value for r in slice_results(results, "n", ["m"], {})][-1] == MISSING_SLICE


def test_metadata_flows_from_the_dataset_to_results_exports_and_the_cli(settings, store, capsys):
    run = EvaluationRunner(settings, store).run(RunConfig(
        name="slices", dataset_path=str(settings.project_root / UNANSWERABLE), document_path=str(REAL_PDF),
        metrics=["token_f1", "context_recall"]))
    results = store.get_case_results(run.id)
    assert {c.metadata["type"] for c in results} == {"answerable", "unanswerable"}
    rows = {r.value: r for r in slice_results(results, "type", ["token_f1", "context_recall"], {})}
    assert rows["unanswerable"].metrics["context_recall"].n_scored == 0  # abstention references are skipped
    assert rows["answerable"].metrics["context_recall"].n_scored == 2

    exported = list(csv.DictReader(io.StringIO(export_csv(run, results).decode("utf-8-sig"))))
    assert {row["meta_type"] for row in exported} == {"answerable", "unanswerable"}
    bundle = json.loads(export_json(run, results))
    assert bundle["cases"][0]["metadata"]["type"] in {"answerable", "unanswerable"}

    assert main(["slices", run.id, "--by", "type"]) == 0
    out = capsys.readouterr().out
    assert "answerable" in out and "unanswerable" in out and "n scored" in out
    assert main(["slices", run.id, "--by", "nope"]) == 1
    assert "Available: type" in capsys.readouterr().err


def test_cli_options_are_passed_through(capsys):
    assert main(["run", "--name", "opt", "--dataset", UNANSWERABLE, "--min-evidence", "0.7", "--skip-headings",
                 "--metrics", "token_f1", "--quiet"]) == 0
    assert main(["run", "--name", "opt", "--min-evidence", "2", "--quiet"]) == 1  # validated: error, not traceback
    assert "min_evidence" in capsys.readouterr().err
    assert main(["run", "--name", "opt", "--retriever", "hybrid", "--quiet"]) == 1
    assert "OPENAI_API_KEY" in capsys.readouterr().err
