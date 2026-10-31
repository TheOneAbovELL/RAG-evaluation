# Part II — Design analysis

Part I said what the workbench must do. This Part records the analysis that turned those requirements into a
design: what one evaluation case must capture, which mistakes RAG evaluations commonly make and how the design
prevents each, how technologies, data, metrics and the baseline were chosen, and how the result is verified. Part
III then describes the architecture that came out of it.

## 15. From problem to design

The design was derived in four steps, each recorded in a chapter of this Part:

1. **Unit of evidence (Chapter 16).** Decide what must be recorded for one question so that any number shown later
   can be traced back to inputs, outputs and configuration.
2. **Failure analysis (Chapter 17).** List the ways an evaluation of this kind produces misleading numbers, and
   turn each into a design constraint.
3. **Choices (Chapters 18–22).** Select technologies, example data, metrics, the offline baseline and the storage
   model against those constraints.
4. **Qualities (Chapters 23–26).** Fix the interface, reliability, security and verification strategies.

The guiding rule throughout was: *every number the product shows must be computable again from what it stored*.

## 16. What one evaluation case must capture

| Element | Why it is needed | Where it lives |
|---|---|---|
| Question, reference answer, case id, metadata | the input and the ground truth (when present) | `EvalCase`, copied into `CaseResult` |
| The answer | the output being judged | `CaseResult.answer` |
| **The passages the generator actually saw**, with ids, ranks and scores | faithfulness and retrieval metrics are only meaningful against the true context | `CaseResult.contexts` (`RetrievedChunk`) |
| Where the context came from | the retriever directly, or the agent's tool calls | `CaseResult.context_source` |
| Each metric's status, score, threshold, pass flag and reason | "0.0" and "not computable" must never be confused; reasons make scores explainable | `MetricResult` |
| Latency, tokens, cost, attempts, error | operational quality and failure analysis | `CaseResult` fields |
| The full run configuration, dataset and document hashes, package versions | reproduction and like-for-like comparison | `RunRecord` |

A consequence of this table is that the pipeline interface returns a `Generation` object containing the contexts
alongside the answer: retrieval output is part of the result, not a side effect.

## 17. Pitfalls in evaluating RAG pipelines

Each pitfall below is a way an evaluation can produce confident but wrong numbers. The right-hand column is the
design constraint adopted to prevent it.

| Pitfall | Effect | Constraint adopted |
|---|---|---|
| Scoring the model's own description of its sources (e.g. a "context" field in a structured answer) instead of the retrieved text | faithfulness and context relevancy measure the model's narrative, not the retrieval | contexts are captured from the retriever or the tool call that returned them; any self-report is stored separately and never scored |
| Run labels or file names carrying parameters ("k3") while the code used something else | comparisons silently mix configurations | the complete `RunConfig` is stored with every run; labels are free text and carry no meaning |
| All-or-nothing batch jobs that write results only at the end | one timeout loses every answer | each case is committed as soon as it finishes; failures become recorded case errors |
| Expensive work at import time (building indexes, creating API clients) | nothing can run, or be tested, without credentials and network | every external client is created lazily, on first use |
| A mandatory paid service | development and testing cost money; examiners cannot run it | a complete offline path (BM25, extractive baseline, lexical metrics) |
| Treating "could not score" as zero | means are biased downwards and failures are hidden | `skipped` and `error` statuses, excluded from statistics and counted |
| Comparing means of small samples without uncertainty | noise is read as improvement | bootstrap intervals on every mean; paired comparisons with an explicit "inconclusive" verdict |
| Parameters hard-coded in scripts, duplicated per experiment | drift between copies | one parameterised runner; configuration only through `RunConfig`, CLI flags, UI or environment |
| Unvalidated inputs | crashes mid-run, or quietly wrong data | datasets, documents, bundles and settings validated before any work starts |
| Silent telemetry or secrets in logs | privacy and security exposure | telemetry disabled; keys held as `SecretStr` and redacted from logs and tracebacks |

## 18. Technology selection

| Concern | Choice | Alternatives considered | Reason |
|---|---|---|---|
| Language | Python 3.12 | — | the evaluation and LLM ecosystem is Python-first; the user works in Python |
| Packaging | uv + `pyproject.toml` + `uv.lock`, hatchling editable install | pip + requirements.txt; Poetry | reproducible lock, fast installs; `start.py` falls back to pip when uv is absent |
| Data contracts | pydantic v2 | dataclasses | validation at boundaries (config, bundles, persisted JSON) for free |
| PDF text | PyMuPDF block extraction (< 2.0) | pdfminer, pypdf | robust layout blocks ≈ paragraphs; PyMuPDF 2.0 was excluded after measuring a 3 s model-loading import (Chapter 109) |
| Offline retrieval | own BM25 implementation | rank-bm25 package | about 50 lines, deterministic, no dependency; fully testable against a hand computation and, since release 1.4 (an inverted index, Part XVI §175), against the textbook definition with exact float equality |
| Dense retrieval | OpenAI-compatible embeddings + LangChain `InMemoryVectorStore`; since release 1.3 also a local embedding model (`fastembed`) scored by plain cosine similarity in `LocalEmbeddingRetriever` | FAISS, Chroma | a single document needs no external index |
| Generation | LangChain `ChatOpenAI`; `create_agent` for the agent mode | raw OpenAI SDK | structured output and tool calling with little code; easy to fake in tests |
| Judge metrics | DeepEval | RAGAS, custom prompts | ready, documented metrics for exactly these four properties |
| Persistence | SQLite (stdlib) | JSON files, PostgreSQL | transactional, zero setup, one file |
| UI | Streamlit | Gradio, a JavaScript front end | Python-native, data-oriented widgets and charts; no build tooling |
| Charts | Altair (ships with Streamlit) | matplotlib | interactive, declarative, fixed [0, 1] scales |
| Tests | pytest + Streamlit AppTest | Selenium/Playwright | runs headless and offline in seconds |

## 19. Example data design

The bundled example was written for this project so that it is free to use and its properties are known.

* **Document.** `examples/documents/honeybees.md` — a title and ten paragraphs about honeybee colonies (castes,
  the queen, worker roles, drones, the waggle dance, honey, beeswax, temperature control, swarming, pollination
  and threats). `scripts/make_example_pdf.py` renders it to a two-page PDF with one text block per paragraph, so
  the PDF path of the system is exercised: extraction yields 11 chunks (the title plus ten paragraphs).
* **Main dataset.** `examples/datasets/honeybees.jsonl` — 20 questions (ids `q01`–`q20`), each answerable from one
  paragraph, with **paraphrased** reference answers. Paraphrase is deliberate: it shows the gap between lexical
  overlap and correctness that Part VI discusses.
* **Unanswerable set.** `honeybees_unanswerable.jsonl` — four questions the document cannot answer (reference = the
  standard abstention sentence) and two answerable controls, labelled in `metadata.type`. It tests whether a
  pipeline abstains.
* **CSV variant.** `honeybees_paraphrased.csv` — five further paraphrased questions with a `topic` column,
  exercising the CSV format and metadata columns.

The document's title becoming a retrievable chunk was kept rather than filtered, because real documents have
headings and the effect on retrieval is instructive (Part VI).

## 20. Metric selection

Nine metrics were chosen to cover answer quality and retrieval quality, each with and without a judge model:

| Question asked | Offline (lexical) | With a judge (DeepEval) |
|---|---|---|
| Is the answer correct? | exact match, token F1, ROUGE-L | correctness (GEval) |
| Is the answer supported by its context? | groundedness | faithfulness |
| Did retrieval find what was needed? | context recall | contextual relevancy |
| Does the answer address the question? | — | answer relevancy |

Requirements are declared per metric (`requires_reference`, `requires_context`, `requires_openai`), so the runner
can refuse impossible configurations up front and each case can report *why* a metric was skipped. Thresholds
are configurable per run; the defaults (0.7 for the judge metrics and for lexical context recall and groundedness,
0.5 for token F1 and ROUGE-L, 1.0 for exact match) are conventions, not calibrated values, and the book says so
wherever they appear.

## 21. Offline baseline design

The offline pipeline had to be genuine — producing answers by computation, not canned responses — so that offline
runs exercise every code path and give LLM runs a floor to beat:

* **Retrieval:** BM25 over content tokens (lower-cased, stop words removed, light plural stemming).
* **Generation:** the extractive generator selects up to *n* sentences from the retrieved passages, weighted by the
  inverse document frequency of question terms they contain, and returns them in reading order; if no sentence
  shares a content term with the question it returns the abstention sentence.
* **Known character:** groundedness is ~1.0 by construction (it copies sentences); token F1 is bounded by how much
  the reference paraphrases the document; it rarely abstains. These properties are documented as features of the
  baseline, not hidden.

## 22. Persistence design

Two tables — `runs` and `case_results` — with pydantic models serialised as JSON and a few indexed columns. Cases
are committed one at a time; each commit refreshes the run's heartbeat, so a run whose process died can be told
apart from a run still executing elsewhere. Exchange between machines uses a separate, validated bundle format
rather than copying database files: bundles carry project-relative paths only, and their summaries are recomputed
from the cases on import.

## 23. Interface design principles

* The workflow follows the evaluation itself: data → pipeline → metrics → run → inspect → compare → export.
* Invalid configurations are visible *before* running (disabled button plus the reason), not as a failure later.
* Every number has its provenance one click away: case table → case detail → retrieved chunks and metric reasons.
* Uncertainty is shown with the number: error bars on charts, intervals in tables, "inconclusive" verdicts.
* Costs are announced before an OpenAI run starts.
* Stored text is rendered as text; values that reach HTML are escaped.
* The app opens with real example results (created by `start.py`), so a new user sees what a finished evaluation
  looks like before configuring one.

## 24. Reliability design

| Threat | Response |
|---|---|
| Transient provider errors (rate limits, timeouts, 5xx) | classified (also when wrapped by DeepEval's tenacity `RetryError`), retried with exponential back-off and jitter stretched to the provider's `Retry-After` hint (capped at 60 s), attempts recorded; optional request pacing (`RAGWB_MAX_REQUESTS_PER_MINUTE`) avoids hitting the limit |
| Permanent provider errors (bad key, bad request) | not retried; recorded as the case's error |
| Unexpected exceptions in a case | caught per case; the run continues; the log keeps the traceback |
| User stops the run | finished cases kept; run marked `cancelled` |
| Process dies | finished cases kept; run marked `interrupted` once its heartbeat is 15 minutes old |
| Corrupt or hostile bundle | rejected by format/version/schema validation before anything is written |

## 25. Security and privacy design

The threat model is a single user on their own machine handling possibly sensitive documents and an API key. The
design therefore keeps everything local (data in `data/`, app bound to `localhost`), disables telemetry, never
writes the key anywhere, bounds every input, sanitises uploaded file names, neutralises spreadsheet formulas in CSV
exports, and escapes stored values before they reach HTML. Part XI examines each measure.

## 26. Verification strategy

| Level | Method |
|---|---|
| Functions | unit tests with hand-computed expectations (BM25, F1, ROUGE-L, bootstrap) |
| Modules | contract tests for every error path (datasets, documents, storage, bundles, configuration) |
| External services | fakes: scripted chat model, deterministic fake embeddings, fake DeepEval metrics |
| System | end-to-end offline runs over the example data, reproducibility checks, CLI tests |
| UI | Streamlit AppTest journeys plus manual checks in a real browser and captured screenshots |
| Whole product | `scripts/verify.py` (environment, lockfile, secret scan, static analysis, tests with coverage, CLI end to end) and `python start.py` from an empty data directory |
