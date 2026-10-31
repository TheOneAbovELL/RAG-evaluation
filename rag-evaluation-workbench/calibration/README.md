# Calibrating the judge against a person

`volcanoes-labelling-sheet.csv` holds 30 answers produced by `qwen/qwen3.8-27b` for the bundled volcano questions, with the
reference answer, the lexical scores and the `correctness` judge's score for each. Nothing in it is a label.
`20261028-035657-qwen-volcanoes-30-b-7d604e.json` is the run itself, as a re-importable bundle (no keys inside).

1. Import the run into your run store (from the project folder):

   ```bash
   uv run ragwb import calibration/20261028-035657-qwen-volcanoes-30-b-7d604e.json
   ```

2. Open the CSV (UTF-8) and, for each row, read the question, the reference answer and the model's answer, then enter `pass`
   or `fail` in the `human_pass` column: would you accept the answer as correct given the reference? Leave a row blank if you
   cannot decide. Do not look at `correctness_score` first, or you will be calibrating the judge against itself.

3. Compare the judge with you:

   ```bash
   uv run ragwb calibrate 20261028-035657-qwen-volcanoes-30-b-7d604e --labels calibration/volcanoes-labelling-sheet.csv --metric correctness
   ```

The report gives agreement, Cohen's kappa and a confusion matrix against your labels. With about 30 labelled cases it is
still a rough estimate, and it describes this judge model, this rubric and this document only.

## Labels written by Claude (not human labels)

`volcanoes-labels-by-claude.csv` holds pass/fail labels for the same 30 answers, written by Claude, an AI model, at the
owner's request, before looking at any metric score. They are one rater's opinion and not a substitute for yours. To compare a
metric with them (the tool still calls the column `human_pass`):

```bash
uv run ragwb calibrate 20261028-035657-qwen-volcanoes-30-b-7d604e --labels calibration/volcanoes-labels-by-claude.csv --metric correctness
```

Result when this was done: the `correctness` judge agreed on 29 of 30 (kappa 0.870), token F1 on 18 of 30 (kappa 0.237);
see `docs/LIVE_VERIFICATION.md`, run 11, for the limits.
