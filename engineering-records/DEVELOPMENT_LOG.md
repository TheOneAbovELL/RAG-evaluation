# Development Log

> **Engineering record.** Written during development and kept unedited apart from this note. Sections
> before the restructuring (DEVELOPMENT_LOG §6) use the working names of that time: package `llm_eval`
> (now `rag_workbench`), variables `LLM_EVAL_*` (now `RAGWB_*`), `dashboard.py` (now `streamlit_app.py`),
> `docs/audit/` (now `docs/engineering/`). Paths such as `RAG1/` or `versions/` refer to the reference
> repository, which is not part of this product.

Chronological engineering record. All entries are from 2026-10-23 (single working session);
times are approximate sequence, not timestamps. Command outputs quoted here were observed, not
reconstructed.

## 1. Inspection and baseline

1. Workspace `RAG Evaluation` found empty; no Git metadata anywhere. Zip extracted to the workspace
   and to a scratch baseline copy.
2. Read every source file, the README and the data files. Recorded inventory and 18 findings
   (D1–D18) in `docs/audit/PHASE0_BASELINE.md`.
3. `uv sync --frozen` failed once on a 30 s network timeout (prompt-toolkit wheel); succeeded with
   `UV_HTTP_TIMEOUT=180` (Python 3.12.15 venv).
4. Baseline runs: summary script OK; `compare_experiments.py` and `save_experiment.py` crash on
   missing files; `import RAG1.agent` raises `OpenAIError: Missing credentials`; `pytest` has 4
   collection errors from `single_tests/`; original dashboard renders in `AppTest` with deprecation
   warnings.
5. Integrity script: saved summaries equal the means of the saved evaluated results, but only
   14/20 (v1), 20/20 (v2), 17/20 (v3) stored contexts are verbatim PDF text → discovered **D1**: the
   pipeline stored the model's self-reported context instead of the retrieved chunks.
6. Noted that DeepEval telemetry is opt-out and was not disabled during baseline step 4's pytest
   run.

## 2. Planning

* Wrote `docs/audit/IMPLEMENTATION_PLAN.md`: requirements R1–R20 derived from README + directive;
  decided on a single `llm_eval` package with thin CLI/UI front ends, lazy construction, real
  context capture, offline BM25 + extractive baseline, SQLite history.
* Alternatives rejected: keeping per-version script copies (duplication D6); a FastAPI backend
  (no requirement for an HTTP API; Streamlit calls the package directly); FAISS/Chroma (10 chunks,
  an in-memory store is sufficient and already a dependency).

## 3. Dependencies

* Removed unused `deepagents`, `numpy` (still installed transitively by pandas),
  `langchain-text-splitters`; replaced the `dotenv` shim with `python-dotenv`; added `pydantic`
  explicitly; added `dev` (pytest, pytest-cov) and `docs` (markdown) groups. `uv lock` + `uv sync`
  succeeded; lock removed google-genai, langchain-anthropic and others pulled in by deepagents.

## 4. Core package

* Implemented `llm_eval/` modules: config, models, text, documents, datasets, retrieval, errors,
  prompts, providers, pipeline, metrics (base, lexical, judge), aggregate, storage, runner, legacy,
  reporting, logging_setup, services, cli.
* DeepEval API checked against the installed 4.2.6 (`OpenAIModel` replaces deprecated `GPTModel`;
  default judge would be `gpt-5.4`, so the judge model is made explicit: `gpt-4o`).
* **Bug found in smoke test:** historical GEval score `1.0000000000000002` violated the
  `MetricResult` [0, 1] validator and, because legacy import ran at start-up, broke every CLI
  command. Fix: tolerance clamp (1e-9) in `legacy.py`, out-of-range scores recorded as metric
  errors, legacy import made non-fatal and atomic per run.
* Changed injected offline failures from transient to permanent errors: they are deterministic per
  question, so retrying only added ~7 s of back-off per failing case.
* CLI smoke test (temporary data dir): offline 20-case run `completed`; failure-injected run
  (rate 0.3, 4 workers) `partial` with 5 errors; three legacy runs imported with recomputed judge
  means identical to the original summaries.
* `RAG1/` turned into a lazy compatibility layer; `ask()` now returns the real retrieved context.
  Root helper scripts take arguments instead of hard-coded, non-existent files.

## 5. Streamlit front end (first version, inside the working copy)

* Multi-page app with `st.navigation`: Overview, New evaluation, Run results, Compare runs, Datasets &
  retrieval, Settings & metrics. AppTest journeys written alongside (7 tests).
* Defects found while testing the UI:
  * AppTest selectbox `set_value` takes the underlying value, not the formatted label (test bug).
  * Pandas 3 stores text with a `str` dtype, so the CSV formula-injection guard (which checked
    `dtype == object`) silently skipped every column — a real security bug caught by
    `test_csv_export_neutralises_formulas`; fixed by checking "not numeric and not bool".
  * `python -m llm_eval` failed outside the project root because the package was not installed;
    switched the project to a hatchling build so `uv sync` installs it in editable mode.
  * A running Streamlit server keeps imported helper modules cached; screenshots taken after editing
    `app/state.py` showed an `ImportError` until the server was restarted (operational note).
  * Offline CLI runs recorded `judge_model = gpt-4o` although no judge metric ran; the CLI now
    records a judge model only when a judge metric is selected.
  * "Best run per metric" broke ties arbitrarily; ties are now shown.
  * `context_recall` scored unanswerable cases against the words of the abstention sentence; such
    cases are now skipped with a reason.
* Observed results (offline baseline, 20 questions): context recall 0.623 / 0.830 / 0.898 for
  k = 1 / 3 / 5; token F1 0.319 / 0.346 / 0.346. Paired k3 − k1: context recall +0.207, 95% CI
  [0.076, 0.354]; token F1 +0.027, CI [−0.019, 0.083] (inconclusive). The extractive baseline never
  abstains on the 4 unanswerable sample questions (exact match 0/6 on that sample) because every
  question shares the word "penguin" with the document. For "What do penguins eat?" BM25 ranks the
  flipper paragraph first: the diet paragraph says "feed"/"diets", not "eat" (lexical mismatch).
* Screenshots: plain `chrome --headless --screenshot` sometimes captured Streamlit's loading
  skeleton; replaced by a DevTools-protocol script that waits until the rendered page is stable for
  3 s and captures a fixed tall viewport (resizing between pages re-triggered the sidebar animation
  and clipped it), trimming the blank bottom with Pillow.

## 6. Restructuring into an independent project (new requirement from TheOneAboveALL)

* Requirement received mid-session: the supplied repository is a reference, the deliverable must be a
  separate, independently structured project with its own identity. (The message named
  `LangChain_Agent_Evaluation_System-main.zip`; the only ZIP supplied was
  `LLM_Evaluation_System-main.zip`, which was treated as the reference.)
* Disclosure: before this requirement, the extracted working copy had been modified in place. The ZIP
  itself was never modified. A pristine reference was re-extracted to `../reference/` and verified
  file-by-file against the ZIP (45 files, 0 SHA-256 mismatches; ZIP SHA-256
  `E7F6270F5D11176D19B70614DFD9F7D21004D32F1BF603CC36783A81F08DE56D`) and marked read-only.
* New identity: **RAG Evaluation Workbench** (`rag_workbench`, CLI `ragwb`, env prefix `RAGWB_`).
  Rationale: the product evaluates a retrieval-augmented QA pipeline, not LLMs in general.
* New tree assembled with a one-off script that copied only code written in this session, renamed
  into a `src/` layout. Nothing from the reference's code was carried over.
* Removed from the product (with the replacement that preserves the functional intent):

  | Reference component | Decision | Replacement |
  |---|---|---|
  | `RAG1/` package | dropped | `pipeline.AgentRAGPipeline` (agent design, real context capture) |
  | `versions/v1..v3` scripts (10 near-duplicates) | dropped | `runner` + `ragwb run/show` |
  | `versions/*/evaluated_results*.jsonl` | converted | `examples/archived-runs/archived-v{1,2,3}.json` bundles |
  | `experiment_v*.jsonl` summaries | dropped | recorded means kept as test oracle in `test_archive_reporting.py` |
  | `compare_experiments.py` | dropped | `ragwb compare` (paired, with CIs) |
  | `save_experiment.py` | dropped | summaries are computed and stored automatically |
  | `single_tests/` demos | dropped | `ragwb score` (score one answer ad hoc) |
  | `main.py` placeholder | dropped | `ragwb` console script |
  | `dashboard.py` | rewritten earlier | `streamlit_app.py` + `src/rag_workbench/ui/` |
  | `screenshots/` | dropped | new screenshots of this product |
  | `pyproject.toml`, `uv.lock`, `.gitignore`, `.env.example` | rewritten | own manifest, fresh lock |
  | `pdfs/Penguins_ACL.pdf`, `eval_dataset.jsonl` | reused as data | `examples/documents/penguins.pdf`, `examples/datasets/penguins.jsonl` |

* Legacy auto-import at start-up replaced by a generic, validated **run bundle** format
  (`archive.py`): `export --format json` writes it, `ragwb import` / the Overview button reads it.
* Fresh `uv lock` (123 packages) and venv for the new project. Lock resolution took ~4 minutes on this
  network; one `uv sync` reported exit code 255 only because the PowerShell pipeline was closed early
  by `Select-Object -First`; the sync itself had succeeded.
* Stale paths found by the test suite after the move (`samples/` → `examples/datasets/`, entry point
  name in AppTest); fixed. Added `test_no_dependency_on_any_reference_tree`.
* `scripts/verify.py` written; first run failed because it compared an archived (judge-metric) run with
  an offline (lexical) run, which correctly exits 1 — the script's expectation was wrong.
* Old working tree moved (not deleted) to the session scratch directory; its `.venv` was deleted.
* Results after the move: 130 tests passed; statement coverage 96 % (view scripts excluded, see
  `docs/TESTING.md`); `verify.py` 5/5.

## 7. Performance check of a documentation claim

* README/UI said an offline run takes "about a second". Measured: cold `ragwb run` 5.6–6.2 s; warm in-process run
  0.29 s; first in-process run 3.2 s. cProfile + `-X importtime`: PyMuPDF 2.0 (resolved by the fresh lock) imports
  `pymupdf.layout` and `pymupdf4llm` and builds ONNX sessions (`import pymupdf` 3.26 s). Block extraction does not
  need them.
* Decision: `pymupdf>=1.28.2,<2`. `uv lock` + `uv sync`: pymupdf 2.0 → 1.28.2, eight packages removed
  (onnxruntime, pymupdf-layout, pymupdf4llm, networkx, flatbuffers, psutil, …). After: `import pymupdf` 1.41 s; cold
  CLI run 3.1 / 3.1 / 2.9 s; tests 130 passed, coverage 96 %.
* README and Overview wording corrected to the measured figures.

## 8. Defects found while documenting (writers reviewing the code)

Four documentation agents wrote parts of the book from the code and reported behaviour they found. Verified
and fixed (each with a regression test):

| Finding | Fix | Test |
|---|---|---|
| `results.py` placed config values (which can come from an imported bundle) inside `unsafe_allow_html` markup unescaped — HTML injection | values `html.escape`d | `test_ui.py::test_imported_config_values_are_html_escaped` |
| every `open_context()` (even `ragwb list`) marked *all* `running` runs `interrupted`, including one executing in another process | schema v2: `runs.heartbeat_at`, refreshed on every case commit; only runs without a heartbeat for 15 min are recovered; v1 stores migrated | `test_storage.py::test_recover_interrupted_only_touches_stale_runs`, `test_case_commits_refresh_the_heartbeat`, `test_schema_v1_store_is_migrated` |
| several store methods let raw `sqlite3` errors escape | translated to `StorageError` in `_connect` | `test_storage.py::test_sqlite_errors_become_storage_errors` |
| embedding-API errors bypassed `classify_openai_error`, so rate limits were "Unexpected" and never retried | classified in `EmbeddingRetriever.retrieve` | `test_retrieval.py::test_embedding_errors_are_classified_for_retry` |
| `ragwb delete <unknown>` exited 0 | exits 1 with a message | `test_cli_services.py` |
| log redaction did not cover traceback text | `RedactingFormatter` redacts the fully formatted record | `test_redacting_formatter_covers_tracebacks` |
| SQuAD normalisation kept curly quotes and dashes | Unicode punctuation removed | `test_squad_normalize_drops_unicode_punctuation` |

Not changed (documented in KNOWN_LIMITATIONS): possessive/contraction fragments become stray tokens (4 words in
the example datasets; fixing would change published context-recall numbers); bootstrap bounds depend on case order
(deterministic per run); judge tokens/cost not counted; DeepEval's own retry policy applies to judge calls; PDF
re-parsed on each rerun of two UI pages; in-flight model calls are not interrupted by cancellation.

Re-verification: the five demo runs were recomputed with the fixed code into a temporary store — 0 differences in
any answer, score, mean or interval. Tests: 137 passed. Book line references were remapped with a diff-based
script (old→new line map; references anchored by the identifiers quoted next to them); references inside changed
regions were rewritten by hand.

## 9. Second review round and independence check

* Second batch of fixes (R8–R13 in book Chapter 105a): broader secret-scan pattern with an explicit fake-key
  marker; bundle summaries recomputed on import; out-of-range metric scores reported as errors; Overview import
  errors shown in-page; Streamlit bound to `localhost`; exported bundles carry project-relative paths only;
  package docstring renamed. Tests: 140 passed; coverage 96 % (1,866 statements, 72 missed).
* Re-verified: the five demo runs and three archived runs recomputed with the final code — 0 differences.
* Reference re-check: 45/45 files byte-identical to the archive, all read-only; archive SHA-256 unchanged.
* Independence check: the product tree (without `.venv`, `data/`, caches) copied to a scratch directory and
  installed with `uv sync --offline --frozen`. First attempt failed with `ImportError: cannot import name
  'ArgsKwargs' from 'pydantic_core._pydantic_core'` — root cause: the scratch path made
  `…\.venv\Lib\site-packages\pydantic_core\_pydantic_core.cp312-win_amd64.pyd` exactly 260 characters (Windows
  MAX_PATH), so the extension failed to load and Python fell back to the stub folder of the same name. Repeated in
  a short temporary path: 140 passed, `verify.py --quick` 5/5, `PROJECT_ROOT` resolved to the copy. Both copies
  deleted afterwards. Troubleshooting note added (keep the project path short on Windows or enable long paths).
* A `uv run pip-audit` process was observed by one writer agent during the session; it was not started by the
  lead or at its request, and no vulnerability-scan result exists in the project.

* Apostrophe consistency (reported by a writer after the second batch): the Unicode-punctuation fix turned a
  curly apostrophe into a space while ASCII `'` is deleted. Curly/modifier apostrophes are now deleted too
  (`text.py:29`); test extended. Stray-token count corrected to 4 words (the earlier count of 3 omitted the CSV).

## 10. Owner request: separate records, no trace of the reference, one start file (2026-10-24)

* Engineering records (`REFERENCE_ANALYSIS.md`, `IMPLEMENTATION_PLAN.md`, `DEVELOPMENT_LOG.md`, `FINAL_AUDIT.md`,
  `evidence/`) moved out of the product to `RAG Evaluation/engineering-records/` (this folder). The product no longer
  references them.
* All reference-derived material removed from the product: the penguin PDF and 20-question dataset (byte-identical
  copies from the reference), the three archived judge-scored run bundles and the code paths that existed only for
  them (`archive.example_bundles`, the Overview "Load archived example runs" box, the no-argument `ragwb import`, the
  `model_self_report` context source), comments citing defect labels or the reference, and penguin-themed test
  fixtures. Provenance of the earlier work is preserved here only.
* New example data written for the project: `examples/documents/honeybees.md` (title + 10 paragraphs) rendered by the
  new `scripts/make_example_pdf.py` to a 2-page PDF (11 chunks: title + paragraphs); `honeybees.jsonl` (20 questions,
  paraphrased references), `honeybees_unanswerable.jsonl` (4 unanswerable + 2 controls), `honeybees_paraphrased.csv`
  (5). All validate.
* New `src/rag_workbench/demo.py` (example run configurations + seeding) and `start.py` (stdlib-only launcher:
  `uv sync --frozen --inexact` or venv+pip fallback → example runs on first launch → Streamlit on localhost, opens the
  browser). Verified: `python start.py --setup-only` on an empty data dir created 5 runs (4 completed, 1 partial);
  `python start.py --no-browser` served http://localhost:8501 (health 200) without re-seeding. First attempt removed
  the docs dependency group on every start; fixed with `--inexact`.
* Tests rewritten for the new data and features (bundle tests now use bundles exported from real runs; UI tests
  build bundles from real runs; independence test removed because it necessarily named reference artefacts; new
  example-runs test). Result: 140 passed; coverage 96 % (1,872 statements, 70 missed).
* New real findings on the honeybee data: k=1 has higher token F1 than k=3 (paired −0.057, CI −0.116…−0.008);
  context recall 0.857 / 0.885 / 0.892 (k=1/3/5); k=5 answers identical to k=3; the title chunk is often retrieved;
  BM25 ranks the varroa paragraph third for "Which parasite threatens honeybee colonies?"; the baseline never abstains
  on u1–u4; injected failures 3/20.
* Book: Part II rewritten as "Design analysis" (no reference); Parts I, X, XII and supporting docs rewritten; Parts
  III–IX and XI revised by the writer agents against the brief. The writers were interrupted by a session rate limit
  once and resumed from their saved work.
* Timing note: CLI `ragwb run` measured 7.2 / 6.7 / 3.4 s while three writer agents were running test suites in
  parallel; the earlier idle-machine measurement (2.9–3.1 s) is the one quoted.

---

## 2026-10-28 — Release 1.1.0 (production-readiness pass)

Trigger: the owner asked for improvements from the future-scope list, analysed and implemented to production grade.
Approved by the owner before any install: dev tools (ruff, mypy) and pip-audit from PyPI; pip-audit sends only package
names and versions to the advisory service.

* **Reliability:** per-case time limit (daemon thread + join; Python cannot kill the thread, so the abandoned call
  runs on until its own HTTP timeout); judge metrics retry transient provider errors with exponential back-off and
  jitter; judge cost captured from DeepEval `evaluation_cost`; prices used stored in the run config.
* **Evaluation quality:** hybrid RRF retrieval; offline `--min-evidence` and `--skip-headings`; metadata slices;
  human-label calibration (Cohen's kappa) with a labelling sheet; apostrophe normalisation made consistent.
  Measured trade-off: min-evidence 0.7 with skip-headings abstains on all 4 unanswerable questions but also on the
  answerable control a2, so the defaults stay off.
* **Operations:** `doctor`, `backup`, `prune`, `rerun`, `--version`; JSON logs with redaction; Settings health panel.
* **Security:** optional shared password (constant-time compare, 5 failures/60 s lockout); `start.py --host` warns
  when exposed without a password.
* **Verification:** ruff and mypy clean (39 files); `scripts/verify.py` now 6 steps + optional `--audit`; pip-audit on
  the exported locked runtime requirements (369 lines): no known vulnerabilities (point-in-time); 253 tests collected,
  252 passed, 1 skipped (opt-in live), coverage 96 % (2,532 statements, 100 missed) — evidence/test-and-coverage-v1.1.txt.
* **Regression check:** the five example runs (86 cases) scored with the 1.0.0 source snapshot and the 1.1.0 code were
  compared case by case: 0 differences, so the numbers in the book remain valid.
* **Scale:** evidence/benchmark-v1.1.txt. No optimisation was needed; 4 workers were slower than 1 offline.
* **Live path:** `scripts/live_smoke.py` written and its guards and failure path tested (fake key, closed local port,
  no external traffic). It was NOT run against the real API: no key was available and spending was not authorised.
  Hybrid retrieval, judge retry and judge cost therefore remain unverified against a live service.
* Bugs found by own review during this pass (all fixed with regression tests): live-smoke checks passed vacuously on
  zero successful cases; log file handle blocked temp-dir cleanup on Windows (`close_logging()`); wrong keyword for
  `OpenAIEmbeddings` timeout found by constructing the real class; ruff autofix collapsed the stop-word list.
* The lockfile needed `uv lock --offline` after the version bump (the project's own entry changed; no dependency changed).
- verify.py 6/6 after book rebuild: PDF 321 pages, 707 bookmarks, 13 Parts; reference-term scan of PDF: 0 hits

---

## 2026-10-28 — Release 1.2.0 (future-scope items that need no live key)

Trigger: the owner asked to complete the future-scope list and said not to use paid keys (Grok free tier would be used).
No key was present in the environment, so items needing a live call (live smoke, judge calibration on real labels,
hybrid with real embeddings, judge-noise estimation) were NOT done and are recorded as open.

* Data: three original documents + 30-question datasets (volcanoes, coffee, lighthouses) written by a delegated agent;
  validated; offline evaluation numbers recorded in the book (token_f1 0.199 / 0.257 / 0.212).
* Run history: tags/notes/search (schema 3, column-based migration), CLI and UI. A test-isolation bug was found by
  review (module-level fixture not inherited by the new test file: cached Streamlit context leaked between tests); fixed.
* Regression gate: exit 0/3/4; empty checks never pass. Verified on real runs (k=3 vs k=1).
* Abstention tuning on a held-out half: negative result (balanced accuracy 0.553 vs 0.500; declines 24/33 answerable
  questions to catch 10/12 unanswerable). Default unchanged. Recorded honestly in KNOWN_LIMITATIONS.
* Semantic metrics: optional via fastembed; tested with a stand-in embedder only; no model downloaded (no authorisation
  for downloads, and not needed to verify the wiring).
* Accounts and TLS: scrypt-hashed accounts, per-user + global lockout, started_by on runs; start.py TLS flags verified
  with a throwaway self-signed certificate (https 200, http refused). Temporary key/cert lived in the scratch directory only.
* Packaging: wheel builds offline; unpacked wheel run from a neutral folder works (root = cwd, examples packaged). A real
  install could not be tested offline. Dockerfile written, not built (no Docker).
* Accessibility: scripted check over five pages in the browser pane against a local server; real findings fixed (heading
  levels, muted-text contrast); canvas tables and third-party widgets remain; keyboard/screen-reader not tested.
* Process issues: the shell layer mangled backslash escapes inside heredoc patch scripts twice (generated code with
  literal newlines inside string literals); caught at import time by the syntax error and fixed with the Edit tool.
  A full-suite run then caught two stale test expectations (schema v2, metric registry); fixed.
* Regression check: five example runs under 1.0.0 vs 1.2.0: 86 cases, 0 differences.
* Verification: scripts/verify.py 6/6 (quick). Full suite 330 passed, 1 skipped, coverage 96 % (3,121 statements, 118 missed).

---

## 2026-10-28 — Release 1.3.0 (live verification and the remaining buildable items)

Trigger: the owner supplied a free-tier key in chat (a Groq `gsk_` key, not xAI Grok as described) and approved installing the
optional fastembed package and downloading one embedding model (~67 MB, Hugging Face hub; no project data sent).
Handling: the key was used only through process environment variables, sent only to api.groq.com, never written to a file or
printed; the owner was told to rotate it. A `git stash` was typed by mistake in one command and blocked by the permission
layer; it never ran (no git operation was performed at any point).

* Live verification (docs/LIVE_VERIFICATION.md): smoke 2 cases 8/8, then 12/12 with judge after fixes; 10-case honeybee run;
  30-case Qwen volcano run (first partial, then 30/30 after a bug fix); judge noise (correctness: within SD 0.023, between SD
  0.371, 1/10 flips). Free-tier daily token quotas (~200k per model) ended attempts at a 20-case multi-metric run.
* Bugs found by live runs: (1) rate limits hidden in tenacity RetryError were not classified; (2) my first fix walked the
  cause chain past the SDK error to the httpx transport error, so connection drops became unexpected case errors. Both fixed with
  regression tests (the second reproduces the exact chain).
* Built: local embeddings + hybrid-local retrieval (optional `semantic` extra, model cached under data/models); request pacing;
  Retry-After; judge-noise command; roles with live revocation; keyboard Tab walk (one page).
* Real-model measurements: five datasets x bm25/local/hybrid-local; no consistent winner; semantic cosines have a high floor.
* Environment findings: the laptop slept between steps (31-minute test pass, stalled runs) - fixed by a keep-awake request;
  Windows MAX_PATH breaks the model cache under very long data paths (documented).
* Not done: calibration against human labels (sheet and bundle supplied in calibration/, labels must come from a person); OpenAI
  itself; live agent pipeline; API embeddings (provider has none); Docker; real wheel install; screen reader.
- Final verify.py --audit 7/7 (373 passed, 2 skipped, 97 % coverage); book 399 pages / 15 Parts; PDF scan: 0 trace hits, no key strings

---

## 2026-10-29 — Release 1.4.0 (completion pass)

Trigger: the owner asked for full completion with future scope and production readiness. Analysis first: items needing a human
(labels), an OpenAI key or Docker cannot be completed by the assistant and stay open; everything else was built and verified.
Authorised network use this pass: PyPI (clean wheel install into a throwaway venv, removed afterwards), jsDelivr (axe-core 4.10.2,
one file, served from a local port and run only against localhost pages), Groq (live agent and multi-metric runs with the key the
owner supplied; never written to a file). A keep-awake request was refused by the permission layer once; work continued without it.

* Built: restore (+ safety copy, validation, active-run guard, Windows lock handling), multi-process concurrency test (4 processes +
  reader: no lock errors), admin Accounts page, password change, last-admin guard, run visibility, calibrate --sweep/--rescore,
  BM25 inverted index (bit-identical; 1.0.0 comparison 86 cases / 0 differences), wheel_check.py, benchmark_documents.py,
  OPERATIONS.md, SECURITY.md.
* Defects found by verification: examples folder unresolved in wheel installs (found by the clean install; fixed); my own tests
  initially asserted the wrong thing about non-admin routing (the page is simply unregistered; test corrected).
* Corrected an earlier claim: Streamlit tables are exposed through a parallel gridcell structure, not unreadable canvases.
* Evidence of note: semantic_similarity sweep (plateau 0.55-0.65 vs default 0.70) recorded; defaults NOT changed (one document, one AI
  rater). Labels in calibration/ written by Claude are not human labels.
* Process: a 20-question multi-metric live run was throttled by the provider's output-tokens-per-minute cap (1,000/min on the Qwen
  model) and took hours; retries honoured Retry-After throughout.
* Verification: 414 tests collected (412 passed, 2 skipped), coverage 96 % (3,555 statements, 126 missed); quick verify 6/6.
* Late findings (1.4.0): the book agent's review found five real source defects (restore on an unreadable store; backup-name collisions;
  Settings count leak under own visibility; stale limitation text; docstring) and a measurement error of mine (both benchmarks timed under
  tracemalloc: throughput 2x low, queries ~10x high, and a wrong conclusion that four workers are slower), all fixed/corrected with an
  erratum in the book. The final verification run then caught that the backup-name fix was incomplete (coarse Windows clock still collided):
  fixed with a counter suffix and a frozen-clock test. Final: verify.py --audit --wheel 8/8 (416 passed, 2 skipped, 96 % coverage, 3,567
  statements, 125 missed), PDF 434 pages / 16 Parts / 899 bookmarks, zero trace hits, check_cites {'ok': 1677, 'UNRESOLVED': 13, 'ANCHOR?': 213}.
* Open (cannot be closed by the assistant): human labels, OpenAI itself, API embeddings, Docker, screen-reader testing.

---

## 2026-10-31 — Release 1.4.1 (provider key placed in the project's .env at the owner's request)

* The owner asked for the Groq key to be used "in the project itself". It was written to the project's `.env` (git- and Docker-ignored;
  the loader reads it automatically). It was NOT written to source, docs, calibration files or the book. A live smoke test from `.env`
  alone passed (2/2 cases, 8/8 checks). The project folder is under OneDrive, so the owner was told the file will sync to the cloud.
* Made the test suite immune to a real `.env`: `RAGWB_NO_DOTENV=1` (set in conftest and in the explicit-environment subprocess
  helpers); previously only the key was blanked and OPENAI_BASE_URL was merely deleted, so `.env` could have re-supplied it.
* `verify.py` secret scan: a git/docker-ignored `.env` is a note, not a failure; keys elsewhere still fail.
* The earlier statements "the key is in no project file" (this log's 1.3/1.4 entries and FINAL_AUDIT addenda) are superseded: the key is
  now in `.env`, the one intended place, and still in the conversation transcript.

## 2026-10-31 — Release 1.4.1 (polish pass, DeepEval finding, Practitioner's Guide)

* Polish fixes found by using the tools as a user would (tests in `tests/test_cli_polish.py`, 19): `.md` leading heading markers stripped
  (`documents._ATX_MARKER`, `.md` only); run references accept an exact id, a unique prefix, a unique suffix (>= 4 characters) or an exact
  name, with an ambiguity message (`cli._get_run`); `show` prints tags and notes; `calibrate` header reads "vs labels from <file>" and
  `--rescore` fails when the metric computes for no case; `prune` never selects a run tagged `keep`; `--workers` and `--limit` reject
  values below 1; `regress --metrics` with an unknown name is an error (exit 1); a local embedding model that cannot load stops run
  preparation with one `ConfigError` (`metrics/semantic.py::local_model_error`); backup names `runs-%Y%m%d-%H%M%S-%f.db`; restore of an
  unreadable store handled; `scripts/set_api_key.py` added (13 tests); `start.py` honours `RAGWB_NO_DOTENV`.
* Finding and fix: DeepEval loaded a real `.env` on import and again through its own pytest plugin, which slowed the suite and let
  the file's contents enter the test process outside `load_settings`. Fix: the package sets `DEEPEVAL_DISABLE_DOTENV=1` by default
  (set to 0 to restore DeepEval's behaviour), `pyproject.toml` runs pytest with `-p no:deepeval`, and `tests/test_dotenv_switch.py`
  (5 tests) is the leak guard.
* New book: the Practitioner's Guide (`docs/user-guide/`, 173 pages), written by parallel writer agents from the code and the Project Book.
* Disclosed incidents (both mine to report, neither involved a key or any project data): (1) a writer agent, while checking how local
  embeddings behave, caused a request to the Hugging Face hub to fetch a public embedding model; (2) the editor agent did the same by
  running `calibrate --rescore`, which loads the local model. Both attempts failed with WinError 206 (path too long) in the model cache
  location, so nothing was downloaded and nothing was written; no API key was sent and no project data left the machine. The network
  was not authorised for those steps. Follow-up already in the code: a model that cannot load is a single clear `ConfigError`.
* Counts refreshed across README-adjacent docs and the Project Book: 455 tests collected, 453 passed, 2 skipped, coverage 97 %
  (3,624 statements, 125 missed, measured by a `pytest --cov` run). Latest full `verify.py --audit --wheel`: 8/8.
* Project Book rebuilt (final edition 1.4.1): 439 pages, 16 Parts, 907 bookmarks, 17.8 MB; PDF text scan for the forbidden traces
  returned zero hits; check_cites {'ok': 1683, 'UNRESOLVED': 13, 'ANCHOR?': 207}, no RANGE problems (after re-pointing line citations
  that moved with the 1.4.1 code changes).
* Not done and not claimed: no human labels exist (the calibration labels were written by an AI rater), and no live OpenAI run was made;
  the only live runs are against Groq's free tier.
