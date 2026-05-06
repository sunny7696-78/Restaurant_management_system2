"""
AI-Powered IntelliPredict
Real-Time Restaurant Demand Forecasting & WasteZero Optimization Platform
"""

import streamlit as st
from config import (
    PAGE_TITLE, PAGE_ICON, LAYOUT, INITIAL_SIDEBAR_STATE, CUSTOM_CSS
)
from logger import logger
from data_generator import generate_dataset, RESTAURANTS
from models import PROPHET_AVAILABLE, XGB_AVAILABLE, TF_AVAILABLE

# Import view components
from views.dashboard import render_dashboard
from views.forecast import render_forecast
from views.inventory import render_inventory
from views.weather import render_weather
from views.revenue import render_revenue
from views.model_lab import render_model_lab

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout=LAYOUT,
    initial_sidebar_state=INITIAL_SIDEBAR_STATE,
)

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ── Data loading (cached) ─────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_data():
    """Loads the restaurant dataset with caching."""
    logger.info("Loading dataset...")
    return generate_dataset()

# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar():
    """Renders the sidebar navigation and restaurant selector."""
    with st.sidebar:
        st.markdown("## 🍽️ IntelliPredict")
        st.markdown("<small style='color:#8A8696'>Restaurant AI Platform</small>", unsafe_allow_html=True)
        st.divider()

        page = st.radio(
            "Navigate",
            ["🏠 Dashboard", "📈 Demand Forecast", "📦 Inventory & Waste",
             "🌦️ Weather & Events", "💰 Revenue Optimizer", "🔬 Model Lab"],
            label_visibility="collapsed",
        )

        st.divider()
        rest_name = st.selectbox("🏪 Restaurant", list(RESTAURANTS.values()))
        rest_id = [k for k, v in RESTAURANTS.items() if v == rest_name][0]

        st.divider()
        st.markdown("<small style='color:#8A8696'>Model Availability</small>", unsafe_allow_html=True)
        st.markdown(f"{'✅' if PROPHET_AVAILABLE else '⚠️'} Prophet")
        st.markdown(f"{'✅' if XGB_AVAILABLE    else '⚠️'} XGBoost")
        st.markdown(f"{'✅' if TF_AVAILABLE     else '⚠️'} LSTM / TensorFlow")
        
        return page, rest_id, rest_name

# ── Main Entry Point ──────────────────────────────────────────────────────────

def main():
    """Main application entry point."""
    page, rest_id, rest_name = render_sidebar()

    with st.spinner("Loading data…"):
        df = load_data()

    if page == "🏠 Dashboard":
        render_dashboard(df, rest_id, rest_name)
    elif page == "📈 Demand Forecast":
        render_forecast(df, rest_id, rest_name)
    elif page == "📦 Inventory & Waste":
        render_inventory(df, rest_id, rest_name)
    elif page == "🌦️ Weather & Events":
        render_weather(df, rest_id, rest_name)
    elif page == "💰 Revenue Optimizer":
        render_revenue(df, rest_id, rest_name)
    elif page == "🔬 Model Lab":
        render_model_lab(df, rest_id, rest_name)

if __name__ == "__main__":
    main()
