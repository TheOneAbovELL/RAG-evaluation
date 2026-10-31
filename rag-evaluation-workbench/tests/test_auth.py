import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from rag_workbench.config import PROJECT_ROOT, load_settings
from rag_workbench.ui.auth import LoginThrottle, password_matches

ENTRY = str(PROJECT_ROOT / "streamlit_app.py")
PASSWORD = "correct-horse-battery"


# ---------------------------------------------------------------- units
def test_password_comparison():
    assert password_matches(PASSWORD, PASSWORD)
    assert not password_matches("wrong", PASSWORD)
    assert not password_matches("", PASSWORD)
    assert password_matches("pässwörd-密码", "pässwörd-密码")  # non-ASCII is compared byte-for-byte


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_throttle_locks_after_the_limit_and_recovers():
    clock = Clock()
    throttle = LoginThrottle(max_failures=3, window_s=60, clock=clock)
    for _ in range(2):
        throttle.record_failure()
        assert throttle.retry_after() == 0
    throttle.record_failure()
    assert throttle.retry_after() == pytest.approx(60)
    clock.now += 45
    assert throttle.retry_after() == pytest.approx(15)
    clock.now += 16
    assert throttle.retry_after() == 0  # the window has passed
    throttle.record_failure()
    assert throttle.retry_after() == 0  # old failures expired; one new failure is under the limit


def test_throttle_reset_clears_failures():
    throttle = LoginThrottle(max_failures=1, window_s=60, clock=Clock())
    throttle.record_failure()
    assert throttle.retry_after() > 0
    throttle.reset()
    assert throttle.retry_after() == 0


def test_settings_never_expose_the_password():
    settings = load_settings({"RAGWB_APP_PASSWORD": PASSWORD}, dotenv=False)
    assert settings.has_app_password
    assert PASSWORD not in repr(settings) and PASSWORD not in str(settings.public_dict())
    assert settings.public_dict()["app_password_configured"] is True
    assert PASSWORD in settings.secret_values()  # available to the log redactor only
    assert not load_settings({}, dotenv=False).has_app_password
    assert not load_settings({"RAGWB_APP_PASSWORD": "   "}, dotenv=False).has_app_password


# ---------------------------------------------------------------- app journeys
@pytest.fixture
def protected(monkeypatch):
    monkeypatch.setenv("RAGWB_APP_PASSWORD", PASSWORD)
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()


def new_app(page=None):
    at = AppTest.from_file(ENTRY, default_timeout=120).run()
    if page:
        at.switch_page(page)
        at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def shown(at):
    return "\n".join([t.value for t in at.title] + [c.value for c in at.caption] + [str(e.value) for e in at.error])


def sign_in(at, password):
    at.text_input(key="login_password").set_value(password)
    at.button[0].click()
    return at.run()


def test_without_a_password_the_app_opens_directly():
    st.cache_resource.clear()
    at = new_app()
    assert "password protected" not in shown(at)
    assert {m.label for m in at.metric} >= {"Runs stored", "OpenAI key"}  # the overview renders straight away


def test_protected_app_blocks_every_page_until_sign_in(protected):
    at = new_app()
    assert "password protected" in shown(at)
    assert not at.metric  # no application content leaked
    deep = new_app("src/rag_workbench/ui/views/results.py")
    assert "password protected" in shown(deep) and not deep.dataframe


def test_wrong_then_right_password(protected):
    at = new_app()
    sign_in(at, "nope")
    assert "Incorrect password." in shown(at) and not at.metric
    sign_in(at, PASSWORD)
    assert not at.exception, [e.value for e in at.exception]
    assert "password protected" not in shown(at)
    assert {m.label for m in at.metric} >= {"Runs stored", "OpenAI key"}  # the overview is now visible


def test_repeated_failures_lock_out_even_the_right_password(protected):
    at = new_app()
    for _ in range(5):
        sign_in(at, "guess")
    sign_in(at, PASSWORD)
    assert "Too many failed attempts" in shown(at) and not at.metric
