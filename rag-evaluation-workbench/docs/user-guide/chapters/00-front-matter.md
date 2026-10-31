# RAG Evaluation Workbench — The Practitioner's Guide

**How to get the best results from the workbench: what to prepare, what to choose, how to read what comes back, and playbooks for real use cases**

| | |
|---|---|
| Product | RAG Evaluation Workbench (`rag_workbench`, command-line tool `ragwb`, launcher `start.py`) |
| Product version | 1.4.1 |
| Guide edition | 1.0, written against the source tree as of 2026-10-31 |
| Prepared for | TheOneAboveALL |
| Companion book | *The Project Book* (engineering, file-by-file reference, methodology and the full test and verification record) |
| Source of truth | the product's own help output and documents: where this guide and the code disagree, the code is right |

## What this guide is, and what it is not

The Project Book explains how the workbench is **built**. This guide explains how to **use** it well. It is organised around the
questions a practitioner actually has: *What should I put in? What should I choose? What do these numbers mean? Is this change an
improvement? How do I keep it running for a team?* Every procedure was written against the real command-line help and, wherever it could
be run without a network or an API key, was run, and the output you see is real output. Anything illustrative is labelled as such.

It is not a theory text. When a metric's formula or the statistics behind a comparison matter, this guide explains them in plain words
and points to the Project Book (for example "Project Book Part VI") for the derivation.

## Reading paths

| If you are... | Read first | Then |
|---|---|---|
| **New to the project**, want results today | Part I (the 15-minute tour), Part IV §4.1 | Part V, Part III |
| **A student or teacher** running labs offline | Part I, Part II, Part VII §7.5 (teaching) | Part V, Part IX (cards) |
| **An engineer changing a RAG pipeline** and needing to know whether it got better | Part III, Part VI §6.1-6.2 (tuning, regression gate) | Part V, Part VII §7.3 (scheduling) |
| **Evaluating with a model provider** (OpenAI-compatible, free tier or paid) | Part III §3.6-3.7, Part IV (live runs) | Part VI §6.4 (judge validation), Part VII §7.4 (cost and quota) |
| **Responsible for a shared deployment** | Part VII §7.1-7.2, Part VIII | Part IX (checklists) |
| **In trouble right now** | Part VIII (symptom-first) | Part IX (command cards) |

## Conventions

* `ragwb ...` means the command-line tool. From the project folder it can be run as `uv run ragwb ...` or, with the project's virtual
  environment, as `python -m rag_workbench ...`; both are the same program.
* A block starting with `>` and a bold label is a call-out: **Pitfall** (a mistake people make), **Why this works** (the reason behind a
  recommendation), **Honest limit** (something the workbench cannot tell you).
* Commands are written for a Unix-style shell. On Windows PowerShell, replace line continuations (`\`) with a backtick and quote paths
  with spaces.
* "Run" means one evaluation (one dataset against one document with one configuration); "case" means one question within a run.

## What was and was not verified

So that you can calibrate how much to trust the advice:

* **Run and observed in this project:** everything offline (BM25 retrieval, the extractive baseline, the lexical and local-embedding
  metrics, storage, export and import, comparison, regression gating, calibration tooling, accounts, backup and restore), and, against one
  OpenAI-compatible provider (Groq's free tier), answer generation, the tool-calling agent pipeline, and the four judge metrics, on small
  samples (the project's `docs/LIVE_VERIFICATION.md` is the record, including what failed).
* **Not run:** anything against OpenAI itself; API embeddings (that provider has none); a human calibration of any judge metric (a
  30-case sheet is waiting for a person; the only labels that exist were written by an AI model and are labelled as such); the container
  image; a screen-reader pass. Where advice in this guide depends on one of these, it says so.
* **Numbers from live runs** in this guide come only from that record and describe one provider, a few models and small samples. They
  illustrate behaviour; they are not benchmarks of any provider.

## Map of the book

| Part | Title | You will learn |
|---|---|---|
| I | Orientation | what the workbench measures, the mental model, installing, a guided tour of the app and the CLI |
| II | Preparing documents and datasets | chunking, file formats, writing good questions and reference answers, building a dataset from scratch |
| III | Choosing a configuration | provider, pipeline, retriever, depth, metrics, thresholds, cost and quota, recommended starting points |
| IV | Running evaluations | the New evaluation page and `ragwb run` in depth, storage, reruns, failures, organising and exchanging runs |
| V | Reading results | summaries, intervals, skipped and errored scores, comparisons, slices, judge noise, calibration, common misreadings |
| VI | Playbooks for improving quality | tuning retrieval, gating changes, unanswerable questions, validating a judge, diagnosing failures |
| VII | Playbooks for teams and operations | accounts, backup and restore, scheduling, cost control, teaching, multiple corpora, wheel and container, the Python API |
| VIII | Troubleshooting and FAQ | symptom-first fixes and answers to the questions people ask most |
| IX | Reference cards | every command, variable and metric; formats; glossary; checklists; a worked end-to-end example |
