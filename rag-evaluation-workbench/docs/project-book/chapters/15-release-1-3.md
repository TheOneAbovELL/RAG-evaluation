# Part XV — Release 1.3: live verification, pacing, local embeddings, judge noise and roles

Release 1.2 ended with a list of things that no amount of offline testing could close (Part XIV §159.3). Release 1.3
(version `1.3.0`, `src/rag_workbench/__init__.py:13`) takes every item on that list that *could* be closed with the
resources at hand, which were a free-tier key for an OpenAI-compatible service (Groq) and one small local embedding model,
and then builds the features those runs showed to be missing. It is therefore a release about the distance between
"implemented and tested with fakes" and "run against the real thing", and this Part is organised around that distance:
what was run, what it found, what had to change, and, as plainly as possible, what is still not run. Every number
in it comes from `docs/LIVE_VERIFICATION.md`, `docs/TESTING.md`, `CHANGELOG.md`, a file that is cited, or a command whose
output is shown here; nothing is projected or estimated.

**What did not change.** Default behaviour is the same: the default retriever is BM25, the default provider is `offline`,
no variable is required, no scoring formula changed and the storage schema is still 3.
Everything below is opt-in or additive, with two exceptions that are visible to every user: transient-error messages now
say "OpenAI-compatible API" instead of naming OpenAI (`errors.py:50`), and accounts created before roles existed are
now treated as `editor` (`rag_workbench/users.py:32`, `:115`).

## 160. Motivation, and the live verification

### 160.1 Closing the loop between "implemented" and "verified"

Through release 1.2 the project could say of its OpenAI-backed paths only that they were implemented and tested with fakes.
That is a real statement, and the fakes were good enough to catch many defects (Part X §105), but it leaves a particular kind
of defect uncatchable: the one that lives in the *contract between this code and a real service*. A fake raises the exception
the author expects; a real provider raises the exception it raises. Release 1.3 was an attempt to find out how large that gap
was, and the answer is in §160.4: two defects, both in error classification, both invisible to every offline test.

The design rule that came out of it is the same as in releases 1.1 and 1.2 — say what was and was not verified — but now
applied in two directions. A path that was run says exactly what ran (§160.2) and how small the sample was; a path that was
not run is listed by name (§160.6, §167), and no sentence in this book claims a live result for OpenAI itself.

### 160.2 What was run

The provider was Groq Cloud's free tier, reached through its OpenAI-compatible endpoint
(`https://api.groq.com/openai/v1`) with `OPENAI_API_KEY` and `OPENAI_BASE_URL`. The models available to that key for chat were
`openai/gpt-oss-20b`, `openai/gpt-oss-120b` and `qwen/qwen3.8-27b`. The provider has no embedding models, so API embeddings
(and hybrid retrieval with API embeddings) were not exercised at all. Every live run used BM25 retrieval, k = 3 and one worker.
All runs were made on 2026-10-28. The complete record is `docs/LIVE_VERIFICATION.md`; this table is its summary.

| # | Run | Result |
|---|---|---|
| 1 | `scripts/live_smoke.py`, 2 cases, no judge, generator `gpt-oss-20b` | 8/8 checks: answers, retrieved context, token usage (658 in / 179 out) and lexical metrics |
| 2 | the same script, 2 cases, four judge metrics (`gpt-oss-120b` judge) | first attempt **8/12**: one case per judge metric hit the free-tier rate limit and was recorded as an *error* (a `RetryError` whose cause the retry logic did not recognise) |
| 3 | the same, after wrapped rate limits were recognised and `Retry-After` was honoured | **12/12** checks; all four judge metrics scored both cases |
| 4 | 10 honeybee questions, four judge metrics | all 10 answered; 3 of 40 judge scores lost to the rate limit (excluded from means, counted as errors) |
| 5 | 20 honeybee questions, four judge metrics | **not completed**: the judge model's daily token budget was already used (199,638 of 200,000 tokens), so the run was stopped |
| 6 | 30 volcano questions, `qwen/qwen3.8-27b` as generator and judge, `correctness` only | finished `partial`: 28 ok, 2 case errors caused by a bug (§160.4) during a network drop |
| 7 | the same run repeated with the bug fixed | 30/30 cases ok |
| 8 | `ragwb judge-noise` on run 7, 10 cases x 3 repeats, `correctness` | §164 |
| 9 | local embeddings (`BAAI/bge-small-en-v1.5`, real model, `HF_HUB_OFFLINE=1`) on five datasets x three retrievers | §162 |
| 10 | keyboard Tab walk of the New evaluation page in a browser | §166 |

Runs 1–7 are the live-service runs; runs 8 and 10 are a re-scoring against the service and a browser check; run 9 needed no
service at all and used a real model on the local machine. Run 5 is in the table on purpose: a record that listed only the
runs that finished would overstate what was verified.

### 160.3 What the live runs showed

Run 4 is the first time the four judge metrics produced numbers from a real judge in this project.

| Metric | Mean | 95% CI | Scored | Failed |
|---|---:|---|---:|---:|
| Token F1 | 0.680 | 0.554–0.804 | 10 | 0 |
| Context recall (lexical) | 0.891 | 0.817–0.961 | 10 | 0 |
| Groundedness (lexical) | 0.967 | 0.922–0.996 | 10 | 0 |
| Answer relevancy (judge) | 1.000 | 1.000–1.000 | 10 | 0 |
| Faithfulness (judge) | 1.000 | 1.000–1.000 | 10 | 0 |
| Context relevancy (judge) | 0.173 | 0.140–0.211 | 8 | 2 |
| Correctness (judge) | 0.522 | 0.233–0.822 | 9 | 1 |

These are the first 10 of 20 questions, so they are not comparable with the offline numbers over all 20 (Part VI §74).
Generation used 3,375 input and 1,105 output tokens; DeepEval reported no judge cost for this provider. The two failures in
context relevancy and the one in correctness are the lost judge scores of the run-4 row above: they are shown in the *Failed*
column and excluded from the means, never counted as zero, which is the rule the whole product is built on.

Run 7 repeats the volcano questions with `qwen/qwen3.8-27b` as generator and judge, scoring `correctness` only:

| Metric | Mean | 95% CI | Scored | Skipped |
|---|---:|---|---:|---:|
| Token F1 | 0.489 | 0.381–0.600 | 30 | 0 |
| Context recall (lexical) | 0.660 | 0.539–0.774 | 25 | 5 |
| Groundedness (lexical) | 0.884 | 0.819–0.940 | 22 | 8 |
| Correctness (judge) | 0.803 | 0.663–0.920 | 30 | 0 |

The skips are the 5 unanswerable questions (no reference to recall) and abstained answers (nothing to ground). Two things
are worth taking from these tables and one thing is not. *Taken:* the pipeline, the context capture, the token accounting,
the lexical metrics and the judge adapter all work end to end against a real service; and an interval over 10 or 30 questions
is wide (the correctness interval in run 4 spans 0.233 to 0.822). *Not taken:* any statement about which model is better.
The two runs use different generators, different judges and different documents; the sample is tiny; and a judge scoring
its own family's output is exactly the situation §164 warns about.

### 160.4 Two defects found only by running live

Both defects are in `errors.py`, the module that turns SDK exceptions into this project's hierarchy
(`ProviderError`, `TransientProviderError`; `errors.py:9-21`). Both were invisible to the offline suite because the suite's
fakes raised the exceptions the author had in mind.

**Defect 1: rate limits recorded as opaque errors.** DeepEval wraps a provider error in tenacity's `RetryError`. The
classifier looked only at the exception it was given, so a 429 arriving as `RetryError[<Future ...>]` was not recognised as an
OpenAI error, was not retried, and was recorded as an error with the unhelpful message `RetryError[<Future ...>]` (run 2,
first attempt: 8 of 12 checks). The fix is `_unwrap` (`errors.py:58-76`): it follows tenacity's `RetryError.last_attempt` and
`__cause__` links, for at most 8 hops, to the first exception that is an OpenAI SDK error, and `classify_openai_error` classifies
that (`errors.py:46`). Wrapped SDK errors are now found, retried, and given the provider's `Retry-After` (§161).

**Defect 2: the walk that went too far.** The first version of the fix walked an exception's cause chain *to its end*. For
a connection drop that is the wrong place to stop: an `openai.APIConnectionError` is raised `from` the underlying `httpx`
transport error, so walking to the end of the chain returned the `httpx` error, which is not an OpenAI error, and the
case was recorded as an *unexpected* error instead of being retried. It happened in run 6 when the network dropped
(cases `v16` and `v17`, which is why that run finished `partial`: 28 ok, 2 errors). The fix is the early return at
`errors.py:71-72`: the search stops at the **first** SDK error, and the docstring says why (`errors.py:61-63`). The regression
test builds exactly that chain, a transport error as the cause of an `APIConnectionError`, and asserts that the classified
result is transient, also when the whole thing is wrapped in a `RetryError`
(`tests/test_retry_hints.py:53`, `:37`).

Defect 2 is the more instructive. It was introduced by the fix for defect 1, passed every offline test that existed at that
point, and was caught only because the network happened to fail during a live run. A one-line change in how a chain is walked
decided whether a dropped connection was retried or recorded as a bug, and nothing but a real network could have told the two
apart. This is the concrete argument for the live runs, and the reason the regression test now exists.

Both defects are listed with the other defects of the project in Part X §105 (items 23 and 24).

### 160.5 Quotas, and the sleeping machine

Two further problems were not defects in the code, and the record keeps them apart from the ones that were.

* **Quota.** Runs 5 and the earlier part of run 6 stalled on daily token budgets (about 200,000 tokens per model on this tier;
  run 5 was stopped with 199,638 of 200,000 used). A 10-case run with four judge metrics used most of one model's
  budget (`docs/KNOWN_LIMITATIONS.md`). Pacing (§161) spaces requests but cannot create quota, and retries wait at most 60 s
  per attempt, so a quota that resets in minutes or hours is not waited out.
* **The environment.** The development machine slept between steps and stalled long runs. That is unrelated to the code, and
  it is recorded because a reader looking at the wall-clock times of the stored run would otherwise wonder: the re-importable
  bundle of run 7 (`calibration/20261028-035657-qwen-volcanoes-30-b-7d604e.json`) records a start of 03:56:57 and a finish of
  04:40:54 UTC for 30 cases. The record attributes slow progress to quotas and to the sleeping machine; the bundle itself does
  not say how much of those 44 minutes was which.

### 160.6 What the live runs do not show

`docs/LIVE_VERIFICATION.md` ends with a "Not covered" list, repeated here because it is the boundary of every claim above.

* No run against OpenAI itself. Groq's service speaks the OpenAI protocol; that is not the same service, and differences in
  rate-limit headers, error bodies and model behaviour are exactly what the live runs were looking for.
* No tool-calling agent pipeline was run live.
* No API-embedding or API-hybrid retrieval was run live (the provider has no embedding models).
* Judge metrics other than `correctness` were measured on at most 10 cases, and there is only one judge-noise measurement.
* Judge scores were never compared with human labels (§163).
* Accessibility was checked by script and by one keyboard walk, not with a screen reader (§166).

## 161. Request pacing and `Retry-After`

### 161.1 Two ways to meet a rate limit

Release 1.1 taught the runner to retry a rate-limited call with exponential back-off (Part XIII). That recovers *after* the
limit is hit. A free tier or a shared key makes the limit easy to hit and slow to recover from, so release 1.3 adds two
mechanisms that work together:

| Mechanism | Acts | Where |
|---|---|---|
| **Pacing**: space operations evenly so the limit is not reached | before a call | `ratelimit.py` |
| **`Retry-After`**: when the limit is reached anyway, wait as long as the provider says | after a rejected call | `errors.py:27-34`, `:79-86` |

### 161.2 Pacing: `RateLimiter`

`RAGWB_MAX_REQUESTS_PER_MINUTE` (`config.py:79`; a number greater than 0 and at most 6,000, unset by default, meaning no pacing)
sets the budget. One *operation* is one answer generation or one judge-metric measurement, not one HTTP request: a judge
measurement can itself make several API calls (DeepEval's faithfulness metric extracts claims and then verifies them), so the
module docstring tells the user to set the limit below the provider's request quota divided by that fan-out
(`ratelimit.py:1-10`).

The mechanism is deliberately the simplest one that cannot burst. `RateLimiter(max_per_minute)` computes a fixed
`interval = 60 / max_per_minute` (`ratelimit.py:26`) and hands out slots one `interval` apart:

```python
with self._lock:
    now = self._clock()
    slot = max(now, self._next_slot)      # never earlier than the previous slot + interval
    self._next_slot = slot + self.interval
wait = slot - now                          # sleep outside the lock
```

(`ratelimit.py:36-43`). Three properties follow from those four lines, and each has a test.

1. **Even spacing.** Callers are served `interval` seconds apart (`tests/test_ratelimit.py:36`).
2. **No banked burst.** `slot` is never earlier than `now`, so time spent idle does not accumulate credit: after a long pause
   the first caller goes at once and the second waits one interval (`tests/test_ratelimit.py:42`).
3. **One budget for all threads.** The slot is claimed under a lock and the sleep happens outside it, so several workers
   share one budget without serialising their sleeping (`tests/test_ratelimit.py:57`).

The behaviour, run on a fake clock with a limit of 12 per minute (so `interval` is 5 s):

```text
interval 5.0
4 back-to-back callers wait: [0.0, 5.0, 5.0, 5.0]
after 100 s idle, next two wait: [0.0, 5.0]
```

The clock and the sleep function are injectable, so the tests never sleep for real. A limit of zero or less raises
`ValueError` (`ratelimit.py:24-25`), and the setting itself is validated when settings are loaded
(`tests/test_ratelimit.py:84`).

`limiter_for(max_per_minute)` keeps one limiter per distinct setting in a process-wide registry (`ratelimit.py:46-55`). That is
how answer generation and the judge metrics, which are constructed in different places, end up sharing one budget: both call
`limiter_for(settings.max_requests_per_minute)`. `tests/test_ratelimit.py:78` asserts it returns the same instance for the same
setting.

### 161.3 Where pacing is applied

| Operation | Acquires a slot | Code |
|---|---|---|
| Answer generation | before **every attempt**, retries included | `runner.py:240` |
| A judge-metric measurement | before every attempt in `JudgeMetric.score` | `metrics/judge.py:70-71`; the limiter is passed in by `build_judge_metric` (`metrics/judge.py:135`) and `build_metrics` (`metrics/__init__.py:45-50`) |
| `ragwb judge-noise` measurements | the same judge metrics, so the same limiter | §164 |
| API embeddings (`EmbeddingRetriever`) | **not paced** | `retrieval.py:127-179` has no limiter |

`tests/test_ratelimit.py:93` checks that a judge metric waits for its slot before each measurement. Taking a slot on every
*attempt* means a retry is also paced, so a burst of failures cannot turn into a burst of requests. API embedding calls are the
exception: they are made when the index is built and when a query is embedded, outside the runner's loop, and they are not
counted. On a provider whose embedding quota is the one that binds, pacing as it stands would not help.

### 161.4 `Retry-After` and the back-off formula

When a call is rejected with a transient error, the runner and the judge compute the wait with `backoff_delay`
(`errors.py:27-34`):

```text
delay = base * 2**(attempt - 1) + jitter(0, base)          # release 1.1 behaviour
if the provider sent Retry-After:  delay = max(delay, min(retry_after, 60))
```

where `base` is `RAGWB_RETRY_BASE_DELAY_S` (default 1.0), `attempt` counts from 1, and `jitter` is `random.uniform` by default so
that workers retrying together do not move in lockstep. `MAX_RETRY_AFTER_S = 60.0` (`errors.py:24`) caps the provider's hint:
a header asking for an hour is not allowed to hang a run for an hour.

The hint travels on the exception. `TransientProviderError` gained an optional `retry_after_s` (`errors.py:19-21`), filled by
`_retry_after`, which reads the `retry-after` response header of the SDK error, converts it to a float, and returns `None` for
a missing, non-numeric or non-positive value (`errors.py:79-86`). Computed with a deterministic jitter (the lower and upper
bound shown), for `base = 1.0`:

```text
attempt 1 no hint: 1.0 - 2.0
attempt 2 no hint: 2.0 - 3.0
attempt 3 no hint: 4.0 - 5.0
hint 5 attempt 1: 5.0
hint 30 attempt 1: 30.0
hint 120 attempt 1: 60.0
```

The hint only ever *lengthens* the wait: a hint shorter than the back-off is ignored, and one longer is honoured up to the cap.
`tests/test_retry_hints.py:79` asserts exactly this, and `:88` asserts that a judge waits for the provider's hint before
retrying. Header carriage and the unwrapping from §160.4 are tested at `:29`, `:37`, `:43`, `:53`, `:67` and `:72`: a header is
carried on the classified error; a rate limit hidden in a `RetryError` or a `raise ... from` chain is transient; a
transport-caused connection error is still transient; and unrelated or permanent errors stay what they were.

### 161.5 Honest limits

* **One limiter per process.** The registry is an in-memory dictionary. Two processes (a CLI run and the web app, or two CLI
  runs) each have their own budget and together can exceed the provider's.
* **Fan-out.** One operation is not one request. The user has to know how many API calls a judge metric makes and divide by it;
  nothing in the product measures that.
* **Request quotas versus token quotas.** Pacing counts operations. A provider that limits *tokens* per minute or per day is
  not protected by a requests-per-minute number; the module docstring says to tune the setting down until runs stop hitting
  429s (`ratelimit.py:7`), which is an experiment, not a calculation. The daily budget of run 5 is the clearest case: pacing
  could not have helped.
* **`Retry-After` as seconds only.** The HTTP date form of the header is not parsed (`float()` fails and the hint is dropped,
  `errors.py:83-85`), and the 60 s cap means a provider that asks for longer is retried sooner than it asked.
* **DeepEval's own retries** run underneath a judge measurement and are invisible to the limiter; the module docstring for
  `JudgeMetric` says so (`metrics/judge.py:51-53`).
* **API embeddings are not paced** (§161.3).

## 162. Local embeddings and `hybrid-local`

### 162.1 What was added

Two retrievers join `bm25`, `embedding` and `hybrid`:

| `--retriever` | What it does | Needs |
|---|---|---|
| `local` | cosine similarity between a query vector and chunk vectors from a **local** model | the optional `semantic` extra |
| `hybrid-local` | BM25 and `local` fused with reciprocal-rank fusion | the same |

`RetrieverName` is now `Literal["bm25", "embedding", "hybrid", "local", "hybrid-local"]` (`config.py:46`). The choices appear
in the CLI (`cli.py:491`), and in the New evaluation page when the package is installed (`ui/views/new_run.py:108-115`). The
extra is declared in `pyproject.toml:20-23` as `semantic = ["fastembed>=0.4"]` and install is `uv sync --extra semantic`;
the locked version is fastembed 0.9.1 (`uv.lock:694-695`). The base install does not change: without the package the retrievers
are refused with the install hint, before any run row is written (`pipeline.py:130-132`;
`tests/test_local_retrieval.py:82`).

### 162.2 One embedder interface, shared with the semantic metrics

Release 1.2 had already defined the interface for the two semantic metrics, and release 1.3 reuses it rather than inventing a
second one:

```python
class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...
```

(`metrics/semantic.py:38-39`). `FastEmbedEmbedder` implements it with a `fastembed.TextEmbedding` behind a lock, because one
ONNX session is shared by worker threads (`metrics/semantic.py:55-70`); `local_embedder(model_name, cache_dir)` returns one
per (model, cache directory) through `lru_cache(maxsize=2)` (`metrics/semantic.py:72-74`). Both consumers go through it:

* `LocalEmbeddingRetriever` takes an `embedder_factory` and calls it lazily (`retrieval.py:181-216`);
* `build_semantic_metric` takes the same kind of factory (`metrics/semantic.py:127-131`), and `build_metrics` passes
  `cache_dir=str(settings.local_model_dir)` (`metrics/__init__.py:42-43`).

The consequence is practical: one model download serves both the retriever and the metrics, tests substitute one stand-in
embedder for both, and a run that uses `hybrid-local` retrieval *and* the semantic metrics loads the model once. This is a
design choice, not a measured saving: no timing of the load is claimed here.

`LocalEmbeddingRetriever` is small. Construction loads nothing (`retrieval.py:190-198`); the first `retrieve` builds the
chunk vectors once, under a lock (`retrieval.py:200-206`); each query is embedded and every chunk scored with `cosine`, sorted
by `(-score, index)` so ties go to the earlier chunk and results are deterministic for a given model
(`retrieval.py:208-216`). `build_retriever` wires it in (`pipeline.py:130-136`): the model is
`config.embedding_model or settings.local_embedding_model`, the cache is `str(settings.local_model_dir)`, and `hybrid-local` is
`HybridRetriever(BM25Retriever(chunks), local)` with the defaults of release 1.1 (`rrf_k = 60`, a pool of `max(3k, 10)`
candidates per retriever; `retrieval.py:104-113`). The run configuration records `embedding_model` as the local model name for
these two retrievers (`cli.py:59-60`, `ui/views/new_run.py:203-204`), so a stored run says which model produced it.

### 162.3 The model cache, and a Windows path-length caveat

The first use downloads the model (default `BAAI/bge-small-en-v1.5`, set by `RAGWB_LOCAL_EMBEDDING_MODEL`, `config.py:72`) into
`<data dir>/models` (`config.py:113-115`) instead of a system temporary folder, so it sits with the rest of the project's
data; `test_model_cache_lives_under_the_data_dir` checks the wiring (`tests/test_local_retrieval.py:100`). After that the
model works with `HF_HUB_OFFLINE=1`, and nothing leaves the machine. `docs/BUILD_AND_RUN.md` puts the size of the download at
about 70 MB quantised.

The caveat is a Windows one and is recorded in `docs/KNOWN_LIMITATIONS.md`: the cache nests folders deeply and can exceed
Windows' 260-character path limit under a long data directory. It is the same failure family as defect 22 of Part X (a deep
install path breaking a compiled module). The practical advice is to keep `RAGWB_DATA_DIR` short. The live comparison itself ran with
`HF_HUB_OFFLINE=1`, that is, from the cache after the download.

### 162.4 The measured comparison

Run 9 compared the three retrievers that need no key, on all five bundled datasets, with the real local model, offline
provider and k = 3. Means over every case of each dataset; the semantic columns use the same local model. From
`docs/LIVE_VERIFICATION.md`:

| dataset | retriever | token F1 | context recall | semantic similarity | semantic context recall |
|---|---|---:|---:|---:|---:|
| honeybees | bm25 | 0.346 | 0.885 | 0.757 | 0.734 |
| honeybees | local | 0.340 | 0.792 | 0.725 | 0.714 |
| honeybees | hybrid-local | 0.376 | 0.870 | 0.758 | 0.734 |
| honeybees-paraphrased | bm25 | 0.225 | 0.664 | 0.715 | 0.733 |
| honeybees-paraphrased | local | 0.242 | 0.786 | 0.751 | 0.765 |
| honeybees-paraphrased | hybrid-local | 0.244 | 0.697 | 0.748 | 0.733 |
| volcanoes | bm25 | 0.199 | 0.660 | 0.648 | 0.638 |
| volcanoes | local | 0.203 | 0.738 | 0.652 | 0.650 |
| volcanoes | hybrid-local | 0.199 | 0.666 | 0.644 | 0.640 |
| coffee | bm25 | 0.257 | 0.765 | 0.659 | 0.636 |
| coffee | local | 0.271 | 0.801 | 0.663 | 0.644 |
| coffee | hybrid-local | 0.259 | 0.801 | 0.655 | 0.646 |
| lighthouses | bm25 | 0.212 | 0.819 | 0.630 | 0.634 |
| lighthouses | local | 0.230 | 0.835 | 0.634 | 0.639 |
| lighthouses | hybrid-local | 0.216 | 0.824 | 0.633 | 0.636 |

The differences from BM25 are easier to read than the table, so here they are, computed from it (local minus BM25, then
hybrid-local minus BM25; a positive number means the local retrievers scored higher):

| dataset | context recall: local | context recall: hybrid-local | token F1: local | token F1: hybrid-local |
|---|---:|---:|---:|---:|
| honeybees | −0.093 | −0.015 | −0.006 | +0.030 |
| honeybees-paraphrased | +0.122 | +0.033 | +0.017 | +0.019 |
| volcanoes | +0.078 | +0.006 | +0.004 | +0.000 |
| coffee | +0.036 | +0.036 | +0.014 | +0.002 |
| lighthouses | +0.016 | +0.005 | +0.018 | +0.004 |

### 162.5 The honest reading

The source record states the reading, and this section keeps to it: **there is no consistent winner.**

* `local` raised lexical context recall on four of five datasets: most on the paraphrased questions (0.664 to 0.786) and
  on volcanoes, coffee and lighthouses, and *lowered* it on the main honeybee set (0.885 to 0.792). The paraphrased set is
  the one where a word-overlap retriever is expected to struggle, so a gain there is the result one would hope for; the loss
  on the main set is the price.
* `hybrid-local` sat close to BM25 (within 0.04 of its context recall on every dataset) and gave the best token F1 on honeybees,
  0.376.
* Averaged over the five datasets with equal weight, `local` is +0.032 on context recall and +0.009 on token F1, and
  `hybrid-local` +0.013 and +0.011. Those means are arithmetic on the table, not a statistic: there are no confidence
  intervals, each dataset has 20 to 30 questions, and the paired comparison the product offers elsewhere (Part VI) was not
  applied to these runs.
* **The answers do not depend on the retriever.** The offline generator is the extractive baseline and answers the same way
  whichever chunks it is handed, so these tables describe *retrieval*, not answer quality. No claim about end-to-end quality
  follows from them.

What the experiment did establish is narrower and still useful: the local retrievers work with a real model on all bundled
datasets, with no key and no network after the download; and the choice between them and BM25 depends on the questions.

### 162.6 The high cosine floor, and the 0.7 default

The semantic metrics (`semantic_similarity`, `semantic_context_recall`) were run with a real model for the first time in the same
experiment, and the result is not flattering. Across the 15 rows above, semantic similarity lies between 0.630 and 0.758 and
semantic context recall between 0.634 and 0.765 (the record's summary: "between 0.63 and 0.76"), for answers that are
extractive quotations of the document. The reason is a property of the model: in a direct check, a paraphrase scored **0.847**
against **0.501** for an unrelated sentence. bge cosines have a high floor: unrelated text sits near 0.5, so the usable
spread between a poor and a good answer is compressed into the upper half of the scale.

The default pass threshold for both semantic metrics is 0.7 (`metrics/semantic.py:107-115`). With these numbers, a threshold of
0.7 sits inside the range occupied by ordinary extractive answers on these datasets, so it says almost nothing until it is
calibrated against human labels for *this* model. The semantic metrics are therefore now run-with-a-real-model but their
thresholds are **uncalibrated**, and `docs/KNOWN_LIMITATIONS.md` says the same. The direct check (0.847 versus 0.501) is
two sentences, not a distribution.

## 163. The labelling sheet and the calibration workflow

Judge scores are model opinions (Part VI §69.6), and the standing recommendation since release 1.1 has been to compare a judge
with a person (`ragwb labels-template`, `ragwb calibrate`, Part XIII §142.4). That comparison needs a person's labels, and release
1.3 did not have any. What it did was to make the comparison cheap to start and impossible to start by accident with invented data.

`calibration/` holds three files (`calibration/README.md`):

* `20261028-035657-qwen-volcanoes-30-b-7d604e.json`, run 7 as a re-importable bundle (30 cases, `qwen/qwen3.8-27b` generating and
  judging, `correctness` among the metrics; it contains no key: a search for key-shaped strings found none);
* `volcanoes-labelling-sheet.csv`, 30 rows with the columns `case_id, question, expected_answer, answer, token_f1_score,
  context_recall_score, groundedness_score, correctness_score, human_pass, note`;
* `README.md`, the instructions.

**No labels were fabricated.** The `human_pass` column is empty in all 30 rows (checked by reading the file for this book:
0 of 30 non-empty), and the README says in its first paragraph that "Nothing in it is a label". At the time of release there was therefore no
judge-versus-human result anywhere in this project (a comparison with an AI rater was added afterwards, §163.1), and the only calibration of the label-reading code is on synthetic labels in
the tests (`tests/test_calibration.py`).

The workflow the README prescribes is three steps, from the project folder:

1. Import the run into the local store: `uv run ragwb import calibration/20261028-035657-qwen-volcanoes-30-b-7d604e.json`.
2. Open the CSV (UTF-8) and, for each row, read the question, the reference answer and the model's answer, then enter `pass` or
   `fail` in `human_pass`; leave the row blank if you cannot decide. **Do not look at `correctness_score` first**, or the judge is
   being calibrated against itself. (The score columns are in the sheet for the analysis, not for the labeller.)
3. Compare: `uv run ragwb calibrate 20261028-035657-qwen-volcanoes-30-b-7d604e --labels calibration/volcanoes-labelling-sheet.csv --metric correctness`.

The report gives agreement, Cohen's kappa and a confusion matrix against the labels. With about 30 labelled cases it is a rough
estimate, and it describes this judge model, this rubric and this document only. A reader who wants a trustworthy figure needs
more cases, a second labeller and a stronger judge; that is future work item 1 in `docs/KNOWN_LIMITATIONS.md`.

### 163.1 A comparison with an AI rater, added after the release

At the owner's request Claude then labelled the 30 answers (`calibration/volcanoes-labels-by-claude.csv`), judging each answer
against its reference **before** looking at any metric score; a correct abstention counted as a pass. The result is 26 pass and
4 fail (v08 answered a different question; v20, v23 and v26 abstained although the text answers them). These are **not human
labels**: one rater, an AI model, who saw the reference answers. The calibration report, run with `ragwb calibrate`, gave:

| Metric | Cases compared | Agreement with the labels | Cohen's kappa | Metric pass rate | Label pass rate |
|---|---:|---:|---|---:|---:|
| Correctness (judge) | 30 | 0.967 | 0.870 (almost perfect) | 0.833 | 0.867 |
| Token F1 (lexical) | 30 | 0.600 | 0.237 (fair) | 0.467 | 0.867 |
| Groundedness (lexical) | 22 | 0.909 | 0.463 (moderate) | 0.864 | 0.955 |

The `correctness` judge agreed on 29 of 30 and caught all 4 of the labeller's fails; its single miss was v05, where it failed a
terse answer that the labeller passed. Token F1 passed only 14 of the 26 answers the labeller passed, which fits Part VI's account
of lexical metrics under-crediting paraphrase. The limits are the point: 30 cases, 4 failures, mostly easy cases and no
borderline answers, so the kappa is unstable and the comparison cannot show how the judge treats subtle errors. It supports "the
judge is not obviously unreliable on easy cases" and nothing stronger; the human sheet remains unfilled, and the full account is
`docs/LIVE_VERIFICATION.md` run 11.

## 164. Judge noise: how much does the judge disagree with itself?

### 164.1 Why the intervals are not enough

The bootstrap intervals in a run summary reflect *which questions were sampled*. They say nothing about call-to-call noise: the
same judge, given the same answer twice, can score it differently. A difference between two runs can therefore be smaller than
the judge's own jitter without the interval showing it (Part VI §71.3). `ragwb judge-noise RUN_ID` measures the jitter. It
re-uses the stored answers and contexts of a run, so neither retrieval nor generation is repeated; only the judge is called
(`judge_noise.py:1-15`).

### 164.2 Definitions

For each judge metric, over the cases that were answered (`status == "ok"` and a non-empty answer), the metric is evaluated
`repeats` times per case (default 3, at least 2, `cli.py:593`, `judge_noise.py:57`). Then:

| Quantity | Definition |
|---|---|
| **within SD** | the average, over cases, of the standard deviation of the repeated scores for the same case |
| **between SD** | the standard deviation, over cases, of the per-case mean scores: how much cases genuinely differ |
| **noise / signal** | within SD divided by between SD; above about 0.5 the judge's jitter is comparable to real differences between cases |
| **verdict flips** | the number of cases whose pass/fail verdict changed between repeats |

(`judge_noise.py:1-15`, `NoiseRow` at `:30-48`.) A measurement that fails is counted in an `errors` column and excluded; it is
never scored as zero (`judge_noise.py:55-93`, `tests/test_judge_noise.py:59`). A case needs at least two successful repeats to
count (`n_cases`); skipped cases are counted separately. `noise_to_signal` is `None` when the between SD is 0 or missing, and
`small_sample` is true below 10 usable cases (`MIN_RELIABLE_CASES = 10`, `judge_noise.py:26`).

**A worked example (illustrative; the numbers are made up and computed offline).** Four cases scored three times each, with a
pass threshold of 0.5:

```text
case  scores           mean    SD (within)
c1    0.9  0.7  0.8    0.800   0.100
c2    0.2  0.2  0.3    0.233   0.058
c3    0.5  0.4  0.6    0.500   0.100
c4    1.0  1.0  1.0    1.000   0.000
within SD  = mean of the four SDs      = 0.064
between SD = SD of the four means      = 0.337
noise/signal = 0.064 / 0.337           = 0.191
verdict flips at 0.5: c3 only (0.5 and 0.6 pass, 0.4 fails) = 1
```

Here the judge's jitter is about a fifth of the real spread between cases, so a mean difference between two runs of, say, 0.1
would not be explained by jitter alone, but the verdict on `c3` is unstable. Both facts matter, and the table reports both.

### 164.3 The command and its brake

`cmd_judge_noise` (`cli.py:197-219`) takes the run's judge metrics by default, or `--metrics`; refuses a run with none
("name some with --metrics"); prints how many judge measurements it is about to make (`repeats x metrics x cases`, "each of which
can make several API calls"); and, above `MAX_UNCONFIRMED_OPERATIONS = 30` (`cli.py:223`), refuses unless `--yes` is given
(`cli.py:207-210`). `--limit N` takes the first N cases. The measurements pass through the same limiter and retry logic as any
judge call (§161). `tests/test_judge_noise.py` covers a steady judge with zero within SD (`:42`), a noisy judge with flips (`:50`),
excluded failures (`:59`), skipped and failed cases (`:67`), the minimum of two repeats (`:74`), the explanatory report (`:79`),
the confirmation gate and a run with a stand-in judge (`:95`), and the no-judge-metrics message (`:105`). The report prints
notes for a small sample, for noise/signal above 0.5, for excluded failures and for a between SD of 0 (`judge_noise.py:95-116`).

### 164.4 The one measurement

Run 8 re-scored 10 cases of run 7 three times each for `correctness`: **within-case SD 0.023, between-case SD 0.371,
noise/signal 0.062, and 1 of 10 cases changed its pass/fail verdict between repeats.** For this judge, this model and this
rubric, the call-to-call jitter is small next to the real differences between cases.

### 164.5 What it does not show

* **Ten cases.** The tool itself flags fewer than ten usable cases as rough; ten is the minimum, not a comfortable sample.
* **One metric.** `faithfulness` and `context_relevancy` were not measured; faithfulness in particular makes several judge calls
  per measurement (it extracts claims and then verifies them), which is more room for variation than a single rubric score.
  A small noise figure for `correctness` is no evidence about them.
* **One judge, one rubric, one document.** The judge was a 27B model scoring its own output on volcano questions.
* **Noise is not validity.** A judge can be perfectly consistent and consistently wrong. Low jitter says nothing about
  whether the scores agree with a person; that is §163, and the labels do not exist yet.
* **The one flipped case** is the more actionable number for anyone using a pass/fail threshold: one case in ten changed its
  verdict from call to call, which is a reminder that a pass rate over a few cases is not stable.

## 165. Roles and session revocation

### 165.1 The permission matrix

Release 1.2 gave every signed-in user the same powers. Release 1.3 adds three roles, held in the users file
(`rag_workbench/users.py:31-32`: `ROLES = ("viewer", "editor", "admin")`, `DEFAULT_ROLE = "editor"`) and enforced in the page scripts through
one table (`ui/auth.py:34-39`):

| Action | viewer | editor | admin |
|---|:-:|:-:|:-:|
| Browse Overview, Run results, Compare runs, Data, Settings; see exports and downloads | yes | yes | yes |
| Start an evaluation (New evaluation page) | no | yes | yes |
| Edit a run's tags and notes | no | yes | yes |
| Delete a run | no | no | yes |

The code's own comment is the first line of the rule: viewing results, comparing and exporting are open to every signed-in user
(`ui/auth.py:34`); `PERMISSIONS` maps `viewer` to the empty set, `editor` to `{run, tag}` and `admin` to `{run, tag, delete}`.
Account management is not in the matrix at all: it is the CLI (`ragwb user ...`, §168), which anyone with a shell on the machine
can run, and there is no admin screen.

How the pages use the table:

* `ui/views/new_run.py:27-29`: for an account without `run` the page shows "Your account is read-only (viewer): it can browse
  results but not start evaluations." and calls `st.stop()` before any form is built.
* `ui/views/results.py:190`: `can_tag` and `can_delete` are computed once; the tags and notes inputs are disabled for a viewer
  and the save button is replaced by "Your account is read-only (viewer): tags and notes cannot be changed." (`:192-198`); the
  *Delete this run* expander shows "Deleting runs needs an admin account." for anyone but an admin (`:208-210`).
* The sidebar shows the role next to the name: "Signed in as **name** (role)" (`ui/auth.py:238`).

### 165.2 Defaults and the safe direction

Three rules decide what a role *is* when the data is unusual, and each fails toward less access:

1. **Accounts without a stored role count as `editor`.** Accounts created before release 1.3 have no `role` key; `role_of`
   returns `entry.get("role", DEFAULT_ROLE)` (`rag_workbench/users.py:115`). That keeps every existing account able to do what it could do
   before, which is the compatibility choice; an operator who wants stricter defaults has to run `ragwb user set-role`.
2. **An unrecognised role gets the least access, not the most.** A stored role that is not in `ROLES` (a typo, a hand-edited
   file) is returned as `viewer` (`rag_workbench/users.py:116`; `tests/test_roles.py:38`).
3. **A user who is not in the file has no role.** `role_of` returns `None` for an unknown or removed name, and for an unreadable
   file (`rag_workbench/users.py:107-114`). `current_role` turns that into `viewer` if it is reached (`ui/auth.py:211`), and `require_login`
   treats it as a removed account (below).

Without named accounts (no login at all, or the shared password) there are no roles: `current_role` returns `admin`, so everyone
has the full access they had before roles existed (`ui/auth.py:208-210`; `tests/test_roles.py:145`). Roles are a property of
named accounts only.

### 165.3 Read on every page load

The role is not cached in the session. `current_role` reads the users file on every call (`ui/auth.py:203-211`), and `can` is
called each time a page script renders (`ui/auth.py:214-216`). Two behaviours follow, both with a test:

* **A role change applies to an open session.** After `set_role("eddie", "viewer")`, the next rerun of the Results page shows the
  tags input disabled without signing in again (`tests/test_roles.py:133`).
* **Removing a user ends their open session.** Release 1.2 documented the opposite, as a limit (Part XIV §156.8): a removed
  user's session stayed valid until sign-out or restart. `require_login` now checks, for a session that is already signed in,
  that the account still exists, and if `role_of` returns `None` it logs "session ended: user ... no longer exists", clears the
  session keys and falls through to the login form (`ui/auth.py:136-148`). The next page load shows "Sign in with your account"
  (`tests/test_roles.py:124`). `ragwb user remove` now says "Any open session for this user ends on its next page load"
  (`cli.py:182`), and `ragwb user set-role` says that the change applies on the next page load (`cli.py:176`).

"Next page load" means the next Streamlit rerun, which is any interaction in the open page, not a wall-clock deadline.

### 165.4 Why UI-level enforcement is sufficient here

The roles are enforced in the page scripts, not in the storage layer, and not in the CLI. That would be inadequate in a design
where the client decides what to call. It is adequate in Streamlit's server-driven model for a reason worth spelling out,
because it is the whole argument.

In Streamlit, each page is a Python script that runs **on the server** on every interaction. The browser sends widget values;
it does not choose which Python code runs. A button exists only if the script, running for this session, executed the line that
creates it, and the code that acts on a click sits under that same line. For a viewer, the New evaluation script stops before
creating any form (`new_run.py:27-29`), and the Results script does not execute the branch that contains the save and delete
buttons (`results.py:197-198`, `:209-210`). The session's username is held in server-side session state (`USER_KEY`,
`ui/auth.py:40`), so a client cannot rewrite it. There is no HTTP endpoint through which a viewer could invoke a write, because
the application has no HTTP API (Part I §8). `tests/test_roles.py:78` asserts the visible half of this: for a viewer there is no
`start_run`, `save_meta` or `delete_run` button on the pages.

This is a reasoned argument about the framework's execution model, backed by AppTest journeys. It has **not** been attacked: there
was no penetration test, and anything that bypasses the page scripts bypasses the roles. The CLI is the obvious example. A person
with a shell and the data folder can run, tag, delete and change roles regardless of the table, which is consistent with the
product's stated model of one trusted team on one machine (Part XI).

### 165.5 What is still missing

* **No password reset.** A forgotten password is replaced by an operator with `ragwb user add NAME --replace`. (Release 1.4 added `ragwb user set-password`, an admin reset and a self-service change: Part XVI §173.3.)
* **No per-user separation of data.** Every signed-in user sees every run. (Release 1.4 added an optional, UI-level filter, `RAGWB_RUN_VISIBILITY=own`: Part XVI §173.4.) `started_by` on a run is attribution, not access
  control (Part XIV §156.4).
* **No admin screen for accounts.** Creating, removing and changing roles is CLI only. (Release 1.4 added an admin-only Accounts page and a last-admin guard: Part XVI §173.1-173.2.)
* **No audit trail of destructive actions.** Sign-ins and sign-outs are logged by username (Part XIV §156.3); the Results page
  writes no log line when a run is deleted (`results.py` has no logger call).
* **Role granularity.** Three coarse roles on a small action set (`run`, `tag`, `delete`). There is no "may export" or "may
  upload" role, and exporting is open to viewers by design.
* **Immediacy is per page load**, not per websocket message: a removed user's open page keeps showing what it already shows until
  the next rerun.

The tests that carry the claims of this section are `tests/test_roles.py` (10 tests): role storage and defaults (`:29`), unknown
roles (`:38`), `set_role` (`:54`), the CLI (`:63`), the three journeys (`:78`, `:95`, `:111`), removal and role change on open
sessions (`:124`, `:133`) and the no-accounts case (`:145`).

## 166. A keyboard accessibility walk

Release 1.2's accessibility check was a script over five pages and said so: keyboard use was "not tested" (Part XIV §158.3).
Release 1.3 closes one slice of that, and only one: a keyboard Tab walk of the **New evaluation** page in a browser
(run 10 in §160.2).

**What was done.** 40 Tab presses on the page. The order of focus was: a skip link first, then the sidebar links, then every form
control in visual order (the uploaders, the selects, the radio groups, the slider, the expanders, the run name field and the Run
button), and then back to the start. There was no trap and no hidden stop: every control was reachable from the keyboard.

**What a script flagged, and what was checked.** A script flagged 16 stops without an outline or box shadow. Streamlit styles
focus another way, so the flag is not a finding by itself; two of the 16, a sidebar link and a radio button, were checked
visually and show a visible focus indicator. The other 14 flagged stops were **not** checked. The honest summary is that 2 of
16 flagged stops were confirmed fine and 14 are unknown, not that all 16 are fine.

**What was not done.** The other pages were not walked. Screen readers were not used: announcement order, labels read aloud and
the behaviour of Streamlit's canvas-drawn tables are untested, and the canvas tables remain unreadable to a screen reader
by Streamlit's design (each has a CSV download as an alternative, Part XIV §158.3). **Corrected in release 1.4:** the tables are exposed through a parallel grid of `gridcell` elements, so they are not unreadable, but each cell is a Tab stop (Part XVI §177.2). Zoom and reflow were not tested. The
script's earlier flag that white-on-blue slider values measure 1.0:1 (Part XIV §158.3) was not resolved either.

The release therefore changes one word in the accessibility statement, from "keyboard not tested" to "keyboard walked on one
page", and no more. `docs/KNOWN_LIMITATIONS.md` words it the same way.

## 167. What is still unverified

These items remain open after release 1.3. They are the union of `CHANGELOG.md` ("Not verified"),
`docs/KNOWN_LIMITATIONS.md` and `docs/LIVE_VERIFICATION.md` ("Not covered"), and they replace the list of Part XIV §159.3 (which
is why several of its items are gone: the live-service calls and the real-model run of the semantic metrics are no longer on it).

1. **OpenAI itself.** Groq's service speaks the same protocol, and that is the extent of what was verified. Rate-limit headers,
   error bodies and model behaviour on OpenAI may differ. `scripts/live_smoke.py` has passed 12/12 against Groq (2 cases) and has
   never been run against OpenAI.
2. **The tool-calling agent pipeline**, live. It is tested with fakes only. (Release 1.4 ran it live on 3 cases: Part XVI §176.3.)
3. **API embeddings and hybrid retrieval with API embeddings.** The provider used had no embedding models. Other
   OpenAI-compatible providers (for example xAI Grok through `OPENAI_BASE_URL`) are supported by configuration only; DeepEval
   accepts a Grok model name at construction (checked offline), but nothing was sent to any provider.
4. **Judge-versus-human agreement.** Needs a person's labels; the sheet is waiting (§163). Until then the judge's scores are
   opinions with a measured jitter (§164) and no measured validity.
5. **The semantic metrics' thresholds.** Run with a real model; the 0.7 default is uncalibrated and the model's cosine floor makes
   it nearly uninformative (§162.6).
6. **Judge noise beyond one measurement:** one metric (`correctness`), ten cases, one judge.
7. **The Docker image** has never been built or run (no Docker was available). **A true wheel install** into a clean environment
   was not done in 1.3 (the unpacked wheel was run from a neutral folder, Part XIV §157.3); release 1.4 did it, Part XVI §176.1.
8. **Accessibility beyond the one keyboard walk**: the other pages, screen readers, zoom and reflow (§166).
9. **Judge cost** is whatever DeepEval reports as `evaluation_cost`; for the Groq endpoint it reported none, so the field has
   still never been compared with a real invoice. Judge token counts are not available.
10. **TLS** beyond a self-signed local certificate (Part XIV §156.6) and the HTTPS path under any real certificate.

**A checklist for trusting a 1.3 result.**

1. Everything in the 1.2 checklist (Part XIV §159.4) still applies.
2. A live result is trusted for the provider, models and sample that produced it, and is not carried to another provider.
3. A judge score is read with the judge's noise in mind: if `judge-noise` has not been run for that metric on that judge, the
   jitter is unknown, and a small difference between two runs is not evidence.
4. A semantic score is not compared with the 0.7 threshold until that threshold has been calibrated for that model.
5. A comparison between retrievers states the dataset and the number of questions, and does not infer an overall winner from
   a table like §162.4.
6. A free-tier run that hit quotas is read with the *Failed* column first: lost judge scores are excluded from the means, so a
   mean over fewer cases is wider than it looks.
7. A role is a convenience for a trusted team, not a security boundary against anyone with shell access.

## 168. Reference: commands, variables and files

### 168.1 New and changed commands, options, variables and files

| Item | Purpose | Where |
|---|---|---|
| `ragwb judge-noise RUN_ID [--repeats 3] [--metrics a,b] [--limit N] [--yes]` | re-score a run's stored answers to measure judge jitter; makes API calls | `cli.py:197-219`, parser `:477-484`, §164 |
| `ragwb user add NAME [--role viewer\|editor\|admin] [--replace] [--password-stdin]` | create an account with a role (default `editor`) | `cli.py:159-192`, parser `:469-476`, §165 |
| `ragwb user set-role NAME --role R` | change a role; applies on the next page load | `cli.py:170-177`, §165 |
| `ragwb user remove NAME` | remove an account; an open session ends on its next page load | `cli.py:178-183`, §165 |
| `ragwb user list` | list accounts with their roles | `cli.py:161-167` |
| `ragwb run --retriever local\|hybrid-local` | local dense retrieval, alone or fused with BM25 | `cli.py:523`, `pipeline.py:130-136`, §162 |
| `RAGWB_MAX_REQUESTS_PER_MINUTE` | pace answers and judge measurements; unset = no pacing; 0 < x ≤ 6000 | `config.py:79`, `:185`, `.env.example:60`, §161 |
| `RAGWB_LOCAL_EMBEDDING_MODEL` | local model for the semantic metrics and the local retrievers (default `BAAI/bge-small-en-v1.5`) | `config.py:72`, `:180`, `.env.example:56`, §162 |
| `<data dir>/models` | local model cache | `config.py:113-115`, §162.3 |
| `<data dir>/users.json` | account store; entries now carry `role` | `rag_workbench/users.py:91-105`, §165 |
| optional extra `semantic = [fastembed]` | install with `uv sync --extra semantic` | `pyproject.toml:20-23`, `uv.lock:694-695`, §162 |
| `HF_HUB_OFFLINE=1` | works after the one-time model download; not a project setting | `docs/BUILD_AND_RUN.md` |
| `calibration/` | labelling sheet, run bundle, instructions | §163 |
| `docs/LIVE_VERIFICATION.md` | the record of what was run live | §160 |

The CLI now has **23 commands**: the 22 of release 1.2 plus `judge-noise` (parser definitions `cli.py:485-618`); `user` gained
`set-role`. The Python surface that is new is `ratelimit.RateLimiter` and `ratelimit.limiter_for`, `errors.backoff_delay`, the
`retry_after_s` attribute of `TransientProviderError`, `retrieval.LocalEmbeddingRetriever`, `judge_noise.measure_noise`,
`format_noise` and `estimate_operations`, and `users.UserStore.role_of` and `set_role` with `ui.auth.can` and `current_role`.

### 168.2 New source files and tests

| File | Lines | Role |
|---|---:|---|
| `src/rag_workbench/ratelimit.py` | 55 | request pacing |
| `src/rag_workbench/judge_noise.py` | 116 | judge-noise measurement |
| `tests/test_local_retrieval.py` | — | 9 tests: ranking, laziness, pipeline wiring, install hint, a full `hybrid-local` run, model cache location, one opt-in real-model check |
| `tests/test_ratelimit.py` | — | 8 tests |
| `tests/test_retry_hints.py` | — | 8 tests |
| `tests/test_judge_noise.py` | — | 8 tests |
| `tests/test_roles.py` | — | 10 tests |
| `calibration/*` | — | labelling sheet, bundle, README |
| `docs/LIVE_VERIFICATION.md` | 116 | the live record |

Changed files: `config.py`, `retrieval.py`, `pipeline.py`, `errors.py`, `metrics/judge.py`, `metrics/semantic.py`,
`metrics/__init__.py`, `runner.py`, `cli.py`, `users.py`, `ui/auth.py`, `ui/views/new_run.py`, `ui/views/results.py`,
`pyproject.toml`, `uv.lock` and `.env.example` (Part V §V.55).

## 169. Verification, other changes, and how to read a 1.3 result

### 169.1 Verification

`docs/TESTING.md` records the final tree: **375 tests collected, 373 passed, 0 failed, 2 skipped** (the opt-in live test and the
opt-in real-model test, `tests/test_local_retrieval.py:107`); statement coverage **97 %** (3,375 statements, 118 missed;
`ui/views/*` is excluded from the measurement, Part IX §97.3); `ruff` and `mypy` clean over 46 source files. The 43 new tests
are the five files of §168.2. `pytest --collect-only -q` was re-run for this Part and reports 375 tests. The six steps of
`scripts/verify.py` are unchanged.

### 169.2 Other changes, and text that lags the code

* **The version** recorded in a run's environment block is now `1.3.0` (`src/rag_workbench/__init__.py:13`).
* **Transient-error messages** read "OpenAI-compatible API ..." (`errors.py:50`); a script that matched on "OpenAI RateLimitError"
  needs updating. The authentication message still names OpenAI (`errors.py:52`).
* **The New evaluation screenshots were not recaptured for release 1.3.** The page can now show the two local retrievers when
  the extra is installed (`ui/views/new_run.py:108-115`); the committed screenshots were taken without the extra and show BM25
  only. They are accurate for what they show, and this note is the only change to them.
* **Text in the source that still describes the previous state.** The module docstring of `users.py` still said "there are no
  roles" (`rag_workbench/users.py:5`), and Part XIV §156 quotes it as it was; the README's access paragraph still says there are no roles;
  `INSTALL_HINT` still suggests `uv pip install fastembed` (`metrics/semantic.py:34`) although the extra is the documented route.
  These are wording lags, not behaviour. (Release 1.4 updated the `users.py` docstring to mention roles; it is now "roles are coarse".)

### 169.3 How to read a 1.3 result

A 1.3 run is the same record as a 1.2 run, with `embedding_model` set to the local model for the two local retrievers. A
result with judge metrics should be read together with its failed counts and, where it matters, a `judge-noise` figure. A
result produced by a free-tier provider should be read together with the quota and the sleeping-machine notes of §160.5: a
slow or partial run says as much about the service tier as about the code.
