"""Presentation helpers shared by the pages."""

from __future__ import annotations

from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from rag_workbench.metrics import METRIC_SPECS
from rag_workbench.models import RunRecord
from rag_workbench.reporting import metric_label

STATUS_COLORS = {
    "completed": "green", "partial": "orange", "failed": "red", "cancelled": "gray", "interrupted": "gray",
    "running": "blue", "imported": "violet",
}

CSS = """
<style>
  .block-container {padding-top: 2rem; max-width: 1400px;}
  div[data-testid="stMetricValue"] {font-size: 1.6rem;}
  /* Inherits the theme's text colour (works in light and dark) and dims it: about 5.7:1 on white, above the
     4.5:1 WCAG AA minimum. A fixed grey would fail in one of the two themes. */
  .eval-muted {opacity: 0.75; font-size: 0.9rem;}
  /* Section headings are h2 (page title is h1) so the outline has no skipped levels; sized like the old h3. */
  div[data-testid="stHeading"] h2 {font-size: 1.6rem; padding-top: 0.6rem;}
</style>
"""


def apply_style() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def short_path(path, root) -> str:
    """Path relative to the project root (forward slashes); absolute for files elsewhere, e.g. custom upload dirs."""
    from pathlib import Path

    p = Path(path)
    try:
        return p.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def status_badge(status: str) -> str:
    return f":{STATUS_COLORS.get(status, 'gray')}-badge[{status}]"


def fmt(value, digits: int = 3, suffix: str = "") -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}{suffix}"
    return f"{value}{suffix}"


def family_caption(metric: str) -> str:
    spec = METRIC_SPECS.get(metric)
    if not spec:
        return ""
    return {"llm_judge": "LLM judge (DeepEval)", "semantic": "embedding similarity (local model)"}.get(
        spec.family, "lexical overlap (offline)")


def provenance_warnings(run: RunRecord) -> None:
    warnings = run.config.get("provenance_warnings") or []
    if warnings:
        with st.container(border=True):
            st.markdown("**Imported run — read the provenance notes before comparing**")
            for w in warnings:
                st.markdown(f"- {w}")


def score_chart(df: pd.DataFrame, *, x: str, y: str, color: str | None = None, ci: tuple[str, str] | None = None,
                height: int = 320, y_title: str = "Mean score") -> alt.Chart:
    """Bar chart on a fixed [0, 1] scale (so differences are not visually exaggerated) with optional CI bars."""
    base = alt.Chart(df)
    enc: dict[str, Any] = {"x": alt.X(f"{x}:N", title=None, sort=None, axis=alt.Axis(labelAngle=0, labelLimit=180)),
           "y": alt.Y(f"{y}:Q", title=y_title, scale=alt.Scale(domain=[0, 1]))}
    if color:
        enc["color"] = alt.Color(f"{color}:N", title=None)
        enc["xOffset"] = alt.XOffset(f"{color}:N")
    tooltip = [alt.Tooltip(f"{c}:Q" if pd.api.types.is_numeric_dtype(df[c]) else f"{c}:N", format=".3f"
                           if pd.api.types.is_numeric_dtype(df[c]) else "") for c in df.columns]
    bars = base.mark_bar().encode(**enc, tooltip=tooltip)
    if ci:
        err_enc = {k: v for k, v in enc.items() if k in ("x", "xOffset")}
        errors = base.mark_rule(color="black", strokeWidth=1.5).encode(
            **err_enc, y=alt.Y(f"{ci[0]}:Q"), y2=alt.Y2(f"{ci[1]}:Q"))
        return (bars + errors).properties(height=height)
    return bars.properties(height=height)


def metric_columns_config(metrics: list[str]) -> dict:
    return {m: st.column_config.NumberColumn(metric_label(m), format="%.3f", help=METRIC_SPECS[m].description
                                             if m in METRIC_SPECS else None) for m in metrics}
