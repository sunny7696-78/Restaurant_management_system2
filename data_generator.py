"""Synthetic data generation for restaurant demand forecasting."""

from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from logger import logger

# ── Constants ───────────────────────────────────────────────────────────────

RESTAURANTS: Dict[str, str] = {
    "R001": "The Golden Kebab",
    "R002": "Urban Bistro",
    "R003": "Pasta House",
    "R004": "Sushi Zen",
}

CATEGORIES: List[str] = ["Main Course", "Starters", "Beverages", "Desserts"]

PRICE_MAP: Dict[str, int] = {
    "Main Course": 450,
    "Starters": 250,
    "Beverages": 150,
    "Desserts": 200,
}

# ── Generator ───────────────────────────────────────────────────────────────

def generate_dataset(days: int = 730) -> pd.DataFrame:
    """Generates a multi-restaurant demand dataset.
    
    Args:
        days: Number of days of historical data to generate.
        
    Returns:
        A pandas DataFrame with generated data.
    """
    logger.info(f"Generating synthetic dataset for {days} days...")
    np.random.seed(42)
    start_date = datetime.now() - timedelta(days=days)
    dates = [start_date + timedelta(days=i) for i in range(days)]
    
    rows = []
    for rest_id, rest_name in RESTAURANTS.items():
        for category in CATEGORIES:
            base_demand = np.random.randint(20, 60)
            price = PRICE_MAP[category]
            
            for date in dates:
                # Seasonality & factors
                is_weekend = 1 if date.weekday() >= 5 else 0
                is_festival = 1 if np.random.random() < 0.03 else 0
                temp = 25 + 10 * np.sin(2 * np.pi * date.timetuple().tm_yday / 365) + np.random.normal(0, 2)
                rain = np.random.exponential(2) if np.random.random() < 0.2 else 0
                
                # Demand calculation
                demand = base_demand
                demand += 15 * is_weekend
                demand += 30 * is_festival
                demand -= 0.5 * (temp - 25)**2 if temp > 30 else 0
                demand -= 5 * rain if rain > 5 else 0
                demand += np.random.normal(0, 5)
                demand = max(5, int(demand))
                
                # Secondary metrics
                waste = demand * np.random.uniform(0.02, 0.12)
                stock = demand * np.random.uniform(1.1, 1.5)
                
                rows.append({
                    "date": date,
                    "restaurant_id": rest_id,
                    "restaurant_name": rest_name,
                    "category": category,
                    "quantity_sold": demand,
                    "revenue": demand * price,
                    "waste_kg": round(waste, 2),
                    "stock_level": int(stock),
                    "temperature": round(temp, 1),
                    "rainfall_mm": round(rain, 1),
                    "is_weekend": is_weekend,
                    "is_festival": is_festival,
                })
                
    return pd.DataFrame(rows)

def get_time_series(df: pd.DataFrame, rest_id: str, category: str) -> pd.DataFrame:
    """Extracts a specific time series from the full dataset.
    
    Args:
        df: The full dataset.
        rest_id: ID of the restaurant.
        category: Menu category.
        
    Returns:
        Filtered DataFrame sorted by date.
    """
    ts = df[(df["restaurant_id"] == rest_id) & (df["category"] == category)].copy()
    return ts.sort_values("date")

def generate_inventory_snapshot(df: pd.DataFrame, rest_id: str) -> pd.DataFrame:
    """Generates a current inventory status snapshot.
    
    Args:
        df: The full dataset.
        rest_id: ID of the restaurant.
        
    Returns:
        Snapshot DataFrame with risk levels and reorder suggestions.
    """
    rest_df = df[df["restaurant_id"] == rest_id]
    today = rest_df["date"].max()
    
    latest = rest_df[rest_df["date"] == today].copy()
    avg_demand = rest_df.groupby("category")["quantity_sold"].mean().to_dict()
    avg_waste = rest_df.groupby("category")["waste_kg"].mean().to_dict()
    
    latest["avg_daily_demand"] = latest["category"].map(avg_demand)
    latest["avg_waste_kg"] = latest["category"].map(avg_waste)
    latest["current_stock"] = latest["stock_level"]
    latest["days_of_stock"] = latest["current_stock"] / latest["avg_daily_demand"]
    
    def get_risk(days):
        if days < 1.1: return "🔴 Critical (Low Stock)"
        if days < 1.3: return "🟡 Caution (Reorder Soon)"
        return "🟢 Healthy (Sufficient)"
        
    latest["risk"] = latest["days_of_stock"].apply(get_risk)
    
    # Suggested reorder: amount to reach 2.5 days of coverage
    latest["reorder_qty"] = (latest["avg_daily_demand"] * 2.5 - latest["current_stock"]).clip(lower=0).round().astype(int)
    
    return latest[["category", "current_stock", "avg_daily_demand", "days_of_stock", "risk", "reorder_qty", "avg_waste_kg"]]