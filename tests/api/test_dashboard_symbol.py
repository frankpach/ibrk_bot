# tests/api/test_dashboard_symbol.py
"""Tests for /dashboard/symbol/{symbol} period parameter."""
import numpy as np
import pandas as pd
from unittest.mock import patch
from fastapi.testclient import TestClient

_TEST_CONTROL_KEY = "test-control-key"


def _make_df(n=30):
    dates = pd.date_range("2026-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "open": np.full(n, 100.0),
        "high": np.full(n, 105.0),
        "low": np.full(n, 95.0),
        "close": np.linspace(100, 110, n),
        "volume": np.full(n, 1_000_000),
    }, index=dates)


def _get_client():
    import sys
    for mod in list(sys.modules.keys()):
        if "app.api.main" in mod:
            del sys.modules[mod]
    from app.api.main import app
    return TestClient(app, headers={"X-Control-Key": _TEST_CONTROL_KEY})


def test_period_1h_calls_correct_bar_size():
    with patch("app.llm.agent.get_data_layer") as mock_dl:
        mock_dl.return_value.get_ohlcv.return_value = _make_df()
        client = _get_client()
        resp = client.get("/dashboard/symbol/AAPL?period=1h")
    assert resp.status_code == 200
    calls = mock_dl.return_value.get_ohlcv.call_args_list
    # First call should use "1 hour"
    assert any("1 hour" in str(c) for c in calls)


def test_period_weekly_returns_bars():
    with patch("app.llm.agent.get_data_layer") as mock_dl:
        mock_dl.return_value.get_ohlcv.return_value = _make_df(52)
        client = _get_client()
        resp = client.get("/dashboard/symbol/AAPL?period=weekly")
    assert resp.status_code == 200
    assert len(resp.json()["bars"]) == 52


def test_period_monthly_returns_bars():
    with patch("app.llm.agent.get_data_layer") as mock_dl:
        mock_dl.return_value.get_ohlcv.return_value = _make_df(24)
        client = _get_client()
        resp = client.get("/dashboard/symbol/AAPL?period=monthly")
    assert resp.status_code == 200
    assert len(resp.json()["bars"]) == 24


def test_unknown_period_falls_back_to_daily():
    with patch("app.llm.agent.get_data_layer") as mock_dl:
        mock_dl.return_value.get_ohlcv.return_value = _make_df()
        client = _get_client()
        resp = client.get("/dashboard/symbol/AAPL?period=bogus")
    assert resp.status_code == 200
    assert "bars" in resp.json()


def test_none_df_returns_empty_bars():
    with patch("app.llm.agent.get_data_layer") as mock_dl:
        mock_dl.return_value.get_ohlcv.return_value = None
        client = _get_client()
        resp = client.get("/dashboard/symbol/AAPL?period=4h")
    assert resp.status_code == 200
    assert resp.json()["bars"] == []
