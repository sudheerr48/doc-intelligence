"""Dashboard page — Smart Organization Suggestions."""

import streamlit as st
from src.core.config import format_size


def render(db, config):
    st.header("Smart Suggestions")
    st.caption("AI-powered recommendations for organizing your files")

    with st.spinner("Analyzing your file organization..."):
        from src.ai.suggestions import suggest_organization
        suggestions = suggest_organization(db)

    if not suggestions:
        st.success("Your files are well organized! No suggestions at this time.")
        return

    st.info(f"Found **{len(suggestions)}** suggestions for improving your file organization.")

    for i, s in enumerate(suggestions, 1):
        priority_color = {
            "high": "red",
            "medium": "orange",
            "low": "blue",
        }.get(s.get("priority", "low"), "gray")

        with st.expander(
            f"**{i}. {s['title']}** — :{priority_color}[{s.get('priority', 'low').upper()}]",
            expanded=(i <= 3),
        ):
            st.markdown(s["description"])
            st.markdown(f"**Suggestion:** {s['suggestion']}")

            if s.get("file_count"):
                st.markdown(f"**Affected files:** {s['file_count']:,}")
            if s.get("total_size"):
                st.markdown(f"**Total size:** {format_size(s['total_size'])}")

            if s.get("sample_files"):
                st.markdown("**Sample files:**")
                for f in s["sample_files"][:5]:
                    st.markdown(f"- `{f}`")
