# tests/test_signal_loop.py
from unittest.mock import patch, MagicMock
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
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "placed", "order_id": "42"}
    mock_httpx.post.return_value = mock_response
    from app.llm.loop import process_pending_signals
    process_pending_signals()
    mock_httpx.post.assert_called_once()
    call_args = mock_httpx.post.call_args
    assert "orders/place" in call_args[0][0]
    assert call_args[1]["json"]["symbol"] == "AAPL"
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
