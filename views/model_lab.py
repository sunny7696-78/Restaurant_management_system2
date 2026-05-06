"""Model lab view component for IntelliPredict."""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from data_generator import CATEGORIES, get_time_series
from models import xgboost_forecast, lstm_forecast, prophet_forecast, ensemble_forecast, PROPHET_AVAILABLE, build_features
from utils import model_comparison_df, feature_importance_chart, PALETTE

def render_model_lab(df: pd.DataFrame, rest_id: str, rest_name: str):
    """Renders the model performance and explainability page.
    
    Args:
        df: The full restaurant dataset.
        rest_id: Selected restaurant ID.
        rest_name: Selected restaurant name.
    """
    st.markdown("# 🔬 Model Performance & Explainability")
    st.markdown(f"<small style='color:#8A8696'>Deep-dive model comparison & diagnostics for {rest_name}</small>", unsafe_allow_html=True)
    st.divider()

    category = st.selectbox("Category", CATEGORIES)
    run_lab  = st.button("🧪 Run All Models & Compare", use_container_width=True)

    if run_lab:
        ts = get_time_series(df, rest_id, category)
        results = {}

        with st.spinner("Training XGBoost…"):
            fc_x, met_x, feat_imp = xgboost_forecast(ts, 14)
            results["XGBoost"] = (fc_x, met_x)

        with st.spinner("Training LSTM…"):
            fc_l, met_l = lstm_forecast(ts, 14)
            results["LSTM"] = (fc_l, met_l)

        if PROPHET_AVAILABLE:
            with st.spinner("Training Prophet…"):
                fc_p, met_p = prophet_forecast(ts, 14)
                results["Prophet"] = (fc_p, met_p)

        st.markdown("<div class='section-header'>Model Comparison — Metrics</div>", unsafe_allow_html=True)
        comp = model_comparison_df(results)
        st.dataframe(comp.set_index("Model"), use_container_width=True)

        # Best model highlight
        best_model = comp.loc[comp["MAPE %"].idxmin(), "Model"]
        st.success(f"🏆 Best Model: **{best_model}** (lowest MAPE)")

        st.markdown("<div class='section-header'>Forecast Comparison Chart</div>", unsafe_allow_html=True)
        fig = go.Figure()
        recent = ts.tail(60)
        fig.add_trace(go.Scatter(x=recent["date"], y=recent["quantity_sold"],
                                  name="Historical", line=dict(color=PALETTE["muted"], width=1.5)))
        colors = [PALETTE["primary"], PALETTE["secondary"], PALETTE["success"]]
        for (name, (fc, _)), color in zip(results.items(), colors):
            fig.add_trace(go.Scatter(x=fc["date"], y=fc["predicted"],
                                      name=name, line=dict(color=color, width=2),
                                      mode="lines+markers", marker=dict(size=3)))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font=dict(color=PALETTE["text"]),
                          xaxis=dict(gridcolor="#2a2a38"),
                          yaxis=dict(gridcolor="#2a2a38"),
                          legend=dict(bgcolor="rgba(0,0,0,0)"),
                          margin=dict(l=0, r=0, t=10, b=0), height=320)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("<div class='section-header'>XGBoost Feature Importance</div>", unsafe_allow_html=True)
        fig_fi = feature_importance_chart(feat_imp)
        st.plotly_chart(fig_fi, use_container_width=True)

        st.markdown("<div class='section-header'>Residual Analysis (XGBoost)</div>", unsafe_allow_html=True)
        df_feat, FEATURES = build_features(ts)
        
        try:
            import xgboost as xgb
            model = xgb.XGBRegressor(n_estimators=200, max_depth=5, learning_rate=0.08,
                                      subsample=0.8, random_state=42, verbosity=0)
        except ImportError:
            from sklearn.ensemble import GradientBoostingRegressor
            model = GradientBoostingRegressor(n_estimators=150, max_depth=4, random_state=42)

        X = df_feat[FEATURES].values
        y = df_feat["quantity_sold"].values
        model.fit(X, y)
        preds    = model.predict(X)
        residuals = y - preds

        fig_res = go.Figure()
        fig_res.add_trace(go.Scatter(x=ts["date"], y=residuals, mode="markers",
                                      marker=dict(color=PALETTE["primary"], size=3, opacity=0.6),
                                      name="Residual"))
        fig_res.add_hline(y=0, line_color=PALETTE["muted"], line_dash="dash")
        fig_res.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font=dict(color=PALETTE["text"]),
                               xaxis=dict(gridcolor="#2a2a38"),
                               yaxis=dict(gridcolor="#2a2a38", title="Residual"),
                               margin=dict(l=0, r=0, t=10, b=0), height=260)
        st.plotly_chart(fig_res, use_container_width=True)

        st.markdown("<div class='section-header'>Residual Distribution</div>", unsafe_allow_html=True)
        fig_hist = go.Figure(go.Histogram(x=residuals, nbinsx=40,
                                           marker_color=PALETTE["secondary"],
                                           opacity=0.8))
        fig_hist.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                font=dict(color=PALETTE["text"]),
                                xaxis=dict(gridcolor="#2a2a38", title="Residual Value"),
                                yaxis=dict(gridcolor="#2a2a38", title="Count"),
                                margin=dict(l=0, r=0, t=10, b=0), height=250)
        st.plotly_chart(fig_hist, use_container_width=True)
