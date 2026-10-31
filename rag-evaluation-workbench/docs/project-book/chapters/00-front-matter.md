# RAG Evaluation Workbench — The Project Book

**Engineering, operation and methodology of a retrieval-augmented question-answering evaluation system**

| | |
|---|---|
| Product | RAG Evaluation Workbench (`rag_workbench`, CLI `ragwb`, launcher `start.py`) |
| Product version | 1.4.1 (`src/rag_workbench/__init__.py`) |
| Book edition | 1.4.1 (final), built from the source tree as of 2026-10-31 |
| Prepared for | TheOneAboveALL |
| Prepared by | Claude (Opus 5.5), acting as engineer and technical writer |
| Python | 3.12 (developed and tested on CPython 3.12.15, Windows 11) |
| Source of truth | the repository; where this book and the code disagree, the code is right |

## How to read this book

* **Students** can read Parts I, VI and VII first: what the system is for, how its numbers are computed and
  what they mean, and how to use it.
* **Engineers reviewing the code** should read Parts III–V (architecture, implementation, file-by-file
  reference) and IX (testing).
* **Operators** need Part VIII (setup and operation) and XI (limitations).
* Part II explains the analysis behind the design, and Part X records how the work was carried out, including the
  defects found and fixed along the way.

Conventions: `path/to/file.py:123` points at a line in the final source; *verified* means the statement was checked
by running code or tests, and the command is given so it can be repeated; *rationale* marks a design reason;
*limitation* marks something the system does not do. Numbers quoted from evaluation runs are real outputs of the
example runs that `start.py` creates; illustrative examples are labelled as such.

## Executive summary

RAG Evaluation Workbench measures how well a retrieval-augmented question-answering pipeline answers questions
about a document. Given a dataset of questions (optionally with reference answers) and a source document, it
retrieves passages, produces an answer per question, scores every answer with a chosen set of metrics, stores the
whole run with its configuration, and lets the user inspect individual answers next to the exact passages they
were based on and compare runs with paired statistics.

It runs in two modes. **Offline**, with no API key and no network, it uses BM25 retrieval (hybrid BM25 + embedding fusion is available once a key is configured; local-embedding retrieval, `local` and `hybrid-local`, needs only the optional `semantic` extra), an extractive answer
baseline and five lexical metrics (two optional local-embedding metrics can be added with the `fastembed` package); this is how the test suite and the documented examples run. **With an OpenAI-compatible service**,
it can generate answers with a GPT-style model (retrieve-then-generate or a tool-calling agent), retrieve with API
embeddings, and score with four DeepEval LLM-judge metrics.

One command, `python start.py`, prepares the environment, creates five example evaluations over the bundled
honeybee document on the first launch (three more bundled documents, volcanoes, coffee and lighthouses, are there for your own runs), and opens the application in the browser.

Verified state at the time of writing: 455 tests are collected and, offline, 453 pass and 2 are skipped (the opt-in live
test and the opt-in real-model test); statement coverage is 97 % (3,624 statements, 125 missed) excluding the Streamlit
page scripts, which are covered by UI journey tests; `ruff` and `mypy` are clean over 47 source files; the local
verification script runs six steps (environment, lockfile, secrets, static analysis, tests, end to end), an optional
dependency audit and an optional clean wheel install; the UI was exercised in a real browser and audited with axe-core.
Release 1.3 added a narrow live check: generation and the DeepEval judge metrics were run against Groq's free tier through
its OpenAI-compatible endpoint, and a real local embedding model (`BAAI/bge-small-en-v1.5`) was run on all bundled datasets
(Part XV). Release 1.4 ran the tool-calling agent pipeline live on three cases, installed the wheel into an empty environment
and swept pass thresholds against labels written by an AI rater (Part XVI). **OpenAI itself and API embeddings were not called
live, the Docker image was never built, and the judge was never compared with human labels.**

## Abstract

Evaluating retrieval-augmented generation requires measuring two coupled systems — retrieval and generation —
under conditions where ground truth is partial and some metrics are themselves model judgments. This book
documents a local, reproducible evaluation workbench designed around three principles: score what actually
happened (the retrieved context, not a description of it); never hide missing data (skipped and failed scores
are counted, not zeroed); and report uncertainty (bootstrap confidence intervals and paired comparisons). It
describes the system's architecture, every source file, the mathematical definitions of its metrics (five lexical, four LLM-judge and two optional semantic), its
user interface, its operation and its test suite, together with an honest account of its limitations and of how
it was built.

## Contents

The table of contents of the PDF edition is generated from the headings. The Markdown edition is split into:

| File | Part |
|---|---|
| `00-front-matter.md` | Title, version, executive summary, abstract |
| `01-foundation.md` | Part I — Project foundation (chapters 1–14) |
| `02-design-analysis.md` | Part II — Design analysis (15–26) |
| `03-architecture.md` | Part III — System architecture (27–40) |
| `04-core-implementation.md` | Part IV — Core implementation (41–60) |
| `05-file-reference.md` | Part V — Detailed file-by-file reference |
| `06-evaluation-methodology.md` | Part VI — Evaluation methodology |
| `07-user-interface.md` | Part VII — User interface and workflows |
| `08-setup-and-operation.md` | Part VIII — Setup and operation |
| `09-testing-and-qa.md` | Part IX — Testing and quality assurance |
| `10-development-history.md` | Part X — Development history and engineering decisions |
| `11-security-reliability-limitations.md` | Part XI — Security, reliability and limitations |
| `12-reference-material.md` | Part XII — Reference material (with generated appendices) |
| `13-release-1-1.md` | Part XIII — Release 1.1: from working tool to production-grade tool |
| `14-release-1-2.md` | Part XIV — Release 1.2: history, gates, accounts and packaging |
| `15-release-1-3.md` | Part XV — Release 1.3: live verification, pacing, local embeddings, judge noise and roles |
| `16-release-1-4.md` | Part XVI — Release 1.4: recovery, account management, calibration sweeps, an indexed BM25 and a clean install |
