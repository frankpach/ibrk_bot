from datetime import datetime, timezone

import pytest

from app.scanner.liquid_hours import is_liquid_at


def _utc(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


def test_none_means_24x7():
    assert is_liquid_at(_utc(2026, 5, 8, 3, 0), None) is True


def test_24x7_string():
    assert is_liquid_at(_utc(2026, 5, 8, 3, 0), "24x7") is True


def test_us_rth_session_open():
    # May 7 2026 is a Wednesday. 14:30 UTC = 09:30 ET (RTH open).
    assert is_liquid_at(_utc(2026, 5, 7, 14, 30), "US_RTH") is True


def test_us_rth_after_close():
    # May 7 2026 is a Wednesday. 22:00 UTC = 17:00 ET (after 16:00 close).
    assert is_liquid_at(_utc(2026, 5, 7, 22, 0), "US_RTH") is False


def test_forex_closed_weekend():
    # May 9 2026 is a Saturday UTC
    assert is_liquid_at(_utc(2026, 5, 9, 12, 0), "FX") is False


def test_forex_open_tuesday():
    # May 12 2026 is a Tuesday
    assert is_liquid_at(_utc(2026, 5, 12, 12, 0), "FX") is True
