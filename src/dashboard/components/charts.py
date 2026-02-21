"""Reusable chart components for the dashboard."""

import streamlit as st

try:
    import pandas as pd
except ImportError:
    pd = None

from src.dashboard.components.metrics import format_size_short


def extension_chart(db):
    """Bar chart of storage by file extension."""
    rows = db.conn.execute("""
        SELECT extension, SUM(size_bytes) as total_size, COUNT(*) as count
        FROM files
        GROUP BY extension
        ORDER BY total_size DESC
        LIMIT 15
    """).fetchall()

    if not rows or pd is None:
        st.info("No data available.")
        return

    df = pd.DataFrame(rows, columns=["Extension", "Size (bytes)", "Files"])
    df["Extension"] = df["Extension"].fillna("(none)")
    df["Size"] = df["Size (bytes)"].apply(format_size_short)
    st.bar_chart(df.set_index("Extension")["Size (bytes)"])
    st.dataframe(
        df[["Extension", "Files", "Size"]],
        use_container_width=True, hide_index=True,
    )


def category_chart(db):
    """Bar chart of storage by category."""
    rows = db.conn.execute("""
        SELECT category, COUNT(*) as count, SUM(size_bytes) as total_size
        FROM files
        GROUP BY category
        ORDER BY total_size DESC
    """).fetchall()

    if not rows or pd is None:
        st.info("No data available.")
        return

    df = pd.DataFrame(rows, columns=["Category", "Files", "Size (bytes)"])
    df["Category"] = df["Category"].fillna("unknown")
    df["Size"] = df["Size (bytes)"].apply(format_size_short)
    st.bar_chart(df.set_index("Category")["Size (bytes)"])
    st.dataframe(
        df[["Category", "Files", "Size"]],
        use_container_width=True, hide_index=True,
    )


def tag_chart(all_tags: dict[str, int], top_n: int = 20):
    """Bar chart of top tags."""
    if not all_tags or pd is None:
        st.info("No tags available.")
        return

    df = pd.DataFrame(
        [{"Tag": t, "Files": c} for t, c in list(all_tags.items())[:top_n]]
    )
    st.bar_chart(df.set_index("Tag")["Files"])


def size_distribution_chart(db):
    """Histogram of file size distribution."""
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
        FROM files
        GROUP BY size_range
        ORDER BY MIN(size_bytes)
    """).fetchall()

    if rows:
        df = pd.DataFrame(rows, columns=["Size Range", "Files"])
        st.bar_chart(df.set_index("Size Range")["Files"])
