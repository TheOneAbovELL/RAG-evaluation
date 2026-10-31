# Part IX — Reference cards

Keep this Part open next to your terminal. It holds nine cards: every command, every environment variable, every metric, the file
formats, a glossary, six printable checklists, a "which command do I need?" table, and one complete worked example with its real
output. Everything was checked against `ragwb <command> --help`, `src/rag_workbench/config.py`, `.env.example` and `ragwb metrics`
for version 1.4.1.

**Conventions.** `ragwb` means `uv run ragwb` or `.venv\Scripts\python.exe -m rag_workbench`. `RUN_ID` is the id printed by `run` and
`list`; it can also be a unique id prefix, the last 6 characters of the id, or an exact run name (at least 4 characters, matching exactly one run). Square brackets mean optional. All commands print errors as `error: ...` on stderr, without a traceback, for expected problems.

---

## 9.1 CLI command cards

`ragwb --help` lists 24 sub-commands. `ragwb --version` prints `ragwb 1.4.1` and exits 0. Run `ragwb COMMAND --help` for the argument
listing. The cards below follow the order of the table in §9.7.

### 9.1.1 Quick index

| Command | One-line purpose |
|---|---|
| `run` | run and store an evaluation |
| `list` | list stored runs, optionally filtered |
| `show` | configuration and summary of one run |
| `compare` | paired comparison of run B against run A |
| `regress` | regression gate: exit code reflects a significant drop |
| `slices` | scores per value of a dataset metadata field |
| `export` | write a CSV, JSON bundle or Markdown report |
| `import` | read run bundles written by `export --format json` |
| `validate` | validate a dataset file |
| `score` | score one answer, store nothing |
| `metrics` | print the metric catalogue |
| `rerun` | repeat a stored run from its recorded configuration |
| `tag` / `note` | label runs and attach a note |
| `delete` | delete one run |
| `prune` | delete runs by retention policy |
| `labels-template` | write a CSV for labelling a run's cases |
| `calibrate` | compare a metric with labels (agreement, kappa) |
| `judge-noise` | re-score answers to measure judge jitter (API calls) |
| `tune-abstention` | choose `--min-evidence` on a development half |
| `doctor` | health checks, no network |
| `backup` / `restore` | consistent copy of the run store and its restore |
| `user` | named accounts for the web app |

### 9.1.2 `run`

```
ragwb run [--name NAME] [--dataset DATASET] [--document DOCUMENT] [--provider {offline,openai}]
          [--pipeline {rag,agent}] [--retriever {bm25,embedding,hybrid,local,hybrid-local}] [-k K]
          [--metrics METRICS] [--threshold METRIC=VALUE] [--model MODEL] [--judge-model JUDGE_MODEL]
          [--workers WORKERS] [--limit LIMIT] [--answer-sentences N] [--inject-failures F]
          [--min-evidence X] [--skip-headings] [--seed SEED] [--notes NOTES] [--quiet]
```

**Purpose.** Run an evaluation of a dataset against a document and store the result.

| Option | Default | Meaning |
|---|---|---|
| `--name` | `cli-run` | human-readable run name (becomes part of the run id) |
| `--dataset` | `examples/datasets/honeybees.jsonl` | dataset `.jsonl` or `.csv` |
| `--document` | `examples/documents/honeybees.pdf` | source `.pdf`, `.txt` or `.md` |
| `--provider` | `offline` | `offline` (extractive baseline) or `openai` (any OpenAI-compatible endpoint) |
| `--pipeline` | `rag` | `rag` retrieve then generate; `agent` tool-calling model (needs provider `openai`) |
| `--retriever` | `bm25` | `bm25`; `embedding`/`hybrid` need an embeddings API; `local`/`hybrid-local` need `fastembed` and a one-time model download |
| `-k` | 3 | chunks retrieved per query, 1 to 50 |
| `--metrics` | offline: `token_f1,rouge_l,context_recall,groundedness`; with provider `openai` the four judge metrics are added | comma-separated names from §9.3 |
| `--threshold METRIC=VALUE` | per-metric default | override a pass threshold, 0 to 1; repeatable |
| `--model` | `gpt-4o` (`RAGWB_GENERATOR_MODEL`) | generator model (provider `openai`) |
| `--judge-model` | `gpt-4o` (`RAGWB_JUDGE_MODEL`) | DeepEval judge model |
| `--workers` | `RAGWB_MAX_WORKERS` (4) | parallel cases |
| `--limit` | all | evaluate only the **first** N cases, N at least 1 |
| `--answer-sentences` | 2 | offline generator: sentences per answer |
| `--inject-failures` | 0 | offline: fraction of cases that fail on purpose (for testing) |
| `--min-evidence` | 0 | offline: abstain unless the answer covers this share (0 to 1) of the question's terms |
| `--skip-headings` | off | drop heading-like blocks from the chunks |
| `--seed` | 0 | seed for offline failure injection |
| `--notes` | none | note stored with the run |
| `--quiet` | off | suppress progress output |

**Exit codes.** 0 completed; 2 partial or failed; 1 configuration or input error; Ctrl+C stops it (stored `cancelled`, Python's interrupt exit).

**Typical use.** `ragwb run --name bees-k3 -k 3 --quiet`.

### 9.1.3 `list`

```
ragwb list [--search WORD [WORD ...]] [--tag TAG] [--status STATUS]
```

Lists stored runs, newest first, with a header line. Every `--search` word must appear in the run's id, name, notes, tags, status,
provider, retriever or file names. `--status` is one of `running`, `completed`, `partial`, `failed`, `cancelled`, `interrupted`, `imported`.
**Exit:** 0.

### 9.1.4 `show`

```
ragwb show RUN_ID
```

Prints the run's configuration (provider, pipeline, retriever, k, models, dataset and document paths), its `tags:` and `notes:` lines when it has them, and its summary table.
**Exit:** 0; 1 unknown id.

### 9.1.5 `compare`

```
ragwb compare RUN_A RUN_B
```

Paired comparison of B against A per shared metric: paired cases, means, difference (B minus A), a bootstrap interval of the difference,
and counts of questions where B is better, tied or worse; `ci_excludes_zero` is the claim to make. **Exit:** 0; 1 no shared metric or
unknown id.

### 9.1.6 `regress`

```
ragwb regress BASELINE CANDIDATE [--max-drop 0.02] [--min-pairs 10] [--max-error-increase 0.05] [--metrics a,b]
```

| Option | Default | Meaning |
|---|---:|---|
| `--max-drop` | 0.02 | largest tolerated drop in a metric mean |
| `--min-pairs` | 10 | paired questions needed to judge a metric |
| `--max-error-increase` | 0.05 | largest tolerated rise in the share of failed cases |
| `--metrics` | all shared | comma-separated metrics to gate |

Verdicts per metric: `ok`, `improved`, `regression`, `possible`, `insufficient`. A `--metrics` name that is not in both runs is an error (`Metric(s) not present in both runs: X. Shared metrics: ...`, exit 1). **Exit:** 0 ok; 3 regression; 4 not judged; 1 error.

### 9.1.7 `slices`

```
ragwb slices RUN_ID --by FIELD
```

Mean score per value of a dataset **metadata** field (for example `type`, `difficulty`, `topic`), with the scored count in brackets.
**Exit:** 0; 1 unknown field (the message lists the available ones).

### 9.1.8 `export`

```
ragwb export RUN_ID [--format {csv,json,md}] [--out-dir OUT_DIR]
```

Writes `<RUN_ID>.<ext>` and prints `Wrote <path>`. `json` is a re-importable bundle. CSV starts with a UTF-8 byte-order mark and neutralises
formula cells. **Exit:** 0.

### 9.1.9 `import`

```
ragwb import BUNDLE [BUNDLE ...]
```

Imports bundles; a run id already present is skipped (`... already present, skipped`, exit 0). Bundles are validated, summaries are
recomputed. **Exit:** 0; 1 invalid bundle.

### 9.1.10 `validate`

```
ragwb validate DATASET
```

Prints `NAME: N cases, M with reference answers`, then errors (`ERROR line N: ...`) and warnings, then `valid` or `INVALID`. **Exit:** 0 valid;
1 invalid.

### 9.1.11 `score`

```
ragwb score --question Q --answer A [--expected REF] [--context PASSAGE ...] [--metrics a,b] [--judge-model M]
```

Scores one answer and stores nothing. `--context` is repeatable. Metrics needing a reference or context are skipped if absent;
judge metrics need a key. **Exit:** 0; 1 error.

### 9.1.12 `metrics`

```
ragwb metrics
```

Prints the catalogue of §9.3. **Exit:** 0.

### 9.1.13 `rerun`

```
ragwb rerun RUN_ID [--name NAME] [--quiet]
```

Repeats a stored run from its recorded configuration, as a new run named `<old name>-rerun` unless `--name` is given. It reads the files at
the recorded paths *now*. **Exit:** as `run`.

### 9.1.14 `tag` and `note`

```
ragwb tag RUN_ID [--add a,b] [--remove c]
ragwb note RUN_ID TEXT
ragwb note RUN_ID --clear
```

Tags are short labels (`ragwb list --tag baseline`); invalid tags give exit 1. A note is free text; give the text **or** `--clear`, not both.
**Exit:** 0; 1 error.

### 9.1.15 `delete`

```
ragwb delete RUN_ID --yes
```

Permanent. Without `--yes` it prints `Refusing to delete without --yes` and exits 1; an unknown id exits 1. **Exit:** 0 deleted.

### 9.1.16 `prune`

```
ragwb prune [--keep-last N] [--older-than-days D] [--yes]
```

Without `--yes` it lists the runs it would delete (a dry run). A policy is required. With both options a run must satisfy both. Fresh
`running` runs are never selected. A run tagged `keep` is never pruned (the output says `N run(s) tagged 'keep' are never pruned.`); any other tag, including `baseline`, does not protect a run. **Exit:** 0; 1 no policy.

### 9.1.17 `labels-template`

```
ragwb labels-template RUN_ID --out F.csv [--force]
```

Writes a CSV with one row per case: `case_id, question, expected_answer, answer`, one `<metric>_score` column per metric, a blank
`human_pass` column and a `note` column. Refuses to overwrite without `--force`. **Exit:** 0; 1 file exists.

### 9.1.18 `calibrate`

```
ragwb calibrate RUN_ID --labels F --metric M [--sweep] [--rescore]
```

Compares a metric's pass/fail with labels: a 2-by-2 table, agreement, Cohen's kappa, precision, recall and pass rates. `--sweep` also
shows agreement at thresholds 0.10 to 0.95; `--rescore` computes an offline or local-model metric the run did not have, from stored
answers, with no API calls. **Exit:** 0; 1 nothing comparable.

### 9.1.19 `judge-noise`

```
ragwb judge-noise RUN_ID [--repeats 3] [--metrics a,b] [--limit N] [--yes]
```

Re-scores stored answers several times to measure jitter. **Makes API calls**; `--yes` is required above 30 measurements. `--repeats` is
2 or more. **Exit:** 0; 1 error.

### 9.1.20 `tune-abstention`

```
ragwb tune-abstention [--dataset F [F ...]] [--document F [F ...]]
```

Chooses `--min-evidence` on a development half and reports on a held-out half. Default: the bundled examples with unanswerable rows
(51 development and 45 test questions). Documents are given in the same order as datasets. **Exit:** 0.

### 9.1.21 `doctor`

```
ragwb doctor
```

Nine checks: python, packages, data directory, disk space, run store, default data, OpenAI key, telemetry, network exposure. No network
calls. **Exit:** 0 all ok (warnings allowed); 1 a check failed.

### 9.1.22 `backup` and `restore`

```
ragwb backup [--out-dir OUT_DIR]
ragwb restore BACKUP [--yes] [--force]
```

`backup` writes a verified consistent copy to `<data dir>/backups` (or `--out-dir`) and prints its size. `restore` needs `--yes`, writes a
`pre-restore-*` safety copy first, and refuses a corrupt backup, a newer schema, or a recently active run (override: `--force`).
**Exit:** 0; 1 refused or error.

### 9.1.23 `user`

```
ragwb user {add,remove,set-role,set-password,list} [NAME] [--role {viewer,editor,admin}] [--replace]
           [--password-stdin] [--force]
```

| Action | Use | Notes |
|---|---|---|
| `add NAME` | create an account | `--role` default editor; `--replace` changes an existing user's password; password 10 to 200 characters |
| `set-role NAME --role R` | change role | applies on the next page load |
| `set-password NAME` | change password | prompts twice, or `--password-stdin` |
| `remove NAME` | delete account | the last admin needs `--force` |
| `list` | list accounts and roles | prints `No user accounts ...` when none |

**Exit:** 0; 1 error or unknown user.

### 9.1.24 Exit codes at a glance

| Code | Where | Meaning |
|---:|---|---|
| 0 | all | success (for `regress`: no significant regression; for `doctor`: no failed check) |
| 1 | all | error: bad input, unknown run, refused action, invalid dataset, failed check |
| 2 | `run`, `rerun` | the run ended `partial` or `failed` |
| 3 | `regress` | regression detected |
| 4 | `regress` | not judged: nothing could be verified |
| other | `run` | Ctrl+C: Python's interrupt exit; the run is stored `cancelled` |

---

## 9.2 Environment variable card

Variables are read from the process environment and, unless `RAGWB_NO_DOTENV=1`, from `.env` in the project root (the process environment wins).
Blank values count as unset. Invalid values stop every command with `error: Invalid configuration: NAME: ...`.

### 9.2.1 Provider and models

| Variable | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | unset | key for the `openai` provider, embedding retrievers and judge metrics; unset means offline only. Held as a secret, never logged |
| `OPENAI_BASE_URL` | unset | another OpenAI-compatible endpoint (a provider's API URL) |
| `RAGWB_GENERATOR_MODEL` | `gpt-4o` | answer-generation model |
| `RAGWB_EMBEDDING_MODEL` | `text-embedding-3-large` | embeddings model for `embedding` and `hybrid` |
| `RAGWB_JUDGE_MODEL` | `gpt-4o` | judge model for the four judge metrics |
| `RAGWB_LOCAL_EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | local model for `local`, `hybrid-local` and the semantic metrics |

### 9.2.2 Reliability, pacing and cost

| Variable | Default | Range | Meaning |
|---|---|---|---|
| `RAGWB_REQUEST_TIMEOUT_S` | 60 | above 0, at most 600 | per-request timeout |
| `RAGWB_CASE_TIMEOUT_S` | 600 | above 0, at most 3600 | per-case limit; a stuck case is abandoned and recorded as an error |
| `RAGWB_MAX_RETRIES` | 3 | 0 to 10 | retries for transient provider errors (each wait is capped at 60 s and honours `Retry-After`) |
| `RAGWB_RETRY_BASE_DELAY_S` | 1 | 0 to 60 | back-off base delay |
| `RAGWB_MAX_REQUESTS_PER_MINUTE` | unset (no pacing) | above 0, at most 6000 | evenly space operations (an answer or a judge measurement); also applies offline |
| `RAGWB_MAX_WORKERS` | 4 | 1 to 32 | default parallel cases |
| `RAGWB_PRICE_INPUT_PER_MTOK` | unset | at least 0 | USD per million input tokens; unset means cost unknown |
| `RAGWB_PRICE_OUTPUT_PER_MTOK` | unset | at least 0 | USD per million output tokens |

### 9.2.3 Locations and limits

| Variable | Default | Meaning |
|---|---|---|
| `RAGWB_HOME` | the checkout, or the current directory for a wheel install | overrides the project root |
| `RAGWB_DATA_DIR` | `<root>/data` | data directory (`runs.db`, `users.json`, `uploads/`, `exports/`, `logs/`, `backups/`, `models/`); a relative path resolves against the project root |
| `RAGWB_DATASET` | `examples/datasets/honeybees.jsonl` | default dataset |
| `RAGWB_DOCUMENT` | `examples/documents/honeybees.pdf` | default document |
| `RAGWB_MAX_DATASET_BYTES` | 5,000,000 | dataset size ceiling |
| `RAGWB_MAX_DOCUMENT_BYTES` | 25,000,000 | document size ceiling |
| `RAGWB_MAX_CASES` | 5,000 | cases per dataset |
| `RAGWB_MAX_FIELD_CHARS` | 20,000 | characters per question or reference |

### 9.2.4 Logging and access

| Variable | Default | Meaning |
|---|---|---|
| `RAGWB_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL` (case-insensitive) |
| `RAGWB_LOG_FORMAT` | `text` | `text` or `json` (one object per line); secrets redacted in both |
| `RAGWB_APP_PASSWORD` | unset | shared web-app password; required for a non-local host unless accounts exist |
| `RAGWB_RUN_VISIBILITY` | `shared` | `shared` or `own` (with accounts, non-admins see only their runs and ownerless ones) |

### 9.2.5 Switches and variables read by other tools

| Variable | Read by | Meaning |
|---|---|---|
| `RAGWB_NO_DOTENV` | settings loader, `start.py` | `1` ignores `.env` entirely, including `start.py`'s check for a configured password (the test suite sets it) |
| `DEEPEVAL_TELEMETRY_OPT_OUT` | DeepEval | set to `1` when the package is imported |
| `DEEPEVAL_DISABLE_DOTENV` | DeepEval | set to `1` by default when the package is imported, so DeepEval does not load dotenv files itself; `0` restores its behaviour |
| `UV_HTTP_TIMEOUT` | `uv`, via `start.py` | `start.py` raises it to 180 s unless set |
| `HF_HUB_OFFLINE` | the model hub client | `1` forbids any hub contact once the model is cached |
| `PYTHONIOENCODING` | Python | set to `utf-8` for your own scripts printing non-ASCII on Windows |

---

## 9.3 Metric catalogue

Output of `ragwb metrics`, arranged as a table. "Needs" lists what must exist for the metric to be scored; otherwise it is **skipped**
(never zero).

| Metric | Family | Default threshold | Needs | What it measures |
|---|---|---:|---|---|
| `exact_match` | lexical | 1.0 | reference | normalised answer string equals the reference |
| `token_f1` | lexical | 0.5 | reference | SQuAD token-overlap F1 between answer and reference |
| `rouge_l` | lexical | 0.5 | reference | longest-common-subsequence F1 between answer and reference |
| `context_recall` | lexical | 0.7 | reference, context | share of reference terms present in the retrieved context |
| `groundedness` | lexical | 0.7 | context | share of answer terms present in the retrieved context |
| `semantic_similarity` | semantic | 0.7 | reference, `fastembed` | embedding cosine similarity between answer and reference |
| `semantic_context_recall` | semantic | 0.7 | reference, context, `fastembed` | best embedding similarity between the reference and any retrieved chunk |
| `answer_relevancy` | llm_judge | 0.7 | OpenAI key | share of answer statements the judge considers relevant to the question (DeepEval) |
| `faithfulness` | llm_judge | 0.7 | context, OpenAI key | share of answer claims supported by the retrieved context (DeepEval) |
| `context_relevancy` | llm_judge | 0.7 | context, OpenAI key | share of retrieved statements relevant to the question (DeepEval) |
| `correctness` | llm_judge | 0.7 | reference, OpenAI key | rubric (GEval) score of factual agreement with the reference |

Default sets: offline `token_f1, rouge_l, context_recall, groundedness`; judge set (with a key) the four `llm_judge` metrics. Cost:
lexical and semantic metrics have no API cost; judge metrics do (§7.4 of Part VII). For what each number does and does not mean, read
Part V §5.4.

---

## 9.4 File formats

### 9.4.1 Dataset: JSONL

One JSON object per line; blank lines are ignored.

```json
{"id": "v03", "question": "Why does rock melt above a subduction zone?", "expected_answer": "The sinking plate gives off water, and that water helps the rock above it to melt.", "metadata": {"type": "why", "difficulty": "medium", "topic": "plate boundaries"}}
```

| Field | Required | Rule |
|---|---|---|
| `question` | yes | non-empty string, at most 20,000 characters (`RAGWB_MAX_FIELD_CHARS`) |
| `id` | no | string or integer, unique; absent means `case-001`, `case-002`, ... by position |
| `expected_answer` | no | string; blank means none (reference metrics are skipped for the row) |
| `metadata` | no | JSON object of anything you want to slice by |
| other fields | ignored | a warning `ignored unknown field(s): ...` |

Limits: at most 5,000 cases and 5,000,000 bytes by default.

### 9.4.2 Dataset: CSV

The header must include `question`. The columns `id`, `question` and `expected_answer` are the known fields; **every other
column becomes metadata** for that row when non-empty. (Do not name a plain column `metadata`: that name is reserved for a JSON object.)

```
id,question,expected_answer,topic
p1,What tells other bees how far away the food is?,The length of the waggle run shows the distance to the food.,communication
```

### 9.4.3 Run bundle (JSON)

Written by `ragwb export RUN_ID --format json`; read by `ragwb import`.

```json
{"format": "rag-workbench-run", "version": 1, "run": { RunRecord }, "cases": [ CaseResult, ... ]}
```

`run` has `id`, `name`, `status`, `created_at`, `finished_at`, a `config` object (dataset and document paths, provider, pipeline, retriever,
`k`, `metrics`, `thresholds`, models, ...), hashes, environment and the `summary`. Each case has `case_id`, `position`, `question`,
`expected_answer`, `status`, `metadata`, `answer`, `contexts` (chunk id, text, page, score, rank), `latency_ms`, tokens, `cost_usd`,
`attempts`, `error` and a `metrics` object of per-metric `{status, score, threshold, passed, reason}`. Scores are between 0 and 1 or null.
On import the bundle is validated; duplicate case ids, a wrong `format` or `version`, invalid JSON, and files over 50 MB are rejected, and
summaries are recomputed rather than trusted. Paths in a bundle are relative to the project.

### 9.4.4 CSV export

One row per case. Columns: `position, case_id, status, question, expected_answer, answer, error, latency_ms, prompt_tokens,
completion_tokens, cost_usd, attempts, n_contexts, context_ids`, then for each metric `<metric>`, `<metric>_passed`, `<metric>_status`.
UTF-8 with a byte-order mark. Cells beginning with a formula character are neutralised.

### 9.4.5 Markdown export

A report with the run header (id, status, created, provider/pipeline/retriever, k, models, dataset and document names with short sha256), a
summary line (cases, succeeded, errors, latency, tokens, cost), a table per metric (mean, 95% CI, median, pass rate, threshold, scored, skipped,
errors) and the five lowest-scoring cases per metric with their reasons.

### 9.4.6 Labels

For `ragwb calibrate --labels F`:

* **CSV:** the header must contain `case_id` and `human_pass`. `labels-template` writes the file with a blank `human_pass`. Accepted spellings:
  `pass/fail`, `true/false`, `yes/no`, `1/0` (plus `y`, `t`, `ok`, `correct`, ...). Blank means unlabelled.
* **JSONL:** one object per line, `{"case_id": "v01", "human_pass": "pass"}`.
* Duplicate case ids are rejected; unknown spellings are rejected with the allowed list. The shipped `calibration/volcanoes-labels-by-claude.csv`
  holds **AI-written labels** (written by Claude, not by a person), despite the column name `human_pass`.

### 9.4.7 Users file

`<data dir>/users.json`: `{"version": 1, "users": {"<name>": {"salt": ..., "hash": ..., "role": ..., "created": ...}}}`. Salt and hash are
the scrypt parameters of the password; role is `viewer`, `editor` or `admin`; `created` is an ISO timestamp. Not included in `ragwb backup`.
A malformed file locks the app (see Part VIII §8.9.2).

### 9.4.8 Other stored files

| Path | What |
|---|---|
| `<data dir>/runs.db` | SQLite run store, schema version 3 (tables `runs`, `case_results`) |
| `<data dir>/backups/runs-<timestamp>.db` | `ragwb backup` output |
| `<data dir>/backups/pre-restore-*.db` | safety copies written by `restore` (`pre-restore-damaged-*` for an unreadable live store) |
| `<data dir>/exports/` | exports written from the web app |
| `<data dir>/logs/rag_workbench.log` | rotating log |
| `<data dir>/models/` | downloaded local embedding model |
| `<project>/.env` | settings and the provider key; read only by this project's loader (DeepEval's own dotenv loading is switched off). Ignored by git and Docker, **not** excluded from zips or cloud-sync folders; never back it up elsewhere |

---

## 9.5 Glossary

| Term | Meaning |
|---|---|
| **RAG** | retrieval-augmented generation: retrieve passages from a document, then generate an answer from them |
| **Evaluation run** | one dataset evaluated against one document with one configuration; stored with its configuration and results |
| **Dataset** | the questions, optional reference answers and metadata you evaluate with |
| **Case** | one dataset row and everything recorded for it in a run |
| **Reference answer** | the expected answer written by you; `expected_answer` |
| **Chunk** | a passage of the document the retriever can return; ids look like `p1-b2` (page 1, block 2) |
| **Chunking** | splitting a document into chunks |
| **Retriever** | the component that picks the `k` most relevant chunks for a question |
| **k** | the number of chunks retrieved per question |
| **BM25** | a lexical ranking function that scores chunks by query-term frequency, rarity and chunk length |
| **IDF** | inverse document frequency: rarer terms count more |
| **Stemming** | cutting word endings so plural and singular match; here a light English rule |
| **Stop words** | very common words ignored by content-term measures; the list is English |
| **Embedding** | a vector representing the meaning of text |
| **Cosine similarity** | the angle-based closeness of two embeddings, from -1 to 1 (mostly 0 to 1 for text) |
| **Dense retrieval** | retrieval by embedding similarity |
| **Hybrid retrieval** | BM25 and dense retrieval fused together |
| **RRF** | reciprocal rank fusion: each retriever contributes `1 / (60 + rank)` per chunk and the sums are ranked |
| **Local model** | an embedding model that runs on your machine (`fastembed`) after a one-time download |
| **Generator** | the component that writes the answer; offline it is an extractive baseline |
| **Extractive baseline** | an offline "generator" that copies the best sentences from the context; not a language model |
| **Agent pipeline** | a tool-calling model that decides when to call the search tool |
| **Provider** | where models run: `offline` or an OpenAI-compatible service |
| **Judge (LLM-as-a-judge)** | a model used to score answers; four metrics use one |
| **Judge model** | the model acting as judge (`--judge-model`) |
| **Judge noise** | variation in a judge's score for the same input on repeated calls |
| **Metric** | a scoring function with a name, a family and a pass threshold |
| **Lexical metric** | scores by word overlap |
| **Semantic metric** | scores by embedding similarity |
| **Token F1** | harmonic mean of token precision and recall between answer and reference |
| **Precision / recall** | the share of answer tokens in the reference / the share of reference tokens in the answer |
| **ROUGE-L** | F1 over the longest common subsequence of tokens |
| **Exact match** | 1 if the normalised answer equals the reference, else 0 |
| **Context recall** | how much of the reference is present in what was retrieved |
| **Groundedness** | how much of the answer is present in what was retrieved (lexical) |
| **Faithfulness** | how many of the answer's claims the context supports (judge) |
| **Answer relevancy** | how much of the answer addresses the question (judge) |
| **Context relevancy** | how much of the retrieved text addresses the question (judge) |
| **Correctness** | factual agreement with the reference by a rubric (judge) |
| **Hallucination** | an answer claim not supported by the context or by fact |
| **Abstention** | declining to answer because the document does not contain the answer |
| **Unanswerable question** | a question the document cannot answer; the right response is to abstain |
| **Abstention sentence** | the fixed reference text used for unanswerable questions |
| **`--min-evidence`** | the offline baseline's abstention knob |
| **Threshold** | the score at or above which a case counts as a pass |
| **Pass rate** | the share of scored cases at or above the threshold |
| **Scored / skipped / error** | scored: has a number; skipped: not applicable (never zero); error: failed (never zero) |
| **Partial run** | a run where some cases errored |
| **Interrupted run** | a run whose process died; marked after 15 minutes without progress |
| **Bootstrap** | resampling cases with replacement to see how much a statistic varies |
| **Confidence interval (CI)** | a range from the bootstrap; 95% with 2,000 resamples here |
| **Paired comparison** | comparing two runs question by question, so shared difficulty cancels |
| **Tie** | a question where two runs score identically |
| **Regression gate** | a check that fails when a candidate is significantly worse than a baseline |
| **Baseline** | the reference run you compare new runs against; tag it |
| **Slice** | the subset of cases sharing a metadata value |
| **Metadata** | extra fields on a dataset row used for slicing |
| **Calibration** | comparing a metric's verdicts with labels to learn how far to trust it |
| **Agreement** | share of cases where metric and label give the same verdict |
| **Cohen's kappa** | agreement corrected for chance; 0 chance, 1 perfect |
| **Threshold sweep** | agreement at each candidate threshold |
| **AI-written labels** | labels written by an AI model, not a person; weaker evidence than human labels |
| **Run bundle** | a JSON file holding one run and all its cases |
| **Run store** | the SQLite file `runs.db` |
| **Schema version** | the store's format number; migrations add columns |
| **Safety copy** | the `pre-restore-*` file a restore writes first |
| **Visibility** | whether users see all runs (`shared`) or their own (`own`) |
| **Role** | viewer, editor or admin |
| **Pacing** | evenly spacing requests to stay under a provider quota |
| **Quota** | a provider's limit on requests or tokens per minute or day |
| **Retry-After** | the provider header saying how long to wait before retrying |
| **Heartbeat** | the timestamp of the last committed case, used to detect dead runs |
| **Data directory** | where the tool keeps its files (`RAGWB_DATA_DIR`) |

---

## 9.6 Six printable checklists

Copy these into your own notes or print them.

### 9.6.1 Before a run

- [ ] The document is the version you intend; its text extracts (open a case and read the contexts).
- [ ] `ragwb validate DATASET` says `valid` and the reference-answer count is what you expect.
- [ ] Questions include a few the document cannot answer, marked in metadata.
- [ ] The configuration is written down: provider, retriever, `k`, metrics, models.
- [ ] Metrics chosen on purpose; judge metrics only where you accept cost and noise.
- [ ] For a paid provider: an offline pass first, a 2-to-3-case smoke test, pacing set, workers 1 or 2.
- [ ] `RAGWB_DATA_DIR` is where you think it is; `ragwb doctor` is clean.
- [ ] The run has a name you can search for.

### 9.6.2 Before you trust a result

- [ ] Status is `completed`, or you know exactly what `partial` lost.
- [ ] You read **scored / skipped / error** counts before any mean.
- [ ] You looked at the five lowest cases for each metric and read their reasons.
- [ ] You know what each metric does not measure (groundedness 1.000 offline is by construction).
- [ ] Differences carry an interval, and you did not claim one where it includes zero.
- [ ] The sample size is stated, and slices with a handful of cases are not over-read.
- [ ] A judge metric has a noise estimate or a label comparison, or you say it has not.
- [ ] Reruns on the same files reproduce the offline numbers.

### 9.6.3 Before sharing a report

- [ ] The report names the dataset, document (with hashes), provider, models, `k`, date and tool version.
- [ ] It states what was and was not measured; AI-written labels are called AI-written.
- [ ] No keys, passwords, private documents or personal data are in the export, notes or file names.
- [ ] Skipped and error counts appear next to every mean.
- [ ] Limits are stated as findings ("20 questions", "one document"), not buried.
- [ ] Anyone reading can reproduce it: the bundle or the commands are attached.

### 9.6.4 Before upgrading

- [ ] `ragwb backup` done and the file kept; `users.json` copied.
- [ ] A restore was rehearsed on a copy.
- [ ] The app and any scheduled job are stopped.
- [ ] You read `CHANGELOG.md` for the new version.
- [ ] After the upgrade `ragwb --version`, `ragwb doctor` (schema v3, integrity ok) and one small offline run pass.
- [ ] Your rollback is clear: old code plus `ragwb restore` of the backup.

### 9.6.5 Before exposing the app

- [ ] Named accounts exist; one or two admins; no shared password in use.
- [ ] TLS is on (`--ssl-cert/--ssl-key` or a proxy); the port is not on the public internet.
- [ ] `RAGWB_RUN_VISIBILITY=own` if users should not see each other's runs; scheduled CLI jobs use a different data directory.
- [ ] The data directory is on an encrypted disk with owner-only permissions and outside any sync folder.
- [ ] The API key is in the service environment, and `.env` is not synced, zipped or backed up elsewhere (it is excluded from git and Docker, not from zips or sync clients). A key that was ever exposed has been rotated at the provider and replaced with `scripts/set_api_key.py`.
- [ ] Backups run and a restore has been tried.
- [ ] You told users what is sent to a provider and that the CLI ignores roles.
- [ ] You read `docs/SECURITY.md` and `docs/KNOWN_LIMITATIONS.md`.

### 9.6.6 Release checklist

From `docs/OPERATIONS.md` §9, for people who change the code:

- [ ] `uv run python scripts/verify.py --audit` passes (environment, lockfile, secrets, lint, types, tests with coverage, end-to-end CLI,
  dependency audit).
- [ ] `uv run python scripts/wheel_check.py` passes (clean install of the wheel).
- [ ] `scripts/benchmark.py` re-run if performance-relevant code changed.
- [ ] The project book is rebuilt (`docs/project-book/tools/build_book.py`).
- [ ] `docs/KNOWN_LIMITATIONS.md` read so the limits you ship are the limits you state.
- [ ] The version and `CHANGELOG.md` agree; no key-shaped string anywhere except an ignored `.env`.

---

## 9.7 Which command do I need?

| I want to... | Use | Notes |
|---|---|---|
| check my dataset before running | `ragwb validate FILE` | exit 1 if invalid |
| run an evaluation | `ragwb run ...` | exit 2 on partial or failed |
| try one answer quickly | `ragwb score --question ... --answer ...` | stores nothing |
| see what runs exist | `ragwb list [--tag T] [--status S] [--search W]` | newest first |
| read one run | `ragwb show RUN_ID` | configuration and summary |
| know if B really beat A | `ragwb compare A B` | paired; look at `ci_excludes_zero` |
| gate a change in CI | `ragwb regress BASE CAND` | exit 0 / 3 / 4 / 1 |
| find where quality is low | `ragwb slices RUN --by FIELD` | needs dataset metadata |
| share or archive a result | `ragwb export RUN --format md|csv|json` | json is re-importable |
| load someone else's result | `ragwb import FILE.json` | validated, recomputed |
| repeat an old run | `ragwb rerun RUN_ID` | uses current file contents |
| label a run | `ragwb tag` / `ragwb note` | `baseline` is a good tag |
| decide if a metric deserves trust | `ragwb labels-template`, fill, `ragwb calibrate` | needs labels; 30+ cases |
| measure judge jitter | `ragwb judge-noise RUN` | API calls |
| tune abstention offline | `ragwb tune-abstention` | bundled data by default |
| check the installation | `ragwb doctor` | exit 1 on a failed check |
| protect my data | `ragwb backup`, copy `users.json` | online-safe |
| undo or recover | `ragwb restore FILE --yes` | stop the app first |
| free disk / clean up | `ragwb prune --keep-last N` | dry run first; tag baselines `keep`; export them |
| delete one run | `ragwb delete RUN --yes` | permanent |
| give a colleague a login | `ragwb user add NAME --role R` | min 10 character password |
| replace or remove the provider key in `.env` | `python scripts/set_api_key.py` | hidden prompt; `--stdin`, `--remove`, `--check`; rotate at the provider first (Part VII §7.1.12) |
| see all metrics | `ragwb metrics` | with thresholds and needs |
| print the version | `ragwb --version` | `ragwb 1.4.1` |

---

## 9.8 A worked end-to-end example (honeybees, offline)

This is the complete session behind most of this guide, run with `RAGWB_NO_DOTENV=1`, an empty `OPENAI_API_KEY` and a scratch data
directory. Output is real and complete except that long file paths are shortened with `...`. Nothing here needs a key or a network.

### 9.8.1 Validate the dataset

```
$ ragwb validate examples/datasets/honeybees.jsonl
honeybees.jsonl: 20 cases, 20 with reference answers
valid
```

### 9.8.2 Run at k = 1, 3 and 5

```
$ ragwb run --name bees-k1 -k 1 --quiet

Run 20261030-205006-bees-k1-1ebcf6: completed
cases 20  ok 20  errors 0  mean latency 0.4 ms
metric                          mean           95% CI    pass  scored  skip  err
Token F1                       0.404      0.335-0.476     20%      20     0    0
ROUGE-L                        0.373      0.301-0.450     20%      20     0    0
Context recall (lexical)       0.857      0.798-0.912     90%      20     0    0
Groundedness (lexical)         1.000      1.000-1.000    100%      20     0    0
```

```
$ ragwb run --name bees-k3 -k 3 --quiet

Run 20261030-205009-bees-k3-1bf34f: completed
cases 20  ok 20  errors 0  mean latency 0.4 ms
metric                          mean           95% CI    pass  scored  skip  err
Token F1                       0.346      0.285-0.419      5%      20     0    0
ROUGE-L                        0.317      0.252-0.393      5%      20     0    0
Context recall (lexical)       0.885      0.839-0.930     95%      20     0    0
Groundedness (lexical)         1.000      1.000-1.000    100%      20     0    0
```

```
$ ragwb run --name bees-k5 -k 5 --quiet

Run 20261030-205011-bees-k5-4a9335: completed
cases 20  ok 20  errors 0  mean latency 0.7 ms
metric                          mean           95% CI    pass  scored  skip  err
Token F1                       0.346      0.285-0.419      5%      20     0    0
ROUGE-L                        0.317      0.252-0.393      5%      20     0    0
Context recall (lexical)       0.892      0.846-0.937     95%      20     0    0
Groundedness (lexical)         1.000      1.000-1.000    100%      20     0    0
```

Run ids contain the UTC timestamp, the run name and a short random suffix, so your ids will differ; substitute your own below.

```
$ ragwb list
                        run_id    name    status provider pipeline retriever  k  n_cases  n_errors tags
20261030-205011-bees-k5-4a9335 bees-k5 completed  offline      rag      bm25  5       20         0
20261030-205009-bees-k3-1bf34f bees-k3 completed  offline      rag      bm25  3       20         0
20261030-205006-bees-k1-1ebcf6 bees-k1 completed  offline      rag      bm25  1       20         0
```

### 9.8.3 Compare

```
$ ragwb compare 20261030-205006-bees-k1-1ebcf6 20261030-205009-bees-k3-1bf34f
A = bees-k1 [20261030-205006-bees-k1-1ebcf6]
B = bees-k3 [20261030-205009-bees-k3-1bf34f]

                   label  paired_cases  mean_a  mean_b  diff_b_minus_a  ci_low  ci_high  b_better  ties  b_worse  ci_excludes_zero
                Token F1            20   0.404   0.346          -0.057  -0.116   -0.008         3    10        7              True
                 ROUGE-L            20   0.373   0.317          -0.056  -0.108   -0.010         3    10        7              True
Context recall (lexical)            20   0.857   0.885           0.028   0.000    0.062         3    17        0             False
  Groundedness (lexical)            20   1.000   1.000           0.000   0.000    0.000         0    20        0             False
```

```
$ ragwb compare 20261030-205009-bees-k3-1bf34f 20261030-205011-bees-k5-4a9335
A = bees-k3 [20261030-205009-bees-k3-1bf34f]
B = bees-k5 [20261030-205011-bees-k5-4a9335]

                   label  paired_cases  mean_a  mean_b  diff_b_minus_a  ci_low  ci_high  b_better  ties  b_worse  ci_excludes_zero
                Token F1            20   0.346   0.346           0.000   0.000    0.000         0    20        0             False
                 ROUGE-L            20   0.317   0.317           0.000   0.000    0.000         0    20        0             False
Context recall (lexical)            20   0.885   0.892           0.007   0.000    0.021         1    19        0             False
  Groundedness (lexical)            20   1.000   1.000           0.000   0.000    0.000         0    20        0             False
```

Reading: k = 3 versus k = 1 lowers token F1 by 0.057 (the interval excludes zero) and raises context recall by 0.028 (it does not).
k = 5 changes nothing detectable over k = 3.

### 9.8.4 Slices

The honeybee set has no metadata, and the tool says so:

```
$ ragwb slices 20261030-205009-bees-k3-1bf34f --by type
error: No case in this run has metadata field 'type'. Available: (none; add a metadata object to dataset rows)
[exit 1]
```

The paraphrased honeybee set (a CSV with a `topic` column, which becomes metadata) can be sliced:

```
$ ragwb run --name paraphrased --dataset examples/datasets/honeybees_paraphrased.csv --quiet

Run 20261030-205044-paraphrased-673e3d: completed
cases 5  ok 5  errors 0  mean latency 0.6 ms
metric                          mean           95% CI    pass  scored  skip  err
Token F1                       0.225      0.109-0.360      0%       5     0    0
ROUGE-L                        0.203      0.081-0.353      0%       5     0    0
Context recall (lexical)       0.664      0.533-0.792     20%       5     0    0
Groundedness (lexical)         1.000      1.000-1.000    100%       5     0    0

$ ragwb slices 20261030-205044-paraphrased-673e3d --by topic
paraphrased [20261030-205044-paraphrased-673e3d] by topic
slice                    cases   ok            Token F1             ROUGE-L  Context recall (le  Groundedness (lexi
communication                1    1     0.222       (1)     0.148       (1)     0.667       (1)     1.000       (1)
honey                        1    1     0.062       (1)     0.062       (1)     0.667       (1)     1.000       (1)
pollination                  1    1     0.480       (1)     0.480       (1)     0.875       (1)     1.000       (1)
reproduction                 1    1     0.098       (1)     0.066       (1)     0.444       (1)     1.000       (1)
workers                      1    1     0.261       (1)     0.261       (1)     0.667       (1)     1.000       (1)
(n scored in brackets; small slices have wide uncertainty)
```

With one case per slice these numbers are anecdotes; the tool's own footnote says so. Note also that on the paraphrased questions context
recall (0.664) is clearly below the original set (0.885): BM25 needs shared words.

### 9.8.5 Tag the baseline and gate a change

```
$ ragwb tag 20261030-205009-bees-k3-1bf34f --add baseline,keep,bees
20261030-205009-bees-k3-1bf34f: tags = baseline, keep, bees

$ ragwb note 20261030-205009-bees-k3-1bf34f k=3 reference run
20261030-205009-bees-k3-1bf34f: note saved
```

Candidate k = 1 against baseline k = 3 (the "change" is going back to k = 1; here it improves token F1):

```
$ ragwb regress 20261030-205009-bees-k3-1bf34f 20261030-205006-bees-k1-1ebcf6
baseline  = bees-k3 [20261030-205009-bees-k3-1bf34f]
candidate = bees-k1 [20261030-205006-bees-k1-1ebcf6]

metric                verdict        pairs  baseline  candidate     diff  95% CI of diff
token_f1              improved          20     0.346      0.404   +0.057  [+0.008, +0.116]
rouge_l               improved          20     0.317      0.373   +0.056  [+0.010, +0.108]
context_recall        possible          20     0.885      0.857   -0.028  [-0.062, +0.000]
groundedness          ok                20     1.000      1.000   +0.000  [+0.000, +0.000]
error rate: baseline 0.0%, candidate 0.0%
PASS: no significant regression.
Note: a 'possible' drop is larger than 0.02 but its interval includes zero; gather more questions before trusting either reading.
[exit 0]
```

And the other direction, a real failing gate:

```
$ ragwb regress 20261030-205006-bees-k1-1ebcf6 20261030-205009-bees-k3-1bf34f
baseline  = bees-k1 [20261030-205006-bees-k1-1ebcf6]
candidate = bees-k3 [20261030-205009-bees-k3-1bf34f]

metric                verdict        pairs  baseline  candidate     diff  95% CI of diff
token_f1              regression        20     0.404      0.346   -0.057  [-0.116, -0.008]
rouge_l               regression        20     0.373      0.317   -0.056  [-0.108, -0.010]
context_recall        ok                20     0.857      0.885   +0.028  [+0.000, +0.062]
groundedness          ok                20     1.000      1.000   +0.000  [+0.000, +0.000]
error rate: baseline 0.0%, candidate 0.0%
FAIL: regression detected.
[exit 3]
```

### 9.8.6 Slice a larger set: volcanoes

```
$ ragwb run --name volc --dataset examples/datasets/volcanoes.jsonl --document examples/documents/volcanoes.pdf --quiet

Run 20261030-205058-volc-10badb: completed
cases 30  ok 30  errors 0  mean latency 0.5 ms
metric                          mean           95% CI    pass  scored  skip  err
Token F1                       0.199      0.149-0.252      3%      30     0    0
ROUGE-L                        0.179      0.132-0.230      3%      30     0    0
Context recall (lexical)       0.660      0.539-0.774     44%      25     5    0
Groundedness (lexical)         1.000      1.000-1.000    100%      30     0    0

$ ragwb slices 20261030-205058-volc-10badb --by type
volc [20261030-205058-volc-10badb] by type
slice                    cases   ok            Token F1             ROUGE-L  Context recall (le  Groundedness (lexi
factual                     14   14     0.276      (14)     0.249      (14)     0.746      (14)     1.000      (14)
list                         4    4     0.128       (4)     0.128       (4)     0.686       (4)     1.000       (4)
numeric                      2    2     0.064       (2)     0.064       (2)     0.500       (2)     1.000       (2)
unanswerable                 5    5     0.042       (5)     0.042       (5)         -       (0)     1.000       (5)
why                          5    5     0.251       (5)     0.206       (5)     0.463       (5)     1.000       (5)
(n scored in brackets; small slices have wide uncertainty)
```

Reading: "why" questions retrieve worst (context recall 0.463), which the overall 0.660 hides; the unanswerable slice has no context
recall at all (`-`, zero scored) because those questions have no reference text.

### 9.8.7 Export in all three formats

```
$ ragwb export 20261030-205009-bees-k3-1bf34f --format md --out-dir .../exports
Wrote ...\exports\20261030-205009-bees-k3-1bf34f.md
$ ragwb export 20261030-205009-bees-k3-1bf34f --format csv --out-dir .../exports
Wrote ...\exports\20261030-205009-bees-k3-1bf34f.csv
$ ragwb export 20261030-205009-bees-k3-1bf34f --format json --out-dir .../exports
Wrote ...\exports\20261030-205009-bees-k3-1bf34f.json
```

File sizes were about 3.5 KB (Markdown), 10 KB (CSV) and 66 KB (JSON bundle). The head of the Markdown report:

```
# Evaluation report: bees-k3

* Run id: `20261030-205009-bees-k3-1bf34f`
* Status: **completed**
* Created: 2026-10-30T20:50:09+00:00
* Provider / pipeline / retriever: offline / rag / bm25
* k: 3  ·  generator: offline-extractive  ·  judge: None
* Dataset: `honeybees.jsonl` (sha256 `7eff99c359ac`)
* Document: `honeybees.pdf` (sha256 `7e743ff01203`)

## Summary

Cases: 20 · succeeded: 20 · errors: 0 · mean latency: 0.4 ms · p95: 0.9 ms · tokens in/out: —/— · cost: — USD

| Metric | Mean | 95% CI | Median | Pass rate | Threshold | Scored | Skipped | Errors |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| Token F1 | 0.346 | 0.285–0.419 | 0.338 | 5% | 0.50 | 20 | 0 | 0 |
| ROUGE-L | 0.317 | 0.252–0.393 | 0.296 | 5% | 0.50 | 20 | 0 | 0 |
| Context recall (lexical) | 0.885 | 0.839–0.930 | 0.882 | 95% | 0.70 | 20 | 0 | 0 |
| Groundedness (lexical) | 1.000 | 1.000–1.000 | 1.000 | 100% | 0.70 | 20 | 0 | 0 |

## Lowest Token F1

| Case | Score | Question | Reason |
|---|---:|---|---|
| q14 | 0.151 | Why do bees build hexagonal cells? | precision 0.10, recall 0.36 (4 shared tokens) |
| q01 | 0.167 | How many queens does a typical honeybee colony have? | precision 0.11, recall 0.40 (2 shared tokens) |
| q12 | 0.186 | How is nectar turned into honey? | precision 0.15, recall 0.24 (4 shared tokens) |
```

Importing the JSON bundle back into the same store is safe and harmless:

```
$ ragwb import .../exports/20261030-205009-bees-k3-1bf34f.json
20261030-205009-bees-k3-1bf34f.json: already present, skipped
```

### 9.8.8 Health check and backup

```
$ ragwb doctor
[ok  ] python            3.12.15
[ok  ] packages          9 required packages installed
[ok  ] data directory    ... is writable
[ok  ] disk space        71.8 GB free
[ok  ] run store         schema v3, 5 runs, integrity ok
[ok  ] default data      honeybees.jsonl and honeybees.pdf load
[ok  ] OpenAI key        not set: offline mode only (BM25, extractive baseline, lexical metrics)
[ok  ] telemetry         DeepEval telemetry is disabled
[ok  ] network exposure  the app listens on localhost only

9 ok, 0 warning(s), 0 failure(s)

$ ragwb backup
Backup written and verified: ...\backups\runs-20261030-205134-178225.db (393,216 bytes)
```

And the restore rehearsal, in Part VII §7.2.3.

### 9.8.9 What you now have

Three comparable runs, a tagged and noted baseline, a slice view, a gate you have seen fail and pass, three export formats and a verified
backup. The honest summary of this experiment is: on 20 honeybee questions, going from k = 1 to k = 3 lowered the extractive baseline's
token F1 by about 0.06 (interval excludes zero) and raised context recall by about 0.03 (interval touches zero); k = 5 added nothing; and
none of this says anything about answer *quality*, because the baseline is not a language model.
