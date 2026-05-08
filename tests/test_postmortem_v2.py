from unittest.mock import patch, MagicMock
from datetime import datetime
from zoneinfo import ZoneInfo
from app.db.models import Trade


def make_trade(pnl_pct=0.04, exit_reason="TAKE_PROFIT"):
    return Trade(
        id=1, symbol="AAPL", action="BUY", quantity=1,
        entry_price=280.0, stop_loss_price=273.0, take_profit_price=296.8,
        stop_loss_pct=0.025, take_profit_pct=0.06,
        signal_strength="STRONG", llm_justification="RSI oversold",
        status="CLOSED", exit_price=280.0 * (1 + pnl_pct),
        exit_reason=exit_reason, pnl_usd=round(280.0 * pnl_pct, 2),
        pnl_pct=pnl_pct,
        opened_at=datetime(2026, 5, 5, 10, 0, tzinfo=ZoneInfo("America/New_York")),
        closed_at=datetime(2026, 5, 6, 14, 0, tzinfo=ZoneInfo("America/New_York")),
        order_id="42",
    )


def test_postmortem_no_openai_import():
    """Verify openai SDK is not imported."""
    import app.llm.postmortem as pm
    import sys
    # openai should not be imported as a side effect
    assert "openai" not in str(pm.__dict__.get("OpenAI", ""))


def test_postmortem_saves_pattern_on_success():
    with patch("app.llm.postmortem._call_opencode") as mock_oc, \
         patch("app.llm.postmortem.insert_pattern") as mock_insert, \
         patch("app.llm.postmortem.notify"):
        mock_oc.return_value = '{"pattern_text": "AAPL RSI oversold -> BUY reliable", "suggestions": []}'
        from app.llm.postmortem import run_postmortem
        run_postmortem(make_trade())
        mock_insert.assert_called_once()
        pattern = mock_insert.call_args[0][0]
        assert pattern.symbol == "AAPL"
        assert pattern.win_count == 1


def test_postmortem_degrades_on_json_parse_failure():
    with patch("app.llm.postmortem._call_opencode") as mock_oc, \
         patch("app.llm.postmortem.insert_pattern") as mock_insert, \
         patch("app.llm.postmortem.notify"):
        mock_oc.return_value = "AAPL looks good for BUY on RSI oversold"
        from app.llm.postmortem import run_postmortem
        run_postmortem(make_trade())
        # Should still save a pattern (plain text fallback)
        mock_insert.assert_called_once()


def test_postmortem_handles_empty_opencode_response():
    with patch("app.llm.postmortem._call_opencode") as mock_oc, \
         patch("app.llm.postmortem.insert_pattern") as mock_insert, \
         patch("app.llm.postmortem.notify"):
        mock_oc.return_value = ""
        from app.llm.postmortem import run_postmortem
        run_postmortem(make_trade())
        # Even with empty response, saves default pattern
        mock_insert.assert_called_once()


def test_postmortem_notifies_frank():
    with patch("app.llm.postmortem._call_opencode") as mock_oc, \
         patch("app.llm.postmortem.insert_pattern"), \
         patch("app.llm.postmortem.notify") as mock_notify:
        mock_oc.return_value = '{"pattern_text": "test", "suggestions": []}'
        from app.llm.postmortem import run_postmortem
        run_postmortem(make_trade())
        mock_notify.assert_called_once()
        msg = mock_notify.call_args[0][0]
        assert "AAPL" in msg


def test_postmortem_loss_trade():
    with patch("app.llm.postmortem._call_opencode") as mock_oc, \
         patch("app.llm.postmortem.insert_pattern") as mock_insert, \
         patch("app.llm.postmortem.notify"):
        mock_oc.return_value = '{"pattern_text": "bad entry", "suggestions": []}'
        from app.llm.postmortem import run_postmortem
        run_postmortem(make_trade(pnl_pct=-0.025, exit_reason="STOP_LOSS"))
        pattern = mock_insert.call_args[0][0]
        assert pattern.loss_count == 1
        assert pattern.win_count == 0
