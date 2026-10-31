# Part X — Development history and engineering decisions

A condensed, truthful account of how the workbench was built. All work took place on 2026-10-23 and 2026-10-24;
the order below is the actual sequence, but times are not recorded. Measurements quoted here can be repeated with
the commands given.

## 100. Requirements and plan

Work started from a product brief: evaluate a retrieval-augmented QA pipeline over a question dataset with the
four standard judge metrics, compare runs, provide a Python-native UI, run without paid services, be thoroughly
tested and documented. The requirements were written down as R1–R22 (Part I, Chapter 10) and the design analysis
of Part II was carried out before any code was written.

## 101. Build order

The package was written in dependency order, each layer tested before the next:

1. configuration (`config.py`) and data contracts (`models.py`);
2. text utilities, document chunking and dataset validation;
3. BM25 and embedding retrieval; the error hierarchy; prompts; the extractive and OpenAI generators;
4. the two pipelines (retrieve-then-generate and tool-calling agent);
5. metrics (lexical and DeepEval judge adapters) and aggregation;
6. SQLite storage, the runner, reporting and exports, logging, application wiring, the CLI;
7. the Streamlit pages; run bundles; the example runs module and the `start.py` launcher;
8. the example document and datasets, the verification script, the documentation tooling and this book.

## 102. Architectural decisions

| Decision | Alternatives considered | Reason for the choice |
|---|---|---|
| One importable package with thin CLI/UI front ends | a chain of scripts; FastAPI between UI and logic | scripts drift apart and duplicate parameters; an HTTP layer had no requirement and would add a process to run |
| Capture context from the retriever/tool, never from the model | trust the model's structured "context" field | only the retrieved text is evidence; the self-report is kept for audit only |
| Default pipeline = retrieve-then-generate; agent mode available | agent only | with a fixed retrieve step, the evaluated context is by construction what the generator saw |
| Offline BM25 + extractive baseline + lexical metrics | mocks that return canned answers | a real (weak) system produces meaningful, inspectable numbers and exercises every code path |
| SQLite, one connection per operation | JSON files; an ORM | transactional, zero setup, safe under Streamlit reruns |
| In-memory embedding index | FAISS, Chroma | one document; no requirement justified a vector database |
| Validation before any run row exists | validate lazily per case | an invalid configuration must not leave a misleading partial run |
| Skipped/errored metrics excluded and counted | impute zero | imputation biases means and hides failures |
| Percentile bootstrap with fixed seed; paired comparison by question text | t-intervals; unpaired comparison | scores are bounded and skewed; pairing removes question difficulty from the comparison |
| Retries only in the runner; client retries off | rely on SDK retries | one observable attempt counter; no multiplied retries |
| Example data written for the project | public QA datasets | free to use, small enough to inspect by hand, properties known (paraphrased references, unanswerable set) |
| A standard-library launcher (`start.py`) | shell scripts per platform; a Makefile | one file that works on Windows, macOS and Linux before any dependency is installed |

## 103. Test milestones

56 unit tests after the first modules; 116 after the runner, storage and CLI; 123 with the first UI journeys; 140
after the review rounds, the run-bundle tests and the example-runs test. The suite has stayed fully offline
throughout (`tests/conftest.py` sets an empty API key and a temporary data directory for every test).

## 104. Documentation milestones

Supporting documents and the generated appendices were produced after the code stabilised; the book's Parts were
drafted from the code under an evidence rule (every claim checked against the source or a command's output),
then revised after each round of code changes, with line references re-verified.

## 105. Defects encountered, root causes and fixes

| # | Symptom | Root cause | Fix | Regression check |
|---|---|---|---|---|
| 1 | CSV export did not neutralise `=`/`+` cells | pandas 3 stores strings with a `str` dtype; the guard checked `dtype == object` | apply the guard to every non-numeric, non-boolean column | `test_csv_export_neutralises_formulas` |
| 2 | `python -m rag_workbench` failed outside the project root | the package was not installed in the environment | hatchling build; `uv sync` installs it editable | `test_module_entry_point_runs_in_a_subprocess` |
| 3 | demo runs with injected failures were slow | deterministic injected failures were raised as *transient*, so the runner backed off and retried pointlessly | injected failures raised as permanent errors | `test_failure_injection_is_deterministic` |
| 4 | UI test failed selecting a case | AppTest's `set_value` takes the underlying value, not the label (test bug) | test corrected | the test itself |
| 5 | screenshots showed an `ImportError` after a code change | the running Streamlit server kept an old version of an imported module | restart the app after editing package code (documented) | — |
| 6 | offline CLI runs recorded a judge model | the CLI always filled `judge_model` | recorded only when a judge metric is selected | `test_cli_run_list_show_compare_export` |
| 7 | "best run per metric" named one of several tied runs | `groupby().head(1)` breaks ties arbitrarily | ties are shown | manual check on the Compare page |
| 8 | unanswerable cases got a context-recall score | the metric scored the words of the abstention reference | skipped when the reference is an abstention | `test_skips_are_not_zero` |
| 9 | screenshots showed loading skeletons or a clipped sidebar | headless Chrome captured before Streamlit rendered; resizing re-triggered the sidebar animation | DevTools-protocol capture that waits for a stable page; fixed tall viewport; crop | inspection of every screenshot |
| 10 | stored config values reached `unsafe_allow_html` markup unescaped | header built with an f-string | values HTML-escaped | `test_imported_config_values_are_html_escaped` |
| 11 | opening the store from any process marked live runs `interrupted` | recovery relabelled every `running` row | heartbeat column (schema 2); only runs silent for 15 min are recovered; v1 stores migrated | `test_recover_interrupted_only_touches_stale_runs`, `test_schema_v1_store_is_migrated` |
| 12 | some store methods leaked raw `sqlite3` errors | translation only in a few methods | central translation in `_connect` | `test_sqlite_errors_become_storage_errors` |
| 13 | embedding-API rate limits were not retried | errors not classified in the embedding retriever | classified via `classify_openai_error` | `test_embedding_errors_are_classified_for_retry` |
| 14 | `ragwb delete` of an unknown id exited 0 | missing error branch | exit 1 with a message | `test_cli_errors_are_reported_not_raised` |
| 15 | traceback text could contain an unredacted key | the filter redacted only the message | `RedactingFormatter` redacts the formatted record | `test_redacting_formatter_covers_tracebacks` |
| 16 | curly quotes and dashes survived answer normalisation; then curly and straight apostrophes normalised differently | ASCII-only punctuation table; then deletion vs. space replacement | Unicode punctuation removed; all apostrophe styles deleted | `test_squad_normalize_drops_unicode_punctuation` |
| 17 | the secret scan missed `sk-proj-…` keys | pattern too narrow | broader pattern; deliberately fake test keys carry a `not-a-real` marker | `scripts/verify.py` |
| 18 | imported bundle summaries were trusted as stored | summary copied from the file | recomputed from the cases on import | `test_bundle_summary_is_recomputed_not_trusted` |
| 19 | out-of-range metric scores were silently clamped | clamp applied to every score | out-of-range → metric error; only float noise (≤ 1e-9) clamped | `test_out_of_range_scores_are_errors_but_float_noise_is_absorbed` |
| 20 | Streamlit listened on all network interfaces | no `server.address` set | `localhost` in `.streamlit/config.toml` and in `start.py` | configuration |
| 21 | exported bundles embedded absolute paths including the user name | paths copied verbatim | `portable_path`: project-relative, else file name only | `test_exported_bundles_contain_no_absolute_paths` |
| 22 | a fresh install in a very deep folder failed with `ImportError: cannot import name 'ArgsKwargs' from 'pydantic_core._pydantic_core'` | the compiled module's path reached Windows' 260-character limit | documented (short paths or long-path support) | troubleshooting entry |
| 23 | a rate-limited judge call was recorded as an error with the message `RetryError[<Future ...>]` and was not retried (release 1.3, found by the first live judge run) | DeepEval wraps the provider error in tenacity's `RetryError`; the classifier did not look inside | wrapped SDK errors are found and classified; retries wait for `Retry-After` | `tests/test_retry_hints.py` |
| 24 | connection drops during a live run were recorded as unexpected case errors instead of being retried (release 1.3, run 6, cases v16 and v17) | the first fix walked the cause chain to its end, past the OpenAI error to the `httpx` transport error, which is not an OpenAI error | the search stops at the first OpenAI SDK error | a regression test reproduces the chain (`tests/test_retry_hints.py`) |
| 25 | in a wheel installed into an empty environment, `tune-abstention`, the first-launch demo runs and the dataset picker could not find the bundled examples (release 1.4, found by `scripts/wheel_check.py`) | three call sites built the path from `PROJECT_ROOT / "examples"` instead of using the `EXAMPLES_DIR` rule that the default dataset already followed | they use `EXAMPLES_DIR` | `scripts/wheel_check.py` check 9 (not a pytest test: it downloads packages) |

Defects 10–21 were found while writing Parts III–XI (defects 23 and 24 were found by live runs in release 1.3, Part XV §160; defect 25 by a clean wheel install in release 1.4, Part XVI §176.2): documenting each function closely exposed behaviour that was
weaker than intended, and each was fixed before the documentation was finalised.

## 106. Failed approaches

* Plain headless-Chrome screenshots (defect 9).
* A first version of the verification script compared two runs that share no metric and treated the resulting
  "no shared metrics" exit as a failure; the product was right and the script's expectation was wrong.

## 107. The single launcher

`start.py` was added so that a fresh checkout needs one command. It uses only the standard library, prefers uv
(`uv sync --frozen --inexact`, which keeps optional documentation packages installed) and falls back to
`python -m venv` + `pip install -e .`. On the first launch it runs the five example evaluations so the app opens
with real results, then starts Streamlit on localhost and opens the browser. Verified from an empty data directory:
the environment synced, the five example runs were created (four `completed`, one `partial` by design), and a second
start served the app without re-creating them.

## 108. Dependency decisions

| Decision | Reason |
|---|---|
| explicit `pydantic` | used directly for contracts and settings |
| `python-dotenv` | optional `.env` loading |
| dev group `pytest`, `pytest-cov`; docs group `markdown` | testing and book build only |
| hatchling build backend | editable install of the `src/` package and the `ragwb` script |
| `pymupdf>=1.28.2,<2` | PyMuPDF 2.0 brings `onnxruntime` and layout models loaded at import that block extraction does not use (Chapter 109) |

## 109. Performance investigation

While checking a documentation claim that an offline run "takes about a second", measurement showed it was false:
a cold `ragwb run` took 5.6–6.2 s. Profiling with `cProfile` and `python -X importtime` located the cost: the
lock had resolved PyMuPDF 2.0, which depends on `onnxruntime`, `pymupdf-layout` and `pymupdf4llm` and loads
layout-analysis models when imported (`import pymupdf` alone: 3.3 s). The workbench needs only plain text blocks,
so the dependency was constrained to `pymupdf>=1.28.2,<2`, which removed eight packages. Measured afterwards:
`import pymupdf` 1.4 s; cold `ragwb run` 2.9–3.1 s over three runs; a warm in-process 20-case run about 0.3 s. The
README and UI wording were corrected to match. No other optimisation was attempted, because no other problem was
measured.

### Remaining technical debt

See Part XI and `docs/KNOWN_LIMITATIONS.md`: the live paths are verified only narrowly (release 1.3 ran one free-tier provider, Part XV; release 1.4 added a live agent run and a clean wheel install, Part XVI), and the UI's cancellation depends on
Streamlit's Stop button. (As of release 1.0 this list also named a single v1 → v2 storage migration and the package
locating its example data relative to its source; release 1.2 replaced both, Part XIV §152.2 and §157.)

### Release 1.1

The work done after the history above - the per-case time limit, judge retry and cost capture, hybrid retrieval, evidence-based
abstention, slices, calibration, `doctor`/`backup`/`prune`/`rerun`, the optional password, JSON logs, the static-analysis
gates, the scale benchmark and the guarded live smoke script - is the subject of Part XIII. The same rule applies: only what
was actually run is reported as verified.

### Release 1.2

The follow-up work - three more example documents with tagged datasets, tags, notes and search for runs, the
`ragwb regress` gate, the held-out abstention tuner (whose result was negative), the optional semantic metrics, named
accounts and TLS, `RAGWB_HOME` and wheel packaging, and a scripted accessibility check - is the subject of Part XIV. The
same rule applies: only what was actually run is reported as verified, and Part XIV §159.3 lists what was not.

### Release 1.3

The release that closed the gap between "implemented" and "verified" as far as a free-tier key and one small local model
allowed - a live run against a real OpenAI-compatible service that found and fixed two defects, request pacing and `Retry-After`,
local embeddings and a hybrid-local retriever, judge-noise measurement, three roles with immediate effect, and one keyboard
walk - is the subject of Part XV. The same rule applies: only what was actually run is reported as verified, and Part XV §167
lists what was not.

### Release 1.4

The release that took every remaining item that needed neither a human labeller, an OpenAI key nor Docker - `ragwb restore` with a
safety copy and an active-run guard, a multi-process store test, an admin Accounts page with a last-admin guard, password change and a
UI-level run filter, threshold sweeps (`calibrate --sweep` and `--rescore`) run on labels written by an AI rater, an inverted-index
BM25 with bit-identical scores, a clean wheel install that found one defect, an axe-core audit with more keyboard walks, a live
agent-pipeline run, and an operations runbook and security overview - is the subject of Part XVI. Four things it found were recorded and
then fixed or corrected (`restore` could not repair an unreadable store; the Settings page leaked a run count; both benchmark scripts timed code under `tracemalloc`, which invalidated their first figures and the offline "four workers are slower" conclusion of Part XIII §146). A full
four-judge live run (run 17) was cut short by a provider token cap. Part XVI §178.2 lists what remains unverified.
