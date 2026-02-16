#!/usr/bin/env python3
"""
Streamlit Web Dashboard
Visual dashboard for Doc Intelligence - storage breakdown, duplicates, file categories.

Launch with:
    doc-intelligence dashboard
    # or
    streamlit run scripts/dashboard.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import streamlit as st
except ImportError:
    print("Streamlit is required for the dashboard.")
    print("Install it with: pip install 'doc-intelligence[dashboard]'")
    sys.exit(1)

from src.storage import FileDatabase
from src.utils import load_config, format_size


def get_db(config: dict) -> FileDatabase:
    db_path = Path(config["database"]["path"]).expanduser()
    return FileDatabase(str(db_path))


def format_size_short(size_bytes: int) -> str:
    """Format size for dashboard metrics."""
    if size_bytes is None:
        return "0 B"
    return format_size(size_bytes)


def main_dashboard():
    st.set_page_config(
        page_title="Doc Intelligence",
        page_icon="📁",
        layout="wide",
    )

    st.title("📁 Doc Intelligence Dashboard")
    st.caption("Your file storage at a glance")

    # Load config
    config = load_config()
    db_path = Path(config["database"]["path"]).expanduser()

    if not db_path.exists():
        st.error("Database not found. Run `doc-intelligence scan` first.")
        st.stop()

    db = get_db(config)
    stats = db.get_stats()

    # --- Top metrics ---
    duplicates = db.get_duplicates()
    total_wasted = sum(d["wasted_size"] for d in duplicates)
    dup_file_count = sum(d["count"] for d in duplicates)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Files", f"{stats['total_files']:,}")
    col2.metric("Total Size", format_size_short(stats['total_size_bytes']))
    col3.metric("Duplicate Sets", f"{stats['duplicate_sets']:,}", f"{dup_file_count:,} files")
    col4.metric("Wasted Space", format_size_short(total_wasted))

    st.divider()

    # --- Charts row ---
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Storage by File Type")
        ext_rows = db.conn.execute("""
            SELECT extension, SUM(size_bytes) as total_size
            FROM files
            GROUP BY extension
            ORDER BY total_size DESC
            LIMIT 12
        """).fetchall()

        if ext_rows:
            import pandas as pd
            ext_df = pd.DataFrame(ext_rows, columns=["Extension", "Size (bytes)"])
            ext_df["Extension"] = ext_df["Extension"].fillna("(no ext)")
            ext_df["Size"] = ext_df["Size (bytes)"].apply(format_size_short)
            st.bar_chart(ext_df.set_index("Extension")["Size (bytes)"])
            st.dataframe(
                ext_df[["Extension", "Size"]],
                use_container_width=True,
                hide_index=True,
            )

    with chart_col2:
        st.subheader("Storage by Category")
        cat_rows = db.conn.execute("""
            SELECT category, COUNT(*) as count, SUM(size_bytes) as total_size
            FROM files
            GROUP BY category
            ORDER BY total_size DESC
        """).fetchall()

        if cat_rows:
            import pandas as pd
            cat_df = pd.DataFrame(cat_rows, columns=["Category", "Files", "Size (bytes)"])
            cat_df["Category"] = cat_df["Category"].fillna("unknown")
            cat_df["Size"] = cat_df["Size (bytes)"].apply(format_size_short)
            st.bar_chart(cat_df.set_index("Category")["Size (bytes)"])
            st.dataframe(
                cat_df[["Category", "Files", "Size"]],
                use_container_width=True,
                hide_index=True,
            )

    st.divider()

    # --- Tabs for detailed views ---
    tab_big, tab_dups, tab_search = st.tabs(["🗄️ Largest Files", "📋 Duplicates", "🔍 Search"])

    with tab_big:
        st.subheader("Largest Files")
        top_n = st.slider("Number of files", 10, 100, 20, key="big_slider")

        big_rows = db.conn.execute("""
            SELECT name, size_bytes, extension, category, path
            FROM files
            ORDER BY size_bytes DESC
            LIMIT ?
        """, [top_n]).fetchall()

        if big_rows:
            import pandas as pd
            big_df = pd.DataFrame(big_rows, columns=["Name", "Size (bytes)", "Type", "Category", "Path"])
            big_df["Size"] = big_df["Size (bytes)"].apply(format_size_short)

            total_big = sum(r[1] for r in big_rows)
            if stats['total_size_bytes'] > 0:
                pct = (total_big / stats['total_size_bytes']) * 100
                st.info(f"These {len(big_rows)} files = **{format_size_short(total_big)}** ({pct:.1f}% of total)")

            st.dataframe(
                big_df[["Name", "Size", "Type", "Category", "Path"]],
                use_container_width=True,
                hide_index=True,
            )

    with tab_dups:
        st.subheader("Duplicate File Groups")

        if duplicates:
            min_size_filter = st.number_input(
                "Min file size (KB)", min_value=0, value=0, step=100, key="dup_min_size"
            )

            filtered = duplicates
            if min_size_filter > 0:
                min_bytes = min_size_filter * 1024
                filtered = [d for d in duplicates if (d["total_size"] // d["count"]) >= min_bytes]

            st.write(f"Showing **{len(filtered)}** duplicate sets")

            for i, dup in enumerate(filtered[:50], 1):
                size_each = dup["total_size"] // dup["count"]
                with st.expander(
                    f"Set #{i}: {dup['count']} copies, {format_size_short(size_each)} each — "
                    f"wasted: {format_size_short(dup['wasted_size'])}"
                ):
                    for p in dup["paths"]:
                        st.text(p)
        else:
            st.success("No duplicates found!")

    with tab_search:
        st.subheader("Search Files")
        query = st.text_input("Search query (filename, path, or content)", key="search_input")

        if query:
            results = db.search(query, limit=100)
            if results:
                import pandas as pd
                search_df = pd.DataFrame(results)
                search_df["size"] = search_df["size_bytes"].apply(format_size_short)
                st.write(f"Found **{len(results)}** results")
                st.dataframe(
                    search_df[["name", "size", "category", "path"]],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.warning("No results found.")

    db.close()


if __name__ == "__main__":
    main_dashboard()
