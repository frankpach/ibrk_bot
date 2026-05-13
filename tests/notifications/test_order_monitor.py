# tests/notifications/test_order_monitor.py
from unittest.mock import MagicMock, patch
from app.notifications.order_monitor import OrderExecutionMonitor, OrderResult


def test_place_and_monitor_immediate_fill():
    client = MagicMock()
    client.place_order.return_value = {
        "order_id": "42", "status": "Filled"
    }
    with patch("app.notifications.order_monitor.get_fill_price_fallback", return_value=100.0):
        monitor = OrderExecutionMonitor(client)
        result = monitor.place_and_monitor("AAPL", "BUY", 10, "MKT")
    assert result.success
    assert result.status == "FILLED"
    assert result.fill_price == 100.0


def test_place_and_monitor_timeout():
    client = MagicMock()
    client.place_order.return_value = {
        "order_id": "42", "status": "Submitted"
    }
    with patch("app.notifications.order_monitor.get_fill_price_fallback", side_effect=Exception("no fill")):
        monitor = OrderExecutionMonitor(client)
        monitor.FILL_TIMEOUT = 0.1
        monitor.POLL_INTERVAL = 0.05
        result = monitor.place_and_monitor("AAPL", "BUY", 10, "MKT")
    assert not result.success
    assert result.status == "TIMEOUT"


def test_place_and_monitor_rejected():
    client = MagicMock()
    client.place_order.side_effect = Exception("Rejected")
    monitor = OrderExecutionMonitor(client)
    result = monitor.place_and_monitor("AAPL", "BUY", 10, "MKT")
    assert not result.success
    assert result.status == "REJECTED"


def test_confirm_entry_fill():
    client = MagicMock()
    with patch("app.notifications.order_monitor.get_fill_price_fallback", return_value=100.0):
        monitor = OrderExecutionMonitor(client)
        with patch("app.notifications.order_monitor.update_trade_status") as mock_update:
            ok = monitor.confirm_entry_fill(1, "42", "AAPL")
            assert ok
            mock_update.assert_called_once()


def test_confirm_close_fill():
    client = MagicMock()
    with patch("app.notifications.order_monitor.get_fill_price_fallback", return_value=100.0):
        monitor = OrderExecutionMonitor(client)
        with patch("app.notifications.order_monitor.update_trade_close_fill") as mock_update:
            price = monitor.confirm_close_fill(1, "42", "AAPL")
            assert price == 100.0
            mock_update.assert_called_once()
