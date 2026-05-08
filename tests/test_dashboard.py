# tests/test_dashboard.py
from app.api.dashboard import render_dashboard


BASE_STATUS = {
    "mode": "paper", "paused": False,
    "daily_pnl_usd": 0.0, "daily_pnl_pct": 0.0,
    "open_positions": 0, "simulated_capital": 500,
}


def test_dashboard_is_valid_html():
    html = render_dashboard(BASE_STATUS, [], [], [], [])
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html


def test_dashboard_contains_system_status():
    status = {**BASE_STATUS, "daily_pnl_usd": 5.0, "daily_pnl_pct": 1.0}
    html = render_dashboard(status, [], [], [], [])
    assert "paper" in html.lower()
    assert "500" in html
    assert "5.00" in html


def test_dashboard_shows_open_positions():
    trades = [{
        "symbol": "AAPL", "action": "BUY", "quantity": 1,
        "entry_price": 287.0, "stop_loss_price": 280.0,
        "take_profit_price": 304.0, "signal_strength": "STRONG",
        "status": "OPEN", "opened_at": "2026-05-06T10:00:00",
    }]
    html = render_dashboard(BASE_STATUS, trades, [], [], [])
    assert "AAPL" in html
    assert "287" in html


def test_dashboard_shows_signals():
    signals = [{
        "symbol": "TSLA", "strength": "STRONG",
        "rsi": 28.5, "volume_ratio": 1.8,
        "created_at": "2026-05-06T10:00:00",
    }]
    html = render_dashboard(BASE_STATUS, [], [], signals, [])
    assert "TSLA" in html
    assert "STRONG" in html


def test_dashboard_shows_patterns():
    patterns = [{
        "symbol": "AAPL",
        "pattern": "RSI<30 + MACD alcista -> BUY confiable",
        "wins": 3, "losses": 1,
    }]
    html = render_dashboard(BASE_STATUS, [], [], [], patterns)
    assert "RSI" in html
    assert "3" in html


def test_dashboard_autorefresh_meta():
    html = render_dashboard(BASE_STATUS, [], [], [], [])
    assert 'http-equiv="refresh"' in html
    assert 'content="60"' in html


def test_dashboard_no_positions_shows_message():
    html = render_dashboard(BASE_STATUS, [], [], [], [])
    assert "Sin posiciones" in html
