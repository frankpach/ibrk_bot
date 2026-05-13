"""Tests for buying power pre-flight in /orders/preview and /orders/place."""
import sys
import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch, MagicMock

ET = ZoneInfo("America/New_York")
MARKET_OPEN_DT = datetime(2026, 5, 5, 10, 0, 0, tzinfo=ET)  # Tuesday 10am


def _fresh_test_client(mock_ibkr):
    """Return a TestClient using a freshly imported app (with IBKRClient patched)."""
    for mod in list(sys.modules.keys()):
        if "app.api.main" in mod:
            del sys.modules[mod]
    from fastapi.testclient import TestClient
    from app.api.main import app
    return TestClient(app)


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
    with patch("app.ibkr.client.IBKRClient", return_value=mock_ibkr):
        tc = _fresh_test_client(mock_ibkr)
        import app.api.main as main_mod
        with patch.object(main_mod, "client") as mock_client, \
             patch.object(main_mod, "datetime") as mock_dt:
            mock_dt.now.return_value = MARKET_OPEN_DT
            mock_client.get_stock_price.return_value = {"market_price": 100.0}
            mock_client.get_account.return_value = _account(buying_power=10.0)
            mock_client.get_portfolio.return_value = []
            resp = tc.post("/orders/preview", json=_preview_payload())
    assert resp.status_code == 400, resp.json()
    assert "buying power" in resp.json()["detail"].lower()


def test_preview_accepts_when_sufficient_buying_power():
    mock_ibkr = MagicMock()
    mock_ibkr.ib.isConnected.return_value = True
    with patch("app.ibkr.client.IBKRClient", return_value=mock_ibkr):
        tc = _fresh_test_client(mock_ibkr)
        import app.api.main as main_mod
        with patch.object(main_mod, "client") as mock_client, \
             patch.object(main_mod, "datetime") as mock_dt:
            mock_dt.now.return_value = MARKET_OPEN_DT
            mock_client.get_stock_price.return_value = {"market_price": 100.0}
            mock_client.get_account.return_value = _account(buying_power=1_000.0, net_liq=1_000.0)
            mock_client.get_portfolio.return_value = []
            resp = tc.post("/orders/preview", json=_preview_payload())
    assert resp.status_code == 200, resp.json()


def test_place_rejects_when_zero_units():
    mock_ibkr = MagicMock()
    mock_ibkr.ib.isConnected.return_value = True
    with patch("app.ibkr.client.IBKRClient", return_value=mock_ibkr):
        tc = _fresh_test_client(mock_ibkr)
        import app.api.main as main_mod
        from app.risk.validator import ValidationResult
        with patch.object(main_mod, "client") as mock_client, \
             patch.object(main_mod, "datetime") as mock_dt, \
             patch("app.risk.validator.validate_order") as mock_validate, \
             patch("app.ibkr.dedup.PreflightChecker.check", return_value=MagicMock(ok=True, reason=None)), \
             patch("app.ibkr.dedup.get_deduplicator") as mock_dedup, \
             patch.object(main_mod, "MAX_POSITION_USD", 0):
            from app.ibkr.dedup import OrderDeduplicator
            mock_dedup.return_value = OrderDeduplicator()
            mock_dt.now.return_value = MARKET_OPEN_DT
            mock_validate.return_value = ValidationResult(approved=True, reasons=["ok"])
            mock_client.get_stock_price.return_value = {"market_price": 100.0}
            mock_client.get_account.return_value = _account(buying_power=1_000.0, net_liq=1_000.0)
            mock_client.get_portfolio.return_value = []
            resp = tc.post("/orders/place", json=_place_payload())
    assert resp.status_code == 400, resp.json()
    assert "0 units" in resp.json()["detail"]


def test_place_rejects_when_buying_power_low():
    mock_ibkr = MagicMock()
    mock_ibkr.ib.isConnected.return_value = True
    with patch("app.ibkr.client.IBKRClient", return_value=mock_ibkr):
        tc = _fresh_test_client(mock_ibkr)
        import app.api.main as main_mod
        from app.risk.validator import ValidationResult
        with patch.object(main_mod, "client") as mock_client, \
             patch.object(main_mod, "datetime") as mock_dt, \
             patch("app.risk.validator.validate_order") as mock_validate, \
             patch("app.ibkr.dedup.PreflightChecker.check", return_value=MagicMock(ok=True, reason=None)), \
             patch("app.ibkr.dedup.get_deduplicator") as mock_dedup, \
             patch("app.notifications.order_monitor.OrderExecutionMonitor.place_and_monitor") as mock_place:
            from app.ibkr.dedup import OrderDeduplicator
            mock_dedup.return_value = OrderDeduplicator()
            mock_place.return_value = MagicMock(success=True, order_id="12345", status="FILLED", fill_price=100.0, filled_quantity=1, reason=None)
            mock_dt.now.return_value = MARKET_OPEN_DT
            mock_validate.return_value = ValidationResult(approved=True, reasons=["ok"])
            mock_client.get_stock_price.return_value = {"market_price": 100.0}
            mock_client.get_account.return_value = _account(buying_power=10.0, net_liq=500.0)
            mock_client.get_portfolio.return_value = []
            resp = tc.post("/orders/place", json=_place_payload())
    assert resp.status_code == 400, resp.json()
    assert "insufficient buying power" in resp.json()["detail"].lower()
