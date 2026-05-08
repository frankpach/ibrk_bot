# tests/test_weekly_report.py
from datetime import datetime
from zoneinfo import ZoneInfo
from app.db.models import Trade, Pattern
from app.reports.weekly import generate_weekly_report


def make_trade(symbol="AAPL", pnl_usd=15.0, pnl_pct=0.04, exit_reason="TAKE_PROFIT"):
    return Trade(
        id=1, symbol=symbol, action="BUY", quantity=1,
        entry_price=280.0, stop_loss_price=273.0, take_profit_price=296.8,
        stop_loss_pct=0.025, take_profit_pct=0.06, signal_strength="STRONG",
        llm_justification="Test", status="CLOSED",
        exit_price=280.0 * 1.04, exit_reason=exit_reason,
        pnl_usd=pnl_usd, pnl_pct=pnl_pct,
        opened_at=datetime(2026, 5, 4, 10, 0, tzinfo=ZoneInfo("America/New_York")),
        closed_at=datetime(2026, 5, 5, 14, 0, tzinfo=ZoneInfo("America/New_York")),
        order_id="42",
    )


def make_pattern(symbol="AAPL", text="RSI<30 -> BUY confiable"):
    now = datetime(2026, 5, 6, tzinfo=ZoneInfo("America/New_York"))
    return Pattern(id=1, symbol=symbol, pattern_text=text,
                   win_count=3, loss_count=1, created_at=now, updated_at=now)


def test_generate_report_with_wins():
    trades = [make_trade("AAPL", 15.0, 0.04), make_trade("MSFT", -5.0, -0.02, "STOP_LOSS")]
    report = generate_weekly_report(trades, [], capital=500.0)
    assert "AAPL" in report
    assert "MSFT" in report
    assert "10.00" in report  # net pnl = 15 - 5
    assert "1" in report  # 1 ganancia


def test_generate_report_no_trades():
    report = generate_weekly_report([], [], capital=500.0)
    assert "Sin operaciones" in report


def test_generate_report_includes_patterns():
    patterns = [make_pattern("AAPL", "RSI<30 -> BUY confiable")]
    report = generate_weekly_report([], patterns, capital=500.0)
    assert "RSI<30" in report


def test_generate_report_calculates_win_rate():
    trades = [
        make_trade("AAPL", 10.0, 0.03),
        make_trade("MSFT", 8.0, 0.025),
        make_trade("TSLA", -5.0, -0.02, "STOP_LOSS"),
    ]
    report = generate_weekly_report(trades, [], capital=500.0)
    assert "66" in report or "67" in report  # 2/3 win rate


def test_generate_report_shows_top_symbols():
    trades = [
        make_trade("AAPL", 10.0), make_trade("AAPL", 8.0),
        make_trade("MSFT", 5.0),
    ]
    report = generate_weekly_report(trades, [], capital=500.0)
    assert "AAPL" in report
    assert "2 operacion" in report
