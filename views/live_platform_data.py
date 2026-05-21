"""Live Platform Data — Zomato/Swiggy/Google simulated real-time feed."""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import re
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from config import PALETTE
from utils import format_inr
from data_generator import RESTAURANTS, CATEGORIES

P = PALETTE
_danger = P["danger"]
_muted = P["muted"]
_primary = P["primary"]
_secondary = P["secondary"]
_success = P["success"]
_text = P["text"]

# ── Simulated platform data (mirrors real API structure) ─────────────────────
# Note: Zomato/Swiggy do not provide public APIs. This simulates the data
# structure you'd get from their Partner APIs (for registered businesses).

PLATFORM_BASE = {
    "Zomato": {
        "color": "#E23744", "icon": "🍕",
        "avg_order_value": 380, "commission_pct": 18,
        "rating_base": 4.1,
    },
    "Swiggy": {
        "color": "#FC8019", "icon": "🛵",
        "avg_order_value": 340, "commission_pct": 20,
        "rating_base": 4.0,
    },
    "Dine-In": {
        "color": "#2EC4B6", "icon": "🍽️",
        "avg_order_value": 680, "commission_pct": 0,
        "rating_base": 4.3,
    },
}


def simulate_platform_data(rest_id: str, days: int = 30) -> pd.DataFrame:
    """Simulate realistic Zomato/Swiggy/Dine-In order data."""
    seed = int(rest_id[-1]) * 42
    rng  = np.random.default_rng(seed)
    rows = []
    today = datetime.now().date()

    for d in range(days):
        date = today - timedelta(days=d)
        is_weekend = date.weekday() >= 5

        for platform, meta in PLATFORM_BASE.items():
            base_orders = (
                45 if platform == "Zomato" else
                38 if platform == "Swiggy" else 60
            ) * (1.3 if is_weekend else 1.0) * (1 + int(rest_id[-1]) * 0.05)

            orders = max(5, int(rng.poisson(base_orders) + rng.normal(0, 3)))
            aov    = meta["avg_order_value"] * (1 + rng.normal(0, 0.05))
            revenue= orders * aov
            commission = revenue * meta["commission_pct"] / 100
            cancelled  = max(0, int(rng.poisson(orders * 0.04)))
            rating     = round(min(5.0, max(1.0, meta["rating_base"] + rng.normal(0, 0.15))), 1)

            rows.append({
                "date":         date,
                "platform":     platform,
                "orders":       orders,
                "cancelled":    cancelled,
                "revenue":      round(revenue, 0),
                "commission":   round(commission, 0),
                "net_revenue":  round(revenue - commission, 0),
                "aov":          round(aov, 0),
                "rating":       rating,
                "is_weekend":   is_weekend,
            })

    return pd.DataFrame(rows).sort_values("date", ascending=False)


def fetch_google_places_rating(rest_name: str) -> dict:
    """Fetch real Google Places rating (requires Places API key in secrets)."""
    try:
        api_key = st.secrets.get("GOOGLE_PLACES_API_KEY", "")
        if not api_key:
            return {"source": "demo", "rating": 4.2, "reviews": 342, "status": "Demo data"}

        search_url = (
            f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
            f"?input={requests.utils.quote(rest_name + ' Ludhiana')}"
            f"&inputtype=textquery&fields=rating,user_ratings_total,name"
            f"&key={api_key}"
        )
        data = requests.get(search_url, timeout=8).json()
        if data.get("candidates"):
            c = data["candidates"][0]
            return {
                "source":  "Google Places API",
                "rating":  c.get("rating", 0),
                "reviews": c.get("user_ratings_total", 0),
                "status":  "Live",
            }
        return {"source": "Google", "rating": 0, "reviews": 0, "status": "Not found"}
    except Exception as e:
        return {"source": "demo", "rating": 4.1, "reviews": 280, "status": "Demo mode"}


def render_live_platform_data(df: pd.DataFrame, rest_id: str, rest_name: str):
    st.markdown("# 📡 Live Platform Data")
    st.markdown(
        f"<small style='color:{_muted}'>Real-time order feeds from Zomato, Swiggy & Dine-In for <b>{rest_name}</b></small>",
        unsafe_allow_html=True,
    )
    st.markdown(f"""
    <div style='background:#2a1f0f;border:1px solid {_secondary}44;border-radius:8px;
                padding:10px 16px;margin-bottom:16px;font-size:12px;color:{_secondary}'>
        ⚠️ <b>Note:</b> Zomato & Swiggy don't offer public APIs. This uses a realistic simulation
        of Partner API data structures. To connect real data, register as a restaurant partner
        and use their Business Manager API credentials in Secrets.
    </div>""", unsafe_allow_html=True)

    st.divider()

    # ── Controls ──────────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    days_range = c1.selectbox("Time Range", [7, 14, 30], format_func=lambda x: f"Last {x} days")
    platform_filter = c2.multiselect("Platforms", list(PLATFORM_BASE.keys()), default=list(PLATFORM_BASE.keys()))
    metric = c3.selectbox("Primary Metric", ["orders", "net_revenue", "aov", "rating"])

    platform_df = simulate_platform_data(rest_id, days=days_range + 1)
    if platform_filter:
        platform_df = platform_df[platform_df["platform"].isin(platform_filter)]

    agg = platform_df.groupby("platform").agg(
        total_orders=("orders", "sum"),
        total_revenue=("revenue", "sum"),
        net_revenue=("net_revenue", "sum"),
        total_commission=("commission", "sum"),
        avg_aov=("aov", "mean"),
        avg_rating=("rating", "mean"),
        cancelled=("cancelled", "sum"),
    ).reset_index()

    # ── Platform KPI cards ────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>📊 Platform Performance Summary</div>", unsafe_allow_html=True)

    cols = st.columns(len(agg))
    for i, (_, row) in enumerate(agg.iterrows()):
        meta  = PLATFORM_BASE.get(row["platform"], {})
        color = meta.get("color", _primary)
        icon  = meta.get("icon", "📦")
        cancel_rate = round(row["cancelled"] / max(row["total_orders"], 1) * 100, 1)

        cols[i].markdown(f"""
        <div class='kpi-card' style='text-align:left;border-color:{color}44'>
            <div style='font-size:20px;margin-bottom:6px'>{icon} <b style='color:{color}'>{row["platform"]}</b></div>
            <div style='font-size:22px;font-weight:700;color:{color}'>{int(row["total_orders"]):,}</div>
            <div style='font-size:11px;color:{_muted};margin-bottom:8px'>orders ({days_range}d)</div>
            <div style='font-size:12px;color:{_text}'>Net Rev: <b style='color:{_success}'>{format_inr(row["net_revenue"])}</b></div>
            <div style='font-size:12px;color:{_text}'>Commission: <b style='color:{_danger}'>{format_inr(row["total_commission"])}</b></div>
            <div style='font-size:12px;color:{_text}'>Avg Order: <b>₹{int(row["avg_aov"])}</b></div>
            <div style='font-size:12px;color:{_text}'>Rating: <b style='color:{_secondary}'>⭐ {row["avg_rating"]:.1f}</b></div>
            <div style='font-size:11px;color:{_danger}'>Cancel rate: {cancel_rate}%</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ── Daily trend chart ─────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>📈 Daily Orders by Platform</div>", unsafe_allow_html=True)

    daily = platform_df.groupby(["date", "platform"])["orders"].sum().reset_index()
    daily["date_str"] = daily["date"].astype(str)

    fig_trend = go.Figure()
    for platform, meta in PLATFORM_BASE.items():
        if platform not in platform_filter:
            continue
        pdata = daily[daily["platform"] == platform]
        fig_trend.add_trace(go.Scatter(
            x=pdata["date_str"], y=pdata["orders"],
            mode="lines+markers",
            name=platform,
            line=dict(color=meta["color"], width=2.5),
            marker=dict(size=5),
        ))
    fig_trend.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=_text),
        xaxis=dict(gridcolor="#2a2a38"),
        yaxis=dict(gridcolor="#2a2a38", title="Orders"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=0, r=0, t=10, b=0), height=280,
    )
    st.plotly_chart(fig_trend, use_container_width=True)

    # ── Revenue split ─────────────────────────────────────────────────────────
    st.divider()
    r1, r2 = st.columns(2)

    with r1:
        st.markdown("<div class='section-header'>💰 Revenue Split by Platform</div>", unsafe_allow_html=True)
        fig_pie = go.Figure(go.Pie(
            labels=agg["platform"],
            values=agg["net_revenue"],
            hole=0.5,
            marker=dict(colors=[PLATFORM_BASE.get(p, {}).get("color", _primary) for p in agg["platform"]]),
        ))
        fig_pie.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color=_text),
            legend=dict(bgcolor="rgba(0,0,0,0)"),
            margin=dict(l=0, r=0, t=10, b=0), height=280,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with r2:
        st.markdown("<div class='section-header'>💸 Commission Cost Analysis</div>", unsafe_allow_html=True)
        total_rev  = agg["total_revenue"].sum()
        total_comm = agg["total_commission"].sum()
        total_net  = agg["net_revenue"].sum()
        comm_pct   = round(total_comm / max(total_rev, 1) * 100, 1)

        st.markdown(f"""
        <div class='kpi-card' style='text-align:left;margin-bottom:10px'>
            <div style='font-size:12px;color:{_muted};margin-bottom:4px'>Total Gross Revenue</div>
            <div style='font-size:20px;font-weight:700;color:{_text}'>{format_inr(total_rev)}</div>
        </div>
        <div class='kpi-card' style='text-align:left;margin-bottom:10px;border-color:{_danger}44'>
            <div style='font-size:12px;color:{_muted};margin-bottom:4px'>Platform Commissions</div>
            <div style='font-size:20px;font-weight:700;color:{_danger}'>- {format_inr(total_comm)} ({comm_pct}%)</div>
        </div>
        <div class='kpi-card' style='text-align:left;border-color:{_success}44'>
            <div style='font-size:12px;color:{_muted};margin-bottom:4px'>Net Revenue (After Commission)</div>
            <div style='font-size:20px;font-weight:700;color:{_success}'>{format_inr(total_net)}</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ── Google rating live fetch ───────────────────────────────────────────────
    st.markdown("<div class='section-header'>🌟 Live Google Rating</div>", unsafe_allow_html=True)

    if st.button("🔍 Fetch Live Google Rating", use_container_width=False):
        with st.spinner("Fetching from Google Places…"):
            gdata = fetch_google_places_rating(rest_name)
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("Google Rating", f"⭐ {gdata['rating']}")
        g2.metric("Total Reviews", f"{gdata['reviews']:,}")
        g3.metric("Data Source",    gdata["source"])
        g4.metric("Status",         gdata["status"])
        if gdata["source"] == "demo":
            st.info("💡 Add GOOGLE_PLACES_API_KEY to Streamlit Secrets to fetch live data.")

    st.divider()

    # ── Peak hours heatmap ────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>⏰ Platform Order Heatmap (Hour × Day)</div>", unsafe_allow_html=True)

    sel_plat = st.selectbox("Select Platform", list(PLATFORM_BASE.keys()), key="hm_plat")
    rng2     = np.random.default_rng(int(rest_id[-1]) + hash(sel_plat) % 100)

    hours = list(range(9, 23))
    days  = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    mat   = rng2.integers(2, 30, size=(7, len(hours))).astype(float)
    for d in [5, 6]:    mat[d] *= 1.4
    for h in [3, 4, 10, 11]: mat[:, h] *= 1.7  # lunch & dinner

    color = PLATFORM_BASE[sel_plat]["color"]
    fig_hm = go.Figure(go.Heatmap(
        z=mat, x=[f"{h}:00" for h in hours], y=days,
        colorscale=[[0, "#1A1A24"], [0.5, color + "88"], [1.0, color]],
        hovertemplate="<b>%{y} %{x}</b><br>Orders: %{z:.0f}<extra></extra>",
    ))
    fig_hm.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=_text),
        xaxis=dict(gridcolor="#2a2a38"),
        yaxis=dict(gridcolor="#2a2a38"),
        margin=dict(l=0, r=0, t=10, b=0), height=260,
    )
    st.plotly_chart(fig_hm, use_container_width=True)

    st.divider()

    # ── Raw data table ────────────────────────────────────────────────────────
    with st.expander("📋 Raw Platform Data Table"):
        display = platform_df.head(50).copy()
        display["revenue"]     = display["revenue"].apply(format_inr)
        display["net_revenue"] = display["net_revenue"].apply(format_inr)
        display["commission"]  = display["commission"].apply(format_inr)
        st.dataframe(display, use_container_width=True, hide_index=True)

        csv = platform_df.to_csv(index=False).encode()
        st.download_button("⬇️ Download Full Data CSV", csv,
                           file_name=f"platform_data_{rest_id}.csv", mime="text/csv")
