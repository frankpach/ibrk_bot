# tests/ibkr/test_fill_tracker.py
from unittest.mock import MagicMock
from app.ibkr.fill_tracker import FillTracker, get_fill_price_fallback


def test_get_fill_price_found():
    client = MagicMock()
    client.get_executions.return_value = [
        {"order_id": "42", "price": 150.0}
    ]
    ft = FillTracker(client)
    price = ft.get_fill_price("42")
    assert price == 150.0


def test_get_fill_price_not_found():
    client = MagicMock()
    client.get_executions.return_value = []
    ft = FillTracker(client)
    price = ft.get_fill_price("99")
    assert price is None


def test_get_last_fill_for_symbol():
    client = MagicMock()
    client.get_executions.return_value = [
        {"symbol": "AAPL", "price": 150.0}
    ]
    ft = FillTracker(client)
    price = ft.get_last_fill_for_symbol("AAPL")
    assert price == 150.0


def test_get_fill_price_fallback_with_fill():
    client = MagicMock()
    client.get_executions.return_value = [{"order_id": "1", "price": 100.0}]
    price = get_fill_price_fallback(client, "1", "AAPL")
    assert price == 100.0


def test_get_fill_price_fallback_with_market():
    client = MagicMock()
    client.get_executions.return_value = []
    client.get_stock_price.return_value = {"market_price": 200.0}
    price = get_fill_price_fallback(client, "1", "AAPL")
    assert price == 200.0


def test_get_fill_price_fallback_raises_when_no_price():
    client = MagicMock()
    client.get_executions.return_value = []
    client.get_stock_price.side_effect = Exception("No price")
    try:
        get_fill_price_fallback(client, "1", "AAPL")
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "Could not determine fill price" in str(e)
