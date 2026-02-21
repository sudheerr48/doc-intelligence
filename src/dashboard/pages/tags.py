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

    c1, c2 = st.columns(2)
    c1.metric("Unique Tags", f"{len(all_tags):,}")
    tagged = db.conn.execute(
        "SELECT COUNT(*) FROM files WHERE tags IS NOT NULL AND tags != '[]'"
    ).fetchone()[0]
    total = db.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    c2.metric("Tagged Files", f"{tagged:,}", f"of {total:,} total")

    st.divider()

    # Tag chart
    st.subheader("Top Tags")
    tag_chart(all_tags, top_n=25)

    st.divider()

    # Tag browser
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
            st.write(
                f"**{len(tagged_files)}** files tagged '{selected_tag}'"
            )
            st.dataframe(
                df[["name", "size", "category", "tags_str", "path"]],
                use_container_width=True,
                hide_index=True,
            )
