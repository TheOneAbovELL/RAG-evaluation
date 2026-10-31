# Part XIII — Release 1.1: from working tool to production-grade tool

Release 1.0 answered the question "can a retrieval-augmented pipeline be evaluated, stored and compared on one
machine, offline?" Release 1.1 (version `1.1.0`, `src/rag_workbench/__init__.py:13`) asks a harder one: *would you
trust this tool with a real evaluation, a real budget and a real team?* This Part explains what changed, why, how the
new pieces work, how to use them, and — as in the rest of the book — where they stop being reliable. Line
references point at the source as of release 1.1 and have been re-checked against the current tree, so a few describe code that release 1.2 later extended (Part XIV); every number is either quoted from `docs/TESTING.md`, `CHANGELOG.md` or
`docs/KNOWN_LIMITATIONS.md`, or comes from a command whose output is shown here.

**What did not change.** The default behaviour of the product is the same. The changelog records that the five
example runs (86 cases in total) score identically under 1.0.0 and 1.1.0; the storage schema is still version 2
(it became 3 in release 1.2, Part XIV §152.2); the new `RunConfig` fields all have defaults (`models.py:134-137`), so a run stored by 1.0 still
loads. Everything below is opt-in or additive, with two exceptions that are deliberate bug-fixes and are listed in
§149.

## 140. Motivation: what "production-grade" means for an evaluation tool

An evaluation tool is not a web service with customers, so "production-grade" does not mean horizontal scaling or
five-nines availability. It means the tool can be *relied on to be right, to be recoverable, and to be safe to leave
running*. Five properties follow, and each one is a section of this Part.

| Property | The failure it prevents | Release 1.1 answer | Section |
|---|---|---|---|
| **Reliability** | One stuck network call freezes a 500-case run; a rate-limited judge call throws away an answer that was already paid for; nobody knows what a run cost | Per-case time limit, judge retry with jitter, judge cost capture, prices stored with the run | §141 |
| **Trust in the metrics** | A metric looks precise but nobody has checked that it agrees with a person; a refused answer and a wrong answer score the same; a headline average hides a failing sub-population | Hybrid retrieval, evidence-based abstention, heading skipping, slice breakdowns, human-label calibration with Cohen's kappa | §142 |
| **Operations** | The run store is corrupt and nobody notices; there is no copy before a risky cleanup; an old experiment cannot be repeated | `doctor`, `backup`, `prune`, `rerun`, `--version` | §143 |
| **Security** | The app is started on `0.0.0.0` with a paid API key behind it and no password | Optional shared password with constant-time comparison and a lockout; the launcher refuses to expose the app without one; JSON logs that stay redacted | §144 |
| **Verification** | "It works on my machine" — with no lint, no type check, no vulnerability scan, no idea how it behaves at 5,000 cases | Static analysis gates, an optional dependency audit, a scale benchmark, a guarded live smoke script | §145, §146 |

Two design rules run through all of it, and they are the same rules that shaped release 1.0:

1. **Never hide missing data.** A timed-out case is an `error`, not a zero; an unknown cost is `None`, not `0.0`; a
   correlation that cannot be computed (`kappa` with a constant rater) is `undefined`, not `1.0`.
2. **Say what was and was not verified.** The OpenAI, embedding, agent and DeepEval paths are still tested with fakes
   only; no live call had been made from this project when this Part was written (release 1.3 later made a narrow one, Part XV §160). §147 collects what remained unverified at release 1.1.

## 141. Reliability

### 141.1 The per-case time limit

**Problem.** Release 1.0 bounded each *HTTP request* (`request_timeout_s`, default 60 s) and retried transient
failures, but nothing bounded a *case*. A case is several requests: one or more generation attempts, then up to
four judge metrics, each with their own requests and retries. A library that blocks inside a socket read, a deadlock
in a dependency, or simply a very slow provider could hold a run indefinitely; in a pooled run one stuck worker
silently lowers throughput, and in a sequential run it stops everything.

**Design.** `RAGWB_CASE_TIMEOUT_S` (default 600 s, allowed range greater than 0 and at most 3,600; `config.py:75`)
is a wall-clock limit for one case, generation plus scoring. It is copied into every run configuration
(`models.py:134`, the CLI at `cli.py:62`, the UI at `new_run.py:205`), so it is stored with the run and a rerun uses
the same limit.

The implementation is `EvaluationRunner.evaluate_case` (`runner.py:184-206`):

```python
        limit = prepared.config.case_timeout_s
        outcome: list[CaseResult] = []

        def work() -> None:
            outcome.append(self._evaluate_case_guarded(prepared, case, position))

        worker = threading.Thread(target=work, name=f"case-{case.id}", daemon=True)
        worker.start()
        worker.join(limit)
        if worker.is_alive():
            log.error("Case %s exceeded the %.0f s time limit and was abandoned", case.id, limit)
            return CaseResult(case_id=case.id, position=position, question=case.question, metadata=case.metadata,
                              expected_answer=case.expected_answer, status="error",
                              error=f"Case exceeded the {limit:g} s time limit and was abandoned "
                                    "(raise RAGWB_CASE_TIMEOUT_S if your provider is slow)")
        return outcome[0]
```

(`runner.py:191-206`.) The case body runs in a *daemon* thread; the caller waits for it with `join(limit)`. If the
thread is still alive afterwards, the runner records an `error` result that names the limit and the variable to raise,
and moves on. The error message is what the user sees in the Cases tab.

**Rationale for a thread.** Alternatives considered: `signal.alarm` (Unix only, main thread only — useless on Windows
and inside Streamlit), `concurrent.futures` with a timeout (the executor's context manager still waits for the stuck
task on exit), and a subprocess per case (it would isolate the hang but would need to serialise the pipeline, the
metrics and the retriever into the child; too heavy). A daemon thread is the smallest mechanism that works on every
platform and lets the *caller* regain control.

**The caveat, stated plainly.** Python cannot kill a thread. The docstring says so (`runner.py:187-189`): "an
abandoned call may still finish in the background; its result is discarded." Consequences, all real:

* The abandoned call keeps running until its own HTTP timeout. It may still consume rate-limit budget and, with a paid
  provider, may still be billed.
* The thread holds whatever it holds (a connection, memory) until it ends. A pathological provider that hangs every
  request could accumulate abandoned daemon threads during a long run.
* Because the thread is a daemon, it cannot keep the interpreter alive at exit.
* The limit measures wall-clock time and does not know about retries: with defaults (`max_retries` 3, 60 s request
  timeout) one generation can legitimately take about four minutes before the judge starts, so 600 s is generous but
  not infinite. If your provider is slow, raise the limit; if it is fast and you want a tight failure bound, lower
  it.
* The default (600 s) is deliberately below the 15-minute window after which a silent `running` run is considered
  dead (`storage.py:27-29`), so a single abandoned case cannot, by itself, make a live run look interrupted.

**How it is tested.** `test_a_hung_case_is_abandoned_after_the_time_limit` (`tests/test_runner.py:178`) installs a
pipeline whose `answer` blocks on a `threading.Event` for the first question, runs with `case_timeout_s=0.3`, and
asserts that the case is an `error` mentioning the time limit, that the run is `partial`, that the other three cases
are `ok`, and that the whole run took under ten seconds although the hung call was still blocked. It proves the run
*moves on*; it cannot prove anything about what the abandoned provider call does afterwards.

**Using it.** `RAGWB_CASE_TIMEOUT_S=120 ragwb run ...` or the `case_timeout_s` field in the stored configuration.
The Configuration tab of a finished run shows it.

### 141.2 Judge retry with exponential back-off and jitter

**Problem.** The generator path already retried transient provider errors (`runner.py:234-252`, Chapter 57), but the
four DeepEval judge metrics did not: a single 429 from the judge model turned a perfectly good answer's metric into
an `error` result for that case. On a rate-limited account a judged run could lose many metric values to a problem
that a two-second wait would have solved.

**Design.** `JudgeMetric` (`metrics/judge.py:48-54`) now wraps its measurement in a retry loop
(`metrics/judge.py:66-78`):

```python
    def score(self, inp: MetricInput, threshold: float) -> ScoreOutcome:
        attempt = 0
        while True:
            try:
                return self._measure(inp, threshold)
            except TransientProviderError as exc:
                attempt += 1
                if attempt > self.max_retries:
                    raise
                delay = self.retry_base_delay_s * 2 ** (attempt - 1) + random.uniform(0, self.retry_base_delay_s)
                log.info("Judge %s: transient error (%s); retry %d/%d in %.1fs", self.name, exc, attempt,
                         self.max_retries, delay)
                self._sleep(delay)
```

* `_measure` (`metrics/judge.py:82-99`) builds a fresh DeepEval metric, calls it, and maps any OpenAI exception through
  `classify_openai_error` (`metrics/judge.py:90-94`), so the same classification that governs generation also governs
  judging: rate limits, timeouts, connection errors and 5xx are `TransientProviderError`; authentication and other
  errors are permanent.
* Only transient errors are retried. A permanent error — a rejected key, a malformed request — propagates immediately
  to `Metric.evaluate`, which records it as a metric `error` (`metrics/base.py:86-89`).
* The delay is `base × 2^(attempt−1)` plus a uniform random amount in `[0, base]`. With `retry_base_delay_s = 1`, the
  waits are 1–2 s, 2–3 s, 4–5 s.
* The attempt budget is the run's `max_retries` (`runner.py:95-96` passes it to the metric factory; default 3).

**Why jitter.** With several workers and a shared rate limit, a burst of 429s makes every worker sleep the same
deterministic interval and then retry *simultaneously*, producing another burst — the "thundering herd". Adding a
random component spreads the retries out. It costs nothing in the average case. The same jitter is applied to the
generator retry (`runner.py:244-245`).

**Why the sleep is injectable.** `JudgeMetric.__init__` takes a `sleep` callable (`metrics/judge.py:56-62`) so tests
record delays instead of waiting: `test_judge_retries_transient_errors_with_backoff` (`tests/test_metrics.py:177`)
and `test_judge_gives_up_after_the_retry_budget_and_does_not_retry_permanent_errors` (`tests/test_metrics.py:188`).

**Honest limits.** DeepEval and the OpenAI client may apply their own retry policy underneath (the class docstring
says so, `metrics/judge.py:51-53`), so the worst-case number of HTTP requests per metric can be larger than
`max_retries + 1`. We had not observed this against a live provider when this Part was written because no live call had been made (release 1.3 saw it against Groq's free tier, Part XV §160). And a
retry repeats a whole measurement: a DeepEval metric makes several model calls, so a transient failure in the last of
them repeats all of them — a cost, not a correctness problem.

### 141.3 Judge cost capture and stored prices

**Problem.** Release 1.0 recorded generator tokens and, when prices were configured, generator cost, but it ignored
the cost of the judge. For a judged run the judge is usually the larger share of the spend, so the reported number
understated the truth (the old limitation in Chapter 49).

**Design.**

* DeepEval metric objects expose an `evaluation_cost` attribute after `measure`. `_measure` reads it defensively
  (`metrics/judge.py:97-99`): `float(cost) if isinstance(cost, int | float) else None`. A missing or non-numeric value
  stays `None`.
* The score tuple may now carry a third element, the cost (`ScoreOutcome`, `metrics/base.py:54`); `Metric.evaluate`
  stores it on the result as `MetricResult.cost_usd` (`metrics/base.py:92`, `:97-98`; `models.py:79`).
* `summarize_run` sums the per-metric costs of successful cases into `RunSummary.total_judge_cost_usd`
  (`aggregate.py:82`, `:91`; `models.py:181`). If no case has a cost, the total is `None`, not `0.0`.
* The prices used for generator cost are now stored *with the run*: `RunRecord.config["prices_usd_per_mtok"]`
  (`runner.py:114`, `:254-256`), holding `{"input": ..., "output": ...}` in USD per million tokens. Prices change; a
  cost figure is only interpretable together with the price that produced it. `test_prices_are_stored_with_the_run`
  (`tests/test_runner.py:203`) checks both the priced and the unpriced case (`None`).
* `test_judge_cost_is_aggregated_per_run` (`tests/test_metrics.py:204`) checks the aggregation with a fake metric.

**Limits.** The judge figure is "whatever DeepEval reports as `evaluation_cost`" (`docs/KNOWN_LIMITATIONS.md`). It is
unverified against a live call, and judge *token counts* are not available at all. Generator cost still needs the
prices to be configured (`RAGWB_PRICE_INPUT_PER_MTOK`, `RAGWB_PRICE_OUTPUT_PER_MTOK`); the default is unset so that
cost is reported as unknown rather than guessed (`config.py:82-83`). Treat every cost in this tool as an estimate to
be reconciled with the provider's invoice.

## 142. Evaluation quality

### 142.1 Hybrid retrieval by reciprocal-rank fusion

**Problem.** BM25 matches words; embeddings match meaning. Each fails where the other succeeds ("parasite" versus
"varroa mite" is a vocabulary gap that BM25 cannot cross; an exact part number is something an embedding may blur).
Combining them usually beats either, but their scores are on incompatible scales: a BM25 score is an unbounded sum of
IDF-weighted terms, a cosine similarity lies in [-1, 1]. Normalising and weighting the two is a tuning problem.

**Design.** `HybridRetriever` (`retrieval.py:94-124`) side-steps scale entirely by fusing *ranks*, using reciprocal
rank fusion (Cormack, Clarke and Buettcher, 2009). Each retriever contributes `1 / (rrf_k + rank)` for every chunk in
its top `pool` results, and a chunk's fused score is the sum:

```python
        pool = max(k * self.pool_factor, 10)
        fused: dict[str, float] = {}
        ...
        for retriever in (self.lexical, self.dense):
            for hit in retriever.retrieve(query, pool):
                fused[hit.chunk_id] = fused.get(hit.chunk_id, 0.0) + 1.0 / (self.rrf_k + hit.rank)
                best.setdefault(hit.chunk_id, hit)
                first_seen.setdefault(hit.chunk_id, len(first_seen))
        order = sorted(fused, key=lambda cid: (-fused[cid], first_seen[cid]))[:k]
```

(`retrieval.py:113-122`.) Parameters: `rrf_k = 60` (the constant from the original paper; it damps the advantage of
being first) and `pool_factor = 3`, so each retriever is asked for `max(3k, 10)` candidates (`retrieval.py:104-113`).
Ties break by first appearance, so results are deterministic. The retriever is a drop-in for the `Retriever` protocol
(`retrieval.py:34-37`), and `build_retriever` constructs it when `config.retriever == "hybrid"`
(`pipeline.py:141-142`), after the same API-key check as the embedding retriever (`pipeline.py:137`).

**Worked example** (this is the stub in `test_rrf_fusion_matches_the_formula_and_prefers_agreement`,
`tests/test_evaluation_options.py:115`). Let the lexical retriever rank `a, b, c` and the dense retriever rank
`c, b, d`, with `rrf_k = 60`:

| Chunk | Lexical rank | Dense rank | Fused score | Result |
|---|---:|---:|---|---:|
| `c` | 3 | 1 | 1/63 + 1/61 = 0.015873 + 0.016393 = 0.032266 | 1 |
| `b` | 2 | 2 | 1/62 + 1/62 = 0.032258 | 2 |
| `a` | 1 | — | 1/61 = 0.016393 | 3 |
| `d` | — | 3 | 1/63 = 0.015873 | 4 |

`c` and `b` are the chunks both retrievers like, so they outrank `a` and `d`, each of which has a single vote — even
though `a` was the lexical retriever's first choice. Note how small the gap between `c` and `b` is: RRF is a
consensus mechanism, not a calibrated probability.

**Using it.** `ragwb run --retriever hybrid` (it needs `OPENAI_API_KEY`; without one the run is refused during
preparation with a message naming the retriever, `pipeline.py:175-178`), or the *Hybrid (BM25 + embeddings)* option on
the New evaluation page (`new_run.py:108-112`), which is offered only when a key is configured.

**Honest limits.** Hybrid retrieval has been evaluated only with `DeterministicFakeEmbedding` in tests
(`docs/KNOWN_LIMITATIONS.md`, future work item 3): the fusion arithmetic is verified, the *quality* benefit on real
embeddings is not. RRF ignores the magnitude of the scores, so a very confident BM25 match and a barely-ranked one
count the same. And the cost is that hybrid runs make embedding calls like the embedding retriever does.

### 142.2 Evidence-based abstention (`min_evidence`) and heading skipping

**Problem.** The offline generator is an extractive baseline (`providers.py:37-88`). In 1.0 it abstained only when no
retrieved sentence shared a content word with the question, and on the bundled unanswerable questions *every* question
shares some content word with the document ("honey", "colony"), so it never abstained. A baseline that never says "I
do not know" cannot be used to test whether the metrics reward abstention, and it makes the "unanswerable" run look
like pure failure.

**Design.** `ExtractiveGenerator` takes `min_evidence` in [0, 1] (`providers.py:47-48`, validated at `:51-52`).
When it is above 0, after choosing its best sentences the generator computes (`providers.py:82-86`):

```python
            wanted = sum(self.idf.get(t, self.default_idf) for t in q_terms)
            covered = sum(self.idf.get(t, self.default_idf) for t in set().union(*(c[3] for c in best)))
            if wanted <= 0 or covered / wanted < self.min_evidence:
                return GeneratorOutput(answer=ABSTAIN_ANSWER)
```

That is: the IDF-weighted share of the question's content terms that the chosen sentences actually contain. A
rare term the question asks about and the passage lacks ("flowers", "species") counts heavily against the answer; a
common word counts little. Below the threshold the generator returns the standard abstention sentence
(`prompts.py`), which `text.is_abstention` recognises, so the abstention-aware metrics (`context_recall` and
`groundedness` skip abstained answers) treat it as a refusal, not as a wrong answer.

The field is part of `RunConfig` (`models.py:136`), the CLI (`--min-evidence`, `cli.py:547-548`) and the New
evaluation page's *Advanced* expander (`new_run.py:156-160`, offline provider only); `build_pipeline` passes it to the
generator (`pipeline.py:159-161`).

**Skipping headings.** Why a second option? The PDF's title ("Honeybee Colonies") is a one-line chunk with no sentence
punctuation. It is retrievable, it matches a question like "Which parasite threatens honeybee colonies?" on the word
*colonies*, and the extractive generator can then quote it. `--skip-headings` removes such chunks *before indexing*
(`pipeline.py:150-151`). The heuristic (`documents.py:68-84`): a block is a heading if it has 1–12 words
(`HEADING_MAX_WORDS`) and does not end in `. ! ? : ; " ” )`. `drop_headings` keeps all chunks if every chunk would
be dropped, so a document of short unpunctuated lines does not become empty.

**The measured trade-off.** The following was run for this book on 2026-10-28 against
`examples/datasets/honeybees_unanswerable.jsonl` (four unanswerable questions `u1`–`u4`, two answerable controls `a1`
and `a2`), using a temporary data directory (`RAGWB_DATA_DIR`) so the real `data/` was untouched, with the default
`k = 3` and BM25 retrieval:

| `--skip-headings` | `--min-evidence` | Abstained on | Token F1 (mean of 6) |
|---|---:|---|---:|
| off | 0 | nothing | 0.039 |
| off | 0.3 | `u1`, `u2`, **`a2`** | 0.373 |
| off | 0.5 | `u1`, `u2`, **`a2`** | 0.373 |
| off | 0.7 | `u1`, `u2`, `u3`, `u4`, **`a2`** | 0.698 |
| off | 0.9 | all six, including **`a1`** | 0.667 |
| on | 0 | nothing | 0.039 |
| on | 0.3 | `u1`, `u2` | 0.373 |
| on | 0.5 | `u1`, `u2`, **`a2`** | 0.373 |
| on | **0.7** | `u1`, `u2`, `u3`, `u4`, **`a2`** | 0.698 |
| on | 0.9 | all six, including **`a1`** | 0.667 |

(Bold marks a wrong abstention on an answerable control.) The row to remember is *skip-headings on, min-evidence
0.7*: the generator abstains on **all four** unanswerable questions — and also on the answerable control question
`a2` ("Which parasite threatens honeybee colonies?", reference "The varroa mite."), while still answering `a1`. At
0.9 it abstains on `a1` too. The token-F1 jump from 0.039 to 0.698 is real arithmetic but must be read carefully: for
the unanswerable cases the *reference answer is the abstention sentence*, so abstaining is an exact match; the metric
is rewarding the behaviour the dataset asks for, not "better answers". The cost of that behaviour is visible in the
bold entries.

The second lesson is that the heading switch is not free either: at 0.3 it changes which questions abstain, because
removing the title chunk removes a chunk that happened to contain the question's own words and therefore inflated the
evidence share.

**Reading the result.** `min_evidence` is a crude proxy for "the retrieved passages answer this question". It cannot
distinguish a question the document answers in different words (`a2` — "parasite" versus "varroa mite") from one it
does not answer at all, because both look like "the question's words are missing from the passage". That is why
`docs/KNOWN_LIMITATIONS.md` says it "trades missed answers for fewer wrong ones and must be tuned on your own data".
It is shipped *off* (`0.0`) so results stay comparable with 1.0.

### 142.3 Slice breakdowns

**Problem.** A run-level mean of 0.35 can hide a split: 0.9 on the cases the document answers and 0.0 on the ones it
cannot, or the reverse. Aggregates answer "how good overall?"; engineers need "good *where*?".

**Design.** Dataset rows may carry a `metadata` object (already supported in 1.0, `datasets.py`). `slice_results`
(`aggregate.py:113-127`) groups a run's cases by `metadata[key]` and summarises each group with the same function that
summarises a whole run (`summarize_metric`, `aggregate.py:47`):

* values are compared as text, so `1` and `"1"` share a slice;
* cases without the key form a `(missing)` slice that is listed last (`aggregate.py:95`, `:124`);
* `metadata_keys` (`aggregate.py:108-110`) lists the keys present on at least one case.

Two front ends use it. `ragwb slices RUN_ID --by FIELD` (`cli.py:370-389`) prints a table; the Run results page
shows *Break down by dataset metadata* under the Summary tab whenever the run has metadata
(`ui/views/results.py:91-102`). On the bundled unanswerable dataset the field is `type`:

```text
$ ragwb slices 20261027-193739-slices-demo-3e6b4c --by type
slices-demo [20261027-193739-slices-demo-3e6b4c] by type
slice                    cases   ok            Token F1             ROUGE-L  Context recall (le  Groundedness (lexi
answerable                   2    2     0.094       (2)     0.094       (2)     1.000       (2)     1.000       (2)
unanswerable                 4    4     0.012       (4)     0.012       (4)         -       (0)     1.000       (4)
(n scored in brackets; small slices have wide uncertainty)
```

(Output of the command above, run for this book against a temporary data directory.) The dash in the unanswerable
row's *Context recall* column is not a zero: the metric is skipped when the reference answer is an abstention, so
`n scored` is 0 and no mean exists — the "missing is not zero" rule applied to a slice. The same view in the UI:

![Run results, Summary tab: metadata slices of the unanswerable run](../screenshots/12-slices.png)

*Screenshot 12 — `unanswerable-k3`, Summary tab, "Break down by dataset metadata".*

**Limits.** Slices of two cases (the answerable slice here) have enormous uncertainty; the table prints the scored
count in brackets for exactly that reason, and the UI caption repeats the warning (`results.py:102`). Slices do not
carry confidence intervals in the CLI table. A slice is a descriptive tool, not a significance test.

### 142.4 Calibration against human labels

**Problem.** A judge metric is a model's opinion under a rubric. Before basing a decision on `faithfulness >= 0.7` one
should know how often that verdict agrees with a person. Release 1.0 said "judge scores are opinions" but offered no way
to measure *how good* an opinion.

**Design.** `calibration.py` compares one metric's pass/fail verdicts on one run with human pass/fail labels for the
same cases and reports agreement. The workflow is two commands and one human step:

```text
ragwb labels-template RUN_ID --out sheet.csv          # one row per case, blank human_pass column
(a person fills human_pass with pass/fail)
ragwb calibrate RUN_ID --labels sheet.csv --metric correctness
```

* `labelling_sheet` (`calibration.py:248-260`) writes a CSV with the evidence a labeller needs — question, reference
  answer, the system's answer (or its error) and every metric's score — and an empty `human_pass` column. Cells that
  start with a spreadsheet formula character are prefixed with an apostrophe (`calibration.py:33`, `:213`), the same
  protection the CSV export has.
* `load_labels` (`calibration.py:54-88`) reads `.csv` (`case_id,human_pass`) or `.jsonl`, accepts `pass/fail`,
  `true/false`, `yes/no`, `1/0` (`calibration.py:31-32`, `:40-51`), skips blank labels (the case is unlabelled), and
  rejects duplicate ids, missing columns, unknown spellings and files over 5 MB with the offending line number.
* `calibrate` (`calibration.py:179-200`) builds the 2×2 table against the metric's *own* `passed` flag (threshold
  included). A labelled case the metric did not score (skipped, errored, or a failed case) is counted separately as
  `n_unscored`, not as a disagreement; labels for ids that are not in the run are counted as `n_unknown`.

**Cohen's kappa.** Raw agreement is misleading when one verdict dominates: if humans pass 95 % of cases, a metric that
passes everything agrees 95 % of the time and knows nothing. Kappa corrects for the agreement expected by chance
(`calibration.py:156-165`):

> κ = (p_observed − p_expected) / (1 − p_expected)

where `p_observed` is the share of cases on which metric and human agree and `p_expected` is the agreement two
independent raters with the same pass rates would have by luck.

**Worked example, by hand** (the numbers of `test_kappa_hand_computed`, `tests/test_calibration.py:30-33`). Fifty
cases are labelled. The confusion table, with the human label as the reference:

| | Human: pass | Human: fail | Row total |
|---|---:|---:|---:|
| **Metric: pass** | 20 (tp) | 5 (fp) | 25 |
| **Metric: fail** | 10 (fn) | 15 (tn) | 25 |
| **Column total** | 30 | 20 | 50 |

1. Observed agreement: (20 + 15) / 50 = **0.7**.
2. The metric passes 25 of 50 (0.5) and fails 25 (0.5); the human passes 30 (0.6) and fails 20 (0.4). The chance that
   both say "pass" is 0.5 × 0.6 = 0.30; that both say "fail" is 0.5 × 0.4 = 0.20. Expected agreement = **0.5**
   (the code computes `((tp+fp)(tp+fn) + (fn+tn)(fp+tn)) / n²` = (25·30 + 25·20) / 2,500 = 0.5).
3. κ = (0.7 − 0.5) / (1 − 0.5) = **0.4**.

The verbal bands of `interpret_kappa` (`calibration.py:168-176`, after Landis and Koch, 1977) are: up to 0 poor, below
0.2 slight, below 0.4 fair, below 0.6 moderate, below 0.8 substantial, otherwise almost perfect. A kappa of exactly
0.4 sits on the boundary between "fair" and "moderate"; floating-point arithmetic yields 0.3999999999999999, so the
code prints "fair". That boundary case is a good reminder that the bands are a convention, not a test of validity. Other quantities from the same table: accuracy 0.7, precision 20/25 = 0.8 (of what the metric passes, humans also
pass 80 %), recall 20/30 ≈ 0.667 (of what humans pass, the metric catches two thirds). Here 50 labelled cases exceed
`MIN_RELIABLE_N = 30` (`calibration.py:29`), so no small-sample warning is printed.

I ran `cohen_kappa(20, 5, 10, 15)` for this book: it returns 0.3999999999999999 and `interpret_kappa` returns `fair`.

**When kappa is undefined.** If either rater is constant (everything passes), `p_expected` is 1 and the formula
divides by zero; the code returns `None`, and the CLI prints `n/a` (`calibration.py:163-164`;
`tests/test_calibration.py:39-41`). Perfect agreement gives 1, perfect disagreement −1, chance level 0.

**Limits, all printed or documented.** Kappa depends on the pass rate, so a skewed sample gives a low kappa even for
good agreement; below 30 compared cases the CLI says "treat kappa as indicative only" (`cli.py:348-349`); one run, one
dataset and one judge model say nothing about other settings (module docstring, `calibration.py:14-16`). And the
hardest limit: **no judge-versus-human calibration has been run on real labels** — there are no real judge scores in
this project when this Part was written, because no live judge call had been made (release 1.3 ran the judge live but still has no human labels, Part XV §163). The tooling is tested with synthetic labels only
(`tests/test_calibration.py`, 39 tests per `docs/TESTING.md`).

### 142.5 Apostrophes in the tokenizer

A smaller quality fix with a large effect on one class of text: 1.0 split `queen's` into `queen` and `s`, and the stray
`s` became a spurious "fact" that context recall looked for. `tokenize` now keeps a word with apostrophes between
letters whole and then deletes the apostrophes (`text.py:29-31`, `:49-55`): `queen's`, `queen’s` (typographic) and
`queens` all become `queens`. SQuAD-style normalisation deletes apostrophes of any style (`text.py:34`). The bundled
data contains only one apostrophe ("workers'"), so the five example runs did not change; this matters for real
documents. Part VI §63.3 describes the old behaviour and its replacement.

## 143. Operations

### 143.1 `ragwb doctor`

**Problem.** When something is wrong ("the app will not start", "my runs vanished"), the first ten minutes go on
establishing the basics. `doctor` runs those basics in one command and — importantly — works when the configuration or
the run store is broken, because `main` handles it before opening the application context (`cli.py:669-670`; `doctor`
reads settings only). It is also shown on the Settings page as a *Health checks* table (`ui/views/settings.py:17-27`).

`run_doctor` (`maintenance.py:43-56`) runs nine probes, each guarded so that one crashing probe becomes a failed
`diagnostics` check rather than taking the diagnosis down (`maintenance.py:51-55`):

| Check | What it verifies | Status rules |
|---|---|---|
| `python` | version ≥ 3.12 | fail below |
| `packages` | the nine required distributions are installed | fail if any missing, naming them |
| `data directory` | creates and removes a temporary file | fail if not writable |
| `disk space` | free bytes where the data lives | warn under 500 MB |
| `run store` | opens the store, `PRAGMA integrity_check`, schema version, run count, abandoned runs | fail on a failed integrity check or unreadable file; warn on abandoned `running` runs |
| `default data` | the default dataset validates and the default document loads | warn on problems |
| `OpenAI key` | whether a key is *configured* | always ok; never calls the API |
| `telemetry` | `DEEPEVAL_TELEMETRY_OPT_OUT` is set | warn if not |
| `network exposure` | `.streamlit/config.toml` `server.address` and whether a password is set | ok for local addresses; warn if exposed *with* a password; fail if exposed or unset *without* one |

Real output on this machine, with the data directory pointing at an empty temporary folder:

```text
$ RAGWB_DATA_DIR=<temp> python -m rag_workbench doctor
[ok  ] python            3.12.15
[ok  ] packages          9 required packages installed
[ok  ] data directory    <temp>\book13-data3 is writable
[ok  ] disk space        68.9 GB free
[ok  ] run store         not created yet (created on first use)
[ok  ] default data      honeybees.jsonl and honeybees.pdf load
[ok  ] OpenAI key        not set: offline mode only (BM25, extractive baseline, lexical metrics)
[ok  ] telemetry         DeepEval telemetry is disabled
[ok  ] network exposure  the app listens on localhost only

9 ok, 0 warning(s), 0 failure(s)
```

Exit status is 1 if any check fails, 0 otherwise (`cli.py:446-454`). The check names and statuses are covered by
`tests/test_maintenance.py:26-80`, including a corrupt store, an unwritable directory, abandoned runs and that
`doctor` never prints a secret.

**Limit worth knowing.** `network exposure` reads the *file* `.streamlit/config.toml` (`maintenance.py:148-164`).
It cannot see a `--host` flag given to `start.py` or a `--server.address` given to a manually started Streamlit; the
launcher's own check (§144.3) covers the first, nothing covers the second.

### 143.2 `ragwb backup`

SQLite files are easy to lose and hard to copy safely while a writer is active: a plain file copy can capture a
half-written page. `backup_store` (`maintenance.py:168-195`) uses SQLite's *online backup API* (`source.backup`,
`maintenance.py:187`), which produces a consistent snapshot even while the app writes, then runs
`PRAGMA integrity_check` on the copy and deletes it if the verdict is not `ok` (`maintenance.py:188`, `:192-194`). The
source is opened read-only (`mode=ro`, `maintenance.py:183`), the target name carries a UTC timestamp
(`runs-YYYYMMDD-HHMMSS.db` in release 1.1; since release 1.4 the name also carries microseconds, `maintenance.py:176-178`) and an existing file is never overwritten (since 1.4 a `-N` counter is added instead of failing, `:179-182`). Output:

```text
$ ragwb backup
Backup written and verified: <data dir>\backups\runs-20261027-193743.db (49,152 bytes)
```

Restoring was deliberately manual in release 1.1 (stop the app, replace `data/runs.db`), because an automated restore that silently
overwrites the live store is a more dangerous feature than the one it protects against. (Release 1.4 added `ragwb restore`, which validates the backup, refuses recently active runs and writes a safety copy first: Part XVI §171.) Backups cover the run store
only; uploaded files (`data/uploads/`) and logs are not included.

### 143.3 `ragwb prune`

Runs accumulate. `select_prunable` (`maintenance.py:203-224`) implements a retention policy with two knobs,
`--keep-last N` (always protect the newest N) and `--older-than-days D` (select runs older than the cutoff). Given
both, a run must be older than the cutoff *and* outside the newest N. Safety properties:

* **Dry run by default.** Without `--yes` the command lists what would be deleted and says so
  (`cli.py:430-443`). With `--yes` it deletes.
* **Refuses to select everything.** Giving neither knob raises `ValueError` (`maintenance.py:210-211`).
* **Never selects a run tagged `keep`** (release 1.4.1; the command prints how many such runs it protected, and `keep` outranks both knobs).
* **Never selects a run that may still be executing**: a `running` run is skipped unless it is stale
  (`maintenance.py:219-220`, with the same 15-minute window as interruption recovery).

```text
$ ragwb prune --keep-last 0
  20261027-193739-slices-demo-3e6b4c  completed   2026-10-27  slices-demo
1 run(s) would be deleted. Re-run with --yes to delete them (consider `ragwb backup`).
```

Deletion cascades to the run's case results (`storage.py:49`, foreign key with `ON DELETE CASCADE`) and is not
undoable, which is why the message points at `backup`. Tests: `test_prune_policies`,
`test_prune_never_selects_a_run_that_may_still_be_executing` (`tests/test_maintenance.py:103-118`).

### 143.4 `ragwb rerun`

Repeating an experiment should not mean re-typing a dozen flags. `rerun_config` (`maintenance.py:293-307`) rebuilds a
`RunConfig` from the stored run: relative dataset and document paths (as written into exported bundles) are resolved
against the project root, the name defaults to `<old name>-rerun`, and the notes record "Re-run of <old id>". The CLI
command (`cli.py:392-409`) then **compares hashes**: if the dataset or document's SHA-256 differs from the one stored
with the original run, it prints a warning that the results are not like-for-like. It runs the new run and prints
`(re-run of <old id>)`.

```text
$ ragwb rerun 20261027-193739-slices-demo-3e6b4c --quiet
Run 20261027-193745-slices-demo-rerun-d4316d: completed (re-run of 20261027-193739-slices-demo-3e6b4c)
```

For an offline run the rerun reproduces the scores exactly (`test_rerun_reproduces_an_offline_run_exactly`,
`tests/test_maintenance.py:121`). For an OpenAI run it repeats the *configuration*, not the answers: model outputs vary,
and a rerun after a provider-side model update is a different experiment. The stored configuration is validated again;
if a field has since become invalid, `rerun` fails with the validation message instead of guessing (`ValueError`,
reported as `error: ...`).

### 143.5 `--version` and JSON logs

`ragwb --version` printed `ragwb 1.1.0` in this release (`cli.py:525`). Logs gain a second format: `RAGWB_LOG_FORMAT=json` switches
the file and console handlers to `RedactingJsonFormatter` (`logging_setup.py:33-48`, selected at `:87-88`), one JSON
object per line with `ts` (UTC, millisecond precision), `level`, `logger`, `message` and, for exceptions, `exc`. That
shape suits `jq`, a log shipper or a SIEM. The security properties are covered in §144.5.

## 144. Security

The threat model of Part XI is unchanged — a single-user local tool — but 1.1 acknowledges that people will, sooner
or later, run it on a shared host. The additions are all opt-in, and the default remains "listens on localhost
only".

### 144.1 The optional shared password

Setting `RAGWB_APP_PASSWORD` turns on a login page in front of the whole app. The setting is a `SecretStr`
(`config.py:66`), excluded from `public_dict` (which reports only `app_password_configured`, `config.py:163-169`)
and included in the log redactor's secret list (`config.py:152-155`).

`streamlit_app.py` calls `require_login(context_or_stop().settings)` before building the page navigation
(`streamlit_app.py:20`); with no password it is a no-op. `require_login` (`ui/auth.py:132-148`; the code below is
as of release 1.1, and 1.2 split the form into a shared-password and an accounts variant, Part XIV §156):

1. returns immediately if no login is configured or the Streamlit *session* is already authenticated
   (`st.session_state["_authenticated"]`, `auth.py:33`, `:136`);
2. otherwise shows a form and **stops the script** (`st.stop()`, `auth.py:148`), so nothing below it — no page, no
   data — is rendered or executed;
3. on submit (the shared-password form, `_login_with_shared_password`, `auth.py:182-200`), first asks the throttle
   whether attempts are allowed (`auth.py:191`), then compares passwords (`auth.py:194`), then either marks the session
   authenticated and reruns (`auth.py:195-197`) or records a failure (`auth.py:198-200`).

### 144.2 Constant-time comparison and the lockout

*Constant-time comparison.* `password_matches` (`auth.py:80-81`) uses `hmac.compare_digest` on the UTF-8 bytes. An
ordinary `==` on strings returns as soon as it finds the first differing character, so response time leaks how many
leading characters were right; `compare_digest` takes time independent of where the strings differ, closing that
timing side channel. (Over a real network the noise usually swamps such differences, but the correct primitive costs
nothing.)

*The lockout.* `LoginThrottle` (`auth.py:45-77`) is a sliding-window limiter: after `MAX_FAILURES = 5` failed attempts
within `WINDOW_S = 60` seconds (`auth.py:31-32`) every further attempt — including one with the right password — is
refused until the oldest failure leaves the window (`retry_after`, `auth.py:60-67`). The clock is injectable
(`auth.py:48-52`) so the tests do not sleep: `test_throttle_locks_after_the_limit_and_recovers`,
`test_repeated_failures_lock_out_even_the_right_password` (`tests/test_auth.py:28`, `:115`). At that rate an attacker
gets five guesses a minute; a 12-character random password is not guessable that way in a lifetime.

*Honest limits.*

* The throttle is **process-wide** (`@st.cache_resource`, `auth.py:113-115`), not per client address. That blocks
  brute force but also means anyone who can reach the login page can lock out every legitimate user for a minute at a
  time — a denial of service. Per-IP throttling would need the client address, which Streamlit does not expose
  reliably.
* The failure counter lives in memory: restarting the server resets it.
* It is **one shared secret**, not user management: there are no accounts, no roles, no audit trail of who did what. (Release 1.2 adds named accounts for exactly this reason, Part XIV §156.)
* Traffic is not encrypted. The password travels in clear text unless a TLS-terminating reverse proxy sits in front
  (the module docstring and `docs/KNOWN_LIMITATIONS.md` both say so).
* The session flag is per browser session; reloading the page starts a new session and asks again.

### 144.3 `start.py --host`

Exposing the app is a deliberate act, so the launcher makes it a checked one. `python start.py --host 0.0.0.0` passes
the address to Streamlit (`start.py:215`), but first `main` calls `host_problem(args.host, password_configured())`
(`start.py:205-208`; release 1.2 also accepts user accounts there, so the code below is as of release 1.1):

```python
def host_problem(host, password_set):
    """Why this host must not be used, or None. The app has no accounts: exposing it needs the shared password."""
    if host in LOCAL_HOSTS or password_set:
        return None
    return (f"refusing to listen on {host!r} without a password. Set RAGWB_APP_PASSWORD (environment or .env) "
            "first, or use the default localhost.")
```

(as of 1.1, now `start.py:112-117`; `LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}`, `start.py:35`.) The launcher uses only the standard
library and cannot import the package, so `password_configured` (`start.py:84-95`) reads the environment and then
parses `.env` by hand for a non-blank `RAGWB_APP_PASSWORD`. The check happens *before* anything is installed or
started: `test_the_launcher_refuses_an_exposed_host_without_a_password_before_touching_anything`
(`tests/test_start.py:113`). For wildcard addresses (`0.0.0.0`, `::`) the readiness probe uses `localhost`
(`start.py:167`).

The limit is the obvious one: the check is only in the launcher. Someone who runs `streamlit run` by hand with
`--server.address 0.0.0.0` bypasses it, and `doctor` cannot see a command-line flag (§143.1). The password gate itself
(§144.1) still applies, because it lives in `streamlit_app.py`.

### 144.4 What the password does not protect

Worth saying out loud because it is easy to over-trust this feature: the password gate protects the *UI*. It does not
protect the CLI (which runs as the file owner by design), the files on disk, the SQLite database, or the logs. Anyone
who can read `data/` or `.env` on the host has everything the app has.

### 144.5 JSON logs stay redacted

The redaction guarantee of Chapter 54 had to survive the new format, or the feature would have been a leak.
`RedactingJsonFormatter.format` (`logging_setup.py:43-48`) builds the payload (`ts`, `level`, `logger`, `message`,
`exc`), serialises it with `json.dumps(..., ensure_ascii=False)` and **then** runs the redactor over the serialised
text (`logging_setup.py:48`). Redacting after serialisation means a secret cannot escape through any field —
including the traceback — and cannot be hidden by JSON escaping of its neighbours. The redactor masks every configured
secret of 8 or more characters (now including the app password, `config.py:152-155`) and anything shaped like
`sk-...` (`logging_setup.py:54-59`). `test_json_log_format_redacts_secrets` (`tests/test_maintenance.py:190`) checks it.
As before, redaction is a second line of defence; the code does not log credentials in the first place.

## 145. Verification

### 145.1 The six steps of `scripts/verify.py`

`verify.py` grew from five to six steps (docstring, `scripts/verify.py:1-22`); each prints PASS or FAIL and the exit
status is non-zero if any fails:

| # | Step | What it does | Network |
|---|---|---|---|
| 1 | environment | Python ≥ 3.12 and the required packages import | no |
| 2 | lockfile | `uv lock --check --offline` (skipped if uv is absent) | no |
| 3 | secrets | no API-key-shaped strings or `.env` files anywhere in the tree | no |
| 4 | **static** | `ruff check .` and `mypy`; skipped with a note if the dev tools are not installed | no |
| 5 | tests | `pytest`, with coverage unless `--quick` | no |
| 6 | end-to-end | CLI `run` → `show` → `export` (csv/json/md) → `import` → `compare` → `slices` → labels → `doctor` → `backup` in a temporary data directory | no |
| (opt) | **audit** | `--audit`: `pip-audit` over the locked runtime requirements | yes |

The optional audit is the only step that touches a remote service; it sends package names and versions, never code or
data, to a public vulnerability database (`scripts/verify.py:17-18`, `:104-119`).

### 145.2 Static analysis gates

The 1.0 tree had no linter and no type checker; the "Fixed" column of Part X lists bugs that either would have
caught. Both are now gates configured in `pyproject.toml`:

* **ruff** (`pyproject.toml:57-77`): line length 120, target Python 3.12, rule families `E W F I UP B C4 SIM RUF PLW`
  (pycodestyle, pyflakes, import order, pyupgrade, bugbear, comprehensions, simplify, ruff-specific, pylint warnings).
  A few rules are switched off with a reason beside each (`RUF001-3`: the UI deliberately uses typographic
  characters; `SIM108`: ternaries are not always clearer), and the page scripts may import after `st.*` setup
  (`E402`).
* **mypy** (`pyproject.toml:85-92`): over `src` and `start.py`, with `check_untyped_defs`, `warn_unused_ignores`,
  `warn_redundant_casts` and `no_implicit_optional`. Third-party stubs are not required (`ignore_missing_imports`).

Run for this book, with the project virtual environment:

```text
$ python -m ruff check .
All checks passed!
$ python -m mypy
Success: no issues found in 39 source files
```

What this does and does not buy. It catches whole classes of mistakes (unused names, wrong `None` handling, a changed
signature not followed through) for free on every change. It does not find logic errors, and `# type: ignore`
comments exist (the logging module sets a private attribute on a `Logger`, `logging_setup.py:76`, `:104`) — `warn_unused_ignores`
keeps them honest.

### 145.3 Tests

`docs/TESTING.md` records 253 tests across 19 files, run offline in about two minutes; the 113 added in 1.1 are the
new files `test_maintenance.py` (21), `test_auth.py` (8), `test_start.py` (11), `test_evaluation_options.py` (21),
`test_calibration.py` (39) and `test_live.py` (7), plus additions to the existing files. Results from
`uv run pytest --cov` (`docs/TESTING.md`): **252 passed, 0 failed, 1 skipped** (the opt-in live test), statement
coverage **96 %** (2,532 statements, 100 missed), with the Streamlit page scripts excluded from the measurement
(`pyproject.toml:53-55`) and exercised by the nine AppTest journeys instead.

### 145.4 Dependency audit — a point-in-time result

`pip-audit` was run over the locked *runtime* requirements (exported with `uv export --frozen --no-dev
--no-hashes --no-emit-project`, `scripts/verify.py:108-115`). Result, quoted from the changelog and
`docs/KNOWN_LIMITATIONS.md`: **no known vulnerabilities at the time of the scan**. Two caveats belong next to that
sentence. First, it is a statement about one moment: `pip-audit` queries an advisory database, so the answer can change
the next day without any change to the code — re-run `scripts/verify.py --audit` before each release. Second, it covers
*known* vulnerabilities in the *locked runtime* packages; it says nothing about the dev tools, transitive packages
outside the lock, unknown flaws, or the pip-fallback install path of the launcher, which resolves versions afresh
(Part XI §115). This run of the book's authoring did not repeat the audit (no network was used).

## 146. Scale and the benchmark

### 146.1 What the benchmark measures

`scripts/benchmark.py` answers "how long do runs, reads and exports take as the dataset grows, offline?". It
generates its own dataset from the example document — one question per sentence, cycling, with a `bucket` metadata
field (`benchmark.py:32-40`) — so no external data is used, runs each size in a fresh temporary data directory, and
reports per size: run time and cases per second, time to read all case results back, time to build the CSV export,
the SQLite file size, and Python-level peak memory via `tracemalloc` in a separate pass from the timing (`benchmark.py:43-68`; see the erratum in §146.2). The four lexical metrics
are used (`token_f1`, `rouge_l`, `context_recall`, `groundedness`). It exits non-zero if a run does not complete or a
case is lost on read-back (`benchmark.py:84-86`).

```text
uv run python scripts/benchmark.py                 # 200, 1000 and 5000 cases, 1 worker
uv run python scripts/benchmark.py --sizes 1000 --workers 4
```

### 146.2 Measured results (corrected in release 1.4)

> **Erratum (release 1.4).** The numbers first printed in this section were wrong, and the conclusion drawn from them in §146.3 is
> withdrawn. `scripts/benchmark.py` started `tracemalloc` before timing the runs, and tracing every allocation slows Python code that
> allocates a lot by a large factor. The script now times with no tracer and measures memory in a separate pass. The original figures,
> kept here only so the error can be seen: 200 cases 3.11 s (64.4 cases/s); 1,000 cases 19.46 s (51.4 cases/s); 5,000 cases 108.97 s
> (45.9 cases/s); read-back of 5,000 cases 0.56 s; CSV export 0.32 s; 1,000 cases with four workers 28.33 s (35.3 cases/s), against 19.46 s with
> one. Throughput was understated by roughly a factor of two, and the "four workers are slower" result was an artefact of the tracer.
> Memory and database sizes were not affected.

Corrected measurements: one laptop (the development machine), offline path, one worker unless stated:

| Cases | Run time | Throughput | Peak Python memory | SQLite file |
|---:|---:|---:|---:|---:|
| 200 | 1.85 s | 107.9 cases/s | 2.3 MB | 0.9 MB |
| 1,000 | 9.98 s | 100.2 cases/s | 10.9 MB | 4.2 MB |
| 5,000 | 46.82 s | 106.8 cases/s | 53.9 MB | 20.8 MB |

| Operation at 5,000 cases | Time |
|---|---:|
| Read all 5,000 case results back from SQLite | 0.31 s |
| Build the CSV export | 0.15 s |

| Setting | Run time | Throughput |
|---|---:|---:|
| 1,000 cases, 1 worker | 9.98 s | 100.2 cases/s |
| 1,000 cases, **4 workers** | 8.65 s | 115.6 cases/s |

Reading: throughput is flat, at about 100 to 108 cases per second from 200 to 5,000 cases; memory and database size grow roughly
linearly (about 11 KB of Python memory and 4 KB of database per case); and reading and exporting are fast compared with running. The
storage layer and the bootstrap intervals are not the bottleneck. The `RAGWB_MAX_CASES` default of 5,000 (`config.py:89`) is exactly
the largest size measured; larger datasets are refused rather than benchmarked.

### 146.3 Workers offline (rewritten in release 1.4)

The first version of this section reported that four workers were about 45 % *slower* than one and explained it with the global
interpreter lock. That result came from the tracer (§146.2) and is withdrawn. Under the corrected harness four workers took 8.65 s
against 9.98 s for one at 1,000 cases: **about 15 % faster**, a small gain, and a single measurement on one machine.

The general point behind the old explanation still stands, and it is why the gain is small. The offline work is CPU-bound Python
(tokenising, scoring with BM25, extractive selection, lexical metrics), and CPython's global interpreter lock allows only one thread
to execute Python bytecode at a time, so threads that are not waiting on anything cannot add up to a multiple of one thread's speed.
They contend, and the pooled path has extra work of its own (futures, the per-case daemon thread of §141.1 that is created for *every*
case regardless of worker count, ordering results by position). Threads pay off much more when cases *wait*: an OpenAI call spends nearly
all its time blocked on the network, during which the GIL is released. That is why the default is 1 worker offline and
`RAGWB_MAX_WORKERS` (4) for OpenAI (`cli.py:61`). The benchmark does **not** tell us how the pooled path scales with real network
latency, because no network call was involved.

**What the benchmark cannot show.** One machine; one document of eleven chunks (retrieval time per query is unrepresentatively small);
no network; no judge metrics; sequential reads; a single run of each setting. It is a regression guard for the storage/aggregation
path and an honest scale statement for the offline workflow (about 100 cases per second from 200 to 5,000 cases), not a capacity plan
for judged runs, which will be limited by the provider.

## 147. The live smoke script, and what is still unverified

### 147.1 `scripts/live_smoke.py`

Every OpenAI and DeepEval code path in this project is exercised only with fakes: a scripted chat model, deterministic
fake embeddings, fake DeepEval metric objects, and real DeepEval objects constructed without a network. That leaves a
gap that no amount of unit testing closes: *do the real clients accept the parameters we pass, and do answers,
embeddings and judge scores come back in the shape the code expects?* `scripts/live_smoke.py` exists to close it, in
the cheapest way that can:

* It **makes paid API calls**, and is guarded accordingly. It refuses to run without `--yes-spend`
  (`live_smoke.py:53-56`), without a configured `OPENAI_API_KEY` (`:54-56`), and with more than five cases
  (`MAX_CASES = 5`, `:27`, `:43-45`). It never prints the key.
* It runs a tiny evaluation (default three cases) in a *temporary* data directory, so the real run store is untouched
  (`:57-59`), and then applies a list of checks that a fake cannot satisfy: at least one case succeeded, every case
  produced a non-empty answer, retrieved context was recorded, token usage was reported, and every selected metric
  scored every successful case (`:83-97`). It prints the judge cost DeepEval reported (`:98-99`) and exits 0 only if
  every check passed (`:100-102`).
* Its refusal paths and its failure path are tested without spending anything: `tests/test_live.py:43-62` verifies
  the missing-flag, missing-key and case-cap guards, and that pointing the script at an unreachable local port makes
  it report failure and exit non-zero. The one test that would really call the API (`test_live_smoke_script_passes`,
  `tests/test_live.py:28`) is skipped unless `RAGWB_LIVE_TESTS=1` and a key are set (`pyproject.toml:55-58`).

**It has not been run.** There was no API key in the environment where this release was prepared, so the script's
success path has never executed. What has been verified is the guard logic and the failure path. Until someone runs
`uv run python scripts/live_smoke.py --yes-spend` with a small budget, the statement "the OpenAI path works" is a
statement about code review and fakes, not about the live service. Nothing in this book claims otherwise.

### 147.2 What remains unverified or unimplemented

Consolidated from `docs/KNOWN_LIMITATIONS.md`:

| Area | State |
|---|---|
| Real OpenAI generator, agent pipeline, embeddings, judge metrics | Implemented and tested with fakes; **no live call had been made** from this project at release 1.1 (release 1.3 ran generation and the judge metrics against Groq's free tier; the agent pipeline, API embeddings and OpenAI itself are still not run live, Part XV §167) |
| Judge cost (`evaluation_cost`) and judge token counts | Cost passed through unverified; tokens unavailable |
| Judge-versus-human calibration | Tooling exists and is tested on synthetic labels; no real labels, no real judge scores |
| Hybrid retrieval quality | Fusion arithmetic verified; quality only against fake embeddings |
| Dependency vulnerabilities | No known issues at one point in time; re-run before every release |
| Accessibility | No formal audit of the UI |
| Concurrency | No multi-process testing; runs longer than a few minutes not measured |
| Timeout thread | Abandoned calls keep running until their own HTTP timeout |
| Access control | One shared password, process-wide lockout, no TLS, no accounts |
| Data growth | Larger than `RAGWB_MAX_CASES` is refused, not scaled |
| Store paths | The local run store keeps absolute paths (exported bundles do not) |

## 148. Reference: new settings, commands and files

### 148.1 New environment variables

| Variable | Setting | Default | Valid values | Effect | Code |
|---|---|---|---|---|---|
| `RAGWB_CASE_TIMEOUT_S` | `case_timeout_s` | 600 | number > 0 and ≤ 3,600 | Wall-clock limit for one case (generation plus scoring); a case over the limit is recorded as an `error` and the run continues | `config.py:75`, `:182`; `runner.py:184-206` |
| `RAGWB_LOG_FORMAT` | `log_format` | `text` | `text`, `json` | Log line format; `json` writes one redacted JSON object per line | `config.py:47`, `:93`, `:194`; `logging_setup.py:87-90` |
| `RAGWB_APP_PASSWORD` | `app_password` | unset | any non-blank string | Enables the login page for the web app; required by `start.py` for any non-local `--host`; masked in logs and settings views | `config.py:66`, `:195`; `ui/auth.py:132-140`, `:182-200`; `start.py:112-117` |

Blank values are treated as unset (`config.py:218-219`), and an invalid value stops start-up with a message naming the
variable (`config.py:226-232`).

### 148.2 New and changed CLI commands

| Command | Purpose | Options | Exit status | Section |
|---|---|---|---|---|
| `ragwb --version` | print the version | — | 0 | §143.5 |
| `ragwb doctor` | health checks, no network | — | 0, or 1 if any check fails | §143.1 |
| `ragwb backup` | verified consistent copy of the run store | `--out-dir` (default `<data>/backups`) | 0, 1 | §143.2 |
| `ragwb prune` | retention clean-up, dry run unless `--yes` | `--keep-last N`, `--older-than-days D`, `--yes` | 0, 1 | §143.3 |
| `ragwb rerun RUN_ID` | repeat a stored run from its configuration | `--name`, `--quiet` | like `run` | §143.4 |
| `ragwb slices RUN_ID` | per-value summary of a metadata field | `--by FIELD` (required) | 0, 1 | §142.3 |
| `ragwb labels-template RUN_ID` | write a CSV for human labelling | `--out FILE` (required), `--force` | 0, 1 | §142.4 |
| `ragwb calibrate RUN_ID` | agreement and kappa of a metric versus human labels | `--labels FILE`, `--metric NAME` (both required) | 0, or 1 if nothing could be compared | §142.4 |
| `ragwb run` (changed) | new options | `--retriever hybrid`, `--min-evidence X`, `--skip-headings` | as before | §142.1, §142.2 |
| `python start.py` (changed) | new option | `--host H` | as before | §144.3 |

In release 1.1 the CLI had 17 commands (the ten of release 1.0 plus the seven above); release 1.2 raised the count to 22 (Part XIV §159.1).

### 148.3 New files

| File | Lines | Role |
|---|---:|---|
| `src/rag_workbench/maintenance.py` | 237 | `run_doctor`, `backup_store`, `select_prunable`, `rerun_config` |
| `src/rag_workbench/calibration.py` | 215 | label parsing, `cohen_kappa`, `calibrate`, `labelling_sheet` |
| `src/rag_workbench/ui/auth.py` | 96 | `LoginThrottle`, `password_matches`, `require_login` |
| `scripts/benchmark.py` | 90 | offline scale benchmark |
| `scripts/live_smoke.py` | 106 | guarded paid smoke test (not run at release 1.1; run against Groq's free tier in release 1.3, Part XV §160) |
| `tests/test_maintenance.py`, `test_auth.py`, `test_start.py`, `test_evaluation_options.py`, `test_calibration.py`, `test_live.py` | — | 107 tests of the above |

## 149. Other changes, and how to read a 1.1 run

* **Scores outside [0, 1]** (beyond a 1e-9 tolerance) are recorded as metric errors rather than silently clamped
  (`metrics/base.py:92-96`); tiny floating-point noise is still absorbed. This is a bug-fix, not an option.
* **Apostrophes** are tokenised consistently (§142.5) — the second deliberate behaviour change. For ordinary English
  text it can shift lexical scores slightly; for the bundled data it did not (the changelog's "identical scores").
* **PyMuPDF is pinned below 2.0** (`pyproject.toml:13-15`): version 2.0 loads ONNX models at import time and added
  about three seconds to every process start, for a feature (layout analysis) that plain block extraction does not use.
* **Tool versions** recorded in a run's environment block now include the 1.1.0 workbench version
  (`runner.py:277`).

**A checklist for trusting a 1.1 result.**

1. `ragwb doctor` is clean, and a recent `ragwb backup` exists.
2. The run's Configuration tab shows the time limit, retriever, `min_evidence`, `skip_headings`, and the stored prices.
3. Skipped and errored counts are read next to every mean; timed-out cases show as `error`, not as low scores.
4. Slices are checked for any metadata field the dataset offers, and slice sizes are read before the means.
5. Before any decision rests on a *judge* score, a calibration against human labels has been run on enough cases
   (30 or more, ideally many more) — or the decision is understood to rest on an unvalidated opinion.
6. Costs are treated as estimates and reconciled with the invoice.
7. Anything that touches the live OpenAI path is understood to be unverified until `scripts/live_smoke.py` has been
   run once with a real key.
