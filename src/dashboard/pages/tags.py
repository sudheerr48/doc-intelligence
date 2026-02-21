"""Tag browser page — view and explore AI-generated file tags."""

import streamlit as st

try:
    import pandas as pd
except ImportError:
    pd = None

from src.dashboard.components.metrics import format_size_short
from src.dashboard.components.charts import tag_chart


def render(db, config):
    st.subheader("AI Tags")

    all_tags = db.get_all_tags()

    if not all_tags:
        st.warning(
            "No tags found. "
            "Run `doc-intelligence tag` to AI-classify your files."
        )
        return

    # Metrics row
    tagged = db.conn.execute(
        "SELECT COUNT(*) FROM files WHERE tags IS NOT NULL AND tags != '[]'"
    ).fetchone()[0]
    total = db.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    untagged = total - tagged
    pct = (tagged / total * 100) if total else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Unique Tags", f"{len(all_tags):,}")
    c2.metric("Tagged Files", f"{tagged:,}")
    c3.metric("Untagged", f"{untagged:,}")
    c4.metric("Coverage", f"{pct:.0f}%")

    st.divider()

    # Tag chart
    tag_chart(all_tags, top_n=25)

    st.divider()

    # Tag browser with multi-select
    selected_tag = st.selectbox(
        "Browse files by tag",
        options=["(select a tag)"] + list(all_tags.keys()),
        key="tag_selector",
    )

    if selected_tag != "(select a tag)":
        tagged_files = db.get_files_by_tag(selected_tag, limit=100)
        if tagged_files and pd is not None:
            df = pd.DataFrame(tagged_files)
            df["size"] = df["size_bytes"].apply(format_size_short)
            df["tags_str"] = df["tags"].apply(
                lambda t: ", ".join(t[:4]) if isinstance(t, list) else ""
            )
            st.caption(f"**{len(tagged_files)}** files tagged **{selected_tag}**")
            st.dataframe(
                df[["name", "size", "category", "tags_str", "path"]],
                column_config={
                    "name": st.column_config.TextColumn("Name", width="medium"),
                    "size": st.column_config.TextColumn("Size", width="small"),
                    "category": st.column_config.TextColumn("Category", width="small"),
                    "tags_str": st.column_config.TextColumn("Tags", width="medium"),
                    "path": st.column_config.TextColumn("Path", width="large"),
                },
                use_container_width=True,
                hide_index=True,
            )
