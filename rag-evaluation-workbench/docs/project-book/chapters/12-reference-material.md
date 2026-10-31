# Part XII — Reference material

Sections marked *generated* are produced from the code by `docs/project-book/tools/generate_reference.py` and
included verbatim when the book is built, so they always match the source tree the book was built from.

## 120. Complete final directory tree *(generated)*

<!-- include: ../generated/directory-tree.md -->

## 121. Dependency reference

Declared in `pyproject.toml` (minimum versions); exact versions are pinned in `uv.lock`.

| Package | Constraint | Installed | Used for | Where |
|---|---|---|---|---|
| deepeval | ≥ 4.2.6 | 4.3.1 | judge metrics (only with an API key) | `metrics/judge.py` (imported lazily) |
| langchain | ≥ 1.4.2 | 1.4.7 | `create_agent`, `tool` | `pipeline.AgentRAGPipeline` |
| langchain-openai | ≥ 1.6.6 | 1.7.2 | `ChatOpenAI`, `OpenAIEmbeddings` | `providers.py`, `pipeline.py`, `retrieval.py` |
| pandas | ≥ 3.0.6 | 3.1.0 | tables, CSV export | `reporting.py`, UI |
| pydantic | ≥ 2.13 | 2.14.1 | data contracts, settings validation | `models.py`, `config.py`, `archive.py` |
| pymupdf | ≥ 1.28.2, < 2 | 1.28.2 | PDF text blocks | `documents.py` (imported lazily) |
| python-dotenv | ≥ 1.0 | 1.2.4 | optional `.env` loading | `config.load_settings` |
| streamlit | ≥ 1.64.0 | 1.66.1 | user interface (brings altair, used for charts) | `streamlit_app.py`, `ui/` |
| *extra `semantic`:* fastembed | ≥ 0.4 | 0.9.1 (`uv.lock`) | local embedding model: semantic metrics and the `local` / `hybrid-local` retrievers (release 1.3 made it an optional extra; install with `uv sync --extra semantic`) | `metrics/semantic.py`, `pipeline.py` (imported lazily) |
| *dev:* pytest, pytest-cov | ≥ 8.3, ≥ 6.0 | 9.1.1, 7.1.0 | tests, coverage | `tests/` |
| *dev:* ruff, mypy, pip-audit | ≥ 0.8, ≥ 1.13, ≥ 2.7 | see `uv.lock` | lint, type check, dependency audit (release 1.1) | `scripts/verify.py` |
| *docs:* markdown | ≥ 3.7 | 3.11.2 | book Markdown → HTML | `docs/project-book/tools/build_book.py` |
| *build:* hatchling | ≥ 1.25 | (build-time) | editable install | `[build-system]` |

Transitively installed packages that the code imports directly: `openai` (error classes, `errors.py`),
`langchain_core` (messages, vector store, fake models in tests), `altair` (charts), `httpx` (tests only),
`websockets` and `PIL` (documentation tooling only).

## 122. Environment-variable reference *(generated)*

<!-- include: ../generated/env-vars.md -->

Blank values are treated as unset. Relative paths are resolved against the project root. Invalid values stop
start-up with `ConfigError: Invalid configuration: <VARIABLE>: <reason>`.

## 123. Configuration reference

| File | Purpose |
|---|---|
| `.env` (not committed) | secrets and overrides; template `.env.example` |
| `.streamlit/config.toml` | `gatherUsageStats = false`, `toolbarMode = "minimal"`, `maxUploadSize = 25` (MB), `headless = true`, primary colour |
| `pyproject.toml` | dependencies, `ragwb` script, pytest markers, coverage scope |
| `.python-version` | `3.12` for uv |
| Per run: `RunConfig` | name, dataset/document paths, provider, pipeline, retriever (`bm25`, `embedding`, `hybrid`, `local` or `hybrid-local`), k (1–50), metrics, thresholds, models, workers (1–32), retries (0–10), request timeout, case timeout, answer sentences, limit, notes, failure rate, `min_evidence`, `skip_headings`, seed |

## 124. API reference

There is no HTTP API. The CLI and the Python entry points are documented in `docs/API_REFERENCE.md`; every
public function and class with its line number is in the source inventory (Appendix A).

## 125. CLI reference *(generated)*

<!-- include: ../generated/cli-reference.md -->

## 126. Data schemas

### Dataset (JSONL)

One JSON object per line: `question` (string, required, non-empty), `expected_answer` (string, optional),
`id` (string or integer, optional; default `case-NNN` by position), `metadata` (object, optional). CSV: header with
`question`; optional `expected_answer`, `id`; other columns become metadata.

### SQLite (`data/runs.db`, `PRAGMA user_version = 2`)

```sql
CREATE TABLE runs (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL,
    created_at TEXT NOT NULL, finished_at TEXT, config_json TEXT NOT NULL,
    dataset_sha256 TEXT, document_sha256 TEXT, n_cases INTEGER NOT NULL DEFAULT 0,
    summary_json TEXT, environment_json TEXT NOT NULL DEFAULT '{}', notes TEXT,
    heartbeat_at TEXT);   -- added in schema 2; refreshed on every committed case
CREATE TABLE case_results (
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE, case_id TEXT NOT NULL,
    position INTEGER NOT NULL, status TEXT NOT NULL, data_json TEXT NOT NULL,
    PRIMARY KEY (run_id, case_id));
CREATE INDEX idx_runs_created ON runs(created_at);
```

(from `src/rag_workbench/storage.py`). A version-1 store is migrated in place by adding `heartbeat_at`. `config_json`, `summary_json` and `data_json` hold the pydantic models
`RunConfig`-derived dict, `RunSummary` and `CaseResult` as JSON.

### Run bundle

`{"format": "rag-workbench-run", "version": 1, "run": RunRecord, "cases": [CaseResult, …]}` — see
`docs/API_REFERENCE.md`.

## 127. Example inputs and outputs

**Input** — first line of `examples/datasets/honeybees.jsonl`:

```json
{"id": "q01", "question": "How many queens does a typical honeybee colony have?", "expected_answer": "A colony normally has a single queen."}
```

**Output** — the summary printed by `ragwb show` for the example run `offline-bm25-k3` (k = 3, BM25, extractive
generator; real output):

```text
metric                          mean           95% CI    pass  scored  skip  err
Token F1                       0.346      0.285-0.419      5%      20     0    0
ROUGE-L                        0.317      0.252-0.393      5%      20     0    0
Context recall (lexical)       0.885      0.839-0.930     95%      20     0    0
Groundedness (lexical)         1.000      1.000-1.000    100%      20     0    0
```

**Output** — `ragwb compare` of k = 1 (A) against k = 3 (B), abridged columns (real output):

```text
                   label  paired_cases  mean_a  mean_b  diff_b_minus_a  ci_low  ci_high  ci_excludes_zero
                Token F1            20   0.404   0.346          -0.057  -0.116   -0.008              True
Context recall (lexical)            20   0.857   0.885           0.028   0.000    0.062             False
```

Retrieving more passages helped context recall slightly but *lowered* token F1 significantly: the extractive
baseline then picks some sentences from less relevant passages (Part VI).

More worked examples, including single-answer scoring with `ragwb score`, are in Part VI.

## 128. Error catalogue

Messages are quoted from the source (placeholders in angle brackets). The CLI prints them as `error: …`; the UI
shows them in an error box.

| Message | Raised by | Meaning / action |
|---|---|---|
| `Invalid configuration: <VAR>: <reason>` | `config.load_settings` | fix the environment variable |
| `OPENAI_API_KEY is not set; it is required for <the OpenAI provider / the embedding retriever> …` | `pipeline._require_key` | set the key or use offline + BM25 |
| `Metric(s) <names> use an OpenAI judge model and need OPENAI_API_KEY.` | `metrics.validate_metric_names` | as above, or drop judge metrics |
| `Unknown metric(s): <names>. Available: …` / `Select at least one metric` | same | choose valid metrics |
| `The agent pipeline needs a tool-calling LLM; choose provider 'openai' or pipeline 'rag'.` | `pipeline.build_pipeline` | offline mode has no agent |
| `Invalid threshold(s): {…}; thresholds must be in [0, 1] for known metrics` | `runner.prepare` | fix `--threshold` |
| `Bad --threshold <item>; expected metric=value` | `cli.build_config` | syntax |
| `Dataset '<name>' is invalid: line N: <problem>; …` | `datasets.load_dataset` | see dataset issues below |
| dataset issues: `invalid JSON (…)`, `expected a JSON object`, `missing or empty 'question'`, `'expected_answer' must be a string`, `duplicate id '<id>' (first seen on line N)`, `'<field>' is N characters; the limit is M`, `dataset exceeds the limit of N cases`, `file is not valid UTF-8`, `unsupported file type`, `CSV header must include a 'question' column`, `dataset contains no cases` | `datasets.parse_dataset` | fix the file at the given line |
| warnings: `duplicate question`, `N case(s) have no expected_answer; reference-based metrics will be skipped`, `ignored unknown field(s)` | same | informational |
| `Document not found` / `Unsupported document type` / `Document is N bytes; the limit is M bytes` / `No extractable text found` / `Could not open PDF` / `<name> is not valid UTF-8 text` | `documents.load_chunks` | supply a readable .pdf/.txt/.md |
| `Bundle not found` / `… is larger than N bytes` / `… is not valid UTF-8 JSON` / `… is not a 'rag-workbench-run' bundle` / `… unsupported bundle version` / `… failed validation` / `… contains duplicate case ids` | `archive.load_bundle` | use a bundle written by `export --format json` |
| `No run with id '<id>'. Use 'list' to see run ids.` | `cli._get_run` | |
| `'<ref>' matches N runs (...); give more of the id.` | `cli._get_run` (release 1.4.1: unique prefix, suffix of 4 or more characters, or exact name; several matches are an error) | |
| `A run with id '<id>' already exists` / `Case '<id>' already recorded …` / `Run '<id>' not found` / `Cannot open run store …` / `… was created by a newer version (schema N)` | `storage.RunStore` | storage problems; the last means the database is from a newer release |
| `File type <ext> not allowed; …` / `File is N bytes; the limit is M bytes` / `Invalid upload filename` | `services.save_upload` | upload restrictions |
| per-case `OpenAI <ErrorType>: … (gave up after N attempts)` | `errors.classify_openai_error`, `runner` | transient error persisted through retries; case recorded as error |
| per-case `OpenAI rejected the API key (AuthenticationError). Check OPENAI_API_KEY.` | same | not retried |
| per-case `Model returned an empty answer` / `Agent returned no structured answer` | `providers`, `pipeline` | case recorded as error |
| per-case `Injected offline failure (offline_failure_rate > 0)` | `providers.ExtractiveGenerator` | testing aid working as intended |
| per-case `Unexpected <Type>: …` / `Internal <Type>: …` | `runner` | a bug or unforeseen input; the run continues and the log has the traceback |
| metric skip reasons: `no expected_answer for this case`, `no retrieved context for this case`, `answer abstained; nothing to ground`, `reference answer is an abstention (unanswerable case)`, `reference answer has no content terms`, `answer has no content terms` | `metrics` | score excluded from means and counted as skipped |

## 129. Troubleshooting guide

See Part VIII for the full guide. Most common: slow package downloads (`UV_HTTP_TIMEOUT`); a changed package not
taking effect in the UI (restart Streamlit); "OPENAI_API_KEY is not set" (expected offline); port 8501 in use
(`--server.port`).

## 130. Reproducibility checklist

1. `uv sync` from the committed `uv.lock` (same package versions).
2. Same dataset and document: compare the SHA-256 values shown on the run's Configuration tab
   (`honeybees.jsonl` → `7eff99c3…`, `honeybees.pdf` → `7e743ff0…`).
3. Same `RunConfig` (exported in every JSON bundle and Markdown report).
4. Offline runs are deterministic: rerunning a configuration reproduces every answer and score
   (`tests/test_runner.py::test_offline_runs_are_reproducible`); only run ids and timestamps differ.
5. Bootstrap intervals use a fixed seed (12345) and 2,000 resamples, so equal scores give equal intervals.
6. Judge metrics are not deterministic: record the judge model and expect small differences between reruns.
7. The example runs are created by `python start.py` on first launch (or again with
   `uv run python scripts/seed_demo_runs.py`); `honeybees.pdf` is regenerated from its Markdown source with
   `uv run python scripts/make_example_pdf.py` (identical text blocks; PDF metadata timestamps differ).
8. `ragwb rerun RUN_ID` repeats a stored run from its recorded configuration and warns if the dataset or document hash has
   changed since (release 1.1, Part XIII §143.4).

## 131. Requirements traceability matrix

<!-- include: ../../REQUIREMENTS_TRACEABILITY.md -->

## 132. Glossary

See Chapter 14.

## 133. Further reading and references

These describe the methods implemented; they were not consulted for any number reported in this book.

* S. Robertson and H. Zaragoza, "The Probabilistic Relevance Framework: BM25 and Beyond", *Foundations and Trends
  in Information Retrieval* 3(4), 2009 — the BM25 ranking function (`retrieval.BM25Retriever`).
* P. Rajpurkar, J. Zhang, K. Lopyrev and P. Liang, "SQuAD: 100,000+ Questions for Machine Comprehension of Text",
  EMNLP 2016 — exact match and token F1, and the answer normalisation used by `text.squad_normalize`.
* C.-Y. Lin, "ROUGE: A Package for Automatic Evaluation of Summaries", ACL Workshop on Text Summarization Branches
  Out, 2004 — ROUGE-L (`metrics.lexical.rouge_l`).
* B. Efron and R. Tibshirani, *An Introduction to the Bootstrap*, Chapman & Hall, 1993 — percentile bootstrap
  intervals (`aggregate.bootstrap_ci`).
* Y. Liu et al., "G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment", EMNLP 2023 — the idea behind
  DeepEval's `GEval` metric.
* P. Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks", NeurIPS 2020 — RAG.
* Documentation of DeepEval, LangChain, Streamlit, PyMuPDF and uv for the APIs used (versions in Chapter 121).

## 134. Final completion checklist

| Item | State |
|---|---|
| Source code, tests, configuration, example data | complete |
| Offline end-to-end operation | verified |
| OpenAI / DeepEval live operation | verified **narrowly** in release 1.3: generation and the four judge metrics on Groq's free tier, small samples; release 1.4 added the agent pipeline (3 of 3 cases) and a 20-question four-judge run in which faithfulness (6 of 20 scored) and context relevancy (1 of 20) were mostly lost to the provider's token cap; OpenAI itself and API embeddings **not run live** |
| UI journeys | verified (AppTest + browser) |
| Documentation set and this book | complete; PDF built and inspected |
| One-command start (`python start.py`) | verified from an empty data directory |
| Static analysis (ruff, mypy) | clean (release 1.1; re-run for 1.4 over 47 source files) |
| Dependency audit | no known vulnerabilities at one point in time (release 1.1, point-in-time) |
| Scale benchmark (offline) | measured, 200 to 5,000 cases (release 1.1) |
| Live smoke script | guarded; run against Groq's free tier (2 cases, 12 of 12 checks, release 1.3); **never run against OpenAI** |
| Semantic metrics (release 1.2) | run with a real model (`BAAI/bge-small-en-v1.5`) in release 1.3; scores sit between 0.63 and 0.76 for extractive answers and the 0.7 thresholds are **uncalibrated** |
| Wheel and Dockerfile (releases 1.2, 1.4) | wheel installed with its dependencies into an empty environment and checked 10 of 10 in release 1.4 (command-line tool only); **Docker build not tested** |
| Accessibility (releases 1.2-1.4) | scripted check of five pages, two defects fixed; axe-core 4.10.2: no violations on six page views, one minor third-party issue; keyboard walks of three pages (no trap); the other pages, screen readers and zoom **not tested** |
| Judge versus human labels (releases 1.3, 1.4) | a 30-case labelling sheet exists in `calibration/`; **no human labels have been entered**, so no human calibration result exists; threshold sweeps were run against labels written by an AI rater (release 1.4) and no default was changed |
| Restore, concurrency, accounts, BM25 index (release 1.4) | tested (39 new tests); the restore of an unreadable store needs a manual step (Part XVI §171.6) |
| TLS (release 1.2) | checked with a self-signed certificate only |
| Git / remote operations | none performed (no repository exists) |

## 135. Future roadmap

See `docs/KNOWN_LIMITATIONS.md` § Future work: labelling the supplied sheet and running `ragwb calibrate` for the `correctness` judge metric, live
checks against OpenAI itself (agent pipeline, API embeddings, hybrid with API embeddings), calibrating or replacing the semantic metrics'
thresholds, database-level separation of runs and an e-mail password reset (accounts, TLS, three roles, an Accounts page and a UI-level run filter exist since 1.4), building the Docker image
(the wheel now installs cleanly), and a fuller accessibility audit with a screen reader and keyboard-only use of every page.

## Appendix A — Source inventory *(generated)*

<!-- include: ../generated/source-inventory.md -->

## Appendix B — Metric catalogue *(generated)*

<!-- include: ../generated/metric-catalogue.md -->

## Appendix C — Test catalogue *(generated)*

<!-- include: ../generated/test-catalogue.md -->
