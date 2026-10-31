# Implementation Plan

> **Engineering record.** Written during development and kept unedited apart from this note. Sections
> before the restructuring (DEVELOPMENT_LOG §6) use the working names of that time: package `llm_eval`
> (now `rag_workbench`), variables `LLM_EVAL_*` (now `RAGWB_*`), `dashboard.py` (now `streamlit_app.py`),
> `docs/audit/` (now `docs/engineering/`). Paths such as `RAG1/` or `versions/` refer to the reference
> repository, which is not part of this product.

## 1. Source of truth

No separate assignment document or specification was supplied. The only statements of intent are
the repository's `README.md` ("A compact evaluation lab for one RAG pipeline: ask questions about a
penguin PDF, score the answers with DeepEval, and compare saved evaluation runs") and the code
itself. The master directive supplies engineering requirements (offline mode, tests, UI, docs).
Requirements below are derived from those two sources; each is tagged with its origin.
Any requirement a future specification adds or contradicts should be reconciled against this list
(see `REQUIREMENTS_TRACEABILITY.md`).

## 2. Requirement interpretation

| ID | Requirement | Source |
|---|---|---|
| R1 | Answer questions about a PDF with a retrieval-augmented pipeline (PDF → chunks → retrieval → generation) | README |
| R2 | Evaluate answers over a JSONL dataset of question / expected-answer pairs | README |
| R3 | Score with answer relevancy, faithfulness, contextual relevancy, correctness (DeepEval, threshold 0.7) | README |
| R4 | Summarise a run: average, pass/fail counts, pass rate per metric | README / `evaluation_summary*.py` |
| R5 | Compare saved runs side by side, best run per metric | README / `dashboard.py` |
| R6 | Configurable retriever `k` (README asks the user to edit source for this) | README |
| R7 | Dashboard in Streamlit | README |
| R8 | Preserve and display the three saved historical runs | README |
| R9 | Run end-to-end without network or API keys (mock / local mode) | Directive §4 |
| R10 | Configurable provider adapters with timeouts, retries, explicit env vars | Directive §4 |
| R11 | Record the real retrieved context, latency, tokens (when reported), errors per case | Directive §4, defect D1/D9 |
| R12 | Partial-failure tolerance: failed cases recorded, run continues, interrupted runs keep progress | Directive §4/§8 |
| R13 | Persist runs with reproducibility metadata (config, dataset hash, timestamps, versions) | Directive §7.2 |
| R14 | Export results (CSV, JSON, Markdown) | Directive §6 |
| R15 | Dataset validation with actionable errors (empty, malformed, duplicate, missing fields) | Directive §8 |
| R16 | UI workflow: configure → run with progress → inspect → compare → export → history | Directive §6 |
| R17 | Automated test suite runnable offline | Directive §8 |
| R18 | No secrets in logs; DeepEval telemetry disabled | Directive §5.3 |
| R19 | Documentation set + technical book (Markdown, PDF if feasible) | Directive §9 |
| R20 | Local verification script | Directive §10 |

## 3. Architecture decision

Keep Python, LangChain/OpenAI, DeepEval, Streamlit and uv (all already present and suitable).
Introduce one importable package `llm_eval/` that owns configuration, data models, the RAG
pipeline, metrics, orchestration, storage and reporting. The CLI, the Streamlit app and the
legacy scripts become thin front ends over it.

```
llm_eval/
  config.py        Settings from env/.env, validated (pydantic)
  models.py        Data contracts: EvalCase, Chunk, RetrievedChunk, Generation, CaseResult, RunRecord
  datasets.py      JSONL parsing/validation, hashing
  documents.py     PDF → chunks (PyMuPDF), whitespace normalisation
  text.py          Tokenisation/normalisation shared by BM25 and lexical metrics
  retrieval.py     Retriever protocol; BM25Retriever (offline); EmbeddingRetriever (OpenAI)
  providers.py     Generator protocol; ExtractiveGenerator (offline); OpenAIChatGenerator
  pipeline.py      RAGPipeline (retrieve → generate) and AgentRAGPipeline (original agent, real context captured)
  metrics/         Metric protocol; lexical metrics (offline); DeepEval judge metrics
  aggregate.py     mean/median/std/pass-rate/bootstrap CI; missing-value handling
  runner.py        Orchestrates a run: progress callback, cancellation, retries, incremental persistence
  storage.py       SQLite store of runs and case results
  legacy.py        Import of versions/vN saved runs (read-only, provenance flagged)
  reporting.py     CSV/JSON/Markdown exports, run comparison
  cli.py           `python -m llm_eval ...`
app/               Streamlit pages; `dashboard.py` stays the entry point
tests/             pytest suite (offline)
```

Key decisions:

* **Retrieval context is captured from the retriever, never from the model's self-report** (fixes D1).
* **Two pipeline modes**: `rag` (deterministic retrieve-then-generate; the default because the evaluated
  context is exactly what was retrieved) and `agent` (the original tool-calling agent, kept for
  continuity, with per-call capture of the tool's real output instead of a global).
* **Offline mode is a real baseline, not a fake**: BM25 retrieval plus an extractive answer generator
  (selects the best-matching sentences from retrieved chunks), scored by lexical metrics with documented
  formulas. Judge metrics are skipped with an explicit "requires OpenAI" status rather than invented.
* **Lazy construction**: nothing touches the network at import time (fixes D3).
* SQLite for history (single file, stdlib, transactional).
* Legacy artefacts are kept untouched; legacy scripts are kept but made path-safe or turned into wrappers.

## 4. Phases

| Phase | Objective | Exit criterion |
|---|---|---|
| P1 | Core package: config, models, datasets, documents, text, retrieval, providers, pipeline | Unit tests pass offline |
| P2 | Metrics (lexical + DeepEval adapters), aggregation | Metric tests with hand-computed expectations |
| P3 | Runner, storage, legacy import, reporting, CLI | Offline end-to-end run via CLI, persisted and exported |
| P4 | Streamlit app (multi-page) | AppTest journeys pass; manual check in browser |
| P5 | Tests hardening, verification script, dependency cleanup | `scripts/verify.ps1`/`verify.py` green |
| P6 | Documentation set + technical book + PDF | PDF opens, TOC present, all modules covered |
| P7 | Final audit + handover | Audit report written from re-inspected files |

## 5. Risks

| Risk | Mitigation |
|---|---|
| No API key → judge metrics and OpenAI paths cannot be executed here | Adapters unit-tested with fakes; documented as "implemented, not live-verified" |
| Dependency changes need `uv lock` (network to PyPI) | Keep changes minimal; record outcome; fall back to existing lock if locking fails |
| Lexical metrics mistaken for semantic quality | Clear naming, formulas and "where it misleads" sections; UI labels method family |
| OneDrive-synced folder can lock SQLite files | WAL off, short transactions, documented |
| PDF generation tooling (no pandoc) | Markdown → HTML (python-markdown) → headless Chrome/Edge print-to-PDF |
