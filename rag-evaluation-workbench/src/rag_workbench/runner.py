"""Evaluation orchestration: dataset → pipeline → metrics → persisted run.

Lifecycle of a run
------------------
1. **Prepare** (no side effects): validate metric names, load and validate the dataset, load the
   document, build the pipeline and metrics. Any problem raises before a run row is created.
2. **Create** a ``running`` run row with the full configuration, dataset/document hashes and
   environment versions.
3. **Execute** cases sequentially or on a thread pool. Each case: generate (with retry on transient
   provider errors, exponential back-off), then score every metric. A failing case is recorded with
   its error and the run continues. Each finished case is committed immediately.
4. **Finish**: aggregate, then mark the run ``completed`` (no case errors), ``partial`` (some),
   ``failed`` (all cases errored) or ``cancelled`` (stopped by the caller).
"""

from __future__ import annotations

import logging
import platform
import re
import sys
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from . import __version__
from .aggregate import summarize_run
from .config import ConfigError, Settings
from .datasets import load_dataset
from .documents import file_sha256, load_chunks
from .errors import ProviderError, TransientProviderError, backoff_delay
from .metrics import METRIC_SPECS, Metric, MetricInput, build_metrics, validate_metric_names
from .models import CaseResult, EvalCase, Generation, RunConfig, RunRecord, RunStatus, utcnow
from .pipeline import Pipeline, build_pipeline
from .ratelimit import limiter_for
from .storage import RunStore, StorageError

log = logging.getLogger(__name__)

_TRACKED_PACKAGES = ("deepeval", "langchain", "langchain-openai", "openai", "pymupdf", "streamlit", "pydantic")


@dataclass
class Progress:
    done: int
    total: int
    case_id: str
    status: str
    message: str


ProgressCallback = Callable[[Progress], None]


@dataclass
class PreparedRun:
    config: RunConfig
    cases: list[EvalCase]
    pipeline: Pipeline
    metrics: list[Metric]
    thresholds: dict[str, float]
    dataset_sha256: str
    document_sha256: str


class EvaluationRunner:
    def __init__(self, settings: Settings, store: RunStore, *,
                 pipeline_factory: Callable[..., Pipeline] = build_pipeline,
                 metrics_factory: Callable[..., list[Metric]] = build_metrics,
                 sleep: Callable[[float], None] = time.sleep):
        self.settings = settings
        self.store = store
        self._pipeline_factory = pipeline_factory
        self._metrics_factory = metrics_factory
        self._sleep = sleep

    # ------------------------------------------------------------------ prepare
    def prepare(self, config: RunConfig) -> PreparedRun:
        validate_metric_names(config.metrics, self.settings)
        bad_thresholds = {k: v for k, v in config.thresholds.items() if k not in METRIC_SPECS or not 0 <= v <= 1}
        if bad_thresholds:
            raise ConfigError(f"Invalid threshold(s): {bad_thresholds}; thresholds must be in [0, 1] for known metrics")
        dataset_path, document_path = Path(config.dataset_path), Path(config.document_path)
        cases = load_dataset(dataset_path, max_bytes=self.settings.max_dataset_bytes,
                             max_cases=self.settings.max_cases, max_field_chars=self.settings.max_field_chars)
        if config.limit:
            cases = cases[: config.limit]
        chunks = load_chunks(document_path, max_bytes=self.settings.max_document_bytes)
        pipeline = self._pipeline_factory(config, self.settings, chunks)
        metrics = self._metrics_factory(config.metrics, self.settings, judge_model=config.judge_model,
                                        timeout_s=config.request_timeout_s, max_retries=config.max_retries)
        thresholds = {m.name: config.thresholds.get(m.name, m.spec.default_threshold) for m in metrics}
        return PreparedRun(config=config, cases=cases, pipeline=pipeline, metrics=metrics, thresholds=thresholds,
                           dataset_sha256=file_sha256(dataset_path), document_sha256=file_sha256(document_path))

    # ---------------------------------------------------------------------- run
    def run(self, config: RunConfig, progress: ProgressCallback | None = None,
            cancel: threading.Event | None = None) -> RunRecord:
        prepared = self.prepare(config)
        return self.execute(prepared, progress=progress, cancel=cancel)

    def execute(self, prepared: PreparedRun, progress: ProgressCallback | None = None,
                cancel: threading.Event | None = None) -> RunRecord:
        cancel = cancel or threading.Event()
        config = prepared.config
        record = RunRecord(
            id=new_run_id(config.name), name=config.name, status="running", created_at=utcnow(),
            config={**config.model_dump(mode="json"), "thresholds": prepared.thresholds,
                    "generator_model": prepared.pipeline.model, "prices_usd_per_mtok": self._prices()},
            dataset_sha256=prepared.dataset_sha256, document_sha256=prepared.document_sha256,
            n_cases=len(prepared.cases), environment=environment_info(), notes=config.notes)
        self.store.create_run(record)
        log.info("Run %s started: %d cases, provider=%s, pipeline=%s, retriever=%s, k=%d", record.id,
                 len(prepared.cases), config.provider, config.pipeline, config.retriever, config.k)

        results: list[CaseResult] = []
        status: RunStatus = "completed"
        try:
            for result in self._iter_results(prepared, cancel):
                self.store.add_case_result(record.id, result)
                results.append(result)
                if progress:
                    progress(Progress(done=len(results), total=len(prepared.cases), case_id=result.case_id,
                                      status=result.status, message=result.error or "ok"))
            if cancel.is_set():
                status = "cancelled"
        except BaseException:
            # Includes KeyboardInterrupt and Streamlit's StopException raised inside `progress`.
            cancel.set()
            self._finish(record.id, "cancelled", results, prepared)
            log.warning("Run %s cancelled after %d/%d cases", record.id, len(results), len(prepared.cases))
            raise
        if status != "cancelled":
            n_error = sum(r.status == "error" for r in results)
            status = "failed" if results and n_error == len(results) else ("partial" if n_error else "completed")
        self._finish(record.id, status, results, prepared)
        log.info("Run %s finished with status %s", record.id, status)
        finished = self.store.get_run(record.id)
        if finished is None:  # only possible if the row was deleted while the run was finishing
            raise StorageError(f"Run {record.id!r} disappeared from the store while finishing")
        return finished

    def _finish(self, run_id: str, status: RunStatus, results: list[CaseResult], prepared: PreparedRun) -> None:
        summary = summarize_run(results, [m.name for m in prepared.metrics], prepared.thresholds)
        self.store.finish_run(run_id, status, summary)

    def _iter_results(self, prepared: PreparedRun, cancel: threading.Event):
        cases = list(enumerate(prepared.cases, start=1))
        workers = max(1, prepared.config.max_workers)
        if workers == 1:
            for position, case in cases:
                if cancel.is_set():
                    return
                yield self.evaluate_case(prepared, case, position)
            return
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ragwb") as pool:
            pending: set[Future] = set()
            queue = iter(cases)
            try:
                for position, case in queue:  # fill the pool without queueing the whole dataset
                    pending.add(pool.submit(self.evaluate_case, prepared, case, position))
                    if len(pending) >= workers * 2:
                        break
                while pending:
                    done, pending = wait(pending, return_when=FIRST_COMPLETED)
                    for future in sorted(done, key=lambda f: f.result().position):
                        yield future.result()
                    if cancel.is_set():
                        continue
                    for position, case in queue:
                        pending.add(pool.submit(self.evaluate_case, prepared, case, position))
                        if len(pending) >= workers * 2:
                            break
            finally:
                for future in pending:
                    future.cancel()

    # ------------------------------------------------------------- single case
    def evaluate_case(self, prepared: PreparedRun, case: EvalCase, position: int) -> CaseResult:
        """Evaluate one case within ``config.case_timeout_s``; never raises.

        The case runs in a daemon worker thread so that a call which never returns (beyond the HTTP timeout) cannot
        stall the run: when the limit passes, the case is recorded as an ``error`` and the run moves on. Python
        cannot kill a thread, so an abandoned call may still finish in the background; its result is discarded.
        """
        limit = prepared.config.case_timeout_s
        outcome: list[CaseResult] = []

        def work() -> None:
            outcome.append(self._evaluate_case_guarded(prepared, case, position))

        worker = threading.Thread(target=work, name=f"case-{case.id}", daemon=True)
        worker.start()
        worker.join(limit)
        if worker.is_alive():
            log.error("Case %s exceeded the %.0f s time limit and was abandoned", case.id, limit)
            return CaseResult(case_id=case.id, position=position, question=case.question, metadata=case.metadata,
                              expected_answer=case.expected_answer, status="error",
                              error=f"Case exceeded the {limit:g} s time limit and was abandoned "
                                    "(raise RAGWB_CASE_TIMEOUT_S if your provider is slow)")
        return outcome[0]

    def _evaluate_case_guarded(self, prepared: PreparedRun, case: EvalCase, position: int) -> CaseResult:
        try:
            return self._evaluate_case(prepared, case, position)
        except Exception as exc:
            log.exception("Internal error evaluating case %s", case.id)
            return CaseResult(case_id=case.id, position=position, question=case.question, metadata=case.metadata,
                              expected_answer=case.expected_answer, status="error",
                              error=f"Internal {type(exc).__name__}: {exc}"[:500])

    def _evaluate_case(self, prepared: PreparedRun, case: EvalCase, position: int) -> CaseResult:
        config = prepared.config
        generation, attempts, error = self._generate_with_retries(prepared.pipeline, case.question, config.max_retries)
        if generation is None:
            return CaseResult(case_id=case.id, position=position, question=case.question, metadata=case.metadata,
                              expected_answer=case.expected_answer, status="error", attempts=attempts, error=error)
        inp = MetricInput(question=case.question, answer=generation.answer, expected_answer=case.expected_answer,
                          contexts=[c.text for c in generation.contexts])
        metric_results = {m.name: m.evaluate(inp, prepared.thresholds[m.name]) for m in prepared.metrics}
        return CaseResult(
            case_id=case.id, position=position, question=case.question, metadata=case.metadata,
            expected_answer=case.expected_answer,
            status="ok", answer=generation.answer, contexts=generation.contexts,
            context_source=generation.context_source, latency_ms=round(generation.latency_ms, 3),
            prompt_tokens=generation.prompt_tokens, completion_tokens=generation.completion_tokens,
            cost_usd=self._cost(generation), attempts=attempts, metrics=metric_results)

    def _generate_with_retries(self, pipeline: Pipeline, question: str,
                               max_retries: int) -> tuple[Generation | None, int, str | None]:
        attempt = 0
        while True:
            attempt += 1
            try:
                limiter_for(self.settings.max_requests_per_minute).acquire()  # no-op unless a limit is configured
                return pipeline.answer(question), attempt, None
            except TransientProviderError as exc:
                if attempt > max_retries:
                    return None, attempt, f"{exc} (gave up after {attempt} attempts)"
                delay = backoff_delay(self.settings.retry_base_delay_s, attempt, exc)  # jitter avoids lockstep retries
                log.info("Transient error (%s); retrying in %.1fs", exc, delay)
                self._sleep(delay)
            except ProviderError as exc:
                return None, attempt, str(exc)
            except Exception as exc:  # unexpected: keep the run alive but surface the type
                log.exception("Unexpected error answering question")
                return None, attempt, f"Unexpected {type(exc).__name__}: {exc}"[:500]

    def _prices(self) -> dict[str, float | None]:
        """Token prices in effect for this run, stored with it so cost figures stay interpretable later."""
        return {"input": self.settings.price_input_per_mtok, "output": self.settings.price_output_per_mtok}

    def _cost(self, generation: Generation) -> float | None:
        p_in, p_out = self.settings.price_input_per_mtok, self.settings.price_output_per_mtok
        if p_in is None or p_out is None or generation.prompt_tokens is None or generation.completion_tokens is None:
            return None
        return (generation.prompt_tokens * p_in + generation.completion_tokens * p_out) / 1_000_000


def new_run_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "run"
    return f"{utcnow():%Y%m%d-%H%M%S}-{slug}-{uuid.uuid4().hex[:6]}"


def environment_info() -> dict:
    versions: dict[str, str | None] = {}
    for package in _TRACKED_PACKAGES:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = None
    return {"rag_workbench": __version__, "python": sys.version.split()[0], "platform": platform.platform(),
            "packages": versions}
