# Build and Run

There is no compile or packaging step. **`python start.py` does everything**: it creates or updates the environment,
runs the offline example evaluations on the first launch and starts the app. The manual steps below are the same
operations done one at a time. Full details, troubleshooting and Windows notes are in the project book, Part VIII.

## Quick start

```bash
python start.py                 # setup + example runs (first launch) + app at http://localhost:8501
python start.py --setup-only    # prepare everything without starting the app
python start.py --port 8600 --no-browser --no-examples
```

`start.py` uses `uv sync` when uv is installed; otherwise it creates `.venv` with `python -m venv` and installs the
project with pip (Python 3.12+ required in that case). Nothing is installed outside the project folder.

## Requirements

* Python 3.12 or newer (`.python-version` pins 3.12; uv downloads it if needed)
* [uv](https://docs.astral.sh/uv/) 0.5+ (developed with 0.13.1)
* Optional: an OpenAI API key; Chrome or Edge only for rebuilding the book's PDF and screenshots

## Install

```bash
uv sync                    # runtime + dev (pytest) dependencies, editable install of rag_workbench
uv sync --group docs       # additionally: markdown, for building the project book
```

Slow package index? Raise uv's timeout: `UV_HTTP_TIMEOUT=180 uv sync` (PowerShell: `$env:UV_HTTP_TIMEOUT="180"`).

Windows: keep the project in a short path (or enable Win32 long paths). Under very deep folders the venv's
compiled modules can exceed the 260-character `MAX_PATH` limit; observed symptom: `ImportError: cannot import name
'ArgsKwargs' from 'pydantic_core._pydantic_core'`.

## Configure (optional)

```bash
cp .env.example .env       # PowerShell: Copy-Item .env.example .env
```

Everything works without a `.env`. Set `OPENAI_API_KEY` to enable the OpenAI provider, the embedding retriever and
judge metrics. All variables: `.env.example` and the book's environment-variable reference.

## Run

```bash
python start.py                            # the usual way (see Quick start)
uv run streamlit run streamlit_app.py      # the app only, at http://localhost:8501; stop with Ctrl+C
uv run ragwb run --name first-run -k 3     # CLI evaluation
uv run python scripts/seed_demo_runs.py    # create the five example runs again
uv run python scripts/make_example_pdf.py  # regenerate examples/documents/honeybees.pdf from its Markdown source
```

Runtime data (run store, uploads, exports, logs) lives in `data/` (or `RAGWB_DATA_DIR`). To reset, stop the app
and delete `data/`; the next `python start.py` recreates the example runs. Nothing else is affected.

## Operate

```bash
uv run ragwb doctor                        # python, packages, disk, run store integrity, stale runs, key, exposure
uv run ragwb backup                        # consistent snapshot into data/backups (safe while the app runs)
uv run ragwb restore <backup.db> --yes     # stop the app first; writes pre-restore-*.db, so it can be undone
uv run ragwb prune --keep-last 20 --yes    # delete old runs (without --yes it only lists them)
uv run ragwb rerun <run-id>                # repeat a run with the same configuration
```

Set `RAGWB_APP_PASSWORD` before starting with `--host 0.0.0.0`; there is no TLS, so use a trusted network or a proxy.

## History, regression checks and accounts

```bash
uv run ragwb tag <run-id> --add baseline,prompt-v1     # labels; remove with --remove
uv run ragwb note <run-id> "k=3, BM25, before the prompt change"
uv run ragwb list --search honeybee --tag baseline     # every word must match
uv run ragwb rerun <baseline-id> --name candidate      # same configuration, today's code
uv run ragwb regress <baseline-id> <candidate-id>      # exit 0 ok, 3 regression, 4 not judged
uv run ragwb user add alice --role editor              # prompts for a password (10+ characters)
uv run ragwb user set-role alice --role admin          # applies on the next page load
uv run python start.py --host 0.0.0.0 --ssl-cert cert.pem --ssl-key key.pem
```

`ragwb regress` can run from any scheduler (cron, Windows Task Scheduler, a CI job) because its exit code carries
the verdict. Scheduling itself is deliberately left to the operating system.

## Local embeddings (optional)

```bash
uv sync --extra semantic                          # installs fastembed (onnxruntime, tokenizers)
uv run ragwb run --retriever hybrid-local         # BM25 + local dense retrieval, still no API key
uv run ragwb run --metrics token_f1,semantic_similarity,semantic_context_recall
```

The first use downloads the embedding model (default `BAAI/bge-small-en-v1.5`, about 70 MB quantised) into
`<data dir>/models`; after that nothing leaves the machine (`HF_HUB_OFFLINE=1` works). On Windows keep the data directory
path short: the model cache nests folders deeply and can exceed the 260-character path limit.

## Rate-limited providers

```bash
RAGWB_MAX_REQUESTS_PER_MINUTE=12   # one operation = one answer or one judge-metric measurement
```

A judge measurement can make several API calls, so pick a value below the provider's request quota divided by that
fan-out, and watch provider token-per-day quotas (free tiers are small). Retries already honour `Retry-After`.

## Installing as a wheel, and Docker

`uv build --wheel` produces a wheel that includes the example data. A wheel install gives the `ragwb` command-line tool
only (the web app needs this project folder). `RAGWB_HOME` sets the folder that holds `data/` and `.env`; without it a
wheel install uses the current directory and a checkout uses the project folder. `docker build -t rag-workbench .`
builds the web app image (set `RAGWB_APP_PASSWORD` when running it); the Dockerfile was written without Docker
available and has not been built or run.

## Verify

```bash
uv run python scripts/verify.py            # environment, lockfile, secret scan, ruff + mypy, tests + coverage, CLI end-to-end
uv run python scripts/verify.py --quick    # without coverage and UI tests
uv run python scripts/verify.py --audit    # also pip-audit (sends package names and versions to an advisory database)
uv run python scripts/verify.py --wheel    # also a clean wheel install (downloads dependencies from PyPI)
uv run python scripts/benchmark_documents.py   # large-document scale benchmark
uv run python scripts/benchmark.py         # offline scale benchmark (200 / 1,000 / 5,000 cases)
uv run python scripts/live_smoke.py --yes-spend --cases 2   # PAID: checks the real OpenAI/DeepEval paths
```

## Rebuild the documentation

```bash
uv run python docs/project-book/tools/diagrams.py            # figures
uv run python docs/project-book/tools/generate_reference.py  # generated appendices
uv run python docs/project-book/tools/build_book.py          # manuscript, HTML and PDF
```

Screenshots: start the app, run `scripts/seed_demo_runs.py --pages docs/project-book/tools/screenshot_pages.json`,
then `docs/project-book/tools/capture_screenshots.py --pages docs/project-book/tools/screenshot_pages.json --out
docs/project-book/screenshots`.
