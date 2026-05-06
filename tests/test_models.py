"""Tests for machine learning model helpers."""

import numpy as np
from models import calc_metrics

def test_calc_metrics():
    """Verifies that metrics calculation is accurate."""
    actual = np.array([10, 20, 30, 40, 50])
    predicted = np.array([12, 18, 33, 37, 55])
    
    metrics = calc_metrics(actual, predicted)
    
    assert "MAE" in metrics
    assert "RMSE" in metrics
    assert "MAPE" in metrics
    
    # Simple checks on values
    assert metrics["MAE"] > 0
    assert metrics["RMSE"] > metrics["MAE"]
    assert metrics["MAPE"] > 0
