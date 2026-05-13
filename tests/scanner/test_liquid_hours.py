# tests/scanner/test_liquid_hours.py
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.scanner.liquid_hours import is_liquid_at


_NY = ZoneInfo("America/New_York")
_UTC = timezone.utc


def test_24x7():
    assert is_liquid_at(datetime(2024, 1, 15, 12, 0, tzinfo=_UTC), "24x7") is True


def test_us_rth_weekday():
    # Mon 10:00 NY
    dt = datetime(2024, 1, 15, 15, 0, tzinfo=_UTC)  # 10:00 NY
    assert is_liquid_at(dt, "US_RTH") is True


def test_us_rth_before_open():
    dt = datetime(2024, 1, 15, 13, 0, tzinfo=_UTC)  # 08:00 NY
    assert is_liquid_at(dt, "US_RTH") is False


def test_us_rth_weekend():
    dt = datetime(2024, 1, 13, 15, 0, tzinfo=_UTC)  # Sat
    assert is_liquid_at(dt, "US_RTH") is False


def test_us_ext_weekday():
    dt = datetime(2024, 1, 15, 13, 0, tzinfo=_UTC)  # 08:00 NY
    assert is_liquid_at(dt, "US_EXT") is True


def test_us_ext_after_hours():
    dt = datetime(2024, 1, 16, 0, 0, tzinfo=_UTC)  # 19:00 NY (Mon)
    assert is_liquid_at(dt, "US_EXT") is True


def test_fx_monday():
    dt = datetime(2024, 1, 15, 12, 0, tzinfo=_UTC)
    assert is_liquid_at(dt, "FX") is True


def test_fx_friday_after_22():
    dt = datetime(2024, 1, 12, 23, 0, tzinfo=_UTC)  # Fri 23:00 UTC
    assert is_liquid_at(dt, "FX") is False


def test_fx_saturday():
    dt = datetime(2024, 1, 13, 12, 0, tzinfo=_UTC)
    assert is_liquid_at(dt, "FX") is False


def test_fx_sunday_before_22():
    dt = datetime(2024, 1, 14, 20, 0, tzinfo=_UTC)  # Sun 20:00 UTC
    assert is_liquid_at(dt, "FX") is False


def test_fx_sunday_after_22():
    dt = datetime(2024, 1, 14, 23, 0, tzinfo=_UTC)  # Sun 23:00 UTC
    assert is_liquid_at(dt, "FX") is True


def test_globex_halt():
    dt = datetime(2024, 1, 15, 22, 30, tzinfo=_UTC)  # Mon 22:30 UTC
    assert is_liquid_at(dt, "GLOBEX") is False


def test_globex_weekend():
    dt = datetime(2024, 1, 13, 12, 0, tzinfo=_UTC)  # Sat
    assert is_liquid_at(dt, "GLOBEX") is False


def test_unknown_code():
    assert is_liquid_at(datetime(2024, 1, 15, 12, 0, tzinfo=_UTC), "UNKNOWN") is False


def test_naive_datetime():
    dt = datetime(2024, 1, 15, 15, 0)  # naive
    assert is_liquid_at(dt, "US_RTH") is True


def test_none_code_defaults_24x7():
    assert is_liquid_at(datetime(2024, 1, 15, 12, 0, tzinfo=_UTC), None) is True
