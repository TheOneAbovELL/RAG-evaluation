"""Live smoke test of the OpenAI and DeepEval paths. THIS MAKES PAID API CALLS.

    uv run python scripts/live_smoke.py --yes-spend            # 3 cases, GPT answers + embeddings + 4 judge metrics
    uv run python scripts/live_smoke.py --yes-spend --cases 2 --skip-judge

It exists because the OpenAI/DeepEval code paths are otherwise tested only with fakes. It runs a tiny evaluation in
a temporary data directory (your run store is untouched) and checks what a fake cannot: that the real clients accept
our parameters, that answers/embeddings/judge scores come back in the expected shape, that token usage and judge
cost are reported, and that every case finishes. It prints a verdict and exits 0 only if everything passed.

Safety: it refuses to run without ``--yes-spend`` and a configured ``OPENAI_API_KEY``; it caps the dataset at 5 cases;
it never prints the key. Rough scale of a default run: 3 answer calls, a handful of embedding calls and about
5-10 judge calls per case (the judge metrics each make several requests), i.e. well under a dollar with gpt-4o-class
models at the time of writing; check your provider's current pricing.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "1")

MAX_CASES = 5


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--yes-spend", action="store_true", help="acknowledge that this makes paid API calls")
    parser.add_argument("--cases", type=int, default=3, help=f"number of dataset cases (1-{MAX_CASES}, default 3)")
    parser.add_argument("--skip-judge", action="store_true", help="skip the four DeepEval judge metrics (cheaper)")
    parser.add_argument("--pipeline", choices=["rag", "agent"], default="rag")
    parser.add_argument("--retriever", choices=["bm25", "embedding", "hybrid", "local", "hybrid-local"],
                        default="embedding")
    args = parser.parse_args(argv)

    if not args.yes_spend:
        print("refusing to run: this makes paid OpenAI API calls. Re-run with --yes-spend to proceed.",
              file=sys.stderr)
        return 2
    if not 1 <= args.cases <= MAX_CASES:
        print(f"--cases must be between 1 and {MAX_CASES}", file=sys.stderr)
        return 2

    from rag_workbench.config import load_settings
    from rag_workbench.logging_setup import close_logging
    from rag_workbench.metrics import DEFAULT_JUDGE_METRICS
    from rag_workbench.models import RunConfig
    from rag_workbench.services import open_context

    base = load_settings()
    if not base.has_openai_key:
        print("refusing to run: OPENAI_API_KEY is not set (put it in .env or the environment).", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="ragwb-live-", ignore_cleanup_errors=True) as tmp:
        settings = base.model_copy(update={"data_dir": Path(tmp)})
        ctx = open_context(settings, console_logging=False)
        metrics = ["token_f1", "context_recall", "groundedness"] + ([] if args.skip_judge else DEFAULT_JUDGE_METRICS)
        config = RunConfig(
            name="live-smoke", dataset_path=str(settings.default_dataset), document_path=str(settings.default_document),
            provider="openai", pipeline=args.pipeline, retriever=args.retriever, k=3, metrics=metrics,
            limit=args.cases, max_workers=1, generator_model=settings.generator_model,
            judge_model=None if args.skip_judge else settings.judge_model,
            embedding_model=None if args.retriever == "bm25" else settings.embedding_model,
            request_timeout_s=settings.request_timeout_s, max_retries=settings.max_retries,
            case_timeout_s=settings.case_timeout_s)
        print(f"Running {args.cases} case(s): pipeline={args.pipeline}, retriever={args.retriever}, "
              f"generator={settings.generator_model}, judge={'-' if args.skip_judge else settings.judge_model}")
        try:
            run = ctx.runner().run(config, progress=lambda p: print(f"  [{p.done}/{p.total}] {p.case_id} {p.status}"))
            cases = ctx.store.get_case_results(run.id)
        finally:
            close_logging()  # release the log file so the temporary directory can be removed on Windows

    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))

    summary = run.summary
    ok_cases = [c for c in cases if c.status == "ok"]
    # Every check below requires at least one successful case: all([]) is True, which would "pass" an empty run.
    check("at least one case succeeded", bool(ok_cases), f"{len(ok_cases)}/{len(cases)} cases ok")
    check("every case produced an answer", len(ok_cases) == len(cases) and bool(cases),
          "; ".join(f"{c.case_id}: {c.error}" for c in cases if c.status == "error"))
    check("answers are non-empty text", bool(ok_cases) and all((c.answer or "").strip() for c in ok_cases))
    check("retrieved context was recorded", bool(ok_cases) and all(c.contexts for c in ok_cases))
    check("token usage was reported", summary is not None and summary.total_prompt_tokens is not None,
          f"in={getattr(summary, 'total_prompt_tokens', None)} out={getattr(summary, 'total_completion_tokens', None)}")
    for name in metrics:
        scored = [c.metrics[name] for c in ok_cases if name in c.metrics and c.metrics[name].status == "ok"]
        errors = [c.metrics[name].reason for c in ok_cases if name in c.metrics and c.metrics[name].status == "error"]
        check(f"metric {name} scored every case", bool(ok_cases) and len(scored) == len(ok_cases),
              f"{len(scored)} scored" + (f"; errors: {errors[:1]}" if errors else ""))
    if not args.skip_judge and summary is not None:
        print(f"judge cost reported by DeepEval: {summary.total_judge_cost_usd}")
    failed = [name for name, ok, _ in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed" + (f"; failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
