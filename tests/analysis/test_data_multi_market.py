from unittest.mock import MagicMock, patch
import asyncio

import pytest
from ib_insync import Stock, Forex, Future, Contract

from app.analysis.data import IBDataLayer


class _FakeBar:
    def __init__(self):
        self.date = "2026-05-08"
        self.open = 1.0
        self.high = 1.1
        self.low = 0.9
        self.close = 1.05
        self.volume = 100


@pytest.fixture
def fake_client():
    client = MagicMock()
    client.ib = MagicMock()
    client.ib.reqHistoricalData = MagicMock(return_value=[_FakeBar() for _ in range(5)])
    # async-style for futures resolution
    fake_details = MagicMock()
    fake_details.contract = Future(symbol="ES", exchange="CME", currency="USD")
    fake_details.contract.lastTradeDateOrContractMonth = "20260619"
    client.ib.reqContractDetailsAsync = MagicMock(return_value=[fake_details])
    return client


def test_stk_uses_stock_trades_rth_true(fake_client):
    layer = IBDataLayer(fake_client)
    layer.get_ohlcv("AAPL", "1 D", "5 mins", context={}, sec_type="STK",
                    exchange="SMART", currency="USD")
    call = fake_client.ib.reqHistoricalData.call_args
    contract = call.args[0] if call.args else call.kwargs["contract"]
    assert isinstance(contract, Stock)
    kwargs = call.kwargs
    assert kwargs["whatToShow"] == "TRADES"
    assert kwargs["useRTH"] is True


def test_cash_uses_forex_midpoint_rth_false(fake_client):
    layer = IBDataLayer(fake_client)
    layer.get_ohlcv("EURUSD", "1 D", "5 mins", context={}, sec_type="CASH",
                    exchange="IDEALPRO", currency="USD")
    call = fake_client.ib.reqHistoricalData.call_args
    contract = call.args[0] if call.args else call.kwargs["contract"]
    assert isinstance(contract, Forex)
    assert call.kwargs["whatToShow"] == "MIDPOINT"
    assert call.kwargs["useRTH"] is False


def test_crypto_uses_contract_trades_rth_false(fake_client):
    layer = IBDataLayer(fake_client)
    layer.get_ohlcv("BTC", "1 D", "5 mins", context={}, sec_type="CRYPTO",
                    exchange="PAXOS", currency="USD")
    call = fake_client.ib.reqHistoricalData.call_args
    contract = call.args[0] if call.args else call.kwargs["contract"]
    assert contract.secType == "CRYPTO"
    assert call.kwargs["whatToShow"] == "TRADES"
    assert call.kwargs["useRTH"] is False


def test_fut_resolves_front_month(fake_client):
    layer = IBDataLayer(fake_client)
    layer.get_ohlcv("ES", "1 D", "5 mins", context={}, sec_type="FUT",
                    exchange="CME", currency="USD")
    # reqContractDetailsAsync was called to resolve expiry
    fake_client.ib.reqContractDetailsAsync.assert_called_once()
    call = fake_client.ib.reqHistoricalData.call_args
    contract = call.args[0] if call.args else call.kwargs["contract"]
    assert isinstance(contract, Future)
    assert contract.lastTradeDateOrContractMonth == "20260619"
    assert call.kwargs["useRTH"] is False


def test_default_sec_type_is_stk_backward_compatible(fake_client):
    layer = IBDataLayer(fake_client)
    layer.get_ohlcv("AAPL", "1 D", "5 mins", context={})
    call = fake_client.ib.reqHistoricalData.call_args
    contract = call.args[0] if call.args else call.kwargs["contract"]
    assert isinstance(contract, Stock)
    assert call.kwargs["whatToShow"] == "TRADES"
    assert call.kwargs["useRTH"] is True
