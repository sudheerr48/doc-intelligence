"""Health report page — scoring, issues, and recommendations."""

import streamlit as st
from src.analysis.health import compute_health_score
from src.dashboard.components.metrics import (
    format_size_short,
    health_badge,
    severity_icon,
)


@st.cache_data(ttl=60)
def _load_health(_db):
    metrics = _db.get_health_metrics()
    health_data = compute_health_score(metrics)
    return metrics, health_data


def render(db, config):
    st.subheader("File System Health Report")

    metrics, health_data = _load_health(db)

    # Score display — badge + summary side by side
    col_badge, col_info = st.columns([1, 3])
    with col_badge:
        health_badge(health_data["score"], health_data["grade"])
    with col_info:
        st.info(health_data["summary"])
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Files", f"{metrics['total_files']:,}")
        c2.metric("Total Size", format_size_short(metrics['total_size']))
        c3.metric("Stale (1yr+)", f"{metrics['stale_files']:,}")
        c4.metric("Large (>100MB)", f"{metrics['large_files']:,}")

    st.divider()

    # Issues + Recommendations side by side
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Issues")
        if health_data["issues"]:
            for issue in health_data["issues"]:
                icon = severity_icon(issue["severity"])
                with st.container():
                    st.markdown(
                        f"{icon} **{issue['title']}**  \n"
                        f"<span style='opacity:0.7;'>{issue['detail']}</span>",
                        unsafe_allow_html=True,
                    )
        else:
            st.success("No issues detected!")

    with col2:
        st.subheader("Recommendations")
        for i, rec in enumerate(health_data["recommendations"], 1):
            st.markdown(f"**{i}.** {rec}")

    st.divider()

    # Secondary metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("New Files (7d)", f"{metrics['new_files_7d']:,}")
    c2.metric("Tagged", f"{metrics['tagged_files']:,}")
    c3.metric("Untagged", f"{metrics['untagged_files']:,}")
    c4.metric("Wasted by Dupes", format_size_short(metrics['wasted_by_duplicates']))

    # Top large files table
    if metrics["top_large_files"]:
        st.divider()
        st.subheader("Largest Files")
        try:
            import pandas as pd
            large_df = pd.DataFrame(metrics["top_large_files"][:10])
            large_df["size_fmt"] = large_df["size"].apply(format_size_short)
            st.dataframe(
                large_df[["name", "size_fmt", "ext", "category"]],
                column_config={
                    "name": st.column_config.TextColumn("Name", width="large"),
                    "size_fmt": st.column_config.TextColumn("Size", width="small"),
                    "ext": st.column_config.TextColumn("Type", width="small"),
                    "category": st.column_config.TextColumn("Category", width="small"),
                },
                use_container_width=True,
                hide_index=True,
            )
        except ImportError:
            for i, f in enumerate(metrics["top_large_files"][:10], 1):
                st.text(
                    f"{i}. {f['name']} — {format_size_short(f['size'])} "
                    f"[{f['category']}]"
                )
