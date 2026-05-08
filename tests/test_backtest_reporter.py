# tests/test_backtest_reporter.py
from app.backtest.engine import BacktestResult
from app.backtest.reporter import format_telegram, format_api


def make_result(trades=3, wins=2, losses=1, pnl=13.0):
    return BacktestResult(
        symbol="AAPL", period_days=180,
        total_trades=trades, wins=wins, losses=losses,
        win_rate=66.7, total_pnl_usd=pnl, total_pnl_pct=2.6,
        profit_factor=4.0, max_drawdown_pct=1.5,
        avg_win_pct=4.0, avg_loss_pct=-2.5,
        trades=[],
    )


def test_format_telegram_contains_symbol():
    text = format_telegram(make_result())
    assert "AAPL" in text


def test_format_telegram_contains_winrate():
    text = format_telegram(make_result())
    assert "66" in text or "67" in text


def test_format_telegram_shows_pnl():
    text = format_telegram(make_result(pnl=13.0))
    assert "13.00" in text


def test_format_telegram_no_trades():
    result = BacktestResult(
        symbol="SPY", period_days=90,
        total_trades=0, wins=0, losses=0,
        win_rate=0.0, total_pnl_usd=0.0, total_pnl_pct=0.0,
        profit_factor=0.0, max_drawdown_pct=0.0,
        avg_win_pct=0.0, avg_loss_pct=0.0, trades=[],
    )
    text = format_telegram(result)
    assert "Sin" in text


def test_format_api_returns_dict():
    api = format_api(make_result())
    assert isinstance(api, dict)
    assert api["symbol"] == "AAPL"
    assert api["win_rate_pct"] == 66.7


def test_format_api_all_required_fields():
    api = format_api(make_result())
    required = [
        "symbol", "period_days", "total_trades", "wins", "losses",
        "win_rate_pct", "total_pnl_usd", "total_pnl_pct",
        "profit_factor", "max_drawdown_pct", "avg_win_pct", "avg_loss_pct", "note",
    ]
    for f in required:
        assert f in api, f"Missing field: {f}"


def test_format_api_note_present():
    api = format_api(make_result())
    assert "note" in api
    assert "commission" in api["note"].lower() or "comission" in api["note"].lower() or "comision" in api["note"].lower()
