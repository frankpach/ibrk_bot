# tests/test_market_hours.py
"""Tests para parser de liquidHours de IB Gateway."""
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from app.ibkr.market_hours import parse_liquid_hours, is_liquid_at


ET = ZoneInfo("America/New_York")

FOREX_HOURS = "20260506:1715-20260507:1700;20260507:1715-20260508:1700;20260509:CLOSED;20260510:1715-20260511:1700"
STOCK_HOURS = "20260507:0930-20260507:1600;20260508:0930-20260508:1600;20260509:CLOSED;20260510:CLOSED"
CRYPTO_HOURS = "20260507:1601-20260508:1600;20260508:1601-20260509:1600;20260509:CLOSED"


def test_parse_returns_list_of_intervals():
    intervals = parse_liquid_hours(STOCK_HOURS)
    assert len(intervals) >= 2
    assert all(hasattr(i, "start") and hasattr(i, "end") for i in intervals)


def test_stock_open_during_session():
    now = datetime(2026, 5, 7, 10, 0, tzinfo=ET)
    assert is_liquid_at(STOCK_HOURS, now) is True


def test_stock_closed_after_session():
    now = datetime(2026, 5, 7, 17, 0, tzinfo=ET)
    assert is_liquid_at(STOCK_HOURS, now) is False


def test_stock_closed_on_weekend():
    now = datetime(2026, 5, 9, 10, 0, tzinfo=ET)
    assert is_liquid_at(STOCK_HOURS, now) is False


def test_forex_open_at_night():
    now = datetime(2026, 5, 7, 23, 0, tzinfo=ET)
    assert is_liquid_at(FOREX_HOURS, now) is True


def test_forex_closed_on_weekend():
    now = datetime(2026, 5, 9, 12, 0, tzinfo=ET)
    assert is_liquid_at(FOREX_HOURS, now) is False


def test_empty_string_returns_false():
    assert is_liquid_at("", datetime.now(ET)) is False


def test_none_returns_false():
    assert is_liquid_at(None, datetime.now(ET)) is False
