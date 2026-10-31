import io

import pytest
import streamlit as st
from test_ui import seeded_run
from test_users import PW, new_app, shown, sign_in

from rag_workbench.cli import main
from rag_workbench.users import UserError, UserStore

NEW_PW = "a brand new password 42"


@pytest.fixture(autouse=True)
def fresh_cache():
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()


@pytest.fixture
def team(settings):
    users = UserStore(settings.users_path)
    users.add("ada", PW, role="admin")
    users.add("eddie", PW, role="editor")
    users.add("vera", PW, role="viewer")
    return users


# ------------------------------------------------------------------ store rules
def test_the_last_admin_cannot_be_removed_or_demoted_while_others_exist(team):
    with pytest.raises(UserError, match="last admin"):
        team.remove("ada")
    with pytest.raises(UserError, match="last admin"):
        team.set_role("ada", "editor")
    assert team.role_of("ada") == "admin" and "ada" in team.names()
    team.set_role("eddie", "admin")  # a second admin makes the first replaceable
    assert team.set_role("ada", "editor") and team.remove("ada")


def test_force_overrides_the_last_admin_guard_and_a_single_account_is_always_removable(tmp_path):
    users = UserStore(tmp_path / "u.json")
    users.add("a", PW, role="admin")
    users.add("b", PW)
    assert users.remove("a", force=True)
    only = UserStore(tmp_path / "solo.json")
    only.add("x", PW, role="admin")
    assert only.remove("x")  # nobody else to lock out


def test_set_password_keeps_role_and_checks_the_current_password(team):
    created = team.entries()[0]["created"]
    with pytest.raises(UserError, match="current password"):
        team.set_password("ada", NEW_PW, current_password="wrong password here")
    with pytest.raises(UserError, match="Passwords must be"):
        team.set_password("ada", "short")
    assert team.set_password("ada", NEW_PW, current_password=PW)
    assert team.verify("ada", NEW_PW) == "ada" and team.verify("ada", PW) is None
    assert team.role_of("ada") == "admin" and team.entries()[0]["created"] == created
    assert not team.set_password("ghost", NEW_PW)


def test_entries_never_contain_secret_material(team):
    entries = team.entries()
    assert [e["user"] for e in entries] == ["ada", "eddie", "vera"]
    assert all(set(e) == {"user", "role", "created"} for e in entries)


def test_cli_set_password_and_force(capsys, monkeypatch, team):
    monkeypatch.setattr("sys.stdin", io.StringIO(NEW_PW + "\n"))
    assert main(["user", "set-password", "vera", "--password-stdin"]) == 0
    assert team.verify("vera", NEW_PW) == "vera"
    assert main(["user", "remove", "ada"]) == 1
    assert "last admin" in capsys.readouterr().err
    assert main(["user", "remove", "ada", "--force"]) == 0


# ------------------------------------------------------------------ the web app
def test_a_non_admin_cannot_even_route_to_the_accounts_page(team):
    at = new_app()
    sign_in(at, "eddie", PW)
    with pytest.raises(ValueError, match="Could not find a navigation page"):
        at.switch_page("src/rag_workbench/ui/views/users.py")  # the page is not registered for editors or viewers
    admin = new_app()
    sign_in(admin, "ada", PW)
    admin.run()  # an admin's navigation includes it
    admin.switch_page("src/rag_workbench/ui/views/users.py")


def test_an_admin_can_add_change_reset_and_remove_accounts(settings, team):
    at = new_app()
    sign_in(at, "ada", PW)
    at.switch_page("src/rag_workbench/ui/views/users.py")
    at.run()
    assert not at.exception, [e.value for e in at.exception]

    at.text_input(key="add_name").set_value("newbie")
    at.text_input(key="add_password").set_value(NEW_PW)
    at.selectbox(key="add_role").select("viewer")
    at.button(key="add_user_submit").click()
    at.run()
    assert team.role_of("newbie") == "viewer" and team.verify("newbie", NEW_PW) == "newbie"

    at.selectbox(key="target_user").select("newbie")
    at.run()
    at.selectbox(key="set_role_value").select("editor")
    at.button(key="set_role_submit").click()
    at.run()
    assert team.role_of("newbie") == "editor"

    at.text_input(key="reset_value").set_value("another long password 99")
    at.button(key="reset_submit").click()
    at.run()
    assert team.verify("newbie", "another long password 99") == "newbie" and team.verify("newbie", NEW_PW) is None

    at.text_input(key="remove_confirm").set_value("newbie")
    at.run()
    at.button(key="remove_user").click()
    at.run()
    assert team.role_of("newbie") is None
    assert not at.exception, [e.value for e in at.exception]


def test_the_page_shows_validation_errors_instead_of_crashing(team):
    at = new_app()
    sign_in(at, "ada", PW)
    at.switch_page("src/rag_workbench/ui/views/users.py")
    at.run()
    at.text_input(key="add_name").set_value("bad name!")
    at.text_input(key="add_password").set_value(NEW_PW)
    at.button(key="add_user_submit").click()
    at.run()
    assert not at.exception and any("Usernames" in e.value for e in at.error)
    at.selectbox(key="target_user").select("ada")
    at.run()
    assert any("cannot remove the account you are signed in" in c.value for c in at.caption)


def test_a_user_can_change_their_own_password(team):
    at = new_app()
    sign_in(at, "vera", PW)
    at.text_input(key="pw_current").set_value(PW)
    at.text_input(key="pw_new").set_value(NEW_PW)
    at.text_input(key="pw_again").set_value(NEW_PW)
    next(b for b in at.button if b.label == "Change password").click()
    at.run()
    assert team.verify("vera", NEW_PW) == "vera" and team.verify("vera", PW) is None
    at.text_input(key="pw_current").set_value("not my password")
    at.text_input(key="pw_new").set_value("yet another password 7")
    at.text_input(key="pw_again").set_value("yet another password 7")
    next(b for b in at.button if b.label == "Change password").click()
    at.run()
    assert any("current password is not correct" in e.value for e in at.error)
    assert team.verify("vera", NEW_PW) == "vera"  # unchanged by the failed attempt


# ------------------------------------------------------------------ per-user run visibility
@pytest.fixture
def own_mode(monkeypatch):
    monkeypatch.setenv("RAGWB_RUN_VISIBILITY", "own")


def test_own_mode_hides_other_users_runs_but_not_shared_ones(settings, team, own_mode):
    shared = seeded_run(settings, name="shared-example")  # no owner
    mine = seeded_run(settings, name="mine", started_by="eddie")
    theirs = seeded_run(settings, name="theirs", started_by="vera")

    at = new_app()
    sign_in(at, "eddie", PW)
    names = {r["name"] for r in at.dataframe[0].value.to_dict("records")}
    assert names == {"shared-example", "mine"}
    at.switch_page("src/rag_workbench/ui/views/results.py")
    at.run()
    labels = " | ".join(at.selectbox(key="results_run").options)
    assert shared.id[-6:] in labels and mine.id[-6:] in labels and theirs.id[-6:] not in labels


def test_own_mode_shows_everything_to_admins_and_is_off_by_default(settings, team, monkeypatch):
    seeded_run(settings, name="a", started_by="eddie")
    seeded_run(settings, name="b", started_by="vera")
    at = new_app()  # default: shared
    sign_in(at, "vera", PW)
    assert len(at.dataframe[0].value) == 2
    monkeypatch.setenv("RAGWB_RUN_VISIBILITY", "own")
    st.cache_resource.clear()
    admin = new_app()
    sign_in(admin, "ada", PW)
    assert len(admin.dataframe[0].value) == 2  # admins are not filtered
    assert shown(admin)  # page rendered


def test_own_mode_does_not_leak_other_users_runs_through_the_settings_run_count(settings, team, own_mode):
    seeded_run(settings, name="shared-example")
    seeded_run(settings, name="mine", started_by="eddie")
    seeded_run(settings, name="theirs", started_by="vera")
    at = new_app()
    sign_in(at, "eddie", PW)
    at.switch_page("src/rag_workbench/ui/views/settings.py")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    text = "\n".join(m.value for m in at.markdown)
    assert "(2 runs)" in text and "(3 runs)" not in text
