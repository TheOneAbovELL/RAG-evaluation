"""Inspect one run: summary statistics, per-case table, case detail with retrieved context, exports."""

from html import escape

import altair as alt
import pandas as pd
import streamlit as st

from rag_workbench.aggregate import metadata_keys, slice_results
from rag_workbench.history import MAX_NOTES_CHARS, TagError, normalise_tags, parse_tag_list, validate_notes
from rag_workbench.reporting import (
    EXPORT_FORMATS,
    cases_dataframe,
    export_run,
    metric_label,
    run_metrics,
    safe_filename,
)
from rag_workbench.ui.auth import can, visible_runs
from rag_workbench.ui.components import family_caption, fmt, metric_columns_config, provenance_warnings, status_badge
from rag_workbench.ui.state import context_or_stop, run_label, select_run, selected_run_id

ctx = context_or_stop()
runs = visible_runs(ctx.settings, ctx.store.list_runs())
st.title("Run results")
if not runs:
    st.info("No runs stored yet.")
    st.page_link("src/rag_workbench/ui/views/new_run.py", label="Run an evaluation", icon=":material/play_circle:")
    st.stop()

ids = [r.id for r in runs]
# A ?run=<id> query parameter (shareable deep link) takes precedence over the session selection.
wanted = st.query_params.get("run") if st.query_params.get("run") in ids else selected_run_id()
run_id = st.selectbox("Run", ids, index=ids.index(wanted) if wanted in ids else 0,
                      format_func=lambda i: run_label(runs[ids.index(i)]), key="results_run")
select_run(run_id)
run = ctx.store.get_run(run_id)
if run is None:  # deleted in another session since the list was read
    st.error("This run no longer exists. Pick another run.")
    st.stop()
results = ctx.store.get_case_results(run_id)
metrics = run_metrics(run)
cfg = run.config

st.markdown(f"## {run.name} {status_badge(run.status)}")
# Config values can come from imported bundles, so every value is HTML-escaped before entering the markup.
facts = [("provider", cfg.get("provider")), ("pipeline", cfg.get("pipeline")), ("retriever", cfg.get("retriever")),
         ("k", cfg.get("k")), ("generator", cfg.get("generator_model")), ("judge", cfg.get("judge_model") or "—")]
st.markdown("<span class='eval-muted'>" + " · ".join(f"{label} <b>{escape(str(value))}</b>" for label, value in facts)
            + f" · id <code>{escape(run.id)}</code></span>", unsafe_allow_html=True)
provenance_warnings(run)
if run.status in {"cancelled", "interrupted"}:
    st.warning(f"This run was {run.status}: {len(results)} of {run.n_cases} cases were evaluated.")
if run.tags:
    st.caption("Tags: " + ", ".join(f"`{t}`" for t in run.tags))
if run.notes:
    st.caption(f"Notes: {run.notes}")

summary = run.summary
if summary is None:
    st.info("This run has no summary yet (it may still be running).")
    st.stop()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Cases", f"{summary.n_ok}/{summary.n_cases}", help="Succeeded / evaluated")
k2.metric("Errors", summary.n_error)
k3.metric("Mean latency", fmt(summary.mean_latency_ms, 1, " ms"), help=f"p95 {fmt(summary.p95_latency_ms, 1)} ms")
tokens = (summary.total_prompt_tokens or 0) + (summary.total_completion_tokens or 0)
k4.metric("Tokens", tokens if summary.total_prompt_tokens is not None else "—",
          help=f"Cost: {fmt(summary.total_cost_usd, 4)} USD (set RAGWB_PRICE_* to compute cost)")

TAB_NAMES = ["Summary", "Cases", "Case detail", "Configuration", "Export & manage"]
TAB_LINKS = {"summary": "Summary", "cases": "Cases", "case": "Case detail", "config": "Configuration",
             "export": "Export & manage"}
tab_summary, tab_cases, tab_detail, tab_config, tab_export = st.tabs(
    TAB_NAMES, default=TAB_LINKS.get(st.query_params.get("tab", ""), "Summary"))

with tab_summary:
    rows = []
    for name, m in summary.metrics.items():
        rows.append({"Metric": metric_label(name), "Method": family_caption(name), "Mean": m.mean,
                     "95% CI low": m.ci_low, "95% CI high": m.ci_high, "Median": m.median, "Std": m.std,
                     "Pass rate": m.pass_rate, "Threshold": m.threshold, "Scored": m.n_scored,
                     "Skipped": m.n_skipped, "Errors": m.n_error})
    st.dataframe(pd.DataFrame(rows), hide_index=True, column_config={
        c: st.column_config.NumberColumn(format="%.3f") for c in ("Mean", "95% CI low", "95% CI high", "Median", "Std")}
        | {"Pass rate": st.column_config.ProgressColumn(min_value=0, max_value=1, format="percent"),
           "Threshold": st.column_config.NumberColumn(format="%.2f")})
    st.caption("Means exclude skipped and errored cases (never counted as zero). Intervals are percentile "
               "bootstrap intervals over cases: they reflect sampling of these questions, not judge noise.")
    keys = metadata_keys(results)
    if keys:
        st.markdown("**Break down by dataset metadata**")
        by = st.selectbox("Metadata field", keys, key="slice_by",
                          help="Groups the cases by this field of the dataset rows, e.g. answerable vs unanswerable.")
        thresholds = {n: m.threshold for n, m in summary.metrics.items()}
        slice_rows = [{"Slice": row.value, "Cases": row.n_cases, "OK": row.n_ok}
                      | {f"{metric_label(n)} mean": row.metrics[n].mean for n in summary.metrics}
                      for row in slice_results(results, by, list(summary.metrics), thresholds)]
        st.dataframe(pd.DataFrame(slice_rows), hide_index=True, column_config={
            f"{metric_label(n)} mean": st.column_config.NumberColumn(format="%.3f") for n in summary.metrics})
        st.caption("Small slices have wide uncertainty; `ragwb slices` also prints how many cases were scored in each.")
    df = cases_dataframe(run, results)
    long = df.melt(id_vars=["case_id"], value_vars=[m for m in metrics if m in df], var_name="metric",
                   value_name="score").dropna()
    if not long.empty:
        long["metric"] = long["metric"].map(metric_label)
        chart = alt.Chart(long).mark_bar().encode(
            x=alt.X("score:Q", bin=alt.Bin(extent=[0, 1], step=0.1), title="Score"),
            y=alt.Y("count():Q", title="Cases"), color=alt.Color("metric:N", legend=None),
            facet=alt.Facet("metric:N", columns=4, title=None)).properties(width=200, height=140)
        st.markdown("**Score distribution per metric**")
        st.altair_chart(chart)

with tab_cases:
    df = cases_dataframe(run, results)
    f1, f2, f3 = st.columns([1, 1, 2])
    status_filter = f1.multiselect("Status", ["ok", "error"], default=["ok", "error"], key="case_status")
    below = f2.selectbox("Below threshold on", ["(any)", *metrics], format_func=lambda m: m if m == "(any)"
                         else metric_label(m), key="case_below")
    text = f3.text_input("Search question / answer", key="case_search")
    view = df[df["status"].isin(status_filter)] if not df.empty else df
    if below != "(any)" and not view.empty:
        view = view[view[f"{below}_passed"] == False]  # noqa: E712  (None = not scored, excluded)
    if text and not view.empty:
        mask = view["question"].str.contains(text, case=False, na=False, regex=False) | \
            view["answer"].fillna("").str.contains(text, case=False, regex=False)
        view = view[mask]
    st.caption(f"{len(view)} of {len(df)} cases")
    shown = ["position", "case_id", "status", "question", "answer", *metrics, "latency_ms", "attempts", "error"]
    st.dataframe(view[[c for c in shown if c in view]] if not view.empty else view, hide_index=True,
                 column_config=metric_columns_config(metrics) | {
                     "latency_ms": st.column_config.NumberColumn("Latency (ms)", format="%.1f"),
                     "question": st.column_config.TextColumn(width="medium"),
                     "answer": st.column_config.TextColumn(width="large")})

with tab_detail:
    if not results:
        st.info("No cases recorded.")
    else:
        labels = {r.case_id: f"{r.position}. {r.question[:90]}" for r in results}
        case_ids = list(labels)
        linked = st.query_params.get("case")
        case_id = st.selectbox("Case", case_ids, index=case_ids.index(linked) if linked in case_ids else 0,
                               format_func=lambda cid: labels[cid], key="detail_case")
        case = next(r for r in results if r.case_id == case_id)
        st.markdown(f"**Question** {status_badge(case.status)}")
        st.write(case.question)
        a, b = st.columns(2)
        a.markdown("**Expected answer**")
        a.write(case.expected_answer or "_(no reference answer)_")
        b.markdown("**Pipeline answer**")
        b.write(case.answer if case.answer is not None else "_(no answer)_")
        if case.error:
            st.error(f"Error after {case.attempts} attempt(s): {case.error}")
        if case.metrics:
            st.markdown("**Metric results**")
            st.dataframe(pd.DataFrame([{"Metric": metric_label(m.name), "Status": m.status, "Score": m.score,
                                        "Threshold": m.threshold, "Passed": m.passed, "Reason": m.reason}
                                       for m in case.metrics.values()]), hide_index=True,
                         column_config={"Score": st.column_config.NumberColumn(format="%.3f"),
                                        "Reason": st.column_config.TextColumn(width="large")})
        source = {"retriever": "chunks returned by the retriever", "agent_tool": "chunks returned to the agent's tool"}
        st.markdown(f"**Context** — {source.get(case.context_source or '', 'none')}")
        for c in case.contexts:
            meta = f"rank {c.rank} · {c.chunk_id}" + (f" · page {c.page} · score {c.score:.3f}" if c.page else "")
            with st.container(border=True):
                st.caption(meta)
                st.text(c.text)  # st.text: document text is shown literally, never interpreted as markdown/HTML
        st.caption(f"Latency {fmt(case.latency_ms, 1, ' ms')} · tokens in/out {fmt(case.prompt_tokens)}/"
                   f"{fmt(case.completion_tokens)}")

with tab_config:
    st.markdown("**Run configuration** (everything needed to reproduce the run; contains no secrets)")
    st.json(cfg, expanded=False)
    st.markdown("**Environment**")
    st.json(run.environment, expanded=False)
    st.markdown(f"Dataset sha256 `{run.dataset_sha256}`  \nDocument sha256 `{run.document_sha256}`")

with tab_export:
    st.markdown("Download this run's results.")
    cols = st.columns(len(EXPORT_FORMATS))
    mime = {"csv": "text/csv", "json": "application/json", "md": "text/markdown"}
    label = {"csv": "CSV (one row per case)", "json": "JSON (full record)", "md": "Markdown report"}
    for col, fmt_name in zip(cols, EXPORT_FORMATS, strict=False):
        col.download_button(label[fmt_name], export_run(run, results, fmt_name),
                            file_name=f"{safe_filename(run.id)}.{fmt_name}", mime=mime[fmt_name],
                            key=f"download_{fmt_name}")
    st.divider()
    can_tag, can_delete = can(ctx.settings, "tag"), can(ctx.settings, "delete")
    with st.expander("Tags and notes"):
        tags_text = st.text_input("Tags (comma separated)", value=", ".join(run.tags), key=f"tags_{run.id}",
                                  disabled=not can_tag,
                                  help="Short labels such as baseline or prompt-v2; used to filter the run list.")
        notes_text = st.text_area("Notes", value=run.notes or "", max_chars=MAX_NOTES_CHARS, key=f"notes_{run.id}",
                                  disabled=not can_tag)
        if not can_tag:
            st.caption("Your account is read-only (viewer): tags and notes cannot be changed.")
        elif st.button("Save tags and notes", key="save_meta"):
            try:
                ctx.store.set_tags(run.id, normalise_tags(parse_tag_list(tags_text)))
                ctx.store.set_notes(run.id, validate_notes(notes_text))
            except TagError as exc:
                st.error(str(exc))
            else:
                st.success("Saved.")
                st.rerun()
    with st.expander("Delete this run"):
        if not can_delete:
            st.caption("Deleting runs needs an admin account.")
        else:
            st.warning("Deleting removes the run and all its case results from the local store. This cannot be undone."
                       + (" An imported run can be imported again from its bundle file."
                          if run.status == "imported" else ""))
            confirm = st.text_input("Type the run id to confirm", key="delete_confirm")
            if st.button("Delete run", disabled=confirm.strip() != run.id, key="delete_run"):
                ctx.store.delete_run(run.id)
                st.session_state.pop("selected_run_id", None)
                st.success("Run deleted.")
                st.rerun()
