"""Dashboard view — with real-time live orders panel."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from config import PALETTE
from utils import format_inr
from realtime_engine import init_live_store, generate_live_tick, push_tick, get_live_store

P = PALETTE
_P_accent = P["accent"]
_P_muted = P["muted"]
_P_primary = P["primary"]
_P_success = P["success"]   # shorthand

def render_dashboard(df: pd.DataFrame, rest_id: str, rest_name: str):
    st.markdown("# 🍽️ IntelliPredict Dashboard")
    st.markdown(
        f"<small style='color:{_P_muted}'>Showing data for <b>{rest_name}</b> · "
        "LSTM + XGBoost + Prophet Ensemble</small>",
        unsafe_allow_html=True,
    )
    st.divider()

    # ── Static KPIs ───────────────────────────────────────────────────────────
    rest_df  = df[df["restaurant_id"] == rest_id]
    today_df = rest_df[rest_df["date"] == rest_df["date"].max()]
    last7    = rest_df[rest_df["date"] >= rest_df["date"].max() - pd.Timedelta(days=7)]
    prev7    = rest_df[
        (rest_df["date"] >= rest_df["date"].max() - pd.Timedelta(days=14)) &
        (rest_df["date"] <  rest_df["date"].max() - pd.Timedelta(days=7))
    ]

    total_today   = int(today_df["quantity_sold"].sum())
    total_waste   = round(last7["waste_kg"].sum(), 1)
    total_revenue = last7["revenue"].sum()
    avg_stock_cov = (
        last7["stock_level"].mean() / last7["quantity_sold"].mean()
        if last7["quantity_sold"].mean() > 0 else 0
    )
    d_demand  = int(last7["quantity_sold"].sum() - prev7["quantity_sold"].sum())
    d_waste   = round(last7["waste_kg"].sum() - prev7["waste_kg"].sum(), 1)
    d_revenue = last7["revenue"].sum() - prev7["revenue"].sum()

    c1, c2, c3, c4 = st.columns(4)
    for col, label, val, delta in [
        (c1, "Today's Demand (Historical)", f"{total_today:,} units",
             f"{'▲' if d_demand>0 else '▼'} {abs(d_demand)} vs last wk"),
        (c2, "Waste (7 days)",   f"{total_waste} kg",
             f"{'▲' if d_waste>0 else '▼'} {abs(d_waste)} kg vs last wk"),
        (c3, "Revenue (7 days)", format_inr(total_revenue),
             f"{'▲' if d_revenue>0 else '▼'} {format_inr(abs(d_revenue))} vs last wk"),
        (c4, "Stock Coverage",   f"{avg_stock_cov:.1f}x", "Avg stock/demand ratio"),
    ]:
        col.markdown(f"""
        <div class='kpi-card'>
            <div class='kpi-label'>{label}</div>
            <div class='kpi-value'>{val}</div>
            <div class='kpi-delta'>{delta}</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ── REAL-TIME LIVE ORDERS ─────────────────────────────────────────────────
    st.markdown("<div class='section-header'>⚡ Real-Time Live Orders</div>", unsafe_allow_html=True)
    st.markdown(
        f"<small style='color:{_P_muted}'>Simulated live order stream with weather & hour-of-day factors</small>",
        unsafe_allow_html=True,
    )

    init_live_store(rest_id)
    store = get_live_store(rest_id)

    # Controls
    ctrl1, ctrl2, ctrl3 = st.columns([1, 1, 2])
    tick_btn    = ctrl1.button("🔄 Fetch Live Tick", use_container_width=True)
    reset_btn   = ctrl2.button("🗑️ Reset Today", use_container_width=True)
    auto_label  = "⏸ Stop Auto-refresh" if st.session_state.get("auto_refresh") else "▶ Auto-refresh (5s)"
    auto_btn    = ctrl3.button(auto_label, use_container_width=True)

    if tick_btn:
        tick = generate_live_tick(rest_id)
        push_tick(rest_id, tick)
        store = get_live_store(rest_id)

    if reset_btn:
        if f"live_{rest_id}" in st.session_state:
            del st.session_state[f"live_{rest_id}"]
        init_live_store(rest_id)
        store = get_live_store(rest_id)

    if auto_btn:
        st.session_state["auto_refresh"] = not st.session_state.get("auto_refresh", False)

    if st.session_state.get("auto_refresh"):
        tick = generate_live_tick(rest_id)
        push_tick(rest_id, tick)
        store = get_live_store(rest_id)
        st.success(f"● Live — Last tick at {store.get('last_tick','–')} · Auto-refreshing…")
        st.rerun()

    # Live KPI row
    lk1, lk2, lk3, lk4 = st.columns(4)
    live_rev = store.get("revenue_today", 0)
    live_qty = store.get("qty_today", 0)
    ticks    = store.get("ticks", [])
    last_tick_qty = ticks[-1]["qty"] if ticks else 0

    for col, label, val, color in [
        (lk1, "Live Orders Today",   f"{live_qty:,} units",          _P_primary),
        (lk2, "Live Revenue Today",  format_inr(live_rev),           P["secondary"]),
        (lk3, "Orders Last Tick",    f"{last_tick_qty} units",        _P_success),
        (lk4, "Ticks Recorded",      f"{len(ticks)}",                 _P_accent),
    ]:
        col.markdown(f"""
        <div class='kpi-card' style='border-color:{color}44'>
            <div class='kpi-label'>{label}</div>
            <div class='kpi-value' style='color:{color}'>{val}</div>
        </div>""", unsafe_allow_html=True)

    # Live order stream chart
    if ticks:
        tick_df = pd.DataFrame(ticks)
        fig_live = go.Figure(go.Bar(
            x=tick_df["time"],
            y=tick_df["qty"],
            marker_color=P["primary"],
            name="Orders/tick",
        ))
        fig_live.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=P["text"]),
            xaxis=dict(gridcolor="#2a2a38", title="Tick Time"),
            yaxis=dict(gridcolor="#2a2a38", title="Orders"),
            margin=dict(l=0, r=0, t=10, b=0), height=200,
        )
        st.plotly_chart(fig_live, use_container_width=True)

        # Category breakdown live
        cat_totals = store.get("category_totals", {})
        if any(v > 0 for v in cat_totals.values()):
            cat_df = pd.DataFrame(
                [{"category": k, "qty": v} for k, v in cat_totals.items() if v > 0]
            )
            col_a, col_b = st.columns([1, 2])
            with col_a:
                st.markdown(f"<small style='color:{_P_muted}'>Live category mix</small>", unsafe_allow_html=True)
                fig_pie = px.pie(
                    cat_df, names="category", values="qty",
                    color_discrete_sequence=[P["primary"], P["secondary"], P["success"], P["accent"]],
                    hole=0.5,
                )
                fig_pie.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", font=dict(color=P["text"]),
                    margin=dict(l=0, r=0, t=0, b=0), height=200,
                    legend=dict(bgcolor="rgba(0,0,0,0)"),
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            with col_b:
                st.markdown(f"<small style='color:{_P_muted}'>Recent live orders</small>", unsafe_allow_html=True)
                recent_orders = store.get("orders_today", [])[-10:][::-1]
                for o in recent_orders:
                    cat_color = {
                        "Main Course": P["primary"],
                        "Starters":    P["secondary"],
                        "Beverages":   P["success"],
                        "Desserts":    P["accent"],
                    }.get(o["category"], P["muted"])
                    muted_c   = P["muted"]
                    text_c    = P["text"]
                    success_c = P["success"]
                    ts_str    = o["timestamp"]
                    cat_str   = o["category"]
                    qty_str   = o["quantity"]
                    rev_str   = format_inr(o["revenue"])
                    order_html = (
                        f"<div style='display:flex;justify-content:space-between;"
                        f"padding:4px 0;border-bottom:1px solid #2a2a3820;font-size:13px'>"
                        f"<span style='color:{muted_c}'>{ts_str}</span>"
                        f"<span style='color:{cat_color};font-weight:600'>{cat_str}</span>"
                        f"<span style='color:{text_c}'>{qty_str} units</span>"
                        f"<span style='color:{success_c}'>{rev_str}</span>"
                        f"</div>"
                    )
                    st.markdown(order_html, unsafe_allow_html=True)
    else:
        st.info("Click **Fetch Live Tick** to start receiving live order data.")

    st.divider()

    # ── Historical charts ─────────────────────────────────────────────────────
    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.markdown("<div class='section-header'>Demand Trend — Last 90 Days</div>", unsafe_allow_html=True)
        agg = rest_df.groupby("date")["quantity_sold"].sum().reset_index()
        fig = go.Figure(go.Scatter(
            x=agg["date"], y=agg["quantity_sold"],
            fill="tozeroy", fillcolor="rgba(255,107,53,0.10)",
            line=dict(color=P["primary"], width=2.2),
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=P["text"]),
            xaxis=dict(gridcolor="#2a2a38"), yaxis=dict(gridcolor="#2a2a38"),
            margin=dict(l=0, r=0, t=10, b=0), height=260,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.markdown("<div class='section-header'>Demand by Category</div>", unsafe_allow_html=True)
        cat_df = rest_df.groupby("category")["quantity_sold"].sum().reset_index()
        fig2 = px.pie(
            cat_df, names="category", values="quantity_sold",
            color_discrete_sequence=[P["primary"], P["secondary"], P["accent"], P["success"]],
            hole=0.45,
        )
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", font=dict(color=P["text"]),
            margin=dict(l=0, r=0, t=0, b=0), height=260,
            legend=dict(bgcolor="rgba(0,0,0,0)"),
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.markdown("<div class='section-header'>Monthly Revenue Breakdown</div>", unsafe_allow_html=True)
    monthly = rest_df.copy()
    monthly["month_label"] = monthly["date"].dt.strftime("%b %Y")
    monthly = monthly.groupby(["month_label", "category"])["revenue"].sum().reset_index()
    fig3 = px.bar(
        monthly, x="month_label", y="revenue", color="category",
        color_discrete_sequence=[P["primary"], P["secondary"], P["accent"], P["success"]],
    )
    fig3.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=P["text"]),
        xaxis=dict(gridcolor="#2a2a38", tickangle=-45),
        yaxis=dict(gridcolor="#2a2a38"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=0, r=0, t=10, b=0), height=300,
    )
    st.plotly_chart(fig3, use_container_width=True)
