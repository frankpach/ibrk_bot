"""Tests for position_size_units formula fix in validate_order()."""
import pytest
from datetime import datetime
from app.risk.validator import validate_order


def test_position_size_units_divides_by_price():
    """With capital=$1000, stop_loss=0.10 → max_position=$200; at price=$50 → 4 units."""
    result = validate_order(
        symbol="AAPL", action="BUY", quantity=4, order_type="MKT",
        stop_loss_pct=0.10, capital=1_000.0, active_positions=0,
        now=datetime(2025, 6, 10, 14, 0, 0), price=50.0,
    )
    assert result.position_size_units == 4


def test_position_size_units_zero_when_price_zero():
    """price=0 must not raise ZeroDivisionError."""
    result = validate_order(
        symbol="AAPL", action="BUY", quantity=1, order_type="MKT",
        stop_loss_pct=0.02, capital=10_000.0, active_positions=0,
        now=datetime(2025, 6, 10, 14, 0, 0), price=0.0,
    )
    assert result.position_size_units == 0


def test_position_size_units_backward_compat():
    """Omitting price= must behave identically to price=1.0."""
    kwargs = dict(symbol="AAPL", action="BUY", quantity=1, order_type="MKT",
                  stop_loss_pct=0.02, capital=10_000.0, active_positions=0,
                  now=datetime(2025, 6, 10, 14, 0, 0))
    r1 = validate_order(**kwargs)
    r2 = validate_order(**kwargs, price=1.0)
    assert r1.position_size_units == r2.position_size_units


def test_position_size_units_crypto_fractional():
    """BTC at $67 000 with capital=$5 000 → fractional units allowed."""
    result = validate_order(
        symbol="BTC", action="BUY", quantity=0, order_type="MKT",
        stop_loss_pct=0.02, capital=5_000.0, active_positions=0,
        now=datetime(2025, 6, 10, 14, 0, 0), price=67_000.0,
    )
    assert result.position_size_units > 0
    assert result.position_size_units < 1
