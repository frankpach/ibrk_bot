# tests/analysis/test_indicators.py
"""Tests for MTE-006: df_hourly activation + new FeatureSet fields."""
import pytest
import pandas as pd
from datetime import datetime, timezone

from app.analysis.indicators import FeatureSet, compute_features


def _make_daily_df(n: int = 60) -> pd.DataFrame:
    """Create a minimal daily OHLCV DataFrame with n rows."""
    closes = [100.0 + i * 0.1 for i in range(n)]
    return pd.DataFrame({
        "open": closes,
        "high": [c + 0.5 for c in closes],
        "low": [c - 0.5 for c in closes],
        "close": closes,
        "volume": [1_000_000] * n,
    })


def _make_hourly_df(n: int = 30) -> pd.DataFrame:
    """Create a minimal hourly OHLCV DataFrame with n rows."""
    closes = [100.0 + i * 0.05 for i in range(n)]
    return pd.DataFrame({
        "open": closes,
        "high": [c + 0.2 for c in closes],
        "low": [c - 0.2 for c in closes],
        "close": closes,
        "volume": [500_000] * n,
    })


# --- FeatureSet dataclass field tests ---

def test_featureset_has_rsi_1h_field():
    fs = FeatureSet(symbol="AAPL", timestamp=datetime.now(timezone.utc))
    assert hasattr(fs, "rsi_1h")
    assert fs.rsi_1h is None


def test_featureset_has_volume_ratio_1h_field():
    fs = FeatureSet(symbol="AAPL", timestamp=datetime.now(timezone.utc))
    assert hasattr(fs, "volume_ratio_1h")
    assert fs.volume_ratio_1h is None


def test_featureset_has_weekly_trend_field():
    fs = FeatureSet(symbol="AAPL", timestamp=datetime.now(timezone.utc))
    assert hasattr(fs, "weekly_trend")
    assert fs.weekly_trend is None


def test_featureset_to_dict_includes_new_fields():
    fs = FeatureSet(symbol="AAPL", timestamp=datetime.now(timezone.utc))
    fs.rsi_1h = 55.5
    fs.volume_ratio_1h = 1.2
    fs.weekly_trend = "BULLISH"
    d = fs.to_dict()
    assert "rsi_1h" in d
    assert d["rsi_1h"] == 55.5
    assert "volume_ratio_1h" in d
    assert d["volume_ratio_1h"] == 1.2
    assert "weekly_trend" in d
    assert d["weekly_trend"] == "BULLISH"


# --- compute_features with df_hourly=None ---

def test_compute_features_no_hourly_rsi_1h_is_none():
    """When df_hourly is None, rsi_1h and volume_ratio_1h remain None."""
    df_daily = _make_daily_df(60)
    fs = compute_features("AAPL", df_daily, df_hourly=None)
    assert fs.rsi_1h is None
    assert fs.volume_ratio_1h is None


def test_compute_features_no_hourly_weekly_trend_is_none():
    df_daily = _make_daily_df(60)
    fs = compute_features("AAPL", df_daily, df_hourly=None)
    assert fs.weekly_trend is None


# --- compute_features with valid df_hourly ---

def test_compute_features_with_hourly_rsi_1h_is_float():
    """When df_hourly has >=15 rows, rsi_1h should be a float between 0-100."""
    df_daily = _make_daily_df(60)
    df_hourly = _make_hourly_df(30)
    fs = compute_features("AAPL", df_daily, df_hourly=df_hourly)
    assert fs.rsi_1h is not None
    assert isinstance(fs.rsi_1h, float)
    assert 0.0 <= fs.rsi_1h <= 100.0


def test_compute_features_with_hourly_volume_ratio_1h_is_float():
    """When df_hourly has >=21 rows, volume_ratio_1h should be a positive float."""
    df_daily = _make_daily_df(60)
    df_hourly = _make_hourly_df(30)
    fs = compute_features("AAPL", df_daily, df_hourly=df_hourly)
    assert fs.volume_ratio_1h is not None
    assert isinstance(fs.volume_ratio_1h, float)
    assert fs.volume_ratio_1h > 0.0


def test_compute_features_hourly_too_short_rsi_1h_is_none():
    """When df_hourly has <15 rows, rsi_1h should remain None."""
    df_daily = _make_daily_df(60)
    df_hourly = _make_hourly_df(10)  # too short for RSI
    fs = compute_features("AAPL", df_daily, df_hourly=df_hourly)
    assert fs.rsi_1h is None


def test_compute_features_daily_unaffected_by_hourly():
    """Adding df_hourly should not change existing daily features."""
    df_daily = _make_daily_df(60)
    fs_no_hourly = compute_features("AAPL", df_daily, df_hourly=None)
    df_hourly = _make_hourly_df(30)
    fs_with_hourly = compute_features("AAPL", df_daily, df_hourly=df_hourly)

    assert fs_no_hourly.rsi_14 == pytest.approx(fs_with_hourly.rsi_14, abs=0.01)
    assert fs_no_hourly.volume_ratio_20d == pytest.approx(fs_with_hourly.volume_ratio_20d, abs=0.01)


# --- _extract_features length test ---

def test_extract_features_returns_10_elements():
    """_extract_features should return a list of 10 elements after MTE-006."""
    from app.ml.signal_filter import SignalFilter
    sf = SignalFilter(model_path="/nonexistent")
    fs = FeatureSet(symbol="AAPL", timestamp=datetime.now(timezone.utc))
    fs.rsi_14 = 55.0
    fs.macd_line = 0.1
    fs.atr_pct = 2.0
    fs.volume_ratio_20d = 1.2
    fs.bollinger_position = 0.6
    fs.rs_vs_spy_30d = 0.01
    fs.rsi_1h = 60.0
    fs.volume_ratio_1h = 1.1
    result = sf._extract_features(fs)
    assert len(result) == 12  # 10 original + vol_regime + vwap_dev


def test_extract_features_new_fields_from_featureset():
    """rsi_1h and volume_ratio_1h are correctly extracted from FeatureSet."""
    from app.ml.signal_filter import SignalFilter
    sf = SignalFilter(model_path="/nonexistent")
    fs = FeatureSet(symbol="AAPL", timestamp=datetime.now(timezone.utc))
    fs.rsi_1h = 65.0
    fs.volume_ratio_1h = 1.5
    result = sf._extract_features(fs)
    assert result[8] == 65.0   # rsi_1h at index 8
    assert result[9] == 1.5    # volume_ratio_1h at index 9


def test_extract_features_new_fields_default_when_none():
    """When rsi_1h/volume_ratio_1h are None, defaults (50, 1.0) are used."""
    from app.ml.signal_filter import SignalFilter
    sf = SignalFilter(model_path="/nonexistent")
    fs = FeatureSet(symbol="AAPL", timestamp=datetime.now(timezone.utc))
    # rsi_1h and volume_ratio_1h are None by default
    result = sf._extract_features(fs)
    assert result[8] == 50     # default rsi_1h
    assert result[9] == 1.0   # default volume_ratio_1h


def test_extract_features_new_fields_from_dict():
    """New fields work when features is a dict (from DB snapshot)."""
    from app.ml.signal_filter import SignalFilter
    sf = SignalFilter(model_path="/nonexistent")
    snap = {
        "rsi_14": 45.0, "macd_line": 0.0, "atr_pct": 2.0,
        "volume_ratio_20d": 1.0, "bollinger_position": 0.5,
        "rs_vs_spy_30d": 0.0, "day_of_week": 1, "hour": 10,
        "rsi_1h": 70.0, "volume_ratio_1h": 2.0,
    }
    result = sf._extract_features(snap)
    assert len(result) == 12  # 10 original + vol_regime + vwap_dev
    assert result[8] == 70.0
    assert result[9] == 2.0
