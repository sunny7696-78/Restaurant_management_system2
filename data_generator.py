import pandas as pd
import numpy as np
from datetime import datetime, timedelta

RESTAURANTS = {
    "R001": "Spice Garden",
    "R002": "The Urban Bistro",
    "R003": "Coastal Flavors",
    "R004": "Royal Dine",
    "R005": "Street Bites",
}

CATEGORIES = ["Starters", "Mains", "Desserts", "Beverages"]

MENU_ITEMS = {
    "Starters":  ["Paneer Tikka", "Veg Spring Roll", "Soup of Day", "Garlic Bread"],
    "Mains":     ["Butter Chicken", "Dal Makhani", "Biryani", "Pasta Arrabbiata"],
    "Desserts":  ["Gulab Jamun", "Ice Cream", "Brownie", "Rasgulla"],
    "Beverages": ["Lassi", "Cold Coffee", "Fresh Lime Soda", "Masala Chai"],
}

PRICE_MAP = {"Starters": 180, "Mains": 320, "Desserts": 120, "Beverages": 80}

INDIAN_FESTIVALS = {
    "2023-01-26","2023-03-08","2023-04-14","2023-08-15",
    "2023-10-24","2023-11-12","2023-12-25",
    "2024-01-26","2024-03-25","2024-04-14","2024-08-15",
    "2024-10-12","2024-11-01","2024-12-25",
    "2025-01-26","2025-03-14","2025-08-15","2025-10-02",
    "2025-10-20","2025-11-20","2025-12-25",
}


def generate_dataset(start="2023-01-01", end="2025-12-31", seed=42):
    np.random.seed(seed)
    dates = pd.date_range(start, end, freq="D")
    records = []

    for rid, rname in RESTAURANTS.items():
        base_demand = np.random.randint(80, 160)
        for dt in dates:
            is_weekend  = int(dt.dayofweek >= 5)
            is_festival = int(str(dt.date()) in INDIAN_FESTIVALS)
            month = dt.month

            season_factor = 1.0
            if month in [10, 11, 12]: season_factor = 1.25
            elif month in [6, 7, 8]:  season_factor = 0.80
            elif month in [1, 2]:     season_factor = 0.90

            temp     = np.random.normal(28 - 8 * np.sin((month - 1) * np.pi / 6), 3)
            rainfall = max(0, np.random.normal(5 if month in [6, 7, 8, 9] else 0.5, 3))

            weather_factor = 1.0 - 0.003 * max(0, rainfall - 2)
            if temp > 38: weather_factor *= 0.92
            if temp < 15: weather_factor *= 1.08

            for cat in CATEGORIES:
                cat_mult = {"Starters": 0.8, "Mains": 1.2, "Desserts": 0.6, "Beverages": 0.9}[cat]
                demand = int(
                    base_demand * cat_mult * season_factor * weather_factor
                    * (1.3 if is_weekend else 1.0)
                    * (1.5 if is_festival else 1.0)
                    * np.random.uniform(0.85, 1.15)
                )
                demand = max(5, demand)
                revenue  = demand * PRICE_MAP[cat] * np.random.uniform(0.92, 1.08)
                waste_kg = demand * np.random.uniform(0.03, 0.12) * np.random.uniform(0.1, 0.3)
                stock    = int(demand * np.random.uniform(1.0, 1.4))

                records.append({
                    "date":            dt,
                    "restaurant_id":   rid,
                    "restaurant_name": rname,
                    "category":        cat,
                    "quantity_sold":   demand,
                    "revenue":         round(revenue, 2),
                    "temperature":     round(temp, 1),
                    "rainfall_mm":     round(rainfall, 1),
                    "is_weekend":      is_weekend,
                    "is_festival":     is_festival,
                    "season_factor":   round(season_factor, 2),
                    "waste_kg":        round(waste_kg, 2),
                    "stock_level":     stock,
                    "month":           month,
                    "day_of_week":     dt.dayofweek,
                    "day_of_year":     dt.dayofyear,
                })

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    return df


def get_time_series(df, restaurant_id, category):
    sub = (df[(df["restaurant_id"] == restaurant_id) & (df["category"] == category)]
           .copy().sort_values("date").reset_index(drop=True))
    return sub


def generate_inventory_snapshot(df, restaurant_id, as_of=None):
    if as_of is None:
        as_of = df["date"].max()
    recent = df[
        (df["restaurant_id"] == restaurant_id) &
        (df["date"] >= as_of - timedelta(days=7)) &
        (df["date"] <= as_of)
    ]
    snap = recent.groupby("category").agg(
        avg_daily_demand=("quantity_sold", "mean"),
        current_stock=("stock_level", "last"),
        avg_waste_kg=("waste_kg", "mean"),
    ).reset_index()
    snap["days_of_stock"] = snap["current_stock"] / snap["avg_daily_demand"].clip(lower=1)
    snap["risk"] = snap["days_of_stock"].apply(
        lambda x: "🔴 Critical" if x < 1.5 else ("🟡 Low" if x < 3 else "🟢 Healthy")
    )
    snap["reorder_qty"] = (
        (snap["avg_daily_demand"] * 7 - snap["current_stock"]).clip(lower=0).astype(int)
    )
    return snap
