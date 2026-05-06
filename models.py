"""Machine learning models for demand forecasting."""

from typing import Dict, Any, Tuple, List, Optional
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
import warnings
from logger import logger

warnings.filterwarnings("ignore")

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    logger.warning("Prophet not available. Using fallback for Prophet forecasts.")

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False
    logger.warning("XGBoost not available. Using GradientBoostingRegressor fallback.")

try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    logger.warning("TensorFlow not available. Using RandomForestRegressor fallback for LSTM.")

# ── Explanations ─────────────────────────────────────────────────────────────

FEATURE_EXPLANATIONS = {
    "day_of_week": "Weekly Cycle: Captures demand patterns based on the day (e.g., higher on weekends).",
    "day_of_month": "Monthly Cycle: Captures patterns like end-of-month shopping or salary cycles.",
    "month": "Seasonality: Accounts for monthly variations like holidays or seasonal shifts.",
    "day_of_year": "Annual Trend: Tracks the position in the year for long-term seasonality.",
    "week_of_year": "Weekly Seasonality: Captures weekly trends across the year.",
    "is_weekend": "Weekend Effect: Identifies higher traffic typical on Saturdays and Sundays.",
    "is_festival": "Holiday Impact: Accounts for spikes during festivals and public holidays.",
    "temperature": "Weather (Temp): Higher temperatures often correlate with increased beverage/cold food sales.",
    "rainfall_mm": "Weather (Rain): Precipitation can significantly reduce outdoor footfall.",
    "lag_7": "Last Week's Anchor: The strongest predictor, based on sales exactly 7 days ago.",
    "lag_14": "Fortnightly Trend: Patterns from 14 days ago to capture bi-weekly cycles.",
    "lag_30": "Monthly Anchor: Sales from 30 days ago to handle monthly repetition.",
    "roll_7": "Momentum: The average demand over the last 7 days, indicating current pace.",
}

# ── Metrics ──────────────────────────────────────────────────────────────────

def calc_metrics(actual: np.ndarray, predicted: np.ndarray) -> Dict[str, float]:
    """Calculates MAE, RMSE, and MAPE metrics.
    
    Args:
        actual: Actual values.
        predicted: Predicted values.
        
    Returns:
        Dictionary containing metric names and values.
    """
    actual = np.array(actual)
    predicted = np.array(predicted)
    mae = mean_absolute_error(actual, predicted)
    rmse = np.sqrt(mean_squared_error(actual, predicted))
    mape = np.mean(np.abs((actual - predicted) / np.clip(actual, 1, None))) * 100
    return {"MAE": round(mae, 2), "RMSE": round(rmse, 2), "MAPE": round(mape, 2)}

# ── Feature engineering ──────────────────────────────────────────────────────

def build_features(ts: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Builds features for time series forecasting models.
    
    Args:
        ts: Input time series DataFrame with 'date' and 'quantity_sold'.
        
    Returns:
        A tuple of (DataFrame with features, list of feature names).
    """
    df = ts.copy()
    df["day_of_week"] = df["date"].dt.dayofweek
    df["day_of_month"] = df["date"].dt.day
    df["month"] = df["date"].dt.month
    df["day_of_year"] = df["date"].dt.dayofyear
    df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)
    df["lag_7"] = df["quantity_sold"].shift(7).bfill()
    df["lag_14"] = df["quantity_sold"].shift(14).bfill()
    df["lag_30"] = df["quantity_sold"].shift(30).bfill()
    df["roll_7"] = df["quantity_sold"].rolling(7, min_periods=1).mean()
    
    features = [
        "day_of_week", "day_of_month", "month", "day_of_year", "week_of_year",
        "is_weekend", "is_festival", "temperature", "rainfall_mm",
        "lag_7", "lag_14", "lag_30", "roll_7",
    ]
    return df, features

# ── Prophet ──────────────────────────────────────────────────────────────────

def prophet_forecast(ts: pd.DataFrame, horizon: int) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """Generates demand forecast using Facebook Prophet.
    
    Args:
        ts: Input time series.
        horizon: Forecasting horizon in days.
        
    Returns:
        Tuple of (forecast DataFrame, metrics dictionary).
    """
    if not PROPHET_AVAILABLE:
        return _fallback_forecast(ts, horizon, "Prophet")
        
    prophet_df = ts[["date", "quantity_sold"]].rename(columns={"date": "ds", "quantity_sold": "y"})
    m = Prophet(
        yearly_seasonality=True, weekly_seasonality=True, daily_seasonality=False,
        seasonality_mode="multiplicative", interval_width=0.80
    )
    m.add_regressor("is_weekend")
    m.add_regressor("is_festival")
    
    prophet_df["is_weekend"] = ts["is_weekend"].values
    prophet_df["is_festival"] = ts["is_festival"].values
    
    logger.info("Fitting Prophet model...")
    m.fit(prophet_df)

    future = m.make_future_dataframe(periods=horizon)
    future["is_weekend"] = future["ds"].dt.dayofweek.isin([5, 6]).astype(int)
    future["is_festival"] = 0  # Simplified for example
    
    forecast = m.predict(future)
    future_fc = forecast.tail(horizon)[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
    future_fc.columns = ["date", "predicted", "lower", "upper"]
    future_fc["predicted"] = future_fc["predicted"].clip(lower=0).round().astype(int)
    future_fc["lower"] = future_fc["lower"].clip(lower=0).round().astype(int)
    future_fc["upper"] = future_fc["upper"].clip(lower=0).round().astype(int)

    in_sample = forecast.iloc[: len(ts)][["yhat"]].values.flatten()
    metrics = calc_metrics(ts["quantity_sold"].values, in_sample)
    return future_fc, metrics

# ── XGBoost ──────────────────────────────────────────────────────────────────

def xgboost_forecast(
    ts: pd.DataFrame, 
    horizon: int,
    external_forecast: Optional[pd.DataFrame] = None
) -> Tuple[pd.DataFrame, Dict[str, float], Dict[str, float]]:
    """Generates demand forecast using XGBoost.
    
    Args:
        ts: Input time series.
        horizon: Forecasting horizon in days.
        external_forecast: Optional real-time weather/event forecast.
        
    Returns:
        Tuple of (forecast DataFrame, metrics, feature importances).
    """
    df, features = build_features(ts)
    X = df[features].values
    y = df["quantity_sold"].values
    split = max(int(len(X) * 0.85), len(X) - 60)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    if XGB_AVAILABLE:
        model = xgb.XGBRegressor(
            n_estimators=200, max_depth=5, learning_rate=0.08,
            subsample=0.8, random_state=42, verbosity=0
        )
    else:
        model = GradientBoostingRegressor(
            n_estimators=150, max_depth=4, learning_rate=0.08, random_state=42
        )

    logger.info(f"Fitting {'XGBoost' if XGB_AVAILABLE else 'GBM'} model...")
    model.fit(X_train, y_train)
    metrics = calc_metrics(y_test, model.predict(X_test))

    # Rolling future prediction
    last_row = df.iloc[-1].copy()
    last_date = ts["date"].max()
    future_rows = []
    extended_qty = list(ts["quantity_sold"].values)

    for i in range(1, horizon + 1):
        fd = last_date + pd.Timedelta(days=i)
        
        # Check for external real-time data
        current_temp = last_row["temperature"]
        current_rain = 0.5
        
        if external_forecast is not None:
            match = external_forecast[external_forecast["date"].dt.date == fd.date()]
            if not match.empty:
                current_temp = match.iloc[0]["temperature"]
                current_rain = match.iloc[0]["rainfall_mm"]

        row = {
            "day_of_week": fd.dayofweek,
            "day_of_month": fd.day,
            "month": fd.month,
            "day_of_year": fd.dayofyear,
            "week_of_year": int(fd.isocalendar().week),
            "is_weekend": int(fd.dayofweek >= 5),
            "is_festival": 0,
            "temperature": current_temp,
            "rainfall_mm": current_rain,
            "lag_7": extended_qty[-7] if len(extended_qty) >= 7 else extended_qty[-1],
            "lag_14": extended_qty[-14] if len(extended_qty) >= 14 else extended_qty[-1],
            "lag_30": extended_qty[-30] if len(extended_qty) >= 30 else extended_qty[-1],
            "roll_7": np.mean(extended_qty[-7:]),
        }
        future_rows.append(row)
        
        # Prepare single row for prediction
        input_data = np.array([[row[f] for f in features]])
        pred = max(0, model.predict(input_data)[0])
        extended_qty.append(int(pred))

    future_df = pd.DataFrame(future_rows)
    preds = model.predict(future_df[features].values).clip(min=0).round().astype(int)
    std_ = np.std(y_train) * 0.25
    result = pd.DataFrame({
        "date": [last_date + pd.Timedelta(days=i) for i in range(1, horizon + 1)],
        "predicted": preds,
        "lower": np.clip(preds - int(std_), 0, None),
        "upper": preds + int(std_),
    })
    feat_imp = dict(zip(features, model.feature_importances_))
    return result, metrics, feat_imp

# ── LSTM ─────────────────────────────────────────────────────────────────────

def lstm_forecast(
    ts: pd.DataFrame, 
    horizon: int, 
    seq_len: int = 14
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """Generates demand forecast using LSTM.
    
    Args:
        ts: Input time series.
        horizon: Forecasting horizon in days.
        seq_len: Length of historical sequence used for prediction.
        
    Returns:
        Tuple of (forecast DataFrame, metrics).
    """
    series = ts["quantity_sold"].values.astype(float)
    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(series.reshape(-1, 1)).flatten()

    def make_sequences(data, sl):
        X, y = [], []
        for i in range(len(data) - sl):
            X.append(data[i: i + sl])
            y.append(data[i + sl])
        return np.array(X), np.array(y)

    X_all, y_all = make_sequences(scaled, seq_len)
    split = max(int(len(X_all) * 0.85), len(X_all) - 60)
    X_train = X_all[:split].reshape(-1, seq_len, 1)
    y_train = y_all[:split]
    X_test = X_all[split:].reshape(-1, seq_len, 1)
    y_test = y_all[split:]

    if TF_AVAILABLE:
        logger.info("Fitting LSTM model...")
        tf.random.set_seed(42)
        model = Sequential([
            LSTM(32, return_sequences=True, input_shape=(seq_len, 1)),
            Dropout(0.1),
            LSTM(16),
            Dense(1),
        ])
        model.compile(optimizer="adam", loss="mse")
        model.fit(X_train, y_train, epochs=20, batch_size=32, verbose=0)
        test_preds_scaled = model.predict(X_test, verbose=0).flatten()
    else:
        logger.info("Fitting fallback RandomForest model for LSTM...")
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X_train.reshape(len(X_train), -1), y_train)
        test_preds_scaled = model.predict(X_test.reshape(len(X_test), -1))

    test_preds = scaler.inverse_transform(test_preds_scaled.reshape(-1, 1)).flatten()
    y_test_inv = scaler.inverse_transform(y_test.reshape(-1, 1)).flatten()
    metrics = calc_metrics(y_test_inv, test_preds)

    # Rolling future prediction
    window = list(scaled[-seq_len:])
    future_preds_scaled = []
    for _ in range(horizon):
        inp = np.array(window[-seq_len:]).reshape(1, seq_len, 1)
        if TF_AVAILABLE:
            p = model.predict(inp, verbose=0)[0][0]
        else:
            p = model.predict(inp.reshape(1, -1))[0]
        future_preds_scaled.append(p)
        window.append(p)

    preds = scaler.inverse_transform(
        np.array(future_preds_scaled).reshape(-1, 1)
    ).flatten().clip(min=0).round().astype(int)

    std_ = np.std(series) * 0.2
    last_date = ts["date"].max()
    result = pd.DataFrame({
        "date": [last_date + pd.Timedelta(days=i) for i in range(1, horizon + 1)],
        "predicted": preds,
        "lower": np.clip(preds - int(std_), 0, None),
        "upper": preds + int(std_),
    })
    return result, metrics

# ── Ensemble ─────────────────────────────────────────────────────────────────

def ensemble_forecast(
    ts: pd.DataFrame, 
    horizon: int,
    external_forecast: Optional[pd.DataFrame] = None
) -> Tuple[pd.DataFrame, Dict[str, float], Dict[str, Any], Optional[Dict[str, float]]]:
    """Combines multiple models into an ensemble forecast.
    
    Args:
        ts: Input time series.
        horizon: Forecasting horizon in days.
        external_forecast: Optional real-time weather/event forecast.
        
    Returns:
        Tuple of (ensemble forecast, metrics, individual results, feature importances).
    """
    results = {}
    all_preds = []

        fc_p, met_p = prophet_forecast(ts, horizon)
        results["Prophet"] = (fc_p, met_p)
        all_preds.append(fc_p["predicted"].values)
    
    # Pass external_forecast to XGBoost
    fc_x, met_x, feat_imp = xgboost_forecast(ts, horizon, external_forecast)
    results["XGBoost"] = (fc_x, met_x)
    all_preds.append(fc_x["predicted"].values)

    fc_l, met_l = lstm_forecast(ts, horizon)
    results["LSTM"] = (fc_l, met_l)
    all_preds.append(fc_l["predicted"].values)

    ensemble_pred = np.mean(all_preds, axis=0).round().astype(int)
    ensemble_std = np.std(all_preds, axis=0)
    last_date = ts["date"].max()
    
    ensemble_fc = pd.DataFrame({
        "date": [last_date + pd.Timedelta(days=i) for i in range(1, horizon + 1)],
        "predicted": ensemble_pred,
        "lower": np.clip(ensemble_pred - ensemble_std.astype(int), 0, None),
        "upper": (ensemble_pred + ensemble_std).astype(int),
    })
    
    # Ensemble metrics: average of component metrics
    all_metrics = [v[1] for v in results.values()]
    avg_metrics = {
        k: round(np.mean([m[k] for m in all_metrics]), 2) 
        for k in ["MAE", "RMSE", "MAPE"]
    }
    return ensemble_fc, avg_metrics, results, feat_imp

# ── Fallback ─────────────────────────────────────────────────────────────────

def _fallback_forecast(ts: pd.DataFrame, horizon: int, name: str) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """Simple random-walk fallback for unavailable models.
    
    Args:
        ts: Input time series.
        horizon: Forecasting horizon.
        name: Name of the missing model.
        
    Returns:
        Tuple of (dummy forecast, empty metrics).
    """
    logger.info(f"Executing fallback for {name} forecast...")
    last_date = ts["date"].max()
    mean_val = int(ts["quantity_sold"].tail(30).mean())
    std_val = int(ts["quantity_sold"].tail(30).std())
    preds = np.clip(
        np.random.normal(mean_val, std_val * 0.1, horizon), 5, None
    ).round().astype(int)
    
    result = pd.DataFrame({
        "date": [last_date + pd.Timedelta(days=i) for i in range(1, horizon + 1)],
        "predicted": preds,
        "lower": np.clip(preds - std_val, 0, None),
        "upper": preds + std_val,
    })
    metrics = {"MAE": 0.0, "RMSE": 0.0, "MAPE": 0.0}
    return result, metrics
