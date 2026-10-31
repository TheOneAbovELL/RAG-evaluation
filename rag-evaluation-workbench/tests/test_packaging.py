import tomllib
from pathlib import Path

from rag_workbench import config


def test_checkout_is_recognised_by_its_pyproject(monkeypatch):
    monkeypatch.delenv("RAGWB_HOME", raising=False)
    root = config._find_project_root()
    assert (root / "pyproject.toml").is_file() and (root / "src" / "rag_workbench").is_dir()


def test_ragwb_home_overrides_everything(monkeypatch, tmp_path):
    monkeypatch.setenv("RAGWB_HOME", str(tmp_path / "home"))
    assert config._find_project_root() == (tmp_path / "home").resolve()


def test_without_a_checkout_the_current_directory_is_used(monkeypatch, tmp_path):
    """Simulates a wheel install: config.py lives somewhere with no pyproject.toml two levels up."""
    fake = tmp_path / "site" / "pkg"
    fake.mkdir(parents=True)
    monkeypatch.delenv("RAGWB_HOME", raising=False)
    monkeypatch.setattr(config, "__file__", str(fake / "config.py"))
    monkeypatch.chdir(tmp_path)
    assert config._find_project_root() == tmp_path.resolve()


def test_wheel_bundles_the_examples_and_they_exist():
    pyproject = tomllib.loads((config.PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    include = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    assert include == {"examples": "rag_workbench/_examples"}
    examples = config.PROJECT_ROOT / "examples"
    assert any(examples.glob("datasets/*.jsonl")) and any(examples.glob("documents/*.pdf"))


def test_default_example_paths_resolve_to_real_files():
    s = config.Settings()
    assert Path(s.default_dataset).is_file() and Path(s.default_document).is_file()
