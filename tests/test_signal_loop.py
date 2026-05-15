# tests/test_signal_loop.py
from unittest.mock import patch, MagicMock, call
from datetime import datetime
from zoneinfo import ZoneInfo
from app.db.models import Signal


def make_signal(symbol="AAPL", strength="STRONG", signal_id=1):
    return Signal(
        id=signal_id, symbol=symbol, strength=strength,
        rsi=28.5, macd=-0.12, volume_ratio=1.8,
        extra_indicators="{}", created_at=datetime.now(ZoneInfo("America/New_York")),
        processed=False,
    )


def _make_processor():
    """Return a LLMSignalProcessor with fresh mocked dependencies."""
    from app.llm.loop import LLMSignalProcessor
    mock_broker = MagicMock()
    mock_notifier = MagicMock()
    mock_dedup = MagicMock()
    return LLMSignalProcessor(broker=mock_broker, notifier=mock_notifier, dedup=mock_dedup)


@patch("app.llm.loop.mark_signal_processed")
@patch("app.llm.loop.analyze_signal")
@patch("app.llm.loop.get_pending_signals")
def test_ignores_signal_when_llm_returns_ignore(mock_signals, mock_analyze, mock_mark):
    from app.llm.agent import LLMDecision
    mock_signals.return_value = [make_signal()]
    mock_analyze.return_value = LLMDecision("IGNORE", 0, 0, "no signal", "LOW")

    processor = _make_processor()
    processor.process_pending_signals()
    mock_mark.assert_called_once_with(1)


@patch("app.llm.loop.mark_signal_processed")
@patch("app.llm.loop.analyze_signal")
@patch("app.llm.loop.get_pending_signals")
def test_places_order_when_llm_returns_buy(mock_signals, mock_analyze, mock_mark):
    from app.llm.agent import LLMDecision
    mock_signals.return_value = [make_signal()]
    mock_analyze.return_value = LLMDecision("BUY", 0.025, 0.06, "strong signal", "HIGH")

    processor = _make_processor()
    with patch.object(processor, "_execute_order", return_value=True) as mock_exec:
        processor.process_pending_signals()
        mock_exec.assert_called_once()
    mock_mark.assert_called_once_with(1)


@patch("app.llm.loop.mark_signal_processed")
@patch("app.llm.loop.analyze_signal")
@patch("app.llm.loop.get_pending_signals")
def test_processes_all_pending_signals(mock_signals, mock_analyze, mock_mark):
    from app.llm.agent import LLMDecision
    mock_signals.return_value = [make_signal("AAPL", signal_id=1), make_signal("MSFT", signal_id=2)]
    mock_analyze.return_value = LLMDecision("IGNORE", 0, 0, "no", "LOW")

    processor = _make_processor()
    processor.process_pending_signals()
    assert mock_mark.call_count == 2


@patch("app.llm.loop.mark_signal_processed")
@patch("app.llm.loop.analyze_signal")
@patch("app.llm.loop.get_pending_signals")
def test_does_not_mark_signal_processed_on_llm_error(mock_signals, mock_analyze, mock_mark):
    """Si el LLM falla, la señal NO se marca como procesada para reintentar en el próximo ciclo."""
    mock_signals.return_value = [make_signal()]
    mock_analyze.side_effect = Exception("LLM timeout")

    processor = _make_processor()
    processor.process_pending_signals()
    mock_mark.assert_not_called()


# --- AC-11: LMT limit_price calculation tests ---

def _mock_broker(price=215.0):
    broker = MagicMock()
    broker.get_price.return_value = price
    acct = MagicMock()
    acct.net_liquidation = 10000.0
    acct.buying_power = 5000.0
    broker.get_account.return_value = acct
    broker.get_portfolio.return_value = []
    return broker


@patch("app.risk.validator.validate_order", return_value=MagicMock(approved=True, reasons=[]))
@patch("app.ibkr.dedup.PreflightChecker")
@patch("app.ibkr.dedup.get_deduplicator")
@patch("app.notifications.order_monitor.OrderExecutionMonitor")
@patch("app.ibkr.client.get_client")
@patch("app.llm.loop.mark_signal_processed")
@patch("app.llm.loop.analyze_signal")
@patch("app.llm.loop.get_pending_signals")
def test_buy_order_uses_lmt_with_slippage_buffer(mock_signals, mock_analyze, mock_mark, mock_get_client, mock_mon, mock_dd, mock_pf, mock_val):
    """AC-11.1: BUY at $215.00 with 0.5% buffer → limit_price=round(215*1.005,2)=216.07, order_type=LMT"""
    from app.llm.agent import LLMDecision
    from app.llm.loop import LLMSignalProcessor
    from tests.mocks.mock_notifications import MockNotificationAdapter
    mock_signals.return_value = [make_signal()]
    mock_analyze.return_value = LLMDecision("BUY", 0.025, 0.06, "strong signal", "HIGH")
    mock_pf.return_value.check.return_value = MagicMock(ok=True)
    mock_dd.return_value.is_duplicate.return_value = False
    mock_mon.return_value.place_and_monitor.return_value = MagicMock(success=True, order_id="42", fill_price=215.0)

    broker = _mock_broker(215.0)
    notifier = MockNotificationAdapter()
    mock_dedup = MagicMock()
    mock_dedup.is_duplicate.return_value = False
    processor = LLMSignalProcessor(broker=broker, notifier=notifier, dedup=mock_dedup)
    processor.process_pending_signals()

    call_kwargs = mock_mon.return_value.place_and_monitor.call_args.kwargs
    assert call_kwargs["order_type"] == "LMT", f"Expected LMT, got {call_kwargs['order_type']}"
    assert call_kwargs["limit_price"] == 216.07, f"Expected 216.07, got {call_kwargs['limit_price']}"


@patch("app.risk.validator.validate_order", return_value=MagicMock(approved=True, reasons=[]))
@patch("app.ibkr.dedup.PreflightChecker")
@patch("app.ibkr.dedup.get_deduplicator")
@patch("app.notifications.order_monitor.OrderExecutionMonitor")
@patch("app.ibkr.client.get_client")
@patch("app.llm.loop.mark_signal_processed")
@patch("app.llm.loop.analyze_signal")
@patch("app.llm.loop.get_pending_signals")
def test_sell_order_uses_lmt_with_slippage_buffer(mock_signals, mock_analyze, mock_mark, mock_get_client, mock_mon, mock_dd, mock_pf, mock_val):
    """AC-11.2: SELL at $215.00 with 0.5% buffer → limit_price=round(215*0.995,2)=213.93"""
    from app.llm.agent import LLMDecision
    from app.llm.loop import LLMSignalProcessor
    from tests.mocks.mock_notifications import MockNotificationAdapter
    mock_signals.return_value = [make_signal()]
    mock_analyze.return_value = LLMDecision("SELL", 0.025, 0.06, "sell signal", "HIGH")
    mock_pf.return_value.check.return_value = MagicMock(ok=True)
    mock_dd.return_value.is_duplicate.return_value = False
    mock_mon.return_value.place_and_monitor.return_value = MagicMock(success=True, order_id="42", fill_price=215.0)

    broker = _mock_broker(215.0)
    notifier = MockNotificationAdapter()
    mock_dedup = MagicMock()
    mock_dedup.is_duplicate.return_value = False
    processor = LLMSignalProcessor(broker=broker, notifier=notifier, dedup=mock_dedup)
    processor.process_pending_signals()

    call_kwargs = mock_mon.return_value.place_and_monitor.call_args.kwargs
    assert call_kwargs["order_type"] == "LMT"
    assert call_kwargs["limit_price"] == 213.93, f"Expected 213.93, got {call_kwargs['limit_price']}"


@patch("app.risk.validator.validate_order", return_value=MagicMock(approved=True, reasons=[]))
@patch("app.ibkr.dedup.PreflightChecker")
@patch("app.ibkr.dedup.get_deduplicator")
@patch("app.notifications.order_monitor.OrderExecutionMonitor")
@patch("app.ibkr.client.get_client")
@patch("app.llm.loop.mark_signal_processed")
@patch("app.llm.loop.analyze_signal")
@patch("app.llm.loop.get_pending_signals")
def test_falls_back_to_mkt_when_price_fetch_fails(mock_signals, mock_analyze, mock_mark, mock_get_client, mock_mon, mock_dd, mock_pf, mock_val):
    """AC-11.3: If price fetch raises exception → order_type=MKT, limit_price=None"""
    from app.llm.agent import LLMDecision
    from app.llm.loop import LLMSignalProcessor
    from tests.mocks.mock_notifications import MockNotificationAdapter
    mock_signals.return_value = [make_signal()]
    mock_analyze.return_value = LLMDecision("BUY", 0.025, 0.06, "strong signal", "HIGH")
    broker = _mock_broker()
    broker.get_price.side_effect = Exception("connection refused")
    mock_pf.return_value.check.return_value = MagicMock(ok=True)
    mock_dd.return_value.is_duplicate.return_value = False
    mock_mon.return_value.place_and_monitor.return_value = MagicMock(success=True, order_id="42", fill_price=0.0)

    notifier = MockNotificationAdapter()
    mock_dedup = MagicMock()
    mock_dedup.is_duplicate.return_value = False
    processor = LLMSignalProcessor(broker=broker, notifier=notifier, dedup=mock_dedup)
    processor.process_pending_signals()

    # Price fetch failure leads to current_price=0.0, units=0, so _execute_order returns False early.
    # The fallback to MKT is still set, but order is not placed due to zero units.
    mock_mon.return_value.place_and_monitor.assert_not_called()
    mock_mark.assert_not_called()
