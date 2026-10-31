"""Tabular views and exports (CSV, JSON, Markdown) of runs and comparisons."""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pandas as pd

from .aggregate import paired_comparison
from .config import PROJECT_ROOT
from .metrics import METRIC_SPECS
from .models import CaseResult, RunRecord

EXPORT_FORMATS = ("csv", "json", "md")
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def metric_label(name: str) -> str:
    spec = METRIC_SPECS.get(name)
    return spec.label if spec else name.replace("_", " ").title()


def run_metrics(run: RunRecord) -> list[str]:
    return list(run.config.get("metrics") or (run.summary.metrics.keys() if run.summary else []))


def cases_dataframe(run: RunRecord, results: list[CaseResult]) -> pd.DataFrame:
    """One row per case with per-metric score/pass columns."""
    metrics = run_metrics(run)
    rows = []
    for r in results:
        row = {
            "position": r.position, "case_id": r.case_id, "status": r.status, "question": r.question,
            "expected_answer": r.expected_answer, "answer": r.answer, "error": r.error,
            "latency_ms": r.latency_ms, "prompt_tokens": r.prompt_tokens, "completion_tokens": r.completion_tokens,
            "cost_usd": r.cost_usd, "attempts": r.attempts, "n_contexts": len(r.contexts),
            "context_ids": ", ".join(c.chunk_id for c in r.contexts),
        }
        for key, value in r.metadata.items():
            row[f"meta_{key}"] = value if isinstance(value, str | int | float | bool) else json.dumps(value)
        for m in metrics:
            res = r.metrics.get(m)
            row[m] = res.score if res else None
            row[f"{m}_passed"] = res.passed if res else None
            row[f"{m}_status"] = res.status if res else None
        rows.append(row)
    return pd.DataFrame(rows)


def summary_dataframe(runs: list[RunRecord]) -> pd.DataFrame:
    """One row per run: identity, configuration essentials and metric means."""
    rows = []
    for run in runs:
        cfg = run.config
        row = {
            "run_id": run.id, "name": run.name, "status": run.status, "created_at": run.created_at,
            "provider": cfg.get("provider"), "pipeline": cfg.get("pipeline"), "retriever": cfg.get("retriever"),
            "k": cfg.get("k"), "generator_model": cfg.get("generator_model"), "n_cases": run.n_cases,
            "n_errors": run.summary.n_error if run.summary else None,
            "mean_latency_ms": run.summary.mean_latency_ms if run.summary else None,
        }
        if run.summary:
            for name, ms in run.summary.metrics.items():
                row[name] = ms.mean
        rows.append(row)
    return pd.DataFrame(rows)


def comparison_dataframe(run_a: RunRecord, results_a: list[CaseResult], run_b: RunRecord,
                         results_b: list[CaseResult]) -> pd.DataFrame:
    shared = [m for m in run_metrics(run_a) if m in run_metrics(run_b)]
    rows = []
    for m in shared:
        c = paired_comparison(results_a, results_b, m)
        rows.append({"metric": m, "label": metric_label(m), "paired_cases": c.n_pairs, "mean_a": c.mean_a,
                     "mean_b": c.mean_b, "diff_b_minus_a": c.mean_diff, "ci_low": c.ci_low, "ci_high": c.ci_high,
                     "b_better": c.wins, "ties": c.ties, "b_worse": c.losses,
                     "ci_excludes_zero": c.significant})
    return pd.DataFrame(rows)


def _csv_safe(value):
    """Neutralise spreadsheet formula injection in exported text cells."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def export_csv(run: RunRecord, results: list[CaseResult]) -> bytes:
    df = cases_dataframe(run, results)
    for column in df.columns:
        # Check every column: pandas 3 stores text with a dedicated "str" dtype, not object.
        if not pd.api.types.is_numeric_dtype(df[column]) and not pd.api.types.is_bool_dtype(df[column]):
            df[column] = df[column].map(_csv_safe)
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8-sig")  # BOM so Excel detects UTF-8


def portable_path(path: str) -> str:
    """Path relative to the project root when inside it, otherwise just the file name."""
    p = Path(path)
    if not p.is_absolute():
        return p.as_posix()
    try:
        return p.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return p.name


def export_json(run: RunRecord, results: list[CaseResult]) -> bytes:
    """A run bundle: re-importable with ``ragwb import`` (see :mod:`rag_workbench.archive`)."""
    from .archive import BUNDLE_FORMAT, BUNDLE_VERSION

    run_data = run.model_dump(mode="json")
    # Bundles are meant to be shared: never embed absolute local paths (they reveal user names and folders).
    for key in ("dataset_path", "document_path"):
        if run_data["config"].get(key):
            run_data["config"][key] = portable_path(run_data["config"][key])
    payload = {"format": BUNDLE_FORMAT, "version": BUNDLE_VERSION, "run": run_data,
               "cases": [r.model_dump(mode="json") for r in results]}
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def _fmt(value, digits: int = 3) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _md_cell(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def export_markdown(run: RunRecord, results: list[CaseResult], *, worst: int = 5) -> str:
    cfg = run.config
    lines = [f"# Evaluation report: {run.name}", "",
             f"* Run id: `{run.id}`", f"* Status: **{run.status}**",
             f"* Created: {run.created_at.isoformat(timespec='seconds')}",
             f"* Provider / pipeline / retriever: {cfg.get('provider')} / {cfg.get('pipeline')} / "
             f"{cfg.get('retriever')}",
             f"* k: {cfg.get('k')}  ·  generator: {cfg.get('generator_model')}  ·  judge: {cfg.get('judge_model')}",
             f"* Dataset: `{Path(str(cfg.get('dataset_path', ''))).name}` (sha256 `{(run.dataset_sha256 or '')[:12]}`)",
             f"* Document: `{Path(str(cfg.get('document_path', ''))).name}` "
             f"(sha256 `{(run.document_sha256 or '')[:12]}`)",
             ""]
    for warning in cfg.get("provenance_warnings") or []:
        lines.append(f"> **Provenance warning:** {warning}")
    if cfg.get("provenance_warnings"):
        lines.append("")
    if run.summary:
        s = run.summary
        lines += ["## Summary", "", f"Cases: {s.n_cases} · succeeded: {s.n_ok} · errors: {s.n_error}"
                  f" · mean latency: {_fmt(s.mean_latency_ms, 1)} ms · p95: {_fmt(s.p95_latency_ms, 1)} ms"
                  f" · tokens in/out: {_fmt(s.total_prompt_tokens)}/{_fmt(s.total_completion_tokens)}"
                  f" · cost: {_fmt(s.total_cost_usd, 4)} USD", "",
                  "| Metric | Mean | 95% CI | Median | Pass rate | Threshold | Scored | Skipped | Errors |",
                  "|---|---:|---|---:|---:|---:|---:|---:|---:|"]
        for name, m in s.metrics.items():
            ci = f"{_fmt(m.ci_low)}–{_fmt(m.ci_high)}" if m.ci_low is not None else "—"
            rate = f"{m.pass_rate:.0%}" if m.pass_rate is not None else "—"
            lines.append(f"| {metric_label(name)} | {_fmt(m.mean)} | {ci} | {_fmt(m.median)} | {rate} | "
                         f"{_fmt(m.threshold, 2)} | {m.n_scored} | {m.n_skipped} | {m.n_error} |")
        lines.append("")
    errors = [r for r in results if r.status == "error"]
    if errors:
        lines += ["## Failed cases", "", "| Case | Error |", "|---|---|"]
        lines += [f"| {_md_cell(r.case_id)} | {_md_cell(r.error)} |" for r in errors]
        lines.append("")
    for name in run_metrics(run):
        scored = sorted((r for r in results if r.score(name) is not None), key=lambda r: r.score(name) or 0.0)[:worst]
        if not scored:
            continue
        lines += [f"## Lowest {metric_label(name)}", "", "| Case | Score | Question | Reason |", "|---|---:|---|---|"]
        lines += [f"| {_md_cell(r.case_id)} | {r.score(name):.3f} | {_md_cell(r.question)} | "
                  f"{_md_cell((r.metrics[name].reason or '')[:200])} |" for r in scored]
        lines.append("")
    lines.append("_Generated by rag_workbench. Judge-model scores are model assessments, not ground truth; "
                 "lexical scores measure word overlap, not meaning._")
    return "\n".join(lines) + "\n"


def export_run(run: RunRecord, results: list[CaseResult], fmt: str) -> bytes:
    if fmt == "csv":
        return export_csv(run, results)
    if fmt == "json":
        return export_json(run, results)
    if fmt == "md":
        return export_markdown(run, results).encode("utf-8")
    raise ValueError(f"Unknown export format {fmt!r}; choose from {EXPORT_FORMATS}")


def safe_filename(text: str) -> str:
    """Filesystem-safe name: no path separators, no traversal, bounded length."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._") or "export"
    return cleaned[:100]


def write_export(run: RunRecord, results: list[CaseResult], fmt: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{safe_filename(run.id)}.{fmt}"
    path.write_bytes(export_run(run, results, fmt))
    return path
