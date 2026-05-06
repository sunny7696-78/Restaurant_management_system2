"""Utility functions for visualization and formatting."""

from typing import Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from config import PALETTE, PLOTLY_LAYOUT

def apply_layout(fig: go.Figure, title: str = "") -> go.Figure:
    """Applies the standard theme and title to a Plotly figure.
    
    Args:
        fig: The Plotly figure to style.
        title: Title of the chart.
        
    Returns:
        The styled Plotly figure.
    """
    fig.update_layout(
        **PLOTLY_LAYOUT, 
        title=dict(text=title, font=dict(size=16, color=PALETTE["primary"]))
    )
    return fig

def forecast_chart(
    ts: pd.DataFrame, 
    forecast: pd.DataFrame, 
    title: str = "Demand Forecast"
) -> go.Figure:
    """Generates a forecast chart with historical data and confidence intervals.
    
    Args:
        ts: Historical time series data.
        forecast: Forecasted data.
        title: Chart title.
        
    Returns:
        A Plotly figure.
    """
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

def historical_trend_chart(ts: pd.DataFrame, days: int = 90) -> go.Figure:
    """Generates a line chart for historical demand trends.
    
    Args:
        ts: Time series data.
        days: Number of days to show.
        
    Returns:
        A Plotly figure.
    """
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

def category_bar_chart(df: pd.DataFrame, restaurant_id: str) -> go.Figure:
    """Generates a bar chart of total demand by category.
    
    Args:
        df: The dataset.
        restaurant_id: ID of the restaurant.
        
    Returns:
        A Plotly figure.
    """
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

def waste_stock_chart(snapshot: pd.DataFrame) -> go.Figure:
    """Generates a grouped bar chart for stock levels vs demand.
    
    Args:
        snapshot: Inventory snapshot data.
        
    Returns:
        A Plotly figure.
    """
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

def weather_demand_heatmap(ts: pd.DataFrame) -> go.Figure:
    """Generates a heatmap showing interaction between weather and demand.
    
    Args:
        ts: Time series data with weather features.
        
    Returns:
        A Plotly figure.
    """
    df = ts.copy()
    df["temp_bin"]  = pd.cut(df["temperature"],  bins=6, precision=0)
    df["rain_bin"]  = pd.cut(df["rainfall_mm"],  bins=5, precision=0)
    pivot = df.pivot_table(values="quantity_sold", index="rain_bin", columns="temp_bin", aggfunc="mean")
    pivot.index   = [str(i) for i in pivot.index]
    pivot.columns = [str(c) for c in pivot.columns]
    fig = px.imshow(pivot, color_continuous_scale=["#1A1A24", PALETTE["secondary"], PALETTE["primary"]],
                    labels=dict(x="Temperature (°C)", y="Rainfall (mm)", color="Avg Demand"))
    return apply_layout(fig, "Weather × Demand Heatmap")

def feature_importance_chart(feat_imp: Dict[str, float], top_n: int = 10) -> go.Figure:
    """Generates a horizontal bar chart of feature importances with descriptive labels.
    
    Args:
        feat_imp: Dictionary mapping feature names to importance scores.
        top_n: Number of top features to show.
        
    Returns:
        A Plotly figure.
    """
    from models import FEATURE_EXPLANATIONS
    
    items = sorted(feat_imp.items(), key=lambda x: x[1], reverse=True)[:top_n]
    
    # Map to human readable names or use original if not in explanations
    labels = []
    explanations = []
    for k, _ in items:
        expl = FEATURE_EXPLANATIONS.get(k, k)
        # Shorten for the axis label but keep full for tooltip
        label = expl.split(":")[0] if ":" in expl else k
        labels.append(label)
        explanations.append(expl)
        
    vals = [v for _, v in items]
    
    fig = go.Figure(go.Bar(
        x=vals, y=labels, orientation="h",
        marker_color=PALETTE["primary"],
        hovertemplate="<b>%{y}</b><br>Importance: %{x:.4f}<extra></extra>",
        customdata=explanations,
    ))
    
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>%{customdata}<br>Score: %{x:.4f}<extra></extra>"
    )
    
    fig.update_layout(yaxis=dict(autorange="reversed"))
    return apply_layout(fig, "Top Factors Driving Predictions")


def revenue_forecast_chart(
    forecast: pd.DataFrame, 
    price: float, 
    price_multiplier: float = 1.0
) -> go.Figure:
    """Generates a revenue forecast line chart.
    
    Args:
        forecast: Forecasted data.
        price: Base price per unit.
        price_multiplier: Price adjustment factor.
        
    Returns:
        A Plotly figure.
    """
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

def model_comparison_df(results: Dict[str, Tuple[pd.DataFrame, Dict[str, Any]]]) -> pd.DataFrame:
    """Converts model results into a summary comparison DataFrame.
    
    Args:
        results: Dictionary mapping model names to (forecast, metrics) tuples.
        
    Returns:
        A summary DataFrame.
    """
    rows = []
    for model_name, (fc, metrics) in results.items():
        rows.append({
            "Model":  model_name,
            "MAE":    metrics.get("MAE", "-"),
            "RMSE":   metrics.get("RMSE", "-"),
            "MAPE %": metrics.get("MAPE", "-"),
        })
    return pd.DataFrame(rows)

def format_inr(value: float) -> str:
    """Formats a currency value in Indian Rupees (INR) with shorthand (Cr, L, K).
    
    Args:
        value: The numeric value to format.
        
    Returns:
        A formatted string (e.g., ₹1.5 L).
    """
    if value >= 1e7:  return f"₹{value/1e7:.2f} Cr"
    if value >= 1e5:  return f"₹{value/1e5:.2f} L"
    if value >= 1e3:  return f"₹{value/1e3:.1f}K"
    return f"₹{value:.0f}"
