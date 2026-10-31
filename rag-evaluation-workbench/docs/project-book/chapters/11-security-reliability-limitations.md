# Part XI — Security, reliability, and limitations

This part describes what the RAG Evaluation Workbench protects against, what it does not, and where its guarantees
end. Every statement about behaviour is taken from the code at the cited `file:line` or from a command run while
this part was written (2026-10-24). Where something was established by reading code but not exercised, the text
says so.

## 110. Scope and threat model

### 110.1 What kind of system this is

The workbench is a **local tool for one person or a small trusted team**. One person runs it on their own machine, as a Streamlit app started
by `start.py` or by hand, or as the command-line program `ragwb` (`src/rag_workbench/cli.py`). There is no separate
backend, no HTTP API of its own, no required login (named accounts and a shared password are optional, Part XIV §156) and no remote storage: the Streamlit pages import the
`rag_workbench` package directly (`streamlit_app.py:1-4`), and everything the program keeps is written below one data
directory (`Settings.data_dir`, `src/rag_workbench/config.py:60`, overridable with `RAGWB_DATA_DIR`).

The threat model is sized to that. The assets worth protecting are:

| Asset | Where it lives | Why it matters |
|---|---|---|
| The OpenAI API key | process environment or `.env` in the project root (`config.py:172-174`) | spending money; account abuse if leaked |
| Evaluation inputs (datasets, documents) | `examples/`, `data/uploads/`, or any path given to the CLI | may be confidential to the user |
| Run history | `data/runs.db` (SQLite) | reproducibility record; may contain answers derived from confidential documents |
| Exports and bundles | `data/exports/` or `--out-dir`; browser downloads | leave the tool; may be shared |
| The user's spreadsheet application | opens exported CSV files | formula-injection target |

### 110.2 Adversaries and entry points considered

1. **Untrusted input files.** A dataset, a source document or a run bundle may come from someone else. All three
   are treated as data: parsed and validated, never executed (§112).
2. **Accidental secret disclosure.** The most realistic leak is the user's own key ending up in a log, a stored run
   configuration, an export, a screenshot or a shared repository (§111).
3. **Spreadsheet formula injection** through exported CSV cells whose text came from a dataset, a document or a model
   answer (§113.1).
4. **Unintended network traffic**: telemetry from third-party libraries and paid API calls the user did not intend
   (§114).

### 110.3 Out of scope

The following are explicitly *not* defended against, and the tool should not be deployed in a way that makes them
relevant:

* **Other users of the same machine.** By default there is no authentication. The app listens on localhost only
  (§114.4), which keeps other hosts out but not other users or processes on the same machine; if that binding is
  bypassed and no password is set, anyone who can reach the port can read every stored run, start runs (which, with a
  key configured, spend the owner's OpenAI credit) and delete runs. Release 1.1 adds an *optional* shared password
  (`RAGWB_APP_PASSWORD`) with a constant-time comparison and a lockout, and the launcher refuses a non-local `--host`
  without it (Part XIII §144). Release 1.2 adds optional **named accounts** (scrypt-hashed passwords in `users.json`,
  per-username and global lockout, sign-ins logged by username, `started_by` on runs) and HTTPS through
  `start.py --ssl-cert/--ssl-key` (Part XIV §156). Neither is an identity platform: there is no e-mail password reset and, by default, no separation of one user's runs from another's, and the HTTPS path was
  checked only with a self-signed certificate. (Release 1.3 added three coarse roles and ends a removed user's session on its next page load, Part XV §165. Release 1.4 added an admin Accounts page, password change, a last-admin guard and `RAGWB_RUN_VISIBILITY=own`, which hides other users' runs in the web pages only; the command line and anyone with file access to `data/` are not filtered, Part XVI §173. `docs/SECURITY.md` summarises the controls and gaps.) One defect is known: after the *last* account is removed the launcher still
  believes accounts exist (Part XIV §156.7).
* **A malicious local user or process** with access to the project directory: it can read `.env`, the SQLite file and
  the logs directly.
* **Hostile model output beyond text.** Model answers are stored and displayed as text; nothing in the code executes
  or follows them. Prompt injection inside a source document can change what the *model* answers in an OpenAI run,
  which affects scores, not the integrity of the tool. This was not tested (no prompt-injection document was run, live or offline).
* **Supply-chain compromise** of PyPI packages (§115).

## 111. Secret management

The only secret the application handles is `OPENAI_API_KEY`. Its handling has five layers.

### 111.1 Held as a `SecretStr`

`Settings.openai_api_key` is a `pydantic.SecretStr | None` (`config.py:64`); the secret `app_password` is held the same way (`config.py:66`). Pydantic renders a `SecretStr` as
`'**********'` in `repr` and `str`, so printing or logging a `Settings` object does not reveal the value; the code
calls `get_secret_value()` only where a client is constructed (`pipeline.py:139`, `pipeline.py:165`,
`metrics/__init__.py:46`) and where the log redactor is configured (`Settings.secret_values`, `config.py:152-155`, used at `logging_setup.py:85`). Blank values are treated
as unset (`config.py:218-219`), and `has_openai_key` requires a non-blank value after stripping (`config.py:144-146`).
`test_secret_never_exposed` (`tests/test_config.py:48-55`) checks that the key appears neither in `repr(settings)` nor
in `public_dict()`.

### 111.2 Never persisted

* `Settings.public_dict()` (`config.py:163-169`) excludes `openai_api_key` and `app_password` and substitutes the booleans
  `openai_api_key_configured`, `app_password_configured` and `user_accounts_configured`. It is what the Settings page displays (`ui/views/settings.py:32-33`).
* What is persisted per run is a `RunConfig` (`models.py:114-147`), whose docstring states "Contains no secrets" and
  whose fields indeed contain none: model names, paths, `k`, metric names, thresholds, worker and retry counts, seed.
  The runner stores `config.model_dump(mode="json")` plus thresholds and the generator model (`runner.py:111-116`).
  The key is passed to client constructors as an argument and never placed in the config.

### 111.3 Redacted in logs

Two cooperating pieces in `logging_setup.py` do this. `RedactSecretsFilter` (`logging_setup.py:51-66`) replaces the
configured key (when at least 8 characters long) with `***` and anything matching `sk-[A-Za-z0-9_\-]{8,}` with
`sk-***` (`logging_setup.py:18`, `56-59`) in the record's message, after `%s` arguments have been interpolated.
`RedactingFormatter` (`logging_setup.py:22-30`) applies the same redaction to the *fully formatted* record, which also
covers exception tracebacks and stack information — text the message filter alone would miss, and which the runner's
`log.exception` calls do produce. Every handler the application creates gets both, and the JSON log format (`RAGWB_LOG_FORMAT=json`) is redacted the same way, on the serialised line (`logging_setup.py:33-48`, `:85-90`, `:99-101`).
`test_secret_redaction_filter` checks the message path and `test_redacting_formatter_covers_tracebacks` raises an
exception whose text contains the secret and checks that the formatted record shows `***` instead. The module
docstring calls this "a second line of defence": the code itself never logs credentials. Two boundaries:

* It is attached only to the `rag_workbench` logger, which does not propagate (`logging_setup.py:103`). Log output of
  third-party libraries (Streamlit, LangChain, OpenAI SDK, DeepEval) does not pass through it.
* Error *messages* produced from OpenAI exceptions avoid the key by construction: `classify_openai_error`
  (`errors.py:37-54`) uses a fixed message for `AuthenticationError` and otherwise the exception text truncated to
  300 characters; `test_classify_openai_errors` (`tests/test_providers_pipeline.py:50-58`) checks that a key-like
  string in an authentication error does not survive.

### 111.4 Kept out of version control

`.gitignore` lists `.env` first (`.gitignore:1-2`) and also ignores `data/` (`.gitignore:4-5`), so neither the key file
nor the run store, uploads, exports and logs are committed; it also ignores DeepEval's cache folder `.deepeval/`
(`.gitignore:14-15`). `.env.example` (`.env.example:5`) contains `OPENAI_API_KEY=` with an empty value and comments for
every optional variable. `.gitignore` takes effect only once the project is put under Git.

### 111.5 The secret scan in `scripts/verify.py`

`check_secrets` (`scripts/verify.py:75-87`) walks the project tree, skipping `.venv`, `__pycache__`, `.pytest_cache`,
`data`, `build` and `.git` (`verify.py:37`). It fails if any `.env` file is present, or if any file under 5 MB contains a
match of `KEY_PATTERN` = `sk-(?:[A-Za-z0-9]+-)?[A-Za-z0-9_\-]{20,}` that does not contain the marker `not-a-real`
(`verify.py:38-39`, `84`). The optional `word-` group covers prefixed key formats such as `sk-proj-…` and
`sk-svcacct-…`, which a plain `sk-` + 20 alphanumerics pattern would miss (checked directly: the plain pattern does
not match `sk-proj-` + 40 characters, the current one does; Part IX, §99.1). The marker lets the test suite keep a
deliberately fake key (`sk-not-a-real-key-for-tests-123456`, `tests/test_config.py:49`) without failing the scan. On
2026-10-24 it reported `[PASS] secrets - no key-shaped strings found`.

Boundaries: the scan is a pattern heuristic — a key in an unusual format, split across lines or encoded would pass —
and any match containing `not-a-real` is exempt by design. A developer who keeps a real `.env` in the project will
always see this step fail; that is intended as a reminder before sharing the tree, not a statement that the key leaked.

## 112. Input validation and file-handling safeguards

### 112.1 Datasets

Dataset parsing (`src/rag_workbench/datasets.py`) never silently drops a row; every problem is an error or a warning
with a line number (`datasets.py:11-12`):

| Check | Code | Outcome |
|---|---|---|
| Suffix is `.jsonl` or `.csv` | `datasets.py:72-75` | error |
| File size ≤ `max_dataset_bytes` (default 5,000,000) — checked on the file size before reading, and again on the bytes | `datasets.py:130-134`, `76-78` | error |
| UTF-8 (BOM accepted) | `datasets.py:79-83` | error naming the byte offset |
| JSONL line is valid JSON and an object | `datasets.py:138-152` | error per line |
| CSV header has a `question` column | `datasets.py:155-159` | error |
| Case count ≤ `max_cases` (default 5,000) | `datasets.py:89-92` | error, parsing stops |
| `question` present, non-empty string; `expected_answer` string or absent | `datasets.py:173-182` | error |
| Field length ≤ `max_field_chars` (default 20,000) | `datasets.py:183-187` | error |
| `id` string or integer, unique | `datasets.py:188-195`, `96-98` | error |
| `metadata` is an object | `datasets.py:196-199` | error |
| Duplicate question text, unknown fields, missing reference answers | `datasets.py:100-102`, `198-200`, `108-111` | warning |

A dataset with any error cannot be run: `load_dataset` raises `DatasetError` (`datasets.py:116-121`); the runner calls it
during *preparation*, before a run row exists (`runner.py:83-99`; `test_validation_happens_before_a_run_is_created`,
`tests/test_runner.py:135-145`); and the New evaluation page disables the Run button (`ui/views/new_run.py:177-194`).
The limits are configurable through `RAGWB_MAX_DATASET_BYTES`, `RAGWB_MAX_CASES` and `RAGWB_MAX_FIELD_CHARS`
(`config.py:152-155`), validated as positive integers (`config.py:87-90`).

### 112.2 Documents

`documents.load_chunks` (`documents.py:38-65`) accepts `.pdf`, `.txt` and `.md` (`documents.py:22`), rejects files larger
than `max_document_bytes` (default 25,000,000; `documents.py:47-49`), requires UTF-8 for text files (`documents.py:108-114`)
and raises `DocumentError` if no text could be extracted (`documents.py:62-63`). PDFs are opened with PyMuPDF; any
exception from opening becomes a `DocumentError` (`documents.py:90-93`). Extraction uses `page.get_text("blocks")` only
(`documents.py:99`) — no rendering, no JavaScript, no embedded files. Chunks are capped at 2,000 characters by sentence
splitting (`documents.py:23`, `94-110`).

The size limit bounds the *file*, not the work PyMuPDF does on it: a small but pathological PDF could still be slow to
parse, and no timeout wraps PDF parsing. This was not tested.

### 112.3 Run bundles

`archive.load_bundle` (`archive.py:34-56`) is the only way external run data enters the store. It:

1. requires the file to exist and be at most `MAX_BUNDLE_BYTES` = 50,000,000 bytes (`archive.py:27`, `36-39`);
2. parses it with `json.loads` — "Importing never executes anything" (`archive.py:3-5`);
3. requires `"format": "rag-workbench-run"` and `"version": 1` (`archive.py:44-47`);
4. validates the run and every case against the pydantic models `RunRecord` and `CaseResult` (`archive.py:48-52`),
   which among other things bounds every metric score to [0, 1] (`models.py:81-86`);
5. rejects duplicate case ids (`archive.py:53-55`).

`import_bundle` (`archive.py:59-81`) then skips an id that already exists rather than overwriting it (`archive.py:62-64`),
**recomputes the summary** from the imported cases, metric names and thresholds instead of trusting the summary in the
file (`archive.py:67-72`), and imports all-or-nothing: if writing a case fails, the half-imported run is deleted
(`archive.py:74-79`). Tests: `test_export_import_round_trip`, `test_invalid_bundles_are_rejected`,
`test_duplicate_case_ids_rejected` and `test_bundle_summary_is_recomputed_not_trusted`, which tampers with a bundle's
token-F1 mean and checks that the imported run shows the recomputed value (`tests/test_archive_reporting.py:44-90`).

What validation does **not** establish:

* **Scores are only as honest as the file.** Validation checks types and ranges, not provenance: a bundle can carry any
  per-case scores within [0, 1]. Only the summary is guaranteed to agree with the cases.
* **Free-form fields are not constrained.** `RunRecord.config` is `dict[str, Any]` (`models.py:190`) and `RunRecord.id`
  is any string (`models.py:185`). Their values reach the UI; §113.2 explains where that matters.

### 112.4 Uploads from the browser

The New evaluation page accepts a dataset and a document upload (`ui/views/new_run.py:37-48`, `70-79`). Streamlit caps
uploads at 25 MB (`.streamlit/config.toml:14`), and both widgets restrict the offered file types. Files are then stored
by `services.save_upload` (`services.py:38-60`), which is the security boundary because a browser-supplied file name is
attacker-controllable:

* the suffix must be in the allowed set (`services.py:46-48`);
* the size must be within the per-type limit — 5 MB for datasets, 25 MB for documents (`services.py:49-50`);
* the stored name is `<first 12 hex chars of SHA-256 of the content>-<sanitised stem><suffix>` (`services.py:51-55`).
  The stem is passed through `reporting.safe_filename` (`reporting.py:198-201`), which replaces every run of characters
  outside `[A-Za-z0-9._-]` with `_`, strips leading and trailing dots and underscores, and caps the length;
  `save_upload` further caps the stem at 60 characters;
* as defence in depth, the resolved target must sit directly in the uploads directory (`services.py:56-57`);
* an existing file with the same name is not rewritten (`services.py:58-59`).

`test_save_upload_sanitises_names` (`tests/test_cli_services.py:64-76`) uploads `../../evil name.jsonl` and checks that
it lands in `uploads/` as `<hash>-evil_name.jsonl`, that identical content yields the same hash prefix, and that a
wrong suffix and an oversized file are refused.

Because names are content-addressed, two different files would collide only if their SHA-256 digests agreed in the
first 48 bits *and* their sanitised stems were equal; the second upload would then resolve to the first file. This is
a theoretical limit of the naming scheme, not an observed problem.

### 112.5 Paths chosen by the user

The browser UI only lets the user pick datasets and documents from a list built by `services.list_files` (bundled
defaults plus files in `uploads/`, `services.py:63-82`), so a browser user cannot point the app at an arbitrary file
path. The CLI, by contrast, accepts any path for `--dataset`, `--document` and `--out-dir` (`cli.py:523-524`, `235`):
the CLI user is the machine's user. Export file names are derived from the run id through `safe_filename`
(`reporting.py:204-208`), so a hostile run id from an imported bundle cannot write outside the chosen directory
(`test_write_export_and_safe_filenames`, `tests/test_archive_reporting.py:143-149`, checks `../../etc/passwd` →
`etc_passwd`). Generated run ids are themselves slugs (`runner.py:265-267`; `test_run_ids_are_safe_and_unique`,
`tests/test_runner.py:159-162`).

### 112.6 SQL

Every statement in `storage.py` that carries data uses `?` placeholders (`storage.py:99-107`, `114-117`, `124-127`,
`133`, `144-147`, `152`, `162-163`, `168`). The single f-string SQL statement interpolates the module constant
`SCHEMA_VERSION` (`storage.py:81`), not user input.

## 113. Exports and rendering of untrusted text

### 113.1 CSV formula injection

A CSV cell that begins with `=`, `+`, `-`, `@`, a tab or a carriage return can be interpreted as a formula by spreadsheet
applications. Dataset questions, reference answers, model answers and error messages all end up in CSV cells, so
`reporting.export_csv` prefixes such values with an apostrophe (`reporting.py:18`, `83-87`, `90-98`).

The guard is applied to every column that is "not numeric and not bool" (`reporting.py:94-97`, with a comment). The
reason is a pandas detail: pandas 3 stores text in a dedicated `str` dtype, so a guard restricted to `dtype == object`
columns would skip every column while looking correct. `test_csv_export_neutralises_formulas`
(`tests/test_archive_reporting.py:119-123`) exports a question `=HYPERLINK("http://evil")` and an answer
`+1 cmd|' /C calc'!A0`, parses the output file, and asserts that both start with `'`.

Limits: the mitigation covers the CSV export only. The Markdown report escapes `|` and newlines in table cells
(`reporting.py:136-137`) but is not otherwise sanitised, and the JSON bundle carries values verbatim — both are data
formats, not spreadsheets. The apostrophe prefix changes the cell's text, the usual trade-off of this defence.

### 113.2 Rendering in the Streamlit UI

Streamlit renders `st.markdown` and `st.write(str)` as Markdown; raw HTML in them is not rendered unless
`unsafe_allow_html=True` is passed. There are two such uses:

1. `ui/components.py:33-34` — `apply_style()` injects the constant `CSS` string (`components.py:20-26`). No external
   data is involved.
2. `ui/views/results.py:45-49` — the header line of the Run results page, an HTML `<span>` listing provider, pipeline,
   retriever, `k`, generator model, judge model and run id.

The second use matters because `generator_model` and `judge_model` are free text typed on the New evaluation page
(`new_run.py:120`, `132`) or passed with `--model` / `--judge-model`, and for **imported bundles every one of these
values, and the run id, comes from the JSON file** (§112.3). Every value is therefore passed through `html.escape`
before it enters the markup (`results.py:3`, comment at `results.py:45`). The UI journey
`test_imported_config_values_are_html_escaped` imports a bundle whose `generator_model` is
`<img src=x onerror=alert(1)>` and asserts that the rendered header contains the escaped text and no `<img` tag.

Elsewhere, untrusted text is rendered as follows:

| Text | Rendering | Effect |
|---|---|---|
| Retrieved chunk text (document content) | `st.text` (`results.py:169`, `data.py:87`) | shown literally; the comment at `results.py:169` states the intent |
| Question, reference answer, pipeline answer in Case detail | `st.write` (`results.py:147-154`) | rendered as Markdown (no raw HTML) |
| Run name | `st.markdown` (`results.py:45`, `compare.py:52`) | Markdown |
| Provenance warnings of imported runs | `st.markdown` (`components.py:68-74`) | Markdown |
| Dataset warnings | `st.markdown` (`new_run.py:65-66`) | Markdown |
| Error messages, metric reasons, tables | `st.error`, `st.dataframe` | text / table cells |
| Run configuration and environment | `st.json` (`results.py:173-177`) | JSON viewer |

Markdown rendering of questions and answers means that Markdown syntax in a dataset or a model answer — headings,
emphasis, links, image syntax — is interpreted rather than shown literally. Whether a Markdown image pointing at a remote
URL makes the viewer's browser fetch it was not tested; if it does, a dataset or bundle could trigger a request to a
third-party host when a case is opened. Chunk text, the largest body of untrusted text, is not affected because it uses
`st.text`.

### 113.3 Destructive actions

Deleting a run from the UI requires typing the run id (`results.py:208-220`); the CLI requires `--yes` (`cli.py:148-165`;
observed: `Refusing to delete without --yes`, exit 1). Deletion cascades to case results through a foreign key with
`ON DELETE CASCADE` and `PRAGMA foreign_keys = ON` (`storage.py:49`, `84`). There is no undo.

## 114. Network boundaries

### 114.1 Offline by default

The default provider is `offline`, the default retriever `bm25`, and without `--metrics` an offline run uses the four
lexical metrics (`cli.py:489-491`, `metrics/__init__.py:12`). The example runs that `start.py` creates on the first launch
are offline too (`src/rag_workbench/demo.py:1-4`). Importing the package does not contact a network service
(`src/rag_workbench/__init__.py:1-5`): OpenAI and LangChain clients are imported inside the functions that construct them
(`providers.py:95`, `pipeline.py:66`, `retrieval.py:149-150`, `metrics/judge.py:83`), and the embedding index is built
lazily on the first query (`retrieval.py:146-160`; `test_embedding_retriever_is_lazy_and_maps_ids`,
`tests/test_retrieval.py:50-67`). The test suite runs with a blank key (`tests/conftest.py:24`), so a passing suite is
evidence that the offline paths need no network.

`start.py` itself contacts the network only through `uv sync` (or `pip install`) while preparing the environment. With
`--frozen` and an already synchronised environment, uv reported `Checked 115 packages in 20ms` and downloaded nothing.

### 114.2 Code paths that call OpenAI

Exactly four constructions send data to OpenAI (or to `OPENAI_BASE_URL` if set), and all of them first require a key
(`pipeline._require_key`, `pipeline.py:175-178`; `metrics.validate_metric_names`, `metrics/__init__.py:25-31`):

| Path | Code | Data sent |
|---|---|---|
| OpenAI generator (`--provider openai --pipeline rag`) | `providers.OpenAIChatGenerator.generate`, `providers.py:103-104` | system prompt, question, top-k chunk texts |
| Agent pipeline (`--pipeline agent`) | `pipeline.AgentRAGPipeline.answer`, `pipeline.py:74-121` | question, tool calls, retrieved chunk texts |
| Embedding retriever (`--retriever embedding`) | `retrieval.EmbeddingRetriever._ensure_index` / `retrieve`, `retrieval.py:146-178` | **every chunk of the document** (indexing) and every query |
| Judge metrics (`answer_relevancy`, `faithfulness`, `context_relevancy`, `correctness`) | `metrics/judge.py:109-115`, via DeepEval's `OpenAIModel` | question, answer, reference answer, retrieved contexts |

The UI states that a run calls the OpenAI API and may incur cost before it starts (`new_run.py:191-194`). The privacy
consequence: with any of these options, the content of the user's dataset and document leaves the machine.

### 114.3 Telemetry

DeepEval sends anonymous telemetry unless `DEEPEVAL_TELEMETRY_OPT_OUT` is set (its own docstring,
`.venv/Lib/site-packages/deepeval/telemetry/__init__.py:8`). The workbench sets it with `os.environ.setdefault` before
DeepEval can be imported, in the package `__init__` (`src/rag_workbench/__init__.py:9-11`) and in the Streamlit entry point
(`streamlit_app.py:10`); `start.py` sets it explicitly in the environment of the Streamlit process (`start.py:158`). The
test suite sets it unconditionally (`tests/conftest.py:11`), and `scripts/verify.py` sets it for its subprocesses
(`verify.py:139`).

Because `setdefault` is used, a value already present in the *process environment* wins; the comment at
`__init__.py:10` documents that a user may opt in with `0`. A value in `.env` cannot re-enable telemetry: the package sets
the variable on import, before `load_settings` calls `load_dotenv(..., override=False)` (`config.py:212`). Under
`start.py` the variable is forced to `1` for the app.

Streamlit's own usage statistics are disabled twice: by `gatherUsageStats = false` in `.streamlit/config.toml:3-5`, and
by `--browser.gatherUsageStats false` on the command line that `start.py` builds (`start.py:159-160`).

DeepEval creates an empty `.deepeval/` folder in the working directory when imported (its `HIDDEN_DIR`,
`.venv/Lib/site-packages/deepeval/constants.py:6`); it is ignored by Git (§111.4).

### 114.4 The Streamlit listening address

`.streamlit/config.toml` sets `address = "localhost"` in its `[server]` section, with the comment "Local tool without
authentication: listen on this machine only." (`.streamlit/config.toml:16-17`), and `start.py` passes
`--server.address` explicitly, `localhost` unless `--host` is given (`start.py:158-159`). Since release 1.1 the launcher
refuses any other host unless `RAGWB_APP_PASSWORD` is set, and since 1.2 unless user accounts exist (`start.py:112-117`, `:198-201`), and `ragwb doctor` reports the
configured address and whether a password protects it (`maintenance.py:148-164`). Without an explicit address, the installed Streamlit
(1.66.1) binds the IPv6 dual-stack wildcard `"::"` — all interfaces
(`.venv/Lib/site-packages/streamlit/web/server/starlette/starlette_server.py:89-103`). Boundaries: a manually started
server reads the setting from the directory Streamlit is started in, so starting it elsewhere, or passing another
`--server.address`, gives whatever binding that implies; and the behaviour was established by reading Streamlit's code
and the configuration, not by a connection attempt from another host.

## 115. Dependency risks

The direct runtime dependencies are declared in `pyproject.toml:7-18`:

| Package | Constraint | Purpose (comment in `pyproject.toml`) |
|---|---|---|
| `deepeval` | `>=4.2.6` | LLM-as-a-judge metrics |
| `langchain` | `>=1.4.2` | tool-calling agent pipeline |
| `langchain-openai` | `>=1.6.6` | OpenAI chat model and embeddings |
| `pandas` | `>=3.0.6` | tabular views and CSV export |
| `pydantic` | `>=2.13` | data contracts and settings validation |
| `pymupdf` | `>=1.28.2,<2` | PDF text extraction; the upper bound avoids PyMuPDF 2.0, which loads onnxruntime and layout models at import |
| `python-dotenv` | `>=1.0` | optional `.env` loading |
| `streamlit` | `>=1.64.0` | user interface |

Development groups add `pytest` and `pytest-cov` (`dev`) and `markdown` (`docs`). Exact versions are pinned by `uv.lock`;
`uv lock --check --offline` inside `verify.py --quick` reported `Resolved 117 packages` on 2026-10-24 for release 1.0 and `Resolved 141 packages` for release 1.1 (the dev group gained ruff, mypy and pip-audit); `uv.lock` has 152 `[[package]]` entries in release 1.3 (the optional `semantic` extra, `fastembed`, and its dependencies). Installed versions
included deepeval 4.3.1, langchain 1.4.7, langchain-openai 1.7.2, openai 3.37.0, pandas 3.1.0, pydantic 2.14.1,
pymupdf 1.28.2, python-dotenv 1.2.4 and streamlit 1.66.1.

Risks worth naming:

* **Vulnerability scan: a point-in-time result.** `pip-audit` over the locked runtime requirements reported no known
  vulnerabilities at the time of the scan (`scripts/verify.py --audit`; `docs/KNOWN_LIMITATIONS.md` and Part XIII §145.4).
  The result is only as current as the advisory database at that moment, covers known issues in the locked runtime
  packages only, and must be repeated before each release; it says nothing about the unlocked pip fallback.
* **Large transitive surface.** DeepEval and LangChain pull in many packages (HTTP clients, tokenisers, telemetry
  clients). Most of that code is imported only on the OpenAI paths, but it is installed in every environment.
* **The pip fallback is not locked.** When `start.py` finds no uv, it installs with pip from the version ranges in
  `pyproject.toml` (`start.py:60`), so the resolved versions can differ from `uv.lock` and from what was tested.
* **Licensing.** PyMuPDF is distributed under the AGPL or a commercial licence. That is a distribution concern rather
  than a runtime risk, but anyone redistributing the tool should check it.
* **Lower-bound-only constraints.** Apart from PyMuPDF, constraints have no upper bound; a fresh `uv lock` can move to
  new major versions. The lock file is the reproducibility mechanism; regenerate it deliberately.
* **Version drift in provenance.** Each run records the installed versions of seven key packages (`runner.py:45`,
  `239-247`), so a later reader can see which library versions produced a run.

## 116. Failure modes, resource limits and reliability guarantees

### 116.1 What happens when things fail

| Failure | Behaviour | Code / test |
|---|---|---|
| Invalid configuration value | `ConfigError` naming the variable, e.g. `error: Invalid configuration: RAGWB_MAX_WORKERS: Input should be less than or equal to 32`; the UI shows "Configuration problem" and stops; `start.py` stops at its store probe with the error | `config.py:226-232`, `ui/state.py:23-29`, `start.py:70-71`; `test_invalid_values_raise_config_error_naming_the_variable` |
| Invalid dataset, document, metric, threshold, missing key | refused during preparation; no run row created | `runner.py:83-99`; `test_validation_happens_before_a_run_is_created` |
| Transient provider error (rate limit, timeout, connection, 5xx) | retried up to `max_retries` with exponential back-off plus jitter; then the case is an error with "gave up after N attempts"; embedding-API errors are mapped the same way | `errors.py:47-49`, `runner.py:234-252`, `retrieval.py:165-172`; `test_transient_errors_are_retried_with_backoff`, `test_retries_give_up`, `test_embedding_errors_are_classified_for_retry` |
| Permanent provider error (bad key, bad request, empty answer) | case recorded as error, run continues | `errors.py:50-53`, `providers.py:116-117`, `runner.py:248-249` |
| Unexpected exception in a pipeline or case | case recorded as error with the exception type, run continues | `runner.py:184-215`, `223-225`; `test_unexpected_exceptions_do_not_abort_the_run` |
| A metric raises, or returns a score outside [0, 1] by more than 1e-9 | that metric is `error` for that case; other metrics and cases continue; errors excluded from means | `metrics/base.py:84-95`; `test_custom_threshold_and_errors_are_captured`, `test_out_of_range_scores_are_errors_but_float_noise_is_absorbed` |
| User stops the run (Streamlit Stop, Ctrl+C, exception in the progress callback) | finished cases kept; run marked `cancelled` with a summary of what finished | `runner.py:130-137`; `test_cancellation_event_stops_and_records_progress`, `test_exception_in_progress_callback_marks_run_cancelled` |
| Process dies mid-run | run left `running`; once no case has been committed for 15 minutes, it is marked `interrupted` the next time any front end opens the store | `services.py:31-34`, `storage.py:27-29`, `135-147`; `test_recover_interrupted_only_touches_stale_runs` |
| Database created by a newer schema | refused with `StorageError` | `storage.py:72-73`; `test_newer_schema_is_refused` |
| Database at schema version 1 or 2 | migrated in place to version 3 (adds `heartbeat_at` and `tags_json` if missing) | `storage.py:74-79`; `test_schema_v1_store_is_migrated` |
| Any other SQLite error | translated to `StorageError` ("Run store error (...)"), reported by the CLI as `error: ...` | `storage.py:85-98`; `test_sqlite_errors_become_storage_errors` |
| Log directory not writable | file logging disabled with a warning; the app continues | `logging_setup.py:92-96` |
| Example runs fail on first launch | `start.py` reports it and starts the app without them | `start.py:80-81` |
| Streamlit exits during start-up | `start.py` exits with the process's code | `start.py:176-177` |

Run statuses are derived mechanically: `completed` with no case errors, `partial` with some, `failed` when every case
errored, `cancelled` when stopped (`runner.py:138-141`). The CLI maps `completed` to exit code 0 and anything else to 2
(`cli.py:79`); errors before a run exists give exit code 1 (`cli.py:639-643`).

### 116.2 Resource limits

| Resource | Limit | Where |
|---|---|---|
| Dataset file | 5,000,000 bytes (configurable) | `config.py:87` |
| Cases per dataset | 5,000 (configurable) | `config.py:89` |
| Question / reference length | 20,000 characters (configurable) | `config.py:90` |
| Document file | 25,000,000 bytes (configurable) | `config.py:88` |
| Browser upload | 25 MB | `.streamlit/config.toml:14` |
| Run bundle | 50,000,000 bytes | `archive.py:27` |
| Chunk size | 2,000 characters | `documents.py:23` |
| `k` | 1–50 (`RunConfig`); UI slider up to 10 | `models.py:125`, `new_run.py:116-117` |
| Parallel cases | 1–32 | `config.py:80`, `models.py:131` |
| Retries | 0–10 | `config.py:76` |
| HTTP request timeout | (0, 600] s, default 60 | `config.py:74` |
| Case time limit | (0, 3,600] s, default 600 | `config.py:75`, `runner.py:191-205` |
| Login attempts | shared password: 5 failures per 60 s, process-wide; accounts: 5 per 60 s per username plus 30 per 60 s across all usernames | `ui/auth.py:31-32`, `:41` |
| Log file | 2,000,000 bytes × (1 + 3 backups) | `logging_setup.py:94` |
| In-flight futures | `2 × workers` | `runner.py:162-178` |
| SQLite lock wait | 15 s | `storage.py:87` |
| Stale-run threshold | 15 minutes without a committed case | `storage.py:27-29` |
| `start.py` health wait | 90 s | `start.py:140` |

There is no limit on the number of stored runs, the size of `runs.db`, or the number of uploaded files (`ragwb prune` removes
old runs on request, `ragwb backup` copies the store and, since release 1.4, `ragwb restore` puts one back, Part XVI §171). Since release 1.1 a per-case wall-clock limit exists
(`RAGWB_CASE_TIMEOUT_S`; the abandoned call keeps running in the background until its HTTP timeout, Part XIII §141.1), but
there is still no budget limit on OpenAI spending: the only cost controls are
the notice in the UI and, if `RAGWB_PRICE_*` is set, cost reporting after the fact (`runner.py:258-262`). Everything a
run loads — dataset, chunks, results for aggregation — is held in memory; the limits above keep that bounded.

### 116.3 Guarantees and their boundaries

**Per-case durability.** Each case result is committed in its own transaction as soon as it is produced
(`runner.py:124-126`, `storage.py:117-125`, `storage.py:5-6`). A crash loses at most the cases in flight.

**Validation before side effects.** A run row is created only after the whole configuration, dataset and document have
been validated and the pipeline and metrics built (`runner.py:1-14`, `102-117`).

**Interrupted-run recovery.** Every committed case refreshes the run's `heartbeat_at` (`storage.py:123`). At start-up,
runs still `running` whose heartbeat (or, for rows without one, creation time) is older than `STALE_AFTER_S` = 15 minutes
are relabelled `interrupted` (`services.py:31-34`, `storage.py:154-166`). Their completed cases remain readable; they are
not resumed. Two consequences of the threshold: a run whose process has just died is still shown as `running` for up to
15 minutes; and a live run that commits no case for 15 minutes — possible with several timeouts and back-off on one slow
case, as the comment at `storage.py:27-28` notes — can be marked `interrupted` by another process starting, after which
its own `finish_run` still writes the final status (`storage.py:121-129`, docstring at `138-139`).

**Deterministic offline results.** BM25 ties break by document order (`retrieval.py:85-86`), the extractive generator is
deterministic, injected failures are seeded per question (`providers.py:60-66`), and bootstrap intervals use a fixed seed
(`aggregate.py:5`, `22-27`). `test_offline_runs_are_reproducible`, `test_parallel_execution_keeps_every_case` and
`test_demo_runs_are_genuine_and_reproducible` check this (`tests/test_runner.py:35-43`, `117-125`, `158-167`). In this
session a CLI run with k = 3 reproduced the `offline-bm25-k3` example run's means exactly, and a CLI run with injected
failures failed the same three cases (`q03`, `q16`, `q17`) as the example run. Judge metrics and OpenAI generation carry
no such guarantee even at temperature 0.

**Concurrency boundary.** Each storage operation opens a short-lived connection (`storage.py:85-98`); SQLite serialises
writers, and a writer waits up to 15 s for a lock. Apart from the heartbeat there is no cross-process coordination. A run
row created as `running` in a temporary store kept status `running` after `ragwb list` opened the same store (checked
directly), so starting a second front end does not relabel live runs. The UI runs one evaluation at a time per browser
session, in the script thread; two browser tabs can start two runs concurrently, which SQLite serialises but which was
not tested.

**Journal mode.** The store uses SQLite's default rollback journal: `PRAGMA journal_mode` on the project's `data/runs.db`
returned `delete` (read-only query, 2026-10-24); the code sets no journal mode. A rollback journal and short
transactions are the conservative choice for folders synchronised by tools such as OneDrive, which this project's folder
is. No locking failures were observed, but the commands for this book used temporary directories outside the
synchronised folder; Part VIII (§88.5) recommends keeping `RAGWB_DATA_DIR` outside synchronised folders.

## 117. Data retention and privacy

### 117.1 What is kept, where, for how long

Everything is local and below the data directory (`config.py:105-142`):

| Path | Content | Retention |
|---|---|---|
| `runs.db` | runs, configurations, summaries, every case's question, reference, answer, retrieved chunk texts, metric reasons, errors | until deleted by the user |
| `uploads/` | every dataset and document uploaded through the UI | forever; deleting a run does not delete them; no UI to remove them |
| `exports/` | files written by `ragwb export` without `--out-dir` | until deleted |
| `logs/rag_workbench.log` (+ `.1`–`.3`) | run start/finish lines, import lines, warnings, stack traces of internal errors | rotated at 2 MB, 3 backups |

There is **no deletion or retention policy**: nothing expires. Deleting a run removes its rows; SQLite does not shrink the
file without `VACUUM`, which the application never runs, so deleted text may persist in free pages of `runs.db` until
overwritten. Resetting all data means deleting the data directory; `start.py` then re-creates the five example runs
(Part VIII, §87.3).

### 117.2 What could be personal or sensitive

* **Document and dataset content** is copied into `runs.db` (chunk texts per case, `models.py:99`) and into exports. If
  the inputs are confidential, so is the run store.
* **Absolute paths in the run store.** The CLI and the UI store `dataset_path` and `document_path` as absolute paths
  (`cli.py:48-49`; observed in `ragwb show`: `C:\Users\omjee\OneDrive\Desktop\PROJECTS\...`), so `runs.db` reveals the user
  name and directory layout.
* **Exports do not carry absolute paths.** `export_json` passes both paths through `portable_path`, which keeps a path
  relative to the project root, or else only the file name (`reporting.py:103-111`, `118-120`); an exported example run
  contained `"dataset_path": "examples/datasets/honeybees.jsonl"`. Tests: `test_exported_bundles_contain_no_absolute_paths`
  and `test_example_paths_become_project_relative`. The Markdown and CSV exports include only the file name
  (`reporting.py:148-149`). Other free-text fields — run names, notes, and the `environment` block with
  `platform.platform()` — are exported as recorded.
* **Environment details.** Each run records `platform.platform()`, the Python version and package versions
  (`runner.py:270-278`).
* **Logs** record run ids, names, case counts and configuration choices (`runner.py:118-119`, `142`), not questions or
  answers. Internal errors are logged with stack traces (`runner.py:212`), and metric failures with the exception message
  (`metrics/base.py:87-88`), which could include fragments of input text.
* **OpenAI paths** send dataset and document content to OpenAI (§114.2), under OpenAI's terms, not this tool's.

All bundled example data — the honeybee document, its PDF rendering and the three datasets — was written for this
project.

## 118. Known issues and unimplemented requirements

### 118.1 Issues found in review

A security and reliability review of the code while this book was written found the issues below; all were fixed, each
fix was re-read in the code for this part, and the test run reported in Part IX §97.2 includes the tests that guard them.

| # | Issue | Current behaviour and guard |
|---|---|---|
| 1 | Run results header could interpolate bundle-supplied values into `unsafe_allow_html` markup | every value `html.escape`d (§113.2); `test_imported_config_values_are_html_escaped` |
| 2 | Start-up recovery could relabel runs live in another process | heartbeat plus 15-minute stale threshold (§116.3); three storage tests |
| 3 | Secrets inside exception tracebacks were not covered by log redaction | `RedactingFormatter` (§111.3); `test_redacting_formatter_covers_tracebacks` |
| 4 | Secret scan did not match prefixed keys such as `sk-proj-…` | prefixed-key pattern with a fake-key marker (§111.5; `scripts/verify.py:38-39`) |
| 5 | Imported summaries were taken from the bundle | recomputed from the cases (§112.3); `test_bundle_summary_is_recomputed_not_trusted` |
| 6 | Out-of-range metric scores were clamped silently | beyond `SCORE_TOLERANCE` = 1e-9 they are `error` results; noise within it is absorbed (`metrics/base.py:23`, `88-92`); `test_out_of_range_scores_are_errors_but_float_noise_is_absorbed` |
| 7 | JSON bundles contained absolute local paths | `portable_path` (§117.2); `test_exported_bundles_contain_no_absolute_paths` |
| 8 | Streamlit listened on all interfaces | `address = "localhost"` and `start.py --server.address localhost` (§114.4) |
| 9 | DeepEval's `.deepeval/` cache folder was not ignored by Git | added to `.gitignore` (§111.4) |

What remains open are limitations of the design rather than defects in the code as written:

* the secret scan is a pattern heuristic (§111.5);
* bundle *scores* are trusted within their valid range; only the summary is recomputed (§112.3);
* Markdown in questions and answers is rendered, and its effect with remote image references was not tested (§113.2);
* the run store keeps absolute paths (§117.2);
* a live run that commits no case for 15 minutes can be relabelled `interrupted` while it runs (§116.3);
* `start.py`'s pip fallback installs unlocked versions (§115).

Methodological limitations — lexical metrics measure word overlap, the extractive baseline never abstains on the bundled
unanswerable questions, BM25 has no synonym handling, twenty questions is a small sample — are documented in
`docs/KNOWN_LIMITATIONS.md` and in the metric chapter. The example runs show two of them concretely: deeper retrieval
lowers token F1 (k = 1 → 3: −0.057, 95 % CI −0.116 to −0.008) because the extractive baseline picks sentences from
off-target chunks, and exact match is 0 of 6 on the unanswerable set (Part VIII, §83.2).

### 118.2 Unimplemented or unverified requirements

Measured against the requirement list and traceability matrix in `docs/REQUIREMENTS_TRACEABILITY.md`:

* **Implemented but only narrowly live-verified:** the OpenAI-compatible generator and the four DeepEval judge metrics were run
  against Groq's free tier in release 1.3 on small samples, including retry behaviour on real rate limits (R1, R3, R10; Part XV §160).
  Release 1.4 ran the agent pipeline live on 3 cases (Part XVI §176.3) and a 20-question four-judge run whose faithfulness and context-relevancy scores were mostly lost to the provider's output-token cap (6 and 1 of 20 scored; §176.4). Not run live: OpenAI itself, API embeddings and hybrid retrieval with API embeddings. Judge scores were never
  compared with human labels (only with labels written by an AI rater). The rest is tested with fakes only (Part IX, §98).
* **Not implemented (and not claimed):** e-mail password reset or database-level separation of runs (named accounts exist, Part XIV §156, three coarse roles since release 1.3, Part XV §165, and password change, an Accounts page and a UI-level run filter since release 1.4, Part XVI §173); an HTTP API; resuming an interrupted
  run; a general migration framework (a column-based migration for schema versions 1 and 2 exists at `storage.py:74-81`); a retention
  policy or upload clean-up; a spending limit; a cancel control other than Streamlit's Stop button; a per-case watchdog.

## 119. Operational risks and explicit limitations

### 119.1 Operational risks

1. **Paid API usage.** With a key configured, a single UI click or CLI command can make several hundred API calls (for 20
   cases with four judge metrics, at least 20 generation calls plus the judge calls DeepEval makes per metric). The UI
   warns (`new_run.py:186-189`) but does not estimate cost unless prices are configured, and even then only afterwards.
2. **Exposed server if the binding is bypassed.** By default the app has no authentication; it is bound to localhost
   through `start.py` and `.streamlit/config.toml` (§114.4). A manual start from another directory or with a different
   `--server.address` removes that protection unless a login is configured (`RAGWB_APP_PASSWORD` or user accounts; either gates the UI, not the CLI or
   the files), and without TLS a login's credentials cross the network in clear text.
3. **Shared bundles carry content.** They carry no absolute paths, but they contain every question, answer and retrieved
   chunk, plus run names and notes (§117.2).
4. **Synchronised data directory.** OneDrive and similar tools can interfere with SQLite file locking (§116.3).
5. **Stale code in a running server.** A running Streamlit server keeps imported modules cached; after editing package
   code, restart it (Part VIII, §88.4).
6. **Install location.** Since release 1.2 `PROJECT_ROOT` comes from `RAGWB_HOME`, else from the checkout (recognised by its
   `pyproject.toml`), else from the current directory, so an installed wheel no longer writes into `site-packages`
   (`config.py:21-34`, Part XIV §157). The unpacked wheel was run from a neutral folder in release 1.2; in release 1.4 the wheel was installed with its dependencies into a clean
   environment and checked 10 of 10 (command-line tool only, Part XVI §176.1). The Dockerfile was not tested.

### 119.2 Explicit limitations

* The tool is designed for one trusted user on one machine, or a small trusted team sharing one instance behind a login. It is not a service.
* Its security controls address accidental leaks and untrusted *files*; they do not address untrusted *users*.
* Its reliability guarantees are per case and per process; across processes it relies only on SQLite and the heartbeat.
* Offline results are deterministic; OpenAI and judge results are not, and were exercised live only narrowly (Groq's free tier, small samples; Part XV §160).
* A dependency scan (`pip-audit`) found no known vulnerabilities in the locked runtime requirements at one point in
  time (§115, Part XIII §145.4); no penetration test and no formal accessibility review have been performed (release 1.2 added a scripted accessibility check, Part XIV §158, release 1.3 one keyboard walk of one page, Part XV §166, and release 1.4 an axe-core audit and two more keyboard walks, Part XVI §177), and the
  only load measurement is the offline scale benchmark (Part XIII §146) — nothing was measured under load against a live provider.
