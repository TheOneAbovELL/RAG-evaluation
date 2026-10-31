"""Streamlit user-journey tests (headless, via streamlit.testing.v1.AppTest)."""

import pytest
import streamlit as st
from conftest import write_jsonl
from streamlit.testing.v1 import AppTest

from rag_workbench.config import PROJECT_ROOT

pytestmark = pytest.mark.ui
ENTRY = str(PROJECT_ROOT / "streamlit_app.py")


@pytest.fixture(autouse=True)
def fresh_cache():
    st.cache_resource.clear()  # each test gets a context bound to its own temp data dir
    yield
    st.cache_resource.clear()


def app(page: str | None = None) -> AppTest:
    at = AppTest.from_file(ENTRY, default_timeout=120)
    at.run()
    if page:
        at.switch_page(page)
        at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def texts(at) -> str:
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption] + [t.value for t in at.title]
    parts += [str(x.value) for x in at.info] + [str(x.value) for x in at.warning] + [str(x.value) for x in at.success]
    parts += [str(x.value) for x in at.error]
    return "\n".join(parts)


def seeded_run(settings, name="seed", **overrides):
    """Store one real offline run (limit 5) and return it."""
    from rag_workbench.models import RunConfig
    from rag_workbench.runner import EvaluationRunner
    from rag_workbench.storage import RunStore

    config = RunConfig(name=name, dataset_path=str(settings.default_dataset),
                       document_path=str(settings.default_document), metrics=["token_f1", "context_recall"],
                       limit=5, **overrides)
    return EvaluationRunner(settings, RunStore(settings.db_path)).run(config)


def bundle_from_run(settings, tmp_path, mutate):
    """Export a real run as a bundle, let `mutate` edit the payload, and import it."""
    import json

    from rag_workbench.archive import import_bundle
    from rag_workbench.reporting import export_json
    from rag_workbench.storage import RunStore

    store = RunStore(settings.db_path)
    run = seeded_run(settings, name="source")
    payload = json.loads(export_json(run, store.get_case_results(run.id)))
    mutate(payload)
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    store.delete_run(run.id)
    return import_bundle(store, path)


def test_overview_empty_state_then_runs():
    at = app()
    assert at.title[0].value == "RAG Evaluation Workbench"
    labels = {m.label: m.value for m in at.metric}
    assert labels["Runs stored"] == "0" and labels["New runs"] == "0" and labels["OpenAI key"] == "not set"
    assert "No evaluations run yet" in texts(at)
    assert len(at.dataframe) == 0


def test_overview_lists_stored_runs(settings):
    seeded_run(settings, name="first")
    seeded_run(settings, name="second")
    at = app()
    assert {m.label: m.value for m in at.metric}["Runs stored"] == "2"
    assert len(at.dataframe) == 1 and "No evaluations run yet" not in texts(at)


def test_new_run_journey_offline_then_results_and_compare(settings):
    seeded_run(settings, name="baseline-k1", k=1)  # something to compare the new run with
    at = app("src/rag_workbench/ui/views/new_run.py")
    assert "20 cases · 20 with reference answers" in texts(at)
    assert "11 chunks extracted" in texts(at)
    # Judge metrics are not offered without a key.
    assert "faithfulness" not in at.multiselect(key="metrics").options
    at.text_input(key="run_name").set_value("ui-offline")
    at.button(key="start_run").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Run **ui-offline** finished" in texts(at)
    assert {m.label for m in at.metric} >= {"Token F1", "ROUGE-L"}

    at.switch_page("src/rag_workbench/ui/views/results.py")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "ui-offline" in texts(at)
    assert {m.label: m.value for m in at.metric}["Cases"] == "20/20"
    assert len(at.tabs) == 5
    at.selectbox(key="detail_case").set_value("q04")
    at.run()
    assert not at.exception
    assert "chunks returned by the retriever" in texts(at)
    assert any(t.value.startswith("rank 1 · p1-b") for t in at.caption)

    at.switch_page("src/rag_workbench/ui/views/compare.py")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Highlighted rows differ" in texts(at)
    assert any("paired" in c.value.lower() for c in at.caption)


def test_new_run_blocks_invalid_inputs(tmp_path, monkeypatch):
    bad = write_jsonl(tmp_path / "bad.jsonl", [{"question": ""}, {"nope": 1}])
    monkeypatch.setenv("RAGWB_DATASET", str(bad))
    at = app("src/rag_workbench/ui/views/new_run.py")
    assert "This dataset cannot be used" in texts(at)
    assert at.button(key="start_run").disabled
    at.multiselect(key="metrics").set_value([])
    at.run()
    assert "no metric is selected" in texts(at)


def test_openai_option_explains_missing_key():
    at = app("src/rag_workbench/ui/views/new_run.py")
    at.radio(key="provider").set_value("openai")
    at.run()
    assert not at.exception
    assert "OPENAI_API_KEY is not set" in texts(at)
    assert at.button(key="start_run").disabled


def test_failure_injection_shows_partial_run():
    at = app("src/rag_workbench/ui/views/new_run.py")
    at.slider(key="failure_rate").set_value(0.5)
    at.text_input(key="run_name").set_value("ui-failures")
    at.button(key="start_run").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "partial" in texts(at) and "Failed cases are recorded" in texts(at)


def test_results_for_imported_run_show_provenance(settings, tmp_path):
    def add_warning(payload):
        payload["run"]["config"]["provenance_warnings"] = ["Scores were re-entered by hand from a printed report."]

    bundle_from_run(settings, tmp_path, add_warning)
    at = app("src/rag_workbench/ui/views/results.py")
    assert "Imported run" in texts(at)
    assert "re-entered by hand" in texts(at)


def test_data_and_settings_pages():
    at = app("src/rag_workbench/ui/views/data.py")
    labels = {m.label: m.value for m in at.metric}
    assert labels["Cases"] == "20" and labels["Errors"] == "0"
    assert any("BM25" in c.value for c in at.caption)
    at = app("src/rag_workbench/ui/views/settings.py")
    assert {"Health checks", "Metric catalogue"} <= {s.value for s in at.header}
    assert "All checks passed." in [s.value for s in at.success]
    assert "sk-" not in texts(at)


def test_imported_config_values_are_html_escaped(settings, tmp_path):
    def hostile(payload):
        payload["run"]["id"] = "hostile"
        payload["run"]["config"]["generator_model"] = "<img src=x onerror=alert(1)>"

    bundle_from_run(settings, tmp_path, hostile)
    at = app("src/rag_workbench/ui/views/results.py")
    html = " ".join(m.value for m in at.markdown if "eval-muted" in m.value)
    assert "&lt;img src=x onerror=alert(1)&gt;" in html and "<img" not in html
