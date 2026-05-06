"""Centralized configuration for the IntelliPredict application."""

from typing import Dict, Any

# ── Page Config ───────────────────────────────────────────────────────────────
PAGE_TITLE = "IntelliPredict — Restaurant AI"
PAGE_ICON = "🍽️"
LAYOUT = "wide"
INITIAL_SIDEBAR_STATE = "expanded"

# ── Color Palette ─────────────────────────────────────────────────────────────
PALETTE: Dict[str, str] = {
    "primary": "#FF6B35",
    "secondary": "#FF9F1C",
    "accent": "#FFBF69",
    "danger": "#E63946",
    "success": "#2EC4B6",
    "bg": "#0F0F13",
    "card": "#1A1A24",
    "text": "#F0EDE8",
    "muted": "#8A8696",
}

# ── Plotly Theme ──────────────────────────────────────────────────────────────
PLOTLY_LAYOUT: Dict[str, Any] = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font": {"color": PALETTE["text"], "family": "'IBM Plex Sans', sans-serif"},
    "xaxis": {"gridcolor": "#2a2a38", "linecolor": "#2a2a38"},
    "yaxis": {"gridcolor": "#2a2a38", "linecolor": "#2a2a38"},
    "legend": {"bgcolor": "rgba(0,0,0,0)", "bordercolor": "#2a2a38"},
    "margin": {"l": 20, "r": 20, "t": 40, "b": 20},
}

# ── CSS Styles ────────────────────────────────────────────────────────────────
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;600;700&family=Space+Grotesk:wght@500;700&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background-color: #0F0F13;
    color: #F0EDE8;
}
h1, h2, h3 { font-family: 'Space Grotesk', sans-serif; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: #13131C;
    border-right: 1px solid #1f1f2e;
}
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stRadio label { color: #c0bcc8 !important; font-size: 0.82rem; }

/* KPI cards */
.kpi-card {
    background: linear-gradient(135deg, #1A1A24 60%, #1f1f30);
    border: 1px solid #2a2a3a;
    border-radius: 12px;
    padding: 18px 20px;
    text-align: center;
    transition: border-color .2s;
}
.kpi-card:hover { border-color: #FF6B35; }
.kpi-label  { font-size: 0.78rem; color: #8A8696; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 6px; }
.kpi-value  { font-size: 1.7rem; font-weight: 700; color: #FF6B35; font-family: 'Space Grotesk', sans-serif; }
.kpi-delta  { font-size: 0.78rem; color: #2EC4B6; margin-top: 4px; }

/* Section header */
.section-header {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.1rem;
    font-weight: 700;
    color: #FF9F1C;
    border-left: 3px solid #FF6B35;
    padding-left: 10px;
    margin: 20px 0 10px;
}

/* Risk badge */
.risk-critical { color: #E63946; font-weight: 700; }
.risk-low      { color: #FFBF69; font-weight: 700; }
.risk-healthy  { color: #2EC4B6; font-weight: 700; }

/* Metric tag */
.metric-tag {
    display: inline-block;
    background: #1f1f2e;
    border: 1px solid #2a2a3a;
    border-radius: 6px;
    padding: 4px 12px;
    font-size: 0.82rem;
    margin: 3px;
    color: #F0EDE8;
}
.metric-tag span { color: #FF6B35; font-weight: 700; margin-left: 4px; }

/* Divider */
hr { border-color: #1f1f2e; }

/* Download button */
[data-testid="stDownloadButton"] button {
    background: linear-gradient(90deg, #FF6B35, #FF9F1C) !important;
    color: #0F0F13 !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 8px !important;
}

/* Tabs */
[data-baseweb="tab"] { color: #8A8696 !important; }
[aria-selected="true"] { color: #FF6B35 !important; border-bottom: 2px solid #FF6B35 !important; }
</style>
"""
