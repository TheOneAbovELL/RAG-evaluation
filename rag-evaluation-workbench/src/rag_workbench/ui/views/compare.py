"""Compare runs: configuration differences, metric means with CIs, best run per metric, paired analysis."""

import pandas as pd
import streamlit as st

from rag_workbench.aggregate import paired_comparison
from rag_workbench.reporting import comparison_dataframe, metric_label, run_metrics
from rag_workbench.ui.auth import visible_runs
from rag_workbench.ui.components import provenance_warnings, score_chart
from rag_workbench.ui.state import context_or_stop, run_label, short_id

ctx = context_or_stop()
runs = visible_runs(ctx.settings, ctx.store.list_runs())
by_id = {r.id: r for r in runs}
st.title("Compare runs")
if len(runs) < 2:
    st.info("At least two runs are needed for a comparison.")
    st.page_link("src/rag_workbench/ui/views/new_run.py", label="Run another evaluation", icon=":material/play_circle:")
    st.stop()

linked = [i for i in st.query_params.get("runs", "").split(",") if i in by_id]  # ?runs=id1,id2 deep link
default = linked if len(linked) >= 2 else [r.id for r in runs[:3]]
chosen = st.multiselect("Runs to compare", list(by_id), default=default, format_func=lambda i: run_label(by_id[i]),
                        key="compare_runs")
if len(chosen) < 2:
    st.warning("Select at least two runs.")
    st.stop()
selected = [by_id[i] for i in chosen]

# ------------------------------------------------------------ configuration
st.header("Configuration")
fields = ["provider", "pipeline", "retriever", "k", "generator_model", "judge_model", "metrics"]
table = {}
for r in selected:
    column = {f: (", ".join(map(str, r.config[f])) if isinstance(r.config.get(f), list) else r.config.get(f))
              for f in fields}
    column["dataset sha256"] = (r.dataset_sha256 or "")[:12]
    column["cases"] = r.n_cases
    column["status"] = r.status
    table[f"{r.name} ({short_id(r)})"] = column
config_df = pd.DataFrame(table).astype(str)
differs = config_df.nunique(axis=1) > 1
st.dataframe(config_df.style.apply(lambda row: ["background-color: rgba(255,170,0,0.18)" if differs[row.name]
                                                else "" for _ in row], axis=1), width="stretch")
st.caption("Highlighted rows differ between the selected runs.")
if len({r.dataset_sha256 for r in selected}) > 1:
    st.warning("The runs used different datasets (or dataset versions). Cases are paired by question text, so only "
               "questions present in both runs are compared.")
if any(r.status == "imported" for r in selected):
    with st.expander("Provenance notes for imported runs"):
        for r in selected:
            if r.status == "imported":
                st.markdown(f"**{r.name}**")
                provenance_warnings(r)

# ------------------------------------------------------------------ means
st.header("Metric means")
rows = []
for r in selected:
    if not r.summary:
        continue
    for name, m in r.summary.metrics.items():
        if m.mean is not None:
            rows.append({"metric": metric_label(name), "run": f"{r.name} ({short_id(r)})", "mean": m.mean,
                         "ci_low": m.ci_low if m.ci_low is not None else m.mean,
                         "ci_high": m.ci_high if m.ci_high is not None else m.mean, "scored": m.n_scored})
means = pd.DataFrame(rows)
if means.empty:
    st.info("The selected runs have no scores.")
    st.stop()
st.altair_chart(score_chart(means, x="metric", y="mean", color="run", ci=("ci_low", "ci_high"), height=360),
                width="stretch")
st.caption("Black lines: 95% bootstrap confidence intervals. Overlapping intervals mean the difference may be "
           "sampling noise; use the paired analysis below for a sharper test.")

best_rows = []
for metric_name, group in means.groupby("metric", sort=False):
    top = group["mean"].max()
    leaders = group[(top - group["mean"]) <= 1e-9]  # ties are shown, not broken arbitrarily
    best_rows.append({"metric": metric_name, "best run": " = ".join(leaders["run"]) if len(leaders) > 1
                      else leaders["run"].iloc[0], "mean": top, "tie": len(leaders) > 1})
best = pd.DataFrame(best_rows)
st.markdown("**Best run per metric**")
st.dataframe(best, hide_index=True, column_config={"mean": st.column_config.NumberColumn(format="%.3f")})

# ----------------------------------------------------------------- paired
st.header("Paired comparison")
st.caption("Compares candidate B against baseline A case by case (same question in both runs). The mean "
           "difference and its bootstrap interval are computed over the per-case differences.")
a_col, b_col = st.columns(2)
a_id = a_col.selectbox("Baseline (A)", chosen, index=0, format_func=lambda i: run_label(by_id[i]), key="pair_a")
b_id = b_col.selectbox("Candidate (B)", chosen, index=1, format_func=lambda i: run_label(by_id[i]), key="pair_b")
if a_id == b_id:
    st.info("Choose two different runs.")
    st.stop()
run_a, run_b = by_id[a_id], by_id[b_id]
results_a, results_b = ctx.store.get_case_results(a_id), ctx.store.get_case_results(b_id)
cmp = comparison_dataframe(run_a, results_a, run_b, results_b)
if cmp.empty:
    st.info("These runs share no metric.")
    st.stop()
cmp["verdict"] = [
    "no paired cases" if n == 0 else ("B better" if sig and d > 0 else "B worse" if sig and d < 0 else "inconclusive")
    for n, sig, d in zip(cmp["paired_cases"], cmp["ci_excludes_zero"], cmp["diff_b_minus_a"].fillna(0), strict=False)]
st.dataframe(cmp.drop(columns=["metric", "ci_excludes_zero"]), hide_index=True, column_config={
    c: st.column_config.NumberColumn(format="%+.3f" if c == "diff_b_minus_a" else "%.3f")
    for c in ("mean_a", "mean_b", "diff_b_minus_a", "ci_low", "ci_high")})
st.caption("'B better/worse' only when the 95% interval of the paired difference excludes zero. With 20 cases, "
           "small differences are usually inconclusive.")

shared = [m for m in run_metrics(run_a) if m in run_metrics(run_b)]
metric = st.selectbox("Per-case differences for", shared, format_func=metric_label, key="pair_metric")
a_map = {" ".join(r.question.lower().split()): r for r in results_a}
diff_rows = []
for rb in results_b:
    ra = a_map.get(" ".join(rb.question.lower().split()))
    score_a, score_b = (ra.score(metric) if ra else None), rb.score(metric)
    if ra and score_a is not None and score_b is not None:
        diff_rows.append({"question": rb.question, "A": score_a, "B": score_b, "B - A": score_b - score_a,
                          "answer A": ra.answer, "answer B": rb.answer})
if diff_rows:
    detail = pd.DataFrame(diff_rows).sort_values("B - A")
    st.dataframe(detail, hide_index=True, column_config={
        "A": st.column_config.NumberColumn(format="%.3f"), "B": st.column_config.NumberColumn(format="%.3f"),
        "B - A": st.column_config.NumberColumn(format="%+.3f")})
    c = paired_comparison(results_a, results_b, metric)
    st.caption(f"{c.n_pairs} paired cases · B better on {c.wins}, tied on {c.ties}, worse on {c.losses}.")
else:
    st.info("No case has this metric scored in both runs.")
