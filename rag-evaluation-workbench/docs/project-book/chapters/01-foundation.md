# Part I — Project foundation

## 1. Title page and project identity

**RAG Evaluation Workbench** is a local Python application for evaluating retrieval-augmented question-answering
pipelines. Its identifiers are used consistently across the product:

| Identifier | Value | Where |
|---|---|---|
| Product name | RAG Evaluation Workbench | UI title, README, page title (`streamlit_app.py`) |
| Distribution name | `rag-evaluation-workbench` | `pyproject.toml` |
| Python package | `rag_workbench` | `src/rag_workbench/` |
| Launcher | `start.py` | project root |
| Command-line tool | `ragwb` | `[project.scripts]` in `pyproject.toml` |
| Environment-variable prefix | `RAGWB_` | `src/rag_workbench/config.py` (`ENV_VARS`) |
| Run bundle format | `rag-workbench-run`, version 1 | `src/rag_workbench/archive.py` |

*Rationale for the name.* The product evaluates retrieval-augmented pipelines specifically, not language models in
general, and it is meant to be used iteratively — configure, run, inspect, compare, repeat — which is what a
workbench is for. The short forms `rag_workbench` and `ragwb` avoid collisions with existing evaluation libraries'
import names.

## 2. Version information and documentation date

| Item | Value |
|---|---|
| Product version | 1.4.1 |
| Documentation date | 2026-10-31 |
| Python | ≥ 3.12; pinned to 3.12 in `.python-version`; tested on CPython 3.12.15 |
| Key dependencies (as locked and installed) | Streamlit 1.66.1, pandas 3.1.0, pydantic 2.14.1, PyMuPDF 1.28.2 (constrained below 2.0, see Chapter 109), LangChain 1.4.7, langchain-core 1.7.0, langchain-openai 1.7.2, openai 3.37.0, DeepEval 4.3.1, python-dotenv 1.2.4 |
| Development dependencies | pytest 9.1.1, pytest-cov 7.1.0; docs group: Markdown 3.11.2 |
| Lock file | `uv.lock`, 152 packages (117 in release 1.0; the dev group gained ruff, mypy and pip-audit, and release 1.3 added the optional `semantic` extra, `fastembed`, with its dependencies); `pyproject.toml` states minimum versions only |
| Operating system used for verification | Windows 11 Home 10.0.26300 |

The exact version of every installed package for a given run is recorded in that run's `environment` field
(`runner.environment_info`) and shown on the Run results → Configuration tab.

## 3. Executive summary

See the front matter. In one sentence: the workbench turns "ask questions about a document and see whether the
answers are good" into a repeatable experiment with recorded configuration, per-answer evidence, honest statistics
and a usable interface — offline by default, with OpenAI and DeepEval as optional, explicitly costed extensions,
started by a single command.

## 4. Abstract

See the front matter.

## 5. Problem statement

A retrieval-augmented generation (RAG) system answers a question in two steps: it *retrieves* passages from a
corpus and *generates* an answer conditioned on them. When such a system gives a bad answer, the cause can be
retrieval (the right passage was not found), generation (the passage was found but misused), or the evaluation
itself (the reference answer is paraphrased, the judge is unreliable, the sample is too small). A useful
evaluation tool therefore has to:

1. run the pipeline over many questions under a precisely recorded configuration;
2. keep, for every answer, the exact passages the generator saw;
3. score retrieval and generation separately, with metrics whose requirements and failure modes are explicit;
4. distinguish "scored zero" from "could not be scored";
5. quantify uncertainty, because evaluation sets are small;
6. compare configurations case by case rather than only by averages;
7. survive individual failures (timeouts, rate limits, malformed outputs) without losing work;
8. be usable without paid services, so that development and testing do not cost money;
9. be easy to start: one command from a fresh checkout to a working application.

## 6. Motivation and background

**Retrieval-augmented generation** grounds a language model's answers in external documents, reducing
unsupported statements and letting the knowledge base change without retraining. Its quality depends on the
retriever (which passages are found, typically the top *k* by a similarity score), on the generator (whether it
uses those passages faithfully), and on their interaction (more passages raise the chance that the answer is
present but add distracting text).

**Evaluation approaches** fall into two broad families, both implemented here:

* *Reference-based lexical metrics* compare the answer with a human-written reference answer by word overlap —
  exact match and token F1 as used for extractive question answering (SQuAD), and ROUGE-L from summarisation.
  They are cheap, deterministic and reproducible, but blind to paraphrase.
* *LLM-as-a-judge metrics* ask a language model to assess an answer against a rubric — whether it addresses the
  question, whether its claims are supported by the context, whether it agrees with the reference. They capture
  meaning but are themselves model outputs, vary between judge models, and cost money.

Retrieval quality can be measured separately from answer quality: if the words of the reference answer are not
in the retrieved passages, no generator could have produced it from them. The workbench's lexical *context
recall* implements exactly this proxy; DeepEval's *contextual relevancy* is the judge-based counterpart.

The bundled example is deliberately small — a two-page document about honeybee colonies, written for this
project, and twenty questions — which makes every answer inspectable by a person. That smallness is also the main
statistical limitation, and the reason confidence intervals and paired comparisons are first-class features.

## 7. Objectives

| # | Objective | Measured by |
|---|---|---|
| O1 | Evaluate a RAG pipeline over a question dataset end to end | an offline run completes for the bundled dataset (verified) |
| O2 | Score what actually happened | stored context equals retriever output (test `test_rag_pipeline_evaluates_exactly_the_retrieved_chunks`) |
| O3 | Work without network or keys | full test suite runs with an empty `OPENAI_API_KEY` |
| O4 | Support real LLM generation and judging when configured | OpenAI and DeepEval adapters (tested with fakes) |
| O5 | Make results reproducible and auditable | configuration, hashes and package versions stored per run |
| O6 | Make uncertainty visible | bootstrap CIs on every mean; paired comparison verdicts |
| O7 | Be robust to failures | per-case error capture, retries, cancellation, interruption recovery |
| O8 | Provide a usable interface | six-page Streamlit app with UI journey tests (and, since release 1.2, a scripted accessibility check, Part XIV §158) |
| O9 | Start with one command | `python start.py` (verified from an empty data directory) |
| O10 | Be documented to the level of the code | this book and its generated appendices |

## 8. Scope and explicit non-goals

**In scope:** single-document (or single-corpus-file) question answering; datasets in JSONL or CSV; PDF, TXT and
Markdown documents; BM25, API-embedding, hybrid (reciprocal-rank-fusion) and local-embedding retrieval (`bm25`, `embedding`, `hybrid`, `local`, `hybrid-local`); offline extractive and OpenAI generation (two pipeline
shapes); eleven metrics (five lexical, four LLM-judge, and two optional semantic metrics that need a local embedding model); local SQLite history; CSV, JSON and Markdown exports; run bundles; a Streamlit UI, a CLI and
a one-command launcher.

**Non-goals** (deliberate, with reasons):

| Non-goal | Reason |
|---|---|
| A hosted multi-user service, an identity platform (password reset, per-user separation of runs), an HTTP API (release 1.1 adds an optional shared password, Part XIII; release 1.2 adds named accounts and TLS for a small trusted team, Part XIV; release 1.3 adds three coarse roles, viewer, editor and admin, Part XV; release 1.4 adds an admin Accounts page, password change and an optional UI-level run filter, Part XVI) | the users are individuals on their own machines; both front ends call the package in-process |
| Training or fine-tuning models | evaluation only |
| Multi-document corpora with metadata filtering, vector databases | an in-memory index is sufficient at the document sizes targeted; a vector store would add operational weight without a requirement |
| Model providers other than OpenAI-compatible ones | one well-supported API shape keeps the scope testable; any service that speaks the OpenAI protocol works through `OPENAI_BASE_URL` (release 1.3 ran one, Groq's free tier, live: Part XV) |
| Benchmark leaderboards or claims about model quality | the bundled dataset is too small to support general claims |
| Human annotation workflows | recommended as future work for judge validation |

## 9. Stakeholders and intended users

| Stakeholder | Interest |
|---|---|
| The project owner (a student) | a complete, explainable, demonstrable evaluation system and its documentation |
| A developer of a RAG pipeline | find out which configuration (retriever, *k*, model, prompt) answers better, and why individual answers fail |
| A reviewer or examiner | check that numbers are genuine, methods are sound and limitations are stated |
| A future maintainer | understand the code quickly and change it safely (tests, references) |

## 10. Functional requirements

The traceability matrix (`docs/REQUIREMENTS_TRACEABILITY.md`, reproduced in Part XII) maps each requirement to code
and tests. In summary:

| ID | Requirement |
|---|---|
| R1 | Answer questions about a document with a retrieval-augmented pipeline |
| R2 | Evaluate over a dataset of questions with optional reference answers |
| R3 | Provide LLM-judge metrics: answer relevancy, faithfulness, contextual relevancy, GEval correctness (threshold 0.7) |
| R4 | Summarise each metric: mean, pass/fail counts, pass rate, uncertainty |
| R5 | Compare runs; show the best run per metric |
| R6 | Make *k* and every other parameter configurable without editing code |
| R7 | Provide a Python-native user interface |
| R8 | Start the whole application with one command |
| R9 | Run end to end without network or keys |
| R10 | Use provider adapters with explicit variables, timeouts and retries |
| R11 | Record real retrieved context, latency, tokens and errors per case |
| R12 | Tolerate partial failures and interruptions without losing completed work |
| R13 | Persist runs with reproducibility metadata |
| R14 | Export CSV, JSON and Markdown; re-import JSON |
| R15 | Validate datasets with actionable, line-numbered errors |
| R16 | Support the workflow configure → run with progress → inspect → compare → export → history in the UI |
| R21 | Score a single answer ad hoc |
| R22 | Ship example data owned by the project |

## 11. Non-functional requirements

| ID | Requirement | How it is met |
|---|---|---|
| N1 | Import safety: importing never needs a key or the network | lazy construction of every external client (Part IV) |
| N2 | Determinism of the offline path | BM25 ties broken by document order; extractive selection deterministic; bootstrap seeded |
| N3 | No secret disclosure | `SecretStr`; `public_dict()`; log and traceback redaction; secret scan in `verify.py` |
| N4 | Bounded inputs | size and count limits for datasets, documents, fields and bundles (`Settings`) |
| N5 | Reasonable local footprint | SQLite; no services to run; one command to start |
| N6 | Testability | 455 collected tests (453 run offline, 2 opt-in tests skipped: one live, one with a real model); fakes for every external dependency |
| N7 | Platform | developed and verified on Windows; paths handled with `pathlib`; the launcher uses only the standard library |
| N8 | Privacy | no telemetry (DeepEval opt-out, Streamlit usage statistics off); data stays in `data/`; app bound to localhost |

## 12. Acceptance criteria

1. `python start.py` sets up the environment and serves the UI; the first launch creates example runs.
2. An offline evaluation of the bundled dataset completes from the UI and from the CLI.
3. Each case shows the answer, the reference, the retrieved passages with scores, and every metric's result and reason.
4. Two runs can be compared, with confidence intervals and a per-case paired analysis.
5. A failing case is recorded with its error and does not stop the run.
6. Invalid datasets and impossible configurations are rejected before a run starts, with a clear message.
7. Results export to CSV, JSON and Markdown; JSON exports re-import.
8. The test suite passes offline; `scripts/verify.py` passes.

All eight were met at the time of writing; the evidence is listed in the acceptance-test matrix (Part XII).

## 13. Assumptions, constraints and dependencies

* **Assumption:** the dataset's reference answers are correct and written from the document. The bundled ones were
  written for the honeybee document; they are paraphrases, not extracts, which matters for lexical metrics.
* **Assumption:** one source document per run. Multiple documents can be concatenated into one text file.
* **Constraint:** no paid API calls or external AI services were authorised during development (release 1.3 added a narrow live check on a free tier, Part XV; release 1.4 added a live agent-pipeline run on the same tier, Part XVI), so most of the OpenAI
  paths could not be exercised live.
* **Constraint:** the environment is a student's Windows laptop; setup must be one command and need no services.
* **Dependency:** OpenAI's API for the optional generator, embeddings and judge; DeepEval's metric implementations
  and prompts for the judge metrics (their exact prompts belong to the installed DeepEval version, 4.3.1).
* **Dependency:** PyMuPDF for PDF text extraction (block-level layout analysis) and for generating the example PDF.
* **Example data:** the honeybee document, its PDF rendering and all datasets were written for this project.

## 14. Glossary

| Term | Meaning in this project |
|---|---|
| Abstention | an answer that declines to answer; recognised by `text.is_abstention` (e.g. "does not provide enough information") |
| Agent pipeline | a LangChain tool-calling agent that decides when and how to call the retrieval tool |
| BM25 | Okapi BM25, a term-frequency / inverse-document-frequency ranking function |
| Bootstrap CI | a confidence interval obtained by resampling cases with replacement and taking percentiles of the resampled means |
| Bundle | a JSON file containing one run and its case results (`rag-workbench-run` format) |
| Case | one dataset row: a question, optional reference answer and metadata |
| Chunk | a retrievable unit of the document (a PDF text block or a paragraph), id `p{page}-b{n}` |
| Context | the passages given to the generator for one question |
| Context recall (lexical) | share of the reference answer's content terms present in the context |
| DeepEval | the open-source library providing the judge metrics |
| Example runs | the five offline runs `start.py` creates on first launch (`rag_workbench.demo`) |
| Extractive generator | the offline baseline that answers with the best-matching sentences from the context |
| Faithfulness | (judge) share of the answer's claims supported by the context |
| GEval | DeepEval's rubric-based judge metric, used for correctness |
| Groundedness (lexical) | share of the answer's content terms present in the context |
| Judge | the language model that scores answers in LLM-as-a-judge metrics |
| *k* | the number of chunks retrieved per query |
| Lexical metric | a metric computed from word overlap |
| Paired comparison | comparing two runs question by question rather than by their averages |
| Pass rate | share of scored cases whose score is at least the metric's threshold |
| Provenance warning | a note stored with an imported run explaining why its numbers need care |
| RAG | retrieval-augmented generation |
| Reference answer | the dataset's expected answer for a question |
| Run | one execution of a pipeline over a dataset with fixed configuration |
| Skipped | a metric that could not be computed for a case (missing input); excluded from means |
| Token F1 | harmonic mean of precision and recall of answer tokens against reference tokens |
