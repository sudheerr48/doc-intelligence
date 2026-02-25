"""Dashboard page — PII Detection Scanner."""

import streamlit as st


def render(db, config):
    st.header("PII Detection")
    st.caption("Scan your indexed files for sensitive personal information")

    col1, col2 = st.columns([3, 1])
    with col2:
        limit = st.number_input("Max files to scan", min_value=10, max_value=5000, value=500)
    with col1:
        run_scan = st.button("Run PII Scan", type="primary", use_container_width=True)

    if run_scan:
        with st.spinner("Scanning files for PII patterns..."):
            from src.ai.pii import scan_files_summary
            summary = scan_files_summary(db, limit=limit)

        # Metrics row
        c1, c2, c3 = st.columns(3)
        c1.metric("Files Scanned", f"{summary['files_scanned']:,}")
        c2.metric("Files with PII", f"{summary['files_with_pii']:,}")
        c3.metric("Total Matches", f"{summary['total_matches']:,}")

        st.divider()

        # Risk breakdown
        risk = summary["risk_breakdown"]
        if any(risk.values()):
            st.subheader("Risk Breakdown")
            r1, r2, r3 = st.columns(3)
            r1.metric("High Risk", risk.get("high", 0), help="SSNs, credit cards")
            r2.metric("Medium Risk", risk.get("medium", 0), help="Emails, phones, DOB")
            r3.metric("Low Risk", risk.get("low", 0), help="IPs, addresses")

        # PII type counts
        if summary["type_counts"]:
            st.subheader("PII Types Found")
            import pandas as pd
            df = pd.DataFrame(
                list(summary["type_counts"].items()),
                columns=["Type", "Count"],
            ).sort_values("Count", ascending=False)
            st.bar_chart(df.set_index("Type"))

        # High risk files
        if summary["high_risk_files"]:
            st.subheader("High Risk Files")
            for f in summary["high_risk_files"][:20]:
                with st.expander(f"**{f['path'].rsplit('/', 1)[-1]}** — {f['match_count']} matches"):
                    st.text(f["path"])
                    for m in f["matches"][:10]:
                        st.markdown(
                            f"- **{m['type']}**: `{m['value']}` "
                            f"(line {m.get('line', '?')}, confidence {m['confidence']:.0%})"
                        )
        elif summary["files_with_pii"] == 0:
            st.success("No PII detected in your files!")

    else:
        st.info(
            "Click **Run PII Scan** to check your indexed files for:\n"
            "- Social Security Numbers (SSN)\n"
            "- Credit card numbers\n"
            "- Email addresses\n"
            "- Phone numbers\n"
            "- IP addresses\n"
            "- Street addresses\n\n"
            "All scanning happens locally — no data leaves your machine."
        )
