import importlib.util
import io

import pytest

from rag_workbench.config import PROJECT_ROOT

OLD = "gsk_" + "o" * 24
NEW = "gsk_" + "n" * 24


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("set_api_key_script", PROJECT_ROOT / "scripts" / "set_api_key.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def env_file(tmp_path):
    path = tmp_path / ".env"
    path.write_text(f"# my settings\nOPENAI_API_KEY={OLD}\nOPENAI_BASE_URL=https://example.invalid/v1\nRAGWB_MAX_RETRIES=4\n",
                    encoding="utf-8")
    return path


def test_only_the_key_line_changes(tool, env_file):
    tool.write_env(env_file, NEW)
    assert env_file.read_text(encoding="utf-8") == (
        f"# my settings\nOPENAI_API_KEY={NEW}\nOPENAI_BASE_URL=https://example.invalid/v1\nRAGWB_MAX_RETRIES=4\n")


def test_a_missing_key_line_is_added_and_a_missing_file_is_created_from_the_example(tool, tmp_path):
    example = tmp_path / ".env.example"
    example.write_text("# template\nOPENAI_API_KEY=\n# RAGWB_MAX_RETRIES=3\n", encoding="utf-8")
    target = tmp_path / ".env"
    tool.write_env(target, NEW, example=example)
    assert target.read_text(encoding="utf-8") == f"# template\nOPENAI_API_KEY={NEW}\n# RAGWB_MAX_RETRIES=3\n"
    only_comments = tmp_path / "other.env"
    only_comments.write_text("# nothing\n", encoding="utf-8")
    tool.write_env(only_comments, NEW)
    assert only_comments.read_text(encoding="utf-8").endswith(f"OPENAI_API_KEY={NEW}\n")


@pytest.mark.parametrize("bad", ["", "abc123", "has a space in it 12345", 'quoted"key"1234567890', "hash#key12345678901"])
def test_implausible_keys_are_refused_without_echoing_them(tool, bad):
    with pytest.raises(ValueError) as exc:
        tool.validate_key(bad)
    assert bad.strip() == "" or bad not in str(exc.value)


def test_main_reads_stdin_updates_the_file_and_never_prints_the_key(tool, env_file, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(NEW + "\n"))
    assert tool.main(["--stdin"], env_file=env_file) == 0
    captured = capsys.readouterr()
    assert NEW not in captured.out + captured.err and OLD not in captured.out + captured.err
    assert f"{len(NEW)} characters" in captured.out
    assert tool.read_setting(env_file, "OPENAI_API_KEY") == NEW


def test_main_refuses_a_bad_key_and_leaves_the_file_alone(tool, env_file, monkeypatch, capsys):
    before = env_file.read_text(encoding="utf-8")
    monkeypatch.setattr("sys.stdin", io.StringIO("nope\n"))
    assert tool.main(["--stdin"], env_file=env_file) == 1
    assert "does not look like" in capsys.readouterr().err and env_file.read_text(encoding="utf-8") == before


def test_remove_blanks_the_key_and_keeps_everything_else(tool, env_file):
    assert tool.main(["--remove"], env_file=env_file) == 0
    text = env_file.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=\n" in text and OLD not in text and "RAGWB_MAX_RETRIES=4" in text


def test_read_setting_ignores_comments_and_quotes(tool, tmp_path):
    path = tmp_path / ".env"
    path.write_text('# OPENAI_API_KEY=commented\nOPENAI_BASE_URL="https://x.invalid/v1"\n', encoding="utf-8")
    assert tool.read_setting(path, "OPENAI_API_KEY") is None
    assert tool.read_setting(path, "OPENAI_BASE_URL") == "https://x.invalid/v1"


def test_check_reports_a_refused_key_without_leaking_it(tool, env_file, monkeypatch):
    import urllib.error

    def refuse(request, timeout=0):
        assert request.headers["Authorization"] == f"Bearer {OLD}"  # it does send the stored key...
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(tool.urllib.request, "urlopen", refuse)
    status, message = tool.check_key(env_file)
    assert (status, message) == (401, "rejected") and OLD not in message  # ...but never reports it


def test_check_without_a_key_makes_no_request(tool, tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("OPENAI_API_KEY=\n", encoding="utf-8")

    def boom(*args, **kwargs):
        raise AssertionError("no request may be made without a key")

    monkeypatch.setattr(tool.urllib.request, "urlopen", boom)
    assert tool.check_key(path) == (None, "no key is set in .env")
