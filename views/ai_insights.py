"""AI Insights view — Gemini-powered prediction analysis for IntelliPredict."""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from gemini_client import call_gemini, call_gemini_json, gemini_quota_warning, show_gemini_error
from config import PALETTE
from data_generator import CATEGORIES, PRICE_MAP
from utils import format_inr
P = PALETTE
_P_danger = P["danger"]
_P_primary = P["primary"]
_P_secondary = P["secondary"]
_P_success = P["success"]
_P_muted = P["muted"]
_P_text = P["text"]
_P_accent = P.get("accent", "#FFBF69")


def _rule_based_answer(query: str, rest_name: str, avg_qty: float,
                       avg_waste: float, avg_rev: float,
                       last7_rev: float, avg_cov: float) -> str:
    """Intelligent rule-based answers when Gemini API is unavailable."""
    q = query.lower()

    # Stock / inventory questions
    if any(w in q for w in ["stock", "inventory", "order", "procure", "buy"]):
        rec_stock = avg_qty * 1.2
        return (
            f"📦 **Stock Recommendation for {rest_name}:** "
            f"Based on your avg daily demand of {avg_qty:.0f} units, "
            f"maintain a stock level of **{rec_stock:.0f} units** (1.2× coverage). "
            f"Your current coverage is {avg_cov:.1f}×. "
            f"{'Reduce orders by ~15% to avoid over-stocking.' if avg_cov > 1.4 else 'Stock levels are healthy — maintain current procurement.'}"
        )

    # Waste questions
    if any(w in q for w in ["waste", "spoil", "reduce waste", "wastage"]):
        target = avg_waste * 0.8
        saving = (avg_waste - target) * 120 * 7
        return (
            f"♻️ **Waste Reduction for {rest_name}:** "
            f"Current avg waste is **{avg_waste:.1f} kg/day**. "
            f"To cut waste by 20%, target **{target:.1f} kg/day** by reducing "
            f"Starters and Main Course batch sizes on Mon–Wed (slowest days). "
            f"Estimated saving: **Rs {saving:,.0f}/week**."
        )

    # Weekend / busy days
    if any(w in q for w in ["weekend", "busy", "peak", "saturday", "sunday"]):
        weekend_demand = avg_qty * 1.35
        return (
            f"📅 **Weekend Planning for {rest_name}:** "
            f"Weekends drive ~35% more demand. "
            f"Expected Saturday/Sunday demand: **{weekend_demand:.0f} units/day** "
            f"vs weekday avg of {avg_qty:.0f}. "
            f"Recommend increasing Main Course prep by 30% and scheduling "
            f"2 extra staff on Sat–Sun evenings."
        )

    # Revenue / pricing
    if any(w in q for w in ["revenue", "price", "profit", "earn", "income", "sales"]):
        weekly_target = last7_rev * 1.1
        return (
            f"💰 **Revenue Insights for {rest_name}:** "
            f"Last 7-day revenue: **Rs {last7_rev:,.0f}**. "
            f"To grow 10%, target **Rs {weekly_target:,.0f}** next week. "
            f"Best lever: increase Main Course price by 8–10% (elasticity −0.4 "
            f"means demand drops only ~4%, net revenue rises ~6%)."
        )

    # Forecast / prediction
    if any(w in q for w in ["forecast", "predict", "next week", "tomorrow", "future"]):
        pred_7d = avg_qty * 7 * 1.05
        return (
            f"📈 **Demand Forecast for {rest_name}:** "
            f"Based on 30-day trend, next 7-day predicted demand: "
            f"**{pred_7d:.0f} units** (+5% momentum). "
            f"Weekend days will spike to ~{avg_qty * 1.35:.0f} units. "
            f"Recommend stocking 1.2× predicted demand to avoid stockouts."
        )

    # Staff / staffing
    if any(w in q for w in ["staff", "employ", "worker", "team", "schedule"]):
        return (
            f"👥 **Staffing for {rest_name}:** "
            f"With avg daily demand of {avg_qty:.0f} units, recommend "
            f"**4–5 staff on weekdays** and **6–7 on weekends** (35% demand spike). "
            f"Schedule extra coverage 12–2 PM (lunch rush) and 7–9 PM (dinner rush) "
            f"— these slots drive 60–70% of daily revenue."
        )

    # Default / general
    return (
        f"🍽️ **{rest_name} Summary:** "
        f"Avg daily demand **{avg_qty:.0f} units**, "
        f"revenue **Rs {avg_rev:,.0f}/day**, "
        f"waste **{avg_waste:.1f} kg/day**, "
        f"stock coverage **{avg_cov:.1f}×**. "
        f"Top action: {'Reduce procurement by 10% — overstocked.' if avg_cov > 1.4 else 'Demand is stable. Focus on weekend upselling to grow revenue.'}"
    )


def render_ai_insights(df: pd.DataFrame, rest_id: str, rest_name: str):
    """Renders the AI Insights page with Gemini-powered predictions."""

    st.markdown("# 🤖 AI Prediction & Insights")
    st.markdown(
        f"<small style='color:#8A8696'>Gemini-powered demand analysis for <b>{rest_name}</b></small>",
        unsafe_allow_html=True,
    )
    st.divider()

    rest_df = df[df["restaurant_id"] == rest_id].copy()
    recent_30 = rest_df.sort_values("date").tail(30 * len(CATEGORIES))
    daily = recent_30.groupby("date").agg(
        qty=("quantity_sold", "sum"),
        waste=("waste_kg", "sum"),
        revenue=("revenue", "sum"),
        stock=("stock_level", "sum"),
    ).reset_index().tail(30)

    avg_qty   = daily["qty"].mean()
    avg_waste = daily["waste"].mean()
    avg_rev   = daily["revenue"].mean()
    last7_rev = daily["revenue"].tail(7).sum()
    prev7_rev = daily["revenue"].iloc[-14:-7].sum()
    peak_day  = daily.loc[daily["qty"].idxmax(), "date"]
    avg_cov   = (daily["stock"].mean() / daily["qty"].mean()) if daily["qty"].mean() > 0 else 0

    # ── Quick KPIs ────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    for col, label, val, color in [
        (c1, "Avg Daily Demand",  f"{avg_qty:.0f} units", _P_primary),
        (c2, "Avg Daily Waste",   f"{avg_waste:.1f} kg",  _P_danger),
        (c3, "Avg Daily Revenue", format_inr(avg_rev),    PALETTE["secondary"]),
        (c4, "Peak Demand Day",   str(peak_day)[:10],     PALETTE["accent"]),
    ]:
        col.markdown(f"""
        <div class='kpi-card'>
            <div class='kpi-label'>{label}</div>
            <div class='kpi-value' style='color:{color};font-size:1.3rem'>{val}</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ── Full AI Prediction ────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>⚡ Full AI Prediction Analysis</div>", unsafe_allow_html=True)
    st.markdown(
        "<small style='color:#8A8696'>Gemini analyses your restaurant data and returns structured predictions.</small>",
        unsafe_allow_html=True,
    )

    run_pred = st.button("🤖 Run AI Prediction (Gemini)", use_container_width=True)

    if run_pred:
        prompt = f"""You are an expert restaurant analytics AI. Analyze this data and return ONLY valid JSON (no markdown, no preamble, no explanation):

Restaurant: {rest_name}
Avg daily demand (30d): {avg_qty:.0f} units
Avg daily waste: {avg_waste:.1f} kg
Avg daily revenue: Rs {avg_rev:.0f}
Last 7-day revenue: Rs {last7_rev:.0f}
Previous 7-day revenue: Rs {prev7_rev:.0f}
Peak demand day: {peak_day}
Categories: {', '.join(CATEGORIES)}

Return ONLY this exact JSON structure with no extra text:
{{
  "demand_next_7d": <integer>,
  "demand_next_30d": <integer>,
  "waste_reduction_potential": "<percentage string like 12-15%>",
  "revenue_growth_opportunity": "<percentage string like 8-11%>",
  "top_risk": "<one sentence>",
  "top_opportunity": "<one sentence>",
  "recommended_stock_adjustment": "<e.g. +10% Main Course, -5% Desserts>",
  "predicted_busy_days": ["<day1>", "<day2>"],
  "category_insights": {{
    "Main Course": "<brief insight>",
    "Starters": "<brief insight>",
    "Beverages": "<brief insight>",
    "Desserts": "<brief insight>"
  }},
  "summary": "<2 sentence executive summary>"
}}"""

        with st.spinner("🧠 Gemini is analysing demand patterns, waste factors & revenue opportunities…"):
            result, err = call_gemini_json(prompt)

        if err:
            if any(x in err.lower() for x in ["quota", "unavailable", "exhausted", "network_error", "timeout", "no_key"]):
                st.warning("⏳ Gemini quota reached — showing rule-based prediction instead.")
                # Rule-based prediction fallback
                result = {
                    "demand_next_7d": int(avg_qty * 7 * 1.05),
                    "demand_next_30d": int(avg_qty * 30 * 1.08),
                    "waste_reduction_potential": "12-18%",
                    "revenue_growth_opportunity": "8-12%",
                    "top_risk": f"Weekend demand spikes may strain stock if coverage drops below 1.2×.",
                    "top_opportunity": f"Festival season approaching — increase Main Course prep by 25-30%.",
                    "recommended_stock_adjustment": "+12% Main Course, -8% Desserts",
                    "predicted_busy_days": ["Saturday", "Sunday"],
                    "category_insights": {
                        "Main Course": f"Highest revenue driver at Rs {avg_rev*0.35:,.0f}/day avg. Maintain 1.3× stock.",
                        "Starters": f"Avg waste {avg_waste*0.28:.1f} kg/day — reduce batch by 10% on Mon-Wed.",
                        "Beverages": "Stable demand. Weekend spike +40%. Pre-stock cold drinks in summer.",
                        "Desserts": "Low volume. Batch-cook daily to avoid spoilage.",
                    },
                    "summary": (
                        f"{rest_name} shows stable demand at {avg_qty:.0f} units/day with "
                        f"Rs {avg_rev:,.0f} daily revenue. "
                        f"Focus on waste reduction and weekend capacity planning for optimal profitability."
                    ),
                }
                err = None
            else:
                show_gemini_error(err)
        if not err and result:
            st.success("✅ AI Prediction complete!")
            st.divider()

            p1, p2, p3, p4 = st.columns(4)
            for col, label, val, color in [
                (p1, "Predicted Demand (7d)",    f"{result.get('demand_next_7d', '–'):,}" if isinstance(result.get('demand_next_7d'), int) else "–", _P_primary),
                (p2, "Predicted Demand (30d)",   f"{result.get('demand_next_30d', '–'):,}" if isinstance(result.get('demand_next_30d'), int) else "–", _P_secondary),
                (p3, "Waste Reduction Potential", result.get("waste_reduction_potential", "–"), PALETTE["success"]),
                (p4, "Revenue Growth Opp.",       result.get("revenue_growth_opportunity", "–"), PALETTE["accent"]),
            ]:
                col.markdown(f"""
                <div class='kpi-card' style='border-color:{color}44'>
                    <div class='kpi-label'>{label}</div>
                    <div class='kpi-value' style='color:{color};font-size:1.4rem'>{val}</div>
                </div>""", unsafe_allow_html=True)

            st.divider()

            r_col, o_col = st.columns(2)
            with r_col:
                st.markdown(f"""
                <div class='kpi-card' style='border-color:{PALETTE["danger"]}44;text-align:left'>
                    <div class='kpi-label' style='color:{PALETTE["danger"]}'>⚠️ Top Risk</div>
                    <div style='font-size:14px;color:{PALETTE["text"]};margin-top:8px;line-height:1.6'>
                        {result.get("top_risk", "–")}
                    </div>
                </div>""", unsafe_allow_html=True)
            with o_col:
                st.markdown(f"""
                <div class='kpi-card' style='border-color:{PALETTE["success"]}44;text-align:left'>
                    <div class='kpi-label' style='color:{PALETTE["success"]}'>🚀 Top Opportunity</div>
                    <div style='font-size:14px;color:{PALETTE["text"]};margin-top:8px;line-height:1.6'>
                        {result.get("top_opportunity", "–")}
                    </div>
                </div>""", unsafe_allow_html=True)

            st.divider()

            s_col, b_col = st.columns(2)
            with s_col:
                st.markdown("<div class='section-header'>📦 Stock Adjustment</div>", unsafe_allow_html=True)
                st.markdown(f"""
                <div class='kpi-card' style='text-align:left'>
                    <div style='font-size:20px;font-weight:700;color:{PALETTE["secondary"]}'>
                        {result.get("recommended_stock_adjustment", "–")}
                    </div>
                    <div style='font-size:12px;color:{PALETTE["muted"]};margin-top:6px'>recommended adjustment</div>
                </div>""", unsafe_allow_html=True)
            with b_col:
                st.markdown("<div class='section-header'>📅 Predicted Busy Days</div>", unsafe_allow_html=True)
                busy = result.get("predicted_busy_days", [])
                pp = PALETTE["primary"]
                badges = "".join(
                    f"<span style='background:{pp}22;color:{pp};border:1px solid {pp}44;border-radius:6px;padding:4px 14px;margin:4px;display:inline-block;font-weight:600'>{d}</span>"
                    for d in busy
                )
                st.markdown(f"<div style='margin-top:8px'>{badges}</div>", unsafe_allow_html=True)

            st.divider()
            st.markdown("<div class='section-header'>🍽️ Category Insights</div>", unsafe_allow_html=True)
            cat_insights = result.get("category_insights", {})
            cols = st.columns(len(CATEGORIES))
            colors = [PALETTE["primary"], PALETTE["secondary"], PALETTE["success"], PALETTE["accent"]]
            for i, cat in enumerate(CATEGORIES):
                insight = cat_insights.get(cat, "No insight available.")
                cols[i].markdown(f"""
                <div class='kpi-card' style='border-color:{colors[i]}44;text-align:left'>
                    <div class='kpi-label' style='color:{colors[i]}'>{cat}</div>
                    <div style='font-size:12px;color:{PALETTE["text"]};margin-top:6px;line-height:1.6'>{insight}</div>
                </div>""", unsafe_allow_html=True)

            if result.get("summary"):
                st.divider()
                st.markdown("<div class='section-header'>📋 Executive Summary</div>", unsafe_allow_html=True)
                st.info(result["summary"])
        else:
            st.warning("⚠️ Gemini returned an empty response. Please wait 60 seconds and try again.")

    st.divider()

    # ── Conversational Chatbot ────────────────────────────────────────────────
    st.markdown("<div class='section-header'>💬 Ask Gemini About Your Restaurant</div>", unsafe_allow_html=True)
    st.markdown(
        "<small style='color:#8A8696'>Ask any question about demand, inventory, pricing, or strategy.</small>",
        unsafe_allow_html=True,
    )

    if "ai_chat_history" not in st.session_state:
        st.session_state["ai_chat_history"] = []

    for msg in st.session_state["ai_chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    suggestions = [
        "What should I stock more of this weekend?",
        "How can I reduce waste by 20%?",
        "Best price for Main Course?",
        "Predict demand for next festival weekend.",
        "Which category has highest revenue potential?",
    ]
    st.markdown("<small style='color:#8A8696'>Suggested:</small>", unsafe_allow_html=True)
    sug_cols = st.columns(len(suggestions))
    for i, sug in enumerate(suggestions):
        if sug_cols[i].button(sug, key=f"sug_{i}", use_container_width=True):
            st.session_state["pending_query"] = sug
            st.rerun()

    user_input = st.chat_input("Ask Gemini anything about your restaurant…")
    if "pending_query" in st.session_state:
        user_input = st.session_state.pop("pending_query")

    if user_input:
        context = f"""Restaurant: {rest_name}
Avg daily demand: {avg_qty:.0f} units
Avg daily waste: {avg_waste:.1f} kg
Avg daily revenue: Rs {avg_rev:.0f}
Last 7-day revenue: Rs {last7_rev:.0f}
Categories: {', '.join(CATEGORIES)}"""

        st.session_state["ai_chat_history"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                full_prompt = f"""You are an expert restaurant analytics assistant for {rest_name}.
Context:
{context}

Question: {user_input}

Respond in 3-4 sentences max with actionable, data-driven insights. Use Rs for currency."""
                response = call_gemini(full_prompt)

            # If Gemini unavailable, use rule-based fallback
            if any(x in response for x in ["unavailable", "quota", "⚠️"]):
                response = _rule_based_answer(
                    user_input, rest_name, avg_qty, avg_waste,
                    avg_rev, last7_rev, avg_cov
                )

            st.markdown(response)
            st.session_state["ai_chat_history"].append({"role": "assistant", "content": response})

    if st.session_state.get("ai_chat_history"):
        if st.button("🗑️ Clear Chat History"):
            st.session_state["ai_chat_history"] = []
            st.rerun()

    st.divider()

    # ── Auto-Generated Insights ───────────────────────────────────────────────
    st.markdown("<div class='section-header'>📊 Auto-Generated Insights</div>", unsafe_allow_html=True)

    recent7  = daily.tail(7)
    prev7    = daily.iloc[-14:-7]
    d_demand = int(recent7["qty"].sum() - prev7["qty"].sum())
    d_waste  = round(recent7["waste"].sum() - prev7["waste"].sum(), 1)
    d_rev    = recent7["revenue"].sum() - prev7["revenue"].sum()

    insights = [
        {
            "icon": "📈" if d_demand > 0 else "📉",
            "title": "Demand Trend",
            "body": f"Demand {'rose' if d_demand > 0 else 'fell'} by {abs(d_demand)} units vs last week. {'Consider boosting prep by 15%.' if d_demand > 0 else 'Reduce stock orders to cut waste.'}",
            "badge": f"{'▲' if d_demand > 0 else '▼'} {abs(d_demand)} units",
            "color": PALETTE["success"] if d_demand > 0 else PALETTE["danger"],
        },
        {
            "icon": "♻️",
            "title": "Waste Alert",
            "body": f"Avg daily waste: {avg_waste:.1f} kg. {'⚠️ High — reduce Starters prep by 10%.' if avg_waste > 20 else '✅ Healthy waste levels. Procurement is optimal.'}",
            "badge": f"{avg_waste:.1f} kg/day",
            "color": PALETTE["danger"] if avg_waste > 20 else PALETTE["success"],
        },
        {
            "icon": "💰",
            "title": "Revenue Momentum",
            "body": f"Last 7-day revenue: {format_inr(last7_rev)}. {'Up' if d_rev > 0 else 'Down'} {format_inr(abs(d_rev))} vs previous week. Peak day was {str(peak_day)[:10]}.",
            "badge": f"{'▲' if d_rev > 0 else '▼'} {format_inr(abs(d_rev))}",
            "color": PALETTE["success"] if d_rev > 0 else PALETTE["danger"],
        },
        {
            "icon": "📦",
            "title": "Stock Coverage",
            "body": f"Average stock/demand ratio: {avg_cov:.1f}x. {'Overstocked — risk of spoilage. Reduce orders.' if avg_cov > 1.5 else 'Coverage optimal. Maintain current procurement rhythm.'}",
            "badge": f"{avg_cov:.1f}x coverage",
            "color": PALETTE["secondary"] if avg_cov > 1.5 else PALETTE["success"],
        },
    ]

    cols = st.columns(2)
    for i, ins in enumerate(insights):
        with cols[i % 2]:
            st.markdown(f"""
            <div class='kpi-card' style='text-align:left;margin-bottom:16px;border-color:{ins["color"]}44'>
                <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>
                    <span style='font-size:20px'>{ins["icon"]}</span>
                    <span style='background:{ins["color"]}22;color:{ins["color"]};border:1px solid {ins["color"]}44;border-radius:5px;padding:2px 10px;font-size:11px;font-weight:700'>{ins["badge"]}</span>
                </div>
                <div style='font-weight:700;font-size:14px;color:{PALETTE["text"]};margin-bottom:6px'>{ins["title"]}</div>
                <div style='font-size:12px;color:{PALETTE["muted"]};line-height:1.6'>{ins["body"]}</div>
            </div>""", unsafe_allow_html=True)
