"""RAG Evaluation Workbench — Streamlit entry point:  uv run streamlit run streamlit_app.py

Defines the page navigation; every page lives in ``src/rag_workbench/ui/views`` and talks to the
``rag_workbench`` package directly (no separate backend process).
"""

import os
from pathlib import Path

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "1")

import streamlit as st

from rag_workbench.ui.auth import current_role, render_account, require_login
from rag_workbench.ui.components import apply_style
from rag_workbench.ui.state import context_or_stop

st.set_page_config(page_title="RAG Evaluation Workbench", page_icon=":material/fact_check:", layout="wide")
apply_style()
require_login(context_or_stop().settings)  # no-op unless RAGWB_APP_PASSWORD is set or user accounts exist
render_account(context_or_stop().settings)

VIEWS = Path(__file__).resolve().parent / "src" / "rag_workbench" / "ui" / "views"
pages = {
    "Evaluate": [
        st.Page(VIEWS / "overview.py", title="Overview", icon=":material/dashboard:", default=True),
        st.Page(VIEWS / "new_run.py", title="New evaluation", icon=":material/play_circle:", url_path="new-run"),
    ],
    "Analyse": [
        st.Page(VIEWS / "results.py", title="Run results", icon=":material/table_view:", url_path="results"),
        st.Page(VIEWS / "compare.py", title="Compare runs", icon=":material/compare_arrows:", url_path="compare"),
    ],
    "Data & system": [
        st.Page(VIEWS / "data.py", title="Datasets & retrieval", icon=":material/dataset:", url_path="data"),
        st.Page(VIEWS / "settings.py", title="Settings & metrics", icon=":material/settings:", url_path="settings"),
    ],
}

if context_or_stop().settings.has_users and current_role(context_or_stop().settings) == "admin":
    pages["Admin"] = [st.Page(VIEWS / "users.py", title="Accounts", icon=":material/group:", url_path="accounts")]

st.navigation(pages).run()
