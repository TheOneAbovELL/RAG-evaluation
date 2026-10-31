"""Evaluation dataset parsing and validation.

Accepted formats
----------------
* **JSONL** (``.jsonl``): one JSON object per line with ``question`` (required),
  ``expected_answer`` (optional), ``id`` (optional) and ``metadata`` (optional object).
  Blank lines are ignored.
* **CSV** (``.csv``): a header row containing at least ``question``; ``expected_answer`` and ``id``
  columns are optional. Other columns are collected into ``metadata``.

Validation never silently drops a row: every problem is reported with its line number. Errors
make the dataset unusable; warnings (e.g. duplicate questions, missing reference answers) do not.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

from .models import EvalCase

SUPPORTED_SUFFIXES = {".jsonl", ".csv"}
_KNOWN_FIELDS = {"id", "question", "expected_answer", "metadata"}


@dataclass
class DatasetIssue:
    line: int | None
    message: str

    def __str__(self) -> str:
        return f"line {self.line}: {self.message}" if self.line else self.message


@dataclass
class DatasetReport:
    """Result of parsing a dataset: the cases plus any errors and warnings."""

    name: str
    cases: list[EvalCase] = field(default_factory=list)
    errors: list[DatasetIssue] = field(default_factory=list)
    warnings: list[DatasetIssue] = field(default_factory=list)
    sha256: str = ""

    @property
    def ok(self) -> bool:
        return not self.errors and bool(self.cases)

    @property
    def n_with_reference(self) -> int:
        return sum(1 for c in self.cases if c.expected_answer)


class DatasetError(ValueError):
    """Raised by :func:`load_dataset` when the dataset has validation errors."""

    def __init__(self, report: DatasetReport):
        self.report = report
        shown = "; ".join(str(e) for e in report.errors[:5])
        more = f" (+{len(report.errors) - 5} more)" if len(report.errors) > 5 else ""
        super().__init__(f"Dataset {report.name!r} is invalid: {shown}{more}")


def parse_dataset(data: bytes, name: str, *, max_bytes: int = 5_000_000, max_cases: int = 5_000,
                  max_field_chars: int = 20_000) -> DatasetReport:
    """Parse raw dataset bytes. ``name`` (a filename) selects the format by its suffix."""
    report = DatasetReport(name=name, sha256=hashlib.sha256(data).hexdigest())
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        report.errors.append(DatasetIssue(None, f"unsupported file type {suffix!r}; use .jsonl or .csv"))
        return report
    if len(data) > max_bytes:
        report.errors.append(DatasetIssue(None, f"file is {len(data):,} bytes; the limit is {max_bytes:,}"))
        return report
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        report.errors.append(DatasetIssue(None, f"file is not valid UTF-8 ({exc.reason} at byte {exc.start})"))
        return report

    rows = _jsonl_rows(text, report) if suffix == ".jsonl" else _csv_rows(text, report)

    seen_ids: dict[str, int] = {}
    seen_questions: dict[str, int] = {}
    for line, row in rows:
        if len(report.cases) >= max_cases:
            report.errors.append(DatasetIssue(line, f"dataset exceeds the limit of {max_cases:,} cases"))
            break
        case = _row_to_case(row, line, len(report.cases) + 1, report, max_field_chars)
        if case is None:
            continue
        if case.id in seen_ids:
            report.errors.append(DatasetIssue(
                line, f"duplicate id {case.id!r} (first seen on line {seen_ids[case.id]})"))
            continue
        key = " ".join(case.question.lower().split())
        if key in seen_questions:
            report.warnings.append(DatasetIssue(line, f"duplicate question (also on line {seen_questions[key]})"))
        seen_ids[case.id] = line
        seen_questions.setdefault(key, line)
        report.cases.append(case)

    if not report.cases and not report.errors:
        report.errors.append(DatasetIssue(None, "dataset contains no cases"))
    missing_refs = len(report.cases) - report.n_with_reference
    if report.cases and missing_refs:
        report.warnings.append(DatasetIssue(
            None, f"{missing_refs} case(s) have no expected_answer; reference-based metrics will be skipped for them"))
    return report


def load_dataset(path: str | Path, **limits: int) -> list[EvalCase]:
    """Load and validate a dataset file, raising :class:`DatasetError` on any error."""
    report = validate_file(path, **limits)
    if not report.ok:
        raise DatasetError(report)
    return report.cases


def validate_file(path: str | Path, **limits: int) -> DatasetReport:
    path = Path(path)
    if not path.is_file():
        report = DatasetReport(name=path.name)
        report.errors.append(DatasetIssue(None, f"file not found: {path}"))
        return report
    max_bytes = limits.get("max_bytes", 5_000_000)
    if path.stat().st_size > max_bytes:
        report = DatasetReport(name=path.name)
        report.errors.append(DatasetIssue(None, f"file is {path.stat().st_size:,} bytes; the limit is {max_bytes:,}"))
        return report
    return parse_dataset(path.read_bytes(), path.name, **limits)


def _jsonl_rows(text: str, report: DatasetReport) -> list[tuple[int, dict]]:
    rows = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            report.errors.append(DatasetIssue(line_no, f"invalid JSON ({exc.msg} at column {exc.colno})"))
            continue
        if not isinstance(obj, dict):
            report.errors.append(DatasetIssue(line_no, f"expected a JSON object, got {type(obj).__name__}"))
            continue
        rows.append((line_no, obj))
    return rows


def _csv_rows(text: str, report: DatasetReport) -> list[tuple[int, dict]]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "question" not in [f.strip() for f in reader.fieldnames]:
        report.errors.append(DatasetIssue(1, "CSV header must include a 'question' column"))
        return []
    rows = []
    for row in reader:
        clean = {(k or "").strip(): v for k, v in row.items() if k is not None}
        metadata = {k: v for k, v in clean.items() if k not in _KNOWN_FIELDS and v not in (None, "")}
        record = {k: v for k, v in clean.items() if k in _KNOWN_FIELDS}
        if metadata:
            record["metadata"] = metadata
        rows.append((reader.line_num, record))
    return rows


def _row_to_case(row: dict, line: int, position: int, report: DatasetReport,
                 max_field_chars: int) -> EvalCase | None:
    question = row.get("question")
    if not isinstance(question, str) or not question.strip():
        report.errors.append(DatasetIssue(line, "missing or empty 'question'"))
        return None
    expected = row.get("expected_answer")
    if expected is not None and not isinstance(expected, str):
        report.errors.append(DatasetIssue(line, "'expected_answer' must be a string"))
        return None
    if isinstance(expected, str) and not expected.strip():
        expected = None
    for field_name, value in (("question", question), ("expected_answer", expected)):
        if value and len(value) > max_field_chars:
            report.errors.append(DatasetIssue(
                line, f"'{field_name}' is {len(value):,} characters; the limit is {max_field_chars:,}"))
            return None
    raw_id = row.get("id")
    if raw_id is None or str(raw_id).strip() == "":
        case_id = f"case-{position:03d}"
    elif isinstance(raw_id, (str, int)) and not isinstance(raw_id, bool):
        case_id = str(raw_id).strip()
    else:
        report.errors.append(DatasetIssue(line, "'id' must be a string or integer"))
        return None
    metadata = row.get("metadata") or {}
    if not isinstance(metadata, dict):
        report.errors.append(DatasetIssue(line, "'metadata' must be a JSON object"))
        return None
    unknown = set(row) - _KNOWN_FIELDS
    if unknown:
        report.warnings.append(DatasetIssue(line, f"ignored unknown field(s): {', '.join(sorted(unknown))}"))
    return EvalCase(id=case_id, question=question.strip(),
                    expected_answer=expected.strip() if expected else None, metadata=metadata)
