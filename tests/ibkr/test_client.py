# tests/ibkr/test_client.py
from unittest.mock import MagicMock, patch
import pytest
from app.ibkr.client import IBKRClient, get_client


def test_get_client_singleton():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        MockClient.return_value = mock
        c1 = get_client()
        c2 = get_client()
        assert c1 is c2


def test_disconnect():
    client = IBKRClient.__new__(IBKRClient)
    client._initialized = True
    client._loop = MagicMock()
    client.ib = MagicMock()
    client.ib.isConnected.return_value = True
    client._run_sync = MagicMock()
    with patch("app.ibkr.client._client_instance", client):
        client.disconnect()
    client._run_sync.assert_called_once()


def test_place_order_lmt_no_price():
    client = IBKRClient.__new__(IBKRClient)
    client._initialized = True
    client._lock = MagicMock()
    client._run_sync = MagicMock(side_effect=ValueError("limit_price is required"))
    with pytest.raises(ValueError):
        client.place_order("AAPL", "BUY", 10, "LMT")


def test_get_commissions():
    client = IBKRClient.__new__(IBKRClient)
    client._initialized = True
    client._lock = MagicMock()
    client._run_sync = MagicMock(return_value={"fills": [], "total_commission": 0})
    result = client.get_commissions(since_days=30)
    assert result["total_commission"] == 0


def test_get_executions():
    client = IBKRClient.__new__(IBKRClient)
    client._initialized = True
    client._lock = MagicMock()
    client._run_sync = MagicMock(return_value=[{"symbol": "AAPL"}])
    result = client.get_executions(since_days=7)
    assert len(result) == 1


def test_get_stock_price():
    client = IBKRClient.__new__(IBKRClient)
    client._initialized = True
    client._lock = MagicMock()
    client._run_sync = MagicMock(return_value={
        "symbol": "AAPL", "market_price": 150.0, "last": 150.0, "bid": 149.9, "ask": 150.1
    })
    result = client.get_stock_price("AAPL")
    assert result["market_price"] == 150.0


def test_get_account():
    client = IBKRClient.__new__(IBKRClient)
    client._initialized = True
    client._lock = MagicMock()
    client._run_sync = MagicMock(return_value={
        "net_liquidation": 100000.0, "buying_power": 50000.0, "cash_balance": 30000.0, "currency": "USD"
    })
    result = client.get_account()
    assert result["buying_power"] == 50000.0


def test_get_portfolio():
    client = IBKRClient.__new__(IBKRClient)
    client._initialized = True
    client._lock = MagicMock()
    client._run_sync = MagicMock(return_value=[{
        "symbol": "AAPL", "quantity": 10, "avg_cost": 145.0,
        "market_value": 1500.0, "unrealized_pnl": 50.0
    }])
    result = client.get_portfolio()
    assert result[0]["symbol"] == "AAPL"


def test_place_order_lmt_with_price():
    client = IBKRClient.__new__(IBKRClient)
    client._initialized = True
    client._lock = MagicMock()
    client._run_sync = MagicMock(return_value={
        "order_id": "123", "symbol": "AAPL", "action": "BUY",
        "quantity": 10, "order_type": "LMT", "status": "Submitted"
    })
    result = client.place_order("AAPL", "BUY", 10, "LMT", limit_price=149.0)
    assert result["order_type"] == "LMT"


def test_place_order_mkt():
    client = IBKRClient.__new__(IBKRClient)
    client._initialized = True
    client._lock = MagicMock()
    client._run_sync = MagicMock(return_value={
        "order_id": "124", "symbol": "AAPL", "action": "SELL",
        "quantity": 5, "order_type": "MKT", "status": "Filled"
    })
    result = client.place_order("AAPL", "SELL", 5, "MKT")
    assert result["status"] == "Filled"


def test_disconnect_not_connected():
    client = IBKRClient.__new__(IBKRClient)
    client._initialized = True
    client._loop = MagicMock()
    client.ib = MagicMock()
    client.ib.isConnected.return_value = False
    client._run_sync = MagicMock()
    with patch("app.ibkr.client._client_instance", client):
        client.disconnect()
    client._run_sync.assert_called_once()
