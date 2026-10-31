# Part III — Choosing a configuration

A run is the answer to a question you asked the workbench, and the configuration is the question. "How good is my retrieval?" and "How good is my answer?" are different questions, and they need different settings. This Part walks through every choice you make before pressing Run, says what each option really measures, and gives you decision tables you can follow without reading any code.

Everything quoted as output in this Part was produced offline for this guide, with the bundled example data, the offline provider and the BM25 retriever, unless it says otherwise. Numbers that come from a live provider are quoted from `docs/LIVE_VERIFICATION.md` and carry the run number (for example "live run 17"). Those live runs used one provider's free tier, a few models and small samples. Treat them as examples of what to expect, not as benchmarks of any model.

## 3.1 The configuration at a glance

### 3.1.1 The twelve decisions

Every run records the same set of choices. Here they are in the order this Part covers them, with the CLI flag (or environment variable) that sets each one and the default.

| # | Decision | CLI flag or variable | Default | Section |
|---|---|---|---|---|
| 1 | Provider (who writes the answers) | `--provider offline\|openai` | `offline` | 3.2 |
| 2 | Pipeline (how context reaches the generator) | `--pipeline rag\|agent` | `rag` | 3.3 |
| 3 | Retriever (how chunks are found) | `--retriever bm25\|embedding\|hybrid\|local\|hybrid-local` | `bm25` | 3.4 |
| 4 | Chunks per query | `-k N` | `3` | 3.5 |
| 5 | Extractive baseline knobs | `--answer-sentences`, `--min-evidence`, `--skip-headings` | `2`, `0` (never abstain), off | 3.6 |
| 6 | Metrics | `--metrics a,b,c` | four lexical metrics offline; those plus four judge metrics with `--provider openai` | 3.7 |
| 7 | Pass thresholds | `--threshold METRIC=VALUE` | 0.5 for token F1 and ROUGE-L, 1.0 for exact match, 0.7 for the rest | 3.7 |
| 8 | Models | `--model`, `--judge-model`, `RAGWB_GENERATOR_MODEL`, `RAGWB_JUDGE_MODEL`, `RAGWB_EMBEDDING_MODEL` | `gpt-4o`, `gpt-4o`, `text-embedding-3-large` | 3.8 |
| 9 | Pacing, retries and budget | `RAGWB_MAX_REQUESTS_PER_MINUTE`, `RAGWB_MAX_RETRIES`, `RAGWB_RETRY_BASE_DELAY_S` | unpaced, 3 retries, 1 s | 3.9 |
| 10 | Parallelism | `--workers` | 1 offline, `RAGWB_MAX_WORKERS` (4) with `openai` | 3.10 |
| 11 | Time limits | `RAGWB_CASE_TIMEOUT_S`, `RAGWB_REQUEST_TIMEOUT_S` | 600 s, 60 s | 3.11 |
| 12 | Seed and size | `--seed`, `--limit` | `0`, all cases | 3.12 |

Two more settings shape every run but are not really choices: the dataset and the document. They are covered in Part II.

> **Why this works.** Because the workbench stores the whole configuration with each run, you can change one decision at a time and compare two runs afterwards (Part V). The single most valuable habit in configuration work is to change exactly one row of the table above between two runs.

### 3.1.2 What the defaults are good for

The defaults are chosen so that `ragwb run` works on a fresh checkout with no key and no network. They give you a deterministic baseline: BM25 retrieval, an extractive answer generator that copies the best sentences from the retrieved text, and four word-overlap metrics. That is the right starting point for learning the tool, for checking that a dataset loads, and for regression testing retrieval changes. It is not a measure of how a language model would answer.

Here is the shortest possible run, exactly as I ran it for this guide:

```text
$ ragwb run --name smoke --limit 3
[  1/3] ok  q01
[  2/3] ok  q02
[  3/3] ok  q03

Run 20261030-205005-smoke-b30ed3: completed
cases 3  ok 3  errors 0  mean latency 0.7 ms
metric                          mean           95% CI    pass  scored  skip  err
Token F1                       0.313      0.167-0.407      0%       3     0    0
ROUGE-L                        0.217      0.083-0.296      0%       3     0    0
Context recall (lexical)       0.917      0.750-1.000    100%       3     0    0
Groundedness (lexical)         1.000      1.000-1.000    100%       3     0    0
```

Read the output once, because the rest of this Part keeps returning to it. Context recall is high (the right words reached the generator), token F1 is low (the answer does not look like the reference), and groundedness is exactly 1.000. Section 3.2 explains why that pattern is expected, not a bug.

> **Pitfall.** Do not read a three-case run as a result. The 95% confidence interval for token F1 above runs from 0.167 to 0.407. A smoke run proves the plumbing works; it says almost nothing about quality.

## 3.2 Provider: offline baseline or an OpenAI-compatible model?

The provider decides who writes the answer. It is the first choice and the one with the largest consequences.

### 3.2.1 What each provider is

* **`offline`** is a deterministic extractive baseline. It is *not* a language model. It splits the retrieved chunks into sentences, scores each sentence by IDF-weighted overlap with the question's content words, and returns the best one or two (in their original order). It needs no key, no network and costs nothing. It runs at about 0.5 to 2 ms per case.
* **`openai`** sends the question and the retrieved chunks to a chat model at temperature 0 and records the model's answer, its token usage and its latency. "OpenAI" is a name for the protocol: any server that speaks the OpenAI chat API works when you set `OPENAI_BASE_URL` (see §3.8). It requires `OPENAI_API_KEY`.

### 3.2.2 What the offline provider can and cannot tell you

The offline provider answers the same way no matter which retriever feeds it, so a difference between two offline runs is a difference in *retrieval* (or in the extractive knobs), never in answer quality. That makes it a precise instrument for one job and a misleading one for another.

| You want to know... | Offline provider | OpenAI-compatible provider |
|---|---|---|
| Does my retriever find the passage that contains the answer? | Yes. Use context recall. | Yes, but with cost and noise you do not need. |
| Did my change to chunking or `k` make retrieval better or worse? | Yes, deterministically. | Only with extra cost. |
| Does my dataset, document and metric set load and score? | Yes. | Wasteful. |
| Is my answer well phrased, complete, not hallucinated? | **No.** The baseline cannot hallucinate and cannot paraphrase. | Yes. |
| Is groundedness informative? | **No.** It is 1.000 by construction because every answer sentence is copied from the context. | Yes (and the judge-based faithfulness is better still). |
| Will the system abstain on unanswerable questions? | Only if you tune `--min-evidence` (§3.6.2), and the measured trade-off is poor. | Depends on the prompt and model. |
| Is the run reproducible bit for bit? | Yes (only latency varies). | No. Temperature 0 helps but cannot pin a model snapshot. |

The measured numbers make the point. On the 20 honeybee questions the offline baseline gets a token F1 of 0.346 and a context recall of 0.885 (this is the run above, with all 20 cases). Live run 17 (a Qwen model as generator on the same 20 questions, with BM25 and k = 3) got a token F1 of 0.629 and a context recall of 0.885. The context recall is identical because the retriever is identical; only the answers changed. That single comparison tells you what the baseline is for: it is a floor. A live model that does not beat it on the same data is not doing useful work.

> **Why this works.** The baseline is a lower-bound control, in the sense that a drug trial has a placebo arm. When a metric moves between two live runs, you can check whether the same metric moves in the baseline. If it does, the cause is retrieval, not the model.

### 3.2.3 Decision table

| Situation | Choose | Reason |
|---|---|---|
| First time with the tool, a CI check, a classroom | `offline` | Free, fast, deterministic, no secrets. |
| You are tuning retrieval (k, retriever, skip headings) | `offline` first | Retrieval effects are isolated from model noise. Confirm the winner live once. |
| You must judge answer quality, hallucination, refusals | `openai` | Only a model produces paraphrase, partial answers and refusals. |
| You must compare two generator models | `openai` for both, with the same retriever and `k` | Keep everything else fixed. |
| You have no budget or no key | `offline`, and say so in the report | Never present extractive-baseline numbers as model quality. |
| You want a regression gate in CI | `offline` | Deterministic, so `ragwb regress` has no noise to explain away. |

### 3.2.4 A staged workflow that saves money

1. Run the offline baseline on the whole dataset. Fix dataset errors and obvious retrieval problems here, where a run takes a fraction of a second.
2. Run the live provider on `--limit 3` with only the cheapest metrics. Check that answers, contexts and token counts look sane.
3. Run the live provider on the full dataset with lexical metrics plus at most one judge metric (`correctness` is the cheapest informative one).
4. Add the other judge metrics only when the first live run shows they are needed, and pace them (§3.9).

Part IV (live runs) shows the same staging with the real commands.

## 3.3 Pipeline: retrieve-then-generate or tool-calling agent?

### 3.3.1 What each pipeline does

* **`rag` (retrieve → generate)**: the workbench retrieves the top-k chunks for the question and hands exactly those to the generator. The context you score is the context the generator saw. There is one model call per case.
* **`agent`**: a tool-calling agent receives the question and a search tool (named `collecting_info`). The agent decides whether to call the tool, with which query, and how many times. Every chunk the tool returns is captured; those chunks, de-duplicated and ranked by the order they were found, become the recorded context (`context_source = agent_tool`). The agent's own description of the context it used is stored separately as an audit field (`model_context_claim`) and is never scored. There can be several model calls per case.

The agent pipeline needs a tool-calling model and therefore the `openai` provider. Combining `--provider offline` with `--pipeline agent` is refused:

```text
$ ragwb run --name x --pipeline agent --quiet
error: The agent pipeline needs a tool-calling LLM; choose provider 'openai' or pipeline 'rag'.
```

### 3.3.2 What each pipeline really measures

The key sentence of this section: **in both pipelines, the context that is scored is the context that was retrieved**. Context recall, groundedness, faithfulness and context relevancy never see anything the system did not retrieve. That has three consequences.

| Property | `rag` | `agent` |
|---|---|---|
| Number of chunks scored per case | exactly `k` | whatever the agent's tool calls returned (up to `k` per call, de-duplicated); may be fewer or more than `k` |
| What a low context recall means | the retriever missed the answer's words in its top k | the agent never searched, searched poorly, or the retriever missed |
| Does `k` mean the same thing? | yes, a fixed budget | no, it is *per tool call* |
| Cost per case | one generation call | several calls (one per reasoning step) plus the tool calls |
| Comparability between runs | high | lower: the agent's strategy varies |

So the two pipelines answer different questions. The `rag` pipeline measures *your retriever plus your generator on a fixed recipe*. The `agent` pipeline measures *the whole agent as a system*, including its decision to search. If you want to know whether a new retriever is better, use `rag`, because the agent's search behaviour is a second variable. If you want to know whether the product you actually ship (an agent with a search tool) works, use `agent`, because `rag` does not exercise the loop.

> **Pitfall.** With the agent pipeline, a case in which the model answers from its own knowledge without calling the tool has *empty context*. Context-based metrics are then skipped for that case, not scored as zero. A run whose "scored" count for `context_recall` is lower than its case count may mean the agent skipped retrieval. Look at `context_source` and the number of contexts in the case detail (Part V).

### 3.3.3 What has been verified

The agent pipeline was run live exactly once, on 3 honeybee questions with a Qwen model (live run 12): all three answered, each with 3 chunks captured from the agent's tool calls, one attempt each, 1,104 to 1,166 prompt tokens and 153 to 283 completion tokens per case. The lexical means over those three cases (token F1 0.811, context recall 0.917, groundedness 0.933) prove the path works. They say nothing about agent quality. Before that it had only been tested with a scripted fake model. If you rely on the agent pipeline, run your own small live check first (Part IV (live runs)).

### 3.3.4 Decision table

| If you are evaluating... | Choose |
|---|---|
| a retriever, a chunking change, `k` | `rag` |
| a generator model or a prompt, with retrieval held fixed | `rag` |
| a deployed assistant that decides when to search | `agent` |
| anything offline | `rag` (the only option) |
| something on a tight token budget | `rag`: the agent pays for several model turns per case |

## 3.4 Retriever: bm25, embedding, hybrid, local, hybrid-local

### 3.4.1 The five retrievers

| Name | How it ranks | Needs | Network | Good at | Weak at |
|---|---|---|---|---|---|
| `bm25` | Okapi BM25 over content words (light stemming, no synonyms) | nothing | none | exact terms, names, numbers, rare words | paraphrase and synonyms ("parasite" vs "parasitic", "threatens" vs "threats") |
| `embedding` | cosine similarity of API embeddings | `OPENAI_API_KEY` and an embeddings endpoint | yes, to embed every chunk and every query | paraphrase, loose wording | exact identifiers, cost, provider availability |
| `hybrid` | BM25 and API embeddings fused by reciprocal rank (RRF, constant 60) | same as `embedding` | yes | a safe default when both signals matter | needs an embeddings endpoint |
| `local` | cosine similarity of a local embedding model (default `BAAI/bge-small-en-v1.5`) | optional `fastembed` package | one-time model download, none afterwards | paraphrase with no key and no per-call cost | model download, disk space, Windows long paths |
| `hybrid-local` | BM25 and the local model fused by RRF | same as `local` | one-time download | paraphrase without losing exact matches | same as `local` |

Hybrid retrievers take a wider pool from each ranker (three times k) before fusing, then keep the top k of the fused ranking.

Which of these your own installation offers is visible in the New evaluation page: `embedding` and `hybrid` appear only when an API key is configured, and `local` and `hybrid-local` only when `fastembed` is importable (Part IV).

### 3.4.2 The evidence: run 9

The project measured all three offline-capable retrievers with a real local embedding model across five datasets (live-verification run 9, offline provider, k = 3). The table below is that record, trimmed to lexical context recall, which is the metric that isolates retrieval. All rows are means over every case of the dataset.

| Dataset | bm25 | local | hybrid-local | Best |
|---|---:|---:|---:|---|
| honeybees (20 questions) | 0.885 | 0.792 | 0.870 | bm25 |
| honeybees-paraphrased (5 questions) | 0.664 | 0.786 | 0.697 | local |
| volcanoes (30 questions) | 0.660 | 0.738 | 0.666 | local |
| coffee (30 questions) | 0.765 | 0.801 | 0.801 | local, hybrid-local (tie) |
| lighthouses (30 questions) | 0.819 | 0.835 | 0.824 | local |

The same record gives token F1 and the two semantic metrics. Honeybees under hybrid-local had the best token F1 of the table (0.376 against 0.346 for bm25 and 0.340 for local). The semantic columns barely moved at all: values between 0.63 and 0.76 for every retriever on every dataset.

I reproduced the BM25 rows of this table independently for this guide. With `--retriever bm25 -k 3` on each bundled dataset, the offline provider gave the same token F1 and context recall: honeybees 0.346 and 0.885, honeybees-paraphrased 0.225 and 0.664, volcanoes 0.199 and 0.660, coffee 0.257 and 0.765, lighthouses 0.212 and 0.819. (I did not re-run the `local` and `hybrid-local` rows: they need a model download, which was not allowed while writing this guide.)

### 3.4.3 Reading the table honestly

* **There is no consistent winner.** `local` is best or tied for best on four of five datasets for context recall, and worst on the one with the most exact-term questions (honeybees: 0.885 down to 0.792).
* **The sets are small.** Five questions for the paraphrased set, 20 to 30 for the rest. Differences of 0.02 to 0.04 are inside the noise of such samples (the confidence intervals of the offline runs are typically 0.1 wide or more).
* **The gain from embeddings is largest where questions are paraphrased.** On the paraphrased honeybee questions local embeddings raised context recall from 0.664 to 0.786, a gain of 0.122 that is bigger than anything else in the table.
* **Hybrid is a hedge, not a magic wand.** In these data `hybrid-local` stayed close to BM25 (0.870 against 0.885 on honeybees, 0.666 against 0.660 on volcanoes), because with a short document BM25's ranking dominates the fusion.
* **Semantic metrics barely distinguished the retrievers**, because the extractive baseline gives the same answer whatever the retriever, and the embedding cosines have a high floor (a paraphrase scored 0.847 and an unrelated sentence 0.501 in a direct check). That is a statement about the metrics, not a verdict on the retrievers.

> **Pitfall.** Do not use semantic *answer* metrics on offline runs to compare retrievers. The extractive baseline picks sentences from the retrieved text, so a better retriever changes the answer only a little, and the semantic score has a high floor. Compare retrievers with context recall (lexical or semantic) and, live, with the judge's context relevancy.

### 3.4.4 A worked example: the paraphrase problem

BM25 has only light stemming and no synonyms. The question "Which parasite threatens honeybee colonies?" fails on the bundled honeybee document because the document says "threats" and "parasitic". BM25 ranks the title chunk first and the varroa paragraph third. This is a known limitation recorded in `docs/KNOWN_LIMITATIONS.md`.

The bundled paraphrased set was written to expose exactly this. Offline BM25 on it:

```text
$ ragwb run --name para --dataset examples/datasets/honeybees_paraphrased.csv --quiet
cases 5  ok 5  errors 0  mean latency 0.7 ms
Token F1                       0.225      0.109-0.360      0%       5     0    0
Context recall (lexical)       0.664      0.533-0.792     20%       5     0    0
```

Context recall falls to 0.664 from 0.885 on the original questions. That is the signature to look for: when a paraphrased version of your question set loses recall and the original does not, your retriever depends on exact wording. A dense or hybrid retriever is then worth testing.

### 3.4.5 Decision table

| If... | Then choose | Because |
|---|---|---|
| your questions reuse the document's own words (manuals, specs, FAQs) | `bm25` | It was best on the original honeybee set and costs nothing. |
| your users paraphrase freely | `local`, then compare with `hybrid-local` | Run 9's largest gain was on paraphrased questions. |
| questions mix exact terms and loose wording | `hybrid-local` (or `hybrid` with an embeddings API) | A hedge that stayed close to the better of the two. |
| you have no key and no model download allowed | `bm25` | Everything else needs one of the two. |
| your provider has no embeddings endpoint | `bm25`, `local` or `hybrid-local` | The only provider tested has none (§3.8.4). |
| you need identifiers, part numbers, error codes | `bm25` or a hybrid | Dense models blur exact strings. |
| you are unsure | run `bm25` and `local` on 20 or more of *your own* questions, `-k 3`, and compare `context_recall` | The bundled data cannot decide this for your documents. |

### 3.4.6 Practical notes about local and API embeddings

* **Local model download.** The first use of `local` or `hybrid-local` (or either semantic metric) downloads the configured model (`RAGWB_LOCAL_EMBEDDING_MODEL`, default `BAAI/bge-small-en-v1.5`) into `<data dir>/models`. After that, no data leaves the machine.
* **Windows paths.** The model cache nests folders deeply and can exceed Windows' 260-character path limit under a long data directory. Keep `RAGWB_DATA_DIR` short.
* **API embeddings cost.** The `embedding` and `hybrid` retrievers build their index in memory for the run, embedding every chunk on first use and every query. In the code I read, nothing persists that index between runs, so each run pays to embed the whole document again. For a large document this is a real cost; the local retrievers have no per-call price.
* **Untested.** API embeddings and API hybrid retrieval were never run live (the only provider tested has no embeddings endpoint). If you use them, make a three-case check first.

## 3.5 Chunks per query (k)

### 3.5.1 What k controls

`k` is the number of chunks the retriever returns per query (CLI `-k`, default 3, allowed 1 to 50; the New evaluation slider goes from 1 to 10, or fewer when the document has fewer chunks). The "chunks" are the document's text blocks (paragraphs or similar blocks, at most 2,000 characters each); the workbench does not expose a chunk-size setting, so `k` is your main handle on how much context the generator sees. The bundled honeybee PDF has 11 chunks, so `k = 5` retrieves almost half of the document.

There are three effects to keep apart:

1. **Recall rises with k.** More chunks mean more chances to contain the reference's words.
2. **Precision falls with k.** More chunks mean more irrelevant text. A judge-based context relevancy score drops as `k` grows, and a generator can be distracted.
3. **The extractive baseline picks from everything it is given.** With more chunks it can choose a high-overlap sentence from a less relevant chunk.

### 3.5.2 The real findings: k = 1, 3 and 5

I ran the offline baseline on four datasets at three values of `k` (BM25, two sentences per answer). Context recall and token F1 are means over all cases; "n" is the number of questions.

| Dataset (n) | k | Token F1 | Context recall | Token F1 pass rate | Context recall pass rate |
|---|---:|---:|---:|---:|---:|
| honeybees (20) | 1 | 0.404 | 0.857 | 20% | 90% |
| honeybees (20) | 3 | 0.346 | 0.885 | 5% | 95% |
| honeybees (20) | 5 | 0.346 | 0.892 | 5% | 95% |
| volcanoes (30) | 1 | 0.199 | 0.571 | 10% | 32% |
| volcanoes (30) | 3 | 0.199 | 0.660 | 3% | 44% |
| volcanoes (30) | 5 | 0.199 | 0.693 | 3% | 56% |
| coffee (30) | 1 | 0.259 | 0.679 | 13% | 64% |
| coffee (30) | 3 | 0.257 | 0.765 | 10% | 76% |
| coffee (30) | 5 | 0.260 | 0.826 | 10% | 80% |
| lighthouses (30) | 1 | 0.255 | 0.762 | 13% | 68% |
| lighthouses (30) | 3 | 0.212 | 0.819 | 10% | 76% |
| lighthouses (30) | 5 | 0.212 | 0.828 | 10% | 76% |

Context recall is scored on 25 of the 30 cases in the three 30-question datasets, because the 5 unanswerable questions have no reference to recall (they are skipped, not zeroed).

Three patterns hold across all four documents:

* **Context recall rises with k, with diminishing returns.** The jump from 1 to 3 is larger than the jump from 3 to 5 in every dataset (honeybees +0.028 then +0.007; volcanoes +0.089 then +0.033; coffee +0.086 then +0.061; lighthouses +0.057 then +0.009), though coffee keeps climbing noticeably.
* **Token F1 does not rise with k, and on two documents it falls.** On honeybees it drops from 0.404 at k = 1 to 0.346 at k = 3; on lighthouses from 0.255 to 0.212. Token F1 is flat on volcanoes and coffee. This matches the note in `docs/KNOWN_LIMITATIONS.md`: with more retrieved chunks the extractive baseline can pick sentences from less relevant passages.
* **k = 5 on honeybees equals k = 3 on token F1** (0.346 both) because the extractive baseline already finds its best two sentences within the top 3.

### 3.5.3 A worked example: the same question at k = 1, 3, 5

Question q01, "How many queens does a typical honeybee colony have?" (reference: "A colony normally has a single queen."). Extractive answer, chunk ids with BM25 scores in brackets:

| k | Chunks retrieved | Answer produced | Token F1 | Context recall |
|---:|---|---|---:|---:|
| 1 | p1-b3 (3.57) | "The queen is the only fully fertile female in the colony. After a mating flight early in her life, she stores sperm from many drones and can lay up to two thousand eggs a day during the peak of the season." | 0.103 | 0.50 |
| 3 | p1-b3 (3.57), p1-b2 (3.17), p2-b1 (3.10) | "The queen is the only fully fertile female in the colony. Honeybees are important pollinators of many fruit, nut and seed crops." | 0.167 | 0.75 |
| 5 | adds p1-b1 (2.61), p1-b10 (2.15) | same as k = 3 | 0.167 | 0.75 |

Notice what happened. The retrieval got *better* from k = 1 to k = 3 (context recall rose from 0.50 to 0.75, because the extra chunk supplied a reference word). The answer did not get better: the second sentence of the k = 3 answer is an irrelevant pollination sentence from a chunk the retriever pulled in to fill a slot. Neither answer says "single queen" in the reference's words, which is why token F1 stays below 0.2 for a basically correct first sentence.

Question q14, "Why do bees build hexagonal cells?", shows the opposite. At k = 1 the answer is two sentences from the right chunk and scores token F1 0.50. At k = 3 the extractive generator's second sentence comes from a different chunk about worker roles, and token F1 falls to 0.151 even though context recall stayed at 0.875.

> **Why this works.** A paired comparison tells you whether such a drop is real rather than noise. `ragwb compare` on the k = 1 and k = 3 honeybee runs reports token F1 down 0.057 with a 95% interval of -0.116 to -0.008 (3 questions better, 10 tied, 7 worse), and context recall up 0.028 with an interval that touches zero (3 better, 17 tied, 0 worse). The tool concludes the first is a real drop; the second is a possible gain. Part V explains how to read these tables.

### 3.5.4 Choosing k: a procedure

1. Start with `k = 3`. It is the default and a sensible middle on every document tested.
2. Run `k` = 1, 3 and 5 offline with the same dataset, one run each, and name them `k1`, `k3`, `k5`.
3. Compare context recall. If the gain from 3 to 5 is below about 0.03 and its interval includes zero, stay at 3.
4. If you will use a live generator, remember that the offline token F1 tells you about the *extractive baseline's* sentence picking, not about your model. A live model is free to ignore the irrelevant chunk. Re-check the winner with `correctness` and `context_relevancy` live on a small sample.
5. Record the choice in the run's notes (`--notes "chose k=3: recall gain from 5 under 0.03"`).

| If... | Then |
|---|---|
| answers are short facts and the document is paragraph-sized | `k` 1 to 3 |
| questions need information from several places | `k` 5 or more, and use a live generator, not the baseline |
| your live judge's context relevancy is low | lower `k`: it measures the share of retrieved statements that are relevant, so extra chunks lower it |
| context recall is low at every k | fix the retriever, the dataset's reference wording or the chunking, not `k` |
| the document has only a handful of chunks | cap `k` below the chunk count; the New evaluation slider does this for you |

> **Pitfall.** Context recall is a set measure over the union of all retrieved chunks. A reference word found in an irrelevant chunk counts as recalled. At large `k` the metric becomes easy to satisfy, so "recall at k = 5" can look better than the retriever deserves. Pair it with the judge's context relevancy when you can afford it.

## 3.6 The extractive baseline's three knobs

These three settings apply only to the offline provider (the first two) and to the chunk list (the third). They exist so you can use the baseline as a controlled instrument.

### 3.6.1 Answer sentences (`--answer-sentences`)

The baseline returns this many best-matching sentences (default 2, up to 10; the New evaluation page calls it "Sentences per extractive answer"). More sentences raise recall of the reference's words and lower precision. Honeybees, k = 3:

| Sentences | Token F1 | ROUGE-L | Token F1 pass rate | Context recall |
|---:|---:|---:|---:|---:|
| 1 | 0.419 | 0.395 | 45% | 0.885 |
| 2 (default) | 0.346 | 0.317 | 5% | 0.885 |
| 3 | 0.297 | 0.270 | 5% | 0.885 |

Context recall is unchanged because the sentence count does not change which chunks were retrieved. Token F1 falls as sentences are added because the extra sentences are padding relative to a one-sentence reference.

How to use this: if your reference answers are one sentence long, set `--answer-sentences 1` to make the baseline's token F1 a fairer floor. If your references are multi-sentence, leave it at 2 or 3. Whichever you choose, keep it fixed across the runs you compare, and note it.

> **Pitfall.** The default of 2 is a convention, not a measurement of your references' length. A baseline floor that is artificially low (as token F1 0.346 at 2 sentences against 0.419 at 1) makes a live model look better than it is. Report the baseline setting next to the baseline number.

### 3.6.2 Abstention: `--min-evidence` and `ragwb tune-abstention`

By default the extractive baseline always answers, as long as at least one sentence shares a content word with the question. It abstains (returns the standard "The PDF does not provide enough information to answer the question." sentence) only if *no* sentence shares any word. That essentially never happens on the bundled documents, because every question shares content words with the document, including the unanswerable ones.

`--min-evidence X` (0 to 1) makes the baseline abstain unless the chosen sentences together cover at least that share of the question's content terms, weighted by IDF. It is a crude proxy for "the passages answer this question".

I ran the six-question unanswerable honeybee set (four unanswerable questions plus two answerable controls) with and without it:

```text
$ ragwb run --name unans --dataset examples/datasets/honeybees_unanswerable.jsonl --quiet
Token F1                       0.039      0.000-0.102      0%       6     0    0
Context recall (lexical)       1.000      1.000-1.000    100%       2     4    0
Groundedness (lexical)         1.000      1.000-1.000    100%       6     0    0

$ ragwb run --name unans-me --dataset examples/datasets/honeybees_unanswerable.jsonl \
      --min-evidence 0.7 --skip-headings --quiet
Token F1                       0.698      0.365-1.000     67%       6     0    0
Context recall (lexical)       1.000      1.000-1.000    100%       2     4    0
Groundedness (lexical)         1.000                -    100%       1     5    0
```

Token F1 jumped from 0.039 to 0.698 because the four unanswerable questions now got the correct abstention (the reference answer for an unanswerable row is the abstention sentence, so a matching abstention scores 1.0). Groundedness now has only one scored case, because abstentions are skipped (there is nothing to ground). This is the evidence behind the statement in `docs/KNOWN_LIMITATIONS.md`: at 0.7 with `--skip-headings`, the baseline abstained on all four unanswerable questions but also on one answerable control.

**Does it generalise? Ask the tuner.** `ragwb tune-abstention` chooses `--min-evidence` on a development half of the bundled unanswerable-bearing datasets and reports on a held-out half. This is the real output:

```text
$ ragwb tune-abstention
Development questions: 51 | test questions: 45
Chosen on the development half: min_evidence=0.8

setting                             declined unanswerable  answered answerable  balanced acc.
Held-out test half:
  min_evidence=0.0 (default)                 0/12 (0.000)        33/33 (1.000)          0.500
  min_evidence=0.8 (tuned)                  10/12 (0.833)         9/33 (0.273)          0.553

Development half, every setting (best five):
  min_evidence=0.8                            7/7 (1.000)        19/44 (0.432)          0.716
  ...
Only 12 unanswerable test questions (fewer than 30): treat the test figures as rough.
```

Read it as the project's own documentation does. On the held-out half, the tuned threshold declined 10 of 12 unanswerable questions (good) but also declined 24 of 33 answerable ones (bad): balanced accuracy 0.553 against 0.500 for never abstaining. **It does not pay off on the bundled data.** The default stays at no abstention. The extractive baseline cannot tell an unanswerable question from a hard one by word overlap alone; a real fix needs a model that judges whether the passages answer the question.

When is it still worth running?

| Situation | Use `--min-evidence`? |
|---|---|
| Your questions are mostly answerable and abstention is not part of what you evaluate | No. Leave it at 0. |
| You want to see how abstention changes the metrics (a teaching demo) | Yes, as in the run above. |
| You have your own dataset with many labelled unanswerable questions | Run `ragwb tune-abstention --dataset yours.jsonl --document yours.pdf`, read the held-out half, and adopt a value only if balanced accuracy beats 0.500 clearly. |
| You evaluate a live model's refusals | Not applicable: the knob is offline-only. Judge refusals with `correctness` against the abstention reference. |

Part VI has a full playbook for unanswerable questions.

### 3.6.3 Skipping headings (`--skip-headings`)

PDF documents often have a title or section heading as its own block. It becomes a chunk with no sentence punctuation, and BM25 may rank it highly because it repeats the topic's key words. The extractive baseline can then return the title as part of the answer. `--skip-headings` drops short blocks that do not end like a sentence before indexing. It is off by default so that results stay comparable with earlier runs, and the heuristic can drop a real short chunk.

On honeybees (k = 3, two sentences) the effect is small: token F1 0.346 to 0.334, ROUGE-L 0.317 to 0.305, context recall unchanged at 0.885. It did not help there, and it slightly lowered token F1. That is the honest finding: it matters when the title outranks the evidence (the "parasite" question in §3.4.4), not as a free improvement.

| If... | Then |
|---|---|
| a failing case's answer or context contains the document title | try `--skip-headings` on a copy of the run and compare |
| your document has many short one-line items that are real content (glossaries, spec tables) | do **not** use it; it can drop them |
| you compare runs across time | keep the setting fixed, or the comparison is not like for like |

## 3.7 Metrics

`ragwb metrics` prints the catalogue. There are eleven metrics: five lexical, two semantic and four judge-based. ("The nine-plus" in casual talk is these eleven; `exact_match`, `semantic_similarity` and `semantic_context_recall` are the ones people forget.)

### 3.7.1 The catalogue

| Metric | Family | Default threshold | Needs | What it measures |
|---|---|---:|---|---|
| `exact_match` | lexical | 1.0 | reference | The normalised answer string equals the reference. |
| `token_f1` | lexical | 0.5 | reference | SQuAD-style token-overlap F1 between answer and reference. |
| `rouge_l` | lexical | 0.5 | reference | Longest-common-subsequence F1: like token F1 but order-sensitive. |
| `context_recall` | lexical | 0.7 | reference, context | Share of the reference's content terms found in the retrieved context. **Retrieval.** |
| `groundedness` | lexical | 0.7 | context | Share of the answer's content terms found in the retrieved context. |
| `semantic_similarity` | semantic | 0.7 | reference, `fastembed` | Embedding cosine between answer and reference. |
| `semantic_context_recall` | semantic | 0.7 | reference, context, `fastembed` | Best embedding similarity between the reference and any retrieved chunk. **Retrieval.** |
| `answer_relevancy` | judge | 0.7 | a judge model | Share of the answer's statements the judge finds relevant to the question. |
| `faithfulness` | judge | 0.7 | context, a judge model | Share of the answer's claims the judge finds supported by the context. |
| `context_relevancy` | judge | 0.7 | context, a judge model | Share of retrieved-context statements the judge finds relevant to the question. **Retrieval (precision).** |
| `correctness` | judge | 0.7 | reference, a judge model | A rubric score (GEval) of factual agreement between answer and reference. |

Three metrics measure *retrieval* (`context_recall`, `semantic_context_recall`, `context_relevancy`); the other eight measure the *answer*. The offline default set is `token_f1, rouge_l, context_recall, groundedness`; with `--provider openai` the four judge metrics are added.

### 3.7.2 Lexical, semantic or judge?

| Property | Lexical | Semantic (local model) | Judge (LLM) |
|---|---|---|---|
| Cost | zero | zero per call; one model download | API calls, several per measurement |
| Network | none | none after download | yes |
| Deterministic | yes | yes | no (a model's opinion) |
| Understands paraphrase | no | partly | yes |
| Speed | microseconds | milliseconds | seconds, and rate limits |
| Validated against labels here | token F1 poor, groundedness moderate (run 11) | threshold sweep, one document (run 13) | `correctness` strong on one easy document (run 11) |
| Best use | regression gates, retrieval checks, first pass | paraphrase-tolerant answer check, retrieval check | final answer quality, hallucination, relevance |

Every family has a failure mode you should know.

* **Lexical metrics measure word overlap, not meaning.** A correct paraphrase scores low. In live run 11, token F1 passed only 14 of the 26 answers a labeller (an AI rater, not a person) had passed: agreement 0.600, kappa 0.237 (fair). Its low pass rate is a property of the metric on paraphrased references, not of the answers.
* **Semantic metrics have a high floor.** The default local model gives about 0.5 for unrelated text and about 0.85 for a paraphrase, so a 0.7 threshold means little until calibrated. In live run 13, `semantic_similarity` with the default 0.70 agreed with the AI-written labels on 0.867 of the cases, but thresholds of 0.55 to 0.65 agreed on 0.967.
* **Judges are model opinions.** They vary with the judge model, cost money, hit rate limits and have call-to-call jitter (§3.7.5).

### 3.7.3 Which metric for which question

| You want to know... | Use | Do not use |
|---|---|---|
| Did retrieval fetch the passage that contains the answer? | `context_recall`; add `semantic_context_recall` for paraphrased references | `groundedness` |
| Is retrieval returning too much irrelevant text? | `context_relevancy` (judge) | `context_recall` (it only rewards presence) |
| Does the answer match the reference closely in wording? | `token_f1`, `rouge_l` | `exact_match` unless references are short canonical strings (names, numbers, dates) |
| Is the answer factually equal to the reference, in any wording? | `correctness` (judge); `semantic_similarity` as a free approximation | lexical overlap alone |
| Does the answer stay within the retrieved evidence (no hallucination)? | `faithfulness` (judge) | `groundedness` on the extractive baseline (always 1.0) |
| Is the answer on-topic? | `answer_relevancy` (judge) | any reference-based metric |
| Is a configuration change safe? (CI) | lexical metrics plus `ragwb regress` | judge metrics (noisy, costly) |

Two practical rules come out of this.

1. **Pair a lexical metric with a meaning metric.** Token F1 says whether the words match; `correctness` or `semantic_similarity` says whether the meaning matches. When they disagree (high correctness, low token F1) you have found a paraphrase, not a failure.
2. **Pair a retrieval metric with an answer metric.** An answer metric moving without a retrieval metric moving means the generator changed. The reverse means retrieval changed.

### 3.7.4 Thresholds and pass rates

Every metric produces a score in [0, 1] per case. The *threshold* turns a score into pass or fail, and the *pass rate* is the share of scored cases at or above it. The mean does not depend on any threshold and is the primary statistic. The pass rate is useful for "how many cases are good enough" questions, but it is only meaningful together with its threshold.

The default thresholds are conventions. They were not derived from data. Token F1 at 0.5 is the clearest example:

```text
$ ragwb run --name honeybees-default --quiet           # threshold token_f1 = 0.5
Token F1                       0.346      0.285-0.419       5%      20     0    0

$ ragwb run --name thr --threshold token_f1=0.3 --threshold rouge_l=0.3 --quiet
Token F1                       0.346      0.285-0.419      60%      20     0    0
ROUGE-L                        0.317      0.252-0.393      45%      20     0    0
```

The mean (0.346) and the scores themselves did not change. Moving the threshold from 0.5 to 0.3 moved the pass rate from 5% to 60%. Neither percentage is "right"; they answer different questions. Because the threshold is stored with the run, you can always see which was used, but two runs with different thresholds have incomparable pass rates. Rules:

* Quote the mean and interval first, the pass rate second, always with the threshold.
* Compare pass rates only between runs that used the same threshold.
* To set a threshold on a defensible basis, calibrate it (§3.7.6).

### 3.7.5 Judge metrics: cost, skips and noise

* **One measurement is several calls.** DeepEval's faithfulness metric extracts claims and then verifies each one; context relevancy splits the context into statements and judges them. Plan for several API calls and substantial output tokens per measurement. Part IV (live runs) shows what that does to a free tier.
* **Abstentions are not skipped by judge metrics.** Only the lexical groundedness and context recall skip abstentions. A judge scores an abstention like any other answer, which is usually what you want for `correctness` against an abstention reference.
* **Failures are excluded, never zeroed.** A measurement that fails after its retries is recorded as an error for that metric on that case and left out of the mean. The run's "scored" and "err" columns tell you how much of the mean rests on how many cases. In live run 17, the faithfulness mean rested on 6 of 20 cases and context relevancy on 1: those means are missing, not results.
* **Noise.** `ragwb judge-noise` re-scores stored answers to measure the jitter between repeated measurements (it makes API calls). Live run 8 (`correctness`, 10 cases, 3 repeats): within-case SD 0.023, between-case SD 0.371, noise to signal ratio 0.062, one of ten cases flipping its pass or fail verdict. For that judge, model and rubric the jitter is small next to real differences between cases. Other judge metrics were not measured.

### 3.7.6 Picking a threshold with `ragwb calibrate --sweep`

Calibration needs *labels*: a pass or fail verdict per case that you trust. `ragwb labels-template RUN_ID --out labels.csv` writes a CSV of the run's cases with a blank `human_pass` column; fill it with `pass` or `fail`, then run:

```text
ragwb calibrate RUN_ID --labels labels.csv --metric correctness --sweep
```

The report shows a confusion table, agreement, Cohen's kappa, and (with `--sweep`) the agreement and kappa at every threshold from 0.10 to 0.95. `--rescore` computes an offline or local-model metric the run does not have from its stored answers, with no API calls. If that metric cannot be computed for any case (for example the local embedding model cannot be loaded), `--rescore` fails with a clear message instead of printing a report of zeros.

The project ships labels, but they are **AI-written labels**: `calibration/volcanoes-labels-by-claude.csv` holds pass or fail verdicts for the 30 answers of live run 7, written by Claude (an AI model), not by a person. The column is called `human_pass` because the tool names it that way; the report header says only "labels from <file name>". The human labelling sheet (`calibration/volcanoes-labelling-sheet.csv`) is still waiting for a person. Using the run 7 bundle from `calibration/` and those labels, I reproduced the live-run result offline (no API call is needed because the judge scores are stored in the bundle):

```text
$ ragwb import calibration/20261028-035657-qwen-volcanoes-30-b-7d604e.json
$ ragwb calibrate 20261028-035657-qwen-volcanoes-30-b-7d604e \
      --labels calibration/volcanoes-labels-by-claude.csv --metric correctness --sweep
Correctness (judge) vs labels from volcanoes-labels-by-claude.csv, run qwen-volcanoes-30-b [20261028-035657-qwen-volcanoes-30-b-7d604e]
labelled cases matched: 30   compared: 30   metric did not score: 0   labels for unknown cases: 0
                    human pass   human fail
metric pass                25            0
metric fail                 1            4
agreement 0.967   kappa 0.870 (almost perfect)   precision 1.000   recall 0.962
pass rate: metric 0.833, human 0.867

 threshold  agreement   kappa  metric pass rate
      0.10      1.000   1.000             0.867   <- best
      0.20      1.000   1.000             0.867
      0.25      0.967   0.870             0.833
      ...
      0.70      0.967   0.870             0.833
      0.75      0.900   0.672             0.767
      0.95      0.767   0.420             0.633
The best row is chosen on these same labels, so it is optimistic; ...
```

How to read a sweep:

1. **Look for a plateau, not a peak.** Agreement is flat at 0.967 for every threshold from 0.25 to 0.70, so the default of 0.70 sits on a wide stable plateau and nothing needs changing. A threshold you would defend is one in the middle of a plateau.
2. **Distrust the `<- best` marker.** It is chosen on the same labels it is scored on, so it is optimistic. Here it picks 0.10 (agreement 1.000) only because one borderline case scored 0.20.
3. **Count the failures.** Only 4 of the 30 labels are fails. A sweep with a handful of fails cannot show how the metric treats subtle errors.
4. **Confirm on new labels before changing a default.** The project did not change its defaults after these sweeps: one document, 30 cases and one AI rater are not enough.

The same calibration command on the lexical groundedness in that run gives agreement 0.909 and kappa 0.463 (moderate) on 22 compared cases (8 skipped as abstentions), and on token F1 the live-run record gives agreement 0.600 and kappa 0.237. The ranking (judge strongest, token F1 weakest) is the finding; the absolute numbers are small-sample.

> **Pitfall.** Labels belong to a particular *set of answers*. I demonstrated the danger by running the offline baseline on the volcano dataset and calibrating its token F1 against the same AI-written labels:
>
> ```text
> $ ragwb calibrate <offline volcano run> --labels calibration/volcanoes-labels-by-claude.csv --metric token_f1 --sweep
> agreement 0.167   kappa 0.011 (slight)   precision 1.000   recall 0.038
> pass rate: metric 0.033, human 0.867
> ```
>
> That result is meaningless: the labels judged the *live model's* answers, not the baseline's. The case ids match, so the tool ran without complaint, but a label for "v05" describes a different answer text. Always generate labels from the run you calibrate (`labels-template`) or from a run with identical answers.

| If... | Then |
|---|---|
| you have no labels | keep the defaults, report means and intervals, and say the thresholds are unvalidated |
| you have 30 or more labelled cases with at least 8 to 10 fails | run `calibrate --sweep` and look for a plateau |
| the plateau is far from the default | change the threshold per run with `--threshold`, record why in `--notes`, and re-check on new labels |
| the metric cannot reach kappa above about 0.6 at any threshold | stop using its pass rate; use another metric or only the mean |

Part VI turns this into a full playbook for building a labelled calibration set.

## 3.8 Models and providers

### 3.8.1 Where the model settings live

You configure the provider through environment variables, which you can put in a `.env` file in the project root (see `.env.example`) or set in your shell. This guide names the variables only; never paste a key into a chat, a commit or a screenshot, and never put one into a shared note.

| Variable | Purpose | Default |
|---|---|---|
| `OPENAI_API_KEY` | credential for the provider | none (offline mode) |
| `OPENAI_BASE_URL` | base URL of any OpenAI-compatible endpoint | OpenAI's own |
| `RAGWB_GENERATOR_MODEL` | model that writes the answers | `gpt-4o` |
| `RAGWB_JUDGE_MODEL` | model that judges (DeepEval) | `gpt-4o` |
| `RAGWB_EMBEDDING_MODEL` | API embedding model for `embedding` and `hybrid` | `text-embedding-3-large` |
| `RAGWB_LOCAL_EMBEDDING_MODEL` | local model for `local`, `hybrid-local` and semantic metrics | `BAAI/bge-small-en-v1.5` |
| `RAGWB_PRICE_INPUT_PER_MTOK`, `RAGWB_PRICE_OUTPUT_PER_MTOK` | USD per million tokens, for generator cost reporting | unset: cost reported as unknown |

On the command line, `--model` overrides the generator and `--judge-model` the judge for one run. Setting a variable to an empty value is the same as not setting it.

### 3.8.2 Any OpenAI-compatible endpoint

To use another provider, put that provider's key in `OPENAI_API_KEY`, set `OPENAI_BASE_URL` to its OpenAI-compatible endpoint, and use model names from that provider's own console. Runs 1 to 17 of `docs/LIVE_VERIFICATION.md` used Groq's free tier this way. Other providers (for example xAI) are supported by configuration only; nothing has been sent to them. Treat any provider other than the one in the live record as untested until you have made a three-case run.

Model naming follows the provider, not this tool. The record used names such as `openai/gpt-oss-20b`, `openai/gpt-oss-120b` and `qwen/qwen3.8-27b` (note the vendor prefixes, which are part of the name). If a name is wrong, the run's cases fail with the provider's "model not found" error: check this on `--limit 1` before a long run.

### 3.8.3 Generator and judge: two different roles

| Role | Setting | What to consider |
|---|---|---|
| Generator | `--model` | This is the system under test. Pick the model you intend to ship. |
| Judge | `--judge-model` | This is the measuring instrument. Use a model at least as strong as the generator; a judge weaker than the generator cannot reliably spot its mistakes. Never judge a model with itself without noting it (a model can favour its own style). |

Run 7 used one model (`qwen/qwen3.8-27b`) for both roles because the free tier offered few models, and the result is labelled accordingly. If you have a choice, use different models, or at least different families. Run 11's labeller (an AI from another family than the judge) is the pattern.

The judge model is recorded in the run only when a judge metric is selected, so an offline run never claims a judge it did not use.

### 3.8.4 Embeddings availability varies

Embeddings are a separate endpoint from chat. The provider in the live record had chat models only, so the `embedding` and `hybrid` retrievers were never exercised live. Before choosing them:

1. Check the provider's documentation for an embeddings endpoint.
2. Set `RAGWB_EMBEDDING_MODEL` to its model name.
3. Run `--retriever embedding --limit 3` and look at the case detail.

If the provider has no embeddings, use `bm25`, `local` or `hybrid-local`. The New evaluation page offers `embedding` and `hybrid` as soon as any key is set, and it cannot know whether your provider actually supports them.

### 3.8.5 Free-tier limits you should plan for

The only live numbers this guide has are from one provider's free tier (documented in `docs/LIVE_VERIFICATION.md` and `docs/KNOWN_LIMITATIONS.md`). They are examples of the *kinds* of limit to expect, not promises about that provider today:

| Limit | Documented value | Effect |
|---|---|---|
| Daily token budget per model | about 200,000 tokens | Live run 5 (20 questions, four judge metrics) could not run: the judge model's daily budget was already used (199,638 of 200,000). |
| Per-minute output tokens, one model | 1,000 output tokens per minute | Live run 17's long judge outputs kept hitting it; 34 of 80 judge measurements failed after the retry budget. |
| Embeddings | none offered | API embedding and hybrid retrieval not exercised. |
| Judge cost reported | none | DeepEval reported no cost for that provider; the cost column is empty. |

Your provider will have its own numbers. The next section shows how to turn them into a plan.

## 3.9 Cost and quota planning

### 3.9.1 Count operations before you spend them

The workbench counts *operations*: one answer generation or one judge measurement. For a dataset of `N` cases and `J` judge metrics:

```text
operations = N x (1 + J)
```

With 20 honeybee questions and four judge metrics that is 20 x 5 = 100 operations (20 answers and 80 measurements), and that is what live run 17 did. Each *measurement* can itself be several API calls, so the number of HTTP requests is larger than the number of operations. A live run's size is therefore dominated by the judge metrics, not by the answers.

| Run shape | Operations (N = 20) | Comment |
|---|---:|---|
| offline, four lexical metrics | 0 API calls | free |
| live, lexical metrics only | 20 | cheapest live run |
| live + `correctness` | 40 | the single most informative judge metric, per cost |
| live + `correctness` + `answer_relevancy` | 60 | both short-output judges |
| live + all four judge metrics | 100 | the expensive configuration |
| agent pipeline, lexical metrics | at least 20, with several model turns each | tokens per case roughly 1,100 prompt and 150 to 280 completion (live run 12) |

### 3.9.2 Token budget arithmetic (illustrative)

Two documented facts bound a calculation. Generation is cheap: for the 10 honeybee questions of live run 4 the generator used 3,375 prompt and 1,105 completion tokens in total (about 340 in and 110 out per question), and for the 20 questions of live run 17, 5,688 prompt and 613 completion tokens in total. Judging is expensive: the project records that a 10-case run with four judge metrics used most of one model's 200,000 token daily budget. If "most" means about 150,000 tokens over 40 measurements, that is about 4,000 tokens per measurement; this is a back-of-envelope estimate from two documented facts, not a measurement, so take it as an order of magnitude and measure your own.

The planning rule that falls out:

* Generation tokens for a typical RAG question are in the hundreds.
* Judge tokens for one measurement are in the thousands, so a four-judge-metric run of 20 cases can consume on the order of 300,000 tokens, which exceeds a 200,000-token daily budget by itself.
* Therefore: budget in judge measurements, not in questions.

> **Why this works.** The daily cap is the plan's hard limit and it is a quota, not a rate. Pacing and retries cannot create quota. Run 5 and the early part of run 6 stalled on daily budgets, and the retry logic waits at most 60 seconds per attempt, which does not outlast a daily reset.

### 3.9.3 Pacing: `RAGWB_MAX_REQUESTS_PER_MINUTE`

Setting `RAGWB_MAX_REQUESTS_PER_MINUTE` spaces model operations evenly, so that the run stays under a provider's request-per-minute quota instead of hitting it and recovering. One process-wide limiter is shared by every worker thread, so several workers cannot exceed the budget together. Allowed values are above 0 and up to 6,000; unset means no pacing.

How to choose a value:

1. Read the provider's requests-per-minute and tokens-per-minute limits.
2. Because one judge measurement can make several requests, divide the request limit by that fan-out. If the limit is tokens per minute rather than requests, tune the value down until runs stop hitting 429 errors.
3. Start low. Live run 17 was paced at 10 operations per minute: 100 operations therefore need at least 10 minutes of pure pacing, and the run still took hours because the *token-per-minute* cap kept rejecting the long judge outputs. Pacing cannot fix a cap on output length.

You can see the pacing work without any provider: a paced offline run waits for its slots. At 120 operations per minute the interval is 0.5 s. I ran six offline cases with `RAGWB_MAX_REQUESTS_PER_MINUTE=120` and the whole command took about 4 s, where the cases themselves take milliseconds. A value of `abc` is refused with a clear message: `Invalid configuration: RAGWB_MAX_REQUESTS_PER_MINUTE: Input should be a valid number...`.

### 3.9.4 Retries and Retry-After

Transient provider errors (rate limit, timeout, connection error, server error) are retried; other errors (authentication, a bad model name, an invalid request) are not.

| Setting | Variable | Default | Range |
|---|---|---|---|
| Retries per generation (and per judge call) | `RAGWB_MAX_RETRIES` | 3 | 0 to 10 |
| Base delay | `RAGWB_RETRY_BASE_DELAY_S` | 1 s | 0 to 60 |
| Request timeout | `RAGWB_REQUEST_TIMEOUT_S` | 60 s | up to 600 |

The delay before retry attempt `n` is `base x 2^(n-1)` plus a random jitter of up to `base`, so with the defaults roughly 1 to 2 s, 2 to 3 s, then 4 to 5 s. When the provider sends a `Retry-After` hint, the delay is stretched to it, capped at 60 seconds. Three consequences:

* A short outage or an occasional 429 is absorbed invisibly. The case record shows how many attempts it needed.
* A rate-limit window longer than a minute is not waited out. Live run 17 used four retries of at most 60 s each; 34 of 80 judge measurements still failed.
* A daily quota is never waited out. Retrying more does not help; a different model, a paid tier or another day does.

Raise `RAGWB_MAX_RETRIES` (up to 10) when failures are bursts of rate limiting; lower it to 0 or 1 when you want a fast failure while debugging a configuration. When you raise it, raise the case time limit too (§3.11), because a case's time limit covers its retries.

### 3.9.5 Cost reporting

Cost is reported only for generation, and only when you configure prices (`RAGWB_PRICE_INPUT_PER_MTOK` and `RAGWB_PRICE_OUTPUT_PER_MTOK`, USD per million tokens). The prices are stored with the run, so old runs keep the prices they were costed with. Judge cost is whatever DeepEval reports; for the provider in the record it reported nothing, and judge token counts are not available. If you need a real judge bill, read it from your provider's usage page.

The New evaluation page warns before a live run ("This run calls the OpenAI API and may incur cost") with the number of generation calls it will make, and mentions judge calls when a judge metric is selected.

## 3.10 Workers

`--workers` sets how many cases are evaluated in parallel (the New evaluation page calls it "Parallel cases"). The default is 1 for the offline provider; for the `openai` provider the CLI uses `RAGWB_MAX_WORKERS` (default 4, allowed 1 to 32).

| Situation | Workers | Reason |
|---|---|---|
| offline | 1 | Offline cases take about a millisecond; the benchmark shows 4 workers at about 116 cases/s versus 100 cases/s for one at 1,000 cases: not worth it. |
| live, no tight quota | 2 to 4 | Cases wait on the network, so parallelism pays. |
| live, free tier, judge metrics | 1 | The quota is the bottleneck; parallel workers only trigger more 429s. |
| shared server, several users running at once | 1 to 2 per run, and set a request-per-minute limit | The limiter is shared per process, which protects the provider key. |
| debugging | 1 | Logs and failures are in dataset order. |

What parallelism does and does not change:

* **Scores are unchanged.** Offline results are identical for 1 and 4 workers; I ran the honeybee set with `--workers 4` and with one worker: both summaries were identical (token F1 0.346, ROUGE-L 0.317, context recall 0.885, groundedness 1.000), and each case keeps its dataset position.
* **Progress is reported approximately in dataset order**, and every case keeps its dataset position in the stored results.
* **Cancelling is not instant.** In-flight model calls finish (and with several workers up to 2 x workers queued cases) before the run stops.
* **Quota is shared.** Two workers do not double your quota; they double the pace at which you consume it.

## 3.11 Time limits

There are two time limits, and they protect against different failures.

| Limit | Variable | Default | Maximum | Protects against |
|---|---|---|---|---|
| One HTTP request | `RAGWB_REQUEST_TIMEOUT_S` | 60 s | 600 s | a single model call that never returns |
| One whole case | `RAGWB_CASE_TIMEOUT_S` | 600 s | 3,600 s | a case that takes too long overall (generation, retries, and every metric) |

The case limit covers *everything* a case does: the generation (with retries and back-off), then every metric (with each judge measurement's retries). When it passes, the case is recorded as an error with the message "Case exceeded the N s time limit and was abandoned (raise RAGWB_CASE_TIMEOUT_S if your provider is slow)", and the run moves on. Python cannot kill a thread, so the abandoned call may keep running in the background until its own HTTP timeout; its result is discarded.

How to size them:

* A generation call on a fast model takes under a second (the mean latency in live run 7 was about 535 ms per case), so 600 s is generous for plain RAG.
* A case with four judge metrics under rate limiting can spend minutes in retries: 4 retries of up to 60 s, times several measurements. If you raise `RAGWB_MAX_RETRIES`, raise `RAGWB_CASE_TIMEOUT_S` with it, or a case will be cut off while it is still retrying.
* Agent cases take several model turns each, so give them more headroom than plain RAG.
* Keep the request timeout well below the case timeout, or one stuck call uses the whole case budget.

Invalid values are rejected before anything runs:

```text
$ RAGWB_CASE_TIMEOUT_S=0 ragwb run --name x --quiet
error: Invalid configuration: RAGWB_CASE_TIMEOUT_S: Input should be greater than 0
```

## 3.12 Seeds and reproducibility

### 3.12.1 What the seed does

`--seed` (default 0) has exactly one effect on the offline path: it seeds the *failure injection* (`--inject-failures`), so that the same cases fail on every rerun. It does not change retrieval, answers or scores. I verified this by running the honeybee baseline with `--seed 7` and `--seed 0`; the two summaries were identical to the digit (token F1 0.346, ROUGE-L 0.317, context recall 0.885, groundedness 1.000). It is not passed to a live model (generation runs at temperature 0), and the bootstrap confidence intervals use their own fixed internal seed.

A different seed with `--inject-failures` selects a different set of failing cases. With `--inject-failures 0.3`, seed 1 failed 6 of 20 cases (q01, q02, q11, q16, q19, q20) and seed 2 also failed 6 (a different set, with a token F1 of 0.378 against 0.343 over the survivors). The rate is a per-case probability, not a quota, so the number failed varies.

### 3.12.2 How reproducible is a run?

| Path | Reproducible? | Notes |
|---|---|---|
| offline + BM25 + lexical metrics | yes, exactly | only latency varies |
| offline + local embeddings | yes for a given model file | same model, same inputs |
| live generation, temperature 0 | approximately | a model alias can change behind your back; the tool cannot pin a snapshot |
| judge metrics | approximately | a judge's opinion jitters (live run 8: SD 0.023 within a case) |
| agent pipeline | approximately, less than RAG | the agent's tool-calling strategy varies |

To make a result trustworthy and re-creatable, rely on what the workbench stores: the whole configuration, SHA-256 hashes of the dataset and document, the effective thresholds, the generator's model name, the package versions and the Python version. `ragwb rerun` warns when the dataset or document hash no longer matches (Part IV). For live runs, also write the date and the provider into `--notes`.

### 3.12.3 `--limit` and sampling

`--limit N` evaluates the first N cases, in dataset order. It is a smoke-testing tool, not a sampler: the first N cases may not be representative (datasets are often grouped by topic or difficulty). For an unbiased subset, make a smaller dataset file by sampling yourself and validate it (Part II). Always say in the notes that a run used `--limit`.

## 3.13 Recommended starting configurations

These eight starting points are my recommendations for the scenarios below, derived from the evidence in this Part. Commands are real flags; the first block was run on the bundled data. Adjust names and files to your own. Environment variables go in `.env` or the shell.

### 3.13.1 The table

| # | Scenario | Provider, pipeline | Retriever, k | Metrics | Other settings |
|---|---|---|---|---|---|
| 1 | Quick smoke test | `offline`, `rag` | `bm25`, 3 | defaults (token F1, ROUGE-L, context recall, groundedness) | `--limit 3` |
| 2 | Offline regression test (CI) | `offline`, `rag` | `bm25`, 3 | defaults, fixed thresholds | same dataset and document every time; `ragwb regress BASELINE CANDIDATE` |
| 3 | Retrieval tuning | `offline`, `rag` | compare `bm25`, `local`, `hybrid-local`; k in 1, 3, 5 | `context_recall`, plus `semantic_context_recall` | one change per run; `ragwb compare` |
| 4 | Answer-quality judging on a budget | `openai`, `rag` | `bm25`, 3 | `token_f1`, `context_recall`, then `correctness` only | `--workers 1`, `RAGWB_MAX_REQUESTS_PER_MINUTE` set, start with `--limit 5` |
| 5 | Paraphrase-heavy questions | `openai` or `offline`, `rag` | `local` or `hybrid-local`, 3 to 5 | `semantic_similarity`, `semantic_context_recall`, `correctness`, `context_recall` | calibrate semantic thresholds first |
| 6 | Teaching lab | `offline`, `rag` | `bm25`, vary k | defaults | `--inject-failures 0.2`, `--seed`, `--answer-sentences` experiments; bundled datasets |
| 7 | Shared team server | `openai`, `rag` | `bm25` or `hybrid-local`, 3 | lexical plus `correctness` | accounts, `RAGWB_RUN_VISIBILITY=own`, one worker per run, `RAGWB_MAX_REQUESTS_PER_MINUTE` set |
| 8 | Large document | `offline` first, then `openai` | `bm25`, 3 to 5 | `context_recall`, then `correctness` | keep inside input limits; larger `RAGWB_CASE_TIMEOUT_S` for live |

### 3.13.2 The scenarios, one by one

**1. Quick smoke test.** Goal: prove the install, the dataset and the document work. Nothing here is a quality statement.

```text
ragwb run --name smoke --limit 3
```

**2. Offline regression test.** Goal: catch a change that makes retrieval worse. Keep the dataset and document files unchanged (the hashes are stored), run the baseline once and tag it, then run the candidate and gate on it. The k = 1 against k = 3 pair below is a real example. Exit code 3 means a regression was found.

```text
ragwb run --name baseline-k1 -k 1 --quiet
ragwb run --name candidate-k3 -k 3 --quiet
ragwb regress <baseline-id> <candidate-id>
```

On the honeybee data this prints `token_f1 regression` (down 0.057, interval [-0.116, -0.008]) and `FAIL: regression detected.` with exit code 3. Reverse the arguments and the same difference prints `improved` and exit code 0. Which direction "better" points is your decision; the gate only says whether a drop is significant.

**3. Retrieval tuning.** Goal: choose retriever and k. Offline, one change at a time.

```text
ragwb run --name bm25-k3 --retriever bm25 -k 3 --metrics context_recall,token_f1 --quiet
ragwb run --name local-k3 --retriever local -k 3 --metrics context_recall,token_f1,semantic_context_recall --quiet
ragwb compare <id-bm25> <id-local>
```

Use at least 20 questions from your own domain, because the bundled sets cannot choose for your documents (§3.4.3).

**4. Answer-quality judging on a budget.** Goal: evidence about answer quality without exhausting a free quota. Use the cheapest informative judge, one worker, pacing, and a tiny first run.

```text
ragwb run --name live-probe --provider openai --metrics token_f1,context_recall,correctness --limit 5 --workers 1
```

Then run the full dataset only after reading the probe's case detail. Skip `faithfulness` and `context_relevancy` unless you need them: they are the long-output metrics that failed most often in live run 17. Part VI covers the full budget playbook.

**5. Paraphrase-heavy questions.** Goal: find out whether wording sensitivity, not missing content, is what costs you. Test `local` against `bm25` on a paraphrased copy of your questions (the bundled `honeybees_paraphrased.csv` shows the pattern), and use meaning-aware metrics, because token F1 under-credits correct paraphrases.

```text
ragwb run --name para-local --dataset examples/datasets/honeybees_paraphrased.csv --retriever local --metrics context_recall,semantic_context_recall,semantic_similarity
```

This needs `fastembed` and a one-time model download; I could not run it for this guide, so check it on your machine with `--limit 2` first. If the model cannot be loaded, the run stops immediately with a single message (Part VIII §8.13) rather than failing case by case. Calibrate the semantic thresholds (§3.7.6) before you trust a pass rate.

**6. Teaching lab.** Goal: let students see cause and effect in seconds, at no cost. Use the bundled data. Give each student a different single change: `-k`, `--answer-sentences`, `--skip-headings`, `--min-evidence`, `--inject-failures`. Have them predict the direction, run, and compare. The runs finish in about a second, so a whole class can iterate repeatedly. Part VI has a ready lab sheet.

**7. Shared team server.** Goal: several people running evaluations without trampling each other or the provider key. Create accounts, set `RAGWB_RUN_VISIBILITY=own`, serve over TLS, put a request-per-minute limit in place and keep each run to one or two workers (Part VII). A single key's quota is shared by everyone who uses it.

**8. Large document.** Goal: evaluate retrieval on a long document without surprises. Input limits apply (a 25 MB document and 5 MB dataset by default, 5,000 cases): beyond them the tool refuses the input instead of struggling. The offline path is fast (the benchmark indexes 5,000 chunks in about 0.3 s and answers a query in about 3 ms), so do the retrieval tuning offline. With API embeddings every chunk is embedded for each run, so cost grows with document size (§3.4.6); prefer `bm25` or `local`. Live, raise `RAGWB_CASE_TIMEOUT_S` if you also raise retries, and sample the dataset rather than running every question the first time.

> **Pitfall.** A bigger document means more distractor chunks, so the same `k` gets harder, and a lexical context recall that was comfortable on a 11-chunk PDF will fall. Re-tune `k` for each document; do not carry the honeybee numbers into your data.

## 3.14 Before you start a run

Work through this list at the keyboard. Each item is something that has bitten a real run.

1. **State the question.** Write one sentence: "I am testing whether ___ improves ___." If you cannot, you are not ready to run.
2. **Change one thing.** Compare to a run that differs in exactly one row of the table in §3.1.1.
3. **Validate the inputs.** `ragwb validate yourdata.jsonl` reports the case count and how many have reference answers. Open the document's chunk count on the New evaluation page.
4. **Pick the provider deliberately.** Offline for retrieval and plumbing, live for answer quality. Do not report baseline numbers as model quality.
5. **Choose metrics that match the question** (§3.7.3): a retrieval metric for retrieval, an answer metric for answers, one lexical and one meaning-aware metric together.
6. **Know your thresholds.** Defaults are conventions. If you will quote a pass rate, record the thresholds and consider calibrating.
7. **Check the key and models** (live only): the key variable is set (the `ragwb doctor` line "OpenAI key" says so without printing it), the base URL is your provider's, the model names are your provider's.
8. **Estimate operations** (§3.9.1): `N x (1 + J)`. Compare it with the provider's daily and per-minute budgets. If it does not fit, shrink `N` or drop a judge metric.
9. **Set pacing** when live: `RAGWB_MAX_REQUESTS_PER_MINUTE` below the quota, workers at 1 on a free tier.
10. **Set time limits** to match your retry budget (§3.11).
11. **Start small.** `--limit 3` or `--limit 5`, then read the case details before scaling up.
12. **Name and annotate the run.** `--name` and `--notes` with the changed setting, the date and the provider.
13. **Know the cost of failure.** Failed cases are recorded and excluded from means, never counted as zero; a run with many errors is a configuration or quota problem, not a score. Read "scored" and "err" before the mean.
14. **Decide what you will do with the result** before you see it, so the number cannot pick the story.

> **Why this works.** Nearly every wasted evaluation falls into one of three patterns: more than one thing changed, the sample was too small to see the difference, or the budget ran out halfway. The list above targets those three.
