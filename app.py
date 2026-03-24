"""
AI-Powered IntelliPredict
Real-Time Restaurant Demand Forecasting & WasteZero Optimization Platform
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

from data_generator import (
    generate_dataset, get_time_series,
    generate_inventory_snapshot, RESTAURANTS, CATEGORIES, PRICE_MAP,
)
from models import (
    prophet_forecast, xgboost_forecast, lstm_forecast, ensemble_forecast,
    PROPHET_AVAILABLE, XGB_AVAILABLE, TF_AVAILABLE,
)
from utils import (
    PALETTE, forecast_chart, historical_trend_chart, category_bar_chart,
    waste_stock_chart, weather_demand_heatmap, feature_importance_chart,
    revenue_forecast_chart, model_comparison_df, format_inr,
)

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="IntelliPredict — Restaurant AI",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown("""
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
""", unsafe_allow_html=True)

# ── Data loading (cached) ─────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_data():
    return generate_dataset()


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🍽️ IntelliPredict")
    st.markdown("<small style='color:#8A8696'>Restaurant AI Platform</small>", unsafe_allow_html=True)
    st.divider()

    PAGE = st.radio(
        "Navigate",
        ["🏠 Dashboard", "📈 Demand Forecast", "📦 Inventory & Waste",
         "🌦️ Weather & Events", "💰 Revenue Optimizer", "🔬 Model Lab"],
        label_visibility="collapsed",
    )

    st.divider()
    rest_name = st.selectbox("🏪 Restaurant", list(RESTAURANTS.values()))
    rest_id   = [k for k, v in RESTAURANTS.items() if v == rest_name][0]

    st.divider()
    st.markdown("<small style='color:#8A8696'>Model Availability</small>", unsafe_allow_html=True)
    st.markdown(f"{'✅' if PROPHET_AVAILABLE else '⚠️'} Prophet")
    st.markdown(f"{'✅' if XGB_AVAILABLE    else '⚠️'} XGBoost")
    st.markdown(f"{'✅' if TF_AVAILABLE     else '⚠️'} LSTM / TensorFlow")

with st.spinner("Loading data…"):
    df = load_data()

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

if PAGE == "🏠 Dashboard":
    st.markdown("# 🍽️ IntelliPredict Dashboard")
    st.markdown(f"<small style='color:#8A8696'>Showing data for **{rest_name}** · Powered by LSTM + XGBoost + Prophet Ensemble</small>", unsafe_allow_html=True)
    st.divider()

    rest_df   = df[df["restaurant_id"] == rest_id]
    today_df  = rest_df[rest_df["date"] == rest_df["date"].max()]
    last7     = rest_df[rest_df["date"] >= rest_df["date"].max() - pd.Timedelta(days=7)]
    prev7     = rest_df[(rest_df["date"] >= rest_df["date"].max() - pd.Timedelta(days=14)) &
                        (rest_df["date"] <  rest_df["date"].max() - pd.Timedelta(days=7))]

    total_today   = int(today_df["quantity_sold"].sum())
    total_waste   = round(last7["waste_kg"].sum(), 1)
    total_revenue = last7["revenue"].sum()
    avg_stock_cov = (last7["stock_level"].mean() / last7["quantity_sold"].mean()) if last7["quantity_sold"].mean() > 0 else 0

    d_demand  = int(last7["quantity_sold"].sum() - prev7["quantity_sold"].sum())
    d_waste   = round(last7["waste_kg"].sum()    - prev7["waste_kg"].sum(), 1)
    d_revenue = last7["revenue"].sum()           - prev7["revenue"].sum()

    c1, c2, c3, c4 = st.columns(4)
    for col, label, val, delta in [
        (c1, "Today's Demand", f"{total_today:,} units", f"{'▲' if d_demand>0 else '▼'} {abs(d_demand)} vs last week"),
        (c2, "Waste (7 days)",  f"{total_waste} kg",      f"{'▲' if d_waste>0 else '▼'} {abs(d_waste)} kg vs last week"),
        (c3, "Revenue (7 days)",format_inr(total_revenue), f"{'▲' if d_revenue>0 else '▼'} {format_inr(abs(d_revenue))} vs last week"),
        (c4, "Stock Coverage",  f"{avg_stock_cov:.1f}x",   "Avg stock/demand ratio"),
    ]:
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


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — DEMAND FORECAST
# ═══════════════════════════════════════════════════════════════════════════════

elif PAGE == "📈 Demand Forecast":
    st.markdown("# 📈 Demand Forecasting")
    st.markdown(f"<small style='color:#8A8696'>Multi-model forecasting for {rest_name}</small>", unsafe_allow_html=True)
    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        category = st.selectbox("Menu Category", CATEGORIES)
    with col2:
        horizon  = st.selectbox("Forecast Horizon", [7, 14, 30], index=1)
    with col3:
        model_choice = st.selectbox("Model", ["Ensemble", "Prophet", "XGBoost", "LSTM"])

    run = st.button("🚀 Run Forecast", use_container_width=True)

    if run:
        ts = get_time_series(df, rest_id, category)
        with st.spinner(f"Training {model_choice} model…"):
            if model_choice == "Prophet":
                forecast, metrics = prophet_forecast(ts, horizon)
                feat_imp = None
                all_results = {}
            elif model_choice == "XGBoost":
                forecast, metrics, feat_imp = xgboost_forecast(ts, horizon)
                all_results = {}
            elif model_choice == "LSTM":
                forecast, metrics = lstm_forecast(ts, horizon)
                feat_imp = None
                all_results = {}
            else:  # Ensemble
                forecast, metrics, all_results, feat_imp = ensemble_forecast(ts, horizon)

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
            st.markdown("<div class='section-header'>Feature Importance</div>", unsafe_allow_html=True)
            fig_fi = feature_importance_chart(feat_imp)
            st.plotly_chart(fig_fi, use_container_width=True)

        st.markdown("<div class='section-header'>Forecast Table</div>", unsafe_allow_html=True)
        display_fc = forecast.copy()
        display_fc["date"] = display_fc["date"].dt.strftime("%Y-%m-%d")
        st.dataframe(display_fc, use_container_width=True)

        csv = forecast.to_csv(index=False).encode()
        st.download_button("⬇️ Download Forecast CSV", csv,
                           file_name=f"forecast_{rest_id}_{category}_{horizon}d.csv",
                           mime="text/csv")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — INVENTORY & WASTE
# ═══════════════════════════════════════════════════════════════════════════════

elif PAGE == "📦 Inventory & Waste":
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


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — WEATHER & EVENTS
# ═══════════════════════════════════════════════════════════════════════════════

elif PAGE == "🌦️ Weather & Events":
    st.markdown("# 🌦️ Weather & Event Impact")
    st.markdown(f"<small style='color:#8A8696'>How external factors affect demand at {rest_name}</small>", unsafe_allow_html=True)
    st.divider()

    rest_df  = df[df["restaurant_id"] == rest_id].copy()
    category = st.selectbox("Category", CATEGORIES)
    ts = get_time_series(df, rest_id, category)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='section-header'>Temperature vs Demand</div>", unsafe_allow_html=True)
        fig_t = px.scatter(ts, x="temperature", y="quantity_sold", color="is_weekend",
                           color_discrete_map={0: PALETTE["primary"], 1: PALETTE["secondary"]},
                           trendline="ols", labels={"is_weekend": "Weekend"})
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
                           color_discrete_sequence=[PALETTE["success"]], trendline="ols")
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


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — REVENUE OPTIMIZER
# ═══════════════════════════════════════════════════════════════════════════════

elif PAGE == "💰 Revenue Optimizer":
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


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 6 — MODEL LAB
# ═══════════════════════════════════════════════════════════════════════════════

elif PAGE == "🔬 Model Lab":
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
        from models import build_features
        df_feat, FEATURES = build_features(ts)
        from sklearn.ensemble import GradientBoostingRegressor
        try:
            import xgboost as xgb
            model = xgb.XGBRegressor(n_estimators=200, max_depth=5, learning_rate=0.08,
                                      subsample=0.8, random_state=42, verbosity=0)
        except ImportError:
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
