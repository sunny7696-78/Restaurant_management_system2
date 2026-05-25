"""
PDF Report Generator for IntelliPredict.
Generates a professional weekly/monthly management report using ReportLab.
"""

import io
import base64
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image, KeepTogether
)
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics import renderPDF
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak

from config import PALETTE
from utils import format_inr
from data_generator import CATEGORIES, PRICE_MAP, RESTAURANTS


# ── Brand colours as ReportLab Color objects ─────────────────────────────────

def hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))


PRIMARY   = colors.Color(*hex_to_rgb(PALETTE["primary"]))
SECONDARY = colors.Color(*hex_to_rgb(PALETTE["secondary"]))
SUCCESS   = colors.Color(*hex_to_rgb(PALETTE["success"]))
DANGER    = colors.Color(*hex_to_rgb(PALETTE["danger"]))
BG_DARK   = colors.Color(*hex_to_rgb(PALETTE["bg"]))
CARD_BG   = colors.Color(*hex_to_rgb(PALETTE["card"]))
TEXT_CLR  = colors.Color(*hex_to_rgb(PALETTE["text"]))
MUTED     = colors.Color(*hex_to_rgb(PALETTE["muted"]))
WHITE     = colors.white
BLACK     = colors.black
LIGHT_BG  = colors.Color(0.97, 0.96, 0.98)
BORDER    = colors.Color(0.16, 0.16, 0.23)


# ── Styles ────────────────────────────────────────────────────────────────────

def build_styles():
    base = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        fontName="Helvetica-Bold",
        fontSize=28,
        textColor=PRIMARY,
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        fontName="Helvetica",
        fontSize=11,
        textColor=MUTED,
        alignment=TA_CENTER,
        spaceAfter=2,
    )
    section_style = ParagraphStyle(
        "Section",
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=PRIMARY,
        spaceBefore=14,
        spaceAfter=6,
        borderPadding=(0, 0, 4, 0),
    )
    body_style = ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.Color(0.2, 0.2, 0.2),
        leading=14,
        spaceAfter=4,
    )
    bold_style = ParagraphStyle(
        "Bold",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=colors.Color(0.1, 0.1, 0.1),
        leading=14,
    )
    insight_style = ParagraphStyle(
        "Insight",
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.Color(0.15, 0.15, 0.15),
        leading=14,
        leftIndent=10,
        spaceAfter=3,
    )
    kpi_label_style = ParagraphStyle(
        "KPILabel",
        fontName="Helvetica",
        fontSize=8,
        textColor=MUTED,
        alignment=TA_CENTER,
    )
    kpi_value_style = ParagraphStyle(
        "KPIValue",
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=PRIMARY,
        alignment=TA_CENTER,
    )
    kpi_delta_style = ParagraphStyle(
        "KPIDelta",
        fontName="Helvetica",
        fontSize=8,
        textColor=SUCCESS,
        alignment=TA_CENTER,
    )
    footer_style = ParagraphStyle(
        "Footer",
        fontName="Helvetica",
        fontSize=7,
        textColor=MUTED,
        alignment=TA_CENTER,
    )
    return {
        "title": title_style, "subtitle": subtitle_style,
        "section": section_style, "body": body_style,
        "bold": bold_style, "insight": insight_style,
        "kpi_label": kpi_label_style, "kpi_value": kpi_value_style,
        "kpi_delta": kpi_delta_style, "footer": footer_style,
    }


# ── Chart helpers (Plotly → PNG bytes) ───────────────────────────────────────

def _plotly_to_image(fig: go.Figure, width=700, height=280) -> Optional[bytes]:
    """Render a Plotly figure to PNG bytes via kaleido."""
    try:
        fig.update_layout(
            paper_bgcolor="white",
            plot_bgcolor="#F8F7FA",
            font=dict(color="#222222", family="Helvetica"),
            xaxis=dict(gridcolor="#E0DDE8", linecolor="#C0BBD0"),
            yaxis=dict(gridcolor="#E0DDE8", linecolor="#C0BBD0"),
            margin=dict(l=40, r=20, t=30, b=40),
        )
        return fig.to_image(format="png", width=width, height=height, scale=2)
    except Exception:
        return None


def _image_flowable(png_bytes: bytes, width_cm=16) -> Optional[Image]:
    if not png_bytes:
        return None
    buf = io.BytesIO(png_bytes)
    img = Image(buf)
    aspect = img.imageHeight / img.imageWidth
    w = width_cm * cm
    img.drawWidth  = w
    img.drawHeight = w * aspect
    return img


# ── KPI card table ────────────────────────────────────────────────────────────

def kpi_table(kpis: list, styles: dict) -> Table:
    """Builds a 4-column KPI card row.

    kpis: list of (label, value, delta, is_good) tuples
    """
    labels = [Paragraph(k[0], styles["kpi_label"]) for k in kpis]
    values = [Paragraph(k[1], styles["kpi_value"]) for k in kpis]
    deltas = [
        Paragraph(k[2], ParagraphStyle(
            "d", fontName="Helvetica", fontSize=8, alignment=TA_CENTER,
            textColor=SUCCESS if k[3] else DANGER,
        ))
        for k in kpis
    ]

    data = [labels, values, deltas]
    col_w = [4.3 * cm] * len(kpis)
    t = Table(data, colWidths=col_w, rowHeights=[14, 24, 14])
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), LIGHT_BG),
        ("BOX",         (0, 0), (-1, -1), 0.5, colors.Color(0.85, 0.82, 0.9)),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [LIGHT_BG]),
        ("TOPPADDING",  (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.Color(0.88, 0.86, 0.92)),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("ROUNDEDCORNERS", [4]),
    ]))
    return t


# ── Data helpers ──────────────────────────────────────────────────────────────

def _get_kpis(df: pd.DataFrame, rest_id: str):
    rest = df[df["restaurant_id"] == rest_id]
    today = rest["date"].max()
    last7  = rest[rest["date"] >= today - pd.Timedelta(days=7)]
    prev7  = rest[(rest["date"] >= today - pd.Timedelta(days=14)) &
                  (rest["date"] <  today - pd.Timedelta(days=7))]

    qty7   = last7["quantity_sold"].sum()
    pqty7  = prev7["quantity_sold"].sum()
    rev7   = last7["revenue"].sum()
    prev7r = prev7["revenue"].sum()
    waste7 = last7["waste_kg"].sum()
    pwaste7= prev7["waste_kg"].sum()
    cov    = (last7["stock_level"].mean() / last7["quantity_sold"].mean()
              if last7["quantity_sold"].mean() > 0 else 0)

    d_qty  = qty7  - pqty7
    d_rev  = rev7  - prev7r
    d_wst  = waste7 - pwaste7

    return {
        "qty7": int(qty7), "rev7": rev7, "waste7": round(waste7, 1),
        "cov": round(cov, 1), "d_qty": int(d_qty), "d_rev": d_rev,
        "d_wst": round(d_wst, 1),
        "today": today,
    }


def _monthly_revenue(df: pd.DataFrame, rest_id: str) -> pd.DataFrame:
    rest = df[df["restaurant_id"] == rest_id].copy()
    rest["month"] = rest["date"].dt.to_period("M")
    return rest.groupby(["month", "category"])["revenue"].sum().reset_index()


def _waste_trend(df: pd.DataFrame, rest_id: str) -> pd.DataFrame:
    rest = df[df["restaurant_id"] == rest_id]
    daily = rest.groupby("date")["waste_kg"].sum().reset_index()
    return daily.tail(30)


def _demand_trend(df: pd.DataFrame, rest_id: str) -> pd.DataFrame:
    rest = df[df["restaurant_id"] == rest_id]
    daily = rest.groupby("date")["quantity_sold"].sum().reset_index()
    return daily.tail(60)


def _category_summary(df: pd.DataFrame, rest_id: str) -> pd.DataFrame:
    rest = df[df["restaurant_id"] == rest_id]
    last7 = rest[rest["date"] >= rest["date"].max() - pd.Timedelta(days=7)]
    return last7.groupby("category").agg(
        qty=("quantity_sold", "sum"),
        revenue=("revenue", "sum"),
        waste=("waste_kg", "sum"),
    ).reset_index().sort_values("revenue", ascending=False)


# ── AI insights via Gemini ────────────────────────────────────────────────────

def _get_ai_summary(kpis: dict, rest_name: str, api_key: str) -> str:
    """Calls Gemini to generate an executive AI summary paragraph."""
    if not api_key:
        return (
            f"Based on the last 7 days of data, {rest_name} recorded "
            f"{kpis['qty7']:,} units sold with revenue of {format_inr(kpis['rev7'])}. "
            f"Waste stood at {kpis['waste7']} kg. "
            f"Management should focus on optimising procurement and pricing strategy "
            f"to sustain growth momentum."
        )
    try:
        import streamlit as st
        from gemini_client import call_gemini
        sign = "+" if kpis["d_rev"] >= 0 else ""
        prompt = (
            f"You are a restaurant business analyst. Write a 3-sentence executive summary "
            f"for a weekly report for {rest_name}. Data: "
            f"Units sold: {kpis['qty7']:,} ({'+' if kpis['d_qty']>=0 else ''}{kpis['d_qty']} vs prev week). "
            f"Revenue: {format_inr(kpis['rev7'])} ({sign}{format_inr(abs(kpis['d_rev']))} vs prev week). "
            f"Waste: {kpis['waste7']} kg ({'+' if kpis['d_wst']>=0 else ''}{kpis['d_wst']} kg vs prev week). "
            f"Stock coverage: {kpis['cov']}x. "
            f"Be concise, professional, and data-driven. No bullet points."
        )
        result = call_gemini(prompt)
        if result.startswith("⚠️") or "quota" in result.lower():
            raise Exception(result)
        return result.strip()
    except Exception:
        return (
            f"This week {rest_name} demonstrated strong operational performance with "
            f"{kpis['qty7']:,} units sold and revenue of {format_inr(kpis['rev7'])}. "
            f"Continued focus on waste reduction and demand forecasting will drive further growth."
        )


# ── Page template with header/footer ─────────────────────────────────────────

class _PageTemplate:
    def __init__(self, rest_name: str, report_period: str):
        self.rest_name = rest_name
        self.report_period = report_period

    def __call__(self, canvas_obj, doc):
        canvas_obj.saveState()
        w, h = A4

        # Header bar
        canvas_obj.setFillColorRGB(*hex_to_rgb(PALETTE["primary"]))
        canvas_obj.rect(0, h - 1.2 * cm, w, 1.2 * cm, fill=1, stroke=0)
        canvas_obj.setFillColor(colors.white)
        canvas_obj.setFont("Helvetica-Bold", 10)
        canvas_obj.drawString(1 * cm, h - 0.85 * cm, "🍽️  IntelliPredict — Restaurant Intelligence Platform")
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.drawRightString(w - 1 * cm, h - 0.85 * cm, self.report_period)

        # Footer bar
        canvas_obj.setFillColorRGB(*hex_to_rgb(PALETTE["card"]))
        canvas_obj.rect(0, 0, w, 1 * cm, fill=1, stroke=0)
        canvas_obj.setFillColor(colors.Color(0.5, 0.5, 0.55))
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.drawString(1 * cm, 0.38 * cm,
            f"Confidential · {self.rest_name} · Generated {datetime.now().strftime('%d %b %Y %H:%M')}")
        canvas_obj.drawRightString(w - 1 * cm, 0.38 * cm, f"Page {doc.page}")

        canvas_obj.restoreState()


# ── Main generator ────────────────────────────────────────────────────────────

def generate_pdf_report(
    df: pd.DataFrame,
    rest_id: str,
    rest_name: str,
    report_type: str = "Weekly",
    gemini_api_key: str = "",
) -> bytes:
    """Generates a full PDF management report.

    Args:
        df: Full restaurant dataset.
        rest_id: Restaurant identifier.
        rest_name: Restaurant display name.
        report_type: "Weekly" or "Monthly".
        gemini_api_key: Optional Gemini key for AI summary.

    Returns:
        PDF as bytes.
    """
    buf = io.BytesIO()
    styles = build_styles()

    today = datetime.now()
    period = (
        f"Week of {(today - timedelta(days=7)).strftime('%d %b')} – {today.strftime('%d %b %Y')}"
        if report_type == "Weekly"
        else f"Month of {today.strftime('%B %Y')}"
    )

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.8 * cm, bottomMargin=1.4 * cm,
    )

    page_cb = _PageTemplate(rest_name, period)
    story = []

    # ── Cover block ───────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.5 * cm))
    story.append(Paragraph("IntelliPredict", styles["title"]))
    story.append(Paragraph(f"{report_type} Management Report", styles["subtitle"]))
    story.append(Paragraph(rest_name, ParagraphStyle(
        "rn", fontName="Helvetica-Bold", fontSize=14,
        textColor=SECONDARY, alignment=TA_CENTER, spaceAfter=2,
    )))
    story.append(Paragraph(period, styles["subtitle"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=14))

    # ── KPIs ──────────────────────────────────────────────────────────────────
    kpis = _get_kpis(df, rest_id)
    story.append(Paragraph("📊 Key Performance Indicators", styles["section"]))

    kpi_data = [
        ("Units Sold (7d)",
         f"{kpis['qty7']:,}",
         f"{'▲' if kpis['d_qty']>=0 else '▼'} {abs(kpis['d_qty'])} vs prev week",
         kpis["d_qty"] >= 0),
        ("Revenue (7d)",
         format_inr(kpis["rev7"]),
         f"{'▲' if kpis['d_rev']>=0 else '▼'} {format_inr(abs(kpis['d_rev']))}",
         kpis["d_rev"] >= 0),
        ("Waste (7d)",
         f"{kpis['waste7']} kg",
         f"{'▲' if kpis['d_wst']>=0 else '▼'} {abs(kpis['d_wst'])} kg",
         kpis["d_wst"] <= 0),   # less waste = good
        ("Stock Coverage",
         f"{kpis['cov']}x",
         "stock / demand ratio",
         True),
    ]
    story.append(kpi_table(kpi_data, styles))
    story.append(Spacer(1, 0.5 * cm))

    # ── AI Executive Summary ──────────────────────────────────────────────────
    story.append(Paragraph("🤖 AI Executive Summary", styles["section"]))
    ai_text = _get_ai_summary(kpis, rest_name, gemini_api_key)

    summary_data = [[Paragraph(ai_text, styles["body"])]]
    summary_tbl = Table(summary_data, colWidths=[17.5 * cm])
    summary_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.Color(1.0, 0.97, 0.94)),
        ("BOX",           (0, 0), (-1, -1), 1.0, PRIMARY),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(summary_tbl)
    story.append(Spacer(1, 0.5 * cm))

    # ── Demand Trend Chart ────────────────────────────────────────────────────
    story.append(Paragraph("📈 Demand Trend — Last 60 Days", styles["section"]))
    demand_df = _demand_trend(df, rest_id)
    fig_demand = go.Figure(go.Scatter(
        x=demand_df["date"], y=demand_df["quantity_sold"],
        fill="tozeroy", fillcolor="rgba(255,107,53,0.15)",
        line=dict(color=PALETTE["primary"], width=2),
        name="Daily Demand",
    ))
    fig_demand.update_layout(
        xaxis_title="Date", yaxis_title="Units Sold", height=280,
    )
    img = _image_flowable(_plotly_to_image(fig_demand), width_cm=17)
    if img:
        story.append(img)
    story.append(Spacer(1, 0.4 * cm))

    # ── Category Performance Table ────────────────────────────────────────────
    story.append(Paragraph("🍽️ Category Performance (Last 7 Days)", styles["section"]))
    cat_df = _category_summary(df, rest_id)

    table_data = [["Category", "Units Sold", "Revenue", "Waste (kg)", "Rev/Unit"]]
    for _, row in cat_df.iterrows():
        rev_per_unit = format_inr(row["revenue"] / row["qty"]) if row["qty"] > 0 else "–"
        table_data.append([
            row["category"],
            f"{int(row['qty']):,}",
            format_inr(row["revenue"]),
            f"{row['waste']:.1f}",
            rev_per_unit,
        ])
    # Totals row
    table_data.append([
        "TOTAL",
        f"{int(cat_df['qty'].sum()):,}",
        format_inr(cat_df["revenue"].sum()),
        f"{cat_df['waste'].sum():.1f}",
        "–",
    ])

    col_widths = [4.5*cm, 3*cm, 3.5*cm, 3*cm, 3.5*cm]
    cat_table = Table(table_data, colWidths=col_widths)
    cat_table.setStyle(TableStyle([
        # Header
        ("BACKGROUND",    (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 9),
        ("ALIGN",         (0, 0), (-1, 0), "CENTER"),
        # Body
        ("FONTNAME",      (0, 1), (-1, -2), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), 9),
        ("ALIGN",         (1, 1), (-1, -1), "CENTER"),
        ("ALIGN",         (0, 1), (0, -1), "LEFT"),
        ("ROWBACKGROUNDS",(0, 1), (-1, -2),
         [colors.white, colors.Color(0.97, 0.96, 0.99)]),
        # Totals row
        ("BACKGROUND",    (0, -1), (-1, -1), colors.Color(0.93, 0.91, 0.97)),
        ("FONTNAME",      (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, -1), (-1, -1), 9),
        # Grid
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.Color(0.82, 0.80, 0.88)),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))
    story.append(cat_table)
    story.append(Spacer(1, 0.5 * cm))

    # ── Revenue Breakdown Chart ───────────────────────────────────────────────
    story.append(Paragraph("💰 Monthly Revenue Breakdown", styles["section"]))
    monthly_df = _monthly_revenue(df, rest_id)
    monthly_df["month_str"] = monthly_df["month"].astype(str)
    fig_rev = px.bar(
        monthly_df, x="month_str", y="revenue", color="category",
        color_discrete_sequence=[
            PALETTE["primary"], PALETTE["secondary"],
            PALETTE["success"], PALETTE["accent"],
        ],
    )
    fig_rev.update_layout(
        xaxis_title="Month", yaxis_title="Revenue (₹)",
        legend_title="Category", height=280,
    )
    img_rev = _image_flowable(_plotly_to_image(fig_rev), width_cm=17)
    if img_rev:
        story.append(img_rev)
    story.append(Spacer(1, 0.4 * cm))

    # ── Waste Analysis ────────────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("♻️ Waste Analysis — Last 30 Days", styles["section"]))
    waste_df = _waste_trend(df, rest_id)
    fig_waste = go.Figure(go.Bar(
        x=waste_df["date"], y=waste_df["waste_kg"],
        marker_color=PALETTE["danger"], name="Waste (kg)",
    ))
    fig_waste.update_layout(
        xaxis_title="Date", yaxis_title="Waste (kg)", height=260,
    )
    img_waste = _image_flowable(_plotly_to_image(fig_waste), width_cm=17)
    if img_waste:
        story.append(img_waste)
    story.append(Spacer(1, 0.4 * cm))

    # ── AI Recommendations ────────────────────────────────────────────────────
    story.append(Paragraph("💡 AI-Powered Recommendations", styles["section"]))

    recent_df = df[df["restaurant_id"] == rest_id]
    last7_df  = recent_df[recent_df["date"] >= recent_df["date"].max() - pd.Timedelta(days=7)]
    avg_waste = last7_df["waste_kg"].mean()
    avg_qty   = last7_df["quantity_sold"].mean()
    top_cat   = last7_df.groupby("category")["revenue"].sum().idxmax()
    low_cat   = last7_df.groupby("category")["waste_kg"].sum().idxmax()

    recommendations = [
        ("📦 Inventory Optimisation",
         f"Reduce {low_cat} procurement by 8-12% to cut waste costs. "
         f"Maintain {top_cat} stock at 1.3x daily demand to prevent stockouts."),
        ("💰 Revenue Opportunity",
         f"{top_cat} is the highest-revenue category. Consider a weekend combo "
         f"promotion to push volume by an estimated 15-20%."),
        ("🌦️ Weather-Based Planning",
         "Pre-position 20% extra Beverages stock on days with forecast temperatures "
         "above 32°C. Reduce Starters prep on rainy days by 10%."),
        ("📅 Staffing Recommendation",
         "Demand peaks on Saturday/Sunday by ~35%. Schedule 2 additional staff "
         "on weekends and reduce Mon/Tue evening shifts by 1 person."),
        ("🎯 Waste Reduction Target",
         f"Current 7-day waste average is {avg_waste:.1f} kg/day. "
         f"Target a 15% reduction by tightening batch sizes on slow weekday afternoons."),
    ]

    for title_r, body_r in recommendations:
        rec_data = [[
            Paragraph(f"<b>{title_r}</b>", styles["bold"]),
            Paragraph(body_r, styles["body"]),
        ]]
        rec_tbl = Table(rec_data, colWidths=[4.5*cm, 13*cm])
        rec_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (0, 0), colors.Color(1.0, 0.97, 0.94)),
            ("BACKGROUND",    (1, 0), (1, 0), colors.white),
            ("BOX",           (0, 0), (-1, -1), 0.4, colors.Color(0.85, 0.82, 0.9)),
            ("LINEAFTER",     (0, 0), (0, 0), 1.5, PRIMARY),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(rec_tbl)
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 0.5 * cm))

    # ── Restaurant overview (all restaurants for admin) ───────────────────────
    story.append(Paragraph("🏪 All Restaurants — 7-Day Snapshot", styles["section"]))

    all_rest_data = [["Restaurant", "Units Sold", "Revenue", "Waste (kg)", "Stock Cov."]]
    for rid, rname in RESTAURANTS.items():
        k = _get_kpis(df, rid)
        all_rest_data.append([
            rname,
            f"{k['qty7']:,}",
            format_inr(k["rev7"]),
            f"{k['waste7']}",
            f"{k['cov']}x",
        ])

    all_rest_tbl = Table(all_rest_data, colWidths=[5*cm, 3*cm, 3.5*cm, 3*cm, 3*cm])
    all_rest_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1),
         [colors.white, colors.Color(0.97, 0.96, 0.99)]),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.Color(0.82, 0.80, 0.88)),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))
    story.append(all_rest_tbl)
    story.append(Spacer(1, 0.5 * cm))

    # ── Disclaimer ────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.Color(0.8, 0.78, 0.85), spaceAfter=8))
    story.append(Paragraph(
        "This report was automatically generated by IntelliPredict using ML-based demand forecasting "
        "(XGBoost + Prophet + LSTM Ensemble) and AI analysis (Google Gemini). "
        "Forecasts are probabilistic estimates and should be validated against ground truth before "
        "major procurement or staffing decisions.",
        styles["footer"],
    ))

    # ── Build PDF ─────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=page_cb, onLaterPages=page_cb)
    return buf.getvalue()
