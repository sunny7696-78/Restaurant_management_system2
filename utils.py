import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ── Color palette ─────────────────────────────────────────────────────────────
PALETTE = {
    "primary":   "#FF6B35",
    "secondary": "#FF9F1C",
    "accent":    "#FFBF69",
    "danger":    "#E63946",
    "success":   "#2EC4B6",
    "bg":        "#0F0F13",
    "card":      "#1A1A24",
    "text":      "#F0EDE8",
    "muted":     "#8A8696",
}

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor ="rgba(0,0,0,0)",
    font=dict(color=PALETTE["text"], family="'IBM Plex Sans', sans-serif"),
    xaxis=dict(gridcolor="#2a2a38", linecolor="#2a2a38"),
    yaxis=dict(gridcolor="#2a2a38", linecolor="#2a2a38"),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="#2a2a38"),
    margin=dict(l=20, r=20, t=40, b=20),
)


def apply_layout(fig, title=""):
    fig.update_layout(**PLOTLY_LAYOUT, title=dict(text=title, font=dict(size=16, color=PALETTE["primary"])))
    return fig


# ── Forecast chart ───────────────────────────────────────────────────────────

def forecast_chart(ts: pd.DataFrame, forecast: pd.DataFrame, title: str = "Demand Forecast"):
    fig = go.Figure()
    recent = ts.tail(60)
    fig.add_trace(go.Scatter(
        x=recent["date"], y=recent["quantity_sold"],
        mode="lines", name="Historical",
        line=dict(color=PALETTE["muted"], width=1.5),
    ))
    fig.add_trace(go.Scatter(
        x=forecast["date"], y=forecast["predicted"],
        mode="lines+markers", name="Forecast",
        line=dict(color=PALETTE["primary"], width=2.5),
        marker=dict(size=4),
    ))
    if "upper" in forecast.columns and "lower" in forecast.columns:
        fig.add_trace(go.Scatter(
            x=pd.concat([forecast["date"], forecast["date"][::-1]]),
            y=pd.concat([forecast["upper"], forecast["lower"][::-1]]),
            fill="toself",
            fillcolor=f"rgba(255,107,53,0.15)",
            line=dict(color="rgba(0,0,0,0)"),
            name="80% Confidence",
            showlegend=True,
        ))
    return apply_layout(fig, title)


# ── Historical trend chart ───────────────────────────────────────────────────

def historical_trend_chart(ts: pd.DataFrame, days: int = 90):
    df = ts.tail(days)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["quantity_sold"],
        fill="tozeroy",
        fillcolor=f"rgba(255,107,53,0.12)",
        line=dict(color=PALETTE["primary"], width=2),
        name="Demand",
    ))
    return apply_layout(fig, f"Last {days} Days — Demand Trend")


# ── Category bar chart ───────────────────────────────────────────────────────

def category_bar_chart(df: pd.DataFrame, restaurant_id: str):
    sub = df[df["restaurant_id"] == restaurant_id].groupby("category").agg(
        total_demand=("quantity_sold", "sum"),
        total_revenue=("revenue", "sum"),
    ).reset_index()
    fig = px.bar(sub, x="category", y="total_demand",
                 color="category",
                 color_discrete_sequence=[PALETTE["primary"], PALETTE["secondary"],
                                          PALETTE["accent"], PALETTE["success"]])
    fig.update_traces(marker_line_width=0)
    return apply_layout(fig, "Total Demand by Category")


# ── Waste vs Stock bar ───────────────────────────────────────────────────────

def waste_stock_chart(snapshot: pd.DataFrame):
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=snapshot["category"], y=snapshot["current_stock"],
        name="Current Stock", marker_color=PALETTE["success"],
    ))
    fig.add_trace(go.Bar(
        x=snapshot["category"], y=snapshot["avg_daily_demand"],
        name="Avg Daily Demand", marker_color=PALETTE["primary"],
    ))
    fig.update_layout(barmode="group")
    return apply_layout(fig, "Stock vs Average Daily Demand")


# ── Weather heatmap ──────────────────────────────────────────────────────────

def weather_demand_heatmap(ts: pd.DataFrame):
    df = ts.copy()
    df["temp_bin"]  = pd.cut(df["temperature"],  bins=6, precision=0)
    df["rain_bin"]  = pd.cut(df["rainfall_mm"],  bins=5, precision=0)
    pivot = df.pivot_table(values="quantity_sold", index="rain_bin", columns="temp_bin", aggfunc="mean")
    pivot.index   = [str(i) for i in pivot.index]
    pivot.columns = [str(c) for c in pivot.columns]
    fig = px.imshow(pivot, color_continuous_scale=["#1A1A24", PALETTE["secondary"], PALETTE["primary"]],
                    labels=dict(x="Temperature (°C)", y="Rainfall (mm)", color="Avg Demand"))
    return apply_layout(fig, "Weather × Demand Heatmap")


# ── Feature importance chart ─────────────────────────────────────────────────

def feature_importance_chart(feat_imp: dict, top_n: int = 10):
    items = sorted(feat_imp.items(), key=lambda x: x[1], reverse=True)[:top_n]
    labels, vals = zip(*items)
    fig = go.Figure(go.Bar(
        x=vals, y=labels, orientation="h",
        marker_color=PALETTE["primary"],
    ))
    fig.update_layout(yaxis=dict(autorange="reversed"))
    return apply_layout(fig, "Top Feature Importances")


# ── Revenue forecast chart ───────────────────────────────────────────────────

def revenue_forecast_chart(forecast: pd.DataFrame, price: float, price_multiplier: float = 1.0):
    forecast = forecast.copy()
    forecast["revenue"] = forecast["predicted"] * price * price_multiplier
    fig = go.Figure(go.Scatter(
        x=forecast["date"], y=forecast["revenue"],
        fill="tozeroy",
        fillcolor=f"rgba(255,159,28,0.15)",
        line=dict(color=PALETTE["secondary"], width=2.5),
        name="Revenue Forecast",
    ))
    return apply_layout(fig, "Revenue Forecast (₹)")


# ── Model comparison table ───────────────────────────────────────────────────

def model_comparison_df(results: dict) -> pd.DataFrame:
    rows = []
    for model_name, (fc, metrics) in results.items():
        rows.append({
            "Model":  model_name,
            "MAE":    metrics.get("MAE", "-"),
            "RMSE":   metrics.get("RMSE", "-"),
            "MAPE %": metrics.get("MAPE", "-"),
        })
    return pd.DataFrame(rows)


# ── KPI helpers ───────────────────────────────────────────────────────────────

def kpi_metric(label: str, value, delta=None, prefix="", suffix=""):
    val_str = f"{prefix}{value:,}{suffix}" if isinstance(value, (int, float)) else f"{prefix}{value}{suffix}"
    return label, val_str, delta


def format_inr(value: float) -> str:
    if value >= 1e7:  return f"₹{value/1e7:.2f} Cr"
    if value >= 1e5:  return f"₹{value/1e5:.2f} L"
    if value >= 1e3:  return f"₹{value/1e3:.1f}K"
    return f"₹{value:.0f}"
