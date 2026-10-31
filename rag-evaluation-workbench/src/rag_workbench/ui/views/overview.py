"""Overview: what exists, what happened recently, how runs compare on one metric."""

import pandas as pd
import streamlit as st

from rag_workbench.history import search_runs
from rag_workbench.reporting import metric_label, summary_dataframe
from rag_workbench.ui.auth import visible_runs
from rag_workbench.ui.components import score_chart, status_badge
from rag_workbench.ui.state import context_or_stop, select_run, short_id

ctx = context_or_stop()
runs = visible_runs(ctx.settings, ctx.store.list_runs())

st.title("RAG Evaluation Workbench")
st.markdown("Evaluate a retrieval-augmented question-answering pipeline over a dataset, inspect every answer "
            "with the context it was given, and compare runs. Works fully offline; OpenAI generation and "
            "DeepEval judge metrics are available when `OPENAI_API_KEY` is configured.")

own = [r for r in runs if r.status != "imported"]
imported = [r for r in runs if r.status == "imported"]
cols = st.columns(4)
cols[0].metric("Runs stored", len(runs), help="Including imported run bundles")
cols[1].metric("New runs", len(own))
cols[2].metric("Cases evaluated", sum(r.n_cases for r in own))
cols[3].metric("OpenAI key", "configured" if ctx.settings.has_openai_key else "not set",
               help="Without a key: offline provider, BM25 retrieval and lexical metrics only.")

if not own:
    with st.container(border=True):
        st.markdown("**No evaluations run yet.** Start with an offline run: BM25 retrieval, an extractive "
                    "answer baseline and lexical metrics. It takes a few seconds at most and needs no API key.")
        st.page_link("src/rag_workbench/ui/views/new_run.py", label="Configure a new evaluation",
                     icon=":material/play_circle:")

if not runs:
    st.stop()

st.header("Recent runs")
filter_cols = st.columns([3, 2])
query = filter_cols[0].text_input("Search runs", key="overview_search",
                                  placeholder="name, note, tag, dataset, provider ...",
                                  help="Every word must appear in the run's name, notes, tags, id, status, provider, "
                                       "retriever or dataset/document file name.")
all_tags = sorted({t for r in runs for t in r.tags})
tag = filter_cols[1].selectbox("Tag", ["(any)", *all_tags], key="overview_tag")
shown = search_runs(runs, query, tag=None if tag == "(any)" else tag)
if not shown:
    st.info(f"No run matches ({len(runs)} stored).")
    st.stop()
df = summary_dataframe(shown)
view = df[["name", "status", "provider", "pipeline", "retriever", "k", "n_cases", "n_errors", "created_at",
           "run_id"]].copy()
view.insert(1, "tags", [", ".join(r.tags) for r in shown])
view["created_at"] = [("imported" if r.status == "imported" else r.created_at.strftime("%Y-%m-%d %H:%M"))
                      for r in shown]
event = st.dataframe(view, hide_index=True, on_select="rerun", selection_mode="single-row", key="overview_runs",
                     column_config={"run_id": st.column_config.TextColumn("Run id"),
                                    "n_errors": st.column_config.NumberColumn("Errors"),
                                    "n_cases": st.column_config.NumberColumn("Cases"),
                                    "created_at": st.column_config.TextColumn("Created")})
picked = event.selection.rows if event and hasattr(event, "selection") else []
if picked:
    run = shown[picked[0]]
    select_run(run.id)
    st.markdown(f"Selected **{run.name}** {status_badge(run.status)}")
    st.page_link("src/rag_workbench/ui/views/results.py", label="Open run results", icon=":material/table_view:")

st.header("One metric across runs")
metric_names = sorted({m for r in runs if r.summary for m in r.summary.metrics})
if metric_names:
    default = metric_names.index("correctness") if "correctness" in metric_names else 0
    metric = st.selectbox("Metric", metric_names, index=default, format_func=metric_label)
    rows = [{"run": f"{r.name} ({short_id(r)})", "mean": r.summary.metrics[metric].mean,
             "ci_low": r.summary.metrics[metric].ci_low, "ci_high": r.summary.metrics[metric].ci_high,
             "provider": r.config.get("provider"), "scored": r.summary.metrics[metric].n_scored}
            for r in reversed(runs) if r.summary and metric in r.summary.metrics
            and r.summary.metrics[metric].mean is not None]
    chart_df = pd.DataFrame(rows)
    if chart_df.empty:
        st.info("No run has a score for this metric yet.")
    else:
        st.altair_chart(score_chart(chart_df, x="run", y="mean", ci=("ci_low", "ci_high")), width="stretch")
        st.caption("Bars: mean over scored cases · black lines: 95% bootstrap confidence interval · runs that use "
                   "different datasets, retrievers or judges are not directly comparable.")

if any(r.config.get("provenance_warnings") for r in imported):
    st.caption("Some imported runs carry provenance warnings. Read them on the run's results page before comparing.")
st.caption(f"Run store: `{ctx.settings.db_path}` · logs: `{ctx.settings.log_path}`")
