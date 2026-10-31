# Part VI — Evaluation methodology

This Part covers what the workbench measures, how each number is computed and how far each number
can be trusted. Every formula here was read from the source, and every result came from running the
code. File references have the form `path:line` relative to `src/rag_workbench/` unless another
root is given.

The chapter uses two kinds of example:

* **Illustrative input.** A question, answer, reference and context written for this chapter on the
  honeybee theme of the bundled examples. Each one is scored with `ragwb score`, which stores
  nothing (`cli.py:476-487`). They were run with `RAGWB_DATA_DIR` set to a temporary directory, so the
  project's data directory was not touched.
* **Stored results.** The five example runs in the project's run store (`data/runs.db`), read with
  `ragwb list`, `ragwb show` and `ragwb compare`. All five are genuine offline evaluations of the
  bundled honeybee data, defined in `demo.py:24-39`. They are created on first launch by
  `python start.py`, or by `scripts/seed_demo_runs.py`, and rerunning them reproduces the same scores.

---

## 61. The evaluation model

### 61.1 What is being evaluated

The object under test is a *pipeline*: a function from a question to a `Generation`. A `Generation`
holds the answer, the context chunks the answer was generated from, and bookkeeping such as latency
and token counts (`models.py:50-67`). There are two pipeline shapes:

* **Retrieve → generate** (`pipeline.py:42-58`). The pipeline retrieves the top-k chunks for the
  question and generates from exactly those chunks, so the chunks stored for evaluation are, by
  construction, the chunks the generator saw.
* **Tool-calling agent** (`pipeline.py:61-124`, OpenAI only). The model decides when to call the
  retrieval tool and with what query. Every chunk the tool returns is captured (`pipeline.py:84-90`)
  and becomes the evaluation context. The agent's own description of its context is stored
  separately as `model_context_claim` and is never scored (`pipeline.py:124`), because a model's
  description of its evidence is not evidence.

The offline pipeline pairs a BM25 retriever (`retrieval.py:40-91`, with k1 = 1.5 and b = 0.75 at
`retrieval.py:26-27`) with an **extractive generator** (`providers.py:37-88`). The extractive
generator is not a language model. It splits the retrieved passages into sentences and ranks them by
the summed IDF of the content terms each shares with the question. It returns the top
`max_sentences` (default 2) in their original order. If no sentence shares a content term with the
question, it returns the fixed abstention sentence (`providers.py:79-81`, sentence defined at
`prompts.py:8`). The generator exists so the whole system can run without a network, and so there is
a lower-bound baseline to compare other pipelines against.

### 61.2 The unit of measurement

The unit of measurement is the *case*: one dataset row (question, optional reference answer,
metadata) run through the pipeline once and scored by every selected metric (`runner.py:217-232`).
For each case and metric, the runner builds a `MetricInput` with four fields: question, answer,
expected answer, and the list of context texts (`metrics/base.py:28-34`, built at
`runner.py:223-224`). It then calls the metric's `evaluate` method (`runner.py:225`).

A run is a set of cases evaluated under one fixed configuration. A run summary aggregates each
metric over the run's cases (§70). A comparison pairs the cases of two runs by question text and
analyses the per-case differences (§72).

### 61.3 Three metric families

| Family | Metrics | How computed | Network |
|---|---|---|---|
| Lexical | `exact_match`, `token_f1`, `rouge_l`, `context_recall`, `groundedness` | Deterministic string and token-set arithmetic (`metrics/lexical.py`) | None |
| Semantic (optional, release 1.2) | `semantic_similarity`, `semantic_context_recall` | Cosine similarity of local sentence embeddings (`metrics/semantic.py`); needs the `fastembed` package | None after the one-time model download |
| LLM judge | `answer_relevancy`, `faithfulness`, `context_relevancy`, `correctness` | A DeepEval metric object prompts an OpenAI judge model (`metrics/judge.py`) | OpenAI API |

`ragwb metrics` prints the catalogue straight from the registry:

```text
exact_match        lexical    threshold 1.0  needs: reference
token_f1           lexical    threshold 0.5  needs: reference
rouge_l            lexical    threshold 0.5  needs: reference
context_recall     lexical    threshold 0.7  needs: reference, context
groundedness       lexical    threshold 0.7  needs: context
semantic_similarity semantic   threshold 0.7  needs: reference, fastembed
semantic_context_recall semantic   threshold 0.7  needs: reference, context, fastembed
answer_relevancy   llm_judge  threshold 0.7  needs: OpenAI
faithfulness       llm_judge  threshold 0.7  needs: context, OpenAI
context_relevancy  llm_judge  threshold 0.7  needs: context, OpenAI
correctness        llm_judge  threshold 0.7  needs: reference, OpenAI
```

The description line printed under each entry is omitted here. The default offline metric set is
`token_f1, rouge_l, context_recall, groundedness` (`metrics/__init__.py:14`), so `exact_match` must be
asked for explicitly, and the two semantic metrics are never defaults. With the OpenAI provider, the CLI adds all four judge metrics by default
(`cli.py:41-42`).

The semantic family is described in Part XIV §155: it scores meaning rather than shared words, so a correct paraphrase
can score high where token F1 scores it low. It was written and unit-tested with a deterministic stand-in embedder, and in release 1.3 it was run once with a real local model (`BAAI/bge-small-en-v1.5`, Part XV §162);
the scores that run produced are in Part XV and **no semantic score appears elsewhere in this Part**; they sit between 0.63 and 0.76 for extractive answers and the model's cosines have a high floor, so the 0.7 thresholds are
unvalidated. Release 1.4 swept `semantic_similarity` against labels written by an AI rater (30 cases of one document): agreement 0.867 at 0.70 and 0.967 for thresholds 0.55-0.65. The default was not changed and no human labels exist (Part XVI §174).

No judge metric was run for this Part of the book (written with no API key). Release 1.3 later ran the judge metrics against a free-tier OpenAI-compatible service on small samples (Part XV §160), and those numbers appear only in Part XV. The
judge metrics are described here from the code and the installed DeepEval library (§69),
and no judge scores appear in this Part.

### 61.4 Reference-based and reference-free metrics

A *reference-based* metric needs a gold answer (`expected_answer`). These are `exact_match`,
`token_f1`, `rouge_l`, `context_recall`, `correctness` and the two semantic metrics. A *reference-free* metric judges the answer
or the context against the question or the context only. These are `groundedness`,
`answer_relevancy`, `faithfulness` and `context_relevancy`.

The distinction limits what a number can tell you. Reference-based metrics measure agreement with an
answer someone chose, so they penalise a correct answer that is phrased differently. Reference-free
metrics work on unlabelled questions, but they cannot catch an answer that is fluent, grounded in the
context and relevant to the question, yet wrong because the context itself was wrong or incomplete.

Three of the metrics measure *retrieval* rather than the answer: `context_recall` (lexical,
reference-based), `semantic_context_recall` (semantic, reference-based) and `context_relevancy` (judge, reference-free). The other eight measure the
*answer*.

---

## 62. Ground-truth requirements

### 62.1 What the dataset must contain

A dataset row needs a `question`; `expected_answer`, `id` and `metadata` are optional
(`datasets.py:1-13`). The validator does three things:

* It rejects a missing or empty question, a non-string reference, over-long fields, duplicate ids and
  invalid JSON lines, and reports each with its line number (`datasets.py:171-204`,
  `datasets.py:138-152`).
* It turns an empty or whitespace-only `expected_answer` into "no reference" (`datasets.py:180-182`).
* It warns, without failing, on duplicate questions (`datasets.py:100-102`) and on cases without a
  reference ("reference-based metrics will be skipped for them", `datasets.py:109-112`).

The bundled examples are `examples/datasets/honeybees.jsonl` (20 questions, ids q01–q20, all with
references), `honeybees_unanswerable.jsonl` (u1–u4 unanswerable, a1–a2 answerable, marked in
`metadata.type`) and `honeybees_paraphrased.csv` (p1–p5, with a `topic` column).

### 62.2 What a good reference looks like for these metrics

The lexical reference-based metrics compare tokens, so the *wording* of the reference becomes part of
the measurement:

* **Exact match.** The reference must be the exact short answer a system is expected to produce, in
  SQuAD style: an entity, a number or a short phrase. With full-sentence references, exact match is
  close to useless. In the stored `unanswerable-k3` run it is 0 on all six cases, including the two
  answerable ones (§74.5).
* **Token F1 and ROUGE-L.** A long reference lowers recall for short correct answers, and a short
  reference lowers precision for verbose answers. The honeybee references are full sentences, for
  example "Foragers collect nectar, pollen, water and plant resin."
* **Context recall.** Every content word in the reference counts as a fact the context should
  contain. Words that survive the stop list without carrying the answer count too: "normally",
  "roughly", "exist", "mainly" and "perform" all appear as "missing" terms in the stored runs (§74).
* **Unanswerable questions.** The reference should be the abstention sentence. `context_recall`
  detects an abstention reference and skips the case (`metrics/lexical.py:69-71`). `exact_match` then
  rewards a pipeline only if it produces exactly that sentence after normalisation.

Only one reference per case is supported. The original SQuAD evaluation takes the maximum score over
several references; this implementation does not.

---

## 63. Text processing shared by the metrics

All lexical metrics, BM25 retrieval and the extractive generator use the functions in `text.py`.
There are two different normalisations, and which one a metric uses changes how it behaves.

### 63.1 SQuAD normalisation (used by exact match, token F1, ROUGE-L)

`squad_normalize` (`text.py:81-87`) does five things in order:

1. Applies Unicode NFKC normalisation and lower-cases the text.
2. **Deletes** every character in Python's `string.punctuation` (ASCII punctuation) together with the
   typographic and modifier apostrophes `‘`, `’` and `ʼ` (`text.py:34`), so every apostrophe style is
   treated like the ASCII `'`.
3. **Replaces with a space** every remaining character whose Unicode category is punctuation (`P*`:
   curly double quotes, dashes, ellipses and so on) (`text.py:84-85`). Steps 2–3 go further than the
   SQuAD v1.1 script, which removes only ASCII punctuation.
4. Replaces the whole words `a`, `an` and `the` with a space.
5. Collapses runs of whitespace.

Tokens are then produced by splitting on spaces. Stop words are **kept**, as in the SQuAD v1.1
script. Running the function shows the consequences:

* Apostrophes are deleted whatever their style, so a possessive merges with its noun.
  `"The queen's diet - nectar"` and `"The queen’s diet — “nectar”…"` both become
  `queens diet nectar`.
* An answer and a reference that differ only in punctuation style therefore normalise to the same
  string (worked example E7, §68).
* This applies to SQuAD normalisation. Since release 1.1 the content-token path (§63.2) treats apostrophes
  between letters the same way: it keeps the word whole and deletes the apostrophe (§63.3).

### 63.2 Content tokens (used by context recall, groundedness, BM25)

`content_tokens` (`text.py:76-78`) runs `tokenize`, removes stop words, then applies `stem`:

* `tokenize` (`text.py:49-55`) applies NFKC, lower-cases and extracts words made of `\w+` runs that may contain
  apostrophes between letters (`text.py:30`); the apostrophes are then deleted (`text.py:31`), so "queen's" becomes
  `queens`. It still splits on hyphens: "thirty-five" gives `thirty` and `five`.
* The stop list (`text.py:15-27`) is a compact English list of 132 words.
* `stem` (`text.py:58-73`) is a deliberately minimal suffix stripper. Tokens of three characters or
  fewer, and digit strings, are left alone. `-ies` becomes `-y`; `-sses`, `-shes`, `-ches`, `-xes` and
  `-zes` lose `-es`; and a final `-s` is removed unless the word ends in `ss`, `us` or `is`. It does
  not handle `-ing`, `-ed`, `-er`, adjective forms or irregular forms.

A probe sentence gives:

```text
content_tokens("The queen's eggs don't all hatch; eating, dancing, shivering, colonies, boxes,
                grass, status, feet, workers' abdomens")
['queen', 'egg', 'dont', 'hatch', 'eating', 'dancing', 'shivering', 'colony', 'box',
 'grass', 'status', 'feet', 'worker', 'abdomen']
```

So `dancing` ≠ `dance`, `shivering` ≠ `shiver`, `feet` ≠ `foot`, and in the stored data `parasitic`
≠ `parasite` and `threats` ≠ `threatens` (§74.3). These mismatches recur in the stored runs.

### 63.3 Apostrophes (changed in release 1.1)

*Release 1.0 behaviour (now fixed).* The tokenizer split on every apostrophe, so a possessive ("queen's") or a
contraction ("don't") left a stray content term: `queen` plus `s`, or `don` plus `t`. A reference with a possessive
therefore got a spurious "fact" that context recall looked for. The probe above printed `'queen', 's'` and
`'don', 't'` under 1.0.

*Release 1.1 behaviour.* `queen's`, `queen’s` (typographic) and `queens` now tokenise identically, and `don't` becomes
`dont` (`text.py:29-31`, `:49-55`; the changelog lists it under *Changed*). The change is a deliberate trade: a rare
verbatim-apostrophe word is no longer split, at the price that `don't` and `dont` are one token. The probe above shows
the 1.1 output.

**Count in the bundled examples.** A scan of all questions and references in the three example
datasets, and of every chunk of the example document, found no word with an internal apostrophe.
The one apostrophe in the data is the trailing plural possessive in "workers'" (reference q13, and
chunk `p1-b8`). It was reduced to `workers` with no stray token under 1.0 and still is. As a result, none of the
stored scores in §74 is affected by the 1.1 change; the changelog states that the five example runs score
identically under 1.0.0 and 1.1.0, and (re-checked: 86 cases, 0 differences) under 1.2.0. Release 1.3 did not change how any metric is computed; it added pacing and retry hints around the model calls (Part XV). Release 1.4 changed how BM25 finds its scores (an inverted index) but not the scores: the five example runs, 86 cases, score identically under 1.0.0 and 1.4.0, with 0 differences, and a test compares every score with the textbook definition by exact float equality (Part XVI §175).

### 63.4 Abstention detection

`is_abstention` (`text.py:98-100`) returns true if any of four case-insensitive patterns occurs
anywhere in the text (`text.py:36-41`):

* `does not (provide|contain) enough information`
* `(not|n't) (enough|sufficient) information`
* `cannot (be )?answer(ed)?`
* `no (relevant )?information`

It searches rather than matching the whole text, so it also fires on phrases embedded in longer
answers. Probes run for this chapter:

| Text | `is_abstention` |
|---|---|
| "There is no information about winter survival." | True |
| "I don't know." | False |
| "The yield cannot be answered precisely, but it is about 25 kg." | True |

The patterns are tuned to the pipelines' own abstention sentence (`prompts.py:8`), which both OpenAI
prompts tell the model to use verbatim (`prompts.py:10-26`). Other refusals are not recognised, and a
substantive answer that happens to contain one of the phrases is misclassified as an abstention.

---

## 64. The metric contract

Every metric returns a `MetricResult` with one of three statuses (`metrics/base.py:1-9`,
`models.py:70-86`):

* **ok** — a score in [0, 1], with `passed = score >= threshold`.
* **skipped** — a required input was missing, or the metric decided it does not apply.
* **error** — the computation raised, or produced a score outside [0, 1]. The error text is kept,
  truncated to 500 characters.

The wrapper `Metric.evaluate` (`metrics/base.py:74-96`) applies these rules in order:

1. **Threshold.** Use the run's per-metric threshold, otherwise the metric's default
   (`metrics/base.py:75`).
2. **Missing reference.** If the metric requires a reference and `expected_answer` is empty, the
   result is skipped with reason "no expected_answer for this case" (`metrics/base.py:76-78`).
3. **Missing context.** If the metric requires context and the context list is empty, the result is
   skipped with reason "no retrieved context for this case" (`metrics/base.py:79-81`).
4. **Run the scorer.** A `MetricSkipped` exception gives skipped, with its message
   (`metrics/base.py:84-85`). Any other exception gives error (`metrics/base.py:86-89`).
5. **Range check** (`metrics/base.py:92-95`). A score below −10⁻⁹ or above 1 + 10⁻⁹
   (`SCORE_TOLERANCE`, `metrics/base.py:23`) is treated as a scorer bug. It is recorded as status
   **error** with reason "score … outside [0, 1]". A NaN fails the same comparison and is also an
   error.
6. **Clamp.** The remaining score is clamped into [0, 1], which absorbs only floating-point noise, and
   `passed` is set (`metrics/base.py:95-97`).

Step 4 isolates failures: one failing metric does not abort the case or the run. Steps 5 and 6
separate two cases that a plain clamp would merge. GEval returning 1.0000000000000002, the example in
the comment at `metrics/base.py:23`, is recorded as 1.0. A genuinely out-of-range value such as 1.3
becomes a visible error instead of being reported as a perfect score. Both behaviours were checked
directly for this chapter: 1.3 and NaN gave status `error`, 1.0000000000000002 gave 1.0 and −10⁻¹²
gave 0.0.

Thresholds affect only `passed` and the pass rate. They never change a score or a mean.

---

## 65. Lexical answer metrics

### 65.1 Exact match (`exact_match`)

**What it measures:** whether the answer and the reference are the same string after SQuAD
normalisation.

**Formula** (`metrics/lexical.py:17-20`):

  EM = 1 if `squad_normalize(answer) == squad_normalize(reference)` else 0.

**Inputs:** answer and reference. **Skipped** when there is no reference. **Default threshold:** 1.0,
which simply makes "pass" mean "matched".

**How to read it:** EM is the share of cases answered with exactly the reference string. It is
meaningful for short factoid references, and for checking whether a pipeline emits the exact
abstention sentence on unanswerable questions.

**Where it misleads:** any difference beyond case, punctuation, articles and whitespace counts as a
full miss. "A single queen" against "A colony normally has a single queen" scores 0, and so does a
correct answer followed by an explanatory sentence. With sentence-length references EM is nearly
always 0 and tells you almost nothing.

### 65.2 Token F1 (`token_f1`)

**What it measures:** bag-of-words overlap between the answer and the reference.

**Formula** (`metrics/lexical.py:23-36`). Let P be the multiset of SQuAD-normalised answer tokens and
G the multiset of reference tokens. Let overlap be |P ∩ G| taken as a multiset (Python
`Counter(pred) & Counter(gold)`). Then:

  precision = overlap / |P|, recall = overlap / |G|, F1 = 2 · precision · recall / (precision + recall).

If either side is empty after normalisation, or the overlap is 0, the score is 0.0 with status
**ok** (not skipped). The reason string reports precision, recall and the number of shared tokens.

**Inputs:** answer and reference. **Skipped** without a reference. **Default threshold:** 0.5.

**How to read it:** precision is the share of the answer's tokens that also appear in the reference;
recall is the share of the reference's tokens the answer covers. Stop words count: articles are
removed, but "of", "and" and "in" all add to the overlap.

**Where it misleads:**

* **Word order is ignored.** An answer that inverts the reference's meaning by swapping two words
  scores 1.0 (worked example E3, §68).
* **Correct paraphrases score low** (E2).
* **Verbose answers lose precision even when fully correct.** In the stored `offline-bm25-k3` run,
  "What jobs do young worker bees do?" scores 0.311 with "precision 0.18, recall 1.00": the answer
  contains every reference token, plus two sentences about other jobs.
* **Shared function words** give unrelated answers spurious partial credit.

### 65.3 ROUGE-L (`rouge_l`)

**What it measures:** in-order overlap, as the longest common subsequence (LCS) of SQuAD-normalised
tokens.

**Formula** (`metrics/lexical.py:39-60`). The LCS length comes from a standard dynamic programme with
a single rolling row (`metrics/lexical.py:39-49`). With L = LCS(P, G):

  precision = L / |P|, recall = L / |G|, ROUGE-L = 2 · precision · recall / (precision + recall).

This is the equally weighted F1 form (β = 1); the original ROUGE-L definition allows a recall
weighting β, which is not used here. An LCS of zero gives 0.0 with status ok.

**Inputs, skip rule and threshold:** the same as token F1; the default threshold is 0.5.

**How to read it:** like token F1, but it also rewards keeping the reference's word order. In this
implementation ROUGE-L never exceeds token F1, because an LCS is a multiset intersection with an
added order constraint. In the stored runs the two metrics are equal on many cases, and ROUGE-L is
lower where the answer reorders the reference's words (for q01 in `offline-bm25-k3`, 0.083 against
0.167).

**Where it misleads:** it has the same blindness to paraphrase as token F1. It catches some
reorderings but not what the reordering means: E3 still scores 0.818.

---

## 66. Lexical retrieval and grounding metrics

### 66.1 Context recall (`context_recall`)

**What it measures:** a proxy for retrieval quality. It is the share of the reference answer's
distinct content terms that appear anywhere in the retrieved context.

**Formula** (`metrics/lexical.py:63-81`). Let R = set(content_tokens(reference)) and C =
set(content_tokens(all context texts joined with spaces)). Then:

  context recall = |R ∩ C| / |R|.

The reason lists up to eight missing terms in alphabetical order.

**Inputs:** reference and context. **Skipped** in four cases:

* the reference is missing;
* there is no context;
* the reference is an abstention, i.e. an unanswerable case whose words say nothing about retrieval
  (`metrics/lexical.py:69-71`);
* the reference has no content terms (`metrics/lexical.py:73-74`).

**Default threshold:** 0.7.

**How to read it:** if the reference's key terms are absent from the context, the generator could
not have produced the reference from that context. A low value points at retrieval. A high value
says the vocabulary is present, not that the relevant fact is.

**Where it misleads:**

* **Any chunk can supply a term.** The measure is a set taken over the union of all chunks, so a
  reference term found in an irrelevant chunk counts as recalled. In the stored runs, the word "male"
  for q04 was recalled at k = 3 from a chunk that BM25 scored 0 and retrieved only to fill a slot. The
  word "roughly" for q06 was recalled at k = 5 from the swarming paragraph ("roughly half of the
  workers") (§74.1).
* **A high score can sit on a wrong answer.** For a2 ("Which parasite threatens honeybee colonies?")
  context recall is 1.000, but the answer is the document title and its first sentence (§74.3).
* **Synonyms and inflections fail.** "secreted" is missing from a context that says "produced";
  "dance" is missing from a context that says "dancing".
* **Words that carry no fact still count** ("normally", "roughly", "mainly", "exist").
* **The reference's vocabulary caps the score.** A context that answers the question in different
  words scores low.
* **It is not the same as judge-based "contextual recall".** RAG evaluation libraries use that name
  for a judge metric; this one is a term-overlap statistic.

### 66.2 Groundedness (`groundedness`)

**What it measures:** a lexical proxy for faithfulness. It is the share of the answer's distinct
content terms that appear in the retrieved context.

**Formula** (`metrics/lexical.py:84-100`). With A = set(content_tokens(answer)) and C as above:

  groundedness = |A ∩ C| / |A|.

The reason lists up to eight unsupported terms.

**Inputs:** answer and context; no reference is needed. **Skipped** when there is no context, when
the answer is an abstention ("nothing to ground", `metrics/lexical.py:90-91`), or when the answer has
no content terms. **Default threshold:** 0.7.

**How to read it:** a term in the answer that never appears in the context suggests content not
drawn from the context. That content may be hallucinated, may be world knowledge, or may be a
paraphrase.

**Where it misleads:**

* **It is 1.0 by construction for the extractive baseline**, which copies context sentences verbatim.
  Every stored run has a groundedness mean of 1.000 with CI 1.000–1.000, so for this generator the
  metric carries no information. The Settings page says the same.
* **Bag-of-words support is not logical support.** An answer that recombines context words into a
  false statement ("Drones collect pollen and sting intruders") is fully "grounded" if every word
  appears somewhere in the context.
* **Correct paraphrases are penalised** when they use words absent from the context (E1: "gather"
  for "collect").
* **Selective answering is rewarded.** Abstentions are skipped, so a pipeline that abstains on every
  hard question is scored only on the questions it chose to answer.

---

## 67. Default thresholds and their status

| Metric | Default | Where defined |
|---|---|---|
| exact_match | 1.0 | `metrics/lexical.py:106-107` |
| token_f1 | 0.5 | `metrics/lexical.py:108-109` |
| rouge_l | 0.5 | `metrics/lexical.py:111-113` |
| context_recall | 0.7 | `metrics/lexical.py:114-116` |
| groundedness | 0.7 | `metrics/lexical.py:117-119` |
| all four judge metrics | 0.7 | `metrics/judge.py:27-45` |

These values are **conventions** chosen for the project. Nothing in the code derives them from data,
and they have not been calibrated against human judgements of acceptable answers (release 1.4 added `ragwb calibrate --sweep` to tabulate agreement at every threshold, and applied it to labels written by an AI rater, not a person: Part XVI §174). They can be
overridden per run, with `--threshold metric=value` on the CLI (`cli.py:43-49`) or in the "Pass
thresholds" expander in the UI. The runner rejects thresholds outside [0, 1] or for unknown metrics
(`runner.py:85-87`). It records the thresholds actually used in the run configuration
(`runner.py:97`, stored at `runner.py:113-114`).

The practical consequence is that a pass rate means something only together with its threshold, and
two runs' pass rates are comparable only if the runs used the same thresholds. The mean does not
depend on any threshold and is the primary statistic. In the stored runs, token F1 passes only 1 of
20 cases at k = 3 (5%) under the 0.5 convention, even though the mean is 0.346.

---

## 68. Worked examples (illustrative input)

All examples were run from the project root with a temporary data directory, in this form:

```powershell
$env:RAGWB_DATA_DIR = "<temporary directory>"
.venv\Scripts\python.exe -m rag_workbench score --question ... --answer ... --expected ... `
    --context ... --metrics exact_match,token_f1,rouge_l,context_recall,groundedness
```

The context in E1 is the worker-bee paragraph of the example document (chunk `p1-b4`):

> Worker bees change jobs as they age. Young workers clean cells and feed larvae, slightly older bees
> build wax comb and process nectar, and the oldest workers become foragers that collect nectar,
> pollen, water and plant resin outside the hive. In summer a worker usually lives for about five to
> six weeks, but workers raised in autumn can survive through the winter.

### E1 — a short, nearly correct answer (illustrative input)

* Question: "What do forager bees collect?"
* Answer: "Foragers gather nectar, pollen and water."
* Reference: "Foragers collect nectar, pollen, water and plant resin."
* Context: the worker-bee paragraph above.

**By hand.**

*SQuAD tokens.* The answer gives `foragers gather nectar pollen and water` (6 tokens). The reference
gives `foragers collect nectar pollen water and plant resin` (8 tokens).

* **EM:** the strings differ, so 0.
* **Token F1:** the shared multiset is {foragers, nectar, pollen, and, water}, 5 tokens. Precision is
  5/6 = 0.833, recall 5/8 = 0.625, and F1 = 2·(5/6)·(5/8)/((5/6)+(5/8)) = 5/7 = 0.714.
* **ROUGE-L:** the longest in-order common subsequence has 4 tokens (for example foragers, nectar,
  pollen, water). Precision is 4/6, recall 4/8, and ROUGE-L = 4/7 = 0.571.

*Content tokens.* In the reference, "and" is a stop word and "foragers" becomes forager, giving
R = {forager, collect, nectar, pollen, water, plant, resin} (7 terms), all present in the context. In
the answer, A = {forager, gather, nectar, pollen, water} (5 terms); "gather" is not in the context.

* **Context recall** = 7/7 = 1.000.
* **Groundedness** = 4/5 = 0.800, with "gather" unsupported.

**Real output:**

```text
Exact match                   0.000  fail    normalised strings differ
Token F1                      0.714  pass    precision 0.83, recall 0.62 (5 shared tokens)
ROUGE-L                       0.571  pass    LCS 4 tokens; P 0.67, R 0.50
Context recall (lexical)      1.000  pass    7/7 reference terms found in context
Groundedness (lexical)        0.800  pass    4/5 answer terms found in context; unsupported: gather
```

The answer is accurate but incomplete (it omits plant resin), and it uses a synonym. The synonym
alone costs 0.2 groundedness, which shows that the metric measures vocabulary, not support.

### E2 — a correct paraphrase (illustrative input)

* Question: "How do honeybees cool the hive?"
* Answer: "Droplets on the honeycomb evaporate while bees beat air over them."
* Reference: "They spread water on the comb and fan their wings so that evaporation cools it."

**By hand.** After removing "the", the answer has 10 tokens and the reference 14. Only "on" is
shared, so F1 = 2·(1/10)·(1/14)/((1/10)+(1/14)) = 2/24 = 0.083, and an LCS of 1 gives the same
ROUGE-L.

**Real output:**

```text
Exact match                   0.000  fail    normalised strings differ
Token F1                      0.083  fail    precision 0.10, recall 0.07 (1 shared tokens)
ROUGE-L                       0.083  fail    LCS 1 tokens; P 0.10, R 0.07
```

An answer that says essentially the same thing fails every lexical metric, and the one shared token
is a preposition.

### E3 — a fluent wrong answer that reuses the reference's words (illustrative input)

* Question: "What do eggs develop into?"
* Answer: "**Unfertilised** eggs develop into workers and **fertilised** eggs develop into drones."
* Reference: "Fertilised eggs develop into workers and unfertilised eggs develop into drones."

**By hand.** The answer is a permutation of the reference's 11 tokens, so the multisets are
identical and token F1 = 1.0. For ROUGE-L, dropping the first word of each string leaves
`eggs develop into workers and` (5) followed by `eggs develop into drones` (4) in common, so
LCS = 9 and P = R = 9/11 = 0.818.

**Real output:**

```text
Exact match                   0.000  fail    normalised strings differ
Token F1                      1.000  pass    precision 1.00, recall 1.00 (11 shared tokens)
ROUGE-L                       0.818  pass    LCS 9 tokens; P 0.82, R 0.82
```

The answer states the biological opposite of the reference and gets a perfect token F1.

### E4 — a correct abstention (illustrative input)

* Question: "How much honey does a colony produce in a year?" (the document does not say; this is
  unanswerable question u1)
* Answer and reference: "The PDF does not provide enough information to answer the question."
* Context: the honey paragraph (chunk `p1-b7`).

**By hand.** The strings are identical, so EM = 1. After "the" is removed twice, each side has 9
tokens, all shared, so F1 and ROUGE-L are 1.0. The reference is an abstention, so context recall is
skipped; the answer is an abstention, so groundedness is skipped.

**Real output:**

```text
Exact match                   1.000  pass    normalised strings are identical
Token F1                      1.000  pass    precision 1.00, recall 1.00 (9 shared tokens)
ROUGE-L                       1.000  pass    LCS 9 tokens; P 1.00, R 1.00
Context recall (lexical)          -  skipped reference answer is an abstention (unanswerable case)
Groundedness (lexical)            -  skipped answer abstained; nothing to ground
```

This is the behaviour the stored offline baseline never shows (§74.5).

### E5 — missing inputs (illustrative input)

E1's question and answer, with no reference and no context:

```text
Exact match                       -  skipped no expected_answer for this case
Token F1                          -  skipped no expected_answer for this case
ROUGE-L                           -  skipped no expected_answer for this case
Context recall (lexical)          -  skipped no expected_answer for this case
Groundedness (lexical)            -  skipped no retrieved context for this case
```

Context recall names the reference as the missing input because the reference check runs before the
context check (`metrics/base.py:76-81`).

### E6 — what normalisation forgives (illustrative input)

Answer "A single Queen!" against reference "single queen". Case, the article and the exclamation
mark are removed, so EM, token F1 and ROUGE-L are all 1.000. The real output reads
`Exact match 1.000 pass normalised strings are identical`, and 1.000 with "2 shared tokens" for the
other two metrics.

### E7 — punctuation style (illustrative input)

* Answer: "The queen’s eggs — mostly fertilised." (curly apostrophe, em dash)
* Reference: "The queen's eggs - mostly fertilised." (ASCII apostrophe, hyphen)

**By hand** (§63.1). In the answer, the curly apostrophe and the full stop are deleted, the em dash
becomes a space and "the" is removed, giving `queens eggs mostly fertilised`. In the reference, the
ASCII apostrophe, hyphen and full stop are deleted, giving the same string. So EM = 1, and all four
tokens are shared in order: token F1 = ROUGE-L = 1.0.

**Real output:**

```text
Exact match                   1.000  pass    normalised strings are identical
Token F1                      1.000  pass    precision 1.00, recall 1.00 (4 shared tokens)
ROUGE-L                       1.000  pass    LCS 4 tokens; P 1.00, R 1.00
```

Apostrophe and dash style do not affect the answer metrics.

### E8 — a judge metric without a key (illustrative input)

```text
> ragwb score --question "q" --answer "a" --metrics faithfulness
error: Metric(s) faithfulness use an OpenAI judge model and need OPENAI_API_KEY.
```

The command exits with code 1. Validation happens before any metric runs
(`metrics/__init__.py:16-26`).

---

## 69. LLM-as-a-judge methodology

This section is based on the code and on the DeepEval library installed in the project environment.
No judge results exist in the project's run store, and none were produced for this book.

### 69.1 How a judge score is produced

`JudgeMetric.score` (`metrics/judge.py:83-98`) does four things for each case:

1. Builds a DeepEval `LLMTestCase` with `input` = question, `actual_output` = answer,
   `expected_output` = reference and `retrieval_context` = the context texts, or `None` if there are
   none (`metrics/judge.py:52-53`).
2. Calls the factory to create a **fresh** DeepEval metric object with a **fresh** judge model object
   (`metrics/judge.py:87`, `metrics/judge.py:118-132`).
3. Calls `metric.measure(test_case)` synchronously. OpenAI SDK exceptions are translated into the
   project's error classes (`metrics/judge.py:88-94`, `errors.py:37-54`).
4. Raises if the metric produced no score. Otherwise it returns the score and DeepEval's reason,
   truncated to 2,000 characters.

The generic wrapper (§64) then applies the skip rules and the range check, clamps floating-point
noise, and turns any exception into a metric **error** for that case.

### 69.2 Judge model configuration

The judge model is a DeepEval `OpenAIModel` built for each measurement with `temperature=0`, the
configured timeout and an optional base URL (`metrics/judge.py:110-116`). Every metric is constructed
with `threshold`, `model`, `async_mode=False` and `include_reason=True`; GEval is constructed without
`include_reason` (`metrics/judge.py:123-133`).

The default judge model is `gpt-4o` (`config.py:70`, environment variable `RAGWB_JUDGE_MODEL`). It
can be overridden per run with `--judge-model` or the "Judge model" field in the UI. The model is set
explicitly rather than left to DeepEval's default, so a run's record says which model judged it.
The CLI records a judge model in the run configuration only when a judge metric is selected
(`cli.py:52-53`), so an offline run never claims a judge it did not use.

### 69.3 Why fresh metric objects per case

DeepEval metric objects keep per-measurement state (score, reason, intermediate verdicts) as
attributes. Reusing one object across cases would let one case's state leak into the next. Sharing
it across worker threads (the runner can evaluate cases in parallel, `runner.py:152-181`) would make
results depend on thread timing. Creating the metric and the model per case, and measuring
synchronously, ties each score to exactly one case (module docstring, `metrics/judge.py:3-5`). The
cost is building a few objects per case, which is negligible next to the API calls.

### 69.4 The four judge metrics

The descriptions below combine the workbench's configuration with the scoring code of the DeepEval
version installed in the project environment: 4.3.1 when this chapter was written, while
`pyproject.toml` requires `deepeval>=4.2.6`. DeepEval's prompts are library internals and can change
between versions.

**Answer relevancy (`answer_relevancy`, `dm.AnswerRelevancyMetric`)**

* **Method:** the judge breaks the answer into statements and gives each a verdict on relevance to
  the question.
* **Score:** in DeepEval 4.3.1, the fraction of verdicts that are "yes" or "borderline"
  (`deepeval/metrics/answer_relevancy/answer_relevancy.py:326-331`). An empty verdict list scores 1
  (`deepeval/metrics/utils/qag.py:118-130`).
* **Inputs:** question and answer; no reference or context needed. **Default threshold:** 0.7.

**Faithfulness (`faithfulness`, `dm.FaithfulnessMetric`)**

* **Method:** the judge extracts claims from the answer and checks each against the retrieval
  context.
* **Score:** the share of claims judged supported. With the default
  `penalize_ambiguous_claims=False`, "borderline" counts as supported
  (`deepeval/metrics/faithfulness/faithfulness.py:408-414`).
* **Inputs:** requires context and is skipped without it. **Default threshold:** 0.7.

**Context relevancy (`context_relevancy`, `dm.ContextualRelevancyMetric`)**

* **Method:** the judge splits the retrieved context into statements and decides whether each is
  relevant to the question.
* **Score:** the share judged "yes" across all chunks. An empty list scores 0
  (`deepeval/metrics/contextual_relevancy/contextual_relevancy.py:276-282`).
* **Inputs:** requires context. **Default threshold:** 0.7.
* This measures the *precision* of retrieval, not recall, so retrieving more chunks tends to lower
  it.

**Correctness (`correctness`, `dm.GEval`)**

* **Method:** a rubric judgement with the criteria string at `metrics/judge.py:25`:

  > "Determine whether the actual output is factually correct based on the expected output"

  and `evaluation_params=[ACTUAL_OUTPUT, EXPECTED_OUTPUT]` (`metrics/judge.py:130-132`). The question is
  not one of the evaluation parameters.
* **Score:** when no rubric is given, GEval asks the judge for a score on a 0–10 range
  (`deepeval/metrics/g_eval/utils.py:405-407`) and normalises it to [0, 1]
  (`deepeval/metrics/g_eval/g_eval.py:145-147`). The installed version requests log-probabilities
  and can compute a probability-weighted score (`deepeval/metrics/g_eval/g_eval.py:357-358`).
* **Inputs:** requires a reference. **Default threshold:** 0.7.

### 69.5 What the workbench does not do for judges

* **No skipping of abstentions.** Only the lexical `groundedness` and `context_recall` skip
  abstentions; judge metrics score an abstention like any other answer.
* **Bounded retries only.** Since release 1.1 a judge call that fails with a transient error (rate limit, timeout,
  connection, 5xx) is retried with exponential back-off and jitter up to the run's `max_retries`
  (`metrics/judge.py:66-78`; Part XIII §141.2). A permanent error, or a transient one that persists beyond the budget,
  still becomes a metric **error** (`metrics/base.py:86-89`) and is excluded from the mean (§70). A heavily
  rate-limited run can therefore still have judge errors.
* **Judge cost is captured, judge tokens are not.** Generator token counts and cost come from generation
  (`runner.py:258-262`). The judge's own cost is whatever DeepEval reports as `evaluation_cost`
  (`metrics/judge.py:97-99`), stored per metric result and summed per run (`aggregate.py:82`, `:91`); the live runs of release 1.3 reported no judge cost for the Groq endpoint (Part XV §160), so it has never
  been checked against a live call, and judge token counts are not available.
* **No repeat measurements in a normal run.** Each case is judged once, so judge variance is not in the run's intervals; `ragwb judge-noise` (release 1.3) re-scores stored answers to measure it (Part XV §164).

### 69.6 Limitations of LLM judges

* **Model opinion, not ground truth.** The module docstring says so (`metrics/judge.py:7-8`), as do
  the UI's Settings page and the footer of the Markdown export (`reporting.py:183-184`).
* **Model dependence.** Scores change with the judge model and with DeepEval's prompt templates.
  Comparing runs judged by different models, or by the same model name across a provider update,
  mixes a change of judge with a change of pipeline.
* **Non-determinism.** `temperature=0` reduces variation but does not guarantee identical outputs
  across calls, and nothing in the workbench checks repeatability.
* **Self-preference.** When the generator and the judge are the same model family (both default to
  `gpt-4o`, `config.py:50,47`), the judge may favour its own style. The workbench neither measures nor
  corrects this.
* **Ceiling effects.** Answer relevancy and faithfulness count the share of acceptable statements or
  claims, and "borderline" verdicts count as acceptable. Concise answers drawn from the context can
  therefore cluster at 1.0, leaving no room to show an improvement. This is a property of the
  formulas above; it has not been measured here.
* **Garbage in.** Faithfulness and context relevancy are only as meaningful as the context passed to
  them. The workbench scores the chunks the retriever actually returned, never a model's description
  of them (§61.1). That choice is what makes these two metrics interpretable at all.

### 69.7 How a judge could be validated (recommendation, not implemented)

The workbench does none of the following. These are the checks this chapter recommends before
relying on judge scores for decisions:

1. **Agreement with human labels.** Have at least two people label a sample of cases: correct,
   partly correct or incorrect for correctness, and supported or not per claim for faithfulness.
   Measure inter-annotator agreement first (Cohen's or Krippendorff's κ). Then measure judge–human
   agreement on the same cases, using κ on thresholded pass/fail and Spearman correlation on scores.
   A judge that agrees with humans less than humans agree with each other is not yet a usable proxy.
2. **Threshold calibration.** On the same sample, choose the pass threshold that best separates
   answers humans accepted from answers they rejected, instead of the 0.7 convention (`ragwb calibrate --sweep` since release 1.4;
   the best row is optimistic because it is chosen on the labels it is measured on).
3. **Repeatability.** Score the same run two or more times and report the spread per case. Treat any
   difference between runs smaller than that spread as noise.
4. **Judge sensitivity.** Re-judge one run with a second judge model and check that the ranking of
   runs is stable.
5. **Adversarial probes.** Include cases like those in §68 (inverted answers, paraphrases,
   abstentions, partly correct answers) with known labels, and check that the judge separates them.

---

## 70. Aggregation

`summarize_metric` (`aggregate.py:47-72`) reduces one metric over all of a run's cases.

### 70.1 Case classification

Each case is classified as follows (`aggregate.py:49-62`):

| Situation | Counted as | Enters statistics? |
|---|---|---|
| Case status `error` (generation failed) | `n_error` | No |
| Case ok, metric absent from the case | `n_skipped` | No |
| Metric status `ok` with a score | scored | Yes |
| Metric status `skipped` | `n_skipped` | No |
| Metric status `error` | `n_error` | No |

Missing values are **excluded and counted, never imputed as zero** (`aggregate.py:1-6`). A run summary
therefore always shows `n_scored`, `n_skipped` and `n_error` next to each metric's mean.

One edge case turned up while testing this chapter. Asking for the summary of a metric a run never
computed (for example `exact_match` on `offline-bm25-k3`) returns `n_scored=0, n_skipped=20`: an
absent metric is reported as skipped, not as an error.

### 70.2 Statistics

Over the list of scores *s₁ … sₙ*:

* **mean:** arithmetic mean (`statistics.fmean`, `aggregate.py:66`);
* **median:** `statistics.median`, the average of the two middle values when n is even;
* **std:** *sample* standard deviation (n − 1 denominator, `statistics.stdev`), only for n > 1
  (`aggregate.py:68`);
* **min** and **max**;
* **95% CI:** percentile bootstrap of the mean (§71), only for n ≥ 2;
* **pass rate** = n_passed / n_scored (`aggregate.py:71`). Skipped and errored cases are in neither
  the numerator nor the denominator.

Run-level statistics (`aggregate.py:75-92`) use only successful cases: mean latency, p95 latency by
linear-interpolation percentile (`aggregate.py:37-44`), and token and cost totals. A total is `None`
(shown as "—") when no case reported it.

### 70.3 Consequences of exclusion

Excluding missing values is the right default when the question is "how good are the answers we
got?", but it changes what the mean describes:

* **The case sets differ.** The `injected-failures-30pct` run has a token F1 mean of 0.344 over 17
  cases. `offline-bm25-k3`, which has an identical configuration apart from the injected failures,
  has 0.346 over 20. Paired over the 17 shared cases, the difference is exactly 0.000 on every metric
  (§74.6). The gap between the two means comes purely from which cases failed, so means of runs with
  different `n_scored` must not be compared directly.
* **Selective abstention is not penalised.** Groundedness skips abstentions, so a pipeline is not
  penalised for refusing. A pipeline that refuses often is scored on a smaller, easier subset.
* **Denominators can be tiny.** In `unanswerable-k3`, context recall is scored on 2 of 6 cases (the
  other 4 are skipped as unanswerable). Its mean of 1.000, CI 1.000–1.000 and pass rate of 100%
  describe two questions.

Always read a mean together with `n_scored`, and a pass rate together with its threshold.

---

## 71. Percentile bootstrap confidence intervals

### 71.1 Procedure

`bootstrap_ci` (`aggregate.py:23-34`, constants at `aggregate.py:18-20`) works as follows:

1. If there are fewer than two values, it returns no interval.
2. It seeds a private `random.Random(12345)`.
3. It draws 2,000 resamples of size n **with replacement** from the n values and records each
   resample's mean (`aggregate.py:30`).
4. It sorts the 2,000 means. With α = 0.025, the lower bound is the element at index
   ⌊0.025 · 2000⌋ = 50 and the upper bound the element at index ⌈0.975 · 2000⌉ − 1 = 1949
   (`aggregate.py:31-33`).

The same function serves both a run's metric means and the paired differences between two runs.

### 71.2 What it captures

The interval expresses **sampling uncertainty over questions**. Treat the dataset's questions as a
sample from a larger population of similar questions: the interval says how much the mean would move
under a different sample of the same size. With 20 questions these intervals are wide. Token F1 in
`offline-bm25-k3` is 0.346 with a CI of 0.285–0.419, a width of about 0.13.

### 71.3 What it does not capture

* **Judge noise.** Each case is scored once, and repeated judge calls could give different scores. `ragwb judge-noise` measures this separately (Part XV §164); one measurement exists, for `correctness` only.
  The caption on the Summary tab says this ("they reflect sampling of these questions, not judge
  noise").
* **Generation noise.** With OpenAI generation, rerunning the pipeline could change the answers.
* **Reference and dataset bias.** If the questions or references are unrepresentative, the interval
  is precise about the wrong thing.
* **Dependence between cases.** The bootstrap assumes cases are exchangeable. Near-duplicate
  questions (q10 and q11 are both about the waggle dance and are answered from the same paragraph)
  make the interval too narrow.
* **Small samples.** The percentile bootstrap under-covers for small n and for skewed or bounded
  data. At n = 2 it is degenerate: `bootstrap_ci([0.0, 1.0])` returns (0.0, 1.0), and two equal values
  give a zero-width interval. Identical scores everywhere, such as groundedness 1.0 on every case,
  give 1.000–1.000. That shows the sample has no variation, not that the population value is certain.

### 71.4 Monte Carlo error and determinism

The fixed seed makes the interval reproducible: the same list of values always gives the same
interval. It does not remove Monte Carlo error; it freezes one draw of it. Recomputing `bootstrap_ci`
on the 20 stored token F1 scores of `offline-bm25-k3` with other seeds gave:

| Seed | Interval |
|---|---|
| 12345 (default) | 0.2854 – 0.4194 |
| 1 | 0.2870 – 0.4215 |
| 2 | 0.2889 – 0.4221 |
| 3 | 0.2871 – 0.4249 |

The bounds move by up to about 0.005, so the third decimal of a CI bound carries no meaning.

The interval also depends on the *order* of the values, because the resampler draws by index. The
paired comparison of k1 → k3 token F1 orders the differences by sorted question text and reports a CI
of −0.1163 to −0.0080. The same differences in dataset order, with the same seed, give −0.1157 to
−0.0081. Both are reproducible, neither is more correct, and the gap is Monte Carlo error again.

Formatting adds one more source of disagreement in the last digit. The k1 → k3 context-recall upper
bound is exactly 0.0625. The CLI prints it as 0.062 (Python rounds this exactly representable
halfway value to even), while the Compare page shows 0.063.

---

## 72. Paired comparison of two runs

### 72.1 Pairing

`paired_comparison` (`aggregate.py:164-179`) compares a candidate run B with a baseline run A on one
metric:

1. It maps each run's cases to a key, `" ".join(question.lower().split())`, i.e. lower-cased with
   whitespace collapsed (`aggregate.py:151-152`). Only cases with a non-null score for the metric are
   kept (`aggregate.py:167-167`).
2. It pairs cases whose keys occur in both runs, with the keys sorted (`aggregate.py:169`).
3. For each pair it computes dᵢ = scoreᴮ − scoreᴬ.
4. It reports n_pairs, the means of A and B over the paired cases only, the mean difference, the
   bootstrap CI of the differences, and the counts of wins (d > 10⁻⁹), ties (|d| ≤ 10⁻⁹) and losses
   (d < −10⁻⁹) (`aggregate.py:173-178`).

Pairing by question text rather than case id lets runs on different dataset files be compared on the
questions they share (the docstring at `aggregate.py:166` gives this reason). Three consequences
follow:

* **Only cases scored in both runs count.** Errored or skipped cases on either side drop out, so
  `mean_a` and `mean_b` can differ from the runs' own means.
* **Punctuation is part of the key.** "How do honeybees cool the hive?" and "How do honeybees cool
  the hive" do not pair.
* **Duplicate questions overwrite each other.** If a run contains the same question twice, the later
  case silently replaces the first one in the mapping. The dataset validator warns about duplicate
  questions (`datasets.py:100-102`).

The CLI (`cli.py:115-124`) and the Compare page tabulate every metric the two runs share
(`reporting.py:72-82`). With no shared metric, the CLI prints "The two runs share no metrics." and
exits with code 1. When the runs share metrics but no questions, every row shows 0 paired cases. That
happens for `offline-bm25-k3` against `unanswerable-k3`: even the answerable questions a1 and a2 are
not in `honeybees.jsonl`.

### 72.2 Why pairing helps

The variation between questions is much larger than most pipeline effects, and pairing removes it.
The CI of the per-case differences is therefore narrower than any comparison of two independent run
intervals. In the stored runs, token F1 has a CI of 0.335–0.476 at k = 1 and 0.285–0.419 at k = 3, so
the intervals overlap. Yet the paired difference is −0.057 with a CI of −0.116 to −0.008, which
excludes zero.

### 72.3 The `significant` flag

`significant` is true when the paired CI excludes zero, i.e. `ci_low > 0` or `ci_high < 0`
(`aggregate.py:146-148`). The CLI prints it as `ci_excludes_zero`. The UI turns it into the verdicts
"B better", "B worse" or "inconclusive" (Part VII, §83.5).

How to read it:

* **It is an approximate test.** It is two-sided at about the 5% level, with the small-sample caveats
  of §71.3.
* **There is no multiple-comparison correction.** The flag is evaluated separately for every metric
  and every pair of runs. With four metrics and several run pairs, some "significant" results are
  expected by chance.
* **"Not significant" means "inconclusive at this sample size",** not "no difference".
* **A lower bound of exactly 0.000 is not significant.** Context recall from k = 1 to k = 3 has a
  difference of +0.028 with a CI of 0.000–0.062 (3 wins, 17 ties, 0 losses), so the flag is false.
  From k = 1 to k = 5 the difference is +0.035 with a CI of 0.005–0.070, so the flag is true.
* **All-zero differences give a CI of 0.000–0.000** and the flag is false. That is correct: there is
  no evidence of a difference.

### 72.4 Win / tie / loss counts

The counts complement the mean, because a change in the mean can come from a few large changes. From
k = 1 to k = 3, token F1 falls by 0.057 on average, but only 7 cases got worse, 3 got better and 10
are tied. Two of the losses, −0.356 and −0.349, account for most of the drop. Ties use a tolerance of
10⁻⁹ (`aggregate.py:165`), so lexical scores, which are exact rationals, tie only when they are equal.

---

## 73. Reproducibility

### 73.1 What is recorded

When a run is created, the runner stores (`runner.py:111-117`):

* **The full `RunConfig`:** provider, pipeline, retriever, k, metrics, effective thresholds, models,
  workers, retries, timeout, answer sentences, limit, notes, failure rate and seed, together with
  the generator's actual model name.
* **SHA-256 hashes** of the dataset and document files (`runner.py:99`).
* **Environment information:** package version, Python version, platform, and the versions of
  tracked packages (`runner.py:270-278`).

The configuration contains no secrets (`models.py:114-115`).

### 73.2 The deterministic offline path

With provider `offline` and the BM25 retriever, the results are fully determined by the dataset, the
document, the configuration and the code:

* **BM25 scores** are exact functions of token counts, and ties are broken by document order
  (`retrieval.py:86`).
* **The extractive generator** sorts candidate sentences by (−weight, original order)
  (`providers.py:79`).
* **Lexical metrics** are pure functions.
* **Injected failures** are seeded per (seed, question) with `random.Random(f"{seed}:{question}")`
  (`providers.py:60-66`). Python seeds a `Random` from a string deterministically, so the same cases
  fail on every rerun. In `injected-failures-30pct` (failure rate 0.3, seed 0 and one worker, as
  recorded in its configuration) the failed cases were q03, q16 and q17: 3 of 20, not 6. The rate is
  a per-case probability, not a quota.
* **The bootstrap seed** is fixed.

Only latency varies between reruns. Parallel workers do not change scores, and results keep their
dataset position. The example runs can be recreated in an empty data directory with
`python start.py --setup-only`, or with `scripts/seed_demo_runs.py` (§61). Rerunning them reproduces
the same answers and scores.

### 73.3 Non-deterministic paths

OpenAI generation, OpenAI embeddings and judge metrics all depend on a remote service. The workbench
sets `temperature=0` (`pipeline.py:71`, `providers.py:100`, `metrics/judge.py:112`) and records model
names. It cannot pin the model snapshot behind an alias, cannot record DeepEval's prompts, and does
not repeat measurements. Reproducing an OpenAI run therefore means running it again and expecting
similar, not identical, scores.

### 73.4 Imported runs

`ragwb import <bundle.json> …` reads run bundles written by `ragwb export --format json`. Bundles are
validated and stored with status `imported`, keeping the original status in
`config["original_status"]` (`archive.py:59-81`). The **run summary** of an imported run is
recomputed from the bundle's case results, using the same aggregation as a new run and the bundle's
metric list and thresholds (`archive.py:67-72`); any summary contained in the file is never
displayed. The **per-case scores** are taken from the bundle as they are, because a bundle holds
results, not the means to re-run the pipeline or the judge.

---

## 74. The stored example results

`ragwb list` printed:

```text
                                        run_id                    name    status provider pipeline retriever  k  n_cases  n_errors
20261023-194809-injected-failures-30pct-f8f2ec injected-failures-30pct   partial  offline      rag      bm25  3       20         3
        20261023-194808-unanswerable-k3-a39b19         unanswerable-k3 completed  offline      rag      bm25  3        6         0
        20261023-194808-offline-bm25-k5-b477d1         offline-bm25-k5 completed  offline      rag      bm25  5       20         0
        20261023-194808-offline-bm25-k3-2d53f3         offline-bm25-k3 completed  offline      rag      bm25  3       20         0
        20261023-194808-offline-bm25-k1-7765a3         offline-bm25-k1 completed  offline      rag      bm25  1       20         0
```

All runs use `examples/documents/honeybees.pdf`. The PDF is generated from `honeybees.md` by
`scripts/make_example_pdf.py`, has two pages and yields 11 chunks: the title chunk `p1-b1`
("Honeybees: Life Inside the Colony"), the paragraphs `p1-b2` to `p1-b10`, and `p2-b1`. The
20-question runs use `examples/datasets/honeybees.jsonl`; `unanswerable-k3` uses
`honeybees_unanswerable.jsonl`. Every run uses the offline extractive generator with two sentences
per answer.

### 74.1 Effect of k

From `ragwb show` (offline extractive generator, BM25, 20 cases, 0 errors):

| Run | Token F1 (CI), pass | ROUGE-L (CI), pass | Context recall (CI), pass | Groundedness |
|---|---|---|---|---|
| offline-bm25-k1 | 0.404 (0.335–0.476), 20% | 0.373 (0.301–0.450), 20% | 0.857 (0.798–0.912), 90% | 1.000 |
| offline-bm25-k3 | 0.346 (0.285–0.419), 5% | 0.317 (0.252–0.393), 5% | 0.885 (0.839–0.930), 95% | 1.000 |
| offline-bm25-k5 | 0.346 (0.285–0.419), 5% | 0.317 (0.252–0.393), 5% | 0.892 (0.846–0.937), 95% | 1.000 |

The printed mean latencies were 0.2, 0.2 and 0.3 ms. The paired comparisons (`ragwb compare`) were:

| A → B | Metric | diff | 95% CI | B better / ties / B worse | excludes 0 |
|---|---|---|---|---|---|
| k1 → k3 | Token F1 | −0.057 | −0.116 to −0.008 | 3 / 10 / 7 | True |
| k1 → k3 | ROUGE-L | −0.056 | −0.108 to −0.010 | 3 / 10 / 7 | True |
| k1 → k3 | Context recall | +0.028 | 0.000 to 0.062 | 3 / 17 / 0 | False |
| k3 → k5 | Token F1 | 0.000 | 0.000 to 0.000 | 0 / 20 / 0 | False |
| k3 → k5 | Context recall | +0.007 | 0.000 to 0.021 | 1 / 19 / 0 | False |
| k1 → k5 | Context recall | +0.035 | 0.005 to 0.070 | 4 / 16 / 0 | True |

Groundedness is 1.000 in every run, and every pair ties on it. k1 → k5 prints the same token F1 and
ROUGE-L figures as k1 → k3.

**Finding 1: more context made the extractive answers worse.** Token F1 and ROUGE-L are *higher*
at k = 1 than at k = 3, and both paired intervals exclude zero. The mechanism is in the generator. It
takes the two highest-weighted sentences from all retrieved passages together, so every extra chunk
brings in sentences that compete with the second sentence of the best chunk. The per-case table on
the Compare page (Part VII, §83.6) lists the largest losses:

* "How does a honeybee colony reproduce?": −0.356 (0.629 → 0.273);
* "Why do bees build hexagonal cells?": −0.349 (0.500 → 0.151);
* "What temperature do bees keep the brood nest at?": −0.212;
* "How long does a worker bee live in summer?": −0.191.

The first of these is the title-chunk effect described in §74.2. The three improvements were q01,
q19 and q20.

**Finding 2: context recall rises a little, and partly by accident.** The k = 1 → 3 gain (+0.028) is
inconclusive; the k = 1 → 5 gain (+0.035) excludes zero. Context recall cannot fall as k grows: the
top-k list for a smaller k is a prefix of the list for a larger k, and the measure is a set union. So
every per-case difference is ≥ 0 and there are no losses. Some of the gains come from chunks that do
not answer the question:

* **q04, "What do unfertilised eggs develop into?"** Only the queen paragraph matches the query.
  BM25 gives the other chunks a score of 0 and fills ranks 2–3 with the first chunks in document
  order, the title and `p1-b2`. The reference term "male" is then found in `p1-b2` ("several thousand
  male drones"), so context recall rises from 0.8 to 1.0.
* **q06, "How long does a worker bee live in summer?"** At k = 5 the missing reference term
  "roughly" is found in the swarming paragraph ("roughly half of the workers"), which is the only
  k3 → k5 change.

Context recall therefore rewards retrieving *more text*, not only better text.

**Finding 3: k = 5 changed no answer.** All 20 answers at k = 5 are identical to those at k = 3, so
token F1 and ROUGE-L tie on every case. The extractive generator always found its two
highest-weighted sentences within the first three chunks.

**Finding 4: groundedness is uninformative for this generator.** Every scored case in every run has
groundedness 1.0, as expected for verbatim extraction (§66.2).

### 74.2 The title chunk

The first chunk of the document is its title, "Honeybees: Life Inside the Colony". It has only four
content tokens (honeybee, life, inside, colony), against a mean of about 32 for the other ten
chunks. BM25's length normalisation therefore weights its matches heavily. For a query that shares
only the term "honeybee" (IDF 0.981), the title's BM25 score works out by hand as follows. Chunk
lengths sum to 327 content tokens, so the average length is 327/11 = 29.7. Then:

  score = 0.981 × (1 × 2.5) / (1 + 1.5 × (0.25 + 0.75 × 4/29.7)) = 0.981 × 1.638 = 1.606.

This is the score shown for `p1-b1` on q02, q10, q16 and q17 in the stored k = 3 run. For queries
that share "honeybee" and "colony" (IDF 0.613), the title scores 1.606 + 1.004 = 2.611, displayed
as 2.61.

Two effects follow:

1. **It is retrieved often.** The title is among the retrieved chunks in 9 of 20 cases at k = 3 and
   13 of 20 at k = 5 (never at k = 1), and in 4 of the 6 unanswerable-run cases. It also fills any
   rank whose BM25 score is 0, because ties are broken by document order and the title comes first.
   This happens for q04, q11 and q13 at k = 3.
2. **It becomes a "sentence".** The title has no terminal punctuation, so `split_sentences` returns
   it as a single sentence. Its weight in the extractive generator is the summed IDF of the question
   terms it contains, which for "honeybee … colony" questions beats most real sentences. In
   `offline-bm25-k3`, the answers to q18 ("A colony reproduces by swarming. Honeybees: Life Inside the
   Colony") and q20 include the title. In `unanswerable-k3`, the answer to a2 begins with it.

The title carries no information, so this is a property of the example document, the chunker and
the baseline generator together, not of BM25 alone. It is also exactly the kind of failure the
workbench is meant to expose: the Case detail tab shows the title as a retrieved chunk (Part VII,
screenshot 05).

### 74.3 Per-case findings in `offline-bm25-k3`

* **The best case.** "Where does beeswax come from?" (q13): token F1 0.909, the highest in the run.
  The answer "Beeswax is produced by glands on the underside of young workers' abdomens." differs
  from the reference only in "produced" versus "secreted", and context recall reports "secreted" as
  missing (0.857).
* **Recall without a good answer.** "How is nectar turned into honey?" (q12): context recall 0.909,
  but token F1 only 0.186. The context contains the whole process, but the generator chose "Honey is
  made from nectar." and the sentence about enzymes, missing the fanning and sealing.
* **Inflection mismatches.** For "How do scout bees choose a new nest site?" (q19), the missing terms
  are "dance" and "win", because the document says "dancing" and "attracts a clear majority". For
  "How do honeybees keep warm in cold weather?" (q16), they are "produce" and "shiver", because the
  document says "generate heat by shivering".
* **Wrong answer, perfect recall.** "Which parasite threatens honeybee colonies?" (a2, in the
  unanswerable run): the query terms "parasite" and "threaten" do not match the document's
  "parasitic" and "threats" (§63.2). Only "honeybee" and "colony" score, so the title chunk ranks
  first (2.61) ahead of the threats paragraph (`p2-b1`, 1.56, rank 3). The answer is "Honeybees: Life
  Inside the Colony Honeybees are social insects that live in colonies of tens of thousands of
  individuals.", with token F1 0.000. Context recall is 1.000 because the threats paragraph at rank 3
  contains "varroa" and "mite".

### 74.4 Groundedness and context recall together

Across the 20 cases of `offline-bm25-k3`, context recall ranges from 0.667 (q08: missing "exist" and
"mainly") to 1.000, with 19 of 20 cases at or above the 0.7 threshold. Groundedness is 1.000
throughout. A reader who looked only at these two retrieval and grounding signals would conclude the
pipeline is in good shape. Its answer metrics (token F1 0.346, a 5% pass rate) and the case details
in §74.3 show otherwise.

### 74.5 Unanswerable questions

`ragwb show` for `unanswerable-k3`:

```text
cases 6  ok 6  errors 0  mean latency 0.2 ms
metric                          mean           95% CI    pass  scored  skip  err
Exact match                    0.000      0.000-0.000      0%       6     0    0
Token F1                       0.039      0.000-0.102      0%       6     0    0
Context recall (lexical)       1.000      1.000-1.000    100%       2     4    0
Groundedness (lexical)         1.000      1.000-1.000    100%       6     0    0
```

**Finding 5: by default the extractive baseline never abstains.** (Release 1.1 adds an opt-in `--min-evidence` threshold; its measured trade-off is in Part XIII §142.2, and release 1.2's held-out tuning found it does not pay off on the bundled data, Part XIV §154.) None of the six stored answers is the
abstention sentence. Each of u1–u4 shares at least one content term with some chunk ("honey",
"colony", "nectar", "honeybee", "species"), so some sentence always has positive weight and the
abstention branch (`providers.py:80-81`) is never reached with `min_evidence` at its default of 0. For example, "How much honey does a colony
produce in a year?" is answered with "Honey is made from nectar. Foragers carry nectar back in a
special honey stomach, …". Exact match is 0 on all six cases, including a1 and a2, whose references
the extractive answers do not reproduce exactly.

Context recall was skipped for the four abstention references and scored 1.000 on a1 and a2.
Groundedness is 1.000 on all six, including the four extracted answers to unanswerable questions,
because the metric cannot tell whether an answer addresses the question.

### 74.6 Injected failures

`injected-failures-30pct` has status `partial`, with 17 of 20 cases ok. All three errors (q03, q16,
q17) read "Injected offline failure (offline_failure_rate > 0)", with one attempt each: injected
failures are permanent errors, so they are not retried (`providers.py:63-66`). The summary reports
17 scored cases and 3 errors per metric. The means (token F1 0.344, ROUGE-L 0.320, context recall
0.881) are computed over the 17. Paired with `offline-bm25-k3`, all 17 shared cases tie on every
metric. This run is the reference demonstration for §70.3.

---

## 75. Sources of bias

* **Dataset bias.** 20 questions about one two-page document, all in English, written alongside the
  document. Many questions reuse the document's vocabulary ("waggle", "brood nest", "unfertilised"),
  which favours lexical retrieval and lexical metrics.
* **Reference wording.** Lexical scores reward answers that resemble the reference author's phrasing.
* **Length bias.** Token F1 and ROUGE-L penalise long answers through precision. Context recall
  rewards long contexts, and groundedness rewards short answers.
* **Vocabulary bias.** BM25 and all content-token metrics fail on synonyms and inflections:
  "secreted"/"produced", "parasite"/"parasitic", "dance"/"dancing".
* **Document-structure bias.** A short title chunk attracts retrieval and enters extractive answers
  (§74.2).
* **Stop-list and stemmer artefacts.** Words such as "roughly", "mainly" and "exist" survive as
  "facts", and (before release 1.1) possessives and contractions produced stray `s` and `t` tokens (§63.3).
* **Selection by skipping.** Means are computed on non-skipped, non-errored cases, which may be
  systematically easier.
* **Judge biases.** Model-specific preferences, possible self-preference between a generator and a
  judge from the same family, and preferences for verbosity are not measured here.
* **Construction bias.** Groundedness for an extractive generator is close to a tautology.

---

## 76. Measurement uncertainty

The uncertainty around a reported mean has several components. The workbench quantifies only one of
them:

| Source | Quantified? | How it shows |
|---|---|---|
| Sampling of questions | Yes | 95% bootstrap CI (§71) |
| Bootstrap Monte Carlo error | No (fixed seed) | About ±0.005 on the bounds here (§71.4) |
| Judge variability | No | Would require repeat measurements |
| Generation variability (OpenAI) | No | Would require repeat runs |
| Metric validity (does it measure "correct"?) | No | Requires human labels (§69.7) |
| Threshold choice | No | Pass rates change with thresholds |

With 20 cases, differences in means below roughly 0.05–0.10 are usually within the noise for
answer-overlap metrics. The k1 → k3 token F1 drop of 0.057 only just clears that bar: its interval's
upper end is −0.008. The Compare page says as much ("With 20 cases, small differences are usually
inconclusive"). Report means to three decimals for traceability, but interpret them to one or two.

---

## 77. Known failure modes (summary)

| Failure mode | Affected | Evidence |
|---|---|---|
| Inverted meaning with the same words scores high | token F1, ROUGE-L, groundedness | E3: F1 1.000, ROUGE-L 0.818 |
| Correct paraphrase scores low | EM, token F1, ROUGE-L, groundedness, context recall | E2: 0.083 |
| Synonym or inflection mismatch | BM25, context recall, groundedness | E1 ("gather"), a2 ("parasite"), q19 ("dance") |
| Irrelevant or zero-score chunk satisfies context recall | context recall | q04 "male", q06 "roughly" (§74.1) |
| Perfect context recall with a wrong answer | context recall | a2: 1.000, F1 0.000 |
| More retrieved text lowers answer quality | extractive generator, answer metrics | k1 → k3 token F1 −0.057 |
| Title chunk retrieved and copied into answers | BM25 + chunker + extractive generator | §74.2 |
| Answer ignoring the question is still "grounded" | groundedness | unanswerable-k3: 1.000 on u1–u4 |
| Extractive baseline never abstains by default (opt-in `min_evidence` in 1.1, Part XIII §142.2) | offline generator | §74.5 |
| Abstention phrases misdetected | groundedness, context recall skipping | §63.4 probes |
| Possessives and contractions yielded stray `s` and `t` tokens (fixed in release 1.1) | context recall, groundedness, BM25 | §63.3 (none in the bundled data) |
| Means over different case sets | all aggregates | §74.6 |
| Degenerate CIs at tiny n or zero variance | CIs | §70.3, §71.3 |
| Judge retries are bounded and judge cost is DeepEval's unverified figure (release 1.1) | judge metrics | §69.5 |
| Pairing misses near-identical questions | paired comparison | §72.1 |

---

## 78. Appropriate and inappropriate uses

**Appropriate uses:**

* **Regression testing.** A deterministic offline run whose scores change indicates that the code,
  data or configuration changed, and the stored hashes and configuration identify which.
* **Comparing retrieval settings** (k, BM25 versus embeddings) with paired context-recall
  differences, remembering that context recall never falls as k grows. The answer metrics must be
  read alongside, because more context can hurt the answer (§74.1).
* **Locating weak cases.** Sorting by a metric and reading the case detail with its retrieved
  context is more informative than any mean; that is how every finding in §74 was found.
* **A baseline floor.** The extractive generator's numbers show what copying sentences achieves. An
  LLM pipeline that does not beat it on correctness is not adding value.
* **Screening with judge metrics,** followed by human review of the low-scoring and borderline cases.

**Inappropriate uses:**

* Declaring a pipeline "correct" or "safe" from lexical scores or pass rates.
* Treating judge scores as ground truth, or comparing judge scores produced by different judge
  models.
* Comparing the means of runs with different datasets or different `n_scored`, or comparing pass
  rates under different thresholds.
* Treating a non-significant paired difference as proof of equivalence.
* Generalising results from the 20-question honeybee set to other documents, domains or languages.
