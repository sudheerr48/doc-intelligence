#!/usr/bin/env python3
"""
Doc Intelligence — Streamlit Dashboard (v6)

Modernized with Plotly charts, cached queries, custom theming,
and column-config tables.

Launch:
    doc-intelligence dashboard
    # or
    streamlit run src/dashboard/app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import streamlit as st
except ImportError:
    print("Streamlit is required: pip install 'doc-intelligence[dashboard]'")
    sys.exit(1)

from src.core.config import load_config
from src.core.database import FileDatabase


# ------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ------------------------------------------------------------------

st.set_page_config(
    page_title="Doc Intelligence",
    page_icon="📁",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------
# Custom CSS — compact metrics, better spacing, dark-theme-friendly
# ------------------------------------------------------------------

st.markdown("""
<style>
    /* Tighter metric cards */
    [data-testid="stMetric"] {
        background: var(--background-secondary, #f8f9fa);
        border: 1px solid var(--border-color, #e9ecef);
        border-radius: 8px;
        padding: 12px 16px;
    }
    [data-testid="stMetric"] label {
        font-size: 0.78rem !important;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        opacity: 0.7;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
    }

    /* Plotly chart containers */
    .stPlotlyChart { border-radius: 8px; }

    /* Sidebar styling */
    [data-testid="stSidebar"] [data-testid="stMarkdown"] h1 {
        font-size: 1.3rem !important;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
        border-radius: 6px 6px 0 0;
    }

    /* Expander borders */
    .streamlit-expanderHeader { border-radius: 6px; }

    /* Dataframe header */
    [data-testid="stDataFrame"] th {
        text-transform: uppercase;
        font-size: 0.72rem !important;
        letter-spacing: 0.05em;
    }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------
# Cached database connection
# ------------------------------------------------------------------

@st.cache_resource(ttl=300)
def _get_db(db_path_str: str) -> FileDatabase:
    """Cache the DB connection for 5 minutes to avoid reopening."""
    return FileDatabase(db_path_str)


# ------------------------------------------------------------------
# Sidebar navigation
# ------------------------------------------------------------------

PAGES = {
    "Overview":     ("overview",    "📊"),
    "File Browser": ("files",       "📂"),
    "Duplicates":   ("duplicates",  "📋"),
    "Tags":         ("tags",        "🏷️"),
    "Health":       ("health",      "🩺"),
    "Search":       ("search",      "🔍"),
    "Analytics":    ("analytics",   "📈"),
    "Settings":     ("settings",    "⚙️"),
}

with st.sidebar:
    st.markdown("# 📁 Doc Intelligence")
    st.caption("AI-powered file intelligence")
    st.divider()

    selected_page = st.radio(
        "Navigation",
        list(PAGES.keys()),
        format_func=lambda x: f"{PAGES[x][1]} {x}",
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("v6.0 — Local & Private")


# ------------------------------------------------------------------
# Load database
# ------------------------------------------------------------------

config = load_config()
db_path = Path(config["database"]["path"]).expanduser()

if not db_path.exists():
    st.error("Database not found. Run `doc-intelligence scan` first to index files.")
    st.info("```bash\npip install doc-intelligence\ndoc-intelligence scan\ndoc-intelligence dashboard\n```")
    st.stop()

db = _get_db(str(db_path))

# ------------------------------------------------------------------
# Render selected page
# ------------------------------------------------------------------

page_key = PAGES[selected_page][0]

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
