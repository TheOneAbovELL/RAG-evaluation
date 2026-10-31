# Known Limitations and Future Work

## Not verified in this environment

* **Live verification is narrow.** The OpenAI-compatible generation path and the four DeepEval judge metrics were run
  against Groq's free tier (models `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `qwen/qwen3.8-27b`) on small samples
  (see `docs/LIVE_VERIFICATION.md`). They work, but no run was made against OpenAI itself, no tool-calling agent
  pipeline was run live, API embeddings were not available on that provider, and judge scores were never compared
  with human labels (they were compared with labels written by an AI rater: see below).
* **Dependency vulnerability scan (v1.1):** `pip-audit` over the locked runtime requirements reported no known
  vulnerabilities at the time of the scan (it queries an advisory database, so the result is only as current as that
  moment; re-run `scripts/verify.py --audit` before each release).
* No formal accessibility audit and no screen-reader pass (axe-core and keyboard walks are recorded below).
* The Dockerfile has not been built or run (no Docker was available). The wheel was installed with all its dependencies into a fresh
  virtual environment and used from a neutral folder (`scripts/wheel_check.py`, 10/10 checks); that installs the command-line tool only.
* The semantic metrics were run with a real local model (`BAAI/bge-small-en-v1.5`) but their scores barely separate good
  from poor answers (bge cosines sit at 0.5 even for unrelated text), so the 0.7 default thresholds are not meaningful
  until calibrated against human labels.
* Other OpenAI-compatible providers (for example xAI Grok via `OPENAI_BASE_URL`) are supported by configuration only;
  DeepEval accepts a Grok model name at construction (checked offline), but nothing was sent to any provider.
* `scripts/live_smoke.py` has passed 12/12 against Groq (2 cases); it has not been run against OpenAI.
* **No judge-versus-human calibration exists.** (A threshold sweep on the AI-written labels is in `docs/LIVE_VERIFICATION.md`.) What exists is a comparison with labels written by Claude (an AI rater, one
  rater, 30 cases, 4 fails; `calibration/volcanoes-labels-by-claude.csv`, `docs/LIVE_VERIFICATION.md` run 11): the
  `correctness` judge agreed on 29 of 30 (kappa 0.870) and token F1 on only 18 of 30 (kappa 0.237). That supports
  "the judge is not obviously unreliable on easy cases", nothing stronger. The human labelling sheet is still unfilled.

## Methodological limits

* **Lexical metrics measure word overlap, not meaning.** A correct paraphrase can score low: the extractive
  baseline's token F1 is about 0.35–0.40 on the example dataset even when it quotes the right sentence, because the
  reference answers are paraphrases.
* **The offline generator is an extractive baseline, not a language model.** Its groundedness is 1.0 by
  construction, by default it never abstains on the bundled unanswerable questions (every question shares content
  words with the document). The optional `--min-evidence` abstention threshold helps only at a cost: at 0.7 with
  `--skip-headings` it abstained on all four unanswerable questions but also on one answerable control question, so
  it trades missed answers for fewer wrong ones and must be tuned on your own data. With more retrieved chunks it can pick sentences from less relevant passages (on the example
  data, token F1 is lower at k = 3 than at k = 1).
* **BM25 has only light stemming and no synonyms**: for "Which parasite threatens honeybee colonies?" it ranks the
  document title first and the varroa paragraph third ("threatens" ≠ "threats", "parasite" ≠ "parasitic").
* **Headings become chunks**: the PDF title is a retrievable chunk with no sentence punctuation, so the extractive
  generator can include it verbatim in an answer. `--skip-headings` drops short unpunctuated chunks before
  indexing; it is off by default so results stay comparable with earlier runs, and the heuristic can drop a real
  short chunk.
* **Judge scores are model opinions** and vary with the judge model; bootstrap intervals capture sampling of
  questions only, not judge noise.
* **Twenty questions is a small sample**: many differences between configurations are statistically
  inconclusive; the UI says so.

## Metric implementation details worth knowing

* Bootstrap bounds depend on the order of the scores as well as the seed (a run's order is the dataset order, so a
  given run is reproducible; two runs with identical scores in a different order can differ in the 3rd decimal).
* Judge calls: transient provider errors (rate limit, timeout, 5xx) are retried with exponential back-off and jitter;
  any other judge failure is recorded as a metric error. Judge cost is whatever DeepEval reports as
  `evaluation_cost` (unverified against a live call); judge token counts are not available.
* Generator cost uses the prices you configure; they are stored with the run (`prices_usd_per_mtok`) so old runs keep
  the prices they were costed with.

## Engineering limits

* Local tool first. The app listens on localhost only by default. Beyond that there is either one shared password
  (`RAGWB_APP_PASSWORD`) or named accounts (`ragwb user add`, scrypt hashes, per-user and global lockout, sign-in log
  lines, `started_by` on runs) and roles (viewer, editor, admin), an admin Accounts page and self-service password change.
  There is no e-mail password reset, and run visibility is shared by default (`RAGWB_RUN_VISIBILITY=own` hides other users' runs
  from non-admins, at application level only). `start.py --ssl-cert/--ssl-key` serves HTTPS (checked with a self-signed
  certificate); without it credentials cross the network in clear text. Roles are read on every page load, so removing a user
  or changing a role takes effect immediately.
* Cancellation from the UI uses Streamlit's Stop button; in-flight model calls (and, with several workers, up to
  2 × workers queued cases) finish before the run stops.
* A `running` run whose process died is shown as `running` until no case has been committed for 15 minutes; then
  the next start-up marks it `interrupted`.
* The New evaluation and Datasets pages re-parse the selected PDF on every rerun (fast for small documents).
* The per-case time limit (`RAGWB_CASE_TIMEOUT_S`, default 600 s) abandons a stuck case and records an error, but
  Python cannot kill a thread: the abandoned call keeps running in the background until its own HTTP timeout.
* Scale (offline path, `scripts/benchmark.py`, one laptop): throughput is flat at about 100-108 cases/s from 200 to 5,000 cases
  (5,000 cases: 47 s, 54 MB peak Python memory, 21 MB database). More workers help only slightly offline (4 workers: 116 vs 100
  cases/s at 1,000 cases); they pay off when cases wait on the network. Earlier releases published roughly half these throughputs and
  claimed four workers were slower: those figures were measured with `tracemalloc` running and are withdrawn (release 1.4).
  Larger datasets than `RAGWB_MAX_CASES` (default 5,000) are refused rather than benchmarked.
* `PROJECT_ROOT` is derived from the source location, so the package is meant to be used from this project
  (editable install); a wheel install works for the command-line tool (`RAGWB_HOME`, bundled examples; `scripts/wheel_check.py`).
* Storage schema is version 3; migrations add columns in place (v1 to v3 are implemented).
* The Streamlit server caches imported modules: after editing package code, restart the app.
* Importing DeepEval (tests, judge metrics) creates an empty `.deepeval/` folder in the working directory
  (ignored by `.gitignore`).
* The local run store keeps absolute file paths (exported bundles do not).
* Coverage measurement excludes `ui/views/*` (exercised by AppTest, which coverage cannot attribute reliably).

## Provider quotas

On Groq's free tier each model had a 200,000-token daily budget; a 10-case run with four judge metrics used most of one
model's budget, and later runs waited on `Retry-After` and then failed. `RAGWB_MAX_REQUESTS_PER_MINUTE` spaces
requests but cannot create quota. Retries wait at most 60 s per attempt, so a daily-quota reset (minutes to hours)
is not waited out.

## Local embeddings

Between BM25, local and hybrid-local retrieval there is no consistent winner on the bundled data (table in `docs/LIVE_VERIFICATION.md`):
local embeddings help paraphrased questions and hurt the main honeybee set. The model cache nests folders deeply and can exceed
Windows' 260-character path limit under a long data directory.

## Accessibility (automated checks and keyboard walks, not a full audit)

* **A first script** (five pages) found skipped heading levels (fixed: section headings are now h2) and muted text at 4.42:1
  (fixed: about 5.7:1 in the light theme and 10:1 in the dark theme, computed).
* **axe-core 4.10.2** (WCAG 2.0/2.1/2.2 A and AA plus best practices) found **no violations** on six page views (Overview,
  Run results summary, cases and case detail, Compare, Datasets, Settings) and **one minor issue** on New evaluation, inside
  Streamlit's own file-uploader component (`role="presentation"` on an element with a tab stop). It did not flag the white-on-blue
  slider values that the first script called 1.0:1, which supports that having been a false positive of that script.
* **Keyboard walks** of New evaluation, Run results and Settings found no trap and a logical order, and a working skip link. Run
  results returns to its start after 59 stops, 23 of them on zero-size grid cells; two focus indicators were checked visually.
* **Tables:** Streamlit draws data tables on a `<canvas>` and exposes a parallel grid structure (`gridcell` elements) to assistive
  technology, so they are not unreadable, but every cell is a Tab stop, which makes long tables tedious by keyboard; every table
  also has a CSV download. The built-in JSON viewer uses syntax colours below 4.5:1. Neither is fixable inside this project.
* **Not done:** a screen-reader pass; keyboard walks of Overview, Compare, Datasets and the Accounts page (axe-core covered them);
  zoom and reflow; the Accounts page was not audited by axe-core.

## Abstention tuning result

`ragwb tune-abstention` on the four bundled documents (51 development and 45 test questions, 12 unanswerable in the
test half) chose `min_evidence=0.8`. On the held-out half it declined 10 of 12 unanswerable questions but also 24 of
33 answerable ones (balanced accuracy 0.553 against 0.500 for never abstaining). That is a poor trade, so the default
stays at no abstention. The extractive baseline cannot tell an unanswerable question from a hard one by word overlap
alone; a real fix needs a model that judges whether the retrieved text answers the question.

## Future work (recommendations, not implemented)

1. Have a person label the supplied sheet (`calibration/volcanoes-labelling-sheet.csv`, 30 cases; an AI-rater version exists for
   comparison), run `ragwb calibrate --sweep` for `correctness` and the semantic metrics, and revisit the default thresholds with
   more cases and more than one document and labeller.
2. Run the live checks against OpenAI itself (API embeddings, hybrid with API embeddings, a stronger judge) and a provider without
   a tight free-tier token cap.
3. Build and test the Docker image.
4. A screen-reader pass (NVDA/VoiceOver) and a keyboard walk of the remaining pages; consider a table alternative with fewer Tab
   stops (for example paged HTML tables) if keyboard use is a requirement.
5. If the app is ever shared widely: SSO, MFA, an audit trail of run changes, and database-level (not only UI-level) separation.
6. A third-party security review before exposing it beyond a trusted network.
