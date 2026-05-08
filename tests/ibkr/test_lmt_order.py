"""Tests for LMT order wiring in IBKRClient.place_order."""
import pytest
import asyncio
import threading
from unittest.mock import MagicMock, AsyncMock, patch


def _make_client():
    """Create IBKRClient bypassing __init__, with _run_sync mocked to run coros directly."""
    from app.ibkr.client import IBKRClient
    c = IBKRClient.__new__(IBKRClient)
    c.ib = MagicMock()
    trade = MagicMock()
    trade.order.orderId = 1
    trade.orderStatus.status = "Submitted"
    c.ib.placeOrder = MagicMock(return_value=trade)
    c.ib.qualifyContracts = MagicMock(return_value=[MagicMock()])
    c._lock = threading.Lock()

    # Run coroutines synchronously in a new event loop
    def run_sync(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    c._run_sync = run_sync
    return c


def test_lmt_order_sets_lmt_price():
    """place_order with order_type='LMT' and limit_price=150.0 must set lmtPrice=150.0."""
    c = _make_client()

    async def fake_connect():
        pass

    c.ib.connectAsync = AsyncMock()
    c.ib.qualifyContractsAsync = AsyncMock()

    c.place_order("AAPL", "BUY", 5, "LMT", limit_price=150.0)
    assert c.ib.placeOrder.called
    placed_order = c.ib.placeOrder.call_args[0][1]
    assert placed_order.lmtPrice == 150.0


def test_mkt_order_does_not_set_lmt_price():
    """MKT order must NOT set lmtPrice to a meaningful value."""
    c = _make_client()
    c.ib.connectAsync = AsyncMock()
    c.ib.qualifyContractsAsync = AsyncMock()

    c.place_order("AAPL", "BUY", 5, "MKT")
    assert c.ib.placeOrder.called
    placed_order = c.ib.placeOrder.call_args[0][1]
    lmt = getattr(placed_order, "lmtPrice", None)
    assert lmt != 150.0  # not set to a price value


def test_preview_request_accepts_limit_price():
    """OrderPreviewRequest must accept limit_price."""
    with patch("app.ibkr.client.IBKRClient") as mock_cls:
        mock_cls.return_value = MagicMock()
        import sys
        for mod in list(sys.modules.keys()):
            if "app.api.main" in mod:
                del sys.modules[mod]
        from importlib import import_module
        main_mod = import_module("app.api.main")
        req = main_mod.OrderPreviewRequest(
            symbol="AAPL", action="BUY", quantity=1, order_type="LMT",
            stop_loss_pct=0.02, take_profit_pct=0.04, limit_price=150.0,
        )
        assert req.limit_price == 150.0


def test_preview_request_limit_price_optional():
    """limit_price must default to None."""
    with patch("app.ibkr.client.IBKRClient") as mock_cls:
        mock_cls.return_value = MagicMock()
        import sys
        for mod in list(sys.modules.keys()):
            if "app.api.main" in mod:
                del sys.modules[mod]
        from importlib import import_module
        main_mod = import_module("app.api.main")
        req = main_mod.OrderPreviewRequest(
            symbol="AAPL", action="BUY", quantity=1, order_type="MKT",
            stop_loss_pct=0.02, take_profit_pct=0.04,
        )
        assert req.limit_price is None
