"""Cached application context and small session-state helpers."""

from __future__ import annotations

import re

import streamlit as st

from rag_workbench.config import ConfigError
from rag_workbench.models import RunRecord
from rag_workbench.services import AppContext, open_context

SELECTED_RUN = "selected_run_id"
GENERATED_ID = re.compile(r"^\d{8}-\d{6}-.+-[0-9a-f]{6}$")  # see runner.new_run_id


@st.cache_resource(show_spinner="Opening the run store…")
def get_context() -> AppContext:
    """One context per server process: settings and the SQLite run store."""
    return open_context(console_logging=False)


def context_or_stop() -> AppContext:
    try:
        return get_context()
    except ConfigError as exc:
        st.error(f"Configuration problem: {exc}")
        st.info("Fix the variable in `.env` (see `.env.example`) and restart the app.")
        st.stop()


def select_run(run_id: str) -> None:
    st.session_state[SELECTED_RUN] = run_id


def selected_run_id() -> str | None:
    return st.session_state.get(SELECTED_RUN)


def short_id(run: RunRecord) -> str:
    """Distinguishing part of a run id: the random suffix of generated ids, or the whole id otherwise."""
    return run.id.rsplit("-", 1)[-1] if GENERATED_ID.match(run.id) else run.id


def run_label(run: RunRecord) -> str:
    when = run.created_at.strftime("%Y-%m-%d %H:%M")
    parts = [run.name, run.status] + ([] if run.status == "imported" else [when]) + [short_id(run)]
    return " · ".join(parts)
