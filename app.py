"""
IntelliPredict — AI-Powered Restaurant Management Platform
Features: Login, Real-Time Orders, Factor Prediction, Demand Forecasting,
Inventory, Revenue, AI Insights, Sentiment Analysis, Alerts,
Heatmap, PDF Reports, Platform Data (Zomato/Swiggy)
"""

import streamlit as st
from config import PAGE_TITLE, PAGE_ICON, LAYOUT, INITIAL_SIDEBAR_STATE, CUSTOM_CSS
from logger import logger
from data_generator import generate_dataset, RESTAURANTS
from models import PROPHET_AVAILABLE, XGB_AVAILABLE, TF_AVAILABLE
from auth import render_login_page, is_authenticated, get_current_user, has_permission, logout

from views.dashboard          import render_dashboard
from views.forecast           import render_forecast
from views.inventory          import render_inventory
from views.weather            import render_weather
from views.revenue            import render_revenue
from views.model_lab          import render_model_lab
from views.ai_insights        import render_ai_insights
from views.user_management    import render_user_management
from views.factor_prediction  import render_factor_prediction
from views.pdf_report         import render_pdf_report
from views.alerts             import render_alerts
from views.heatmap            import render_heatmap
from views.sentiment          import render_sentiment
from views.live_platform_data import render_live_platform_data

st.set_page_config(
    page_title=PAGE_TITLE, page_icon=PAGE_ICON,
    layout=LAYOUT, initial_sidebar_state=INITIAL_SIDEBAR_STATE,
)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

if not is_authenticated():
    render_login_page()
    st.stop()

user = get_current_user()
role = user.get("role", "staff")

@st.cache_data(show_spinner=False)
def load_data():
    logger.info("Loading dataset...")
    return generate_dataset()

def render_sidebar():
    with st.sidebar:
        st.markdown("## 🍽️ IntelliPredict")
        st.markdown(f"<small style='color:#8A8696'>Restaurant AI Platform</small>", unsafe_allow_html=True)
        st.divider()

        all_pages = [
            # label                      permission key
            ("🏠 Dashboard",             "dashboard"),
            ("⚡ Real-Time Orders",       "dashboard"),
            ("📡 Platform Data",          "dashboard"),
            ("📈 Demand Forecast",        "forecast"),
            ("🧩 Factor Prediction",      "forecast"),
            ("📦 Inventory & Waste",      "inventory"),
            ("🌦️ Weather & Events",       "weather"),
            ("💰 Revenue Optimizer",      "revenue"),
            ("🗺️ Restaurant Heatmap",     "revenue"),
            ("🔬 Model Lab",              "model_lab"),
            ("🤖 AI Insights",            "ai_insights"),
            ("🎯 Sentiment Analysis",     "ai_insights"),
            ("📱 Smart Alerts",           "ai_insights"),
            ("📊 PDF Report",             "ai_insights"),
            ("👥 User Management",        "user_management"),
        ]

        visible = [label for label, key in all_pages if has_permission(key)]
        page = st.radio("Navigate", visible, label_visibility="collapsed")

        st.divider()

        if role == "admin":
            rest_name = st.selectbox("🏪 Restaurant", list(RESTAURANTS.values()))
        else:
            assigned  = user.get("restaurant_access", "R001")
            rest_name = RESTAURANTS.get(assigned, list(RESTAURANTS.values())[0])
            st.markdown(f"<small style='color:#8A8696'>🏪 {rest_name}</small>", unsafe_allow_html=True)

        rest_id = [k for k, v in RESTAURANTS.items() if v == rest_name][0]

        st.divider()
        st.markdown("<small style='color:#8A8696'>Model Status</small>", unsafe_allow_html=True)
        st.markdown(f"{'✅' if PROPHET_AVAILABLE else '⚠️'} Prophet")
        st.markdown(f"{'✅' if XGB_AVAILABLE    else '⚠️'} XGBoost")
        st.markdown(f"{'✅' if TF_AVAILABLE     else '⚠️'} LSTM")

        st.divider()

        role_colors = {"admin": "#E63946", "manager": "#FF9F1C", "staff": "#2EC4B6"}
        rc      = role_colors.get(role, "#8A8696")
        avatar  = user.get("avatar", "??")
        name    = user.get("name", "User")

        st.markdown(f"""
        <div style='background:#0F0F13;border:1px solid #2a2a3a;border-radius:10px;padding:12px 14px'>
            <div style='display:flex;align-items:center;gap:10px'>
                <div style='width:34px;height:34px;border-radius:50%;background:{rc}33;
                            display:flex;align-items:center;justify-content:center;
                            font-size:12px;font-weight:700;color:{rc}'>{avatar}</div>
                <div>
                    <div style='font-size:13px;font-weight:600;color:#F0EDE8'>{name}</div>
                    <div style='font-size:10px;color:{rc};font-weight:700;
                                text-transform:uppercase;letter-spacing:.06em'>{role}</div>
                </div>
            </div>
        </div>""", unsafe_allow_html=True)

        if st.button("🚪 Sign Out", use_container_width=True):
            logout()

        return page, rest_id, rest_name


def main():
    page, rest_id, rest_name = render_sidebar()

    with st.spinner("Loading data…"):
        df = load_data()

    page_map = {
        "🏠 Dashboard":          ("dashboard",       lambda: render_dashboard(df, rest_id, rest_name)),
        "⚡ Real-Time Orders":    ("dashboard",       lambda: render_dashboard(df, rest_id, rest_name)),
        "📡 Platform Data":       ("dashboard",       lambda: render_live_platform_data(df, rest_id, rest_name)),
        "📈 Demand Forecast":    ("forecast",        lambda: render_forecast(df, rest_id, rest_name)),
        "🧩 Factor Prediction":  ("forecast",        lambda: render_factor_prediction(df, rest_id, rest_name)),
        "📦 Inventory & Waste":  ("inventory",       lambda: render_inventory(df, rest_id, rest_name)),
        "🌦️ Weather & Events":   ("weather",         lambda: render_weather(df, rest_id, rest_name)),
        "💰 Revenue Optimizer":  ("revenue",         lambda: render_revenue(df, rest_id, rest_name)),
        "🗺️ Restaurant Heatmap": ("revenue",         lambda: render_heatmap(df, rest_id, rest_name)),
        "🔬 Model Lab":          ("model_lab",       lambda: render_model_lab(df, rest_id, rest_name)),
        "🤖 AI Insights":        ("ai_insights",     lambda: render_ai_insights(df, rest_id, rest_name)),
        "🎯 Sentiment Analysis": ("ai_insights",     lambda: render_sentiment(rest_name)),
        "📱 Smart Alerts":       ("ai_insights",     lambda: render_alerts(df, rest_id, rest_name)),
        "📊 PDF Report":         ("ai_insights",     lambda: render_pdf_report(df, rest_id, rest_name)),
        "👥 User Management":    ("user_management", lambda: render_user_management()),
    }

    if page in page_map:
        key, renderer = page_map[page]
        if has_permission(key):
            renderer()
        else:
            st.error("⛔ You don't have permission to access this page.")
    else:
        render_dashboard(df, rest_id, rest_name)


if __name__ == "__main__":
    main()
