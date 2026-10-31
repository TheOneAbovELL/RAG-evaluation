# Part VIII — Troubleshooting and FAQ

This Part is organised by **what you see**, not by what is wrong. Find your symptom, check the likely cause with the command shown,
and apply the fix. Wherever it was possible without a network or a key, the problem was reproduced for this guide and the
**real error text** is quoted. Where it was not possible (a port race, a screen that stays blank, a path-length failure), the
entry says so and relies on the project's own documentation instead, naming it.

The second half (§8.15) is a FAQ of 54 short questions with direct answers.

---

## 8.1 How to use this chapter

Every entry has the same four parts:

| Part | Meaning |
|---|---|
| **Symptom** | what you see, in the words the tool uses |
| **Likely cause** | the usual reason, most likely first |
| **How to confirm** | a command or a place to look that distinguishes the causes |
| **Fix** | what to do, and what *not* to do |

Three habits make most problems smaller before you start:

1. **Read the first line of the error.** Expected problems are printed as `error: ...` on stderr with exit code 1; there is no
   traceback for them. A traceback means something unexpected, and the log has more.
2. **Run `ragwb doctor`.** It checks Python, packages, the data directory and free disk, the run store, the default data, the key,
   telemetry and network exposure in a second and makes no network calls.
3. **Look at the log:** `<data dir>/logs/rag_workbench.log`. It records run starts, retries, throttling, sign-ins and unexpected
   case errors with their tracebacks. Keys and passwords are redacted.

> **Pitfall.** Do not "fix" a problem by pasting your API key into a ticket, a chat or a log to show what you did. A key that has
> been pasted anywhere should be rotated at the provider.
>
> **If a key was exposed:** (1) rotate it in the provider's console (create a new key, revoke the old one: the workbench cannot do
> this); (2) install the new one with `python scripts/set_api_key.py`, which asks for it with hidden input and never prints it
> (`--stdin` for a password manager, `--remove` to go back to offline mode, `--check` to test the new key with one request);
> (3) look for other copies: shell history, backups, and any zip or cloud-sync copy of the project folder, because `.env` is
> ignored by git and Docker but **not** by zips or sync clients (Part VII §7.1.12, §7.7.5).

---

## 8.2 Start-up problems

### 8.2.1 `error: Invalid configuration: ...`

**Symptom.** Every command fails at once with a message naming an environment variable. Real examples:

```
error: Invalid configuration: RAGWB_MAX_RETRIES: Input should be less than or equal to 10
error: Invalid configuration: RAGWB_MAX_REQUESTS_PER_MINUTE: Input should be greater than 0
error: Invalid configuration: RAGWB_RUN_VISIBILITY: Input should be 'shared' or 'own'
error: Invalid configuration: RAGWB_LOG_LEVEL: Value error, unknown log level 'LOUD'
error: Invalid configuration: RAGWB_MAX_DOCUMENT_BYTES: Input should be greater than 0
```

**Likely cause.** A variable (in your shell, a scheduler's environment, or `.env`) holds a value outside its allowed range. Blank
values are treated as unset, so an empty `RAGWB_MAX_RETRIES=` is fine.

**How to confirm.** The variable is named in the message. Print it: `echo $RAGWB_MAX_RETRIES` (PowerShell
`$env:RAGWB_MAX_RETRIES`). Ranges are in Part IX §9.2.

**Fix.** Correct or unset the variable. If you did not set it, a stale value is coming from your shell profile, a scheduled task, or
`.env`. Run with `RAGWB_NO_DOTENV=1` to rule out `.env`.

### 8.2.2 `start.py` refuses to start

**Symptom (exposure).** `[start] refusing to listen on '0.0.0.0' without a login. Set RAGWB_APP_PASSWORD (environment or .env), or
create accounts with `ragwb user add NAME`, first; or use the default localhost.`

**Likely cause.** You passed `--host` with a non-local address and no password or accounts exist. This is the safety net, not a bug.

**Fix.** Create an account (`echo "a-long-password" | ragwb user add alice --role admin --password-stdin`), or set
`RAGWB_APP_PASSWORD`, or drop `--host`. See Part VII §7.1.

**Symptom (TLS).** `[start] --ssl-cert and --ssl-key must be given together`, or `[start] --ssl-cert file not found: nofile.pem`.

**Fix.** Give both options, and check the files exist (the paths are tested before anything starts).

### 8.2.3 No uv, old Python

**Symptom.** `[start] uv is not installed and this Python is 3.x; install uv (https://docs.astral.sh/uv/) or run this file with
Python 3.12 or newer.`

**Likely cause.** Without `uv`, `start.py` falls back to creating a `.venv` with the standard library, which needs Python 3.12+.

**Fix.** Install `uv`, or launch `start.py` with a 3.12+ interpreter. (Reproduced from the source; no environment was built.)

### 8.2.4 `the application could not open its run store`

**Symptom.** `[start] the application could not open its run store:` followed by details.

**Likely cause.** A bad setting, an unwritable data directory, a damaged `runs.db`, or a store from a newer version.

**How to confirm.** `ragwb doctor` prints the real reason on the `data directory` and `run store` lines.

**Fix.** See §8.10 (corrupt store) and §7.2 for the restore procedure.

---

## 8.3 Ports and reachability

**Symptom.** The browser says "connection refused" at `http://localhost:8501`, or `start.py` reports "the app exited during
start-up", or Streamlit logs `Port <n> is not available`.

**Likely causes**, in order:

1. The app is not running (you closed the terminal, or pressed Ctrl+C).
2. It is running on a **different port** than you expect. `start.py` takes the first free port from 8501 (it tries 50), so a second
   instance comes up on 8502. Read the URL it prints.
3. Another process took the chosen port between the launcher's check and Streamlit's start (a race). The project book (Part VIII,
   §88.2) documents this; it was not reproduced for this guide.
4. You are connecting from another machine to an app bound to `localhost`.
5. A firewall blocks the port when you use `--host 0.0.0.0`.

**How to confirm.** Health endpoint: `/_stcore/health` returns `ok` when the server is up. Who holds a port, on Windows:

```powershell
Get-NetTCPConnection -LocalPort 8501 | Select-Object OwningProcess
netstat -ano | findstr :8501
```

**Fix.** Re-run `python start.py` (the race is rare); choose a port with `--port 8600`; use `--host` only together with a login (and
preferably TLS); open the firewall port deliberately. `ragwb doctor` line **network exposure** tells you which address the app is
configured to listen on.

---

## 8.4 `uv sync`, downloads and the network

**Symptom.** `[start] `uv sync` failed; see the messages above (a slow network may need a retry).`, or a package download times out.

**Likely cause.** A slow or filtered network. `start.py` already raises uv's HTTP timeout to 180 seconds unless `UV_HTTP_TIMEOUT` is
set.

**How to confirm.** The messages printed above the failure show which package and what error.

**Fix.**

```bash
UV_HTTP_TIMEOUT=600 python start.py            # PowerShell: $env:UV_HTTP_TIMEOUT = "600"; python start.py
```

Re-locking (`uv lock`) can take minutes on a slow network without being an error.

> **Why this works.** Nothing in the *evaluation* needs the network; only installing packages (and, optionally, a first-time model
> download or a provider call) does. Once the environment exists, `ragwb` runs fully offline.

**Do not** "fix" install trouble by deleting `uv.lock`: the lock pins the audited dependency set.

---

## 8.5 Validation errors

Validation is the cheapest place to catch problems. Always run `ragwb validate FILE` before a run; it exits 0 when valid and 1 when
not, and lists problems with line numbers.

### 8.5.1 Dataset errors (all reproduced)

Input file with a duplicate id, a line that is not JSON, a row with no question and a row with an empty question:

```
broken.jsonl: 1 cases, 1 with reference answers
  ERROR   line 3: invalid JSON (Expecting value at column 1)
  ERROR   line 2: duplicate id 'a1' (first seen on line 1)
  ERROR   line 4: missing or empty 'question'
  ERROR   line 5: missing or empty 'question'
INVALID
```

| Message | Cause | Fix |
|---|---|---|
| `file not found: <path>` | wrong path or working directory | give a full path |
| `dataset contains no cases` | empty file | add rows |
| `line N: invalid JSON (...)` | broken JSONL line (a trailing comma, single quotes, a pasted line break) | one JSON object per line |
| `line N: duplicate id 'x' (first seen on line M)` | ids must be unique | rename |
| `line N: missing or empty 'question'` | the only required field | fill it |
| `line N: 'expected_answer' must be a string` | a number or list was used | quote it |
| `line N: 'id' must be a string or integer` | a boolean or object | use text or a number |
| `line N: 'metadata' must be a JSON object` | metadata given as a string or list | use `{"type": "..."}` |
| `line N: dataset exceeds the limit of 5 cases` (limit shown) | more rows than `RAGWB_MAX_CASES` (default 5,000) | raise the limit or split |
| `'question' is N characters; the limit is M` | over `RAGWB_MAX_FIELD_CHARS` (20,000) | shorten or raise |
| `CSV header must include a 'question' column` | missing/misnamed column | add the header |

Warnings do not block a run: `1 case(s) have no expected_answer; reference-based metrics will be skipped for them` (valid, exit 0), and
`ignored unknown field(s): ...`.

When a run is started with an invalid dataset the same problem is reported as one line, for example
`error: Dataset 'nothere.jsonl' is invalid: file not found: <path>`.

### 8.5.2 Document and configuration errors

| Command | Real message |
|---|---|
| `run --document file.docx` | `error: Unsupported document type '.docx'; use one of ['.md', '.pdf', '.txt']` |
| `run --document empty.txt` | `error: No extractable text found in empty.txt` |
| a document over the size limit | `error: Document is 17 bytes; the limit is 5 bytes` (limit set via `RAGWB_MAX_DOCUMENT_BYTES`) |
| `run -k 0` | `error: 1 validation error for RunConfig` then `k` / `Input should be greater than or equal to 1` |
| `run -k 99` | the same, `less than or equal to 50` |
| `run --limit 0` (or a negative number, or text) | `ragwb run: error: argument --limit: must be 1 or more` (exit 2, the argument parser; text gives `'abc' is not a whole number`) |
| `run --workers 0` | `ragwb run: error: argument --workers: must be 1 or more` (exit 2) |
| `run --min-evidence 1.5` | `min_evidence` / `Input should be less than or equal to 1` |
| `run --metrics nonsense` | `error: Unknown metric(s): nonsense. Available: exact_match, token_f1, rouge_l, context_recall, groundedness, semantic_similarity, semantic_context_recall, answer_relevancy, faithfulness, context_relevancy, correctness` |
| `run --threshold token_f1=2` | `error: Invalid threshold(s): {'token_f1': 2.0}; thresholds must be in [0, 1] for known metrics` |
| `run --threshold token_f1` | `error: Bad --threshold 'token_f1'; expected metric=value` |
| `run --metrics answer_relevancy` (no key) | `error: Metric(s) answer_relevancy use an OpenAI judge model and need OPENAI_API_KEY.` |
| `run --provider openai --metrics token_f1` (no key) | `error: OPENAI_API_KEY is not set; it is required for the OpenAI provider. Add it to .env or use the offline provider with the BM25 retriever.` |
| `run --retriever embedding` (no key) | `error: OPENAI_API_KEY is not set; it is required for the embedding retriever. Add it to .env or use the offline provider with the BM25 retriever.` |
| `run --pipeline agent` (offline) | `error: The agent pipeline needs a tool-calling LLM; choose provider 'openai' or pipeline 'rag'.` |
| `show nope` / `compare A nope` | `error: No run with id 'nope'. Use 'list' to see run ids.` |
| `show 2026` (a prefix, suffix or name that matches several runs) | `error: '2026' matches 3 runs (<ids>); give more of the id.` Type more of the id, or use the full id. |
| `delete ID` without `--yes` | exit 1 (add `--yes`) |
| `slices RUN --by type` when no case has metadata | `error: No case in this run has metadata field 'type'. Available: (none; add a metadata object to dataset rows)` |
| `prune` with no policy | `error: Give keep_last and/or older_than_days; refusing to select every run` |

> **Pitfall.** `--workers` and `--limit` (and `judge-noise --limit`) reject 0, negative numbers and text with exit 2, so a typo
> cannot silently mean "the default". One input is still accepted silently when you might expect an error: a dataset with
> **no reference answers** runs to completion with every reference metric skipped:
>
> ```
> Token F1                           -                -       -       0     1    0
> Context recall (lexical)           -                -       -       0     1    0
> ```
>
> That is "completed", exit 0, and no scores. See §8.6.3.

---

## 8.6 Empty, low and surprising scores

Most "the tool is broken" reports are really "the number does not mean what I thought". This section is about reading numbers; the
detailed theory is in Part V §5.4.

### 8.6.1 Token F1 is low although the answers look right

**Symptom.** Token F1 around 0.2 to 0.4 (the bundled honeybee baseline gets a mean of 0.346 with a 5% pass rate at k = 3).

**Likely cause.** Token F1 counts shared words between the answer and the reference. The offline baseline copies whole sentences
from the document, while references are short paraphrases. A correct paraphrase can score 0.000:

```
Candidate: "Usually just one."   Reference: "A colony normally has a single queen."
Token F1  0.000  fail  no shared tokens
```

**How to confirm.** Open a case in Run results, or run `ragwb score` with your own pair. The `reason` column says how many tokens
were shared. Check recall versus precision in the reason (`precision 0.11, recall 0.40`): long answers have low precision.

**Fix.** Do not tune the system to raise token F1. Use a semantic or judge metric for meaning, report token F1 as a lexical
overlap measure, and read the live record: with LLM-written answers, lexical F1 under-credits correct ones (live run 11:
token F1 passed 14 of the 26 answers a rater passed).

### 8.6.2 Groundedness is exactly 1.000 everywhere

**Symptom.** Groundedness 1.000, interval 1.000 to 1.000.

**Likely cause.** The offline generator can only copy sentences from the retrieved context, so every answer word is in the context by
construction. This is a property of the baseline, not evidence of quality.

**Fix.** Ignore groundedness for the offline baseline. It becomes informative with a real generator. Also see §8.6.7 for the
lexical-groundedness limits.

### 8.6.3 Scores are `-` or "not scored"

**Symptom.** A metric row shows `-` for mean and interval and `scored 0`, with a skip count.

**Likely cause**, by what the `reason` says:

| Reason | Meaning | Fix |
|---|---|---|
| `no expected_answer for this case` | the metric needs a reference and the row has none | add references, or accept that these cases are skipped |
| `no retrieved context for this case` | nothing retrieved (or the agent made no search) | check the retriever and `k` |
| status `error` | the metric raised; the reason names the exception | read the case detail; see §8.7 |

**Important.** Skipped and errored cases are **excluded** from every mean and counted; they are never treated as zero. Always read
the *scored* column next to the mean. A 1.000 on 1 scored case is not a result (live run 17: context relevancy "0.429" on 1 case).

In the volcano example, `context_recall` shows `scored 25, skip 5` because the five unanswerable questions have no reference
text to recall.

### 8.6.4 Context recall is low

**Likely causes**, most to least common: the answer is not in the document; BM25 cannot match the question's words to the passage
(no synonyms, only light stemming); `k` is too small; the chunk boundary splits the answer; or the reference is a paraphrase
whose terms never occur in the passage.

**How to confirm.** Look at the retrieved chunks of a low case. Then sweep `k`. On the volcano set, offline, context recall
rose steadily with `k`:

| k | 1 | 3 | 5 | 10 |
|---|---:|---:|---:|---:|
| context recall | 0.571 | 0.660 | 0.693 | 0.748 |
| token F1 | 0.199 | 0.199 | 0.199 | 0.199 |

**Fix.** Raise `k` if recall is the problem; try a dense retriever for paraphrased questions (Part III §3.4); fix the dataset if the
answer is not in the document. Recall is a ceiling for the whole system: a generator cannot use what was not retrieved.

### 8.6.5 Scores did not change when I changed the retriever or k

**Likely cause.** The offline extractive baseline can ignore most of the extra context: token F1 above was *identical* for k = 3, 5
and 10. Another cause: the run did not use the setting you thought (check `ragwb show RUN_ID`), or you compared a run with itself.

### 8.6.6 A difference is large but "not significant"

**Symptom.** Means differ by 0.03 and `ci_excludes_zero` is `False`; `regress` says `possible`.

**Likely cause.** Twenty questions is a small sample. The paired interval is wide.

**Fix.** Add questions (Part II §2.9), or accept "no detectable difference". The honest sentence is "this evaluation cannot tell".

### 8.6.7 A semantic metric gives high scores to everything

**Symptom.** Semantic similarity between 0.63 and 0.76 for nearly all answers.

**Likely cause.** bge-style cosines have a high floor: in the project's check an unrelated sentence scored 0.501 and a paraphrase
0.847. The default threshold 0.7 is not meaningful until calibrated.

**Fix.** Calibrate on labelled cases (`ragwb calibrate ... --sweep`, Part V §5.10). In the one AI-labelled sweep on 30 cases, a threshold of
0.55 to 0.65 agreed better than 0.70; that is a single document and an AI rater, not a recommendation.

### 8.6.8 My judge scores look too good or too bad

**Likely cause.** Judge metrics are model opinions. Faithfulness and answer relevancy were 1.000 on easy sets in live runs; context
relevancy was 0.173 in run 4 because most retrieved chunks do not address the question. Judge scores vary with judge model,
and a `RetryError`-style rate-limit loss reduces the number of scored cases (§8.7).

**Fix.** Measure noise (`ragwb judge-noise`, makes API calls), compare with labels, and report the judge model name.

### 8.6.9 All metrics are lower on a new dataset

**Likely cause.** Different document or question style, not necessarily worse system. Compare only runs on the same dataset and
document (the paired comparison requires shared questions). Dataset and document hashes are stored with each run.

---

## 8.7 Rate limits, retries and connection errors

These apply to live (provider) runs. I did not run any live call for this guide; the messages and numbers below come from
`docs/LIVE_VERIFICATION.md`, `docs/KNOWN_LIMITATIONS.md`, `docs/OPERATIONS.md` and the project book.

### 8.7.1 Many cases fail with rate-limit errors

**Symptom.** Case errors mentioning a rate limit (HTTP 429), or judge metric errors on a fraction of cases.

**Likely cause.** Your requests per minute or tokens per minute (or per day) exceed the provider quota. A judge measurement may be
several calls; judges that write long outputs hit **output-token** limits first (live run 17).

**How to confirm.** The case detail shows the error; the log shows retries and throttling. Count: `scored` plus `err` in the
summary.

**Fix**, in order:

1. `RAGWB_MAX_REQUESTS_PER_MINUTE` well below the quota (Part VII §7.4.3);
2. `--workers 1`;
3. fewer or cheaper judge metrics; a model with a higher cap;
4. a larger `RAGWB_MAX_RETRIES` (max 10). Retries wait at most 60 seconds per attempt and honour `Retry-After`;
5. `ragwb rerun RUN_ID` after the quota resets.

> **Pitfall.** Pacing cannot create quota. If a **daily** token budget is exhausted (live run 5: 199,638 of 200,000 tokens used), no
> pacing or retry setting will finish the run today. Stop, wait for the reset, or change model/provider.

### 8.7.2 `Connection error` on some cases

**Symptom.** Case errors reading `Connection error`.

**Likely cause.** A network drop. Short drops are retried; a long one exhausts the retry budget. (Live run 6 hit this.)

**Fix.** Check connectivity, `ragwb rerun RUN_ID`, and consider a higher `RAGWB_MAX_RETRIES` and `RAGWB_REQUEST_TIMEOUT_S` on a flaky
link. A rare variant (a defect fixed in the live record) mislabelled a connection drop as an unexpected error; if you see
"Unexpected error answering question" in the log, report it with the traceback.

### 8.7.3 `OpenAI rejected the API key (AuthenticationError). Check OPENAI_API_KEY.`

**Likely cause.** A wrong, expired or revoked key, or a key for a different provider than `OPENAI_BASE_URL`. The key is validated
only when a call is made, so each case fails with this permanent (non-retried) error and the run ends `failed`.

**Fix.** Correct the key (in the environment or `.env`; `python scripts/set_api_key.py` replaces it from a hidden prompt without printing it; restart the app, which reads settings once per process), and re-run.
A key in the process environment overrides one in `.env`.

### 8.7.4 The run seems to hang

**Likely causes.** Retry waits; pacing; a very slow provider; a stuck call. The per-case limit (`RAGWB_CASE_TIMEOUT_S`, default
600 seconds) abandons a stuck case and records an error, but Python cannot kill the thread, so the abandoned call may keep running
until its own HTTP timeout.

**How to confirm.** The log. Offline, pacing alone can make a run slow on purpose: four cases at 6 operations per minute took 32
seconds.

**Fix.** Lower timeouts and retries, or cancel (Ctrl+C in the CLI; the Stop button in the app) and `rerun`.

---

## 8.8 Partial, failed, cancelled and interrupted runs

| Status | Meaning | Exit code of `run` | What to do |
|---|---|---:|---|
| `completed` | every case answered | 0 | nothing |
| `partial` | some cases errored | 2 | read the errors; `rerun` |
| `failed` | every case errored | 2 | fix the cause (configuration, key, network) first |
| `cancelled` | you stopped it (Ctrl+C) | Python's interrupt code | `rerun` when ready |
| `interrupted` | the process died; marked at the next start | n/a | `rerun` |
| `running` | active, or died less than 15 minutes ago | n/a | wait, or restart |
| `imported` | came from a bundle | n/a | n/a |

**Reproduced.** Injecting failures into 30% of cases offline:

```
Run 20261030-210042-partial-29cf43: partial
cases 20  ok 17  errors 3  mean latency 0.5 ms
Token F1                       0.344      0.276-0.432       6%      17     0    3
```

exit code 2, and every metric shows `scored 17 ... err 3`. With `--inject-failures 1` all 20 error, status `failed`, exit 2, and the
metric rows show `-`.

**Likely cause of a stuck `running`.** The process was killed (power loss, closed terminal). The run stays `running` until no case has
been committed for 15 minutes; the next start-up marks it `interrupted`. `ragwb list --status running` shows it; `ragwb doctor`
warns about runs that look abandoned.

**Fix.** Completed cases of a partial or interrupted run are kept and scored. To get a complete run, `ragwb rerun RUN_ID` (a new run
with the same configuration); do not average a partial run with a full one without saying so. Part IV §4.7 explains the lifecycle.

> **Why this works.** Cases are committed as they finish, and failures are recorded per case, so one bad question never loses the
> rest of the run.

---

## 8.9 Locked-out admin, forgotten passwords and sign-in trouble

### 8.9.1 No admin can sign in

**Symptom.** Nobody can manage accounts; the Accounts page says "Managing accounts needs an admin account."

**Likely cause.** The last admin was demoted or removed with `--force`, or an admin forgot their password (there is no self-service
reset).

**How to confirm.** `ragwb user list` on the server.

**Fix (reproduced).** Stop the app, then create a new admin:

```bash
echo "rescue-admin-pass-9" | ragwb user add rescue --role admin --password-stdin
```

```
Saved user rescue (admin). Sign in on the web app with this username.
```

To reset a user's password: `ragwb user set-password NAME` (prompts twice) or `... --password-stdin`. Result:
`Password changed for bob. Open sessions stay signed in until they end.`

### 8.9.2 `error: The users file users.json is unreadable or malformed`

**Symptom (real).**

```
error: The users file users.json is unreadable or malformed (Expecting property name enclosed in double quotes: line 1 column 3 (char 2)); fix or delete it to continue
```

**Likely cause.** A hand-edit, a half-synced or truncated file. The app treats a damaged file as "accounts exist" and **locks** rather than
opening.

**Fix.** Restore your copy of `users.json`, or move the file aside and add a new admin: the tool then reports
`No user accounts (the app uses RAGWB_APP_PASSWORD, or no login).` and `user add` works. Until you add a password or an account,
nothing protects the app; keep it on `localhost`.

### 8.9.3 Locked out for 60 seconds

**Symptom.** Sign-in is refused though the password is right.

**Likely cause.** Five failed attempts for that username within 60 seconds trigger a lockout; a global limit also exists. Check the log
for `sign-in failed` lines.

**Fix.** Wait a minute. If you see failures you did not cause, that is someone guessing: restrict the network exposure.

### 8.9.4 `Passwords must be 10-200 characters`, or a username is rejected

Usernames are lowercase letters, digits, `.`, `_` and `-`, up to 32 characters, starting with a letter or digit. See Part VII §7.1.3.

### 8.9.5 A removed user is still signed in

A removed user's session ends on their next page load, and role changes apply at the next page load. A browser tab left open does not
refresh by itself.

---

## 8.10 A corrupt store and restoring from a backup

**Symptom.** Any command fails with `Run store error (runs.db): file is not a database`, `Cannot open run store ...: ...`, or `database
is locked`; `ragwb doctor` shows a `[FAIL] run store` line (reproduced):

```
[FAIL] run store         <data dir>\runs.db cannot be read: Run store error (runs.db): file is not a database
8 ok, 0 warning(s), 1 failure(s)
```

and `ragwb list` gives `error: Run store error (runs.db): file is not a database` (exit 1).

**Likely causes.** Disk errors; a sync client rewriting the file while the app runs (the data directory inside OneDrive, Dropbox or
similar); a copy taken while the file was being written; a full disk.

**How to confirm.** `ragwb doctor` (integrity check), free disk space on the `disk space` line, and whether the data directory is
inside a synced folder.

**Fix.**

1. Stop the web app and any running evaluation.
2. Find your newest backup (`<data dir>/backups/`, or wherever you keep them).
3. `ragwb restore BACKUP --yes`. With a damaged live file the command keeps a raw copy as
   `pre-restore-damaged-<timestamp>.db` and carries on.
4. `ragwb doctor` should read `schema v3, N runs, integrity ok`.
5. Move `RAGWB_DATA_DIR` out of any synced folder (Part VII §7.7.5).

Restore also refuses (all reproduced): a non-database backup, a missing file, a backup from a newer schema, and a store with a
run still active without `--force`. See Part VII §7.2.4 for the exact messages.

> **Pitfall.** With no backup you cannot recover run data from a damaged `runs.db` with these tools. Runs exported as JSON bundles
> can be re-imported (`ragwb import FILE.json`). That is the cheapest insurance there is.

If the message is `database is locked`, another process holds the file: stop the app or the other evaluation, or move the data
directory off a synced folder. The store waits up to 15 seconds for a lock before failing.

---

## 8.11 The web app is blank, slow or shows old behaviour

I did not drive a browser for this guide, so the entries below come from the project's documentation
(`docs/KNOWN_LIMITATIONS.md` and the project book, Part VIII) and from reading the code. Treat them as the documented causes.

| Symptom | Likely cause | How to confirm | Fix |
|---|---|---|---|
| Blank page or spinner forever | the Streamlit server is not up, or crashed on start | `/_stcore/health` should say `ok`; look at the terminal that launched it | restart `python start.py`; read the first error |
| `ImportError` or old behaviour after editing package code | Streamlit caches imported modules between page reruns | the error appears only after a code change | stop and start the server (changes in `ui/views/` are picked up; other modules are not) |
| Changed `.env` and nothing happened | settings are read once per process | `Settings & metrics` page shows the old value | restart the app |
| New evaluation page slow with a large PDF | the page re-parses the selected PDF on every interaction | small PDFs are fast; a 200-page PDF loads in about 0.2 s offline | use a smaller file for experimenting, or run from the CLI |
| Pages slow with thousands of cases | tables are drawn in the browser | a 5,000-case read-back takes 0.3 s in the library; the browser is the cost | export CSV and analyse there |
| A run looks stuck at 0 of N | provider waiting, pacing, or retries | the log | §8.7 |
| "Managing accounts needs an admin account" | you are not an admin, or no accounts exist | `ragwb user list` | §8.9 |
| Table navigation by keyboard is tedious | every cell is a Tab stop | documented limitation | use the CSV download of the table |
| Page asks for a login you do not remember | accounts or a shared password are configured | `ragwb user list`; `RAGWB_APP_PASSWORD` set? | reset with `ragwb user set-password` |

The Stop button cancels a run, but in-flight model calls (and with several workers up to 2 x workers queued cases) finish first.

---

## 8.12 Windows path length

**Symptom.** Import errors for compiled modules (documented example: `ImportError: cannot import name 'ArgsKwargs' from
'pydantic_core._pydantic_core'`), or a local-model download that fails with a file-not-found error deep inside `models/`.

**Likely cause.** Windows' 260-character `MAX_PATH` limit. Two things nest deeply: a `.venv` inside a deeply nested project folder, and the
embedding model cache under `<data dir>/models`. This project's own folder sits several levels deep under OneDrive, so it is a realistic
case. I did not reproduce a path-length failure for this guide.

**How to confirm.** Count characters of the longest path: in PowerShell,
`Get-ChildItem -Recurse -File | ForEach-Object { $_.FullName.Length } | Measure-Object -Maximum`.

**Fix.** Move the project to a short path (for example `C:\ragwb`), or enable Win32 long paths in Windows and tools; set
`RAGWB_DATA_DIR=C:\ragwb-data`; then run `python start.py` again.

---

## 8.13 Local embeddings: `fastembed` and model downloads

The local retrievers (`local`, `hybrid-local`) and the semantic metrics use a small embedding model through the optional
`fastembed` package (`uv sync --extra semantic`). The first use downloads the model from a public hub into `<data dir>/models`; after
that nothing leaves the machine and `HF_HUB_OFFLINE=1` works.

### 8.13.1 The run stops at once: "The local embedding model ... could not be loaded"

**Symptom.** `run --retriever local` (or `hybrid-local`, or any run with `semantic_similarity` or `semantic_context_recall`) stops
before the first case with one error and exit 1. The message looks like this (a real one, shortened; the path is yours):

```text
error: The local embedding model 'BAAI/bge-small-en-v1.5' could not be loaded (ValueError: Could not load model
BAAI/bge-small-en-v1.5 from any source.). The first use downloads it (about 70 MB, needs network access once) into
<data dir>\models; after that it works offline. Check the network or pre-download the model (see Local embeddings in
BUILD_AND_RUN.md).
```

In earlier builds the same situation looked like a hang: the model was loaded lazily, so *every case* waited for its own failed
download (about 45 seconds each) and then logged an error, and the run ended `failed` with a dash for every mean. Now the model is
loaded when the run is **prepared** (in `build_retriever` for the retrievers and in `build_semantic_metric` for the metrics, both in
the `src/rag_workbench` package), so a model that cannot be loaded produces this single message and no run is stored. The text in
parentheses is the error type and detail from the loader; it is the part to look at (`ValueError` above means every source failed;
a `PermissionError` or `OSError` points at the folder).

**Likely causes.** The model has never been downloaded and the machine has no network, a firewall or proxy blocks the model hub, the
download was interrupted (the cache folder then holds only a `refs/main` marker), or the cache path is too long for Windows. In the
last case the loader reports `WinError 206` ("The filename or extension is too long") in its log, because the cache nests folders
deeply; this guide's author saw exactly that when the data directory sat in a very long path.

**How to confirm.** Look in `<data dir>/models` (is there a model snapshot with `.onnx` files?). Note the cost of finding out: the
loader retries a few times with growing pauses, so the message can take about 40 seconds to appear. That is one wait, not one per case.

**Fix.** Download the model once on a connected machine (run a local-retriever evaluation with the network on), then copy the
`models/` folder to the offline machine's data directory, or set `RAGWB_DATA_DIR` to a store that already has it. Keep the data
directory path short (for example `C:
agwb-data`). After that, `HF_HUB_OFFLINE=1` prevents any contact. Delete an empty or partial
`models` folder before retrying.

The same check protects `ragwb calibrate --rescore` for the semantic metrics: if the model cannot be loaded you get this message; if
the metric loads but cannot be computed for any case, the command fails with `<metric> could not be computed for any case: <reason>`
instead of printing a report of zeros.

> **Pitfall.** On a connected machine, **even `--metrics semantic_similarity` contacts the hub on first use**, and the console may
> show `Warning: You are sending unauthenticated requests to the HF Hub` and a "Fetching 5 files" progress bar. No project data is sent,
> but if your policy forbids any outbound connection, do not run semantic metrics or local retrievers until the model is in place.

### 8.13.2 The metric or retriever says the package is missing

If `fastembed` is not installed, the semantic metrics are described as "optional, needs fastembed" in `ragwb metrics`, and the
retrievers refuse to start with an install hint. Install the extra (`uv sync --extra semantic`, which needs the network).

### 8.13.3 Which model is used

`BAAI/bge-small-en-v1.5` by default; change it with `RAGWB_LOCAL_EMBEDDING_MODEL`. The model is English-oriented.

---

## 8.14 More symptoms, briefly

| Symptom | Likely cause | Fix |
|---|---|---|
| `ragwb` is not recognised | the environment is not on `PATH` | use `uv run ragwb`, or `.venv\Scripts\python.exe -m rag_workbench` |
| Non-English characters print as `?` or raise `UnicodeEncodeError` in your own script | the Windows console code page is cp1252 | set `PYTHONIOENCODING=utf-8` for your scripts; files written by the tool are UTF-8 |
| Excel shows garbled characters in a CSV export | Excel needs a BOM | the export already starts with a UTF-8 byte-order mark; open it with Data > From Text if it still misbehaves |
| A `.deepeval/` folder appeared | importing DeepEval creates it | harmless; it is ignored by git |
| `regress` exits 4 and "nothing was verified" | fewer paired questions than `--min-pairs`, or different datasets | §7.3.1 of Part VII |
| `regress` exits 1: `Metric(s) not present in both runs: X. Shared metrics: ...` | a `--metrics` name that is mistyped or missing from one of the runs | use one of the shared metrics the message lists |
| `compare` says no shared metric | the runs used disjoint metric sets | re-run with the same metrics |
| `import` says `already present, skipped` | the bundle's run id exists | harmless; delete the run first to replace it |
| `restore` is refused: "still active" | a run looked active within 15 minutes | stop it, or `--force` if you are sure |
| `prune` deleted my baseline | only runs tagged `keep` are spared; `baseline` does not protect | tag baselines `keep` (`ragwb tag RUN --add baseline,keep`); export them first; Part VII §7.2.6 |
| A `rerun` gives different numbers | the dataset or document file changed, or the provider is non-deterministic | compare hashes in `ragwb show` / the Markdown export |
| `labels-template` fails: file exists | it will not overwrite | add `--force` |
| `calibrate` finds nothing comparable | label case ids do not match the run, or the metric was not scored | match `case_id`; use `--rescore` for offline and local metrics |
| Cost shows `—` | no prices configured | set `RAGWB_PRICE_INPUT_PER_MTOK` and `RAGWB_PRICE_OUTPUT_PER_MTOK`, or accept unknown |

---

## 8.15 FAQ

Fifty-four questions, answered directly. References in brackets point to where a longer answer lives.

### Metrics

**1. Which metrics should I start with?** Offline: token F1, ROUGE-L, context recall and groundedness (the defaults). With a provider,
add `correctness` first; it needs a reference and had the best agreement with AI-written labels in the project's check. Add the
other judge metrics later and one at a time. (Part III §3.7)

**2. Why is token F1 so low when the answer is right?** It counts shared words, and a correct paraphrase shares few. The bundled
baseline scores 0.346 mean on honeybees. (§8.6.1)

**3. What does context recall measure?** The share of the reference answer's content terms that appear in the retrieved context.
It measures retrieval, not the generator, and it is skipped when there is no reference. (Part V §5.4)

**4. What does groundedness measure?** The share of the answer's content terms present in the retrieved context. It cannot
detect a wrong claim phrased with words that happen to be in the context, and it is 1.000 by construction for the extractive
baseline.

**5. What is the difference between groundedness and faithfulness?** Groundedness is lexical (word presence). Faithfulness is a
judge metric: a model extracts claims from the answer and checks each against the context. Faithfulness understands meaning; it also
costs money and can be rate-limited. (Part V §5.4)

**6. What is context relevancy and why can it be low?** The share of retrieved statements the judge finds relevant to the question.
It penalises retrieving more than you need: live run 4 gave 0.173 with `k = 3` because most retrieved text did not address the
question. Low context relevancy with high recall means "found the answer but also a lot of noise".

**7. Are the semantic metrics useful?** Only after calibration. The tested model (`bge-small-en-v1.5`) scores 0.63 to 0.76 on
nearly everything; the default threshold 0.7 says little. (§8.6.7)

**8. Does the pass threshold matter?** It changes the **pass rate**, not the mean or the interval. A mean of 0.346 with a 5% pass
rate and a threshold of 0.5 tells you the distribution is below 0.5. Change thresholds with `--threshold metric=value`, but report
the mean and interval first.

**9. What happens to errors and skipped cases?** Excluded from means and counted, never zero. (§8.6.3, Part V §5.3)

**10. Can I add my own metric?** In a script, yes: `Metric(MetricSpec(...), scorer)` takes a function that returns
`(score, reason)`, and `.evaluate(MetricInput(...))` applies the standard skip/error handling (tested with a toy "short answer"
metric). The CLI's `--metrics` list is fixed to the built-in catalogue. (Part VII §7.9)

**11. Which metric catches hallucination?** None alone. Groundedness (cheap, lexical) and faithfulness (judge) look for answer content
unsupported by the context; correctness looks for disagreement with the reference. Read the case detail for the cases they flag.

**12. Are the judge metrics reliable?** One measurement exists: in a 10-case, 3-repeat check of `correctness`, call-to-call
jitter was small (within-case SD 0.023) next to differences between cases (0.371), and one of ten cases flipped its verdict. Against
AI-written labels on 30 volcano cases the judge agreed on 29 (kappa 0.870), with an AI rater and mostly easy cases. No human
calibration exists. (`docs/LIVE_VERIFICATION.md` runs 8 and 11; Part V §5.9)

### Statistics

**13. What is the confidence interval?** A percentile bootstrap interval of the mean: 2,000 resamples of the scored cases, 95%
confidence, a fixed seed (12345). The same results always give the same interval. It captures **question sampling only**, not judge
noise. (Part V §5.2)

**14. How many questions do I need?** Twenty to thirty shows large differences only; many configurations are statistically
indistinguishable at that size, and the tool says so. More questions narrow the interval roughly with the square root of the
number. (Part II §2.9, Part V §5.8)

**15. What does the paired comparison do?** It matches the two runs question by question and bootstraps the difference, so a
question that is hard for both cancels out. It lists how many questions B won, tied and lost. `ci_excludes_zero` is the claim to make.

**16. Why does my k = 5 versus k = 3 comparison show zeros?** The extractive baseline answered the same on all 20 questions
(token F1 difference 0.000, 20 ties). Not a bug. (Part VII §7.5.3, exercise 2)

**17. What is Cohen's kappa?** Agreement between a metric's pass/fail and labels, corrected for chance. 0 is chance-level, 1 is
perfect. With fewer than 30 compared cases the tool warns it is indicative only. (Part V §5.10)

**18. How does `regress` decide?** A metric regresses when its mean drops by more than `--max-drop` (0.02) **and** the interval of
the paired difference excludes zero; a drop beyond the limit with an interval including zero is `possible` (not a failure); the
error rate may not rise by more than `--max-error-increase` (0.05). Exit codes: 0 ok, 3 regression, 4 not judged, 1 error.

**19. Can I trust a run where "pass rate" is 100% on few cases?** No. Read the scored count and the interval.

### Privacy and data flow

**20. What is sent to a provider?** With a provider: the questions, the retrieved text and the generated answers go to the
provider's API, and judge metrics send every answer and its context again. Offline mode sends nothing. (`docs/SECURITY.md`)

**21. Is anything sent in offline mode?** No evaluation data. DeepEval and Streamlit telemetry are disabled (`ragwb doctor` checks
it). Installing packages and the optional one-time model download use the network.

**22. Is my API key stored in runs, exports or logs?** No: keys are held as secrets, redacted in logs and tracebacks, never rendered in
the UI or written to run configurations (the settings view shows only whether a key is configured). The key lives in the environment or in
`.env`; see Part VII §7.7.5 about `.env` in synced folders. If the key was ever exposed, rotate it at the provider and install the new one with `scripts/set_api_key.py` (Part VII §7.1.12).

**23. Does the local embedding model send my documents anywhere?** No project data. It downloads the model from a public hub once
(§8.13), then runs locally.

**24. Can I use a provider other than OpenAI?** Any OpenAI-compatible endpoint: put its key in `OPENAI_API_KEY`, its URL in
`OPENAI_BASE_URL`, and its model names in `RAGWB_GENERATOR_MODEL` and `RAGWB_JUDGE_MODEL`. The live record is Groq's free tier; other
providers are supported by configuration only. Use `--retriever bm25` unless the provider offers embeddings.

**25. Who can see runs on a shared instance?** With the default `shared` visibility, every signed-in user; with `own`, non-admins see
only their runs and ownerless ones. Application-level only. (Part VII §7.1.6)

**26. Where are my documents kept?** Wherever you keep them; uploads through the web app go to `<data dir>/uploads`. The run store
keeps absolute paths and hashes, not copies, of dataset and document files.

### Reproducibility

**27. Will two people get the same numbers?** Offline: yes, to every printed decimal, given the same dataset, document and settings.
Judge metrics: no, model calls vary; measure the noise.

**28. What does the run store record?** The full configuration, dataset and document hashes, package versions, per-case latency, tokens
and errors, and the prices used for cost. (Part IV §4.5)

**29. What does `--seed` do?** It seeds the offline failure injection (`--inject-failures`). The offline pipeline is otherwise
deterministic, and the bootstrap uses its own fixed seed.

**30. Why can bootstrap bounds differ in the third decimal for the same scores?** They depend on the order of the scores as well as
the seed; a run's order is the dataset order, so a given run is reproducible. (`docs/KNOWN_LIMITATIONS.md`)

**31. How do I prove which dataset a run used?** Compare the sha256 in `ragwb show` or the Markdown export header with your file.

### Scale

**32. How many cases can I run?** Up to `RAGWB_MAX_CASES` (default 5,000); larger datasets are refused. Offline, 5,000 cases took
about 47 seconds, with 54 MB peak Python memory and a 21 MB database; throughput was about 100 cases per second, flat from 200
to 5,000 (`docs/OPERATIONS.md` §7). Measured on one laptop.

**33. How big can a document be?** 25 MB by default (`RAGWB_MAX_DOCUMENT_BYTES`). 5,000 chunks index in about 0.3 s and answer a
query in about 3 ms; a 200-page PDF (1,600 chunks) loads in about 0.2 s.

**34. Do more workers help?** Offline only slightly (4 workers: about 115 versus 100 cases per second at 1,000 cases). With a
provider they matter, until you hit its quota. (Part III §3.10)

**35. How fast is a live run?** Set by the provider's quotas, not by this tool. A 20-question run with four judge metrics took hours
on a free tier with a 1,000 output-tokens-per-minute cap (live run 17).

**36. How many people can use one instance?** It is a single process; sessions live in memory. It is intended for a small trusted
group, not for the public internet. A third-party security review has not been done.

**37. Were the older benchmark numbers wrong?** Earlier releases published roughly half these throughputs and claimed four workers
were slower; they were measured with a memory tracer running and withdrawn in release 1.4. Use the corrected numbers above.

### Supported inputs

**38. Which document types?** `.pdf`, `.txt`, `.md`. Anything else gives `Unsupported document type`. (Part II §2.1)

**39. What about scanned PDFs?** There is no OCR. A PDF with no extractable text fails with `No extractable text found in <file>`.
Convert it to text first.

**40. Which dataset formats?** `.jsonl` (one object per line) and `.csv` (header with a `question` column). Required: `question`. Optional:
`id`, `expected_answer`, `metadata`. In CSV, **extra columns become metadata** (the bundled `topic` column of the paraphrased set
slices as `--by topic`). Unknown JSON fields are ignored with a warning. (Part II §2.4)

**41. Can questions have no reference answer?** Yes. Reference-based metrics are skipped for them, which is correct for testing
groundedness-only or live monitoring, but a dataset with no references scores nothing on reference metrics (§8.5.2).

**42. How are unanswerable questions marked?** By giving them the abstention sentence as the reference answer (the bundled sets use
"The PDF does not provide enough information to answer the question.") and a `type: unanswerable` metadata value for slicing.
(Part II §2.7)

### Languages

**43. Does it work for languages other than English?** Partly, and be honest about it. The tokenizer matches letters of any script
and lower-cases after Unicode normalisation, so German, French and Russian text is split into words. But the stop-word list, the
stemmer (a light English plural stripper) and BM25's behaviour are English-oriented, and the abstention patterns are English
sentences. In a test, an 8-word German sentence kept all 8 as content tokens (no German stop words removed), and the French word
`œufs` was stemmed with an English rule to `œuf`. Scores in other languages are therefore noisier and not comparable with English
ones.

**44. What about Chinese or Japanese?** There is **no word segmentation**: a Japanese sentence without spaces became a **single
token**, so lexical metrics (token F1, ROUGE-L, recall, groundedness) are close to all-or-nothing and BM25 retrieval cannot match
partial words. Use judge or embedding-based approaches, and expect lexical metrics to be unusable. Judge quality in other languages
depends on the judge model and was not tested.

**45. Do judge metrics work in other languages?** The prompts are English; whether a given model judges, say, Hindi answers
reliably is unmeasured here. Test with labelled cases first.

### Modes and choices

**46. Offline provider or an OpenAI-compatible one?** Offline: free, deterministic, fast, an extractive baseline that quotes the
document. Provider: real generation and judge metrics, at cost and noise. Develop offline, finish live. (Part III §3.2)

**47. RAG pipeline or agent?** The RAG pipeline always retrieves `k` chunks, then generates. The agent lets a tool-calling model decide
when to search; the scored context is what its search tool actually returned, never its own account of it. The agent was run live on
3 questions only, so treat it as proven to work, not as characterised. (Part III §3.3)

**48. Which retriever?** `bm25` is the lexical default and needs no setup; `embedding` and `hybrid` call an embeddings API (needs a key and
a provider that offers embeddings); `local` and `hybrid-local` use a local model. On the bundled data there is no consistent winner:
local embeddings helped paraphrased questions (context recall 0.664 to 0.786) and hurt the main honeybee set (0.885 to 0.792).
(`docs/LIVE_VERIFICATION.md` run 9; Part III §3.4)

**49. Web app or CLI?** The same code. The web app is for exploring and sharing; the CLI is for scripting, schedulers and CI. The CLI
has no access control. A run started in either appears in both.

**50. Shared password or named accounts?** A shared password is one login for everyone, no roles, no ownership. Named accounts give
roles, ownership and per-user lockout. If both exist, accounts win. Prefer accounts for any real team. (Part VII §7.1)

### A few more, quickly

**51. Can I run two evaluations at once?** Yes, as separate processes against the same store; writes are short and wait up to 15
seconds for a lock. Avoid two writers on a synced folder.

**52. Can I delete a single run safely?** `ragwb delete RUN_ID --yes` (admin role in the web app). It is permanent; back up first.

**53. Can I change a dataset after a run?** You can, but the stored hash no longer matches the file, and a rerun will measure the new
file. Version your datasets (Part II §2.12).

**54. How do I report a defect?** Include the command, the first line of the error, `ragwb --version`, the `doctor` output, and the
relevant log lines. Do not include keys or documents you may not share.

---

## 8.16 Checklist: when something looks wrong

- [ ] I read the first line of the error and ran `ragwb doctor`.
- [ ] I checked `ragwb show RUN_ID` to see what the run really used.
- [ ] I looked at the *scored* and *skipped* counts before the mean.
- [ ] I re-ran the smallest case that shows the problem (`--limit 3`).
- [ ] I did not paste a key anywhere, and I restored from a backup rather than editing `runs.db`.
- [ ] I wrote down the fix, so the next person finds it.
