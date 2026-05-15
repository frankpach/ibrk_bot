# tests/test_postmortem.py
from unittest.mock import patch, MagicMock
from datetime import datetime
from zoneinfo import ZoneInfo
from app.db.models import Trade


def make_closed_trade(pnl_pct=0.04, exit_reason="TAKE_PROFIT"):
    return Trade(
        id=1, symbol="AAPL", action="BUY", quantity=3,
        entry_price=280.0, stop_loss_price=273.0, take_profit_price=296.8,
        stop_loss_pct=0.025, take_profit_pct=0.06,
        signal_strength="STRONG", llm_justification="RSI oversold + MACD crossover",
        status="CLOSED", exit_price=280.0 * (1 + pnl_pct),
        exit_reason=exit_reason, pnl_usd=round(280.0 * pnl_pct * 3, 2),
        pnl_pct=pnl_pct,
        opened_at=datetime(2026, 5, 5, 10, 0, tzinfo=ZoneInfo("America/New_York")),
        closed_at=datetime(2026, 5, 6, 14, 0, tzinfo=ZoneInfo("America/New_York")),
        order_id="42",
    )


@patch("app.llm.postmortem.insert_pattern")
@patch("app.infrastructure.llm.opencode_adapter.OpenCodeAdapter.call")
def test_inserts_pattern_after_win(mock_oc, mock_insert):
    mock_oc.return_value = '{"pattern_text": "AAPL + RSI<30 + MACD alcista -> BUY confiable", "suggestions": []}'

    from app.llm.postmortem import run_postmortem
    run_postmortem(make_closed_trade(pnl_pct=0.04, exit_reason="TAKE_PROFIT"))

    mock_insert.assert_called_once()
    call_args = mock_insert.call_args[0][0]
    assert call_args.symbol == "AAPL"
    assert call_args.win_count == 1
    assert call_args.loss_count == 0


@patch("app.llm.postmortem.insert_pattern")
@patch("app.infrastructure.llm.opencode_adapter.OpenCodeAdapter.call")
def test_inserts_loss_pattern_after_stop_loss(mock_oc, mock_insert):
    mock_oc.return_value = '{"pattern_text": "AAPL + RSI marginal -> evitar entrada sin volumen", "suggestions": []}'

    from app.llm.postmortem import run_postmortem
    run_postmortem(make_closed_trade(pnl_pct=-0.025, exit_reason="STOP_LOSS"))

    mock_insert.assert_called_once()
    call_args = mock_insert.call_args[0][0]
    assert call_args.win_count == 0
    assert call_args.loss_count == 1


@patch("app.llm.postmortem.insert_pattern")
def test_skips_postmortem_without_opencode_bin(mock_insert):
    with patch("app.llm.postmortem.OPENCODE_BIN", None):
        from app.llm.postmortem import run_postmortem
        run_postmortem(make_closed_trade())
        mock_insert.assert_not_called()
