# Source inventory

Generated from the source with `ast` by `docs/project-book/tools/generate_reference.py`. Line numbers refer to the files as they were when the book was built.

| File | Lines | Classes | Functions/methods |
|---|---:|---:|---:|
| `src/rag_workbench/__init__.py` | 19 | 0 | 0 |
| `src/rag_workbench/__main__.py` | 5 | 0 | 0 |
| `src/rag_workbench/abstention.py` | 177 | 3 | 15 |
| `src/rag_workbench/aggregate.py` | 179 | 2 | 10 |
| `src/rag_workbench/archive.py` | 82 | 1 | 2 |
| `src/rag_workbench/calibration.py` | 260 | 2 | 17 |
| `src/rag_workbench/cli.py` | 691 | 0 | 35 |
| `src/rag_workbench/config.py` | 241 | 2 | 18 |
| `src/rag_workbench/datasets.py` | 204 | 3 | 10 |
| `src/rag_workbench/demo.py` | 47 | 0 | 3 |
| `src/rag_workbench/documents.py` | 140 | 1 | 7 |
| `src/rag_workbench/errors.py` | 91 | 2 | 6 |
| `src/rag_workbench/history.py` | 80 | 1 | 5 |
| `src/rag_workbench/judge_noise.py` | 116 | 1 | 6 |
| `src/rag_workbench/logging_setup.py` | 105 | 3 | 9 |
| `src/rag_workbench/maintenance.py` | 308 | 1 | 15 |
| `src/rag_workbench/metrics/__init__.py` | 57 | 0 | 2 |
| `src/rag_workbench/metrics/base.py` | 98 | 4 | 4 |
| `src/rag_workbench/metrics/judge.py` | 135 | 1 | 6 |
| `src/rag_workbench/metrics/lexical.py` | 121 | 0 | 6 |
| `src/rag_workbench/metrics/semantic.py` | 143 | 3 | 11 |
| `src/rag_workbench/models.py` | 197 | 10 | 5 |
| `src/rag_workbench/pipeline.py` | 184 | 3 | 10 |
| `src/rag_workbench/prompts.py` | 34 | 0 | 2 |
| `src/rag_workbench/providers.py` | 119 | 4 | 6 |
| `src/rag_workbench/ratelimit.py` | 55 | 1 | 3 |
| `src/rag_workbench/regression.py` | 107 | 2 | 5 |
| `src/rag_workbench/reporting.py` | 208 | 0 | 15 |
| `src/rag_workbench/retrieval.py` | 216 | 5 | 12 |
| `src/rag_workbench/runner.py` | 278 | 3 | 15 |
| `src/rag_workbench/services.py` | 82 | 1 | 5 |
| `src/rag_workbench/storage.py` | 205 | 2 | 15 |
| `src/rag_workbench/text.py` | 100 | 0 | 7 |
| `src/rag_workbench/ui/__init__.py` | 1 | 0 | 0 |
| `src/rag_workbench/ui/auth.py` | 261 | 2 | 22 |
| `src/rag_workbench/ui/components.py` | 99 | 0 | 8 |
| `src/rag_workbench/ui/state.py` | 48 | 0 | 6 |
| `src/rag_workbench/ui/views/__init__.py` | 0 | 0 | 0 |
| `src/rag_workbench/ui/views/compare.py` | 129 | 0 | 0 |
| `src/rag_workbench/ui/views/data.py` | 87 | 0 | 1 |
| `src/rag_workbench/ui/views/new_run.py` | 248 | 0 | 1 |
| `src/rag_workbench/ui/views/overview.py` | 89 | 0 | 0 |
| `src/rag_workbench/ui/views/results.py` | 220 | 0 | 0 |
| `src/rag_workbench/ui/views/settings.py` | 58 | 0 | 0 |
| `src/rag_workbench/ui/views/users.py` | 72 | 0 | 1 |
| `src/rag_workbench/users.py` | 200 | 2 | 16 |
| `start.py` | 221 | 0 | 13 |
| `streamlit_app.py` | 42 | 0 | 0 |
| `scripts/benchmark.py` | 100 | 0 | 4 |
| `scripts/benchmark_documents.py` | 107 | 0 | 5 |
| `scripts/live_smoke.py` | 107 | 0 | 2 |
| `scripts/make_example_pdf.py` | 50 | 0 | 1 |
| `scripts/seed_demo_runs.py` | 47 | 0 | 1 |
| `scripts/set_api_key.py` | 131 | 0 | 6 |
| `scripts/verify.py` | 221 | 0 | 12 |
| `scripts/wheel_check.py` | 86 | 0 | 3 |

Total: 56 files, 389 functions and methods.

## `src/rag_workbench/__init__.py`

RAG Evaluation Workbench: evaluate a retrieval-augmented QA pipeline over a dataset.

*(no top-level definitions; page script or package marker)*

## `src/rag_workbench/__main__.py`

*(no top-level definitions; page script or package marker)*

## `src/rag_workbench/abstention.py`

Choosing the offline generator's abstention threshold on data it was not tuned on.

* **class `Setting`** (line 38) — —
    * `label(self)` (line 42) — —
* **class `Confusion`** (line 47) — Abstention decisions against what should have happened (positive = abstained).
    * `n_unanswerable(self)` (line 56) — —
    * `n_answerable(self)` (line 60) — —
    * `abstain_recall(self)` (line 64) — —
    * `answer_rate(self)` (line 68) — —
    * `balanced_accuracy(self)` (line 72) — —
    * `__add__(self, other)` (line 76) — —
* **class `TuningReport`** (line 81) — —
* `should_abstain(case)` (line 92) — —
* `split_cases(cases, salt)` (line 96) — Deterministic 50/50 split by hash parity of ``salt + id`` (stable across runs and platforms).
* `_decisions(settings, document, cases, setting)` (line 106) — —
* `tune(settings, pairs, *, thresholds)` (line 121) — Tune on the development halves of every (dataset, document) pair; report on the test halves.
* `_fmt(value)` (line 156) — —
* `format_report(report)` (line 160) — —

## `src/rag_workbench/aggregate.py`

Aggregation of per-case results into run summaries, and paired comparison of two runs.

* `bootstrap_ci(values, *, resamples, confidence, seed)` (line 23) — Percentile bootstrap CI of the mean. Needs at least two values.
* `percentile(values, q)` (line 37) — Linear-interpolation percentile (q in [0, 100]).
* `summarize_metric(name, results, threshold)` (line 47) — —
* `summarize_run(results, metric_names, thresholds)` (line 75) — —
* **class `SliceRow`** (line 99) — Summary of one metadata value (a "slice") of a run: how the system does on, say, ``type = unanswerable``.
* `metadata_keys(results)` (line 108) — Metadata keys present on at least one case, sorted.
* `slice_results(results, key, metric_names, thresholds)` (line 113) — Group cases by ``metadata[key]`` and summarise each group like a run.
* **class `PairedComparison`** (line 131) — Per-metric comparison of run B against run A on the cases both runs scored.
    * `significant(self)` (line 146) — True when the bootstrap CI of the paired difference excludes zero.
* `_case_key(case)` (line 151) — —
* `_scores_by_question(results, metric)` (line 155) — —
* `paired_comparison(results_a, results_b, metric, *, tie_tolerance)` (line 164) — Pair cases by normalised question text (robust to differing case ids across datasets).

## `src/rag_workbench/archive.py`

Run bundles: a single JSON file holding one run and all its case results.

* **class `BundleError`** (line 30) — The file is not a valid run bundle.
* `load_bundle(path, *, max_bytes)` (line 34) — —
* `import_bundle(store, path)` (line 59) — Import one bundle. Returns the run id, or ``None`` if a run with that id already exists.

## `src/rag_workbench/calibration.py`

Calibrating a metric against human judgement.

* **class `LabelsError`** (line 36) — The labels file is missing, unreadable or malformed.
* `parse_label(value)` (line 40) — True/False for recognised pass/fail spellings, None for blank. Raises ValueError for anything else.
* `load_labels(path)` (line 54) — Read human labels from CSV (``case_id,human_pass``) or JSONL (``{"case_id":..., "human_pass":...}``).
* `_csv_rows(text, name)` (line 91) — —
* `_jsonl_rows(text, name)` (line 98) — —
* **class `Agreement`** (line 114) — —
    * `accuracy(self)` (line 126) — —
    * `human_pass_rate(self)` (line 130) — —
    * `metric_pass_rate(self)` (line 134) — —
    * `precision(self)` (line 138) — Of the cases the metric passed, the share humans also passed.
    * `recall(self)` (line 143) — Of the cases humans passed, the share the metric also passed.
    * `kappa(self)` (line 148) — —
    * `small_sample(self)` (line 152) — —
* `cohen_kappa(tp, fp, fn, tn)` (line 156) — Cohen's kappa for two binary raters; ``None`` when undefined (no cases, or both raters constant).
* `interpret_kappa(kappa)` (line 168) — Landis & Koch (1977) verbal bands. Conventional labels, not a validity test.
* `calibrate(results, labels, metric)` (line 179) — Compare ``metric``'s pass/fail verdicts with ``labels`` over the cases of a run.
* `sweep_thresholds(results, labels, metric, thresholds)` (line 206) — Agreement with ``labels`` at each candidate pass threshold, using the stored scores of ``metric``.
* `best_threshold(rows)` (line 238) — The threshold with the highest kappa (ties: higher accuracy, then the lower threshold). ``None`` if undefined.
* `labelling_sheet(run, results)` (line 248) — A CSV for human labelling: the evidence for each case plus an empty ``human_pass`` column.

## `src/rag_workbench/cli.py`

Command-line interface: ``uv run ragwb <command>`` (equivalently ``python -m rag_workbench <command>``).

* `build_config(args, settings)` (line 40) — —
* `cmd_run(args, ctx)` (line 69) — —
* `_print_summary(run)` (line 82) — —
* `cmd_list(args, ctx)` (line 99) — —
* `cmd_tag(args, ctx)` (line 115) — —
* `cmd_tune_abstention(args, ctx)` (line 124) — —
* `cmd_regress(args, ctx)` (line 138) — —
* `_read_password(args)` (line 155) — —
* `cmd_user(args, ctx)` (line 164) — —
* `cmd_judge_noise(args, ctx)` (line 202) — —
* `cmd_note(args, ctx)` (line 226) — —
* `cmd_show(args, ctx)` (line 236) — —
* `cmd_compare(args, ctx)` (line 250) — —
* `cmd_export(args, ctx)` (line 262) — —
* `cmd_validate(args, ctx)` (line 270) — —
* `cmd_delete(args, ctx)` (line 283) — —
* `cmd_metrics(args, ctx)` (line 294) — —
* `cmd_import(args, ctx)` (line 304) — —
* `cmd_labels_template(args, ctx)` (line 311) — —
* `_rescored(ctx, metric, cases)` (line 322) — Copies of ``cases`` with ``metric`` computed from the stored answers and contexts (no API calls).
* `cmd_calibrate(args, ctx)` (line 348) — —
* `cmd_slices(args, ctx)` (line 385) — —
* `cmd_rerun(args, ctx)` (line 407) — Repeat a stored run from its recorded configuration (same dataset, document, pipeline and metrics).
* `cmd_backup(args, ctx)` (line 427) — —
* `cmd_restore(args, ctx)` (line 433) — —
* `cmd_prune(args, ctx)` (line 445) — —
* `cmd_doctor(settings)` (line 465) — —
* `cmd_score(args, ctx)` (line 476) — Score one answer with the chosen metrics, without running a pipeline or storing anything.
* `_positive_int(text)` (line 493) — —
* `_get_run(ctx, run_id)` (line 503) — The run with this exact id, or the single run matching it as an id prefix, an id suffix (the short id the web app shows) or an exact name. Ambiguous or unknown references are errors that say what matched.
* `build_parser()` (line 521) — —
* `main(argv)` (line 674) — —

## `src/rag_workbench/config.py`

Centralised configuration.

* `_find_project_root()` (line 21) — The folder that holds ``data/``, ``.env`` and ``examples/``.
* **class `ConfigError`** (line 50) — Raised when configuration values are missing or invalid.
* **class `Settings`** (line 54) — Runtime settings. Construct with :func:`load_settings` rather than directly.
    * `_valid_level(cls, value)` (line 99) — —
    * `db_path(self)` (line 106) — —
    * `uploads_dir(self)` (line 110) — —
    * `local_model_dir(self)` (line 114) — —
    * `users_path(self)` (line 118) — —
    * `has_users(self)` (line 122) — True when named accounts exist (a damaged users file counts: it must lock the app, not open it).
    * `login_required(self)` (line 129) — —
    * `backups_dir(self)` (line 133) — —
    * `exports_dir(self)` (line 137) — —
    * `log_path(self)` (line 141) — —
    * `has_openai_key(self)` (line 145) — —
    * `has_app_password(self)` (line 149) — —
    * `secret_values(self)` (line 152) — Every configured secret value, for log redaction.
    * `require_openai_key(self)` (line 157) — The API key's value, for handing to a client. Raises :class:`ConfigError` if none is configured.
    * `public_dict(self)` (line 163) — Settings safe to display or persist: secrets replaced by a presence flag.
* `load_settings(env, *, dotenv)` (line 204) — Build :class:`Settings` from ``env`` (defaults to ``os.environ``).
* `_env_name(field)` (line 237) — —

## `src/rag_workbench/datasets.py`

Evaluation dataset parsing and validation.

* **class `DatasetIssue`** (line 31) — —
    * `__str__(self)` (line 35) — —
* **class `DatasetReport`** (line 40) — Result of parsing a dataset: the cases plus any errors and warnings.
    * `ok(self)` (line 50) — —
    * `n_with_reference(self)` (line 54) — —
* **class `DatasetError`** (line 58) — Raised by :func:`load_dataset` when the dataset has validation errors.
    * `__init__(self, report)` (line 61) — —
* `parse_dataset(data, name, *, max_bytes, max_cases, max_field_chars)` (line 68) — Parse raw dataset bytes. ``name`` (a filename) selects the format by its suffix.
* `load_dataset(path, **limits)` (line 116) — Load and validate a dataset file, raising :class:`DatasetError` on any error.
* `validate_file(path, **limits)` (line 124) — —
* `_jsonl_rows(text, report)` (line 138) — —
* `_csv_rows(text, report)` (line 155) — —
* `_row_to_case(row, line, position, report, max_field_chars)` (line 171) — —

## `src/rag_workbench/demo.py`

Example runs over the bundled honeybee data (offline: no network, no API key).

* `_config(name, *, dataset, document, notes, k, metrics, failure_rate)` (line 18) — —
* `demo_configs(project_root, dataset, document)` (line 24) — —
* `seed_demo_runs(ctx)` (line 42) — Run every example configuration and return the stored runs by key.

## `src/rag_workbench/documents.py`

Source-document loading and chunking.

* **class `DocumentError`** (line 27) — Raised when a document cannot be read or contains no extractable text.
* `file_sha256(path)` (line 31) — —
* `load_chunks(path, *, max_chars, max_bytes)` (line 39) — Read ``path`` and return its chunks in reading order, with stable ids ``p{page}-b{n}``.
* `is_heading(text)` (line 73) — Heuristic: a short block that does not end like a sentence (``"Life Inside the Colony"``).
* `drop_headings(chunks)` (line 82) — Chunks without heading-like blocks (all chunks are kept if every one looks like a heading).
* `_pdf_blocks(path)` (line 88) — —
* `_text_blocks(path)` (line 112) — —
* `_split_long(text, max_chars)` (line 123) — —

## `src/rag_workbench/errors.py`

Exception hierarchy for model/provider calls and the mapping from OpenAI SDK errors.

* **class `ProviderError`** (line 9) — A model call failed in a way that retrying will not fix (bad key, invalid request...).
* **class `TransientProviderError`** (line 13) — A model call failed in a way that may succeed on retry (rate limit, timeout, 5xx).
    * `__init__(self, message, retry_after_s)` (line 19) — —
* `backoff_delay(base_s, attempt, exc, *, jitter)` (line 27) — Exponential back-off with jitter, stretched to the provider's ``Retry-After`` hint (capped at a minute).
* `classify_openai_error(exc)` (line 37) — Translate an OpenAI SDK exception into our hierarchy; ``None`` if it is not an OpenAI error.
* `_unwrap(exc)` (line 58) — The first OpenAI SDK error in ``exc``'s chain, or ``exc`` itself if there is none.
* `_retry_after(exc)` (line 79) — Seconds from a ``Retry-After`` response header, if the SDK error carries one.
* `_short(exc, limit)` (line 89) — —

## `src/rag_workbench/history.py`

Organising run history: tags, notes and search.

* **class `TagError`** (line 21) — A tag or note is not acceptable.
* `normalise_tags(tags)` (line 25) — Lowercase, strip, de-duplicate (keeping first-seen order) and validate. Raises :class:`TagError`.
* `parse_tag_list(text)` (line 41) — ``"a, b"`` -> ``["a", "b"]`` (commas or whitespace separate tags).
* `validate_notes(notes)` (line 46) — —
* `_haystack(run)` (line 54) — —
* `search_runs(runs, query, *, tag, status)` (line 63) — Filter ``runs`` (order preserved). ``query`` words must all appear in the run's id, name, notes, tags, status, provider, pipeline, retriever or dataset/document file names.

## `src/rag_workbench/judge_noise.py`

How much does a judge metric disagree with itself?

* **class `NoiseRow`** (line 30) — —
    * `noise_to_signal(self)` (line 41) — —
    * `small_sample(self)` (line 47) — —
* `estimate_operations(cases, n_metrics, repeats)` (line 51) — —
* `measure_noise(cases, metrics, thresholds, repeats, *, progress)` (line 55) — —
* `format_noise(rows)` (line 95) — —

## `src/rag_workbench/logging_setup.py`

Logging configuration with secret redaction.

* **class `RedactingFormatter`** (line 22) — Redacts the fully formatted record, including exception tracebacks and stack info.
    * `__init__(self, fmt, redactor)` (line 25) — —
    * `format(self, record)` (line 29) — —
* **class `RedactingJsonFormatter`** (line 33) — One JSON object per line (``ts``, ``level``, ``logger``, ``message``, optional ``exc``), redacted.
    * `__init__(self, redactor)` (line 39) — —
    * `format(self, record)` (line 43) — —
* **class `RedactSecretsFilter`** (line 51) — —
    * `__init__(self, secrets)` (line 52) — —
    * `redact(self, text)` (line 56) — —
    * `filter(self, record)` (line 61) — —
* `close_logging()` (line 69) — Close and detach the package's log handlers (releases the log file; needed before deleting a data directory on Windows, and lets :func:`configure_logging` reconfigure with new settings).
* `configure_logging(settings, *, console)` (line 79) — Idempotently configure the ``rag_workbench`` logger.

## `src/rag_workbench/maintenance.py`

Operations tooling: health checks (``ragwb doctor``), store backup, retention pruning and re-running a stored run.

* **class `Check`** (line 36) — —
* `run_doctor(settings, *, config_file)` (line 43) — Run every health check and return the results (never raises).
* `_check_python()` (line 59) — —
* `_check_packages()` (line 65) — —
* `_check_data_dir(settings)` (line 77) — —
* `_check_disk(settings)` (line 87) — —
* `_check_store(settings)` (line 95) — —
* `_is_stale(run)` (line 117) — —
* `_check_examples(settings)` (line 121) — —
* `_check_key(settings)` (line 135) — —
* `_check_telemetry()` (line 141) — —
* `_check_exposure(settings, config_file)` (line 148) — —
* `backup_store(store_path, dest_dir)` (line 168) — Copy the run store with SQLite's online backup API (consistent even while the app is writing).
* `select_prunable(runs, *, keep_last, older_than_days)` (line 203) — Runs eligible for deletion under a retention policy. Runs that may still be executing are never selected.
* `restore_store(backup_path, store_path, safety_dir, *, force)` (line 229) — Replace the run store with a backup made by :func:`backup_store`.
* `rerun_config(run, *, name, project_root)` (line 294) — Rebuild a :class:`RunConfig` from a stored run so the same experiment can be repeated.

## `src/rag_workbench/metrics/__init__.py`

Metric registry: lexical (offline) and LLM-judge (DeepEval, OpenAI) metrics.

* `validate_metric_names(names, settings)` (line 18) — Raise :class:`ConfigError` for unknown metrics, or judge metrics without an API key.
* `build_metrics(names, settings, *, judge_model, timeout_s, max_retries)` (line 34) — —

## `src/rag_workbench/metrics/base.py`

Metric contract and the shared evaluation wrapper.

* **class `MetricInput`** (line 29) — —
* **class `MetricSpec`** (line 37) — —
* **class `MetricSkipped`** (line 49) — Raised inside a metric function to report a 'skipped' result with a reason.
* **class `Metric`** (line 58) — A named scorer plus its requirements. Subclasses or plain scorers both fit.
    * `__init__(self, spec, scorer)` (line 61) — —
    * `name(self)` (line 66) — —
    * `score(self, inp, threshold)` (line 69) — Compute ``(score, reason)`` or ``(score, reason, cost_usd)``. Subclasses without a plain scorer override.
    * `evaluate(self, inp, threshold)` (line 75) — —

## `src/rag_workbench/metrics/judge.py`

LLM-as-a-judge metrics backed by DeepEval: answer relevancy, faithfulness, context relevancy, correctness.

* **class `JudgeMetric`** (line 48) — A DeepEval metric; ``factory(threshold)`` returns a fresh DeepEval metric object.
    * `__init__(self, spec, factory, *, max_retries, retry_base_delay_s, sleep, limiter)` (line 56) — —
    * `score(self, inp, threshold)` (line 66) — —
    * `_measure(self, inp, threshold)` (line 82) — —
* `build_judge_metric(name, *, model, api_key, base_url, timeout_s, max_retries, retry_base_delay_s, max_requests_per_minute)` (line 102) — Create a judge metric. The DeepEval model object is created per measurement.

## `src/rag_workbench/metrics/lexical.py`

Offline, deterministic lexical metrics.

* `exact_match(inp)` (line 17) — 1.0 when the SQuAD-normalised answer equals the normalised reference.
* `token_f1(inp)` (line 23) — SQuAD token-level F1 between answer and reference (multiset overlap of normalised tokens).
* `_lcs_length(a, b)` (line 39) — —
* `rouge_l(inp)` (line 52) — ROUGE-L F1 (Lin, 2004): longest common subsequence of normalised tokens.
* `context_recall(inp)` (line 63) — Share of the reference answer's distinct content terms that appear in the retrieved context.
* `groundedness(inp)` (line 84) — Share of the answer's distinct content terms that appear in the retrieved context.

## `src/rag_workbench/metrics/semantic.py`

Optional offline semantic metrics, computed with a local sentence-embedding model.

* **class `Embedder`** (line 39) — —
    * `embed(self, texts)` (line 40) — —
* `semantic_available()` (line 43) — —
* `cosine(a, b)` (line 47) — Cosine similarity in [-1, 1]; 0.0 when either vector is all zeros.
* **class `FastEmbedEmbedder`** (line 56) — The real embedder: a local ONNX model through ``fastembed`` (imported lazily).
    * `__init__(self, model_name, cache_dir)` (line 59) — —
    * `embed(self, texts)` (line 68) — —
* `local_embedder(model_name, cache_dir)` (line 74) — —
* **class `SemanticMetric`** (line 78) — A metric that scores with embeddings. ``embedder_factory`` is called once, on first use.
    * `__init__(self, spec, kind, embedder_factory)` (line 81) — —
    * `_get_embedder(self)` (line 88) — —
    * `score(self, inp, threshold)` (line 94) — —
* `local_model_error(model_name, cache_dir, exc)` (line 120) — One clear message for a model that cannot be loaded (usually: not downloaded yet and no network).
* `build_semantic_metric(name, *, model_name, embedder_factory, cache_dir)` (line 131) — —

## `src/rag_workbench/models.py`

Data contracts shared by every layer (pipeline, metrics, storage, UI).

* `utcnow()` (line 18) — —
* **class `EvalCase`** (line 22) — One dataset row: a question, an optional reference answer and free-form metadata.
* **class `Chunk`** (line 31) — A unit of the source document that can be retrieved.
* **class `RetrievedChunk`** (line 40) — A chunk returned by a retriever for one query, with its score and 1-based rank.
* **class `Generation`** (line 50) — What a pipeline produced for one question.
    * `total_tokens(self)` (line 64) — —
* **class `MetricResult`** (line 70) — Outcome of one metric on one case. ``score`` is None unless ``status == 'ok'``.
    * `_bounded(cls, value)` (line 83) — —
* **class `CaseResult`** (line 89) — Everything recorded for one dataset case within a run.
    * `score(self, metric)` (line 109) — —
* **class `RunConfig`** (line 114) — Everything needed to reproduce a run. Contains no secrets.
    * `_unique_metrics(cls, value)` (line 146) — —
* **class `MetricSummary`** (line 152) — Aggregate of one metric across a run's cases.
* **class `RunSummary`** (line 171) — —
* **class `RunRecord`** (line 184) — —

## `src/rag_workbench/pipeline.py`

RAG pipelines and the factory that assembles one from a :class:`RunConfig`.

* **class `Pipeline`** (line 35) — —
    * `model(self)` (line 37) — —
    * `answer(self, question)` (line 39) — —
* **class `RAGPipeline`** (line 43) — —
    * `model(self)` (line 49) — —
    * `answer(self, question)` (line 52) — —
* **class `AgentRAGPipeline`** (line 61) — Tool-calling agent pipeline with the real retrieved context captured per question.
    * `__init__(self, retriever, *, k, model, api_key, base_url, timeout_s)` (line 64) — —
    * `answer(self, question)` (line 74) — —
* `build_retriever(config, chunks, settings)` (line 127) — —
* `build_pipeline(config, settings, chunks)` (line 152) — Assemble the pipeline a run config describes. Raises :class:`ConfigError` for invalid combinations.
* `_require_key(settings, what)` (line 181) — —

## `src/rag_workbench/prompts.py`

Prompts used by the OpenAI-backed pipelines.

* `format_context(passages)` (line 29) — —
* `rag_user_prompt(question, passages)` (line 33) — —

## `src/rag_workbench/providers.py`

Answer generators: turn a question plus retrieved passages into an answer.

* **class `GeneratorOutput`** (line 25) — —
* **class `Generator`** (line 31) — —
    * `generate(self, question, passages)` (line 34) — —
* **class `ExtractiveGenerator`** (line 37) — Selects up to ``max_sentences`` best-matching sentences, kept in their original order.
    * `__init__(self, idf, *, max_sentences, failure_rate, seed, min_evidence)` (line 47) — —
    * `_maybe_fail(self, question)` (line 60) — —
    * `generate(self, question, passages)` (line 68) — —
* **class `OpenAIChatGenerator`** (line 91) — Retrieve-then-generate answering with an OpenAI chat model.
    * `__init__(self, *, model, api_key, base_url, timeout_s)` (line 94) — —
    * `generate(self, question, passages)` (line 103) — —

## `src/rag_workbench/ratelimit.py`

Client-side pacing for providers with request-rate limits (free tiers, shared keys).

* **class `RateLimiter`** (line 19) — Evenly spaces :meth:`acquire` calls so that at most ``max_per_minute`` happen per minute.
    * `__init__(self, max_per_minute, *, clock, sleep)` (line 22) — —
    * `acquire(self)` (line 32) — Block until this caller's slot; return how long it waited (seconds).
* `limiter_for(max_per_minute)` (line 50) — The process-wide limiter for this setting (generation and judge metrics share it).

## `src/rag_workbench/regression.py`

A regression gate: is a candidate run measurably worse than a baseline run?

* **class `Finding`** (line 33) — —
* **class `RegressionReport`** (line 45) — —
    * `exit_code(self)` (line 54) — —
* `_error_rate(results)` (line 62) — —
* `check_regression(baseline, baseline_cases, candidate, candidate_cases, *, max_drop, min_pairs, max_error_increase, metrics)` (line 66) — —
* `format_regression(report)` (line 88) — —

## `src/rag_workbench/reporting.py`

Tabular views and exports (CSV, JSON, Markdown) of runs and comparisons.

* `metric_label(name)` (line 21) — —
* `run_metrics(run)` (line 26) — —
* `cases_dataframe(run, results)` (line 30) — One row per case with per-metric score/pass columns.
* `summary_dataframe(runs)` (line 53) — One row per run: identity, configuration essentials and metric means.
* `comparison_dataframe(run_a, results_a, run_b, results_b)` (line 72) — —
* `_csv_safe(value)` (line 85) — Neutralise spreadsheet formula injection in exported text cells.
* `export_csv(run, results)` (line 92) — —
* `portable_path(path)` (line 103) — Path relative to the project root when inside it, otherwise just the file name.
* `export_json(run, results)` (line 114) — A run bundle: re-importable with ``ragwb import`` (see :mod:`rag_workbench.archive`).
* `_fmt(value, digits)` (line 128) — —
* `_md_cell(text)` (line 136) — —
* `export_markdown(run, results, *, worst)` (line 140) — —
* `export_run(run, results, fmt)` (line 188) — —
* `safe_filename(text)` (line 198) — Filesystem-safe name: no path separators, no traversal, bounded length.
* `write_export(run, results, fmt, out_dir)` (line 204) — —

## `src/rag_workbench/retrieval.py`

Retrievers: map a query to the top-k document chunks.

* **class `Retriever`** (line 34) — —
    * `retrieve(self, query, k)` (line 37) — —
* **class `BM25Retriever`** (line 40) — Okapi BM25 with the non-negative IDF variant ``ln(1 + (N - n + 0.5) / (n + 0.5))``.
    * `__init__(self, chunks, *, k1, b)` (line 45) — —
    * `score(self, query)` (line 65) — BM25 score of every chunk for ``query`` (0.0 for chunks sharing no term with it).
    * `retrieve(self, query, k)` (line 81) — —
* **class `HybridRetriever`** (line 94) — Fuses a lexical and a dense retriever with reciprocal rank fusion (RRF).
    * `__init__(self, lexical, dense, *, rrf_k, pool_factor)` (line 104) — —
    * `retrieve(self, query, k)` (line 110) — —
* **class `EmbeddingRetriever`** (line 127) — Dense retrieval with OpenAI embeddings. Requires ``OPENAI_API_KEY``.
    * `__init__(self, chunks, *, model, api_key, base_url, timeout_s, max_retries)` (line 132) — —
    * `_ensure_index(self)` (line 146) — —
    * `retrieve(self, query, k)` (line 162) — —
* **class `LocalEmbeddingRetriever`** (line 181) — Dense retrieval with a local embedding model: cosine similarity between the query and every chunk.
    * `__init__(self, chunks, *, model, embedder_factory)` (line 190) — —
    * `_index(self)` (line 200) — —
    * `retrieve(self, query, k)` (line 208) — —

## `src/rag_workbench/runner.py`

Evaluation orchestration: dataset → pipeline → metrics → persisted run.

* **class `Progress`** (line 49) — —
* **class `PreparedRun`** (line 61) — —
* **class `EvaluationRunner`** (line 71) — —
    * `__init__(self, settings, store, *, pipeline_factory, metrics_factory, sleep)` (line 72) — —
    * `prepare(self, config)` (line 83) — —
    * `run(self, config, progress, cancel)` (line 102) — —
    * `execute(self, prepared, progress, cancel)` (line 107) — —
    * `_finish(self, run_id, status, results, prepared)` (line 148) — —
    * `_iter_results(self, prepared, cancel)` (line 152) — —
    * `evaluate_case(self, prepared, case, position)` (line 184) — Evaluate one case within ``config.case_timeout_s``; never raises.
    * `_evaluate_case_guarded(self, prepared, case, position)` (line 208) — —
    * `_evaluate_case(self, prepared, case, position)` (line 217) — —
    * `_generate_with_retries(self, pipeline, question, max_retries)` (line 234) — —
    * `_prices(self)` (line 254) — Token prices in effect for this run, stored with it so cost figures stay interpretable later.
    * `_cost(self, generation)` (line 258) — —
* `new_run_id(name)` (line 265) — —
* `environment_info()` (line 270) — —

## `src/rag_workbench/services.py`

Application wiring shared by the CLI and the Streamlit app.

* **class `AppContext`** (line 19) — —
    * `runner(self)` (line 23) — —
* `open_context(settings, *, console_logging)` (line 27) — Load settings, configure logging, open the store and mark runs left ``running`` as interrupted.
* `save_upload(settings, filename, data, *, allowed_suffixes, max_bytes)` (line 38) — Store an uploaded file under ``uploads/`` with a sanitised, content-addressed name.
* `bundled_datasets(settings)` (line 63) — The default dataset followed by the example datasets shipped in ``examples/datasets/``.
* `list_files(settings, suffixes, extra)` (line 70) — Known files of the given types: bundled defaults first, then uploads (newest first).

## `src/rag_workbench/storage.py`

SQLite persistence for runs and per-case results.

* **class `StorageError`** (line 60) — Raised when the run store cannot be read or written.
* **class `RunStore`** (line 64) — —
    * `__init__(self, path)` (line 65) — —
    * `_connect(self)` (line 86) — —
    * `create_run(self, record)` (line 101) — —
    * `add_case_result(self, run_id, result)` (line 117) — —
    * `finish_run(self, run_id, status, summary, finished_at)` (line 127) — —
    * `set_tags(self, run_id, tags)` (line 137) — —
    * `set_notes(self, run_id, notes)` (line 144) — —
    * `delete_run(self, run_id)` (line 150) — —
    * `recover_interrupted(self, stale_after_s)` (line 154) — Mark ``running`` runs with no heartbeat for ``stale_after_s`` seconds as ``interrupted``.
    * `heartbeat(self, run_id)` (line 169) — When a case of this run was last committed (or the run was created), or ``None`` if unknown.
    * `get_run(self, run_id)` (line 175) — —
    * `list_runs(self)` (line 180) — —
    * `get_case_results(self, run_id)` (line 185) — —
    * `count_case_results(self, run_id)` (line 191) — —
* `_row_to_run(row)` (line 196) — —

## `src/rag_workbench/text.py`

Text normalisation shared by BM25 retrieval, the extractive generator and lexical metrics.

* `normalize_whitespace(text)` (line 44) — Collapse all runs of whitespace (including line breaks) into single spaces.
* `tokenize(text)` (line 49) — Lower-cased word tokens after Unicode NFKC normalisation; apostrophes inside words are dropped.
* `stem(token)` (line 58) — Very light, conservative suffix stripping so plural/singular forms match.
* `content_tokens(text)` (line 76) — Stemmed tokens with stop words removed.
* `squad_normalize(text)` (line 81) — SQuAD v1.1 answer normalisation (punctuation extended to Unicode): lower-case, drop punctuation and articles.
* `split_sentences(text)` (line 90) — Split prose into sentences on terminal punctuation followed by a capital/digit.
* `is_abstention(answer)` (line 98) — True when the answer declines to answer (the pipeline's 'not enough information' reply).

## `src/rag_workbench/ui/__init__.py`

Streamlit user interface.

*(no top-level definitions; page script or package marker)*

## `src/rag_workbench/ui/auth.py`

Optional access control for the web app.

* **class `LoginThrottle`** (line 45) — Sliding-window limiter for failed logins (thread-safe, injectable clock for tests).
    * `__init__(self, max_failures, window_s, clock)` (line 48) — —
    * `_trim(self, now)` (line 56) — —
    * `retry_after(self)` (line 60) — Seconds until another attempt is allowed (0 when attempts are allowed now).
    * `record_failure(self)` (line 69) — —
    * `reset(self)` (line 75) — —
* `password_matches(supplied, expected)` (line 80) — —
* **class `ThrottleSet`** (line 84) — Per-username limiters plus one loose global limiter. Unknown usernames are tracked too, so the lockout behaves identically for names that exist and names that do not.
    * `__init__(self, max_failures, window_s, global_max, clock)` (line 88) — —
    * `_for(self, key)` (line 96) — —
    * `retry_after(self, key)` (line 102) — —
    * `record_failure(self, key)` (line 105) — —
    * `reset(self, key)` (line 109) — —
* `_throttle()` (line 114) — —
* `_throttles()` (line 119) — —
* `current_user()` (line 123) — The signed-in username, or ``None`` (no login configured, or shared-password mode).
* `_short(name)` (line 128) — —
* `require_login(settings)` (line 132) — Block the page with a login form until valid credentials are entered. No-op when no login is configured.
* `_login_with_accounts(users)` (line 151) — —
* `_login_with_shared_password(settings)` (line 182) — —
* `current_role(settings)` (line 203) — The signed-in user's role, read from the users file on every call so changes apply immediately.
* `can(settings, action)` (line 214) — Whether the current user may ``run``, ``tag`` or ``delete``.
* `visible_runs(settings, runs)` (line 219) — The runs the current user may see. Everything unless ``RAGWB_RUN_VISIBILITY=own`` with named accounts.
* `render_account(settings)` (line 231) — Sidebar: who is signed in, and a way to sign out. Nothing is shown when no login is configured.

## `src/rag_workbench/ui/components.py`

Presentation helpers shared by the pages.

* `apply_style()` (line 33) — —
* `short_path(path, root)` (line 37) — Path relative to the project root (forward slashes); absolute for files elsewhere, e.g. custom upload dirs.
* `status_badge(status)` (line 48) — —
* `fmt(value, digits, suffix)` (line 52) — —
* `family_caption(metric)` (line 60) — —
* `provenance_warnings(run)` (line 68) — —
* `score_chart(df, *, x, y, color, ci, height, y_title)` (line 77) — Bar chart on a fixed [0, 1] scale (so differences are not visually exaggerated) with optional CI bars.
* `metric_columns_config(metrics)` (line 97) — —

## `src/rag_workbench/ui/state.py`

Cached application context and small session-state helpers.

* `get_context()` (line 18) — One context per server process: settings and the SQLite run store.
* `context_or_stop()` (line 23) — —
* `select_run(run_id)` (line 32) — —
* `selected_run_id()` (line 36) — —
* `short_id(run)` (line 40) — Distinguishing part of a run id: the random suffix of generated ids, or the whole id otherwise.
* `run_label(run)` (line 45) — —

## `src/rag_workbench/ui/views/__init__.py`

*(no top-level definitions; page script or package marker)*

## `src/rag_workbench/ui/views/compare.py`

Compare runs: configuration differences, metric means with CIs, best run per metric, paired analysis.

*(no top-level definitions; page script or package marker)*

## `src/rag_workbench/ui/views/data.py`

Browse datasets and documents, and try retrieval interactively (offline BM25).

* `short(path)` (line 22) — —

## `src/rag_workbench/ui/views/new_run.py`

Configure and launch an evaluation run, with validation before anything executes.

*(no top-level definitions; page script or package marker)*

## `src/rag_workbench/ui/views/overview.py`

Overview: what exists, what happened recently, how runs compare on one metric.

*(no top-level definitions; page script or package marker)*

## `src/rag_workbench/ui/views/results.py`

Inspect one run: summary statistics, per-case table, case detail with retrieved context, exports.

*(no top-level definitions; page script or package marker)*

## `src/rag_workbench/ui/views/settings.py`

Effective configuration (no secrets), metric catalogue, environment variables and limitations.

*(no top-level definitions; page script or package marker)*

## `src/rag_workbench/ui/views/users.py`

Accounts (admin only): list users, add one, change a role, reset a password, remove an account.

* `flash(action, *args, **kwargs)` (line 26) — Run a UserStore action and show its outcome; never lets a validation error crash the page.

## `src/rag_workbench/users.py`

Named user accounts for the web app (optional).

* **class `UserError`** (line 40) — The username, password or users file is not acceptable.
* `normalise_username(name)` (line 44) — —
* `_hash(password, salt)` (line 52) — —
* **class `UserStore`** (line 56) — —
    * `__init__(self, path)` (line 57) — —
    * `_load(self)` (line 61) — —
    * `names(self)` (line 74) — —
    * `has_users(self)` (line 77) — —
    * `_save(self, users)` (line 84) — —
    * `add(self, name, password, *, replace, role)` (line 92) — —
    * `role_of(self, name)` (line 108) — The user's role, or ``None`` if there is no such user (a removed user must lose access at once).
    * `entries(self)` (line 119) — ``[{"user", "role", "created"}]`` sorted by name, without any secret material.
    * `admins(self)` (line 125) — —
    * `_guard_last_admin(self, users, username, action, force)` (line 129) — Refuse to remove or demote the only admin while other accounts remain: nobody could manage accounts then.
    * `set_password(self, name, new_password, *, current_password)` (line 139) — Change a user's password, keeping role and creation date. ``current_password`` (when given) must be right.
    * `set_role(self, name, role, *, force)` (line 155) — —
    * `remove(self, name, *, force)` (line 168) — —
    * `verify(self, name, password)` (line 182) — The normalised username if the credentials are right, else ``None``. Same cost either way.

## `start.py`

Start RAG Evaluation Workbench — one command does everything:

* `say(message)` (line 38) — —
* `run(cmd, **kwargs)` (line 42) — —
* `prepare_environment()` (line 47) — —
* `store_is_empty()` (line 66) — —
* `create_examples()` (line 75) — —
* `password_configured(env, env_file)` (line 84) — True if RAGWB_APP_PASSWORD is set (in the environment or in .env) to a non-blank value.
* `accounts_configured(env)` (line 100) — True if named user accounts exist (``<data dir>/users.json`` lists at least one user, or cannot be parsed).
* `host_problem(host, password_set)` (line 114) — Why this host must not be used, or None. Exposing the app needs a login: the shared password or accounts.
* `tls_problem(cert, key)` (line 122) — Why the TLS options are unusable, or None.
* `free_port(preferred)` (line 134) — —
* `wait_until_ready(port, process, timeout, host, https)` (line 142) — —
* `launch(port, open_browser, host, ssl_cert, ssl_key)` (line 159) — —
* `main()` (line 194) — —

## `streamlit_app.py`

RAG Evaluation Workbench — Streamlit entry point:  uv run streamlit run streamlit_app.py

*(no top-level definitions; page script or package marker)*

## `scripts/benchmark.py`

Scale benchmark for the offline path: how long do runs, reads and exports take as the dataset grows?

* `make_dataset(path, size, document)` (line 32) — —
* `one_run(size, workers, *, measure_memory)` (line 43) — —
* `bench(size, workers)` (line 75) — Timings from a run with no tracer; peak memory from a second run under ``tracemalloc`` (which slows Python code several-fold, so its timings are discarded).
* `main(argv)` (line 83) — —

## `scripts/benchmark_documents.py`

Scale benchmark for large source documents: loading, chunking, BM25 indexing and query latency.

* `vocabulary()` (line 33) — —
* `write_text(path, paragraphs, vocab, rng)` (line 38) — —
* `write_pdf(path, pages, vocab, rng)` (line 46) — —
* `bench(path, vocab, rng)` (line 58) — —
* `main(argv)` (line 83) — —

## `scripts/live_smoke.py`

Live smoke test of the OpenAI and DeepEval paths. THIS MAKES PAID API CALLS.

* `main(argv)` (line 30) — —

## `scripts/make_example_pdf.py`

Render the example Markdown document to PDF (so the PDF extraction path has a bundled example).

* `main()` (line 22) — —

## `scripts/seed_demo_runs.py`

Create the five offline example runs used in the documentation (no network, no API key).

* `main()` (line 20) — —

## `scripts/set_api_key.py`

Replace (or remove) the provider API key in the project's ``.env`` without the key ever appearing on screen or in a log.

* `validate_key(key)` (line 37) — The stripped key, or raises ``ValueError`` with a message that does not contain the key.
* `update_env_text(text, key)` (line 47) — ``text`` with the ``OPENAI_API_KEY`` line set to ``key`` (added if there is none); all other lines untouched.
* `write_env(path, key, example)` (line 63) — —
* `read_setting(path, name)` (line 78) — —
* `check_key(path)` (line 88) — One authenticated request to ``<base url>/models``; returns ``(status, message)`` and never the key.
* `main(argv, env_file)` (line 104) — —

## `scripts/verify.py`

Local verification sequence for RAG Evaluation Workbench.

* `step(name, ok, detail)` (line 44) — —
* `run(cmd, env, cwd)` (line 49) — —
* `check_environment()` (line 54) — —
* `check_lockfile()` (line 67) — —
* `check_secrets()` (line 76) — —
* `check_static()` (line 97) — —
* `check_audit()` (line 111) — —
* `check_wheel()` (line 129) — —
* `check_tests(quick)` (line 137) — —
* `check_end_to_end()` (line 152) — —
* `main()` (line 197) — —

## `scripts/wheel_check.py`

Clean-install check: build the wheel, install it into a throwaway virtual environment, and use it from a neutral folder.

* `check(name, ok, detail)` (line 26) — —
* `run(cmd, cwd, env)` (line 31) — —
* `main()` (line 36) — —
