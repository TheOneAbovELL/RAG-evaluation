"""Example runs over the bundled honeybee data (offline: no network, no API key).

Used by ``start.py`` on first launch (so the app opens with real results to explore) and by
``scripts/seed_demo_runs.py``. Every run is a genuine offline evaluation; rerunning reproduces the same scores.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .config import EXAMPLES_DIR
from .metrics import DEFAULT_OFFLINE_METRICS
from .models import RunConfig, RunRecord
from .services import AppContext


def _config(name: str, *, dataset: Path, document: Path, notes: str, k: int = 3,
            metrics: Sequence[str] = DEFAULT_OFFLINE_METRICS, failure_rate: float = 0.0) -> RunConfig:
    return RunConfig(name=name, dataset_path=str(dataset), document_path=str(document), k=k, notes=notes,
                     metrics=list(metrics), offline_failure_rate=failure_rate)


def demo_configs(project_root: Path, dataset: Path, document: Path) -> dict[str, RunConfig]:
    unanswerable = EXAMPLES_DIR / "datasets" / "honeybees_unanswerable.jsonl"
    return {
        "k1": _config("offline-bm25-k1", dataset=dataset, document=document, k=1,
                      notes="Example: retrieval depth 1"),
        "k3": _config("offline-bm25-k3", dataset=dataset, document=document,
                      notes="Example: default retrieval depth"),
        "k5": _config("offline-bm25-k5", dataset=dataset, document=document, k=5,
                      notes="Example: retrieval depth 5"),
        "unanswerable": _config(
            "unanswerable-k3", dataset=unanswerable, document=document,
            metrics=["exact_match", "token_f1", "context_recall", "groundedness"],
            notes="Example: questions the document cannot answer (abstention behaviour)"),
        "failures": _config("injected-failures-30pct", dataset=dataset, document=document, failure_rate=0.3,
                            notes="Example: deterministic injected provider failures"),
    }


def seed_demo_runs(ctx: AppContext) -> dict[str, RunRecord]:
    """Run every example configuration and return the stored runs by key."""
    s = ctx.settings
    runner = ctx.runner()
    return {key: runner.run(config)
            for key, config in demo_configs(s.project_root, s.default_dataset, s.default_document).items()}
