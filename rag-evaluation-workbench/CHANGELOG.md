# Changelog

## 1.4.1 — 2026-10-31

* **Provider key in the project's `.env`** (Groq free tier, `qwen/qwen3.8-27b`, paced at 10 operations/minute): the app, CLI and
  `start.py` pick it up automatically; a live smoke test passed from `.env` alone (2 of 2 cases, 8/8 checks).
* `RAGWB_NO_DOTENV=1` skips the project `.env`; the test suite sets it (and its subprocess helpers pass it) so a real key or setting
  in `.env` can never reach a test. Test: `tests/test_dotenv_switch.py`.
* `scripts/verify.py`: a git- and Docker-ignored `.env` no longer fails the secret scan (it is the documented home of the key); keys
  anywhere else, or a `.env` that is not ignored, still do.
* `docs/SECURITY.md` and `docs/OPERATIONS.md`: a section on keeping a `.env` in a cloud-synced folder.
* `scripts/set_api_key.py`: replace (or `--remove`) the key in `.env` from a hidden prompt, never printing it; `--check` sends one
  request to the configured endpoint and prints only the status. Rotating the key itself is done in the provider's console.
  13 tests (`tests/test_set_api_key.py`).
* Two new books: the final edition of the Project Book (1.4.1) and a new Practitioner's Guide (`docs/user-guide/`).

## 1.4.0 — 2026-10-29

Completes the remaining items that can be built and verified without a human labeller, an OpenAI key or Docker. Default
behaviour is unchanged: the five example runs (86 cases) score identically under 1.0.0 and 1.4.0.

### Added
* **Disaster recovery:** `ragwb restore BACKUP --yes` (validates the backup, refuses newer schemas and recently active runs,
  writes a `pre-restore-*` safety copy first, migrates an older schema, and reports a store held open by another process).
* **Accounts management:** an admin-only Accounts page (add, change role, reset password, remove), self-service password
  change, `ragwb user set-password`, and protection against removing or demoting the last admin (`--force` overrides).
* **Per-user run visibility:** `RAGWB_RUN_VISIBILITY=own` hides other users' runs from non-admins.
* **Calibration tooling:** `ragwb calibrate --sweep` (agreement and kappa at every pass threshold) and `--rescore` (compute an
  offline or local-model metric from a run's stored answers).
* **Verification:** `scripts/wheel_check.py` and `verify.py --wheel` (clean wheel install, 10 checks), a multi-process
  concurrency test, `scripts/benchmark_documents.py` (large documents), the axe-core accessibility audit and keyboard walks
  recorded in `docs/LIVE_VERIFICATION.md`.
* **Docs:** `docs/OPERATIONS.md` (runbook) and `docs/SECURITY.md`.
* 43 new tests (418 in total).

### Changed
* BM25 uses an inverted index: scores are bit-for-bit identical (a test compares against the textbook definition). Its speed-up was
  first measured under the tracer (about 1.6x); under the corrected harness queries at 5,000 chunks take about 3 ms.

### Fixed
* **`ragwb restore` could not run against an unreadable `runs.db`** (every command opened the store first), which is exactly when
  a restore is needed. It now runs before the store is opened and keeps a raw copy of the damaged file.
* Backups and safety copies written in the same second could collide; names now include microseconds and, if a name still exists, a counter (a coarse Windows clock made microseconds alone insufficient; found by the final verification run).
* In `own` visibility mode the Settings page counted every run; it now counts only the runs the user may see.
* **Benchmarks were measured under `tracemalloc`**, which slows Python code several-fold. Re-measured without the tracer: about 100-108
  cases/s (not 46-64), 5,000 cases in 47 s (not 109 s), BM25 queries at 5,000 chunks about 3 ms (not 40 ms), and four workers are
  slightly *faster* than one offline (116 vs 100 cases/s), so the earlier claim that they were slower is withdrawn. Memory figures
  were unaffected. The scripts now time without a tracer and measure memory in a separate pass.
* Wheel installs could not find the bundled examples for `tune-abstention`, the first-launch demo runs and the dataset
  picker (found by the clean install); they now use the packaged copy.

### Findings recorded (not changes)
* The live agent pipeline works (3 of 3 cases, context captured from tool calls).
* On the 30 volcano answers, `semantic_similarity` agrees best with the AI-written labels at thresholds 0.55-0.65 (agreement
  0.967), not at its 0.70 default (0.867); not changed, because it is one document and one AI rater.
* axe-core found no violations on six page views and one minor issue in Streamlit's own file uploader.
* Streamlit tables are exposed to assistive technology through a parallel grid structure; they are not unreadable canvases,
  but each cell is a Tab stop (some on zero-size elements).

### Not verified
* Judge calibration against human labels (the sheet is waiting for a person), OpenAI itself, API embeddings, the Docker image,
  screen-reader use.

## 1.3.0 — 2026-10-28

Completes the items of the future-work list that could be built and verified with the resources available: a free-tier
OpenAI-compatible key (Groq) and one small local embedding model. Default behaviour is unchanged.

### Added
* **Local embeddings:** `--retriever local` and `--retriever hybrid-local` (BM25 fused with local dense retrieval) use a
  local sentence-embedding model through the optional `semantic` extra (`uv sync --extra semantic`); no key, no
  network after the one-time model download into `data/models`. Verified with `BAAI/bge-small-en-v1.5` on all bundled datasets.
* **Request pacing:** `RAGWB_MAX_REQUESTS_PER_MINUTE` spaces answers and judge measurements evenly (one shared limiter
  for all workers) so free-tier quotas are not hit.
* **Provider rate limits:** retries now honour the provider's `Retry-After` hint (capped at 60 s) and recognise rate
  limits hidden inside DeepEval's tenacity `RetryError`; errors say "OpenAI-compatible API" rather than naming OpenAI.
* **Judge noise:** `ragwb judge-noise RUN_ID` re-scores a run's stored answers several times and reports within-case SD,
  between-case SD, noise/signal and pass/fail flips per judge metric.
* **Roles:** `viewer` (read-only), `editor` (run, tag; the default and the meaning of accounts created before roles) and
  `admin` (also delete runs); `ragwb user add --role`, `ragwb user set-role`. Roles are read on every page load, so a role
  change or a removed user takes effect at once (an open session of a removed user ends).
* **Live verification** against a real OpenAI-compatible service (Groq): generation, DeepEval judge metrics and token usage.
  See `docs/LIVE_VERIFICATION.md` for exactly what ran and what failed.
* 43 new tests (375 in total).

### Fixed
* Found by the live run and fixed with a regression test: classifying an exception chain walked past the OpenAI SDK error
  to its transport cause, so connection drops were recorded as unexpected case errors instead of being retried.

### Not verified
* Judge-versus-*human* calibration (a person must label the supplied sheet; a comparison with labels written by an AI rater
  exists: correctness judge 29/30 agreement, kappa 0.870), the semantic metrics' thresholds,
  the Docker image, a real wheel install, screen-reader use.

## 1.2.0 — 2026-10-28

Follow-up release: everything from the future-work list that can be built and verified without a live API key.
Default behaviour is unchanged.

### Added
* **Data:** three more original example documents (volcanoes, coffee, lighthouses) with 30 questions each,
  tagged by `type`, `difficulty` and `topic`; the bundled data now covers 4 documents and 110 questions.
* **Run history:** tags and notes on runs (`ragwb tag`, `ragwb note`, Results page), filtered listing
  (`ragwb list --search/--tag/--status`) and a search/tag filter on the Overview; storage schema 3 (migrates in place).
* **Regression gate:** `ragwb regress BASELINE CANDIDATE` fails (exit 3) when a metric drops significantly (paired
  bootstrap) or the error rate rises; exit 4 when nothing could be judged, so an empty check never looks clean.
* **Abstention tuning:** `ragwb tune-abstention` picks the offline threshold on a development half and reports it on a
  held-out half. Measured result: it does not pay off on the bundled data (see Known limitations); the default stays off.
* **Optional semantic metrics** (`semantic_similarity`, `semantic_context_recall`) using a local embedding model through
  `fastembed` (not a dependency; refused with an install hint when absent).
* **Accounts and TLS:** named user accounts with scrypt-hashed passwords (`ragwb user add/remove/list`), per-user
  lockout and sign-in log lines, `started_by` on runs started in the app, sign-out; `start.py --ssl-cert/--ssl-key`
  serves HTTPS.
* **Packaging:** `RAGWB_HOME`, a checkout check so an installed wheel never writes into `site-packages`, examples bundled
  into the wheel, a `Dockerfile` (not built here).
* **Accessibility:** section headings are h2 under the h1 page title (no skipped levels), muted text meets 4.5:1 in
  both themes, an automated WCAG-style check of five pages (see Known limitations for what remains).
* 79 new tests (332 in total).

### Changed
* The UI uses `st.header` for section headings (previously `st.subheader`).

### Not verified
* Any live OpenAI/Grok/DeepEval call; the semantic metrics with a real model; the Dockerfile; judge-versus-human
  calibration on real labels.

## 1.1.0 — 2026-10-28

Production-readiness release. Default behaviour is unchanged: the five example runs (86 cases) score identically
under 1.0.0 and 1.1.0.

### Added
* **Reliability:** per-case time limit (`RAGWB_CASE_TIMEOUT_S`); judge metrics retry transient provider errors with
  exponential back-off and jitter; judge cost (DeepEval `evaluation_cost`) is recorded; the prices used are stored with
  each run.
* **Evaluation quality:** hybrid retrieval (BM25 + embeddings, reciprocal-rank fusion); `--min-evidence` abstention
  threshold and `--skip-headings` for the offline generator; per-metadata slice breakdowns (`ragwb slices`, results
  page); human-label calibration of metrics with Cohen's kappa (`ragwb labels-template`, `ragwb calibrate`).
* **Operations:** `ragwb doctor` (and a Health checks panel in Settings), `ragwb backup`, `ragwb prune`,
  `ragwb rerun`, `ragwb --version`; JSON log format (`RAGWB_LOG_FORMAT=json`).
* **Security:** optional shared password for the web app (`RAGWB_APP_PASSWORD`) with constant-time comparison and a
  lockout; `start.py --host`, which warns when the app is exposed without a password.
* **Verification:** `scripts/verify.py` runs ruff and mypy and, with `--audit`, pip-audit; `scripts/benchmark.py`
  (scale); `scripts/live_smoke.py` (guarded, paid, 1-5 cases; not run here).
* 113 new tests (253 in total).

### Changed
* Apostrophes are normalised consistently (`queen's`, `queen’s` and `queens` tokenise the same way).
* PyMuPDF is pinned below 2.0 (2.0 loads ONNX models at import and added about three seconds to every start).
* Metric scores outside 0-1 (beyond a 1e-9 tolerance) are recorded as errors.

### Verified
* `pip-audit` over the locked runtime requirements: no known vulnerabilities at the time of the scan.
* Offline scale: about 45-65 cases/s from 200 to 5,000 cases (figures withdrawn in 1.4, see Fixed there: they were measured under a tracer); storage and bootstrap costs are not a bottleneck.
* Not verified: any live OpenAI/DeepEval call (no key was available).

## 1.0.0 — 2026-10-24

First release of RAG Evaluation Workbench.

### Added
* `start.py`: one command that prepares the environment, creates example runs on first launch and starts the app.
* `rag_workbench` package: validated configuration, pydantic data contracts, dataset parsing (JSONL/CSV) with
  line-numbered errors, PDF/TXT/MD chunking, BM25 and OpenAI-embedding retrievers, extractive offline generator,
  OpenAI retrieve-then-generate and tool-calling agent pipelines that record the context actually retrieved.
* Metrics: exact match, token F1, ROUGE-L, lexical context recall and groundedness (offline); DeepEval answer
  relevancy, faithfulness, contextual relevancy and GEval correctness (with an API key). Out-of-range scores are
  reported as errors.
* Runner with validation before execution, retries with exponential back-off, thread pool, cancellation,
  per-case persistence, heartbeat-based recovery of interrupted runs, latency/token/cost tracking.
* Aggregation with missing-value accounting, bootstrap confidence intervals and paired run comparison.
* SQLite run history (schema 2); CSV/JSON/Markdown exports; validated, re-importable JSON run bundles with
  project-relative paths and summaries recomputed on import.
* `ragwb` CLI: `run`, `list`, `show`, `compare`, `export`, `import`, `validate`, `score`, `metrics`, `delete`.
* Streamlit app: Overview, New evaluation, Run results, Compare runs, Datasets & retrieval, Settings & metrics;
  localhost-only by default; HTML-escaped display of stored values.
* Example data written for this project: a document on honeybee colonies (Markdown source and generated PDF),
  20 questions with reference answers, unanswerable and paraphrased datasets.
* Secret handling: `SecretStr` settings, log and traceback redaction, secret scan in `scripts/verify.py`;
  DeepEval telemetry and Streamlit usage statistics disabled.
* 140 offline tests (including 8 Streamlit journeys), `scripts/verify.py`, technical book.
