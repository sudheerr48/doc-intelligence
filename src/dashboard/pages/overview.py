"""Dashboard overview page — KPI metrics and storage breakdown."""

import streamlit as st
from src.dashboard.components.metrics import format_size_short
from src.dashboard.components.charts import extension_chart, category_chart


@st.cache_data(ttl=60)
def _load_stats(_db):
    stats = _db.get_stats()
    duplicates = _db.get_duplicates()
    total_wasted = sum(d["wasted_size"] for d in duplicates)
    dup_file_count = sum(d["count"] for d in duplicates)
    all_tags = _db.get_all_tags()
    embed_stats = _db.get_embedding_stats()
    return stats, total_wasted, dup_file_count, all_tags, embed_stats


def render(db, config):
    stats, total_wasted, dup_file_count, all_tags, embed_stats = _load_stats(db)

    # Top metrics row
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Files", f"{stats['total_files']:,}")
    c2.metric("Total Size", format_size_short(stats['total_size_bytes']))
    c3.metric("Duplicate Sets", f"{stats['duplicate_sets']:,}",
              f"{dup_file_count:,} files" if dup_file_count else None)
    c4.metric("Reclaimable", format_size_short(total_wasted),
              delta_color="inverse" if total_wasted else "off")
    c5.metric("Unique Tags", f"{len(all_tags):,}")

    st.divider()

    # Charts row — bar chart + donut side by side
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Storage by File Type")
        extension_chart(db)
    with col2:
        st.subheader("Storage by Category")
        category_chart(db)

    # Quick insight cards
    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Embedded Files", f"{embed_stats['embedded_files']:,}",
              f"of {embed_stats['files_with_content']:,} with content")
    c2.metric("File Types", f"{len(stats.get('by_extension', {})):,}")
    c3.metric("Categories", f"{len(stats.get('by_category', {})):,}")
