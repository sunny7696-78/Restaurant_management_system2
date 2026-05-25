"""Multi-Restaurant Demand Heatmap view for IntelliPredict."""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from config import PALETTE
from utils import format_inr
from data_generator import RESTAURANTS, CATEGORIES

P         = PALETTE
_primary   = P["primary"]
_secondary = P["secondary"]
_success   = P["success"]
_danger    = P["danger"]
_muted     = P["muted"]
_text      = P["text"]
_accent    = P.get("accent", "#FFBF69")

RESTAURANT_COORDS = {
    "R001": {"name": "The Golden Kebab", "lat": 30.9010, "lon": 75.8573, "area": "Civil Lines"},
    "R002": {"name": "Urban Bistro",     "lat": 30.9120, "lon": 75.8481, "area": "Model Town"},
    "R003": {"name": "Pasta House",      "lat": 30.8970, "lon": 75.8650, "area": "Sarabha Nagar"},
    "R004": {"name": "Sushi Zen",        "lat": 30.9200, "lon": 75.8390, "area": "BRS Nagar"},
}


def render_heatmap(df: pd.DataFrame, rest_id: str, rest_name: str):
    st.markdown("# 🗺️ Multi-Restaurant Demand Heatmap")
    st.markdown(
        f"<small style='color:{_muted}'>Demand intensity across all Ludhiana restaurant locations</small>",
        unsafe_allow_html=True,
    )
    st.divider()

    # ── Per-restaurant KPIs ───────────────────────────────────────────────────
    rest_kpis = {}
    for rid, rinfo in RESTAURANT_COORDS.items():
        rdf   = df[df["restaurant_id"] == rid]
        today = rdf["date"].max()
        last7 = rdf[rdf["date"] >= today - pd.Timedelta(days=7)]
        qty   = int(last7["quantity_sold"].sum())
        rev   = last7["revenue"].sum()
        waste = round(last7["waste_kg"].sum(), 1)
        cov   = round(
            last7["stock_level"].mean() / last7["quantity_sold"].mean(), 1
        ) if last7["quantity_sold"].mean() > 0 else 0
        rest_kpis[rid] = {"qty": qty, "rev": rev, "waste": waste, "cov": cov}

    # ── Controls ──────────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    metric     = c1.selectbox("Heatmap Metric", ["Demand (Units)", "Revenue (₹)", "Waste (kg)"])
    time_range = c2.selectbox("Time Range", ["Last 7 Days", "Last 30 Days", "Last 90 Days"])
    category   = c3.selectbox("Category Filter", ["All Categories"] + CATEGORIES)

    ndays = {"Last 7 Days": 7, "Last 30 Days": 30, "Last 90 Days": 90}[time_range]

    # ── Build map dataframe ───────────────────────────────────────────────────
    rows = []
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

        rows.append({
            "restaurant_id": rid,
            "name":    rinfo["name"],
            "area":    rinfo["area"],
            "lat":     rinfo["lat"],
            "lon":     rinfo["lon"],
            "value":   heat_val,
            "display": fmt_val,
            "qty":     qty_val,
            "rev":     rev_val,
            "waste":   waste_val,
        })

    map_df  = pd.DataFrame(rows)
    max_val = map_df["value"].max() if map_df["value"].max() > 0 else 1
    map_df["size"] = 20 + 60 * (map_df["value"] / max_val)

    # ── Map using Plotly Express (compatible with all Plotly versions) ─────────
    st.markdown("<div class='section-header'>🗺️ Live Demand Map — Ludhiana</div>",
                unsafe_allow_html=True)

    hover_text = [
        f"<b>{row['name']}</b><br>Area: {row['area']}<br>"
        f"{metric}: {row['display']}<br>"
        f"Revenue: {format_inr(row['rev'])}<br>"
        f"Waste: {row['waste']} kg"
        for _, row in map_df.iterrows()
    ]

    fig = go.Figure()

    # Bubble layer — one trace per restaurant (no colorbar, no deprecated args)
    colors_list = [_primary, _secondary, _success, _accent]
    for i, (_, row) in enumerate(map_df.iterrows()):
        color = colors_list[i % len(colors_list)]
        fig.add_trace(go.Scattermapbox(
            lat=[row["lat"]],
            lon=[row["lon"]],
            mode="markers+text",
            marker=dict(
                size=float(row["size"]),
                color=color,
                opacity=0.7,
            ),
            text=[row["name"].split()[0]],
            textposition="top right",
            textfont=dict(size=11, color=_text),
            hovertext=[hover_text[i]],
            hoverinfo="text",
            name=row["name"],
        ))

    fig.update_layout(
        mapbox=dict(
            style="carto-darkmatter",
            center=dict(lat=30.905, lon=75.850),
            zoom=12.5,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=_text),
        margin=dict(l=0, r=0, t=0, b=0),
        height=460,
        legend=dict(
            bgcolor="rgba(26,26,36,0.85)",
            bordercolor="#2a2a38",
            font=dict(color=_text, size=11),
            x=0.01, y=0.99,
        ),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Bubble size legend ────────────────────────────────────────────────────
    st.caption(f"Bubble size = {metric}. Larger bubble = higher value.")

    st.divider()

    # ── Restaurant KPI cards ──────────────────────────────────────────────────
    st.markdown("<div class='section-header'>🏪 Restaurant Rankings</div>",
                unsafe_allow_html=True)

    rank   = map_df.sort_values("value", ascending=False).reset_index(drop=True)
    medals = ["🥇", "🥈", "🥉", "4️⃣"]
    cols   = st.columns(4)

    for i, (_, row) in enumerate(rank.iterrows()):
        kpi = rest_kpis[row["restaurant_id"]]
        cols[i].markdown(f"""
        <div class='kpi-card' style='text-align:left;border-color:{_primary}44'>
            <div style='font-size:22px;margin-bottom:6px'>{medals[i]}</div>
            <div style='font-weight:700;font-size:13px;color:{_text};margin-bottom:2px'>{row["name"]}</div>
            <div style='font-size:11px;color:{_muted};margin-bottom:10px'>{row["area"]}</div>
            <div style='font-size:13px;color:{_primary};font-weight:700'>{row["display"]}</div>
            <div style='font-size:11px;color:{_muted}'>{metric}</div>
            <hr style='border:none;border-top:1px solid #2a2a3820;margin:8px 0'>
            <div style='font-size:11px;color:{_muted}'>Revenue: <b style='color:{_secondary}'>{format_inr(kpi["rev"])}</b></div>
            <div style='font-size:11px;color:{_muted}'>Waste: <b style='color:{_danger}'>{kpi["waste"]} kg</b></div>
            <div style='font-size:11px;color:{_muted}'>Stock: <b style='color:{_success}'>{kpi["cov"]}x</b></div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ── Side-by-side comparison bars ──────────────────────────────────────────
    st.markdown("<div class='section-header'>📊 Cross-Restaurant Comparison</div>",
                unsafe_allow_html=True)

    compare_df = pd.DataFrame([
        {
            "Restaurant": RESTAURANT_COORDS[rid]["name"],
            "Demand":     rest_kpis[rid]["qty"],
            "Revenue_K":  round(rest_kpis[rid]["rev"] / 1000, 1),
            "Waste":      rest_kpis[rid]["waste"],
        }
        for rid in RESTAURANT_COORDS
    ])

    m1, m2, m3 = st.columns(3)
    disc = [_primary, _secondary, _success, _accent]

    for col, y_col, title, y_label in [
        (m1, "Demand",    "Units Sold (7d)",   "Units"),
        (m2, "Revenue_K", "Revenue ₹K (7d)",   "₹ (thousands)"),
        (m3, "Waste",     "Waste kg (7d)",      "kg"),
    ]:
        fig_b = px.bar(
            compare_df, x="Restaurant", y=y_col,
            color="Restaurant",
            color_discrete_sequence=disc,
            title=title,
        )
        fig_b.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=_text), showlegend=False,
            xaxis=dict(gridcolor="#2a2a38", tickangle=-15),
            yaxis=dict(gridcolor="#2a2a38", title=y_label),
            margin=dict(l=0, r=0, t=30, b=0), height=240,
        )
        col.plotly_chart(fig_b, use_container_width=True)

    st.divider()

    # ── Hour × day demand heatmap ─────────────────────────────────────────────
    st.markdown("<div class='section-header'>⏰ Demand Heatmap — Day × Hour</div>",
                unsafe_allow_html=True)

    sel_rest = st.selectbox("Select Restaurant for Hourly View",
                            list(RESTAURANTS.values()), key="hm_rest")
    sel_rid  = [k for k, v in RESTAURANTS.items() if v == sel_rest][0]

    np.random.seed(int(sel_rid[-1]))
    hours  = list(range(8, 23))
    days   = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    matrix = np.random.randint(10, 100, size=(len(days), len(hours))).astype(float)
    for d in [5, 6]:            # weekends
        matrix[d] *= 1.4
    for h_idx, h in enumerate(hours):
        if h in [12, 13, 19, 20]:   # lunch + dinner
            matrix[:, h_idx] *= 1.6

    fig_hm = go.Figure(go.Heatmap(
        z=matrix,
        x=[f"{h}:00" for h in hours],
        y=days,
        colorscale="YlOrRd",
        hovertemplate="<b>%{y} %{x}</b><br>Demand: %{z:.0f} units<extra></extra>",
        showscale=True,
    ))
    fig_hm.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=_text),
        xaxis=dict(gridcolor="#2a2a38"),
        yaxis=dict(gridcolor="#2a2a38"),
        margin=dict(l=0, r=0, t=10, b=0), height=280,
    )
    st.plotly_chart(fig_hm, use_container_width=True)
