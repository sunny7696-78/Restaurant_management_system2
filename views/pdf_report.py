"""PDF Report Generator view for IntelliPredict."""

import streamlit as st
import pandas as pd
import io
from datetime import datetime
from config import PALETTE
from utils import format_inr
from data_generator import RESTAURANTS, CATEGORIES, PRICE_MAP

P = PALETTE
PC = {k: v for k, v in P.items()}

def render_pdf_report(df: pd.DataFrame, rest_id: str, rest_name: str):
    st.markdown("# 📊 Executive PDF Report")
    st.markdown(f"<small style='color:{P['muted']}'>One-click professional report with charts, KPIs & AI recommendations</small>", unsafe_allow_html=True)
    st.divider()

    c1, c2, c3 = st.columns(3)
    report_type = c1.selectbox("Report Type", ["Weekly", "Monthly", "Quarterly"])
    include_ai  = c2.checkbox("Include AI Summary (Gemini)", value=True)
    all_rests   = c3.checkbox("Include All Restaurants", value=False)

    st.divider()

    # Preview KPIs
    rest_df = df[df["restaurant_id"] == rest_id]
    today   = rest_df["date"].max()
    last7   = rest_df[rest_df["date"] >= today - pd.Timedelta(days=7)]
    prev7   = rest_df[(rest_df["date"] >= today - pd.Timedelta(days=14)) & (rest_df["date"] < today - pd.Timedelta(days=7))]

    qty7    = int(last7["quantity_sold"].sum())
    rev7    = last7["revenue"].sum()
    waste7  = round(last7["waste_kg"].sum(), 1)
    cov     = round(last7["stock_level"].mean() / last7["quantity_sold"].mean(), 1) if last7["quantity_sold"].mean() > 0 else 0
    d_qty   = qty7 - int(prev7["quantity_sold"].sum())
    d_rev   = rev7 - prev7["revenue"].sum()

    st.markdown("<div class='section-header'>📋 Report Preview</div>", unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    for col, lbl, val, d, good in [
        (k1, "Units Sold (7d)", f"{qty7:,}", f"{'▲' if d_qty>=0 else '▼'} {abs(d_qty)}", d_qty>=0),
        (k2, "Revenue (7d)",    format_inr(rev7), f"{'▲' if d_rev>=0 else '▼'} {format_inr(abs(d_rev))}", d_rev>=0),
        (k3, "Waste (7d)",      f"{waste7} kg", "vs last week", True),
        (k4, "Stock Coverage",  f"{cov}x", "stock/demand", True),
    ]:
        dc = P["success"] if good else P["danger"]
        col.markdown(f"""<div class='kpi-card'>
            <div class='kpi-label'>{lbl}</div>
            <div class='kpi-value'>{val}</div>
            <div style='font-size:11px;color:{dc}'>{d}</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    if st.button("📥 Generate & Download PDF Report", use_container_width=True):
        with st.spinner("Building professional PDF report…"):
            try:
                from pdf_generator import generate_pdf_report
                api_key = ""
                if include_ai:
                    try:
                        api_key = st.secrets.get("GEMINI_API_KEY", "")
                    except Exception:
                        api_key = ""

                target_id   = rest_id
                target_name = rest_name
                pdf_bytes   = generate_pdf_report(df, target_id, target_name, report_type, api_key)

                fname = f"IntelliPredict_{target_name.replace(' ','_')}_{report_type}_{datetime.now().strftime('%Y%m%d')}.pdf"
                st.success("✅ PDF generated successfully!")
                st.download_button(
                    label="⬇️ Download PDF Report",
                    data=pdf_bytes,
                    file_name=fname,
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"PDF generation failed: {e}")
                st.info("Make sure `reportlab` and `kaleido` are installed. Check requirements.txt.")

    st.divider()
    st.markdown("<div class='section-header'>📄 What's Included in the Report</div>", unsafe_allow_html=True)
    items = [
        ("📊", "KPI Summary", "Units sold, revenue, waste, stock coverage vs previous period"),
        ("🤖", "AI Executive Summary", "Gemini-generated 3-sentence management narrative"),
        ("📈", "Demand Trend Chart", "60-day historical demand trend with area chart"),
        ("🍽️", "Category Performance Table", "Revenue, units, waste per menu category"),
        ("💰", "Monthly Revenue Breakdown", "Stacked bar chart by category across months"),
        ("♻️", "Waste Analysis Chart", "30-day daily waste bar chart"),
        ("💡", "AI Recommendations", "5 actionable recommendations on inventory, staffing, pricing"),
        ("🏪", "All Restaurants Snapshot", "Cross-restaurant comparison table"),
    ]
    for icon, title, desc in items:
        st.markdown(f"""<div style='display:flex;gap:12px;padding:10px 0;border-bottom:1px solid #2a2a3820'>
            <span style='font-size:20px'>{icon}</span>
            <div>
                <div style='font-weight:600;font-size:13px;color:{P["text"]}'>{title}</div>
                <div style='font-size:12px;color:{P["muted"]}'>{desc}</div>
            </div>
        </div>""", unsafe_allow_html=True)
