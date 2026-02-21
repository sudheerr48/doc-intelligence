"""Duplicate files page — find and review duplicate groups."""

from pathlib import Path

import streamlit as st

try:
    import pandas as pd
except ImportError:
    pd = None

from src.dashboard.components.metrics import format_size_short


def render(db, config):
    st.subheader("Duplicate File Groups")

    duplicates = db.get_duplicates()

    if not duplicates:
        st.success("No duplicates found — your files are clean!")
        return

    total_wasted = sum(d["wasted_size"] for d in duplicates)
    dup_files = sum(d["count"] for d in duplicates)

    c1, c2, c3 = st.columns(3)
    c1.metric("Duplicate Sets", f"{len(duplicates):,}")
    c2.metric("Duplicate Files", f"{dup_files:,}")
    c3.metric("Reclaimable Space", format_size_short(total_wasted))

    st.divider()

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        min_size_filter = st.number_input(
            "Min file size (KB)", min_value=0, value=0, step=100,
            key="dup_min_size",
        )
    with col2:
        sort_option = st.selectbox(
            "Sort by", ["Wasted space (most)", "Copies (most)", "File size (largest)"],
            key="dup_sort",
        )

    filtered = duplicates
    if min_size_filter > 0:
        min_bytes = min_size_filter * 1024
        filtered = [
            d for d in duplicates
            if (d["total_size"] // d["count"]) >= min_bytes
        ]

    # Sort
    if sort_option == "Copies (most)":
        filtered = sorted(filtered, key=lambda d: d["count"], reverse=True)
    elif sort_option == "File size (largest)":
        filtered = sorted(filtered, key=lambda d: d["total_size"] // d["count"], reverse=True)

    st.caption(f"Showing **{len(filtered)}** duplicate sets")

    # Table view for quick scan + expanders for detail
    if filtered and pd is not None:
        top_dups = []
        for d in filtered[:50]:
            size_each = d["total_size"] // d["count"]
            sample = Path(d["paths"][0]).name if d["paths"] else ""
            top_dups.append({
                "Sample File": sample,
                "Copies": d["count"],
                "Size Each": format_size_short(size_each),
                "Wasted": format_size_short(d["wasted_size"]),
            })

        st.dataframe(
            pd.DataFrame(top_dups),
            column_config={
                "Sample File": st.column_config.TextColumn("File", width="large"),
                "Copies": st.column_config.NumberColumn("Copies", width="small"),
                "Size Each": st.column_config.TextColumn("Size", width="small"),
                "Wasted": st.column_config.TextColumn("Wasted", width="small"),
            },
            use_container_width=True,
            hide_index=True,
        )

    # Expandable detail groups
    st.divider()
    for i, dup in enumerate(filtered[:30], 1):
        size_each = dup["total_size"] // dup["count"]
        with st.expander(
            f"**Set {i}** — {dup['count']} copies, "
            f"{format_size_short(size_each)} each "
            f"(wasted: {format_size_short(dup['wasted_size'])})"
        ):
            for p in dup["paths"]:
                st.code(p, language=None)
