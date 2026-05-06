"""Demand forecast view component for IntelliPredict."""

import streamlit as st
import pandas as pd
from data_generator import CATEGORIES, get_time_series
from models import prophet_forecast, xgboost_forecast, lstm_forecast, ensemble_forecast, FEATURE_EXPLANATIONS
from utils import forecast_chart, feature_importance_chart, model_comparison_df
from weather_api import get_forecast

def render_forecast(df: pd.DataFrame, rest_id: str, rest_name: str):
    """Renders the demand forecasting page.
    
    Args:
        df: The full restaurant dataset.
        rest_id: Selected restaurant ID.
        rest_name: Selected restaurant name.
    """
    st.markdown("# 📈 Demand Forecasting")
    st.markdown(f"<small style='color:#8A8696'>Multi-model forecasting for {rest_name}</small>", unsafe_allow_html=True)
    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        category = st.selectbox("Menu Category", CATEGORIES)
    with col2:
        horizon = st.selectbox("Forecast Horizon", [7, 14, 30], index=1)
    with col3:
        model_choice = st.selectbox("Model", ["Ensemble", "Prophet", "XGBoost", "LSTM"])

    run = st.button("🚀 Run Forecast", use_container_width=True)

    # Fetch real-time weather forecast
    raw_weather = get_forecast()
    weather_df = None
    if raw_weather:
        w_df = pd.DataFrame(raw_weather)
        w_df["date"] = pd.to_datetime(w_df["datetime"])
        # Daily averages for the forecast
        weather_df = w_df.groupby(w_df["date"].dt.date).agg({
            "temp": "mean",
            "rain": "max"
        }).reset_index()
        weather_df.columns = ["date", "temperature", "rainfall_mm"]
        weather_df["date"] = pd.to_datetime(weather_df["date"])

    if run:
        ts = get_time_series(df, rest_id, category)
        
        if weather_df is not None:
            st.info("🌐 Real-time weather forecast integrated for the next 5 days.")
        
        with st.spinner(f"Training {model_choice} model…"):
            if model_choice == "Prophet":
                forecast, metrics = prophet_forecast(ts, horizon)
                feat_imp = None
                all_results = {}
            elif model_choice == "XGBoost":
                forecast, metrics, feat_imp = xgboost_forecast(ts, horizon, weather_df)
                all_results = {}
            elif model_choice == "LSTM":
                forecast, metrics = lstm_forecast(ts, horizon)
                feat_imp = None
                all_results = {}
            else:  # Ensemble
                forecast, metrics, all_results, feat_imp = ensemble_forecast(ts, horizon, weather_df)

        st.markdown("<div class='section-header'>Forecast Chart</div>", unsafe_allow_html=True)
        fig = forecast_chart(ts, forecast, f"{rest_name} · {category} · {horizon}-day Forecast")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("<div class='section-header'>Model Metrics</div>", unsafe_allow_html=True)
        m1, m2, m3 = st.columns(3)
        for col, k in zip([m1, m2, m3], ["MAE", "RMSE", "MAPE"]):
            col.markdown(f"""
            <div class='kpi-card'>
                <div class='kpi-label'>{k}</div>
                <div class='kpi-value'>{metrics.get(k, '–')}</div>
            </div>""", unsafe_allow_html=True)

        if all_results:
            st.markdown("<div class='section-header'>Component Model Comparison</div>", unsafe_allow_html=True)
            comp_df = model_comparison_df(all_results)
            st.dataframe(comp_df.set_index("Model"), use_container_width=True)

        if feat_imp:
            st.markdown("<div class='section-header'>Predictive Factor Analysis</div>", unsafe_allow_html=True)
            st.markdown("<small style='color:#8A8696'>Insights into what's driving this specific forecast</small>", unsafe_allow_html=True)
            
            fig_fi = feature_importance_chart(feat_imp)
            st.plotly_chart(fig_fi, use_container_width=True)
            
            with st.expander("📖 View Factor Definitions"):
                for feat, score in sorted(feat_imp.items(), key=lambda x: x[1], reverse=True)[:8]:
                    desc = FEATURE_EXPLANATIONS.get(feat, "Standard statistical feature.")
                    st.markdown(f"**{feat.replace('_', ' ').title()}**: {desc}")

        st.markdown("<div class='section-header'>Forecast Table</div>", unsafe_allow_html=True)
        display_fc = forecast.copy()
        display_fc["date"] = display_fc["date"].dt.strftime("%Y-%m-%d")
        st.dataframe(display_fc, use_container_width=True)

        csv = forecast.to_csv(index=False).encode()
        st.download_button("⬇️ Download Forecast CSV", csv,
                           file_name=f"forecast_{rest_id}_{category}_{horizon}d.csv",
                           mime="text/csv")
