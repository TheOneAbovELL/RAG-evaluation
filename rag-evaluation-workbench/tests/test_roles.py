import io

import pytest
import streamlit as st
from test_ui import seeded_run
from test_users import PW, new_app, shown, sign_in

from rag_workbench.cli import main
from rag_workbench.users import DEFAULT_ROLE, ROLES, UserError, UserStore


@pytest.fixture(autouse=True)
def fresh_cache():
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()


@pytest.fixture
def team(settings):
    users = UserStore(settings.users_path)
    users.add("vera", PW, role="viewer")
    users.add("eddie", PW, role="editor")
    users.add("ada", PW, role="admin")
    return users


# ------------------------------------------------------------------ store
def test_roles_are_stored_and_default_to_editor(tmp_path):
    users = UserStore(tmp_path / "users.json")
    users.add("a", PW)
    users.add("b", PW, role="admin")
    assert users.role_of("a") == DEFAULT_ROLE == "editor" and users.role_of("b") == "admin"
    assert users.role_of("nobody") is None and users.role_of("bad name!") is None
    assert ROLES == ("viewer", "editor", "admin")


def test_unknown_roles_are_rejected_and_unrecognised_stored_roles_get_least_access(tmp_path):
    users = UserStore(tmp_path / "users.json")
    with pytest.raises(UserError, match="Unknown role"):
        users.add("a", PW, role="root")
    users.add("a", PW)
    import json

    data = json.loads(users.path.read_text(encoding="utf-8"))
    data["users"]["a"]["role"] = "superuser"
    users.path.write_text(json.dumps(data), encoding="utf-8")
    assert users.role_of("a") == "viewer"  # a tampered or future role never grants more access
    del data["users"]["a"]["role"]
    users.path.write_text(json.dumps(data), encoding="utf-8")
    assert users.role_of("a") == "editor"  # accounts from before roles existed keep their old access


def test_set_role(tmp_path):
    users = UserStore(tmp_path / "users.json")
    users.add("a", PW)
    assert users.set_role("A", "admin") and users.role_of("a") == "admin"
    assert not users.set_role("ghost", "viewer")
    with pytest.raises(UserError, match="Unknown role"):
        users.set_role("a", "boss")


def test_cli_roles(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(PW + "\n"))
    assert main(["user", "add", "carol", "--role", "viewer", "--password-stdin"]) == 0
    assert "carol (viewer)" in capsys.readouterr().out
    assert main(["user", "list"]) == 0
    assert "carol  (viewer)" in capsys.readouterr().out
    assert main(["user", "set-role", "carol", "--role", "admin"]) == 0
    assert main(["user", "set-role", "carol"]) == 1  # --role is required
    assert main(["user", "set-role", "ghost", "--role", "admin"]) == 1
    capsys.readouterr()
    assert main(["user", "list"]) == 0
    assert "carol  (admin)" in capsys.readouterr().out


# ------------------------------------------------------------------ the web app
def test_a_viewer_can_browse_but_not_start_runs_edit_or_delete(settings, team):
    run = seeded_run(settings, name="r")
    at = new_app()
    sign_in(at, "vera", PW)
    assert "Signed in as **vera** (viewer)" in shown(at)
    at.switch_page("src/rag_workbench/ui/views/new_run.py")
    at.run()
    assert not [b for b in at.button if b.key == "start_run"]
    assert any("read-only" in w.value for w in at.warning)
    at.switch_page("src/rag_workbench/ui/views/results.py")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.text_input(key=f"tags_{run.id}").disabled
    assert not [b for b in at.button if b.key in {"save_meta", "delete_run"}]
    assert "Deleting runs needs an admin account" in shown(at)


def test_an_editor_can_run_and_tag_but_not_delete(settings, team, store):
    run = seeded_run(settings, name="r")
    at = new_app()
    sign_in(at, "eddie", PW)
    at.switch_page("src/rag_workbench/ui/views/results.py")
    at.run()
    at.text_input(key=f"tags_{run.id}").set_value("reviewed")
    at.button(key="save_meta").click()
    at.run()
    assert store.get_run(run.id).tags == ["reviewed"]
    assert not [b for b in at.button if b.key == "delete_run"]
    at.switch_page("src/rag_workbench/ui/views/new_run.py")
    at.run()
    assert [b for b in at.button if b.key == "start_run"]


def test_an_admin_can_delete(settings, team, store):
    run = seeded_run(settings, name="r")
    at = new_app()
    sign_in(at, "ada", PW)
    at.switch_page("src/rag_workbench/ui/views/results.py")
    at.run()
    at.text_input(key="delete_confirm").set_value(run.id)
    at.run()  # the button stays disabled until the id has been typed
    at.button(key="delete_run").click()
    at.run()
    assert store.get_run(run.id) is None


def test_removing_a_user_ends_their_open_session_on_the_next_page_load(settings, team):
    at = new_app()
    sign_in(at, "eddie", PW)
    assert at.metric  # signed in
    team.remove("eddie")
    at.run()
    assert not at.metric and "Sign in with your account" in shown(at)


def test_a_role_change_applies_to_an_open_session_without_signing_in_again(settings, team):
    run = seeded_run(settings, name="r")
    at = new_app()
    sign_in(at, "eddie", PW)
    at.switch_page("src/rag_workbench/ui/views/results.py")
    at.run()
    assert not at.text_input(key=f"tags_{run.id}").disabled
    team.set_role("eddie", "viewer")
    at.run()
    assert at.text_input(key=f"tags_{run.id}").disabled


def test_without_accounts_everyone_keeps_full_access(settings):
    run = seeded_run(settings, name="r")
    at = new_app("src/rag_workbench/ui/views/results.py")
    assert not at.text_input(key=f"tags_{run.id}").disabled
    assert at.text_input(key="delete_confirm") is not None  # the delete section is offered
    assert [b for b in at.button if b.key == "delete_run"]
