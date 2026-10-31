"""Optional access control for the web app.

Two modes, chosen by what is configured (accounts take precedence):

* **Named accounts**: created with ``ragwb user add``; each person signs in with their own username and password
  (see :mod:`rag_workbench.users`). Sign-ins and failed attempts are logged with the username, and runs started
  from the app record who started them (``started_by``).
* **Shared password**: ``RAGWB_APP_PASSWORD``, one password for everybody.

Neither is a substitute for TLS (see ``start.py --ssl-cert``): without an encrypted connection credentials travel in
clear text. Failed attempts are throttled per username (and, more loosely, across all usernames) so passwords cannot
be guessed by brute force; comparisons are constant-time; passwords are never logged or rendered.
"""

from __future__ import annotations

import hmac
import logging
import threading
import time
from collections import deque
from collections.abc import Callable

import streamlit as st

from rag_workbench.config import Settings
from rag_workbench.users import UserError, UserStore, normalise_username

log = logging.getLogger(__name__)

MAX_FAILURES = 5
WINDOW_S = 60.0
SESSION_KEY = "_authenticated"
# What each role may do in the web app (viewing results, comparing and exporting are open to every signed-in user).
PERMISSIONS: dict[str, frozenset[str]] = {
    "viewer": frozenset(),
    "editor": frozenset({"run", "tag"}),
    "admin": frozenset({"run", "tag", "delete"}),
}
USER_KEY = "_user"
GLOBAL_MAX_FAILURES = 30  # across all usernames per window
MAX_TRACKED_USERNAMES = 1000


class LoginThrottle:
    """Sliding-window limiter for failed logins (thread-safe, injectable clock for tests)."""

    def __init__(self, max_failures: int = MAX_FAILURES, window_s: float = WINDOW_S,
                 clock: Callable[[], float] = time.monotonic):
        self.max_failures = max_failures
        self.window_s = window_s
        self._clock = clock
        self._failures: deque[float] = deque()
        self._lock = threading.Lock()

    def _trim(self, now: float) -> None:
        while self._failures and now - self._failures[0] >= self.window_s:
            self._failures.popleft()

    def retry_after(self) -> float:
        """Seconds until another attempt is allowed (0 when attempts are allowed now)."""
        with self._lock:
            now = self._clock()
            self._trim(now)
            if len(self._failures) < self.max_failures:
                return 0.0
            return self.window_s - (now - self._failures[0])

    def record_failure(self) -> None:
        with self._lock:
            now = self._clock()
            self._trim(now)
            self._failures.append(now)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()


def password_matches(supplied: str, expected: str) -> bool:
    return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))


class ThrottleSet:
    """Per-username limiters plus one loose global limiter. Unknown usernames are tracked too, so the lockout
    behaves identically for names that exist and names that do not."""

    def __init__(self, max_failures: int = MAX_FAILURES, window_s: float = WINDOW_S,
                 global_max: int = GLOBAL_MAX_FAILURES, clock: Callable[[], float] = time.monotonic):
        self._make = lambda limit: LoginThrottle(limit, window_s, clock)
        self._per_key: dict[str, LoginThrottle] = {}
        self._max_failures = max_failures
        self._global = self._make(global_max)
        self._lock = threading.Lock()

    def _for(self, key: str) -> LoginThrottle:
        with self._lock:
            if key not in self._per_key and len(self._per_key) >= MAX_TRACKED_USERNAMES:
                self._per_key.pop(next(iter(self._per_key)))  # bound memory against random-username floods
            return self._per_key.setdefault(key, self._make(self._max_failures))

    def retry_after(self, key: str) -> float:
        return max(self._for(key).retry_after(), self._global.retry_after())

    def record_failure(self, key: str) -> None:
        self._for(key).record_failure()
        self._global.record_failure()

    def reset(self, key: str) -> None:
        self._for(key).reset()


@st.cache_resource
def _throttle() -> LoginThrottle:
    return LoginThrottle()


@st.cache_resource
def _throttles() -> ThrottleSet:
    return ThrottleSet()


def current_user() -> str | None:
    """The signed-in username, or ``None`` (no login configured, or shared-password mode)."""
    return st.session_state.get(USER_KEY)


def _short(name: str) -> str:
    return name.strip()[:40]  # %r in the log call escapes control characters


def require_login(settings: Settings) -> None:
    """Block the page with a login form until valid credentials are entered. No-op when no login is configured."""
    if not settings.login_required:
        return
    if st.session_state.get(SESSION_KEY):
        user = current_user()
        if not (settings.has_users and user and UserStore(settings.users_path).role_of(user) is None):
            return
        # The account was removed while this session was open: end the session now.
        log.info("session ended: user %r no longer exists", user)
        for key in (SESSION_KEY, USER_KEY):
            st.session_state.pop(key, None)
    if settings.has_users:
        _login_with_accounts(UserStore(settings.users_path))
    else:
        _login_with_shared_password(settings)
    st.stop()


def _login_with_accounts(users: UserStore) -> None:
    throttles = _throttles()
    st.title("RAG Evaluation Workbench")
    st.caption("Sign in with your account.")
    with st.form("login"):
        username = st.text_input("Username", key="login_username")
        supplied = st.text_input("Password", type="password", key="login_password")
        submitted = st.form_submit_button("Sign in", type="primary")
    if not submitted:
        return
    try:
        key = normalise_username(username)
    except UserError:
        key = "?"  # one shared bucket for malformed names
    wait = throttles.retry_after(key)
    if wait > 0:
        st.error(f"Too many failed attempts. Try again in {int(wait) + 1} seconds.")
        log.warning("sign-in refused (throttled) user=%r", _short(username))
        return
    verified = users.verify(username, supplied)
    if verified:
        throttles.reset(key)
        st.session_state[SESSION_KEY] = True
        st.session_state[USER_KEY] = verified
        log.info("sign-in ok user=%r", verified)
        st.rerun()
    throttles.record_failure(key)
    log.warning("sign-in failed user=%r", _short(username))
    st.error("Incorrect username or password.")


def _login_with_shared_password(settings: Settings) -> None:
    expected = settings.app_password.get_secret_value() if settings.app_password else ""
    throttle = _throttle()
    st.title("RAG Evaluation Workbench")
    st.caption("This instance is password protected.")
    with st.form("login"):
        supplied = st.text_input("Password", type="password", key="login_password")
        submitted = st.form_submit_button("Sign in", type="primary")
    if submitted:
        wait = throttle.retry_after()
        if wait > 0:
            st.error(f"Too many failed attempts. Try again in {int(wait) + 1} seconds.")
        elif password_matches(supplied, expected):
            throttle.reset()
            st.session_state[SESSION_KEY] = True
            st.rerun()
        else:
            throttle.record_failure()
            st.error("Incorrect password.")


def current_role(settings: Settings) -> str:
    """The signed-in user's role, read from the users file on every call so changes apply immediately.

    Without named accounts (no login, or the shared password) everyone has full access, as before roles existed.
    """
    user = current_user()
    if not user or not settings.has_users:
        return "admin"
    return UserStore(settings.users_path).role_of(user) or "viewer"


def can(settings: Settings, action: str) -> bool:
    """Whether the current user may ``run``, ``tag`` or ``delete``."""
    return action in PERMISSIONS.get(current_role(settings), frozenset())


def visible_runs(settings: Settings, runs: list) -> list:
    """The runs the current user may see. Everything unless ``RAGWB_RUN_VISIBILITY=own`` with named accounts.

    In ``own`` mode admins see every run; others see the runs they started plus runs with no owner (examples, CLI
    runs and imported bundles), so seeded data stays usable.
    """
    if settings.run_visibility != "own" or not settings.has_users or current_role(settings) == "admin":
        return runs
    user = current_user()
    return [r for r in runs if not r.config.get("started_by") or r.config.get("started_by") == user]


def render_account(settings: Settings) -> None:
    """Sidebar: who is signed in, and a way to sign out. Nothing is shown when no login is configured."""
    if not settings.login_required or not st.session_state.get(SESSION_KEY):
        return
    with st.sidebar:
        user = current_user()
        if user:
            st.caption(f"Signed in as **{user}** ({current_role(settings)})")
        if user and settings.has_users:
            with st.expander("Change password"):
                with st.form("change_password", clear_on_submit=True):
                    current = st.text_input("Current password", type="password", key="pw_current")
                    new = st.text_input("New password", type="password", key="pw_new")
                    again = st.text_input("Repeat new password", type="password", key="pw_again")
                    changed = st.form_submit_button("Change password")
                if changed:
                    if new != again:
                        st.error("The new passwords do not match.")
                    else:
                        try:
                            UserStore(settings.users_path).set_password(user, new, current_password=current)
                        except UserError as exc:
                            st.error(str(exc))
                        else:
                            log.info("password changed user=%r", user)
                            st.success("Password changed.")
        if st.button("Sign out", key="sign_out"):
            log.info("sign-out user=%r", user)
            for key in (SESSION_KEY, USER_KEY):
                st.session_state.pop(key, None)
            st.rerun()
