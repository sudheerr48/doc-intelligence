"""File browser page — search, filter, and browse indexed files."""

import streamlit as st

try:
    import pandas as pd
except ImportError:
    pd = None

from src.dashboard.components.metrics import format_size_short


def render(db, config):
    st.subheader("File Browser")

    # Filters in a single compact row
    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
    with col1:
        query = st.text_input(
            "Search", placeholder="filename, path, or content...",
            key="file_search", label_visibility="collapsed",
        )
    with col2:
        extensions = db.conn.execute(
            "SELECT DISTINCT extension FROM files ORDER BY extension"
        ).fetchall()
        ext_list = ["All types"] + [r[0] or "(none)" for r in extensions]
        ext_filter = st.selectbox("Extension", ext_list, key="ext_filter",
                                  label_visibility="collapsed")
    with col3:
        categories = db.conn.execute(
            "SELECT DISTINCT category FROM files ORDER BY category"
        ).fetchall()
        cat_list = ["All categories"] + [r[0] or "unknown" for r in categories]
        cat_filter = st.selectbox("Category", cat_list, key="cat_filter",
                                  label_visibility="collapsed")
    with col4:
        sort_by = st.selectbox(
            "Sort", ["Size (largest)", "Size (smallest)", "Name", "Modified (recent)"],
            key="sort_by", label_visibility="collapsed",
        )

    # Size filter row
    min_size_mb = st.slider(
        "Minimum file size (MB)", 0.0, 500.0, 0.0, 0.5,
        key="min_size", label_visibility="collapsed",
    ) if st.checkbox("Filter by min size", key="size_toggle") else 0.0

    # Build query
    conditions, params = [], []

    if query:
        conditions.append(
            "(LOWER(name) LIKE LOWER(?) OR LOWER(path) LIKE LOWER(?))"
        )
        like_param = f"%{query}%"
        params.extend([like_param, like_param])

    if ext_filter != "All types":
        ext_val = None if ext_filter == "(none)" else ext_filter
        if ext_val is None:
            conditions.append("extension IS NULL")
        else:
            conditions.append("extension = ?")
            params.append(ext_val)

    if cat_filter != "All categories":
        conditions.append("category = ?")
        params.append(cat_filter)

    if min_size_mb > 0:
        conditions.append("size_bytes >= ?")
        params.append(int(min_size_mb * 1048576))

    where = " AND ".join(conditions) if conditions else "1=1"
    order_map = {
        "Size (largest)": "size_bytes DESC",
        "Size (smallest)": "size_bytes ASC",
        "Name": "name ASC",
        "Modified (recent)": "modified_at DESC",
    }
    order = order_map.get(sort_by, "size_bytes DESC")

    sql = f"""
        SELECT name, extension, size_bytes, category, tags, path
        FROM files WHERE {where}
        ORDER BY {order} LIMIT 500
    """
    rows = db.conn.execute(sql, params).fetchall()

    if not rows or pd is None:
        st.info("No files match your filters.")
        return

    df = pd.DataFrame(
        rows, columns=["Name", "Extension", "Size (bytes)", "Category", "Tags", "Path"],
    )
    df["Size"] = df["Size (bytes)"].apply(format_size_short)

    st.caption(f"Showing **{len(df)}** files")

    st.dataframe(
        df[["Name", "Size", "Extension", "Category", "Path"]],
        column_config={
            "Name": st.column_config.TextColumn("Name", width="medium"),
            "Size": st.column_config.TextColumn("Size", width="small"),
            "Extension": st.column_config.TextColumn("Type", width="small"),
            "Category": st.column_config.TextColumn("Category", width="small"),
            "Path": st.column_config.TextColumn("Path", width="large"),
        },
        use_container_width=True,
        hide_index=True,
        height=600,
    )
