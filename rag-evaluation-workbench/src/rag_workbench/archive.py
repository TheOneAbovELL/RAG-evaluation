"""Run bundles: a single JSON file holding one run and all its case results.

``reporting.export_json`` writes bundles; this module validates and imports them, so runs can be
shared between machines or kept as reference results. Importing never executes anything: the file
is parsed as JSON and validated against the pydantic models before a single row is written.

Imported runs get status ``imported``; the status they had when exported is kept in
``config["original_status"]``. Command line: ``ragwb import <bundle.json> ...``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from .aggregate import summarize_run
from .models import CaseResult, RunRecord
from .storage import RunStore, StorageError

log = logging.getLogger(__name__)

BUNDLE_FORMAT = "rag-workbench-run"
BUNDLE_VERSION = 1
MAX_BUNDLE_BYTES = 50_000_000


class BundleError(ValueError):
    """The file is not a valid run bundle."""


def load_bundle(path: str | Path, *, max_bytes: int = MAX_BUNDLE_BYTES) -> tuple[RunRecord, list[CaseResult]]:
    path = Path(path)
    if not path.is_file():
        raise BundleError(f"Bundle not found: {path}")
    if path.stat().st_size > max_bytes:
        raise BundleError(f"{path.name} is larger than {max_bytes:,} bytes")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"{path.name} is not valid UTF-8 JSON: {exc}") from None
    if not isinstance(payload, dict) or payload.get("format") != BUNDLE_FORMAT:
        raise BundleError(f"{path.name} is not a {BUNDLE_FORMAT!r} bundle")
    if payload.get("version") != BUNDLE_VERSION:
        raise BundleError(f"{path.name} has unsupported bundle version {payload.get('version')!r}")
    try:
        run = RunRecord.model_validate(payload["run"])
        cases = [CaseResult.model_validate(c) for c in payload.get("cases", [])]
    except (KeyError, ValidationError) as exc:
        raise BundleError(f"{path.name} failed validation: {str(exc)[:500]}") from None
    ids = [c.case_id for c in cases]
    if len(set(ids)) != len(ids):
        raise BundleError(f"{path.name} contains duplicate case ids")
    return run, cases


def import_bundle(store: RunStore, path: str | Path) -> str | None:
    """Import one bundle. Returns the run id, or ``None`` if a run with that id already exists."""
    run, cases = load_bundle(path)
    if store.get_run(run.id) is not None:
        log.info("Run %s already present; bundle %s skipped", run.id, Path(path).name)
        return None
    config = {**run.config, "original_status": run.config.get("original_status", run.status),
              "imported_from": Path(path).name}
    # The summary shown for an imported run is recomputed from its cases, never taken from the file.
    metric_names = list(config.get("metrics") or (run.summary.metrics if run.summary else []))
    thresholds = config.get("thresholds") or {}
    summary = summarize_run(cases, metric_names, {m: thresholds.get(m) for m in metric_names})
    record = run.model_copy(update={"status": "imported", "config": config, "n_cases": len(cases),
                                    "summary": summary})
    store.create_run(record)
    try:
        for case in cases:
            store.add_case_result(run.id, case)
    except StorageError:
        store.delete_run(run.id)  # all or nothing
        raise
    log.info("Imported run %s (%d cases) from %s", run.id, len(cases), Path(path).name)
    return run.id

