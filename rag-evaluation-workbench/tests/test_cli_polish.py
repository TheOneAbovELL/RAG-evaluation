import pytest
from conftest import REAL_DATASET, REAL_PDF

from rag_workbench.cli import main
from rag_workbench.documents import load_chunks
from rag_workbench.models import RunConfig
from rag_workbench.runner import EvaluationRunner


# ------------------------------------------------------------------ Markdown headings
def test_markdown_heading_markup_is_dropped_but_the_words_are_kept(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text("# Title Here\n\n## A subsection\n\nBody with a # inside it. More text here.\n\n####### not a heading\n",
                   encoding="utf-8")
    texts = [c.text for c in load_chunks(doc)]
    assert texts[0] == "Title Here" and texts[1] == "A subsection"
    assert texts[2] == "Body with a # inside it. More text here."  # a # in the middle is text
    assert texts[3] == "####### not a heading"  # seven marks is not Markdown heading syntax


def test_plain_text_files_keep_a_leading_hash(tmp_path):
    doc = tmp_path / "notes.txt"
    doc.write_text("# not markup in a .txt file\n\nsecond paragraph.\n", encoding="utf-8")
    assert load_chunks(doc)[0].text.startswith("# not markup")


def test_the_bundled_markdown_source_no_longer_leaks_markup_into_the_title_chunk():
    from rag_workbench.config import EXAMPLES_DIR

    first = load_chunks(EXAMPLES_DIR / "documents" / "honeybees.md")[0].text
    assert first == "Honeybees: Life Inside the Colony"


# ------------------------------------------------------------------ run references
@pytest.fixture
def two_runs(settings, store):
    runner = EvaluationRunner(settings, store)
    out = []
    for name in ("alpha-run", "beta-run"):
        out.append(runner.run(RunConfig(name=name, dataset_path=str(REAL_DATASET), document_path=str(REAL_PDF),
                                        metrics=["token_f1"], limit=2)))
    return out


def test_runs_can_be_referenced_by_full_id_prefix_short_suffix_or_exact_name(two_runs, capsys):
    alpha, beta = two_runs
    for ref in (alpha.id, alpha.id[:-3] if alpha.id[:-3] != beta.id[:-3] else alpha.id, alpha.id[-6:], "alpha-run"):
        assert main(["show", ref]) == 0, ref
        assert alpha.id in capsys.readouterr().out


def test_ambiguous_and_unknown_references_are_refused_with_a_useful_message(two_runs, capsys):
    alpha, beta = two_runs
    common = alpha.id[:8]  # both runs were created on the same day: the date prefix matches both
    assert main(["show", common]) == 1
    err = capsys.readouterr().err
    assert "matches 2 runs" in err and alpha.id in err and beta.id in err
    assert main(["show", "no-such-run"]) == 1
    assert "No run with id" in capsys.readouterr().err
    assert main(["show", "abc"]) == 1  # shorter than the partial-match minimum: no guessing


def test_show_prints_tags_and_notes(two_runs, capsys):
    alpha, _ = two_runs
    assert main(["tag", alpha.id, "--add", "baseline,v1"]) == 0
    assert main(["note", alpha.id, "first honeybee baseline"]) == 0
    capsys.readouterr()
    assert main(["show", alpha.id]) == 0
    out = capsys.readouterr().out
    assert "tags: baseline, v1" in out and "notes: first honeybee baseline" in out


# ------------------------------------------------------------------ calibrate
def test_calibrate_wording_does_not_claim_the_labels_are_human(two_runs, tmp_path, capsys):
    alpha, _ = two_runs
    labels = tmp_path / "ai-labels.csv"
    labels.write_text("case_id,human_pass\nq01,pass\nq02,fail\n", encoding="utf-8")
    assert main(["calibrate", alpha.id, "--labels", str(labels), "--metric", "token_f1"]) == 0
    out = capsys.readouterr().out
    assert "vs labels from ai-labels.csv" in out and "human labels" not in out


def test_rescoring_a_metric_that_cannot_be_computed_says_why_instead_of_printing_zeros(two_runs, tmp_path, monkeypatch, capsys):
    from rag_workbench import metrics as metrics_pkg

    alpha, _ = two_runs
    labels = tmp_path / "l.csv"
    labels.write_text("case_id,human_pass\nq01,pass\n", encoding="utf-8")
    monkeypatch.setattr(metrics_pkg, "semantic_available", lambda: True)

    class Broken:
        def embed(self, texts):
            raise RuntimeError("the embedding model is not installed")

    from rag_workbench.metrics import semantic as sem

    monkeypatch.setattr(sem, "local_embedder", lambda name, cache_dir=None: Broken())
    assert main(["calibrate", alpha.id, "--labels", str(labels), "--metric", "semantic_similarity", "--rescore"]) == 1
    assert "could not be computed for any case" in capsys.readouterr().err


# ------------------------------------------------------------------ prune, regress, workers, start, local model
def test_prune_never_deletes_a_run_tagged_keep(two_runs, capsys):
    alpha, _ = two_runs
    assert main(["tag", alpha.id, "--add", "keep"]) == 0
    capsys.readouterr()
    assert main(["prune", "--keep-last", "1", "--yes"]) == 0
    out = capsys.readouterr().out
    assert "tagged 'keep' are never pruned" in out
    ids = {line.split()[0] for line in _list_lines(capsys)}
    assert alpha.id in ids  # the older run survived because of its tag; the newest was kept by --keep-last


def _list_lines(capsys):
    assert main(["list"]) == 0
    return [line for line in capsys.readouterr().out.splitlines()[1:] if line.strip()]


def test_regress_with_a_metric_neither_run_has_is_an_error_not_a_silent_not_judged(two_runs, capsys):
    alpha, beta = two_runs
    assert main(["regress", alpha.id, beta.id, "--metrics", "nope"]) == 1
    err = capsys.readouterr().err
    assert "not present in both runs: nope" in err and "token_f1" in err


@pytest.mark.parametrize("flag", ["--workers", "--limit"])
@pytest.mark.parametrize("value", ["0", "-2", "x"])
def test_workers_and_limit_must_be_positive_whole_numbers(flag, value, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["run", flag, value, "--quiet"])
    assert exc.value.code == 2 and flag in capsys.readouterr().err


def test_start_py_honours_the_no_dotenv_switch(tmp_path):
    import importlib.util

    from rag_workbench.config import PROJECT_ROOT

    spec = importlib.util.spec_from_file_location("start_script_polish", PROJECT_ROOT / "start.py")
    start = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(start)
    env_file = tmp_path / ".env"
    env_file.write_text("RAGWB_APP_PASSWORD=from-file\n", encoding="utf-8")
    assert start.password_configured(env={}, env_file=env_file)
    assert not start.password_configured(env={"RAGWB_NO_DOTENV": "1"}, env_file=env_file)
    assert start.password_configured(env={"RAGWB_NO_DOTENV": "1", "RAGWB_APP_PASSWORD": "from-env"}, env_file=env_file)


def test_a_local_model_that_cannot_load_stops_the_run_before_any_case(settings, monkeypatch):
    from rag_workbench import pipeline as pipeline_mod
    from rag_workbench.config import ConfigError
    from rag_workbench.pipeline import build_retriever

    def cannot_load(name, cache_dir=None):
        raise RuntimeError("Could not load model from any source")

    monkeypatch.setattr(pipeline_mod, "semantic_available", lambda: True)
    monkeypatch.setattr(pipeline_mod, "local_embedder", cannot_load)
    config = RunConfig(name="t", dataset_path=str(REAL_DATASET), document_path=str(REAL_PDF), retriever="local",
                       metrics=["token_f1"])
    with pytest.raises(ConfigError, match=r"could not be loaded.*(one-time|download)"):
        build_retriever(config, load_chunks(REAL_PDF), settings)


def test_a_semantic_metric_whose_model_cannot_load_fails_at_build_time(settings, monkeypatch):
    from rag_workbench import metrics as metrics_pkg
    from rag_workbench.config import ConfigError
    from rag_workbench.metrics import build_metrics
    from rag_workbench.metrics import semantic as sem

    def cannot_load(name, cache_dir=None):
        raise RuntimeError("no network")

    monkeypatch.setattr(metrics_pkg, "semantic_available", lambda: True)
    monkeypatch.setattr(sem, "local_embedder", cannot_load)
    with pytest.raises(ConfigError, match="could not be loaded"):
        build_metrics(["semantic_similarity"], settings)
