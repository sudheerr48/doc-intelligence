#!/usr/bin/env python3
"""
Streamlit Web Dashboard
Visual dashboard for Doc Intelligence — storage breakdown, duplicates,
tags, health, and AI-powered natural language search.

Launch with:
    doc-intelligence dashboard
    # or
    streamlit run scripts/dashboard.py
"""

import sys
import json
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
    st.caption("AI-powered file intelligence — always-on, local, private")

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
    all_tags = db.get_all_tags()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Files", f"{stats['total_files']:,}")
    col2.metric("Total Size", format_size_short(stats['total_size_bytes']))
    col3.metric("Duplicate Sets", f"{stats['duplicate_sets']:,}", f"{dup_file_count:,} files")
    col4.metric("Wasted Space", format_size_short(total_wasted))
    col5.metric("Unique Tags", f"{len(all_tags):,}")

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
    tab_health, tab_big, tab_dups, tab_tags, tab_search, tab_ai = st.tabs([
        "🩺 Health", "🗄️ Largest Files", "📋 Duplicates",
        "🏷️ Tags", "🔍 Search", "🤖 AI Search",
    ])

    # --- Health Tab ---
    with tab_health:
        st.subheader("File System Health Report")

        metrics = db.get_health_metrics()

        from src.health import compute_health_score
        health_data = compute_health_score(metrics)

        # Score display
        score = health_data["score"]
        grade = health_data["grade"]

        score_col1, score_col2, score_col3 = st.columns(3)
        score_col1.metric("Health Score", f"{score}/100")
        score_col2.metric("Grade", grade)
        score_col3.metric("Stale Files (1y+)", f"{metrics['stale_files']:,}")

        st.info(health_data["summary"])

        # Quick stats row
        h_col1, h_col2, h_col3, h_col4 = st.columns(4)
        h_col1.metric("Large Files (>100MB)", f"{metrics['large_files']:,}")
        h_col2.metric("New Files (7d)", f"{metrics['new_files_7d']:,}")
        h_col3.metric("Tagged", f"{metrics['tagged_files']:,}")
        h_col4.metric("Untagged", f"{metrics['untagged_files']:,}")

        # Issues
        if health_data["issues"]:
            st.subheader("Issues")
            for issue in health_data["issues"]:
                severity_color = {
                    "high": "🔴", "medium": "🟡", "low": "🟢"
                }.get(issue["severity"], "⚪")
                st.markdown(f"{severity_color} **{issue['title']}** — {issue['detail']}")

        # Recommendations
        if health_data["recommendations"]:
            st.subheader("Recommendations")
            for rec in health_data["recommendations"]:
                st.markdown(f"- {rec}")

    # --- Largest Files Tab ---
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

    # --- Duplicates Tab ---
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

    # --- Tags Tab ---
    with tab_tags:
        st.subheader("AI Tags")

        if all_tags:
            import pandas as pd

            # Tag cloud / summary
            st.write(f"**{len(all_tags)}** unique tags across your files")

            tag_df = pd.DataFrame(
                [{"Tag": t, "Files": c} for t, c in all_tags.items()]
            )
            st.bar_chart(tag_df.head(20).set_index("Tag")["Files"])

            # Tag browser
            selected_tag = st.selectbox(
                "Browse files by tag",
                options=["(select a tag)"] + list(all_tags.keys()),
                key="tag_selector",
            )

            if selected_tag != "(select a tag)":
                tagged_files = db.get_files_by_tag(selected_tag, limit=100)
                if tagged_files:
                    files_df = pd.DataFrame(tagged_files)
                    files_df["size"] = files_df["size_bytes"].apply(format_size_short)
                    files_df["tags_str"] = files_df["tags"].apply(
                        lambda t: ", ".join(t[:4]) if isinstance(t, list) else ""
                    )
                    st.write(f"**{len(tagged_files)}** files tagged '{selected_tag}'")
                    st.dataframe(
                        files_df[["name", "size", "category", "tags_str", "path"]],
                        use_container_width=True,
                        hide_index=True,
                    )
        else:
            st.warning(
                "No tags found. Run `doc-intelligence tag` to AI-classify your files."
            )

    # --- Search Tab ---
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

    # --- AI Search Tab ---
    with tab_ai:
        st.subheader("Ask Your Files (AI-Powered)")
        st.caption("Ask questions in plain English — powered by Claude")

        # Check AI availability
        from src.ai import is_ai_available

        if not is_ai_available():
            st.warning(
                "AI features require the `anthropic` package and `ANTHROPIC_API_KEY` env var.\n\n"
                "```bash\n"
                "pip install 'doc-intelligence[ai]'\n"
                "export ANTHROPIC_API_KEY=your-key-here\n"
                "```"
            )
        else:
            nl_query = st.text_input(
                "Ask a question",
                placeholder='e.g. "Show me all PDFs larger than 5MB" or "What are my most duplicated files?"',
                key="nl_query",
            )

            show_sql = st.checkbox("Show generated SQL", key="show_sql")

            if nl_query:
                with st.spinner("Thinking..."):
                    try:
                        from src.ai import nl_to_sql
                        sql = nl_to_sql(nl_query)

                        if show_sql:
                            st.code(sql, language="sql")

                        results = db.run_query(sql)

                        if results:
                            import pandas as pd
                            result_df = pd.DataFrame(results)

                            # Format size columns
                            for col in result_df.columns:
                                if "size" in col.lower() or "bytes" in col.lower():
                                    result_df[f"{col}_fmt"] = result_df[col].apply(
                                        lambda x: format_size_short(int(x)) if x else "0 B"
                                    )

                            st.write(f"**{len(results)}** results")
                            st.dataframe(result_df, use_container_width=True, hide_index=True)
                        else:
                            st.info("No results found.")

                    except ValueError as e:
                        st.error(f"Query blocked: {e}")
                    except RuntimeError as e:
                        st.error(f"Query failed: {e}")
                    except Exception as e:
                        st.error(f"Error: {e}")

    db.close()


if __name__ == "__main__":
    main_dashboard()
