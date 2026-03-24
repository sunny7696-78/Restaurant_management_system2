import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
import warnings
warnings.filterwarnings("ignore")

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False


# ── Metrics ──────────────────────────────────────────────────────────────────

def calc_metrics(actual, predicted):
    actual    = np.array(actual)
    predicted = np.array(predicted)
    mae  = mean_absolute_error(actual, predicted)
    rmse = np.sqrt(mean_squared_error(actual, predicted))
    mape = np.mean(np.abs((actual - predicted) / np.clip(actual, 1, None))) * 100
    return {"MAE": round(mae, 2), "RMSE": round(rmse, 2), "MAPE": round(mape, 2)}


# ── Feature engineering ──────────────────────────────────────────────────────

def build_features(ts: pd.DataFrame):
    df = ts.copy()
    df["day_of_week"]  = df["date"].dt.dayofweek
    df["day_of_month"] = df["date"].dt.day
    df["month"]        = df["date"].dt.month
    df["day_of_year"]  = df["date"].dt.dayofyear
    df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)
    df["lag_7"]  = df["quantity_sold"].shift(7).bfill()
    df["lag_14"] = df["quantity_sold"].shift(14).bfill()
    df["lag_30"] = df["quantity_sold"].shift(30).bfill()
    df["roll_7"] = df["quantity_sold"].rolling(7, min_periods=1).mean()
    FEATURES = [
        "day_of_week","day_of_month","month","day_of_year","week_of_year",
        "is_weekend","is_festival","temperature","rainfall_mm",
        "lag_7","lag_14","lag_30","roll_7",
    ]
    return df, FEATURES


# ── Prophet ──────────────────────────────────────────────────────────────────

def prophet_forecast(ts: pd.DataFrame, horizon: int):
    if not PROPHET_AVAILABLE:
        return _fallback_forecast(ts, horizon, "Prophet")
    prophet_df = ts[["date", "quantity_sold"]].rename(columns={"date": "ds", "quantity_sold": "y"})
    m = Prophet(yearly_seasonality=True, weekly_seasonality=True, daily_seasonality=False,
                seasonality_mode="multiplicative", interval_width=0.80)
    m.add_regressor("is_weekend")
    m.add_regressor("is_festival")
    prophet_df["is_weekend"]  = ts["is_weekend"].values
    prophet_df["is_festival"] = ts["is_festival"].values
    m.fit(prophet_df)

    last_date  = ts["date"].max()
    future     = m.make_future_dataframe(periods=horizon)
    future["is_weekend"]  = future["ds"].dt.dayofweek.isin([5, 6]).astype(int)
    future["is_festival"] = 0
    forecast   = m.predict(future)
    future_fc  = forecast.tail(horizon)[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
    future_fc.columns = ["date", "predicted", "lower", "upper"]
    future_fc["predicted"] = future_fc["predicted"].clip(lower=0).round().astype(int)
    future_fc["lower"]     = future_fc["lower"].clip(lower=0).round().astype(int)
    future_fc["upper"]     = future_fc["upper"].clip(lower=0).round().astype(int)

    in_sample  = forecast.iloc[: len(ts)][["yhat"]].values.flatten()
    metrics    = calc_metrics(ts["quantity_sold"].values, in_sample)
    return future_fc, metrics


# ── XGBoost ──────────────────────────────────────────────────────────────────

def xgboost_forecast(ts: pd.DataFrame, horizon: int):
    df, FEATURES = build_features(ts)
    X = df[FEATURES].values
    y = df["quantity_sold"].values
    split = max(int(len(X) * 0.85), len(X) - 60)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    if XGB_AVAILABLE:
        model = xgb.XGBRegressor(n_estimators=200, max_depth=5, learning_rate=0.08,
                                  subsample=0.8, random_state=42, verbosity=0)
    else:
        model = GradientBoostingRegressor(n_estimators=150, max_depth=4, learning_rate=0.08, random_state=42)

    model.fit(X_train, y_train)
    metrics = calc_metrics(y_test, model.predict(X_test))

    # Build future feature rows
    last_row  = df.iloc[-1].copy()
    last_date = ts["date"].max()
    future_rows = []
    extended_qty = list(ts["quantity_sold"].values)

    for i in range(1, horizon + 1):
        fd = last_date + pd.Timedelta(days=i)
        row = {
            "day_of_week":  fd.dayofweek,
            "day_of_month": fd.day,
            "month":        fd.month,
            "day_of_year":  fd.dayofyear,
            "week_of_year": fd.isocalendar().week,
            "is_weekend":   int(fd.dayofweek >= 5),
            "is_festival":  0,
            "temperature":  last_row["temperature"],
            "rainfall_mm":  0.5,
            "lag_7":        extended_qty[-7]  if len(extended_qty) >= 7  else extended_qty[-1],
            "lag_14":       extended_qty[-14] if len(extended_qty) >= 14 else extended_qty[-1],
            "lag_30":       extended_qty[-30] if len(extended_qty) >= 30 else extended_qty[-1],
            "roll_7":       np.mean(extended_qty[-7:]),
        }
        future_rows.append(row)
        pred = max(0, model.predict(np.array([[row[f] for f in FEATURES]]))[0])
        extended_qty.append(int(pred))

    future_df = pd.DataFrame(future_rows)
    preds = model.predict(future_df[FEATURES].values).clip(min=0).round().astype(int)
    std_  = np.std(y_train) * 0.25
    result = pd.DataFrame({
        "date":      [last_date + pd.Timedelta(days=i) for i in range(1, horizon + 1)],
        "predicted": preds,
        "lower":     np.clip(preds - int(std_), 0, None),
        "upper":     preds + int(std_),
    })
    feat_imp = dict(zip(FEATURES, model.feature_importances_))
    return result, metrics, feat_imp


# ── LSTM ─────────────────────────────────────────────────────────────────────

def lstm_forecast(ts: pd.DataFrame, horizon: int, seq_len: int = 14):
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
    split   = max(int(len(X_all) * 0.85), len(X_all) - 60)
    X_train = X_all[:split].reshape(-1, seq_len, 1)
    y_train = y_all[:split]
    X_test  = X_all[split:].reshape(-1, seq_len, 1)
    y_test  = y_all[split:]

    if TF_AVAILABLE:
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
        # Fallback: simple RF on lag features
        rf = RandomForestRegressor(n_estimators=100, random_state=42)
        rf.fit(X_train.reshape(len(X_train), -1), y_train)
        test_preds_scaled = rf.predict(X_test.reshape(len(X_test), -1))

    test_preds = scaler.inverse_transform(test_preds_scaled.reshape(-1, 1)).flatten()
    y_test_inv = scaler.inverse_transform(y_test.reshape(-1, 1)).flatten()
    metrics    = calc_metrics(y_test_inv, test_preds)

    # Rolling future prediction
    window = list(scaled[-seq_len:])
    future_preds_scaled = []
    for _ in range(horizon):
        inp = np.array(window[-seq_len:]).reshape(1, seq_len, 1)
        if TF_AVAILABLE:
            p = model.predict(inp, verbose=0)[0][0]
        else:
            p = rf.predict(inp.reshape(1, -1))[0]
        future_preds_scaled.append(p)
        window.append(p)

    preds = scaler.inverse_transform(
        np.array(future_preds_scaled).reshape(-1, 1)
    ).flatten().clip(min=0).round().astype(int)

    std_ = np.std(series) * 0.2
    last_date = ts["date"].max()
    result = pd.DataFrame({
        "date":      [last_date + pd.Timedelta(days=i) for i in range(1, horizon + 1)],
        "predicted": preds,
        "lower":     np.clip(preds - int(std_), 0, None),
        "upper":     preds + int(std_),
    })
    return result, metrics


# ── Ensemble ─────────────────────────────────────────────────────────────────

def ensemble_forecast(ts, horizon):
    results = {}
    all_preds = []

    if PROPHET_AVAILABLE:
        fc_p, met_p = prophet_forecast(ts, horizon)
        results["Prophet"] = (fc_p, met_p)
        all_preds.append(fc_p["predicted"].values)

    fc_x, met_x, feat_imp = xgboost_forecast(ts, horizon)
    results["XGBoost"] = (fc_x, met_x)
    all_preds.append(fc_x["predicted"].values)

    fc_l, met_l = lstm_forecast(ts, horizon)
    results["LSTM"] = (fc_l, met_l)
    all_preds.append(fc_l["predicted"].values)

    ensemble_pred = np.mean(all_preds, axis=0).round().astype(int)
    ensemble_std  = np.std(all_preds, axis=0)
    last_date = ts["date"].max()
    ensemble_fc = pd.DataFrame({
        "date":      [last_date + pd.Timedelta(days=i) for i in range(1, horizon + 1)],
        "predicted": ensemble_pred,
        "lower":     np.clip(ensemble_pred - ensemble_std.astype(int), 0, None),
        "upper":     (ensemble_pred + ensemble_std).astype(int),
    })
    # Ensemble metrics: average of component metrics
    all_metrics = [v[1] for v in results.values()]
    avg_metrics = {k: round(np.mean([m[k] for m in all_metrics]), 2) for k in ["MAE", "RMSE", "MAPE"]}
    return ensemble_fc, avg_metrics, results, feat_imp


# ── Fallback ─────────────────────────────────────────────────────────────────

def _fallback_forecast(ts, horizon, name):
    last_date = ts["date"].max()
    mean_val  = int(ts["quantity_sold"].tail(30).mean())
    std_val   = int(ts["quantity_sold"].tail(30).std())
    preds     = np.clip(
        np.random.normal(mean_val, std_val * 0.1, horizon), 5, None
    ).round().astype(int)
    result = pd.DataFrame({
        "date":      [last_date + pd.Timedelta(days=i) for i in range(1, horizon + 1)],
        "predicted": preds,
        "lower":     np.clip(preds - std_val, 0, None),
        "upper":     preds + std_val,
    })
    metrics = {"MAE": 0.0, "RMSE": 0.0, "MAPE": 0.0}
    return result, metrics
