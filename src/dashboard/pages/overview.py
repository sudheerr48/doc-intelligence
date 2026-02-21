"""Dashboard overview page — KPI metrics and storage breakdown."""

import streamlit as st
from src.dashboard.components.metrics import format_size_short, metric_row
from src.dashboard.components.charts import extension_chart, category_chart


def render(db, config):
    stats = db.get_stats()
    duplicates = db.get_duplicates()
    total_wasted = sum(d["wasted_size"] for d in duplicates)
    dup_file_count = sum(d["count"] for d in duplicates)
    all_tags = db.get_all_tags()

    # Top metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Files", f"{stats['total_files']:,}")
    c2.metric("Total Size", format_size_short(stats['total_size_bytes']))
    c3.metric("Duplicate Sets", f"{stats['duplicate_sets']:,}",
              f"{dup_file_count:,} files")
    c4.metric("Wasted Space", format_size_short(total_wasted))
    c5.metric("Unique Tags", f"{len(all_tags):,}")

    st.divider()

    # Charts row
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Storage by File Type")
        extension_chart(db)
    with col2:
        st.subheader("Storage by Category")
        category_chart(db)
