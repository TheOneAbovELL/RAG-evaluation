import io
import json
import logging
import time

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from rag_workbench.cli import main
from rag_workbench.config import PROJECT_ROOT, load_settings
from rag_workbench.ui.auth import ThrottleSet
from rag_workbench.users import MIN_PASSWORD_LENGTH, UserError, UserStore, normalise_username

ENTRY = str(PROJECT_ROOT / "streamlit_app.py")
PW = "correct horse battery"


@pytest.fixture
def users(tmp_path):
    return UserStore(tmp_path / "users.json")


# ------------------------------------------------------------------ store
def test_add_verify_and_normalisation(users):
    assert users.add("  Alice ", PW) == "alice"
    assert users.verify("alice", PW) == "alice"
    assert users.verify("ALICE", PW) == "alice"  # usernames are case-insensitive
    assert users.verify("alice", PW + "x") is None
    assert users.verify("bob", PW) is None
    assert users.verify("", "") is None and users.verify("a b", PW) is None


def test_passwords_are_never_stored(users):
    users.add("alice", PW)
    raw = users.path.read_text(encoding="utf-8")
    assert PW not in raw
    assert set(json.loads(raw)["users"]["alice"]) == {"salt", "hash", "role", "created"}


def test_same_password_gets_a_different_salt_and_hash(users):
    users.add("alice", PW)
    users.add("bob", PW)
    entries = json.loads(users.path.read_text(encoding="utf-8"))["users"]
    assert entries["alice"]["salt"] != entries["bob"]["salt"]
    assert entries["alice"]["hash"] != entries["bob"]["hash"]


@pytest.mark.parametrize("bad", ["", "-x", "has space", "UPPER!", "x" * 33, "é"])
def test_bad_usernames_are_rejected(bad):
    with pytest.raises(UserError, match="Usernames"):
        normalise_username(bad)


def test_password_length_limits_and_duplicates(users):
    with pytest.raises(UserError, match="Passwords must be"):
        users.add("alice", "x" * (MIN_PASSWORD_LENGTH - 1))
    with pytest.raises(UserError, match="Passwords must be"):
        users.add("alice", "x" * 201)
    users.add("alice", PW)
    with pytest.raises(UserError, match="already exists"):
        users.add("alice", "another long password")
    users.add("alice", "another long password", replace=True)
    assert users.verify("alice", PW) is None
    assert users.verify("alice", "another long password") == "alice"


def test_remove_and_list(users):
    assert users.names() == [] and not users.has_users()
    users.add("bob", PW)
    users.add("alice", PW)
    assert users.names() == ["alice", "bob"] and users.has_users()
    assert users.remove("bob") and not users.remove("bob")
    assert users.names() == ["alice"]
    assert users.remove("alice")
    assert not users.path.exists() and not users.has_users()  # the last removal leaves no file behind


def test_rerun_does_not_inherit_the_original_starter():
    from rag_workbench.maintenance import rerun_config
    from rag_workbench.models import RunConfig, RunRecord, utcnow

    config = RunConfig(name="orig", dataset_path="d.jsonl", document_path="p.pdf", metrics=["token_f1"],
                       started_by="alice")
    run = RunRecord(id="r1", name="orig", status="completed", created_at=utcnow(), config=config.model_dump())
    assert rerun_config(run).started_by is None


def test_a_damaged_users_file_locks_rather_than_opens(users):
    users.path.write_text("{not json", encoding="utf-8")
    assert users.has_users()  # fail closed
    assert users.verify("alice", PW) is None
    with pytest.raises(UserError, match="unreadable"):
        users.names()


def test_oversize_password_is_refused_and_unknown_users_still_pay_for_hashing(users):
    users.add("alice", PW)
    assert users.verify("alice", "x" * 10_000) is None
    start = time.perf_counter()
    users.verify("alice", "wrong password here")
    known = time.perf_counter() - start
    start = time.perf_counter()
    users.verify("nobody", "wrong password here")
    unknown = time.perf_counter() - start
    assert unknown > known * 0.3  # an unknown name is not refused instantly (no timing oracle for usernames)


# ------------------------------------------------------------------ throttling
def test_throttle_set_is_per_username_with_a_loose_global_limit():
    now = [0.0]
    throttles = ThrottleSet(max_failures=3, window_s=60, global_max=5, clock=lambda: now[0])
    for _ in range(3):
        throttles.record_failure("alice")
    assert throttles.retry_after("alice") > 0
    assert throttles.retry_after("bob") == 0  # one user's failures do not lock another
    throttles.record_failure("bob")
    throttles.record_failure("bob")
    assert throttles.retry_after("carol") > 0  # five failures overall: the global limit applies to everyone
    now[0] += 61
    assert throttles.retry_after("alice") == 0 and throttles.retry_after("carol") == 0
    throttles.record_failure("dave")
    throttles.reset("dave")
    assert throttles.retry_after("dave") == 0


# ------------------------------------------------------------------ settings and CLI
def test_settings_report_accounts_without_exposing_anything(tmp_path):
    settings = load_settings({"RAGWB_DATA_DIR": str(tmp_path)}, dotenv=False)
    assert not settings.has_users and not settings.login_required
    UserStore(settings.users_path).add("alice", PW)
    assert settings.has_users and settings.login_required
    assert settings.public_dict()["user_accounts_configured"] is True
    assert PW not in str(settings.public_dict())


def test_cli_user_commands(capsys, monkeypatch):
    assert main(["user", "list"]) == 0
    assert "No user accounts" in capsys.readouterr().out
    monkeypatch.setattr("sys.stdin", io.StringIO(PW + "\n"))
    assert main(["user", "add", "Alice", "--password-stdin"]) == 0
    assert "Saved user alice" in capsys.readouterr().out
    monkeypatch.setattr("sys.stdin", io.StringIO(PW + "\n"))
    assert main(["user", "add", "alice", "--password-stdin"]) == 1  # exists
    assert "already exists" in capsys.readouterr().err
    monkeypatch.setattr("sys.stdin", io.StringIO("short\n"))
    assert main(["user", "add", "bob", "--password-stdin"]) == 1
    capsys.readouterr()
    assert main(["user", "add"]) == 1
    assert "needs a username" in capsys.readouterr().err
    assert main(["user", "list"]) == 0
    assert "alice" in capsys.readouterr().out
    assert main(["user", "remove", "alice"]) == 0
    assert main(["user", "remove", "alice"]) == 1


# ------------------------------------------------------------------ UI
@pytest.fixture
def with_accounts(settings):
    UserStore(settings.users_path).add("alice", PW)
    st.cache_resource.clear()
    yield settings
    st.cache_resource.clear()


def new_app(page=None):
    at = AppTest.from_file(ENTRY, default_timeout=120).run()
    if page:
        at.switch_page(page)
        at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def shown(at):
    parts = [t.value for t in at.title] + [c.value for c in at.caption] + [str(e.value) for e in at.error]
    return "\n".join(parts)


def sign_in(at, user, password):
    at.text_input(key="login_username").set_value(user)
    at.text_input(key="login_password").set_value(password)
    at.button[0].click()
    return at.run()


def test_accounts_block_the_app_until_a_valid_sign_in(with_accounts, caplog):
    at = new_app()
    assert "Sign in with your account" in shown(at) and not at.metric
    with caplog.at_level(logging.INFO, logger="rag_workbench.ui.auth"):
        sign_in(at, "alice", "wrong password here")
        assert "Incorrect username or password." in shown(at) and not at.metric
        sign_in(at, "nobody", PW)
        assert "Incorrect username or password." in shown(at)  # same message: no username enumeration
        sign_in(at, "Alice", PW)
    assert not at.exception, [e.value for e in at.exception]
    assert {m.label for m in at.metric} >= {"Runs stored"}
    assert "Signed in as **alice** (editor)" in shown(at)
    assert "sign-in failed" in caplog.text and "sign-in ok user='alice'" in caplog.text
    assert PW not in caplog.text and "wrong password here" not in caplog.text  # passwords never reach the log


def test_account_login_wins_over_the_shared_password(with_accounts, monkeypatch):
    monkeypatch.setenv("RAGWB_APP_PASSWORD", "some shared password")
    st.cache_resource.clear()
    assert "Sign in with your account" in shown(new_app())


def test_repeated_failures_lock_that_username(with_accounts):
    at = new_app()
    for _ in range(5):
        sign_in(at, "alice", "wrong password here")
    sign_in(at, "alice", PW)  # correct, but locked out
    assert "Too many failed attempts" in shown(at) and not at.metric


def test_sign_out_returns_to_the_login_form(with_accounts):
    at = new_app()
    sign_in(at, "alice", PW)
    at.button(key="sign_out").click()
    at.run()
    assert "Sign in with your account" in shown(at) and not at.metric


def test_runs_started_in_the_app_record_who_started_them(with_accounts):
    from rag_workbench.storage import RunStore

    at = new_app()
    sign_in(at, "alice", PW)
    at.switch_page("src/rag_workbench/ui/views/new_run.py")
    at.run()
    at.text_input(key="run_name").set_value("by-alice")
    at.button(key="start_run").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    [run] = [r for r in RunStore(with_accounts.db_path).list_runs() if r.name == "by-alice"]
    assert run.config["started_by"] == "alice"
