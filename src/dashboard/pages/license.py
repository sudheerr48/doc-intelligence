"""Dashboard page — License & Account."""

import streamlit as st


def render(db, config):
    st.header("License & Account")

    from src.licensing import get_current_tier, TIER_LIMITS
    from src.licensing.keys import load_stored_license, store_license, clear_license
    from src.licensing.tiers import get_tier_display_name, Tier

    tier = get_current_tier()
    tier_name = get_tier_display_name(tier)
    info = load_stored_license()

    # Current status
    col1, col2, col3 = st.columns(3)
    col1.metric("Current Tier", tier_name)
    if info and info.valid:
        col2.metric("Status", "Active")
        if info.days_remaining is not None:
            col3.metric("Days Remaining", str(info.days_remaining))
        else:
            col3.metric("Expires", "Never")
    else:
        col2.metric("Status", "Free")
        col3.metric("Days Remaining", "—")

    st.divider()

    # Feature comparison
    st.subheader("Feature Comparison")

    features = [
        ("max_files", "Max Files"),
        ("ai_tagging", "AI Tagging"),
        ("pii_detection", "PII Detection"),
        ("semantic_search", "Semantic Search"),
        ("image_classification", "Image Classification"),
        ("smart_suggestions", "Smart Suggestions"),
        ("health_report", "Health Report"),
        ("duplicate_detection", "Duplicate Detection"),
        ("mcp_server", "MCP Server"),
    ]

    header_cols = st.columns([2, 1, 1, 1])
    header_cols[0].markdown("**Feature**")
    header_cols[1].markdown("**Free**")
    header_cols[2].markdown("**Pro**")
    header_cols[3].markdown("**Team**")

    for key, label in features:
        cols = st.columns([2, 1, 1, 1])
        cols[0].write(label)
        for i, t in enumerate([Tier.FREE, Tier.PRO, Tier.TEAM]):
            val = TIER_LIMITS[t][key]
            if val is None:
                cols[i + 1].write("Unlimited")
            elif isinstance(val, bool):
                cols[i + 1].write("Yes" if val else "No")
            else:
                cols[i + 1].write(str(val))

    st.divider()

    # Activation
    st.subheader("Activate License")
    key_input = st.text_input(
        "License Key",
        placeholder="DI-PRO-XXXXXXXX-XXXXXXXXXXXX-XXXXXXXXXXXXXXXX",
    )
    col1, col2 = st.columns(2)
    if col1.button("Activate", type="primary", disabled=not key_input):
        result = store_license(key_input)
        if result.valid:
            st.success(f"License activated! Tier: {result.tier.upper()}")
            st.rerun()
        else:
            st.error(f"Invalid key: {result.error}")

    if col2.button("Deactivate", disabled=(tier == Tier.FREE)):
        clear_license()
        st.success("License removed. Reverted to Free tier.")
        st.rerun()
