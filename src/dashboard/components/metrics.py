"""Reusable metric display components."""

import streamlit as st
from src.core.config import format_size


def format_size_short(size_bytes: int) -> str:
    if size_bytes is None:
        return "0 B"
    return format_size(size_bytes)


def metric_row(metrics: list[tuple[str, str, str | None]]):
    """Display a row of st.metric cards. Each tuple: (label, value, delta)."""
    cols = st.columns(len(metrics))
    for col, (label, value, delta) in zip(cols, metrics):
        col.metric(label, value, delta)


def health_badge(score: int, grade: str):
    """Display a health score badge."""
    if score >= 90:
        color = "green"
    elif score >= 75:
        color = "blue"
    elif score >= 60:
        color = "orange"
    else:
        color = "red"

    st.markdown(
        f"<div style='text-align:center; padding:1rem; "
        f"border:2px solid {color}; border-radius:12px; "
        f"background: linear-gradient(135deg, {color}11, {color}22);'>"
        f"<h1 style='margin:0; color:{color};'>{grade}</h1>"
        f"<p style='margin:0; font-size:1.5rem;'>{score}/100</p>"
        f"</div>",
        unsafe_allow_html=True,
    )


def severity_icon(severity: str) -> str:
    return {"high": "🔴", "medium": "🟡", "low": "🔵"}.get(severity, "⚪")
