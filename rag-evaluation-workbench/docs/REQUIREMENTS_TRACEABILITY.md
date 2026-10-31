# Requirements Traceability Matrix

Each requirement of the product brief is mapped to its implementation and to the evidence that it works.
Status values: **Done** (implemented and verified by the listed evidence), **Done — not live-verified**
(implemented and tested with fakes; the real external service was not called).

Test results refer to `uv run pytest` (140 passed, 0 failed) and `uv run python scripts/verify.py` (5/5 checks).

| ID | Requirement | Implementation | Verification | Status | Limitations |
|---|---|---|---|---|---|
| R1 | Answer questions about a document with a retrieval-augmented pipeline | `pipeline.py` (`RAGPipeline`, `AgentRAGPipeline`), `retrieval.py`, `providers.py`, `documents.py` | `test_providers_pipeline.py`, `test_runner.py::test_offline_end_to_end_on_the_real_dataset` | Done (offline); Done — not live-verified (OpenAI paths) | Agent mode tested with a scripted fake chat model |
| R2 | Evaluate answers over a dataset of questions with optional reference answers | `datasets.py`, `runner.py` | `test_datasets.py` (19), `test_runner.py` (14) | Done | — |
| R3 | LLM-judge metrics: answer relevancy, faithfulness, contextual relevancy, correctness (threshold 0.7) | `metrics/judge.py`, `metrics/__init__.py` | `test_metrics.py::test_judge_metric_*`, `test_build_judge_metric_constructs_deepeval_objects_without_network` | Done — not live-verified | No judge call was made in this environment |
| R4 | Per-metric summary: mean, pass/fail counts, pass rate, uncertainty | `aggregate.summarize_metric`, `bootstrap_ci` | `test_aggregate.py` | Done | — |
| R5 | Compare runs; best run per metric | `aggregate.paired_comparison`, `reporting.comparison_dataframe`, `ui/views/compare.py`, `ragwb compare` | `test_aggregate.py::test_paired_comparison_*`, `test_archive_reporting.py::test_summary_and_comparison_frames`, `test_ui.py::test_new_run_journey_offline_then_results_and_compare` | Done | Pairs by question text |
| R6 | Every parameter (k, retriever, models, metrics, thresholds) configurable without code changes | `RunConfig`, CLI flags, UI form | `test_cli_services.py::test_cli_run_list_show_compare_export` | Done | — |
| R7 | Python-native user interface | `streamlit_app.py`, `ui/` | `test_ui.py` (9 journeys); real-browser check; screenshots | Done | No browser-automation suite beyond AppTest |
| R8 | One command starts the whole application | `start.py`, `demo.py` | `python start.py --setup-only` on an empty data directory (5 example runs created); `python start.py --no-browser` served the app; `test_runner.py::test_demo_runs_are_genuine_and_reproducible` | Done | uv recommended; pip fallback needs Python 3.12+ |
| R9 | Run end-to-end without network or API keys | offline provider, `BM25Retriever`, `ExtractiveGenerator`, lexical metrics | whole suite runs with `OPENAI_API_KEY=""`; `verify.py` end-to-end | Done | Offline answers are an extractive baseline |
| R10 | Provider adapters with explicit variables, timeouts, retries | `config.py`, `errors.classify_openai_error`, `runner._generate_with_retries`, `providers.OpenAIChatGenerator`, `retrieval.EmbeddingRetriever` | `test_runner.py::test_transient_errors_are_retried_with_backoff`, `test_retries_give_up`, `test_retrieval.py::test_embedding_errors_are_classified_for_retry` | Done — not live-verified | Per-case time limit abandons (cannot kill) a stuck call; see R23 |
| R11 | Record the real retrieved context, latency, tokens, errors per case | `models.CaseResult`, `pipeline.py` | `test_rag_pipeline_evaluates_exactly_the_retrieved_chunks`, `test_agent_pipeline_captures_real_tool_output_not_self_report` | Done | Tokens only when the provider reports usage |
| R12 | Partial failures recorded; interrupted runs keep progress | `runner.evaluate_case`, per-case commits, heartbeat recovery | `test_runner.py::test_partial_and_failed_statuses`, `test_cancellation_event_stops_and_records_progress`, `test_storage.py::test_recover_interrupted_only_touches_stale_runs` | Done | — |
| R13 | Persist runs with reproducibility metadata | `storage.py` (schema 2), `RunRecord` | `test_storage.py` (9), `test_runner.py::test_offline_runs_are_reproducible` | Done | — |
| R14 | Export CSV, JSON, Markdown; re-import JSON | `reporting.py`, `archive.py`, UI Export tab, `ragwb export/import` | `test_archive_reporting.py` (13) | Done | — |
| R15 | Dataset validation with actionable errors | `datasets.parse_dataset` | `test_datasets.py` | Done | — |
| R16 | UI workflow: configure → run with progress → inspect → compare → export → history | `ui/views/*` | `test_ui.py`; screenshots in `docs/project-book/screenshots/` | Done | Cancellation via Streamlit's Stop button |
| R17 | Automated offline test suite | `tests/` | 453 passed, 2 skipped (opt-in live and real-model tests; 455 collected); coverage 97 % (views excluded) | Done | Real OpenAI/DeepEval calls untested |
| R18 | No secrets in logs or UI; no telemetry | `SecretStr`, `public_dict`, `RedactSecretsFilter`, `RedactingFormatter`, telemetry opt-outs | `test_config.py::test_secret_never_exposed`, `test_cli_services.py::test_secret_redaction_filter`, `test_redacting_formatter_covers_tracebacks`, `verify.py` secret scan | Done | — |
| R19 | Documentation set and technical book (Markdown + PDF) | `README.md`, `docs/*.md`, `docs/project-book/` | PDF built and checked by `build_book.py` | Done | — |
| R20 | Local verification script | `scripts/verify.py` | executed: 6/6 (environment, lockfile, secrets, static, tests, end-to-end) | Done | — |
| R21 | Score a single answer ad hoc | `ragwb score` | `test_cli_services.py::test_score_command` | Done | Judge metrics need a key |
| R22 | Example data owned by the project | `examples/documents/honeybees.md` (+ generated PDF), `examples/datasets/honeybees*.{jsonl,csv}` | `validate` on each file; `test_documents.py`, `test_datasets.py` | Done | — |
| R23 | Stuck or failing cases cannot stall or corrupt a run | `runner.py` (time limit), `metrics/judge.py` (retry) | `test_runner.py` watchdog, `test_metrics.py` judge retry | Done | Abandoned thread keeps running until its HTTP timeout |
| R24 | Operators can check health, back up, prune and repeat runs | `maintenance.py`, `cli.py` | `test_maintenance.py` (21) | Done | — |
| R25 | Access control when exposed beyond localhost | `ui/auth.py`, `start.py --host` | `test_auth.py` (8), `test_start.py` | Done | Shared password, no TLS |
| R26 | Per-slice results and human calibration of metrics | `aggregate.py`, `calibration.py` | `test_evaluation_options.py`, `test_calibration.py` (39) | Done | Calibration tested on synthetic labels only |
| R27 | Hybrid retrieval and offline abstention options | `retrieval.py`, `providers.py` | `test_retrieval.py`, `test_evaluation_options.py` (21) | Done | Hybrid evaluated with fake embeddings only |
| R28 | Quality gates: lint, types, dependency audit | `pyproject.toml`, `scripts/verify.py` | verify.py `static` step; pip-audit: no known vulnerabilities | Done | Audit is a point-in-time result |
| R29 | Scale behaviour measured | `scripts/benchmark.py` | 5,000 cases in 47 s (about 100 cases/s), 54 MB peak, completed (re-measured in 1.4; the first figures were inflated by a tracer) | Done | Offline path, one machine |
| R30 | Guarded live smoke test of OpenAI/DeepEval paths | `scripts/live_smoke.py`, `tests/test_live.py` | guard and failure paths tested | Done — not run live | Needs a key and spends money |
| R31 | Larger, tagged example corpus | `examples/documents/*`, `examples/datasets/*` | `test_example_corpus.py` | Done | Original text; small (30 questions each) |
| R32 | Organise run history: tags, notes, search | `history.py`, `storage.py` (schema 3), `cli.py`, UI | `test_history.py` (14), `test_storage.py` | Done | Search is a substring match |
| R33 | Regression gate for changes | `regression.py`, `ragwb regress` | `test_regression.py` (10) | Done | Needs enough paired questions |
| R34 | Abstention threshold tuned on held-out data | `abstention.py`, `ragwb tune-abstention` | `test_abstention.py` | Done - result negative | Few unanswerable questions; default stays off |
| R35 | Offline semantic metrics | `metrics/semantic.py` | `test_semantic.py` (10, stand-in embedder) | Done - not run with a real model | Optional `fastembed` |
| R36 | Named accounts and TLS | `users.py`, `ui/auth.py`, `start.py` | `test_users.py`, `test_start.py`; TLS probed with a self-signed certificate | Done | No roles, no data separation |
| R37 | Packaging | `config.py`, `pyproject.toml`, `Dockerfile` | `test_packaging.py`; wheel contents run from a neutral folder | Done - wheel CLI only; Docker not built | No Docker in the environment |
| R38 | Accessibility basics | `ui/components.py`, UI headings | scripted WCAG-style check of five pages | Partly | Canvas tables and third-party widgets are not accessible |
| R39 | Dense retrieval without an API key | `retrieval.py` (`LocalEmbeddingRetriever`), `pipeline.py`, `config.py` | `test_local_retrieval.py`; real-model comparison in `docs/LIVE_VERIFICATION.md` | Done - verified with a real model | Mixed gains; model download needed |
| R40 | Stay within provider quotas | `ratelimit.py`, `errors.py` (Retry-After), `metrics/judge.py` | `test_ratelimit.py`, `test_retry_hints.py`; live Groq runs | Done | Judge calls fan out; token quotas are separate |
| R41 | Quantify judge noise | `judge_noise.py`, `ragwb judge-noise` | `test_judge_noise.py`; live measurement in `docs/LIVE_VERIFICATION.md` | Done | Needs API calls |
| R42 | Roles and immediate revocation | `users.py`, `ui/auth.py`, UI views | `test_roles.py` | Done | No per-user data separation |
| R43 | Real-service verification of generation and judge metrics | `scripts/live_smoke.py` | live runs against Groq (12/12 checks), 30-case run | Done - one provider, small samples | Free-tier quotas |
| R44 | Keyboard accessibility | UI (Streamlit widgets) | scripted Tab walk over the New evaluation page + visual check of two focus indicators | Partly | axe-core (6 views clean) and 3 pages walked; no screen reader |
| R45 | Recover the run store from a backup | `maintenance.py` (`restore_store`), `ragwb restore` | `test_restore_concurrency.py` | Done | Stop the app first (Windows file lock is reported) |
| R46 | Manage accounts without the CLI; no lock-out | `ui/views/users.py`, `users.py`, `ui/auth.py` | `test_accounts_admin.py` | Done | No self-service reset by e-mail |
| R47 | Per-user run visibility | `ui/auth.py` (`visible_runs`), `RAGWB_RUN_VISIBILITY` | `test_accounts_admin.py` | Done | UI-level only; file access bypasses it |
| R48 | Choose a metric's pass threshold from labels | `calibration.py` (`sweep_thresholds`), `calibrate --sweep/--rescore` | `test_calibration_sweep.py`; live sweep in `docs/LIVE_VERIFICATION.md` | Done | Small samples; AI-written labels |
| R49 | Safe concurrent use of one run store | `storage.py` (short connections, 15 s busy timeout) | `test_restore_concurrency.py` (4 processes + a reader) | Done | Single machine |
| R50 | Clean-install proof | `scripts/wheel_check.py`, `verify.py --wheel` | 10/10 checks in a fresh venv | Done | CLI only (web app needs the project folder); Docker still unbuilt |
| R51 | Large-document scale | `retrieval.py` (inverted index), `scripts/benchmark_documents.py` | `test_bm25_equivalence.py`; benchmark table in `docs/OPERATIONS.md` | Done | 5,000 chunks: ~3 ms/query |
| R52 | Operations and security documentation | `docs/OPERATIONS.md`, `docs/SECURITY.md` | reviewed against the code | Done | No third-party penetration test |
| R53 | Live agent pipeline verification | `pipeline.py` (`AgentRAGPipeline`) | live Groq run, 3/3 cases, context from tool calls | Done - one provider, 3 cases | OpenAI itself not run |

## Acceptance-test matrix

| Acceptance criterion | How to check | Observed |
|---|---|---|
| One command sets up and starts the app | `python start.py` | environment synced, 5 example runs on first launch, app served at http://localhost:8501 |
| An offline evaluation completes from the UI | New evaluation → Run evaluation | 20/20 cases, completed (`test_ui.py`) |
| Results show answers with the retrieved chunks | Run results → Case detail | screenshot 05 |
| Two runs can be compared with uncertainty | Compare runs | screenshot 08; paired CI table |
| Failures are recorded, not fatal | example run with injected failures | status `partial`, 3/20 errors (screenshot 07) |
| Invalid dataset is rejected before running | upload a malformed file | start button disabled, errors listed (`test_new_run_blocks_invalid_inputs`) |
| OpenAI without a key is refused clearly | provider = OpenAI | message naming `OPENAI_API_KEY` (`test_openai_option_explains_missing_key`) |
| Exports re-import | export JSON → `ragwb import` | round trip equal (`test_export_import_round_trip`) |
| Tests pass offline | `uv run pytest` | 453 passed, 2 skipped |
