# tests/test_risk_validator.py
from datetime import datetime
from zoneinfo import ZoneInfo
from app.risk.validator import validate_order

ET = ZoneInfo("America/New_York")


def market_open():
    return datetime(2026, 5, 5, 10, 0, 0, tzinfo=ET)  # Tuesday 10am


def market_closed():
    return datetime(2026, 5, 9, 10, 0, 0, tzinfo=ET)  # Saturday


def test_rejects_unknown_symbol():
    r = validate_order("FAKE", "BUY", 1, "MKT", 0.02, 1000.0, 0, market_open())
    assert r.approved is False
    assert any("not allowed" in x for x in r.reasons)


def test_rejects_too_many_positions():
    r = validate_order("AAPL", "BUY", 1, "MKT", 0.02, 1000.0, 3, market_open())
    assert r.approved is False
    assert any("positions" in x for x in r.reasons)


def test_rejects_invalid_order_type():
    r = validate_order("AAPL", "BUY", 1, "STOP", 0.02, 1000.0, 0, market_open())
    assert r.approved is False
    assert any("order type" in x for x in r.reasons)


def test_rejects_outside_market_hours():
    r = validate_order("AAPL", "BUY", 1, "MKT", 0.02, 1000.0, 0, market_closed())
    assert r.approved is False
    assert any("market hours" in x for x in r.reasons)


def test_approves_valid_order():
    r = validate_order("AAPL", "BUY", 1, "MKT", 0.02, 1000.0, 0, market_open())
    assert r.approved is True
    assert r.estimated_risk_usd <= 20.0


def test_min_risk_when_capital_below_100():
    # MIN_RISK_USD = 1.0 (ajustado para cuenta simulada de $500)
    r = validate_order("AAPL", "BUY", 1, "MKT", 0.02, 50.0, 0, market_open())
    assert r.approved is True
    assert r.estimated_risk_usd >= 1.0


def test_returns_position_size():
    r = validate_order("AAPL", "BUY", 1, "MKT", 0.025, 1000.0, 0, market_open())
    assert r.approved is True
    assert r.position_size_units > 0
