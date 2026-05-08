# tests/test_settings_env.py
"""Tests for settings centralization — env vars and MockIBClient."""
import os
import pytest
from unittest.mock import patch


def test_api_base_importable_from_settings():
    from app.config.settings import API_BASE
    assert API_BASE.startswith("http://")
    assert "8088" in API_BASE


def test_opencode_bin_importable_from_settings():
    from app.config.settings import OPENCODE_BIN
    assert isinstance(OPENCODE_BIN, str)
    assert len(OPENCODE_BIN) > 0


def test_opencode_model_importable_from_settings():
    from app.config.settings import OPENCODE_MODEL
    assert isinstance(OPENCODE_MODEL, str)


def test_ib_mock_is_bool():
    from app.config.settings import IB_MOCK
    assert isinstance(IB_MOCK, bool)


def test_ib_client_id_data_is_int():
    from app.config.settings import IB_CLIENT_ID_DATA
    assert isinstance(IB_CLIENT_ID_DATA, int)
    assert IB_CLIENT_ID_DATA >= 1


def test_api_base_overridable_via_env():
    with patch.dict(os.environ, {"API_BASE": "http://custom:9999"}):
        import importlib
        import app.config.settings as s
        importlib.reload(s)
        assert s.API_BASE == "http://custom:9999"
        # Restore
        importlib.reload(s)


def test_ib_mock_defaults_false():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("IB_MOCK", None)
        import importlib
        import app.config.settings as s
        importlib.reload(s)
        assert s.IB_MOCK is False
        importlib.reload(s)


class TestMockIBClient:
    def setup_method(self):
        from app.analysis.mock_client import MockIBClient
        self.client = MockIBClient()

    def test_is_connected_returns_true(self):
        assert self.client.ib.isConnected() is True

    def test_get_stock_price_aapl_deterministic(self):
        result1 = self.client.get_stock_price("AAPL")
        result2 = self.client.get_stock_price("AAPL")
        assert result1["market_price"] == result2["market_price"]
        assert result1["symbol"] == "AAPL"
        assert "market_price" in result1
        assert "bid" in result1
        assert "ask" in result1

    def test_get_stock_price_fixed_value(self):
        result = self.client.get_stock_price("AAPL")
        assert result["market_price"] == 287.50

    def test_get_account_returns_expected_keys(self):
        account = self.client.get_account()
        assert "net_liquidation" in account
        assert "buying_power" in account
        assert account["net_liquidation"] == 500.0

    def test_get_portfolio_returns_list(self):
        portfolio = self.client.get_portfolio()
        assert isinstance(portfolio, list)

    def test_place_order_returns_mock_id(self):
        result = self.client.place_order("AAPL", "BUY", 1, "MKT")
        assert result["order_id"] == "mock_001"
        assert result["status"] == "Submitted"

    def test_req_historical_data_returns_bars(self):
        from ib_insync import Stock
        contract = Stock("AAPL", "SMART", "USD")
        bars = self.client.ib.reqHistoricalData(
            contract, endDateTime="", durationStr="30 D",
            barSizeSetting="1 day", whatToShow="TRADES",
            useRTH=True, formatDate=1,
        )
        assert len(bars) == 30
        assert hasattr(bars[0], "close")
        assert hasattr(bars[0], "volume")

    def test_req_historical_data_deterministic(self):
        from ib_insync import Stock
        contract = Stock("AAPL", "SMART", "USD")
        bars1 = self.client.ib.reqHistoricalData(
            contract, endDateTime="", durationStr="30 D",
            barSizeSetting="1 day", whatToShow="TRADES",
            useRTH=True, formatDate=1,
        )
        bars2 = self.client.ib.reqHistoricalData(
            contract, endDateTime="", durationStr="30 D",
            barSizeSetting="1 day", whatToShow="TRADES",
            useRTH=True, formatDate=1,
        )
        assert bars1[0].close == bars2[0].close

    def test_disconnect_does_nothing(self):
        # Should not raise
        self.client.disconnect()

    def test_no_socket_opened(self):
        import socket
        # MockIBClient should not have any real sockets
        # We verify by checking it never connects to IB port
        # (This is inherently verified by the class design, but we test that
        # creating MockIBClient doesn't attempt any network connection)
        import socket as _socket
        original_connect = _socket.socket.connect
        calls = []
        def mock_connect(self_sock, address):
            calls.append(address)
            return original_connect(self_sock, address)
        with patch.object(_socket.socket, 'connect', mock_connect):
            from app.analysis.mock_client import MockIBClient
            client = MockIBClient()
        # No connection to IB Gateway port
        ib_connections = [c for c in calls if 4002 in str(c)]
        assert len(ib_connections) == 0
