"""Effective configuration (no secrets), metric catalogue, environment variables and limitations."""

import pandas as pd
import streamlit as st

from rag_workbench import __version__
from rag_workbench.config import ENV_VARS
from rag_workbench.maintenance import run_doctor
from rag_workbench.metrics import METRIC_SPECS
from rag_workbench.ui.auth import visible_runs
from rag_workbench.ui.state import context_or_stop

ctx = context_or_stop()
s = ctx.settings
st.title("Settings & metrics")

st.header("Health checks")
st.caption("The same checks as `ragwb doctor`. No network calls are made.")
checks = run_doctor(s)
st.dataframe(pd.DataFrame([{"check": c.name, "status": c.status, "detail": c.detail} for c in checks]),
             hide_index=True, column_config={"detail": st.column_config.TextColumn(width="large")})
if any(c.status == "fail" for c in checks):
    st.error("At least one check failed; see the detail column.")
elif any(c.status == "warn" for c in checks):
    st.warning("Some checks need attention; see the detail column.")
else:
    st.success("All checks passed.")

st.header("Effective configuration")
st.caption("Read from environment variables and `.env` at start-up. Restart the app after changing them. "
           "The API key itself is never displayed.")
public = s.public_dict()
st.dataframe(pd.DataFrame([{"setting": k, "value": str(v)} for k, v in public.items()]), hide_index=True)

with st.expander("Environment variables"):
    st.dataframe(pd.DataFrame([{"variable": var, "setting": field} for var, field in ENV_VARS.items()]),
                 hide_index=True)

st.header("Metric catalogue")
st.dataframe(pd.DataFrame([{
    "metric": name, "label": spec.label, "family": spec.family, "default threshold": spec.default_threshold,
    "needs reference": spec.requires_reference, "needs context": spec.requires_context,
    "needs OpenAI": spec.requires_openai, "description": spec.description} for name, spec in METRIC_SPECS.items()]),
    hide_index=True, column_config={"description": st.column_config.TextColumn(width="large")})
st.markdown(
    "- **Lexical** metrics compare words, not meaning: a correct paraphrase can score low.\n"
    "- **Judge** metrics are an LLM's assessment under a rubric (DeepEval). They vary with the judge model and "
    "are not ground truth.\n"
    "- Skipped metrics (missing reference, missing context, abstained answer) are excluded from means.\n"
    "- The offline generator is an extractive baseline: its groundedness is ~1.0 by construction because it "
    "copies sentences from the context.")

st.header("Storage")
runs = visible_runs(s, ctx.store.list_runs())  # in own-visibility mode the count must not leak other users' runs
st.markdown(f"- Run store: `{s.db_path}` ({len(runs)} runs)\n- Uploads: `{s.uploads_dir}`\n"
            f"- Exports (CLI): `{s.exports_dir}`\n- Log file: `{s.log_path}`")
st.caption(f"RAG Evaluation Workbench {__version__}. To reset local data, stop the app and delete the data "
           "directory; nothing else is affected.")
