"""Tests for buying power pre-flight in /orders/preview and /orders/place."""
import sys
import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch, MagicMock

ET = ZoneInfo("America/New_York")
MARKET_OPEN_DT = datetime(2026, 5, 5, 10, 0, 0, tzinfo=ET)  # Tuesday 10am

_TEST_CONTROL_KEY = "test-control-key"


def _fresh_app():
    for mod in list(sys.modules.keys()):
        if "app.api.main" in mod:
            del sys.modules[mod]
    from fastapi.testclient import TestClient
    from app.api.main import app
    return TestClient(app, headers={"X-Control-Key": _TEST_CONTROL_KEY})


def _account(buying_power: float, net_liq: float = 500.0):
    return {"net_liquidation": net_liq, "buying_power": buying_power, "cash_balance": buying_power}


def _preview_payload():
    return {"symbol": "AAPL", "action": "BUY", "quantity": 1,
            "order_type": "MKT", "stop_loss_pct": 0.02, "take_profit_pct": 0.04}


def _place_payload():
    return {"symbol": "AAPL", "action": "BUY", "quantity": 1,
            "order_type": "MKT", "stop_loss_pct": 0.02, "take_profit_pct": 0.04}


def test_preview_rejects_when_insufficient_buying_power():
    mock_ibkr = MagicMock()
    mock_ibkr.ib.isConnected.return_value = True
    mock_ibkr.get_stock_price.return_value = {"market_price": 100.0}
    mock_ibkr.get_account.return_value = _account(buying_power=10.0)
    mock_ibkr.get_portfolio.return_value = []

    with patch("app.ibkr.client.get_client", return_value=mock_ibkr), \
         patch("app.api.main.datetime") as mock_dt:
        mock_dt.now.return_value = MARKET_OPEN_DT
        tc = _fresh_app()
        resp = tc.post("/orders/preview", json=_preview_payload())

    assert resp.status_code == 400, resp.json()
    assert "buying power" in resp.json()["detail"].lower()


def test_preview_accepts_when_sufficient_buying_power():
    mock_ibkr = MagicMock()
    mock_ibkr.ib.isConnected.return_value = True
    mock_ibkr.get_stock_price.return_value = {"market_price": 100.0}
    mock_ibkr.get_account.return_value = _account(buying_power=1_000.0, net_liq=1_000.0)
    mock_ibkr.get_portfolio.return_value = []

    with patch("app.ibkr.client.get_client", return_value=mock_ibkr), \
         patch("app.api.main.datetime") as mock_dt:
        mock_dt.now.return_value = MARKET_OPEN_DT
        tc = _fresh_app()
        resp = tc.post("/orders/preview", json=_preview_payload())

    assert resp.status_code == 200, resp.json()


def test_place_rejects_when_zero_units():
    mock_ibkr = MagicMock()
    mock_ibkr.ib.isConnected.return_value = True
    mock_ibkr.get_stock_price.return_value = {"market_price": 100.0}
    mock_ibkr.get_account.return_value = _account(buying_power=1_000.0, net_liq=1_000.0)
    mock_ibkr.get_portfolio.return_value = []

    from app.risk.validator import ValidationResult
    from app.ibkr.dedup import OrderDeduplicator

    with patch("app.ibkr.client.get_client", return_value=mock_ibkr), \
         patch("app.api.main.datetime") as mock_dt, \
         patch("app.risk.validator.validate_order",
               return_value=ValidationResult(approved=True, reasons=["ok"])), \
         patch("app.ibkr.dedup.PreflightChecker.check",
               return_value=MagicMock(ok=True, reason=None)), \
         patch("app.ibkr.dedup.get_deduplicator", return_value=OrderDeduplicator()), \
         patch("app.api.main.MAX_POSITION_USD", 0):
        mock_dt.now.return_value = MARKET_OPEN_DT
        tc = _fresh_app()
        resp = tc.post("/orders/place", json=_place_payload())

    assert resp.status_code == 400, resp.json()
    assert "0 units" in resp.json()["detail"]


def test_place_rejects_when_buying_power_low():
    mock_ibkr = MagicMock()
    mock_ibkr.ib.isConnected.return_value = True
    mock_ibkr.get_stock_price.return_value = {"market_price": 100.0}
    mock_ibkr.get_account.return_value = _account(buying_power=10.0, net_liq=500.0)
    mock_ibkr.get_portfolio.return_value = []

    from app.risk.validator import ValidationResult
    from app.ibkr.dedup import OrderDeduplicator

    with patch("app.ibkr.client.get_client", return_value=mock_ibkr), \
         patch("app.api.main.datetime") as mock_dt, \
         patch("app.risk.validator.validate_order",
               return_value=ValidationResult(approved=True, reasons=["ok"])), \
         patch("app.ibkr.dedup.PreflightChecker.check",
               return_value=MagicMock(ok=True, reason=None)), \
         patch("app.ibkr.dedup.get_deduplicator", return_value=OrderDeduplicator()), \
         patch("app.notifications.order_monitor.OrderExecutionMonitor.place_and_monitor",
               return_value=MagicMock(success=True, order_id="12345", status="FILLED",
                                      fill_price=100.0, filled_quantity=1, reason=None)):
        mock_dt.now.return_value = MARKET_OPEN_DT
        tc = _fresh_app()
        resp = tc.post("/orders/place", json=_place_payload())

    assert resp.status_code == 400, resp.json()
    assert "insufficient buying power" in resp.json()["detail"].lower()
