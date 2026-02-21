"""Search page — text search, semantic search, and AI queries."""

import json
import streamlit as st

try:
    import pandas as pd
except ImportError:
    pd = None

from src.dashboard.components.metrics import format_size_short
from src.dashboard.components.tables import query_results_table


def render(db, config):
    tab_text, tab_semantic, tab_ai = st.tabs([
        "Text Search", "Semantic Search", "AI Query",
    ])

    with tab_text:
        _text_search(db)
    with tab_semantic:
        _semantic_search(db)
    with tab_ai:
        _ai_query(db)


def _text_search(db):
    st.subheader("Search Files")
    query = st.text_input(
        "Search query",
        placeholder="filename, path, or content...",
        key="text_search_input",
    )
    if query:
        results = db.search(query, limit=100)
        if results and pd is not None:
            df = pd.DataFrame(results)
            df["size"] = df["size_bytes"].apply(format_size_short)
            df["match"] = df["content_match"].apply(
                lambda x: "content" if x else "name/path"
            )
            st.caption(f"Found **{len(results)}** results")
            st.dataframe(
                df[["name", "size", "category", "match", "path"]],
                column_config={
                    "name": st.column_config.TextColumn("Name", width="medium"),
                    "size": st.column_config.TextColumn("Size", width="small"),
                    "category": st.column_config.TextColumn("Category", width="small"),
                    "match": st.column_config.TextColumn("Match Type", width="small"),
                    "path": st.column_config.TextColumn("Path", width="large"),
                },
                use_container_width=True,
                hide_index=True,
            )
        elif not results:
            st.warning("No results found.")


def _semantic_search(db):
    st.subheader("Search by Meaning")

    try:
        from src.ai.providers import is_embedding_available
    except ImportError:
        st.warning("AI packages not installed.")
        return

    if not is_embedding_available():
        st.warning(
            "Semantic search requires embeddings.\n\n"
            "Set `VOYAGE_API_KEY` or `OPENAI_API_KEY`, then run:\n"
            "```\ndoc-intelligence embed\n```"
        )
        return

    embed_stats = db.get_embedding_stats()
    if embed_stats["embedded_files"] == 0:
        st.warning("No embeddings found. Run `doc-intelligence embed` first.")
        return

    st.caption(f"Searching **{embed_stats['embedded_files']}** embedded files")

    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input(
            "Describe what you're looking for",
            placeholder="e.g., tax documents from 2024",
            key="semantic_query",
        )
    with col2:
        threshold = st.slider(
            "Min similarity", 0.0, 1.0, 0.3, 0.05, key="sem_threshold",
        )

    if query:
        with st.spinner("Computing similarity..."):
            try:
                from src.ai.embeddings import generate_embeddings
                query_vec = generate_embeddings([query])[0]
                results = db.semantic_search(query_vec, limit=20)
                results = [r for r in results if r["similarity"] >= threshold]

                if results and pd is not None:
                    df = pd.DataFrame(results)
                    df["size"] = df["size_bytes"].apply(format_size_short)
                    if "tags" in df.columns:
                        df["tags_str"] = df["tags"].apply(
                            lambda t: ", ".join(json.loads(t)[:3])
                            if isinstance(t, str) and t.startswith("[") else ""
                        )
                    else:
                        df["tags_str"] = ""

                    st.caption(f"**{len(results)}** matches")
                    st.dataframe(
                        df[["similarity", "name", "size", "tags_str", "path"]],
                        column_config={
                            "similarity": st.column_config.ProgressColumn(
                                "Score", min_value=0.0, max_value=1.0,
                                format="%.3f",
                            ),
                            "name": st.column_config.TextColumn("Name", width="medium"),
                            "size": st.column_config.TextColumn("Size", width="small"),
                            "tags_str": st.column_config.TextColumn("Tags", width="medium"),
                            "path": st.column_config.TextColumn("Path", width="large"),
                        },
                        use_container_width=True,
                        hide_index=True,
                    )
                elif not results:
                    st.info("No similar files found above threshold.")
            except Exception as e:
                st.error(f"Error: {e}")


def _ai_query(db):
    st.subheader("Ask Your Files (AI-Powered)")
    st.caption("Ask questions in plain English — powered by Claude or GPT")

    try:
        from src.ai.providers import is_ai_available
    except ImportError:
        st.warning("AI packages not installed.")
        return

    if not is_ai_available():
        st.warning(
            "AI features require `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`.\n\n"
            "```bash\n"
            "pip install 'doc-intelligence[ai]'\n"
            "export ANTHROPIC_API_KEY=your-key\n"
            "```"
        )
        return

    col1, col2 = st.columns([4, 1])
    with col1:
        nl_query = st.text_input(
            "Ask a question",
            placeholder='e.g., "Show me all PDFs larger than 5MB"',
            key="nl_query",
        )
    with col2:
        show_sql = st.checkbox("Show SQL", key="show_sql")

    if nl_query:
        with st.spinner("Thinking..."):
            try:
                from src.ai.query import nl_to_sql
                sql = nl_to_sql(nl_query)

                if show_sql:
                    st.code(sql, language="sql")

                results = db.run_query(sql)
                if results:
                    st.caption(f"**{len(results)}** results")
                    query_results_table(results)
                else:
                    st.info("No results found.")

            except ValueError as e:
                st.error(f"Query blocked: {e}")
            except RuntimeError as e:
                st.error(f"Query failed: {e}")
            except Exception as e:
                st.error(f"Error: {e}")
