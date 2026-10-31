import json

import pytest
import streamlit as st
from test_ui import app, seeded_run, texts

from rag_workbench.archive import import_bundle
from rag_workbench.cli import main
from rag_workbench.history import (
    MAX_TAGS,
    TagError,
    normalise_tags,
    parse_tag_list,
    search_runs,
    validate_notes,
)
from rag_workbench.models import RunRecord, utcnow
from rag_workbench.reporting import export_json


@pytest.fixture(autouse=True)
def fresh_cache():
    st.cache_resource.clear()  # UI tests must not reuse a context bound to another test's data dir
    yield
    st.cache_resource.clear()


def run_record(run_id, name="alpha", tags=(), notes=None, status="completed", **config):
    return RunRecord(id=run_id, name=name, status=status, created_at=utcnow(), config=config, tags=list(tags),
                     notes=notes)


# ------------------------------------------------------------------ tags and notes
def test_normalise_tags_lowercases_dedupes_and_hyphenates_spaces():
    assert normalise_tags(["Baseline", " baseline ", "Prompt V2", "", "v1.0_rc"]) == ["baseline", "prompt-v2", "v1.0_rc"]


@pytest.mark.parametrize("bad", ["bad!", "-lead", "x" * 31, "naïve"])
def test_invalid_tags_are_rejected(bad):
    with pytest.raises(TagError, match="Invalid tag"):
        normalise_tags([bad])


def test_too_many_tags_are_rejected():
    with pytest.raises(TagError, match="at most"):
        normalise_tags([f"t{i}" for i in range(MAX_TAGS + 1)])


def test_parse_tag_list_accepts_commas_and_spaces():
    assert parse_tag_list("a, b  c,,d") == ["a", "b", "c", "d"]
    assert parse_tag_list("") == []


def test_notes_are_trimmed_cleared_and_limited():
    assert validate_notes("  hi  ") == "hi"
    assert validate_notes("   ") is None and validate_notes(None) is None
    with pytest.raises(TagError, match="limited"):
        validate_notes("x" * 2001)


# ------------------------------------------------------------------ search
def test_search_requires_every_word_and_ignores_case():
    runs = [run_record("r1", "Honeybee baseline", tags=["baseline"], notes="BM25 k=3", retriever="bm25"),
            run_record("r2", "Hybrid trial", tags=["hybrid"], retriever="hybrid", dataset_path="C:\\data\\bees.jsonl"),
            run_record("r3", "Broken", status="failed")]
    ids = lambda found: [r.id for r in found]  # noqa: E731
    assert ids(search_runs(runs, "honeybee BASELINE")) == ["r1"]
    assert ids(search_runs(runs, "honeybee hybrid")) == []
    assert ids(search_runs(runs, "bees.jsonl")) == ["r2"]  # Windows path reduced to the file name
    assert ids(search_runs(runs, "")) == ["r1", "r2", "r3"]
    assert ids(search_runs(runs, tag="Hybrid")) == ["r2"]
    assert ids(search_runs(runs, status="failed")) == ["r3"]
    assert ids(search_runs(runs, "bm25", tag="baseline", status="completed")) == ["r1"]


# ------------------------------------------------------------------ storage
def test_store_round_trips_tags_and_notes(store):
    store.create_run(run_record("r1", tags=["a", "b"]))
    assert store.get_run("r1").tags == ["a", "b"]
    store.set_tags("r1", ["c"])
    store.set_notes("r1", "hello")
    run = store.get_run("r1")
    assert run.tags == ["c"] and run.notes == "hello"
    store.set_notes("r1", None)
    assert store.get_run("r1").notes is None
    from rag_workbench.storage import StorageError

    with pytest.raises(StorageError, match="not found"):
        store.set_tags("ghost", [])
    with pytest.raises(StorageError, match="not found"):
        store.set_notes("ghost", "x")


def test_tags_travel_with_an_exported_bundle(settings, store, tmp_path):
    run = seeded_run(settings, name="tagged")
    store.set_tags(run.id, ["keep-me"])
    run = store.get_run(run.id)
    payload = json.loads(export_json(run, store.get_case_results(run.id)))
    assert payload["run"]["tags"] == ["keep-me"]
    payload["run"]["id"] = "imported-copy"
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    imported_id = import_bundle(store, path)
    assert store.get_run(imported_id).tags == ["keep-me"]


# ------------------------------------------------------------------ CLI
def test_cli_tag_note_and_filtered_list(capsys):
    assert main(["run", "--name", "alpha-run", "--limit", "2", "--quiet"]) == 0
    assert main(["run", "--name", "beta-run", "--limit", "2", "--quiet"]) == 0
    from rag_workbench.config import load_settings
    from rag_workbench.services import open_context

    runs = {r.name: r for r in open_context(load_settings(), console_logging=False).store.list_runs()}
    alpha = runs["alpha-run"].id
    capsys.readouterr()

    assert main(["tag", alpha, "--add", "Baseline, v1"]) == 0
    assert "tags = baseline, v1" in capsys.readouterr().out
    assert main(["tag", alpha, "--remove", "v1"]) == 0
    assert "tags = baseline" in capsys.readouterr().out
    assert main(["note", alpha, "first attempt"]) == 0
    capsys.readouterr()

    assert main(["list", "--tag", "baseline"]) == 0
    out = capsys.readouterr().out
    assert "alpha-run" in out and "beta-run" not in out
    assert main(["list", "--search", "first", "attempt"]) == 0
    assert "alpha-run" in capsys.readouterr().out
    assert main(["list", "--search", "nothing-matches"]) == 0
    assert "No run matches" in capsys.readouterr().out

    assert main(["note", alpha, "--clear"]) == 0
    assert main(["note", alpha]) == 1  # neither text nor --clear
    assert main(["note", alpha, "x", "--clear"]) == 1  # both
    capsys.readouterr()
    assert main(["tag", alpha, "--add", "bad!"]) == 1
    assert "Invalid tag" in capsys.readouterr().err
    assert main(["tag", "no-such-run", "--add", "x"]) == 1


# ------------------------------------------------------------------ UI
def test_overview_search_and_tag_filter(settings, store):
    first = seeded_run(settings, name="first-run")
    seeded_run(settings, name="second-run")
    store.set_tags(first.id, ["baseline"])
    at = app()
    assert len(at.dataframe[0].value) == 2
    at.text_input(key="overview_search").set_value("second")
    at.run()
    assert [r["name"] for r in at.dataframe[0].value.to_dict("records")] == ["second-run"]
    at.text_input(key="overview_search").set_value("")
    at.selectbox(key="overview_tag").select("baseline")
    at.run()
    assert [r["name"] for r in at.dataframe[0].value.to_dict("records")] == ["first-run"]
    at.selectbox(key="overview_tag").select("(any)")
    at.text_input(key="overview_search").set_value("zzz")
    at.run()
    assert "No run matches (2 stored)" in texts(at)


def test_results_page_saves_tags_and_notes_and_rejects_bad_tags(settings, store):
    run = seeded_run(settings, name="to-label")
    at = app("src/rag_workbench/ui/views/results.py")
    at.text_input(key=f"tags_{run.id}").set_value("Keep, v2")
    at.text_area(key=f"notes_{run.id}").set_value("checked by hand")
    at.button(key="save_meta").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    saved = store.get_run(run.id)
    assert saved.tags == ["keep", "v2"] and saved.notes == "checked by hand"
    assert "Tags: `keep`, `v2`" in texts(at)

    at.text_input(key=f"tags_{run.id}").set_value("bad!")
    at.button(key="save_meta").click()
    at.run()
    assert "Invalid tag" in texts(at)
    assert store.get_run(run.id).tags == ["keep", "v2"]  # unchanged
