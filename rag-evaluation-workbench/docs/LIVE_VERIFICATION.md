# Live verification record

What was actually run against real services and a real local model, with the outcomes, the failures and the limits. All
numbers come from runs made on 2026-10-28; nothing here is projected or estimated. Samples are small and every result
describes one provider, a handful of models and the bundled example data only.

## Provider and models

Groq Cloud's free tier, through its OpenAI-compatible endpoint (`https://api.groq.com/openai/v1`), using
`OPENAI_API_KEY`/`OPENAI_BASE_URL`. Models available to that key for chat: `openai/gpt-oss-20b`, `openai/gpt-oss-120b`
and `qwen/qwen3.8-27b`. The provider has no embedding models, so API embeddings (and therefore hybrid retrieval with API
embeddings) were not exercised. All runs used BM25 retrieval, k = 3, one worker.

## What was run

| # | Run | Result |
|---|---|---|
| 1 | `live_smoke.py`, 2 cases, no judge, generator `gpt-oss-20b` | 8/8 checks: answers, retrieved context, token usage (658 in / 179 out) and lexical metrics |
| 2 | `live_smoke.py`, 2 cases, four judge metrics (`gpt-oss-120b` judge) | first attempt 8/12: one case per judge metric hit the free-tier rate limit and was recorded as an *error* (a `RetryError` whose cause the retry logic did not recognise) |
| 3 | same, after recognising wrapped rate limits and honouring `Retry-After` | 12/12 checks, all four judge metrics scored both cases |
| 4 | 10 honeybee questions, four judge metrics | all 10 answered; 3 of 40 judge scores lost to the rate limit (excluded from means, counted as errors): see the table below |
| 5 | 20 honeybee questions, four judge metrics | not completed: the judge model's daily token budget was already used (199,638 of 200,000 tokens), so the run was stopped |
| 6 | 30 volcano questions, `qwen/qwen3.8-27b` as generator and judge, `correctness` only | finished `partial`: 28 ok, 2 case errors caused by a bug (below) during a network drop |
| 7 | the same run repeated with the bug fixed | 30/30 cases ok (table below) |
| 8 | `ragwb judge-noise` on run 7, 10 cases x 3 repeats, `correctness` | see below |
| 9 | local embeddings (`BAAI/bge-small-en-v1.5`, real model, `HF_HUB_OFFLINE=1`) on five datasets x three retrievers | see below |
| 10 | keyboard Tab walk of the New evaluation page in a browser | see below |
| 11 | run 7 compared with pass/fail labels written by Claude (an AI rater) | see below; not human labels |
| 12 | tool-calling **agent** pipeline, 3 honeybee questions, `qwen/qwen3.8-27b` | 3/3 ok (below) |
| 13 | threshold sweeps for `correctness` and the local `semantic_similarity` against the same labels | see below |
| 14 | clean wheel install in a throwaway venv (`scripts/wheel_check.py`) | 10/10 checks; one defect found and fixed |
| 15 | axe-core 4.10.2 accessibility audit of seven page views | 6 clean, 1 minor third-party issue |
| 16 | keyboard Tab walks of Run results and Settings | no trap (below) |
| 17 | all 20 honeybee questions, four judge metrics, `qwen/qwen3.8-27b` for both roles, paced at 10 operations/minute | 20/20 answered; two judge metrics mostly lost to the provider's token cap (below) |

### Run 4 — 10 honeybee questions (`gpt-oss-20b` generating, `gpt-oss-120b` judging)

| Metric | Mean | 95% CI | Scored | Failed |
|---|---:|---|---:|---:|
| Token F1 | 0.680 | 0.554–0.804 | 10 | 0 |
| Context recall (lexical) | 0.891 | 0.817–0.961 | 10 | 0 |
| Groundedness (lexical) | 0.967 | 0.922–0.996 | 10 | 0 |
| Answer relevancy (judge) | 1.000 | 1.000–1.000 | 10 | 0 |
| Faithfulness (judge) | 1.000 | 1.000–1.000 | 10 | 0 |
| Context relevancy (judge) | 0.173 | 0.140–0.211 | 8 | 2 |
| Correctness (judge) | 0.522 | 0.233–0.822 | 9 | 1 |

These are the first 10 of 20 questions, so they are not comparable with offline numbers over all 20. Tokens used for generation:
3,375 in, 1,105 out. DeepEval reported no judge cost for this provider.

### Run 7 — 30 volcano questions (`qwen/qwen3.8-27b` generating and judging)

| Metric | Mean | 95% CI | Scored | Skipped |
|---|---:|---|---:|---:|
| Token F1 | 0.489 | 0.381–0.600 | 30 | 0 |
| Context recall (lexical) | 0.660 | 0.539–0.774 | 25 | 5 |
| Groundedness (lexical) | 0.884 | 0.819–0.940 | 22 | 8 |
| Correctness (judge) | 0.803 | 0.663–0.920 | 30 | 0 |

Skips are the 5 unanswerable questions (no reference to recall) and abstained answers (nothing to ground).

### Run 8 — judge noise (`correctness`, 10 cases, 3 repeats)

Within-case SD 0.023, between-case SD 0.371, noise/signal 0.062, 1 of 10 cases changed its pass/fail verdict between
repeats. For this judge, model and rubric the call-to-call jitter is small next to the real differences between cases; ten
cases are too few to say more, and other metrics (faithfulness, context relevancy) were not measured.

### Run 9 — retrievers with a real local embedding model (offline provider, k = 3)

Means over every case of each dataset; semantic columns use the same local model.

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

Reading it: there is no consistent winner. Local embeddings raised lexical context recall on the paraphrased questions
(0.664 to 0.786) and on volcanoes/coffee/lighthouses, and lowered it on the main honeybee set (0.885 to 0.792); hybrid-local
sat close to BM25 and gave the best token F1 on honeybees (0.376). The semantic metrics barely move: scores sit between
0.63 and 0.76 for these extractive answers, and in a direct check a paraphrase scored 0.847 against 0.501 for an unrelated
sentence, so bge cosines have a high floor. The 0.7 default threshold therefore says almost nothing until calibrated.
The extractive baseline answers the same way regardless of retriever, so these tables describe retrieval, not answer quality.

### Run 10 — keyboard walk

40 Tab presses on the New evaluation page: a skip link first, then the sidebar links, then every form control in visual
order (uploaders, selects, radio groups, slider, expanders, run name, Run button), then back to the start: no trap, no
hidden stop. A script flagged 16 stops without an outline or shadow, but Streamlit styles focus another way; two (a sidebar
link and a radio button) were checked visually and show a visible indicator. The other 14 flagged stops, the other pages and
screen readers were not checked.

### Run 11 — the judge against labels written by Claude (an AI rater, not a person)

`calibration/volcanoes-labels-by-claude.csv` holds pass/fail labels for the 30 answers of run 7, written by Claude (the AI
assistant that built this project) at the project owner's request. They are **not human labels** and the report's "human"
wording refers to them only because the tool names its column `human_pass`. Method: each answer was judged against its reference
answer *before* looking at any metric score; a correct abstention on an unanswerable question counts as a pass. Result: 26
pass, 4 fail (v08 answered a different question; v20, v23 and v26 abstained although the text answers them).

| Metric | Cases compared | Agreement with the labels | Cohen's kappa | Metric pass rate | Label pass rate |
|---|---:|---:|---|---:|---:|
| Correctness (judge) | 30 | 0.967 | 0.870 (almost perfect) | 0.833 | 0.867 |
| Token F1 (lexical) | 30 | 0.600 | 0.237 (fair) | 0.467 | 0.867 |
| Groundedness (lexical) | 22 | 0.909 | 0.463 (moderate) | 0.864 | 0.955 |

Reading it, with its limits:

* The `correctness` judge agreed with the labels on 29 of 30 cases. Its one miss was v05 ("The youngest island sits above the
  hotspot."), which it failed while the labeller passed it; its stated reason claimed a contradiction with the reference that the
  labeller did not find. It failed no answer the labeller passed except that one, and it caught all 4 of the labeller's fails.
* Token F1 passed 14 of the 26 answers the labeller passed: with these paraphrased references the lexical metric under-credits
  correct answers (recall 0.538), which matches the earlier finding that its scores say little about meaning.
* Groundedness agrees with the labels on 20 of 22 scored cases, but it measures support by the retrieved text, not correctness,
  so the comparison is only loosely meaningful.
* **Limits:** one rater, who is an AI model from a different family than the judge but has the same blind spots as any model
  and saw the reference answers; 30 cases of one document with only 4 failures, so the kappa is unstable and the sample is mostly
  easy cases (no borderline answers); labels with 4 fails cannot show how the judge treats subtle errors. This is evidence that
  the judge is not obviously unreliable on this easy set; it is **not** the human calibration the tooling is meant for, and
  `calibration/volcanoes-labelling-sheet.csv` is still waiting for a person.

### Run 12 — the agent pipeline, live

`--pipeline agent` with `qwen/qwen3.8-27b` as the tool-calling model, BM25 as the tool, 3 questions: all three answered
("A typical honeybee colony has one queen.", and similar), each with 3 chunks captured from the agent's own tool calls
(`context_source = agent_tool`), 1 attempt each, 1,104-1,166 prompt tokens and 153-283 completion tokens per case. Lexical
means over the 3 cases: token F1 0.811, context recall 0.917, groundedness 0.933. Three cases prove the path works (the model
called the search tool, the retrieved text was recorded and scored); they say nothing about agent quality. The agent pipeline had
only been tested with a scripted fake model before.

### Run 13 — pass-threshold sweeps against the AI-written labels (30 cases)

`ragwb calibrate --sweep`, `--rescore` for the metric the run did not have (computed from stored answers with the local model).

| Metric | Agreement / kappa at the default 0.70 | Best plateau |
|---|---|---|
| `correctness` (judge) | 0.967 / 0.870 | agreement is flat at 0.967 for every threshold from 0.25 to 0.70; 1.000 only at 0.10-0.20, which is one borderline case (v05 scored 0.20) |
| `semantic_similarity` (local model) | 0.867 / 0.595 | 0.967 / 0.839 for thresholds 0.55-0.65; 0.933 at 0.40-0.50; falls to 0.767 at 0.75 and 0.433 at 0.90 |

Reading it: the judge's default sits on a wide stable plateau, so nothing needs changing. The semantic metric's default 0.70 is
stricter than the data supports (it fails 4 answers the labeller passed), and unlike the extractive answers of run 9, these LLM
answers do separate from wrong ones by embedding similarity. The defaults were **not** changed: one document, 30 cases, 4
failures and one AI rater are not enough to move a threshold; the tooling to redo this with real labels exists.

### Run 14 — clean wheel install

`scripts/wheel_check.py` builds the wheel, installs it with all its dependencies from PyPI into a fresh virtual environment (25 s
on a warm cache) and uses it from a neutral folder: the wheel builds; it installs; the package imports from `site-packages`;
`--version` prints `ragwb 1.4.0`; an offline evaluation completes; data is written to the current directory and nothing lands in
`site-packages`; `doctor` reports 9 ok and 0 failures; `tune-abstention` finds the bundled examples; the run store reads back
(10/10). The first attempt found a real defect: the example folder was resolved relative to the project, so `tune-abstention`,
the first-launch demo runs and the dataset picker failed in a wheel install. Fixed, and the check now guards it.

### Run 15 — axe-core accessibility audit

axe-core 4.10.2 (WCAG 2.0/2.1/2.2 A and AA plus best practices; downloaded from the jsDelivr CDN, served to the browser from a
local port, run against this app's local pages only): Overview, Run results (summary, cases, case detail), Compare, Datasets and
Settings: **no violations** (38-43 rules passed per view; 1 "needs review" item on two views). New evaluation: **one minor
violation**, `presentation-role-conflict` on Streamlit's own file-uploader dropzone (2 nodes), which this project cannot change.
axe-core cannot see inside canvases; the table contents are checked by the keyboard walk instead.

### Run 16 — keyboard walks

Run results: 104 focus events over 40 Tab presses, returning to its first stop after 59, no trap. The walk revealed that tables
are exposed as `gridcell` elements (so assistive technology can read them) but that each cell is its own Tab stop and 23 stops are
on zero-size elements. Settings: 63 events over 40 presses, still inside its tables when stopped. Together with the earlier walk of
New evaluation this covers three of the six pages; Overview, Compare, Datasets and Accounts were not walked.

### Run 17 — 20 honeybee questions with all four judge metrics (Qwen), under the provider's token cap

| Metric | Mean | 95% CI | Scored | Failed (rate limit) |
|---|---:|---|---:|---:|
| Token F1 | 0.629 | 0.544–0.714 | 20 | 0 |
| Context recall (lexical) | 0.885 | 0.839–0.930 | 20 | 0 |
| Groundedness (lexical) | 0.920 | 0.862–0.969 | 20 | 0 |
| Answer relevancy (judge) | 0.925 | 0.800–1.000 | 20 | 0 |
| Faithfulness (judge) | 1.000 | 1.000–1.000 | 6 | 14 |
| Context relevancy (judge) | 0.429 | — | 1 | 19 |
| Correctness (judge) | 0.958 | 0.884–1.000 | 19 | 1 |

All 20 answers were produced (5,688 prompt and 613 completion tokens; DeepEval reported no judge cost). **The run took hours and is only
partly complete as an evaluation:** this model's free tier allows 1,000 output tokens per minute, the faithfulness and context-relevancy
judges write long outputs, and 34 of the 80 judge measurements kept hitting the limit until the retry budget (4 retries, at most 60 s
each) ran out. Those 34 were recorded as errors and left out of the means (never counted as zero), exactly as designed, so the
faithfulness mean rests on 6 cases and the context-relevancy mean on 1: treat both as missing, not as results. The three metrics that
fit the cap (answer relevancy, correctness, and the lexical ones) are complete or nearly so. Compared with run 7 on a different
document, `correctness` agrees in character (0.958 here, 0.803 there) but the samples differ. A paid tier, a provider without this cap,
or a longer retry budget (`RAGWB_MAX_RETRIES`) would complete the run; none was available.

## Failures found by the live runs, and what changed

1. **Rate limits recorded as opaque errors.** DeepEval wraps the provider error in tenacity's `RetryError`; the classifier
   did not look inside, so a 429 was not retried and the message was `RetryError[<Future ...>]`. Fixed: wrapped SDK errors are
   found and classified, and retries wait for the provider's `Retry-After`.
2. **Connection drops recorded as unexpected case errors.** The first fix walked an exception's cause chain to its end, past
   the OpenAI error to the underlying `httpx` transport error, which is not an OpenAI error. Found when the network dropped
   during run 6 (cases v16 and v17). Fixed: the search stops at the first OpenAI SDK error; a regression test reproduces
   the chain.
3. **Quota, not code.** Runs 5 and the earlier part of 6 stalled on daily token budgets (about 200,000 per model on this
   tier). Pacing (`RAGWB_MAX_REQUESTS_PER_MINUTE`) cannot create quota, and retries wait at most 60 s.
4. **Environment.** The development machine slept between steps and stalled long runs; unrelated to the code.

## Not covered

No run against OpenAI itself; the agent pipeline was run live on 3 cases only; no API-embedding or API-hybrid retrieval run; judge
metrics other than `correctness` were measured on at most 10 cases and only one judge-noise measurement exists; judge scores
were never compared with *human* labels (run 11 used an AI rater; the 30-case human labelling sheet in `calibration/` is still
waiting for a person);
accessibility was checked by script and one keyboard walk, not with a screen reader.
