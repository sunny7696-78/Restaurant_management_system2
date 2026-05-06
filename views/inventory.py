"""Inventory and waste view component for IntelliPredict."""

import streamlit as st
import pandas as pd
from data_generator import generate_inventory_snapshot
from utils import waste_stock_chart, format_inr, PALETTE
import plotly.graph_objects as go

def render_inventory(df: pd.DataFrame, rest_id: str, rest_name: str):
    """Renders the inventory and waste optimization page.
    
    Args:
        df: The full restaurant dataset.
        rest_id: Selected restaurant ID.
        rest_name: Selected restaurant name.
    """
    st.markdown("# 📦 Inventory & Waste Optimization")
    st.markdown(f"<small style='color:#8A8696'>WasteZero recommendations for {rest_name}</small>", unsafe_allow_html=True)
    st.divider()

    snapshot = generate_inventory_snapshot(df, rest_id)

    st.markdown("<div class='section-header'>Stock Risk Assessment</div>", unsafe_allow_html=True)
    for _, row in snapshot.iterrows():
        risk_class = "risk-critical" if "Critical" in row["risk"] else ("risk-low" if "Low" in row["risk"] else "risk-healthy")
        c1, c2, c3, c4, c5 = st.columns([2, 1.5, 1.5, 1.5, 2])
        c1.markdown(f"**{row['category']}**")
        c2.metric("Avg Daily Demand", f"{row['avg_daily_demand']:.0f}")
        c3.metric("Current Stock",    f"{row['current_stock']:.0f}")
        c4.metric("Days Coverage",    f"{row['days_of_stock']:.1f}")
        c5.markdown(f"<span class='{risk_class}'>{row['risk']}</span>", unsafe_allow_html=True)
        st.divider()

    st.markdown("<div class='section-header'>Stock vs Daily Demand</div>", unsafe_allow_html=True)
    fig = waste_stock_chart(snapshot)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("<div class='section-header'>Reorder Recommendations</div>", unsafe_allow_html=True)
    reorder = snapshot[snapshot["reorder_qty"] > 0][["category", "reorder_qty", "avg_waste_kg"]].copy()
    reorder.columns = ["Category", "Suggested Reorder Qty", "Avg Daily Waste (kg)"]
    reorder["Est. Waste Cost Saving (₹)"] = (
        reorder["Avg Daily Waste (kg)"] * 7 * 200
    ).round(0).astype(int)
    st.dataframe(reorder.set_index("Category"), use_container_width=True)

    total_saving = reorder["Est. Waste Cost Saving (₹)"].sum()
    st.markdown(f"""
    <div class='kpi-card' style='max-width:300px;margin-top:12px'>
        <div class='kpi-label'>Potential Weekly Waste Saving</div>
        <div class='kpi-value'>{format_inr(total_saving)}</div>
        <div class='kpi-delta'>By optimising reorder quantities</div>
    </div>""", unsafe_allow_html=True)

    st.markdown("<div class='section-header'>Waste Trend (Last 60 Days)</div>", unsafe_allow_html=True)
    rest_df = df[df["restaurant_id"] == rest_id].copy()
    waste_trend = rest_df.groupby("date")["waste_kg"].sum().reset_index().tail(60)
    fig_w = go.Figure(go.Scatter(
        x=waste_trend["date"], y=waste_trend["waste_kg"],
        fill="tozeroy", fillcolor="rgba(230,57,70,0.12)",
        line=dict(color=PALETTE["danger"], width=2),
    ))
    fig_w.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color=PALETTE["text"]),
                        xaxis=dict(gridcolor="#2a2a38"),
                        yaxis=dict(gridcolor="#2a2a38", title="Waste (kg)"),
                        margin=dict(l=0, r=0, t=10, b=0), height=250)
    st.plotly_chart(fig_w, use_container_width=True)
