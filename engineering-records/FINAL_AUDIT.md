# Final Audit and Handover Report

Date: 2026-10-24. Every statement below was checked by inspecting the final files or by running the command quoted.

## A. Outcome

**RAG Evaluation Workbench** evaluates a retrieval-augmented question-answering pipeline over a question dataset:
it retrieves passages, answers, scores every answer with up to nine metrics, stores each run with its full
configuration, and lets the user inspect answers next to the exact retrieved context and compare runs with paired
bootstrap statistics — offline by default, with OpenAI generation/embeddings and DeepEval judge metrics when a
key is configured.

* **Inherited from the reference** (as data or ideas, never as source files): the penguin PDF and 20-question
  dataset (byte-identical), three historical judge-scored runs (converted to bundles), the four DeepEval metrics
  with threshold 0.7, the agent design and prompt, PyMuPDF block extraction, OpenAI embedding retrieval.
* **Newly implemented:** everything else — see `CHANGELOG.md` and `docs/REQUIREMENTS_TRACEABILITY.md` (R1–R22,
  all Done; the OpenAI/DeepEval paths are *Done — not live-verified*).

## B. Architecture and implementation

One package (`src/rag_workbench`: 24 module files plus 10 in `ui/`) with two in-process front ends (Streamlit, `ragwb` CLI) and
SQLite history. Details: `docs/ARCHITECTURE.md`, book Parts III–V. Dependencies chosen for this product
(`pyproject.toml`; 117 locked packages), including the evidence-based constraint `pymupdf<2`. Configuration via
`RAGWB_*` variables and optional `.env`; secrets never stored, logged or displayed.

## C. Frontend

Streamlit, six pages (Overview, New evaluation, Run results, Compare runs, Datasets & retrieval, Settings &
metrics). Start: `uv run streamlit run streamlit_app.py`. Verified by 8 AppTest journeys, by running an
evaluation through the real UI in a browser, and by 11 screenshots captured from the running app.

## D. Build and execution

Python 3.12 (3.12.15 used) · `uv sync` · `uv run streamlit run streamlit_app.py` · `uv run ragwb run --name x` ·
`uv run pytest` · `uv run python scripts/verify.py`. Details: `docs/BUILD_AND_RUN.md`.

## E. Verification evidence

| Check | Result | Evidence |
|---|---|---|
| Test suite | 140 passed, 0 failed, 0 skipped | `evidence/test-and-coverage-final.txt` |
| Coverage | 96 % (1,866 statements, 72 missed; `ui/views/*` excluded, covered by AppTest) | same |
| `scripts/verify.py` | 5/5 (environment, lockfile, secret scan, tests + coverage, CLI end-to-end) | `evidence/verify-final.txt` |
| Reproducibility | 5 demo + 3 archived runs recomputed with final code: 0 differences | DEVELOPMENT_LOG §8–9 |
| Independent install | fresh copy, `uv sync --offline --frozen`: 140 passed, verify 5/5 | DEVELOPMENT_LOG §9 |
| PDF | 274 pages, all 12 Parts present and each starting a page, 630 bookmarks, no empty pages | `tools/build_book.py` output |

**Not performed / not verifiable here:** no live OpenAI or DeepEval call (no key; external AI use not authorised);
no dependency vulnerability scan; no formal accessibility audit; no load testing. A `uv run pip-audit` process
was observed on the machine by one writer agent during the session; it was **not** started by the lead or at its
request, and no scan result is part of this project — the owner may want to check where it came from.

## F. Documentation

* Book: `docs/project-book/RAG_Evaluation_Workbench_Project_Book.pdf`; Markdown: `docs/project-book/PROJECT_BOOK.md`;
  sources `docs/project-book/chapters/` (Parts I–XII, all mandatory chapters; Part V covers 37/37 inventoried files).
* Supporting: `README.md`, `CHANGELOG.md`, `docs/ARCHITECTURE.md`, `docs/BUILD_AND_RUN.md`, `docs/TESTING.md`,
  `docs/API_REFERENCE.md`, `docs/KNOWN_LIMITATIONS.md`, `docs/REQUIREMENTS_TRACEABILITY.md`.
* Engineering records: `docs/engineering/REFERENCE_ANALYSIS.md`, `IMPLEMENTATION_PLAN.md`, `DEVELOPMENT_LOG.md`,
  this file, `evidence/`.
* Limitation: line references were verified by writers and re-checked mechanically (no out-of-range or reversed
  references); a heuristic anchor check produced warnings that, on sampling, were false positives. The code is the
  source of truth.

## G. Independent-build audit

| # | Requirement | Result | How checked |
|---|---|---|---|
| 1 | Runs without the reference repository | **Pass** | copy outside the workspace installed offline and passed all tests; `PROJECT_ROOT` resolved to the copy |
| 2 | Dependencies selected for this product | **Pass** | manifest rewritten; unused packages dropped; `pymupdf<2` from profiling |
| 3 | No unnecessary legacy files | **Pass** | none of `RAG1/`, `versions/`, `single_tests/`, `pdfs/`, old scripts, summaries or screenshots exist; caches removed |
| 4 | README describes the final application | **Pass** | rewritten; commands verified |
| 5 | Frontend invokes the new implementation | **Pass** | pages import only `rag_workbench`; AppTest journeys |
| 6 | Tests validate the final implementation | **Pass** | 140 tests, all against `rag_workbench`; `test_no_dependency_on_any_reference_tree` |
| 7 | Documentation describes the final tree | **Pass** | generated tree/inventory from the final source; references re-checked |
| 8 | Runtime independent of the ZIP / extracted folder | **Pass** | grep finds no reference paths in `src/`, `scripts/`, config; item 1 |
| 9 | Reused assets evaluated for licence/attribution | **Pass, with caveat** | the reference has **no licence file**; its PDF, dataset and historical results are reused as examples on the assumption they belong to the project owner, who supplied them — confirm before any public release |
| 10 | A coherent product, not two repositories | **Pass** | single identity (name, package, CLI, env prefix, bundle format) |

## H. Repository and version-control state

* **Git metadata:** none existed — not in the supplied archive, the workspace, the reference copy or the product
  (`Test-Path .git` → False at each level). Consequently there was no remote configuration to inspect or preserve.
* **Read-only checks performed:** directory listings, `Test-Path .git`, file hashing. No `git` command was run.
* **No commits, pushes, pulls, fetches, branches, tags, releases, pull requests, remote changes, deployments or
  publications were performed.** Nothing was uploaded to any service. Network use was limited to downloading
  packages from the Python package index via uv.
* **Reference preservation:** the supplied ZIP was never modified (SHA-256
  `E7F6270F5D11176D19B70614DFD9F7D21004D32F1BF603CC36783A81F08DE56D`, re-checked at the end). `../reference/` holds a
  pristine extraction, verified file-by-file against the archive (45/45 identical) and marked read-only.
  Disclosure: before the restructuring requirement arrived, an earlier working copy extracted into the workspace
  had been modified; it was moved out of the workspace into the session's scratch directory (not deleted).
* **User work:** the workspace was empty at the start; no user file existed to overwrite.
* **Prohibited operations requested and not executed:** none were requested.

## I. Remaining work

1. Live verification of the OpenAI provider, agent pipeline, embedding retriever and judge metrics (small budget).
2. Judge validation against human labels; a dependency vulnerability scan; an accessibility review.
3. Open limitations (`docs/KNOWN_LIMITATIONS.md`): stray possessive tokens in content-token metrics; bootstrap
   order-dependence; judge tokens/cost not counted; heartbeat-based recovery can mislabel a run whose single case
   takes over 15 minutes (its final status is still written); the run store keeps absolute paths locally.
4. Confirm the licensing of the reused example data.

---

## Addendum — final state after the 2026-10-24/27 changes

* Engineering records live here, outside the product. The product contains no reference to them, to the ZIP or to
  the earlier repository; all example data (honeybee document, datasets) was written for the project.
* `python start.py` is the single start file (verified from an empty data directory: environment synced, 5 example
  runs created — 4 completed, 1 partial by design — second start did not re-seed; app served on localhost).
* `scripts/verify.py`: 5/5 (140 tests passed, coverage 96 %). Book: 281 pages, 12 Parts, 640 bookmarks; the PDF text
  contains no reference-repository terms (regex scan: 0 hits).
* Product directory: 117 files (excluding `.venv`); runtime `data/` and caches removed.

## Incident note (2026-10-27)

While removing the verbatim copy of the supplied archive (`reference/`), the safety check compared the copy with
`Downloads\LLM_Evaluation_System-main.zip`. The ZIP was no longer in Downloads, so the comparison covered 0 files and
the "no mismatches" condition passed vacuously; the copy was deleted anyway. This should have failed closed. Impact:
none on the product; the content remains available as the first-step extraction in the session scratch directory
(`...\scratchpad\original\LLM_Evaluation_System-main`, 45 files, never modified). The ZIP's last verified SHA-256 was
`E7F6270F5D11176D19B70614DFD9F7D21004D32F1BF603CC36783A81F08DE56D`.

## Addendum — release 1.1.0 (2026-10-28)

* Version 1.1.0; `scripts/verify.py`: environment, lockfile, secrets, static (ruff + mypy), tests (252 passed, 1 skipped,
  coverage 96 %) and end-to-end all pass. The pip-audit step is optional (`--audit`) and was run separately: no known
  vulnerabilities in the locked runtime requirements at the time.
* Still not verified: any real OpenAI or DeepEval call; judge-versus-human calibration on real labels; hybrid retrieval
  with real embeddings; accessibility audit.
* Git: the project directory still has no Git metadata; no version-control or network-publishing operation was run.
  The only network access this pass was the approved PyPI install of dev tools and the pip-audit advisory query.

## Addendum — release 1.2.0 (2026-10-28)

* Version 1.2.0. Still unverified: every live-service path (OpenAI/Grok/DeepEval), semantic metrics with a real model,
  judge calibration on real labels, Docker image, a real wheel install, keyboard/screen-reader accessibility.
* Git: still no Git metadata in the project; no version-control or publishing operation was run. Network: none this pass
  (TLS probe was to localhost; wheel build used the offline cache).

## Addendum — release 1.3.0 (2026-10-28)

* Network use this pass, all authorised: PyPI (fastembed and its dependencies), Hugging Face hub (one model download),
  Groq API (live runs; example document text and questions were the only project data sent).
* The Groq key supplied in chat appears in the conversation transcript; the owner was advised to rotate it. It is not present in
  any project file (secret scan and a grep of calibration/ passed).
* Git: no Git metadata in the project; no version-control or publishing operation was run.

## Addendum — release 1.4.0 (2026-10-29)

* Open and not closable by the assistant: judge-versus-human calibration (needs a person), OpenAI itself and API embeddings (no key),
  Docker image (no Docker), screen-reader testing (needs a person with a screen reader).
* Git: no Git metadata in the project; no version-control or publishing operation was run (one stray `git stash` typed earlier in the
  session was blocked and never executed).
* The Groq key supplied in chat is in the transcript only; owner advised to rotate it.

## Addendum — release 1.4.1 (2026-10-31)

* The Groq key supplied by the owner is stored in `rag-evaluation-workbench/.env` (git/Docker-ignored). Earlier addenda saying it was in no
  project file are superseded. Exposure to manage: the folder is inside OneDrive (cloud sync), and the key remains in the chat transcript;
  the owner was advised to rotate it when testing is finished.

## Addendum — release 1.4.1, closing record (2026-10-31)

* Verified state: 455 tests collected, 453 passed, 2 skipped (opt-in live and real-model tests), statement coverage 97 % (3,624
  statements, 125 missed; `ui/views/*` excluded). `scripts/verify.py --audit --wheel`: 8/8 at the last full run.
* Changes since the earlier 1.4.1 addendum: the CLI polish fixes, `scripts/set_api_key.py`, and the DeepEval finding (it loaded a real
  `.env` on import and through its pytest plugin; fixed with `DEEPEVAL_DISABLE_DOTENV=1` and `-p no:deepeval`, guarded by
  `tests/test_dotenv_switch.py`). Details are in DEVELOPMENT_LOG, 2026-10-31.
* Books: Project Book (final edition, 439 pages, 16 Parts, zero forbidden-trace hits in the PDF text, no out-of-range line citations,
  13 unresolved citations that are placeholders and examples) and the new Practitioner's Guide (`docs/user-guide/`, 173 pages).
* Disclosed incidents: two agents (a guide writer and the editor, the latter through `calibrate --rescore`) unintentionally triggered a
  request to the Hugging Face hub to fetch a public embedding model. Both failed with WinError 206 (path too long); no key and no
  project data were sent, nothing was downloaded. Network use in this pass was otherwise none.
* Still open and not closable by the assistant: judge-versus-human calibration (no human labels exist), OpenAI itself and API embeddings
  (no key), Docker image (no Docker), screen-reader testing, and rotation of the Groq key that sits in `.env` and in the chat transcript.
* Git: no Git metadata; no version-control or publishing operation was run.
