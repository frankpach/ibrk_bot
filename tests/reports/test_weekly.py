# tests/reports/test_weekly.py
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from app.reports.weekly import generate_weekly_report, get_closed_trades_since, send_weekly_report

_DB = "app.infrastructure.db.compat"


def test_generate_weekly_report_empty():
    report = generate_weekly_report([], [], 1000.0)
    assert "Sin operaciones" in report


def test_generate_weekly_report_with_trades_and_patterns():
    trade = MagicMock()
    trade.symbol = "AAPL"
    trade.action = "BUY"
    trade.pnl_usd = 50.0
    trade.exit_reason = "TAKE_PROFIT"
    trade.entry_price = 100.0
    pattern = MagicMock()
    pattern.pattern_text = "Bullish engulfing"
    report = generate_weekly_report([trade], [pattern], 1000.0)
    assert "AAPL" in report
    assert "Bullish engulfing" in report
    assert "Win rate" in report


def test_generate_weekly_report_losses():
    trade = MagicMock()
    trade.symbol = "TSLA"
    trade.action = "BUY"
    trade.pnl_usd = -30.0
    trade.exit_reason = "STOP_LOSS"
    trade.entry_price = 200.0
    report = generate_weekly_report([trade], [], 1000.0)
    assert "TSLA" in report
    assert "-" in report


def test_generate_weekly_report_many_trades():
    trades = []
    for i in range(10):
        t = MagicMock()
        t.symbol = "SYM"
        t.action = "BUY"
        t.pnl_usd = 10.0
        t.exit_reason = "TP"
        t.entry_price = 100.0
        trades.append(t)
    report = generate_weekly_report(trades, [], 1000.0)
    assert "... y 5 operaciones mas" in report


@patch(f"{_DB}.get_connection")
def test_get_closed_trades_since(mock_get_conn):
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [
        {
            "id": 1, "symbol": "AAPL", "action": "BUY", "quantity": 10,
            "entry_price": 100.0, "stop_loss_price": 98.0, "take_profit_price": 110.0,
            "stop_loss_pct": 0.02, "take_profit_pct": 0.06, "signal_strength": "STRONG",
            "llm_justification": "test", "status": "CLOSED", "exit_price": 105.0,
            "exit_reason": "TP", "pnl_usd": 50.0, "pnl_pct": 0.05,
            "opened_at": datetime.utcnow().isoformat(), "closed_at": datetime.utcnow().isoformat(),
            "order_id": "1",
        }
    ]
    mock_get_conn.return_value = mock_conn
    trades = get_closed_trades_since(datetime.utcnow() - timedelta(days=7))
    assert len(trades) == 1
    assert trades[0].symbol == "AAPL"


@patch("app.reports.weekly.get_closed_trades_since", return_value=[])
@patch(f"{_DB}.get_patterns_for_week", return_value=[])
@patch("app.reports.weekly.notify")
def test_send_weekly_report(mock_notify, mock_patterns, mock_trades):
    send_weekly_report(capital=1000.0)
    mock_notify.assert_called_once()
    assert "Semanal" in mock_notify.call_args[0][0]
