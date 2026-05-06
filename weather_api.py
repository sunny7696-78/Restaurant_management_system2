import streamlit as st
import requests
from typing import List, Dict, Any

# Get API Key from Streamlit secrets (for deployment)
# Fallback to an empty string if not found
API_KEY = st.secrets.get("OPENWEATHER_API_KEY", "")
CITY = "ludhiana"

def get_weather():
    """Fetches current weather data."""
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={API_KEY}&units=metric"
        data = requests.get(url, timeout=5).json()

        temp = data['main']['temp']
        weather = data['weather'][0]['main']
        rain = 1 if weather in ['Rain', 'Drizzle'] else 0
        return temp, rain
    except Exception:
        return 25, 0

def get_forecast() -> List[Dict[str, Any]]:
    """Fetches 5-day weather forecast (3-hour intervals)."""
    try:
        url = f"http://api.openweathermap.org/data/2.5/forecast?q={CITY}&appid={API_KEY}&units=metric"
        data = requests.get(url, timeout=5).json()
        
        forecasts = []
        if "list" in data:
            for entry in data["list"]:
                forecasts.append({
                    "datetime": entry["dt_txt"],
                    "temp": entry["main"]["temp"],
                    "rain": 1 if any(w["main"] in ["Rain", "Drizzle"] for w in entry["weather"]) else 0
                })
        return forecasts
    except Exception:
        return []