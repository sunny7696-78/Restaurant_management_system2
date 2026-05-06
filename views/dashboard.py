"""Dashboard view component for IntelliPredict."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from config import PALETTE
from utils import format_inr

def render_dashboard(df: pd.DataFrame, rest_id: str, rest_name: str):
    """Renders the main dashboard page.
    
    Args:
        df: The full restaurant dataset.
        rest_id: Selected restaurant ID.
        rest_name: Selected restaurant name.
    """
    st.markdown("# 🍽️ IntelliPredict Dashboard")
    st.markdown(
        f"<small style='color:#8A8696'>Showing data for **{rest_name}** · "
        "Powered by LSTM + XGBoost + Prophet Ensemble</small>", 
        unsafe_allow_html=True
    )
    st.divider()

    rest_df = df[df["restaurant_id"] == rest_id]
    today_df = rest_df[rest_df["date"] == rest_df["date"].max()]
    last7 = rest_df[rest_df["date"] >= rest_df["date"].max() - pd.Timedelta(days=7)]
    prev7 = rest_df[(rest_df["date"] >= rest_df["date"].max() - pd.Timedelta(days=14)) &
                    (rest_df["date"] <  rest_df["date"].max() - pd.Timedelta(days=7))]

    total_today = int(today_df["quantity_sold"].sum())
    total_waste = round(last7["waste_kg"].sum(), 1)
    total_revenue = last7["revenue"].sum()
    avg_stock_cov = (last7["stock_level"].mean() / last7["quantity_sold"].mean()) if last7["quantity_sold"].mean() > 0 else 0

    d_demand = int(last7["quantity_sold"].sum() - prev7["quantity_sold"].sum())
    d_waste = round(last7["waste_kg"].sum() - prev7["waste_kg"].sum(), 1)
    d_revenue = last7["revenue"].sum() - prev7["revenue"].sum()

    c1, c2, c3, c4 = st.columns(4)
    kpis = [
        (c1, "Today's Demand", f"{total_today:,} units", f"{'▲' if d_demand>0 else '▼'} {abs(d_demand)} vs last week"),
        (c2, "Waste (7 days)", f"{total_waste} kg", f"{'▲' if d_waste>0 else '▼'} {abs(d_waste)} kg vs last week"),
        (c3, "Revenue (7 days)", format_inr(total_revenue), f"{'▲' if d_revenue>0 else '▼'} {format_inr(abs(d_revenue))} vs last week"),
        (c4, "Stock Coverage", f"{avg_stock_cov:.1f}x", "Avg stock/demand ratio"),
    ]
    
    for col, label, val, delta in kpis:
        col.markdown(f"""
        <div class='kpi-card'>
            <div class='kpi-label'>{label}</div>
            <div class='kpi-value'>{val}</div>
            <div class='kpi-delta'>{delta}</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.markdown("<div class='section-header'>Demand Trend — Last 90 Days</div>", unsafe_allow_html=True)
        agg = rest_df.groupby("date")["quantity_sold"].sum().reset_index()
        fig = go.Figure(go.Scatter(
            x=agg["date"], y=agg["quantity_sold"],
            fill="tozeroy", fillcolor="rgba(255,107,53,0.10)",
            line=dict(color=PALETTE["primary"], width=2.2),
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=PALETTE["text"]),
            xaxis=dict(gridcolor="#2a2a38", showgrid=True),
            yaxis=dict(gridcolor="#2a2a38", showgrid=True),
            margin=dict(l=0, r=0, t=10, b=0), height=280,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.markdown("<div class='section-header'>Demand by Category</div>", unsafe_allow_html=True)
        cat_df = rest_df.groupby("category")["quantity_sold"].sum().reset_index()
        fig2 = px.pie(cat_df, names="category", values="quantity_sold",
                      color_discrete_sequence=[PALETTE["primary"], PALETTE["secondary"],
                                               PALETTE["accent"], PALETTE["success"]],
                      hole=0.45)
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", font=dict(color=PALETTE["text"]),
                           margin=dict(l=0, r=0, t=0, b=0), height=280,
                           legend=dict(bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.markdown("<div class='section-header'>Monthly Revenue Breakdown</div>", unsafe_allow_html=True)
    monthly = rest_df.copy()
    monthly["month_label"] = monthly["date"].dt.strftime("%b %Y")
    monthly = monthly.groupby(["month_label","category"])["revenue"].sum().reset_index()
    fig3 = px.bar(monthly, x="month_label", y="revenue", color="category",
                  color_discrete_sequence=[PALETTE["primary"], PALETTE["secondary"],
                                           PALETTE["accent"], PALETTE["success"]])
    fig3.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                       font=dict(color=PALETTE["text"]),
                       xaxis=dict(gridcolor="#2a2a38", tickangle=-45),
                       yaxis=dict(gridcolor="#2a2a38"),
                       legend=dict(bgcolor="rgba(0,0,0,0)"),
                       margin=dict(l=0, r=0, t=10, b=0), height=300)
    st.plotly_chart(fig3, use_container_width=True)
