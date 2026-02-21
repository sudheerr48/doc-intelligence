"""Settings page — configuration overview, status, and provider info."""

import os
from pathlib import Path

import streamlit as st

from src.dashboard.components.metrics import format_size_short


def render(db, config):
    st.subheader("Configuration & Status")

    # Database info
    st.markdown("#### Database")
    db_path = Path(config["database"]["path"]).expanduser()

    c1, c2, c3, c4 = st.columns(4)
    try:
        db_size = db_path.stat().st_size
        c1.metric("Database Size", format_size_short(db_size))
    except OSError:
        c1.metric("Database Size", "N/A")

    embed_stats = db.get_embedding_stats()
    c2.metric("Embedded Files", f"{embed_stats['embedded_files']:,}")
    c3.metric("Files with Content", f"{embed_stats['files_with_content']:,}")

    total_files = db.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    c4.metric("Total Indexed", f"{total_files:,}")

    st.text_input("Database Path", str(db_path), disabled=True,
                  label_visibility="collapsed")

    st.divider()

    # Providers section (new plugin system)
    st.markdown("#### Providers")
    try:
        from src.providers.registry import list_all
        all_providers = list_all()
        prov_config = config.get("providers", {})

        cols = st.columns(len(all_providers))
        for col, (component, registered) in zip(cols, all_providers.items()):
            active = prov_config.get(component, "builtin")
            col.metric(
                component.title(),
                active,
                f"{len(registered)} available",
            )

        with st.expander("Provider details"):
            for component, registered in all_providers.items():
                active = prov_config.get(component, "builtin")
                names = ", ".join(
                    f"**{n}**" if n == active else n for n in registered
                )
                st.markdown(f"- **{component}**: {names}")
            st.caption("Edit `config.yaml` providers section to switch. See PLUGINS.md.")
    except ImportError:
        st.info("Provider system not loaded.")

    st.divider()

    # API keys status
    st.markdown("#### API Keys")
    keys = {
        "ANTHROPIC_API_KEY": "Anthropic Claude (AI classification, queries)",
        "OPENAI_API_KEY": "OpenAI (alternative AI provider, embeddings)",
        "VOYAGE_API_KEY": "Voyage AI (embeddings, Anthropic partner)",
    }

    key_cols = st.columns(len(keys))
    for col, (key, desc) in zip(key_cols, keys.items()):
        val = os.environ.get(key, "")
        if val:
            masked = val[:8] + "..." + val[-4:] if len(val) > 12 else "***"
            col.success(f"**{key}**\n\n`{masked}`")
        else:
            col.warning(f"**{key}**\n\nNot set")

    st.divider()

    # Scan folders and config in two columns
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Scan Folders")
        folders = config.get("scan_folders", [])
        for f in folders:
            p = Path(f["path"]).expanduser()
            exists = p.exists()
            icon = "✅" if exists else "❌"
            status = "exists" if exists else "missing"
            st.markdown(
                f"{icon} `{p}` — **{f.get('category', 'unknown')}** ({status})"
            )

    with col2:
        st.markdown("#### Exclude Patterns")
        patterns = config.get("exclude_patterns", [])
        st.code("\n".join(patterns), language="text")

    st.divider()

    # Raw config sections
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### AI Configuration")
        st.json(config.get("ai", {}))
    with col2:
        st.markdown("#### Embedding Configuration")
        st.json(config.get("embeddings", {}))
