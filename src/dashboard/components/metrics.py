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
    """Display a health score badge with gradient background and progress bar."""
    if score >= 90:
        color, bg = "#22c55e", "rgba(34,197,94,0.08)"
    elif score >= 75:
        color, bg = "#3b82f6", "rgba(59,130,246,0.08)"
    elif score >= 60:
        color, bg = "#f59e0b", "rgba(245,158,11,0.08)"
    else:
        color, bg = "#ef4444", "rgba(239,68,68,0.08)"

    pct = score / 100
    st.markdown(
        f"<div style='text-align:center; padding:1.2rem; "
        f"border:2px solid {color}; border-radius:12px; "
        f"background:{bg};'>"
        f"<h1 style='margin:0; color:{color}; font-size:3rem;'>{grade}</h1>"
        f"<p style='margin:4px 0 8px; font-size:1.4rem; font-weight:600;'>{score}/100</p>"
        f"<div style='background:rgba(128,128,128,0.15); border-radius:4px; "
        f"height:6px; overflow:hidden;'>"
        f"<div style='width:{pct*100:.0f}%; height:100%; background:{color}; "
        f"border-radius:4px;'></div></div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def severity_icon(severity: str) -> str:
    return {"high": "🔴", "medium": "🟡", "low": "🔵"}.get(severity, "⚪")
