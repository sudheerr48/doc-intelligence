"""Reusable data table components with column_config."""

import json
import streamlit as st

try:
    import pandas as pd
except ImportError:
    pd = None

from src.dashboard.components.metrics import format_size_short


def files_table(rows: list[dict], columns: list[str] = None):
    """Display a formatted file list with rich column configuration."""
    if not rows or pd is None:
        st.info("No files to display.")
        return

    df = pd.DataFrame(rows)

    if "size_bytes" in df.columns:
        df["size"] = df["size_bytes"].apply(format_size_short)

    if "tags" in df.columns:
        df["tags_str"] = df["tags"].apply(
            lambda t: ", ".join(t[:4])
            if isinstance(t, list) else (
                ", ".join(json.loads(t)[:4])
                if isinstance(t, str) and t.startswith("[") else ""
            )
        )

    display_cols = columns or [
        c for c in ["name", "size", "extension", "category", "tags_str", "path"]
        if c in df.columns
    ]

    col_config = {}
    if "name" in display_cols:
        col_config["name"] = st.column_config.TextColumn("Name", width="medium")
    if "size" in display_cols:
        col_config["size"] = st.column_config.TextColumn("Size", width="small")
    if "extension" in display_cols:
        col_config["extension"] = st.column_config.TextColumn("Type", width="small")
    if "category" in display_cols:
        col_config["category"] = st.column_config.TextColumn("Category", width="small")
    if "tags_str" in display_cols:
        col_config["tags_str"] = st.column_config.TextColumn("Tags", width="medium")
    if "path" in display_cols:
        col_config["path"] = st.column_config.TextColumn("Path", width="large")

    st.dataframe(
        df[display_cols],
        column_config=col_config,
        use_container_width=True,
        hide_index=True,
    )


def query_results_table(results: list[dict]):
    """Display SQL query results with auto-formatting of size columns."""
    if not results or pd is None:
        st.info("No results found.")
        return

    df = pd.DataFrame(results)

    col_config = {}
    for col in df.columns:
        if "size" in col.lower() or "bytes" in col.lower():
            df[f"{col}_fmt"] = df[col].apply(
                lambda x: format_size_short(int(x)) if x else "0 B"
            )
            col_config[f"{col}_fmt"] = st.column_config.TextColumn(
                f"{col} (formatted)", width="small",
            )

    st.dataframe(df, column_config=col_config, use_container_width=True, hide_index=True)
