# Part II — Preparing documents and datasets

An evaluation can only be as good as its inputs. The pipeline, the metrics and the statistics are the easy part: they are code, and they behave the same every time. The hard part is the **document** (is it split into chunks that a retriever can use?) and the **dataset** (do the questions and reference answers measure what you care about?). This Part teaches you to prepare both, using the bundled examples and a small worked example that you build yourself from nothing.

Everything in this Part was run offline on version 1.4.1 in a scratch data directory. Where output is quoted it is real, shortened only for width. Where a number is a worked example of arithmetic rather than a measurement, it says "illustrative".

---

## 2.1 Supported documents

The workbench evaluates one document per run.

| Type | Extension | How it is read | Notes |
|---|---|---|---|
| PDF | `.pdf` | PyMuPDF text blocks, per page, sorted top to bottom then left to right | Needs a text layer. A scanned image has none. |
| Plain text | `.txt` | split on blank lines | Must be valid UTF-8. |
| Markdown | `.md` | split on blank lines; a leading `#` to `######` heading marker is removed, other Markdown is **not** interpreted | lists, tables, emphasis and links stay as plain text (§2.2.3). |

Anything else is refused with a clear message:

```text
error: Unsupported document type '.docx'; use one of ['.md', '.pdf', '.txt']
error: No extractable text found in empty.md
error: Document not found: <path>\nothere.pdf
```

Limits, all configurable by environment variable:

| Limit | Default | Setting |
|---|---|---|
| document file size | 25 MB | `RAGWB_MAX_DOCUMENT_BYTES` |
| characters per chunk | 2,000 | fixed in code (`DEFAULT_MAX_CHUNK_CHARS`) |
| dataset file size | 5 MB | `RAGWB_MAX_DATASET_BYTES` |
| cases per dataset | 5,000 | `RAGWB_MAX_CASES` |
| characters per question or reference | 20,000 | `RAGWB_MAX_FIELD_CHARS` |

A document you want to evaluate in Word format or HTML must be converted first (to PDF with a text layer, or to Markdown or text). The conversion is part of your evaluation design: a bad conversion changes what the retriever sees.

> **Why this works.** The same content in `.md` and `.pdf` form produces the same *paragraph* chunks (§2.2.1), but different *files*, so the two runs carry different document hashes and are not strictly comparable as a controlled pair. In the guide's test, the honeybee Markdown and PDF gave identical scores (token F1 0.346, context recall 0.885) because the paragraph text is identical and the title chunk reads the same in both (since release 1.4.1 the `#` marker of a Markdown heading is removed from the chunk text). Do not rely on that for your own documents: a real PDF conversion usually differs in more ways. If you compare formats, compare them as two documents.

---

## 2.2 How chunking works in practice

A **chunk** is the unit the retriever ranks and the generator reads. The workbench makes chunks by simple, predictable rules, which is both a strength (you can reason about them) and a limit (it does not understand layout).

### 2.2.1 The rules

1. **Text and Markdown**: the file is split on blank lines (a blank line is two newline characters). Each paragraph, with its internal line breaks collapsed into single spaces, becomes one chunk.
2. **PDF**: each page's text blocks, as reported by the PDF library, are collected, sorted by vertical then horizontal position, and each non-empty block becomes one chunk. For an ordinary single-column PDF a block is a paragraph.
3. **Long blocks** are split. Any chunk longer than 2,000 characters is cut at sentence boundaries into pieces no longer than 2,000 characters; a single "sentence" longer than that is hard-cut.
4. **Ids** are `p{page}-b{n}`: page number and the block's order on that page. Text and Markdown files are always "page 1".
5. **Nothing is removed** by default. Headings, bullet lists, table rows and captions all become chunks or parts of chunks.

You can see every chunk of any document on the **Datasets & retrieval** page, Document chunks tab, before you run anything. Do this every time you use a new document.

### 2.2.2 What the bundled honeybee document looks like

The honeybee document has a one-line title and ten paragraphs. Loaded with the workbench's own loader:

```text
honeybees.md 11 chunks; after dropping headings: 10
  p1-b1   page=1 len=  33 heading=True  'Honeybees: Life Inside the Colony'
  p1-b2   page=1 len= 381 heading=False 'Honeybees are social insects that live in colonies of tens o'
  p1-b3   page=1 len= 302 heading=False 'The queen is the only fully fertile female in the colony. Af'
  ...
  p1-b11  page=1 len= 305 heading=False 'Honeybees are important pollinators of many fruit, nut and s'
honeybees.pdf 11 chunks; after dropping headings: 10
  p1-b1   page=1 len=  33 heading=True  'Honeybees: Life Inside the Colony'
  ...
  p1-b10  page=1 len= 329 heading=False 'A colony reproduces by swarming. When a colony grows crowded'
  p2-b1   page=2 len= 305 heading=False 'Honeybees are important pollinators of many fruit, nut and s'
```

Three observations:

* The Markdown and PDF titles are the same 33 characters. The loader removes the `# ` marker from a Markdown heading (it is markup, not text), so the title chunk carries only the words. Other Markdown is not rendered (§2.2.3).
* In the PDF, the last paragraph falls on page 2, so its id is `p2-b1` and the chunk ids are not simply consecutive. Chunk ids are stable for a given file, which is why you can refer to them in notes.
* The title is chunk 1 in both. With `-k 3`, that title chunk can occupy one of the three retrieval slots even though it contains no information. This is the "title chunk" effect that recurs through the guide.

The other three bundled documents (coffee, volcanoes, lighthouses) each produce 15 chunks, on two PDF pages.

### 2.2.3 Headings, lists and tables

The loader treats Markdown as text with one exception: a heading marker (`#` to `######` followed by a space) at the start of a block is removed, and the words are kept. Everything else (lists, emphasis, links, tables) is not interpreted and stays as written. A `.txt` file is never touched this way.

Here is a deliberately awkward Markdown file, `edge.md`:

```text
  # Edge case document

## Section heading

First paragraph with a soft
line break inside it.
Still the same paragraph.
- bullet one
- bullet two

| Zone | Covered |
|---|---|
| Splash | rarely |
| Low | almost always |

Short unpunctuated line

Final paragraph ends here.
```

and what the loader makes of it:

```text
edge.md 6 chunks; after dropping headings: 3
  p1-b1   len=  18 heading=True   'Edge case document'
  p1-b2   len=  15 heading=True   'Section heading'
  p1-b3   len= 101 heading=False  'First paragraph with a soft line break inside it. Still the ...'
  p1-b4   len=  72 heading=False  '| Zone | Covered | |---|---| | Splash | rarely | | Low | alm'
  p1-b5   len=  23 heading=True   'Short unpunctuated line'
  p1-b6   len=  26 heading=False  'Final paragraph ends here.'
```

What to learn from it:

| Input | Result | Consequence |
|---|---|---|
| soft line breaks inside a paragraph | joined into one chunk | hard-wrapped text is fine, as long as paragraphs are separated by blank lines |
| a bullet list right after a paragraph, with no blank line | merged into the paragraph's chunk | put a blank line before a list if you want it to be its own chunk |
| a Markdown table | one chunk of pipe-separated text | numbers in a table lose their row and column labels once flattened |
| `#` to `######` marker at the start of a block (`.md` only) | removed; the words stay | the heading chunk is clean text and an answer that includes it no longer shows a `#`. A `.txt` file keeps the marker, because plain text has no markup |
| bullets, table pipes, `**emphasis**`, `[links](url)` | kept exactly as written | only the heading marker is treated as markup; nothing else is interpreted, so a table is flattened text |
| a short line without final punctuation | treated as a heading | it may be a real, short fact (a caption, a list label) |

### 2.2.4 `--skip-headings`

`ragwb run --skip-headings` (in the web app: the checkbox "Skip heading-like blocks (e.g. the document title)" in the Advanced expander of New evaluation) drops chunks that look like headings before the index is built. The heuristic is simple: a chunk of **12 words or fewer that does not end in `.`, `!`, `?`, `:`, `;`, a quote or `)`**. If *every* chunk looks like a heading, all chunks are kept.

On the honeybee document it removes exactly the title (11 chunks become 10). On `edge.md` it removes three chunks (6 become 3): the two headings and the short unpunctuated line. The third was not a heading, which shows the cost of the heuristic: it can drop a real short chunk. That is why it is **off by default**: runs stay comparable with earlier runs and nothing is lost silently.

When to use it:

| Situation | Advice |
|---|---|
| The document has a title and section headings, and the retriever puts them in the top *k* | turn it on, and re-check the Document chunks tab for casualties |
| The document has short real facts without punctuation (glossary terms, list labels, captions) | leave it off, or clean the document first |
| You are comparing runs against earlier runs | keep it the same in both, or compare it deliberately as the one changed setting |

The effect is measurable, and smaller than you might expect. The tour in Part I §1.8 changed two settings at once (k and headings). To isolate the headings, run two runs that differ only in that flag and compare them:

```bash
ragwb run --name hb-k3 -k 3 --quiet
ragwb run --name hb-k3-skip -k 3 --skip-headings --quiet
ragwb compare <hb-k3-id> <hb-k3-skip-id>
```

```text
                   label  paired_cases  mean_a  mean_b  diff_b_minus_a  ci_low  ci_high  b_better  ties  b_worse  ci_excludes_zero
                Token F1            20   0.346   0.334          -0.013  -0.033    0.000         0    17        3             False
                 ROUGE-L            20   0.317   0.305          -0.012  -0.024    0.000         0    17        3             False
Context recall (lexical)            20   0.885   0.885           0.000   0.000    0.000         0    20        0             False
  Groundedness (lexical)            20   1.000   1.000           0.000   0.000    0.000         0    20        0             False
```

Dropping the title changed three answers and made none better; token F1 fell by 0.013 (inconclusive) and context recall did not move at all. The tour's gain of 0.060 therefore came almost entirely from lowering *k* from 3 to 1, not from skipping the title. Why would removing a useless chunk not help? At k = 3 the freed slot is simply filled by the next-best paragraph, and the extractive generator, which picks the best sentences across all retrieved chunks, can then pick a sentence from that extra paragraph instead. The title chunk is not always the problem it looks like in a single case (Part I §1.7.3 shows the one where it was).

> **Why this works.** This is the reason to change one setting per run. Had you only compared the tour's two runs, you would have concluded that skipping headings plus k = 1 helps and not known which half mattered. Keeping everything else equal is the whole point of paired comparison (Part IV §4.3).

### 2.2.5 Long blocks

Here is a text file of 30 sentences in one paragraph (1,550 characters). With the default limit of 2,000 characters it is one chunk. With a limit of 300 characters (a programming-level option, not exposed on the command line), it splits into six chunks of 254 to 259 characters, each starting at a sentence boundary:

```text
long.txt 6 chunks (max 300)  p1-b1 len=254  p1-b2 len=255 ... p1-b6 len=259
long.txt 1 chunk  (default)  p1-b1 len=1550
```

Chunk size is not a command-line setting in this release. If you want smaller chunks, make smaller paragraphs in the document: blank lines are your chunking control.

### 2.2.6 What chunk granularity means for retrieval

Paragraph chunks are coarse. A 300-character paragraph about several things will be retrieved if any of them matches, and the extractive generator then has to pick sentences from it. That has predictable effects:

* **A question's answer is usually in one paragraph**, so *k = 1* often suffices when the retriever ranks well, and larger *k* adds noise (§2.9, Part III §3.3).
* **A paragraph that covers three facts** can answer three questions, and a single bad ranking can lose all three. Datasets built from such paragraphs are correlated: three questions are not three independent samples (§2.9).
* **Paragraphs that are too long** (near 2,000 characters) dilute the keyword signal in BM25 (long chunks get length-normalised) and give a generator more irrelevant text.

> **Pitfall.** Do not judge a chunker by how it looks in a text editor. Judge it by the Document chunks tab and by running the Retrieval playground on five of your own questions. If the answer to a question is split across two chunks, no *k* will fix that: restructure the document or the question.

---

## 2.3 What makes a document easy or hard

| Property | Effect | What to do |
|---|---|---|
| **Short, single-column prose with blank-line paragraphs** | easy: one block per paragraph; the bundled examples are all like this | nothing |
| **Scanned PDF (page images, no text layer)** | no text is extracted, so the run is refused: "No extractable text found" | run OCR first and evaluate the OCR output, as a different document |
| **Multi-column PDF** | the library's blocks are sorted by vertical position then left to right, so two-column text can interleave lines from the two columns | check the Document chunks tab; if interleaved, convert to text with a column-aware tool |
| **Tables** | cells become run-on text, losing column headers | write the table as sentences in the source, or accept that table questions are hard |
| **Headers, footers and page numbers** | each becomes its own short chunk on every page | clean the source, or use `--skip-headings` and verify |
| **Very long paragraphs** (over 2,000 characters) | split at sentence boundaries, which may separate a fact from its context | add paragraph breaks in the source |
| **Hard-wrapped text without blank lines between paragraphs** | the whole text becomes one huge paragraph, split only at 2,000 characters | insert blank lines between paragraphs |
| **Very large documents** | no problem for the workbench: it is fast | see below |
| **Non-UTF-8 text** | refused: "is not valid UTF-8 text" | re-save as UTF-8 |

### 2.3.1 How large can a document be?

The workbench is not the bottleneck. The document benchmark in `docs/OPERATIONS.md` §7 reports, on one laptop: **5,000 chunks index in about 0.3 s and answer a query in about 3 ms (p95 under 4 ms)**, and a **200-page PDF (1,600 chunks) loads in 0.2 s** and answers in under 1 ms. (These were re-measured in release 1.4 after an earlier benchmark that ran under a memory tracer had inflated times.) The input ceiling is the 25 MB file-size default. So size is not what makes a document hard.

What makes a large document hard is evaluation design: with 1,600 chunks and *k = 3*, retrieval has to find the right three among 1,600, a much harder task than among 11. Your questions must cover the document's breadth (§2.5.2), and your dataset needs to be larger to say anything about it (§2.9).

### 2.3.2 Diagnosing a hard document

Before you write a single question, do this for any new document (five minutes):

1. Open **Datasets & retrieval**, Document chunks tab. Scroll all the chunks. Do they look like what a human would call paragraphs?
2. Note the count and the shortest and longest chunks. Chunks under 30 characters are usually headings, page numbers or stray labels.
3. Open the Retrieval playground. Type two real questions and check that the right paragraph is rank 1.
4. Decide whether to clean the source, convert it, or turn on `--skip-headings`.

If you skip this step, a poor chunking will look like a poor retriever or a poor generator, and you will spend days tuning the wrong stage.

---

## 2.4 Dataset formats

A dataset is a list of **cases**. A case is a question, usually a reference answer, and optional metadata.

### 2.4.1 JSONL

One JSON object per line. Blank lines are ignored.

```json
{"id": "t01", "question": "What is a tide pool?", "expected_answer": "A small basin of seawater that stays behind on a rocky shore after the tide goes out.", "metadata": {"type": "factual", "difficulty": "easy", "topic": "definition"}}
```

| Field | Required | Meaning |
|---|---|---|
| `question` | **yes** | non-empty string |
| `expected_answer` | no | the reference answer (a string). Without it, reference-based metrics are skipped for that case. |
| `id` | no | string or integer, unique. If omitted, the case gets `case-001`, `case-002`, ... by position. |
| `metadata` | no | a JSON **object** of your own fields, used for slicing |

Other keys are ignored with a warning ("ignored unknown field(s): answer").

### 2.4.2 CSV

A header row that includes `question`. The columns `id` and `expected_answer` are optional. **Every other column becomes metadata** (empty cells are dropped):

```text
id,question,expected_answer,topic
p1,What tells other bees how far away the food is?,The length of the waggle run shows the distance to the food.,communication
p2,Why do bees fan nectar with their wings?,Fanning evaporates water so the nectar thickens into honey.,honey
```

CSV is convenient for spreadsheets. Remember to quote fields that contain commas, and save as UTF-8 (a leading byte-order mark is accepted). JSONL is safer for long answers and nested metadata.

### 2.4.3 Validation, with line numbers

`ragwb validate` (and the dataset check on the New evaluation and Datasets pages) never silently drops a row. Every problem is reported with its line number. **Errors** make the dataset unusable; **warnings** do not.

Here is a deliberately broken file, `bad.jsonl`:

```text
{"id": "b1", "question": "What is a tide pool?", "expected_answer": "A basin of seawater."}
{"id": "b2", "question": "Why do mussels spread?", "expected_answer": "No sea stars.", "metadata": {"type": "why"}
{"id": "b1", "question": "What is a sea star?", "expected_answer": "An echinoderm."}
["not", "an", "object"]
{"id": "b4", "question": "", "expected_answer": "Empty question."}
{"id": "b5", "question": "What is a tide pool?", "expected_answer": 42}
{"id": "b6", "question": "How do anemones feed?", "expected_answer": "They sting prey.", "metadata": "hard"}
{"id": "b7", "question": "What do barnacles do?", "answer": "They glue down."}
```

```bash
ragwb validate bad.jsonl
```

```text
bad.jsonl: 2 cases, 1 with reference answers
  ERROR   line 2: invalid JSON (Expecting ',' delimiter at column 115)
  ERROR   line 4: expected a JSON object, got list
  ERROR   line 3: duplicate id 'b1' (first seen on line 1)
  ERROR   line 5: missing or empty 'question'
  ERROR   line 6: 'expected_answer' must be a string
  ERROR   line 7: 'metadata' must be a JSON object
  warning line 8: ignored unknown field(s): answer
  warning 1 case(s) have no expected_answer; reference-based metrics will be skipped for them
INVALID
```

The exit code is 1. Notes on reading it:

* The errors are listed with the JSON-syntax problems first (lines 2 and 4), then the row-level ones; so the line numbers are not in ascending order. Fix them all.
* Line 2 is missing its closing brace (the column number points at where parsing failed, not necessarily at the typo).
* The first line says "2 cases", which counts only the rows that parsed into cases; do not read it as the number you intended.
* Line 8 is a warning: the reference key is `answer`, which is not a recognised field, so the case would have no reference. That is a silent-failure trap that the warning catches. Always read warnings.
* If you pass the invalid file to `ragwb run`, the run is refused before anything executes:

```text
error: Dataset 'bad.jsonl' is invalid: line 2: invalid JSON (...); line 4: expected a JSON object, got list; line 3: duplicate id 'b1' (first seen on line 1); line 5: missing or empty 'question'; line 6: 'expected_answer' must be a string (+1 more)
```

CSV-specific cases:

```text
warn.csv: 3 cases, 2 with reference answers
  warning line 4: duplicate question (also on line 2)
  warning 1 case(s) have no expected_answer; reference-based metrics will be skipped for them
valid
```

and a CSV without a `question` header:

```text
nohdr.csv: 0 cases, 0 with reference answers
  ERROR   line 1: CSV header must include a 'question' column
INVALID
```

Other file-level errors: `file not found`, `unsupported file type '.md'; use .jsonl or .csv`, "file is not valid UTF-8", "dataset exceeds the limit of 5,000 cases".

### 2.4.4 `validate` on the bundled sets

```text
honeybees.jsonl: 20 cases, 20 with reference answers            valid
volcanoes.jsonl: 30 cases, 30 with reference answers            valid
honeybees_paraphrased.csv: 5 cases, 5 with reference answers    valid
honeybees_unanswerable.jsonl: 6 cases, 6 with reference answers valid
```

Make `ragwb validate` a habit after every edit, and put it in your CI if the dataset lives in version control (Part VII).

> **Pitfall.** A *valid* dataset is not a *good* dataset. Validation checks syntax, ids, types and duplicates. It does not check that the reference is right, that the question is answerable from the document, or that the dataset is balanced. The rest of this Part is about those.

---

## 2.5 How to write good questions

### 2.5.1 Start from your users, not from the document

The most common failure is writing questions by reading a paragraph and turning it into a question using its own words. The questions then share their words with the answer, a keyword retriever finds them trivially, and the evaluation reports high scores that do not predict real use.

Instead, in order of preference:

1. **Real questions**: from logs, support tickets, a search box, interviews. Keep their phrasing, including typos and vagueness if your users have them.
2. **Questions by someone who has not read the document closely**: ask a colleague to write ten questions about the topic, then check which the document can answer.
3. **Questions you write after reading, paraphrased on purpose**: the "paraphrase style" below.

### 2.5.2 Coverage

Aim to cover the document, not just its first page. A practical method:

1. List the document's paragraphs (the Document chunks tab gives you the list).
2. Make sure **every paragraph is the source of at least one question**, and no paragraph is the source of more than three or four.
3. Record the source chunk id in the case's metadata (`"source": "p1-b6"`), so you can later ask "which paragraphs fail?" with `ragwb slices --by source`.

The bundled datasets follow this: the 20-question honeybee set has two questions on several paragraphs (queen, drones, waggle dance) and one or two on the others; the document has ten content paragraphs.

### 2.5.3 Difficulty mix

A set of only easy questions tells you nothing about hard ones and makes every pipeline look good. The bundled 30-question sets use a mix:

| Dataset | easy | medium | hard |
|---|---:|---:|---:|
| volcanoes (30) | 6 | 18 | 6 |
| coffee (30) | 6 | 19 | 5 |
| lighthouses (30) | 6 | 16 | 8 |

Define "hard" concretely in your own dataset. Useful definitions for a retrieval pipeline:

* **easy**: the question shares several words with the answer paragraph; one sentence answers it.
* **medium**: the question uses some of the paragraph's words and some synonyms; the answer needs one sentence or two.
* **hard**: the question is phrased with different vocabulary, or the answer needs facts from two sentences, or it requires a small inference ("which island lies over the hotspot?" → "the youngest").

### 2.5.4 Paraphrase style

For each question, ask: *if a user did not know the document's exact words, how would they ask?* The honeybee set has a paraphrased companion, `honeybees_paraphrased.csv`:

| Original style (honeybees.jsonl) | Paraphrased style (honeybees_paraphrased.csv) |
|---|---|
| "How do honeybees tell each other where food is?" | "What tells other bees how far away the food is?" |
| "How is nectar turned into honey?" | "Why do bees fan nectar with their wings?" |

On the offline baseline (k = 3): original set token F1 0.346 and context recall 0.885; paraphrased set (5 questions) token F1 0.225 and context recall 0.664. This is a **different, much smaller dataset**, so treat the gap as an illustration, not a measurement. The live record's embeddings table (run 9) gives a better controlled picture: on the paraphrased questions, a local embedding retriever raised context recall from 0.664 (BM25) to 0.786, while on the main honeybee set it lowered it from 0.885 to 0.792. Paraphrase is exactly where retriever differences show up, and only a dataset with paraphrased questions can reveal them.

> **Why this works.** A keyword retriever and an embedding retriever are indistinguishable on questions that copy the document's words. Evaluating retrievers requires questions that do not. If you are choosing between retrievers (Part III §3.2), at least a third of your questions should be paraphrased.

### 2.5.5 Question types

Use a few types and label them in metadata (§2.8). The bundled 30-question sets use these:

| Type | Example (volcanoes) | What it stresses |
|---|---|---|
| `factual` | "What name is given to molten rock that is still underground?" | one-sentence lookup |
| `numeric` | numbers, dates, quantities | exactness: a lexical metric can rate "ten" and "10" differently; check your references (§2.6) |
| `list` | "What are the three types of ..." | completeness: the answer must contain several items, and a short extractive answer may get only some |
| `why` | "Why does rock melt above a subduction zone?" | explanation: references are longer and more paraphrased, so lexical scores are lower |
| `unanswerable` | "What was the deadliest volcanic eruption in history?" | abstention (§2.7) |

Counts in the three 30-question sets (`type` field):

| Dataset | factual | list | numeric | unanswerable | why |
|---|---:|---:|---:|---:|---:|
| volcanoes | 14 | 4 | 2 | 5 | 5 |
| coffee | 13 | 6 | 2 | 5 | 4 |
| lighthouses | 10 | 4 | 2 | 5 | 9 |

Write each question so that it has **one right answer in the document**. "What are the threats to honeybees?" has a list as the right answer; "Tell me about honeybees" has none.

### 2.5.6 Question writing checklist

* Does a user plausibly ask this?
* Could the question be answered *without* the document? If yes, it does not test retrieval; it tests the model's memory.
* Does it avoid copying more than three or four consecutive words from the answer sentence? (The audit script in §2.11 measures this.)
* Is it self-contained? "What does it do?" has no meaning outside a conversation.
* Does it have exactly one defensible answer?
* Does it differ from the other questions? Near-duplicates inflate the sample without adding information.

---

## 2.6 How to write reference answers

The reference is the answer you compare against. It determines what the lexical metrics reward.

### 2.6.1 The rules

1. **Short.** One sentence, or a short list, containing the facts the question asks for and little else. Long references make token F1 punish any answer that is not equally long.
2. **Complete.** Every fact required by the question is present. For "How do bees cool the hive?", both mechanisms ("spread water" and "fan wings").
3. **Paraphrased.** Written in your own words, not pasted from the document (below).
4. **Correct.** Verified against the document, not recalled from memory. A reference that is true in the world but not in the document will punish a correct, faithful answer.
5. **Self-standing.** It reads as an answer to the question without the question.
6. **Consistent style.** If most references are full sentences, all should be; if numbers are digits in some and words in others, normalise. "ten" and "10" are different tokens to a lexical metric.

### 2.6.2 Why verbatim sentences inflate lexical scores: a controlled experiment

The reference should describe the answer, not copy a sentence. To show why, here are two datasets for the **same ten questions** on the **same document**, run through the **same pipeline** (offline, BM25, k = 3). The only difference is the reference answers. In `tidepools.jsonl` they are my own paraphrases ("Mussels multiply and push out other species."). In `tidepools_verbatim.jsonl` each reference is replaced by the document sentence with the most words in common with my paraphrase (so "When sea stars are removed from a shore, mussels spread and crowd out other species.").

```text
tidepools.jsonl (paraphrased references)
Token F1                       0.265      0.145-0.385     20%      10     0    0
ROUGE-L                        0.252      0.137-0.371     10%      10     0    0
Context recall (lexical)       0.818      0.701-0.926     67%       9     1    0

tidepools_verbatim.jsonl (references copied from the document)
Token F1                       0.603      0.409-0.753     80%      10     0    0
ROUGE-L                        0.600      0.403-0.753     80%      10     0    0
Context recall (lexical)       1.000      1.000-1.000    100%       9     1    0
```

The paired comparison confirms it is not noise:

```text
                   label  paired_cases  mean_a  mean_b  diff_b_minus_a  ci_low  ci_high  b_better  ties  b_worse
                Token F1            10   0.265   0.603           0.339   0.220    0.440         9     1        0
                 ROUGE-L            10   0.252   0.600           0.348   0.224    0.453         9     1        0
Context recall (lexical)             9   0.818   1.000           0.182   0.077    0.296         6     3        0
```

**Token F1 more than doubled (0.265 to 0.603), the pass rate went from 20% to 80%, and context recall went to a perfect 1.000, with no change in the pipeline.** The extractive baseline quotes sentences from the document, and a reference that is a sentence from the document is by construction what it quotes. The scores then measure whether the baseline picked *that sentence*, not whether it answered the question.

A live language model that paraphrases would be hurt by verbatim references the other way: a correct answer in different words scores low against a copied sentence.

> **Pitfall.** Verbatim references are tempting because they are fast to write and easy to verify. They make your numbers higher, your pipeline look better and your comparisons less informative. They also make baselines look unrealistically strong compared with live models. Write references in your own words.

You can measure how much of your references is copied with the audit script in §2.11: it reports the longest run of consecutive words each reference shares with the document. In this experiment, the paraphrased references share on average **31%** of their words as one contiguous run; the verbatim ones share **97%**. The bundled honeybee references share about **50%**, volcanoes **37%**, coffee **44%** and lighthouses **49%**. These bundled sets are written in a paraphrased style but still reuse some of the document's phrasing: the offline token F1 of 0.2 to 0.35 on them reflects partial overlap, not a failure.

### 2.6.3 Words that do not appear in the document

A second effect, visible in the tide pool run. Lowest context recall cases:

```text
| t08 | 0.500 | How do hermit crabs deal with growing too big for their shell? | 4/8 reference terms found in context; missing: bigger, chain, look, swapping |
| t05 | 0.667 | What happens to the salt level when pool water evaporates?     | 4/6 reference terms found in context; missing: get, stay |
| t09 | 0.667 | What do anemones do at low tide to avoid drying out?           | 4/6 reference terms found in context; missing: fragment, retract |
```

In case t08, retrieval worked: the hermit-crab paragraph was retrieved. Context recall was low because my reference used words ("bigger", "chain", "look", "swapping") that the document does not use ("larger", "line up", "find", "swap"). The metric cannot tell a synonym from a miss. This is a fact of life with reference-based lexical metrics. Ways to live with it:

* Use some of the document's content words in the reference (not whole sentences): "a larger empty shell", "swap shells".
* Read the **Reason** column before concluding retrieval failed.
* Add semantic or judge metrics when meaning matters (Part III §3.4).

### 2.6.4 Reference length

Token F1 balances precision (how much of the answer is in the reference) against recall (how much of the reference is in the answer). An extractive baseline that returns two sentences (about 30 words) against a 7-word reference has low precision by construction. Look at the Lowest Token F1 table of the tide pool run:

```text
| t10 | 0.000 | How many species of sea star live on the Pacific coast? | no shared tokens |
| t03 | 0.050 | What are the zones of a rocky shore, from the highest to the lowest? | precision 0.03, recall 0.10 (1 shared tokens) |
| t05 | 0.140 | What happens to the salt level when pool water evaporates? | precision 0.08, recall 0.43 (3 shared tokens) |
```

(t10 is an unanswerable question; see §2.7.) Case t03 asks for a list and the reference is a 10-word list ("Splash zone, high tide zone, middle zone and low zone."). The pipeline's answer was two long sentences about zones that included the list only in passing, so precision is 0.03 and recall 0.10. Neither is a "wrong answer" in a human sense: the metric prefers an answer of the reference's length. For list questions, consider whether a metric like context recall (did the retrieved chunk contain the zones?) is the fairer measure for your baseline.

### 2.6.5 Numbers, names and units

* Prefer to state numbers the way the document does: if the document says "about thirty-five degrees Celsius", a reference saying "35°C" shares no tokens with it.
* Normalisation (lower-casing, removing articles and punctuation) is applied by token F1, ROUGE-L and exact match: so "The Queen." and "queen" match, but digits and spelled-out numbers do not.
* If the answer is a single token (a name, a year), `exact_match` becomes useful; for sentences it is nearly always 0.000 (it was 0.000 on every row of the bundled unanswerable run).

### 2.6.6 When there is no reference

A case without `expected_answer` is allowed. Reference-based metrics (`exact_match`, `token_f1`, `rouge_l`, `context_recall`, `correctness`) are skipped for it, and the summary shows the skip. Reference-free metrics (`groundedness`, `faithfulness`, `answer_relevancy`, `context_relevancy`) still work. Use this for quick exploration of a new question set, never for a decision.

---

## 2.7 Unanswerable questions and the abstention sentence

A pipeline that answers confidently when the document has no answer is dangerous. The workbench lets you test for it by including questions the document cannot answer and a reference that is the **abstention sentence**:

> The PDF does not provide enough information to answer the question.

This exact sentence is the pipeline's own abstention answer (a constant in the code; the wording says "PDF" even for Markdown or text). Both live prompts instruct the model to use it verbatim when the context does not contain the answer.

### 2.7.1 How to write one

* The question is on-topic (it shares vocabulary with the document) but asks for something the document does not state. "How much honey does a colony produce in a year?" is on-topic for the honeybee document, which never says.
* Check the document carefully: it must be genuinely absent, not only hard to find.
* The reference is the abstention sentence, word for word. Metadata `"type": "unanswerable"`.

The bundled honeybee set `honeybees_unanswerable.jsonl` has 6 cases: four unanswerable (`u1`-`u4`, for example "How far can a honeybee fly on a single foraging trip?") and two answerable controls (`a1`, `a2`). The three 30-question sets each include 5 unanswerable cases.

### 2.7.2 What the metrics do with them

* The workbench recognises an abstention by four patterns (for example "does not provide enough information", "cannot be answered", "no information").
* If the **reference** is an abstention, `context_recall` is **skipped** ("reference answer is an abstention (unanswerable case)"). In the volcano run: 25 scored, 5 skipped.
* If the **answer** is an abstention, `groundedness` is skipped (no claim to ground).
* `token_f1`, `rouge_l` and `exact_match` are still scored: a correct abstention against an abstention reference scores 1.0; a confident wrong answer scores about 0.

### 2.7.3 What the offline baseline does with them (real run)

By default the extractive baseline abstains only if no retrieved sentence shares a content word with the question. Unanswerable questions about honeybees share words ("honeybee", "colony"), so it does not:

```bash
ragwb run --name hb-unans --dataset examples/datasets/honeybees_unanswerable.jsonl -k 3 --quiet
```

```text
Token F1                       0.039      0.000-0.102       0%       6     0    0
ROUGE-L                        0.039      0.000-0.102       0%       6     0    0
Context recall (lexical)       1.000      1.000-1.000     100%       2     4    0
```

The four unanswerable questions all received a confident answer made of copied sentences (for example u1 "How much honey does a colony produce in a year?" got "Honey is made from nectar. Foragers carry nectar back in a special honey stomach..."). Token F1 on them is about 0. Context recall shows 2 scored and 4 skipped.

With the optional `--min-evidence` threshold and `--skip-headings`:

```bash
ragwb run --name hb-unans2 --dataset examples/datasets/honeybees_unanswerable.jsonl -k 3 --skip-headings --min-evidence 0.7 --quiet
```

```text
Token F1                       0.698      0.365-1.000      67%       6     0    0
```

Looking at the answers: u1-u4 all abstained (token F1 1.0 each), a1 was answered ("After a mating flight early in her life, she stores sperm from many drones...", 0.187) and a2 ("Which parasite threatens honeybee colonies?") also abstained (0.0). **The threshold bought four correct abstentions at the cost of one missed answerable question.** This matches the documented limit: the baseline cannot tell an unanswerable question from a hard one by word overlap alone. On the four bundled documents with held-out questions, the best threshold declined 10 of 12 unanswerable questions but also 24 of 33 answerable ones (`docs/KNOWN_LIMITATIONS.md`), which is why the default is no abstention.

> **Why this works.** The unanswerable cases are the honest test for a live model: models are generally fluent, and a fluent hallucination is the failure that matters. In offline mode they only teach you what the baseline does. Keep them in your dataset so that when you move to a live provider you can measure the abstention behaviour, and make the share match reality (5 of 30, about 17%, in the bundled sets).

### 2.7.4 Reading a slice with unanswerable cases

Because unanswerable cases pull token F1 down (near zero for a confident answer), a mean over the whole dataset mixes two populations. Slice by `type` (§2.8) and read answerable and unanswerable separately. In the volcano run, token F1 was 0.042 on the five unanswerable cases against 0.276 on the 14 factual ones.

---

## 2.8 Metadata for slicing

Metadata is what turns one number into a diagnosis. Put at least these three fields in every serious dataset:

| Field | Values | Answers the question |
|---|---|---|
| `type` | factual, numeric, list, why, unanswerable | Which kinds of questions fail? |
| `difficulty` | easy, medium, hard | Does the pipeline fail only on hard ones? |
| `topic` | your own (for example "plate boundaries") | Which parts of the document are weak? |

Optional extras: `source` (the chunk id), `author` (who wrote the question), `batch` (when it was added), `origin` ("real-user" or "written").

### 2.8.1 `ragwb slices`

```bash
ragwb slices <run-id> --by type
ragwb slices <run-id> --by difficulty
ragwb slices <run-id> --by topic
```

Output for the 30-question volcano run at k = 3 (offline), by `difficulty`:

```text
slice                    cases   ok            Token F1             ROUGE-L  Context recall (le  Groundedness (lexi
easy                         6    6     0.150       (6)     0.114       (6)     0.629       (5)     1.000       (6)
hard                         6    6     0.175       (6)     0.162       (6)     0.492       (4)     1.000       (6)
medium                      18   18     0.223      (18)     0.206      (18)     0.712      (16)     1.000      (18)
(n scored in brackets; small slices have wide uncertainty)
```

Notice what a sloppy reading would conclude ("the baseline is worse on easy questions than on medium ones: 0.150 against 0.223") and why it would be wrong: the easy slice has 6 cases, and "easy" here means easy for a *human* to see the answer, not easy to match lexically. The metadata describes the question, not the metric. Two cautions:

1. **Small slices have wide uncertainty.** `ragwb slices` prints no interval, only the scored count in brackets. A slice of 1 to 3 cases (the topic slices in the volcano set have 1 to 4) is an anecdote, not a statistic.
2. **A metadata field name must exist** in the dataset. Slices work on any field in the `metadata` object (or any extra CSV column), and the web app offers the available fields in a selector.

### 2.8.2 Designing metadata so slices mean something

* **Few values, many cases each.** 3 difficulty levels over 30 questions gives about 10 per slice; 13 topics over 30 questions gives 2 to 4 per slice. Use coarse topics, or accept that topic slices are for finding candidates to read, not for concluding.
* **Define each value** in a short note next to the dataset (what is "hard"?), so that a second author labels consistently.
* **Label before you run.** If you assign `difficulty` after seeing which questions failed, the slices will tell you what you already believed.
* **Keep types mutually exclusive.** A question that is both `numeric` and `why` should be given one, by a stated rule.

---

## 2.9 Dataset size and what it buys

### 2.9.1 Why size matters: the interval

Every mean comes with a 95% interval over the questions. How wide it is depends on how spread out the per-question scores are and on how many questions you have. For a rough rule, the half-width is about 2 × (standard deviation of the scores) ÷ √(number of questions).

Real numbers from the bundled data (offline baseline, k = 3, token F1):

| Dataset | Questions | Token F1 mean | 95% interval | Width |
|---|---:|---:|---|---:|
| honeybees | 20 | 0.346 | 0.285 – 0.419 | 0.134 |
| volcanoes | 30 | 0.199 | 0.149 – 0.252 | 0.103 |
| coffee | 30 | 0.257 | 0.186 – 0.328 | 0.142 |
| lighthouses | 30 | 0.212 | 0.149 – 0.277 | 0.128 |

Widths of 0.10 to 0.14 around means of 0.2 to 0.35 are wide. **Two pipelines whose means differ by less than about 0.1 cannot be told apart on 20 to 30 questions by their separate intervals**, which is why the paired comparison exists (it removes question difficulty from the difference and so is sharper).

### 2.9.2 Illustrative arithmetic: how many questions for a target precision

The honeybee token F1 scores have a standard deviation of 0.159 (shown on the Run results Summary tab). With the rule above, the half-width at 20 questions is about 2 × 0.159 ÷ √20 = 0.071, close to the observed 0.067. To halve it to about 0.035 you need four times as many questions: 80. To bring it to ±0.03 you need about 110 (illustrative arithmetic: 1.96 × 0.159 ÷ 0.03 = 10.4, squared). The cost of precision grows with the square.

| Target half-width on this spread (illustrative) | Questions needed |
|---|---:|
| ±0.07 | about 20 |
| ±0.05 | about 40 |
| ±0.035 | about 80 |
| ±0.03 | about 110 |

For paired comparisons, the spread of the *differences* matters, which is usually smaller than the spread of the scores, so fewer questions are needed to detect a given gain. The tour comparison in Part I found a 0.060 gain in token F1 significant on 20 questions (interval 0.012 to 0.117), while a similar comparison on ten tide-pool questions found a context-recall gain of 0.105 not significant (interval 0.000 to 0.278): ten questions are not enough to see even a 0.1 change.

### 2.9.3 A small experiment: the same dataset, truncated

`--limit N` evaluates only the first N cases. Running the honeybee set at three sizes:

| `--limit` | Token F1 mean | 95% interval | Context recall mean | 95% interval |
|---:|---:|---|---:|---|
| 5 | 0.293 | 0.216 – 0.371 | 0.950 | 0.850 – 1.000 |
| 10 | 0.310 | 0.261 – 0.357 | 0.891 | 0.817 – 0.961 |
| 20 | 0.346 | 0.285 – 0.419 | 0.885 | 0.839 – 0.930 |

Read this carefully, because it contains two warnings:

* **The means move.** Context recall is 0.950 on the first five questions and 0.885 on all twenty. A sample of five told you retrieval was nearly perfect.
* **The interval does not shrink steadily.** The width for 5 cases (0.155) is larger than for 10 cases (0.096), because the width depends on how spread out the particular scores are, not only on how many there are. The bootstrap can only resample what it has seen; with very few cases the interval is unreliable in both directions. Do not interpret an interval on fewer than about 15 to 20 cases as a measure of anything.

> **Pitfall.** `--limit` takes the *first* N questions, not a random sample. If your dataset is ordered by topic or difficulty, a limited run is biased. Shuffle the file (and keep it shuffled) before using `--limit` for quick checks, and never publish a result from `--limit`.

### 2.9.4 What size to aim for

| Purpose | Sensible size | Because |
|---|---|---|
| Smoke test, plumbing check | 5-10 | checks that the pipeline runs; says nothing about quality |
| Exploration, development | 20-30 | enough to see big differences (more than 0.1) and read every failing case |
| A decision between two configurations | 50-100 paired questions, or more | detects differences of 0.05 to 0.1 with confidence |
| A regression gate in CI | at least 30, and stable | `ragwb regress` needs 10 paired questions per metric by default (`--min-pairs`) and a 0.02 tolerated drop; with few questions it will report "not judged" |
| A claim in a report | as many as needed to report an interval narrower than the effect you claim | see §2.9.2 |

### 2.9.5 Independence: more questions are not always more information

Ten questions about the same paragraph are not ten independent samples; they share a retrieval outcome. The interval assumes independent questions, so correlated questions make it too narrow. Spread your questions across paragraphs (§2.5.2) and consider the *effective* sample size to be closer to the number of distinct paragraphs or facts covered. The honeybee document has ten content paragraphs: a 20-question set is, in effect, two questions per fact area.

---

## 2.10 Building a dataset from a new document: a worked example

This is the full procedure, with a document and dataset created from nothing. Everything below was run.

### 2.10.1 Step 1: the document

Create `tidepools.md`: a short, original document about tide pools (ten paragraphs including the title). Part of it:

```text
  # Tide Pools: Life Between the Tides

A tide pool is a small basin of seawater left behind on a rocky shore when the tide goes out. Because the
water in a pool is trapped for several hours, the animals that live there must cope with sudden changes in
temperature, saltiness and oxygen.

The shore is divided into zones by how long each part is covered by the sea. The splash zone is wetted only
by spray, the high tide zone is covered for a short time twice a day, the middle zone is covered and
uncovered every day, and the low zone is almost always underwater.

On a sunny afternoon the water in a shallow pool can warm by as much as ten degrees Celsius. ...
```

(Each paragraph is on one line in the real file; it is wrapped here for width. The remaining paragraphs cover sea stars, mussels and barnacles, hermit crabs, anemones, predators, and how visitors can help.)

**Rules I followed:** one idea per paragraph, blank line between paragraphs, a title, no tables, ordinary punctuation, every fact stated once.

### 2.10.2 Step 2: look at the chunks

Before writing questions, check how the document is chunked. Open the Document chunks tab, or load it with the loader. Result: **10 chunks** (title plus nine paragraphs), 181 to 275 characters each, one 34-character heading chunk (`Tide Pools: Life Between the Tides`). With `--skip-headings`, 9 chunks.

Nothing alarming: no chunk is a fragment, none is near the 2,000-character limit.

### 2.10.3 Step 3: plan coverage

The document has nine content paragraphs (the Document chunks tab numbers them `p1-b2` to `p1-b10`). I planned ten questions: nine answerable and one unanswerable. Types: factual 4, why 3, list 1, numeric 1, unanswerable 1. Difficulty: easy 2, medium 5, hard 3.

Now the honest part, which you should do as well: map each question to its source paragraph.

| Paragraph | Topic | Questions |
|---|---|---|
| `p1-b2` | what a tide pool is, why conditions change | t01, t02 |
| `p1-b3` | shore zones | t03 |
| `p1-b4` | temperature and salt swings | t04, t05 |
| `p1-b5` | sea stars | t06, t07 |
| `p1-b6` | mussels and barnacles | none |
| `p1-b7` | hermit crabs | t08 |
| `p1-b8` | anemones | t09 |
| `p1-b9` | predators and hiding | none |
| `p1-b10` | protecting tide pools | none |

Three of nine paragraphs have no question, so this first version of the dataset says nothing about whether retrieval can find them. That is a coverage gap, found by a table that took two minutes to write. For a real dataset you would add questions for `p1-b6`, `p1-b9` and `p1-b10` before trusting any result. I leave the gap in this worked example so that the numbers below can be reproduced from the files above.

### 2.10.4 Step 4: write questions and references

The ten cases of `tidepools.jsonl`, with the rationale:

```json
{"id": "t01", "question": "What is a tide pool?", "expected_answer": "A small basin of seawater that stays behind on a rocky shore after the tide goes out.", "metadata": {"type": "factual", "difficulty": "easy", "topic": "definition"}}
{"id": "t02", "question": "Why must tide pool animals tolerate sudden changes?", "expected_answer": "The water in a pool is trapped for hours, so temperature, saltiness and oxygen can change quickly.", "metadata": {"type": "why", "difficulty": "medium", "topic": "conditions"}}
{"id": "t03", "question": "What are the zones of a rocky shore, from the highest to the lowest?", "expected_answer": "Splash zone, high tide zone, middle zone and low zone.", "metadata": {"type": "list", "difficulty": "medium", "topic": "zones"}}
{"id": "t04", "question": "By how much can a shallow pool warm on a sunny afternoon?", "expected_answer": "By up to about ten degrees Celsius.", "metadata": {"type": "numeric", "difficulty": "easy", "topic": "conditions"}}
{"id": "t05", "question": "What happens to the salt level when pool water evaporates?", "expected_answer": "The pool gets saltier because the salt stays behind.", "metadata": {"type": "why", "difficulty": "medium", "topic": "conditions"}}
{"id": "t06", "question": "How does a sea star eat a mussel?", "expected_answer": "It pulls the shell open with its arms, pushes its stomach inside and digests the body there.", "metadata": {"type": "factual", "difficulty": "medium", "topic": "predators"}}
{"id": "t07", "question": "What happens to a shore when its sea stars are taken away?", "expected_answer": "Mussels multiply and push out other species.", "metadata": {"type": "why", "difficulty": "hard", "topic": "predators"}}
{"id": "t08", "question": "How do hermit crabs deal with growing too big for their shell?", "expected_answer": "They look for a bigger empty shell, sometimes swapping in a chain by size.", "metadata": {"type": "factual", "difficulty": "medium", "topic": "crabs"}}
{"id": "t09", "question": "What do anemones do at low tide to avoid drying out?", "expected_answer": "They retract their tentacles and cover themselves with shell fragments and sand.", "metadata": {"type": "factual", "difficulty": "hard", "topic": "anemones"}}
{"id": "t10", "question": "How many species of sea star live on the Pacific coast?", "expected_answer": "The PDF does not provide enough information to answer the question.", "metadata": {"type": "unanswerable", "difficulty": "hard", "topic": "predators"}}
```

Design notes on a few of these:

* **t01** is easy and shares words with the paragraph: a sanity check that the pipeline can do the basics.
* **t02** is a *why* question whose answer spans two sentences; the reference summarises them.
* **t03** is a list question: the reference lists all four zones; I expect low token F1 and want to see it (§2.6.4).
* **t07** has a hard question phrased differently from the document ("taken away" for "removed", "multiply" for "spread"): it tests paraphrase.
* **t08** and **t09**: I wrote the references with synonyms on purpose, to demonstrate §2.6.3 (it worked: "bigger", "chain", "retract" are not in the document).
* **t10** is on-topic (sea stars, predators) but asks for a figure the document never gives; the reference is the abstention sentence.

### 2.10.5 Step 5: validate

```bash
ragwb validate tidepools.jsonl
```

```text
tidepools.jsonl: 10 cases, 10 with reference answers
valid
```

### 2.10.6 Step 6: run it offline

```bash
ragwb run --name tp-k3 --dataset tidepools.jsonl --document tidepools.md -k 3 --quiet
```

```text
Run 20261030-205127-tp-k3-502661: completed
cases 10  ok 10  errors 0  mean latency 0.5 ms
metric                          mean           95% CI    pass  scored  skip  err
Token F1                       0.265      0.145-0.385     20%      10     0    0
ROUGE-L                        0.252      0.137-0.371     10%      10     0    0
Context recall (lexical)       0.818      0.701-0.926     67%       9     1    0
Groundedness (lexical)         1.000      1.000-1.000    100%      10     0    0
```

The same run with headings dropped (`--skip-headings`) gave token F1 0.242 (0.142-0.336), ROUGE-L 0.230, the same context recall 0.818: no real change on this document, because the short title was not in anyone's top three. Not every option helps; on the honeybee document, the title was.

### 2.10.7 Step 7: read the result like an evaluator

1. **Counts add up.** 10 cases, 10 ok; context recall has 9 scored and 1 skipped. Which one? The unanswerable t10, whose reference is an abstention. Good: that is intended.
2. **Retrieval looks fine** (context recall 0.818, 67% pass) and **answers look weak** (token F1 0.265, 20% pass). Which part? The Lowest Token F1 table:

   ```text
   | t10 | 0.000 | How many species of sea star live on the Pacific coast? | no shared tokens |
   | t03 | 0.050 | What are the zones of a rocky shore, ...                 | precision 0.03, recall 0.10 (1 shared tokens) |
   | t05 | 0.140 | What happens to the salt level when pool water evaporates? | precision 0.08, recall 0.43 (3 shared tokens) |
   ```

   t10 is the confident answer to an unanswerable question: a real failure of the baseline (§2.7). t03 is the list question with a mismatch of answer length. t05 is a *why* question where the baseline returned a longer passage.
3. **Slice it:**

   ```text
   slice                    cases   ok            Token F1             ROUGE-L  Context recall (le  Groundedness (lexi
   factual                      4    4     0.393       (4)     0.373       (4)     0.764       (4)     1.000       (4)
   list                         1    1     0.050       (1)     0.050       (1)     1.000       (1)     1.000       (1)
   numeric                      1    1     0.186       (1)     0.186       (1)     1.000       (1)     1.000       (1)
   unanswerable                 1    1     0.000       (1)     0.000       (1)         -       (0)     1.000       (1)
   why                          3    3     0.280       (3)     0.264       (3)     0.769       (3)     1.000       (3)
   ```

   (The unanswerable row's context recall is `-` with 0 scored: skipped, not zero.) Slices of one case (list, numeric, unanswerable) are anecdotes, but they show the mechanics: with ten questions you can slice by type only to find cases to read, not to conclude.
4. **Vary one setting.** I ran k = 1, 3 and 5:

   | Run | Token F1 | Context recall (scored 9) |
   |---|---:|---:|
   | k = 1 | 0.257 (0.163-0.341) | 0.713 (0.512-0.889) |
   | k = 3 | 0.265 (0.145-0.385) | 0.818 (0.701-0.926) |
   | k = 5 | 0.265 (0.145-0.385) | 0.832 (0.736-0.926) |

   And the paired comparisons: k = 1 to k = 3 gives context recall +0.105 (0.000 to 0.278), 2 better, 7 tied, 0 worse; `ci_excludes_zero` is False, so the tool calls it inconclusive. k = 3 to k = 5: +0.014 (0.000 to 0.042), 1 better, 8 tied. **Ten questions cannot decide this**, though the pattern (more context recall with more chunks, never worse) is suggestive. This is exactly what §2.9 predicts: to confirm a 0.1 gain in context recall you need considerably more than ten questions.

### 2.10.8 Step 8: check the references, then fix them

Two findings need action. The coverage table in §2.10.3 shows three paragraphs with no questions, so I would write at least one question for each. And the Lowest Context recall table (§2.6.3) showed that three references used words the document does not use. Two options for those: rewrite those references to use the document's content words, or keep them, accepting a slight score penalty, as a test of paraphrase robustness. A decision, recorded in a notes file next to the dataset, is better than either habit. In a real project I would rewrite t08 and t09 and **version the dataset** (§2.12).

### 2.10.9 Step 9: save and tag

```bash
ragwb tag 20261030-205127-tp-k3-502661 --add baseline
ragwb note 20261030-205127-tp-k3-502661 "tidepools v1, 10 questions, BM25 k=3"
```

Later: `ragwb list --tag baseline`. Tags and notes make the run findable in a month.

---

## 2.11 Reviewing a dataset for leakage and ambiguity

Before you trust a dataset, review it. The goal is to find questions that are too easy for the wrong reason (**leakage**), questions with no single right answer (**ambiguity**), and references that are wrong.

### 2.11.1 Kinds of leakage

| Leak | Example | Effect |
|---|---|---|
| **Question copies the answer sentence** | "The queen can lay up to two thousand eggs a day. How many eggs can a queen lay in a day?" | any keyword retriever finds it; inflates retrieval |
| **Reference copies the document** | §2.6.2 | inflates lexical metrics for extractive and quoting pipelines |
| **The question names the paragraph** | "In the section on beeswax, what produces wax?" | gives the retriever a free hint a real user would not |
| **Answerable from general knowledge** | "What is the capital of France?" in a document about France | tests the model's memory, not the retriever |
| **Test questions seen during tuning** | you tune `min_evidence` on the same 20 questions you report on | optimistic result; keep a held-out half (the workbench's `tune-abstention` does so) |
| **Near-duplicates** | five phrasings of one question | inflates the sample and over-weights one paragraph |

### 2.11.2 A copy-detection script

A simple, standard-library-only script measures, for each case, the longest run of consecutive words shared with the document, for the question and for the reference. Save it as `audit_dataset.py`:

```python
"""usage: python audit_dataset.py DATASET.jsonl DOCUMENT.md"""
import json, re, sys
from pathlib import Path

def words(text):
    return re.findall(r"[a-z0-9']+", text.lower())

def longest_shared_run(a, grams, max_n=30):
    best = 0
    for n in range(1, min(len(a), max_n) + 1):
        if any(tuple(a[i:i + n]) in grams[n] for i in range(len(a) - n + 1)):
            best = n
        else:
            break
    return best

def main(dataset, document):
    doc_words = words(Path(document).read_text(encoding="utf-8"))
    grams = {n: {tuple(doc_words[i:i + n]) for i in range(len(doc_words) - n + 1)} for n in range(1, 31)}
    rows = [json.loads(l) for l in Path(dataset).read_text(encoding="utf-8").splitlines() if l.strip()]
    ref_ratios, q_runs = [], []
    print(f"{'id':5} {'q_run':>5} {'ref_len':>7} {'ref_run':>7} {'ref_copied%':>11}")
    for r in rows:
        q, ref = words(r["question"]), words(r.get("expected_answer") or "")
        q_run = longest_shared_run(q, grams)
        ref_run = longest_shared_run(ref, grams) if ref else 0
        ratio = 100 * ref_run / len(ref) if ref else 0
        q_runs.append(q_run)
        if "does not provide enough" not in (r.get("expected_answer") or ""):
            ref_ratios.append(ratio)
        print(f"{r.get('id','?'):5} {q_run:5d} {len(ref):7d} {ref_run:7d} {ratio:10.0f}%")
    print(f"mean longest question run: {sum(q_runs)/len(q_runs):.1f} words; "
          f"mean reference copied (answerable only): {sum(ref_ratios)/len(ref_ratios):.0f}%")

main(sys.argv[1], sys.argv[2])
```

It is not part of the workbench; it is a helper for you. Running it on the example sets and on my tide pool files:

| Dataset | mean longest question run (words) | mean reference copied (answerable) |
|---|---:|---:|
| tidepools.jsonl (my paraphrased references) | 2.9 | 31% |
| tidepools_verbatim.jsonl | 2.9 | 97% |
| honeybees.jsonl | 2.4 | 50% |
| volcanoes.jsonl | 2.3 | 37% |
| coffee.jsonl | 2.1 | 44% |
| lighthouses.jsonl | 2.7 | 49% |

Rules of thumb (these are my judgement, not thresholds from the workbench): a mean question run above about four words suggests the questions were written by copying; a reference copied above about 70% suggests verbatim references. Both are flags to review, not proofs. A "copied" two-word run like "honeybee colony" is normal.

### 2.11.3 Reviewing for ambiguity

Read each question and ask a colleague to answer it from the document **without seeing your reference**. Compare:

* **Different answers** → the question is ambiguous or the reference incomplete.
* **"The document doesn't say"** when you labelled it answerable → wrong label, or the answer is too hidden.
* **An answer more detailed than your reference** → decide whether the reference should be longer.

Disagreement between two reviewers on 10% of questions is normal in a first pass. Fix the questions, not the metric.

### 2.11.4 Review checklist per case

1. Can I point at the sentence(s) in the document that answer it?
2. Is the reference correct and complete according to that sentence?
3. Is the question phrased the way a user would ask?
4. Could the answer be known without the document?
5. Is it too similar to another case?
6. Is the `type`, `difficulty` and `topic` label right?
7. If it is unanswerable: is the topic really absent?

A 10-question dataset takes about 20 minutes to review this way. A 100-question dataset deserves two reviewers.

---

## 2.12 Versioning datasets

A dataset changes: questions are added, references corrected, labels fixed. The workbench records, with every run:

* the **dataset file's SHA-256** and the **document's SHA-256** (first 12 hex characters shown in reports and on the Compare page's configuration table; the full hash on the Results Configuration tab and the Datasets page);
* the file paths, configuration, package versions, seed.

These hashes are over the *file bytes*, so any change, including a changed comma or line ending, gives a new hash. In the tide pool example:

```text
* Dataset: `tidepools.jsonl` (sha256 `5effea36fd90`)
* Document: `tidepools.md` (sha256 `17b222f206fa`)
```

I then changed one word in the document ("ten degrees" to "eight degrees", for a different version of the fact), saved it as another file and re-ran with the same dataset:

```text
* Dataset: `tidepools.jsonl` (sha256 `5effea36fd90`)
* Document: `tidepools_edit.md` (sha256 `646ddfc53718`)
```

The dataset hash is unchanged and the document hash is different, so the record proves that **only the document changed**. The scores moved slightly (token F1 0.265 to 0.260, context recall 0.818 to 0.781), and exactly one case changed: t04, whose reference says "ten degrees" while the document now says "eight" (its context recall fell from 1.000 to 0.667 and its token F1 from 0.186 to 0.139). The Compare page's configuration table shows the dataset hash row; the document hash is on the Results Configuration tab and in every export, so check it there when you suspect the document changed.

### 2.12.1 A versioning practice that works

1. **Name files with a version**: `tidepools-v1.jsonl`, `tidepools-v2.jsonl`. Never edit a file that a published run used.
2. **Keep datasets in version control** (git or any other) and record the commit.
3. **Write a changelog** next to the dataset: "v2: rewrote t08 and t09 references to use document words; added t11-t14".
4. **Re-run the baseline on the new version.** Runs on different dataset versions are not comparable. If you change v1 to v2 and compare old v1 runs with new v2 runs, the paired comparison pairs by question text and uses only shared questions, and `paired_cases` will show how many survived. Check that column.
5. **Tag runs**: `ragwb tag <run> --add baseline,v2`.
6. **Export bundles** (`ragwb export <run> --format json`) to keep the evidence with its configuration; bundles can be re-imported elsewhere.

> **Pitfall.** If two runs have different dataset hashes, any difference in scores may come from the data. Always check the dataset hash row on the Compare page before interpreting a difference as the effect of a configuration change. The Compare page warns when hashes differ.

### 2.12.2 Changing a dataset without breaking history

If you fix a reference in place, the question text is unchanged, so old and new runs still pair by question; but scores for that case may change for reasons that have nothing to do with the pipeline. For a regression gate, fix the dataset first, re-run the baseline on the fixed dataset, and only then compare candidates against it.

---

## 2.13 The bundled example corpus

Four short documents, each as `.md` (the source) and `.pdf` (the rendering the examples use). Three of the documents have a 30-question dataset with metadata, and honeybees has three.

| Document | Chunks | Datasets | Questions |
|---|---:|---|---:|
| honeybees | 11 | `honeybees.jsonl` | 20 |
| | | `honeybees_paraphrased.csv` | 5 |
| | | `honeybees_unanswerable.jsonl` | 6 |
| volcanoes | 15 | `volcanoes.jsonl` | 30 |
| coffee | 15 | `coffee.jsonl` | 30 |
| lighthouses | 15 | `lighthouses.jsonl` | 30 |

Baseline offline results (BM25, k = 3, default headings, extractive generator) that you can reproduce exactly:

| Run | Questions | Token F1 | 95% interval | Context recall | Scored / skipped |
|---|---:|---:|---|---:|---|
| honeybees | 20 | 0.346 | 0.285 – 0.419 | 0.885 | 20 / 0 |
| honeybees_paraphrased | 5 | 0.225 | 0.109 – 0.360 | 0.664 | 5 / 0 |
| honeybees_unanswerable | 6 | 0.039 | 0.000 – 0.102 | 1.000 | 2 / 4 |
| volcanoes | 30 | 0.199 | 0.149 – 0.252 | 0.660 | 25 / 5 |
| coffee | 30 | 0.257 | 0.186 – 0.328 | 0.765 | 25 / 5 |
| lighthouses | 30 | 0.212 | 0.149 – 0.277 | 0.819 | 25 / 5 |

(The honeybees_unanswerable context recall of 1.000 is on only two answerable control cases, with a degenerate interval: do not read it as good retrieval.)

### 2.13.1 What each is good for

**Honeybees (20).** The first thing to run. Ten paragraphs, one-line title, no metadata. Good for learning the interface, for seeing the title-chunk effect (k = 1 versus k = 3), and for observing that a baseline that quotes the right sentence still scores token F1 of about 0.35. The live record has many runs on it, so you can compare offline numbers with live ones (for example run 4: 10 honeybee questions, token F1 0.680, with `gpt-oss-20b` generating via Groq).

**Honeybees paraphrased (5, CSV).** Shows the CSV format (an extra `topic` column becomes metadata) and the effect of paraphrased questions. Too small to conclude anything; excellent for a demonstration, and a template for writing your own paraphrased set.

**Honeybees unanswerable (6).** Four unanswerable and two answerable control questions: the minimal test of abstention, `--min-evidence` and slicing by `type`. Its reference for unanswerable cases is the abstention sentence.

**Volcanoes (30).** The fullest dataset: `type`, `difficulty` and `topic` metadata on every case, five unanswerable, six hard questions, 13 topics. It is the one used for the live judge study (30 questions in runs 6 and 7, and the AI-rater labels), so it is the right dataset for practising `slices` and for comparing offline with live results. For example, with `qwen/qwen3.8-27b` generating, token F1 was 0.489, against 0.199 for the offline baseline, on the same questions.

**Coffee (30).** More `list` questions (6) and a richer set of topics (growing region, caffeine, processing, roasting, history). A good second dataset for checking that a finding on volcanoes holds elsewhere.

**Lighthouses (30).** The most `why` questions (9) and the most hard ones (8): the best set for testing explanation-style answers, where lexical metrics are weakest. Context recall (0.819) is the highest of the 30-question sets, token F1 (0.212) near the lowest: strong retrieval, weak overlap, a vivid example of why the two metrics must be read apart.

### 2.13.2 Using the corpus to practise

A sensible sequence for a new user:

1. Run honeybees at k = 1, 3, 5 and compare (Part IV §4.3).
2. Run `honeybees_unanswerable` with and without `--min-evidence 0.7 --skip-headings`.
3. Run volcanoes and slice by `type` and `difficulty`.
4. Run coffee and lighthouses and ask whether volcano's findings hold.
5. Then write your own document and dataset (§2.10).

Remember that the documents are short and were written for this project. Results on them show how the tool behaves, not how your documents behave.

---

## 2.14 Before you trust an evaluation set

Run through this checklist for every dataset before you act on a result from it.

### Document

- [ ] I opened the Document chunks tab and read the chunks. They are paragraphs, not fragments or interleaved columns.
- [ ] The document is text-based (not a scan), UTF-8 (for `.txt`/`.md`) and under the size limit.
- [ ] I know whether the title and headings are chunks, and I decided on `--skip-headings` deliberately.
- [ ] I tried the Retrieval playground on at least two questions.
- [ ] I recorded the document's SHA-256 (it is in every run).

### Questions

- [ ] The questions resemble real user questions; some were not written by the document's own author.
- [ ] Every paragraph is the source of at least one question, and none of more than three or four.
- [ ] There is a mix of easy, medium and hard, and of factual, numeric, list and why.
- [ ] At least a third are paraphrased (if I am choosing between retrievers).
- [ ] Some are unanswerable, in a share that matches reality, and the document truly lacks the answer.
- [ ] No question copies more than three or four consecutive words from its answer sentence (audit script).
- [ ] No near-duplicates; no questions answerable without the document.

### References

- [ ] Each reference is short, complete, correct per the document, and in my own words.
- [ ] I measured how much is copied (the audit script) and it is well below 70%.
- [ ] Numbers and names are written in a consistent form that matches the document's.
- [ ] Unanswerable cases use the abstention sentence exactly.
- [ ] A second person checked at least a sample.

### Format and size

- [ ] `ragwb validate` says valid, and I read every warning.
- [ ] Metadata (`type`, `difficulty`, `topic`) is present, defined, and was assigned before I saw any results.
- [ ] I know how wide my intervals are at this size (§2.9) and what difference I can detect.
- [ ] I did not tune settings on the questions I report on (or I kept a held-out half).

### Versioning

- [ ] The dataset has a version in its filename and is under version control.
- [ ] Baseline runs exist on *this* version of the dataset, tagged.
- [ ] Any comparison I make shares one dataset hash and one document hash.

If you cannot tick most of these, the numbers that come out will be honest, precise-looking and wrong in ways the tool cannot warn you about. The tool is strict about arithmetic. It cannot be strict about the quality of the questions you give it.

Next: Part III helps you choose a configuration (retriever, *k*, mode, metrics) to run on the evaluation set you have just prepared.
