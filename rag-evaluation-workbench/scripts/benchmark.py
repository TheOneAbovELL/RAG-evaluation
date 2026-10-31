"""Scale benchmark for the offline path: how long do runs, reads and exports take as the dataset grows?

    uv run python scripts/benchmark.py                 # 200, 1000 and 5000 cases, 1 worker
    uv run python scripts/benchmark.py --sizes 100 500 --workers 4

Questions are generated from the example document (a question per sentence, cycling), so no external data is used and
results are comparable between machines only in relative terms. Everything runs in a temporary data directory.
Reported per size: wall time of the run (and cases per second), time to read all case results back, time to build the
CSV export, and the size of the SQLite file. Python-level peak memory is measured in a second run under ``tracemalloc`` (it excludes memory allocated by C
extensions); that run's timings are discarded because the tracer slows Python code several-fold.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

from rag_workbench.config import load_settings
from rag_workbench.documents import load_chunks
from rag_workbench.logging_setup import close_logging
from rag_workbench.models import RunConfig
from rag_workbench.reporting import export_csv
from rag_workbench.services import open_context
from rag_workbench.text import split_sentences


def make_dataset(path: Path, size: int, document: Path) -> None:
    sentences = [s for chunk in load_chunks(document) for s in split_sentences(chunk.text)]
    with path.open("w", encoding="utf-8") as handle:
        for i in range(size):
            sentence = sentences[i % len(sentences)]
            words = sentence.split()
            question = "What about " + " ".join(words[: min(6, len(words))]).rstrip(".,;:") + "?"
            handle.write(json.dumps({"id": f"b{i:05d}", "question": question, "expected_answer": sentence,
                                     "metadata": {"bucket": str(i % 4)}}) + "\n")


def one_run(size: int, workers: int, *, measure_memory: bool) -> dict:
    with tempfile.TemporaryDirectory(prefix="ragwb-bench-", ignore_cleanup_errors=True) as tmp:
        base = load_settings()
        settings = base.model_copy(update={"data_dir": Path(tmp), "max_cases": max(size, 1)})
        dataset = Path(tmp) / "bench.jsonl"
        make_dataset(dataset, size, settings.default_document)
        ctx = open_context(settings, console_logging=False)
        config = RunConfig(name=f"bench-{size}", dataset_path=str(dataset), document_path=str(settings.default_document),
                           metrics=["token_f1", "rouge_l", "context_recall", "groundedness"], max_workers=workers)
        try:
            if measure_memory:
                tracemalloc.start()
            started = time.perf_counter()
            run = ctx.runner().run(config)
            run_s = time.perf_counter() - started
            peak = 0
            if measure_memory:
                _, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
            started = time.perf_counter()
            cases = ctx.store.get_case_results(run.id)
            read_s = time.perf_counter() - started
            started = time.perf_counter()
            export_csv(run, cases)
            export_s = time.perf_counter() - started
            return {"cases": size, "workers": workers, "status": run.status, "run_s": run_s, "cases_per_s": size / run_s,
                    "read_s": read_s, "csv_s": export_s, "peak_mb": peak / 1e6,
                    "db_mb": settings.db_path.stat().st_size / 1e6, "n_read": len(cases)}
        finally:
            close_logging()


def bench(size: int, workers: int) -> dict:
    """Timings from a run with no tracer; peak memory from a second run under ``tracemalloc`` (which slows Python code
    several-fold, so its timings are discarded)."""
    timed = one_run(size, workers, measure_memory=False)
    timed["peak_mb"] = one_run(size, workers, measure_memory=True)["peak_mb"]
    return timed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sizes", type=int, nargs="+", default=[200, 1000, 5000])
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args(argv)
    rows = [bench(size, args.workers) for size in args.sizes]
    print(f"{'cases':>6} {'workers':>7} {'status':>10} {'run s':>8} {'cases/s':>8} {'read s':>7} {'csv s':>6} "
          f"{'peak MB':>8} {'db MB':>6}")
    for r in rows:
        print(f"{r['cases']:>6} {r['workers']:>7} {r['status']:>10} {r['run_s']:>8.2f} {r['cases_per_s']:>8.1f} "
              f"{r['read_s']:>7.2f} {r['csv_s']:>6.2f} {r['peak_mb']:>8.1f} {r['db_mb']:>6.1f}")
    ok = all(r["status"] == "completed" and r["n_read"] == r["cases"] for r in rows)
    print("all runs completed and every case was read back" if ok else "FAILED: a run did not complete")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
