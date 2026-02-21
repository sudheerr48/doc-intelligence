"""Settings page — configuration overview and status."""

import os
from pathlib import Path

import streamlit as st

from src.dashboard.components.metrics import format_size_short


def render(db, config):
    st.subheader("Configuration & Status")

    # Database info
    st.markdown("### Database")
    db_path = Path(config["database"]["path"]).expanduser()
    c1, c2 = st.columns(2)
    c1.text_input("Database Path", str(db_path), disabled=True)
    try:
        db_size = db_path.stat().st_size
        c2.metric("Database Size", format_size_short(db_size))
    except OSError:
        c2.metric("Database Size", "N/A")

    embed_stats = db.get_embedding_stats()
    c3, c4 = st.columns(2)
    c3.metric("Embedded Files", f"{embed_stats['embedded_files']:,}")
    c4.metric("Files with Content", f"{embed_stats['files_with_content']:,}")

    st.divider()

    # API keys status
    st.markdown("### API Keys")
    keys = {
        "ANTHROPIC_API_KEY": "Anthropic Claude (AI classification, queries)",
        "OPENAI_API_KEY": "OpenAI (alternative AI provider, embeddings)",
        "VOYAGE_API_KEY": "Voyage AI (embeddings, Anthropic partner)",
    }
    for key, desc in keys.items():
        val = os.environ.get(key, "")
        if val:
            masked = val[:8] + "..." + val[-4:] if len(val) > 12 else "***"
            st.success(f"**{key}**: `{masked}` — {desc}")
        else:
            st.warning(f"**{key}**: Not set — {desc}")

    st.divider()

    # Scan folders
    st.markdown("### Scan Folders")
    folders = config.get("scan_folders", [])
    for f in folders:
        p = Path(f["path"]).expanduser()
        exists = p.exists()
        status = "exists" if exists else "missing"
        icon = "✅" if exists else "❌"
        st.text(f"{icon}  {p}  ({f.get('category', 'unknown')}) — {status}")

    st.divider()

    # AI config
    st.markdown("### AI Configuration")
    ai_config = config.get("ai", {})
    st.json(ai_config)

    st.divider()

    # Embedding config
    st.markdown("### Embedding Configuration")
    emb_config = config.get("embeddings", {})
    st.json(emb_config)

    st.divider()

    # Exclude patterns
    st.markdown("### Exclude Patterns")
    patterns = config.get("exclude_patterns", [])
    st.code("\n".join(patterns), language="text")
