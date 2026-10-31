# Part VIII — Setup and operation

This part is the operator's manual: how to install the RAG Evaluation Workbench, start it, configure it, run
evaluations from the browser and the command line, find outputs and logs, reset it, and fix the problems that
are known to occur. The primary way to install and run the product is one command, `python start.py`
(§81). The manual route with uv and the `ragwb` CLI remains available and is described alongside it.

Commands shown with output were run on 2026-10-24 on a Windows 11 machine (Git Bash and PowerShell). Everything
that writes data was pointed at a temporary directory with `RAGWB_DATA_DIR`, never at the project's own `data/`.

## 80. Supported Python versions and prerequisites

### 80.1 Python

`pyproject.toml:6` declares `requires-python = ">=3.12"`, and `.python-version` pins `3.12`. When uv creates the
environment it honours the pin and uses a uv-managed CPython 3.12 rather than whatever Python is on `PATH`: the
project's `.venv/pyvenv.cfg` records `home = C:\Users\omjee\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none`
and `version_info = 3.12`, and the environment's interpreter reports:

```text
> .venv\Scripts\python.exe --version
Python 3.12.15
```

**Supported** therefore means CPython 3.12: it is the only version on which the code and the test suite were run.
The declared range allows 3.13 and later, but the application has not been run on them; treat them as untested.

The launcher `start.py` is a different case. It uses only the standard library (`start.py:15`), so any Python 3
can *run* it; on the development machine it was started with the system Python 3.13.3 and created the 3.12
environment through uv. Only when uv is missing does the launcher need Python 3.12+ itself, because it then builds
the environment with that interpreter (`start.py:54-57`).

### 80.2 uv (recommended)

The project is managed with [uv](https://docs.astral.sh/uv/) (version 0.13.1 on the development machine). uv
provides the Python interpreter, the virtual environment, the lock file `uv.lock` and the `uv run` launcher.
`start.py` uses uv when it finds it on `PATH` and falls back to the standard `venv` module otherwise (§81.3).

### 80.3 Optional: Chrome or Edge

Any modern browser can use the app. Google Chrome or Microsoft Edge specifically is needed only for the book
tooling: `docs/project-book/tools/capture_screenshots.py` drives a headless Chrome/Edge through the DevTools
protocol and looks for the executables at the standard Windows install paths or on `PATH`
(`capture_screenshots.py:29-33`, `50-54`). No other system software is required.

### 80.4 Network

Installing needs access to PyPI (and, the first time, to uv's Python download source). Running does not: the
default configuration — and the first-launch example runs — are fully offline. Only the OpenAI provider, the
embedding retriever and the four judge metrics contact the network (Part XI, §114.2).

## 81. Installing and starting: `python start.py`

### 81.1 The command

From the project root:

```bash
python start.py
```

(On systems where the Python 3 executable is called `python3`, use that.) The module docstring states the
contract (`start.py:1-16`): prepare the environment, create example runs on the first launch, start the app on
this machine only (or another host with a login, optionally over TLS), open it in the browser; Ctrl+C stops it. Nothing is installed outside the project folder.

### 81.2 What it does, step by step

1. **Prepare the environment** (`prepare_environment`, `start.py:47-63`). If `uv` is on `PATH`, it runs
   `uv sync --frozen --inexact` with `UV_HTTP_TIMEOUT` defaulting to 180 seconds (`start.py:48-53`).
   * `--frozen` installs exactly the versions in `uv.lock` and never rewrites the lock;
   * `--inexact` leaves extra packages already in `.venv` in place (for example the `docs` group, §82.2);
   * the sync creates `.venv/` if needed, installs the runtime dependencies of `pyproject.toml:7-18`, the default
     `dev` group (`[tool.uv] default-groups = ["dev"]`, `pyproject.toml:45-46`: pytest, pytest-cov, ruff, mypy and pip-audit), and the
     project itself in editable mode — the build backend is hatchling (`pyproject.toml:35-43`), and the editable
     install appears as `.venv/Lib/site-packages/_editable_impl_rag_evaluation_workbench.pth`.
   If the sync fails the launcher stops with "`uv sync` failed; see the messages above (a slow network may need a
   retry)." (`start.py:52`).
2. **Create the example runs on the first launch** (`store_is_empty`, `create_examples`; `start.py:66-81`, `203-204`).
   The launcher asks the application, through the environment's interpreter, how many runs the store holds. If
   the answer is 0 it calls `rag_workbench.demo.seed_demo_runs`, which performs five genuine offline evaluations of
   the bundled honeybee data (`src/rag_workbench/demo.py:24-47`; §83.2). If creating them fails, the app still
   starts without them (`start.py:80-81`). If the run store cannot even be opened, the launcher stops and prints the
   application's error (`start.py:70-71`).
3. **Pick a port** (`free_port`, `start.py:132-137`): the first port from 8501 (or `--port`) on which nothing accepts a
   connection on `127.0.0.1`, trying 50 ports.
4. **Start Streamlit** (`launch`, `start.py:157-189`) as
   `.venv/…/python -m streamlit run streamlit_app.py --server.port <port> --server.address <host>
   --server.headless true --browser.gatherUsageStats false` (plus `--server.sslCertFile`/`--server.sslKeyFile` with TLS), with `DEEPEVAL_TELEMETRY_OPT_OUT=1` in its environment.
   The address (`localhost` unless `--host` is given) and the statistics setting are passed on the command line, so they
   hold even if `.streamlit/config.toml` were not read.
5. **Wait until it is healthy** (`wait_until_ready`, `start.py:140-154`): poll `http://localhost:<port>/_stcore/health`
   for up to 90 s (`https://` with TLS, certificate not verified for this probe of the launcher's own server), then print `RAG Evaluation Workbench is running at http://localhost:<port>  (Ctrl+C to stop)` and
   open the browser.
6. **Stop on Ctrl+C**: terminate Streamlit, wait up to 10 s, then kill it (`start.py:182-188`).

### 81.3 Fallback without uv

If uv is not installed (`start.py:54-63`), the launcher requires the Python running it to be 3.12 or newer
(otherwise it exits with a message pointing to uv), creates `.venv` with `python -m venv` if it does not exist, and
runs `.venv/…/python -m pip install --quiet -e . pytest pytest-cov`. The result is the same editable install with
the test tools, but **not** pinned by `uv.lock`: pip resolves the version ranges in `pyproject.toml` afresh, so the
installed versions can differ from the ones the project was tested with. This path was not exercised for this
book (uv is installed on the development machine).

### 81.4 Flags

| Flag | Effect | Code |
|---|---|---|
| `--port N` | preferred port; the first free port from N is used (default 8501) | `start.py:194`, `208` |
| `--host H` | address to listen on (default `localhost`); any other address makes the launcher exit unless `RAGWB_APP_PASSWORD` is set in the environment or `.env`, or user accounts exist (`ragwb user add`) | `start.py:195-197`, `105-110`, `198-201` |
| `--ssl-cert F`, `--ssl-key F` | serve over HTTPS with a PEM certificate and key (both required; each file must exist); without TLS on a non-local host the launcher prints a warning that credentials cross the network unencrypted | `start.py:198-199`, `113-122`, `155-159` |
| `--no-browser` | do not open a browser window | `start.py:200` |
| `--no-examples` | skip the first-launch example runs even if the store is empty | `start.py:201`, `203` |
| `--setup-only` | prepare the environment and the examples, then exit without starting the app | `start.py:202`, `205-207` |

### 81.5 Observed first launch

Run with a fresh temporary data directory and a blank key:

```text
$ RAGWB_DATA_DIR=<temp>/start-data python start.py --setup-only
[start] $ C:\Users\omjee\.local\bin\uv.EXE sync --frozen --inexact
Checked 115 packages in 20ms
[start] $ ...\.venv\Scripts\python.exe -c from rag_workbench.services import open_context; print(len(open_context(console_logging=False).store.list_runs()))
[start] first launch: running the offline example evaluations (a few seconds)
[start] $ ...\.venv\Scripts\python.exe -c from rag_workbench.demo import seed_demo_runs; ...
  offline-bm25-k1: completed
  offline-bm25-k3: completed
  offline-bm25-k5: completed
  unanswerable-k3: completed
  injected-failures-30pct: partial
[start] setup complete
```

(the two long `-c` command lines are abridged). Exit code 0; wall-clock time 7.25 s, with the environment already
synchronised. The temporary directory then contained `runs.db` and `logs/rag_workbench.log`. Running the same
command again printed the sync and probe lines and `[start] setup complete` without the example step — the
store was no longer empty — and took 2.88 s. "Checked 115 packages" means the environment already matched the
lock; a first install on a new machine downloads and installs those packages instead, which takes minutes
on a slow network.

The interactive mode (`python start.py`, without `--setup-only`) was not run for this part, to avoid starting a
server against the project's data directory; the launcher's behaviour in that mode is described from the code above.

### 81.6 Manual alternative with uv

Everything `start.py` does can be done by hand:

```bash
uv sync                                   # .venv, locked dependencies, dev group, editable install
uv sync --group docs                      # optional: adds `markdown` for building the project book
uv run python scripts/seed_demo_runs.py   # optional: the five example runs (§89.3)
uv run streamlit run streamlit_app.py     # the app, on http://localhost:8501
```

`uv sync` without `--frozen` re-locks if `uv.lock` is out of date with `pyproject.toml`; use
`uv sync --frozen` to install exactly the lock. To check the lock without changing anything:
`uv lock --check --offline` (this is also step 2 of `scripts/verify.py`, `scripts/verify.py:66-72`).

## 82. Configuration

### 82.1 Where settings come from

All settings are read once, by `config.load_settings` (`src/rag_workbench/config.py:204-232`), from environment
variables. Before reading, it loads `.env` **from the project root** with `override=False`
(`config.py:211-213`): a variable already set in the process environment wins over `.env`. Blank values are
treated as unset (`config.py:179-180`). Settings are frozen (`config.py:37`), and the Streamlit app reads them when
its context is first created (`ui/state.py:17-20`), so **changes require a restart** — the Settings page says so
(`ui/views/settings.py:30-31`).

```bash
cp .env.example .env                 # Git Bash
Copy-Item .env.example .env          # PowerShell
```

`.env.example` is entirely optional content: "Everything is optional: without OPENAI_API_KEY the workbench runs
fully offline" (`.env.example:1-2`). `.env` is ignored by Git (`.gitignore:1-2`).

### 82.2 Variables

The authoritative list is the `ENV_VARS` mapping (`config.py:173-197`); the generated table
`docs/project-book/generated/env-vars.md` is produced from it and from the `Settings` field defaults and
constraints. In summary:

| Group | Variables | Defaults / constraints |
|---|---|---|
| OpenAI access | `OPENAI_API_KEY`, `OPENAI_BASE_URL` | unset |
| Models | `RAGWB_GENERATOR_MODEL`, `RAGWB_EMBEDDING_MODEL`, `RAGWB_JUDGE_MODEL` | `gpt-4o`, `text-embedding-3-large`, `gpt-4o` |
| Reliability | `RAGWB_REQUEST_TIMEOUT_S`, `RAGWB_CASE_TIMEOUT_S` (new in 1.1), `RAGWB_MAX_RETRIES`, `RAGWB_RETRY_BASE_DELAY_S`, `RAGWB_MAX_WORKERS` | 60 s (0–600], 600 s (0–3,600], 3 [0–10], 1 s [0–60], 4 [1–32] |
| Cost | `RAGWB_PRICE_INPUT_PER_MTOK`, `RAGWB_PRICE_OUTPUT_PER_MTOK` | unset → cost reported as unknown |
| Locations | `RAGWB_DATA_DIR`, `RAGWB_DATASET`, `RAGWB_DOCUMENT` | `data`, `examples/datasets/honeybees.jsonl`, `examples/documents/honeybees.pdf` (`config.py:60-62`) |
| Project root | `RAGWB_HOME` (new in 1.2; read at import time, from the environment only, not from `.env`) | unset → the checkout the package lives in, else the current directory (`config.py:21-34`); see §82.3 |
| Local embedding model | `RAGWB_LOCAL_EMBEDDING_MODEL` (new in 1.2) | `BAAI/bge-small-en-v1.5`; used by the optional semantic metrics and, since 1.3, by the `local` and `hybrid-local` retrievers (`config.py:72`, `:180`); the model is cached in `<data dir>/models` (`config.py:113-115`) |
| Request pacing | `RAGWB_MAX_REQUESTS_PER_MINUTE` (new in 1.3) | unset → no pacing; otherwise a number greater than 0 and at most 6000 (`config.py:79`, `:185`); see Part XV §161 |
| Input limits | `RAGWB_MAX_DATASET_BYTES`, `RAGWB_MAX_DOCUMENT_BYTES`, `RAGWB_MAX_CASES`, `RAGWB_MAX_FIELD_CHARS` | 5,000,000; 25,000,000; 5,000; 20,000 |
| Logging | `RAGWB_LOG_LEVEL`, `RAGWB_LOG_FORMAT` (new in 1.1) | `INFO`, one of DEBUG, INFO, WARNING, ERROR, CRITICAL (`config.py:92-103`); `text`, or `json` for one redacted JSON object per line (`config.py:93`) |
| Run visibility | `RAGWB_RUN_VISIBILITY` (new in 1.4) | `shared` (default): every signed-in user sees every run; `own`: with named accounts, non-admins see only runs they started plus runs with no owner, in the web pages only (`config.py:94`, `:198`; Part XVI §173.4) |
| Access | `RAGWB_APP_PASSWORD` (new in 1.1); user accounts in `<data dir>/users.json` (new in 1.2, managed with `ragwb user`) | neither → no login; the shared password → one password for everybody; accounts → named sign-ins (they take precedence), and `start.py --host` may then listen on a non-local address (`config.py:66`, `:119-128`, `ui/auth.py:132-140`) |

`OPENAI_API_KEY` keeps the name the OpenAI SDK and DeepEval expect; every other variable has the `RAGWB_` prefix
(`config.py:3-5`). `OPENAI_BASE_URL` is passed to every OpenAI client the workbench builds (`pipeline.py:139`,
`168-171`; `metrics/judge.py:113-114`), which allows an OpenAI-compatible endpoint. Release 1.3 exercised this against Groq's free tier (generation and the judge metrics, not embeddings); OpenAI itself was not exercised (Part XV §160).

All settings apply equally to `start.py`, which passes its environment on to every process it starts. In
particular `RAGWB_DATA_DIR` decides which run store the launcher probes and seeds.

### 82.3 Path resolution

The three path variables are resolved against the **project root**, not the current directory, when relative
(`config.py:221-223`); `~` is expanded. The project root is `RAGWB_HOME` when that is set; otherwise the directory two levels above `config.py` when it holds a
`pyproject.toml` (a checkout); otherwise, for an installed wheel, the current directory, so data is never written into
`site-packages` (`config.py:21-34`, Part XIV §157). So `RAGWB_DATA_DIR=data` always means `<project>/data`, wherever a command is run from, and an
absolute path is used as given (`tests/test_config.py:17-25` checks both).

### 82.4 Validation

Values are validated by pydantic; a bad value raises `ConfigError` naming the *variable* (`config.py:226-232`):

```text
$ RAGWB_MAX_WORKERS=99 python -m rag_workbench list
error: Invalid configuration: RAGWB_MAX_WORKERS: Input should be less than or equal to 32
```

(exit code 1). In the UI the same error appears as "Configuration problem: …" followed by "Fix the variable in
`.env` (see `.env.example`) and restart the app." (`ui/state.py:23-29`). Under `start.py` an invalid value already
stops the launcher at the store probe, which prints the application's error (`start.py:70-71`).

### 82.5 Seeing the effective configuration

The **Settings & metrics** page shows `Settings.public_dict()` — every setting, with the key replaced by the flag
`openai_api_key_configured` (`config.py:163-169`, `ui/views/settings.py:29-33`) — plus the variable-to-setting
mapping, the metric catalogue and the storage paths.

## 83. Example data and example runs

### 83.1 Files in `examples/`

All example data was written for this project. Release 1.2 added three more documents, each in Markdown and PDF form (a title and 14 paragraphs, so 15 chunks), with a 30-question dataset tagged by `type`, `difficulty` and `topic` (Part XIV §151): `volcanoes`, `coffee` and `lighthouses`. The honeybee assets, which the first-launch example runs use, are:

| Path | Content | `ragwb validate` output |
|---|---|---|
| `examples/documents/honeybees.md` | the source text: a title line and ten paragraphs about honeybee colonies | — |
| `examples/documents/honeybees.pdf` | the same text rendered to a 2-page PDF by `scripts/make_example_pdf.py`; yields **11 chunks**: the title `p1-b1` ("Honeybees: Life Inside the Colony"), paragraphs `p1-b2` … `p1-b10` and `p2-b1` | — |
| `examples/datasets/honeybees.jsonl` | the default dataset: 20 questions `q01`–`q20`, all with reference answers | `honeybees.jsonl: 20 cases, 20 with reference answers` / `valid` |
| `examples/datasets/honeybees_unanswerable.jsonl` | 6 questions: `u1`–`u4` not answerable from the document (reference = the abstention sentence), `a1`–`a2` answerable; `metadata.type` marks which | `honeybees_unanswerable.jsonl: 6 cases, 6 with reference answers` / `valid` |
| `examples/datasets/honeybees_paraphrased.csv` | 5 questions `p1`–`p5` in CSV form with an extra `topic` column (becomes metadata) | `honeybees_paraphrased.csv: 5 cases, 5 with reference answers` / `valid` |

The validation lines were produced on 2026-10-24; each command exited with code 0. The PDF exists so that the
PDF extraction path has a bundled example; `scripts/make_example_pdf.py` regenerates it deterministically from the
Markdown file, one text block per paragraph (`scripts/make_example_pdf.py:1-8`). The `test_real_pdf_chunks` test
pins the 11-chunk result (`tests/test_documents.py:7-14`).

### 83.2 The five example runs

`rag_workbench.demo.demo_configs` (`src/rag_workbench/demo.py:24-39`) defines the runs that `start.py` creates on
the first launch and `scripts/seed_demo_runs.py` creates on request:

| Key | Run name | Configuration | Observed result |
|---|---|---|---|
| `k1` | `offline-bm25-k1` | default data, the four default lexical metrics, k = 1 | completed; token F1 0.404, context recall 0.857 |
| `k3` | `offline-bm25-k3` | same, k = 3 | completed; token F1 0.346, context recall 0.885 |
| `k5` | `offline-bm25-k5` | same, k = 5 | completed; token F1 0.346, context recall 0.892 |
| `unanswerable` | `unanswerable-k3` | `honeybees_unanswerable.jsonl`, metrics exact match, token F1, context recall, groundedness | completed; exact match 0.000 on 6 scored; context recall skipped for the 4 unanswerable cases |
| `failures` | `injected-failures-30pct` | k = 3, `offline_failure_rate = 0.3` | partial: 17 ok, 3 errors (`q03`, `q16`, `q17`) |

Results are from `ragwb show` on the runs created by the launcher; they are deterministic and were reproduced by the
CLI runs in §85.4. Two observations worth knowing before reading them:

* **Deeper retrieval lowers the answer-overlap scores here.** Going from k = 1 to k = 3 *lowers* token F1 (paired
  difference −0.057, 95 % CI −0.116 to −0.008, which excludes zero) while context recall rises only slightly
  (0.857 → 0.885 → 0.892 for k = 1/3/5). The extractive baseline picks the best-matching sentences from all
  retrieved chunks, and extra chunks offer more off-target sentences. k = 5 produces the same answers as k = 3.
* **The baseline never abstains** on `u1`–`u4`: every question shares some content word with the document, so it
  always finds a sentence to return (exact match 0 of 6). Its answer to `a2` begins with the title chunk, because a
  title has no sentence punctuation and is treated as one sentence.

## 84. Running the application

### 84.1 Starting the Streamlit app

`python start.py` (§81) is the normal way. It prints the URL, by default <http://localhost:8501>, and opens it.
The manual equivalent is:

```bash
uv run streamlit run streamlit_app.py
```

`.streamlit/config.toml` is read from the directory Streamlit is started in, so start it from the project root:

| Setting | Value | Effect |
|---|---|---|
| `browser.gatherUsageStats` | `false` | no Streamlit usage statistics (`config.toml:3-5`) |
| `client.toolbarMode` | `"minimal"` | hides developer/deploy controls (`config.toml:7-9`) |
| `server.maxUploadSize` | `25` | 25 MB upload ceiling, matching the document limit (`config.toml:11-14`) |
| `server.headless` | `true` | Streamlit does not open a browser window itself (`config.toml:15`) |
| `server.address` | `"localhost"` | listen on this machine only; the config comment notes there are no accounts, and the optional shared password (Part XIII §144) is what allows another address (`config.toml:16-17`) |
| `theme.primaryColor` | `#3b5bdb` | accent colour; light/dark follows the viewer (`config.toml:19-21`) |

Without an explicit address, the installed Streamlit (1.66.1) binds all interfaces (Part XI, §114.4).
`start.py` always passes `--server.address localhost`; if you start Streamlit by hand from another directory, pass
it yourself. Do not pass `--server.address 0.0.0.0` (or another external address) unless the network is trusted:
anyone who can reach the port can read, start and delete runs.

The entry point sets `DEEPEVAL_TELEMETRY_OPT_OUT=1` before anything else (`streamlit_app.py:10`), configures the
page, and registers six pages in three groups (`streamlit_app.py:23-37`): **Evaluate** — Overview, New evaluation;
**Analyse** — Run results, Compare runs; **Data & system** — Datasets & retrieval, Settings & metrics; an admin of an installation with
accounts also sees **Admin** — Accounts (`streamlit_app.py:39-40`, release 1.4). On first use
the app opens the run store, creating `data/runs.db` and `data/logs/` if they do not exist (`services.py:27-35`,
`storage.py:64-83`).

### 84.2 First look after `start.py`

After a first launch the Overview lists the five example runs, so every page has real content: Run results for any
of them, Compare runs across `offline-bm25-k1`, `-k3` and `-k5`, the failed cases of `injected-failures-30pct`, and
the abstention behaviour in `unanswerable-k3`. With `--no-examples` (or after deleting all runs), the Overview
instead shows "No evaluations run yet." and a link to configure one (`ui/views/overview.py:28-33`).

### 84.3 A new evaluation in the UI

1. **New evaluation.** The defaults are valid: dataset `examples/datasets/honeybees.jsonl` ("20 cases · 20 with
   reference answers"), document `examples/documents/honeybees.pdf` ("11 chunks extracted"), provider Offline,
   pipeline Retrieve → generate, retriever BM25, k = 3, and the four default lexical metrics (token F1, ROUGE-L,
   context recall, groundedness). These strings are asserted by the UI test
   `test_new_run_journey_offline_then_results_and_compare` (`tests/test_ui.py:85-115`).
2. Press **Run evaluation**. A progress bar and the last eight case lines are shown while it runs
   (`new_run.py:210-224`); then "Run **<name>** finished: completed · 20/20 cases succeeded" and one tile per metric.
3. **Inspect this run** opens **Run results**: summary statistics with bootstrap intervals, the per-case table,
   case detail with the retrieved chunks, the stored configuration, and exports.

The evaluation itself is short: for a 20-case offline run the interval between the "started" and "finished" log
lines is a fraction of a second. The first run in a fresh server process also pays one-time initialisation
(imports, opening the PDF). No precise UI timing was measured for this part.

### 84.4 Running without credentials

Nothing needs to be configured. Without `OPENAI_API_KEY`:

* the Overview shows the key as `not set` (`overview.py:25-26`);
* the New evaluation page offers only the BM25 retriever (`new_run.py:108`; with the optional `semantic` extra installed it also offers the two local retrievers) and only the five lexical metrics
  (plus the two semantic metrics if `fastembed` is installed; `new_run.py:130-131`), and explains "Judge metrics (answer relevancy, faithfulness, context relevancy, correctness)
  need OPENAI_API_KEY." (`new_run.py:138-139`);
* selecting the OpenAI provider shows "OPENAI_API_KEY is not set. Add it to `.env` and restart to use OpenAI." and
  disables the Run button with "Cannot start yet: OpenAI is selected but OPENAI_API_KEY is not set."
  (`new_run.py:101-102`, `184-189`; asserted by `test_openai_option_explains_missing_key`, `tests/test_ui.py:129-135`);
* the CLI refuses OpenAI options with an explicit message (§88.3).

The first-launch examples and the whole test suite run in this mode.

### 84.5 Running with OpenAI

Set `OPENAI_API_KEY` in `.env` (or the environment) and restart. The provider `openai` (retrieve-then-generate or
tool-calling agent), the `embedding` retriever and the four judge metrics then become available:

```bash
uv run ragwb run --name gpt4o-k3 --provider openai -k 3 \
    --metrics token_f1,context_recall,answer_relevancy,faithfulness,context_relevancy,correctness
```

**Cost warning.** These runs make paid API calls: one generation call per case (more for the agent, which calls its
retrieval tool and then answers), embedding calls for every chunk and every query with the embedding retriever, and
judge calls for every case and judge metric. Before an OpenAI run the UI shows "This run calls the OpenAI API and
may incur cost." with the number of generation calls (`new_run.py:191-194`). The workbench does not cap spending.
Cost is computed only if both `RAGWB_PRICE_INPUT_PER_MTOK` and `RAGWB_PRICE_OUTPUT_PER_MTOK` are set
(`runner.py:258-262`); otherwise it is shown as unknown ("—"). Use `--limit N` (CLI) or "Evaluate first N cases"
(UI, Advanced) to try a configuration on a few cases first.

**Verification status.** No OpenAI or DeepEval call was made while building this Part. Release 1.3 later ran generation and
the four DeepEval judge metrics against Groq's free tier through its OpenAI-compatible endpoint, on small samples (Part XV §160);
release 1.4 ran the tool-calling agent pipeline live on three cases (Part XVI §176.3); OpenAI itself and API embeddings have not been run live (Part IX, §98).

### 84.6 Local embeddings and rate-limited providers (release 1.3)

```bash
uv sync --extra semantic                      # installs fastembed (the optional `semantic` extra in pyproject.toml)
uv run ragwb run --retriever hybrid-local     # BM25 fused with local dense retrieval; no key, no network after the model download
RAGWB_MAX_REQUESTS_PER_MINUTE=12              # in .env or the environment: pace answers and judge measurements
```

The first use downloads the embedding model (default `BAAI/bge-small-en-v1.5`) into `<data dir>/models`; after that
`HF_HUB_OFFLINE=1` works. On Windows keep the data directory path short: the model cache nests folders deeply and can exceed
the 260-character path limit (`docs/BUILD_AND_RUN.md`, `docs/KNOWN_LIMITATIONS.md`). One pacing *operation* is one answer or one
judge-metric measurement, and a measurement can make several API calls, so choose a value below the provider's request quota
divided by that fan-out. Pacing cannot create quota, and a provider's daily token budget is not waited out (Part XV §161).

## 85. Command-line usage

### 85.1 Invocation

```bash
uv run ragwb <command> ...
.venv\Scripts\ragwb.exe <command> ...          # Windows, environment already prepared
.venv\Scripts\python.exe -m rag_workbench <command> ...
```

`ragwb` is the console script declared at `pyproject.toml:20-21`; `python -m rag_workbench` runs `__main__.py`, which
calls `cli.main` (`src/rag_workbench/__main__.py:1-5`). The complete help text of every subcommand is captured from
argparse in `docs/project-book/generated/cli-reference.md`.

### 85.2 Commands

| Command | Purpose | Key options | Code |
|---|---|---|---|
| `run` | run an evaluation | `--name`, `--dataset`, `--document`, `--provider {offline,openai}`, `--pipeline {rag,agent}`, `--retriever {bm25,embedding,hybrid,local,hybrid-local}`, `-k`, `--metrics`, `--threshold METRIC=VALUE` (repeatable), `--model`, `--judge-model`, `--workers` and `--limit` (both must be 1 or more since 1.4.1, otherwise a usage error), `--answer-sentences`, `--inject-failures`, `--min-evidence`, `--skip-headings`, `--seed`, `--notes`, `--quiet` | `cli.py:69-79`, `416-439` |
| `list` | list stored runs, optionally filtered; shows a `tags` column | `--search WORD...`, `--tag`, `--status` | `cli.py:99-112`, `441-446` |
| `show RUN_ID` | configuration essentials and summary of one run | — | `cli.py:231-238`, `489-491` |
| `compare RUN_A RUN_B` | paired comparison of B against A on shared metrics | — | `cli.py:241-250`, `492-495` |
| `export RUN_ID` | write CSV, JSON bundle or Markdown | `--format {csv,json,md}`, `--out-dir` | `cli.py:253-258`, `496-500` |
| `validate FILE` | validate a dataset | — | `cli.py:261-271`, `501-503` |
| `delete RUN_ID` | delete a run | `--yes` (required) | `cli.py:274-282`, `504-507` |
| `metrics` | describe the metrics | — | `cli.py:285-292`, `508` |
| `import BUNDLE [BUNDLE ...]` | import one or more bundles written by `export --format json` | — | `cli.py:295-299`, `509-511` |
| `score` | score one answer, store nothing | `--question`, `--answer`, `--expected`, `--context` (repeatable), `--metrics`, `--judge-model` | `cli.py:476-487`, `512-519` |
| `labels-template RUN_ID` | write a CSV for human labelling | `--out` (required), `--force` | `cli.py:302-310`, `520-524` |
| `calibrate RUN_ID` | metric-versus-label agreement and Cohen's kappa; `--sweep` tabulates agreement at thresholds 0.10-0.95; `--rescore` computes an offline or local-model metric from stored answers | `--labels` (required), `--metric` (required), `--sweep`, `--rescore` | `cli.py:333-367`, `599-607` |
| `slices RUN_ID` | per-value summary of a metadata field | `--by` (required) | `cli.py:370-389`, `531-534` |
| `rerun RUN_ID` | repeat a stored run from its recorded configuration | `--name`, `--quiet` | `cli.py:392-409`, `535-539` |
| `backup` | verified copy of the run store | `--out-dir` | `cli.py:424-427`, `617-619` |
| `restore BACKUP` | replace the run store with a backup after validating it; writes a `pre-restore-*` safety copy; refuses a recently active run (release 1.4; stop the web app first) | `--yes` (required), `--force` | `cli.py:424-433`, `553-557` |
| `prune` | delete old runs by retention policy (dry run by default; runs tagged `keep` are never selected) | `--keep-last`, `--older-than-days`, `--yes` | `cli.py:430-443`, `543-547` |
| `doctor` | installation, configuration and store checks (no network) | — | `cli.py:465-474`, `548` |
| `tag RUN_ID` | add or remove tags on a run | `--add`, `--remove` (comma-separated) | `cli.py:115-121`, `447-451` |
| `note RUN_ID [TEXT]` | set or clear a run's note | `--clear` | `cli.py:221-228`, `452-456` |
| `regress BASELINE CANDIDATE` | fail when a candidate run is significantly worse than a baseline (exit 0 / 3 / 4) | `--max-drop`, `--min-pairs`, `--max-error-increase`, `--metrics` | `cli.py:138-147`, `457-465` |
| `tune-abstention` | choose `min_evidence` on a development half, report it on a held-out half | `--dataset`, `--document` (matching order) | `cli.py:124-135`, `484-488` |
| `user add\|remove\|set-role\|set-password\|list [NAME]` | manage web-app accounts and their roles (scrypt-hashed passwords in `<data dir>/users.json`; `viewer`, `editor` (the default) or `admin`) | `--role`, `--replace`, `--password-stdin`, `--force` (override the last-admin guard; release 1.4) | `cli.py:159-194`, `536-544` |
| `judge-noise RUN_ID` | re-score a run's stored answers several times and report judge jitter (makes API calls; release 1.3) | `--repeats` (default 3), `--metrics`, `--limit`, `--yes` | `cli.py:197-219`, `476-483` |

A global `--version` prints `ragwb 1.4.1` (`cli.py:525`). Part XIII explains the seven commands added in release 1.1, Part XIV the five added in 1.2 (`tag`, `note`, `regress`, `tune-abstention`, `user`), Part XV the one added in 1.3 (`judge-noise`; `user` also gained `set-role`) and Part XVI the one added in 1.4 (`restore`; `user` also gained `set-password` and `--force`, `calibrate` gained `--sweep` and `--rescore`), 24 commands in all.
Without `--metrics`, `run` uses the four lexical metrics for `--provider offline` and the lexical plus all four
judge metrics for `--provider openai` (`cli.py:41-42`). Workers default to 1 offline and `RAGWB_MAX_WORKERS` (4) for
OpenAI (`cli.py:60`). `import` requires at least one path (`nargs="+"`): without one, argparse prints
`ragwb import: error: the following arguments are required: bundles`.

### 85.3 Exit codes

| Code | Meaning | Code |
|---|---|---|
| 0 | success; for `run`, status `completed`; for `regress`, a judged comparison with no regression | `cli.py:79`, `129-138` |
| 1 | error before or outside a run (bad configuration, dataset, document, bundle, storage, unknown run id); `compare` with no shared metrics; `delete` without `--yes` or of a run that does not exist; `validate` of an invalid dataset | `cli.py:567-570`, `105-106`, `134-141`, `130` |
| 2 | `run` finished with any status other than `completed` (`partial`, `failed`, `cancelled`); also argparse usage errors | `cli.py:79` |
| 3 | `regress` found a significant regression or a rise in the error rate beyond the tolerance (release 1.2) | `regression.py:29`, `:53-59` |
| 4 | `regress` could not judge any metric (too few paired questions or no shared metrics): nothing was verified (release 1.2) | `regression.py:29`, `:57-58` |

Errors are printed as `error: <message>` on standard error (`cli.py:686`).

### 85.4 An evaluation from the CLI

With `RAGWB_DATA_DIR` pointing at a fresh temporary directory and a blank key:

```text
$ python -m rag_workbench run --name first-offline-run -k 3
[  1/20] ok  q01
[  2/20] ok  q02
...                                   (q03-q19 likewise)
[ 20/20] ok  q20

Run 20261023-195457-first-offline-run-0ffc69: completed
cases 20  ok 20  errors 0  mean latency 0.6 ms
metric                          mean           95% CI    pass  scored  skip  err
Token F1                       0.346      0.285-0.419      5%      20     0    0
ROUGE-L                        0.317      0.252-0.393      5%      20     0    0
Context recall (lexical)       0.885      0.839-0.930     95%      20     0    0
Groundedness (lexical)         1.000      1.000-1.000    100%      20     0    0
```

Exit code 0, and the scores are identical to the `offline-bm25-k3` example run, as expected of a deterministic
baseline. The run id is `<UTC timestamp>-<slug of the name>-<6 random hex digits>` (`runner.py:265-267`); the
timestamp is UTC, which is why it shows 19:54 at 01:24 local time. Groundedness is 1.000 by construction: the
extractive baseline copies sentences from the context (stated on the Settings page, `settings.py:50-51`). The
command's wall-clock time, including Python start-up and imports, was 7.13 s in this session, measured while the test
suite was running in parallel; the evaluation itself is a small fraction of that.

Continuing in the same data directory with a k = 1 run and a comparison:

```text
$ python -m rag_workbench run --name k1 -k 1 --quiet
Run 20261023-195510-k1-20b329: completed
...
$ python -m rag_workbench compare 20261023-195510-k1-20b329 20261023-195457-first-offline-run-0ffc69
A = k1 [20261023-195510-k1-20b329]
B = first-offline-run [20261023-195457-first-offline-run-0ffc69]

                   label  paired_cases  mean_a  mean_b  diff_b_minus_a  ci_low  ci_high  b_better  ties  b_worse  ci_excludes_zero
                Token F1            20   0.404   0.346          -0.057  -0.116   -0.008         3    10        7              True
                 ROUGE-L            20   0.373   0.317          -0.056  -0.108   -0.010         3    10        7              True
Context recall (lexical)            20   0.857   0.885           0.028   0.000    0.062         3    17        0             False
  Groundedness (lexical)            20   1.000   1.000           0.000   0.000    0.000         0    20        0             False
```

A failure-injected run demonstrates partial results and exit code 2:

```text
$ python -m rag_workbench run --name inj --inject-failures 0.3 --quiet
Run 20261023-195514-inj-a75112: partial
cases 20  ok 17  errors 3  mean latency 0.3 ms
...
```

The same three cases fail as in the example run: injected failures are deterministic per question and seed
(`providers.py:60-66`).

### 85.5 Scoring a single answer

```text
$ python -m rag_workbench score --question "Where does beeswax come from?" \
    --answer "Beeswax is produced by glands on the underside of worker bees." \
    --expected "Wax glands on the abdomen of young worker bees." \
    --context "Beeswax is secreted by wax glands on the underside of the abdomen of young worker bees."
Token F1                      0.556  pass    precision 0.50, recall 0.62 (5 shared tokens)
ROUGE-L                       0.556  pass    LCS 5 tokens; P 0.50, R 0.62
Context recall (lexical)      1.000  pass    6/6 reference terms found in context
Groundedness (lexical)        0.833  pass    5/6 answer terms found in context; unsupported: produced
```

Nothing is stored (`cli.py:344-372`). The groundedness reason shows the lexical nature of the metric: "produced"
does not occur in the context, although "secreted" means the same.

## 86. Generating reports

Every run can be exported in three formats (`reporting.EXPORT_FORMATS`, `reporting.py:17`):

| Format | Content | Producer |
|---|---|---|
| `csv` | one row per case: identity, question, reference, answer, error, latency, tokens, cost, attempts, context ids, and score / passed / status per metric; UTF-8 with BOM so Excel detects the encoding; formula-like cells prefixed with `'` | `reporting.export_csv`, `reporting.py:92-100` |
| `json` | a **run bundle**: `{"format": "rag-workbench-run", "version": 1, "run": …, "cases": [...]}`; re-importable with `ragwb import` | `reporting.export_json`, `reporting.py:114-125` |
| `md` | a Markdown report: run identity, configuration, dataset/document hashes, provenance warnings if any, summary table with CIs, failed cases, the five lowest-scoring cases per metric, and a closing caveat that judge scores are model assessments and lexical scores measure overlap | `reporting.export_markdown`, `reporting.py:140-185` |

From the CLI the file is written to `<data_dir>/exports/<run id>.<format>` unless `--out-dir` is given
(`cli.py:253-258`, `reporting.py:204-208`):

```text
$ python -m rag_workbench export 20261023-195457-first-offline-run-0ffc69 --format json
Wrote <temp>\cli-data\exports\20261023-195457-first-offline-run-0ffc69.json
```

In the UI the **Export & manage** tab of Run results offers the same three files as downloads, named after the run
id (`ui/views/results.py:180-188`).

A bundle exported on one machine can be imported on another. Paths in it are portable: the exported file above
contains `"dataset_path": "examples/datasets/honeybees.jsonl"` and `"document_path": "examples/documents/honeybees.pdf"`
— relative to the project root, or just the file name for files outside it (`reporting.portable_path`,
`reporting.py:103-111`). Imported runs get status `imported`, keep their original status in
`config["original_status"]`, and have their summary recomputed from the imported cases (`archive.py:65-72`).
Observed: importing the bundle into the store that already holds the run prints
`… .json: already present, skipped`; importing it into an empty data directory prints
`… .json: imported as 20261023-195457-first-offline-run-0ffc69`.

Cross-run views — the configuration diff, means with intervals, best run per metric and paired per-case
differences — are on the Compare runs page; the CLI equivalent is `ragwb compare`. A comparison cannot be exported
as a file.

## 87. Logs, stopping and resetting

### 87.1 Inspecting logs

The application logs to `<data_dir>/logs/rag_workbench.log` (`config.py:128-139`), i.e. `data/logs/rag_workbench.log`
by default:

* **Format**: `%(asctime)s %(levelname)-7s %(name)s: %(message)s` (`logging_setup.py:90`; with `RAGWB_LOG_FORMAT=json` the file holds one JSON object per line instead, `logging_setup.py:33-48`, `:87-88`). `asctime` is local time;
  run ids and stored timestamps are UTC (`models.py:18-19`), so the two differ by the local UTC offset.
* **Rotation**: `RotatingFileHandler` with `maxBytes=2_000_000` and `backupCount=3`, UTF-8 (`logging_setup.py:94`):
  at most four files of about 2 MB (`rag_workbench.log`, `.1`, `.2`, `.3`).
* **Redaction**: every handler has `RedactSecretsFilter` and a `RedactingFormatter`, which replace the configured
  key and any `sk-…` string in the message and in the fully formatted record, tracebacks included
  (`logging_setup.py:22-66`, `66-69`).
* **Level**: `RAGWB_LOG_LEVEL` (default `INFO`).
* **Console**: both front ends configure logging with `console=False` (`cli.py:681`, `ui/state.py:20`), so
  application log lines go only to the file; the CLI's own output is its `print` statements, and the terminal of
  `start.py` shows the launcher's `[start]` lines and Streamlit's own messages.
* **Unwritable location**: file logging is disabled with a warning and the application continues
  (`logging_setup.py:92-96`).

What is logged: bundle imports, chunk loading, run start and finish with status, transient-error retries,
interrupted-run recovery, metric failures and internal errors with stack traces (`archive.py:63`, `80`;
`documents.py:64`; `runner.py:118-119`, `136`, `142`, `186`, `219`; `services.py:34`; `metrics/base.py:87`).
Configuration errors reported by the CLI are printed, not logged.

```powershell
Get-Content data\logs\rag_workbench.log -Tail 20          # PowerShell
Get-Content data\logs\rag_workbench.log -Wait              # follow
```

```bash
tail -n 20 data/logs/rag_workbench.log                     # Git Bash
```

### 87.2 Stopping

* **The app started with `start.py`**: press Ctrl+C in its terminal; the launcher terminates Streamlit and waits up
  to 10 s before killing it (`start.py:182-188`). The same applies to a manually started Streamlit server.
* **A run in progress in the UI**: use Streamlit's Stop control. The runner treats any exception raised from the
  progress callback (which includes Streamlit's stop) as cancellation: finished cases are kept and the run is marked
  `cancelled` with a summary of what finished (`runner.py:130-137`; spinner text "use Streamlit's Stop button to
  cancel; finished cases are kept", `new_run.py:227`). With several workers, model calls already in flight finish
  before the run stops.
* **A CLI run**: Ctrl+C raises `KeyboardInterrupt`, handled the same way (`runner.py:132-137`).
* **A killed process** (closed window, power loss): the run stays `running` in the database. Every committed case
  refreshes a heartbeat; once a `running` run has had no committed case for 15 minutes, the next start of the UI or
  of any CLI command marks it `interrupted` (`services.py:31-34`, `storage.py:27-29`, `154-166`). A run whose process
  has just died is therefore shown as `running` for up to 15 minutes. Its completed cases remain visible;
  interrupted runs are not resumed.

### 87.2a Backup, restore and the runbook (release 1.4)

`ragwb backup` writes a consistent, verified copy of `runs.db` into `<data dir>/backups`; `ragwb restore BACKUP --yes` replaces the
run store with one. Restore validates the backup first (readable, `integrity_check` ok, has the run tables, not from a newer
schema), refuses while a run has committed a case in the last 15 minutes unless `--force`, writes a `pre-restore-*` safety copy of
the current store, replaces it atomically and migrates an older schema. **Stop the web app and any running evaluation first**: on
Windows a held-open store makes the replacement fail with "Access is denied", which the command reports without changing anything
(`maintenance.py:228-290`). A backup covers `runs.db` only; copy `users.json` separately. `restore` also works when the store cannot be opened at all: it is dispatched before the store is opened and keeps a raw
`pre-restore-damaged-*` copy of the unreadable file (Part XVI §171.6). Backup and safety-copy names carry microseconds. The complete runbook (install, configuration, monitoring, upgrades and rollback, access management, capacity, an incident
playbook) is `docs/OPERATIONS.md`; the security overview is `docs/SECURITY.md` (Part XVI §178).

### 87.3 Resetting disposable data

All runtime state lives in the data directory; code, examples and `.env` live elsewhere. The Settings page states
the procedure: "To reset local data, stop the app and delete the data directory; nothing else is affected."
(`ui/views/settings.py:57-58`).

```powershell
# PowerShell, from the project root, with the app stopped
Remove-Item -Recurse -Force data
python start.py
```

```bash
# Git Bash
rm -rf data
python start.py
```

Because the store is then empty, `start.py` re-creates the five example runs (§81.2, step 2), so the app opens in the
same state as after the very first launch. Use `python start.py --no-examples` for a genuinely empty start.

**What is lost**: every stored run and its case results (`runs.db`), files uploaded through the UI (`uploads/`),
CLI exports written to the default location (`exports/`), and the logs. Runs exported as JSON bundles elsewhere can
be imported again with `ragwb import`.

**What is not touched**: `examples/`, `src/`, `.env`, `.venv/`, the documentation, and any export written with
`--out-dir` outside `data/`.

Stop the app first: Streamlit keeps the run-store context cached for the life of the process (`ui/state.py:17-20`),
and on Windows an open SQLite file may refuse deletion.

To delete a single run instead, use **Run results → Export & manage → Delete this run** (type the run id to
confirm) or `ragwb delete <run-id> --yes`. For experiments, a throw-away data directory is safer than deleting the
real one:

```powershell
$env:RAGWB_DATA_DIR = "$env:TEMP\ragwb-scratch"; python start.py
```

## 88. Troubleshooting

### 88.1 Slow or failing downloads

`start.py` already raises uv's HTTP timeout to 180 s unless `UV_HTTP_TIMEOUT` is set (`start.py:50`). If
installation still fails with a network timeout, retry, or raise the timeout further:

```powershell
$env:UV_HTTP_TIMEOUT = "600"; python start.py
```

```bash
UV_HTTP_TIMEOUT=600 python start.py
```

The same variable applies to a manual `uv sync`. Re-locking (`uv lock`) resolves the whole dependency graph and can
take minutes on a slow network; that is not an error by itself.

### 88.2 Port already in use

`start.py` skips occupied ports: it uses the first port from 8501 (or `--port`) on which nothing accepts a
connection, so a second instance simply comes up on 8502 (`start.py:132-137`). It does, however, pass that port to
Streamlit explicitly, and with an explicitly set port the installed Streamlit does not search further: it logs
`Port <n> is not available` and exits with code 1
(`.venv/Lib/site-packages/streamlit/web/server/starlette/starlette_server.py:423-440`). That can only happen if
another process takes the port between the launcher's check and Streamlit's start; the launcher then reports
"the app exited during start-up" (`start.py:176-177`) — run it again. A manually started Streamlit without
`--server.port` tries the next port by itself.

To find the process holding a port on Windows: `Get-NetTCPConnection -LocalPort 8501 | Select-Object OwningProcess`
(PowerShell) or `netstat -ano | findstr :8501`.

### 88.3 Missing-key and invalid-combination errors

The exact messages, observed on 2026-10-24 with a blank key (exit code 1 each):

| Command | Message (on stderr) | Source |
|---|---|---|
| `ragwb run --provider openai` (default metrics include judge metrics, validated first) | `error: Metric(s) answer_relevancy, faithfulness, context_relevancy, correctness use an OpenAI judge model and need OPENAI_API_KEY.` | `metrics/__init__.py:23-26` |
| `ragwb run --provider openai --metrics token_f1` | `error: OPENAI_API_KEY is not set; it is required for the OpenAI provider. Add it to .env or use the offline provider with the BM25 retriever.` | `pipeline.py:175-178` |
| `ragwb run --retriever embedding` | `error: OPENAI_API_KEY is not set; it is required for the embedding retriever. Add it to .env or use the offline provider with the BM25 retriever.` | same |
| `ragwb run --pipeline agent` | `error: The agent pipeline needs a tool-calling LLM; choose provider 'openai' or pipeline 'rag'.` | `pipeline.py:155-157` |

In the UI the corresponding states are explained before the button is pressed (§84.4).

With a key that OpenAI rejects, the run is not refused up front — the key's validity is only known when a call is
made. Each case then fails with `OpenAI rejected the API key (AuthenticationError). Check OPENAI_API_KEY.`
(`errors.py:50-51`), a permanent error that is not retried, and the run ends `failed`. This path was tested with a
constructed exception, not against the real API.

If you edited `.env` and nothing changed: the app reads settings once per process; stop it (Ctrl+C) and start it
again. A key in the process environment also overrides one in `.env` (`override=False`, `config.py:212`).

### 88.4 Code changes not taking effect in a running app

A running Streamlit server re-executes the page scripts on each interaction but keeps the package modules they import
cached; after editing a helper module, a running server can show an `ImportError` or old behaviour. After editing
anything under `src/rag_workbench/` other than `ui/views/`, stop the server and start it again.

### 88.5 OneDrive-synchronised folders and SQLite

Sync clients (OneDrive, Dropbox and similar) can open or lock files while they are being written, which interferes
with SQLite's locking. The store uses SQLite's default rollback journal rather than WAL (which adds `-wal`/`-shm`
files) and short, one-operation connections with a 15-second lock wait (`storage.py:85-98`); a read-only query on the
project's `data/runs.db` returned `journal_mode = delete`. No locking error was observed while preparing this book,
but if you see `database is locked`, `Run store error (...)` or `Cannot open run store ...`, move the data directory out
of the synchronised tree:

```powershell
$env:RAGWB_DATA_DIR = "C:\ragwb-data"
```

or set `RAGWB_DATA_DIR` in `.env`.

### 88.6 Windows: very long paths

Keep the project in a short path, or enable Win32 long paths. In very deep folders, files inside `.venv` can exceed
the 260-character `MAX_PATH` limit, and imports of compiled modules fail. The symptom documented in
`docs/BUILD_AND_RUN.md` is `ImportError: cannot import name 'ArgsKwargs' from 'pydantic_core._pydantic_core'`. The
remedy is to move the project to a shorter path (or enable long paths) and run `python start.py` again. This was not
reproduced for this book.

### 88.7 Other messages

| Message | Meaning | Action |
|---|---|---|
| `[start] uv is not installed and this Python is 3.x; …` | no uv and the launching Python is older than 3.12 | install uv, or run `start.py` with Python 3.12+ (`start.py:53-57`) |
| `[start] the application could not open its run store: …` | settings or storage problem, details follow | fix the variable or the data directory named in the message |
| `Dataset '<name>' is invalid: line N: ...` | validation errors (first five shown) | `ragwb validate <file>` for the full list |
| `Document is N bytes; the limit is M bytes` / `No extractable text found in <file>` | document too large, or an image-only PDF | raise `RAGWB_MAX_DOCUMENT_BYTES`, or use a text-based PDF / `.txt` / `.md` |
| `<path> was created by a newer version (schema N)` | `runs.db` from a newer release | use that release, or another data directory (`storage.py:72-73`); an older store (schema 1 or 2) is migrated to 3 on first open (`storage.py:74-79`) |
| `File logging disabled: ...` | log directory not writable | check permissions of the data directory |
| `No run with id '<id>'. Use 'list' to see run ids.` / `No run with id '<id>'.` | wrong run id | `ragwb list` |
| `'<ref>' matches N runs (...); give more of the id.` | the prefix, suffix or name matches several runs (release 1.4.1) | give more of the id, or the full id from `ragwb list` |
| `Refusing to delete without --yes` | safety check | add `--yes` |
| Run shown as `running` long after its process died | the 15-minute stale threshold has not passed | wait, then restart the app or run any CLI command |
| Run shown as `interrupted` | its process died, or it committed no case for 15 minutes while another front end started (Part XI, §116.3) | completed cases are kept; start a new run |

## 89. Windows notes and reproducing the documented examples

### 89.1 PowerShell versus bash

Most shell examples in this book use POSIX syntax. Under Windows PowerShell 5.1:

| Task | Git Bash | PowerShell |
|---|---|---|
| Set a variable for one command | `RAGWB_DATA_DIR=/tmp/x python start.py` | `$env:RAGWB_DATA_DIR = "$env:TEMP\x"; python start.py` (persists for the session) |
| Copy the template | `cp .env.example .env` | `Copy-Item .env.example .env` |
| Delete the data directory | `rm -rf data` | `Remove-Item -Recurse -Force data` |
| Continue a long line | `\` | `` ` `` (backtick) |
| Run the venv interpreter | `.venv/Scripts/python.exe` | `.venv\Scripts\python.exe` |
| Chain only on success | `a && b` | `a; if ($?) { b }` |

### 89.2 Paths with spaces

The development path contains a space (`...\PROJECTS\RAG Evaluation\...`). Quote it whenever it is typed:
`cd "C:\Users\omjee\OneDrive\Desktop\PROJECTS\RAG Evaluation\rag-evaluation-workbench"`. The code is unaffected —
paths are handled as `pathlib.Path` objects throughout, `start.py` passes arguments as lists rather than a shell
string (`start.py:42-44`), and every command in this part was run from that directory. Upload names are reduced to
safe characters, so spaces in uploaded file names become `_` (`services.py:52`). Quote file arguments that contain
spaces: `ragwb validate "C:\My Data\questions.jsonl"`.

### 89.3 Reproducing the example runs

`start.py` creates the five example runs automatically on the first launch. To create them on demand:

```bash
uv run python scripts/seed_demo_runs.py
uv run python scripts/seed_demo_runs.py --pages docs/project-book/tools/screenshot_pages.json
```

The script calls the same `seed_demo_runs` as the launcher (`scripts/seed_demo_runs.py:16-26`) and writes to the
**configured** run store — `data/` unless `RAGWB_DATA_DIR` says otherwise — so set `RAGWB_DATA_DIR` first if you do
not want a second copy next to your own runs. Rerunning produces identical scores with new run ids
(`test_demo_runs_are_genuine_and_reproducible`, `tests/test_runner.py:165-174`). With `--pages` it also writes the page
list for the screenshot tool, including run-specific deep links such as `/results?run=<k3 id>&tab=cases`
(`scripts/seed_demo_runs.py:27-43`). The project's own `data/runs.db` currently holds exactly the five example runs
(read-only query, 2026-10-24).

To regenerate the example PDF from its Markdown source: `uv run python scripts/make_example_pdf.py`.

### 89.4 Screenshots and book tooling

`docs/project-book/tools/` contains:

| File | What it does | Writes |
|---|---|---|
| `capture_screenshots.py` | drives headless Chrome/Edge over the DevTools protocol, waits until Streamlit has finished and the page has been stable for 3 s, captures each page at width 1440 and trims the blank bottom with Pillow (`capture_screenshots.py:1-12`, `35-47`, `110`) | `docs/project-book/screenshots/*.png` |
| `screenshot_pages.json` | the `[name, path]` list produced by `seed_demo_runs.py --pages` | — |
| `generate_reference.py` | generates the reference appendices from the code with `ast` and argparse (`generate_reference.py:1-13`) | `docs/project-book/generated/*.md` |
| `diagrams.py` | generates the SVG figures; the module graph is derived from actual imports (`diagrams.py:1-8`) | `docs/project-book/figures/*.svg` |

Full screenshot procedure:

```bash
uv run python scripts/seed_demo_runs.py --pages docs/project-book/tools/screenshot_pages.json
python start.py --no-browser                              # in a second terminal
uv run python docs/project-book/tools/capture_screenshots.py \
    --pages docs/project-book/tools/screenshot_pages.json --out docs/project-book/screenshots
```

The capture script accepts `--base` (default `http://localhost:8501`), `--width` (1440) and `--port` (9333, the
DevTools port), and refuses any base URL that is not `http://localhost` or `http://127.0.0.1`
(`capture_screenshots.py:124-131`). It needs Pillow and `websockets`, both installed with Streamlit. Waiting for a
stable page matters because a plain `chrome --headless --screenshot` can capture Streamlit's loading skeleton. The
eleven screenshots `01-overview.png` … `11-unanswerable.png` (including `06-run-configuration.png`, the Configuration
tab) are present; the capture and generator scripts were not re-run for this part, because they overwrite files that
belong to other parts of the book.

### 89.5 The verification sequence

```bash
uv run python scripts/verify.py            # with coverage and UI tests
uv run python scripts/verify.py --quick    # without coverage and UI tests
uv run python scripts/verify.py --audit    # also pip-audit (contacts a vulnerability database)
uv run python scripts/verify.py --wheel    # also build the wheel and install it into a clean venv (downloads from PyPI; release 1.4)
```

The six steps (environment, lockfile, secrets, static analysis, tests, end-to-end) are described in Part IX, §97.4; `--audit`
adds a seventh, a `pip-audit` scan of the locked runtime requirements (the only step that uses the network). The
end-to-end step validates all example datasets, runs, shows, exports in three formats, re-imports the exported bundle,
runs and compares a second configuration, runs with injected failures, checks that an OpenAI run without a key is refused,
and exercises `slices`, `labels-template`, `backup` and `doctor` — all in a temporary directory that is deleted
afterwards (`scripts/verify.py:137-178`).
