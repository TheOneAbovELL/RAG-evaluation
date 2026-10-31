# Phase 0 — Baseline Audit of the Original Repository

> **Engineering record.** Written during development and kept unedited apart from this note. Sections
> before the restructuring (DEVELOPMENT_LOG §6) use the working names of that time: package `llm_eval`
> (now `rag_workbench`), variables `LLM_EVAL_*` (now `RAGWB_*`), `dashboard.py` (now `streamlit_app.py`),
> `docs/audit/` (now `docs/engineering/`). Paths such as `RAG1/` or `versions/` refer to the reference
> repository, which is not part of this product.

Date of inspection: 2026-10-23. Inspector: Claude (Opus 5.5) acting on TheOneAboveALL's directive.

All observations below were made on an unmodified copy of
`C:\Users\omjee\Downloads\LLM_Evaluation_System-main.zip`, extracted into the
workspace `C:\Users\omjee\OneDrive\Desktop\PROJECTS\RAG Evaluation` (which was
empty beforehand) and also into a scratch copy used for later diffing. The zip
itself was not modified.

## 1. Workspace and version-control state

| Check | Command | Result |
|---|---|---|
| Workspace contents before extraction | `Get-ChildItem -Force -Recurse` | 0 items (empty folder) |
| Git metadata in workspace | `Test-Path .git` | `False` |
| Git metadata in zip | zip entry listing | No `.git` entry (GitHub "Download ZIP" export) |
| Remote configuration | — | Not applicable: no repository, therefore no remotes |
| `.env` file | `ls .env` | Absent; only `.env.example` (17 bytes, one key `OPENAI_API_KEY`, value is not a real key) |
| `OPENAI_API_KEY` in process environment | shell check (value never printed) | Not set |

Consequence: no Git operations were possible or performed. Every change is a local file change.

## 2. Inventory (54 zip entries)

| Path | Size | Role |
|---|---:|---|
| `RAG1/agent.py` | 859 B | LangChain `create_agent` with `gpt-4o`, `ask(question)` |
| `RAG1/tools.py` | 495 B | `collecting_info` retrieval tool, `k=2` hardcoded, global `last_retrieved_context` |
| `RAG1/indexing.py` | 437 B | Embeds PDF blocks with `text-embedding-3-large` **at import time** |
| `RAG1/file_reader.py` | 789 B | PyMuPDF block extraction |
| `RAG1/prompts.py` | 379 B | System prompt |
| `RAG1/objects.py` | 259 B | Pydantic `Answer(answer, context)` |
| `versions/v{1,2,3}/eval_runner*.py` | 857 B each | Run RAG over dataset → `results*.jsonl` |
| `versions/v{1,2,3}/eval_all_metrics*_fast.py` | 3041 B each | DeepEval batch scoring → `evaluated_results*.jsonl` |
| `versions/v1/eval_all_metrics1.py` | 2012 B | Older per-case scorer |
| `versions/v{1,2,3}/evaluation_summary*.py` | 840 B each | Print averages / pass rates |
| `versions/v*/results*.jsonl`, `evaluated_results*.jsonl` | 18–24 KB | Saved run artefacts (20 rows each) |
| `experiment_v{1,2,3}.jsonl` | ~280 B | Run summaries (single JSON object despite `.jsonl`) |
| `eval_dataset.jsonl` | 3.7 KB | 20 `{question, expected_answer}` rows |
| `dashboard.py` | 3.2 KB | Streamlit dashboard over the 3 summaries |
| `compare_experiments.py`, `save_experiment.py` | <1 KB | Helper scripts with hardcoded filenames |
| `single_tests/test_single_eval_*.py` | <1.2 KB | DeepEval single-metric demos (module-level code) |
| `main.py` | 99 B | Placeholder "Hello" |
| `pdfs/Penguins_ACL.pdf` | 104 KB | Source document (10 text blocks) |
| `screenshots/Screenshot_{1..4}.png` | 19–88 KB | Screenshots of the original dashboard |
| `pyproject.toml`, `uv.lock`, `.python-version` | — | uv project, Python `>=3.12`, pin `3.12` |

No model weights, large datasets, or credentials were found.

## 3. Environment

| Item | Observed |
|---|---|
| OS | Windows 11 Home (10.0.26300) |
| System Python | 3.13.3 |
| uv | 0.13.1 |
| `uv sync --frozen` | First attempt failed: network timeout downloading `prompt-toolkit` (30 s default). Retried with `UV_HTTP_TIMEOUT=180`: succeeded, created `.venv` with **Python 3.12.15** |
| Key installed versions | deepeval 4.2.6, langchain 1.4.2, streamlit 1.64.0, pandas 3.0.6, pymupdf 1.28.2, pydantic 2.13.5 |
| pandoc / graphviz / wkhtmltopdf | Not installed |
| Microsoft Edge, Google Chrome, Node.js | Installed |

## 4. Baseline test results (original code, no API key)

| # | Command | Outcome |
|---|---|---|
| B1 | `cd versions/v2 && python evaluation_summary2.py` | **Pass.** Prints averages: AR 1.00, F 1.00, CR 0.78 (12/20 ≥ 0.7), Correctness 0.91 (19/20) |
| B2 | `python compare_experiments.py` | **Fail.** `FileNotFoundError: 'baseline2.json'` (file never existed in repo) |
| B3 | `python save_experiment.py` (root) | **Fail.** `FileNotFoundError: 'evaluated_results3.jsonl'` (only exists under `versions/v3/`) |
| B4 | `extract_paragraphs('pdfs/Penguins_ACL.pdf')` | **Pass.** 10 blocks, 379–501 chars; embedded `\n` remain (regex only strips `\r`, contradicting its comment) |
| B5 | `python -c "import RAG1.agent"` | **Fail.** `openai.OpenAIError: Missing credentials` raised **at import** from `RAG1/indexing.py` |
| B6 | `python main.py` | Pass (prints placeholder) |
| B7 | `python -m pytest -q` | **4 collection errors.** Pytest collects `single_tests/test_*.py`; module-level `metric.measure()` raises `DeepEvalError: OpenAI API key is not configured` |
| B8 | Dashboard via `streamlit.testing.v1.AppTest` | **Pass**, no exceptions; 2 tables, 6 metric tiles; deprecation warnings for `use_container_width` |

Note on B7: DeepEval telemetry is **opt-out** (`DEEPEVAL_TELEMETRY_OPT_OUT`). It was not
disabled during B7, so importing DeepEval may have attempted an anonymous telemetry request
during that one baseline command. From this point on every entry point disables it.

## 5. Data integrity checks on saved runs

Script recomputed means from `versions/vN/evaluated_resultsN.jsonl` and compared them with
`experiment_vN.jsonl`:

| Run | Recomputed means match summary? | `None` scores | Questions identical to dataset? | Stored `context` verbatim substring of PDF |
|---|---|---|---|---|
| v1 | Yes | 0 | Yes | 14 / 20 |
| v2 | Yes | 0 | Yes | 20 / 20 |
| v3 | Yes | 0 | Yes | 17 / 20 |

## 6. Defects and deficiencies found

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| D1 | **Critical (methodology)** | The `context` saved for every case is the LLM's *self-reported* `Answer.context` field, not the chunks actually retrieved. Faithfulness and contextual relevancy were therefore judged against text the model wrote, not against retrieval output. `tools.last_retrieved_context` captures the real chunks but `ask()` never returns it. | `RAG1/agent.py`; §5: up to 6/20 stored contexts are not verbatim PDF text |
| D2 | High | Run labels contradict stored parameters: `experiment_v2_k1` and `experiment_v3_k2` record `retriever_k: 3`; `tools.py` currently has `k=2`; `save_experiment.py` writes label `experiment_v3_k3`. The actual `k` of each saved run is unknowable. | `experiment_v*.jsonl`, `save_experiment.py`, `RAG1/tools.py` |
| D3 | High | Network/API calls and PDF embedding happen at import time; import fails without a key; path `pdfs/...` is CWD-relative. | B5, `RAG1/indexing.py` |
| D4 | High | No offline mode; nothing can run end-to-end without paid OpenAI calls. | B5, B7 |
| D5 | High | No automated tests; `single_tests` are demos that break `pytest`. | B7 |
| D6 | Medium | Configuration hardcoded (models, `k`, threshold, filenames) and duplicated across 10 near-identical version scripts. | `diff` of version scripts shows only filename changes |
| D7 | Medium | Helper scripts reference non-existent files. | B2, B3 |
| D8 | Medium | No error handling: one failed API call aborts the whole run and loses all results (results written only at the end). | `eval_runner*.py` |
| D9 | Medium | No latency, token or cost tracking. No run metadata (timestamp, model, dataset hash). | all runners |
| D10 | Medium | Dashboard limited to 3 hardcoded summary files; cannot run evaluations, inspect cases, or show per-case results. | `dashboard.py` |
| D11 | Low | System prompt names the tool `collection_info`; actual tool is `collecting_info`. | `RAG1/prompts.py`, `RAG1/tools.py` |
| D12 | Low | `eval_all_metrics1.py` writes key `context_relvancy` (typo). | `versions/v1/eval_all_metrics1.py` |
| D13 | Low | Unused dependencies `deepagents`, `numpy`, `langchain-text-splitters`; `dotenv` is a shim package for `python-dotenv`. | `grep` found no imports |
| D14 | Low | Global mutable state (`last_retrieved_context`) is not thread-safe. | `RAG1/tools.py` |
| D15 | Low | `.gitignore` does not ignore `.venv`, caches or generated run data. | `.gitignore` |
| D16 | Low | Summary files named `.jsonl` contain one pretty-printed JSON object. | `experiment_v*.jsonl` |
| D17 | Info | Streamlit deprecation warnings (`use_container_width`). | B8 |
| D18 | Info | DeepEval telemetry enabled by default. | §4 note |

## 7. What already works and is worth keeping

* The RAG concept: PDF → chunks → vector search → LangChain agent with structured output.
* The four DeepEval metrics and their 0.7 threshold (answer relevancy, faithfulness,
  contextual relevancy, GEval correctness).
* The 20-question dataset and the penguin PDF.
* Three saved runs of real historical judge scores (kept and imported read-only, with the
  provenance caveats D1/D2 attached).
* The dashboard's core views (run table, metric chart, run inspector, best-per-metric).
