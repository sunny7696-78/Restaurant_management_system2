"""Tests for data generation logic."""

import pytest
import pandas as pd
from data_generator import generate_dataset, get_time_series, RESTAURANTS, CATEGORIES

def test_generate_dataset_structure():
    """Verifies the generated dataset has the correct columns and restaurants."""
    df = generate_dataset(days=10)
    
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert len(df["restaurant_id"].unique()) == len(RESTAURANTS)
    
    expected_columns = [
        "date", "restaurant_id", "restaurant_name", "category",
        "quantity_sold", "revenue", "waste_kg", "stock_level",
        "temperature", "rainfall_mm", "is_weekend", "is_festival"
    ]
    for col in expected_columns:
        assert col in df.columns

def test_get_time_series():
    """Verifies that get_time_series filters data correctly."""
    df = generate_dataset(days=30)
    rest_id = list(RESTAURANTS.keys())[0]
    category = CATEGORIES[0]
    
    ts = get_time_series(df, rest_id, category)
    
    assert len(ts) == 30
    assert (ts["restaurant_id"] == rest_id).all()
    assert (ts["category"] == category).all()
    assert ts["date"].is_monotonic_increasing
