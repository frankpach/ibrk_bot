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


def _price_resp(price=215.0):
    return MagicMock(status_code=200, json=MagicMock(return_value={"market_price": price}))


def _price_resp_error():
    return MagicMock(status_code=500)


def _preview_resp(units=10):
    return MagicMock(status_code=200, json=MagicMock(return_value={"recommended_units": units}))


def _place_resp():
    return MagicMock(status_code=200, json=MagicMock(return_value={"status": "placed", "order_id": "42"}))


def _ignore_resp():
    return MagicMock(status_code=200, json=MagicMock(return_value={"status": "ok"}))


@patch("app.llm.loop.mark_signal_processed")
@patch("app.llm.loop.analyze_signal")
@patch("app.llm.loop.get_pending_signals")
def test_ignores_signal_when_llm_returns_ignore(mock_signals, mock_analyze, mock_mark):
    from app.llm.agent import LLMDecision
    mock_signals.return_value = [make_signal()]
    mock_analyze.return_value = LLMDecision("IGNORE", 0, 0, "no signal", "LOW")
    from app.llm.loop import process_pending_signals
    process_pending_signals()
    mock_mark.assert_called_once_with(1)


@patch("app.llm.loop.httpx")
@patch("app.llm.loop.mark_signal_processed")
@patch("app.llm.loop.analyze_signal")
@patch("app.llm.loop.get_pending_signals")
def test_places_order_when_llm_returns_buy(mock_signals, mock_analyze, mock_mark, mock_httpx):
    from app.llm.agent import LLMDecision
    mock_signals.return_value = [make_signal()]
    mock_analyze.return_value = LLMDecision("BUY", 0.025, 0.06, "strong signal", "HIGH")
    mock_httpx.get.return_value = _price_resp(215.0)
    mock_httpx.post.side_effect = [_preview_resp(10), _place_resp()]
    from app.llm.loop import process_pending_signals
    process_pending_signals()
    mock_httpx.post.assert_called()
    calls = mock_httpx.post.call_args_list
    assert any("orders/place" in str(c[0][0]) for c in calls)
    mock_mark.assert_called_once_with(1)


@patch("app.llm.loop.mark_signal_processed")
@patch("app.llm.loop.analyze_signal")
@patch("app.llm.loop.get_pending_signals")
def test_processes_all_pending_signals(mock_signals, mock_analyze, mock_mark):
    from app.llm.agent import LLMDecision
    mock_signals.return_value = [make_signal("AAPL", signal_id=1), make_signal("MSFT", signal_id=2)]
    mock_analyze.return_value = LLMDecision("IGNORE", 0, 0, "no", "LOW")
    from app.llm.loop import process_pending_signals
    process_pending_signals()
    assert mock_mark.call_count == 2


@patch("app.llm.loop.mark_signal_processed")
@patch("app.llm.loop.analyze_signal")
@patch("app.llm.loop.get_pending_signals")
def test_does_not_mark_signal_processed_on_llm_error(mock_signals, mock_analyze, mock_mark):
    """Si el LLM falla, la señal NO se marca como procesada para reintentar en el próximo ciclo."""
    mock_signals.return_value = [make_signal()]
    mock_analyze.side_effect = Exception("LLM timeout")
    from app.llm.loop import process_pending_signals
    process_pending_signals()
    mock_mark.assert_not_called()


# --- AC-11: LMT limit_price calculation tests ---

@patch("app.llm.loop.httpx")
@patch("app.llm.loop.mark_signal_processed")
@patch("app.llm.loop.analyze_signal")
@patch("app.llm.loop.get_pending_signals")
def test_buy_order_uses_lmt_with_slippage_buffer(mock_signals, mock_analyze, mock_mark, mock_httpx):
    """AC-11.1: BUY at $215.00 with 0.5% buffer → limit_price=round(215*1.005,2)=216.07, order_type=LMT"""
    from app.llm.agent import LLMDecision
    mock_signals.return_value = [make_signal()]
    mock_analyze.return_value = LLMDecision("BUY", 0.025, 0.06, "strong signal", "HIGH")
    mock_httpx.get.return_value = _price_resp(215.0)
    mock_httpx.post.side_effect = [_preview_resp(10), _place_resp()]

    from app.llm.loop import process_pending_signals
    process_pending_signals()

    post_calls = mock_httpx.post.call_args_list
    # Check both preview and place payloads
    for c in post_calls:
        payload = c[1].get("json") or (c[0][1] if len(c[0]) > 1 else {})
        if payload.get("symbol") == "AAPL":
            assert payload["order_type"] == "LMT", f"Expected LMT, got {payload['order_type']}"
            assert payload["limit_price"] == 216.07, f"Expected 216.07, got {payload['limit_price']}"


@patch("app.llm.loop.httpx")
@patch("app.llm.loop.mark_signal_processed")
@patch("app.llm.loop.analyze_signal")
@patch("app.llm.loop.get_pending_signals")
def test_sell_order_uses_lmt_with_slippage_buffer(mock_signals, mock_analyze, mock_mark, mock_httpx):
    """AC-11.2: SELL at $215.00 with 0.5% buffer → limit_price=round(215*0.995,2)=213.93"""
    from app.llm.agent import LLMDecision
    mock_signals.return_value = [make_signal()]
    mock_analyze.return_value = LLMDecision("SELL", 0.025, 0.06, "sell signal", "HIGH")
    mock_httpx.get.return_value = _price_resp(215.0)
    mock_httpx.post.side_effect = [_preview_resp(10), _place_resp()]

    from app.llm.loop import process_pending_signals
    process_pending_signals()

    post_calls = mock_httpx.post.call_args_list
    for c in post_calls:
        payload = c[1].get("json") or (c[0][1] if len(c[0]) > 1 else {})
        if payload.get("symbol") == "AAPL":
            assert payload["order_type"] == "LMT"
            assert payload["limit_price"] == 213.93, f"Expected 213.93, got {payload['limit_price']}"


@patch("app.llm.loop.httpx")
@patch("app.llm.loop.mark_signal_processed")
@patch("app.llm.loop.analyze_signal")
@patch("app.llm.loop.get_pending_signals")
def test_falls_back_to_mkt_when_price_fetch_fails(mock_signals, mock_analyze, mock_mark, mock_httpx):
    """AC-11.3: If price fetch raises exception → order_type=MKT, limit_price=None"""
    from app.llm.agent import LLMDecision
    mock_signals.return_value = [make_signal()]
    mock_analyze.return_value = LLMDecision("BUY", 0.025, 0.06, "strong signal", "HIGH")
    mock_httpx.get.side_effect = Exception("connection refused")
    mock_httpx.post.side_effect = [_preview_resp(10), _place_resp()]

    from app.llm.loop import process_pending_signals
    process_pending_signals()

    post_calls = mock_httpx.post.call_args_list
    for c in post_calls:
        payload = c[1].get("json") or (c[0][1] if len(c[0]) > 1 else {})
        if payload.get("symbol") == "AAPL":
            assert payload["order_type"] == "MKT"
            assert payload["limit_price"] is None
