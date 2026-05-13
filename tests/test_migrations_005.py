# tests/test_migrations_005.py
"""Tests for Issue 005: agent, loop, telegram migrations."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


def test_analyze_signal_returns_llm_decision():
    from app.llm.agent import LLMDecision
    from app.analysis.pipeline import AnalysisResult
    from app.analysis.scorer import QuantScore

    mock_result = AnalysisResult(symbol="AAPL", recommendation="BUY", llm_confidence=0.8)
    mock_result.score = QuantScore(
        symbol="AAPL", total=82.0, momentum=0.8, trend=0.7,
        volume=0.6, volatility=0.7, portfolio_fit=0.8, sentiment=0.7,
        price_change=0.6, recommendation="PRIORITY", weights_used={},
    )
    mock_result.llm_narrative = "Strong signal"

    with patch("app.analysis.pipeline.AnalysisPipeline.run", return_value=mock_result), \
         patch("app.llm.agent.insert_decision"), \
         patch("app.llm.agent.get_data_layer"):
        from app.llm.agent import analyze_signal
        result = analyze_signal("AAPL", "STRONG", 28.5, -0.12, 1.8, signal_id=1)

    assert isinstance(result, LLMDecision)
    assert result.action in ("BUY", "SELL", "IGNORE")


def test_analyze_signal_returns_ignore_on_pipeline_error():
    with patch("app.llm.agent.get_data_layer", side_effect=Exception("IB down")):
        from app.llm.agent import analyze_signal, LLMDecision
        result = analyze_signal("AAPL", "STRONG", 28.5, -0.12, 1.8, signal_id=1)
    assert isinstance(result, LLMDecision)
    assert result.action == "IGNORE"


def test_get_data_layer_returns_ibdatalayer():
    import app.llm.agent as agent_mod
    from app.analysis.data import IBDataLayer
    from app.analysis.mock_client import MockIBClient

    agent_mod._data_layer_instance = None
    mock_layer = IBDataLayer(MockIBClient())

    with patch("app.llm.agent.get_data_layer", return_value=mock_layer):
        from app.llm.agent import get_data_layer
        result = get_data_layer()
        assert isinstance(result, IBDataLayer)

    agent_mod._data_layer_instance = None


def test_loop_still_works():
    from app.llm.agent import LLMDecision
    with patch("app.llm.loop.get_pending_signals") as mock_sig, \
         patch("app.llm.loop.analyze_signal") as mock_analyze, \
         patch("app.llm.loop.mark_signal_processed") as mock_mark, \
         patch("app.llm.loop.httpx") as mock_http, \
         patch("app.llm.loop.notify"):
        from app.db.models import Signal
        from datetime import datetime
        from zoneinfo import ZoneInfo
        sig = Signal(
            id=1, symbol="AAPL", strength="STRONG", rsi=28.5, macd=-0.12,
            volume_ratio=1.8, extra_indicators="{}",
            created_at=datetime.now(ZoneInfo("America/New_York")),
        )
        mock_sig.return_value = [sig]
        mock_analyze.return_value = LLMDecision("BUY", 0.025, 0.06, "test", "HIGH")
        preview_resp = MagicMock()
        preview_resp.status_code = 200
        preview_resp.json.return_value = {"recommended_units": 10}
        place_resp = MagicMock()
        place_resp.status_code = 200
        place_resp.json.return_value = {"status": "placed"}
        mock_http.post.side_effect = [preview_resp, place_resp]

        from app.llm.loop import process_pending_signals
        process_pending_signals()
        mock_mark.assert_called_once_with(1)


def test_analyze_signal_action_mapping():
    from app.analysis.pipeline import AnalysisResult
    from app.analysis.scorer import QuantScore

    action_map = {
        "BUY": "BUY", "SELL": "SELL", "IGNORE": "IGNORE",
        "WATCHLIST": "IGNORE", "PROPOSE": "IGNORE",
        "REJECTED": "IGNORE", "PRIORITY": "BUY", "ERROR": "IGNORE",
    }

    for rec, expected_action in action_map.items():
        mock_result = AnalysisResult(symbol="TSLA", recommendation=rec, llm_confidence=0.7)
        mock_result.score = QuantScore(
            symbol="TSLA", total=70.0, momentum=0.7, trend=0.7,
            volume=0.6, volatility=0.7, portfolio_fit=0.7, sentiment=0.7,
            price_change=0.5, recommendation=rec, weights_used={},
        )
        mock_result.llm_narrative = "Test"

        with patch("app.analysis.pipeline.AnalysisPipeline.run", return_value=mock_result), \
             patch("app.llm.agent.insert_decision"), \
             patch("app.llm.agent.get_data_layer"):
            from app.llm.agent import analyze_signal
            result = analyze_signal("TSLA", "STRONG", 28.5, -0.12, 1.8, signal_id=1)

        assert result.action == expected_action, f"rec={rec} expected={expected_action} got={result.action}"


@pytest.mark.asyncio
async def test_cmd_analizar_sends_result():
    from app.analysis.pipeline import AnalysisResult
    from app.analysis.scorer import QuantScore
    from app.analysis.hard_rules import HardRulesResult

    mock_update = MagicMock()
    mock_update.effective_chat.id = "8645527459"
    mock_update.message.reply_text = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.args = ["AAPL"]

    mock_result = AnalysisResult(
        symbol="AAPL", recommendation="PROPOSE",
        llm_confidence=0.75, in_universe=False,
    )
    mock_result.score = QuantScore(
        symbol="AAPL", total=72.0, momentum=0.7, trend=0.6,
        volume=0.7, volatility=0.6, portfolio_fit=0.8, sentiment=0.7,
        price_change=0.5, recommendation="PROPOSE", weights_used={},
    )
    mock_result.llm_narrative = "Favorable technical conditions"
    mock_result.hard_rules = HardRulesResult(passed=True, failures=[], warnings=[])

    mock_pipeline_instance = MagicMock()
    mock_pipeline_instance.run.return_value = mock_result

    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", "8645527459"), \
         patch("app.analysis.pipeline.AnalysisPipeline", return_value=mock_pipeline_instance), \
         patch("app.llm.agent.get_data_layer"):
        from app.notifications.telegram_bot import cmd_analizar
        await cmd_analizar(mock_update, mock_ctx)

    assert mock_update.message.reply_text.call_count >= 2
    last_call = mock_update.message.reply_text.call_args_list[-1]
    msg = last_call[0][0] if last_call[0] else last_call[1].get("text", "")
    assert "AAPL" in msg
