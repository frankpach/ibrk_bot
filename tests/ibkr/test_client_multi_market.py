from unittest.mock import AsyncMock, MagicMock
import asyncio
import threading

import pytest
from ib_insync import Stock, Forex, Contract

from app.ibkr.client import IBKRClient


@pytest.fixture
def client():
    """Create IBKRClient bypassing __init__ (no real IB connection)."""
    c = IBKRClient.__new__(IBKRClient)
    c.ib = MagicMock()
    c._lock = threading.Lock()
    c._connected = True

    # Create a dedicated event loop for this test client
    loop = asyncio.new_event_loop()

    def run_sync(coro):
        return loop.run_until_complete(coro)

    c._run_sync = run_sync

    yield c

    loop.close()


# ---- get_stock_price --------------------------------------------------------

def test_get_price_stk_default(client):
    ticker = MagicMock()
    ticker.marketPrice.return_value = 192.5
    client.ib.reqMktData = MagicMock(return_value=ticker)
    client.ib.qualifyContractsAsync = AsyncMock()
    client.ib.cancelMktData = MagicMock()

    async def noop(): pass
    client._connect_async = noop

    price = client.get_stock_price("AAPL")
    contract_used = client.ib.reqMktData.call_args.args[0]
    assert isinstance(contract_used, Stock)
    assert price["market_price"] == 192.5


def test_get_price_cash_uses_forex(client):
    ticker = MagicMock()
    ticker.marketPrice.return_value = 1.0834
    client.ib.reqMktData = MagicMock(return_value=ticker)
    client.ib.qualifyContractsAsync = AsyncMock()
    client.ib.cancelMktData = MagicMock()

    async def noop(): pass
    client._connect_async = noop

    price = client.get_stock_price("EURUSD", sec_type="CASH",
                                   exchange="IDEALPRO", currency="USD")
    contract_used = client.ib.reqMktData.call_args.args[0]
    assert isinstance(contract_used, Forex)
    assert price["market_price"] == 1.0834


def test_get_price_crypto_uses_paxos(client):
    ticker = MagicMock()
    ticker.marketPrice.return_value = 67000.0
    client.ib.reqMktData = MagicMock(return_value=ticker)
    client.ib.qualifyContractsAsync = AsyncMock()
    client.ib.cancelMktData = MagicMock()

    async def noop(): pass
    client._connect_async = noop

    price = client.get_stock_price("BTC", sec_type="CRYPTO",
                                   exchange="PAXOS", currency="USD")
    contract_used = client.ib.reqMktData.call_args.args[0]
    assert contract_used.secType == "CRYPTO"
    assert contract_used.exchange == "PAXOS"


# ---- place_order ------------------------------------------------------------

def test_place_order_stk_default(client):
    trade = MagicMock()
    trade.order.orderId = 42
    trade.orderStatus.status = "Submitted"
    client.ib.placeOrder = MagicMock(return_value=trade)
    client.ib.qualifyContractsAsync = AsyncMock()

    async def noop(): pass
    client._connect_async = noop

    result = client.place_order("AAPL", "BUY", 1, "MKT")
    contract = client.ib.placeOrder.call_args.args[0]
    assert isinstance(contract, Stock)
    assert result["order_id"] == "42"


def test_place_order_crypto(client):
    trade = MagicMock()
    trade.order.orderId = 99
    trade.orderStatus.status = "Submitted"
    client.ib.placeOrder = MagicMock(return_value=trade)
    client.ib.qualifyContractsAsync = AsyncMock()

    async def noop(): pass
    client._connect_async = noop

    client.place_order("BTC", "BUY", 0.01, "MKT",
                       sec_type="CRYPTO", exchange="PAXOS", currency="USD")
    contract = client.ib.placeOrder.call_args.args[0]
    assert contract.secType == "CRYPTO"
    assert contract.symbol == "BTC"


def test_place_order_cash_uses_forex(client):
    trade = MagicMock()
    trade.order.orderId = 7
    trade.orderStatus.status = "Submitted"
    client.ib.placeOrder = MagicMock(return_value=trade)
    client.ib.qualifyContractsAsync = AsyncMock()

    async def noop(): pass
    client._connect_async = noop

    client.place_order("EURUSD", "BUY", 25_000, "MKT",
                       sec_type="CASH", exchange="IDEALPRO", currency="USD")
    contract = client.ib.placeOrder.call_args.args[0]
    assert isinstance(contract, Forex)
