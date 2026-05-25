"""Customer Sentiment Analysis view for IntelliPredict."""

import streamlit as st
from gemini_client import call_gemini, call_gemini_json, gemini_quota_warning, show_gemini_error
import pandas as pd
import json
import requests
import re
import plotly.graph_objects as go
import plotly.express as px
from config import PALETTE
from data_generator import CATEGORIES

P = PALETTE
_accent = P["accent"]
_danger = P["danger"]
_muted = P["muted"]
_primary = P["primary"]
_secondary = P["secondary"]
_success = P["success"]
_text = P["text"]

SAMPLE_REVIEWS = """The biryani was absolutely divine! Perfectly spiced and the portions were generous. However, the service was a bit slow - we waited 25 minutes for our order. The ambiance is great though.

The starters were mediocre - the paneer tikka was dry and overpriced at ₹350. Main course was better, the dal makhani is the best I've had. Desserts were average. Overall a 3/5 experience.

Love this place! Fast service, friendly staff. The beverages menu is excellent - their mango lassi is outstanding. Prices are very reasonable for the quality. Will definitely come back!

Absolutely terrible experience. Waited 45 minutes for food that arrived cold. The pasta was undercooked and the pizza was soggy. Staff was rude when we complained. Never coming back.

The food quality has gone down compared to last year. Starters used to be amazing but now the quantity has reduced and taste is not the same. Main course is still good. Service is prompt.

Amazing ambiance and excellent food! The chef's special main course was phenomenal. Desserts section needs improvement though - limited options and a bit pricey. Beverages are top notch!"""


def call_gemini_sentiment(reviews_text: str, rest_name: str, api_key: str) -> dict:
    """Analyse sentiment with Gemini and return structured results."""
    prompt = f"""You are a restaurant analytics expert. Analyze these customer reviews for {rest_name} and return ONLY valid JSON.

Reviews:
{reviews_text}

Return this exact JSON (no markdown, no extra text):
{{
  "overall_score": <float 1-5>,
  "total_reviews": <int>,
  "sentiment_breakdown": {{
    "positive": <percentage int>,
    "neutral": <percentage int>,
    "negative": <percentage int>
  }},
  "category_scores": {{
    "Food Quality": <float 1-5>,
    "Service": <float 1-5>,
    "Pricing": <float 1-5>,
    "Ambiance": <float 1-5>,
    "Beverages": <float 1-5>
  }},
  "top_positives": ["<point1>", "<point2>", "<point3>"],
  "top_negatives": ["<point1>", "<point2>", "<point3>"],
  "menu_insights": {{
    "Main Course": "<brief insight>",
    "Starters": "<brief insight>",
    "Beverages": "<brief insight>",
    "Desserts": "<brief insight>"
  }},
  "urgent_actions": ["<action1>", "<action2>", "<action3>"],
  "summary": "<2 sentence executive summary>"
}}"""

    from gemini_client import call_gemini_json
    return call_gemini_json(prompt)


def _star_html(score: float, color: str) -> str:
    full  = int(score)
    half  = 1 if score - full >= 0.5 else 0
    empty = 5 - full - half
    stars = "★" * full + ("½" if half else "") + "☆" * empty
    return f"<span style='color:{color};font-size:18px'>{stars}</span> <b style='color:{color}'>{score:.1f}/5</b>"


def render_sentiment(df, rest_id: str, rest_name: str):
    st.markdown("# 🎯 Customer Sentiment Analysis")
    st.markdown(f"<small style='color:{_muted}'>Paste Google/Zomato/Swiggy reviews → Gemini analyses sentiment by category for <b>{rest_name}</b></small>", unsafe_allow_html=True)
    st.divider()

    # ── Input ─────────────────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>📝 Paste Customer Reviews</div>", unsafe_allow_html=True)

    col_input, col_tip = st.columns([2, 1])
    with col_input:
        reviews = st.text_area(
            "One review per paragraph (paste from Google Maps, Zomato, Swiggy, etc.)",
            value=SAMPLE_REVIEWS,
            height=200,
            placeholder="Paste customer reviews here...",
        )
    with col_tip:
        st.markdown(f"""
        <div style='background:#1A1A24;border:1px solid #2a2a3a;border-radius:10px;padding:16px'>
            <div style='font-size:12px;font-weight:700;color:{_primary};margin-bottom:10px'>💡 How to get reviews</div>
            <div style='font-size:12px;color:{_muted};line-height:1.8'>
                <b style='color:{_text}'>Google Maps:</b><br>Search restaurant → Reviews tab → Copy<br><br>
                <b style='color:{_text}'>Zomato:</b><br>Restaurant page → Reviews → Copy text<br><br>
                <b style='color:{_text}'>Swiggy:</b><br>Restaurant → Ratings & Reviews → Copy
            </div>
        </div>""", unsafe_allow_html=True)

    run = st.button("🎯 Analyse Sentiment with Gemini", use_container_width=True)

    if not run:
        return

    api_key = ""
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        pass

    if not api_key:
        st.error("❌ GEMINI_API_KEY not set in Streamlit Secrets.")
        return

    if not reviews.strip():
        st.error("Please paste some reviews first.")
        return

    with st.spinner("🧠 Gemini is reading and analysing customer reviews…"):
        result, err = call_gemini_sentiment(reviews, rest_name, api_key)

    if err:
        show_gemini_error(err)
        return

    if not result:
        st.error("Could not parse Gemini response. Try again.")
        return

    st.success("✅ Sentiment analysis complete!")
    st.divider()

    # ── Overall score ─────────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>⭐ Overall Sentiment Score</div>", unsafe_allow_html=True)

    score  = result.get("overall_score", 3.0)
    pos    = result.get("sentiment_breakdown", {}).get("positive", 60)
    neu    = result.get("sentiment_breakdown", {}).get("neutral",  20)
    neg    = result.get("sentiment_breakdown", {}).get("negative", 20)
    total  = result.get("total_reviews", len(reviews.strip().split("\n\n")))

    score_color = _success if score >= 4 else (_secondary if score >= 3 else _danger)

    h1, h2, h3, h4 = st.columns(4)
    h1.markdown(f"""<div class='kpi-card'>
        <div class='kpi-label'>Overall Score</div>
        <div class='kpi-value' style='color:{score_color};font-size:2rem'>{score:.1f}/5</div>
        <div style='font-size:14px'>{_star_html(score, score_color)}</div>
    </div>""", unsafe_allow_html=True)
    h2.markdown(f"""<div class='kpi-card'>
        <div class='kpi-label'>Positive Reviews</div>
        <div class='kpi-value' style='color:{_success}'>{pos}%</div>
    </div>""", unsafe_allow_html=True)
    h3.markdown(f"""<div class='kpi-card'>
        <div class='kpi-label'>Neutral Reviews</div>
        <div class='kpi-value' style='color:{_muted}'>{neu}%</div>
    </div>""", unsafe_allow_html=True)
    h4.markdown(f"""<div class='kpi-card'>
        <div class='kpi-label'>Negative Reviews</div>
        <div class='kpi-value' style='color:{_danger}'>{neg}%</div>
    </div>""", unsafe_allow_html=True)

    # Summary
    if result.get("summary"):
        st.markdown(f"""
        <div style='background:#1A1A24;border:1px solid {_primary}44;border-left:4px solid {_primary};
                    border-radius:10px;padding:16px;margin:16px 0'>
            <div style='font-size:12px;color:{_primary};font-weight:700;margin-bottom:6px'>📋 EXECUTIVE SUMMARY</div>
            <div style='font-size:14px;color:{_text};line-height:1.7'>{result["summary"]}</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ── Category scores ───────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>📊 Score by Category</div>", unsafe_allow_html=True)

    cat_scores = result.get("category_scores", {})
    if cat_scores:
        chart_col, detail_col = st.columns([1, 1])

        with chart_col:
            cats  = list(cat_scores.keys())
            vals  = list(cat_scores.values())
            colors_radar = [_success if v >= 4 else (_secondary if v >= 3 else _danger) for v in vals]

            fig_radar = go.Figure(go.Scatterpolar(
                r=vals + [vals[0]],
                theta=cats + [cats[0]],
                fill="toself",
                fillcolor="rgba(255,107,53,0.15)",
                line=dict(color=_primary, width=2),
                marker=dict(color=_primary, size=6),
            ))
            fig_radar.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 5], gridcolor="#2a2a38", color=_muted),
                    angularaxis=dict(gridcolor="#2a2a38", color=_text),
                    bgcolor="rgba(0,0,0,0)",
                ),
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color=_text),
                margin=dict(l=20, r=20, t=20, b=20),
                height=300,
            )
            st.plotly_chart(fig_radar, use_container_width=True)

        with detail_col:
            for cat, val in cat_scores.items():
                c = _success if val >= 4 else (_secondary if val >= 3 else _danger)
                bar_w = int(val / 5 * 100)
                st.markdown(f"""
                <div style='margin-bottom:14px'>
                    <div style='display:flex;justify-content:space-between;margin-bottom:4px'>
                        <span style='font-size:13px;color:{_text};font-weight:600'>{cat}</span>
                        <span style='color:{c};font-weight:700'>{val}/5</span>
                    </div>
                    <div style='background:#0F0F13;border-radius:4px;height:8px'>
                        <div style='height:8px;width:{bar_w}%;background:{c};border-radius:4px'></div>
                    </div>
                </div>""", unsafe_allow_html=True)

    st.divider()

    # ── Positives & Negatives ─────────────────────────────────────────────────
    pos_col, neg_col = st.columns(2)
    with pos_col:
        st.markdown("<div class='section-header'>✅ What Customers Love</div>", unsafe_allow_html=True)
        for pt in result.get("top_positives", []):
            st.markdown(f"""
            <div style='background:#0f2a26;border:1px solid {_success}44;border-radius:8px;
                        padding:10px 14px;margin-bottom:8px;font-size:13px;color:{_text}'>
                ✅ {pt}
            </div>""", unsafe_allow_html=True)

    with neg_col:
        st.markdown("<div class='section-header'>⚠️ What Needs Improvement</div>", unsafe_allow_html=True)
        for pt in result.get("top_negatives", []):
            st.markdown(f"""
            <div style='background:#2a0f12;border:1px solid {_danger}44;border-radius:8px;
                        padding:10px 14px;margin-bottom:8px;font-size:13px;color:{_text}'>
                ⚠️ {pt}
            </div>""", unsafe_allow_html=True)

    st.divider()

    # ── Menu insights ─────────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>🍽️ Menu Category Insights</div>", unsafe_allow_html=True)
    menu_ins = result.get("menu_insights", {})
    mcols    = st.columns(4)
    mcolors  = [_primary, _secondary, _success, _accent]
    for i, cat in enumerate(CATEGORIES):
        insight = menu_ins.get(cat, "No specific feedback found.")
        mcols[i].markdown(f"""
        <div class='kpi-card' style='text-align:left;border-color:{mcolors[i]}44'>
            <div style='font-size:11px;color:{mcolors[i]};font-weight:700;margin-bottom:6px;text-transform:uppercase'>{cat}</div>
            <div style='font-size:12px;color:{_text};line-height:1.6'>{insight}</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ── Urgent actions ────────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>🚨 Urgent Actions Required</div>", unsafe_allow_html=True)
    for i, action in enumerate(result.get("urgent_actions", []), 1):
        st.markdown(f"""
        <div style='background:#1A1A24;border:1px solid {_secondary}44;border-left:4px solid {_secondary};
                    border-radius:8px;padding:12px 16px;margin-bottom:8px;
                    display:flex;align-items:center;gap:12px'>
            <span style='font-size:16px;font-weight:700;color:{_secondary};min-width:24px'>{i}.</span>
            <span style='font-size:13px;color:{_text}'>{action}</span>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ── Sentiment pie ─────────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>🥧 Sentiment Distribution</div>", unsafe_allow_html=True)
    fig_pie = go.Figure(go.Pie(
        labels=["Positive", "Neutral", "Negative"],
        values=[pos, neu, neg],
        hole=0.5,
        marker=dict(colors=[_success, _muted, _danger]),
        textinfo="label+percent",
        textfont=dict(color=_text),
    ))
    fig_pie.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=_text),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=0, r=0, t=10, b=0),
        height=280,
    )
    st.plotly_chart(fig_pie, use_container_width=True)
