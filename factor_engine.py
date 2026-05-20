"""Factor-based prediction engine for IntelliPredict.

Analyses all demand-driving factors (weather, weekday, festival,
price elasticity, seasonality, lag) and returns weighted predictions
with per-factor explanations.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from weather_api import get_weather

# ── Factor definitions ────────────────────────────────────────────────────────

FACTORS = {
    "weekend_effect": {
        "label":   "Weekend Effect",
        "icon":    "📅",
        "desc":    "Saturdays and Sundays drive significantly higher footfall.",
        "max_pct": 35,
    },
    "festival_boost": {
        "label":   "Festival / Holiday Boost",
        "icon":    "🎉",
        "desc":    "Local festivals and public holidays spike demand by 40-60%.",
        "max_pct": 55,
    },
    "weather_impact": {
        "label":   "Weather Impact",
        "icon":    "🌦️",
        "desc":    "Rain reduces footfall; pleasant temp (20-28°C) boosts it.",
        "max_pct": 20,
    },
    "time_of_day": {
        "label":   "Time-of-Day Factor",
        "icon":    "⏰",
        "desc":    "Lunch (12-2 PM) and dinner (7-9 PM) peaks drive most revenue.",
        "max_pct": 80,
    },
    "lag_demand": {
        "label":   "Lag-7 Demand Anchor",
        "icon":    "📊",
        "desc":    "Last week's same-day sales — the strongest single predictor.",
        "max_pct": 40,
    },
    "seasonality": {
        "label":   "Monthly Seasonality",
        "icon":    "📆",
        "desc":    "Summer and festive months (Oct-Dec) show higher baseline demand.",
        "max_pct": 18,
    },
    "price_elasticity": {
        "label":   "Price Elasticity",
        "icon":    "💸",
        "desc":    "Demand sensitivity to pricing — higher prices reduce volume.",
        "max_pct": 15,
    },
    "momentum": {
        "label":   "7-Day Momentum",
        "icon":    "⚡",
        "desc":    "Rolling average of the last 7 days indicates current demand pace.",
        "max_pct": 25,
    },
}


def compute_factors(
    ts: pd.DataFrame,
    target_date: datetime,
    category: str,
    price_multiplier: float = 1.0,
) -> Tuple[Dict[str, float], float, List[Dict]]:
    """Computes all demand factors for a target date.

    Args:
        ts: Historical time series for the restaurant+category.
        target_date: The date to predict demand for.
        category: Menu category being predicted.
        price_multiplier: Price adjustment ratio (1.0 = no change).

    Returns:
        Tuple of (factor_scores, predicted_demand, factor_breakdown_list)
    """
    recent = ts.tail(30)
    baseline = recent["quantity_sold"].mean() if len(recent) > 0 else 50.0

    scores: Dict[str, float] = {}

    # 1. Weekend effect
    is_weekend = target_date.weekday() >= 5
    scores["weekend_effect"] = 0.30 if is_weekend else 0.0

    # 2. Festival boost (simple calendar heuristic — Oct/Nov/Dec are festive)
    month = target_date.month
    festival_months = {10: 0.25, 11: 0.40, 12: 0.50, 1: 0.20, 8: 0.15}
    scores["festival_boost"] = festival_months.get(month, 0.0)

    # 3. Weather impact (live)
    try:
        temp, rain = get_weather()
        w = 0.0
        if rain:        w -= 0.20
        if temp > 35:   w -= 0.10
        elif 20 <= temp <= 28: w += 0.08
        scores["weather_impact"] = w
    except Exception:
        temp, rain = 25, 0
        scores["weather_impact"] = 0.0

    # 4. Time-of-day
    h = datetime.now().hour
    tod_map = {
        (12, 14): 0.60,
        (19, 21): 0.75,
        (7,  9):  0.20,
        (0,  6):  -0.80,
    }
    tod = 0.0
    for (start, end), factor in tod_map.items():
        if start <= h <= end:
            tod = factor
            break
    scores["time_of_day"] = tod

    # 5. Lag-7 anchor
    lag7_date = target_date - timedelta(days=7)
    lag7_rows = ts[ts["date"].dt.date == lag7_date.date()]
    if len(lag7_rows) > 0:
        lag7_val = lag7_rows["quantity_sold"].values[0]
        scores["lag_demand"] = (lag7_val - baseline) / max(baseline, 1)
    else:
        scores["lag_demand"] = 0.0

    # 6. Seasonality
    seasonal_boost = {12: 0.15, 11: 0.10, 10: 0.08, 1: 0.05}.get(month, 0.0)
    scores["seasonality"] = seasonal_boost

    # 7. Price elasticity (elasticity = -0.4)
    elasticity = -0.4
    scores["price_elasticity"] = elasticity * (price_multiplier - 1.0)

    # 8. 7-day momentum
    roll7 = recent["quantity_sold"].mean() if len(recent) >= 7 else baseline
    scores["momentum"] = (roll7 - baseline) / max(baseline, 1) * 0.5

    # ── Aggregate prediction ──────────────────────────────────────────────────
    total_adjustment = sum(scores.values())
    predicted = max(5, baseline * (1 + total_adjustment))

    # ── Build breakdown list ──────────────────────────────────────────────────
    breakdown = []
    for key, score in scores.items():
        meta = FACTORS[key]
        impact_pct = round(score * 100, 1)
        direction  = "positive" if score > 0 else ("negative" if score < 0 else "neutral")
        breakdown.append({
            "key":        key,
            "label":      meta["label"],
            "icon":       meta["icon"],
            "desc":       meta["desc"],
            "score":      round(score, 4),
            "impact_pct": impact_pct,
            "direction":  direction,
            "bar_width":  min(100, abs(impact_pct) * 4),
        })

    breakdown.sort(key=lambda x: abs(x["score"]), reverse=True)

    return scores, round(predicted, 1), breakdown


def factor_forecast(
    ts: pd.DataFrame,
    horizon: int,
    category: str,
    price_multiplier: float = 1.0,
) -> pd.DataFrame:
    """Generates a factor-based multi-day forecast.

    Args:
        ts: Historical time series.
        horizon: Number of days to forecast.
        category: Menu category.
        price_multiplier: Price adjustment ratio.

    Returns:
        DataFrame with predicted values and factor contributions.
    """
    rows = []
    today = datetime.now()
    recent = ts.tail(30)
    baseline = recent["quantity_sold"].mean() if len(recent) > 0 else 50.0

    for i in range(1, horizon + 1):
        target = today + timedelta(days=i)
        _, predicted, breakdown = compute_factors(
            ts, target, category, price_multiplier
        )
        top_factor = breakdown[0]["label"] if breakdown else "Baseline"
        rows.append({
            "date":       target.strftime("%Y-%m-%d"),
            "day":        target.strftime("%a"),
            "predicted":  int(predicted),
            "lower":      int(predicted * 0.88),
            "upper":      int(predicted * 1.12),
            "top_factor": top_factor,
            "confidence": max(60, min(95, int(92 - i * 0.9))),
        })

    return pd.DataFrame(rows)
