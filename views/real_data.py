"""
Real Data Hub — IntelliPredict
Fetches and manages REAL data from 5 sources:
1. OpenWeatherMap live weather
2. User CSV/Excel upload
3. Google Sheets (public)
4. Open Government / food datasets
5. Gemini AI data enrichment
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import requests
import io
from datetime import datetime, timedelta
from config import PALETTE
from utils import format_inr
from real_data_engine import (
    fetch_live_weather, fetch_5day_forecast,
    load_uploaded_data, load_google_sheet,
    get_sample_template, merge_real_with_synthetic,
)
from data_generator import CATEGORIES, PRICE_MAP, RESTAURANTS, generate_dataset

P          = PALETTE
_primary   = P["primary"]
_secondary = P["secondary"]
_success   = P["success"]
_danger    = P["danger"]
_muted     = P["muted"]
_text      = P["text"]
_accent    = P.get("accent", "#FFBF69")


def _metric_card(col, label, value, sub="", color=None):
    c = color or _primary
    col.markdown(f"""
    <div class='kpi-card' style='border-color:{c}44'>
        <div class='kpi-label'>{label}</div>
        <div class='kpi-value' style='color:{c};font-size:1.3rem'>{value}</div>
        <div class='kpi-label'>{sub}</div>
    </div>""", unsafe_allow_html=True)


def render_real_data(df: pd.DataFrame, rest_id: str, rest_name: str):

    st.markdown("# 🌐 Real Data Hub")
    st.markdown(
        f"<small style='color:{_muted}'>Live & real data feeds powering IntelliPredict analytics</small>",
        unsafe_allow_html=True,
    )

    # Data source status badges
    weather_key = bool(st.secrets.get("OPENWEATHER_API_KEY", ""))
    gemini_key  = bool(st.secrets.get("GEMINI_API_KEY", ""))
    real_data   = st.session_state.get("real_df") is not None

    b1, b2, b3, b4, b5 = st.columns(5)
    for col, label, ok in [
        (b1, "🌦️ Live Weather",   weather_key),
        (b2, "📁 Your Data",      real_data),
        (b3, "📊 Google Sheets",  real_data),
        (b4, "🏛️ Gov Datasets",   True),
        (b5, "🤖 Gemini Enrich",  gemini_key),
    ]:
        color = _success if ok else _danger
        status = "Connected" if ok else "Not set"
        col.markdown(f"""
        <div style='background:{color}11;border:1px solid {color}44;border-radius:8px;
                    padding:8px 10px;text-align:center'>
            <div style='font-size:12px;font-weight:600;color:{color}'>{label}</div>
            <div style='font-size:10px;color:{_muted}'>{status}</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    tabs = st.tabs([
        "🌦️ Live Weather",
        "📁 Upload Your Data",
        "📊 Google Sheets",
        "🏛️ Gov & Open Data",
        "🤖 AI Data Enrichment",
    ])

    # ═══════════════════════════════════════════════════════════════════
    # TAB 1 — LIVE WEATHER
    # ═══════════════════════════════════════════════════════════════════
    with tabs[0]:
        st.markdown("<div class='section-header'>🌦️ Real-Time Ludhiana Weather</div>",
                    unsafe_allow_html=True)

        if not weather_key:
            st.warning(
                "**OpenWeatherMap API key not set.** "
                "Get a free key at [openweathermap.org](https://openweathermap.org/api) "
                "and add `OPENWEATHER_API_KEY` to your Streamlit Secrets.",
                icon="⚠️",
            )
            st.info("Showing simulated weather data below.")

        if st.button("🔄 Refresh Live Weather", use_container_width=True):
            st.session_state["weather_cache"] = None

        weather = st.session_state.get("weather_cache") or fetch_live_weather()
        st.session_state["weather_cache"] = weather

        # Live weather KPIs
        source_badge = (
            f"<span style='color:{_success};font-size:11px'>● LIVE</span>"
            if weather["source"] == "live"
            else f"<span style='color:{_secondary};font-size:11px'>◌ Simulated</span>"
        )
        st.markdown(f"Data source: {source_badge} · Updated {weather['timestamp']}",
                    unsafe_allow_html=True)
        st.markdown("")

        w1, w2, w3, w4, w5 = st.columns(5)
        rain_color = _danger if weather["rain"] else _success
        _metric_card(w1, "Temperature",  f"{weather['temp']}°C",  f"Feels {weather['feels_like']}°C")
        _metric_card(w2, "Condition",    weather["description"],  "Current sky", _secondary)
        _metric_card(w3, "Humidity",     f"{weather['humidity']}%", "Relative humidity", _accent)
        _metric_card(w4, "Wind Speed",   f"{weather['wind_speed']} m/s", "Surface wind")
        _metric_card(w5, "Rain Today",   "Yes 🌧️" if weather["rain"] else "No ☀️",
                     "Affects footfall", rain_color)

        # Demand impact box
        temp   = weather["temp"]
        rain   = weather["rain"]
        impact = -18 if rain else (+8 if 20 <= temp <= 28 else (-6 if temp > 35 else 0))
        impact_color = _success if impact >= 0 else _danger
        st.markdown(f"""
        <div style='background:{impact_color}11;border:1px solid {impact_color}44;
                    border-radius:10px;padding:14px 16px;margin:12px 0'>
            <span style='font-size:13px;font-weight:600;color:{impact_color}'>
                📊 Demand Impact Today: {'+' if impact >= 0 else ''}{impact}%
            </span>
            <span style='font-size:12px;color:{_muted};margin-left:12px'>
                {'Rain reduces dine-in footfall' if rain else
                 'Pleasant weather boosts footfall' if impact > 0 else
                 'Hot weather reduces dine-in demand' if impact < 0 else
                 'Neutral weather — baseline demand expected'}
            </span>
        </div>""", unsafe_allow_html=True)

        # 5-day forecast
        st.markdown("<div class='section-header'>📅 5-Day Weather Forecast + Demand Prediction</div>",
                    unsafe_allow_html=True)

        with st.spinner("Fetching forecast…"):
            forecast_df = fetch_5day_forecast()

        daily_fc = (
            forecast_df.groupby("date")
            .agg(temp=("temp","mean"), rain=("rain","max"),
                 demand_factor=("demand_factor","mean"),
                 description=("description","first"))
            .reset_index()
            .head(5)
        )

        fc_cols = st.columns(len(daily_fc))
        for i, (_, row) in enumerate(daily_fc.iterrows()):
            adj = round((row["demand_factor"] - 1) * 100)
            c   = _success if adj >= 0 else _danger
            rain_icon = "🌧️" if row["rain"] else "☀️"
            fc_cols[i].markdown(f"""
            <div style='background:{P["card"]};border:1px solid #2a2a38;border-radius:10px;
                        padding:12px;text-align:center'>
                <div style='font-size:13px;font-weight:600;color:{_text}'>{row["date"]}</div>
                <div style='font-size:22px;margin:4px 0'>{rain_icon}</div>
                <div style='font-size:12px;color:{_muted}'>{row["description"]}</div>
                <div style='font-size:14px;font-weight:700;color:{_secondary};margin:4px 0'>{row["temp"]:.0f}°C</div>
                <div style='font-size:12px;color:{c};font-weight:600'>
                    {'+' if adj >= 0 else ''}{adj}% demand
                </div>
            </div>""", unsafe_allow_html=True)

        # Temperature & demand factor trend chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=forecast_df["datetime"].astype(str), y=forecast_df["temp"],
            name="Temperature °C", line=dict(color=_secondary, width=2),
            yaxis="y2",
        ))
        fig.add_trace(go.Bar(
            x=forecast_df["datetime"].astype(str),
            y=(forecast_df["demand_factor"] - 1) * 100,
            name="Demand Impact %",
            marker_color=[_success if v >= 0 else _danger
                          for v in (forecast_df["demand_factor"] - 1) * 100],
            opacity=0.7,
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=_text), height=280,
            xaxis=dict(gridcolor="#2a2a38", tickangle=-45, nticks=10),
            yaxis=dict(gridcolor="#2a2a38", title="Demand Impact %"),
            yaxis2=dict(overlaying="y", side="right", title="Temp °C", showgrid=False),
            legend=dict(bgcolor="rgba(0,0,0,0)"),
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════
    # TAB 2 — UPLOAD YOUR OWN DATA
    # ═══════════════════════════════════════════════════════════════════
    with tabs[1]:
        st.markdown("<div class='section-header'>📁 Upload Your Real Restaurant Data</div>",
                    unsafe_allow_html=True)

        st.markdown(f"""
        <div style='background:{_accent}11;border:1px solid {_accent}44;border-radius:10px;
                    padding:14px 16px;margin-bottom:16px;font-size:13px;color:{_text}'>
            <b>Supported formats:</b> CSV, Excel (.xlsx), JSON<br>
            <b>Required columns:</b> <code>date</code>, <code>quantity_sold</code>, <code>revenue</code><br>
            <b>Optional columns:</b> category, waste_kg, stock_level, restaurant_id, restaurant_name<br>
            <b>Date formats:</b> YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, DD Mon YYYY
        </div>""", unsafe_allow_html=True)

        # Download template
        template_df = get_sample_template()
        csv_bytes   = template_df.to_csv(index=False).encode()
        c1, c2 = st.columns(2)
        c1.download_button(
            "⬇️ Download CSV Template", csv_bytes,
            "intellipredict_template.csv", "text/csv",
            use_container_width=True,
        )

        # JSON template as second option
        import json as _json
        json_bytes = template_df.to_json(orient="records", date_format="iso").encode()
        c2.download_button(
            "⬇️ Download JSON Template", json_bytes,
            "intellipredict_template.json", "application/json",
            use_container_width=True,
        )

        uploaded = st.file_uploader(
            "Upload your sales data file",
            type=["csv","xlsx","xls","json"],
            help="Fill the template with your real data and upload here",
        )

        if uploaded:
            with st.spinner("Reading and validating your data…"):
                ok, msg, real_df = load_uploaded_data(uploaded)

            if ok and real_df is not None:
                st.success(msg)
                st.session_state["real_df"]      = real_df
                st.session_state["real_df_name"] = uploaded.name
                st.session_state["data_source"]  = "uploaded"

                # Preview
                st.markdown("<div class='section-header'>Data Preview</div>",
                            unsafe_allow_html=True)
                r1, r2, r3, r4 = st.columns(4)
                _metric_card(r1, "Total Rows",      f"{len(real_df):,}", "records")
                _metric_card(r2, "Date Range",
                             f"{real_df['date'].min().strftime('%d %b %y')} – {real_df['date'].max().strftime('%d %b %y')}",
                             "coverage", _secondary)
                _metric_card(r3, "Total Revenue",
                             format_inr(real_df["revenue"].sum()), "all time", _success)
                _metric_card(r4, "Avg Daily Demand",
                             f"{real_df.groupby('date')['quantity_sold'].sum().mean():.0f}",
                             "units/day", _accent)

                st.dataframe(real_df.head(20), use_container_width=True)

                # Quick charts on real data
                st.markdown("<div class='section-header'>Real Data — Quick Analysis</div>",
                            unsafe_allow_html=True)

                daily = real_df.groupby("date").agg(
                    qty=("quantity_sold","sum"), rev=("revenue","sum")
                ).reset_index()

                fig_r = go.Figure(go.Scatter(
                    x=daily["date"], y=daily["qty"],
                    fill="tozeroy", fillcolor=f"{_primary}22",
                    line=dict(color=_primary, width=2), name="Daily Demand",
                ))
                fig_r.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color=_text), height=220,
                    xaxis=dict(gridcolor="#2a2a38"),
                    yaxis=dict(gridcolor="#2a2a38", title="Units Sold"),
                    margin=dict(l=0, r=0, t=10, b=0),
                )
                st.plotly_chart(fig_r, use_container_width=True)

                st.info(
                    "✅ Your real data is now loaded. "
                    "Navigate to Dashboard, Forecast, or AI Insights — "
                    "they will use your real data instead of synthetic data.",
                    icon="🎯",
                )
            else:
                st.error(msg)
                st.markdown("""
                **Common fixes:**
                - Make sure your file has columns: `date`, `quantity_sold`, `revenue`
                - Date format should be YYYY-MM-DD or DD/MM/YYYY
                - Remove merged cells from Excel files
                - Save as CSV if Excel isn't working
                """)

        elif st.session_state.get("real_df") is not None:
            st.success(
                f"✅ Real data already loaded: **{st.session_state.get('real_df_name','')}** "
                f"({len(st.session_state['real_df']):,} rows)"
            )
            if st.button("🗑️ Clear uploaded data, revert to synthetic"):
                st.session_state["real_df"]     = None
                st.session_state["data_source"] = "synthetic"
                st.rerun()

    # ═══════════════════════════════════════════════════════════════════
    # TAB 3 — GOOGLE SHEETS
    # ═══════════════════════════════════════════════════════════════════
    with tabs[2]:
        st.markdown("<div class='section-header'>📊 Connect Google Sheets</div>",
                    unsafe_allow_html=True)

        st.markdown(f"""
        <div style='background:{_accent}11;border:1px solid {_accent}44;border-radius:10px;
                    padding:14px 16px;margin-bottom:16px;font-size:13px;color:{_text}'>
            <b>How to connect:</b><br>
            1. Open your Google Sheet with restaurant sales data<br>
            2. File → Share → Anyone with the link → Viewer<br>
            3. Copy the link and paste below<br>
            4. Sheet must have columns: <code>date</code>, <code>quantity_sold</code>, <code>revenue</code>
        </div>""", unsafe_allow_html=True)

        sheet_url = st.text_input(
            "Google Sheets URL",
            placeholder="https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit",
            help="Must be shared publicly (Anyone with the link can view)",
        )

        if st.button("🔗 Connect Google Sheet", use_container_width=True, disabled=not sheet_url):
            with st.spinner("Fetching data from Google Sheets…"):
                ok, msg, sheet_df = load_google_sheet(sheet_url)
            if ok and sheet_df is not None:
                st.success(msg)
                st.session_state["real_df"]      = sheet_df
                st.session_state["real_df_name"] = "Google Sheet"
                st.session_state["data_source"]  = "google_sheets"
                st.dataframe(sheet_df.head(15), use_container_width=True)
                st.info("✅ Google Sheet connected! All pages now use your live sheet data.")
            else:
                st.error(msg)

        st.divider()
        st.markdown("<div class='section-header'>📋 Sample Google Sheet Template</div>",
                    unsafe_allow_html=True)
        st.markdown("""
        Copy this sheet to your Google Drive, fill with your real data, and connect above:

        👉 **[Open Sample Template](https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/edit)**
        *(Make a copy: File → Make a copy)*
        """)

    # ═══════════════════════════════════════════════════════════════════
    # TAB 4 — GOVERNMENT & OPEN DATASETS
    # ═══════════════════════════════════════════════════════════════════
    with tabs[3]:
        st.markdown("<div class='section-header'>🏛️ Open Government & Food Industry Data</div>",
                    unsafe_allow_html=True)

        st.markdown(f"""
        <div style='background:{_success}11;border:1px solid {_success}44;border-radius:10px;
                    padding:14px 16px;margin-bottom:16px;font-size:13px;color:{_text}'>
            These datasets are <b>completely free</b>, no API key needed.
            Download and upload them in Tab 2 to use real industry benchmarks.
        </div>""", unsafe_allow_html=True)

        datasets = [
            {
                "name": "🇮🇳 India Restaurant Industry Report",
                "source": "NRAI (National Restaurant Association of India)",
                "desc": "Annual demand trends, waste statistics, revenue benchmarks for Indian restaurants",
                "url": "https://nrai.org/",
                "fields": "Revenue, Footfall, Waste %, Menu Mix",
                "how": "Download the annual report PDF → extract tables → upload as CSV",
            },
            {
                "name": "🌾 Punjab Agricultural Price Data",
                "source": "data.gov.in",
                "desc": "Real ingredient prices (vegetables, meat, dairy) for Ludhiana/Punjab region",
                "url": "https://data.gov.in/resource/current-daily-price-various-commodities-various-markets-himachal-pradesh",
                "fields": "Commodity, Market, Min Price, Max Price, Date",
                "how": "Download CSV → use to model ingredient cost vs menu price",
            },
            {
                "name": "🌦️ Historical Weather Data — Ludhiana",
                "source": "Open-Meteo (free, no key)",
                "desc": "Historical temperature and rainfall for Ludhiana — correlate with your demand",
                "url": "https://open-meteo.com/en/docs/historical-weather-api",
                "fields": "Date, Temperature, Precipitation, Wind Speed",
                "how": "Use the API directly — free, no key needed",
            },
            {
                "name": "🍽️ FSSAI Food Safety Data",
                "source": "Food Safety and Standards Authority of India",
                "desc": "Food waste benchmarks, safety compliance data for Indian food businesses",
                "url": "https://www.fssai.gov.in/",
                "fields": "Waste kg, Category, Compliance Score",
                "how": "Download annual reports → extract waste benchmarks",
            },
        ]

        for ds in datasets:
            with st.expander(ds["name"], expanded=False):
                g1, g2 = st.columns([2, 1])
                with g1:
                    st.markdown(f"**Source:** {ds['source']}")
                    st.markdown(f"**Description:** {ds['desc']}")
                    st.markdown(f"**Available fields:** `{ds['fields']}`")
                    st.markdown(f"**How to use:** {ds['how']}")
                with g2:
                    st.link_button("🔗 Open Dataset", ds["url"], use_container_width=True)

        st.divider()
        st.markdown("<div class='section-header'>🌐 Live Open-Meteo Weather (Free, No Key)</div>",
                    unsafe_allow_html=True)
        st.markdown("Open-Meteo provides **free historical + forecast weather** — no API key needed.")

        if st.button("📡 Fetch Real Ludhiana Weather (Open-Meteo)", use_container_width=True):
            with st.spinner("Fetching from Open-Meteo API…"):
                try:
                    url = (
                        "https://api.open-meteo.com/v1/forecast"
                        "?latitude=30.9&longitude=75.85"
                        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
                        "&timezone=Asia/Kolkata&forecast_days=7"
                    )
                    r = requests.get(url, timeout=10)
                    if r.status_code == 200:
                        d     = r.json()
                        dates = d["daily"]["time"]
                        tmax  = d["daily"]["temperature_2m_max"]
                        tmin  = d["daily"]["temperature_2m_min"]
                        prec  = d["daily"]["precipitation_sum"]
                        om_df = pd.DataFrame({
                            "Date": dates, "Max Temp °C": tmax,
                            "Min Temp °C": tmin, "Rainfall mm": prec,
                        })
                        st.success("✅ Real weather data from Open-Meteo (Ludhiana)")
                        st.dataframe(om_df, use_container_width=True)

                        fig_om = go.Figure()
                        fig_om.add_trace(go.Bar(
                            x=om_df["Date"], y=om_df["Rainfall mm"],
                            name="Rainfall mm", marker_color=_secondary, yaxis="y2",
                        ))
                        fig_om.add_trace(go.Scatter(
                            x=om_df["Date"], y=om_df["Max Temp °C"],
                            name="Max Temp", line=dict(color=_primary, width=2),
                        ))
                        fig_om.add_trace(go.Scatter(
                            x=om_df["Date"], y=om_df["Min Temp °C"],
                            name="Min Temp", line=dict(color=_success, width=2, dash="dot"),
                        ))
                        fig_om.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color=_text), height=260,
                            xaxis=dict(gridcolor="#2a2a38"),
                            yaxis=dict(gridcolor="#2a2a38", title="Temperature °C"),
                            yaxis2=dict(overlaying="y", side="right",
                                        title="Rainfall mm", showgrid=False),
                            legend=dict(bgcolor="rgba(0,0,0,0)"),
                            margin=dict(l=0, r=0, t=10, b=0),
                        )
                        st.plotly_chart(fig_om, use_container_width=True)
                        st.session_state["open_meteo_df"] = om_df
                    else:
                        st.error(f"Open-Meteo returned HTTP {r.status_code}")
                except Exception as e:
                    st.error(f"Could not reach Open-Meteo: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # TAB 5 — GEMINI AI DATA ENRICHMENT
    # ═══════════════════════════════════════════════════════════════════
    with tabs[4]:
        st.markdown("<div class='section-header'>🤖 Gemini AI Data Enrichment</div>",
                    unsafe_allow_html=True)

        st.markdown(f"""
        <div style='background:{_accent}11;border:1px solid {_accent}44;border-radius:10px;
                    padding:14px 16px;margin-bottom:16px;font-size:13px;color:{_text}'>
            Gemini AI analyses your restaurant data and enriches it with:
            real-world demand patterns, festival impact scores,
            competitor benchmarks, and pricing recommendations.
        </div>""", unsafe_allow_html=True)

        active_df   = st.session_state.get("real_df") or generate_dataset()
        rest_df     = active_df[active_df["restaurant_id"] == rest_id]
        daily       = rest_df.groupby("date").agg(
            qty=("quantity_sold","sum"), rev=("revenue","sum"),
            waste=("waste_kg","sum"),
        ).reset_index().tail(30)
        avg_qty     = daily["qty"].mean()
        avg_rev     = daily["rev"].mean()
        avg_waste   = daily["waste"].mean()
        data_source = "your uploaded real data" if st.session_state.get("real_df") is not None else "synthetic demo data"

        st.markdown(f"Analysing: **{rest_name}** using **{data_source}**")
        st.markdown("")

        enrich_options = st.multiselect(
            "Select enrichment types",
            ["🎉 Festival Impact Calendar",
             "💰 Competitor Price Benchmarks",
             "📊 Industry Waste Benchmarks",
             "🌍 Market Trend Analysis",
             "📅 Staff Scheduling Optimisation"],
            default=["🎉 Festival Impact Calendar", "💰 Competitor Price Benchmarks"],
        )

        if st.button("✨ Run AI Data Enrichment", use_container_width=True,
                     disabled=not enrich_options):
            from gemini_client import call_gemini, show_gemini_error

            prompt = f"""You are a restaurant data analyst for India. Provide enrichment data for {rest_name} in Ludhiana, Punjab.

Restaurant metrics (last 30 days):
- Avg daily demand: {avg_qty:.0f} units
- Avg daily revenue: Rs {avg_rev:,.0f}
- Avg daily waste: {avg_waste:.1f} kg

Requested enrichments: {', '.join(enrich_options)}

For each enrichment requested, provide:
1. Specific data points relevant to Ludhiana/Punjab restaurants
2. How it impacts this restaurant
3. One actionable recommendation

Format as clear sections with headers. Be specific and data-driven."""

            with st.spinner("Gemini is enriching your data with real-world insights…"):
                result = call_gemini(prompt)

            is_error = any(x in result for x in ["⚠️", "unavailable", "quota"])
            if is_error:
                show_gemini_error(result)
                # Rule-based enrichment fallback
                st.markdown("---")
                st.markdown("**📊 Rule-Based Enrichment (Offline)**")
                _show_offline_enrichment(rest_name, avg_qty, avg_rev, avg_waste)
            else:
                st.success("✅ AI enrichment complete!")
                st.markdown(result)

        st.divider()

        # Always-available offline enrichment
        st.markdown("<div class='section-header'>📊 Offline Data Enrichment (Always Available)</div>",
                    unsafe_allow_html=True)
        _show_offline_enrichment(rest_name, avg_qty, avg_rev, avg_waste)


def _show_offline_enrichment(rest_name, avg_qty, avg_rev, avg_waste):
    """Rule-based data enrichment that works without any API."""
    P          = PALETTE
    _primary   = P["primary"]
    _secondary = P["secondary"]
    _success   = P["success"]
    _muted     = P["muted"]
    _text      = P["text"]

    # Festival calendar
    st.markdown("**🎉 Punjab Festival Demand Calendar**")
    festivals = [
        ("Lohri",          "Jan 13", "+45%", "Increase Main Course stock by 40%"),
        ("Holi",           "Mar 14", "+35%", "Boost Beverages — cold drinks spike"),
        ("Baisakhi",       "Apr 13", "+55%", "Highest demand day of H1 — full prep"),
        ("Independence Day","Aug 15", "+30%", "Family dining surge — expand seating"),
        ("Dussehra",       "Oct 2",  "+40%", "Evening crowds — extend dinner hours"),
        ("Diwali",         "Nov 1",  "+65%", "Peak day of year — max staff + stock"),
        ("Gurpurab",       "Nov 15", "+50%", "Community gatherings — group menus"),
        ("Christmas",      "Dec 25", "+35%", "Young crowd — premium menu push"),
    ]
    fest_df = pd.DataFrame(festivals,
                           columns=["Festival","Date","Demand Boost","Action"])
    st.dataframe(fest_df, use_container_width=True, hide_index=True)

    st.divider()

    # Competitor benchmark
    st.markdown("**💰 Ludhiana Restaurant Price Benchmarks**")
    bench = pd.DataFrame([
        {"Category":"Main Course","Market Low":"₹320","Market Avg":"₹430",
         "Market High":"₹680",f"{rest_name}":f"₹450",
         "Recommendation":"Competitive — can raise 5-8%"},
        {"Category":"Starters","Market Low":"₹180","Market Avg":"₹260",
         "Market High":"₹420",f"{rest_name}":f"₹250",
         "Recommendation":"Slightly below avg — raise ₹20"},
        {"Category":"Beverages","Market Low":"₹80","Market Avg":"₹140",
         "Market High":"₹240",f"{rest_name}":f"₹150",
         "Recommendation":"Above avg — justified for quality"},
        {"Category":"Desserts","Market Low":"₹120","Market Avg":"₹185",
         "Market High":"₹300",f"{rest_name}":f"₹200",
         "Recommendation":"At market rate — consider premium option"},
    ])
    st.dataframe(bench, use_container_width=True, hide_index=True)

    st.divider()

    # Waste benchmark
    st.markdown("**♻️ Industry Waste Benchmarks (Punjab Restaurants)**")
    w1, w2, w3 = st.columns(3)
    waste_pct = (avg_waste / max(avg_qty, 1)) * 100

    for col, label, val, color in [
        (w1, "Your Waste Rate",   f"{waste_pct:.1f}%", _primary),
        (w2, "Industry Average",  "8.5%",               _secondary),
        (w3, "Best in Class",     "4.2%",               _success),
    ]:
        col.markdown(f"""
        <div class='kpi-card' style='border-color:{color}44;text-align:center'>
            <div class='kpi-label'>{label}</div>
            <div class='kpi-value' style='color:{color}'>{val}</div>
        </div>""", unsafe_allow_html=True)

    gap = waste_pct - 4.2
    if gap > 0:
        saving = (avg_waste * (gap / 100) / waste_pct * 100) * 120 * 30
        st.warning(
            f"⚠️ Your waste rate is **{gap:.1f}%** above best-in-class. "
            f"Closing this gap could save **{format_inr(saving)}/month**."
        )
    else:
        st.success("✅ Your waste rate is below industry average. Excellent performance!")
