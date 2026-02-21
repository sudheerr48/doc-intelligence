"""Duplicate files page — find and review duplicate groups."""

import streamlit as st
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

    min_size_filter = st.number_input(
        "Min file size (KB)", min_value=0, value=0, step=100,
        key="dup_min_size",
    )

    filtered = duplicates
    if min_size_filter > 0:
        min_bytes = min_size_filter * 1024
        filtered = [
            d for d in duplicates
            if (d["total_size"] // d["count"]) >= min_bytes
        ]

    st.write(f"Showing **{len(filtered)}** duplicate sets")

    for i, dup in enumerate(filtered[:50], 1):
        size_each = dup["total_size"] // dup["count"]
        with st.expander(
            f"Set #{i}: {dup['count']} copies, "
            f"{format_size_short(size_each)} each — "
            f"wasted: {format_size_short(dup['wasted_size'])}"
        ):
            for p in dup["paths"]:
                st.text(p)
