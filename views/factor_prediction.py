"""Factor-Based Prediction view for IntelliPredict.

Shows every demand-driving factor with live scores, visual breakdown,
and a multi-day factor forecast table.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from config import PALETTE
from utils import format_inr
from factor_engine import compute_factors, factor_forecast, FACTORS
from weather_api import get_weather
from data_generator import CATEGORIES, PRICE_MAP

P = PALETTE
_P_muted = P["muted"]
_P_primary = P["primary"]


def _color(direction: str) -> str:
    return {
        "positive": P["success"],
        "negative": P["danger"],
        "neutral":  P["muted"],
    }.get(direction, P["muted"])


def render_factor_prediction(df: pd.DataFrame, rest_id: str, rest_name: str):
    st.markdown("# 🧩 Factor-Based Prediction")
    st.markdown(
        f"<small style='color:{_P_muted}'>Every demand driver explained & quantified for <b>{rest_name}</b></small>",
        unsafe_allow_html=True,
    )
    st.divider()

    # ── Controls ──────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    category         = col1.selectbox("Menu Category", CATEGORIES)
    horizon          = col2.selectbox("Forecast Horizon", [7, 14, 30], index=0)
    price_multiplier = col3.slider("Price Adjustment", min_value=0.50, max_value=2.00, value=1.00, step=0.05)
    run = col4.button("🧩 Analyse Factors", use_container_width=True)

    base_price = PRICE_MAP[category]
    adj_price  = int(base_price * price_multiplier)
    col4.markdown(
        f"<small style='color:{_P_muted}'>₹{base_price} → <b style='color:{_P_primary}'>₹{adj_price}</b></small>",
        unsafe_allow_html=True,
    )

    st.divider()

    if not run:
        st.info("👆 Configure the settings above and click **Analyse Factors** to see what's driving demand today.")
        return

    # ── Get time series ───────────────────────────────────────────────────────
    ts = df[(df["restaurant_id"] == rest_id) & (df["category"] == category)].copy()
    ts = ts.sort_values("date")

    today = datetime.now()
    scores, predicted, breakdown = compute_factors(ts, today, category, price_multiplier)

    # ── Live weather box ──────────────────────────────────────────────────────
    try:
        temp, rain = get_weather()
        weather_status = f"🌧️ {temp:.0f}°C · Raining" if rain else f"☀️ {temp:.0f}°C · Clear"
        weather_color  = P["danger"] if rain else P["success"]
    except Exception:
        weather_status = "🌡️ Weather data unavailable"
        weather_color  = P["muted"]
        temp, rain     = 25, 0

    w1, w2, w3 = st.columns(3)
    w1.markdown(f"""
    <div class='kpi-card' style='border-color:{weather_color}44'>
        <div class='kpi-label'>Live Weather (Ludhiana)</div>
        <div class='kpi-value' style='color:{weather_color};font-size:1.2rem'>{weather_status}</div>
    </div>""", unsafe_allow_html=True)

    h = today.hour
    time_label = (
        "🍽️ Lunch Rush"   if 12 <= h <= 14 else
        "🌙 Dinner Rush"  if 19 <= h <= 21 else
        "☕ Breakfast"    if 7  <= h <=  9 else
        "😴 Off-Peak"
    )
    w2.markdown(f"""
    <div class='kpi-card'>
        <div class='kpi-label'>Current Time Slot</div>
        <div class='kpi-value' style='color:{P["secondary"]};font-size:1.2rem'>{time_label} ({today.strftime("%H:%M")})</div>
    </div>""", unsafe_allow_html=True)

    day_label = "Weekend 📅" if today.weekday() >= 5 else "Weekday"
    w3.markdown(f"""
    <div class='kpi-card'>
        <div class='kpi-label'>Day Type</div>
        <div class='kpi-value' style='color:{P["accent"]};font-size:1.2rem'>{day_label} · {today.strftime("%A")}</div>
    </div>""", unsafe_allow_html=True)

    st.divider()

    # ── Predicted demand hero ─────────────────────────────────────────────────
    st.markdown("<div class='section-header'>📍 Today's Factor-Adjusted Prediction</div>", unsafe_allow_html=True)

    baseline = ts.tail(30)["quantity_sold"].mean() if len(ts) > 0 else 50
    total_adj_pct = round((predicted - baseline) / max(baseline, 1) * 100, 1)
    adj_color = P["success"] if total_adj_pct >= 0 else P["danger"]

    h1, h2, h3, h4 = st.columns(4)
    for col, label, val, color in [
        (h1, "Baseline Demand",    f"{baseline:.0f} units", _P_muted),
        (h2, "Factor Adjustment",  f"{'+'if total_adj_pct>=0 else ''}{total_adj_pct}%", adj_color),
        (h3, "Predicted Demand",   f"{int(predicted)} units", _P_primary),
        (h4, "Predicted Revenue",  format_inr(int(predicted) * adj_price), P["secondary"]),
    ]:
        col.markdown(f"""
        <div class='kpi-card' style='border-color:{color}44'>
            <div class='kpi-label'>{label}</div>
            <div class='kpi-value' style='color:{color};font-size:1.5rem'>{val}</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ── Factor breakdown ──────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>🔍 Factor-by-Factor Breakdown</div>", unsafe_allow_html=True)
    st.markdown(
        f"<small style='color:{_P_muted}'>Each factor's contribution to today's predicted demand</small>",
        unsafe_allow_html=True,
    )

    for b in breakdown:
        color   = _color(b["direction"])
        bar_pct = min(100, b["bar_width"])
        sign    = "+" if b["impact_pct"] >= 0 else ""

        st.markdown(f"""
        <div style='background:#1A1A24;border:1px solid #2a2a3a;border-left:4px solid {color};
                    border-radius:10px;padding:14px 18px;margin-bottom:10px'>
            <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>
                <div style='font-size:15px;font-weight:700;color:{P["text"]}'>
                    {b["icon"]} {b["label"]}
                </div>
                <span style='background:{color}22;color:{color};border:1px solid {color}44;
                             border-radius:6px;padding:3px 12px;font-size:13px;font-weight:700'>
                    {sign}{b["impact_pct"]}%
                </span>
            </div>
            <div style='font-size:12px;color:{P["muted"]};margin-bottom:10px;line-height:1.5'>
                {b["desc"]}
            </div>
            <div style='background:#0F0F13;border-radius:4px;height:8px;overflow:hidden'>
                <div style='height:8px;width:{bar_pct}%;background:{color};
                            border-radius:4px;transition:width 0.4s'></div>
            </div>
        </div>""", unsafe_allow_html=True)

    # ── Factor waterfall chart ────────────────────────────────────────────────
    st.divider()
    st.markdown("<div class='section-header'>📊 Factor Waterfall Chart</div>", unsafe_allow_html=True)

    labels   = [b["label"] for b in breakdown] + ["Predicted Total"]
    values   = [b["score"] * baseline for b in breakdown] + [0]
    measures = ["relative"] * len(breakdown) + ["total"]
    colors_wf = [_color(b["direction"]) for b in breakdown] + [P["primary"]]

    fig_wf = go.Figure(go.Waterfall(
        orientation="v",
        measure=measures,
        x=labels,
        y=[b["score"] * baseline for b in breakdown] + [predicted],
        connector=dict(line=dict(color=P["muted"], width=1, dash="dot")),
        increasing=dict(marker_color=P["success"]),
        decreasing=dict(marker_color=P["danger"]),
        totals=dict(marker_color=P["primary"]),
    ))
    fig_wf.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=P["text"]),
        xaxis=dict(gridcolor="#2a2a38", tickangle=-30),
        yaxis=dict(gridcolor="#2a2a38", title="Demand Units"),
        margin=dict(l=0, r=0, t=10, b=0), height=320,
    )
    st.plotly_chart(fig_wf, use_container_width=True)

    st.divider()

    # ── Multi-day factor forecast ─────────────────────────────────────────────
    st.markdown("<div class='section-header'>📅 Multi-Day Factor Forecast</div>", unsafe_allow_html=True)
    st.markdown(
        f"<small style='color:{_P_muted}'>Factor-adjusted predictions for next {horizon} days</small>",
        unsafe_allow_html=True,
    )

    with st.spinner("Computing factor-based forecast…"):
        fc_df = factor_forecast(ts, horizon, category, price_multiplier)

    # Forecast line chart
    fig_fc = go.Figure()
    fig_fc.add_trace(go.Scatter(
        x=fc_df["date"], y=fc_df["upper"],
        mode="lines", line=dict(color="rgba(0,0,0,0)"),
        showlegend=False, name="Upper CI",
    ))
    fig_fc.add_trace(go.Scatter(
        x=fc_df["date"], y=fc_df["lower"],
        fill="tonexty", fillcolor="rgba(255,107,53,0.15)",
        mode="lines", line=dict(color="rgba(0,0,0,0)"),
        name="Confidence Band",
    ))
    fig_fc.add_trace(go.Scatter(
        x=fc_df["date"], y=fc_df["predicted"],
        mode="lines+markers",
        line=dict(color=P["primary"], width=2.5),
        marker=dict(size=5, color=P["primary"]),
        name="Factor Forecast",
    ))
    fig_fc.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=P["text"]),
        xaxis=dict(gridcolor="#2a2a38"),
        yaxis=dict(gridcolor="#2a2a38", title="Units"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=0, r=0, t=10, b=0), height=260,
    )
    st.plotly_chart(fig_fc, use_container_width=True)

    # Forecast table
    display_df = fc_df.copy()
    display_df.columns = ["Date", "Day", "Predicted", "Lower", "Upper", "Top Factor", "Confidence %"]
    st.dataframe(display_df.set_index("Date"), use_container_width=True)

    csv = fc_df.to_csv(index=False).encode()
    st.download_button(
        "⬇️ Download Factor Forecast CSV", csv,
        file_name=f"factor_forecast_{rest_id}_{category}_{horizon}d.csv",
        mime="text/csv",
    )

    st.divider()

    # ── Price elasticity simulator ────────────────────────────────────────────
    st.markdown("<div class='section-header'>💸 Price Elasticity Simulator</div>", unsafe_allow_html=True)
    elasticity = -0.4
    price_range = [p / 100 for p in range(50, 201, 10)]
    sim_rows = []
    for pm in price_range:
        adj_d = max(5, baseline * (1 + elasticity * (pm - 1)))
        adj_r = adj_d * base_price * pm
        sim_rows.append({"Price Mult": pm, "Price": int(base_price * pm),
                         "Demand": int(adj_d), "Revenue": int(adj_r)})
    sim_df = pd.DataFrame(sim_rows)

    fig_el = go.Figure()
    fig_el.add_trace(go.Scatter(
        x=sim_df["Price"], y=sim_df["Revenue"],
        mode="lines+markers",
        line=dict(color=P["secondary"], width=2.5),
        name="Revenue",
        yaxis="y2",
    ))
    fig_el.add_trace(go.Bar(
        x=sim_df["Price"], y=sim_df["Demand"],
        marker_color=P["primary"],
        name="Demand",
        opacity=0.7,
    ))
    fig_el.add_vline(
        x=adj_price,
        line_dash="dash", line_color=P["success"],
        annotation_text=f"Current ₹{adj_price}",
        annotation_font_color=P["success"],
    )
    fig_el.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=P["text"]),
        xaxis=dict(gridcolor="#2a2a38", title="Price (₹)"),
        yaxis=dict(gridcolor="#2a2a38", title="Demand Units"),
        yaxis2=dict(overlaying="y", side="right", title="Revenue (₹)", showgrid=False),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=0, r=0, t=10, b=0), height=300,
        barmode="overlay",
    )
    st.plotly_chart(fig_el, use_container_width=True)
