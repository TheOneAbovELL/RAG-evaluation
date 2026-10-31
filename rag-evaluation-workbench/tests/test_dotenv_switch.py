import pytest

from rag_workbench import config


@pytest.fixture
def project_with_env(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("RAGWB_GENERATOR_MODEL=from-dotenv\n", encoding="utf-8")
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("RAGWB_GENERATOR_MODEL", raising=False)  # registers a restore, so the loader cannot leak it
    return tmp_path


def test_the_project_dotenv_is_loaded_by_default(project_with_env, monkeypatch):
    monkeypatch.delenv("RAGWB_NO_DOTENV", raising=False)
    assert config.load_settings().generator_model == "from-dotenv"


def test_ragwb_no_dotenv_skips_it(project_with_env, monkeypatch):
    monkeypatch.setenv("RAGWB_NO_DOTENV", "1")
    assert config.load_settings().generator_model == "gpt-4o"  # the default, not the .env value


def test_the_suite_itself_runs_with_the_switch_on():
    import os

    assert os.environ.get("RAGWB_NO_DOTENV") == "1"


def test_importing_the_package_tells_deepeval_not_to_load_dotenv_files_itself(tmp_path):
    """Found when a real .env slowed the whole suite: DeepEval auto-loads a .env from the working directory on import."""
    import subprocess
    import sys

    (tmp_path / ".env").write_text("RAGWB_MAX_REQUESTS_PER_MINUTE=3\nSOME_LEAKED_SETTING=yes\n", encoding="utf-8")
    code = (
        "import os, rag_workbench\n"
        "from rag_workbench.metrics import judge  # imports nothing heavy until used; then force the DeepEval import\n"
        "import deepeval  # noqa: F401\n"
        "print(os.environ.get('SOME_LEAKED_SETTING'), os.environ.get('RAGWB_MAX_REQUESTS_PER_MINUTE'), "
        "os.environ.get('DEEPEVAL_DISABLE_DOTENV'))\n")
    env = {k: v for k, v in __import__("os").environ.items() if k not in {"DEEPEVAL_DISABLE_DOTENV", "SOME_LEAKED_SETTING"}}
    env["RAGWB_NO_DOTENV"] = "1"
    out = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=180,
                         check=False)
    assert out.returncode == 0, out.stderr[-800:]
    assert out.stdout.strip().endswith("None None 1"), out.stdout  # nothing from the .env reached the environment


def test_the_test_process_environment_is_not_polluted_by_the_real_project_dotenv():
    """A real .env must never leak into the suite (it once paced every test at 10 operations a minute)."""
    import os

    from rag_workbench.config import PROJECT_ROOT

    env_file = PROJECT_ROOT / ".env"
    if not env_file.is_file():
        pytest.skip("no project .env on this machine")
    watched = {"RAGWB_MAX_REQUESTS_PER_MINUTE", "RAGWB_GENERATOR_MODEL", "RAGWB_JUDGE_MODEL", "RAGWB_MAX_RETRIES"}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        name, _, value = line.partition("=")
        if name.strip() in watched and value.strip():
            assert os.environ.get(name.strip()) != value.strip(), f"{name.strip()} leaked from .env into the test process"
