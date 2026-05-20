"""Real-time data simulation engine for IntelliPredict.

Simulates live order ticks, rolling KPIs, and live demand pulses
using Streamlit session state as an in-memory store.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List
from weather_api import get_weather

# ── Real-time tick generator ──────────────────────────────────────────────────

CATEGORY_WEIGHTS = {
    "Main Course": 0.35,
    "Starters":    0.25,
    "Beverages":   0.28,
    "Desserts":    0.12,
}

PRICE_MAP = {
    "Main Course": 450,
    "Starters":    250,
    "Beverages":   150,
    "Desserts":    200,
}

def _hour_factor() -> float:
    """Demand multiplier based on current hour (lunch/dinner peaks)."""
    h = datetime.now().hour
    if 12 <= h <= 14:   return 1.6   # lunch rush
    if 19 <= h <= 21:   return 1.8   # dinner rush
    if  7 <= h <= 9:    return 1.2   # breakfast
    if  0 <= h <= 6:    return 0.2   # overnight
    return 1.0

def _weather_factor() -> float:
    """Demand multiplier based on live weather."""
    try:
        temp, rain = get_weather()
        factor = 1.0
        if rain:
            factor -= 0.20          # rain reduces footfall
        if temp > 35:
            factor -= 0.10          # very hot → less dine-in
        elif 20 <= temp <= 28:
            factor += 0.08          # pleasant weather boost
        return max(0.5, factor)
    except Exception:
        return 1.0

def generate_live_tick(rest_id: str, base_rate: float = 3.0) -> Dict:
    """Generates one simulated live order tick.

    Args:
        rest_id: Restaurant identifier.
        base_rate: Average orders per minute at baseline.

    Returns:
        Dict with order details.
    """
    hour_f    = _hour_factor()
    weather_f = _weather_factor()
    effective_rate = base_rate * hour_f * weather_f

    # Poisson-distributed orders this tick
    n_orders = max(0, int(np.random.poisson(effective_rate)))

    orders = []
    for _ in range(n_orders):
        cat = np.random.choice(
            list(CATEGORY_WEIGHTS.keys()),
            p=list(CATEGORY_WEIGHTS.values()),
        )
        qty = np.random.randint(1, 4)
        orders.append({
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "restaurant_id": rest_id,
            "category": cat,
            "quantity": qty,
            "revenue": qty * PRICE_MAP[cat],
        })

    return {
        "orders": orders,
        "total_qty": sum(o["quantity"] for o in orders),
        "total_revenue": sum(o["revenue"] for o in orders),
        "hour_factor": round(hour_f, 2),
        "weather_factor": round(weather_f, 2),
        "effective_rate": round(effective_rate, 2),
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }


def init_live_store(rest_id: str):
    """Initialises session-state live data store for a restaurant."""
    key = f"live_{rest_id}"
    if key not in st.session_state:
        st.session_state[key] = {
            "orders_today": [],
            "qty_today": 0,
            "revenue_today": 0,
            "last_tick": None,
            "ticks": [],          # rolling 30-tick history
            "category_totals": {c: 0 for c in CATEGORY_WEIGHTS},
        }

def push_tick(rest_id: str, tick: Dict):
    """Appends a tick to the live store."""
    key = f"live_{rest_id}"
    store = st.session_state[key]
    store["orders_today"].extend(tick["orders"])
    store["qty_today"]     += tick["total_qty"]
    store["revenue_today"] += tick["total_revenue"]
    store["last_tick"]      = tick["timestamp"]
    store["ticks"].append({
        "time": tick["timestamp"],
        "qty": tick["total_qty"],
        "revenue": tick["total_revenue"],
    })
    # Keep only last 30 ticks
    store["ticks"] = store["ticks"][-30:]
    for o in tick["orders"]:
        store["category_totals"][o["category"]] = (
            store["category_totals"].get(o["category"], 0) + o["quantity"]
        )
    st.session_state[key] = store

def get_live_store(rest_id: str) -> Dict:
    """Returns the live store for a restaurant."""
    return st.session_state.get(f"live_{rest_id}", {})
