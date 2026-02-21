"""Reusable Plotly chart components for the dashboard."""

import streamlit as st

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import plotly.express as px
    import plotly.graph_objects as go
except ImportError:
    px = None
    go = None

from src.dashboard.components.metrics import format_size_short

# Shared Plotly layout defaults
_LAYOUT = dict(
    margin=dict(l=0, r=0, t=32, b=0),
    height=350,
    font=dict(size=12),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    colorway=["#6366f1", "#8b5cf6", "#a78bfa", "#c4b5fd",
              "#818cf8", "#4f46e5", "#7c3aed", "#5b21b6"],
)


def extension_chart(db):
    """Interactive bar chart of storage by file extension."""
    rows = db.conn.execute("""
        SELECT extension, SUM(size_bytes) as total_size, COUNT(*) as count
        FROM files GROUP BY extension
        ORDER BY total_size DESC LIMIT 15
    """).fetchall()

    if not rows or pd is None:
        st.info("No data available.")
        return

    df = pd.DataFrame(rows, columns=["Extension", "Size (bytes)", "Files"])
    df["Extension"] = df["Extension"].fillna("(none)")
    df["Size"] = df["Size (bytes)"].apply(format_size_short)

    if px is not None:
        fig = px.bar(
            df, x="Extension", y="Size (bytes)",
            hover_data={"Size": True, "Files": True, "Size (bytes)": False},
            color="Size (bytes)",
            color_continuous_scale="Viridis",
        )
        fig.update_layout(**_LAYOUT, showlegend=False, coloraxis_showscale=False)
        fig.update_traces(hovertemplate="%{x}<br>%{customdata[0]}<br>%{customdata[1]} files")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.bar_chart(df.set_index("Extension")["Size (bytes)"])


def category_chart(db):
    """Interactive donut chart of storage by category."""
    rows = db.conn.execute("""
        SELECT category, COUNT(*) as count, SUM(size_bytes) as total_size
        FROM files GROUP BY category ORDER BY total_size DESC
    """).fetchall()

    if not rows or pd is None:
        st.info("No data available.")
        return

    df = pd.DataFrame(rows, columns=["Category", "Files", "Size (bytes)"])
    df["Category"] = df["Category"].fillna("unknown")
    df["Size"] = df["Size (bytes)"].apply(format_size_short)

    if px is not None:
        fig = px.pie(
            df, names="Category", values="Size (bytes)",
            hover_data={"Size": True, "Files": True, "Size (bytes)": False},
            hole=0.4,
        )
        fig.update_layout(**_LAYOUT, height=350)
        fig.update_traces(textposition="inside", textinfo="label+percent")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.bar_chart(df.set_index("Category")["Size (bytes)"])


def tag_chart(all_tags: dict[str, int], top_n: int = 20):
    """Horizontal bar chart of top tags."""
    if not all_tags or pd is None:
        st.info("No tags available.")
        return

    items = list(all_tags.items())[:top_n]
    df = pd.DataFrame(items, columns=["Tag", "Files"])
    df = df.sort_values("Files", ascending=True)

    if px is not None:
        fig = px.bar(
            df, x="Files", y="Tag", orientation="h",
            color="Files", color_continuous_scale="Viridis",
        )
        fig.update_layout(
            **_LAYOUT,
            height=max(300, top_n * 28),
            showlegend=False,
            coloraxis_showscale=False,
            yaxis=dict(tickfont=dict(size=11)),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.bar_chart(df.set_index("Tag")["Files"])


def size_distribution_chart(db):
    """Histogram of file size distribution with log-scale buckets."""
    if pd is None:
        return

    rows = db.conn.execute("""
        SELECT
            CASE
                WHEN size_bytes < 1024 THEN '< 1 KB'
                WHEN size_bytes < 1048576 THEN '1 KB - 1 MB'
                WHEN size_bytes < 10485760 THEN '1 - 10 MB'
                WHEN size_bytes < 104857600 THEN '10 - 100 MB'
                WHEN size_bytes < 1073741824 THEN '100 MB - 1 GB'
                ELSE '> 1 GB'
            END as size_range,
            COUNT(*) as count
        FROM files GROUP BY size_range ORDER BY MIN(size_bytes)
    """).fetchall()

    if not rows:
        return

    df = pd.DataFrame(rows, columns=["Size Range", "Files"])

    if px is not None:
        fig = px.bar(
            df, x="Size Range", y="Files",
            color="Files", color_continuous_scale="Viridis",
            text="Files",
        )
        fig.update_layout(**_LAYOUT, showlegend=False, coloraxis_showscale=False)
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.bar_chart(df.set_index("Size Range")["Files"])


def age_distribution_chart(db):
    """File age analysis as a horizontal bar chart."""
    if pd is None:
        return None

    rows = db.conn.execute("""
        SELECT
            CASE
                WHEN modified_at > CURRENT_TIMESTAMP - INTERVAL '7 days' THEN 'Last 7 days'
                WHEN modified_at > CURRENT_TIMESTAMP - INTERVAL '30 days' THEN 'Last 30 days'
                WHEN modified_at > CURRENT_TIMESTAMP - INTERVAL '90 days' THEN 'Last 90 days'
                WHEN modified_at > CURRENT_TIMESTAMP - INTERVAL '365 days' THEN 'Last year'
                ELSE 'Over 1 year'
            END as age_group,
            COUNT(*) as count,
            SUM(size_bytes) as total_size
        FROM files GROUP BY age_group
    """).fetchall()

    if not rows:
        return None

    df = pd.DataFrame(rows, columns=["Age", "Files", "Size (bytes)"])
    df["Size"] = df["Size (bytes)"].apply(format_size_short)

    if px is not None:
        fig = px.bar(
            df, x="Files", y="Age", orientation="h",
            hover_data={"Size": True, "Size (bytes)": False},
            color="Files", color_continuous_scale="RdYlGn_r",
            text="Files",
        )
        fig.update_layout(**_LAYOUT, height=280, showlegend=False, coloraxis_showscale=False)
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.bar_chart(df.set_index("Age")["Files"])

    return df
