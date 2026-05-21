"""Multi-Restaurant Demand Heatmap view for IntelliPredict."""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from config import PALETTE
from utils import format_inr
from data_generator import RESTAURANTS, CATEGORIES

P = PALETTE

# Real Ludhiana-area coordinates for demo restaurants
RESTAURANT_COORDS = {
    "R001": {"name": "The Golden Kebab",  "lat": 30.9010, "lon": 75.8573, "area": "Civil Lines"},
    "R002": {"name": "Urban Bistro",      "lat": 30.9120, "lon": 75.8481, "area": "Model Town"},
    "R003": {"name": "Pasta House",       "lat": 30.8970, "lon": 75.8650, "area": "Sarabha Nagar"},
    "R004": {"name": "Sushi Zen",         "lat": 30.9200, "lon": 75.8390, "area": "BRS Nagar"},
}


def render_heatmap(df: pd.DataFrame, rest_id: str, rest_name: str):
    st.markdown("# 🗺️ Multi-Restaurant Demand Heatmap")
    st.markdown(f"<small style='color:{P['muted']}'>Real-time demand intensity across all restaurant locations in Ludhiana</small>", unsafe_allow_html=True)
    st.divider()

    # ── Compute per-restaurant KPIs ───────────────────────────────────────────
    rest_kpis = {}
    for rid, rinfo in RESTAURANT_COORDS.items():
        rdf   = df[df["restaurant_id"] == rid]
        today = rdf["date"].max()
        last7 = rdf[rdf["date"] >= today - pd.Timedelta(days=7)]
        qty   = int(last7["quantity_sold"].sum())
        rev   = last7["revenue"].sum()
        waste = round(last7["waste_kg"].sum(), 1)
        cov   = round(last7["stock_level"].mean() / last7["quantity_sold"].mean(), 1) if last7["quantity_sold"].mean() > 0 else 0
        rest_kpis[rid] = {"qty": qty, "rev": rev, "waste": waste, "cov": cov}

    # ── Controls ──────────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    metric    = c1.selectbox("Heatmap Metric", ["Demand (Units)", "Revenue (₹)", "Waste (kg)"])
    time_range= c2.selectbox("Time Range", ["Last 7 Days", "Last 30 Days", "Last 90 Days"])
    category  = c3.selectbox("Category Filter", ["All Categories"] + CATEGORIES)

    days_map = {"Last 7 Days": 7, "Last 30 Days": 30, "Last 90 Days": 90}
    ndays    = days_map[time_range]

    # ── Build map data ────────────────────────────────────────────────────────
    map_rows = []
    for rid, rinfo in RESTAURANT_COORDS.items():
        rdf   = df[df["restaurant_id"] == rid]
        today = rdf["date"].max()
        filt  = rdf[rdf["date"] >= today - pd.Timedelta(days=ndays)]
        if category != "All Categories":
            filt = filt[filt["category"] == category]

        qty_val   = int(filt["quantity_sold"].sum())
        rev_val   = filt["revenue"].sum()
        waste_val = round(filt["waste_kg"].sum(), 1)

        if metric == "Demand (Units)":
            heat_val = qty_val
            fmt_val  = f"{qty_val:,} units"
        elif metric == "Revenue (₹)":
            heat_val = rev_val
            fmt_val  = format_inr(rev_val)
        else:
            heat_val = waste_val
            fmt_val  = f"{waste_val} kg"

        map_rows.append({
            "restaurant_id": rid,
            "name":     rinfo["name"],
            "area":     rinfo["area"],
            "lat":      rinfo["lat"],
            "lon":      rinfo["lon"],
            "value":    heat_val,
            "display":  fmt_val,
            "qty":      qty_val,
            "rev":      rev_val,
            "waste":    waste_val,
        })

    map_df = pd.DataFrame(map_rows)
    max_val = map_df["value"].max() if map_df["value"].max() > 0 else 1
    map_df["size"]    = 20 + 60 * (map_df["value"] / max_val)
    map_df["opacity"] = 0.4 + 0.5 * (map_df["value"] / max_val)

    # ── Plotly map ────────────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>🗺️ Live Demand Map</div>", unsafe_allow_html=True)

    fig = go.Figure()

    # Heatmap scatter circles
    fig.add_trace(go.Scattermapbox(
        lat=map_df["lat"],
        lon=map_df["lon"],
        mode="markers",
        marker=dict(
            size=map_df["size"],
            color=map_df["value"],
            colorscale=[[0, "#1A1A24"], [0.3, "#FF9F1C"], [0.7, "#FF6B35"], [1.0, "#E63946"]],
            opacity=0.6,
            showscale=True,
            colorbar=dict(
                title=metric,
                tickfont=dict(color=P["text"]),
                titlefont=dict(color=P["text"]),
                bgcolor="rgba(26,26,36,0.8)",
                bordercolor="#2a2a38",
            ),
        ),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Area: %{customdata[1]}<br>"
            f"{metric}: %{{customdata[2]}}<br>"
            "Revenue: %{customdata[3]}<br>"
            "Waste: %{customdata[4]} kg<br>"
            "<extra></extra>"
        ),
        customdata=list(zip(
            map_df["name"], map_df["area"], map_df["display"],
            map_df["rev"].apply(format_inr), map_df["waste"],
        )),
        name="Demand Intensity",
    ))

    # Restaurant label pins
    fig.add_trace(go.Scattermapbox(
        lat=map_df["lat"],
        lon=map_df["lon"],
        mode="markers+text",
        marker=dict(size=12, color=P["primary"]),
        text=map_df["name"].apply(lambda x: x.split()[0]),
        textposition="top right",
        textfont=dict(size=11, color=P["text"]),
        hoverinfo="skip",
        name="Restaurants",
    ))

    fig.update_layout(
        mapbox=dict(
            style="carto-darkmatter",
            center=dict(lat=30.905, lon=75.850),
            zoom=12.5,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=P["text"]),
        margin=dict(l=0, r=0, t=0, b=0),
        height=480,
        legend=dict(
            bgcolor="rgba(26,26,36,0.8)",
            bordercolor="#2a2a38",
            font=dict(color=P["text"]),
        ),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Restaurant comparison cards ───────────────────────────────────────────
    st.markdown("<div class='section-header'>🏪 Restaurant Comparison</div>", unsafe_allow_html=True)

    cols = st.columns(4)
    rank = map_df.sort_values("value", ascending=False).reset_index(drop=True)
    medal = ["🥇", "🥈", "🥉", "4️⃣"]

    for i, (_, row) in enumerate(rank.iterrows()):
        kpi = rest_kpis[row["restaurant_id"]]
        cols[i].markdown(f"""
        <div class='kpi-card' style='text-align:left;border-color:{P["primary"]}44'>
            <div style='font-size:22px;margin-bottom:6px'>{medal[i]}</div>
            <div style='font-weight:700;font-size:13px;color:{P["text"]};margin-bottom:2px'>{row["name"]}</div>
            <div style='font-size:11px;color:{P["muted"]};margin-bottom:10px'>{row["area"]}</div>
            <div style='font-size:12px;color:{P["primary"]};font-weight:700'>{row["display"]}</div>
            <div style='font-size:11px;color:{P["muted"]}'>{metric}</div>
            <hr style='border:none;border-top:1px solid #2a2a3820;margin:8px 0'>
            <div style='font-size:11px;color:{P["muted"]}'>Revenue: <b style='color:{P["secondary"]}'>{format_inr(kpi["rev"])}</b></div>
            <div style='font-size:11px;color:{P["muted"]}'>Waste: <b style='color:{P["danger"]}'>{kpi["waste"]} kg</b></div>
            <div style='font-size:11px;color:{P["muted"]}'>Stock: <b style='color:{P["success"]}'>{kpi["cov"]}x</b></div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ── Comparative bar chart ──────────────────────────────────────────────────
    st.markdown("<div class='section-header'>📊 Side-by-Side Comparison</div>", unsafe_allow_html=True)

    compare_df = pd.DataFrame([
        {"Restaurant": RESTAURANT_COORDS[rid]["name"],
         "Demand": rest_kpis[rid]["qty"],
         "Revenue": rest_kpis[rid]["rev"] / 1000,
         "Waste":   rest_kpis[rid]["waste"]}
        for rid in RESTAURANT_COORDS
    ])

    m1, m2 = st.columns(2)
    with m1:
        fig_bar = px.bar(
            compare_df, x="Restaurant", y="Demand",
            color="Restaurant",
            color_discrete_sequence=[P["primary"], P["secondary"], P["success"], P["accent"]],
            title="Units Sold (7d)",
        )
        fig_bar.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=P["text"]), showlegend=False,
            xaxis=dict(gridcolor="#2a2a38"), yaxis=dict(gridcolor="#2a2a38"),
            margin=dict(l=0, r=0, t=30, b=0), height=260,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with m2:
        fig_rev = px.bar(
            compare_df, x="Restaurant", y="Revenue",
            color="Restaurant",
            color_discrete_sequence=[P["primary"], P["secondary"], P["success"], P["accent"]],
            title="Revenue ₹K (7d)",
        )
        fig_rev.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=P["text"]), showlegend=False,
            xaxis=dict(gridcolor="#2a2a38"), yaxis=dict(gridcolor="#2a2a38"),
            margin=dict(l=0, r=0, t=30, b=0), height=260,
        )
        st.plotly_chart(fig_rev, use_container_width=True)

    # ── Hourly heatmap ────────────────────────────────────────────────────────
    st.divider()
    st.markdown("<div class='section-header'>⏰ Demand Heatmap by Day × Hour</div>", unsafe_allow_html=True)

    sel_rest = st.selectbox("Select Restaurant", list(RESTAURANTS.values()), key="hm_rest")
    sel_rid  = [k for k, v in RESTAURANTS.items() if v == sel_rest][0]

    np.random.seed(int(sel_rid[-1]))
    hours = list(range(8, 23))
    days  = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    matrix = np.random.randint(10, 100, size=(len(days), len(hours))).astype(float)
    # boost weekends and lunch/dinner
    for d in [5, 6]:
        matrix[d] *= 1.4
    for h_idx, h in enumerate(hours):
        if h in [12, 13, 19, 20]:
            matrix[:, h_idx] *= 1.6

    fig_hm = go.Figure(go.Heatmap(
        z=matrix,
        x=[f"{h}:00" for h in hours],
        y=days,
        colorscale=[[0, "#1A1A24"], [0.3, "#FF9F1C"], [0.7, "#FF6B35"], [1.0, "#E63946"]],
        hovertemplate="<b>%{y} %{x}</b><br>Demand: %{z} units<extra></extra>",
        showscale=True,
    ))
    fig_hm.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=P["text"]),
        xaxis=dict(gridcolor="#2a2a38"),
        yaxis=dict(gridcolor="#2a2a38"),
        margin=dict(l=0, r=0, t=10, b=0), height=280,
    )
    st.plotly_chart(fig_hm, use_container_width=True)
