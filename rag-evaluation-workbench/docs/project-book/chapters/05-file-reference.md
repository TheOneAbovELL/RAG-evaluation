# Part V — Detailed file-by-file reference

This Part walks through the repository one file at a time. It is meant to be read next to the code: every
statement here was checked against the source, and line numbers are given as `file.py:N` (relative to the
file's own directory where unambiguous, otherwise to the project root). Line numbers written as `file.py:N` (in the prose of every Part) are checked against the final source by a script. The
"Line" columns of the interface tables in sections V.1-V.39 were written for release 1.0 and re-checked only for the
files that sections V.41 onwards and Parts XIV and XV re-describe (`start.py` and `ui/auth.py` are current); for every other file
`docs/project-book/generated/source-inventory.md` lists each definition with its current line number and is regenerated
from the code by `docs/project-book/tools/generate_reference.py`. When this Part
and the code disagree, the code is right.

Conventions used in every section:

* **Path**: the file's path relative to the project root.
* **Imports**: *internal* means modules of `rag_workbench`; *third-party* means installed distributions.
  Imports that happen inside a function (lazy imports) are marked as such, because they matter: the package
  promises that importing it never touches the network or builds an index.
* **Public interface**: a table of the names other modules use. "Line" is the line of the `def`/`class`
  statement.
* **Tests**: test files live in `tests/`; `docs/project-book/generated/test-catalogue.md` lists every test
  function (418 collected in release 1.4). The shared fixtures in `tests/conftest.py` force every test offline: `OPENAI_API_KEY` is set to the
  empty string (which also stops `.env` from supplying one), `RAGWB_DATA_DIR` points at the test's `tmp_path`,
  and `RAGWB_RETRY_BASE_DELAY_S` is `0` (`conftest.py:22-31`).

The order of the sections is: the launcher `start.py` and the Streamlit entry point; the package, from the
foundation modules upward (configuration, errors, logging, data contracts, text processing, inputs, retrieval,
generation, pipelines, metrics, aggregation, storage, orchestration, bundles, reporting, wiring, example runs,
CLI); the user interface; the scripts; the documentation tooling; and the configuration and data assets. A coverage table at the end maps
every file in the source inventory to its section.

---

## V.1 `start.py` — the one-command launcher

**Path:** `start.py` (212 lines). Usage: `python start.py [--port N] [--host H] [--ssl-cert F --ssl-key F] [--no-browser] [--no-examples] [--setup-only]`.

**Purpose and responsibilities.** The single entry point for a person who has just downloaded the project: prepare
the environment, create the example runs on the first launch, start the Streamlit app on this machine only, open
the browser, and stop cleanly on Ctrl+C (docstring, lines 1-16). It uses **only the Python standard library**
(line 15), because it must run before any dependency is installed.

**Imports.** Standard library only: `argparse`, `os`, `shutil`, `socket`, `subprocess`, `sys`, `time`,
`ssl` (release 1.2), `urllib.request`, `webbrowser`, `pathlib`. It never imports `rag_workbench` itself; everything that needs the
package runs in a child process with the environment's interpreter.

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `ROOT`, `VENV`, `VENV_PYTHON`, `MIN_PYTHON`, `LOCAL_HOSTS` | 31-35 | constants | Project root (the script's folder), `.venv`, its interpreter (`Scripts/python.exe` on Windows, `bin/python` elsewhere), `(3, 12)` and the local host names. |
| `say` | 38 | `(message)` | Print `[start] message`, flushed. |
| `run` | 42 | `(cmd, **kwargs) -> CompletedProcess` | Echo the command, then `subprocess.run` it in `ROOT`. |
| `prepare_environment` | 47 | `()` | uv or venv+pip set-up. |
| `store_is_empty` | 66 | `() -> bool` | Ask the installed package how many runs are stored. |
| `create_examples` | 75 | `()` | Run the five example evaluations. |
| `password_configured` | 84 | `(env=None, env_file=None) -> bool` | True if `RAGWB_APP_PASSWORD` is non-blank in the environment or in `.env`. |
| `accounts_configured` | 98 | `(env=None) -> bool` | True if `<data dir>/users.json` lists a user (or cannot be parsed) and is larger than two bytes (release 1.2). |
| `host_problem` | 112 | `(host, password_set) -> str \| None` | The refusal message for a non-local host without a login (shared password or accounts), else `None`. |
| `tls_problem` | 120 | `(cert, key) -> str \| None` | A message if only one TLS file is given or a file is missing, else `None` (release 1.2). |
| `free_port` | 132 | `(preferred) -> int` | First port in `preferred..preferred+49` on which nothing accepts a connection. |
| `wait_until_ready` | 140 | `(port, process, timeout=90, host="localhost", https=False) -> bool` | Poll Streamlit's health endpoint (certificate not verified when `https`). |
| `launch` | 157 | `(port, open_browser, host="localhost", ssl_cert=None, ssl_key=None) -> int` | Start Streamlit, open the browser, wait, handle Ctrl+C. |
| `main` | 192 | `() -> int` | Parse flags and run the steps in order. |

**How it works, step by step.**

1. `main` (185-208) parses `--port` (default 8501), `--host` (default `localhost`), `--ssl-cert`, `--ssl-key`,
   `--no-browser`, `--no-examples` and `--setup-only` (187-195), changes into `ROOT` (197), so the launcher behaves the same
   from any working directory, and refuses a non-local `--host` when neither `RAGWB_APP_PASSWORD` nor user accounts exist
   (`host_problem`), or a TLS pair that is incomplete or missing a file (`tls_problem`) (198-201).
2. `prepare_environment` (46-62). If `uv` is on `PATH` it runs `uv sync --frozen --inexact` (50): `--frozen`
   installs exactly what `uv.lock` pins without re-resolving, and `--inexact` leaves packages that are not in the
   lock installed instead of removing them. `UV_HTTP_TIMEOUT` defaults to 180 seconds unless the user has set it
   (49). A failure exits with a message suggesting a retry on slow networks (51). Without uv, it requires Python
   3.12+ (53-56), creates `.venv` with `python -m venv` if it does not exist (57-60), and runs
   `pip install --quiet -e . pytest pytest-cov` with the venv's interpreter (61-62). Nothing is installed outside
   the project folder (docstring, line 6).
3. `store_is_empty` (65-71) runs a one-line probe in the environment's interpreter — `open_context(...)` then
   `len(store.list_runs())` — and treats output `0` as empty. Opening the context also creates the data directory
   and performs the normal start-up recovery (V.24). If the probe fails, the launcher exits with the last 2,000
   characters of the child's stderr (69-70): an unusable run store or configuration is reported before the app
   starts.
4. Unless `--no-examples` is given, an empty store triggers `create_examples` (74-80), which runs
   `rag_workbench.demo.seed_demo_runs` (V.25) in a child process and prints each run's name and status. A failure
   here is reported but not fatal: the app starts without examples (79-80). Because the check is "store is empty",
   later launches never re-seed, and a user who deletes some runs keeps the rest.
5. `--setup-only` stops here with "setup complete" (205-207).
6. `free_port` (125-130) probes `127.0.0.1` with `connect_ex` from the preferred port upward and returns the first
   port with no listener; it exits if 50 consecutive ports are taken. `--port` is therefore a preference, not a
   guarantee.
7. `launch` (150-182) starts `python -m streamlit run streamlit_app.py --server.port <port> --server.address
   <host> --server.headless true --browser.gatherUsageStats false` with `DEEPEVAL_TELEMETRY_OPT_OUT=1` in the
   child's environment (151-153); with both TLS files it adds `--server.sslCertFile` and `--server.sslKeyFile` (155-156),
   and for a non-local host without TLS it prints a warning that credentials cross the network unencrypted
   (157-159); `<host>` is `localhost` unless `--host` is given, and `0.0.0.0` or `::` are probed as
   `localhost` (160). The address and statistics flags repeat `.streamlit/config.toml` (V.39), so the
   app stays local-only even if that file is changed. `wait_until_ready` (133-147) polls
   `http(s)://<host>:<port>/_stcore/health` every 0.5 s for up to 90 s and returns early if the child exits; for HTTPS it
   skips certificate verification (135-136), because the probe only ever talks to the server the launcher itself started. When
   the app is ready the launcher prints the URL and opens it with `webbrowser.open` unless `--no-browser`
   (164-168); if the child exited during start-up it exits with the child's code (169-170); if it is merely slow it
   says so and keeps waiting (171-173). It then blocks on `process.wait()`.
8. Ctrl+C (`KeyboardInterrupt`, 175-181) terminates the child, waits up to 10 s and kills it if necessary. `main`
   returns the child's exit code or 0, which becomes the launcher's exit status (182, 211-212).

**Inputs and outputs.** Flags in; console messages prefixed `[start]`, an environment in `.venv`, example runs in
the configured data directory, and a running server on `http://<host>:<port>`.

**Configuration.** No `Settings` are read directly; the child processes read `.env` and `RAGWB_*` as usual (for
example `RAGWB_DATA_DIR` decides which store is probed and seeded). `UV_HTTP_TIMEOUT` is honoured when set.

**Error behaviour.** Every unrecoverable step ends with `sys.exit("[start] ...")` and a specific message: uv sync
failed, Python too old without uv, venv creation or pip install failed, the run store could not be opened, no free
port, a non-local host without a login, an unusable TLS option pair, or the app exited during start-up. Example creation failing is the only non-fatal error.

**Verification.** The host, login, account-detection and TLS-option rules (`password_configured`, `accounts_configured`, `host_problem`, `tls_problem`) and the readiness polling are covered by `tests/test_start.py` (14 tests); TLS was additionally checked end to end with a throwaway self-signed certificate (Part XIV §156.6); the rest is checked by hand: on an empty data directory,
`python start.py --setup-only` creates the five example runs and exits; `python start.py --no-browser` then serves
`http://localhost:8501` (or the next free port) and does not create the runs again.

**Design rationale.** A single stdlib-only script removes the "install the right tools first" step: uv gives
locked, reproducible installs when present, and the venv/pip fallback needs nothing beyond Python 3.12. Seeding
examples on first launch means a new user opens an app that already contains real results to explore, without a
network connection or an API key.

**Limitations.** The pip fallback installs from `pyproject.toml` lower bounds, not from `uv.lock`, so its versions
may differ from the locked ones. The uv branch assumes uv's default project environment `.venv` (it then runs
`VENV_PYTHON`); a custom `UV_PROJECT_ENVIRONMENT` would not be found. `free_port` and Streamlit's own bind are two
separate steps, so another process could take the port in between.

---

## V.2 `streamlit_app.py` — Streamlit entry point

**Path:** `streamlit_app.py` (42 lines). Started with `uv run streamlit run streamlit_app.py`.

**Purpose.** Declare the multipage navigation and nothing else. Every page is a script under
`src/rag_workbench/ui/views/`; the entry point only wires them into `st.navigation`. There is no separate
backend process: pages call the `rag_workbench` package in-process (module docstring, lines 3-4).

**Imports.** Standard library `os`, `pathlib.Path`; third-party `streamlit`; internal
`rag_workbench.ui.auth` (`render_account`, `require_login`) and `rag_workbench.ui.components.apply_style`.

**What it does, line by line.**

| Lines | Behaviour |
|---|---|
| 10 | `os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "1")` before `streamlit` and the package are imported. The package `__init__` does the same; doing it here too means the variable is set even before any import that could transitively load DeepEval, so no anonymous telemetry is sent by default. `setdefault` lets a user opt back in by exporting `0`. |
| 18 | `st.set_page_config(page_title="RAG Evaluation Workbench", page_icon=":material/fact_check:", layout="wide")`. |
| 19 | `apply_style()` injects the small CSS block from `ui/components.py`. |
| 20-21 | `require_login(context_or_stop().settings)` blocks every page behind the login form when a shared password or user accounts are configured (a no-op otherwise); `render_account` adds the sidebar "Signed in as … / Sign out" block (V.43). |
| 23 | `VIEWS` is resolved from `__file__`, so the app works regardless of the current working directory. |
| 24-37 | Three navigation sections: **Evaluate** (Overview — the default page — and New evaluation, `url_path="new-run"`), **Analyse** (Run results `results`, Compare runs `compare`), **Data & system** (Datasets & retrieval `data`, Settings & metrics `settings`). |
| 39-40 | Release 1.4: when named accounts exist and the signed-in role is `admin`, an **Admin** section with the *Accounts* page (`users.py`, `url_path="accounts"`, V.56) is added; no other user sees it. |
| 42 | `st.navigation(pages).run()` executes the selected page script. |

**Interfaces.** None (a page script). The `url_path` values are part of the public surface: deep links such as
`/results?run=<id>&tab=case&case=q10` and `/compare?runs=a,b` (built by `scripts/seed_demo_runs.py:29-41`)
depend on them.

**Configuration.** None directly; `.streamlit/config.toml` (section V.39) supplies server and theme settings.

**Tests.** Every test in `tests/test_ui.py` starts from this file: `AppTest.from_file(ENTRY, ...)` with
`ENTRY = PROJECT_ROOT / "streamlit_app.py"` (`test_ui.py:11, 21-28`), then `switch_page(...)` to the page under
test.

**Limitations.** The page list is static; adding a page means editing this file. Page scripts are referenced by
filesystem path, so renaming a view file breaks both this list and every `st.page_link` that points at it.

---

## V.3 Package markers: `__init__.py`, `__main__.py`, `ui/__init__.py`, `ui/views/__init__.py`

**`src/rag_workbench/__init__.py`** (15 lines). The docstring opens with the product name ("RAG Evaluation
Workbench: evaluate a retrieval-augmented QA pipeline over a dataset.") and states the package's import-safety contract:
importing it "never contacts a network service, reads an API key, or builds an index" (lines 3-4), so the CLI,
the UI and the tests can import everything without a key or a connection, and expensive objects are built only
when a run needs them. Line 11 sets `DEEPEVAL_TELEMETRY_OPT_OUT=1` with `setdefault` before any submodule can
import DeepEval, which otherwise sends anonymous telemetry. Line 13 defines
`__version__ = "1.2.0"`, which `runner.environment_info()` records in every run and the Settings page displays.
`__all__ = ["__version__"]`.

**`src/rag_workbench/__main__.py`** (5 lines). `sys.exit(main())` with `main` from `.cli`, so
`python -m rag_workbench <command>` is equivalent to the `ragwb` console script declared in `pyproject.toml`.
Test: `test_cli_services.py::test_module_entry_point_runs_in_a_subprocess` runs the module in a subprocess and
asserts exit code 0. `scripts/verify.py` drives the end-to-end check through this entry point
(`verify.py:137-178`).

**`src/rag_workbench/ui/__init__.py`** (1 line): docstring only, `"""Streamlit user interface."""`.

**`src/rag_workbench/ui/views/__init__.py`** (empty). The view files are page scripts executed by Streamlit,
not modules imported by anything; the marker only keeps the directory a regular package.

---

## V.4 `src/rag_workbench/config.py` — centralised settings

**Path:** `src/rag_workbench/config.py` (236 lines).

**Purpose and responsibilities.** One place where every tunable value is defined, validated and documented:
model names, timeouts, retry policy, worker count, optional prices, input limits, file locations and log level.
Nothing else in the code hard-codes a model name, limit or path, and every path is resolved against the project
root rather than the current working directory.

**Imports.** Standard library `os`, `pathlib.Path`, `typing.Literal`. Third-party `python-dotenv`
(`load_dotenv`), `pydantic` (`BaseModel`, `Field`, `SecretStr`, `ValidationError`, `field_validator`). No internal
imports: this is a leaf module that everything else may import.

### Public interface

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `PROJECT_ROOT` | 37 | `Path` | `Path(__file__).resolve().parents[2]` — the repository root, valid because the package is installed in editable mode from `src/` (comment, line 20). |
| `EXAMPLES_DIR` | 39 | `Path` | `PROJECT_ROOT / "examples"`, or the copy bundled in a wheel (`rag_workbench/_examples`) when the former does not exist; used by `tune-abstention`, the demo runs and the dataset picker since release 1.4. |
| `ProviderName`, `PipelineMode`, `RetrieverName` | 24-26 | `Literal` aliases | `"offline"\|"openai"`, `"rag"\|"agent"`, `"bm25"\|"embedding"\|"hybrid"\|"local"\|"hybrid-local"`; reused by `models.RunConfig`. |
| `ConfigError` | 50 | `class ConfigError(ValueError)` | Raised for missing or invalid configuration, everywhere in the package. |
| `Settings` | 54 | pydantic model, `frozen` | Runtime settings; build with `load_settings`. |
| `Settings.db_path` / `uploads_dir` / `exports_dir` / `log_path` | 80 / 79 / 83 / 87 | properties | `data_dir/runs.db`, `data_dir/uploads`, `data_dir/exports`, `data_dir/logs/rag_workbench.log`. |
| `Settings.has_openai_key` | 145 | property → `bool` | True only if a key is set *and* non-blank after `strip()`. |
| `Settings.public_dict()` | 163 | `() -> dict` | `model_dump(mode="json")` without `openai_api_key`, plus `openai_api_key_configured: bool`. |
| `ENV_VARS` | 173 | `dict[str, str]` | Environment variable → field name; the single source for the docs and the Settings page. |
| `load_settings` | 204 | `(env: dict[str, str] \| None = None, *, dotenv: bool = True) -> Settings` | Build settings from the environment. |

### Fields (`config.py:39-70`)

| Field | Default | Constraint | Environment variable |
|---|---|---|---|
| `project_root` | `PROJECT_ROOT` | — | (none) |
| `data_dir` | `PROJECT_ROOT/data` | path | `RAGWB_DATA_DIR` |
| `default_dataset` | `examples/datasets/honeybees.jsonl` | path | `RAGWB_DATASET` |
| `default_document` | `examples/documents/honeybees.pdf` | path | `RAGWB_DOCUMENT` |
| `openai_api_key` | `None` | `SecretStr` | `OPENAI_API_KEY` |
| `openai_base_url` | `None` | — | `OPENAI_BASE_URL` |
| `generator_model` | `gpt-4o` | — | `RAGWB_GENERATOR_MODEL` |
| `embedding_model` | `text-embedding-3-large` | — | `RAGWB_EMBEDDING_MODEL` |
| `judge_model` | `gpt-4o` | — | `RAGWB_JUDGE_MODEL` |
| `request_timeout_s` | `60.0` | `0 < x <= 600` | `RAGWB_REQUEST_TIMEOUT_S` |
| `max_retries` | `3` | `0..10` | `RAGWB_MAX_RETRIES` |
| `retry_base_delay_s` | `1.0` | `0..60` | `RAGWB_RETRY_BASE_DELAY_S` |
| `max_workers` | `4` | `1..32` | `RAGWB_MAX_WORKERS` |
| `price_input_per_mtok` / `price_output_per_mtok` | `None` | `>= 0` | `RAGWB_PRICE_INPUT_PER_MTOK` / `RAGWB_PRICE_OUTPUT_PER_MTOK` |
| `max_dataset_bytes` | `5_000_000` | `> 0` | `RAGWB_MAX_DATASET_BYTES` |
| `max_document_bytes` | `25_000_000` | `> 0` | `RAGWB_MAX_DOCUMENT_BYTES` |
| `max_cases` | `5_000` | `> 0` | `RAGWB_MAX_CASES` |
| `max_field_chars` | `20_000` | `> 0` | `RAGWB_MAX_FIELD_CHARS` |
| `log_level` | `INFO` | one of DEBUG/INFO/WARNING/ERROR/CRITICAL, upper-cased (`_valid_level`, lines 71-72) | `RAGWB_LOG_LEVEL` |

`model_config = {"frozen": True}` (line 37) makes a `Settings` instance immutable, so the object cached by the
Streamlit app (one per server process) cannot be mutated by one page and silently affect another.

### How `load_settings` works (`config.py:204-232`)

1. If `env` is `None` (the normal case), it loads `PROJECT_ROOT/.env` with `override=False` — real environment
   variables win over the file — and then snapshots `os.environ` (lines 133-164). If the caller passes an explicit
   `env` dict, neither `.env` nor `os.environ` is consulted; the tests use this to build isolated settings
   (`load_settings({...}, dotenv=False)` in `test_runner.py:68`). The `dotenv` flag only matters when `env` is
   `None`.
2. For each entry of `ENV_VARS`, a missing or whitespace-only value is skipped (lines 168-142): **blank means
   unset**. Because `load_dotenv` does not override existing variables, an exported-but-empty
   `OPENAI_API_KEY=` also prevents `.env` from supplying a key — the mechanism `conftest.py:25` relies on.
3. Path fields (`_PATH_FIELDS`, line 152) are `expanduser()`-ed and, when relative, resolved against
   `PROJECT_ROOT`, not the CWD (lines 144-174). Other values are passed as stripped strings; pydantic coerces
   numbers.
4. A pydantic `ValidationError` is converted into a `ConfigError` whose message names the *environment
   variable*, not the field: `_env_name` (lines 186-162) maps the field in `err["loc"][0]` back through
   `ENV_VARS`. `from None` suppresses the pydantic traceback.

**Error behaviour.** `ConfigError("Invalid configuration: RAGWB_MAX_WORKERS: Input should be less than or equal to
32")`-style messages. The CLI prints them as `error: ...` with exit code 1 (`cli.py:639-643`); the UI shows them
via `ui/state.context_or_stop` and stops the page.

**Secret handling.** `openai_api_key` is a `SecretStr`, so its value never appears in `repr`. The value is read
with `.get_secret_value()` only at the points that construct clients (`pipeline.py:139, 165`,
`metrics/__init__.py:46`, `config.py:152-155` for the log redactor, used at `logging_setup.py:85`). `public_dict()` is the only serialisation used for display
(Settings page) and never contains the key.

**Tests.** `tests/test_config.py`: `test_defaults_resolve_inside_project`,
`test_relative_paths_are_resolved_against_project_root`, `test_absolute_path_kept`,
`test_numeric_parsing_and_blank_values_ignored`, `test_invalid_values_raise_config_error_naming_the_variable`
(parametrised), `test_secret_never_exposed`.

**Limitations.** `PROJECT_ROOT` was derived from the source location in release 1.0, which in a non-editable wheel install would have
pointed into `site-packages`' parent. Since release 1.2 it is `RAGWB_HOME`, else the checkout (recognised by `pyproject.toml`), else the
current directory, and since release 1.4 a clean wheel install has been verified for the command-line tool (Part XVI §176). `.env` is loaded into the process environment (a side effect of `load_dotenv`), so it affects child
processes too. Settings are read once per process; the UI says to restart after changing them.

---

## V.5 `src/rag_workbench/errors.py` — provider error hierarchy

**Path:** `src/rag_workbench/errors.py` (91 lines).

**Purpose.** Separate model-call failures that retrying can fix from those it cannot, and translate OpenAI SDK
exceptions into that vocabulary in one place. The runner's retry loop depends on this split.

**Imports.** None at module level; `openai` is imported lazily inside `classify_openai_error` (line 20).

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `ProviderError` | 6 | `class ProviderError(RuntimeError)` | Non-retryable failure (bad key, invalid request, empty answer, injected offline failure). |
| `TransientProviderError` | 10 | `class TransientProviderError(ProviderError)` | Retryable failure (rate limit, timeout, connection error, 5xx). |
| `classify_openai_error` | 14 | `(exc: BaseException) -> ProviderError \| None` | Map an OpenAI SDK exception; `None` if `exc` is not an OpenAI error. |
| `_short` | 34 | `(exc, limit=300) -> str` | `str(exc)` (or the type name if empty), truncated to 300 characters with `...`. |

**Mapping (`errors.py:46-54`).** `openai.RateLimitError`, `APITimeoutError`, `APIConnectionError`,
`InternalServerError` → `TransientProviderError("OpenAI <Type>: <message>")`. `openai.AuthenticationError` →
`ProviderError` with a fixed text that names `OPENAI_API_KEY` but does **not** echo the SDK message (which may
contain a key fragment). Any other `openai.OpenAIError` → `ProviderError("OpenAI <Type>: <message>")`. Anything
else → `None`, and the caller re-raises the original exception.

Because `TransientProviderError` subclasses `ProviderError`, a caller that only cares about "a provider failed"
can catch the base class; the runner catches the subclass first (`runner.py:241, 221`).

**Callers.** `providers.OpenAIChatGenerator.generate` (`providers.py:109-113`), `pipeline.AgentRAGPipeline.answer`
(`pipeline.py:99-105`), `retrieval.EmbeddingRetriever.retrieve` (`retrieval.py:165-172`),
`metrics/judge.JudgeMetric.score` (`judge.py:89-95`). `providers.ExtractiveGenerator`
raises `ProviderError` directly for injected failures.

**Tests.** `test_providers_pipeline.py::test_classify_openai_errors` builds real `openai` exception objects with
`httpx` responses and checks: rate limit and timeout are transient; authentication maps to a plain
`ProviderError` mentioning `OPENAI_API_KEY` and not containing `"sk-abc"`; a `ValueError` maps to `None`.

**Limitations.** Only OpenAI SDK exception types are recognised. Exceptions raised by other layers (for example
an `httpx` error that a wrapper does not convert, or an error raised by DeepEval itself) return `None`; in the
runner they become "Unexpected ..." case errors and are not retried.

---

## V.6 `src/rag_workbench/logging_setup.py` — logging with redaction

**Path:** `src/rag_workbench/logging_setup.py` (105 lines).

**Purpose.** Configure the `rag_workbench` logger once per process with a rotating file handler (and optionally a
console handler), and mask secrets in everything written — message, traceback and stack info — as a second line
of defence; the code itself never logs credentials (docstring, lines 3-5).

**Imports.** Standard library `logging`, `re`, `logging.handlers.RotatingFileHandler`; internal
`.config.Settings`.

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `_KEY_PATTERN` | 18 | regex `sk-[A-Za-z0-9_\-]{8,}` | Anything shaped like an OpenAI key (this also covers `sk-proj-...` keys, since `-` is in the class). |
| `RedactingFormatter` | 22 | `logging.Formatter` subclass, `(fmt, redactor)` (23) | `format` (27) runs the standard formatting — including the `exc_info` traceback and `stack_info` text — and passes the whole result through `redactor.redact`. |
| `RedactSecretsFilter` | 51 | `logging.Filter` subclass | Masks known secrets and key-shaped strings. |
| `RedactSecretsFilter.__init__` | 52 | `(secrets: list[str])` | Keeps only secrets of length >= 8 (short strings would cause spurious replacements). |
| `RedactSecretsFilter.redact` | 56 | `(text: str) -> str` | Replace each secret with `***`, then `_KEY_PATTERN` with `sk-***`. |
| `RedactSecretsFilter.filter` | 61 | `(record) -> bool` | Formats the message (`getMessage()`), redacts it, and if it changed stores the redacted text in `record.msg` with `record.args = None`. Always returns `True` (never drops a record). |
| `configure_logging` | 79 | `(settings: Settings, *, console: bool = True) -> logging.Logger` | Idempotent configuration. |

**How `configure_logging` works.** It always sets the logger level from `settings.log_level` (line 82). If the
logger already carries the attribute `_rag_workbench_configured` it returns immediately (lines 83-84) — so handlers
are attached exactly once, however often Streamlit reruns or tests call it. Otherwise it creates the filter with
the configured key (if any), a `RedactingFormatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s",
redactor)` sharing the same redactor (line 85), a `RotatingFileHandler(settings.log_path, maxBytes=2_000_000,
backupCount=3, encoding="utf-8")` — skipped with a warning if the log directory cannot be created (lines 92-96) —
and a `StreamHandler` when `console=True`. Each handler gets both the formatter and the filter (lines 99-69). They
are attached **to the handlers**, not to the logger: records emitted by child loggers such as
`rag_workbench.runner` propagate to the parent's handlers without passing through the parent logger's own
filters, so a logger-level filter would miss them. The filter redacts the message early (so any other handler
or code inspecting the record sees the masked text); the formatter is what covers tracebacks, which the filter
cannot reach because the traceback text is produced only during formatting. `propagate = False` (line 103) keeps
records out of the root logger (and out of Streamlit's console output).

**Configuration.** `log_level`, `log_path` (derived from `data_dir`), `openai_api_key`.

**Callers.** `services.open_context` (`services.py:30`). The CLI and the Streamlit app both pass
`console_logging=False`, so in normal use logs go only to `data/logs/rag_workbench.log`.

**Tests.** `test_cli_services.py::test_secret_redaction_filter` asserts that a record formatted as
`"key=<secret> other=sk-..."` comes out as `"key=*** other=sk-***"`;
`test_cli_services.py::test_redacting_formatter_covers_tracebacks` formats a record whose `exc_info` carries an
exception message containing the secret and asserts the secret is absent and `"boom with ***"` present — the case
that matters for `log.exception(...)` calls such as `runner.py:212, 224`.

**Limitations.** (1) The first configuration wins: because of the idempotency flag, a later call with a different
key or log path does not reconfigure handlers (only the level changes). (2) Redaction is string replacement of the
one configured key plus the `sk-` pattern; other secrets (for example a key for a custom `OPENAI_BASE_URL`
provider with a different shape) are only masked if they equal the configured key. (3) The idempotency marker is a private attribute set on the logger
object (`_rag_workbench_configured`, lines 83 and 71), not a module global, so it survives module reloads.

---

## V.7 `src/rag_workbench/models.py` — data contracts

**Path:** `src/rag_workbench/models.py` (197 lines).

**Purpose.** The pydantic models that flow between every layer: dataset rows, document chunks, retrieval hits,
generations, metric results, case results, run configuration, summaries and stored run records. Storage writes
them as JSON, bundles embed them, the UI reads them; keeping them in one module keeps those layers consistent.

**Imports.** Standard library `datetime`, `typing`; third-party `pydantic`; internal `.config` (the three
`Literal` aliases).

### Type aliases (`models.py:12-15`)

* `RunStatus = Literal["running", "completed", "partial", "failed", "cancelled", "interrupted", "imported"]`
* `CaseStatus = Literal["ok", "error"]`
* `MetricStatus = Literal["ok", "skipped", "error"]`
* `ContextSource = Literal["retriever", "agent_tool"]` — where a case's stored context came from: the chunks the
  retriever returned for the question (`rag` pipeline) or the chunks the agent's retrieval tool returned (`agent`
  pipeline). There is deliberately no value for a model's own description of its evidence; such text is kept only
  in `Generation.model_context_claim` and never stored as context.

### Models

| Name | Line | Fields (defaults) | Notes |
|---|---:|---|---|
| `utcnow()` | 18 | — | `datetime.now(timezone.utc)`; all timestamps are timezone-aware UTC. |
| `EvalCase` | 22 | `id`, `question`, `expected_answer=None`, `metadata={}` | One dataset row. |
| `Chunk` | 31 | `id`, `text`, `page`, `source` | `id` has the form `p{page}-b{n}` (from `documents.py`). |
| `RetrievedChunk` | 40 | `chunk_id`, `text`, `page`, `score`, `rank` | `rank` is 1-based. |
| `Generation` | 50 | `answer`, `contexts`, `context_source="retriever"`, `model`, `latency_ms`, `prompt_tokens=None`, `completion_tokens=None`, `retrieval_queries=[]`, `model_context_claim=None` | Output of `Pipeline.answer`. `model_context_claim` holds the agent's self-reported context "for audit only" (line 61). `total_tokens` property (63-67) is `None` only when both counts are `None`. |
| `MetricResult` | 70 | `name`, `status`, `score=None`, `threshold=None`, `passed=None`, `reason=None` | `_bounded` validator (80-85) rejects scores outside [0, 1]. |
| `CaseResult` | 89 | `case_id`, `position`, `question`, `expected_answer`, `status`, `answer=None`, `contexts=[]`, `context_source=None`, `latency_ms`, `prompt_tokens`, `completion_tokens`, `cost_usd` (all `None`), `attempts=1`, `error=None`, `metrics={}` | Everything stored per case. `score(metric)` (107) returns the score or `None` when the metric is missing or not `ok`. |
| `RunConfig` | 114 | see below | "Everything needed to reproduce a run. Contains no secrets." |
| `MetricSummary` | 150 | `name`, `n_scored`, `n_skipped`, `n_error`, `mean`, `median`, `std`, `min`, `max`, `ci_low`, `ci_high`, `threshold`, `n_passed`, `pass_rate` | Produced by `aggregate.summarize_metric`. |
| `RunSummary` | 169 | `n_cases`, `n_ok`, `n_error`, `metrics: dict[str, MetricSummary]`, `mean_latency_ms`, `p95_latency_ms`, `total_prompt_tokens`, `total_completion_tokens`, `total_cost_usd` | Produced by `aggregate.summarize_run`. |
| `RunRecord` | 182 | `id`, `name`, `status`, `created_at`, `finished_at=None`, `config: dict`, `dataset_sha256`, `document_sha256`, `n_cases=0`, `summary=None`, `environment={}`, `notes=None` | One row of the `runs` table. |

### `RunConfig` (`models.py:114-147`)

| Field | Default / constraint | Meaning |
|---|---|---|
| `name` | 1..120 chars | Human-readable run name. |
| `dataset_path`, `document_path` | required strings | Input files. |
| `provider` | `"offline"` | `offline` or `openai`. |
| `pipeline` | `"rag"` | `rag` or `agent`. |
| `retriever` | `"bm25"` | `bm25` or `embedding`. |
| `k` | `3`, `1..50` | Chunks retrieved per query. |
| `metrics` | at least one; `_unique_metrics` (137-142) rejects duplicates | Metric names (validated against the registry by the runner, not here). |
| `thresholds` | `{}` | Per-metric pass thresholds; the runner validates names and range. |
| `generator_model`, `embedding_model`, `judge_model` | `None` | Explicit models; `None` means "use the Settings default" (generator, embedding) or "no judge used". |
| `max_workers` | `1`, `1..32` | Parallel cases. |
| `max_retries` | `3`, `0..10` | Retries for transient errors. |
| `request_timeout_s` | `60.0`, `> 0` | Per-call timeout. |
| `max_answer_sentences` | `2`, `1..10` | Extractive generator only. |
| `limit` | `None`, `>= 1` | Evaluate only the first N cases. |
| `notes` | `None` | Free text. |
| `offline_failure_rate` | `0.0`, `0..1` | Deterministic failure injection for the offline provider (comment line 138). |
| `seed` | `0` | Seed for failure injection. |

`RunRecord.config` is deliberately a plain `dict`, not a `RunConfig`: the runner stores the dumped config plus
resolved values (`thresholds` filled with defaults, the actual `generator_model`), and imported bundles carry
extra keys (`original_status`, `imported_from`, and optionally `provenance_warnings`) that a strict model would
reject.

**Error behaviour.** Constructing any model with invalid data raises `pydantic.ValidationError`, which is a
subclass of `ValueError`; the CLI (`cli.py:685`) and the New evaluation page (`new_run.py:211`) catch
`ValueError` for that reason.

**Tests.** Exercised throughout; `test_storage.py::test_round_trip_preserves_unicode_and_order` checks JSON
round-tripping, `test_metrics.py` exercises `MetricResult`, and `test_archive_reporting.py` validates whole
bundles against these models.

**Limitations.** `RunConfig` does not cross-validate fields (for example `provider="offline"` with
`pipeline="agent"`); that is `pipeline.build_pipeline`'s job, so it happens at `prepare()` time.

---

## V.8 `src/rag_workbench/text.py` — text normalisation

**Path:** `src/rag_workbench/text.py` (100 lines).

**Purpose.** The deterministic, Unicode-aware text functions shared by BM25 retrieval, the extractive generator,
document chunking and the lexical metrics. Keeping them in one module guarantees that the retriever and the
metrics agree on what a "term" is.

**Imports.** Standard library `re`, `string`, `unicodedata`. No internal imports.

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `STOPWORDS` | 15 | `frozenset[str]` | ~130 English function words. Used only for content-token measures; SQuAD F1/EM keep stop words (comment, lines 12-14). |
| `ABSTENTION_PATTERNS` | 36 | `tuple[re.Pattern, ...]` | Four case-insensitive patterns that recognise "not enough information" replies. |
| `normalize_whitespace` | 44 | `(text) -> str` | `" ".join(text.split())`. |
| `tokenize` | 49 | `(text) -> list[str]` | NFKC-normalise, lower-case, then `\w+` matches (Unicode). |
| `stem` | 58 | `(token) -> str` | Minimal plural stripping. |
| `content_tokens` | 76 | `(text) -> list[str]` | `[stem(t) for t in tokenize(text) if t not in STOPWORDS]`. |
| `squad_normalize` | 81 | `(text) -> str` | SQuAD v1.1 normalisation. |
| `split_sentences` | 90 | `(text) -> list[str]` | Regex sentence splitter. |
| `is_abstention` | 98 | `(answer) -> bool` | Any abstention pattern matches. |

**Internal logic.**

* `stem` (lines 65-73): tokens of length <= 3 and digit strings are returned unchanged; `-ies` → `-y` when the
  token is longer than 4 characters (`colonies → colony`); `-sses/-shes/-ches/-xes/-zes` lose `es`
  (`boxes → box`); a final `s` is dropped unless the token ends in `ss`, `us` or `is` (`workers → worker`,
  `grass`, `status`, `analysis` unchanged). The docstring explains the choice: predictable behaviour rather than
  a Porter stemmer.
* Stop-word removal happens **before** stemming, on the lower-cased token (line 78).
* `squad_normalize` (lines 83-87): NFKC + lower-case, delete every ASCII punctuation character **and the
  apostrophe variants `‘ ’ ʼ`** via `str.translate` with `_PUNCT_TABLE` (line 34; ASCII deletion is what the
  SQuAD v1.1 evaluation script does), then replace every remaining character whose Unicode category starts with `P` —
  curly double quotes, dashes, ellipses — with a space (line 85), replace the articles `a|an|the` with a space,
  and squash whitespace. So `"The  Queen's diet: ROYAL, jelly!"` → `"queens diet royal jelly"`, and
  `"The queen’s diet — “jelly”…"` → `"queens diet jelly"`: both apostrophe styles join `queen` and `s`
  identically.
* `split_sentences` (lines 90-95) normalises whitespace and splits with `_SENTENCE_RE`
  (`(?<=[.!?])\s+(?=["'(\[]?[A-Z0-9])`, line 28): a split happens at whitespace preceded by `.`, `!` or `?` and
  followed by an optional opening quote/bracket and an upper-case ASCII letter or digit.
* `ABSTENTION_PATTERNS` (lines 36-36): "does not provide/contain enough information", "not/n't enough/sufficient
  information", "cannot (be) answer(ed)", "no (relevant) information". The pipeline's own abstention sentence
  (`prompts.ABSTAIN_ANSWER`) matches the first.

**Interactions.** `retrieval.BM25Retriever` and `providers.ExtractiveGenerator` use `content_tokens`;
`documents._split_long` and the extractive generator use `split_sentences`; `metrics/lexical.py` uses
`squad_normalize`, `content_tokens` and `is_abstention`.

**Tests.** `tests/test_text.py`: `test_stem` (parametrised word list), `test_tokenize_is_unicode_aware`
(`"Abejas RÉINE 蜜蜂!"` → `["abejas", "réine", "蜜蜂"]`),
`test_content_tokens_drop_stopwords_and_stem`, `test_squad_normalize_matches_reference_behaviour`,
`test_normalize_whitespace_collapses_newlines`, `test_split_sentences`, `test_is_abstention` (parametrised),
`test_squad_normalize_drops_unicode_punctuation`.

**Limitations.** English-only stop words and stemming. Since release 1.1 `tokenize`/`content_tokens` keep a word with
apostrophes between letters whole and then delete the apostrophes (`queen's`, `queen’s` and `queens` all give
`queens`; `can't` gives `cant`; `text.py:29-31`, `:49-55`), so possessives and contractions no longer leave a stray
content token as they did in release 1.0. The stop-word list contains `no`, `nor` and `not`, so
content-token measures (BM25, groundedness, context recall) ignore negation: "drones can sting" and "drones
cannot sting" share the same content terms except `cannot`. Sentence splitting misfires on abbreviations followed
by a capital ("e.g. The") and does not split sentences that start with a lower-case or non-Latin character.
Abstention detection is pattern-based; a model that declines in other words ("I don't know") is not recognised.

---

## V.9 `src/rag_workbench/datasets.py` — dataset parsing and validation

**Path:** `src/rag_workbench/datasets.py` (204 lines).

**Purpose and responsibilities.** Turn a `.jsonl` or `.csv` file into a list of `EvalCase` objects, and report
every problem with a line number instead of dropping rows silently (docstring, lines 11-12). Errors make the
dataset unusable; warnings do not.

**Imports.** Standard library `csv`, `hashlib`, `io`, `json`, `dataclasses`, `pathlib.Path`; internal
`.models.EvalCase`.

### Public interface

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `SUPPORTED_SUFFIXES` | 26 | `{".jsonl", ".csv"}` | Also used by the UI file uploader. |
| `DatasetIssue` | 31 | dataclass `(line: int \| None, message: str)` | One problem; `__str__` (35) renders `"line N: message"` or just the message. |
| `DatasetReport` | 40 | dataclass `(name, cases=[], errors=[], warnings=[], sha256="")` | Result of parsing. |
| `DatasetReport.ok` | 50 | property | `not errors and bool(cases)` — an empty dataset is never ok. |
| `DatasetReport.n_with_reference` | 54 | property | Count of cases with a non-empty `expected_answer`. |
| `DatasetError` | 58 | `class DatasetError(ValueError)`, `__init__(report)` (61) | Carries the report; message lists the first five errors plus "(+N more)". |
| `parse_dataset` | 68 | `(data: bytes, name: str, *, max_bytes=5_000_000, max_cases=5_000, max_field_chars=20_000) -> DatasetReport` | Parse raw bytes; `name`'s suffix selects the format. |
| `load_dataset` | 116 | `(path, **limits) -> list[EvalCase]` | Validate and raise `DatasetError` if not ok. |
| `validate_file` | 124 | `(path, **limits) -> DatasetReport` | Validate a file on disk without raising. |

### How parsing works

**`parse_dataset` (`datasets.py:68-113`).**

1. The report is created with `sha256` of the raw bytes (line 71) — the same bytes later hashed for the run
   record.
2. Early, single-error exits (each returns immediately): unsupported suffix (72-75); size above `max_bytes`
   (76-78); not decodable as `utf-8-sig` (79-83; the `-sig` codec silently accepts a UTF-8 byte-order mark,
   which Excel adds).
3. Rows are produced by `_jsonl_rows` or `_csv_rows` as `(line_number, dict)` pairs (85). Those helpers append
   their own errors to the report.
4. Each row is converted by `_row_to_case` (93). The loop then enforces cross-row rules:
   * reaching `max_cases` appends an error and stops (90-92) — the dataset becomes invalid rather than being
     truncated;
   * a duplicate `id` is an **error** naming the first line it appeared on (96-99);
   * a duplicate question (compared lower-cased with whitespace collapsed, line 99) is a **warning** (101-102).
5. After the loop: no cases and no errors → error "dataset contains no cases" (107-108); cases without a
   reference produce one summary warning that reference-based metrics will be skipped for them (109-112).

**`_jsonl_rows` (138-152).** Iterates `text.splitlines()` with 1-based line numbers, skips blank lines, reports
`invalid JSON (<msg> at column N)` and "expected a JSON object, got <type>" per line, and keeps going, so one
pass lists every broken line.

**`_csv_rows` (155-168).** Uses `csv.DictReader`. If the header lacks a `question` column (after stripping
header names) it reports an error on line 1 and returns no rows. For each row it strips header names, moves
every column other than `id`, `question`, `expected_answer`, `metadata` into a `metadata` dict (empty values
dropped), and records `reader.line_num` — the physical line on which the record ended, which differs from the
record index when a quoted field spans lines.

**`_row_to_case` (171-204).** Per-row validation, in order: `question` must be a non-empty string (173-176);
`expected_answer` must be a string if present (177-180), and an all-whitespace reference is treated as absent
(181-182); `question` and `expected_answer` longer than `max_field_chars` are errors (183-187); `id` defaults to
`case-{position:03d}` when missing or blank, must otherwise be a string or integer but not a bool (186-193;
`bool` is excluded explicitly because it is a subclass of `int`); `metadata` must be a dict (196-199); unknown
top-level keys produce a warning and are ignored (200-202). The returned case has `question` and
`expected_answer` stripped.

**`validate_file` (124-135)** reports "file not found" without raising, and checks the size with `stat()` before
reading the file into memory, so an oversized upload is rejected without loading it.

**Inputs and outputs.** Bytes or a path in; a `DatasetReport` (or a list of `EvalCase`) out. The `position` used
for default ids is the index among *accepted* cases, which equals the row order whenever the dataset is valid.

**Configuration.** Callers pass `max_dataset_bytes`, `max_cases` and `max_field_chars` from `Settings` (runner,
CLI `validate`, New evaluation and Datasets pages). The functions' own defaults equal the Settings defaults.

**Error behaviour.** `parse_dataset` and `validate_file` never raise for bad content; `load_dataset` raises
`DatasetError` (a `ValueError`) whose message shows up to five issues. In a run, `EvaluationRunner.prepare`
calls `load_dataset`, so an invalid dataset aborts before any run row is written.

**Tests.** `tests/test_datasets.py`: `test_real_dataset_is_valid`, `test_ids_metadata_and_optional_reference`,
`test_blank_lines_ignored_and_bom_accepted`, `test_errors_are_reported_with_line_numbers` (parametrised over
broken inputs), `test_duplicate_questions_are_warnings_not_errors`, `test_empty_dataset_is_an_error`,
`test_limits`, `test_non_utf8_and_unsupported_type`, `test_non_ascii_round_trip`,
`test_csv_format_with_extra_columns_as_metadata`, `test_csv_requires_question_column`,
`test_load_dataset_raises_with_summary`. `test_runner.py::test_validation_happens_before_a_run_is_created` checks
that a missing dataset raises `DatasetError` and creates no run.

**Design rationale.** Line-numbered errors and warnings make the validator usable as a pre-flight check from the
CLI (`ragwb validate`) and the UI. Duplicate ids are errors because case ids key the `case_results` table
(primary key `(run_id, case_id)`); duplicate questions are only warnings because they are legal, though they
weaken paired comparison (which keys on question text).

**Limitations.** JSONL unknown keys are ignored (with a warning), not merged into metadata as in CSV. CSV
metadata values are always strings. The whole file is decoded into memory (bounded by `max_bytes`).

---

## V.10 `src/rag_workbench/documents.py` — document loading and chunking

**Path:** `src/rag_workbench/documents.py` (134 lines).

**Purpose.** Read the source document (PDF, plain text or Markdown) and split it into retrievable `Chunk`s with
stable ids, plus a streaming SHA-256 helper used to fingerprint inputs.

**Imports.** Standard library `hashlib`, `logging`, `pathlib`; internal `.models.Chunk`,
`.text.normalize_whitespace`, `.text.split_sentences`; third-party `pymupdf`, imported lazily inside
`_pdf_blocks` (line 88) because it is a heavy native module and text documents do not need it.

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `SUPPORTED_SUFFIXES` | 22 | `{".pdf", ".txt", ".md"}` | Also used by the UI uploader. |
| `DEFAULT_MAX_CHUNK_CHARS` | 23 | `2_000` | Upper bound on a chunk's length. |
| `DocumentError` | 26 | `class DocumentError(ValueError)` | Unreadable document, unsupported type, too large, or no text. |
| `file_sha256` | 30 | `(path: Path) -> str` | Hex SHA-256, read in 64 KiB blocks (`1 << 16`, line 33). |
| `load_chunks` | 38 | `(path, *, max_chars=2000, max_bytes=None) -> list[Chunk]` | Load and chunk a document. |
| `_pdf_blocks` | 87 | `(path) -> list[tuple[int, str]]` | `(page, text)` per PyMuPDF text block. |
| `_text_blocks` | 108 | `(path) -> list[tuple[int, str]]` | `(1, paragraph)` per blank-line-separated paragraph. |
| `_split_long` | 117 | `(text, max_chars) -> list[str]` | Split an over-long block on sentence boundaries. |

**How `load_chunks` works (`documents.py:38-65`).** Checks, in order: the path is a file (42-43); the suffix is
supported (44-46); the size does not exceed `max_bytes` when given (47-49). It then gets raw blocks from
`_pdf_blocks` or `_text_blocks`, passes each through `_split_long`, and numbers the resulting pieces per page
(56-61): ids are `p{page}-b{n}` with `n` counting from 1 on each page. An empty result raises
`DocumentError("No extractable text found in <name>")` (62-63), which is what a scanned, image-only PDF produces.

**`_pdf_blocks` (87-105).** `pymupdf.open` failures of any type are wrapped in `DocumentError` (68-71; PyMuPDF
raises several internal exception types). For each page (1-based), it takes `page.get_text("blocks")`, keeps
text blocks (`b[6] == 0`, i.e. not image blocks), sorts them by `(y0, x0)` — top to bottom, then left to right
(100) — and keeps each non-empty block after whitespace normalisation. For a typical single-column PDF this gives
one chunk per paragraph (module docstring, line 3); `examples/documents/honeybees.pdf` yields 11 chunks: the title
`p1-b1`, paragraphs `p1-b2`…`p1-b10` and `p2-b1`. The dependency is pinned below PyMuPDF 2 in `pyproject.toml` because 2.0 loads layout models at import
time that this plain block extraction does not need (section V.39).

**`_text_blocks` (108-114).** Reads UTF-8 (a decode error becomes `DocumentError`), normalises `\r\n`, splits on
`"\n\n"` and normalises whitespace inside each paragraph. All text chunks are on page 1. Since release 1.4.1 a `.md` file
also has a leading ATX heading marker (`_ATX_MARKER`, `^#{1,6}\s+`) removed from each paragraph, once, because `# Title` is markup
rather than text; the heading words stay, and `.txt` files are not touched (`tests/test_cli_polish.py`).

**`_split_long` (117-134).** Blocks within `max_chars` are returned as-is. Longer blocks are split into sentences
and greedily packed into pieces of at most `max_chars`; a single sentence longer than `max_chars` is hard-cut
into `max_chars`-sized slices first (124-126), which can split a word.

**Configuration.** Callers pass `max_bytes=settings.max_document_bytes`. `max_chars` is not exposed through
`Settings`; every caller uses the default 2,000.

**Interactions.** `runner.prepare` (chunks plus `file_sha256` of dataset and document), `pipeline.build_pipeline`
(when called without chunks), the New evaluation page (chunk count, k slider bound) and the Datasets page
(chunk browser and retrieval playground).

**Tests.** `tests/test_documents.py`: `test_real_pdf_chunks` (11 chunks from the shipped PDF, the first being the title "Honeybees: Life Inside the Colony"),
`test_text_document_split_on_blank_lines`, `test_long_blocks_are_split_on_sentences`, `test_errors` (missing
file, unsupported type, whitespace-only text, size limit, a non-PDF file named `.pdf`, Latin-1 text), `test_sha256_is_stable` (the SHA-256 of `abc`).

**Limitations.** Reading order is a geometric sort, so multi-column layouts interleave columns. No OCR. Chunk ids
are stable only while the document and `max_chars` are unchanged. Headings and tables are treated as ordinary
blocks.

---

## V.11 `src/rag_workbench/retrieval.py` — retrievers

**Path:** `src/rag_workbench/retrieval.py` (209 lines).

**Purpose.** Map a query to the top-k chunks. Two implementations share a structural `Retriever` protocol: an
offline, deterministic Okapi BM25 and an OpenAI-embedding retriever whose index is built lazily.

**Imports.** Standard library `math`, `threading`, `collections.Counter`, `typing.Protocol`; internal
`.errors.classify_openai_error`, `.models.Chunk`, `.models.RetrievedChunk`, `.text.content_tokens`. Lazy (inside
`_ensure_index`): `langchain_core.vectorstores.InMemoryVectorStore`, `langchain_openai.OpenAIEmbeddings`.

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `BM25_K1`, `BM25_B` | 26, 22 | `1.5`, `0.75` | Standard Okapi parameters. |
| `Retriever` | 34 | `Protocol`: `name: str`; `retrieve(query, k) -> list[RetrievedChunk]` | Interface used by pipelines. |
| `BM25Retriever` | 40 | `(chunks, *, k1=1.5, b=0.75)` | Offline lexical retrieval. `name = "bm25"`. |
| `BM25Retriever.score` | 65 | `(query) -> list[float]` | One BM25 score per chunk, in document order. |
| `BM25Retriever.retrieve` | 81 | `(query, k) -> list[RetrievedChunk]` | Top-k with deterministic tie-breaking. |
| `BM25Retriever.idf` | 62 | `dict[str, float]` attribute | Also reused by the extractive generator. |
| `BM25Retriever._postings`, `_len_norm` | 56, 60 | inverted index `term -> [(chunk index, tf)]`; per-chunk `k1 * (1 - b + b * len / avg_len)` | Release 1.4: `score` visits only the chunks that contain a query term. |
| `EmbeddingRetriever` | 127 | `(chunks, *, model, api_key, base_url=None, timeout_s=60.0, max_retries=3)` | Dense retrieval. `name = "embedding"`. |
| `EmbeddingRetriever.retrieve` | 162 | `(query, k) -> list[RetrievedChunk]` | Builds the index on first use, then similarity search; maps OpenAI errors. |

### BM25 internals

*Indexing* (`__init__`, 45-63): an empty chunk list raises `ValueError`. Each chunk becomes a `Counter` of its
content tokens (stemmed, stop words removed); document lengths are token counts; the average length falls back
to `1.0` if no chunk has any content term (53). Since release 1.4 the constructor also builds an inverted index (56-59): for each
term, a list of `(chunk index, term frequency)` pairs, so a term's document frequency is the length of its list, and the
chunk-dependent part of the denominator is computed once per chunk (60). IDF uses the
non-negative variant

    idf(t) = ln(1 + (N - n_t + 0.5) / (n_t + 0.5))

(lines 61-63), which stays positive even for terms that occur in more than half of the chunks; the classic
Robertson–Spärck Jones form goes negative there, which would make a common query term *reduce* a chunk's score.

*Scoring* (`score`, 65-79): the query is tokenised the same way; for each query term in order, and for each chunk in that term's
postings list, it adds `idf(t) * tf * (k1 + 1) / (tf + len_norm)` to the chunk's accumulator (line 78). Query terms are
iterated as a list, so a term repeated in the query contributes once per occurrence. Terms absent from the
corpus have no postings and are skipped (73-75). Every chunk's accumulator still receives its contributions in query order,
starting from `0.0`, which is why the floating-point sums are identical to those of the pre-1.4 scan over every chunk
(`tests/test_bm25_equivalence.py`; Part XVI §175).

*Ranking* (`retrieve`, 81-91): `k < 1` raises `ValueError`. Chunk indices are sorted by `(-score, index)`
(line 86), so ties — including the all-zero case of a query with no shared content term — are broken by document
order, and results are fully reproducible. `k` larger than the corpus returns every chunk. Scores are rounded to
6 decimals in the returned `RetrievedChunk` (ranking uses the unrounded values); ranks are 1-based.

### Embedding retriever internals

The constructor (121-133) stores parameters and a `chunk id → Chunk` map but creates **no** client — so building a
pipeline never calls the API (module docstring, lines 5-6). `_ensure_index` (136-149) runs under a
`threading.Lock`: the first caller creates `OpenAIEmbeddings(model, api_key, base_url, request_timeout,
max_retries)`, an `InMemoryVectorStore`, and adds all chunk texts with `ids` and `metadata={"chunk_id": ...}`;
concurrent callers on a thread pool wait for the same index rather than embedding the document several times.
`self._store` is assigned only after `add_texts` succeeds (148), so a failed build leaves no half-built index and
the next call tries again. `retrieve` (151-167) checks `k`, then runs the index build and
`similarity_search_with_score(query, k=k)` inside one `try` (154-161) — both call the embeddings API — and maps
each hit back to the original chunk through `metadata["chunk_id"]`, so returned text, page and id are the stored
chunk's. The score is the store's similarity value (cosine similarity, per the module docstring).

**Configuration.** `embedding_model` (from `RunConfig.embedding_model` or `Settings.embedding_model`),
`openai_api_key`, `openai_base_url`, `request_timeout_s`, `max_retries` — supplied by
`pipeline.build_retriever`.

**Error behaviour.** `ValueError` for empty chunk lists and `k < 1`. Any exception from the index build or the
query is passed through `errors.classify_openai_error` (158): rate limits, timeouts, connection errors and 5xx
become `TransientProviderError`, so the runner retries the case with back-off exactly as for a chat failure; other
OpenAI errors become `ProviderError` (recorded without retry); non-OpenAI exceptions are re-raised unchanged and
recorded by the runner as "Unexpected ..." errors. Unlike the chat generators, which set `max_retries=0` and leave
retries to the runner (V.13), the embeddings client keeps its own retry loop (`max_retries` is passed through,
line 104), so a transient embedding failure can be retried by the client and then again by the runner.

**Tests.** `tests/test_retrieval.py`: `test_bm25_score_matches_hand_computation` (recomputes the formula by
hand), `test_bm25_ranks_relevant_chunk_first`, `test_bm25_is_deterministic_with_ties`,
`test_k_larger_than_corpus_and_invalid_k`, `test_embedding_retriever_is_lazy_and_maps_ids` (monkeypatches
`OpenAIEmbeddings` with LangChain's `DeterministicFakeEmbedding`; asserts nothing is created at construction,
exactly one client is created on first retrieval, and the index is reused),
`test_embedding_errors_are_classified_for_retry` (a fake embeddings class raising `openai.RateLimitError` from
`embed_documents` makes `retrieve` raise `TransientProviderError`).

**Limitations.** BM25 is purely lexical: synonyms and paraphrases do not match (the
`honeybees_paraphrased.csv` dataset exists to show this). The embedding index lives in memory and is rebuilt for
every run; there is no persistent vector store.

---

## V.12 `src/rag_workbench/prompts.py` — prompts

**Path:** `src/rag_workbench/prompts.py` (34 lines). **Imports:** none.

**Purpose.** The system prompts and user-prompt template of the OpenAI-backed pipelines, and the exact abstention
sentence shared by the prompts, the extractive generator and abstention detection.

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `ABSTAIN_ANSWER` | 8 | `str` | `"The PDF does not provide enough information to answer the question."` |
| `AGENT_SYSTEM_PROMPT` | 10 | `str` | Agent instructions: use the `collecting_info` tool before answering, answer only from retrieved information, reply exactly `ABSTAIN_ANSWER` otherwise. |
| `RAG_SYSTEM_PROMPT` | 21 | `str` | Retrieve-then-generate instructions: use only the numbered passages, be concise, abstain with the exact sentence. |
| `format_context` | 29 | `(passages: list[str]) -> str` | `"[1] text\n\n[2] text..."`. |
| `rag_user_prompt` | 33 | `(question, passages) -> str` | `"Context passages:\n<numbered passages>\n\nQuestion: <question>"`. |

**Design rationale.** The agent prompt names the tool exactly as it is registered (docstring, lines 4-5); a
prompt that named a different tool would leave the model guessing. A single fixed abstention sentence
makes abstentions machine-recognisable (`text.is_abstention`), which the lexical metrics use to skip cases instead
of scoring them as wrong.

**Tests.** `test_providers_pipeline.py::test_openai_generator_records_tokens_and_prompt` asserts that the user
message contains `"[1] Bees collect nectar."`; the extractive-generator tests compare against `ABSTAIN_ANSWER`.

**Limitations.** The agent prompt's wording (including its lower-case opening) is short and has not been tuned. Prompts are not configurable and not recorded in the run configuration, so
editing them changes results without a visible configuration difference between runs.

---

## V.13 `src/rag_workbench/providers.py` — answer generators

**Path:** `src/rag_workbench/providers.py` (119 lines).

**Purpose.** Turn a question plus retrieved passage texts into an answer. Two generators share the `Generator`
protocol: an offline extractive baseline (explicitly *not* a language model, docstring lines 3-7) and an OpenAI
chat model via LangChain.

**Imports.** Standard library `random`, `dataclasses`, `typing.Protocol`; internal `.errors`
(`ProviderError`, `classify_openai_error`), `.prompts` (`ABSTAIN_ANSWER`, `RAG_SYSTEM_PROMPT`, `rag_user_prompt`),
`.text` (`content_tokens`, `split_sentences`). Lazy: `langchain_openai.ChatOpenAI` (constructor, line 95),
`langchain_core.messages` (in `generate`, line 104).

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `GeneratorOutput` | 25 | dataclass `(answer, prompt_tokens=None, completion_tokens=None)` | Generator result. |
| `Generator` | 31 | `Protocol`: `model: str`; `generate(question, passages) -> GeneratorOutput` | Interface used by `RAGPipeline`. |
| `ExtractiveGenerator` | 37 | `(idf, *, max_sentences=2, failure_rate=0.0, seed=0)` | Offline baseline; `model = "offline-extractive"`. |
| `ExtractiveGenerator.generate` | 68 | `(question, passages) -> GeneratorOutput` | Select best-matching sentences. |
| `OpenAIChatGenerator` | 91 | `(*, model, api_key, base_url=None, timeout_s=60.0)` | OpenAI chat model, temperature 0. |
| `OpenAIChatGenerator.generate` | 103 | `(question, passages) -> GeneratorOutput` | One chat call. |

### `ExtractiveGenerator`

*Construction* (47-58): `max_sentences < 1` raises `ValueError`. `default_idf = max(idf.values(), default=1.0)`
(55): a question term that never occurs in the document is treated as maximally rare.

*Generation* (68-88):

1. `_maybe_fail(question)` (60-66): when `failure_rate > 0`, draws `random.Random(f"{seed}:{question}").random()`
   and raises `ProviderError("Injected offline failure (offline_failure_rate > 0)")` if the draw is below the
   rate. A string seed makes the outcome depend only on seed and question, so a rerun fails on the same cases.
   The *non-transient* class is used on purpose: retrying a deterministic failure would only add back-off delay
   (comment, lines 53-54).
2. Every passage is split into sentences; each sentence's weight is the sum of IDF values of the *distinct*
   content terms it shares with the question (73-78). The running `order` index records each sentence's
   position across the passage list, which arrives in rank order.
3. Sentences with positive weight are sorted by `(-weight, order)` and the top `max_sentences` kept (79). If none
   remains, the answer is `ABSTAIN_ANSWER` (80-81) — also the result for an empty passage list.
4. The selected sentences are joined **in their original order** (72), so the answer reads as document text
   rather than as a ranked list.

No token counts are reported (`prompt_tokens` stays `None`), so cost is unknown rather than zero.

### `OpenAIChatGenerator`

The constructor (94-101) creates `ChatOpenAI(model=..., temperature=0, api_key=..., base_url=..., timeout=timeout_s,
max_retries=0)`. The client's own retry loop is disabled because the runner performs retries in one observable
place and records the attempt count (comment, lines 83-84). `generate` (103-119) sends
`[SystemMessage(RAG_SYSTEM_PROMPT), HumanMessage(rag_user_prompt(...))]`; any exception goes through
`classify_openai_error` and is re-raised as `ProviderError`/`TransientProviderError` when recognised (107-113). A
non-string `content` is stringified; an empty answer raises `ProviderError("Model returned an empty answer")`
(116-117). Token counts come from `response.usage_metadata` (`input_tokens`, `output_tokens`) when present.

**Configuration.** `max_answer_sentences`, `offline_failure_rate`, `seed` (RunConfig) for the extractive
generator; `generator_model`, `openai_api_key`, `openai_base_url`, `request_timeout_s` for the OpenAI one — all
passed in by `pipeline.build_pipeline`.

**Tests.** `tests/test_providers_pipeline.py`: `test_extractive_generator_selects_matching_sentences_in_order`,
`test_extractive_generator_abstains_without_overlap`, `test_failure_injection_is_deterministic` (rate 1.0 always
raises; rate 0.5 with seed 3 gives identical, mixed outcomes on two passes),
`test_openai_generator_records_tokens_and_prompt` and `test_openai_generator_errors` (both replace `_llm` with a
scripted object, so no network is used).

**Limitations.** Sentence selection inherits `split_sentences`' rules: a block without terminal punctuation, such
as the example document's title chunk `p1-b1`, counts as one sentence and can be copied into an answer (the
example run's answer to `a2` begins "Honeybees: Life Inside the Colony Honeybees are social insects …"). The
baseline also never abstains when any sentence shares a content term with the question, which on the example
data means it answers all four unanswerable questions. The extractive baseline can only copy sentences, so its lexical groundedness is about 1.0 by
construction (the Settings page states this) and its F1 against paraphrased references is low. It is a lower
bound and a test vehicle, not a competitor to an LLM.

---

## V.14 `src/rag_workbench/pipeline.py` — pipelines and the pipeline factory

**Path:** `src/rag_workbench/pipeline.py` (178 lines).

**Purpose and responsibilities.** Define the two answering pipelines and assemble the right one from a
`RunConfig`. The module's central invariant (docstring, lines 5-14): the context recorded for evaluation is the
context the generator actually saw — in `rag` mode by construction, in `agent` mode by capturing every tool
result per question. The agent's self-reported context is stored only as `model_context_claim` and never scored:
a model's description of its evidence is not evidence, so faithfulness and context metrics are computed against
what the retriever actually returned. The capture list is local to each call rather than shared state, so
concurrent questions on the thread pool cannot see each other's chunks.

**Imports.** Standard library `time`, `dataclasses`, `typing.Protocol`; internal `.config` (`ConfigError`,
`Settings`), `.documents.load_chunks`, `.errors` (`ProviderError`, `classify_openai_error`), `.models`
(`Chunk`, `Generation`, `RetrievedChunk`, `RunConfig`), `.prompts.AGENT_SYSTEM_PROMPT`, `.providers`,
`.retrieval`. Lazy: `langchain_openai.ChatOpenAI` (constructor), and inside `AgentRAGPipeline.answer`:
`langchain.agents.create_agent`, `langchain.tools.tool`, `langchain_core.messages`, `pydantic`.

### Public interface

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `Pipeline` | 34 | `Protocol`: `model: str`; `answer(question) -> Generation` | What the runner calls. |
| `RAGPipeline` | 42 | dataclass `(retriever, generator, k)`; `model` property (45) | Retrieve top-k, then generate from exactly those chunks. |
| `RAGPipeline.answer` | 51 | `(question) -> Generation` | |
| `AgentRAGPipeline` | 60 | `(retriever, *, k, model, api_key, base_url=None, timeout_s=60.0)` | LangChain tool-calling agent. |
| `AgentRAGPipeline.answer` | 73 | `(question) -> Generation` | |
| `build_retriever` | 126 | `(config, chunks, settings) -> Retriever` | BM25 or embeddings. |
| `build_pipeline` | 138 | `(config, settings, chunks=None) -> Pipeline` | The factory the runner uses. |
| `_require_key` | 167 | `(settings, what) -> None` | `ConfigError` if no API key. |

### `RAGPipeline.answer` (51-57)

Starts a `perf_counter` timer, retrieves `k` chunks for the question, passes their texts to the generator, and
returns a `Generation` with `contexts` = the retrieved chunks, `context_source="retriever"`, the generator's model
and token counts, `retrieval_queries=[question]`, and `latency_ms` covering retrieval plus generation.

### `AgentRAGPipeline`

*Construction* (63-71): stores the retriever and `k`; creates a `ChatOpenAI` client with temperature 0 and
`max_retries=0` (runner-level retries, as in V.13).

*`answer`* (73-123), step by step:

1. Two lists local to this call, `captured` and `queries` (79-80). Because they are created per call, concurrent
   questions on the thread pool never share state.
2. The tool `collecting_info(query)` (82-89) is a closure defined for this call: it retrieves `k` chunks for the
   **model-chosen** query, records the query, appends hits whose `chunk_id` was not already captured, and returns
   the chunk texts joined by blank lines to the model. Its docstring is the tool description the model sees.
3. A pydantic `Answer(answer, context)` model (91-93) is the structured response format; its `context` field
   is what ends up in `model_context_claim`.
4. `create_agent(model=self._llm, tools=[collecting_info], system_prompt=AGENT_SYSTEM_PROMPT,
   response_format=Answer)` (95-96) builds the agent; `agent.invoke({"messages": [HumanMessage(question)]})` runs
   it (98-104). Exceptions are classified with `classify_openai_error`; unrecognised ones propagate unchanged.
   Latency covers the whole agent loop.
5. A missing `structured_response` or an empty answer raises `ProviderError("Agent returned no structured
   answer")` (106-108).
6. Token usage is summed over every `AIMessage` that carries `usage_metadata` (109-116); if none does, both
   counts are `None` rather than 0.
7. Captured chunks are re-ranked 1..n in capture order (117-118): the per-call retrieval rank is replaced by the
   order in which the agent obtained them.
8. The `Generation` has `contexts=captured`, `context_source="agent_tool"`, `retrieval_queries=queries` and
   `model_context_claim=structured.context` (119-123).

If the agent answers without calling the tool, `captured` is empty; context-requiring metrics then report
`skipped` ("no retrieved context for this case") rather than judging the answer against nothing.

### `build_retriever` (126-132) and `build_pipeline` (138-161)

`build_retriever` returns `BM25Retriever(chunks)` for `bm25`; for `embedding` it requires a key and returns an
`EmbeddingRetriever` with `config.embedding_model or settings.embedding_model`, the key, the base URL, and the
run's timeout and retry count.

`build_pipeline` loads chunks itself if none are passed (134-135; the runner always passes them), builds the
retriever, then:

| provider | pipeline | Result |
|---|---|---|
| `offline` | `agent` | `ConfigError("The agent pipeline needs a tool-calling LLM; ...")` (139-140) |
| `offline` | `rag` | `RAGPipeline(retriever, ExtractiveGenerator(idf, ...), k)`; the IDF table comes from the BM25 retriever, or from a throw-away `BM25Retriever(chunks)` when the embedding retriever is used (141) |
| `openai` | `agent` | `AgentRAGPipeline(retriever, k, model, key, base_url, timeout)` (149-151) |
| `openai` | `rag` | `RAGPipeline(retriever, OpenAIChatGenerator(...), k)` (152-154) |

For `openai`, `_require_key` runs first (156) and the model is `config.generator_model or
settings.generator_model` (158). With `build_retriever`, the possible `ConfigError`s are: agent with the offline
provider; OpenAI provider without a key; embedding retriever without a key. `_require_key`'s message names what
needs the key and suggests the offline provider with BM25.

**Configuration.** `provider`, `pipeline`, `retriever`, `k`, `generator_model`, `embedding_model`,
`max_answer_sentences`, `offline_failure_rate`, `seed`, `request_timeout_s`, `max_retries` from `RunConfig`;
`openai_api_key`, `openai_base_url`, `generator_model`, `embedding_model`, `max_document_bytes` from `Settings`.

**Error behaviour.** `ConfigError` for invalid combinations (raised during `runner.prepare`, before any run row
exists). At answer time: `ProviderError`/`TransientProviderError` for classified failures, other exceptions
unchanged — the runner turns all of them into case errors.

**Tests.** `tests/test_providers_pipeline.py`: `test_rag_pipeline_evaluates_exactly_the_retrieved_chunks`,
`test_build_pipeline_validation` (each `ConfigError` path), `test_build_openai_pipelines_with_key` (constructing
clients makes no network call), `test_agent_pipeline_captures_real_tool_output_not_self_report` (a scripted
`GenericFakeChatModel` subclass that accepts `bind_tools` first calls `collecting_info`, then returns an `Answer`
whose `context` is "I invented this context."; the test asserts that the recorded contexts are exactly the chunk
the tool returned for the model's query "forager collect nectar", `p1-b2`, that `context_source == "agent_tool"`, and that the self-report survives only as `model_context_claim`; token usage is summed over both model messages, 250/30).

**Limitations.** The agent is rebuilt for every question (the tool is a per-call closure), which adds a little
setup time per case. How LangChain surfaces an exception raised *inside* the tool (for example an embedding
failure) depends on its agent tool-error handling and was not verified for this book. Agent runs are not
deterministic even at temperature 0, because the model chooses the queries and the number of tool calls.

---

## V.15 `src/rag_workbench/metrics/__init__.py` — metric registry

**Path:** `src/rag_workbench/metrics/__init__.py` (57 lines).

**Purpose.** The single registry of metric names, the default metric selections, name/key validation, and the
factory that turns names into `Metric` objects for a run.

**Imports.** Internal `..config` (`ConfigError`, `Settings`), `.base` (`Metric`, `MetricInput`, `MetricSkipped`,
`MetricSpec`), `.judge` (`JUDGE_SPECS`, `build_judge_metric`), `.lexical.LEXICAL_METRICS`. Importing the package
does **not** import DeepEval: `judge.py` imports it only inside functions.

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `METRIC_SPECS` | 10 | `dict[str, MetricSpec]` | Lexical specs followed by judge specs; insertion order is the display order everywhere (`ragwb metrics`, Settings page, New evaluation multiselect). |
| `DEFAULT_OFFLINE_METRICS` | 12 | `["token_f1", "rouge_l", "context_recall", "groundedness"]` | Default for offline runs, the UI, `ragwb score` and the example runs. `exact_match` is excluded (too strict for sentence-length answers). |
| `DEFAULT_JUDGE_METRICS` | 13 | `list(JUDGE_SPECS)` | Added to the offline defaults by the CLI when `--provider openai` and no `--metrics` are given. |
| `validate_metric_names` | 16 | `(names, settings=None) -> None` | Raise `ConfigError` for unknown names, an empty list, or judge metrics without a key. |
| `build_metrics` | 29 | `(names, settings, *, judge_model=None, timeout_s=None) -> list[Metric]` | Validate, then build in the given order. |

**Logic.** `validate_metric_names` (16-26) checks unknown names first (the message lists all available names),
then emptiness, then — only when `settings` is given — whether any selected spec has `requires_openai` while
`settings.has_openai_key` is false. `build_metrics` (29-42) calls the validator, then returns the shared
`LEXICAL_METRICS` instances for lexical names (they are stateless, so sharing them across threads and runs is
safe) and a new `JudgeMetric` for each judge name, with `judge_model or settings.judge_model` and
`timeout_s or settings.request_timeout_s`.

**Callers.** `runner.EvaluationRunner.prepare` (validation and building via the injectable `metrics_factory`),
`cli.cmd_score`, the UI (specs only), `reporting.metric_label`.

**Tests.** `test_metrics.py::test_registry_and_validation` (registry equals the union of both families; the three
`ConfigError` messages; `build_metrics` keeps order and returns a `JudgeMetric` for `correctness` when a key is
configured).

---

## V.16 `src/rag_workbench/metrics/base.py` — the metric contract

**Path:** `src/rag_workbench/metrics/base.py` (98 lines).

**Purpose.** Define what a metric is and implement the one wrapper (`Metric.evaluate`) that all metrics share, so
that requirement checks, skip semantics, error capture, range checking and pass/fail are identical for lexical and
judge metrics. The three-status contract is stated in the docstring (lines 3-9): `ok` (score in [0, 1], `passed =
score >= threshold`), `skipped` (a required input is absent), `error` (the computation raised). Skipped and errored
results are excluded from means, never counted as zero.

**Imports.** Standard library `logging`, `dataclasses`, `typing`; internal `..models.MetricResult`.

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `SCORE_TOLERANCE` | 23 | `1e-9` | How far outside [0, 1] a score may be and still count as floating-point noise (the comment cites GEval returning `1.0000000000000002`). |
| `Family` | 25 | `Literal["lexical", "semantic", "llm_judge"]` | Metric family (`semantic` added in release 1.2). |
| `MetricInput` | 29 | frozen dataclass `(question, answer, expected_answer, contexts: list[str])` | What every metric receives. Contexts are texts only. |
| `MetricSpec` | 37 | frozen dataclass `(name, label, family, description, default_threshold, requires_reference=False, requires_context=False, requires_openai=False, requires_local_model=False)` | Static description of a metric. |
| `MetricSkipped` | 48 | `Exception` subclass | Raised inside a scorer to report `skipped` with a reason. |
| `Scorer` | 53 | `Callable[[MetricInput], tuple[float, str]]` | A plain scoring function returning `(score, reason)`. |
| `Metric` | 57 | `(spec, scorer=None)` | A named scorer plus its requirements. |
| `Metric.name` | 65 | property | `spec.name`. |
| `Metric.score` | 68 | `(inp, threshold) -> tuple[float, str]` | Calls the scorer; subclasses without one override it (`JudgeMetric`). `NotImplementedError` if neither. |
| `Metric.evaluate` | 74 | `(inp, threshold=None) -> MetricResult` | The shared wrapper. |

**`Metric.evaluate` step by step (74-96).**

1. `threshold` defaults to `spec.default_threshold` (75).
2. If the spec requires a reference and `inp.expected_answer` is falsy → `skipped`, reason "no expected_answer for
   this case" (76-78). If it requires context and `inp.contexts` is empty → `skipped`, "no retrieved context for this
   case" (79-81). These checks run before any computation, so a judge metric never makes an API call for a case it
   cannot score.
3. `self.score(inp, threshold)` is called. `MetricSkipped` → `skipped` with the exception text as reason (84-85).
   Any other `Exception` is logged at WARNING and becomes `error` with reason `"<Type>: <message>"` truncated to 500
   characters (86-89) — one failing metric never aborts a case or a run.
4. Range check (92-96): the score is converted with `float()`. A value outside
   `[-SCORE_TOLERANCE, 1 + SCORE_TOLERANCE]` is treated as a scorer bug, not as a very low or high score, and
   becomes `error` with reason `"score <value> outside [0, 1]"` (92-94); NaN fails the comparison and is reported the
   same way. Only a value within the tolerance is clamped to [0, 1] (95), which absorbs floating-point noise without
   hiding real out-of-range results (and keeps the `MetricResult._bounded` validator from rejecting `1.0000000000000002`).
5. `ok` result with `passed = score >= threshold` (96-97). The threshold is always stored on the result, including
   for skipped and errored outcomes.

The `float()` conversion sits outside the `try`, so a scorer that returns a non-numeric score raises from
`evaluate`; in a run, `EvaluationRunner.evaluate_case` catches that and records the whole case as an "Internal ..."
error (V.21).

**Design rationale.** Putting requirement checks in the spec rather than in each scorer keeps the scorers pure
functions and lets the UI and CLI describe each metric's needs from data (`ragwb metrics`, the Settings table).
The explicit `skipped` status is what makes missing references and abstentions visible as counts instead of zeros.

**Tests.** `test_metrics.py::test_skips_are_not_zero`, `test_custom_threshold_and_errors_are_captured` (a custom
threshold is respected; a scorer raising `RuntimeError` yields `error` with the message and `score is None`),
`test_judge_metric_requirements_and_failures`, `test_out_of_range_scores_are_errors_but_float_noise_is_absorbed`
(a scorer returning 5.0 gives `error` with "outside [0, 1]" and no score; `1.0000000000000002` is stored as 1.0).

**Limitations.** `passed` is always derived from this wrapper's comparison, never from a library's own success
flag. Thresholds are inclusive (`>=`), which matters for `exact_match` (threshold 1.0).

---

## V.17 `src/rag_workbench/metrics/lexical.py` — offline lexical metrics

**Path:** `src/rag_workbench/metrics/lexical.py` (121 lines).

**Purpose.** Five deterministic, offline metrics that measure surface overlap, not meaning (docstring, lines 3-6):
useful as regression signals and sanity checks, misleading as judgements of correctness.

**Imports.** Standard library `collections.Counter`; internal `..text` (`content_tokens`, `is_abstention`,
`squad_normalize`), `.base` (`Metric`, `MetricInput`, `MetricSkipped`, `MetricSpec`).

| Name | Line | Default threshold | Needs | Definition |
|---|---:|---:|---|---|
| `exact_match` | 17 | 1.0 | reference | 1.0 if `squad_normalize(answer) == squad_normalize(reference)`, else 0.0. |
| `token_f1` | 23 | 0.5 | reference | SQuAD token F1 over normalised tokens, multiset overlap. |
| `_lcs_length` | 39 | — | — | Longest common subsequence length, O(len(a)·len(b)) time, one rolling row of memory. |
| `rouge_l` | 52 | 0.5 | reference | ROUGE-L F1 = 2PR/(P+R) with P = LCS/len(answer), R = LCS/len(reference). |
| `context_recall` | 63 | 0.7 | reference, context | Distinct reference content terms found in the joined contexts / distinct reference content terms. |
| `groundedness` | 84 | 0.7 | context | Distinct answer content terms found in the joined contexts / distinct answer content terms. |
| `LEXICAL_METRICS` | 103 | — | — | `dict[str, Metric]` built from five `Metric(MetricSpec(...), scorer)` pairs (lines 106-118). |

**Internal details.**

* `token_f1` (23-36) keeps stop words (SQuAD practice) because it uses `squad_normalize(...).split()`, not
  `content_tokens`. An answer or reference that is empty after normalisation scores 0.0 with an explanatory reason
  (27-28); no overlap scores 0.0 "no shared tokens". The reason string reports precision, recall and the overlap
  count — the explanation shown in the case detail view.
* `rouge_l` (52-60) returns 0.0 "no common subsequence" when the LCS is empty. Word order matters:
  `"nectar collect bees"` vs `"bees collect nectar"` has LCS 1, score 1/3 (asserted in
  `test_rouge_l_hand_computed`).
* `context_recall` (63-81) raises `MetricSkipped` when the **reference** is itself an abstention — an unanswerable
  case, whose reference words say nothing about retrieval (69-71) — and when the reference has no content terms
  (73-74). The reason lists up to eight missing terms.
* `groundedness` (84-100) raises `MetricSkipped` when the **answer** abstains (90-91) or has no content terms. The
  reason lists up to eight unsupported terms.
* Both content-term metrics use **sets** of stemmed, stop-word-free tokens, so repetition does not inflate them.

**Inputs/outputs.** `MetricInput` in, `(score, reason)` out; `Metric.evaluate` wraps them into `MetricResult`.

**Tests.** `tests/test_metrics.py`: `test_exact_match`, `test_token_f1_hand_computed` (P = 3/5, R = 1 → 0.75,
with `and` counted), `test_token_f1_counts_multiset_overlap` (`"pollen pollen pollen"` vs `"pollen nectar"` → 0.4),
`test_rouge_l_hand_computed`, `test_context_recall_and_groundedness` (3/4 each, with the missing/unsupported term
named in the reason), `test_skips_are_not_zero` (missing reference, empty context, abstaining answer, stop-word-only
reference, unanswerable reference). `cli.cmd_score` gives the same functions an interactive front end.

**Design rationale and limitations.** Lexical metrics make the full system runnable and testable without network
access or cost, and give deterministic numbers for regression checks. Their failure modes are
documented in the module and the UI: a correct paraphrase scores low on F1/ROUGE-L; a fluent wrong answer that
reuses the reference answer's words scores high; `groundedness` of the extractive baseline is about 1.0 by construction;
content-term measures ignore negation (V.8).

---

## V.18 `src/rag_workbench/metrics/judge.py` — LLM-as-a-judge metrics

**Path:** `src/rag_workbench/metrics/judge.py` (135 lines).

**Purpose.** Four DeepEval-backed metrics scored by an OpenAI judge model: answer relevancy, faithfulness,
context relevancy and correctness (GEval). The docstring is explicit about their status: model opinions under a
rubric, not ground truth; they vary between judge models and, less, between repeated calls (lines 7-8).

**Imports.** Standard library `logging`, `random`, `time`, `typing`, `collections.abc.Callable`; internal `..errors.TransientProviderError`, `..errors.classify_openai_error`, `.base`. Lazy (inside
functions): `deepeval.test_case.LLMTestCase` (line 79), `deepeval.models.OpenAIModel` (106), `deepeval.metrics`
and `deepeval.test_case.SingleTurnParams` (114-115).

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `CORRECTNESS_CRITERIA` | 25 | `str` | GEval criteria: "Determine whether the actual output is factually correct based on the expected output". |
| `JUDGE_SPECS` | 27 | `dict[str, MetricSpec]` | The four specs, all with default threshold 0.7 and `requires_openai=True`. |
| `JudgeMetric` | 48 | `Metric` subclass, `(spec, factory, *, max_retries=2, retry_base_delay_s=1.0, sleep=time.sleep)` | `factory(threshold)` returns a fresh DeepEval metric object. |
| `JudgeMetric.score` | 64 | `(inp, threshold) -> ScoreOutcome` | Retry loop (exponential back-off plus jitter) around `_measure` for transient provider errors (release 1.1). |
| `JudgeMetric._measure` | 78 | `(inp, threshold) -> (score, reason, cost)` | One synchronous DeepEval measurement; also returns DeepEval's `evaluation_cost` when it is a number. |
| `build_judge_metric` | 98 | `(name, *, model, api_key, base_url=None, timeout_s=60.0, max_retries=2, retry_base_delay_s=1.0) -> JudgeMetric` | Create a judge metric for one of the four names. |

| Metric | DeepEval class | Extra requirement | Uses |
|---|---|---|---|
| `answer_relevancy` | `AnswerRelevancyMetric` | — | question, answer |
| `faithfulness` | `FaithfulnessMetric` | context | answer, retrieved context |
| `context_relevancy` | `ContextualRelevancyMetric` | context | question, retrieved context |
| `correctness` | `GEval(name="Correctness", criteria=CORRECTNESS_CRITERIA, evaluation_params=[ACTUAL_OUTPUT, EXPECTED_OUTPUT])` | reference | answer, reference |

**How a judgement is made.** `JudgeMetric.score` (64-76) calls `_measure` and, on a `TransientProviderError`, sleeps
`base × 2^(attempt−1)` plus up to `base` seconds of jitter and tries again, up to `max_retries` times (Part XIII §141.2).
`_measure` (78-95) builds an `LLMTestCase(input=question,
actual_output=answer, expected_output=reference, retrieval_context=contexts or None)`, obtains a **new** DeepEval
metric from the factory, and calls `metric.measure(test_case)`. Exceptions are mapped by `classify_openai_error`
when they are OpenAI errors and re-raised (84-90); `Metric.evaluate` then records them as `error`. A `None` score
raises `RuntimeError("judge returned no score")` (91-92), also recorded as `error`. The reason is stripped and
truncated to 2,000 characters.

`build_judge_metric` (98-129) raises `KeyError` for non-judge names. Its inner `judge_model()` (106-112) constructs a
`deepeval.models.OpenAIModel(model, api_key, temperature=0, timeout)` plus `base_url` when configured; `factory`
(114-128) calls it **every time**, so each measurement gets its own model object and metric object. Common
arguments are `threshold`, `model`, `async_mode=False` and `include_reason=True`; `include_reason` is removed for
GEval (line 125).

**Design rationale.** Fresh objects per case: DeepEval metric objects hold per-measurement state (score, reason),
so sharing one across worker threads would be unsafe (docstring, lines 3-5). Synchronous mode makes each failure
attributable to one case. The judge model is explicit and recorded in the run configuration (`cli.build_config`
records it only when a judge metric runs). The correctness criteria (line 25) ask only for factual agreement
between the answer and the reference, so a correct paraphrase is not penalised for wording — the gap the lexical
reference metrics leave open.

**Configuration.** `judge_model` (RunConfig or Settings), `openai_api_key`, `openai_base_url`,
`request_timeout_s`.

**Error behaviour.** A judge failure never fails the case: the case stays `ok` with that metric `error`. There is
**bounded retry** for judge calls since release 1.1: a transient error (rate limit, timeout, connection, 5xx) is retried
with back-off and jitter up to the run's `max_retries`; only after the budget is spent, or for a permanent error, does
it become a metric error.

**Tests.** `tests/test_metrics.py`: `test_judge_metric_uses_fresh_metric_and_threshold` (a fake DeepEval metric
returns 0.82 with threshold 0.9 → `ok`, `passed False`, reason stripped; a second evaluation builds a second object
with the default threshold 0.7), `test_judge_metric_requirements_and_failures` (missing reference → skipped;
`openai.RateLimitError` → `error` mentioning `RateLimitError`; `None` score → `error`),
`test_build_judge_metric_constructs_deepeval_objects_without_network` (real DeepEval objects are constructed with
the right thresholds and class, no API call).

**Limitations.** Judge cost is whatever DeepEval reports as `evaluation_cost` (stored as `MetricResult.cost_usd`, summed
in `RunSummary.total_judge_cost_usd`) and has never been compared with a real invoice; judge token counts and latency are
not measured. DeepEval's internal behaviour (prompting, any retries it performs) is outside this module's control. Judge scores
are not reproducible in the strict sense.

---

## V.19 `src/rag_workbench/aggregate.py` — summaries and paired comparison

**Path:** `src/rag_workbench/aggregate.py` (179 lines).

**Purpose.** Turn per-case results into a `RunSummary`, and compare two runs case by case. The rules in the
docstring (lines 3-5) are the statistical contract of the product: missing values are excluded and counted, never
imputed as zero; confidence intervals are percentile-bootstrap intervals of the mean with a fixed seed, so the same
results always give the same interval.

**Imports.** Standard library `math`, `random`, `statistics`, `dataclasses`; internal `.models` (`CaseResult`,
`MetricSummary`, `RunSummary`).

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `BOOTSTRAP_RESAMPLES`, `CONFIDENCE`, `BOOTSTRAP_SEED` | 18-20 | `2_000`, `0.95`, `12345` | Bootstrap parameters. |
| `bootstrap_ci` | 23 | `(values, *, resamples=2000, confidence=0.95, seed=12345) -> (low, high) \| (None, None)` | Percentile bootstrap CI of the mean. |
| `percentile` | 37 | `(values, q) -> float \| None` | Linear-interpolation percentile, `q` in [0, 100]. |
| `summarize_metric` | 47 | `(name, results, threshold) -> MetricSummary` | One metric across a run. |
| `summarize_run` | 75 | `(results, metric_names, thresholds) -> RunSummary` | Whole-run summary. |
| `PairedComparison` | 131 | dataclass `(metric, n_pairs, mean_a, mean_b, mean_diff, ci_low, ci_high, wins, ties, losses)` | B versus A on shared cases. |
| `PairedComparison.significant` | 146 | property → `bool` | True when the CI of the paired difference excludes zero. |
| `_case_key` | 151 | `(case) -> str` | Question lower-cased, whitespace collapsed. |
| `paired_comparison` | 164 | `(results_a, results_b, metric, *, tie_tolerance=1e-9) -> PairedComparison` | Paired analysis. |

**`bootstrap_ci` (23-34).** Fewer than two values → `(None, None)`. Otherwise a `random.Random(seed)` draws
`resamples` samples of size `n` with replacement (`rng.choices`), computes their means, sorts them, and returns
`means[floor(alpha * R)]` and `means[ceil((1 - alpha) * R) - 1]` with `alpha = 0.025` — the 51st and 1,950th of
2,000 sorted means. Because the seed is fixed and the input order is the case order, identical results always give
identical intervals.

**`percentile` (37-44).** Sorted values, position `(n - 1) * q / 100`, linear interpolation between neighbours;
`None` for an empty list. Used for p95 latency.

**`summarize_metric` (47-72)** classifies each case:

| Case situation | Counted as |
|---|---|
| case `status == "error"` | `n_error` |
| case ok but metric absent from `case.metrics` | `n_skipped` |
| metric `ok` with a score | scored (and `n_passed` if `passed`) |
| metric `skipped` | `n_skipped` |
| metric `error` | `n_error` |

Mean (`statistics.fmean`), median, sample standard deviation (only with more than one score), min, max, CI and
`pass_rate = n_passed / n_scored` are computed over scored values only; all are `None` when nothing was scored.

**`summarize_run` (75-92).** Counts cases, `ok` cases and errors; summarises each requested metric with its
threshold; mean and p95 latency over `ok` cases; token totals and total cost as sums over cases that report them,
or `None` when no case does (so "unknown" is never shown as 0).

**`paired_comparison` (164-179).** Builds `{question_key: score}` for each run, keeping only scored cases (120-121),
intersects the keys (sorted, so the bootstrap input order is deterministic), computes `diffs = B - A`, the
bootstrap CI of the differences, means of A and B over the paired cases only, and win/tie/loss counts with
`tie_tolerance`. Pairing by normalised question text rather than case id (docstring, line 166) lets runs over
differently-built datasets (for example with and without explicit ids) be compared on the questions they share.

**Interactions.** `runner._finish` and `archive.import_bundle` (which recomputes every imported summary) call
`summarize_run`; `reporting.comparison_dataframe` and the Compare page
call `paired_comparison`.

**Tests.** `tests/test_aggregate.py`: `test_missing_values_are_excluded_not_zeroed` (`(n_scored, n_skipped,
n_error) == (2, 1, 2)`), `test_empty_summary`, `test_bootstrap_is_deterministic_and_brackets_mean`,
`test_percentile`, `test_paired_comparison_matches_by_question_text`, `test_paired_comparison_significance_flag`.
`test_archive_reporting.py::test_export_import_round_trip` and `test_bundle_summary_is_recomputed_not_trusted`
check that the summary recomputed by `summarize_run` on import equals the original run's.

**Limitations.** The CI reflects sampling over these questions, not judge noise or generation randomness (the
Results page caption says so). With 20 cases, intervals are wide. Duplicate questions within one run collapse to
one key in pairing (the last one wins). The percentile bootstrap is slightly anti-conservative for very small n; no
BCa correction or multiple-comparison adjustment is applied across metrics.

---

## V.20 `src/rag_workbench/storage.py` — SQLite run store

**Path:** `src/rag_workbench/storage.py` (205 lines).

**Purpose and responsibilities.** Persist runs and per-case results in one SQLite file (`data/runs.db`), commit
each case as soon as it is produced, keep a per-run heartbeat so that only runs whose process has really died are
recovered as `interrupted`, migrate older stores, refuse stores written by a newer schema, and report every SQLite
failure as one exception type. Because every case is committed immediately, a crash, a cancellation or a failed
API call never loses the cases that already finished.

**Imports.** Standard library `json`, `sqlite3`, `contextlib.contextmanager`, `datetime` (`datetime`,
`timedelta`), `pathlib`, `typing`; internal `.models` (`CaseResult`, `RunRecord`, `RunStatus`, `RunSummary`,
`utcnow`).

### Schema (`storage.py:26-52`, `SCHEMA_VERSION = 3`, line 26)

* `runs(id TEXT PRIMARY KEY, name, status, created_at, finished_at, config_json, dataset_sha256, document_sha256,
  n_cases INTEGER DEFAULT 0, summary_json, environment_json DEFAULT '{}', notes, heartbeat_at, tags_json DEFAULT '[]')`, plus index
  `idx_runs_created` on `created_at`.
* `case_results(run_id REFERENCES runs(id) ON DELETE CASCADE, case_id, position, status, data_json,
  PRIMARY KEY (run_id, case_id))`.

Rows store the pydantic models as JSON (`config_json`, `summary_json`, `environment_json`, `data_json`); scalar
columns duplicate the fields used for ordering and filtering (design notes, lines 3-12). Timestamps are ISO-8601
strings of UTC datetimes, so lexical order equals chronological order — `recover_interrupted` relies on this when
it compares heartbeat strings. `heartbeat_at` is internal: it is not part of `RunRecord` and `_row_to_run` does
not read it.

`STALE_AFTER_S = 15 * 60` (line 29): a `running` run with no committed case for 15 minutes is considered dead. The
comment (27-28) explains the generous value: one slow case can take several timeouts plus back-off (4 attempts × 60
s plus delays is about 5 minutes with default settings).

### Public interface

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `SCHEMA_VERSION` | 26 | `3` | Stored in `PRAGMA user_version`. |
| `STALE_AFTER_S` | 29 | `900` | Default staleness window for recovery. |
| `StorageError` | 60 | `class StorageError(RuntimeError)` | The store cannot be opened, read or written. |
| `RunStore` | 64 | `(path)` | Opens/creates/migrates the database. |
| `create_run` | 101 | `(record: RunRecord) -> None` | Insert a run row with an initial heartbeat. |
| `add_case_result` | 117 | `(run_id, result: CaseResult) -> None` | Insert one case and refresh the run's heartbeat, in one transaction. |
| `finish_run` | 127 | `(run_id, status, summary, finished_at=None) -> None` | Set final status, summary, finish time. |
| `set_tags` | 137 | `(run_id, tags: list[str]) -> None` | Replace a run's tags (release 1.2); `StorageError` if the run does not exist. |
| `set_notes` | 144 | `(run_id, notes: str \| None) -> None` | Replace or clear a run's note (release 1.2). |
| `delete_run` | 150 | `(run_id) -> bool` | Delete a run (cases cascade). |
| `recover_interrupted` | 154 | `(stale_after_s: float = STALE_AFTER_S) -> int` | Stale `running` runs → `interrupted`; returns the count. |
| `heartbeat` | 169 | `(run_id) -> datetime \| None` | Release 1.4: when a case of the run was last committed (or `None`); read by the restore guard (Part XVI §171.3). |
| `get_run` | 175 | `(run_id) -> RunRecord \| None` | |
| `list_runs` | 180 | `() -> list[RunRecord]` | Newest first (`ORDER BY created_at DESC, id`). |
| `get_case_results` | 185 | `(run_id) -> list[CaseResult]` | Ordered by `position`. |
| `count_case_results` | 191 | `(run_id) -> int` | |
| `_row_to_run` | 196 | `(row) -> RunRecord` | Decode a row. |

**Internal logic.**

* `__init__` (65-83) creates the parent directory and runs the idempotent `CREATE ... IF NOT EXISTS` script. It
  then reads `PRAGMA user_version`: a version above 3 raises `StorageError("... was created by a newer version
  (schema N)")` (72-73); then, instead of trusting the number, it reads `PRAGMA table_info(runs)` and adds whichever
  of `heartbeat_at` and `tags_json` is missing with `ALTER TABLE runs ADD COLUMN ...` (74-79; the
  `CREATE TABLE IF NOT EXISTS` does not alter an existing table); any version below 3 — including 0 for a fresh
  file — is then set to 3 (80-81). All of this runs in one transaction. `OSError` (for example `mkdir` below a file)
  and SQLite errors raised while connecting become `StorageError("Cannot open run store ...")` (82-83); an SQLite
  error inside the schema script itself (for example a file that is not a database) has already been translated by
  `_connect` into `StorageError("Run store error ...")`, which passes through unchanged.
* `_connect` (85-98) opens a **new connection per operation** with a 15-second busy timeout, `sqlite3.Row` rows and
  `PRAGMA foreign_keys = ON` (needed per connection for the cascade), and uses the connection as a transaction
  context — commit on success, rollback on exception — then closes it. Short-lived connections are safe across
  Streamlit reruns and threads (design note, line 5). It is also the single place where SQLite errors are
  translated (design note, line 10): `sqlite3.IntegrityError` is re-raised unchanged so callers can turn constraint
  violations into specific messages (93-94); every other `sqlite3.Error` raised inside the block becomes
  `StorageError("Run store error (<file name>): <message>")` (95-96).
* `create_run` (101-115) inserts the row with `heartbeat_at = utcnow()` (112) and `tags_json` (113) and maps `IntegrityError` to "A run
  with id ... already exists". `add_case_result` (117-125) inserts the case and runs `UPDATE runs SET heartbeat_at
  = now` in the same transaction (123), and maps `IntegrityError` to "Case ... already recorded for run ... (or run
  missing)" — the foreign key makes inserting a case for an unknown run an integrity error.
* `finish_run` (127-135) raises `StorageError("Run ... not found")` when no row was updated.
* `set_tags` and `set_notes` (137-148) are single `UPDATE` statements that raise `StorageError("Run ... not found")` when no row matches.
* `recover_interrupted` (154-166) computes `cutoff = now - stale_after_s` and runs one `UPDATE ... SET status =
  'interrupted', finished_at = now WHERE status = 'running' AND COALESCE(heartbeat_at, created_at) < cutoff`. Runs
  migrated from version 1 have no heartbeat and fall back to their creation time. A run that another process is
  still executing keeps committing cases, so its heartbeat stays fresh and it is left alone; this matters because
  `services.open_context` calls this method at every start-up — for example when the CLI starts while the UI is
  running an evaluation. If a run is wrongly marked (no case finished within the window), its own `finish_run`
  still sets the final status later (docstring, 157-159).

**Error behaviour.** Every method reports SQLite failures as `StorageError`: opening via `__init__`'s handler,
constraint violations via the specific messages of `create_run`/`add_case_result`, everything else via `_connect`.
`finish_run` also raises `StorageError` for an unknown run. Two narrow exceptions to the rule: `sqlite3.connect`
and the `PRAGMA foreign_keys` statement run before `_connect`'s `try`, so a failure to open the file after
construction would still surface as a raw `sqlite3.Error`; and an `IntegrityError` from a method other than the two
inserts would propagate unchanged (none of the other statements can violate a constraint). Corrupt JSON in a row
would surface as a pydantic `ValidationError` from `_row_to_run` / `get_case_results`.

**Concurrency.** The runner writes every case from the thread that consumes results (V.21), not from worker
threads, so writes are serialised in practice; the busy timeout covers a second process (for example the CLI
while the UI is open). WAL mode is not enabled.

**Tests.** `tests/test_storage.py`: `test_round_trip_preserves_unicode_and_order` (cases inserted out of order come
back ordered by position), `test_duplicates_and_missing_runs_are_errors`, `test_finish_list_delete_cascade`
(cascade verified with a raw SQL count), `test_recover_interrupted_only_touches_stale_runs` (a run whose heartbeat
is set to the year 2000 becomes `interrupted`; a freshly created `running` run and a completed run are untouched),
`test_case_commits_refresh_the_heartbeat` (an old heartbeat is refreshed by `add_case_result`, so nothing is
recovered), `test_schema_v1_store_is_migrated` (a hand-built version-1 database is upgraded to the current `user_version`,
its heartbeat-less `running` run is recovered via `created_at`, and new runs can be created),
`test_sqlite_errors_become_storage_errors` (after dropping `case_results`, `get_case_results` raises
`StorageError` matching "Run store error"), `test_newer_schema_is_refused`,
`test_unwritable_location_reports_storage_error` (accepts `StorageError` or `OSError`).

**Limitations.** Migrations are column-based (v1 and v2 stores gain the columns they lack); there is no other kind. Staleness is time-based: a run whose single case takes longer
than `STALE_AFTER_S` could be marked `interrupted` by another process's start-up before it finishes (it is then
corrected by its own `finish_run`). There is no full-text search or per-metric column (filtering happens in
pandas); the whole case list of a run is loaded into memory for display and export.

---

## V.21 `src/rag_workbench/runner.py` — evaluation orchestration

**Path:** `src/rag_workbench/runner.py` (278 lines).

**Purpose and responsibilities.** Execute one evaluation run end to end: validate everything before writing
anything, create the run row, evaluate cases sequentially or on a thread pool, retry transient generation
failures with exponential back-off and jitter, record each finished case immediately, honour cancellation, and
finish with a summary and a status that reflects what happened. The lifecycle is documented in the module
docstring (lines 3-13). The guiding rule is that one failing case or metric never aborts a run, and that every
run records what is needed to interpret and reproduce it: configuration, input hashes, package versions, latency,
tokens and (when prices are configured) cost.

**Imports.** Standard library `logging`, `platform`, `random`, `re`, `sys`, `threading`, `time`, `uuid`,
`concurrent.futures` (`FIRST_COMPLETED`, `Future`, `ThreadPoolExecutor`, `wait`), `dataclasses`,
`importlib.metadata`, `pathlib`, `typing`. Internal: `__version__`, `.aggregate.summarize_run`, `.config`
(`ConfigError`, `Settings`), `.datasets.load_dataset`, `.documents` (`file_sha256`, `load_chunks`), `.errors`
(`ProviderError`, `TransientProviderError`), `.metrics` (`METRIC_SPECS`, `Metric`, `MetricInput`, `build_metrics`,
`validate_metric_names`), `.models`, `.pipeline` (`Pipeline`, `build_pipeline`), `.storage.RunStore`.

### Public interface

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `Progress` | 49 | dataclass `(done, total, case_id, status, message)` | Passed to the progress callback after every case. |
| `ProgressCallback` | 57 | `Callable[[Progress], None]` | |
| `PreparedRun` | 61 | dataclass `(config, cases, pipeline, metrics, thresholds, dataset_sha256, document_sha256)` | Everything validated and built, nothing written. |
| `EvaluationRunner` | 71 | `(settings, store, *, pipeline_factory=build_pipeline, metrics_factory=build_metrics, sleep=time.sleep)` | The orchestrator; factories and `sleep` are injectable for tests. |
| `prepare` | 83 | `(config) -> PreparedRun` | Phase 1: validation and construction. |
| `run` | 102 | `(config, progress=None, cancel=None) -> RunRecord` | `prepare` then `execute`. |
| `execute` | 107 | `(prepared, progress=None, cancel=None) -> RunRecord` | Phases 2-4. |
| `evaluate_case` | 184 | `(prepared, case, position) -> CaseResult` | One case; never raises. |
| `new_run_id` | 265 | `(name) -> str` | `YYYYmmdd-HHMMSS-<slug>-<6 hex>`. |
| `environment_info` | 270 | `() -> dict` | Versions recorded with each run. |

Private: `_finish` (145), `_iter_results` (152), `_evaluate_case` (217), `_generate_with_retries` (234),
`_cost` (258); `_TRACKED_PACKAGES` (45).

### `prepare` (83-99) — no side effects

1. `validate_metric_names(config.metrics, settings)` (84): unknown metrics, empty selection, judge metrics
   without a key.
2. Thresholds: any key not in `METRIC_SPECS` or value outside [0, 1] → `ConfigError("Invalid threshold(s): ...")`
   (85-87).
3. `load_dataset` with the Settings limits (89-90) → `DatasetError` on any validation error; then truncation to
   `config.limit` (91-92).
4. `load_chunks` with `max_document_bytes` (93) → `DocumentError`.
5. `pipeline_factory(config, settings, chunks)` (94) → `ConfigError` for invalid provider/pipeline/retriever/key
   combinations. No network call happens here (lazy clients, lazy embedding index).
6. `metrics_factory(config.metrics, settings, judge_model=config.judge_model, timeout_s=config.request_timeout_s)`
   (95-96).
7. Effective thresholds: the configured value or the spec default, for every metric (97).
8. SHA-256 of the dataset and document files (99).

Because all of this precedes `store.create_run`, a configuration error never leaves a half-created run behind
(`test_validation_happens_before_a_run_is_created` asserts `store.list_runs() == []` after four failing
configurations). The UI calls `prepare` separately so it can show "Configuration rejected" before starting the
progress bar.

### `execute` (107-143)

1. Creates a `RunRecord` with a fresh id, status `running`, `created_at`, and a `config` that is
   `config.model_dump(mode="json")` **overridden** with the effective `thresholds` and
   `generator_model = prepared.pipeline.model` (113-114) — so an offline run records `offline-extractive`, and an
   OpenAI run records the model actually used even when the config left it `None`. Hashes, `n_cases` (after
   `limit`), `environment_info()` and notes are stored; `store.create_run` writes the row (117).
2. Iterates `_iter_results`; each result is written with `store.add_case_result` **before** the progress callback
   runs (125-129), so a crash or a stop inside the callback never loses a finished case.
3. If the cancel event is set after the loop, status is `cancelled` (130-131).
4. Any `BaseException` during the loop — explicitly including `KeyboardInterrupt` and Streamlit's `StopException`
   raised inside `progress` (comment, line 133) — sets the cancel event, finishes the run as `cancelled` with the
   results so far, logs a warning and **re-raises** (132-137). The UI's Stop button and Ctrl-C in the CLI therefore
   both leave a consistent, summarised, `cancelled` run.
5. Otherwise the status is `failed` if every case errored, `partial` if some did, `completed` if none did
   (138-140); `_finish` stores the summary (145-147, via `summarize_run`) and `get_run` returns the stored record.

The `failed` rule requires `results` to be non-empty; an empty result list cannot occur without cancellation,
because a validated dataset always has at least one case and `limit` is at least 1.

### `_iter_results` (152-181) — sequential or bounded parallel execution

* `max_workers == 1` (155-160): a plain loop that checks the cancel event **before** each case and stops
  immediately.
* `max_workers > 1` (161-181): a `ThreadPoolExecutor(thread_name_prefix="ragwb")`. It submits at most
  `2 × workers` cases up front (165-168) rather than queueing the whole dataset, so cancellation does not leave
  hundreds of queued futures. It then waits with `FIRST_COMPLETED`, yields each completed batch sorted by position
  (171-172), and refills the window from the same iterator — unless the cancel event is set (173-174), in which
  case it only drains what is already in flight. The `finally` block cancels futures that have not started (179-181)
  when the generator is closed early, for example because the consumer raised.

Results are yielded in completion order (sorted only within each batch); the store returns them ordered by
`position`, so the stored run is identical to a sequential one (`test_parallel_execution_keeps_every_case` checks
positions 1..20 and identical answers to a serial run). `future.result()` cannot raise because `evaluate_case`
never raises.

### `evaluate_case` / `_evaluate_case` (184-232)

`evaluate_case` wraps `_evaluate_case` in a catch-all: any exception (a bug in a metric wrapper, a pydantic
validation failure) is logged with traceback and turned into an `error` case with message
`"Internal <Type>: <msg>"` truncated to 500 characters (209-215). `_evaluate_case` calls
`_generate_with_retries`; if no generation was obtained it returns an `error` case with the attempt count and
error text, and **no metrics** (220-222). Otherwise it builds a `MetricInput` from the question, answer, reference
and the *texts of the recorded contexts* (223-224) — the same contexts stored on the case, which is what makes the
scored context auditable — evaluates every metric with its effective threshold (225), and returns an `ok` case
with answer, contexts, context source, latency (rounded to 3 decimals), token counts, cost, attempts and metric
results (226-232).

### `_generate_with_retries` (234-252)

| Exception from `pipeline.answer` | Behaviour |
|---|---|
| none | return `(generation, attempt, None)` |
| `TransientProviderError` | if `attempt > max_retries` → give up with `"<msg> (gave up after N attempts)"`; else sleep `retry_base_delay_s * 2**(attempt-1) + uniform(0, retry_base_delay_s)` and retry (214-220) |
| `ProviderError` (non-transient) | return the error immediately (221-222) |
| any other `Exception` | log with traceback, return `"Unexpected <Type>: <msg>"` truncated to 500 (223-225) |

So `max_retries = 3` allows up to 4 attempts. The jitter term avoids synchronised retries across worker threads
(comment, line 218). `sleep` is injected, which lets `test_transient_errors_are_retried_with_backoff` assert the
exact delays (two sleeps, in [1, 2] and [2, 3] seconds for base delay 1) without waiting.

### `_cost` (258-262), `new_run_id` (265-267), `environment_info` (270-278)

`_cost` returns `(prompt_tokens × input price + completion_tokens × output price) / 1e6` only when both prices and
both token counts are known; otherwise `None` — prices are deliberately unset by default because they change
(`config.py:60-61`). `new_run_id` slugifies the name to `[a-z0-9-]`, at most 40 characters (or `run`), and adds a
UTC timestamp and six hex characters of a UUID4: unique, sortable, and free of path separators (the UI's
`state.GENERATED_ID` regex recognises this shape). `environment_info` records the package version, Python version,
`platform.platform()` and the installed versions of `deepeval`, `langchain`, `langchain-openai`, `openai`,
`pymupdf`, `streamlit`, `pydantic` (`None` when not installed).

**Configuration.** From `Settings`: `max_dataset_bytes`, `max_cases`, `max_field_chars`, `max_document_bytes`,
`retry_base_delay_s`, `price_input_per_mtok`, `price_output_per_mtok` (plus everything the factories read). From
`RunConfig`: `metrics`, `thresholds`, `limit`, `max_workers`, `max_retries`, `judge_model`, `request_timeout_s`,
`notes`, `name`.

**Error behaviour seen by callers.** `prepare`/`run` raise `ConfigError`, `DatasetError`, `DocumentError` (all
`ValueError`s) before any write. `execute` raises `StorageError` if the store fails, and re-raises any
`BaseException` from the loop after marking the run cancelled. Provider and metric failures never propagate; they
are data in the stored run.

**Tests.** `tests/test_runner.py` (13 tests): `test_offline_end_to_end_on_the_real_dataset`,
`test_offline_runs_are_reproducible`, `test_missing_reference_skips_reference_metrics`,
`test_partial_and_failed_statuses`, `test_transient_errors_are_retried_with_backoff`, `test_retries_give_up`
(`max_retries=2` → exactly 3 calls), `test_unexpected_exceptions_do_not_abort_the_run`,
`test_cancellation_event_stops_and_records_progress` (2 of 4 cases stored, summary over 2),
`test_exception_in_progress_callback_marks_run_cancelled` (a custom `BaseException` from the callback propagates,
run `cancelled`, one case stored), `test_parallel_execution_keeps_every_case`,
`test_validation_happens_before_a_run_is_created`, `test_limit_and_cost` (2 × 7e-5 USD with prices 2 and 10),
`test_run_ids_are_safe_and_unique`. Most use `conftest.FakePipeline`, injected through `pipeline_factory`.

**Limitations.** Judge metrics are retried only for transient errors and only up to `max_retries` (V.18). A case that exceeds
`case_timeout_s` is abandoned but its daemon thread keeps running until its own HTTP timeout (Part XIII §141.1). In parallel mode a cancellation still completes the cases
already in flight (up to `2 × workers`), and they are stored. Cancellation is cooperative: a single slow model call
is not interrupted. A `StorageError` raised while finishing a cancelled run would replace the original exception (which survives only
as its `__context__`). Runs are
executed synchronously in the caller's thread (in the UI, the Streamlit script thread); there is no background job
queue.

---

## V.22 `src/rag_workbench/archive.py` — run bundles

**Path:** `src/rag_workbench/archive.py` (82 lines).

**Purpose.** Validate and import *run bundles*: single JSON files holding one run and all its case results.
`reporting.export_json` writes them; this module reads them, so runs can be moved between machines or kept as
reference results. Importing never executes anything — the file is parsed as JSON and validated against the
pydantic models before a single row is written (docstring, lines 3-5). Imported runs get status `imported`, and
the status they had when exported is kept in `config["original_status"]` (lines 7-8).

**Imports.** Standard library `json`, `logging`, `pathlib`; third-party `pydantic.ValidationError`; internal
`.aggregate.summarize_run`, `.models` (`CaseResult`, `RunRecord`), `.storage` (`RunStore`, `StorageError`).

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `BUNDLE_FORMAT`, `BUNDLE_VERSION`, `MAX_BUNDLE_BYTES` | 25-27 | `"rag-workbench-run"`, `1`, `50_000_000` | Format marker, version, size cap. |
| `BundleError` | 30 | `class BundleError(ValueError)` | Not a valid bundle. |
| `load_bundle` | 34 | `(path, *, max_bytes=50_000_000) -> tuple[RunRecord, list[CaseResult]]` | Read and validate. |
| `import_bundle` | 59 | `(store, path) -> str \| None` | Import; `None` if a run with that id exists. |

**Bundle layout.** `{"format": "rag-workbench-run", "version": 1, "run": <RunRecord as JSON>, "cases":
[<CaseResult as JSON>, ...]}`.

**`load_bundle` (34-56)** rejects, each with a `BundleError` naming the file: a missing file (36-37); a file larger
than `max_bytes`, checked with `stat()` before reading (38-39); invalid UTF-8 or JSON (40-43); a payload that is not
an object with the right `format` (44-45); an unsupported `version` (46-47); a missing `run` key or any pydantic
validation failure of the run or any case (48-52, message truncated to 500 characters); duplicate case ids (53-55),
which would otherwise violate the `case_results` primary key halfway through an import.

**`import_bundle` (59-81).** Loads the bundle; if `store.get_run(run.id)` exists it logs and returns `None`
(idempotent re-import, 62-64). Otherwise it records provenance in the config — `original_status` (kept from a
previous import if present, else the bundle's status) and `imported_from` (the file name) (65-66). The summary is
**recomputed from the cases, never taken from the file** (comment, line 67): the metric names are the config's
`metrics` (or, failing that, the bundle summary's metric names), thresholds come from the config's `thresholds`
(`None` for metrics without one), and `summarize_run` builds a fresh `RunSummary` (68-70). The run is stored as a
copy with status `imported`, `n_cases = len(cases)` and the recomputed summary (71-73). Cases are inserted one by
one; if any insert raises `StorageError`, the run is deleted again and the error re-raised (74-79): all or nothing.
Recomputing means a bundle cannot show means, CIs or pass rates that its own cases do not support — a hand-edited
or corrupted summary is simply discarded.

**Interactions.** `cli.cmd_import` (`ragwb import <bundle.json> ...`, at least one path required). The UI has no
import button; imported runs appear on every page like other runs, marked with the violet `imported` badge, and
`ui/components.provenance_warnings` shows any `config["provenance_warnings"]` a bundle carries.

**Tests.** `tests/test_archive_reporting.py` builds its bundles by exporting two real offline runs over the example
data (fixture `two_runs`, k = 1 and k = 3): `test_export_import_round_trip` (import into a second store returns the
same id, identical cases, status `imported` with `original_status == "completed"`, the recomputed context-recall
mean equals the original, and a second import returns `None`), `test_invalid_bundles_are_rejected` (parametrised:
not JSON, wrong format, wrong version, invalid run; plus missing file and size limit),
`test_duplicate_case_ids_rejected`, `test_bundle_summary_is_recomputed_not_trusted` (a bundle whose stored Token F1
mean is tampered to 0.999 imports with the true mean). `test_cli_services.py::test_import_command` covers the CLI
path, and `test_ui.py::test_results_for_imported_run_show_provenance` imports a bundle carrying a provenance warning.

**Design rationale.** Bundles are the safe interchange format: no pickle, no code, schema-validated, and imported
runs are visibly marked `imported` so they are never mistaken for runs executed on this machine.

**Limitations.** A bundle whose run id already exists is skipped, not merged or renamed; to import two different
runs with the same id one must be deleted first. The whole file is read into memory (bounded by 50 MB). Individual
case scores and metric statuses are validated against the models but are otherwise taken as recorded; only the
aggregate is recomputed.

---

## V.23 `src/rag_workbench/reporting.py` — tables and exports

**Path:** `src/rag_workbench/reporting.py` (208 lines).

**Purpose.** Build the pandas DataFrames shown by the UI and the CLI, and the three export formats: CSV (one row
per case), JSON (a re-importable run bundle, safe to share) and Markdown (a human-readable report).

**Imports.** Standard library `io`, `json`, `re`, `pathlib`; third-party `pandas`; internal
`.aggregate.paired_comparison`, `.config.PROJECT_ROOT`, `.metrics.METRIC_SPECS`, `.models`. Lazy: the `.archive` constants are imported inside
`export_json` (line 116). The code does not state the reason, and `archive` does not import `reporting`, so no
import cycle requires it; its effect is only that importing `reporting` does not load `archive` and `storage`.

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `EXPORT_FORMATS` | 17 | `("csv", "json", "md")` | Allowed formats (CLI choices, UI download buttons). |
| `metric_label` | 21 | `(name) -> str` | The spec's label, or a title-cased fallback for unknown names. |
| `run_metrics` | 26 | `(run) -> list[str]` | `config["metrics"]`, or the summary's metric names if the config has none. |
| `cases_dataframe` | 30 | `(run, results) -> DataFrame` | One row per case. |
| `summary_dataframe` | 53 | `(runs) -> DataFrame` | One row per run. |
| `comparison_dataframe` | 72 | `(run_a, results_a, run_b, results_b) -> DataFrame` | One row per shared metric. |
| `_csv_safe` | 85 | `(value)` | Formula-injection guard. |
| `export_csv` | 92 | `(run, results) -> bytes` | UTF-8 CSV with BOM. |
| `portable_path` | 103 | `(path: str) -> str` | Relative paths unchanged; absolute paths made relative to the project root when inside it, otherwise reduced to the file name. |
| `export_json` | 114 | `(run, results) -> bytes` | Run bundle without absolute local paths. |
| `_fmt`, `_md_cell` | 128, 134 | helpers | Number formatting with `—` for `None`; escape `|` and newlines for Markdown tables. |
| `export_markdown` | 140 | `(run, results, *, worst=5) -> str` | Report. |
| `export_run` | 188 | `(run, results, fmt) -> bytes` | Dispatch by format; `ValueError` for others. |
| `safe_filename` | 198 | `(text) -> str` | Filesystem-safe name. |
| `write_export` | 204 | `(run, results, fmt, out_dir) -> Path` | Write `<safe run id>.<fmt>`. |

**DataFrames.**

* `cases_dataframe` (30-50): columns `position, case_id, status, question, expected_answer, answer, error,
  latency_ms, prompt_tokens, completion_tokens, cost_usd, attempts, n_contexts, context_ids` (comma-joined chunk
  ids), then for every run metric `<m>` (score), `<m>_passed`, `<m>_status`.
* `summary_dataframe` (53-69): `run_id, name, status, created_at, provider, pipeline, retriever, k,
  generator_model, n_cases, n_errors, mean_latency_ms` plus one column per summarised metric with its mean.
* `comparison_dataframe` (72-82): for metrics present in both runs' metric lists (order of run A), the
  `paired_comparison` fields renamed for display — `paired_cases, mean_a, mean_b, diff_b_minus_a, ci_low,
  ci_high, b_better, ties, b_worse, ci_excludes_zero` — plus `metric` and `label`.

**Exports.**

* `export_csv` (92-100) neutralises spreadsheet formula injection: every non-numeric, non-boolean column is mapped
  through `_csv_safe`, which prefixes `'` to strings starting with `=`, `+`, `-`, `@`, tab or carriage return
  (prefix list, line 18). All columns are checked because pandas 3 stores text with a dedicated string dtype rather
  than `object` (comment, line 95). The bytes are encoded `utf-8-sig` so Excel detects UTF-8.
* `export_json` (114-125): `{"format", "version", "run", "cases"}` with `indent=2`, `ensure_ascii=False`; this is
  exactly what `archive.load_bundle` accepts. Because bundles are meant to be shared, `config["dataset_path"]` and
  `config["document_path"]` are rewritten with `portable_path` (116-120; comment, line 119): an absolute path inside
  the project becomes project-relative (for example `examples/datasets/honeybees.jsonl`), and an absolute path
  elsewhere — an upload in a custom data directory, a temporary file — is reduced to its file name, so a bundle
  never reveals user names or folder layouts. `portable_path` (103-111) resolves the path before comparing with
  `PROJECT_ROOT`. Only the exported copy is changed; the stored run keeps its absolute paths.
* `export_markdown` (140-185): a header block (run id, status, creation time, provider/pipeline/retriever, k,
  generator and judge models, dataset and document file names with the first 12 hex digits of their SHA-256), any
  provenance warnings as block quotes, a summary line (cases, errors, latency mean/p95, tokens, cost) and a metric
  table (mean, CI, median, pass rate, threshold, scored/skipped/errors), a "Failed cases" table, and for each metric
  the `worst` lowest-scoring cases with question and the first 200 characters of the reason. It ends with a
  reminder that judge scores are model assessments and lexical scores measure word overlap.
* `safe_filename` (198-201) replaces every run of characters outside `[A-Za-z0-9._-]` with `_`, strips leading and
  trailing `.`/`_`, falls back to `export`, and truncates to 100 characters, so `../../etc/passwd` becomes
  `etc_passwd`. `write_export` (204-208) creates the output directory and overwrites an existing file of the same
  name.

**Configuration.** None directly; the CLI defaults `out_dir` to `Settings.exports_dir`.

**Tests.** `tests/test_archive_reporting.py`: `test_csv_export_neutralises_formulas`
(`=HYPERLINK(...)` and `+1 cmd|...` are prefixed), `test_json_and_markdown_exports` (bundle fields, report title,
metric table, "Lowest ..." section, failed-case table with escaped `|` and flattened newline, `ValueError` for
`xlsx`), `test_write_export_and_safe_filenames`, `test_summary_and_comparison_frames`
(the fixture's two real runs, k = 1 and k = 3, appear in the summary frame, and the comparison frame pairs all
20 cases), `test_example_paths_become_project_relative` (a bundle of a run over the example data stores
`examples/datasets/honeybees.jsonl` and `examples/documents/honeybees.pdf`),
`test_exported_bundles_contain_no_absolute_paths` (a run over temporary files exports `dataset_path ==
"small.jsonl"`, with no leading separator or drive colon in either path).

**Limitations.** A bundle exported from a run whose inputs lie outside the project keeps only file names, so on
import the paths no longer locate the files (the SHA-256 hashes still identify them). The CSV guard also prefixes legitimate text that starts with `-` (for example a bulleted answer).
Markdown exports are not localised and show at most `worst` cases per metric. There is no export of a comparison
(comparisons are shown in the UI and CLI only).

---

## V.24 `src/rag_workbench/services.py` — application wiring

**Path:** `src/rag_workbench/services.py` (82 lines).

**Purpose.** The small amount of glue shared by the CLI and the Streamlit app: building a context (settings,
logging, store, crash recovery), storing uploads safely, and listing selectable datasets and documents.

**Imports.** Standard library `hashlib`, `logging`, `dataclasses`, `pathlib`; internal `.config`
(`Settings`, `load_settings`), `.logging_setup.configure_logging`, `.reporting.safe_filename`,
`.runner.EvaluationRunner`, `.storage.RunStore`.

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `AppContext` | 19 | dataclass `(settings, store)` | What the UI caches and the CLI passes to commands. |
| `AppContext.runner` | 23 | `() -> EvaluationRunner` | A new runner bound to the context. |
| `open_context` | 27 | `(settings=None, *, console_logging=True) -> AppContext` | Load settings (unless given), configure logging, open the store, recover interrupted runs. |
| `save_upload` | 38 | `(settings, filename, data, *, allowed_suffixes, max_bytes) -> Path` | Store an upload safely. |
| `bundled_datasets` | 63 | `(settings) -> list[Path]` | Default dataset, then `examples/datasets/*.jsonl|*.csv` sorted. |
| `list_files` | 70 | `(settings, suffixes, extra) -> list[Path]` | `extra` files that exist, then uploads of the given types newest first, de-duplicated by resolved path. |

**`open_context` (27-35).** `recover_interrupted()` runs at every start-up with the default staleness window; a
non-zero count is logged as a warning. This is where runs left `running` by a killed process become
`interrupted` — but only once their heartbeat is older than `storage.STALE_AFTER_S` (15 minutes), so opening the
CLI while the UI is executing a run does not mark that live run as interrupted (V.20).

**`save_upload` (38-60).** Rejects disallowed suffixes and oversized data with `ValueError` (46-50). The target
name is `<first 12 hex of SHA-256(content)>-<safe_filename(stem)[:60]><suffix>` in `uploads_dir` (51-55); a
resolved-parent check rejects anything that would land outside the directory (56-57, defence in depth — the
sanitised name already contains no separators). The file is written only if it does not exist (58-59), so
re-uploading the same file is a no-op and two different files can never overwrite each other (their names carry
different hashes).

**`list_files` (70-82).** The default dataset is also inside `examples/datasets`, so `bundled_datasets` lists it
twice; the resolved-path de-duplication (77-81) removes the second occurrence.

**Tests.** `test_cli_services.py::test_save_upload_sanitises_names` (`"../../evil name.jsonl"` lands in
`uploads_dir` as `<hash>-evil_name.jsonl`; same content gives the same hash prefix; bad suffix and size raise
`ValueError`; `list_files` puts the bundled file first and includes the upload). `open_context` is used by most CLI
tests.

**Limitations.** Uploads are never cleaned up automatically. `list_files` sorts uploads by modification time,
which `save_upload` does not refresh for a re-upload of identical content.

---

## V.25 `src/rag_workbench/demo.py` — the example runs

**Path:** `src/rag_workbench/demo.py` (46 lines).

**Purpose.** Define and execute the five offline example evaluations over the bundled honeybee data. `start.py`
runs them on the first launch so the app opens with real results, and `scripts/seed_demo_runs.py` runs them for the
documentation (docstring, lines 1-5). They need no network and no API key; rerunning reproduces the same scores
with new run ids.

**Imports.** Standard library `pathlib`; internal `.metrics.DEFAULT_OFFLINE_METRICS`, `.models` (`RunConfig`,
`RunRecord`), `.services.AppContext`.

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `demo_configs` | 24 | `(project_root, dataset, document) -> dict[str, RunConfig]` | The five configurations, keyed `k1`, `k3`, `k5`, `unanswerable`, `failures`. |
| `seed_demo_runs` | 42 | `(ctx: AppContext) -> dict[str, RunRecord]` | Run every configuration with `ctx.runner()` and return the stored runs by key. |

**The five configurations (`demo.py:24-39`).** All use the offline provider, the `rag` pipeline and BM25.

| Key | Run name | Dataset | k | Metrics | Shows |
|---|---|---|---:|---|---|
| `k1` | `offline-bm25-k1` | default (`honeybees.jsonl`) | 1 | offline defaults | retrieval depth 1 |
| `k3` | `offline-bm25-k3` | default | 3 | offline defaults | the default depth |
| `k5` | `offline-bm25-k5` | default | 5 | offline defaults | retrieval depth 5 |
| `unanswerable` | `unanswerable-k3` | `examples/datasets/honeybees_unanswerable.jsonl` | 3 | `exact_match`, `token_f1`, `context_recall`, `groundedness` | abstention handling and skips |
| `failures` | `injected-failures-30pct` | default | 3 | offline defaults | `offline_failure_rate=0.3`: deterministic injected failures, a `partial` run |

The "default" dataset and document are `Settings.default_dataset` and `Settings.default_document`
(`seed_demo_runs`, lines 34-37), so `RAGWB_DATASET`/`RAGWB_DOCUMENT` redirect four of the runs; the unanswerable
dataset is always taken from `examples/` under `project_root` (line 24).

**What the example runs produce.** On the current data, `ragwb show <run id>` prints these metric means (rerun
`uv run python scripts/seed_demo_runs.py` with `RAGWB_DATA_DIR` set to an empty folder to reproduce them):

| Run | Cases (ok/errors) | Token F1 | ROUGE-L | Context recall | Groundedness |
|---|---|---:|---:|---:|---:|
| `offline-bm25-k1` | 20/0 | 0.404 | 0.373 | 0.857 | 1.000 |
| `offline-bm25-k3` | 20/0 | 0.346 | 0.317 | 0.885 | 1.000 |
| `offline-bm25-k5` | 20/0 | 0.346 | 0.317 | 0.892 | 1.000 |
| `injected-failures-30pct` | 17/3 (`q03`, `q16`, `q17` fail) | 0.344 | 0.320 | 0.881 | 1.000 |

`unanswerable-k3` (6 cases) scores exact match 0.000 over all 6 cases, Token F1 0.039, groundedness 1.000, and
context recall 1.000 over the 2 answerable cases, with the 4 unanswerable cases **skipped** (their reference is the
abstention sentence). The extractive baseline never abstains on the four unanswerable questions: it always finds
some sentence that shares a content word. `ragwb compare` on `k1` versus `k3` reports a Token F1 difference of
−0.057 with CI −0.116…−0.008, which excludes zero: deeper retrieval makes the baseline's answers *worse* on this
metric (k = 3 is better on 3 cases, tied on 10 and worse on 7) — with more passages to choose from, its two best-weighted sentences
can come from a less relevant chunk — while context recall rises by 0.028 (CI 0.000…0.062,
inconclusive); `k5` answers are identical to `k3`'s. These are the runs and numbers shown in the book's screenshots.

**Error behaviour.** None of its own: `runner.run` raises before writing anything if a dataset or document is
missing or invalid (V.21); `start.py` reports such a failure and continues without examples.

**Tests.** `tests/test_runner.py::test_demo_runs_are_genuine_and_reproducible` runs `seed_demo_runs` twice on an
empty store: the five keys exist, `failures` is `partial` and `k3` `completed`, `unanswerable` has 6 cases, and the
second `k3` run has exactly the same Token F1 mean as the first.

**Design rationale.** Keeping the example definitions in the package (not in a script) lets the launcher, the
documentation script and the tests share one definition; the runs are ordinary evaluations, so everything the app
shows for them is produced by the same code path as a user's own runs.

---

## V.26 `src/rag_workbench/cli.py` — command-line interface

**Path:** `src/rag_workbench/cli.py` (644 lines). Entry points: the `ragwb` console script
(`pyproject.toml`, `[project.scripts]`) and `python -m rag_workbench`.

**Purpose.** Every core operation without the UI: run, list, show, compare, export, validate, delete, describe
metrics, import bundles, and score a single answer. The full help text is captured in
`docs/project-book/generated/cli-reference.md`.

**Imports.** Standard library `argparse`, `sys`, `pathlib`; internal `.archive`, `.config`, `.datasets`
(`DatasetError`, `validate_file`), `.documents.DocumentError`, `.metrics`, `.models.RunConfig`, `.reporting`,
`.runner.Progress`, `.services.open_context`, `.storage.StorageError`.

### Commands and functions

| Command | Function (line) | Behaviour | Exit codes |
|---|---|---|---|
| `run` | `cmd_run` (47) | Build a `RunConfig` (`build_config`), run it with a progress printer (`[ n/N] ok  case-id` or `ERR` plus the message; suppressed by `--quiet`), print the summary. | 0 if `completed`; **2** if `partial`, `failed` or `cancelled`; 1 on configuration errors |
| `list` | `cmd_list` (77) | `summary_dataframe` restricted to `run_id, name, status, provider, pipeline, retriever, k, n_cases, n_errors`; a hint when empty. | 0 |
| `show RUN_ID` | `cmd_show` (88) | Name, id, status, creation time, key config fields, summary table. | 0; 1 for an unknown id |
| `compare A B` | `cmd_compare` (98) | `comparison_dataframe(A, B)` printed with three decimals. | 0; 1 if the runs share no metric |
| `export RUN_ID` | `cmd_export` (110) | `write_export` in `--format csv|json|md` to `--out-dir` or `Settings.exports_dir`. | 0 |
| `validate FILE` | `cmd_validate` (118) | Case count, reference count, every error and warning, then `valid`/`INVALID`. | 0 valid; 1 invalid |
| `delete RUN_ID --yes` | `cmd_delete` (131) | Refuses without `--yes`; prints `deleted`, or `No run with id '...'.` on stderr for an unknown id (135-139). | 0 if deleted; 1 without `--yes` or for an unknown id |
| `metrics` | `cmd_metrics` (142) | Name, family, default threshold, requirements, description for every spec. | 0 |
| `import BUNDLE [BUNDLE...]` | `cmd_import` (151) | Import the given bundle files (at least one path is required, `nargs="+"`, line 345); per file `imported as <id>` or `already present, skipped`. | 0; 1 if a bundle is invalid or missing; 2 (argparse) without a path |
| `score` | `cmd_score` (158) | Evaluate `--metrics` (default: the offline defaults) on `--question`, `--answer`, optional `--expected` and repeatable `--context`; prints score, pass/fail or status, reason. Nothing is stored. | 0; 1 for unknown metrics or judge metrics without a key |

Helpers: `_print_summary` (66) prints the metric table (mean, CI, pass rate, scored/skipped/errors) and any
provenance warnings; `_get_run` (503) resolves an exact id, a unique prefix or suffix of at least 4 characters, or an exact run name, and raises
`LookupError` for an unknown or ambiguous reference (the ambiguous message names up to five matches); `build_parser` (521-671) defines the
arguments; `main` (674-687).

### `build_config` (25-48)

* Metrics: `--metrics` split on commas, else `DEFAULT_OFFLINE_METRICS` for the offline provider and offline +
  judge defaults for `openai` (26-27).
* `--threshold metric=value` (repeatable) parsed with `partition("=")`; a non-numeric value raises
  `ConfigError("Bad --threshold ...")` (28-34). Unknown metric names in thresholds are rejected later by
  `prepare`.
* Paths: `--dataset`/`--document` or the Settings defaults, resolved to absolute paths (38-39) so the stored config
  is unambiguous.
* `judge_model` is recorded only if a selected metric needs OpenAI (36, 43) — "so the config never claims one that
  wasn't used" (comment, line 38). `embedding_model` is recorded only for the embedding retriever (40).
* Workers: `--workers`, else 1 for offline and `Settings.max_workers` for OpenAI (45). `max_retries` and
  `request_timeout_s` always come from Settings (46) — there are no CLI flags for them.
* `--answer-sentences` (default 2), `--limit`, `--notes`, `--inject-failures` (default 0.0) and `--seed` (default 0)
  map to the corresponding `RunConfig` fields; `--model` maps to `generator_model`.

Run options and defaults (from `build_parser`): `--name cli-run`, `--provider offline`, `--pipeline rag`,
`--retriever bm25`, `-k 3`.

### `main` (387-397) and error behaviour

`main` parses arguments, opens a context with `console_logging=False` (logs go to the file only, keeping stdout
clean), and dispatches to `args.func`. `BundleError`, `ConfigError`, `DatasetError`, `DocumentError`,
`StorageError`, `LookupError` and `ValueError` are printed to stderr as `error: <message>` with exit code 1. Since
pydantic's `ValidationError` subclasses `ValueError`, an invalid `RunConfig` (for example `-k 0`) is reported the
same way. `argparse` errors exit with code 2 before `main`'s handler runs. `KeyboardInterrupt` is not caught: the
runner marks the run `cancelled` and Python prints a traceback.

**Tests.** `tests/test_cli_services.py`: `test_cli_run_list_show_compare_export` (also asserts `judge_model` is
`None` for lexical-only runs), `test_cli_errors_are_reported_not_raised` (OpenAI without key, unknown metric,
`-k 0`, unknown run, bad threshold, invalid dataset, delete without `--yes`, deleting an already-deleted run,
missing bundle — all exit 1),
`test_injected_failures_give_partial_run_exit_code` (all cases fail → status `failed`, exit 2),
`test_module_entry_point_runs_in_a_subprocess`, `test_import_command` (export a run as JSON, import it while it
exists — "already present" — then delete and import again — "imported as"), `test_score_command`.
`scripts/verify.py` repeats the main workflow against a temporary data directory.

**Limitations.** `score` uses default thresholds only. There is no
`--max-retries`/`--timeout` flag; set `RAGWB_MAX_RETRIES`/`RAGWB_REQUEST_TIMEOUT_S` instead.

---

## V.27 `src/rag_workbench/ui/state.py` — cached context and session helpers

**Path:** `src/rag_workbench/ui/state.py` (48 lines).

**Purpose.** One `AppContext` per Streamlit server process, a uniform way for pages to fail on configuration
errors, the "selected run" shared between pages, and run labels.

**Imports.** Standard library `re`; third-party `streamlit`; internal `rag_workbench.config.ConfigError`,
`rag_workbench.models.RunRecord`, `rag_workbench.services` (`AppContext`, `open_context`). Absolute imports are used
because page scripts are executed by Streamlit rather than imported as package modules.

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `SELECTED_RUN` | 13 | `"selected_run_id"` | Session-state key. |
| `GENERATED_ID` | 14 | regex `^\d{8}-\d{6}-.+-[0-9a-f]{6}$` | Shape of `runner.new_run_id` ids. |
| `get_context` | 18 | `() -> AppContext`, `@st.cache_resource(show_spinner="Opening the run store…")` | `open_context(console_logging=False)` once per process. |
| `context_or_stop` | 23 | `() -> AppContext` | On `ConfigError`: show the error and a hint to fix `.env`, then `st.stop()`. |
| `select_run` / `selected_run_id` | 32 / 36 | | Write/read `st.session_state["selected_run_id"]`. |
| `short_id` | 40 | `(run) -> str` | The 6-hex suffix for generated ids, the whole id otherwise (for example an imported run whose id was chosen by hand). |
| `run_label` | 45 | `(run) -> str` | `"name · status · YYYY-mm-dd HH:MM · short id"`; the date is omitted for imported runs (their creation time is not when they were loaded). |

**Design notes.** Caching the context means settings are read and `recover_interrupted` runs once per server
process, not on every rerun; the cached `Settings` is frozen (V.4). An exception raised by the cached function is
not cached, so after fixing `.env` and restarting, the next rerun retries. `tests/test_ui.py` clears
`st.cache_resource` before and after each test (`fresh_cache` fixture) so each test gets a context bound to its own
temporary data directory.

**Limitations.** The run store path and settings are fixed for the lifetime of the server process; changing
`.env` requires a restart (the Settings page says so).

---

## V.28 `src/rag_workbench/ui/components.py` — presentation helpers

**Path:** `src/rag_workbench/ui/components.py` (99 lines).

**Purpose.** Formatting and chart helpers shared by the pages.

**Imports.** Third-party `altair`, `pandas`, `streamlit`; internal `rag_workbench.metrics.METRIC_SPECS`,
`rag_workbench.models.RunRecord`, `rag_workbench.reporting.metric_label`.

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `STATUS_COLORS` | 15 | `dict` | completed green, partial orange, failed red, cancelled/interrupted gray, running blue, imported violet. |
| `CSS` / `apply_style` | 18 / 27 | `() -> None` | Injects padding, max width 1400 px, metric font size and the `.eval-muted` class. |
| `short_path` | 33 | `(path, root) -> str` | Project-relative POSIX path, or the absolute path for files outside the project (uploads in a custom data dir). |
| `status_badge` | 44 | `(status) -> str` | Streamlit Markdown badge `:<color>-badge[status]`. |
| `fmt` | 48 | `(value, digits=3, suffix="") -> str` | `—` for `None`/NaN; fixed decimals for floats. |
| `family_caption` | 56 | `(metric) -> str` | "LLM judge (DeepEval)" or "lexical overlap (offline)". |
| `provenance_warnings` | 63 | `(run) -> None` | Bordered box headed "Imported run — read the provenance notes before comparing" listing `config["provenance_warnings"]`. |
| `score_chart` | 72 | `(df, *, x, y, color=None, ci=None, height=320, y_title="Mean score") -> alt.Chart` | Bar chart on a fixed [0, 1] axis with optional CI rules. |
| `metric_columns_config` | 92 | `(metrics) -> dict` | `NumberColumn` per metric with label, `%.3f` and the description as help. |

**`score_chart` (72-89).** The y scale is fixed to `domain=[0, 1]` so small differences are not visually
exaggerated (docstring). With `color`, bars are grouped by `xOffset`. Tooltips list every column (numbers with
`.3f`). With `ci=(low, high)`, a black `mark_rule` from `low` to `high` is layered on each bar, sharing the x and
xOffset encodings.

**Interactions.** Only the page scripts use it. `provenance_warnings` reads keys that only imported bundles carry;
no code in the package writes `provenance_warnings`.

**Tests.** Indirectly through `tests/test_ui.py` (for example `test_results_for_imported_run_show_provenance`
asserts "Imported run" appears).

---

## V.29 `src/rag_workbench/ui/views/overview.py` — Overview page

**Path:** `src/rag_workbench/ui/views/overview.py` (88 lines). Default page (`/`).

**Purpose.** Show what exists, point a new user at the first step, list recent runs and plot one metric across runs.

**Imports.** `pandas`, `streamlit`; internal `ui.state` (`context_or_stop`, `select_run`, `short_id`),
`ui.components` (`score_chart`, `status_badge`), `reporting` (`metric_label`, `summary_dataframe`).

**Flow.**

1. KPI row (20-25): runs stored (including imported bundles), new runs (non-imported), cases evaluated (sum of
   `n_cases` over non-imported runs), and whether an OpenAI key is configured.
2. Empty state (27-32): when there is no non-imported run, a box explains the offline default ("It takes a few
   seconds at most and needs no API key") and links to the New evaluation page. After `python start.py` this box
   normally does not appear, because the first launch creates the five example runs (V.1).
3. If no runs exist at all the page stops (34-35).
4. Recent runs table (37-53): selected columns of `summary_dataframe`, with `created_at` shown as "imported" for
   imported runs; single-row selection stores the run as selected and shows a link to the results page.
5. One metric across runs (55-71): a selectbox over every metric name present in any summary, defaulting to
   `correctness` when present; bars of each run's mean with 95 % CI (oldest first), and a caption warning that runs
   with different datasets, retrievers or judges are not directly comparable.
6. A caption when imported runs carry provenance warnings (73-74), and the store and log paths (75).

**Tests.** `test_ui.py::test_overview_empty_state_then_runs` (KPIs `0`/`0`/`not set`, the empty-state text, no
table) and `test_ui.py::test_overview_lists_stored_runs` (two stored runs → "Runs stored" = 2, one table, no
empty-state text).

---

## V.30 `src/rag_workbench/ui/views/new_run.py` — New evaluation page

**Path:** `src/rag_workbench/ui/views/new_run.py` (248 lines). URL `/new-run`.

**Purpose.** Configure a run with validation feedback *before* anything executes, launch it with live progress,
and summarise the result. The page builds the same `RunConfig` the CLI builds and drives the same runner.

**Imports.** `pandas`, `streamlit`; internal `ui.state` (`context_or_stop`, `select_run`), `ui.components`
(`short_path`, `status_badge`), `config.ConfigError`, `datasets` (`DatasetError`, `SUPPORTED_SUFFIXES`,
`validate_file`), `documents` (`SUPPORTED_SUFFIXES`, `DocumentError`, `load_chunks`), `metrics`
(`DEFAULT_OFFLINE_METRICS`, `METRIC_SPECS`), `models.RunConfig`, `reporting.metric_label`, `runner.Progress`,
`services` (`bundled_datasets`, `list_files`, `save_upload`), `storage.StorageError`.

### Section 1 — Data (29-88)

* **Dataset upload** (32-43): `st.file_uploader` restricted to `.jsonl`/`.csv`; its help text describes the format and shows the configured
  size limit (`Size limit: {max_dataset_bytes / 1e6:g} MB`, line 34). A new upload is saved with
  `save_upload` (limit `max_dataset_bytes`) **once per upload** — tracked by `upload.file_id` in
  `st.session_state["_dataset_upload_id"]` — and preselected through `st.session_state["dataset_choice"]`. Saving
  only once keeps a later manual selection from being overridden on every rerun (comment, line 35). A
  `ValueError` from `save_upload` is shown as an error.
* **Dataset selection** (44-51): `list_files(s, DATASET_SUFFIXES, bundled_datasets(s))`; the page stops if there is
  none. Options are shown as project-relative paths.
* **Validation feedback** (52-64): `validate_file` with the Settings limits on every rerun; success shows
  "N cases · M with reference answers", failure lists up to ten errors; warnings in an expander; a 20-row preview.
* **Document** (66-88): the same upload pattern with `.pdf/.txt/.md` and `max_document_bytes`; `load_chunks`
  shows "N chunks extracted" or the `DocumentError`, leaving `chunks = []`.

### Section 2 — Pipeline (91-118)

Provider radio (`offline`/`openai`) with a warning when OpenAI is chosen without a key; the pipeline radio offers
`agent` only for `openai`; the retriever radio offers `embedding` only when a key is configured; the k slider runs
from 1 to `min(10, number of chunks)` (default 3). For OpenAI a generator-model text input (default
`Settings.generator_model`); for offline a "Sentences per extractive answer" input (1-10, default 2).

### Section 3 — Metrics (121-159)

The multiselect offers only metrics usable with the current key (122), defaulting to the offline defaults. A
judge-model input appears only when a selected metric needs OpenAI (129-131), so `judge_model` stays `None` for
lexical-only runs, as in the CLI. Per-metric threshold inputs (0-1, step 0.05, spec default) sit in an expander.
"Advanced": parallel cases (1-32; default 1 offline, `Settings.max_workers` otherwise), "Evaluate first N cases
(0 = all)", seed, the failure-injection slider (offline only) and notes.

### Section 4 — Run (148-215)

* Default name `"{provider}-{pipeline}-{retriever}-k{k}"` (163).
* **Problem list** (166-178): invalid dataset, no usable document text, no metric, OpenAI without key, empty name.
  Any problem disables the Run button and is shown as one warning.
* **Cost notice** (180-183): for OpenAI or judge runs, the number of generation calls (cases after `limit`) and a
  note about judge calls.
* **Start** (185-202): builds `RunConfig` (with `embedding_model` only for the embedding retriever,
  `limit=None` for 0, `max_retries`/`request_timeout_s` from Settings) and calls `runner.prepare`. `ConfigError`,
  `DatasetError`, `DocumentError` and `ValueError` (which covers pydantic validation) show "Configuration
  rejected: ..." and stop.
* **Execute** (204-219): a progress bar and a code box with the last eight case outcomes (`✓`/`✗ case — error`)
  updated from the `on_progress` callback; `runner.execute` runs inside a spinner whose text explains that
  Streamlit's Stop button cancels and that finished cases are kept. Pressing Stop raises Streamlit's stop exception
  inside the callback; the runner marks the run `cancelled` and re-raises (V.21). A `StorageError` is shown and
  stops the page.
* **Result** (220-236): the run becomes the selected run; a success message (or a warning if the status is not
  `completed`) with the status badge and `n_ok/n_cases`; a caption when cases failed; one metric tile per metric
  (mean, with scored/skipped/error counts as help); a link to the results page.

**Configuration.** Reads `has_openai_key`, `generator_model`, `judge_model`, `embedding_model`, `max_workers`,
`max_retries`, `request_timeout_s`, `max_dataset_bytes`, `max_document_bytes`, `max_cases`, `max_field_chars`.

**Tests.** `tests/test_ui.py`: `test_new_run_journey_offline_then_results_and_compare` (validation messages "20
cases · 20 with reference answers" and "11 chunks extracted", judge metrics absent from the options without a key,
an offline run named `ui-offline` completes, then the results and compare pages render),
`test_new_run_blocks_invalid_inputs` (an invalid dataset disables the button; an empty metric selection is listed
as a problem), `test_openai_option_explains_missing_key`, `test_failure_injection_shows_partial_run`.

**Limitations.** The k slider caps k at 10 although `RunConfig` allows 50 (use the CLI for more). The run executes
in the script thread, so the page is busy until it finishes or is stopped. Validation runs on every rerun (cheap for
the bundled sizes; bounded by the limits for uploads).

---

## V.31 `src/rag_workbench/ui/views/results.py` — Run results page

**Path:** `src/rag_workbench/ui/views/results.py` (220 lines). URL `/results`.

**Purpose.** Inspect one run: header and provenance, KPIs, summary statistics, a filterable case table, a case
detail view with the exact context that was scored, the stored configuration and environment, exports and
deletion.

**Imports.** Standard library `html.escape`; `altair`, `pandas`, `streamlit`; internal `ui.state` (`context_or_stop`, `run_label`, `select_run`,
`selected_run_id`), `ui.components` (`family_caption`, `fmt`, `metric_columns_config`, `provenance_warnings`,
`status_badge`), `reporting` (`EXPORT_FORMATS`, `cases_dataframe`, `export_run`, `metric_label`, `run_metrics`,
`safe_filename`).

**Run selection and deep links (29-41).** A `?run=<id>` query parameter takes precedence over the session's
selected run (comment, line 22); the selectbox shows `run_label`s, and the chosen run becomes the selected run.
`?tab=summary|cases|case|config|export` selects the initial tab through `st.tabs(..., default=...)` (68-72), and
`?case=<case_id>` preselects the case in the detail tab (139-141). These are the links the screenshot page list
uses.

**Header (43-58).** Name and status badge; provider, pipeline, retriever, k, generator, judge and id in one muted
HTML line rendered with `unsafe_allow_html=True` (45-48). Because config values can come from imported bundles
(comment, line 44), every value and the run id are passed through `html.escape` before entering the markup, so a
bundle cannot inject HTML or script into the page; provenance warnings for imported runs; a warning for `cancelled`/`interrupted` runs stating how many of
`n_cases` were evaluated; notes. A run without a summary (still running elsewhere) stops with an info message.

**KPIs (60-66).** Cases `n_ok/n_cases`, errors, mean latency (p95 as help), tokens (or `—` when unknown; cost as
help, with a hint to set `RAGWB_PRICE_*`).

**Tabs.**

* *Summary* (74-109): per-metric table (method family, mean, CI, median, std, pass rate as a progress column,
  threshold, scored/skipped/errors) with a caption that means exclude skipped and errored cases and that intervals
  reflect question sampling, not judge noise; a faceted histogram of scores per metric (bins of 0.1 on [0, 1]) built
  from `cases_dataframe` melted to long form.
* *Cases* (111-131): filters for status, "Below threshold on <metric>" (rows where `<m>_passed == False`; unscored
  cases, whose value is `None`, are excluded — comment, line 120) and a case-insensitive literal search over question
  and answer; the table shows position, id, status, question, answer, metric scores, latency, attempts, error.
* *Case detail* (133-167): question with status badge, expected and pipeline answers side by side, the error and
  attempt count for failed cases, a per-metric table (status, score, threshold, passed, reason), and the context
  labelled by `context_source` (line 159) — "chunks returned by the retriever" or "chunks returned to the agent's
  tool" ("none" for a failed case). Each chunk is shown with rank and id, plus page and score when `page` is
  non-zero (it always is for chunks from `documents.load_chunks`, whose pages start at 1), and its text is rendered with
  `st.text` so document content is never interpreted as Markdown or HTML (comment, line 166).
* *Configuration* (169-174): the stored config and environment as collapsed JSON, and both SHA-256 hashes.
* *Export & manage* (176-195): one download button per format (`export_run`, file name `safe_filename(run.id)`),
  and a deletion expander that enables "Delete run" only when the typed text equals the run id (for an imported
  run the warning adds that it can be imported again from its bundle file, line 165); afterwards the selection is
  cleared and the page reruns.

**Tests.** `test_ui.py::test_new_run_journey_offline_then_results_and_compare` (KPI "Cases" = "20/20", five tabs,
the detail of `q04` shows "chunks returned by the retriever" and a caption starting `rank 1 · p1-b`),
`test_results_for_imported_run_show_provenance` (a bundle exported from a real run with an added provenance warning
is imported; the page shows "Imported run" and the warning text), `test_imported_config_values_are_html_escaped` (a
bundle whose `generator_model` is `<img src=x onerror=alert(1)>` renders as escaped text in the header line).

**Limitations.** Every rerun loads all case results of the selected run and regenerates all three export payloads
for the download buttons. The search is a substring match, not full-text search.

---

## V.32 `src/rag_workbench/ui/views/compare.py` — Compare runs page

**Path:** `src/rag_workbench/ui/views/compare.py` (128 lines). URL `/compare`.

**Purpose.** Compare two or more runs: configuration differences, metric means with confidence intervals, the
best run per metric, and a paired case-by-case analysis of a candidate against a baseline.

**Imports.** `pandas`, `streamlit`; internal `ui.state` (`context_or_stop`, `run_label`, `short_id`),
`ui.components` (`provenance_warnings`, `score_chart`), `aggregate.paired_comparison`, `reporting`
(`comparison_dataframe`, `metric_label`, `run_metrics`).

**Flow.**

1. Needs at least two stored runs (15-18). `?runs=id1,id2,...` preselects runs when at least two valid ids are
   given; otherwise the three most recent runs are preselected (20-21). Fewer than two selected → warning and stop.
2. *Configuration* (30-53): a table with one column per run and rows provider, pipeline, retriever, k,
   generator_model, judge_model, metrics, dataset SHA-256 prefix, cases, status. Rows whose values differ across
   runs (`nunique(axis=1) > 1`) are highlighted. Different dataset hashes trigger a warning that cases are paired by
   question text, so only shared questions are compared. Imported runs' provenance notes are available in an
   expander.
3. *Metric means* (56-73): grouped bars (one colour per run) with CI rules; a missing CI (fewer than two scored
   cases) is drawn as a zero-length interval at the mean (64-65). The caption notes that overlapping intervals may
   be sampling noise and points to the paired analysis.
4. *Best run per metric* (75-83): the run with the highest mean; ties within 1e-9 are shown as `A = B` with
   `tie = True`, not broken arbitrarily (comment, line 78).
5. *Paired comparison* (86-108): baseline A and candidate B selectboxes (defaults: the first and second chosen
   runs; identical choices stop with a hint); `comparison_dataframe(A, B)` plus a verdict column — "no paired cases"
   when `paired_cases == 0`, "B better"/"B worse" only when the CI of the paired difference excludes zero (sign of
   the mean difference), "inconclusive" otherwise (101-103). The caption warns that with 20 cases small differences
   are usually inconclusive.
6. *Per-case differences* (110-128): for one shared metric, a table of question, A and B scores, `B - A` and both
   answers, sorted by difference, for questions scored in both runs (pairing by normalised question text, as in
   `aggregate._case_key`), and a caption with wins, ties and losses from `paired_comparison`.

**Tests.** `test_ui.py::test_new_run_journey_offline_then_results_and_compare` (with a stored k = 1 run to compare
against, the page renders without exceptions, shows "Highlighted rows differ" and a caption mentioning paired cases).

**Limitations.** Means of runs over different datasets or judges are plotted side by side; the page warns but does
not prevent it. If the chosen runs share no metric (for example a lexical-only run and a judge-only run), the paired section stops
with "These runs share no metric." Statistical testing is per metric with no multiple-comparison correction.

---

## V.33 `src/rag_workbench/ui/views/data.py` — Datasets & retrieval page

**Path:** `src/rag_workbench/ui/views/data.py` (87 lines). URL `/data`.

**Purpose.** Browse datasets and document chunks, and try BM25 retrieval interactively, without running an
evaluation.

**Imports.** `pandas`, `streamlit`; internal `ui.state.context_or_stop`, `ui.components.short_path`, `datasets`
(`SUPPORTED_SUFFIXES`, `validate_file`), `documents` (`SUPPORTED_SUFFIXES`, `DocumentError`, `load_chunks`),
`retrieval.BM25Retriever`, `services` (`bundled_datasets`, `list_files`).

| Name | Line | Purpose |
|---|---:|---|
| `short(path)` | 22 | `short_path(path, s.project_root)`, used as `format_func`. |

**Tabs.** *Datasets* (26-56): select a dataset; KPIs for cases, references, errors and warnings; every error and
warning; a table with id, question, reference and word counts; the SHA-256; a format reference in an expander.
*Document chunks* (58-69): every chunk with id, page, length and text, plus totals. *Retrieval playground*
(71-87): a query (default "How is nectar turned into honey?", line 74) and a k slider; a fresh `BM25Retriever` over the selected
document's chunks shows ranked hits with page and BM25 score; when every score is zero a warning explains that no
chunk shares a content word and that results are in document order. Embedding retrieval is deliberately not offered
here to avoid cost (caption, lines 69-70).

**Tests.** `test_ui.py::test_data_and_settings_pages` (Cases 20, Errors 0, a caption mentioning BM25).

**Limitations.** The playground uses the document selected in the second tab (the variable `chunks` from that
tab); it rebuilds the BM25 index on every rerun, which is cheap for small documents.

---

## V.34 `src/rag_workbench/ui/views/settings.py` — Settings & metrics page

**Path:** `src/rag_workbench/ui/views/settings.py` (57 lines). URL `/settings`.

**Purpose.** Show the effective configuration without secrets, the environment-variable mapping, the metric
catalogue with interpretation notes, and storage locations.

**Imports.** `pandas`, `streamlit`; internal `ui.state.context_or_stop`, `rag_workbench.__version__`,
`config.ENV_VARS`, `metrics.METRIC_SPECS`.

**Content.** `Settings.public_dict()` as a two-column table (28-32) — the key itself is never displayed, only
`openai_api_key_configured`; `ENV_VARS` in an expander; `METRIC_SPECS` as a table (label, family, default
threshold, requirements, description) followed by four notes: lexical metrics compare words; judge metrics are an
LLM's assessment and not ground truth; skipped metrics are excluded from means; the offline generator's
groundedness is about 1.0 by construction. Finally the run store, uploads, exports and log paths with the run count,
the package version, and how to reset local data (delete the data directory).

**Tests.** `test_ui.py::test_data_and_settings_pages` asserts the "Metric catalogue" subheader and that no `sk-`
string appears in the rendered text.

---

## V.35 `scripts/verify.py` — local verification sequence

**Path:** `scripts/verify.py` (203 lines). Usage: `uv run python scripts/verify.py [--quick] [--audit]`.

**Purpose.** One command that checks the environment, the lockfile, the tree for secrets, static analysis (ruff and mypy), the test
suite and an offline end-to-end CLI workflow (plus, with `--audit`, a dependency vulnerability scan), printing `[PASS]`/`[FAIL]` per step and exiting non-zero if any step fails. Apart from the optional `--audit`, it
contacts no remote service and writes only to a temporary directory, pytest's temporary directories and the
coverage data file (docstring, lines 17-21).

**Imports.** Standard library only (`argparse`, `importlib`, `os`, `re`, `shutil`, `subprocess`, `sys`,
`tempfile`, `pathlib`). The package is exercised through subprocesses (`python -m rag_workbench`, `python -m
pytest`).

| Function | Line | What it checks |
|---|---:|---|
| `step(name, ok, detail="")` | 43 | Records a result in the module-level `results` list and prints it. |
| `run(cmd, env=None, cwd=ROOT)` | 48 | `subprocess.run` with captured UTF-8 output (`errors="replace"`). |
| `check_environment()` | 53 | Python >= 3.12 and importable `rag_workbench`, `streamlit`, `pandas`, `pydantic`, `pymupdf`, `langchain`, `langchain_openai`, `deepeval`, `pytest`. |
| `check_lockfile()` | 66 | `uv lock --check --offline`; reported as passed-but-skipped when `uv` is not on `PATH`. |
| `check_secrets()` | 75 | Walks the tree (skipping `.venv`, `__pycache__`, `.pytest_cache`, `data`, `build`, `.git`); fails if a `.env` file exists or any file under 5 MB contains a match of `KEY_PATTERN` (line 37) that does not contain `FAKE_MARKER` (line 38, `b"not-a-real"`). |
| `check_static()` | 90 | Runs `ruff check .` and `mypy`; reports "clean (ruff, mypy)", or a note if a tool is not installed. |
| `check_audit()` | 104 | Only with `--audit`: exports the locked runtime requirements with `uv export --frozen --no-dev --no-hashes --no-emit-project` and runs `pip-audit --no-deps --disable-pip` over them; the only step that contacts a remote service. |
| `check_tests(quick)` | 122 | `pytest -q -p no:cacheprovider`, with `-m "not ui"` for `--quick`, otherwise with `--cov --cov-report=term`; reports the summary line and the coverage total; prints the last 4,000 characters of output on failure. |
| `check_end_to_end()` | 137 | See below. |
| `main()` | 182 | Runs the six checks in order (and the audit when asked) and prints `N/M checks passed`. |

**End-to-end check (137-179).** Since release 1.2 it also runs `tag`, a filtered `list`, `regress` of a run against itself, `tune-abstention` over the unanswerable dataset, `user list` and an unfiltered `backup` (lines 171-177); the original description follows. In a `TemporaryDirectory` with `RAGWB_DATA_DIR` pointing at it, an empty
`OPENAI_API_KEY` and telemetry opt-out: `validate` every example dataset; an offline `run` with k = 3 that must
print `Run <id>: completed`; `show`; `export` in all three formats; `import` of the exported JSON bundle (a
round trip through `load_bundle`; the run already exists, so it is reported as skipped, line 122); a second run
with k = 1 and a successful `compare`; a run with `--inject-failures 1.0 --limit 2` expecting exit 2;
`run --provider openai` expecting a clean exit 1 without a key; and, since release 1.1, a run over the unanswerable
dataset followed by `slices --by type`, `labels-template`, `backup` and `doctor`.

**Design notes.** Because the `.env` check fails the step whenever a `.env` exists, a developer with a local key
file sees `secrets` fail by design — the message says the file must never be shared. The script is the single
command that answers "does this checkout work?" without network access: `uv run python scripts/verify.py` prints
`6/6 checks passed` on a healthy tree (7/7 with `--audit`).

**Secret pattern (lines 37-38).** `KEY_PATTERN = rb"sk-(?:[A-Za-z0-9]+-)?[A-Za-z0-9_\-]{20,}"` matches classic
`sk-...` keys as well as prefixed project and service-account keys (`sk-proj-...`, `sk-svcacct-...`): an optional
alphanumeric segment followed by `-`, then at least 20 key characters including `_` and `-`. Every match is checked
against `FAKE_MARKER`; deliberately fake keys used in tests carry the text `not-a-real` and are ignored (line 83),
so the test suite can contain key-shaped strings without failing the step.

**Limitations.** The key pattern is a heuristic: it finds OpenAI-shaped keys only, and any real key that happened to
contain `not-a-real` would be ignored. Coverage omits `ui/views/*` (see `pyproject.toml`).

---

## V.36 `scripts/seed_demo_runs.py` — example runs for the documentation

**Path:** `scripts/seed_demo_runs.py` (47 lines). Usage: `uv run python scripts/seed_demo_runs.py [--pages FILE]`.

**Purpose.** A thin command-line wrapper around `rag_workbench.demo.seed_demo_runs` (V.25): add the five offline
example runs to the configured run store, print their ids and statuses, and optionally write the page list used by
the screenshot tool (docstring, lines 1-7). `start.py` creates the same runs automatically on a first launch.

**Imports.** Standard library `argparse`, `json`, `pathlib`; internal `rag_workbench.demo.seed_demo_runs`,
`rag_workbench.services.open_context`.

| Function | Line | Signature | Purpose |
|---|---:|---|---|
| `main` | 20 | `() -> None` | Seed the runs, print `key  run-id  status`, write `--pages` if given. |

**`--pages` (27-43).** Writes a JSON list of eleven `[name, path]` pairs, from `01-overview` (`/`) to
`11-unanswerable`, using the new run ids in deep links — for example `/results?run=<k3>&tab=case&case=q10`,
`/results?run=<k3>&tab=config` (`06-run-configuration`), `/results?run=<failures>&tab=cases` and
`/compare?runs=<k1>,<k3>,<k5>`. `docs/project-book/tools/capture_screenshots.py` consumes this file; the committed
`docs/project-book/tools/screenshot_pages.json` is one such file.

**Error behaviour and side effects.** No handling of its own: an exception (for example a `ConfigError` from
`.env`) propagates with a traceback. It writes to the configured data directory, and every call adds five new runs
(it does not check whether example runs already exist); set `RAGWB_DATA_DIR` to keep the main store untouched.

---

## V.37 `scripts/make_example_pdf.py` — generate the example PDF

**Path:** `scripts/make_example_pdf.py` (50 lines). Usage: `uv run python scripts/make_example_pdf.py [name]` (the name defaults to `honeybees`; release 1.2 added the
argument so the volcanoes, coffee and lighthouses documents could be rendered the same way).

**Purpose.** Render `examples/documents/<name>.md` to `examples/documents/<name>.pdf`, so that the PDF
extraction path (`documents._pdf_blocks`) has bundled examples whose content is known exactly (docstring,
lines 1-8).

**Imports.** Standard library `argparse`, `pathlib`; third-party `pymupdf` (imported at module level — this is a developer
script, not part of the package).

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `ROOT`, `DOCUMENTS` | 17-18 | `Path` | Project root and `examples/documents`; the source is `DOCUMENTS/<name>.md`, the target the same path with `.pdf` (`main`, 25-26). |
| `MARGIN, GAP, FONT_SIZE, TITLE_SIZE` | 19 | `56, 12, 11, 18` | Layout in points. |
| `main` | 22 | `() -> None` | Parse the optional name, build and save the PDF. |

**How it works (`make_example_pdf.py:22-46`).** The source is split on blank lines; the first block is the title
(its leading `#` and spaces stripped, line 29) and the rest are paragraphs. On an A4 page (595 × 842 points) the
title is written with `insert_text` in Helvetica Bold (`hebo`) at 18 pt (29). Each paragraph is written with
`insert_textbox` in Helvetica (`helv`) at 11 pt, line height 1.35, into the rectangle from the current position
to the bottom margin (33-34). `insert_textbox` returns the unused height; a negative value means the text did not
fit and nothing was written, so the script starts a new page and retries the same paragraph (35-39). Otherwise the
cursor moves down by the used height plus `GAP`. Metadata (title, creator) is set and the file is saved with
`garbage=4, deflate=True` (40-41); the script prints the page and paragraph counts.

**Result.** One PyMuPDF text block per paragraph, which is what `documents.load_chunks` turns into one chunk per
paragraph: the current PDF has 2 pages and 11 chunks — the title `p1-b1` ("Honeybees: Life Inside the Colony"),
paragraphs `p1-b2`…`p1-b10`, and `p2-b1` (asserted by `test_documents.py::test_real_pdf_chunks`). Loading the
Markdown source directly also gives 11 chunks, all on page 1 (`p1-b1`…`p1-b11`), because text files have no pages.
The output is deterministic apart from PDF metadata timestamps (docstring, line 7), so regenerating changes the
file's SHA-256 even when the content is identical — and with it the document hash recorded by new runs.

**Limitations.** Only the layout this one document needs: no Markdown formatting beyond the title line, no
hyphenation, and a paragraph taller than a whole page would loop forever (each retry on a fresh page would fail
again); the example's paragraphs are far shorter than that.

---

## V.38 Documentation tooling (`docs/project-book/tools/`)

These three scripts produce the book's generated appendices, figures and screenshots (a fourth,
`build_book.py`, assembles and renders the book itself and is not described here). They are not part of the
product (not covered by tests or coverage) but are kept in the repository so the book can be rebuilt from the code.

### `generate_reference.py` (174 lines)

**Purpose.** Write the Markdown files in `docs/project-book/generated/` from the code itself, so reference tables
cannot drift (docstring, lines 5-12). **Imports:** `ast`, `pathlib`; lazily `rag_workbench.config`,
`rag_workbench.metrics`, `rag_workbench.cli`.

| Function | Line | Output |
|---|---:|---|
| `summary(node)` | 25 | First paragraph of a docstring, on one line. |
| `signature(fn)` | 30 | `name(args, *, kwonly, **kwargs)` without annotations or defaults. |
| `source_inventory()` | 42 | `source-inventory.md`: per file (all of `src/`, `start.py`, `streamlit_app.py`, `scripts/*.py`) line count, number of top-level classes, number of all function/method nodes (`ast.walk`), and each top-level class, method and function with line number and docstring summary. |
| `directory_tree()` | 75 | `directory-tree.md`, excluding runtime and generated folders and `.claude`. |
| `env_vars()` | 93 | `env-vars.md` from `ENV_VARS` and `Settings.model_fields` (defaults made project-relative, constraints from field metadata). |
| `metric_catalogue()` | 112 | `metric-catalogue.md` from `METRIC_SPECS`. |
| `test_catalogue()` | 125 | `test-catalogue.md`: every top-level `test_*` function with its docstring or first `assert` line, marked when parametrised. |
| `cli_reference()` | 151 | `cli-reference.md`: `ragwb --help` and each subparser's help (reads argparse's private `_actions` to find the subparsers). |
| `main()` | 163 | Writes all six files and prints their line counts. |

**Limitation.** Signatures omit annotations and defaults; the inventory's "functions/methods" count includes nested
functions (for example `on_progress` in `new_run.py`), which is why that page shows one function although it
defines no top-level function.

### `diagrams.py` (296 lines)

**Purpose.** Generate the SVG figures in `docs/project-book/figures/`: `architecture.svg`, `data-flow.svg`,
`run-lifecycle.svg`, `sequence-run.svg`, `sequence-agent.svg` and `module-graph.svg`. **Imports:** `ast`,
`html.escape`, `pathlib`.

* `Svg` (25-73): a minimal SVG builder (`box`, `arrow`, `text`, `save`) with a fixed palette and an arrow marker;
  `edge_between` (76-91) clips a centre-to-centre line to both box borders.
* `architecture`, `data_flow`, `lifecycle` (94-163) and `sequence` (166-189) are declared by hand: they describe the
  design and must be updated when it changes. The lifecycle figure encodes the run statuses of V.21 and the
  start-up recovery of V.20/V.24; the two sequence diagrams (built in `main`, 260-288) show an offline run from the
  UI and the agent's context capture.
* `module_graph` (192-255) is **derived from the source**: it parses every module of `rag_workbench` except `ui/`
  and `__main__`, resolves relative and absolute `rag_workbench.` imports to module names, lays modules out by
  dependency depth (leaves at the bottom) and draws an edge per import. It cannot drift from the code.

### `capture_screenshots.py` (154 lines)

**Purpose.** Capture full-page PNG screenshots of a locally running app for the book, using the Chrome DevTools
Protocol directly over `websockets` (described in the docstring as already a Streamlit dependency) with headless
Chrome or Edge. **Imports:** `argparse`, `asyncio`, `base64`, `json`, `shutil`, `subprocess`, `tempfile`, `time`,
`urllib.request`, `pathlib`, third-party `websockets`; lazily `PIL` (`Image`, `ImageChops`) for cropping.

* `main` (123-150) refuses any `--base` other than `http://localhost...`/`http://127.0.0.1...` (131-132), starts the
  browser headless with a temporary profile and a remote-debugging port, waits for the DevTools endpoint, runs
  `capture`, and always terminates the browser and deletes the profile.
* `CDP.call` (61-70) sends a JSON-RPC message and waits for the reply with the same id.
* `capture` (73-105) forces light colour scheme and a fixed 1440 × 2800 viewport, navigates to each page, and polls
  `READY_JS` (35-46) every 0.5 s: the page counts as ready when the Streamlit app exists, no skeleton is shown, the
  status widget is not "running", markdown has rendered, and the page fingerprint (text length and element count)
  has been stable for 3 s; after 60 s it captures anyway with a warning.
* `trim_bottom` (108-120) crops the empty area below the content, ignoring the 300-pixel sidebar whose background
  runs the full height.

The page list (`--pages`) is the JSON written by `seed_demo_runs.py --pages`; output goes to
`docs/project-book/screenshots/` (twelve PNG files: the eleven pages of the list, plus `12-slices.png`, the Summary tab of the
unanswerable run with the metadata breakdown, captured separately).

---

## V.39 Project configuration and data assets

### `pyproject.toml`

* **Project** (lines 1-18): name `rag-evaluation-workbench`, version `1.2.0`, `requires-python >=3.12`. Runtime
  dependencies with lower bounds: `deepeval>=4.2.6` (judge metrics; used only with a key), `langchain>=1.4.2`
  (agent), `langchain-openai>=1.6.6` (chat and embeddings), `pandas>=3.0.6`, `pydantic>=2.13`,
  `pymupdf>=1.28.2,<2`, `python-dotenv>=1.0`, `streamlit>=1.64.0`. The PyMuPDF upper bound is explained by the
  comment at lines 13-14: PyMuPDF 2.0 adds onnxruntime and layout models loaded at import time (about 3 s
  measured), which plain block extraction does not need. The list contains only packages the code imports.
* **Console script** (20-21): `ragwb = "rag_workbench.cli:main"`.
* **Dependency groups** (23-33): `dev` (`pytest>=8.3`, `pytest-cov>=6.0`, `ruff>=0.8`, `mypy>=1.13`, `pip-audit>=2.7`;
  installed by default through `[tool.uv] default-groups = ["dev"]`, lines 45-46) and `docs` (`markdown>=3.7`, for rendering the
  book).
* **Build** (35-43): hatchling, wheel package `src/rag_workbench`, and (42-43) a `force-include` table mapping `examples` to `rag_workbench/_examples` so a wheel carries the example data (release 1.2).
* **pytest** (48-54): `testpaths = ["tests"]`, `addopts = "-ra"`, markers `ui` for the AppTest journeys (used by
  `verify.py --quick` to skip them) and `live` for the opt-in paid tests.
* **coverage** (56-58): source `rag_workbench`, omitting `*/ui/views/*` because page scripts run in-process under
  AppTest, which coverage cannot attribute reliably.

The exact resolved versions are pinned in `uv.lock` (141 `[[package]]` entries, up from 117 because the dev group gained ruff, mypy and pip-audit), which `verify.py` checks with
`uv lock --check --offline`.

### `.streamlit/config.toml`

`[browser] gatherUsageStats = false` (no Streamlit usage statistics); `[client] toolbarMode = "minimal"` (hides
developer/deploy controls); `[server] maxUploadSize = 25` (MB, matching the default document limit — datasets are
further limited to 5 MB by the application), `headless = true`, and `address = "localhost"` (lines 16-17): the
file's comment says the tool has no authentication by default, so it listens on this machine only (the optional shared
password or named accounts, `start.py --host` and `--ssl-cert/--ssl-key` are the supported way to change that, Part XIII §144 and Part XIV §156); `[theme] primaryColor = "#3b5bdb"` with no base
theme, so the app follows the viewer's light/dark preference.

### `.env.example`

A commented template of every variable in `config.ENV_VARS`, with the defaults of V.4. Only `OPENAI_API_KEY=` is
uncommented (and empty). The header states that everything is optional and that without a key the workbench runs
fully offline. Copy it to `.env`; `load_settings` reads `.env` from the project root without overriding real
environment variables.

### `.gitignore`

Ignores `.env` (secrets), `data/` (run store, uploads, exports, logs), `.venv/`, `__pycache__/`, `*.py[cod]`,
`.pytest_cache/`, `.coverage`, `htmlcov/`, `.deepeval/` (an empty cache folder DeepEval creates in the working
directory when imported), `build/`, `dist/`, `*.egg-info/`, and `docs/project-book/build/`
(generated book builds; the Markdown sources and PDF are kept).

### `examples/` data assets

All example data was written for this project: one short document about honeybee colonies and three datasets
over it, and (release 1.2) three more documents, each with a 30-question dataset tagged by `type`, `difficulty` and
`topic`: `examples/documents/{volcanoes,coffee,lighthouses}.{md,pdf}` (15 chunks each: a title and 14 paragraphs) and
`examples/datasets/{volcanoes,coffee,lighthouses}.jsonl` (Part XIV §151). The table below describes the honeybee assets.

| Asset | Content | Used by |
|---|---|---|
| `examples/documents/honeybees.md` | The source text: a `# Honeybees: Life Inside the Colony` title line and ten blank-line separated paragraphs (the colony, the queen, workers, drones, the waggle dance, honey, beeswax, temperature control, swarming, pollination and threats). As a Markdown document it loads as 11 chunks `p1-b1`…`p1-b11`. | Input of `scripts/make_example_pdf.py`; selectable as a document in the UI. |
| `examples/documents/honeybees.pdf` | Generated from the Markdown by `scripts/make_example_pdf.py` (V.37): 2 A4 pages, 11 chunks — title `p1-b1` ("Honeybees: Life Inside the Colony"), paragraphs `p1-b2`…`p1-b10` and `p2-b1`. | Default document (`Settings.default_document`); `conftest.REAL_PDF`; `test_documents.py::test_real_pdf_chunks`; the example runs. |
| `examples/datasets/honeybees.jsonl` | 20 questions with ids `q01`…`q20`, every one with a reference answer (for example `q01` "How many queens does a typical honeybee colony have?" → "A colony normally has a single queen."). | Default dataset (`Settings.default_dataset`); `conftest.REAL_DATASET`; four of the five example runs; UI tests ("20 cases · 20 with reference answers"). |
| `examples/datasets/honeybees_unanswerable.jsonl` | 6 rows: four questions the document cannot answer (`u1`-`u4`, for example "How much honey does a colony produce in a year?", reference = the exact abstention sentence, `metadata.type = "unanswerable"`) and two answerable controls (`a1`, `a2`, `metadata.type = "answerable"`). | The `unanswerable-k3` example run: `context_recall` is skipped for the four unanswerable references, and the extractive baseline's answers show that it does not abstain. |
| `examples/datasets/honeybees_paraphrased.csv` | 5 rows, columns `id, question, expected_answer, topic` (ids `p1`…`p5`; `topic` becomes metadata), with questions and references paraphrased away from the document's wording. | Demonstrates the CSV format and the limits of lexical metrics and BM25 on paraphrase. |

Two properties of this data are visible in the example runs. The title chunk `p1-b1` has no terminal punctuation,
so `split_sentences` returns it whole as one "sentence". It is also retrieved often: it is very short, and BM25's
length normalisation favours a short chunk that contains a query term such as *honeybee* or *colony*. The extractive generator can then select it: its answer to `a2` ("Which
parasite threatens honeybee colonies?") is the title followed by the first sentence of `p1-b2`, "Honeybees: Life
Inside the Colony Honeybees are social insects …". And none of the six unanswerable-dataset answers is an exact match
(exact match 0/6), since the baseline answers every question with copied sentences.

---

## V.40 Coverage table

Every file listed in `docs/project-book/generated/source-inventory.md` (the original 40 files, the five added in release 1.1, V.41-V.45, and the five added in release 1.2, V.47-V.51, the two added in release 1.3, V.53-V.54, and the one source file and two scripts added in release 1.4, V.56-V.57), and the other files this Part describes.

| File (inventory) | Lines | Section |
|---|---:|---|
| `src/rag_workbench/__init__.py` | 15 | V.3 |
| `src/rag_workbench/__main__.py` | 5 | V.3 |
| `src/rag_workbench/aggregate.py` | 179 | V.19 |
| `src/rag_workbench/archive.py` | 82 | V.22 |
| `src/rag_workbench/cli.py` | 644 | V.26 |
| `src/rag_workbench/config.py` | 239 | V.4 |
| `src/rag_workbench/datasets.py` | 204 | V.9 |
| `src/rag_workbench/demo.py` | 47 | V.25 |
| `src/rag_workbench/documents.py` | 134 | V.10 |
| `src/rag_workbench/errors.py` | 91 | V.5 |
| `src/rag_workbench/logging_setup.py` | 105 | V.6 |
| `src/rag_workbench/metrics/__init__.py` | 57 | V.15 |
| `src/rag_workbench/metrics/base.py` | 98 | V.16 |
| `src/rag_workbench/metrics/judge.py` | 135 | V.18 |
| `src/rag_workbench/metrics/lexical.py` | 121 | V.17 |
| `src/rag_workbench/models.py` | 197 | V.7 |
| `src/rag_workbench/pipeline.py` | 178 | V.14 |
| `src/rag_workbench/prompts.py` | 34 | V.12 |
| `src/rag_workbench/providers.py` | 119 | V.13 |
| `src/rag_workbench/reporting.py` | 208 | V.23 |
| `src/rag_workbench/retrieval.py` | 216 | V.11 |
| `src/rag_workbench/runner.py` | 278 | V.21 |
| `src/rag_workbench/services.py` | 82 | V.24 |
| `src/rag_workbench/storage.py` | 205 | V.20 |
| `src/rag_workbench/text.py` | 100 | V.8 |
| `src/rag_workbench/ui/__init__.py` | 1 | V.3 |
| `src/rag_workbench/ui/components.py` | 99 | V.28 |
| `src/rag_workbench/ui/state.py` | 48 | V.27 |
| `src/rag_workbench/ui/views/__init__.py` | 0 | V.3 |
| `src/rag_workbench/ui/views/compare.py` | 129 | V.32 |
| `src/rag_workbench/ui/views/data.py` | 87 | V.33 |
| `src/rag_workbench/ui/views/new_run.py` | 248 | V.30 |
| `src/rag_workbench/ui/views/overview.py` | 89 | V.29 |
| `src/rag_workbench/ui/views/results.py` | 220 | V.31 |
| `src/rag_workbench/ui/views/settings.py` | 57 | V.34 |
| `start.py` | 219 | V.1 |
| `streamlit_app.py` | 42 | V.2 |
| `scripts/make_example_pdf.py` | 50 | V.37 |
| `scripts/seed_demo_runs.py` | 47 | V.36 |
| `scripts/verify.py` | 203 | V.35 |
| `src/rag_workbench/maintenance.py` | 294 | V.41 |
| `src/rag_workbench/calibration.py` | 260 | V.42 |
| `src/rag_workbench/ui/auth.py` | 261 | V.43 |
| `scripts/benchmark.py` | 90 | V.44 |
| `scripts/live_smoke.py` | 106 | V.45 |
| `src/rag_workbench/history.py` | 80 | V.47 |
| `src/rag_workbench/regression.py` | 107 | V.48 |
| `src/rag_workbench/abstention.py` | 177 | V.49 |
| `src/rag_workbench/users.py` | 200 | V.50 |
| `src/rag_workbench/metrics/semantic.py` | 123 | V.51 |
| `src/rag_workbench/ratelimit.py` | 55 | V.53 |
| `src/rag_workbench/judge_noise.py` | 116 | V.54 |
| `src/rag_workbench/ui/views/users.py` | 72 | V.56 |
| `scripts/wheel_check.py` | 86 | V.57 |
| `scripts/benchmark_documents.py` | 104 | V.57 |

| File (outside the inventory) | Section |
|---|---|
| `docs/project-book/tools/generate_reference.py`, `diagrams.py`, `capture_screenshots.py` (and `screenshot_pages.json`) | V.38 |
| `pyproject.toml`, `.streamlit/config.toml`, `.env.example`, `.gitignore` | V.39 |
| `Dockerfile`, `.dockerignore` | V.52 |
| `examples/documents/honeybees.md`, `examples/documents/honeybees.pdf`, `examples/datasets/honeybees.jsonl`, `honeybees_unanswerable.jsonl`, `honeybees_paraphrased.csv`; `examples/documents/{volcanoes,coffee,lighthouses}.{md,pdf}`, `examples/datasets/{volcanoes,coffee,lighthouses}.jsonl` | V.39 |

All 40 inventoried files of release 1.0 (the five files added in 1.1 are V.41-V.45) — the 35 files under `src/rag_workbench/`, `start.py`, `streamlit_app.py` and the 3 scripts — are covered; test modules are referenced from the section of the code they exercise rather than documented separately.

---

## V.41 `src/rag_workbench/maintenance.py` — operations tooling (release 1.1)

**Path:** `src/rag_workbench/maintenance.py` (294 lines). **Purpose.** Local operations helpers used by the CLI and the
Settings page: health checks, a verified backup of the run store, its restore (release 1.4), a retention policy, and rebuilding a run
configuration for a re-run. Nothing here calls the network (docstring, lines 1-5).

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `Check` | 36 | frozen dataclass `(name, status, detail)` | One health-check result; status is `ok`, `warn` or `fail`. |
| `run_doctor` | 43 | `(settings, *, config_file=None) -> list[Check]` | Runs nine probes; a crashing probe becomes a failed `diagnostics` check (51-55). |
| `_check_store` | 95 | `(settings) -> Check` | Opens the store, runs `PRAGMA integrity_check` and reads `user_version`; warns about abandoned `running` runs (109-113). |
| `_check_exposure` | 148 | `(settings, config_file) -> Check` | Reads `server.address` from `.streamlit/config.toml`; fails when exposed or unset without a password. |
| `backup_store` | 168 | `(store_path, dest_dir) -> Path` | SQLite online backup of a read-only connection (179-183), integrity-checked, removed on failure (192-194). |
| `select_prunable` | 203 | `(runs, *, keep_last=None, older_than_days=None) -> list[RunRecord]` | Retention selection; refuses an empty policy (206-207); never selects a live `running` run (215-216). |
| `restore_store` | 228 | `(backup_path, store_path, safety_dir, *, force=False) -> (Path, Path \| None)` | Release 1.4: validates the backup (237-252), refuses a recently active run (255-262), writes a `pre-restore-*` safety copy (263-264), stages and replaces atomically (265-271), reports a Windows lock (272-275), migrates (276). Part XVI §171. |
| `rerun_config` | 280 | `(run, *, name=None, project_root=None) -> RunConfig` | Rebuilds and re-validates a stored configuration; resolves relative paths against the project root. |

**Tests.** `tests/test_maintenance.py` (21 tests per `docs/TESTING.md`). **Limitations and rationale:** Part XIII §143.

---

## V.42 `src/rag_workbench/calibration.py` — judge-versus-human agreement (release 1.1)

**Path:** `src/rag_workbench/calibration.py` (215 lines). **Purpose.** Compare one metric's pass/fail verdicts on a run with
human labels and report agreement and Cohen's kappa. The module docstring (lines 1-17) names the limits: kappa is
unstable on small samples, depends on the pass rate, and says nothing about other settings.

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `MIN_RELIABLE_N`, `MAX_LABEL_FILE_BYTES` | 29-30 | `30`, `5_000_000` | Small-sample flag and label-file size limit. |
| `LabelsError` | 36 | `ValueError` subclass | Missing, unreadable or malformed labels file. |
| `parse_label` | 40 | `(value) -> bool or None` | `pass/fail`, `true/false`, `yes/no`, `1/0`; blank is `None`; anything else raises. |
| `load_labels` | 54 | `(path) -> dict[str, bool]` | CSV (`case_id,human_pass`) or JSONL; rejects duplicates and bad headers with line numbers. |
| `Agreement` | 114 | frozen dataclass | Confusion counts plus `accuracy`, `precision`, `recall`, `kappa`, `small_sample`. |
| `cohen_kappa` | 156 | `(tp, fp, fn, tn) -> float or None` | `(observed - expected) / (1 - expected)`; `None` when undefined. |
| `interpret_kappa` | 168 | `(kappa) -> str` | Landis and Koch verbal bands. |
| `calibrate` | 179 | `(results, labels, metric) -> Agreement` | Builds the 2x2 table against the metric's own `passed` flag. |
| `DEFAULT_SWEEP` | 203 | tuple, 0.10 ... 0.95 | Release 1.4: the candidate pass thresholds of `--sweep`. |
| `sweep_thresholds` | 206 | `(results, labels, metric, thresholds=DEFAULT_SWEEP) -> list[(float, Agreement)]` | Agreement at each threshold from the stored scores; unscored and unknown cases excluded. |
| `best_threshold` | 238 | `(rows) -> float \| None` | Highest kappa, then accuracy, then the lower threshold; optimistic by construction (Part XVI §174). |
| `labelling_sheet` | 248 | `(run, results) -> bytes` | CSV for human labelling, formula-prefix guarded (213). |

**Tests.** `tests/test_calibration.py` (39 tests per `docs/TESTING.md`), including the hand-computed example
(`test_kappa_hand_computed`, line 30: 20/5/10/15 gives observed 0.7, expected 0.5, kappa 0.4). Worked example and
limits: Part XIII §142.4.

---

## V.43 `src/rag_workbench/ui/auth.py` — optional access control (release 1.1, extended in 1.2 and 1.3)

**Path:** `src/rag_workbench/ui/auth.py` (261 lines). **Purpose.** A login in front of the whole Streamlit app. Two modes,
chosen by what is configured (accounts take precedence): **named accounts** created with `ragwb user add` (V.50), or the
**shared password** `RAGWB_APP_PASSWORD`; a no-op when neither exists (docstring, lines 1-13).

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `MAX_FAILURES`, `WINDOW_S`, `SESSION_KEY`, `USER_KEY` | 31-34 | `5`, `60.0`, `"_authenticated"`, `"_user"` | Per-key lockout parameters and the two session keys. |
| `GLOBAL_MAX_FAILURES`, `MAX_TRACKED_USERNAMES` | 35-36 | `30`, `1000` | The loose limit across all usernames per window; the bound on tracked names. |
| `LoginThrottle` | 45 | class with injectable clock | Thread-safe sliding-window limiter: `retry_after` (54), `record_failure` (63), `reset` (69). |
| `password_matches` | 80 | `(supplied, expected) -> bool` | `hmac.compare_digest` on UTF-8 bytes (constant time), used by the shared-password mode. |
| `ThrottleSet` | 84 | `(max_failures, window_s, global_max, clock)` | One limiter per username (including unknown names) plus one global limiter; memory bounded at 1,000 names. |
| `_throttle`, `_throttles` | 107, 112 | `@st.cache_resource` | One shared-password throttle and one `ThrottleSet` per server process. |
| `current_user` | 123 | `() -> str \| None` | The signed-in username (none in shared-password mode). |
| `require_login` | 132 | `(settings) -> None` | Shows the right form and calls `st.stop()` until valid credentials are entered (128-134). |
| `_login_with_accounts` | 151 | `(users) -> None` | Username and password form; normalises the name, checks the throttle, verifies, logs `sign-in ok/failed/refused`. |
| `_login_with_shared_password` | 182 | `(settings) -> None` | The release 1.1 form, unchanged in behaviour. |
| `visible_runs` | 219 | `(settings, runs) -> list` | Release 1.4: with `RAGWB_RUN_VISIBILITY=own` and named accounts, non-admins see their own runs and runs with no owner (219-228). |
| `render_account` | 231 | `(settings) -> None` | Sidebar "Signed in as …", a *Change password* expander (239-256; release 1.4) and a Sign out button. |

Called from `streamlit_app.py:20-21`. **Tests.** `tests/test_auth.py` (8 tests, shared password) and `tests/test_users.py`
(21 tests, accounts: sign-in gate, lockout, sign-out, `started_by`). **Limits:** throttle state is in memory and resets on
restart; the shared-password throttle is process-wide (a nuisance user can lock everyone out for a minute); passwords are
not encrypted in transit unless TLS is used (`start.py --ssl-cert`); a removed user's session now ends on its next page
load and roles gate the page scripts (release 1.3, Part XV §165); see Part XIII §144, Part XIV §156 and Part XV §165.

---

## V.44 `scripts/benchmark.py` — offline scale benchmark (release 1.1)

**Path:** `scripts/benchmark.py` (90 lines). Usage: `uv run python scripts/benchmark.py [--sizes N ...] [--workers W]`.
Generates a dataset of the requested size from the example document (`make_dataset`, 32-40), runs it offline in a
temporary data directory with four lexical metrics, and reports run time, throughput, read-back time, CSV export time,
peak Python memory (`tracemalloc`, measured in a separate pass since release 1.4) and database size (`bench`, 43-68). Exit status 1 if a run did not complete or lost a
case on read-back (84-86). Measured results (corrected in release 1.4: the first timings ran under `tracemalloc`, and the conclusion that four workers are slower
than one offline was withdrawn; four workers are about 15 % faster at 1,000 cases):
Part XIII §146. No automated test asserts timings.

---

## V.45 `scripts/live_smoke.py` — guarded live smoke test (release 1.1)

**Path:** `scripts/live_smoke.py` (106 lines). Usage: `uv run python scripts/live_smoke.py --yes-spend [--cases N]
[--skip-judge] [--pipeline rag|agent] [--retriever bm25|embedding|hybrid]`. **It makes paid API calls.** It refuses to run
without `--yes-spend` (39-42), without `OPENAI_API_KEY` (54-56), and with more than five cases (27, 43-45); it runs in a
temporary data directory (57-59) and prints PASS/FAIL per check (79-97). Its guards and failure path are tested
without spending (`tests/test_live.py`); **the success path has been run only against Groq's free tier (2 cases, 12 of 12 checks, Part XV §160), never against OpenAI itself.**
See Part XIII §147.

---

## V.46 Release 1.1 changes to existing files

| File | Change | Where described |
|---|---|---|
| `config.py` | `case_timeout_s`, `app_password`, `log_format`, `backups_dir`, `has_app_password`, `secret_values`; `RetrieverName` gains `hybrid`; `ENV_VARS` gains three variables | Part XIII §141, §144, §148 |
| `models.py` | `RunConfig.case_timeout_s`, `min_evidence`, `skip_headings`; `MetricResult.cost_usd`; `RunSummary.total_judge_cost_usd` | §141, §142 |
| `runner.py` | per-case time limit in a daemon thread; prices stored with the run | §141.1, §141.3 |
| `metrics/judge.py`, `metrics/base.py` | judge retry with jitter; cost capture; scores outside [0, 1] are errors | §141.2, §141.3, §149 |
| `retrieval.py`, `pipeline.py` | `HybridRetriever` (reciprocal-rank fusion) and its wiring | §142.1 |
| `providers.py`, `documents.py` | `min_evidence` abstention; `is_heading`, `drop_headings` | §142.2 |
| `aggregate.py` | `slice_results`, `metadata_keys`, judge-cost total | §142.3 |
| `text.py` | apostrophes inside words are deleted, not split on | §142.5 |
| `logging_setup.py` | `RedactingJsonFormatter`, `close_logging` | §143.5, §144.5 |
| `cli.py` | seven new commands, `--version`, new `run` options | §143, §148.2 |
| `start.py` | `--host`, `password_configured`, `host_problem` | §144.3 |
| `streamlit_app.py`, `ui/views/*` | login gate; slices, Health checks, hybrid / min-evidence / skip-headings controls | §142, §144 |
| `scripts/verify.py` | six steps (static analysis added), optional `--audit` | §145.1 |

---

## V.47 `src/rag_workbench/history.py` — tags, notes and run search (release 1.2)

**Path:** `src/rag_workbench/history.py` (80 lines). **Purpose.** The rules for organising a run history, shared by the CLI
and the UI: what a tag may look like, how notes are validated, and a plain case-insensitive search over the fields a person
remembers a run by (docstring, lines 1-6). Imports `re`, `collections.abc.Iterable` and `.models.RunRecord`.

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `MAX_TAGS`, `MAX_TAG_LENGTH`, `MAX_NOTES_CHARS` | 15-17 | `10`, `30`, `2000` | Limits. |
| `TagError` | 21 | `ValueError` subclass | An unacceptable tag or note. |
| `normalise_tags` | 25 | `(tags) -> list[str]` | Lowercase, strip, spaces to hyphens, de-duplicate in first-seen order, validate. |
| `parse_tag_list` | 41 | `(text) -> list[str]` | Commas or whitespace separate tags. |
| `validate_notes` | 46 | `(notes) -> str \| None` | Blank means no note; over 2,000 characters is refused. |
| `search_runs` | 63 | `(runs, query="", *, tag=None, status=None) -> list[RunRecord]` | Every query word must appear in the run's id, name, notes, tags, status, provider, pipeline, retriever or dataset/document file names (`_haystack`, 54). |

**Tests.** `tests/test_history.py` (14 tests). **Limits and rationale:** Part XIV §152.

---

## V.48 `src/rag_workbench/regression.py` — the regression gate (release 1.2)

**Path:** `src/rag_workbench/regression.py` (107 lines). **Purpose.** Decide whether a candidate run is measurably worse than
a baseline, per shared metric, using the paired bootstrap of V.19, and turn that into an exit code (docstring, lines 1-17).

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `Verdict`, `EXIT_OK`, `EXIT_REGRESSION`, `EXIT_UNJUDGED` | 28-29 | literal type; `0`, `3`, `4` | The five verdicts and the three exit statuses. |
| `Finding` | 33 | frozen dataclass | One metric: verdict, pairs, means, difference, interval. |
| `RegressionReport` | 45 | frozen dataclass | Findings, both error rates, `error_regression`, the settings; `exit_code` (54-59). |
| `check_regression` | 66 | `(baseline, baseline_cases, candidate, candidate_cases, *, max_drop=0.02, min_pairs=10, max_error_increase=0.05, metrics=None)` | Verdict per metric plus the error-rate rule. |
| `format_regression` | 88 | `(report) -> str` | The printed table, PASS / FAIL / NOT JUDGED line and the `possible` note. |

**Tests.** `tests/test_regression.py` (10 tests). **Limits and rationale:** Part XIV §153.

---

## V.49 `src/rag_workbench/abstention.py` — held-out tuning of `min_evidence` (release 1.2)

**Path:** `src/rag_workbench/abstention.py` (177 lines). **Purpose.** Choose the offline generator's abstention threshold on a
development half of the questions and report it on a held-out half next to the untuned default (docstring, lines 1-17).

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `THRESHOLDS`, `MIN_RELIABLE_UNANSWERABLE` | 33-34 | `0.0 … 0.9`; `30` | The search grid and the sample-size warning level. |
| `Setting` | 38 | frozen dataclass `(min_evidence, skip_headings)` | One point of the grid. |
| `Confusion` | 47 | frozen dataclass `(tp, fn, fp, tn)` | Abstention decisions with `abstain_recall`, `answer_rate`, `balanced_accuracy` (63-74). |
| `TuningReport` | 81 | dataclass | Chosen and baseline settings, development scores, test confusions, sizes, notes. |
| `should_abstain` | 92 | `(case) -> bool` | A question should be declined when its reference is itself an abstention. |
| `split_cases` | 96 | `(cases, salt="") -> (dev, test)` | Deterministic split by the parity of a SHA-256 byte. |
| `tune` | 121 | `(settings, pairs, *, thresholds=THRESHOLDS) -> TuningReport` | Grid search on development halves, report on test halves. |
| `format_report` | 160 | `(report) -> str` | The printed comparison. |

**Tests.** `tests/test_abstention.py` (6 tests). **Result, limits and rationale:** Part XIV §154 — the tuned setting is a poor
trade and the default stays off.

---

## V.50 `src/rag_workbench/users.py` — named accounts (release 1.2)

**Path:** `src/rag_workbench/users.py` (200 lines; 160 in release 1.2, roles in 1.3, management in 1.4). **Purpose.** An optional account store for the web app: one JSON file,
`<data dir>/users.json`, holding for each user a random salt, a scrypt hash and a creation time; never a password
(docstring, lines 1-8).

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `SCRYPT_N`, `SCRYPT_R`, `SCRYPT_P` | 27 | `2**14`, `8`, `1` | The hash cost. |
| `MIN_PASSWORD_LENGTH`, `MAX_PASSWORD_LENGTH`, `USERNAME_RE` | 28-30 | `10`, `200`, `^[a-z0-9][a-z0-9._-]{0,31}$` | Input rules. |
| `UserError` | 40 | `ValueError` subclass | Bad username, password or users file. |
| `normalise_username` | 44 | `(name) -> str` | Strip, lowercase, validate. |
| `_hash` | 52 | `(password, salt) -> bytes` | `hashlib.scrypt`, 32-byte output. |
| `UserStore` | 56 | `(path)` | `names` (74), `has_users` (77, fails closed on a damaged file), `add` (92), `role_of` (108), `entries` (119), `admins` (125), `_guard_last_admin` (129), `set_password` (139), `set_role` (155), `remove` (168), `verify` (182: constant-time compare; unknown users cost the same hashing work). Release 1.4 added `entries`, `admins`, `_guard_last_admin`, `set_password` and the `force` argument. |

**Tests.** `tests/test_users.py` (21 tests). **Limits and rationale:** Part XIV §156, including the empty-users-file gap of
§156.7.

---

## V.51 `src/rag_workbench/metrics/semantic.py` — optional embedding metrics (release 1.2)

**Path:** `src/rag_workbench/metrics/semantic.py` (123 lines). **Purpose.** Two offline metrics that compare meaning with a
local sentence-embedding model through the optional `fastembed` package: `semantic_similarity` (answer versus reference)
and `semantic_context_recall` (best chunk versus reference) (docstring, lines 1-20).

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `INSTALL_HINT` | 34 | string | The message shown when the package is missing. |
| `Embedder` | 38 | `Protocol` | `embed(texts) -> list[list[float]]`. |
| `semantic_available` | 42 | `() -> bool` | Is `fastembed` importable? |
| `cosine` | 46 | `(a, b) -> float` | Cosine similarity in [-1, 1]; 0.0 for a zero vector. |
| `FastEmbedEmbedder` | 55 | `(model_name)` | The real embedder (lazy import, lock around the shared ONNX session). **Never executed in this project.** |
| `local_embedder` | 72 | `@lru_cache(maxsize=2)` | One embedder per model name. |
| `SemanticMetric` | 76 | `Metric` subclass | Builds its embedder on first use; scores clipped to [0, 1]. |
| `SEMANTIC_SPECS`, `build_semantic_metric` | 106, 118 | specs (threshold 0.7); factory | Registry entries and construction. |

**Tests.** `tests/test_semantic.py` (10 tests, with a deterministic stand-in embedder). **Limits:** Part XIV §155.4.

---

## V.52 Release 1.2 changes to existing files, and new non-code files

| File | Change | Where described |
|---|---|---|
| `config.py` | `_find_project_root` (`RAGWB_HOME`, checkout check, working-directory fallback), packaged `EXAMPLES_DIR`, `local_embedding_model`, `users_path`, `has_users`, `login_required`, `user_accounts_configured` in `public_dict`; two `ENV_VARS` entries | Part XIV §155, §156, §157 |
| `models.py` | `RunRecord.tags`; `RunConfig.started_by` | §152, §156.4 |
| `storage.py` | schema 3, column-based migration, `set_tags`, `set_notes` | §152.2 |
| `cli.py` | five new commands (`tag`, `note`, `regress`, `tune-abstention`, `user`), filtered `list` | §152-§154, §156 |
| `metrics/base.py`, `metrics/__init__.py` | `semantic` family, `requires_local_model`, refusal with an install hint | §155 |
| `ui/auth.py`, `streamlit_app.py` | accounts mode, `ThrottleSet`, `current_user`, `render_account` | §156 |
| `ui/components.py`, `ui/views/*` | `st.header` section headings (h2) and CSS; Overview search and tag filter; Results *Tags and notes* expander; `started_by` on new runs; semantic metrics offered when installed | §152.4, §158 |
| `start.py` | `accounts_configured`, `tls_problem`, `--ssl-cert/--ssl-key`, HTTPS readiness probe | §156.6 |
| `pyproject.toml` | version 1.2.0; wheel `force-include` of `examples` | §157.3 |
| `scripts/make_example_pdf.py` | optional document-name argument | §151.2 |
| `Dockerfile`, `.dockerignore` | new; the image has never been built | §157.4 |
| `examples/` | three documents (Markdown and PDF) and three tagged datasets | §151 |

---

## V.53 `src/rag_workbench/ratelimit.py` — request pacing (release 1.3)

**Path:** `src/rag_workbench/ratelimit.py` (55 lines). **Purpose.** Space model operations evenly so a provider's
request-rate quota is not hit. **Imports:** standard library only (`threading`, `time`).

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `RateLimiter` | 19 | `class RateLimiter(max_per_minute, *, clock, sleep)` | `interval = 60 / max_per_minute` (`:26`); `acquire()` reserves the next slot under a lock and sleeps until it (`:32-43`); `None` means no limit and `acquire` returns 0 at once; zero or negative raises `ValueError` (`:24-25`). The clock and the sleep function are injectable so tests never wait. |
| `limiter_for` | 50 | `(max_per_minute) -> RateLimiter` | A process-wide registry keyed by the setting, so answer generation and judge metrics share one limiter (`:46-55`). |

**Callers.** `EvaluationRunner._generate_with_retries` (`runner.py:234`) and `JudgeMetric.score` (`metrics/judge.py:66-67`,
constructed with `limiter_for(...)` at `metrics/judge.py:135`). **Tests.** `tests/test_ratelimit.py` (8 tests). **Limits and design:**
Part XV §161.

---

## V.54 `src/rag_workbench/judge_noise.py` — judge call-to-call noise (release 1.3)

**Path:** `src/rag_workbench/judge_noise.py` (116 lines). **Purpose.** Re-score the stored answers of a run several times and
report how much a judge disagrees with itself. **Imports:** `statistics`, internal `metrics.base` and `models`.

| Name | Line | Signature | Purpose |
|---|---:|---|---|
| `NoiseRow` | 30 | frozen dataclass | One row per metric: cases with at least two usable repeats, repeats, within SD, between SD, verdict flips, failed measurements, skipped cases; properties `noise_to_signal` (within / between, `None` when either is missing or the between SD is 0) and `small_sample` (fewer than `MIN_RELIABLE_CASES = 10`). |
| `estimate_operations` | 51 | `(cases, n_metrics, repeats) -> int` | Judge measurements a call would make (answered cases x metrics x repeats). |
| `measure_noise` | 55 | `(cases, metrics, thresholds, repeats, *, progress) -> list[NoiseRow]` | Fewer than two repeats raises `ValueError`; failed measurements are counted as errors and excluded, never scored as zero. |
| `format_noise` | 95 | `(rows) -> str` | The table printed by `ragwb judge-noise`, with notes for small samples, noise/signal above 0.5, excluded failures and a between SD of 0. |

**Tests.** `tests/test_judge_noise.py` (8 tests). **Design and the one measurement made:** Part XV §164.

---

## V.55 Release 1.3 changes to existing files

| File | Change | Where described |
|---|---|---|
| `config.py` | `RetrieverName` gains `local` and `hybrid-local`; `local_model_dir` (`<data dir>/models`); `max_requests_per_minute` and `RAGWB_MAX_REQUESTS_PER_MINUTE` | Part XV §161, §162 |
| `errors.py` | `TransientProviderError.retry_after_s`, `backoff_delay`, `_unwrap`, `_retry_after`; "OpenAI-compatible API" in transient messages | §160, §161 |
| `retrieval.py`, `pipeline.py` | `LocalEmbeddingRetriever`; `build_retriever` branches for `local` and `hybrid-local` | §162 |
| `metrics/semantic.py`, `metrics/__init__.py` | `cache_dir` and `local_embedder(model, cache_dir)`, shared by the retriever and the semantic metrics | §162.2 |
| `metrics/judge.py`, `runner.py` | pacing (`limiter_for(...).acquire()`) and `backoff_delay` in both retry loops | §161 |
| `cli.py` | `judge-noise`; `user --role` and `user set-role`; local retrievers in `run --retriever` | §162, §164, §165 |
| `users.py` | `ROLES`, `DEFAULT_ROLE`, `role_of`, `set_role`; accounts with no stored role count as `editor` | §165 |
| `ui/auth.py`, `ui/views/new_run.py`, `ui/views/results.py` | `PERMISSIONS`, `current_role`, `can`; session ends when the account is removed; role shown in the sidebar; read-only pages for viewers; local retriever options when the extra is installed | §165 |
| `pyproject.toml`, `uv.lock`, `.env.example` | optional extra `semantic = [fastembed]`; version 1.3.0; two new variables | §162, §168 |
| `calibration/` | labelling sheet and a re-importable run bundle for the judge-versus-human check | §163 |

---

## V.56 `src/rag_workbench/ui/views/users.py` — the Accounts page (release 1.4)

**Path:** `src/rag_workbench/ui/views/users.py` (72 lines). **Purpose.** An admin-only page to list accounts, add one, change a
role, reset a password and remove an account. It is a page script (no functions of its own except a helper), registered only for an
admin of an installation with named accounts (see V.2, lines 39-40).

**Imports.** pandas and streamlit; internal `ui.auth` (`current_role`, `current_user`), `ui.state.context_or_stop` and `users`
(`MIN_PASSWORD_LENGTH`, `ROLES`, `UserError`, `UserStore`).

| Lines | Behaviour |
|---|---|
| 10-15 | gets the context and, unless accounts exist and the role is `admin`, shows "Managing accounts needs an admin account." and stops |
| 19-23 | role legend and the table of `UserStore.entries()` (`user`, `role`, `created`; no secret material) |
| 26-36 | `flash(action, ...)`: runs a store action; a `UserError` or a missing user becomes an on-page error |
| 39-47 | *Add an account* form (username, password, role; default `editor`) |
| 49-62 | *Change an account*: select an account, set its role, reset its password (no check of the old password) |
| 64-72 | *Remove this account* expander: typing the username enables the button; the signed-in admin cannot remove themself |

**Tests.** `tests/test_accounts_admin.py` (11 tests), including the routing test for non-admins (`:79`) and the admin journey
(`:90`). **Limits and rationale:** Part XVI §173. The page has no screenshot and was not audited with axe-core.

---

## V.57 `scripts/wheel_check.py` and `scripts/benchmark_documents.py` — release 1.4 verification scripts

`scripts/wheel_check.py` (86 lines) builds the wheel, installs it with its dependencies from PyPI into a throwaway virtual
environment and runs ten checks from an empty folder (`check`, 26; `main`, 36; `verify.py --wheel` runs it). It needs the network and
`uv`; it removes everything it creates. `scripts/benchmark_documents.py` (104 lines) generates synthetic text documents and a
200-page PDF from the vocabulary of the bundled example and reports load time, chunk count, BM25 index time, query p50 and p95 and
Python-level peak memory (`bench`, 57; `main`, 80). It was corrected in release 1.4 to time with no tracer and measure memory in a separate pass
(Part XVI §175.4). Neither script is run by the test suite. **Described in:** Part XVI §175 and §176.

---

## V.58 Release 1.4 changes to existing files

| File | Change | Where described |
|---|---|---|
| `maintenance.py` | `restore_store` | Part XVI §171 |
| `storage.py` | `RunStore.heartbeat` | §171.3 |
| `cli.py` | `restore`; `user set-password` and `--force`; `calibrate --sweep` and `--rescore` (`_rescored`); `_read_password`; `tune-abstention` uses `EXAMPLES_DIR` | §171, §173, §174, §176.2 |
| `calibration.py` | `DEFAULT_SWEEP`, `sweep_thresholds`, `best_threshold` | §174 |
| `users.py` | `entries`, `admins`, `_guard_last_admin`, `set_password`, `force` on `remove` and `set_role` | §173 |
| `ui/auth.py` | `visible_runs`; *Change password* expander | §173.3, §173.4 |
| `config.py` | `run_visibility` and `RAGWB_RUN_VISIBILITY` | §173.4 |
| `retrieval.py` | BM25 inverted index (`_postings`, `_len_norm`); identical scores | §175 |
| `demo.py`, `services.py` | use `EXAMPLES_DIR` | §176.2 |
| `streamlit_app.py` | conditional Accounts page | §173.1 |
| `ui/views/overview.py`, `results.py`, `compare.py` | list runs through `visible_runs` | §173.4 |
| `scripts/verify.py` | `--wheel` | §176.1 |
| `pyproject.toml`, `uv.lock` | version 1.4.0 | §179 |
