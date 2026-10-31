from pathlib import Path

import pytest

from rag_workbench.config import PROJECT_ROOT, ConfigError, load_settings


def test_defaults_resolve_inside_project():
    s = load_settings({}, dotenv=False)
    assert s.default_dataset == PROJECT_ROOT / "examples" / "datasets" / "honeybees.jsonl"
    assert s.default_document == PROJECT_ROOT / "examples" / "documents" / "honeybees.pdf"
    assert s.default_dataset.is_file() and s.default_document.is_file()
    assert s.judge_model == "gpt-4o"
    assert not s.has_openai_key


def test_relative_paths_are_resolved_against_project_root():
    s = load_settings({"RAGWB_DATA_DIR": "tmpdata"}, dotenv=False)
    assert s.data_dir == PROJECT_ROOT / "tmpdata"
    assert s.db_path == PROJECT_ROOT / "tmpdata" / "runs.db"


def test_absolute_path_kept(tmp_path):
    s = load_settings({"RAGWB_DATA_DIR": str(tmp_path)}, dotenv=False)
    assert s.data_dir == Path(tmp_path)


def test_numeric_parsing_and_blank_values_ignored():
    s = load_settings({"RAGWB_MAX_RETRIES": "5", "RAGWB_REQUEST_TIMEOUT_S": " ", "OPENAI_API_KEY": "  "},
                      dotenv=False)
    assert s.max_retries == 5
    assert s.request_timeout_s == 60.0
    assert not s.has_openai_key


@pytest.mark.parametrize("env", [
    {"RAGWB_MAX_RETRIES": "-1"},
    {"RAGWB_MAX_RETRIES": "many"},
    {"RAGWB_REQUEST_TIMEOUT_S": "0"},
    {"RAGWB_LOG_LEVEL": "LOUD"},
])
def test_invalid_values_raise_config_error_naming_the_variable(env):
    with pytest.raises(ConfigError) as info:
        load_settings(env, dotenv=False)
    assert next(iter(env)) in str(info.value)


def test_secret_never_exposed():
    secret = "sk-not-a-real-key-for-tests-123456"
    s = load_settings({"OPENAI_API_KEY": secret}, dotenv=False)
    assert s.has_openai_key
    assert secret not in repr(s)
    public = s.public_dict()
    assert secret not in str(public)
    assert public["openai_api_key_configured"] is True
