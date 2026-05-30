"""
Real Data Engine for IntelliPredict.

Fetches LIVE real data from:
1. OpenWeatherMap — real Ludhiana weather (temp, rain, humidity, wind)
2. User-uploaded CSV/Excel — your own restaurant sales data
3. Google Sheets (public) — shared team data
4. Gemini AI — enriches synthetic base with real-world patterns

All functions return pandas DataFrames compatible with the app.
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import io
from datetime import datetime, timedelta
from typing import Optional, Tuple

# ── 1. LIVE WEATHER DATA ─────────────────────────────────────────────────────

def fetch_live_weather() -> dict:
    """Fetch real-time Ludhiana weather from OpenWeatherMap."""
    api_key = st.secrets.get("OPENWEATHER_API_KEY", "")
    result = {
        "temp": 28.0, "feels_like": 30.0, "humidity": 65,
        "wind_speed": 3.5, "description": "Clear sky",
        "rain": 0, "visibility": 10000, "source": "simulated",
        "city": "Ludhiana", "timestamp": datetime.now().strftime("%H:%M"),
    }
    if not api_key:
        return result
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q=Ludhiana,IN&appid={api_key}&units=metric"
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            d = r.json()
            result.update({
                "temp":        round(d["main"]["temp"], 1),
                "feels_like":  round(d["main"]["feels_like"], 1),
                "humidity":    d["main"]["humidity"],
                "wind_speed":  round(d["wind"].get("speed", 0), 1),
                "description": d["weather"][0]["description"].title(),
                "rain":        1 if d["weather"][0]["main"] in ["Rain","Drizzle","Thunderstorm"] else 0,
                "visibility":  d.get("visibility", 10000),
                "source":      "live",
            })
    except Exception:
        pass
    return result


def fetch_5day_forecast() -> pd.DataFrame:
    """Fetch 5-day weather forecast for demand planning."""
    api_key = st.secrets.get("OPENWEATHER_API_KEY", "")
    rows = []
    if api_key:
        try:
            url = f"https://api.openweathermap.org/data/2.5/forecast?q=Ludhiana,IN&appid={api_key}&units=metric&cnt=40"
            r = requests.get(url, timeout=8)
            if r.status_code == 200:
                for item in r.json().get("list", []):
                    dt = datetime.fromtimestamp(item["dt"])
                    rows.append({
                        "datetime":    dt,
                        "date":        dt.strftime("%d %b"),
                        "time":        dt.strftime("%H:%M"),
                        "temp":        round(item["main"]["temp"], 1),
                        "humidity":    item["main"]["humidity"],
                        "rain":        1 if item["weather"][0]["main"] in ["Rain","Drizzle"] else 0,
                        "description": item["weather"][0]["description"].title(),
                        "demand_factor": _weather_demand_factor(
                            item["main"]["temp"],
                            1 if item["weather"][0]["main"] in ["Rain","Drizzle"] else 0
                        ),
                    })
        except Exception:
            pass

    if not rows:
        # Fallback: realistic simulated forecast
        now = datetime.now()
        for i in range(40):
            dt = now + timedelta(hours=i*3)
            temp = 28 + 4 * np.sin(i * 0.3) + np.random.randn() * 2
            rain = 1 if np.random.rand() < 0.15 else 0
            rows.append({
                "datetime": dt, "date": dt.strftime("%d %b"),
                "time": dt.strftime("%H:%M"), "temp": round(temp, 1),
                "humidity": int(60 + np.random.randint(0, 25)),
                "rain": rain, "description": "Light Rain" if rain else "Partly Cloudy",
                "demand_factor": _weather_demand_factor(temp, rain),
            })

    return pd.DataFrame(rows)


def _weather_demand_factor(temp: float, rain: int) -> float:
    factor = 1.0
    if rain:          factor -= 0.18
    if temp > 38:     factor -= 0.12
    elif temp > 35:   factor -= 0.06
    elif 20 <= temp <= 28: factor += 0.08
    elif temp < 15:   factor -= 0.10
    return round(max(0.5, factor), 2)


# ── 2. USER-UPLOADED REAL DATA ────────────────────────────────────────────────

REQUIRED_COLS = {"date", "quantity_sold", "revenue"}
OPTIONAL_COLS = {"category", "waste_kg", "stock_level", "restaurant_id", "restaurant_name"}

def validate_uploaded_df(df: pd.DataFrame) -> Tuple[bool, str, pd.DataFrame]:
    """Validate and normalise an uploaded DataFrame.
    Returns (is_valid, message, cleaned_df).
    """
    df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]

    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        # Try common aliases
        aliases = {
            "qty": "quantity_sold", "sales": "quantity_sold",
            "units": "quantity_sold", "orders": "quantity_sold",
            "rev": "revenue", "amount": "revenue", "income": "revenue",
            "dt": "date", "day": "date", "sale_date": "date",
        }
        for col in list(df.columns):
            if col in aliases and aliases[col] not in df.columns:
                df = df.rename(columns={col: aliases[col]})
        missing = REQUIRED_COLS - set(df.columns)

    if missing:
        return False, f"Missing required columns: {missing}. Required: date, quantity_sold, revenue", df

    # Parse date
    try:
        df["date"] = pd.to_datetime(df["date"], dayfirst=True)
    except Exception as e:
        return False, f"Could not parse 'date' column: {e}", df

    # Fill optional columns
    if "category" not in df.columns:
        df["category"] = "Main Course"
    if "waste_kg" not in df.columns:
        df["waste_kg"] = (df["quantity_sold"] * 0.08).round(2)
    if "stock_level" not in df.columns:
        df["stock_level"] = (df["quantity_sold"] * 1.2).round(0).astype(int)
    if "restaurant_id" not in df.columns:
        df["restaurant_id"] = "R001"
    if "restaurant_name" not in df.columns:
        df["restaurant_name"] = "My Restaurant"

    # Add derived columns
    df["is_weekend"]  = df["date"].dt.dayofweek >= 5
    df["is_festival"] = False
    df["temperature"] = 28.0
    df["rainfall_mm"] = 0.0

    df = df.sort_values("date").reset_index(drop=True)
    return True, f"✅ Loaded {len(df):,} rows from {df['date'].min().date()} to {df['date'].max().date()}", df


def load_uploaded_data(uploaded_file) -> Tuple[bool, str, Optional[pd.DataFrame]]:
    """Parse an uploaded CSV or Excel file."""
    try:
        name = uploaded_file.name.lower()
        if name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        elif name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(uploaded_file)
        elif name.endswith(".json"):
            df = pd.read_json(uploaded_file)
        else:
            return False, "Unsupported format. Upload CSV, Excel (.xlsx), or JSON.", None

        ok, msg, df = validate_uploaded_df(df)
        return ok, msg, df if ok else None
    except Exception as e:
        return False, f"Failed to read file: {e}", None


# ── 3. GOOGLE SHEETS (Public) ─────────────────────────────────────────────────

def load_google_sheet(sheet_url: str) -> Tuple[bool, str, Optional[pd.DataFrame]]:
    """Load data from a public Google Sheet (CSV export URL)."""
    try:
        # Convert share URL to CSV export URL
        if "/edit" in sheet_url or "/view" in sheet_url:
            sheet_id = sheet_url.split("/d/")[1].split("/")[0]
            csv_url  = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        elif "export?format=csv" in sheet_url:
            csv_url = sheet_url
        else:
            return False, "Invalid Google Sheets URL. Share the sheet publicly and paste the link.", None

        r = requests.get(csv_url, timeout=10)
        if r.status_code != 200:
            return False, f"Could not access sheet (HTTP {r.status_code}). Make sure it's shared publicly.", None

        df = pd.read_csv(io.StringIO(r.text))
        ok, msg, df = validate_uploaded_df(df)
        return ok, msg, df if ok else None
    except Exception as e:
        return False, f"Error loading sheet: {e}", None


# ── 4. SAMPLE TEMPLATE ────────────────────────────────────────────────────────

def get_sample_template() -> pd.DataFrame:
    """Return a sample CSV template for users to fill in their real data."""
    from data_generator import CATEGORIES, PRICE_MAP, RESTAURANTS
    rows = []
    now  = datetime.now()
    for i in range(30):
        d = now - timedelta(days=29-i)
        for cat in CATEGORIES:
            qty = int(np.random.randint(20, 80))
            rows.append({
                "date":          d.strftime("%Y-%m-%d"),
                "restaurant_id": "R001",
                "restaurant_name": "My Restaurant",
                "category":      cat,
                "quantity_sold": qty,
                "revenue":       qty * PRICE_MAP[cat],
                "waste_kg":      round(qty * 0.08, 1),
                "stock_level":   int(qty * 1.2),
            })
    return pd.DataFrame(rows)


# ── 5. MERGE REAL + SYNTHETIC ─────────────────────────────────────────────────

def merge_real_with_synthetic(real_df: pd.DataFrame,
                               synthetic_df: pd.DataFrame) -> pd.DataFrame:
    """Merge uploaded real data with synthetic for restaurants not in real data.
    Real data takes precedence for overlapping restaurants/dates.
    """
    real_rests = real_df["restaurant_id"].unique()
    synth_other = synthetic_df[~synthetic_df["restaurant_id"].isin(real_rests)]
    merged = pd.concat([real_df, synth_other], ignore_index=True)
    merged = merged.sort_values(["restaurant_id", "date"]).reset_index(drop=True)
    return merged
