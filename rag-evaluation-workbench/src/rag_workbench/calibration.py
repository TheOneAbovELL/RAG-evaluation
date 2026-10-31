"""Calibrating a metric against human judgement.

A judge metric (or any metric with a pass threshold) is an opinion; whether to trust it is an empirical question.
This module compares a metric's pass/fail verdicts on a run with human pass/fail labels for the same cases and
reports agreement: accuracy, Cohen's kappa (agreement beyond chance), and the confusion matrix with the human label
as the reference.

Workflow::

    ragwb labels-template RUN_ID --out sheet.csv     # one row per case, with a blank human_pass column
    (a person fills human_pass with pass/fail)
    ragwb calibrate RUN_ID --labels sheet.csv --metric correctness

Limits to keep in mind: kappa is unstable on small samples (fewer than :data:`MIN_RELIABLE_N` labelled cases is
flagged), it depends on the pass rate (a skewed sample gives a low kappa even for good agreement), and one run,
one dataset and one judge model say nothing about other settings.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path

from .models import CaseResult, RunRecord

MIN_RELIABLE_N = 30
MAX_LABEL_FILE_BYTES = 5_000_000
_TRUE = {"1", "true", "t", "yes", "y", "pass", "passed", "ok", "correct"}
_FALSE = {"0", "false", "f", "no", "n", "fail", "failed", "incorrect", "wrong"}
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class LabelsError(ValueError):
    """The labels file is missing, unreadable or malformed."""


def parse_label(value: object) -> bool | None:
    """True/False for recognised pass/fail spellings, None for blank. Raises ValueError for anything else."""
    if isinstance(value, bool):
        return value
    text = str(value if value is not None else "").strip().lower()
    if not text:
        return None
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    raise ValueError(f"unrecognised label {value!r} (use pass/fail, true/false, yes/no or 1/0)")


def load_labels(path: str | Path) -> dict[str, bool]:
    """Read human labels from CSV (``case_id,human_pass``) or JSONL (``{"case_id":..., "human_pass":...}``).

    Blank labels are skipped (the case counts as unlabelled). Duplicate ids, missing columns, unknown values and
    oversize files raise :class:`LabelsError` with the offending line.
    """
    path = Path(path)
    if not path.is_file():
        raise LabelsError(f"Labels file not found: {path}")
    if path.stat().st_size > MAX_LABEL_FILE_BYTES:
        raise LabelsError(f"{path.name} is larger than {MAX_LABEL_FILE_BYTES:,} bytes")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise LabelsError(f"{path.name} is not valid UTF-8") from exc
    if path.suffix.lower() == ".jsonl":
        rows = _jsonl_rows(text, path.name)
    elif path.suffix.lower() == ".csv":
        rows = _csv_rows(text, path.name)
    else:
        raise LabelsError(f"Unsupported labels file type {path.suffix!r}; use .csv or .jsonl")
    labels: dict[str, bool] = {}
    for line, row in rows:
        case_id = str(row.get("case_id", "")).strip()
        if not case_id:
            raise LabelsError(f"{path.name} line {line}: missing case_id")
        try:
            label = parse_label(row.get("human_pass"))
        except ValueError as exc:
            raise LabelsError(f"{path.name} line {line}: {exc}") from None
        if case_id in labels:
            raise LabelsError(f"{path.name} line {line}: duplicate case_id {case_id!r}")
        if label is not None:
            labels[case_id] = label
    return labels


def _csv_rows(text: str, name: str) -> list[tuple[int, dict]]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or not {"case_id", "human_pass"} <= {f.strip() for f in reader.fieldnames}:
        raise LabelsError(f"{name}: the header must contain case_id and human_pass columns")
    return [(reader.line_num, {(k or "").strip(): v for k, v in row.items()}) for row in reader]


def _jsonl_rows(text: str, name: str) -> list[tuple[int, dict]]:
    rows = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LabelsError(f"{name} line {number}: invalid JSON ({exc.msg})") from None
        if not isinstance(row, dict):
            raise LabelsError(f"{name} line {number}: expected a JSON object")
        rows.append((number, row))
    return rows


@dataclass(frozen=True)
class Agreement:
    metric: str
    n_compared: int
    n_labelled: int  # labels supplied for cases of this run
    n_unscored: int  # labelled cases the metric did not score (skipped/error/failed case)
    n_unknown: int  # label ids that match no case of the run
    tp: int  # metric pass, human pass
    fp: int  # metric pass, human fail
    fn: int  # metric fail, human pass
    tn: int  # metric fail, human fail

    @property
    def accuracy(self) -> float | None:
        return (self.tp + self.tn) / self.n_compared if self.n_compared else None

    @property
    def human_pass_rate(self) -> float | None:
        return (self.tp + self.fn) / self.n_compared if self.n_compared else None

    @property
    def metric_pass_rate(self) -> float | None:
        return (self.tp + self.fp) / self.n_compared if self.n_compared else None

    @property
    def precision(self) -> float | None:
        """Of the cases the metric passed, the share humans also passed."""
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else None

    @property
    def recall(self) -> float | None:
        """Of the cases humans passed, the share the metric also passed."""
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else None

    @property
    def kappa(self) -> float | None:
        return cohen_kappa(self.tp, self.fp, self.fn, self.tn)

    @property
    def small_sample(self) -> bool:
        return self.n_compared < MIN_RELIABLE_N


def cohen_kappa(tp: int, fp: int, fn: int, tn: int) -> float | None:
    """Cohen's kappa for two binary raters; ``None`` when undefined (no cases, or both raters constant)."""
    n = tp + fp + fn + tn
    if n == 0:
        return None
    observed = (tp + tn) / n
    expected = ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / (n * n)
    if expected == 1.0:
        return None
    return (observed - expected) / (1 - expected)


def interpret_kappa(kappa: float | None) -> str:
    """Landis & Koch (1977) verbal bands. Conventional labels, not a validity test."""
    if kappa is None:
        return "undefined"
    for bound, label in ((0.0, "poor (worse than chance)"), (0.2, "slight"), (0.4, "fair"), (0.6, "moderate"),
                         (0.8, "substantial")):
        if kappa < bound or (bound == 0.0 and kappa <= 0.0):
            return label
    return "almost perfect"


def calibrate(results: list[CaseResult], labels: dict[str, bool], metric: str) -> Agreement:
    """Compare ``metric``'s pass/fail verdicts with ``labels`` over the cases of a run."""
    by_id = {r.case_id: r for r in results}
    tp = fp = fn = tn = unscored = 0
    for case_id, human in labels.items():
        case = by_id.get(case_id)
        result = case.metrics.get(metric) if case else None
        if result is None or result.status != "ok" or result.passed is None:
            if case is not None:
                unscored += 1
            continue
        if result.passed and human:
            tp += 1
        elif result.passed and not human:
            fp += 1
        elif not result.passed and human:
            fn += 1
        else:
            tn += 1
    return Agreement(metric=metric, n_compared=tp + fp + fn + tn, n_labelled=sum(1 for c in labels if c in by_id),
                     n_unscored=unscored, n_unknown=sum(1 for c in labels if c not in by_id), tp=tp, fp=fp, fn=fn,
                     tn=tn)


DEFAULT_SWEEP = tuple(round(0.05 * i, 2) for i in range(2, 20))  # 0.10 ... 0.95


def sweep_thresholds(results: list[CaseResult], labels: dict[str, bool], metric: str,
                     thresholds: tuple[float, ...] = DEFAULT_SWEEP) -> list[tuple[float, Agreement]]:
    """Agreement with ``labels`` at each candidate pass threshold, using the stored scores of ``metric``.

    A case passes at threshold ``t`` when its score is at least ``t``; cases the metric did not score are left out,
    exactly as in :func:`calibrate`. The result is a table, not a recommendation: see :func:`best_threshold` for its
    limits.
    """
    by_id = {r.case_id: r for r in results}
    scored: list[tuple[float, bool]] = []
    unscored = unknown = 0
    for case_id, human in labels.items():
        case = by_id.get(case_id)
        if case is None:
            unknown += 1
            continue
        result = case.metrics.get(metric)
        if result is None or result.status != "ok" or result.score is None:
            unscored += 1
            continue
        scored.append((result.score, human))
    rows = []
    for t in thresholds:
        tp = sum(1 for s, h in scored if s >= t - 1e-9 and h)
        fp = sum(1 for s, h in scored if s >= t - 1e-9 and not h)
        fn = sum(1 for s, h in scored if s < t - 1e-9 and h)
        tn = sum(1 for s, h in scored if s < t - 1e-9 and not h)
        rows.append((t, Agreement(metric=metric, n_compared=len(scored), n_labelled=len(scored) + unscored,
                                  n_unscored=unscored, n_unknown=unknown, tp=tp, fp=fp, fn=fn, tn=tn)))
    return rows


def best_threshold(rows: list[tuple[float, Agreement]]) -> float | None:
    """The threshold with the highest kappa (ties: higher accuracy, then the lower threshold). ``None`` if undefined.

    Chosen on the same labels it is measured on, so its agreement is optimistic, and with a few dozen labels several
    thresholds usually tie: treat it as a starting point to confirm on new labels, not a calibrated value.
    """
    candidates = [(a.kappa, a.accuracy or 0.0, -t, t) for t, a in rows if a.kappa is not None]
    return max(candidates)[3] if candidates else None


def labelling_sheet(run: RunRecord, results: list[CaseResult]) -> bytes:
    """A CSV for human labelling: the evidence for each case plus an empty ``human_pass`` column."""
    metrics = list(run.summary.metrics) if run.summary else sorted({m for r in results for m in r.metrics})
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["case_id", "question", "expected_answer", "answer", *[f"{m}_score" for m in metrics],
                     "human_pass", "note"])
    for r in results:
        cells = [r.case_id, r.question, r.expected_answer or "", r.answer or r.error or ""]
        cells += ["" if r.score(m) is None else f"{r.score(m):.3f}" for m in metrics]
        cells = [("'" + c) if isinstance(c, str) and c.startswith(_FORMULA_PREFIXES) else c for c in cells]
        writer.writerow([*cells, "", ""])
    return buffer.getvalue().encode("utf-8-sig")
