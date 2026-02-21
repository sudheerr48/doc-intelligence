"""File browser page — search, filter, and browse indexed files."""

import streamlit as st

try:
    import pandas as pd
except ImportError:
    pd = None

from src.dashboard.components.metrics import format_size_short


def render(db, config):
    st.subheader("File Browser")

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        query = st.text_input(
            "Search", placeholder="filename, path, or content...",
            key="file_search",
        )
    with col2:
        extensions = db.conn.execute(
            "SELECT DISTINCT extension FROM files ORDER BY extension"
        ).fetchall()
        ext_list = ["All"] + [r[0] or "(none)" for r in extensions]
        ext_filter = st.selectbox("Extension", ext_list, key="ext_filter")
    with col3:
        categories = db.conn.execute(
            "SELECT DISTINCT category FROM files ORDER BY category"
        ).fetchall()
        cat_list = ["All"] + [r[0] or "unknown" for r in categories]
        cat_filter = st.selectbox("Category", cat_list, key="cat_filter")

    # Size filter
    size_col1, size_col2 = st.columns(2)
    with size_col1:
        min_size_mb = st.number_input(
            "Min size (MB)", min_value=0.0, value=0.0,
            step=1.0, key="min_size",
        )
    with size_col2:
        sort_by = st.selectbox(
            "Sort by",
            ["Size (largest)", "Size (smallest)", "Name", "Modified (recent)"],
            key="sort_by",
        )

    # Build query
    conditions = []
    params = []

    if query:
        conditions.append(
            "(LOWER(name) LIKE LOWER(?) OR LOWER(path) LIKE LOWER(?))"
        )
        like_param = f"%{query}%"
        params.extend([like_param, like_param])

    if ext_filter != "All":
        ext_val = None if ext_filter == "(none)" else ext_filter
        if ext_val is None:
            conditions.append("extension IS NULL")
        else:
            conditions.append("extension = ?")
            params.append(ext_val)

    if cat_filter != "All":
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
        ORDER BY {order}
        LIMIT 500
    """

    rows = db.conn.execute(sql, params).fetchall()

    if not rows or pd is None:
        st.info("No files match your filters.")
        return

    df = pd.DataFrame(
        rows,
        columns=["Name", "Extension", "Size (bytes)", "Category", "Tags", "Path"],
    )
    df["Size"] = df["Size (bytes)"].apply(format_size_short)

    st.write(f"Showing **{len(df)}** files")

    st.dataframe(
        df[["Name", "Size", "Extension", "Category", "Path"]],
        use_container_width=True,
        hide_index=True,
    )
