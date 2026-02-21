"""Health report page — scoring, issues, and recommendations."""

import streamlit as st
from src.analysis.health import compute_health_score
from src.dashboard.components.metrics import (
    format_size_short,
    health_badge,
    severity_icon,
)


def render(db, config):
    st.subheader("File System Health Report")

    metrics = db.get_health_metrics()
    health_data = compute_health_score(metrics)
    score = health_data["score"]
    grade = health_data["grade"]

    # Score display
    col_badge, col_info = st.columns([1, 3])
    with col_badge:
        health_badge(score, grade)
    with col_info:
        st.info(health_data["summary"])
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Files", f"{metrics['total_files']:,}")
        c2.metric("Total Size", format_size_short(metrics['total_size']))
        c3.metric("Stale (1yr+)", f"{metrics['stale_files']:,}")
        c4.metric("Large (>100MB)", f"{metrics['large_files']:,}")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        # Issues
        st.subheader("Issues")
        if health_data["issues"]:
            for issue in health_data["issues"]:
                icon = severity_icon(issue["severity"])
                st.markdown(
                    f"{icon} **{issue['title']}** — {issue['detail']}"
                )
        else:
            st.success("No issues detected!")

    with col2:
        # Recommendations
        st.subheader("Recommendations")
        for rec in health_data["recommendations"]:
            st.markdown(f"- {rec}")

    st.divider()

    # Detailed metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("New Files (7d)", f"{metrics['new_files_7d']:,}")
    c2.metric("Tagged", f"{metrics['tagged_files']:,}")
    c3.metric("Untagged", f"{metrics['untagged_files']:,}")
    c4.metric(
        "Wasted by Dupes",
        format_size_short(metrics['wasted_by_duplicates']),
    )

    # Top large files
    if metrics["top_large_files"]:
        st.subheader("Largest Files")
        for i, f in enumerate(metrics["top_large_files"][:10], 1):
            st.text(
                f"{i}. {f['name']} — {format_size_short(f['size'])} "
                f"[{f['category']}]"
            )
