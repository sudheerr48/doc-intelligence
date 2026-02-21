"""Analytics page — charts, distributions, and insights."""

from pathlib import Path

import streamlit as st

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import plotly.express as px
except ImportError:
    px = None

from src.dashboard.components.metrics import format_size_short
from src.dashboard.components.charts import (
    size_distribution_chart,
    age_distribution_chart,
)


@st.cache_data(ttl=60)
def _load_analytics(_db):
    stats = _db.get_stats()
    metrics = _db.get_health_metrics()
    return stats, metrics


def render(db, config):
    st.subheader("File Analytics")

    stats, metrics = _load_analytics(db)

    # Quick stats
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("File Types", f"{metrics['extension_types']:,}")
    c2.metric("Categories", f"{len(metrics['category_breakdown']):,}")
    c3.metric("Tagged", f"{metrics['tagged_files']:,}")
    c4.metric("New (7d)", f"{metrics.get('new_files_7d', 0):,}")

    st.divider()

    # Size distribution + Age distribution side by side
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("File Size Distribution")
        size_distribution_chart(db)
    with col2:
        st.subheader("File Age Analysis")
        age_distribution_chart(db)

    st.divider()

    # Extension vs category charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top Extensions by Count")
        if pd is not None:
            ext_rows = db.conn.execute("""
                SELECT extension, COUNT(*) as count
                FROM files GROUP BY extension
                ORDER BY count DESC LIMIT 20
            """).fetchall()

            if ext_rows:
                df = pd.DataFrame(ext_rows, columns=["Extension", "Count"])
                df["Extension"] = df["Extension"].fillna("(none)")
                if px is not None:
                    fig = px.bar(
                        df, x="Extension", y="Count",
                        color="Count", color_continuous_scale="Viridis",
                    )
                    fig.update_layout(
                        margin=dict(l=0, r=0, t=32, b=0), height=350,
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        showlegend=False, coloraxis_showscale=False,
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.bar_chart(df.set_index("Extension")["Count"])

    with col2:
        st.subheader("Storage per Category")
        if pd is not None:
            cat_rows = db.conn.execute("""
                SELECT category, SUM(size_bytes) as total
                FROM files GROUP BY category ORDER BY total DESC
            """).fetchall()

            if cat_rows:
                df = pd.DataFrame(cat_rows, columns=["Category", "Total"])
                df["Category"] = df["Category"].fillna("unknown")
                df["Size"] = df["Total"].apply(format_size_short)
                if px is not None:
                    fig = px.bar(
                        df, x="Category", y="Total",
                        hover_data={"Size": True, "Total": False},
                        color="Total", color_continuous_scale="Viridis",
                    )
                    fig.update_layout(
                        margin=dict(l=0, r=0, t=32, b=0), height=350,
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        showlegend=False, coloraxis_showscale=False,
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.bar_chart(df.set_index("Category")["Total"])

    # Duplicate analysis
    st.divider()
    st.subheader("Duplicate Analysis")

    dups = db.get_duplicates()
    if dups:
        c1, c2, c3 = st.columns(3)
        total_wasted = sum(d["wasted_size"] for d in dups)
        c1.metric("Duplicate Sets", f"{len(dups):,}")
        c2.metric("Total Duplicates", f"{sum(d['count'] for d in dups):,}")
        c3.metric("Wasted Space", format_size_short(total_wasted))

        if pd is not None:
            top_dups = []
            for d in dups[:10]:
                size_each = d["total_size"] // d["count"]
                sample = Path(d["paths"][0]).name if d["paths"] else ""
                top_dups.append({
                    "File": sample,
                    "Copies": d["count"],
                    "Size Each": format_size_short(size_each),
                    "Wasted": format_size_short(d["wasted_size"]),
                })
            st.dataframe(
                pd.DataFrame(top_dups),
                column_config={
                    "File": st.column_config.TextColumn("File", width="large"),
                    "Copies": st.column_config.NumberColumn("Copies", width="small"),
                    "Size Each": st.column_config.TextColumn("Size", width="small"),
                    "Wasted": st.column_config.TextColumn("Wasted", width="small"),
                },
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.success("No duplicates found!")
