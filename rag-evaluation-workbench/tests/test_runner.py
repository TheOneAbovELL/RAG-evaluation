import threading
import time

import pytest
from conftest import REAL_DATASET, REAL_PDF

from rag_workbench.config import ConfigError, load_settings
from rag_workbench.datasets import DatasetError
from rag_workbench.documents import DocumentError
from rag_workbench.errors import ProviderError, TransientProviderError
from rag_workbench.models import RunConfig
from rag_workbench.runner import EvaluationRunner, new_run_id


def runner_with(settings, store, pipeline, sleeps=None):
    return EvaluationRunner(settings, store, pipeline_factory=lambda *a, **k: pipeline,
                            sleep=(sleeps.append if sleeps is not None else lambda s: None))


def test_offline_end_to_end_on_the_real_dataset(settings, store):
    config = RunConfig(name="real", dataset_path=str(REAL_DATASET), document_path=str(REAL_PDF), k=3,
                       metrics=["token_f1", "rouge_l", "context_recall", "groundedness", "exact_match"])
    run = EvaluationRunner(settings, store).run(config)
    assert run.status == "completed" and run.n_cases == 20
    results = store.get_case_results(run.id)
    assert len(results) == 20 and all(r.status == "ok" for r in results)
    assert all(len(r.contexts) == 3 and r.context_source == "retriever" for r in results)
    assert run.summary.metrics["token_f1"].n_scored == 20
    assert 0 < run.summary.metrics["token_f1"].mean < 1
    assert run.config["thresholds"]["token_f1"] == 0.5
    assert run.config["generator_model"] == "offline-extractive"
    assert len(run.dataset_sha256) == 64 and run.environment["packages"]["deepeval"]


def test_offline_runs_are_reproducible(settings, store, offline_config):
    runner = EvaluationRunner(settings, store)
    a, b = runner.run(offline_config()), runner.run(offline_config())
    assert a.id != b.id

    def scores(run):
        return [(r.answer, {k: m.score for k, m in r.metrics.items()}) for r in store.get_case_results(run.id)]

    assert scores(a) == scores(b)


def test_missing_reference_skips_reference_metrics(settings, store, offline_config):
    run = EvaluationRunner(settings, store).run(offline_config())
    q4 = next(r for r in store.get_case_results(run.id) if r.case_id == "q4")
    assert q4.metrics["token_f1"].status == "skipped"
    assert q4.metrics["groundedness"].status in {"ok", "skipped"}
    assert run.summary.metrics["token_f1"].n_skipped == 1


def test_partial_and_failed_statuses(settings, store, offline_config, fake_pipeline_cls):
    pipeline = fake_pipeline_cls({"What do forager bees collect?": ProviderError("bad request")})
    run = runner_with(settings, store, pipeline).run(offline_config())
    assert run.status == "partial" and run.summary.n_error == 1
    failed = next(r for r in store.get_case_results(run.id) if r.status == "error")
    assert failed.error == "bad request" and failed.metrics == {}

    always = fake_pipeline_cls({q: ProviderError("down") for q in [
        "What do forager bees collect?", "How many queens does a colony have?", "How do bees stay warm in winter?",
        "What threatens honeybee colonies?"]})
    assert runner_with(settings, store, always).run(offline_config()).status == "failed"


def test_transient_errors_are_retried_with_backoff(settings, store, offline_config, fake_pipeline_cls):
    settings = load_settings({"RAGWB_RETRY_BASE_DELAY_S": "1", "RAGWB_DATA_DIR": str(settings.data_dir)},
                             dotenv=False)

    def flaky(attempt):
        return TransientProviderError("429") if attempt < 3 else None

    pipeline = fake_pipeline_cls({"What do forager bees collect?": flaky})
    sleeps = []
    run = runner_with(settings, store, pipeline, sleeps).run(offline_config(max_retries=3))
    case = next(r for r in store.get_case_results(run.id) if r.case_id == "q1")
    assert case.status == "ok" and case.attempts == 3
    assert len(sleeps) == 2 and 1 <= sleeps[0] <= 2 and 2 <= sleeps[1] <= 3  # 1*2^0, 1*2^1 plus jitter


def test_retries_give_up(settings, store, offline_config, fake_pipeline_cls):
    pipeline = fake_pipeline_cls({"What do forager bees collect?": TransientProviderError("timeout")})
    run = runner_with(settings, store, pipeline).run(offline_config(max_retries=2))
    case = next(r for r in store.get_case_results(run.id) if r.case_id == "q1")
    assert case.status == "error" and case.attempts == 3 and "gave up after 3 attempts" in case.error
    assert pipeline.calls["What do forager bees collect?"] == 3


def test_unexpected_exceptions_do_not_abort_the_run(settings, store, offline_config, fake_pipeline_cls):
    pipeline = fake_pipeline_cls({"How many queens does a colony have?": KeyError("boom")})
    run = runner_with(settings, store, pipeline).run(offline_config())
    assert run.status == "partial"
    assert "Unexpected KeyError" in next(r.error for r in store.get_case_results(run.id) if r.status == "error")


def test_cancellation_event_stops_and_records_progress(settings, store, offline_config):
    cancel = threading.Event()
    seen = []

    def progress(p):
        seen.append(p.case_id)
        if p.done == 2:
            cancel.set()

    run = EvaluationRunner(settings, store).run(offline_config(), progress=progress, cancel=cancel)
    assert run.status == "cancelled"
    assert store.count_case_results(run.id) == 2 and run.summary.n_cases == 2


def test_exception_in_progress_callback_marks_run_cancelled(settings, store, offline_config):
    class Stop(BaseException):
        pass

    def progress(p):
        raise Stop()

    with pytest.raises(Stop):
        EvaluationRunner(settings, store).run(offline_config(), progress=progress)
    run = store.list_runs()[0]
    assert run.status == "cancelled" and store.count_case_results(run.id) == 1


def test_parallel_execution_keeps_every_case(settings, store, offline_config):
    config = RunConfig(name="par", dataset_path=str(REAL_DATASET), document_path=str(REAL_PDF), k=2,
                       metrics=["token_f1"], max_workers=4)
    run = EvaluationRunner(settings, store).run(config)
    results = store.get_case_results(run.id)
    assert run.status == "completed" and len(results) == 20
    assert [r.position for r in results] == list(range(1, 21))
    serial = EvaluationRunner(settings, store).run(config.model_copy(update={"max_workers": 1}))
    assert [r.answer for r in store.get_case_results(serial.id)] == [r.answer for r in results]


def test_validation_happens_before_a_run_is_created(settings, store, offline_config, tmp_path):
    runner = EvaluationRunner(settings, store)
    with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
        runner.run(offline_config(metrics=["faithfulness"]))
    with pytest.raises(ConfigError, match="Invalid threshold"):
        runner.run(offline_config(thresholds={"token_f1": 1.5}))
    with pytest.raises(DatasetError):
        runner.run(offline_config(dataset_path=str(tmp_path / "missing.jsonl")))
    with pytest.raises(DocumentError):
        runner.run(offline_config(document_path=str(tmp_path / "missing.pdf")))
    assert store.list_runs() == []


def test_limit_and_cost(settings, store, offline_config, fake_pipeline_cls):
    priced = load_settings({"RAGWB_PRICE_INPUT_PER_MTOK": "2", "RAGWB_PRICE_OUTPUT_PER_MTOK": "10",
                            "RAGWB_DATA_DIR": str(settings.data_dir)}, dotenv=False)
    run = runner_with(priced, store, fake_pipeline_cls()).run(offline_config(limit=2))
    assert run.n_cases == 2
    # 10 prompt tokens * $2/M + 5 completion tokens * $10/M = 7e-5 per case
    assert run.summary.total_cost_usd == pytest.approx(2 * 7e-5)
    unpriced = runner_with(settings, store, fake_pipeline_cls()).run(offline_config(limit=1))
    assert unpriced.summary.total_cost_usd is None


def test_run_ids_are_safe_and_unique():
    ids = {new_run_id("My Run / ../evil") for _ in range(20)}
    assert len(ids) == 20
    assert all("/" not in i and ".." not in i for i in ids)


def test_demo_runs_are_genuine_and_reproducible(settings):
    from rag_workbench.demo import seed_demo_runs
    from rag_workbench.services import open_context

    ctx = open_context(settings, console_logging=False)
    runs = seed_demo_runs(ctx)
    assert set(runs) == {"k1", "k3", "k5", "unanswerable", "failures"}
    assert runs["failures"].status == "partial" and runs["k3"].status == "completed"
    assert runs["unanswerable"].n_cases == 6
    again = seed_demo_runs(ctx)
    assert again["k3"].summary.metrics["token_f1"].mean == runs["k3"].summary.metrics["token_f1"].mean


def test_a_hung_case_is_abandoned_after_the_time_limit(settings, store, offline_config):
    release = threading.Event()

    class HangingPipeline:
        model = "hang"

        def answer(self, question):
            if question.startswith("What do forager"):
                release.wait(30)  # simulates a call that never returns
            return FakePipeline().answer(question)

    from conftest import FakePipeline

    try:
        started = time.perf_counter()
        run = runner_with(settings, store, HangingPipeline()).run(offline_config(case_timeout_s=0.3))
        elapsed = time.perf_counter() - started
    finally:
        release.set()
    case = next(r for r in store.get_case_results(run.id) if r.case_id == "q1")
    assert case.status == "error" and "time limit" in case.error
    assert run.status == "partial" and elapsed < 10  # did not wait for the hung call
    assert [r.status for r in store.get_case_results(run.id)].count("ok") == 3


def test_prices_are_stored_with_the_run(settings, store, offline_config, fake_pipeline_cls):
    priced = load_settings({"RAGWB_PRICE_INPUT_PER_MTOK": "2", "RAGWB_PRICE_OUTPUT_PER_MTOK": "10",
                            "RAGWB_DATA_DIR": str(settings.data_dir)}, dotenv=False)
    run = runner_with(priced, store, fake_pipeline_cls()).run(offline_config(limit=1))
    assert run.config["prices_usd_per_mtok"] == {"input": 2.0, "output": 10.0}
    unpriced = runner_with(settings, store, fake_pipeline_cls()).run(offline_config(limit=1))
    assert unpriced.config["prices_usd_per_mtok"] == {"input": None, "output": None}
