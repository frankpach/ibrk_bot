# tests/test_issue002_eliminate_internal_http.py
"""Issue 002 — Eliminate internal HTTP calls in trading modules."""
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


# ── 1. Ports exist ──────────────────────────────────────────────────────────

def test_broker_port_has_required_methods():
    from app.application.ports.broker_port import IBrokerPort
    required = {"get_price", "place_order", "get_portfolio", "get_account", "reconnect"}
    assert required.issubset({m for m in dir(IBrokerPort) if not m.startswith("_")})


def test_llm_port_has_required_methods():
    from app.application.ports.llm_port import ILLMPort
    required = {"analyze_signal", "run_postmortem", "interpret_analysis"}
    assert required.issubset({m for m in dir(ILLMPort) if not m.startswith("_")})


def test_notification_port_has_required_methods():
    from app.application.ports.notification_port import INotificationPort
    required = {"notify", "request_approval"}
    assert required.issubset({m for m in dir(INotificationPort) if not m.startswith("_")})


# ── 2. Mock adapters ────────────────────────────────────────────────────────

def test_mock_broker_adapter_returns_configurable_price():
    from tests.mocks.mock_broker import MockBrokerAdapter
    broker = MockBrokerAdapter(prices={"AAPL": Decimal("150.25")})
    price = broker.get_price("AAPL", "STK", "SMART", "USD")
    assert price == Decimal("150.25")


def test_mock_broker_adapter_returns_zero_for_unknown_symbol():
    from tests.mocks.mock_broker import MockBrokerAdapter
    broker = MockBrokerAdapter()
    price = broker.get_price("UNKNOWN", "STK", "SMART", "USD")
    assert price == Decimal("0")


def test_mock_broker_adapter_place_order_returns_result():
    from tests.mocks.mock_broker import MockBrokerAdapter
    from app.domain.trading.value_objects import Order, OrderResult
    broker = MockBrokerAdapter()
    order = Order(symbol="AAPL", action="BUY", quantity=1, order_type="MKT")
    result = broker.place_order(order)
    assert isinstance(result, OrderResult)
    assert result.success is True
    assert result.order_id == "mock-1"


def test_mock_notification_adapter_records_messages():
    from tests.mocks.mock_notifications import MockNotificationAdapter
    notifier = MockNotificationAdapter()
    notifier.notify("hello")
    assert notifier.messages == ["hello"]


# ── 3. No httpx in trading modules ─────────────────────────────────────────

def test_loop_py_has_no_httpx():
    import app.llm.loop as mod
    import inspect
    source = inspect.getsource(mod)
    assert "httpx" not in source, "app/llm/loop.py still imports or uses httpx"


def test_positions_manager_has_no_httpx():
    import app.positions.manager as mod
    import inspect
    source = inspect.getsource(mod)
    assert "httpx" not in source, "app/positions/manager.py still imports or uses httpx"


def test_alerts_manager_has_no_httpx():
    import app.alerts.manager as mod
    import inspect
    source = inspect.getsource(mod)
    assert "httpx" not in source, "app/alerts/manager.py still imports or uses httpx"


# ── 4. loop.py works with mock broker ──────────────────────────────────────

def test_execute_order_with_mock_broker():
    """_execute_order should place an order via the broker port without HTTP."""
    from unittest.mock import patch, MagicMock
    from tests.mocks.mock_broker import MockBrokerAdapter
    from tests.mocks.mock_notifications import MockNotificationAdapter
    from app.llm.agent import LLMDecision
    from app.llm.loop import LLMSignalProcessor

    broker = MockBrokerAdapter(prices={"AAPL": Decimal("150.0")})
    notifier = MockNotificationAdapter()
    mock_dedup = MagicMock()
    mock_dedup.is_duplicate.return_value = False
    processor = LLMSignalProcessor(broker=broker, notifier=notifier, dedup=mock_dedup)

    # Patch market-hours validation so test passes regardless of local time
    with patch("app.risk.validator.validate_order", return_value=MagicMock(approved=True, reasons=[])), \
         patch("app.ibkr.dedup.PreflightChecker") as mock_preflight, \
         patch("app.ibkr.dedup.get_deduplicator") as mock_dedup_patch, \
         patch("app.notifications.order_monitor.OrderExecutionMonitor") as mock_monitor, \
         patch("app.ibkr.client.get_client"):
        mock_preflight.return_value.check.return_value = MagicMock(ok=True)
        mock_dedup_patch.return_value.is_duplicate.return_value = False
        mock_monitor.return_value.place_and_monitor.return_value = MagicMock(
            success=True, order_id="mock-123", fill_price=150.0, reason=None
        )
        decision = LLMDecision(action="BUY", stop_loss_pct=0.025, take_profit_pct=0.06,
                               justification="test", confidence="HIGH")
        result = processor._execute_order("AAPL", decision)
        assert result is True
        mock_monitor.return_value.place_and_monitor.assert_called_once()


# ── 5. positions/manager.py works with mock broker ─────────────────────────

def test_get_current_price_with_mock_broker():
    from tests.mocks.mock_broker import MockBrokerAdapter
    from app.positions.manager import _get_current_price, set_broker
    broker = MockBrokerAdapter(prices={"AAPL": Decimal("155.50")})
    set_broker(broker)
    price = _get_current_price("AAPL")
    assert price == 155.50


# ── 6. alerts/manager.py works with mock broker ────────────────────────────

def test_get_price_and_prev_close_with_mock_broker():
    from tests.mocks.mock_broker import MockBrokerAdapter
    from app.alerts.manager import AlertManager
    broker = MockBrokerAdapter(prices={"AAPL": Decimal("160.00")}, prev_closes={"AAPL": Decimal("160.00")})
    manager = AlertManager(broker=broker)
    current, prev = manager.get_price_and_prev_close("AAPL")
    assert current == 160.00
    assert prev == 160.00
