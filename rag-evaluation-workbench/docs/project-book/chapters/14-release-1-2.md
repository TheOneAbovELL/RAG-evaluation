# Part XIV — Release 1.2: history, gates, accounts and packaging

Release 1.1 made the tool *trustworthy to run*. Release 1.2 (version `1.2.0`, `src/rag_workbench/__init__.py:13`) makes
it *comfortable to live with*: runs can be labelled and found again, a change can be checked against a baseline
automatically, more than one document and one dataset ship with the product, several people can use one instance under
their own names, and the package can be installed somewhere other than a checkout. It also contains one experiment that
did **not** work, and this Part reports it as plainly as the ones that did. Every line reference points at the final
source; every number is quoted from `CHANGELOG.md`, `docs/KNOWN_LIMITATIONS.md` or `docs/TESTING.md`, or comes from a
command whose output is shown here.

The changelog describes the release as the follow-up work that "can be built and verified without a live API key". That
sentence is also the boundary of this Part as written for release 1.2: nothing here was checked against OpenAI, Grok or DeepEval (release 1.3 closed part of that gap, Part XV), and §159.3
lists exactly what that leaves open.

**What did not change.** The default behaviour of the product is the same. The five example runs (86 cases in total)
score identically under 1.0.0 and 1.2.0 — a comparison of every stored score found 0 differences. The default
metrics, retriever, generator and thresholds are untouched. Every new `RunConfig` field has a default
(`models.py:117`), the run store migrates in place (§152.2), and the bundle format (version 1) is unchanged, so a bundle exported by 1.1 loads with `tags` defaulting to empty (by construction; not exercised by a test). Everything
below is opt-in or additive, with two exceptions that are cosmetic and listed in §159.4: the section headings of the web
pages are now level-2 headings, and the Overview table gained a `tags` column.

## 150. Motivation: what a second release is for

A first release is judged by whether it works; a second is judged by whether it survives use. Using release 1.1 for a
while exposes eight frictions, and each is a section of this Part.

| Friction | What it costs | Release 1.2 answer | Section |
|---|---|---|---|
| One document, one dataset | Every example experiment is over the same 20 honeybee questions; conclusions drawn from it do not transfer, and there is little unanswerable material to exercise abstention | Three more original documents with 30 tagged questions each | §151 |
| A growing run list nobody can search | After a few dozen runs "which one was the prompt-v2 baseline?" needs the run id | Tags, notes, search, filters, schema 3 | §152 |
| Comparing two runs by eye | Whether a change made things worse is a judgement made again each time, and an empty or underpowered comparison looks like a clean one | `ragwb regress`, with an exit code that never lets "nothing was checked" look like "passed" | §153 |
| An option that is off by default for no measured reason | `min_evidence` was introduced in 1.1 with a warning that it "must be tuned on your own data" — and no way to do that honestly | `ragwb tune-abstention`: tune on one half, report on the other | §154 |
| Lexical metrics punish paraphrase | A correct answer in different words scores low | Optional local-embedding metrics | §155 |
| One shared password | Nobody is accountable for a run, and access cannot be revoked per person; credentials cross the network in clear text | Named accounts, attributable sign-ins, `started_by`, TLS | §156 |
| It only works from a checkout | The package derived its data folder from its own source location | `RAGWB_HOME`, a checkout check, bundled examples, a Dockerfile | §157 |
| "No accessibility audit" | A stated gap with no measurement behind it | A scripted check of five pages; two defects fixed; the rest listed | §158 |

The two design rules of release 1.1 still govern everything:

1. **Never hide missing data.** A gate that could not judge any metric exits with its own status (4), not 0; an unknown
   judge cost stays `None`; an unavailable metric is refused with an install hint, not scored as zero.
2. **Say what was and was not verified.** Every new feature below is tested offline. Three of them — semantic metrics,
   the Docker image, and a true wheel install — could not be exercised against the real thing in the environment where
   the project was built, and each section says so where it matters.

## 151. Data: three more documents and a richer dataset format

### 151.1 Why more data came first

Every later feature in this Part needs something to run on. Tuning an abstention threshold (§154) on a dataset that
contains four unanswerable questions would be meaningless; a regression gate (§153) needs enough paired questions to
judge a metric; slices (§142.3) need metadata that varies. The bundled data before 1.2 was
one 20-question honeybee dataset, a six-row unanswerable set and a five-row paraphrase CSV. Release 1.2 adds three
documents — **volcanoes**, **coffee** and **lighthouses** — each with its own 30-question dataset, so the bundled
collection is now four documents and 110 questions (20 + 3 × 30).

All three documents are original text written for the project, one title and fourteen paragraphs each. That matters
for two reasons: there is no licensing question to answer before shipping them inside a wheel (§157), and nobody can
accuse an evaluation of "the model memorised this" when the text did not exist before the project did.

### 151.2 How a document becomes chunks

Each document exists twice, as Markdown (`examples/documents/<name>.md`) and as a PDF
(`examples/documents/<name>.pdf`), because the PDF extraction path is part of what the product claims to support.
The PDFs are generated, not drawn: `scripts/make_example_pdf.py` takes an optional document name (default `honeybees`)
and renders `examples/documents/<name>.md` onto an A4 page, one text block per paragraph, with a bold title
(`scripts/make_example_pdf.py:22-46`). The module docstring states the contract: "a `# Title` line followed by
blank-line separated paragraphs", so `documents.load_chunks` yields one chunk per paragraph. Each new document loads as
**15 chunks** — the title and 14 paragraphs — and `test_document_yields_one_chunk_per_paragraph`
(`tests/test_example_corpus.py:25`) asserts that both the Markdown and the PDF form give exactly the number of
blank-line-separated blocks.

The title is a chunk of its own. That is the known "headings become chunks" behaviour of §142.2,
and it is deliberately left in: `--skip-headings` exists to deal with it, and shipping documents on which the problem
is visible keeps that option testable.

### 151.3 The dataset format: metadata that carries meaning

Each new dataset row has the shape

```json
{"id": "v01", "question": "What is molten rock called once it has reached the surface in an eruption?",
 "expected_answer": "Once erupted it is known as lava.",
 "metadata": {"type": "factual", "difficulty": "easy", "topic": "definition"}}
```

— the fields the dataset loader already supported (`datasets.py` accepts a `metadata` object of scalar values), used
systematically. Three keys appear on every row:

| Key | Values | Purpose |
|---|---|---|
| `type` | `factual`, `numeric`, `list`, `why`, `unanswerable` | Slice by kind of question; `unanswerable` rows carry the standard abstention sentence as their reference, which is how `text.is_abstention` and the tuner (§154) recognise them |
| `difficulty` | `easy`, `medium`, `hard` | Slice by how hard the question is meant to be |
| `topic` | free text, for example `definition` | Slice by sub-topic |

Three rows in each dataset also carry `style: paraphrase`, marking questions worded away from the document's own
vocabulary — the case where BM25 and lexical metrics are expected to struggle.

The counts, taken from the files, are:

| Dataset | Questions | factual | numeric | list | why | unanswerable |
|---|---:|---:|---:|---:|---:|---:|
| `volcanoes.jsonl` | 30 | 14 | 2 | 4 | 5 | 5 |
| `coffee.jsonl` | 30 | 13 | 2 | 6 | 4 | 5 |
| `lighthouses.jsonl` | 30 | 10 | 2 | 4 | 9 | 5 |

Together with `honeybees_unanswerable.jsonl` (four unanswerable and two answerable questions) the bundle therefore holds
19 unanswerable questions: the pool that §154 splits. `test_dataset_rows` (`tests/test_example_corpus.py:34`) asserts
30 unique ids per dataset, the three metadata keys on every row, the allowed values of `type` and `difficulty`, at least
five unanswerable rows each with the abstention sentence, and a non-empty reference on every other row. The tests are
*static* checks of well-formedness — they run no evaluation — so they say the data is usable, not that it is good.

### 151.4 What the new data scores

Measured baselines, offline, BM25, `k = 3`, all 30 cases each, as produced by running the default metrics:

| Dataset | token F1 | context recall | ROUGE-L | groundedness |
|---|---:|---:|---:|---:|
| volcanoes | 0.199 | 0.660 | 0.179 | 1.000 |
| coffee | 0.257 | 0.765 | 0.229 | 1.000 |
| lighthouses | 0.212 | 0.819 | 0.197 | 1.000 |

Read these as the book has always asked: groundedness is 1.0 *by construction* because the offline generator only quotes
retrieved text (§63); token F1 and ROUGE-L are low because the extractive baseline quotes whole sentences while
the references are short paraphrases; and the datasets include five unanswerable questions each, on which a
reference-based metric has nothing to measure. The honeybee dataset scores higher on token F1 (0.346 at `k = 3`) — a
reminder that these three figures are properties of *these documents and these questions*, not of the tool.

**Honest limits.** The questions and references were written alongside the documents, so retrieval is easier
than on found text, and nothing in the repository records an independent review or second labeller; difficulty and topic are the author's judgement; thirty
questions per document is still a small sample (the bootstrap intervals in the UI will say so). The data exists to
exercise the tool, not to rank retrievers.

## 152. Run history: tags, notes and search

### 152.1 The model

A run now has two organising fields next to its name: **tags** and **notes**. `RunRecord.notes` already existed (a free
text field set when a run started); `RunRecord.tags` is new (`models.py:197`), a list of short strings that defaults to
empty, so nothing that builds a run record has to change.

The rules live in one small module, `src/rag_workbench/history.py`, used identically by the CLI and the UI:

* A tag is lowercase, at most 30 characters, made of letters, digits, `.`, `_` and `-`, starting with a letter or digit
  (`history.py:16`, `:18`); a run has at most 10 (`history.py:15`). `normalise_tags` (`history.py:25-38`) lowercases,
  strips, turns inner spaces into hyphens, drops blanks and duplicates (keeping first-seen order) and raises
  `TagError` for anything else.
* `parse_tag_list` (`history.py:41-43`) accepts commas **or whitespace** as separators. That is convenient in the UI
  text box, and it has a consequence worth knowing: `--add "prompt v2"` is *two* tags, `prompt` and `v2`. Run against a
  real run, `ragwb tag RUN --add baseline,"prompt v2"` printed `tags = baseline, prompt, v2`. A tag with a space in it
  has to be typed with the hyphen (`prompt-v2`).
* Notes are trimmed; empty or blank means "no note" (stored as `None`); more than 2,000 characters is refused
  (`history.py:17`, `:46-51`).

Search (`history.py:63-79`) is deliberately plain: split the query into words, and require **every** word to appear,
case-insensitively, in a single string built from the run's id, name, notes, tags, status, provider, pipeline,
retriever and the *file names* of its dataset and document (`_haystack`, `history.py:54-60`; backslashes in Windows
paths are normalised first, so `honeybees.jsonl` matches on every platform). It is a substring match, not a ranking:
`aggr` finds `aggregate`. An optional `tag` filter and an optional `status` filter are exact. Order is preserved.

**Why no full-text index.** A run history is dozens or hundreds of rows read from one SQLite file; scanning them is
instant, and an index would add a second structure that can disagree with the first. The design target is "find the run
I half remember", not "search a corpus".

### 152.2 Schema version 3, and a migration that checks columns

Tags needed a column, so the storage schema moved from version 2 to **3** (`storage.py:26`). The new column is
`tags_json TEXT NOT NULL DEFAULT '[]'` (`storage.py:46`), a JSON list in the same style as the other JSON columns.
What is worth reading is how the migration decides what to do (`storage.py:74-81`):

```python
                # Migrations add whatever a store created by an older version lacks (v1: heartbeat, v2: tags).
                columns = {row["name"] for row in conn.execute("PRAGMA table_info(runs)")}
                if "heartbeat_at" not in columns:
                    conn.execute("ALTER TABLE runs ADD COLUMN heartbeat_at TEXT")
                if "tags_json" not in columns:
                    conn.execute("ALTER TABLE runs ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'")
                if version < SCHEMA_VERSION:
                    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
```

Release 1.1 migrated by comparing `PRAGMA user_version` with the target; 1.2 asks the table which columns it has and adds
the missing ones. The reason is that *a version number can lie and a column list cannot*: a store whose
`user_version` was bumped by a crashed earlier attempt, or copied from another machine, or created at 1 and touched by
a 1.1 build, is handled the same way. `ADD COLUMN` with a constant default is a metadata-only change in SQLite, so the
migration is instantaneous and the old rows read back with `[]`. A store from a *newer* version is still refused
(`storage.py:72-73`), so an old binary never writes to a schema it does not understand. The user-visible statement in the
changelog — "storage schema 3 (migrates in place)" — is exercised by `test_schema_v1_store_is_migrated` (`tests/test_storage.py:77`); `ragwb doctor` reports the result as `run store  schema v3`.

Two small writers were added, `set_tags` and `set_notes` (`storage.py:137-148`). Both are single `UPDATE` statements and
both raise `StorageError` when the id does not exist (`rowcount == 0`), so a stale page cannot silently tag nothing.
`create_run` and `_row_to_run` carry the new column (`storage.py:106`, `:198`). Because tags are part of
`RunRecord`, they are inside exported bundles with no change to the bundle format
(`test_tags_travel_with_an_exported_bundle`, `tests/test_history.py:94`).

### 152.3 On the command line

| Command | Effect |
|---|---|
| `ragwb tag RUN [--add a,b] [--remove c]` | Edit the tags; prints the resulting list (`cli.py:115-121`) |
| `ragwb note RUN "text"` / `ragwb note RUN --clear` | Set or clear the note; exactly one of the two must be given (`cli.py:221-228`) |
| `ragwb list [--search WORD...] [--tag T] [--status S]` | Filtered list; the table has a `tags` column (`cli.py:99-112`) |

Removal happens before addition in `cmd_tag` (`cli.py:116-118`), so `--remove x --add x` leaves the tag in place. A
filtered list that matches nothing says so and gives the total ("No run matches (of 2 stored)") rather than printing
an empty table. Run against a real two-run store:

```
$ ragwb list --tag baseline --search first
                        run_id    name    status provider pipeline retriever  k  n_cases  n_errors               tags
20261027-212430-base-k3-5d3ae8 base-k3 completed  offline      rag      bm25  3       20         0 baseline,prompt,v2
```

### 152.4 In the web app

* **Overview** gained a *Search runs* box and a *Tag* selector above the runs table, and the table gained a `tags`
  column (`ui/views/overview.py:38-53`); the tag selector is built from the tags that exist. The screenshot in
  §80.3 shows both controls; the `tags` column is empty there because the example runs are untagged.
* **Run results** shows tags and notes under the title (`ui/views/results.py:54-57`), and the *Export & manage* tab has a
  *Tags and notes* expander with a text input, a text area and a *Save tags and notes* button
  (`ui/views/results.py:190-207`). Invalid input is reported with `st.error`, not an exception.

`test_overview_search_and_tag_filter` and `test_results_page_saves_tags_and_notes_and_rejects_bad_tags`
(`tests/test_history.py:143`, `:162`) drive both pages with Streamlit's AppTest.

**Honest limits.** Tags are per run, not per case. Editing tags or notes is not logged or versioned: the last save wins,
and anyone who can use the app can edit anyone's run (the same no-roles caveat as §156). Notes are plain text; they are
HTML-escaped where displayed, like every user-supplied value in the app.

## 153. The regression gate: `ragwb regress`

### 153.1 The question

After changing a prompt, a retriever setting or a model, the question is not "did the mean go down?" — it nearly always
moves a little — but "did it go down by more than noise, on something I care about?" §71 and §72 already provide the
statistics (a paired bootstrap interval of the per-question difference); release 1.2 turns them into a *decision that a
script can act on*:

```
ragwb rerun BASELINE_ID --name candidate     # same configuration, today's code
ragwb regress BASELINE_ID CANDIDATE_ID       # exit 0 pass, 3 regression, 4 nothing could be judged
```

### 153.2 The verdict for one metric

`check_regression` (`regression.py:66-85`) pairs the two runs question by question (`paired_comparison`, which matches
cases by normalised question text, so run ids and dataset file names may differ: `aggregate.py:151-152`, `:164`) and gives
each shared metric one of five verdicts (`regression.py:28`, `:74-81`):

| Verdict | Condition | Fails the gate? |
|---|---|---|
| `insufficient` | fewer than `min_pairs` paired questions (default 10), or no difference could be computed | no — but see exit 4 |
| `regression` | mean difference below `−max_drop` (default 0.02) **and** the bootstrap interval of the difference excludes zero | **yes** |
| `possible` | mean difference below `−max_drop`, but the interval still contains zero | no, with a printed note |
| `improved` | interval excludes zero and the mean difference is positive | no |
| `ok` | everything else | no |

"Excludes zero" is `PairedComparison.significant` (`aggregate.py:145-148`): the low end above 0 or the high end below 0.
The two thresholds are doing different jobs. `max_drop` says how large a drop *matters to you*; the interval says whether
the drop is *distinguishable from sampling noise*. A drop must be both. A large drop whose interval straddles zero is
called `possible` rather than a failure, because with a 20-question dataset that is the honest reading — and failing a
build on it would teach people to ignore the gate.

The **error rate is gated separately** (`regression.py:62-63`, `:83-85`): if the candidate's share of `error` cases
exceeds the baseline's by more than `max_error_increase` (default 0.05), the gate fails even though the cases that
*did* score look identical. Without that, a candidate that crashes on a third of the questions could pass because the
survivors scored the same — the "missing data hides inside the mean" failure that §70.3 argues against.

### 153.3 The exit code: three outcomes, not two

```python
    @property
    def exit_code(self) -> int:
        if self.error_regression or any(f.verdict == "regression" for f in self.findings):
            return EXIT_REGRESSION
        if not any(f.verdict != "insufficient" for f in self.findings):
            return EXIT_UNJUDGED
        return EXIT_OK
```

(`regression.py:53-59`, constants at `:29`.) The second branch is the point of the design. If *every* metric is
`insufficient` — too few paired questions, no metrics in common, a `--metrics` filter that matched nothing — the gate
returns **4**, "NOT JUDGED", and prints that "nothing was verified". A gate that returned 0 in that situation would be
worse than no gate, because it turns a missing check into a green tick. Exit 4 is a different number from 3 so a pipeline
can decide separately whether an unjudged comparison blocks a release.

### 153.4 Measured behaviour on real runs

All of this was run for this chapter (offline, bm25, the honeybee dataset, 20 questions): a baseline at `k = 3` and a
candidate at `k = 1`, created with `ragwb run` and compared with `ragwb regress`:

```
metric                verdict        pairs  baseline  candidate     diff  95% CI of diff
token_f1              improved          20     0.346      0.404   +0.057  [+0.008, +0.116]
rouge_l               improved          20     0.317      0.373   +0.056  [+0.010, +0.108]
context_recall        possible          20     0.885      0.857   -0.028  [-0.062, +0.000]
groundedness          ok                20     1.000      1.000   +0.000  [+0.000, +0.000]
error rate: baseline 0.0%, candidate 0.0%
PASS: no significant regression.
Note: a 'possible' drop is larger than 0.02 but its interval includes zero; gather more questions before trusting either reading.
```

Four things in this output are worth reading slowly.

1. The candidate retrieves fewer chunks, so token F1 and ROUGE-L rise — the extractive baseline quotes fewer irrelevant
   sentences — while context recall falls, because fewer chunks give less coverage of the reference. That is exactly the
   trade-off of the limitation noted since release 1.0 (token F1 lower at `k = 3` than at `k = 1`).
2. `context_recall` shows a drop of 0.028, larger than the 0.02 tolerance. Its interval's upper end prints as `+0.000`;
   the test is a strict inequality on the unrounded value, and the gate classified it `possible`, not `regression`. It
   passes — and the note under the table says why you should not rest on that.
3. `groundedness` is `ok` with a zero-width interval: both runs score 1.0 on every question, as they must (§151.4).
4. The verdict is about **this metric set**. The gate has no opinion on a metric you did not run.

The other outcomes, also run:

| Command | Output (last line) | Exit |
|---|---|---|
| `ragwb regress BASE BASE` (a run against itself) | `PASS: no significant regression.` | 0 |
| `ragwb regress BASE CAND --min-pairs 50` | `NOT JUDGED: no metric had at least 50 paired questions; nothing was verified.` | 4 |
| `ragwb regress BASE INJ`, where `INJ` was run with `--inject-failures 0.3` (3 of 20 cases failed) | `error rate: baseline 0.0%, candidate 15.0%  -> REGRESSION`, then `FAIL: regression detected.` | 3 |

In the third row every metric is `ok` on the 17 surviving pairs, yet the gate fails — the error-rate rule working as
designed. Self-comparison passing is a sanity check of the plumbing, not evidence about anything.

The unit tests (`tests/test_regression.py:36-93`) cover each branch with constructed runs: a clear drop, identical runs,
a clear gain, a noisy drop (`possible`), a drop inside the tolerance, too few pairs, no shared metrics, more failures
with matching scores, a `--metrics` filter, and the exit codes through the real CLI (`test_cli_regress_exit_codes`,
`tests/test_regression.py:93`). The command itself is `cmd_regress` (`cli.py:138-147`), with options at `cli.py:573-580`.

### 153.5 Honest limits

* **Several metrics, no correction.** The gate looks at each metric separately at 95 % and does not adjust for looking at
  four of them. With four independent metrics the chance that *some* interval excludes zero by luck is higher than 5 %.
  The `possible` class is the partial answer; it is not a multiple-comparison procedure.
* **One tolerance for every metric.** `max_drop = 0.02` is an absolute difference on a 0–1 scale. A 0.02 drop in
  groundedness and a 0.02 drop in token F1 are not equally important, and the CLI offers one number for all of them
  (`--metrics` narrows which metrics are gated; it does not give them separate tolerances).
* **Sample size sets what is detectable.** With 20 pairs, the intervals in §153.4 are about ±0.05 wide; a true drop
  smaller than that will usually be `ok` or `possible`. A passing gate means "no *detectable* regression", and the
  detection limit is printed in the interval, not in the verdict.
* **Judge noise is not in the interval.** For LLM-judge metrics the bootstrap captures question sampling only
  (`docs/KNOWN_LIMITATIONS.md`); the same run scored twice by a judge would differ, and the gate would not know.
* **Pairing is by question text.** Two runs over different datasets with few questions in common give few pairs and end
  in `NOT JUDGED` — which is the correct outcome, and also a possible surprise.

## 154. Abstention tuning, and an experiment that failed

### 154.1 The setup

§142.2 introduced `min_evidence`: the offline generator declines to answer when the sentences it chose cover too
small an IDF-weighted share of the question's content terms. It was off by default, with a warning that it traded missed
answers for fewer wrong ones and "must be tuned on your own data". Release 1.2 supplies the tuning — and then reports
what the tuning found.

`ragwb tune-abstention` (`cli.py:124-135`, parser at `cli.py:603-606`) is built around the one rule that makes a tuning
result worth reading: **a threshold must be reported on questions it was not chosen on.** A threshold picked by looking at
the same questions it is then scored on flatters itself, and with a few dozen questions the flattery is large. So
`src/rag_workbench/abstention.py`:

1. **Splits** the questions into a development half and a test half, deterministically, by the parity of the first
   byte of `SHA-256("<document file name>:<case id>")` (`abstention.py:96-103`). Nothing is random, so the same data
   splits the same way on every machine; the document name is the salt, so documents split independently.
2. **Labels** each question with what *should* happen: a question should be declined when its reference answer is
   itself an abstention (`should_abstain`, `abstention.py:92-93`, using `text.is_abstention`, `text.py:98-100`);
   every other question should be answered.
3. **Searches** 20 settings on the development half — `min_evidence` from 0.0 to 0.9 in steps of 0.1
   (`THRESHOLDS`, `abstention.py:33`) with and without `--skip-headings`
   (`abstention.py:128`) — building a real BM25 offline pipeline for each (`_decisions`, `abstention.py:106-118`).
4. **Chooses** by *balanced accuracy*: the mean of the share of unanswerable questions declined and the share of
   answerable questions answered (`Confusion.balanced_accuracy`, `abstention.py:71-74`). Plain accuracy would reward
   never abstaining when almost every question is answerable; balanced accuracy weights the two kinds of error equally.
   Ties go to the lowest threshold and to *not* skipping headings (`abstention.py:136-139`), so the least intrusive setting
   that does as well wins.
5. **Reports** the chosen setting and the untuned baseline (`min_evidence = 0.0`) on the held-out half
   (`abstention.py:141-144`), plus a warning when the held-out half has fewer than 30 unanswerable questions
   (`MIN_RELIABLE_UNANSWERABLE`, `abstention.py:34`, `:146-148`).

By default the tuner uses the four bundled document/dataset pairs (`cli.py:124-135`): `honeybees_unanswerable` with
`honeybees`, then `volcanoes`, `coffee` and `lighthouses` — 96 questions, of which 19 are unanswerable. Other data can be
supplied with `--dataset` and `--document`, in matching order.

### 154.2 The result

```
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

(abridged; the full output also lists the next four development settings. This is the actual output of the command on
the bundled data, re-run for this chapter.)

Read it in four steps.

* **The default declines nothing.** On the held-out half, `min_evidence = 0` declined 0 of 12 unanswerable questions and
  answered all 33 answerable ones: balanced accuracy 0.500, the value of a classifier that ignores its input.
* **The tuned setting declines almost every unanswerable question — and most answerable ones.** At `min_evidence = 0.8`
  it declined 10 of 12 unanswerable questions, but it also declined 24 of the 33 answerable ones (it answered only 9).
  Balanced accuracy 0.553.
* **The gain is small against the noise.** Each unanswerable question moves balanced accuracy by 1/12 × 1/2 ≈ 0.042, so
  the whole improvement of 0.053 is worth about one and a quarter unanswerable questions in a 12-question sample. The
  tool prints exactly that caution (the last line).
* **The development score overstates the test score.** The chosen setting scored 0.716 on the half it was chosen on and
  0.553 on the other — the optimism that selection always carries, visible because the halves were kept apart.

**Conclusion: this is a poor trade, and the default stays off.** A setting that throws away 73 % of answerable questions
to catch 83 % of unanswerable ones is not a better assistant; it is a different failure. The reason is structural: the
extractive baseline sees word overlap, and an unanswerable question that shares vocabulary with the document (the bundled honeybee question "Which
flowers produce the most nectar?" is one) looks no different, by overlap, from a hard answerable
question. Deciding whether the retrieved text *answers* the question needs something that reads for meaning — a judge
model — and the known limitation says so (`docs/KNOWN_LIMITATIONS.md`, *Abstention tuning result*).

### 154.3 Why report a negative result

Three reasons that apply beyond this tool. First, the work *was* the right work: a tuner that cannot say "no setting
helps" is not a tuner (`abstention.py:149-150` adds the note "the baseline is the right default" when no setting beats
never abstaining on the development half). Second, an option that stays off for a *measured* reason is worth more than one
that stays off by convention — a reader no longer has to wonder whether it would have helped. Third, the result is
reproducible: the split is a hash, the search is a grid, and `test_tuning_reports_a_held_out_half_and_is_reproducible`
(`tests/test_abstention.py:50`) checks that two runs of the tuner give identical reports.

### 154.4 Honest limits

* The test half has **12** unanswerable questions; the figures are wide-interval estimates (the tool says so).
* One grid, one retriever (BM25), one generator (the extractive baseline), four short documents written for the project.
  A threshold tuned here says little about another corpus; the command exists so it can be re-tuned on one.
* Balanced accuracy weights the two kinds of mistake equally. If wrongly answering an unanswerable question is much
  worse than missing an answer (or the reverse), a different objective would choose differently.
* The tuner does not apply anything. It prints a recommendation; setting `--min-evidence` remains a deliberate act.

## 155. Optional semantic metrics

### 155.1 Why they exist

Token F1 and ROUGE-L reward shared words, so a correct answer in different words scores low (§63). Embedding
similarity compares *meaning* instead. Release 1.2 adds two metrics, offline in the sense that no API is called, using a
small sentence-embedding model that runs on the local machine:

| Metric | Computes | Needs |
|---|---|---|
| `semantic_similarity` | cosine similarity between the answer and the reference answer | reference |
| `semantic_context_recall` | the **best** cosine similarity between the reference and any single retrieved chunk | reference, context |

Both default to a pass threshold of 0.7 (`metrics/semantic.py:107-116`), and their family is the new `semantic`
(`metrics/base.py:25`).

### 155.2 Design: optional, lazy, refused with a hint

The metrics are **optional** because the base install must stay small and installable offline: they need the
`fastembed` package, which is not a dependency (`pyproject.toml:7-18` lists the runtime set). Several decisions follow
from that:

* `MetricSpec` gained `requires_local_model` (`metrics/base.py:46`), next to `requires_openai`. The registry uses it in
  `validate_metric_names` (`metrics/__init__.py:25-27`): selecting a semantic metric without the package raises
  `ConfigError` carrying `INSTALL_HINT` ("run `uv pip install fastembed`"), *before* any case is evaluated. Run for this
  chapter, in an environment without the package:
  `ragwb run --metrics semantic_similarity` → `error: Metric(s) semantic_similarity are unavailable. The semantic metrics
  need the optional 'fastembed' package: ...`, exit 1. `ragwb metrics` still lists both metrics, with `fastembed` as a
  requirement.
* The web app only offers them when `semantic_available()` is true (`ui/views/new_run.py:131`) and otherwise shows a
  one-line caption saying how to enable them (`ui/views/new_run.py:136-137`).
* The model is chosen by `RAGWB_LOCAL_EMBEDDING_MODEL` (`config.py:72`, `:180`), default `BAAI/bge-small-en-v1.5`. The
  first use downloads that model from its public hub; the module docstring is explicit that only the model is fetched
  and no project data leaves the machine (`metrics/semantic.py:10-13`).
* **Lazy and shared.** `SemanticMetric` builds its embedder on first use, under a lock (`metrics/semantic.py:87-91`), so
  a run that never scores a semantic metric never loads a model, and `local_embedder` is memoised
  (`metrics/semantic.py:72-74`); the ONNX session itself is guarded by another lock because several worker threads
  share it (`metrics/semantic.py:64-69`). `test_the_embedder_is_created_once_and_lazily` (`tests/test_semantic.py:81`)
  checks the once-and-lazy part.
* The wrapper that handles skipping and errors for every metric is reused unchanged: a missing reference gives
  `skipped`, an embedder exception gives an `error` result, not a crashed run (`tests/test_semantic.py:64`, `:71`).

### 155.3 The scoring

```python
        if self._kind == "similarity":
            answer_vec, reference_vec = embedder.embed([inp.answer, reference])
            cos = cosine(answer_vec, reference_vec)
            return max(0.0, min(1.0, cos)), f"cosine similarity {cos:.3f} between answer and reference"
        vectors = embedder.embed([reference, *inp.contexts])
        sims = [cosine(vectors[0], v) for v in vectors[1:]]
        best = max(range(len(sims)), key=sims.__getitem__)
```

(`metrics/semantic.py:94-102`.) Cosine similarity lies in [−1, 1]; the score is clipped into [0, 1], and a negative
cosine therefore becomes 0 (the *reason* text keeps the raw value, so nothing is hidden). Context recall takes the maximum
over chunks, which answers "did retrieval bring back text that says what the reference says?" — and is lenient by design:
one good chunk among five is a pass.

### 155.4 What is and is not verified

This is the most important paragraph of the section. **The semantic metrics have been run only against a deterministic
bag-of-words stand-in embedder** (the tests in `tests/test_semantic.py:38-118`: cosine arithmetic, high similarity for
shared words, low for unrelated text, best-chunk selection, the refusal path, a full run through the runner with the
stand-in, and the wiring of the configured model name). **No real model has been downloaded or run in this project, and
`fastembed` is not installed in the development environment.** Consequently:

* The code path that calls `fastembed.TextEmbedding` (`metrics/semantic.py:55-69`) has never executed.
* The 0.7 thresholds are unvalidated starting points. Cosine scales differ between models; a sentence on the right topic
  with the wrong number scores high. The module docstring says as much and points to `ragwb calibrate` against human
  labels as the way to set a threshold.
* No semantic score appears anywhere in this book's measured results, deliberately.

## 156. Accounts and TLS

### 156.1 From one password to named accounts

Release 1.1 offered an optional shared password. It kept strangers out and could not answer two questions that a shared
instance raises immediately: *who started this run?* and *how do I take access away from one person?* Release 1.2 adds
named accounts. It is, in the words of the module docstring, "a small local mechanism, not an identity platform: there
are no roles, no password reset flow, and every signed-in user sees every run" (`rag_workbench/users.py:1-8`; release 1.3 added roles, and release 1.4 updated the docstring to mention them).

Accounts live in one JSON file, `<data dir>/users.json` (`config.py:117-119`). Each entry holds a random 16-byte salt, a
base64 scrypt hash and a creation time; **passwords are never stored**
(`rag_workbench/users.py:91-103`; `test_passwords_are_never_stored`, `tests/test_users.py:34`). The file after `ragwb user add alice`, listing only the
*keys* of each entry, is `{"version": 1, "users": {"alice": ["created", "hash", "salt"]}}`.

| Decision | Choice | Why |
|---|---|---|
| Hash function | `hashlib.scrypt`, `n = 2**14`, `r = 8`, `p = 1`, 32-byte output (`rag_workbench/users.py:30`, `:51-52`) | Memory-hard, in the standard library (no new dependency); 16 MiB of memory per hash (128 × n × r bytes) and, measured on the development machine, about 0.2 s per hash (five hashes timed), which is cheap for a person signing in and expensive for a guessing script |
| Salt | fresh 16 random bytes per password, including on `--replace` (`rag_workbench/users.py:100`) | The same password gets a different hash for every user; `test_same_password_gets_a_different_salt_and_hash` (`tests/test_users.py:41`) |
| Username | 1-32 characters, lowercase letters, digits, `.`, `_`, `-`, starting with a letter or digit (`rag_workbench/users.py:35`, `:43-48`) | Case-insensitive by normalisation; safe to put in a log line and a filename |
| Password length | 10 to 200 characters (`rag_workbench/users.py:33-34`) | A floor against trivial passwords; a ceiling so an attacker cannot make the server hash megabytes |
| Writes | temp file, `chmod 0600` where the platform honours it, `os.replace` (`rag_workbench/users.py:83-89`) | Atomic; a crash cannot leave half a file. On Windows most mode bits are ignored, and the code says so |

### 156.2 Verification that does not leak which users exist

`UserStore.verify` (`rag_workbench/users.py:180-199`) has two properties that are easy to get wrong:

* **Constant-time comparison.** The candidate hash is compared with `hmac.compare_digest`, not `==`.
* **Unknown users cost the same.** If the username does not exist, the function still derives a scrypt hash — against a
  dummy salt (`rag_workbench/users.py:36`) — and compares it with a dummy value, then returns `None`. A password check that
  returned early for unknown names would let an attacker time the responses to learn which usernames are valid.
  `test_oversize_password_is_refused_and_unknown_users_still_pay_for_hashing` (`tests/test_users.py:85`) asserts the
  hashing happens for unknown names.

**A damaged file fails closed.** `has_users` returns `True` when the users file cannot be parsed (`rag_workbench/users.py:76-80`):
a corrupted file must lock the app, not silently open it. `Settings.has_users` and `login_required`
(`config.py:122-130`) build on that, and `test_a_damaged_users_file_locks_rather_than_opens` (`tests/test_users.py:77`)
checks it.

### 156.3 Lockout and sign-in logging

Failed attempts are throttled twice (`ui/auth.py:84-112`): **per username** (5 failures per 60 seconds,
`ui/auth.py:31-32`) and **globally** across all usernames (30 per 60 seconds, `ui/auth.py:41`). The per-name limit
stops one account being guessed at; the loose global limit stops a script that rotates through many names. Two details:

* Names that do not exist get a limiter too, and malformed names share one bucket (`ui/auth.py:162-165`), so a lockout
  looks the same whether or not the account is real — the lockout would otherwise be a second way to enumerate users.
* The table of limiters is bounded (1,000 entries, `ui/auth.py:42`, `:98-99`), so a flood of random usernames cannot grow
  server memory without limit.

The log records what happened, never the secret: `sign-in ok user='alice'`, `sign-in failed user='x'`,
`sign-in refused (throttled)` and `sign-out` (`ui/auth.py:168`, `:175`, `:178`, `:228`). The username is truncated to
40 characters and written with `%r`, which escapes control characters, so a crafted username cannot forge a log line
(`ui/auth.py:128-129`). The password is never passed to a logger.

### 156.4 Who started this run

When someone is signed in, the New evaluation page stamps `started_by` into the run configuration
(`ui/views/new_run.py:208`, from `current_user()`, `ui/auth.py:123-125`); the field is a new optional string on
`RunConfig`, at most 64 characters (`models.py:117`). It therefore appears in the run's Configuration tab and travels in
bundles. The sidebar shows *Signed in as …* and a *Sign out* button (`ui/auth.py:231-243`), and `streamlit_app.py`
calls `require_login` then `render_account` on every page (`streamlit_app.py:20-21`).

**Precedence.** When both accounts and `RAGWB_APP_PASSWORD` are configured, accounts win
(`ui/auth.py:136-139`; `test_account_login_wins_over_the_shared_password`, `tests/test_users.py:191`). Shared-password mode
keeps working exactly as in 1.1 when no account exists, and records no `started_by`.

### 156.5 The CLI

`ragwb user add NAME`, `ragwb user remove NAME` and `ragwb user list` (`cli.py:159-193`; parser `cli.py:549-556`). `add`
prompts for the password twice with `getpass` unless `--password-stdin` is given (which reads one line, for scripts);
`--replace` changes an existing user's password. Run for this chapter: adding `alice` with a 14-character password
succeeded; adding `bob` with a 5-character password was refused with `Passwords must be 10-200 characters`; `list`
printed only `alice`.

### 156.6 TLS: `start.py --ssl-cert/--ssl-key`

Accounts do nothing for a password sent in clear text. `python start.py --ssl-cert cert.pem --ssl-key key.pem` passes
both files to Streamlit's own TLS options (`start.py:162-163`) and serves HTTPS. Three rules in the launcher are worth
reading:

* **Both or neither**, and both must exist: `tls_problem` (`start.py:120-129`) refuses a lone flag or a missing file with a
  message naming the option, before anything is installed or started (`start.py:205-208`;
  `test_tls_options_must_come_as_a_valid_pair`, `tests/test_start.py:59`).
* **No warning is hidden.** On a non-local host without TLS the launcher prints a warning that "sign-in credentials cross
  the network unencrypted" (`start.py:164-166`).
* **The readiness probe skips certificate verification** for its own local server (`start.py:142-143`): a self-signed
  certificate must not make a healthy server look dead. This is safe *only* because the probe talks to the process the
  launcher itself just started, on `localhost`; the comment next to the code says so, and the code that opens a browser
  prints the `https://` URL (`start.py:172-173`).

Exposure rules from 1.1 are unchanged, with one extension: `host_problem` now accepts either the shared password **or**
accounts as "a login" (`start.py:112-118`), and the refusal message mentions `ragwb user add`
(`test_exposed_host_message_mentions_accounts`, `tests/test_start.py:69`). `accounts_configured` reads the users file in
the data directory (`start.py:98-109`).

**Measured.** TLS was checked end to end: a throwaway self-signed certificate was generated with `openssl`, and
`python start.py --ssl-cert ... --ssl-key ... --no-browser --no-examples` was started. The HTTPS health endpoint answered
200, a plain-HTTP request to the same port was refused, and the launcher printed the `https://` URL. The certificate was
self-signed and discarded; a certificate from a real authority, a proxy in front, or any cipher or protocol-version
policy were not examined.

### 156.7 A gap found while writing this chapter, and its fix

The first version of `start.py:accounts_configured` decided that accounts exist from the *size* of the users file:
present and larger than two bytes. After the **last** user was removed, `ragwb user remove` rewrote the file as
`{"version": 1, "users": {}}`, which is larger than two bytes. Checked against a data directory in exactly that state, the
launcher said accounts existed (`accounts_configured` returned True and `host_problem('0.0.0.0', ...)` returned None)
while the app itself had no login (`settings.login_required` was False). So after creating and then removing every
account, with no shared password set, `python start.py --host 0.0.0.0` was accepted with **no login at all**. The unit test
covered an empty object (`{}`) and a one-user file, not an empty `users` mapping.

The review that found it was the book-writing pass, not a test. It was fixed in two places, each with a test:

* `start.accounts_configured` now parses the file and returns true only if the `users` mapping is non-empty; a file it cannot
  parse counts as "accounts exist", so a damaged file locks the app rather than opening it (`tests/test_start.py`,
  `test_accounts_are_detected_from_the_users_file`, which now covers an empty mapping and a broken file).
* `UserStore.remove` deletes the file when the last account is removed, so nothing is left half-configured
  (`tests/test_users.py`, `test_remove_and_list`).

### 156.8 Honest limits

* **No roles (added in release 1.3, Part XV §165), no reset, no per-user separation of runs.** Every signed-in user sees and can delete every run
  (`docs/KNOWN_LIMITATIONS.md`).
* **Removing a user does not end an existing session** (true at release 1.2; release 1.3 ends it on the next page load, Part XV §165.3). `ragwb user remove` said so in its output; the session lived in
  Streamlit's server-side state until sign-out or restart.
* **Attribution is not inherited by re-runs.** `maintenance.rerun_config` clears `started_by`, so a run repeated from the
  command line is not stamped with the original starter's name (`tests/test_users.py`, `test_rerun_does_not_inherit_the_original_starter`).
* **The Docker `CMD` accepts either login.** It refuses to start unless `RAGWB_APP_PASSWORD` is set or `/app/data/users.json`
  exists (`Dockerfile:29`); the image itself was never built.
* **Brute-force protection is in-process memory.** Throttle state lives in the Streamlit server and resets on restart;
  there is no rate limiting at the network layer.
* TLS protects the connection, not the data at rest: `runs.db` and `users.json` are ordinary files.

## 157. Packaging: running from somewhere other than a checkout

### 157.1 The problem

Until 1.2 the data folder was derived from the source location (`src/rag_workbench/config.py` → two levels up). From a
checkout that is exactly right; from an installed wheel it would have meant writing `data/` *inside `site-packages`*.
`docs/KNOWN_LIMITATIONS.md` in release 1.1 said as much ("meant to be used from this project, not installed as a
standalone wheel").

### 157.2 Where the project root comes from now

`_find_project_root` (`config.py:21-34`) tries three things in order:

1. `RAGWB_HOME`, if set (`config.py:30-32`): an explicit choice always wins.
2. The checkout this file lives in — two directories up, **recognised by its `pyproject.toml`** (`config.py:33-34`). The
   marker is the point: a directory two levels up from a file in `site-packages` has no `pyproject.toml`.
3. Otherwise the current working directory.

`PROJECT_ROOT` is computed once at import (`config.py:37`) and everything that used to be relative to the source tree —
`data/`, `.env`, the default dataset and document — follows it. The example files are located by a second rule
(`config.py:38-40`): `examples/` under the root if it exists (or if no packaged copy does), otherwise the copy bundled in
the package, `rag_workbench/_examples`.

The tests (`tests/test_packaging.py:7-36`) cover each rule: a checkout is recognised by its `pyproject.toml`; `RAGWB_HOME`
overrides it; with no checkout the current directory is used (the test fakes a `config.py` location with no
`pyproject.toml` two levels up); the wheel's `force-include` table maps `examples` to `rag_workbench/_examples`; and the
default example paths resolve to real files.

### 157.3 The wheel

`pyproject.toml:42-43` adds `[tool.hatch.build.targets.wheel.force-include]` mapping `examples` to
`rag_workbench/_examples`, so a wheel carries the bundled documents and datasets and `ragwb run` works with no arguments
after installation. Built for this release with `uv build --wheel --offline`, the artefact is
`rag_evaluation_workbench-1.2.0-py3-none-any.whl`, 60 files, with the examples under `rag_workbench/_examples`.

**What was actually tested.** The wheel was *unpacked* and run from a neutral folder with the project's own virtual
environment (which already has the dependencies). It reported the project root as that neutral folder, the examples as
the *packaged* copy, and `ragwb run` completed and wrote `./data` there — so the logic that matters (no write into the
package, examples found) holds. **A true `pip install` into a fresh environment was not tested**, because the dependencies
could not be fetched offline. Treat the wheel as "unpacked-and-run verified", not "install verified".

### 157.4 The Dockerfile

A `Dockerfile` and `.dockerignore` were added at the repository root. The image is `python:3.12-slim` with `uv`;
it copies the project files, runs `uv sync --frozen --no-dev` (`Dockerfile:10-22`), declares `/app/data` a volume and
exposes 8501 (`Dockerfile:24-25`). Its start command refuses to run unless `RAGWB_APP_PASSWORD` is set or a users file exists, because inside a
container the app listens on every interface (`Dockerfile:26-29`); keys are passed at run time with `-e`, never baked
into the image. `.dockerignore` keeps the virtual environment, data, `.env`, caches and tests out of the build context.

**The image has not been built or run.** No Docker was available in the environment; the file's own first comment says
so, and `docs/KNOWN_LIMITATIONS.md` repeats it. It also has no TLS (put a TLS-terminating proxy in front), and it does
not pre-create the example runs.

### 157.5 Using it

```bash
RAGWB_HOME=/srv/ragwb ragwb run --name first        # data under /srv/ragwb/data, examples from the package
ragwb doctor                                        # lists the data directory it resolved and the store schema
```

**Limits.** `RAGWB_HOME` is read at import time, so it must be set in the environment (or a shell) before the process
starts — a `.env` file cannot change it, because the `.env` file is itself located *relative to* the root.

## 158. Accessibility: a scripted check, two fixes, and what is left

### 158.1 What was measured

Until now the books said "no formal accessibility audit". Release 1.2 replaces that with something narrower and real: a
script was run in the browser pane over **five pages** (Overview, New evaluation, Run results, Compare runs, Settings
& metrics). It checked heading structure, accessible names of buttons, links and inputs, image alternatives, and text
contrast. It found two defects in this project's own code and some issues that belong to Streamlit.

| Finding | Status |
|---|---|
| **Heading levels skipped** (an `h1` page title followed directly by `h3` section titles, because the pages used `st.subheader`) | Fixed |
| **Muted text at 4.42:1** (below the 4.5:1 WCAG AA minimum for normal text) | Fixed |
| Streamlit draws data tables on a `<canvas>`, which screen readers cannot read | Not fixable here; every table has a CSV download as an alternative |
| The built-in JSON viewer uses syntax colours below 4.5:1 | Not fixable here |
| White-on-blue slider values flagged at 1.0:1 | Probably a false positive of the script (the text sits above the thumb, not on it); **not confirmed** |

### 158.2 The two fixes

**Headings.** Every section heading in the page scripts is now `st.header` (Streamlit renders it as an `h2`) instead of
`st.subheader` (`h3`) — for example `ui/views/overview.py:38`, `:68`, `ui/views/new_run.py:36`, `:98`, `:129`, `:173`,
`ui/views/compare.py:30`, `:56`, `:86`, `ui/views/settings.py:17`, `:29`, `:39`, `:53`. The page title stays the single `h1`,
so the outline has no skipped level. That would have made the headings visibly larger, so one CSS rule restores the old
size: `div[data-testid="stHeading"] h2 {font-size: 1.6rem; padding-top: 0.6rem;}`
(`ui/components.py:27-28`). This is the "section headings are bigger h2 headings" change visible in the recaptured
screenshots of this book. `test_data_and_settings_pages` was changed to look for the headings in `at.header` rather than
`at.subheader` (`tests/test_ui.py:164`).

**Contrast.** The muted-text class used a fixed grey that measured 4.42:1. A single fixed grey cannot pass in both
themes, so `.eval-muted` now uses `opacity: 0.75` on the **theme's own text colour** (`ui/components.py:24-26`): it
inherits whatever the theme calls text and dims it. The computed contrast is about 5.7:1 on the light theme and 10:1 on
the dark one. These are computed ratios, not measurements from a rendering engine.

### 158.3 What the check does not cover

Say it plainly: **keyboard-only operation, screen-reader announcement order, and zoom/reflow were not tested.** An
automated script finds a class of defects (structure, names, contrast); it cannot tell whether the page is *usable* by
someone who relies on a keyboard or a screen reader. A fuller audit with real assistive technology is item 8 of the
future-work list (`docs/KNOWN_LIMITATIONS.md`). Until it is done, do not describe the interface as "accessible"; describe
it as "checked for a defined set of automated issues, two of which were fixed".

## 159. Reference, verification, and what is still unverified

### 159.1 New commands, options, variables and files

| Item | Purpose | Where |
|---|---|---|
| `ragwb tag RUN [--add] [--remove]` | edit run tags | `cli.py:115-121`, §152.3 |
| `ragwb note RUN [TEXT] [--clear]` | set or clear the run note | `cli.py:221-228`, §152.3 |
| `ragwb list [--search WORD...] [--tag T] [--status S]` (changed) | filtered list with a `tags` column | `cli.py:99-112`, `:442-446` |
| `ragwb regress BASE CAND [--max-drop 0.02] [--min-pairs 10] [--max-error-increase 0.05] [--metrics A,B]` | regression gate; exit 0 / 3 / 4 | `cli.py:138-147`, `:458-465`, §153 |
| `ragwb tune-abstention [--dataset ...] [--document ...]` | held-out tuning of `min_evidence` | `cli.py:124-135`, `:485-488`, §154 |
| `ragwb user add\|remove\|list NAME [--replace] [--password-stdin]` | named accounts | `cli.py:159-193`, `:469-476`, §156 |
| `python start.py --ssl-cert F --ssl-key F` | serve over HTTPS | `start.py:198-199`, §156.6 |
| `RAGWB_HOME` | explicit project root (data, `.env`) | `config.py:30-32`, §157.2 |
| `RAGWB_LOCAL_EMBEDDING_MODEL` | local model for the semantic metrics (default `BAAI/bge-small-en-v1.5`) | `config.py:72`, `:180`, §155 |
| Metrics `semantic_similarity`, `semantic_context_recall` | optional, need `fastembed` | `metrics/semantic.py:107-116`, §155 |
| `<data dir>/users.json` | account store (salt, scrypt hash, creation time) | `config.py:117-119`, §156.1 |
| Run field `started_by`; run field `tags`; DB column `tags_json`; schema 3 | attribution; organisation | `models.py:117`, `:197`; `storage.py:26`, `:46` |

The CLI now has **22 commands**: the 17 of release 1.1 plus `tag`, `note`, `regress`, `tune-abstention` and `user`
(parser definitions `cli.py:478-617`). The new source files are:

| File | Lines | Role |
|---|---:|---|
| `src/rag_workbench/history.py` | 80 | tag and note rules, run search |
| `src/rag_workbench/regression.py` | 107 | regression gate |
| `src/rag_workbench/abstention.py` | 177 | held-out threshold tuning |
| `src/rag_workbench/users.py` | 128 | account store |
| `src/rag_workbench/metrics/semantic.py` | 121 | semantic metrics |
| `Dockerfile`, `.dockerignore` | — | container recipe (never built) |
| `examples/documents/{volcanoes,coffee,lighthouses}.{md,pdf}`, `examples/datasets/{volcanoes,coffee,lighthouses}.jsonl` | — | the added corpus |
| `tests/test_history.py`, `test_regression.py`, `test_abstention.py`, `test_semantic.py`, `test_users.py`, `test_packaging.py`, `test_example_corpus.py` | — | 78 new tests across all new test files |

### 159.2 Verification

`docs/TESTING.md` records the verified state of the final tree: **332 tests collected, 331 passed, 1 skipped** (the
opt-in live test); statement coverage **96 %** (3,124 statements, 116 missed; §97.2 of Part IX shows an earlier run of the same suite); `ruff` and `mypy` clean over 44 source
files. The six steps of `scripts/verify.py` are unchanged. The default-behaviour claim in the introduction was checked by
re-scoring the five example runs under both versions: 86 cases, 0 differences.

### 159.3 What is still unverified

These are the items that no amount of offline testing closed at release 1.2 (Part XV §167 gives the list after release 1.3). They are the same list as `CHANGELOG.md` ("Not verified")
and `docs/KNOWN_LIMITATIONS.md`.

1. **Any live OpenAI, Grok or DeepEval call.** The generator, agent, embedding retriever, hybrid retriever and four judge
   metrics were tested with fakes only at release 1.2. `scripts/live_smoke.py` existed and had never been run with a key (release 1.3 ran it against Groq's free tier; OpenAI itself is still untested, Part XV §160, §167).
2. **The semantic metrics with a real model.** At release 1.2: tested with a stand-in embedder only (run with a real model in release 1.3, Part XV §162.6, where the 0.7 default is found uncalibrated); `fastembed` was not installed; the 0.7
   thresholds are unvalidated (§155.4).
3. **The Dockerfile.** Not built (no Docker here).
4. **A true wheel install.** The unpacked wheel was run; `pip install` into a clean environment was not (§157.3).
5. **Judge-versus-human calibration on real labels.** The tooling is tested on synthetic labels only.
6. **Accessibility beyond the scripted check:** keyboard-only use, screen-reader announcements, zoom and reflow
   (§158.3), and the slider-contrast flag.
7. **TLS beyond a self-signed local certificate** (§156.6).

### 159.4 Other changes, and how to read a 1.2 result

* **Section headings are level-2** and the Overview table has a `tags` column (cosmetic; §152.4, §158.2). The UI helper
  `st.subheader` is no longer used by the page scripts.
* **The version** recorded in a run's environment block is now `1.2.0` (`src/rag_workbench/__init__.py:13`).
* **`ragwb list` output** gained the `tags` column; a script that parses the old table by position needs updating.

**A checklist for trusting a 1.2 result.**

1. Everything in the 1.1 checklist (Part XIII §149) still applies.
2. A claim that a change "did not make things worse" rests on a `ragwb regress` result that was **judged** (exit 0 with at
   least one non-`insufficient` metric) — not on exit 0 alone, and not on exit 4.
3. A `possible` verdict is read as "not settled", and the pair count and interval width are read before the verdict.
4. A threshold chosen on data is reported on data it was not chosen on, and the size of that second sample is stated.
5. Semantic scores are not trusted until a threshold has been calibrated against human labels for *that* model.
6. In a multi-user instance, `started_by` is attribution, not security: see §156.8 for who can still do what.
7. TLS is on whenever a login is used across a network, and the launcher's refusal messages are heeded rather than
   worked around.
