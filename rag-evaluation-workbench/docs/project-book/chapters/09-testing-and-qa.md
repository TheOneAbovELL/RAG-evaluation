# Part IX — Testing and quality assurance

This part describes how the RAG Evaluation Workbench is tested, why the important tests exist, what the suite
actually reported when it was run for this book, and what it does not test. Test names and line numbers refer to
the files under `tests/`. Every result quoted here comes from a command given in §97, so a reader can reproduce
it.

## 90. Test strategy

The suite rests on four decisions.

1. **Everything runs offline, with no key.** An autouse fixture blanks `OPENAI_API_KEY` for every test
   (`tests/conftest.py:21-30`). Every path that would call OpenAI is tested through an injected fake: a scripted
   chat model, a deterministic fake embedding, fake DeepEval metric objects. A green run therefore proves nothing
   about the live API, and this part says so explicitly (§98).
2. **Real data where it is cheap, synthetic data where precision matters.** End-to-end tests use the bundled
   honeybee dataset and PDF (`conftest.py:17-18`), so a change that breaks the actual product breaks a test.
   Metric and retrieval tests use tiny hand-built inputs whose expected values are worked out by hand in comments
   (for example `tests/test_metrics.py:26-30`, `tests/test_retrieval.py:13-25`), so a formula error cannot hide
   behind a plausible-looking number.
3. **The real orchestration code runs; only the edges are replaced.** The runner accepts a `pipeline_factory`, a
   `metrics_factory` and a `sleep` function (`src/rag_workbench/runner.py:72-80`). Tests inject a `FakePipeline` and
   a recording `sleep`, but the retry loop, the thread pool, persistence and aggregation are the production code.
4. **Front ends are tested through their public entry points.** The CLI is tested by calling `cli.main([...])` and
   checking exit codes and output; the Streamlit app is tested headlessly with Streamlit's `AppTest`, which executes
   the real page scripts. There is no HTTP API to test (§93.3).

Where a test needs stored runs or bundles, it creates them by running real offline evaluations rather than loading
canned files (`tests/test_archive_reporting.py:24-41`, `tests/test_ui.py:38-65`), so every bundle a test imports was
produced by the current exporter.

## 91. Test architecture and fixtures

### 91.1 Tooling

* **pytest**, configured in `pyproject.toml` (`[tool.pytest.ini_options]`): `testpaths = ["tests"]`, `addopts = "-ra"`
  (summary of non-passing outcomes), and one marker, `ui`, for "Streamlit AppTest user-journey tests".
  `tests/test_ui.py` applies it module-wide (`pytestmark = pytest.mark.ui`, `tests/test_ui.py:10`), so
  `-m "not ui"` skips the journeys.
* **pytest-cov** for statement coverage (`[tool.coverage.run] source = ["rag_workbench"]`).
* **streamlit.testing.v1.AppTest** for the UI.
* Fakes from LangChain itself where available: `GenericFakeChatModel` (`tests/test_providers_pipeline.py:4`) and
  `DeterministicFakeEmbedding` (`tests/test_retrieval.py:51`).

Both `pytest` and `pytest-cov` are in the `dev` dependency group, which `uv sync` installs by default and which
`start.py` installs on both of its paths (Part VIII, §81.2–81.3).

### 91.2 Fixtures in `tests/conftest.py`

| Fixture / helper | Scope | What it provides | Why it matters |
|---|---|---|---|
| module top: `os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "1"` | session | set before any `rag_workbench` import (`conftest.py:11`) | no telemetry from test runs, however pytest is started |
| `isolated_env` | autouse, per test | blank `OPENAI_API_KEY`; `RAGWB_DATA_DIR` = `<tmp_path>/data`; `RAGWB_RETRY_BASE_DELAY_S` = 0; removes price, dataset, document and base-URL variables (`conftest.py:21-30`) | no test can read a developer's `.env` key (a blank value also blocks `.env`, because `load_dotenv` does not override existing variables), touch the project's `data/`, sleep through back-off, or pick up a custom default dataset |
| `settings` | per test | `load_settings()` under that environment (`conftest.py:33-35`) | the real settings loader |
| `store` | per test | a `RunStore` on the temporary data directory (`conftest.py:38-40`) | a real SQLite file per test |
| `chunks` | per test | four short honeybee passages as `Chunk` objects (`conftest.py:43-51`) | small enough to compute BM25 by hand |
| `small_dataset` | per test | a four-question JSONL file; `q4` has no reference answer (`conftest.py:59-66`) | exercises "skipped, not zero" on every run that uses it |
| `small_document` | per test | the four passages written as a `.txt` file (`conftest.py:69-73`) | the text-document path, independent of PyMuPDF |
| `offline_config` | per test | a factory for `RunConfig` over the two files above with the four default lexical metrics and `k = 2`, with keyword overrides (`conftest.py:76-83`) | one-line variations in runner tests |
| `FakePipeline` / `fake_pipeline_cls` | class / fixture | a pipeline double that returns scripted answers or raises scripted exceptions per question, optionally depending on the attempt number, and counts calls (`conftest.py:86-110`) | the basis of every failure, retry and cost test |
| `write_jsonl` | helper | writes rows as JSONL (`conftest.py:54-56`) | malformed datasets in one line |
| `REAL_DATASET`, `REAL_PDF` | constants | the bundled example files (`conftest.py:17-18`) | end-to-end tests use the real artefacts |

Module-level helpers outside `conftest.py`:

* `tests/test_ui.py`: the autouse `fresh_cache` clears `st.cache_resource` before and after each test
  (`tests/test_ui.py:14-18`) — otherwise the cached application context of one test, bound to that test's temporary
  data directory, would leak into the next; `seeded_run` stores one real five-case offline run
  (`tests/test_ui.py:38-47`); `bundle_from_run` exports such a run, lets the test edit the JSON payload, deletes the
  original and imports the edited bundle (`tests/test_ui.py:50-65`).
* `tests/test_archive_reporting.py`: `two_runs` performs real k = 1 and k = 3 runs over the example data, and `bundle`
  exports the second as a JSON bundle (`tests/test_archive_reporting.py:24-41`).
* `tests/test_runner.py`: `runner_with` builds a runner around a given pipeline and a recording `sleep`
  (`tests/test_runner.py:15-17`).

## 92. Directory map and test catalogue

### 92.1 Map

```text
tests/
  conftest.py                  shared fixtures and FakePipeline (no tests)
  test_text.py                 tokenisation, stemming, SQuAD normalisation, sentences, abstention
  test_config.py               settings loading, path resolution, validation, secret handling
  test_datasets.py             JSONL/CSV parsing and every validation rule
  test_documents.py            PDF and text chunking, error cases, hashing
  test_retrieval.py            BM25 against hand computation, ties, embedding retriever wiring
  test_providers_pipeline.py   extractive generator, failure injection, OpenAI adapters, agent pipeline
  test_metrics.py              lexical metrics, skip rules, score range, judge adapter
  test_aggregate.py            summaries, bootstrap, percentile, paired comparison
  test_storage.py              SQLite store, heartbeat recovery, schema migration
  test_runner.py               run orchestration, example runs
  test_archive_reporting.py    bundles, exports, comparison frames
  test_cli_services.py         CLI commands, uploads, log redaction
  test_ui.py                   Streamlit AppTest journeys
  test_maintenance.py          doctor, backup, prune, rerun, JSON logs (release 1.1)
  test_auth.py                 shared password, constant-time compare, lockout (release 1.1)
  test_start.py                launcher host/login/TLS rules, account detection, readiness polling (1.1, extended in 1.2)
  test_evaluation_options.py   hybrid fusion, min-evidence, heading skipping, slices (release 1.1)
  test_calibration.py          kappa by hand, label parsing, labelling sheet, CLI flow (release 1.1)
  test_live.py                 opt-in paid live test; guards of the smoke script (release 1.1)
  test_history.py              tag/note rules, search, storage round trip, bundles, CLI, Overview filter, Results editing (release 1.2)
  test_regression.py           every verdict, error-rate rule, exit codes (release 1.2)
  test_abstention.py           confusion arithmetic, deterministic split, held-out report, CLI (release 1.2)
  test_semantic.py             cosine, both metrics with a stand-in embedder, lazy load, refusal without the package (release 1.2)
  test_users.py                scrypt store, throttling, CLI, sign-in/lockout/sign-out/started_by journeys (release 1.2)
  test_packaging.py            project-root resolution, wheel bundles the examples (release 1.2)
  test_example_corpus.py       the three added documents and datasets are well-formed (release 1.2)
  test_local_retrieval.py      local retriever ranking and laziness, pipeline wiring, install hint, hybrid-local run (release 1.3)
  test_ratelimit.py            even spacing, no burst after idling, shared by threads, setting validation (release 1.3)
  test_retry_hints.py          Retry-After carried, tenacity unwrapping, transport-caused errors stay transient, back-off cap (release 1.3)
  test_judge_noise.py          within/between SD, flips, excluded failures, confirmation gate (release 1.3)
  test_roles.py                role storage and defaults, tampered roles, viewer/editor/admin journeys, removal at once (release 1.3)
  test_restore_concurrency.py  restore round trip and reversibility, refusals leave the store untouched, active-run guard, held-open store, four processes plus a reader (release 1.4)
  test_accounts_admin.py       last-admin guard, password change, admin Accounts page journeys, run visibility (release 1.4)
  test_calibration_sweep.py    threshold sweep table, best threshold and its tie rule, CLI sweep and rescore (release 1.4)
  test_bm25_equivalence.py     bit-for-bit equality of BM25 scores with the textbook definition (release 1.4)
```

`docs/project-book/generated/test-catalogue.md` lists every test function with its line number and its docstring
or first assertion; it is generated from the source by `docs/project-book/tools/generate_reference.py`. The rest of
this section explains the tests by area and, for the important ones, why they exist.

### 92.2 Text processing (`test_text.py`)

All lexical machinery — BM25, the extractive generator, context recall, groundedness — depends on `text.py`.
`test_tokenize_is_unicode_aware` checks that accented and non-Latin words survive tokenisation;
`test_content_tokens_drop_stopwords_and_stem` pins `"What do the workers build?"` → `["worker", "build"]`;
`test_squad_normalize_matches_reference_behaviour` pins the SQuAD answer normalisation that token F1 and exact match
rely on, and `test_squad_normalize_drops_unicode_punctuation` extends it to curly quotes, dashes and ellipses, which
Python's `string.punctuation` does not contain (`text.py:81-86`); `test_stem` (parametrised) pins the deliberately
light stemmer, including words it must leave alone (`grass`, `status`, `analysis`, per `text.py:59-64`);
`test_is_abstention` (parametrised) matters because abstention detection decides whether groundedness and context
recall are skipped.

### 92.3 Configuration (`test_config.py`)

`test_defaults_resolve_inside_project` pins the default dataset and document to the bundled honeybee files.
`test_relative_paths_are_resolved_against_project_root` and `test_absolute_path_kept` guarantee that behaviour does
not depend on the current directory. `test_invalid_values_raise_config_error_naming_the_variable` (parametrised)
ensures the user is told *which* variable is wrong. `test_secret_never_exposed` (`tests/test_config.py:48-55`) checks
that the key appears neither in `repr(settings)` nor in `public_dict()`; its deliberately fake key contains the marker
`not-a-real`, which the secret scan in `verify.py` ignores (§97.4).

### 92.4 Datasets and documents (`test_datasets.py`, `test_documents.py`)

`test_errors_are_reported_with_line_numbers` is parametrised over eight malformed inputs (invalid JSON, a non-object
line, missing or blank question, non-string reference, non-object metadata, bad id type, duplicate id) and asserts
both the message and the presence of a line number — validation never silently drops a row (`datasets.py:11-12`).
`test_limits` and `test_non_utf8_and_unsupported_type` cover the input limits; `test_non_ascii_round_trip` covers
non-English text; `test_real_dataset_is_valid` pins the bundled dataset (20 cases, first id `q01`). On the document
side, `test_real_pdf_chunks` (`tests/test_documents.py:7-14`) asserts that the bundled PDF yields 11 chunks, that the
first is the title "Honeybees: Life Inside the Colony", that no chunk contains a line break, and that ids are
unique; `test_errors` walks every `DocumentError` (not found, unsupported type, no text, over the limit, unopenable
PDF, non-UTF-8 text); `test_sha256_is_stable` pins the hash function against the known SHA-256 of `abc`, because
dataset and document hashes are the provenance record of every run.

### 92.5 Retrieval (`test_retrieval.py`)

`test_bm25_score_matches_hand_computation` recomputes the Okapi BM25 score of one chunk from the formula in the test
itself; `test_bm25_ranks_relevant_chunk_first` checks that "What do forager bees collect?" ranks the forager chunk
first; `test_bm25_is_deterministic_with_ties` checks that all-zero scores return document order;
`test_k_larger_than_corpus_and_invalid_k` covers the edges. `test_embedding_retriever_is_lazy_and_maps_ids`
(`tests/test_retrieval.py:50-67`) replaces `OpenAIEmbeddings` with a factory returning
`DeterministicFakeEmbedding(size=16)` and asserts that nothing is built at construction time, that the index is built
once on first query and reused, and that results map back to real chunk ids.
`test_embedding_errors_are_classified_for_retry` makes the fake embeddings raise a real `openai.RateLimitError` and
asserts that `retrieve` raises `TransientProviderError`, so the runner retries it like a generation error. These two
are the only tests of the embedding retriever; they test the wiring, not retrieval quality with real embeddings.

### 92.6 Providers and pipelines (`test_providers_pipeline.py`)

* `test_extractive_generator_selects_matching_sentences_in_order` and `..._abstains_without_overlap` pin the offline
  baseline, including that it reports no tokens ("not a language model").
* `test_failure_injection_is_deterministic` (`:30-47`) asserts identical failures over two passes, a strictly partial
  failure count at rate 0.5, and that the injected error is exactly `ProviderError` (`type(info.value) is
  ProviderError`), not its retryable subclass — see §96.1.
* `test_classify_openai_errors` (`:50-58`) constructs real `openai` exception objects and checks the mapping: rate
  limit and timeout → `TransientProviderError`; authentication → `ProviderError` whose message names `OPENAI_API_KEY`
  and does not contain the key-like string from the exception.
* `test_openai_generator_records_tokens_and_prompt` and `test_openai_generator_errors` replace the LangChain client
  with a scripted object and check token accounting, the numbered-passage prompt, the empty-answer error and timeout
  mapping.
* `test_rag_pipeline_evaluates_exactly_the_retrieved_chunks` (`:92-98`) guards the central measurement rule: the
  contexts recorded for scoring are exactly the retriever's output, because a model's description of its evidence
  is not evidence.
* `test_agent_pipeline_captures_real_tool_output_not_self_report` (`:126-144`) drives the real `AgentRAGPipeline` and
  LangChain's `create_agent` with a scripted tool-calling fake chat model. The fake first calls `collecting_info`
  with the query "forager collect nectar", then returns a structured answer whose `context` field is
  `"I invented this context."`. The test asserts that the recorded contexts are the chunk the tool actually returned
  (`p1-b2`), that the self-report is kept only as `model_context_claim`, and that tokens are summed across both model
  messages (250 in, 30 out). It is the most important test of the agent mode, and it runs without GPT.
* `test_build_pipeline_validation` and `test_build_openai_pipelines_with_key` cover the factory's refusals and
  construction with a test key (no call is made at construction).

### 92.7 Metrics (`test_metrics.py`)

The lexical tests use hand-computed expectations stated in comments: token F1 0.75 where SQuAD keeps the stop word
"and" (`:26-32`), multiset overlap 0.4 (`:35-38`), ROUGE-L from an LCS of 3 (`:41-46`), context recall 3/4 with the
missing term ("pollen") named in the reason (`:49-55`). `test_skips_are_not_zero` (`:58-67`) encodes the rule that
missing inputs and abstentions are *skipped*, never scored 0 — the rule that keeps means honest — including the case
of an unanswerable question whose reference is the abstention sentence. `test_custom_threshold_and_errors_are_captured`
checks that a metric that raises becomes an `error` result rather than aborting the case.
`test_out_of_range_scores_are_errors_but_float_noise_is_absorbed` (`:148`) checks the score-range rule of
`Metric.evaluate`: a score more than `SCORE_TOLERANCE` = 1e-9 outside [0, 1] is an `error` with no score, while
floating-point noise such as `1.0000000000000002` becomes exactly 1.0 (`src/rag_workbench/metrics/base.py:23`, `88-92`).

Judge metrics are tested at the adapter boundary. `test_judge_metric_uses_fresh_metric_and_threshold` and
`test_judge_metric_requirements_and_failures` use a `FakeDeepEvalMetric` with DeepEval's `measure`/`score`/`reason`
protocol: a fresh metric object per case (DeepEval metrics are stateful), thresholds passed through, retrieval context
passed as `retrieval_context`, a `RateLimitError` turned into an `error` result, and a `None` score treated as an
error. `test_build_judge_metric_constructs_deepeval_objects_without_network` (`:137-145`) builds the real DeepEval
objects (`GEval`, `AnswerRelevancyMetric`, `FaithfulnessMetric`, `ContextualRelevancyMetric`) with a test key, which
verifies that the adapter matches the installed DeepEval API without measuring anything.

### 92.8 Aggregation (`test_aggregate.py`)

`test_missing_values_are_excluded_not_zeroed` (`:23-32`) builds five cases — two scored, one skipped, one metric error,
one failed case — and asserts counts `(2, 1, 2)`, mean 0.5 and pass rate 0.5: the arithmetic core of every reported
number. `test_bootstrap_is_deterministic_and_brackets_mean` guarantees identical intervals for identical data (fixed
seed). `test_paired_comparison_matches_by_question_text` checks that pairing normalises case and whitespace and drops
questions present in only one run or skipped in one, which is what makes run comparisons paired.

### 92.9 Storage (`test_storage.py`)

Round trip with Unicode and position ordering, duplicate and missing-run errors, cascade delete, refusal of a newer
schema, and an unwritable location. `test_recover_interrupted_only_touches_stale_runs` back-dates one run's heartbeat
and checks that only that run becomes `interrupted` while a run with a fresh heartbeat — one another process may be
executing — stays `running`; `test_case_commits_refresh_the_heartbeat` checks that committing a case renews it;
`test_schema_v1_store_is_migrated` builds a version-1 database by hand and checks it is upgraded to version 2;
`test_sqlite_errors_become_storage_errors` drops a table underneath the store and checks the error is translated into
`StorageError`.

### 92.10 Runner (`test_runner.py`)

| Test | Why it matters |
|---|---|
| `test_offline_end_to_end_on_the_real_dataset` (`:19-31`) | the real product path on the real data: 20 cases, 3 contexts each from the retriever, thresholds and generator model recorded, dataset hash and package versions stored |
| `test_offline_runs_are_reproducible` (`:34-39`) | two runs give identical answers and scores with different ids |
| `test_missing_reference_skips_reference_metrics` | `q4` without a reference is skipped for token F1 and counted as skipped |
| `test_partial_and_failed_statuses` (`:50-60`) | one permanent error → `partial`, error text kept, no metrics; all errors → `failed` |
| `test_transient_errors_are_retried_with_backoff` (`:63-72`) | §96.3 |
| `test_retries_give_up` (`:75-80`) | after `max_retries` the case fails with "gave up after 3 attempts" and the pipeline was called exactly 3 times |
| `test_unexpected_exceptions_do_not_abort_the_run` | a `KeyError` in the pipeline becomes "Unexpected KeyError" on one case |
| `test_cancellation_event_stops_and_records_progress` (`:90-101`) | cancelling after two cases leaves a `cancelled` run with exactly two stored results and a summary of two |
| `test_exception_in_progress_callback_marks_run_cancelled` (`:104-114`) | a `BaseException` from the progress callback — how Streamlit's Stop reaches the runner — re-raises and leaves a `cancelled` run with its finished case |
| `test_parallel_execution_keeps_every_case` (`:117-125`) | four workers: 20 results in position order, answers identical to a serial run |
| `test_validation_happens_before_a_run_is_created` (`:128-138`) | missing key for a judge metric, bad threshold, missing dataset, missing document: all refused and **no run row exists** |
| `test_limit_and_cost` (`:141-149`) | `limit=2` evaluates two cases; cost computed from prices (7e-5 USD per case) and `None` when prices are unset |
| `test_run_ids_are_safe_and_unique` (`:152-155`) | 20 ids from a hostile name are unique and contain no `/` or `..` |
| `test_demo_runs_are_genuine_and_reproducible` (`:158-167`) | the five example runs that `start.py` creates: the expected keys, `k3` completed, `failures` partial, the unanswerable run has 6 cases, and a second seeding reproduces the `k3` token F1 mean exactly |

### 92.11 Bundles and reporting (`test_archive_reporting.py`)

All tests here work on bundles exported from real runs (the `two_runs` and `bundle` fixtures).
`test_export_import_round_trip` (`:33-42`) imports a bundle into a second store, compares the case results for
equality, checks the `imported` status and `original_status`, checks the recomputed context-recall mean, and checks
that a second import is skipped. `test_invalid_bundles_are_rejected` is parametrised over four malformed files plus
missing and oversized files; `test_duplicate_case_ids_rejected` edits a real bundle. `test_bundle_summary_is_recomputed_not_trusted`
(`:71-79`) tampers with the bundle's token F1 mean (0.999) and asserts that the imported run shows the mean recomputed
from its cases. `test_exported_bundles_contain_no_absolute_paths` (`:82-88`) and
`test_example_paths_become_project_relative` (`:91-94`) check that bundles never carry absolute local paths: files
outside the project are reduced to their name, the example files become `examples/datasets/honeybees.jsonl` and
`examples/documents/honeybees.pdf`. `test_csv_export_neutralises_formulas` is discussed in §95.1;
`test_json_and_markdown_exports` checks the bundle header, 20 cases, the Markdown title, a summary row, a "Lowest …"
section, rendering of a provenance warning, failed-case escaping (`P \| R`), and refusal of an unknown format;
`test_write_export_and_safe_filenames` checks `../../etc/passwd` → `etc_passwd`; `test_summary_and_comparison_frames`
checks the run table and a paired difference.

### 92.12 CLI and services (`test_cli_services.py`)

See §93.2 for the CLI tests. The service-level tests: `test_save_upload_sanitises_names` (`:64-76`, upload name
`../../evil name.jsonl` → `<hash>-evil_name.jsonl` inside `uploads/`; content addressing; suffix and size refusals);
`test_secret_redaction_filter` (`:91-96`, the configured secret and an `sk-…` string are both masked in the formatted
message); and `test_redacting_formatter_covers_tracebacks` (`:79-88`, a secret inside an exception's text is masked in
the formatted traceback).

### 92.13 Release 1.1 test files

| File | Tests | Notable cases (names as in the file) |
|---|---:|---|
| `test_maintenance.py` | 21 | `test_doctor_passes_on_a_healthy_installation`, `test_doctor_detects_a_corrupt_store`, `test_doctor_checks_network_exposure` (parametrised), `test_backup_is_a_consistent_verified_copy`, `test_prune_never_selects_a_run_that_may_still_be_executing`, `test_rerun_reproduces_an_offline_run_exactly`, `test_json_log_format_redacts_secrets` |
| `test_auth.py` | 8 | `test_password_comparison`, `test_throttle_locks_after_the_limit_and_recovers`, `test_settings_never_expose_the_password`, `test_protected_app_blocks_every_page_until_sign_in`, `test_repeated_failures_lock_out_even_the_right_password` |
| `test_start.py` | 11 | `test_exposed_hosts_are_refused_without_a_password_and_allowed_with_one`, `test_password_is_detected_in_the_environment_and_in_dotenv`, `test_wait_until_ready_sees_a_healthy_server_and_stops_when_the_process_died`, `test_the_launcher_refuses_an_exposed_host_without_a_password_before_touching_anything` |
| `test_evaluation_options.py` | 21 | `test_rrf_fusion_matches_the_formula_and_prefers_agreement` (the worked example of Part XIII §142.1), min-evidence and heading-skipping cases, slice breakdowns |
| `test_calibration.py` | 39 | `test_kappa_hand_computed` (20/5/10/15 gives 0.4), `test_kappa_is_undefined_when_a_rater_never_varies`, label parsing and error messages, the labelling-sheet round trip, the CLI flow |
| `test_live.py` | 7 | `test_live_smoke_script_passes` (skipped unless `RAGWB_LIVE_TESTS=1` and a key are set), `test_smoke_script_refuses_to_spend_without_the_flag`, `test_smoke_script_reports_failure_and_exits_nonzero_when_the_api_is_unreachable` |

Additions to existing files: `test_runner.py` gained `test_a_hung_case_is_abandoned_after_the_time_limit` and
`test_prices_are_stored_with_the_run`; `test_metrics.py` gained the judge retry and cost tests
(`test_judge_retries_transient_errors_with_backoff`, `test_judge_gives_up_after_the_retry_budget_and_does_not_retry_permanent_errors`,
`test_judge_cost_is_aggregated_per_run`); `test_ui.py` covers the settings health checks.

## 93. Unit, integration and interface tests

### 93.1 Unit versus integration

There is no directory split; the distinction is by what a test touches.

* **Unit tests** exercise one function or class with in-memory inputs: `test_text.py`, `test_config.py`, most of
  `test_datasets.py`, `test_metrics.py`, `test_aggregate.py`, `test_retrieval.py`, and the generator and error-mapping
  tests in `test_providers_pipeline.py`.
* **Integration tests** cross module boundaries and use real files and a real SQLite database: `test_storage.py`,
  `test_runner.py` (dataset loading → pipeline → metrics → store → aggregation), `test_archive_reporting.py` (runs →
  bundles → second store → exports), `test_documents.py` (PyMuPDF on the real PDF), and the agent pipeline test (real
  LangChain agent graph with a fake model).
* **Interface tests** drive the two front ends: `test_cli_services.py` and `test_ui.py`.

### 93.2 CLI-level tests

`test_cli_run_list_show_compare_export` (`tests/test_cli_services.py:14-27`) runs two short evaluations through
`main([...])`, then `list`, `show`, `compare` and `export --format json`, asserting exit codes, output fragments, the
exported file, and that neither offline run records a judge model (`:21`) — the configuration must never claim a
judge that did not run. `test_cli_errors_are_reported_not_raised` (`:30-47`) feeds a series of bad invocations —
OpenAI without a key, unknown metric, `-k 0`, unknown run id, malformed `--threshold`, an invalid dataset, `delete`
without `--yes`, a missing bundle — and asserts exit code 1 for each (and that the OpenAI message names
`OPENAI_API_KEY`), proving that user errors produce messages, not tracebacks.
`test_injected_failures_give_partial_run_exit_code` checks exit code 2. `test_module_entry_point_runs_in_a_subprocess`
(`:55-61`) runs `python -m rag_workbench metrics` in a separate process from a temporary working directory with a
minimal environment, which proves the editable install works outside the project root. `test_import_command`
(`:99-109`) runs, exports, imports (skipped: already present), deletes and imports again (imported).
`test_score_command` covers ad-hoc scoring and its refusal of a judge metric without a key.

### 93.3 API testing

The workbench has **no HTTP API**: the Streamlit pages call the package directly. Its programmatic interfaces are the
Python package, the CLI and the run-bundle file format; all three are tested above. There are therefore no HTTP,
contract or schema tests to be missing; the closest thing to a data contract — the bundle — is covered by the
round-trip, tampering, path and invalid-bundle tests.

`start.py` has no automated test. Its two observable behaviours — `--setup-only` seeding an empty store and leaving a
non-empty one alone — were checked by hand for Part VIII (§81.5); the seeding function it calls is covered by
`test_demo_runs_are_genuine_and_reproducible`.

## 94. UI testing with AppTest

### 94.1 How it works

`streamlit.testing.v1.AppTest.from_file` loads `streamlit_app.py` and runs the real page scripts in-process, without a
browser, exposing the rendered elements (titles, markdown, metrics, buttons, widgets) for inspection and interaction.
The helper `app(page)` (`tests/test_ui.py:21-28`) runs the entry point, switches to a page, reruns, and asserts that no
exception was rendered; `texts(at)` concatenates markdown, captions, titles and alert texts for substring assertions.
Each test runs against its own temporary data directory (`isolated_env` plus `fresh_cache`).

### 94.2 The journeys

| # | Test (`tests/test_ui.py`) | Journey | Key assertions |
|---|---|---|---|
| 1 | `test_overview_empty_state_then_runs` (`:68`) | open the app on an empty store | title; tiles "Runs stored 0", "New runs 0", "OpenAI key not set"; "No evaluations run yet"; no table |
| 2 | `test_overview_lists_stored_runs` (`:77`) | two stored runs | "Runs stored 2"; one table; the empty-state text is gone |
| 3 | `test_new_run_journey_offline_then_results_and_compare` (`:85`) | with one stored run, configure and start an offline run, inspect it, compare | "20 cases · 20 with reference answers", "11 chunks extracted"; judge metrics not offered without a key; "Run **ui-offline** finished"; results show "Cases 20/20" and five tabs; case detail of `q04` shows "chunks returned by the retriever" and a `rank 1 · p1-b…` caption; the compare page shows "Highlighted rows differ" and a paired-comparison caption |
| 4 | `test_new_run_blocks_invalid_inputs` (`:118`) | default dataset replaced (via `RAGWB_DATASET`) with a broken file | "This dataset cannot be used"; Run button disabled; clearing the metrics shows "no metric is selected" |
| 5 | `test_openai_option_explains_missing_key` (`:129`) | choose the OpenAI provider without a key | "OPENAI_API_KEY is not set"; Run button disabled |
| 6 | `test_failure_injection_shows_partial_run` (`:138`) | set injected failures to 0.5 and run | "partial" and "Failed cases are recorded" |
| 7 | `test_results_for_imported_run_show_provenance` (`:148`) | import a bundle that carries a provenance warning | the "Imported run" box and the warning text |
| 8 | `test_data_and_settings_pages` (`:158`) | Datasets & retrieval, then Settings & metrics | dataset tiles "Cases 20", "Errors 0"; a BM25 caption; "Metric catalogue" subheader; no `sk-` anywhere on the Settings page |
| 9 | `test_imported_config_values_are_html_escaped` (`:168`) | import a bundle whose `generator_model` is `<img src=x onerror=alert(1)>` and open it | the header markup contains the escaped text and no `<img` tag |

Journey 3 is the closest thing to an end-to-end test of the product: it goes through every page a user visits for a
first evaluation, using the real dataset, PDF, BM25, generator, metrics, runner and SQLite store.

### 94.3 What AppTest does not cover

AppTest checks the element tree Streamlit produces, not what a browser draws: layout, CSS, charts as rendered images,
file downloads and JavaScript behaviour are outside it, and no test drives the two `st.file_uploader` widgets. These
were checked manually in a browser and through the screenshots in `docs/project-book/screenshots/` (Part VIII,
§89.4); that is evidence of appearance at one moment, not an automated test.

## 95. Regression tests

Several behaviours were each broken at some point while the product was built; each now has a test that fails if it
breaks again. They are listed by what they guard.

### 95.1 CSV formula-injection guard covers every text column

* **Behaviour.** `export_csv` prefixes cells starting with `=`, `+`, `-`, `@`, tab or carriage return with `'`
  (`reporting.py:18`, `83-87`), and applies this to every column that is not numeric and not boolean
  (`reporting.py:92-100`, with a comment).
* **Why the test is written the way it is.** Under pandas 3, text columns have a dedicated `str` dtype; a guard that
  only treated `dtype == object` columns would silently skip every column while the helper `_csv_safe` itself stayed
  correct. `test_csv_export_neutralises_formulas` (`tests/test_archive_reporting.py:119-123`) therefore exports a
  question `=HYPERLINK("http://evil")` and an answer `+1 cmd|' /C calc'!A0`, parses the **output file** back, and
  asserts that both start with `'`.

### 95.2 Metric scores outside [0, 1]

* **Behaviour.** Judge libraries can return floating-point noise just above 1 (for example `1.0000000000000002` from
  GEval). `Metric.evaluate` absorbs deviations up to `SCORE_TOLERANCE` = 1e-9 and turns anything further outside
  [0, 1] into an `error` result with the reason `score … outside [0, 1]` (`metrics/base.py:93-96`, `92-96`); the
  `MetricResult` validator rejects out-of-range scores when a bundle is imported (`models.py:81-86`).
* **Guard.** `test_out_of_range_scores_are_errors_but_float_noise_is_absorbed` (`tests/test_metrics.py:148`). Checked
  directly as well: a scorer returning 5.0 gives `error`, −0.1 gives `error`, `1.0000000000000002` gives `ok` with
  score 1.0 (§99.2).

### 95.3 Context recall skips unanswerable cases

* **Behaviour.** For an unanswerable question the reference answer is the abstention sentence; measuring whether its
  words occur in the retrieved chunks says nothing about retrieval, so context recall is skipped with a reason
  (`metrics/lexical.py:69-71`). In the `unanswerable-k3` example run this skips the four unanswerable cases and
  scores only `a1` and `a2`.
* **Guard.** `test_skips_are_not_zero` (`tests/test_metrics.py:58-67`) asserts `skipped` and the word "unanswerable"
  in the reason.

### 95.4 The module entry point works outside the project root

* **Behaviour.** The project is installed in editable mode (hatchling build backend), so `python -m rag_workbench`
  works from any directory.
* **Guard.** `test_module_entry_point_runs_in_a_subprocess` (`tests/test_cli_services.py:55-61`) runs the module with
  `cwd=tmp_path`.

### 95.5 Offline runs record no judge model

* **Behaviour.** The CLI records a judge model only when a judge metric is selected (`cli.py:57-58`, `39-40`).
* **Guard.** `test_cli_run_list_show_compare_export` asserts `config["judge_model"] is None` for both CLI runs
  (`tests/test_cli_services.py:21`); `ragwb show` of an offline run prints `judge_model: None`.

### 95.6 Injected failures are permanent

* **Behaviour.** Injected offline failures are deterministic per question, so they are raised as `ProviderError`,
  which is not retried; raising the retryable `TransientProviderError` would only add back-off delay to every failing
  case (`providers.py:63-66`, with a comment).
* **Guard.** `test_failure_injection_is_deterministic` (`tests/test_providers_pipeline.py:30-47`) asserts the exact
  type, `type(info.value) is ProviderError`. A plain `pytest.raises(ProviderError)` would not be enough, because
  `TransientProviderError` is a subclass of `ProviderError` (`errors.py:13`). The exact type suffices because only
  `TransientProviderError` is retried (`runner.py:241-249`).

### 95.7 Other guarded behaviours

| Behaviour | Code | Guard |
|---|---|---|
| Run results header escapes values from imported bundles before inserting them into HTML | `ui/views/results.py:3`, `45-50` | `test_imported_config_values_are_html_escaped` |
| Start-up recovery marks only stale `running` runs as interrupted (heartbeat, 15-minute threshold); schema 1 → 2 migration | `storage.py:26-29`, `73-76`, `117`, `135-147` | `test_recover_interrupted_only_touches_stale_runs`, `test_case_commits_refresh_the_heartbeat`, `test_schema_v1_store_is_migrated` |
| SQLite errors surface as `StorageError` | `storage.py:85-98` | `test_sqlite_errors_become_storage_errors` |
| Secrets inside tracebacks are redacted in log output | `logging_setup.py:22-30` | `test_redacting_formatter_covers_tracebacks` |
| Embedding-API errors join the retry hierarchy | `retrieval.py:165-172` | `test_embedding_errors_are_classified_for_retry` |
| SQuAD normalisation removes Unicode punctuation | `text.py:81-86` | `test_squad_normalize_drops_unicode_punctuation` |
| Imported bundle summaries are recomputed, not trusted | `archive.py:67-72` | `test_bundle_summary_is_recomputed_not_trusted` |
| Bundles carry no absolute paths | `reporting.py:103-111` | `test_exported_bundles_contain_no_absolute_paths`, `test_example_paths_become_project_relative` |
| Scored contexts are the retriever's / tool's output, never the model's self-report | `pipeline.py:52-59`, `74-124` | `test_rag_pipeline_evaluates_exactly_the_retrieved_chunks`, `test_agent_pipeline_captures_real_tool_output_not_self_report` |
| "Best run per metric" shows ties instead of breaking them arbitrarily | `ui/views/compare.py:78` | none specific; journey 3 opens the Compare page but does not construct a tie |

## 96. Failure injection

The runner's error handling is tested at three levels.

### 96.1 Offline failure injection (product feature)

`RunConfig.offline_failure_rate` (`models.py:139`; CLI `--inject-failures`; UI "Inject failures" slider) makes the
extractive generator raise `ProviderError("Injected offline failure (offline_failure_rate > 0)")` for a deterministic
subset of questions: the decision is `random.Random(f"{seed}:{question}").random() < rate` (`providers.py:60-66`).
Determinism makes it testable: `test_failure_injection_is_deterministic` asserts identical outcomes over two passes
and a strictly partial failure count at rate 0.5. It is exercised end to end by the CLI
(`test_injected_failures_give_partial_run_exit_code`, rate 1.0 → exit 2), by the UI (journey 6, rate 0.5 →
"partial"), by `verify.py`'s end-to-end step (rate 1.0, `--limit 2`, expected exit 2), and by the example run
`injected-failures-30pct`, in which rate 0.3 on the 20 honeybee questions fails exactly `q03`, `q16` and `q17`
(17 ok, 3 errors — reproduced by a separate CLI run in Part VIII, §85.4).

### 96.2 Scripted pipeline failures (`FakePipeline`)

`FakePipeline` maps questions to behaviours: a fixed answer, an exception instance, or a callable of the attempt
number (`conftest.py:91-105`). That is enough to script every failure mode the runner distinguishes: a permanent
`ProviderError` (`test_partial_and_failed_statuses`), a `TransientProviderError` that clears after some attempts
(`test_transient_errors_are_retried_with_backoff`) or never clears (`test_retries_give_up`), and an arbitrary exception
(`test_unexpected_exceptions_do_not_abort_the_run`). At the adapter level, real `openai` exception objects are
constructed with `httpx` responses (`tests/test_providers_pipeline.py:50-58`, `82-89`; `tests/test_metrics.py:126-134`).

### 96.3 Retry back-off with a stubbed sleep

The runner takes its `sleep` function as a constructor argument (`runner.py:72-80`), and `runner_with`
(`tests/test_runner.py:15-17`) passes `sleeps.append`. `test_transient_errors_are_retried_with_backoff` (`:67-79`) sets a
base delay of 1 s, makes the first two attempts fail with `TransientProviderError("429")`, and asserts that the case
succeeds on attempt 3 and that exactly two delays were requested, in `[1, 2]` and `[2, 3]` — `base × 2^(attempt−1)`
plus up to one base delay of jitter (`runner.py:244-245`). No real time passes; the test documents the back-off
schedule as precisely as a specification would.

### 96.4 Cancellation and crashes

Cancellation is injected two ways: setting the `threading.Event` from the progress callback after two cases, and raising
a `BaseException` subclass from the callback (`tests/test_runner.py:97-121`). Process death is simulated at the storage
level by back-dating a run's heartbeat and calling `recover_interrupted`
(`test_recover_interrupted_only_touches_stale_runs`). No test kills a real process.

## 97. Commands and actual results

### 97.1 Commands

```bash
uv run pytest                                   # everything
uv run pytest -m "not ui"                       # without the AppTest journeys
uv run pytest --cov --cov-report=term           # with coverage
uv run pytest tests/test_runner.py -k retries   # one area
uv run python scripts/verify.py [--quick]
```

On Windows the same can be run with the environment's interpreter directly, which is how the results below were
produced: `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`. The option `-p no:cacheprovider` stops pytest
from writing `.pytest_cache/`; for the coverage run, `COVERAGE_FILE` pointed at a scratch directory so that the
project's `.coverage` file was not overwritten.

### 97.2 Results observed for this book

The runs below were made on 2026-10-28 against the release 1.2 tree. `pytest --collect-only` reported 331 tests in 26
files; the per-file counts agreed with `docs/TESTING.md` (the release 1.3 state follows the table).

| File | Collected cases |
|---|---:|
| `test_abstention.py` | 6 |
| `test_aggregate.py` | 6 |
| `test_archive_reporting.py` | 13 |
| `test_auth.py` | 8 |
| `test_calibration.py` | 39 |
| `test_cli_services.py` | 9 |
| `test_config.py` | 9 |
| `test_datasets.py` | 19 |
| `test_documents.py` | 5 |
| `test_evaluation_options.py` | 21 |
| `test_example_corpus.py` | 9 |
| `test_history.py` | 14 |
| `test_live.py` | 7 |
| `test_maintenance.py` | 21 |
| `test_metrics.py` | 15 |
| `test_packaging.py` | 5 |
| `test_providers_pipeline.py` | 10 |
| `test_regression.py` | 10 |
| `test_retrieval.py` | 7 |
| `test_runner.py` | 16 |
| `test_semantic.py` | 10 |
| `test_start.py` | 14 |
| `test_storage.py` | 9 |
| `test_text.py` | 19 |
| `test_ui.py` | 9 |
| `test_users.py` | 21 |
| **Total** | **331** |

(Case counts come from `pytest --collect-only -q`; several files expand through parametrisation, so they exceed the
number of test functions. Release 1.2 added seven files and 78 tests: `test_history.py`, `test_regression.py`,
`test_abstention.py`, `test_semantic.py`, `test_users.py`, `test_packaging.py` and `test_example_corpus.py`, plus additions
to `test_start.py`, `test_storage.py`, `test_metrics.py`, `test_maintenance.py` and `test_ui.py`.)

**Release 1.3.** The table above is the release 1.2 state. Release 1.3 added five files, `test_local_retrieval.py` (9),
`test_ratelimit.py` (8), `test_retry_hints.py` (8), `test_judge_noise.py` (8) and `test_roles.py` (10), and 43 tests in all;
`pytest --collect-only -q` on the final tree reports **375 tests** in 31 test files. The per-file counts in `docs/TESTING.md`
add up to 374, so one collected case is not attributed to a row there (the same one-test gap as in release 1.2, 332 collected
against 331 in the table). The final run recorded in `docs/TESTING.md` is **373 passed, 0 failed, 2 skipped** (the opt-in live
test and the opt-in real-model test), with statement coverage of **97 %** (3,375 statements, 118 missed); `ruff` and `mypy`
are clean over 46 source files. The per-module coverage listing and the `verify.py --quick` output below are the release 1.2
runs and were not regenerated.

**Release 1.4.** Four files were added: `test_restore_concurrency.py` (11), `test_accounts_admin.py` (12), `test_calibration_sweep.py` (8) and
`test_bm25_equivalence.py` (12), 43 tests in all. `pytest --collect-only -q` reports **418 tests** in 35 test files, and the per-file counts in
`docs/TESTING.md` now add up to 418, so the one-test gap of releases 1.2 and 1.3 is gone. The recorded run is **416 passed, 0 failed, 2 skipped**
(the same two opt-in tests), statement coverage **96 %** (3,567 statements, 125 missed), `ruff` and `mypy` clean over 47 source files. The four new
files hold 43 tests and all passed in the final full run (2 min 36 s for the whole suite). `test_restore_concurrency.py` starts real processes (four evaluations and a
reader against one store); `test_bm25_equivalence.py` uses exact `==` on float lists, never `approx` (Part XVI §172, §175.3).

**With coverage** - `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --cov --cov-report=term`, with
`COVERAGE_FILE` pointing at a scratch directory so the project's own `.coverage` file was not overwritten:

```text
Name                                    Stmts   Miss  Cover
-----------------------------------------------------------
src\rag_workbench\__init__.py               4      0   100%
src\rag_workbench\__main__.py               3      3     0%
src\rag_workbench\abstention.py           112      0   100%
src\rag_workbench\aggregate.py             99      0   100%
src\rag_workbench\archive.py               55      3    95%
src\rag_workbench\calibration.py          148      1    99%
src\rag_workbench\cli.py                  412     20    95%
src\rag_workbench\config.py               124      3    98%
src\rag_workbench\datasets.py             150      4    97%
src\rag_workbench\demo.py                  15      0   100%
src\rag_workbench\documents.py             90      2    98%
src\rag_workbench\errors.py                17      1    94%
src\rag_workbench\history.py               49      0   100%
src\rag_workbench\logging_setup.py         68      9    87%
src\rag_workbench\maintenance.py          167     16    90%
src\rag_workbench\metrics\__init__.py      33      0   100%
src\rag_workbench\metrics\base.py          59      1    98%
src\rag_workbench\metrics\judge.py         67      2    97%
src\rag_workbench\metrics\lexical.py       64      2    97%
src\rag_workbench\metrics\semantic.py      59      6    90%
src\rag_workbench\models.py               147      5    97%
src\rag_workbench\pipeline.py             104      8    92%
src\rag_workbench\prompts.py                7      0   100%
src\rag_workbench\providers.py             74      2    97%
src\rag_workbench\regression.py            63      0   100%
src\rag_workbench\reporting.py            129      2    98%
src\rag_workbench\retrieval.py            109      3    97%
src\rag_workbench\runner.py               191      8    96%
src\rag_workbench\services.py              56      2    96%
src\rag_workbench\storage.py               97      0   100%
src\rag_workbench\text.py                  39      0   100%
src\rag_workbench\ui\__init__.py            0      0   100%
src\rag_workbench\ui\auth.py              139      3    98%
src\rag_workbench\ui\components.py         54      3    94%
src\rag_workbench\ui\state.py              28      4    86%
src\rag_workbench\users.py                 89      3    97%
-----------------------------------------------------------
-----------------------------------------------------------
TOTAL                                    3121    116    96%
330 passed, 1 skipped in 72.21s
```

This re-run was made before two late tests were added; it reports 116 missed statements out of 3,121. The final tree
(`docs/TESTING.md`) records 331 passed and 116 missed out of 3,124. Both give 96 %.

The one skipped test is `tests/test_live.py:26`, the opt-in paid live test ("set RAGWB_LIVE_TESTS=1 and OPENAI_API_KEY
to run paid live tests"). There were no failures or errors. `-ra` printed only the skip.

**`scripts/verify.py --quick`** (`--quick` skips the AppTest journeys and coverage):

```text
[PASS] environment - Python 3.12.15
[PASS] lockfile - Resolved 141 packages in 1ms
[PASS] secrets - no key-shaped strings found
[PASS] static - clean (ruff, mypy)
[PASS] tests - 321 passed, 1 skipped, 9 deselected in 47.07s
[PASS] end-to-end - CLI workflow completed offline

6/6 checks passed
```

Exit code 0. The 9 deselected tests are the `ui`-marked AppTest journeys; 321 + 1 + 9 = 331.

The commands ran one after another; durations in pytest's summary line are not a performance measurement.

**Statement coverage only.** `--cov` measures statements, not branches (`branch = true` is not set), so 100 % for a
module does not mean that every condition was exercised both ways.

### 97.3 Why `ui/views/*` is not in the coverage figure

`pyproject.toml` configures `[tool.coverage.run] omit = ["*/ui/views/*"]` with the comment "page scripts are exercised
by AppTest in-process, which coverage cannot attribute reliably". The six page scripts are not imported as modules:
Streamlit (and AppTest) compiles and executes each file as a script on every rerun, so their line counts would depend on
how coverage's tracer interacts with Streamlit's script runner rather than on what the tests exercise. Rather than
report a misleading number, the project excludes them and relies on the AppTest journeys (§94). The consequence must
be stated plainly: the six files in `src/rag_workbench/ui/views/` (`compare.py`, `data.py`, `new_run.py`,
`overview.py`, `results.py`, `settings.py`) have **no measured coverage**, and the 96 % figure describes the package
without them. The shared UI modules `ui/components.py` and `ui/state.py`, which are imported normally, *are* measured.
`start.py` lies outside the package and is not measured either.

The single 0 % file, `__main__.py`, is executed only by `test_module_entry_point_runs_in_a_subprocess`, in a child
process that coverage is not configured to trace.

### 97.4 `scripts/verify.py`

`verify.py` (`scripts/verify.py:1-22`) runs six checks (plus an optional seventh) and exits non-zero if any fails:

1. **environment** - Python >= 3.12 and the core packages importable;
2. **lockfile** - `uv lock --check --offline` (skipped if uv is not on `PATH`);
3. **secrets** - no `.env` file and no key-shaped string (`sk-...`, including prefixed forms such as `sk-proj-...`) in the
   tree outside `.venv`, caches, `data`, `build` and `.git`, ignoring deliberately fake keys that contain `not-a-real`
   (`scripts/verify.py:38-39`; Part XI, §111.5);
4. **static** - `ruff check .` and `mypy` (`scripts/verify.py:90-101`); skipped with a note if the tools are not
   installed (release 1.1);
5. **tests** - pytest; with `--quick`, `-m "not ui"` and no coverage;
6. **end-to-end** - in a temporary data directory: `validate` every example dataset; an offline run; `show`; `export`
   as CSV, JSON and Markdown; `import` of the exported bundle (skipped as already present); a second run and a
   `compare`; a failure-injected run (expected exit 2); `run --provider openai` without a key (expected exit 1); and,
   new in 1.1, a run over the unanswerable dataset followed by `slices --by type`, `labels-template`, `backup` and
   `doctor`, and, new in 1.2, `tag`, a filtered `list`, a `regress` of a run against itself, `tune-abstention` and `user list`
   (`scripts/verify.py:137-178`).
7. **audit** (only with `--audit`) - `pip-audit` over the locked runtime requirements (`scripts/verify.py:104-119`);
   the only step that contacts a remote service.

Its output is quoted in §97.2.

## 98. Known untested areas and environmental limitations

### 98.1 What is not tested

* **Real OpenAI and DeepEval calls are never executed by the test suite.** The OpenAI generator, the agent pipeline, the embedding
  retriever and the four judge metrics are tested only through fakes and by constructing real client and metric
  objects without calling them. Release 1.3 ran generation and the four judge metrics once, by hand, against Groq's free tier
  (`docs/LIVE_VERIFICATION.md`, Part XV §160), which found two defects the fakes had not; that run is a record, not a test.
  Still unverified: OpenAI itself, the agent pipeline and API embeddings against a live service, the agent's structured-output
  reliability with GPT, judge-score stability beyond the one noise measurement, and anything under real load.
* **The embedding retriever** is tested with `DeterministicFakeEmbedding` and a fake that raises: wiring, laziness, id
  mapping and error classification, not retrieval quality. The local retriever is tested with a stand-in embedder and, in one
  opt-in test, with the real model; its retrieval quality was compared with BM25 once, by hand (Part XV §162).
* **`start.py`**: since release 1.1 its host and password rules and readiness polling are tested (`tests/test_start.py`);
  the environment preparation, the pip fallback without uv and the interactive server mode are not covered by automated
  tests and were not exercised for this book.
* **Load testing is limited to one offline benchmark.** The largest automated workload in the test suite is the 20-case
  dataset; `scripts/benchmark.py` measured 200 to 5,000 offline cases on one machine (Part XIII §146) but is not a test and
  asserts nothing. Runs against a live provider were never measured.
* **No browser-level end-to-end tests** beyond AppTest and manual checks with screenshots. File uploads through the
  browser widget are not covered (the sanitisation function behind them is).
* **No formal accessibility testing.** Release 1.2 added a scripted browser check of five pages (not part of the test suite; Part XIV §158) and release 1.3 one keyboard Tab walk of the New evaluation page (Part XV §166). Release 1.4 added an axe-core 4.10.2 audit (no violations on six page views, one minor issue in Streamlit's file uploader) and keyboard walks of Run results and Settings (Part XVI §177); keyboard walks of Overview, Compare, Datasets and Accounts, screen readers and zoom were not checked.
* **Concurrency is lightly tested**: one four-worker run compared with a serial run; heartbeat-based recovery tested at
  the storage level. No test runs two processes or two Streamlit sessions against one store.
* **Markdown rendering of untrusted text** in the UI (questions and answers are rendered with `st.write`) is not
  tested; only the HTML-escaped header is (journey 9).
* **`ui/views/*` coverage** is not measured (§97.3).
* **Dependency scan:** `pip-audit` over the locked runtime requirements found no known vulnerabilities at one point in
  time (Part XIII §145.4); it is a point-in-time result and is not part of the default test run (`verify.py --audit`).
* **The live path:** `scripts/live_smoke.py` has been run against Groq's free tier (2 cases, 12 of 12 checks, Part XV §160) but never
  against OpenAI itself; its guards and failure path are tested (Part XIII §147).

### 98.2 Environmental limitations

* All runs were made on one machine: Windows 11, CPython 3.12.15, the package versions in `uv.lock`. No Linux, macOS or
  Python 3.13+ run of the application was made (`start.py` itself was launched with Python 3.13.3).
* The project folder is synchronised by OneDrive; tests use pytest's temporary directories outside it, so the suite does
  not exercise SQLite inside a synchronised folder.
* Timings vary with machine load; the durations above were measured with other work running.

## 99. Reproducing the checks

Every check below writes nothing to `data/`.

### 99.1 Secret-scan pattern

```bash
.venv/Scripts/python.exe -c "import re; old=re.compile(rb'sk-[A-Za-z0-9]{20,}'); new=re.compile(rb'sk-(?:[A-Za-z0-9]+-)?[A-Za-z0-9_\-]{20,}'); k=b'sk-proj-'+b'A'*40; print(bool(old.search(k)), bool(new.search(k)))"
```

Observed: `False True`. A simple `sk-` + 20 alphanumerics pattern misses the `sk-proj-` form; the pattern in
`scripts/verify.py:38` matches it (it also matched `sk-svcacct-` + 40 characters and `sk-` + 40 characters). Do not test
the scan by planting a key-shaped string in the tree.

### 99.2 Out-of-range scores

```python
from rag_workbench.metrics.base import Metric, MetricSpec, MetricInput
for v in (5.0, 1.0000000000000002, -0.1):
    m = Metric(MetricSpec("x", "X", "lexical", "", 0.5), lambda inp, v=v: (v, "bogus"))
    r = m.evaluate(MetricInput("q", "a", None, []))
    print(v, r.status, r.score, r.reason)
```

Observed: `5.0 error None score 5.0 outside [0, 1]`; `1.0000000000000002 ok 1.0 bogus`;
`-0.1 error None score -0.1 outside [0, 1]`.

### 99.3 Injected failures: permanent, not transient

```python
from rag_workbench.errors import ProviderError, TransientProviderError
print(issubclass(TransientProviderError, ProviderError))   # True
```

This is why `pytest.raises(ProviderError)` alone could not tell the two apart, and why the test checks
`type(info.value) is ProviderError`.

### 99.4 Seeing a guard work

To see a regression test catch a regression, revert the guarded behaviour locally and run the named test. For example,
changing the column test in `reporting.export_csv` to `if df[column].dtype == object:` makes
`test_csv_export_neutralises_formulas` fail under pandas 3. (Not re-done for this book.)

### 99.5 Example-run results

```bash
RAGWB_DATA_DIR=<temp> python start.py --setup-only
RAGWB_DATA_DIR=<temp> uv run ragwb list
RAGWB_DATA_DIR=<temp> uv run ragwb compare <k1 id> <k3 id>
```

reproduces the example results quoted in Part VIII (§83.2, §85.4), for example the paired token-F1 difference of
−0.057 (95 % CI −0.116 to −0.008) between k = 1 and k = 3.
