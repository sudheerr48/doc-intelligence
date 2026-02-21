#!/usr/bin/env python3
"""
Doc Intelligence — Streamlit Dashboard

Full-featured web interface for file intelligence:
  - Overview with KPI metrics and storage charts
  - File browser with search, filter, and sort
  - Duplicate finder and management
  - AI tag browser and management
  - Health report with scoring and recommendations
  - Text, semantic, and AI-powered search
  - Analytics with distributions and trends
  - Settings and configuration overview

Launch:
    doc-intelligence dashboard
    # or
    streamlit run src/dashboard/app.py
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import streamlit as st
except ImportError:
    print("Streamlit is required for the dashboard.")
    print("Install with: pip install 'doc-intelligence[dashboard]'")
    sys.exit(1)

from src.core.config import load_config
from src.core.database import FileDatabase


# ------------------------------------------------------------------
# Page configuration
# ------------------------------------------------------------------

st.set_page_config(
    page_title="Doc Intelligence",
    page_icon="📁",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------
# Sidebar navigation
# ------------------------------------------------------------------

PAGES = {
    "Overview": "overview",
    "File Browser": "files",
    "Duplicates": "duplicates",
    "Tags": "tags",
    "Health": "health",
    "Search": "search",
    "Analytics": "analytics",
    "Settings": "settings",
}

PAGE_ICONS = {
    "Overview": "📊",
    "File Browser": "📂",
    "Duplicates": "📋",
    "Tags": "🏷️",
    "Health": "🩺",
    "Search": "🔍",
    "Analytics": "📈",
    "Settings": "⚙️",
}

with st.sidebar:
    st.title("📁 Doc Intelligence")
    st.caption("AI-powered file intelligence")
    st.divider()

    selected_page = st.radio(
        "Navigation",
        list(PAGES.keys()),
        format_func=lambda x: f"{PAGE_ICONS.get(x, '')} {x}",
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("v5.0 — Local & Private")

# ------------------------------------------------------------------
# Load database
# ------------------------------------------------------------------

config = load_config()
db_path = Path(config["database"]["path"]).expanduser()

if not db_path.exists():
    st.error(
        "Database not found. Run `doc-intelligence scan` first to index files."
    )
    st.info(
        "```bash\n"
        "pip install doc-intelligence\n"
        "doc-intelligence scan\n"
        "doc-intelligence dashboard\n"
        "```"
    )
    st.stop()

db = FileDatabase(str(db_path))

# ------------------------------------------------------------------
# Render selected page
# ------------------------------------------------------------------

page_key = PAGES[selected_page]

if page_key == "overview":
    from src.dashboard.pages.overview import render
elif page_key == "files":
    from src.dashboard.pages.files import render
elif page_key == "duplicates":
    from src.dashboard.pages.duplicates import render
elif page_key == "tags":
    from src.dashboard.pages.tags import render
elif page_key == "health":
    from src.dashboard.pages.health import render
elif page_key == "search":
    from src.dashboard.pages.search import render
elif page_key == "analytics":
    from src.dashboard.pages.analytics import render
elif page_key == "settings":
    from src.dashboard.pages.settings import render

render(db, config)

# ------------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------------

db.close()
