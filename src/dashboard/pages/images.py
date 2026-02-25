"""Dashboard page — Image Classification."""

import streamlit as st


def render(db, config):
    st.header("Image Classification")
    st.caption("Classify images as screenshots, photos, documents, diagrams, and more")

    # Tier enforcement
    from src.licensing.tiers import check_feature
    if not check_feature("image_classification"):
        st.warning("**Pro Feature** — Image classification requires a Pro license.")
        st.markdown(
            "Upgrade to automatically classify images as screenshots, photos, "
            "documents, diagrams, and more.\n\n"
            "```\ndoc-intelligence activate <YOUR-LICENSE-KEY>\n```\n\n"
            "[Get a Pro license](https://doc-intelligence.dev/pricing)"
        )
        return

    with st.spinner("Classifying images..."):
        from src.ai.image_classify import image_classification_summary
        summary = image_classification_summary(db)

    if summary["total_images"] == 0:
        st.warning("No images found in the index. Run a scan first.")
        return

    st.metric("Total Images", f"{summary['total_images']:,}")
    st.divider()

    # Category breakdown
    categories = summary.get("categories", {})
    if categories:
        st.subheader("Image Categories")

        import pandas as pd
        df = pd.DataFrame(
            list(categories.items()),
            columns=["Category", "Count"],
        ).sort_values("Count", ascending=False)
        st.bar_chart(df.set_index("Category"))

        # Category cards
        cols = st.columns(min(len(categories), 4))
        for idx, (cat, count) in enumerate(
            sorted(categories.items(), key=lambda x: x[1], reverse=True)
        ):
            icon = {
                "screenshot": "📸",
                "photo": "📷",
                "document": "📄",
                "diagram": "📊",
                "icon": "🎨",
                "meme": "😂",
                "other": "❓",
            }.get(cat, "📁")
            cols[idx % len(cols)].metric(f"{icon} {cat.title()}", f"{count:,}")

    # Sample classifications
    st.divider()
    st.subheader("Sample Classifications")

    for item in summary.get("classifications", [])[:20]:
        conf_pct = f"{item['confidence']:.0%}"
        name = item["path"].rsplit("/", 1)[-1] if "/" in item["path"] else item["path"]
        st.markdown(
            f"- **{name}** → `{item['category']}` ({conf_pct}) "
            f"*{', '.join(item.get('reasons', []))}*"
        )
