"""Weather and events view component for IntelliPredict."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from data_generator import CATEGORIES, get_time_series
from utils import weather_demand_heatmap, PALETTE
from weather_api import get_forecast

def render_weather(df: pd.DataFrame, rest_id: str, rest_name: str):
    """Renders the weather and event impact page.
    
    Args:
        df: The full restaurant dataset.
        rest_id: Selected restaurant ID.
        rest_name: Selected restaurant name.
    """
    st.markdown("# 🌦️ Weather & Event Impact")
    st.markdown(f"<small style='color:#8A8696'>How external factors affect demand at {rest_name}</small>", unsafe_allow_html=True)
    
    # Real-time Forecast Section
    raw_weather = get_forecast()
    if raw_weather:
        st.markdown("<div class='section-header'>Real-Time 5-Day Forecast</div>", unsafe_allow_html=True)
        w_df = pd.DataFrame(raw_weather)
        w_df["date"] = pd.to_datetime(w_df["datetime"])
        daily = w_df.groupby(w_df["date"].dt.date).agg({"temp": "mean", "rain": "max"}).reset_index()
        
        cols = st.columns(min(len(daily), 6))
        for i, (idx, row) in enumerate(daily.iterrows()):
            if i < len(cols):
                with cols[i]:
                    date_str = row["date"].strftime("%a, %b %d")
                    icon = "🌧️" if row["rain"] > 0 else "☀️"
                    st.markdown(f"""
                    <div style='background:rgba(255,255,255,0.05); padding:10px; border-radius:10px; text-align:center; border:1px solid rgba(255,255,255,0.1)'>
                        <div style='font-size:0.8rem; color:#8A8696'>{date_str}</div>
                        <div style='font-size:1.5rem; margin:5px 0'>{icon}</div>
                        <div style='font-size:1.1rem; font-weight:bold; color:{PALETTE["primary"]}'>{row["temp"]:.1f}°C</div>
                    </div>
                    """, unsafe_allow_html=True)
        st.divider()

    st.divider()

    rest_df  = df[df["restaurant_id"] == rest_id].copy()
    category = st.selectbox("Category", CATEGORIES)
    ts = get_time_series(df, rest_id, category)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='section-header'>Temperature vs Demand</div>", unsafe_allow_html=True)
        fig_t = px.scatter(ts, x="temperature", y="quantity_sold", color="is_weekend",
                           color_discrete_map={0: PALETTE["primary"], 1: PALETTE["secondary"]},
                           trendline="lowess", labels={"is_weekend": "Weekend"})
        fig_t.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color=PALETTE["text"]),
                            xaxis=dict(gridcolor="#2a2a38"),
                            yaxis=dict(gridcolor="#2a2a38"),
                            margin=dict(l=0, r=0, t=10, b=0), height=300,
                            legend=dict(bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig_t, use_container_width=True)

    with c2:
        st.markdown("<div class='section-header'>Rainfall vs Demand</div>", unsafe_allow_html=True)
        fig_r = px.scatter(ts, x="rainfall_mm", y="quantity_sold",
                           color_discrete_sequence=[PALETTE["success"]], trendline="lowess")
        fig_r.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color=PALETTE["text"]),
                            xaxis=dict(gridcolor="#2a2a38"),
                            yaxis=dict(gridcolor="#2a2a38"),
                            margin=dict(l=0, r=0, t=10, b=0), height=300)
        st.plotly_chart(fig_r, use_container_width=True)

    st.markdown("<div class='section-header'>Weather × Demand Heatmap</div>", unsafe_allow_html=True)
    fig_h = weather_demand_heatmap(ts)
    st.plotly_chart(fig_h, use_container_width=True)

    st.markdown("<div class='section-header'>Festival vs Normal Demand</div>", unsafe_allow_html=True)
    fest_avg   = ts[ts["is_festival"] == 1]["quantity_sold"].mean()
    normal_avg = ts[ts["is_festival"] == 0]["quantity_sold"].mean()
    weekend_avg= ts[ts["is_weekend"]  == 1]["quantity_sold"].mean()

    fig_bar = go.Figure(go.Bar(
        x=["Normal Day", "Weekend", "Festival Day"],
        y=[normal_avg, weekend_avg, fest_avg],
        marker_color=[PALETTE["muted"], PALETTE["secondary"], PALETTE["primary"]],
        text=[f"{v:.0f}" for v in [normal_avg, weekend_avg, fest_avg]],
        textposition="outside",
    ))
    fig_bar.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font=dict(color=PALETTE["text"]),
                          yaxis=dict(gridcolor="#2a2a38", title="Avg Demand"),
                          xaxis=dict(gridcolor="rgba(0,0,0,0)"),
                          margin=dict(l=0, r=0, t=10, b=0), height=280)
    st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("<div class='section-header'>Day-of-Week Demand Pattern</div>", unsafe_allow_html=True)
    dow = ts.groupby("day_of_week")["quantity_sold"].mean().reset_index()
    dow["day_name"] = dow["day_of_week"].map({0:"Mon",1:"Tue",2:"Wed",3:"Thu",4:"Fri",5:"Sat",6:"Sun"})
    fig_dow = go.Figure(go.Bar(
        x=dow["day_name"], y=dow["quantity_sold"],
        marker_color=[PALETTE["primary"] if d >= 5 else PALETTE["muted"] for d in dow["day_of_week"]],
    ))
    fig_dow.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font=dict(color=PALETTE["text"]),
                          yaxis=dict(gridcolor="#2a2a38", title="Avg Demand"),
                          xaxis=dict(gridcolor="rgba(0,0,0,0)"),
                          margin=dict(l=0, r=0, t=10, b=0), height=260)
    st.plotly_chart(fig_dow, use_container_width=True)
