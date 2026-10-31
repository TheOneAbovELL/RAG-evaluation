# Part IV — Core implementation

Part III described the shape of the system. This part goes inside the functions: how each important piece of code works, what it guarantees, what it deliberately does not do, and where it is limited. Line references (`file:line`) point at the current source. Short code excerpts are copied verbatim. Design reasons that are my reading of the code, rather than statements from the code or its comments, are marked **rationale:**.

## 41. Application entry points

The supported way to start the product is `python start.py`. Behind the launcher there are four ways into the program, and all of them end at the same composition root, `services.open_context` (`src/rag_workbench/services.py:27-35`).

| Entry point | Defined in | What it does first |
|---|---|---|
| `python start.py` | `start.py` (project root, standard library only) | Prepares `.venv`, seeds the example runs into an empty store, starts the Streamlit app on `localhost` and opens the browser (§41.1) |
| `ragwb <command>` | `pyproject.toml:20-21` → `rag_workbench.cli:main` | Parses arguments, then `open_context(load_settings(), console_logging=False)` (`cli.py:674-682`) |
| `python -m rag_workbench <command>` | `src/rag_workbench/__main__.py:1-5` | `sys.exit(main())` — identical to `ragwb` |
| `streamlit run streamlit_app.py` | `streamlit_app.py` | Sets the telemetry opt-out, page config and CSS, registers six pages, runs navigation |
| Python import | `rag_workbench` package | Nothing expensive: sets `DEEPEVAL_TELEMETRY_OPT_OUT` with `setdefault` and defines `__version__ = "1.4.1"` (`__init__.py:11-13`) |

### 41.1 `start.py`

The launcher is a 212-line script whose module docstring is its manual (`start.py:1-16`). `main` parses seven flags — `--port` (default 8501), `--host` (default `localhost`), `--ssl-cert`, `--ssl-key`, `--no-browser`, `--no-examples` and `--setup-only` (`start.py:194-202`) — changes to the project root, refuses a non-local host that has no login (shared password or accounts) and a malformed TLS pair, and then calls the steps in order (`start.py:192-215`):

```python
    os.chdir(ROOT)
    problem = host_problem(args.host, password_configured() or accounts_configured()) or tls_problem(
        args.ssl_cert, args.ssl_key)
    if problem:
        sys.exit(f"[start] {problem}")
    prepare_environment()
    if not args.no_examples and store_is_empty():
        create_examples()
    if args.setup_only:
        say("setup complete")
        return 0
    return launch(free_port(args.port), not args.no_browser, args.host, args.ssl_cert, args.ssl_key)
```

(`start.py:204-215`.) The functions it calls:

| Function | Lines | Behaviour |
|---|---|---|
| `prepare_environment` | `start.py:47-63` | With `uv` on `PATH`: `uv sync --frozen --inexact`, with `UV_HTTP_TIMEOUT` defaulting to 180 s; on failure, exit with a message. Without `uv`: refuse Python older than 3.12, create `.venv` with `python -m venv` if it is missing, and `pip install -e . pytest pytest-cov` into it |
| `store_is_empty` | `start.py:66-72` | Runs `open_context(console_logging=False).store.list_runs()` with the `.venv` interpreter in a subprocess and compares the printed count with `0`. A failure exits with the last 2,000 characters of the child's stderr |
| `password_configured` | `start.py:84-94` | True if `RAGWB_APP_PASSWORD` is non-blank in the environment or in `.env` (the launcher reads `.env` itself because it cannot import the package) |
| `accounts_configured` | `start.py:98-109` | True if `<data dir>/users.json` lists a user (or cannot be parsed) and is larger than two bytes (release 1.2; see Part XIV §156.7 for the case this misjudges) |
| `host_problem` | `start.py:112-117` | Returns an error message for a host outside `localhost`, `127.0.0.1`, `::1` when no login (shared password or accounts) is set, otherwise `None` |
| `tls_problem` | `start.py:120-129` | Returns a message if only one of `--ssl-cert`/`--ssl-key` is given or a file is missing, otherwise `None` |
| `create_examples` | `start.py:75-81` | Runs `demo.seed_demo_runs(open_context(...))` in the same way and prints each run's name and status. A failure is reported, and the app still starts |
| `free_port` | `start.py:132-137` | Probes `127.0.0.1` from the preferred port upwards (50 candidates) and returns the first port nothing is listening on |
| `wait_until_ready` | `start.py:140-154` | Polls `http(s)://<host>:<port>/_stcore/health` every 0.5 s until it answers `ok`, the server process exits, or 90 s pass; with HTTPS the certificate is not verified, because the probe talks to the launcher's own local server |
| `launch` | `start.py:157-189` | Starts `python -m streamlit run streamlit_app.py --server.port P --server.address H --server.headless true --browser.gatherUsageStats false` (plus `--server.sslCertFile`/`--server.sslKeyFile` for HTTPS, and a printed warning for a non-local host without TLS) with `DEEPEVAL_TELEMETRY_OPT_OUT=1`, opens the browser once healthy, waits for the server, and on Ctrl+C terminates it (kill after 10 s) |

The example runs come from `rag_workbench.demo` (`demo.py:24-47`), which defines five offline configurations over the bundled honeybee data. `demo_configs` returns them as BM25 at k = 1, 3 and 5 over `honeybees.jsonl`, an unanswerable-question run over `honeybees_unanswerable.jsonl`, and a run with `offline_failure_rate=0.3`. `seed_demo_runs` executes each with the normal runner and returns the stored records. They are genuine evaluations, so "rerunning reproduces the same scores" (`demo.py:4`; `tests/test_runner.py:165`, `test_demo_runs_are_genuine_and_reproducible`). `scripts/seed_demo_runs.py` is a thin command-line wrapper around the same function (`scripts/seed_demo_runs.py:16-26`).

**Rationale:** keeping the launcher free of third-party imports — and having it talk to the package only through the `.venv` interpreter — means the first command a user types works on a machine with nothing installed except Python. Probing for an empty store rather than a marker file means that deleting `data/` resets the first-launch behaviour.

### 41.2 `open_context`

```python
def open_context(settings: Settings | None = None, *, console_logging: bool = True) -> AppContext:
    """Load settings, configure logging, open the store and mark runs left ``running`` as interrupted."""
    settings = settings or load_settings()
    configure_logging(settings, console=console_logging)
    store = RunStore(settings.db_path)
    recovered = store.recover_interrupted()
```

(`services.py:27-32`.) Four things happen in order: settings are loaded and validated (raising `ConfigError` on bad values); the `rag_workbench` logger is configured once per process; the SQLite store is opened, creating the schema or migrating an older one if necessary; and runs left in `running` whose heartbeat is older than 15 minutes — runs whose process has died — are relabelled `interrupted` (Chapter 52). The returned `AppContext` is a two-field dataclass whose `runner()` method builds a fresh `EvaluationRunner` on each call (`services.py:18-24`). Building a runner is cheap — its constructor only stores references (`runner.py:72-80`).

Both front ends pass `console_logging=False`: the CLI prints its own output and the Streamlit server has its own console, so the package logs only to the rotating file.

### 41.3 The Streamlit entry script

`streamlit_app.py` is 42 lines. It sets the telemetry opt-out again before importing Streamlit (`streamlit_app.py:10`) — **rationale:** the entry script may be the first code Streamlit executes, before any `rag_workbench` import — calls `st.set_page_config(... layout="wide")` (`:18`) and `apply_style()` (`:19`), builds absolute page paths from `VIEWS = Path(__file__).resolve().parent / "src" / "rag_workbench" / "ui" / "views"` (`:23`), and groups the pages:

| Group | Page | Script | URL path |
|---|---|---|---|
| Evaluate | Overview (default) | `overview.py` | `/` |
| Evaluate | New evaluation | `new_run.py` | `/new-run` |
| Analyse | Run results | `results.py` | `/results` |
| Analyse | Compare runs | `compare.py` | `/compare` |
| Data & system | Datasets & retrieval | `data.py` | `/data` |
| Data & system | Settings & metrics | `settings.py` | `/settings` |

(`streamlit_app.py:24-37`.) Since release 1.4 a seventh page, *Accounts* (`users.py`, URL path `/accounts`, group *Admin*), is added to the dictionary only when named accounts exist and the signed-in role is `admin` (`streamlit_app.py:39-40`; Part XVI §173.1). The last line, `st.navigation(pages).run()` (`:42`), executes the selected page.

## 42. Core domain concepts and data models

All shared data types are pydantic models in `src/rag_workbench/models.py`. They are the vocabulary of the system; storage writes them as JSON and reads them back with `model_validate_json`.

### 42.1 Status vocabularies

| Literal | Values | Defined |
|---|---|---|
| `RunStatus` | `running`, `completed`, `partial`, `failed`, `cancelled`, `interrupted`, `imported` | `models.py:12` |
| `CaseStatus` | `ok`, `error` | `models.py:13` |
| `MetricStatus` | `ok`, `skipped`, `error` | `models.py:14` |
| `ContextSource` | `retriever`, `agent_tool` | `models.py:15` |

Both context sources name *retrieval output*: either the chunks the retriever returned for the question, or the chunks returned to the agent's tool. The vocabulary has no value for "what the model says it used", because that is never scored. The Results page shows the source above the context list ("chunks returned by the retriever" / "chunks returned to the agent's tool", `ui/views/results.py:163-164`).

### 42.2 Models

| Model | Fields (abridged) | Notes |
|---|---|---|
| `EvalCase` (`:22`) | `id`, `question`, `expected_answer?`, `metadata` | One dataset row |
| `Chunk` (`:31`) | `id`, `text`, `page`, `source` | Unit of retrieval |
| `RetrievedChunk` (`:40`) | `chunk_id`, `text`, `page`, `score`, `rank` (1-based) | A chunk as returned for one query |
| `Generation` (`:50`) | `answer`, `contexts`, `context_source`, `model`, `latency_ms`, token counts, `retrieval_queries`, `model_context_claim` | Output of `Pipeline.answer`; `total_tokens` property returns `None` only when both counts are unknown (`:63-67`) |
| `MetricResult` (`:70`) | `name`, `status`, `score?`, `threshold?`, `passed?`, `reason?` | Validator rejects scores outside [0, 1] (`:80-85`) |
| `CaseResult` (`:88`) | case identity, `status`, answer, contexts, latency, tokens, `cost_usd`, `attempts`, `error`, `metrics` | `score(metric)` helper returns `None` when absent (`:107-109`) |
| `RunConfig` (`:112`) | name, paths, provider, pipeline, retriever, `k` (1–50), metrics (non-empty, unique), thresholds, models, workers (1–32), retries (0–10), timeout, answer sentences (1–10), `limit`, `notes`, `offline_failure_rate` (0–1), `seed` | "Everything needed to reproduce a run. Contains no secrets." (`:113`) |
| `MetricSummary` (`:145`) | counts, mean, median, std, min, max, CI, threshold, `n_passed`, `pass_rate` | One metric over a run |
| `RunSummary` (`:164`) | case counts, per-metric summaries, latency mean/p95, token totals, cost total | |
| `RunRecord` (`:176`) | `id`, `name`, `status`, timestamps, `config` (dict), hashes, `n_cases`, `summary?`, `environment`, `notes` | `config` is a plain dict, so imported bundles may carry extra keys (`provenance_warnings`, `original_status`, `imported_from`) |

### 42.3 Two deliberate splits

- **`Generation` vs `CaseResult`.** A generation is what the pipeline knows; a case result adds what the runner knows (position, attempts, error, cost, metrics). Keeping them apart means pipelines never construct storage objects.
- **`RunConfig` (typed) vs `RunRecord.config` (dict).** The record stores `config.model_dump(mode="json")` plus the effective thresholds and the pipeline's real model name (`runner.py:113-114`). For an offline run, `generator_model` therefore reads `offline-extractive` (`providers.py:45`) even though the form left it blank; `ragwb show` on the k = 3 example run prints exactly that.

## 43. Main execution pipeline

### 43.1 `RAGPipeline.answer`

```python
    def answer(self, question: str) -> Generation:
        start = time.perf_counter()
        contexts = self.retriever.retrieve(question, self.k)
        output = self.generator.generate(question, [c.text for c in contexts])
```

(`pipeline.py:52-55`.) The method times retrieval plus generation with `perf_counter`, retrieves the top-k chunks for the question, passes exactly their texts to the generator, and returns a `Generation` whose `contexts` is the same list and whose `context_source` is `"retriever"` (`pipeline.py:56-58`). There is no point at which the evaluated context could diverge from the generator's input; `tests/test_providers_pipeline.py:92` (`test_rag_pipeline_evaluates_exactly_the_retrieved_chunks`) asserts this.

### 43.2 `AgentRAGPipeline.answer`

The agent mode lets a tool-calling model decide when and how to search, while the evaluated context remains real retrieval output (`pipeline.py:61-124`):

1. Lists `captured` and `queries` are created as locals (`:79-80`).
2. A LangChain `@tool` named `collecting_info` is defined as a closure. Each call retrieves `k` chunks for the model's query, appends the query, and appends only chunks not already captured, de-duplicating by `chunk_id` (`:82-89`). It returns the joined chunk texts to the model.
3. A pydantic `Answer(answer, context)` schema is declared as the structured response format (`:91-96`). The system prompt names the tool exactly as it is registered, `collecting_info` (`prompts.py:13`); a prompt that names a non-existent tool leaves the model to guess.
4. `create_agent(model=self._llm, tools=[collecting_info], system_prompt=AGENT_SYSTEM_PROMPT, response_format=Answer)` builds the agent; `agent.invoke` runs it (`:92-96`). SDK exceptions are translated by `classify_openai_error` (`:97-101`).
5. A missing or blank structured answer is a `ProviderError` (`:103-105`).
6. Token usage is summed over all `AIMessage`s in the transcript; if none reported usage, the counts stay `None` rather than `0` (`:106-113`).
7. Captured chunks are re-ranked 1…n in capture order (`:114-115`), so `rank` describes the order the agent saw them across all its tool calls, not the retriever's per-query rank.
8. The returned `Generation` has `context_source="agent_tool"`, the captured chunks as `contexts`, the list of model-chosen queries and the model's `context` field as `model_context_claim` (`:116-120`).

`tests/test_providers_pipeline.py:126` (`test_agent_pipeline_captures_real_tool_output_not_self_report`) checks that the stored context is the tool output, not the self-report. **Limitation:** if the agent answers without calling the tool, `contexts` is empty; context-based metrics are then `skipped` ("no retrieved context for this case", `metrics/base.py:80-82`), which is honest but means the agent's answer is scored only on reference metrics.

### 43.3 `build_pipeline`

`build_pipeline(config, settings, chunks=None)` (`pipeline.py:146-162`) is the only place that decides which concrete classes run:

| `provider` | `pipeline` | `retriever` | Result |
|---|---|---|---|
| `offline` | `rag` | `bm25` | `RAGPipeline(BM25Retriever, ExtractiveGenerator)` |
| `offline` | `rag` | `embedding` | `RAGPipeline(EmbeddingRetriever, ExtractiveGenerator)` — the generator's IDF table comes from a separate BM25 index over the same chunks (`:150`); needs a key for the embeddings |
| `offline` | `agent` | any | `ConfigError`: "The agent pipeline needs a tool-calling LLM…" (`:147-148`) |
| `openai` | `rag` | any | `RAGPipeline(retriever, OpenAIChatGenerator)` |
| `openai` | `agent` | any | `AgentRAGPipeline(retriever, …)` |

`_require_key` raises a `ConfigError` that names `OPENAI_API_KEY` and suggests the offline alternative (`pipeline.py:175-178`).

## 44. Evaluation lifecycle

The run lifecycle figure is in Chapter 32. This chapter follows the code.

### 44.1 Prepare

`EvaluationRunner.prepare(config)` (`runner.py:83-99`) performs every check that can fail before anything is written:

1. `validate_metric_names(config.metrics, self.settings)` — unknown names, empty list, judge metrics without a key (`metrics/__init__.py:18-31`).
2. Thresholds must belong to known metrics and lie in [0, 1] (`runner.py:85-87`).
3. `load_dataset` with the configured limits; `DatasetError` on any validation error (`runner.py:89-90`).
4. `config.limit` truncates the case list (`runner.py:91-92`).
5. `load_chunks` with the document size limit (`runner.py:93`).
6. The pipeline and metrics are built through the injected factories (`runner.py:94-96`).
7. Effective thresholds are resolved: the configured override, else the metric's default (`runner.py:97`).
8. Both input files are hashed (`runner.py:99`).

The result is a `PreparedRun` dataclass (`runner.py:60-68`). The UI deliberately calls `prepare` and `execute` separately (`ui/views/new_run.py:210`, `:228`) so that configuration errors appear as "Configuration rejected: …" before the progress bar is shown.

### 44.2 Execute

`execute(prepared, progress, cancel)` (`runner.py:107-143`):

1. Builds the `RunRecord` with a new id, status `running`, the serialised configuration plus effective thresholds and real model name, hashes, case count, `environment_info()` and notes, and inserts it (`:111-117`).
2. Logs the start with provider, pipeline, retriever and `k` (`:118-119`).
3. Iterates over `_iter_results` and, for each result, commits it, appends it, and calls `progress` (`:124-129`).
4. Decides the status (`:130-140`) and calls `_finish` (`:141`, defined at `:148-150`), which aggregates with `summarize_run` and writes status, summary and `finished_at`.
5. Returns the stored record (`:143-146`), so the caller sees exactly what was persisted.

### 44.3 Status rules

| Final status | Condition | Code |
|---|---|---|
| `completed` | No case has `status == "error"` | `runner.py:140` |
| `partial` | At least one error, at least one success | `runner.py:140` |
| `failed` | Results exist and every one is an error | `runner.py:140` |
| `cancelled` | Cancel event set, or any `BaseException` escaped the loop | `runner.py:130-137` |
| `interrupted` | Row still `running`, with no heartbeat for 15 minutes, when a process opens the store | `storage.py:154-166` |
| `imported` | Row created by `archive.import_bundle` | `archive.py:71` |

A cancelled run still gets a summary over the cases it finished (`tests/test_runner.py:97`: two cases recorded, `summary.n_cases == 2`).

### 44.4 Run identifiers

```python
def new_run_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "run"
    return f"{utcnow():%Y%m%d-%H%M%S}-{slug}-{uuid.uuid4().hex[:6]}"
```

(`runner.py:265-267`.) The id is sortable by UTC time, readable, restricted to `[a-z0-9-]`, and made unique by six hex characters of a UUID4 — for example `20261023-194808-offline-bm25-k3-2d53f3` for the k = 3 example run. The UI recognises this shape with a regular expression to show only the random suffix as a short id (`ui/state.py:14`, `:40-42`).

## 45. Dataset ingestion and validation

### 45.1 Accepted formats

| Format | Required | Optional | Other columns/keys |
|---|---|---|---|
| JSONL (`.jsonl`) | `question` | `expected_answer`, `id`, `metadata` (object) | Warning "ignored unknown field(s)" (`datasets.py:198-202`) |
| CSV (`.csv`) | header with `question` | `expected_answer`, `id` | Collected into `metadata` (`datasets.py:163-166`) |

### 45.2 `parse_dataset`

`parse_dataset(data, name, *, max_bytes, max_cases, max_field_chars)` (`datasets.py:68-113`) works on bytes so that the UI (uploads) and files share one code path:

1. Hash the raw bytes (`:71`) — the hash identifies the exact file version in the run record.
2. Reject unsupported suffixes and oversize input immediately (`:73-78`).
3. Decode as `utf-8-sig`, which accepts and strips a byte-order mark; report the failing byte offset otherwise (`:80-83`).
4. Produce `(line_number, row_dict)` pairs with `_jsonl_rows` or `_csv_rows`. JSONL blank lines are skipped; invalid JSON and non-object lines are errors with the column of the decode failure (`:138-152`). CSV uses `csv.DictReader` and records `reader.line_num` (`:155-168`), which is the physical line of the row's end, so multi-line quoted fields report their last line.
5. For each row, enforce the case limit (`:90-92`), convert with `_row_to_case`, reject duplicate ids as errors (`:96-99`) and duplicate questions (case- and whitespace-insensitive) as warnings (`:100-102`).
6. An empty dataset is an error (`:107-108`); missing reference answers produce one summary warning stating that reference-based metrics will be skipped (`:109-112`).

`_row_to_case` (`datasets.py:171-204`) checks types precisely: `question` must be a non-blank string; `expected_answer` must be a string, and a blank one becomes `None`; both are length-limited; `id` may be a string or an integer but not a boolean (`:191` excludes `bool`, which is a subclass of `int` in Python); `metadata` must be an object. Missing ids become `case-{position:03d}`, where `position` counts accepted cases (`:189-190`).

### 45.3 Reports, not exceptions

Parsing never raises for content problems. It returns a `DatasetReport` with `cases`, `errors`, `warnings` and `sha256`; `ok` means "no errors and at least one case" (`datasets.py:39-55`). `load_dataset` is the strict wrapper used by the runner: it raises `DatasetError`, whose message lists the first five errors and how many more exist (`datasets.py:58-65`, `:116-121`). `validate_file` checks existence and the size on disk before reading the file (`datasets.py:124-134`), so an oversize file is never loaded into memory. The `ragwb validate` command and the New evaluation page both use the report form to show every issue (`cli.py:266-270`, `ui/views/new_run.py:57-66`).

### 45.4 Documents

`load_chunks(path, *, max_chars=2000, max_bytes=None)` (`documents.py:38-65`) validates existence, suffix (`.pdf`, `.txt`, `.md`) and size, extracts raw blocks, splits long blocks, and assigns ids `p{page}-b{n}` numbered per page (`:56-61`). An empty result is a `DocumentError` ("No extractable text found", `:62-63`), which covers image-only PDFs.

- **PDF** (`_pdf_blocks`, `documents.py:87-105`): opens with PyMuPDF (any open failure becomes a `DocumentError`), takes `page.get_text("blocks")`, keeps text blocks (type 0), sorts them by `(y0, x0)` — top-to-bottom, then left-to-right — and normalises whitespace: PyMuPDF block text contains the PDF's line breaks, and `normalize_whitespace` collapses them, so a chunk is one line of prose (`tests/test_documents.py:13` asserts no chunk contains a newline).
- **Text/Markdown** (`_text_blocks`, `documents.py:108-114`): UTF-8 only, split on blank lines after normalising Windows line endings, all on page 1. Since release 1.4.1, for `.md` files only, a leading ATX heading marker (`#` to `######` followed by a space, `_ATX_MARKER`) is stripped from each paragraph, so a title chunk reads `Honeybees: Life Inside the Colony` and no longer begins with `# `; the words are kept and `.txt` files are untouched.
- **Long blocks** (`_split_long`, `documents.py:117-134`): sentences are packed greedily into pieces of at most `max_chars`; a single sentence longer than the limit is hard-split.

On the bundled `honeybees.pdf` this yields 11 chunks: the title block `p1-b1` ("Honeybees: Life Inside the Colony"), nine paragraphs `p1-b2`…`p1-b10` and one paragraph on page 2, `p2-b1` (`tests/test_documents.py:7-14`). The log line "Loaded 11 chunks from honeybees.pdf" records each load (`documents.py:64`).

## 46. Model/provider abstraction

### 46.1 Interfaces

Three `Protocol`s decouple the runner from concrete providers:

```python
class Retriever(Protocol):
    name: str

    def retrieve(self, query: str, k: int) -> list[RetrievedChunk]: ...
```

(`retrieval.py:34-37`.) `Generator` exposes `model: str` and `generate(question, passages) -> GeneratorOutput` (`providers.py:31-34`); `Pipeline` exposes `model: str` and `answer(question) -> Generation` (`pipeline.py:35-39`). `GeneratorOutput` is a dataclass of `answer` and optional token counts (`providers.py:24-26`).

### 46.2 Implementations

| Class | Kind | Key implementation details |
|---|---|---|
| `BM25Retriever` (`retrieval.py:40`) | Offline retriever | Precomputes term counts, lengths, an inverted index and IDF at construction; deterministic ties (Chapter 60) |
| `EmbeddingRetriever` (`retrieval.py:127`) | OpenAI retriever | Builds a LangChain `InMemoryVectorStore` with `OpenAIEmbeddings` on first query under a lock (`:140-153`); translates SDK errors from index building and querying with `classify_openai_error` (`:158-165`); maps hits back to chunks through `metadata["chunk_id"]` (`:168`) |
| `LocalEmbeddingRetriever` (`retrieval.py:181`) | Local retriever (release 1.3) | Cosine similarity between a query vector and chunk vectors from a local model; vectors computed once, on the first query, under a lock; ties go to the earlier chunk; makes no network call after the one-time model download (Part XV §162) |
| `ExtractiveGenerator` (`providers.py:37`) | Offline generator | IDF-weighted sentence selection; model name `offline-extractive`; optional deterministic failure injection |
| `OpenAIChatGenerator` (`providers.py:91`) | OpenAI generator | `ChatOpenAI(temperature=0, timeout=…, max_retries=0)` (`:101-102`); system + user messages; reports `input_tokens`/`output_tokens` from `usage_metadata` (`:115-119`); blank answer → `ProviderError` (`:116-117`) |
| `AgentRAGPipeline` (`pipeline.py:61`) | OpenAI pipeline | Tool-calling agent; context captured from tool calls |

### 46.3 Error translation

`classify_openai_error(exc)` (`errors.py:37-54`) maps SDK exceptions onto two classes:

| OpenAI exception | Mapped to | Runner behaviour |
|---|---|---|
| `RateLimitError`, `APITimeoutError`, `APIConnectionError`, `InternalServerError` | `TransientProviderError` (carrying the provider's `Retry-After` seconds when it sent one, `errors.py:79-86`) | Retry with back-off, at least as long as `Retry-After` (capped at 60 s, `errors.py:24-34`) |
| `AuthenticationError` | `ProviderError("OpenAI rejected the API key (AuthenticationError). Check OPENAI_API_KEY.")` | Fail the case, no retry |
| Any other `OpenAIError` | `ProviderError` | Fail the case, no retry |
| Not an OpenAI error | `None` (caller re-raises) | Runner records "Unexpected …" |

Since release 1.3 the exception is first unwrapped with `_unwrap` (`errors.py:58-76`), which follows tenacity's `RetryError.last_attempt` and `__cause__` links to the *first* OpenAI SDK error and stops there: DeepEval wraps provider errors in `RetryError`, and an earlier version of the walk went on to the underlying `httpx` transport error (both defects were found by the live runs, Part XV §160). Messages say "OpenAI-compatible API" for transient errors because the endpoint need not be OpenAI. Messages are built from `str(exc)` truncated to 300 characters (`errors.py:89-91`); the docstring notes that they never include request headers (`errors.py:40`). Every OpenAI call site uses the same idiom — try, classify, `raise mapped from exc`, otherwise re-raise (`providers.py:107-113`, `pipeline.py:99-105`, `retrieval.py:165-172`, `metrics/judge.py:88-94`). Classifying in the embedding retriever matters because both building the index and querying it call the embeddings API. An unclassified rate limit there would be recorded as "Unexpected …" and never retried (`tests/test_retrieval.py:70`, `test_embedding_errors_are_classified_for_retry`).

### 46.4 Why retries are not in the SDK

Both OpenAI-backed classes pass `max_retries=0` to `ChatOpenAI`; the comment explains: "Retries are handled by the runner (one place, observable attempt counts), so the client's own retry loop is disabled" (`providers.py:98-101`). The attempt count is then stored per case (`CaseResult.attempts`) and shown with errors ("Error after N attempt(s)", `ui/views/results.py:155`). **Limitation:** `EmbeddingRetriever` still passes the configured `max_retries` to `OpenAIEmbeddings` (`retrieval.py:152-152`), so the client library retries embedding calls internally first. Only when it gives up does the classified error reach the runner, which then applies its own back-off. Those inner retries are not counted in `attempts`, and the two layers can multiply the total wait.

## 47. Prompt and task configuration

### 47.1 Prompts

`prompts.py` holds the only prompt text in the product. Both prompts restrict the model to the supplied evidence and define one exact abstention sentence:

```python
ABSTAIN_ANSWER = "The PDF does not provide enough information to answer the question."
```

(`prompts.py:8`.) `RAG_SYSTEM_PROMPT` tells the model to answer "using ONLY the numbered context passages provided" and to reply with that sentence if they do not contain the answer (`prompts.py:21-26`). The user message is built by `rag_user_prompt`, which numbers passages `[1] … [k]` (`prompts.py:29-34`). `AGENT_SYSTEM_PROMPT` instructs the agent to use `collecting_info` before answering and to base answers only on retrieved information (`prompts.py:10-19`).

The exact abstention sentence is what makes abstentions machine-recognisable: `text.is_abstention` matches it and a few paraphrases with four regular expressions (`text.py:36-41`, `:98-100`), and the extractive generator returns the same constant when it finds no overlapping sentence (`providers.py:80-81`).

### 47.2 Task configuration

The "task" a run performs is described entirely by `RunConfig` (Chapter 42) and assembled by the two front ends:

| Field | CLI (`cli.py:40-65`) | UI (`ui/views/new_run.py`) |
|---|---|---|
| metrics | `--metrics` or defaults: lexical four for offline, lexical + judge for OpenAI (`cli.py:41-42`) | Multiselect limited to metrics usable with the current key (`:125-131`) |
| thresholds | repeated `--threshold metric=value`; malformed values → `ConfigError` (`cli.py:43-49`) | Number inputs per selected metric (`:135-140`) |
| judge model | Recorded only if a judge metric is selected (`cli.py:57-58`) | Text input shown only if a judge metric is selected (`:132-134`) |
| workers | `--workers`, else 1 offline / `RAGWB_MAX_WORKERS` for OpenAI (`cli.py:60`) | Number input with the same default (`:144`) |
| answer sentences | `--answer-sentences` (default 2) | Shown for offline only (`:115-118`) |
| failure injection | `--inject-failures` | Slider for offline only (`:145-149`); skip-headings checkbox and (offline) min-evidence slider `:150-158` |

The judge-model rule keeps the configuration honest: an offline run must not claim a judge model that never ran. The comment at `cli.py:57` states it.

### 47.3 Judge rubric

The GEval correctness criterion is a constant: "Determine whether the actual output is factually correct based on the expected output" (`metrics/judge.py:25`). The comment above it summarises the rubric: "the judge compares the answer with the reference answer for factual agreement" (`metrics/judge.py:24`). Changing the criterion text changes what the score means, so it is a module constant rather than a setting.

## 48. Metric calculation and aggregation

### 48.1 The metric contract

A metric is a `Metric(spec, scorer)` (`metrics/base.py:58-63`). `MetricSpec` (`:37-46`) carries name, label, family (`lexical`, `semantic` or `llm_judge`), description, default threshold and four requirement flags (reference, context, OpenAI, and since release 1.2 a local embedding model). `Metric.evaluate(inp, threshold=None)` (`:75-98`) is the single entry point:

```python
        if self.spec.requires_reference and not inp.expected_answer:
            return MetricResult(name=self.name, status="skipped", threshold=threshold,
                                reason="no expected_answer for this case")
```

(`metrics/base.py:77-79`.) After the reference and context checks, it calls `score`. A `MetricSkipped` raised by the scorer becomes `skipped` with its message (`:84-85`). Any other exception becomes `error` with `"{Type}: {message}"` truncated to 500 characters and a warning log line (`:86-89`). The returned score is then range-checked:

```python
        score = float(score)
        if not -SCORE_TOLERANCE <= score <= 1 + SCORE_TOLERANCE:  # a scorer bug, not a low/high score
            return MetricResult(name=self.name, status="error", threshold=threshold,
                                reason=f"score {score!r} outside [0, 1]")
        score = min(1.0, max(0.0, score))  # absorb floating-point noise only
```

(`metrics/base.py:93-97`, with `SCORE_TOLERANCE = 1e-9` at `:23`, commented "e.g. GEval can return 1.0000000000000002".) A score outside the range by more than the tolerance is treated as a scorer bug and recorded as a metric `error`. A value just outside the range is float noise and is clamped. Only then is `passed = score >= threshold` computed (`:96-97`). Clamping every score silently would have hidden a broken scorer behind plausible 0s and 1s. `tests/test_metrics.py:148` (`test_out_of_range_scores_are_errors_but_float_noise_is_absorbed`) covers both branches.

### 48.2 Catalogue

| Metric | Family | Default threshold | Needs | Computation |
|---|---|---:|---|---|
| `exact_match` | lexical | 1.0 | reference | SQuAD-normalised strings equal (`lexical.py:17-20`) |
| `token_f1` | lexical | 0.5 | reference | Multiset token overlap F1 (`lexical.py:23-36`) |
| `rouge_l` | lexical | 0.5 | reference | LCS-based F1 (`lexical.py:52-60`) |
| `context_recall` | lexical | 0.7 | reference, context | Share of reference content terms present in context (`lexical.py:63-81`) |
| `groundedness` | lexical | 0.7 | context | Share of answer content terms present in context (`lexical.py:84-100`) |
| `answer_relevancy` | llm_judge | 0.7 | OpenAI | DeepEval `AnswerRelevancyMetric` |
| `faithfulness` | llm_judge | 0.7 | context, OpenAI | DeepEval `FaithfulnessMetric` |
| `context_relevancy` | llm_judge | 0.7 | context, OpenAI | DeepEval `ContextualRelevancyMetric` |
| `correctness` | llm_judge | 0.7 | reference, OpenAI | DeepEval `GEval` with the correctness criterion |

(Specs at `metrics/lexical.py:103-121` and `metrics/judge.py:27-45`; the same table is printed by `ragwb metrics`.)

Two lexical metrics skip in specific situations rather than produce misleading numbers:

- `context_recall` skips when the reference itself is an abstention — an unanswerable case — because "the reference's words ('not enough information') say nothing about retrieval" (`lexical.py:69-71`).
- `groundedness` skips abstaining answers: "nothing to ground" (`lexical.py:90-91`).

Both also skip when the text has no content terms after stop-word removal (`lexical.py:73-74`, `:93-94`). Their reasons list up to eight missing or unsupported terms (`lexical.py:79-80`, `:98-99`), which is what the case-detail view shows next to the score.

### 48.3 Judge metrics

`JudgeMetric.score` (`metrics/judge.py:83-98`) builds a DeepEval `LLMTestCase` with `input`, `actual_output`, `expected_output` and `retrieval_context` (or `None` when empty), obtains a **fresh** DeepEval metric from the factory, calls `measure` synchronously, translates SDK errors, rejects a `None` score, and returns the score with the reason truncated to 2,000 characters. The factory (`:118-132`) creates a new `deepeval.models.OpenAIModel(model, api_key, temperature=0, timeout, base_url?)` for every measurement (`:110-116`) and passes `async_mode=False` and `include_reason=True` (GEval does not take `include_reason`, so it is removed for that metric, `:129`). The module docstring gives the reason for fresh objects: DeepEval metrics "hold per-measurement state, so sharing them across threads would be unsafe" (`metrics/judge.py:3-4`).

### 48.4 Aggregation

`summarize_metric(name, results, threshold)` (`aggregate.py:47-71`) classifies every case exactly once:

| Case situation | Counted as |
|---|---|
| `case.status == "error"` | `n_error` |
| Case ok but metric absent | `n_skipped` |
| Metric `ok` with a score | scored (and `n_passed` if passed) |
| Metric `skipped` | `n_skipped` |
| Metric `error` | `n_error` |

Mean (`statistics.fmean`), median, sample standard deviation (only with two or more scores), min and max are computed over scored values; `pass_rate = n_passed / n_scored`; the CI comes from `bootstrap_ci` (Chapter 60). With no scored values everything is `None`, not zero (`tests/test_aggregate.py:35`). `summarize_run` (`aggregate.py:75-92`) adds latency mean and 95th percentile over successful cases (linear interpolation, `aggregate.py:37-44`), token totals and cost total — each `None` when no case reported the quantity, so "unknown" is never shown as 0.

The `injected-failures-30pct` example run illustrates the counts. `ragwb show` reports 20 cases, 17 ok and 3 errors (q03, q16 and q17), and every metric reports `scored 17, err 3`. Its token-F1 mean of 0.344 is over the 17 scored cases only. The unanswerable example shows skips: context recall is `scored 2, skip 4`, because the four unanswerable references are abstentions.

## 49. Evaluation orchestration

### 49.1 The runner's dependencies

```python
class EvaluationRunner:
    def __init__(self, settings: Settings, store: RunStore, *,
                 pipeline_factory: Callable[..., Pipeline] = build_pipeline,
                 metrics_factory: Callable[..., list[Metric]] = build_metrics,
                 sleep: Callable[[float], None] = time.sleep):
```

(`runner.py:71-75`.) The three keyword-only parameters exist for tests: a fake pipeline factory scripts provider failures per question, and a fake `sleep` records back-off delays instead of waiting (`tests/test_runner.py:63-80`).

### 49.2 Case evaluation

`evaluate_case` (`runner.py:184-206`) runs the case in a daemon thread and waits for it for at most `case_timeout_s` (default 600 s, `RAGWB_CASE_TIMEOUT_S`; `runner.py:191-199`). If the thread is still alive after the limit, the case is recorded as an `error` ("Case exceeded the N s time limit and was abandoned") and the run moves on (`runner.py:200-205`); Python cannot kill a thread, so the abandoned call may keep running until its own HTTP timeout and its result is discarded (`runner.py:187-189`). The thread runs `_evaluate_case_guarded` (`runner.py:208-215`), which turns any internal exception into an `error` case with `"Internal {Type}: {message}"` and logs the traceback. `_evaluate_case` (`runner.py:217-232`):

1. Calls `_generate_with_retries`. If it returns no generation, the case is recorded as `error` with the attempt count and message (`:220-222`).
2. Builds `MetricInput` from the case and the generation's context texts (`:223-224`).
3. Evaluates every metric with its effective threshold (`:225`).
4. Returns an `ok` `CaseResult` with rounded latency, tokens, `_cost(generation)`, attempts and metric results (`:226-232`).

A case is `error` only when no answer was produced. A metric that fails is recorded inside an `ok` case as a metric `error`, so one broken judge call does not discard the answer or the other metrics.

### 49.3 Cost

`_cost` (`runner.py:258-262`) returns `None` unless both prices and both token counts are known; otherwise `(prompt_tokens × input_price + completion_tokens × output_price) / 1,000,000`. The settings comment explains why prices default to unset: "prices change; when unset, cost is reported as unknown instead of guessed" (`config.py:82-83`). The prices in effect are stored with every run under `prices_usd_per_mtok` (`runner.py:114`, `:254-256`), so an old run keeps the prices it was costed with. Judge-model cost is captured separately: `JudgeMetric._measure` reads DeepEval's `evaluation_cost` (`metrics/judge.py:97-99`) and `Metric.evaluate` stores it as `MetricResult.cost_usd` (`metrics/base.py:92`, `:96-97`). **Limitation:** judge token counts are not available, and the `evaluation_cost` figure has never been checked against a live call.

### 49.4 Environment capture

`environment_info()` (`runner.py:270-278`) records the workbench version, Python version, `platform.platform()` and the installed versions of `deepeval`, `langchain`, `langchain-openai`, `openai`, `pymupdf`, `streamlit` and `pydantic` (`runner.py:45`), with `None` for packages that are not installed. Together with the two file hashes and the full configuration, this is the run's provenance.

## 50. Result representation

### 50.1 In storage

Run-level fields are columns; everything structured is JSON (`storage.py:31-57`):

| Table | Columns |
|---|---|
| `runs` | `id` (PK), `name`, `status`, `created_at`, `finished_at`, `config_json`, `dataset_sha256`, `document_sha256`, `n_cases`, `summary_json`, `environment_json`, `notes`, `heartbeat_at` |
| `case_results` | `run_id` (FK → `runs.id`, `ON DELETE CASCADE`), `case_id`, `position`, `status`, `data_json`; PK `(run_id, case_id)` |

An index on `runs(created_at)` supports the newest-first listing (`storage.py:56`).

### 50.2 In memory and in the UI

`reporting.cases_dataframe` (`reporting.py:30-49`) flattens each `CaseResult` into one row with identity, answer, error, latency, tokens, cost, attempts, the number and ids of contexts, and three columns per metric: `<m>` (score), `<m>_passed`, `<m>_status`. The Cases tab filters on `<m>_passed == False`, which deliberately excludes unscored rows (`None`) from "below threshold" (`ui/views/results.py:119-120`). `summary_dataframe` gives one row per run with configuration essentials and metric means (`reporting.py:53-69`); `comparison_dataframe` gives one row per shared metric with paired statistics and a `ci_excludes_zero` flag (`reporting.py:72-82`).

### 50.3 In the CLI

`_print_summary` (`cli.py:82-96`) prints counts, mean latency and a fixed-width table of mean, 95% CI, pass rate and scored/skipped/error counts, followed by any provenance warnings carried by an imported run, each prefixed with `!`. For the k = 3 example run (`ragwb show 20261023-194808-offline-bm25-k3-2d53f3`) it prints:

```text
cases 20  ok 20  errors 0  mean latency 0.2 ms
metric                          mean           95% CI    pass  scored  skip  err
Token F1                       0.346      0.285-0.419      5%      20     0    0
ROUGE-L                        0.317      0.252-0.393      5%      20     0    0
Context recall (lexical)       0.885      0.839-0.930     95%      20     0    0
Groundedness (lexical)         1.000      1.000-1.000    100%      20     0    0
```

## 51. Error handling and recovery

### 51.1 Exception hierarchy

| Exception | Base | Raised by | Meaning |
|---|---|---|---|
| `ConfigError` | `ValueError` | `config`, `metrics`, `pipeline`, `runner.prepare`, `cli.build_config` | Invalid or missing configuration |
| `DatasetError` | `ValueError` | `datasets.load_dataset` | Dataset has validation errors (carries the report) |
| `DocumentError` | `ValueError` | `documents.load_chunks` | Unreadable, unsupported or empty document |
| `ProviderError` | `RuntimeError` | providers, pipeline, judge | Permanent model-call failure |
| `TransientProviderError` | `ProviderError` | `classify_openai_error` | Retryable model-call failure |
| `MetricSkipped` | `Exception` | lexical scorers | Control flow: produce a `skipped` result |
| `StorageError` | `RuntimeError` | `RunStore` | Store cannot be opened, is from a newer schema, or any SQLite operation fails (all `sqlite3` errors are translated) |
| `BundleError` | `ValueError` | `archive.load_bundle` | Not a valid run bundle |

### 51.2 Where each failure is absorbed

| Failure | Absorbed at | Effect |
|---|---|---|
| Bad configuration/dataset/document | `prepare` raises; CLI prints `error: …` exit 1 (`cli.py:682-686`); UI shows "Configuration rejected" (`new_run.py:211-213`) | No run row |
| Transient provider error | `_generate_with_retries` (`runner.py:241-247`) | Retried up to `max_retries` |
| Permanent provider error | `_generate_with_retries` (`runner.py:248-249`) | Case `error` |
| Unexpected exception in a pipeline | `_generate_with_retries` (`runner.py:250-252`) | Case `error` "Unexpected Type: …", traceback logged |
| Exception elsewhere in case evaluation | `_evaluate_case_guarded` (`runner.py:208-215`) | Case `error` "Internal Type: …" |
| Metric failure or out-of-range score | `Metric.evaluate` (`metrics/base.py:83-95`) |
| Case that never returns | `evaluate_case` time limit (`runner.py:197-205`) | Case `error` "…exceeded the N s time limit and was abandoned" | Metric `error` inside an `ok` case |
| Cancellation / Stop / Ctrl-C | `execute` (`runner.py:132-137`) | Run `cancelled` with summary of finished cases, exception re-raised |
| Process death | `recover_interrupted` at a start-up at least 15 minutes after the last heartbeat (`services.py:32-34`, `storage.py:154-166`) | Run `interrupted`; finished cases kept |
| SQLite failure (locked, corrupt, unwritable) | `RunStore._connect` (`storage.py:93-96`) | `StorageError`, reported by the CLI as `error: …` (exit 1) |
| Bundle write failure | `import_bundle` (`archive.py:77-79`) | Partially imported run deleted |

### 51.3 Injected failures

`ExtractiveGenerator._maybe_fail` (`providers.py:60-66`) raises `ProviderError("Injected offline failure …")` when `random.Random(f"{seed}:{question}").random() < failure_rate`. The seed string makes the decision a pure function of seed and question, so a rerun fails on the same cases (`tests/test_providers_pipeline.py:30`). It is raised as a permanent error on purpose; the comment says retrying "a deterministic failure would only add back-off delay" (`providers.py:63-64`). With the default settings, three retries of a deterministic failure would add about 7–10 s of sleeping per failing case (1–2 + 2–3 + 4–5 s, §60.6) and change nothing.

### 51.4 Gaps

- **One translation point for SQLite errors.** Every store operation goes through `_connect`, which turns any `sqlite3.Error` other than an integrity error into `StorageError` (`storage.py:93-96`). A locked or corrupted database therefore surfaces in the CLI as `error: …` with exit code 1, never as a traceback, whichever method hit it (`tests/test_storage.py:95`, `test_sqlite_errors_become_storage_errors`).
- **Limitation:** if `finish_run` itself fails at the end of `execute`, the run stays `running` until a start-up at least 15 minutes after its last heartbeat marks it `interrupted`; the committed case results remain.

## 52. Persistence and storage

### 52.1 Connection discipline

```python
    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
```

(`storage.py:87-89`.) Every method opens a connection and uses `with conn:` so that the transaction commits on success and rolls back on exception (`:91`). `sqlite3.IntegrityError` is re-raised unchanged so that callers can turn constraint violations into specific messages; every other `sqlite3.Error` becomes `StorageError("Run store error (runs.db): …")` (`:93-96`). The connection is closed in `finally` (`:92-93`). The 15-second timeout lets a writer wait for another process's lock. Foreign keys are enabled per connection because SQLite does not persist that setting; it is what makes `DELETE FROM runs` cascade to `case_results` (`tests/test_storage.py:44`).

### 52.2 Schema versioning

At construction the store creates its tables if absent and reads `PRAGMA user_version` (`storage.py:67-83`). The current version is `SCHEMA_VERSION = 3` (`storage.py:26`):

| Stored version | Action |
|---|---|
| 0 (new file) | Tables created with the v3 schema; stamped 3 |
| 1 | `ALTER TABLE runs ADD COLUMN heartbeat_at TEXT`, then the column added for 3; stamped 3 (`storage.py:76-77`) |
| 2 | `ALTER TABLE runs ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'`; stamped 3 (`storage.py:78-79`) |
| 3 | Nothing |
| > 3 | `StorageError` "was created by a newer version (schema N)" (`storage.py:72-73`) |

Since release 1.2 the migration does not trust the version number alone: it asks `PRAGMA table_info(runs)` which columns exist and adds whichever of `heartbeat_at` and `tags_json` is missing (`storage.py:74-79`, Part XIV §152.2). The migration runs inside the same transaction as the schema script. `OSError` (for example an unwritable directory) is reported as a `StorageError` too (`storage.py:82-83`). Tests cover the migration (`tests/test_storage.py:77`, `test_schema_v1_store_is_migrated`) and the refusal (`tests/test_storage.py:102`). Version 2 exists to support heartbeat-based recovery (§52.3); version 3 adds run tags (Part XIV §152).

### 52.3 Writes

| Method | SQL | Failure mapping |
|---|---|---|
| `create_run` (`:101-115`) | `INSERT INTO runs …` with JSON-serialised config, summary and environment (`ensure_ascii=False` keeps non-ASCII readable) and `heartbeat_at = now` | `IntegrityError` → "A run with id … already exists"; other errors → `StorageError` via `_connect` |
| `add_case_result` (`:117-125`) | `INSERT INTO case_results …` with `model_dump_json()`, then `UPDATE runs SET heartbeat_at = now` in the same transaction | `IntegrityError` (duplicate case or missing run) → `StorageError` |
| `finish_run` (`:127-135`) | `UPDATE runs SET status, summary_json, finished_at` | Zero rows updated → `StorageError("Run … not found")` |
| `set_tags` / `set_notes` (`:137-148`) | `UPDATE runs SET tags_json = ?` / `UPDATE runs SET notes = ?` (release 1.2) | Zero rows updated → `StorageError("Run … not found")` |
| `delete_run` (`:150-152`) | `DELETE FROM runs WHERE id = ?` | Returns whether a row was deleted |
| `recover_interrupted(stale_after_s=STALE_AFTER_S)` (`:154-166`) | `UPDATE runs SET status = 'interrupted', finished_at = now WHERE status = 'running' AND COALESCE(heartbeat_at, created_at) < now − stale_after_s` | Returns the count |

The heartbeat makes recovery safe when several processes share one store. `STALE_AFTER_S` is 15 minutes (`storage.py:29`). The comment explains the margin: one slow case can take "4 attempts x 60 s + delays", about five minutes with default settings (`storage.py:27-28`). A run being executed by another process keeps committing cases and is therefore never older than the cutoff. A run without a heartbeat — rows from a v1 store — falls back to `created_at`. Even if a live run were marked wrongly, its own `finish_run` overwrites the status with the real outcome. All timestamps are written by `utcnow().isoformat()` as ISO-8601 strings with the same UTC offset, so the string `<` comparison in SQL orders them chronologically. Without the heartbeat, recovery would have to treat every `running` row as dead, and `ragwb list` alone could relabel a live run in another process (`tests/test_storage.py:57`, `test_recover_interrupted_only_touches_stale_runs`; `:69`, `test_case_commits_refresh_the_heartbeat`).

All values are passed as parameters (`?`); the only formatted SQL is the `PRAGMA user_version = {SCHEMA_VERSION}` statement, whose value is a module constant (`storage.py:81`).

### 52.4 Reads

`get_run`, `list_runs` (newest first, ties by id), `get_case_results` (ordered by `position`) and `count_case_results` (`storage.py:175-193`). `_row_to_run` (`storage.py:196-205`) rebuilds a `RunRecord`, parsing timestamps with `datetime.fromisoformat` and JSON columns with `json.loads` / `model_validate_json`. Because case results are always read ordered by `position`, the order in which worker threads finished does not matter (`tests/test_runner.py:124`, which also checks that a four-worker run's answers equal a serial run's).

### 52.5 Bundles

A bundle is `{"format": "rag-workbench-run", "version": 1, "run": RunRecord, "cases": [CaseResult…]}` written by `export_json` (`reporting.py:114-125`). `load_bundle` (`archive.py:34-56`) enforces a 50,000,000-byte limit, UTF-8 JSON, the format tag and version, validates the run and every case with pydantic, and rejects duplicate case ids. `import_bundle` (`archive.py:59-81`) is idempotent: an existing id returns `None`. It sets status `imported` and keeps the exported status as `config["original_status"]` and the file name as `config["imported_from"]`. It deletes the run again if any case insert fails.

`import_bundle` also **recomputes the summary** from the bundle's cases with `summarize_run`, using the bundle's metric list and thresholds. The summary stored in the file is discarded: "The summary shown for an imported run is recomputed from its cases, never taken from the file" (`archive.py:67-72`). A bundle whose summary disagrees with its cases therefore cannot misreport means or intervals (`tests/test_archive_reporting.py:82`, `test_bundle_summary_is_recomputed_not_trusted`).

On export, `export_json` replaces `dataset_path` and `document_path` with `portable_path(...)`: a path relative to the project root when the file lies inside it, otherwise only the file name. The comment gives the reason: absolute local paths "reveal user names and folders" (`reporting.py:103-111`, `:118-122`; `tests/test_archive_reporting.py:93`). The run stored locally keeps its original paths; only the shared bundle is made portable.

## 53. Reporting and exports

| Format | Function | Content | Encoding |
|---|---|---|---|
| CSV | `export_csv` (`reporting.py:92-100`) | `cases_dataframe` — one row per case | UTF-8 with BOM, "so Excel detects UTF-8" (`:100`) |
| JSON | `export_json` (`reporting.py:114-125`) | Full run bundle, re-importable; input paths made portable | UTF-8, indented, `ensure_ascii=False` |
| Markdown | `export_markdown` (`reporting.py:140-185`) | Header, provenance warnings, summary table, failed cases, the five lowest-scoring cases per metric with reasons, a closing caveat | UTF-8 |

`export_run` dispatches by format and raises `ValueError` for unknown formats (`reporting.py:188-195`). The CLI writes to `data/exports/<safe id>.<fmt>` or `--out-dir` (`cli.py:259-264`, `reporting.py:204-208`); the UI streams the same bytes through `st.download_button` without writing to disk (`ui/views/results.py:180-188`).

Details that matter:

- **Formula neutralisation.** `_csv_safe` prefixes a `'` to any text cell starting with `=`, `+`, `-`, `@`, tab or carriage return (`reporting.py:18`, `:85-89`). `export_csv` applies it to every column that is neither numeric nor boolean; the comment records why the check is not `dtype == object`: "pandas 3 stores text with a dedicated 'str' dtype, not object" (`reporting.py:94-97`). A check for `object` dtype would silently skip every text column under pandas 3; `test_csv_export_neutralises_formulas` guards the behaviour (`tests/test_archive_reporting.py:119`).
- **Markdown cell escaping.** `_md_cell` escapes `|` and replaces newlines so that answers cannot break table rows (`reporting.py:136-137`).
- **Honest footer.** Every Markdown report ends with "Judge-model scores are model assessments, not ground truth; lexical scores measure word overlap, not meaning" (`reporting.py:183-184`).
- **Unknown values.** `_fmt` renders `None` as an em dash, never as 0 (`reporting.py:128-133`).

## 54. Logging and diagnostics

### 54.1 Logger configuration

`configure_logging(settings, console=True)` (`logging_setup.py:79-105`) configures only the `rag_workbench` logger:

- Level from `RAGWB_LOG_LEVEL` (validated in `config.py:92-103`), applied on every call (`logging_setup.py:82`).
- Idempotent: a private attribute `_rag_workbench_configured` prevents duplicate handlers when Streamlit reruns or tests call it again (`:83-84`, `:104`); `close_logging` (`:69-76`) detaches the handlers so a test or a data-directory deletion can start clean.
- A `RotatingFileHandler` at `data/logs/rag_workbench.log`, 2,000,000 bytes, three backups, UTF-8 (`:94`); if the directory cannot be created, a warning is logged and file logging is skipped (`:92-96`).
- An optional console handler (`:97-98`); both front ends turn it off.
- A `RedactingFormatter` with format `"%(asctime)s %(levelname)-7s %(name)s: %(message)s"` (`:90`), or, with `RAGWB_LOG_FORMAT=json`, a `RedactingJsonFormatter` that writes one JSON object per line with `ts`, `level`, `logger`, `message` and, for exceptions, `exc` (`:33-48`, `:87-88`).
- `propagate = False` so records do not reach the root logger (`:103`).

### 54.2 Redaction

Redaction happens at two levels, sharing one `redact` function. `RedactSecretsFilter.redact` replaces the configured API key (if at least eight characters) with `***` and anything matching `sk-[A-Za-z0-9_\-]{8,}` with `sk-***` (`logging_setup.py:18`, `:56-59`).

1. **Filter** (`logging_setup.py:51-66`), attached to every handler. It formats the message (`record.getMessage()`). Only if redaction changes it does it replace `record.msg` and clear `record.args` (`:61-66`). This redacts secrets passed as `%s` arguments as well as literal text, before any handler sees the record.
2. **Formatter** (`RedactingFormatter`, `logging_setup.py:22-30`), set on every handler. It redacts the *fully formatted* output — "including exception tracebacks and stack info" — by running `redact` over `super().format(record)` (`:29-30`). The filter alone could not do this, because a traceback is only rendered by the formatter. An exception message containing a key, logged with `log.exception`, would otherwise reach the file unredacted.

The two levels are complementary: the filter cannot see a traceback, and the formatter alone would leave secrets in `record.args` for any handler without it. The module docstring calls redaction "a second line of defence; the code itself never logs credentials" (`logging_setup.py:4-5`). `tests/test_cli_services.py:91` checks both replacement rules, and `tests/test_cli_services.py:79` (`test_redacting_formatter_covers_tracebacks`) checks the traceback case.

### 54.3 What is logged

| Event | Level | Location |
|---|---|---|
| Chunks loaded from a document | INFO | `documents.py:64` |
| Run started (cases, provider, pipeline, retriever, k) | INFO | `runner.py:118-119` |
| Transient error and retry delay | INFO | `runner.py:246` |
| Unexpected error answering a question (with traceback) | ERROR | `runner.py:251` |
| Internal error evaluating a case (with traceback) | ERROR | `runner.py:212` |
| Case abandoned after the time limit | ERROR | `runner.py:201` |
| Judge metric transient error and retry | INFO | `metrics/judge.py:76` |
| Metric failure | WARNING | `metrics/base.py:88` |
| Run cancelled after n/N cases | WARNING | `runner.py:136` |
| Run finished with status | INFO | `runner.py:142` |
| Runs marked interrupted at start-up | WARNING | `services.py:34` |
| Bundle imported / already present | INFO | `archive.py:80`, `:63` |

A sample from the project's log file (`data/logs/rag_workbench.log`, observed):

```text
2026-10-24 01:18:08,641 INFO    rag_workbench.runner: Run 20261023-194808-offline-bm25-k3-2d53f3 started: 20 cases, provider=offline, pipeline=rag, retriever=bm25, k=3
2026-10-24 01:18:08,783 INFO    rag_workbench.runner: Run 20261023-194808-offline-bm25-k3-2d53f3 finished with status completed
```

Log timestamps are local time, while run ids and stored timestamps are UTC (`models.py:18-19`), which is why the id above shows 19:48 and the log 01:18 on the next day (the machine's clock is UTC+5:30).

### 54.4 Diagnostics outside the log

Each case carries its own diagnosis: `error`, `attempts`, per-metric `status` and `reason`. The run carries `environment` and the input hashes, shown on the Configuration tab (`ui/views/results.py:173-178`). The Settings page shows the effective configuration with the key replaced by `openai_api_key_configured` (`config.py:163-169`, `ui/views/settings.py:32-33`) and the paths of the store, uploads, exports and log (`ui/views/settings.py:53-58`).

## 55. API endpoints

### 55.1 There is no HTTP API

The workbench exposes no HTTP endpoints of its own. The Streamlit server serves the user interface, but the product defines no REST, RPC or webhook routes. This is deliberate. The only clients are the bundled Streamlit app, which calls the package in-process, and the CLI. **Rationale:** an HTTP layer would need real authentication, request validation and a job model for long runs, and it would expose an OpenAI-key-spending service on the network; none of that is needed by a single local user. The two programmatic surfaces are the CLI and the Python package.

### 55.2 CLI surface

| Command | Arguments | Effect | Exit codes |
|---|---|---|---|
| `run` | `--name`, `--dataset`, `--document`, `--provider {offline,openai}`, `--pipeline {rag,agent}`, `--retriever {bm25,embedding,hybrid,local,hybrid-local}`, `-k`, `--metrics`, `--threshold M=V` (repeatable), `--model`, `--judge-model`, `--workers`, `--limit`, `--answer-sentences`, `--inject-failures`, `--min-evidence`, `--skip-headings`, `--seed`, `--notes`, `--quiet` | Execute and store a run; print progress and summary | 0 completed, 2 partial/failed/cancelled, 1 error |
| `list` | `[--search WORD...] [--tag T] [--status S]` | Table of stored runs, optionally filtered, with a `tags` column (`cli.py:99-112`) | 0 |
| `show` | `run_id` | Configuration essentials and summary; since 1.4.1 also the run's tags and notes when it has any | 0, 1 unknown id |
| `compare` | `run_a run_b` | Paired comparison of B against A | 0, 1 no shared metric / unknown id |
| `export` | `run_id --format {csv,json,md} --out-dir` | Write an export file | 0, 1 |
| `validate` | `dataset` | Print cases, errors, warnings | 0 valid, 1 invalid |
| `delete` | `run_id --yes` | Delete a run (refuses without `--yes`; an unknown id prints `No run with id …` on stderr) | 0 deleted, 1 refused or unknown id (`cli.py:274-282`) |
| `metrics` | — | Describe all metrics | 0 |
| `import` | `bundle.json…` (one or more, required) | Import bundles written by `export --format json`, idempotently (`cli.py:301-305`, `:510-512`) | 0, 1 invalid bundle |
| `score` | `--question --answer --expected --context… --metrics --judge-model` | Score one answer; nothing stored | 0, 1 |
| `labels-template` | `run_id --out FILE [--force]` | Write a CSV for human pass/fail labelling (`cli.py:302-310`) | 0, 1 |
| `calibrate` | `run_id --labels FILE --metric M [--sweep] [--rescore]` | Agreement and Cohen's kappa between a metric and labels (`cli.py:333-367`; the header reads `<metric> vs labels from <file>, run <name> [<id>]`, and since 1.4.1 `--rescore` stops with a `ConfigError` when the metric can be computed for no case); `--sweep` adds agreement at every threshold 0.10-0.95 and `--rescore` computes an offline or local-model metric from stored answers (`cli.py:313-330`; Part XVI §174) | 0, 1 if nothing could be compared |
| `slices` | `run_id --by FIELD` | Per-value summary of a dataset metadata field (`cli.py:370-389`) | 0, 1 |
| `rerun` | `run_id [--name] [--quiet]` | Repeat a stored run from its recorded configuration, warning if the dataset or document hash changed (`cli.py:392-409`) | like `run` |
| `backup` | `[--out-dir]` | Verified copy of the run store (`cli.py:424-427`) | 0, 1 |
| `restore` | `backup [--yes] [--force]` | Replace the run store with a backup after validating it; writes a `pre-restore-*` safety copy first and refuses recently active runs unless `--force` (`cli.py:418-427`; release 1.4, Part XVI §171) | 0, 1 |
| `prune` | `[--keep-last N] [--older-than-days D] [--yes]` | Select old runs, never one tagged `keep` (1.4.1); a dry run unless `--yes` (`cli.py:430-443`) | 0, 1 |
| `doctor` | — | Installation, configuration and store checks, no network (`cli.py:465-474`) | 0, 1 if any check fails |
| `tag` | `run_id [--add a,b] [--remove c]` | Edit a run's tags (`cli.py:115-121`; Part XIV §152) | 0, 1 |
| `note` | `run_id [TEXT] [--clear]` | Set or clear a run's note (`cli.py:221-228`) | 0, 1 |
| `regress` | `baseline candidate [--max-drop] [--min-pairs] [--max-error-increase] [--metrics]` | Regression gate (`cli.py:138-147`; Part XIV §153; since 1.4.1 a `--metrics` name that is not shared by both runs is an error, exit 1, that lists the shared metrics) | 0 pass, 3 regression, 4 nothing judged |
| `tune-abstention` | `[--dataset … --document …]` | Choose `min_evidence` on a development half, report on a test half (`cli.py:124-135`; Part XIV §154) | 0, 1 |
| `user` | `add\|remove\|set-role\|set-password\|list [NAME] [--role R] [--replace] [--password-stdin] [--force]` | Manage web-app accounts and their roles (`cli.py:159-193`; Part XIV §156, Part XV §165) | 0, 1 |
| `judge-noise` | `run_id [--repeats 3] [--metrics …] [--limit N] [--yes]` | Re-score a run's stored answers several times and report within-case SD, between-case SD, noise/signal and verdict flips per judge metric; makes API calls and asks for `--yes` above 30 measurements (`cli.py:197-219`; Part XV §164) | 0, 1 |

The parser also has a global `--version` flag (`cli.py:525`). The CLI therefore has 24 commands: the ten of release 1.0, seven added in 1.1 (Part XIII), five added in 1.2 (`tag`, `note`, `regress`, `tune-abstention` and `user`, Part XIV), one added in 1.3 (`judge-noise`, Part XV; `user` also gained `set-role`) and one added in 1.4 (`restore`, Part XVI; `user` also gained `set-password` and `--force`, and `calibrate` gained `--sweep` and `--rescore`).
(Parser at `cli.py:521-671`; handlers at `cli.py:69-519`.) A run argument is resolved by `_get_run`: the exact id, otherwise a unique id prefix, a unique id suffix (the short id the web app shows; at least 4 characters) or an exact run name; several matches raise a `LookupError` that lists up to five ids and asks for more of the id, and no match raises one with a hint to use `list` (`cli.py:503-518`), which `main` reports as `error: …` (`cli.py:639-643`). `ragwb score` scores one answer with chosen metrics without running a pipeline or storing anything, which is useful for checking how a metric reacts to a specific answer (`cli.py:476-487`).

### 55.3 Python surface

The package does not declare a stable public API (`__all__` in `__init__.py` lists only `__version__`; `metrics/__init__.py:52-55` declares the metric exports). The functions the front ends use are nevertheless a coherent programmatic interface:

```text
from rag_workbench.services import open_context
ctx = open_context()                                  # settings + store (+ interrupted-run recovery)
runner = ctx.runner()                                 # EvaluationRunner
prepared = runner.prepare(RunConfig(...))             # validates; raises ConfigError / DatasetError / DocumentError
run = runner.execute(prepared, progress=cb, cancel=event)   # RunRecord as stored
cases = ctx.store.get_case_results(run.id)            # list[CaseResult]
reporting.comparison_dataframe(run_a, cases_a, run_b, cases_b)
reporting.write_export(run, cases, "md", out_dir)
archive.import_bundle(ctx.store, path)
```

| Function | Signature (abridged) | Defined |
|---|---|---|
| `load_settings` | `(env=None, *, dotenv=True) -> Settings` | `config.py:204` |
| `open_context` | `(settings=None, *, console_logging=True) -> AppContext` | `services.py:27` |
| `EvaluationRunner.run` | `(config, progress=None, cancel=None) -> RunRecord` | `runner.py:102` |
| `EvaluationRunner.evaluate_case` | `(prepared, case, position) -> CaseResult` | `runner.py:184` |
| `build_pipeline` | `(config, settings, chunks=None) -> Pipeline` | `pipeline.py:146` |
| `build_metrics` | `(names, settings, *, judge_model=None, timeout_s=None) -> list[Metric]` | `metrics/__init__.py:34` |
| `Metric.evaluate` | `(inp: MetricInput, threshold=None) -> MetricResult` | `metrics/base.py:75` |
| `summarize_run` | `(results, metric_names, thresholds) -> RunSummary` | `aggregate.py:75` |
| `paired_comparison` | `(results_a, results_b, metric, *, tie_tolerance=1e-9) -> PairedComparison` | `aggregate.py:164` |
| `validate_file` / `parse_dataset` | `(path, **limits)` / `(data, name, **limits) -> DatasetReport` | `datasets.py:124`, `:68` |
| `load_chunks` | `(path, *, max_chars=2000, max_bytes=None) -> list[Chunk]` | `documents.py:38` |

**Limitation:** because this surface is not declared public, it carries no compatibility promise beyond what the tests exercise.

## 56. Frontend implementation

This chapter covers how the Streamlit pages are built; user workflows are described elsewhere in the book.

### 56.1 Page scripts and the rerun model

Each file in `src/rag_workbench/ui/views/` is a script that Streamlit executes from top to bottom on every widget interaction. The scripts therefore follow a fixed shape: obtain the context, read from the store, render, and stop early when a precondition fails. For example, the Compare page stops with an info box when fewer than two runs exist (`ui/views/compare.py:15-18`) and the Results page stops when the selected run has no summary yet (`ui/views/results.py:60-62`).

### 56.2 State and caching

| Mechanism | Used for | Location |
|---|---|---|
| `st.cache_resource` | One `AppContext` per server process (settings + store) | `ui/state.py:17-20` |
| `st.session_state["selected_run_id"]` | The run selected on one page, preselected on Results | `ui/state.py:13`, `:32-37` |
| `st.session_state["_dataset_upload_id"]` / `["_document_upload_id"]` | Save an upload once per new file, so a later manual selection is not overridden on rerun | `ui/views/new_run.py:43-48`, `:76-81` |
| `st.session_state["dataset_choice"]` / `["document_choice"]` | Preselect the just-uploaded file | `ui/views/new_run.py:47`, `:80` |
| Widget `key`s | Keep widget values across reruns (`results_run`, `compare_runs`, `metrics`, …) | throughout |
| `st.query_params` | Deep links: `?run=`, `?tab=`, `?case=` on Results; `?runs=id1,id2` on Compare | `ui/views/results.py:33`, `:73-76`, `:140`; `ui/views/compare.py:20-21` |

`context_or_stop` wraps the cached factory: a `ConfigError` (for example an out-of-range `RAGWB_MAX_WORKERS`) becomes an error message plus "Fix the variable in `.env` … and restart the app" and `st.stop()` (`ui/state.py:23-29`). Because the context is a cached resource, it is shared by all browser sessions of the server; this is safe because `RunStore` holds only a path and opens connections per operation, and `Settings` is frozen.

Nothing else is cached. Pages re-read the run list on every rerun, and the New evaluation and Datasets pages re-extract the selected document on every rerun (`ui/views/new_run.py:91`, `ui/views/data.py:62`). **Rationale:** reading from SQLite every time means a run finished in another session or by the CLI appears without cache invalidation; the cost is discussed in Chapter 58.

### 56.3 Navigation

Pages link to each other with `st.page_link` using the script path, e.g. after a run finishes (`ui/views/new_run.py:248`) or when a row is selected on the Overview table (`ui/views/overview.py:61-66`). Selecting a row stores the run id in session state; the Results page then prefers the `?run=` query parameter, then the session selection, then the newest run (`ui/views/results.py:31-36`). The Results page also accepts `?tab=` with the keys `summary`, `cases`, `case`, `config`, `export` mapped to tab titles and passed as `st.tabs(..., default=...)` (`ui/views/results.py:72-76`); the screenshot tooling uses these links (`scripts/seed_demo_runs.py`).

### 56.4 Executing a run from a page

The New evaluation page builds a `RunConfig` from widget values, calls `prepare`, then `execute` with a callback that writes into two placeholders created beforehand — a `st.progress` bar and an `st.empty` code box showing the last eight case lines (`ui/views/new_run.py:216-224`). Because Streamlit widgets can be updated from the running script, progress appears live without threads or polling. Before the button is enabled, the page computes a list of blocking problems (dataset invalid, no chunks, no metric, OpenAI selected without a key, empty name) and disables the button while any remain (`ui/views/new_run.py:177-189`, `:196`). Options that cannot work are not offered: the agent pipeline only appears for the OpenAI provider and the embedding retriever only when a key exists (`ui/views/new_run.py:103`, `:108`); judge metrics are hidden without a key, and semantic metrics without the optional package (`ui/views/new_run.py:130-131`).

### 56.5 Shared components

`ui/components.py` holds presentation helpers:

- `score_chart` (`:70-87`) draws Altair bars on a fixed `[0, 1]` y-scale "so differences are not visually exaggerated", with optional black rule marks for the CI and grouped bars via `xOffset`.
- `status_badge` maps statuses to Streamlit badge colours (`:13-16`, `:42-43`).
- `fmt` renders `None`/NaN as an em dash (`:46-51`).
- `provenance_warnings` renders an imported run's warnings in a bordered box (`:61-67`).
- `metric_columns_config` attaches each metric's description as column help (`:90-92`).
- `short_path` shows paths relative to the project root when possible (`:31-39`).

`ui/state.py` adds two labelling helpers used by every run selector. `short_id` returns only the random suffix of generated ids (`ui/state.py:40-42`). `run_label` joins name, status, creation time and short id, but leaves out the time for imported runs (`ui/state.py:45-48`). **Rationale:** an imported run's `created_at` comes from the bundle, so it would mislead as a "when was this run here" label.

### 56.6 Rendering untrusted text

Document text and retrieved chunks are rendered with `st.text`, which shows text literally; the comment says it is "never interpreted as markdown/HTML" (`ui/views/results.py:169`, `ui/views/data.py:87`). One header line on the Results page is built as HTML with `unsafe_allow_html=True`. It interpolates configuration values and the run id, each passed through `html.escape` first: "Config values can come from imported bundles, so every value is HTML-escaped before entering the markup" (`ui/views/results.py:3`, `:45-49`). Chapter 59 records how this was found.

## 57. Background tasks and concurrency

### 57.1 No background jobs

There is no scheduler, queue, daemon or background worker. A run executes synchronously in the thread that calls `execute`: the CLI's main thread or the Streamlit script thread of the session that pressed the button. The only concurrency is optional parallelism *within* a run.

### 57.2 The bounded thread pool

```python
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ragwb") as pool:
            pending: set[Future] = set()
            queue = iter(cases)
```

(`runner.py:161`.) With `max_workers == 1` the runner simply loops and checks the cancel event before each case (`runner.py:155-160`). With more workers, `_iter_results` (`runner.py:152-181`):

1. Submits cases until `2 × workers` futures are pending (`:162-168`). **Rationale:** enough queued work to keep threads busy, without submitting the whole dataset — which would make cancellation slow and hold every pending future in memory.
2. Waits with `FIRST_COMPLETED` (`:173`), yields the finished results sorted by position within that batch (`:171-172`), then tops the pending set back up (`:175-178`) unless cancellation was requested (`:173-174`).
3. In `finally`, calls `future.cancel()` on everything still pending (`:179-181`); futures that have not started are cancelled, running ones finish and the executor's context exit waits for them.

Because `_iter_results` is a generator consumed by `execute`, all side effects — `add_case_result`, `progress` callbacks — happen on the consuming thread, one at a time. SQLite is therefore written from a single thread per run, and Streamlit widgets are only touched by the script thread.

### 57.3 Thread safety of shared components

| Component shared across workers | Why it is safe |
|---|---|
| `BM25Retriever` | Read-only after construction |
| `EmbeddingRetriever` | Index creation guarded by `threading.Lock` (`retrieval.py:143`, `:140`) |
| `ExtractiveGenerator` | Read-only state; failure injection uses a local `random.Random` per call (`providers.py:65`) |
| `OpenAIChatGenerator` / agent | One `ChatOpenAI` client; agent tool and capture lists created per question (`pipeline.py:80-97`) |
| Lexical metrics | Stateless functions |
| Judge metrics | Fresh DeepEval metric and model objects per measurement (`metrics/judge.py:87`, `:89`) |
| `PreparedRun` | Not mutated during execution |

`tests/test_runner.py:124` runs the real dataset with four workers and checks that all 20 cases are present in position order and that the answers equal those of a serial run.

### 57.4 Cancellation semantics

| Trigger | Mechanism | Result |
|---|---|---|
| Caller sets the `cancel` event | Sequential loop returns before the next case; pooled loop stops submitting and drains in-flight cases | `cancelled`, finished cases kept (`tests/test_runner.py:97`) |
| Exception raised inside `progress` (Streamlit Stop) | `except BaseException` in `execute` sets the event, finishes as `cancelled`, re-raises | `cancelled` (`tests/test_runner.py:111`) |
| Ctrl-C in the CLI | `KeyboardInterrupt` reaches the same branch | `cancelled`, traceback printed |
| Process killed | No code runs | Row stays `running` until a start-up at least 15 minutes after the last heartbeat (`recover_interrupted`) |

**Limitation:** cancellation is cooperative. An in-flight OpenAI call is not aborted; it completes (or times out after `request_timeout_s`) before the run ends. Retry sleeps are not interrupted either.

### 57.5 Retry back-off

`_generate_with_retries` (`runner.py:234-252`) sleeps `retry_base_delay_s × 2^(attempt−1)` plus uniform jitter in `[0, retry_base_delay_s]` before each retry (`:244-245`). The algorithm and its rationale are in Chapter 60.

## 58. Performance-sensitive code

### 58.1 Observed numbers

These come from the project's own data and ad-hoc timing of the 1.0 build. The offline scale benchmark added in 1.1 (`scripts/benchmark.py`) is described in Part XIII:

- `ragwb show` reports a mean per-case latency of 0.2 ms for the k = 1 and k = 3 example runs and 0.3 ms for k = 5. This is retrieval plus extractive generation, as timed inside `RAGPipeline.answer`.
- A complete 20-case offline run of the default configuration takes about 0.3 s when executed in-process with an already-open context (measured 0.31–0.33 s over three runs). That includes metric scoring, 20 per-case commits and the bootstrap summary. The measurement used `EvaluationRunner.run`, timed with `time.perf_counter`, with `RAGWB_DATA_DIR` pointing at a temporary directory and one warm-up run first.
- A cold `ragwb run --quiet` of the same configuration — process start, imports, opening the store and the run — takes about 3 s on an otherwise idle machine (measured 2.9–3.4 s).
- `pytest` collects 455 tests; 453 pass offline and two opt-in tests are skipped, one live and one with a real model (Part IX).

These are orders of magnitude from one Windows laptop, not a benchmark. On the example data the evaluation itself costs little offline. A cold CLI invocation is dominated by interpreter start-up and imports, which take roughly ten times as long as the run itself. OpenAI runs are dominated by network latency, which the thread pool addresses.

### 58.2 Hot paths and their complexity

| Code | Complexity | Notes |
|---|---|---|
| `BM25Retriever.__init__` (`retrieval.py:45-63`) | O(total tokens) | Term counters, lengths, the inverted index (`_postings`), per-chunk length normalisation and IDF precomputed once per run |
| `BM25Retriever.score` (`retrieval.py:65-79`) | O(sum of the postings lengths of the query terms) | Since release 1.4 only chunks that contain a query term are touched (it was O(N × \|q\|) before, a scan of every chunk); scores are bit-for-bit those of the scan (Part XVI §175) |
| `BM25Retriever.retrieve` (`retrieval.py:81-91`) | O(N log N) | Full sort instead of a heap; fine for tens to thousands of chunks |
| `ExtractiveGenerator.generate` (`providers.py:68-88`) | O(sentences × tokens) | Re-tokenises the retrieved passages on every question; nothing is cached between questions |
| `_lcs_length` (`lexical.py:39-49`) | O(n × m) time, O(m) memory | Rolling row; answers and references are short |
| `bootstrap_ci` (`aggregate.py:23-34`) | O(B × n + B log B), B = 2,000 | Runs once per metric per summary and once per metric per paired comparison |
| `RunStore.add_case_result` | One connection + one transaction per case | Durability is chosen over throughput |
| `RunStore.list_runs` | Parses every run's JSON | Called on each rerun of several pages |

### 58.3 Deliberate performance choices

- **Precomputation in BM25** keeps per-query work to dictionary lookups. The offline generator reuses the retriever's IDF table instead of computing its own (`pipeline.py:158`).
- **Lazy embedding index** defers the embedding API calls to the first query and builds the index once per run (`retrieval.py:146-160`).
- **Bounded submission** (`2 × workers`) caps memory and keeps cancellation responsive (`runner.py:167`, `:177`).
- **Streaming file hashing** reads 64 KiB blocks (`documents.py:33`), so hashing a large document does not load it whole (the parser still loads it).
- **Size limits before reading.** `validate_file` and `load_chunks` check the size on disk before reading the content (`datasets.py:130-134`, `documents.py:47-49`).
- **Dependency weight.** PyMuPDF is pinned below 2.0 (`pyproject.toml:13-15`). PyMuPDF 2.0 loaded `onnxruntime` and layout models at import, which block extraction does not use. With the pin, `uv.lock` lists 117 packages (count the `[[package]]` entries).

### 58.4 Known costs

- **Limitation:** the New evaluation and Datasets pages call `load_chunks` on every rerun (`ui/views/new_run.py:91`, `ui/views/data.py:62`), re-parsing the PDF each time a widget changes; each rerun writes another "Loaded 11 chunks from honeybees.pdf" line to the log. For a 25 MB PDF this would make the page sluggish; `st.cache_data` keyed on path and modification time would remove it.
- **Limitation:** the Retrieval playground rebuilds a `BM25Retriever` for every query (`ui/views/data.py:80`).
- **Limitation:** judge metrics create a new DeepEval model object per measurement (`metrics/judge.py:110-116`, `:89`). This is chosen for thread safety; the overhead is small next to the API call.

## 59. Security-sensitive code

The threat model is a single user on their own machine, who may load files from elsewhere (datasets, documents, run bundles) and who has an OpenAI key worth protecting.

### 59.1 Secret handling

| Measure | Code |
|---|---|
| Key held as `SecretStr`; masked in `repr` | `config.py:64` |
| Key presence exposed as a boolean only | `has_openai_key` (`config.py:144-146`), `public_dict` (`config.py:163-169`) |
| Key never part of a run configuration or bundle | `RunConfig` has no key field (`models.py:114-140`) |
| Key read with `get_secret_value()` only where a client is constructed | `pipeline.py:139`, `:165`; `metrics/__init__.py:46`; `config.py:152-155` |
| Log redaction of the configured key and `sk-…` patterns, in messages and in formatted tracebacks | `logging_setup.py:18-66` |
| Shared bundles carry no absolute local paths | `reporting.py:103-122` |
| Error messages built without request headers; authentication error replaced by a fixed sentence | `errors.py:40`, `:50-51` |
| `.env` git-ignored | `.gitignore` |
| Telemetry disabled (DeepEval, Streamlit) | `__init__.py:11`, `streamlit_app.py:10`, `.streamlit/config.toml:5` |

`scripts/verify.py` additionally scans the project tree for API-key-shaped strings and `.env` files (its step 3).

### 59.2 Untrusted files

| Input | Protection | Code |
|---|---|---|
| Uploaded file names | Suffix allow-list; size limit; name reduced to `[A-Za-z0-9._-]`, length-limited and prefixed with 12 hex characters of the content hash; resolved target must be inside `uploads/` | `services.py:38-60`, `reporting.py:198-201` |
| Upload overwrite | Content-addressed name and `if not target.exists()` — an upload can never replace a different file | `services.py:55`, `:58-59` |
| Datasets | Size, case-count and field-length limits; strict typing; no evaluation of content | `datasets.py:68-204` |
| Documents | Suffix and size limits; PyMuPDF open errors contained | `documents.py:44-49`, `:90-93` |
| Run bundles | 50 MB limit; JSON only (never executed); format/version check; full pydantic validation; duplicate-id check; summary recomputed from cases; atomic import | `archive.py:34-81` |
| Imported config values in HTML | `html.escape` before `unsafe_allow_html` markup | `ui/views/results.py:45-50` |
| Export file names | `safe_filename` on the run id | `reporting.py:198-208` |
| CSV exports | Spreadsheet formula neutralisation | `reporting.py:85-100` |
| Display of document text | `st.text` (literal) | `ui/views/results.py:169`, `ui/views/data.py:87` |
| SQL | Parameterised statements throughout | `storage.py` |
| Destructive actions | UI delete requires typing the run id (`ui/views/results.py:215-216`); CLI delete requires `--yes` (`cli.py:275-277`) | |

### 59.3 Residual risks

- **Mitigated — HTML in the Results header.** The Results header line passes `provider`, `pipeline`, `retriever`, `k`, `generator_model`, `judge_model` and the run id into `st.markdown(..., unsafe_allow_html=True)`. `RunRecord.config` is an untyped dict, so an imported bundle can contain arbitrary strings in those fields. Every value therefore passes through `html.escape` before it enters the markup (`ui/views/results.py:45-50`; `tests/test_ui.py:169`, `test_imported_config_values_are_html_escaped`). The rule for future code is that any new `unsafe_allow_html` call must escape its inputs the same way.
- **Limitation — PDF parsing.** PyMuPDF is native code processing untrusted PDFs. Size limits reduce, but do not remove, the risk of a malicious document.
- **Limitation — no per-user separation below the page level.** By default (no login configured) anyone who can reach the Streamlit port can run evaluations with the configured key, upload files and delete runs. The shipped configuration binds the server to `localhost` (the config comment reads "Local tool without authentication: listen on this machine only", `.streamlit/config.toml:16-17`), so other machines cannot reach it. Other users and processes on the same machine still can. Release 1.1 adds an optional shared password (`RAGWB_APP_PASSWORD`, `ui/auth.py`) that gates the whole app, and `start.py` refuses a non-local `--host` unless one is set (`start.py:112-117`); it is a single shared secret, not user management, and traffic is not encrypted (Part XIII). Release 1.2 adds named accounts with scrypt-hashed passwords and attributable sign-ins (`users.py`, `ui/auth.py`) and HTTPS through `start.py --ssl-cert/--ssl-key` (Part XIV §156); release 1.3 adds three roles (Part XV §165) and release 1.4 an admin Accounts page, self-service password change and an optional run filter (`RAGWB_RUN_VISIBILITY=own`, Part XVI §173). There is still no e-mail password reset, and the run filter is applied in the web pages only: the command line and anyone with file access to `data/` see every run.
- **Limitation — CLI paths are trusted.** `--dataset`, `--document`, `--out-dir` and bundle paths are used as given; this is appropriate for a local command-line tool run by the file owner.

## 60. Important algorithms and their reasoning

### 60.1 Okapi BM25 retrieval

**What.** For query terms *q* and chunk *d*:

```text
score(d, q) = Σ_{t ∈ q}  IDF(t) · tf(t,d)·(k1 + 1) / ( tf(t,d) + k1·(1 − b + b·|d|/avgdl) )
IDF(t)      = ln( 1 + (N − n_t + 0.5) / (n_t + 0.5) )
k1 = 1.5,  b = 0.75
```

**How.** Terms are `content_tokens` — NFKC-normalised, lower-cased `\w+` tokens with English stop words removed and a light plural stemmer applied (`text.py:49-78`). The constructor counts term frequencies per chunk, chunk lengths in content tokens, the average length (guarded against zero) and document frequencies, then computes IDF (`retrieval.py:51-63`). Since release 1.4 the constructor also builds an inverted index, `term -> [(chunk index, term frequency)]`, so a term's document frequency is the length of its postings list. `score` loops over the query terms in order and, for each, over that term's postings only, adding the term's contribution to each chunk's accumulator (`retrieval.py:65-79`); because every chunk still receives its contributions in query order starting from `0.0`, the floating-point sums equal those of the earlier per-chunk scan exactly (Part XVI §175.3). Query terms are not de-duplicated, so a term repeated in the query counts twice. `retrieve` sorts by `(-score, index)` (`retrieval.py:86`), so ties — including the all-zero case of a query with no matching term — fall back to document order, and the result is fully deterministic. Scores are rounded to six decimals for storage.

**Worked example (computed with the code).** For the four test chunks in `tests/conftest.py` and the query "What do forager bees collect?", `content_tokens` yields `['forager', 'bee', 'collect']`. "Forager" and "collect" each occur in one chunk, so each has IDF ln(1 + 3.5/1.5) ≈ 1.204. "Bee" occurs in two chunks, so its IDF is ln 2 ≈ 0.693; "Honeybees" stems to `honeybee`, not `bee`, so the first chunk does not count. The chunk scores are 0.0, 2.7875, 0.7345 and 0.0. The forager chunk `p1-b2` ranks first, and the winter-cluster chunk `p1-b3`, which shares only "bees", ranks second.

**Why.** The non-negative IDF variant (`retrieval.py:41`) keeps terms that occur in more than half the chunks from contributing negative scores — important in a single-topic document where words like "honeybee" are everywhere. The parameters are the standard values cited at `retrieval.py:30-31`. BM25 needs no model, no network and no randomness, which is what an offline, reproducible baseline requires. **Limitation:** it is purely lexical. On the bundled PDF, the question "Which parasite threatens honeybee colonies?" (case a2 of `honeybees_unanswerable.jsonl`) yields the terms `['parasite', 'threaten', 'honeybee', 'colony']`. The document says "parasitic varroa mite" and "threats", which the light stemmer does not map to `parasite` and `threaten`, so only the generic terms match. Length normalisation then ranks the four-word title chunk `p1-b1` first (2.611), ahead of the opening paragraph `p1-b2` (2.313); the paragraph that actually names the varroa mite, `p2-b1`, comes third (1.564). The k = 3 example run shows the same pattern more widely: the title chunk is among the retrieved chunks for 9 of the 20 questions.

### 60.2 Extractive answer selection

**What.** The offline "generator" returns up to `max_sentences` sentences from the retrieved passages, chosen by IDF-weighted overlap with the question, in their original order.

**How** (`providers.py:68-88`):

1. Optional failure injection (Chapter 51).
2. `q_terms` = set of the question's content tokens.
3. Every passage is split into sentences (`text.split_sentences`, which splits after `.`, `!` or `?` when followed by whitespace and an optional quote/bracket and a capital letter or digit, `text.py:33`, `:90-95`). For each sentence, the weight is the sum of IDF values of the *distinct* question terms it contains; terms absent from the corpus IDF table get the maximum IDF ("unseen terms are treated as rare", `providers.py:55`). A running `order` counter records the sentence's position across all passages.
4. Sentences with weight > 0 are sorted by `(-weight, order)` and the top `max_sentences` kept (`providers.py:79`).
5. No positive-weight sentence → the standard abstention answer (`providers.py:80-81`).
6. The chosen sentences are re-sorted by `order` and joined (`providers.py:72`), so the answer reads in document order.

**Worked example (computed with the code).** With the same four chunks, retrieving `k = 2` for "What do forager bees collect?" and selecting two sentences gives: "Forager bees collect nectar, pollen and water. In winter the bees cluster together and shiver to stay warm." The first sentence matches all three terms. The second matches only the lower-IDF "bee", but it still has positive weight, so it fills the second slot.

**Why.** It is a transparent lower bound: an answer built only from retrieved text, so differences between retrieval settings show up in the answer metrics without an LLM in the loop. **Limitations** the example shows directly: any shared term, however common, counts as evidence, so the baseline rarely abstains. In the unanswerable example run it answers all four unanswerable questions (u1–u4) with document sentences instead of the abstention sentence, so exact match is 0 on all six cases. For example, u1 asks "How much honey does a colony produce in a year?" and gets "Honey is made from nectar. …". Its lexical groundedness is 1.0 by construction because every word comes from the context. A title chunk without terminal punctuation counts as one "sentence", which is why the answer to a2 begins "Honeybees: Life Inside the Colony Honeybees are social insects …".

### 60.3 Longest common subsequence (ROUGE-L)

**What.** ROUGE-L F1 = 2PR/(P + R), where P = LCS/|answer| and R = LCS/|reference| over SQuAD-normalised tokens (`lexical.py:52-60`).

**How.** `_lcs_length` (`lexical.py:39-49`) is the classic dynamic programme `L[i][j] = L[i−1][j−1] + 1` if tokens match, else `max(L[i−1][j], L[i][j−1])`, kept as a single previous row plus the current row:

```python
    prev = [0] * (len(b) + 1)
    for x in a:
        curr = [0]
        for j, y in enumerate(b, start=1):
            curr.append(prev[j - 1] + 1 if x == y else max(prev[j], curr[j - 1]))
        prev = curr
```

(`lexical.py:43-48`.) For "forager bees collect nectar and pollen" against "foragers collect nectar pollen and water" the function returns 3, for the common subsequence collect, nectar, pollen; "forager" and "foragers" do not match, because these metrics do not stem (computed with the code).

**Why.** LCS rewards in-order overlap without requiring contiguity, which token F1 ignores. The rolling row reduces memory from O(nm) to O(m); time stays O(nm), acceptable for short answers. Normalisation follows SQuAD v1.1, so the lexical metrics are comparable with common QA practice. It lower-cases after NFKC normalisation, removes ASCII punctuation, removes the articles a/an/the and collapses whitespace (`text.py:81-87`). It extends SQuAD in one respect: every character in a Unicode punctuation category (`P*`) is also replaced by a space. This covers curly quotes, dashes and ellipses, which `string.punctuation` misses (`text.py:84-85`). Without that step, an answer containing "queen’s" or an en dash could fail exact match against an otherwise identical reference. `tests/test_text.py:55` (`test_squad_normalize_drops_unicode_punctuation`) covers it. Unlike `content_tokens`, SQuAD normalisation keeps stop words, "as in the original SQuAD evaluation script" (`text.py:13-14`).

### 60.4 Percentile bootstrap confidence interval

**What.** A 95% interval for the mean of a metric's scored values.

**How** (`aggregate.py:23-34`):

```python
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choices(values, k=n)) / n for _ in range(resamples))
    alpha = (1 - confidence) / 2
    low = means[max(0, math.floor(alpha * resamples))]
    high = means[min(resamples - 1, math.ceil((1 - alpha) * resamples) - 1)]
```

With B = 2,000 resamples and α = 0.025, the bounds are the sorted resample means at indices 50 and 1,949. Fewer than two values give `(None, None)`.

**Why.** The percentile bootstrap makes no normality assumption, which matters because metric scores are bounded in [0, 1] and often pile up at 0 or 1 (every example run has groundedness 1.0 on every case, giving the degenerate interval 1.000–1.000). The fixed seed (12345, `aggregate.py:20`) makes the interval a deterministic function of the scores, so a stored summary can be recomputed exactly (`tests/test_aggregate.py:41`). **Limitation:** the interval covers sampling of questions only; it says nothing about judge-model variability (`ui/views/results.py:89-90`), and with 20 cases it is wide.

### 60.5 Paired comparison

**What.** For one metric, compare candidate run B against baseline run A on the cases both scored.

**How** (`aggregate.py:151-179`):

1. Key every case by its question, lower-cased and whitespace-collapsed (`_case_key`, `:151-152`), ignoring case ids so runs over differently-identified datasets still pair.
2. Keep only cases with a score in each run; intersect the keys (`:169-171`).
3. Differences `d_i = B_i − A_i` (`:170`); mean difference and a bootstrap CI of the differences (same function, same seed) (`:171`).
4. Wins, ties and losses with a tolerance of 1e-9 (`:177-178`).
5. `significant` is true when the CI excludes zero (`:145-148`); the UI turns this into "B better", "B worse" or "inconclusive" (`ui/views/compare.py:101-103`).

**Why.** Pairing removes the between-question variance that dominates unpaired comparisons: two runs over the same 20 questions differ much less from each other than the questions differ in difficulty. The example runs show the effect. `ragwb compare` with k = 1 as A and k = 3 as B gives:

| Metric | Mean A | Mean B | Mean B − A | 95% CI | B better / tied / worse | CI excludes 0 |
|---|---:|---:|---:|---|---|---|
| Token F1 | 0.404 | 0.346 | −0.057 | [−0.116, −0.008] | 3 / 10 / 7 | yes |
| ROUGE-L | 0.373 | 0.317 | −0.056 | [−0.108, −0.010] | 3 / 10 / 7 | yes |
| Context recall | 0.857 | 0.885 | +0.028 | [0.000, 0.062] | 3 / 17 / 0 | no |

More context helps retrieval slightly but measurably *hurts* the extractive answers. With three chunks, the two highest-weighted sentences more often come from a less relevant chunk — often the title chunk — and overlap less with the reference. Comparing k = 3 with k = 5 gives identical token-F1 scores on all 20 cases and a context-recall gain of 0.007, which is inconclusive. Comparing the two runs' separate intervals instead would ignore that the same questions appear in both, and so would be a weaker test. **Limitation:** "significant" is a bootstrap heuristic at 95%, uncorrected for testing several metrics at once.

### 60.6 Retry with exponential back-off and jitter

**What.** Retry transient provider failures with increasing delays.

**How** (`runner.py:234-252`):

```python
                delay = self.settings.retry_base_delay_s * 2 ** (attempt - 1)
                delay += random.uniform(0, self.settings.retry_base_delay_s)  # jitter avoids synchronized retries
```

(`runner.py:244-245`.) Attempt 1 is the first call. After a `TransientProviderError`, if `attempt > max_retries` the case fails with "… (gave up after N attempts)"; otherwise the runner sleeps through the injectable `sleep` and tries again. With the default base of 1 s and `max_retries = 3`, the waits are about 1–2 s, 2–3 s and 4–5 s, for at most four calls. Permanent `ProviderError`s and unexpected exceptions are not retried. `tests/test_runner.py:67` checks two sleeps of 1–2 s and 2–3 s before a third attempt succeeds; `tests/test_runner.py:82` checks that `max_retries = 2` gives up after three attempts.

**Why.** Rate limits and 5xx errors are usually short-lived; exponential growth backs off quickly under sustained pressure, and the jitter — as the inline comment says — keeps parallel workers that failed together from retrying in lock-step. Classifying errors first (Chapter 46) keeps the back-off from being wasted on failures that cannot succeed, such as a rejected key. **Limitation:** the delay has no upper cap other than the bounded `max_retries` (≤ 10) and base delay (≤ 60 s), so extreme settings could produce very long waits, and the sleep is not interruptible by cancellation.
