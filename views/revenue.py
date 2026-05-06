"""Revenue optimizer view component for IntelliPredict."""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from data_generator import CATEGORIES, PRICE_MAP, get_time_series
from models import xgboost_forecast
from utils import format_inr, PALETTE

def render_revenue(df: pd.DataFrame, rest_id: str, rest_name: str):
    """Renders the revenue optimization page.
    
    Args:
        df: The full restaurant dataset.
        rest_id: Selected restaurant ID.
        rest_name: Selected restaurant name.
    """
    st.markdown("# 💰 Revenue Optimization")
    st.markdown(f"<small style='color:#8A8696'>Price elasticity & revenue simulation for {rest_name}</small>", unsafe_allow_html=True)
    st.divider()

    category = st.selectbox("Category", CATEGORIES)
    base_price = PRICE_MAP[category]

    col1, col2 = st.columns(2)
    with col1:
        horizon = st.selectbox("Forecast Horizon (days)", [7, 14, 30], index=1)
    with col2:
        price_multiplier = st.slider("Price Adjustment", 0.5, 2.0, 1.0, 0.05,
                                     format="%.2fx  (₹%.0f per unit)")

    run_rev = st.button("💡 Simulate Revenue", use_container_width=True)

    if run_rev:
        ts = get_time_series(df, rest_id, category)
        with st.spinner("Running forecast…"):
            forecast, metrics, feat_imp = xgboost_forecast(ts, horizon)

        adj_price = base_price * price_multiplier
        # Simple price elasticity: higher price → lower demand
        elasticity = -0.4
        demand_adj = forecast.copy()
        demand_adj["predicted"] = (
            demand_adj["predicted"] * (1 + elasticity * (price_multiplier - 1))
        ).clip(lower=1).round().astype(int)

        demand_adj["revenue"]      = demand_adj["predicted"] * adj_price
        demand_adj["revenue_base"] = forecast["predicted"]   * base_price
        demand_adj["profit_margin"]= demand_adj["revenue"] * 0.35

        total_rev  = demand_adj["revenue"].sum()
        base_rev   = demand_adj["revenue_base"].sum()
        delta_rev  = total_rev - base_rev

        c1, c2, c3 = st.columns(3)
        for col, label, val in [
            (c1, "Projected Revenue", format_inr(total_rev)),
            (c2, "Base Revenue",      format_inr(base_rev)),
            (c3, "Revenue Delta",     f"{'▲' if delta_rev>0 else '▼'} {format_inr(abs(delta_rev))}"),
        ]:
            col.markdown(f"""
            <div class='kpi-card'>
                <div class='kpi-label'>{label}</div>
                <div class='kpi-value'>{val}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<div class='section-header'>Revenue Forecast at Adjusted Price</div>", unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=demand_adj["date"], y=demand_adj["revenue_base"],
                                  name="Base Revenue", line=dict(color=PALETTE["muted"], dash="dot", width=1.5)))
        fig.add_trace(go.Scatter(x=demand_adj["date"], y=demand_adj["revenue"],
                                  name="Adjusted Revenue", fill="tozeroy",
                                  fillcolor="rgba(255,159,28,0.12)",
                                  line=dict(color=PALETTE["secondary"], width=2.5)))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font=dict(color=PALETTE["text"]),
                          xaxis=dict(gridcolor="#2a2a38"),
                          yaxis=dict(gridcolor="#2a2a38", title="Revenue (₹)"),
                          legend=dict(bgcolor="rgba(0,0,0,0)"),
                          margin=dict(l=0, r=0, t=10, b=0), height=300)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("<div class='section-header'>Optimal Pricing Summary</div>", unsafe_allow_html=True)
        st.markdown(f"""
        | | Base | Adjusted |
        |---|---|---|
        | Price per Unit | ₹{base_price} | ₹{adj_price:.0f} |
        | Avg Daily Demand | {forecast['predicted'].mean():.0f} | {demand_adj['predicted'].mean():.0f} |
        | Total Revenue | {format_inr(base_rev)} | {format_inr(total_rev)} |
        | Est. Profit (35%) | {format_inr(base_rev*0.35)} | {format_inr(total_rev*0.35)} |
        """)

        st.markdown("<div class='section-header'>Price vs Revenue Trade-off</div>", unsafe_allow_html=True)
        multipliers = np.arange(0.5, 2.05, 0.05)
        revenues    = []
        for m in multipliers:
            d = forecast["predicted"].mean() * (1 + elasticity * (m - 1))
            revenues.append(max(0, d) * base_price * m)
        fig2 = go.Figure(go.Scatter(
            x=multipliers * base_price, y=revenues,
            line=dict(color=PALETTE["primary"], width=2.5),
        ))
        fig2.add_vline(x=adj_price, line_color=PALETTE["secondary"], line_dash="dash")
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                           font=dict(color=PALETTE["text"]),
                           xaxis=dict(gridcolor="#2a2a38", title="Price (₹)"),
                           yaxis=dict(gridcolor="#2a2a38", title="Expected Revenue (₹/day)"),
                           margin=dict(l=0, r=0, t=10, b=0), height=280)
        st.plotly_chart(fig2, use_container_width=True)
