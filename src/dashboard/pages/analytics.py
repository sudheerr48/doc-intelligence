"""Analytics page — charts, distributions, and insights."""

import streamlit as st

try:
    import pandas as pd
except ImportError:
    pd = None

from src.dashboard.components.metrics import format_size_short
from src.dashboard.components.charts import (
    extension_chart,
    category_chart,
    size_distribution_chart,
)


def render(db, config):
    st.subheader("File Analytics")

    stats = db.get_stats()
    metrics = db.get_health_metrics()

    # Quick stats
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("File Types", f"{metrics['extension_types']:,}")
    c2.metric(
        "Categories",
        f"{len(metrics['category_breakdown']):,}",
    )
    c3.metric("Tagged", f"{metrics['tagged_files']:,}")
    c4.metric("With Content", f"{metrics.get('new_files_7d', 0):,} new (7d)")

    st.divider()

    # Size distribution
    st.subheader("File Size Distribution")
    size_distribution_chart(db)

    st.divider()

    # Extension vs category heatmap
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top Extensions by Count")
        if pd is not None:
            ext_rows = db.conn.execute("""
                SELECT extension, COUNT(*) as count
                FROM files
                GROUP BY extension
                ORDER BY count DESC
                LIMIT 20
            """).fetchall()

            if ext_rows:
                df = pd.DataFrame(ext_rows, columns=["Extension", "Count"])
                df["Extension"] = df["Extension"].fillna("(none)")
                st.bar_chart(df.set_index("Extension")["Count"])

    with col2:
        st.subheader("Storage per Category")
        if pd is not None:
            cat_rows = db.conn.execute("""
                SELECT category, SUM(size_bytes) as total
                FROM files
                GROUP BY category
                ORDER BY total DESC
            """).fetchall()

            if cat_rows:
                df = pd.DataFrame(cat_rows, columns=["Category", "Total"])
                df["Category"] = df["Category"].fillna("unknown")
                df["Size"] = df["Total"].apply(format_size_short)
                st.bar_chart(df.set_index("Category")["Total"])

    st.divider()

    # Stale file analysis
    st.subheader("File Age Analysis")
    if pd is not None:
        age_rows = db.conn.execute("""
            SELECT
                CASE
                    WHEN modified_at > CURRENT_TIMESTAMP - INTERVAL '7 days'
                        THEN 'Last 7 days'
                    WHEN modified_at > CURRENT_TIMESTAMP - INTERVAL '30 days'
                        THEN 'Last 30 days'
                    WHEN modified_at > CURRENT_TIMESTAMP - INTERVAL '90 days'
                        THEN 'Last 90 days'
                    WHEN modified_at > CURRENT_TIMESTAMP - INTERVAL '365 days'
                        THEN 'Last year'
                    ELSE 'Over 1 year'
                END as age_group,
                COUNT(*) as count,
                SUM(size_bytes) as total_size
            FROM files
            GROUP BY age_group
        """).fetchall()

        if age_rows:
            df = pd.DataFrame(
                age_rows, columns=["Age Group", "Files", "Size (bytes)"],
            )
            df["Size"] = df["Size (bytes)"].apply(format_size_short)
            st.bar_chart(df.set_index("Age Group")["Files"])
            st.dataframe(
                df[["Age Group", "Files", "Size"]],
                use_container_width=True,
                hide_index=True,
            )

    # Duplicate stats
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
                from pathlib import Path
                sample = Path(d["paths"][0]).name if d["paths"] else ""
                top_dups.append({
                    "File": sample,
                    "Copies": d["count"],
                    "Size Each": format_size_short(size_each),
                    "Wasted": format_size_short(d["wasted_size"]),
                })
            st.dataframe(
                pd.DataFrame(top_dups),
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.success("No duplicates found!")
