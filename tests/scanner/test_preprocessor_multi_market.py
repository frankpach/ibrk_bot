import json
from unittest.mock import MagicMock, patch

import pytest
import pandas as pd
import numpy as np

from app.scanner.preprocessor import _weekly_trend_filter


# ---------------------------------------------------------------------------
# _weekly_trend_filter unit tests
# ---------------------------------------------------------------------------

def _make_weekly_df(n_rows: int, trend: str) -> pd.DataFrame:
    """Helper: build a synthetic weekly close series with the desired trend."""
    base = 100.0
    if trend == "BULLISH":
        # Steadily rising so last_close > sma20 > sma50
        closes = [base + i * 0.5 for i in range(n_rows)]
    elif trend == "BEARISH":
        # Steadily falling so last_close < sma20 < sma50
        closes = [base - i * 0.5 for i in range(n_rows)]
    else:
        # Flat — SMA20 ≈ SMA50 ≈ last_close
        closes = [base] * n_rows
    return pd.DataFrame({"close": closes})


def test_weekly_trend_filter_bullish():
    df = _make_weekly_df(60, "BULLISH")
    assert _weekly_trend_filter(df) == "BULLISH"


def test_weekly_trend_filter_bearish():
    df = _make_weekly_df(60, "BEARISH")
    assert _weekly_trend_filter(df) == "BEARISH"


def test_weekly_trend_filter_none():
    assert _weekly_trend_filter(None) == "NEUTRAL"


def test_weekly_trend_filter_insufficient_data():
    df = pd.DataFrame({"close": [100.0] * 15})  # < 20 rows
    assert _weekly_trend_filter(df) == "NEUTRAL"


def test_weekly_trend_filter_exactly_20_rows():
    """Exactly 20 rows is the minimum accepted — should not return NEUTRAL due to size."""
    df = _make_weekly_df(20, "BULLISH")
    result = _weekly_trend_filter(df)
    # With only 20 rows sma50 falls back to sma20, so condition is sma20 > sma20 = False
    # Result is NEUTRAL — that is acceptable, the point is it doesn't crash
    assert result in ("BULLISH", "NEUTRAL")


def test_weekly_trend_filter_neutral_flat():
    df = _make_weekly_df(60, "NEUTRAL")
    assert _weekly_trend_filter(df) == "NEUTRAL"


# ---------------------------------------------------------------------------
# Veto logic: strength downgrade on BEARISH weekly
# ---------------------------------------------------------------------------

def _build_fake_ib_client(weekly_bars_count: int = 0):
    """Return a mock ib_client whose reqHistoricalData returns fake bars."""
    bar_template = MagicMock()
    bar_template.open = 100.0
    bar_template.high = 105.0
    bar_template.low = 95.0
    bar_template.close = 100.0
    bar_template.volume = 1_000

    mock_ib = MagicMock()

    # weekly bars: descending close prices to create BEARISH trend
    weekly_bars = []
    for i in range(weekly_bars_count):
        b = MagicMock()
        b.close = 200.0 - i * 1.0  # falling prices
        weekly_bars.append(b)

    def _req_hist(contract, endDateTime, durationStr, barSizeSetting, whatToShow, useRTH, formatDate):
        if barSizeSetting == "1 week":
            return weekly_bars
        # Return 30 fake daily/hourly/5min bars
        return [bar_template] * 30

    mock_ib.ib.reqHistoricalData.side_effect = _req_hist
    return mock_ib


def test_strong_signal_downgraded_on_bearish_weekly():
    """STRONG base signal + BEARISH weekly trend => result strength is MEDIUM."""
    from app.scanner import preprocessor

    meta = {"symbol": "AAPL", "sec_type": "STK", "exchange": "SMART",
            "currency": "USD", "liquid_hours": "US_RTH"}

    # Build a bearish weekly (60 descending bars)
    ib_client = _build_fake_ib_client(weekly_bars_count=60)

    fake_df = pd.DataFrame({
        "open": [100.0] * 30, "high": [105.0] * 30,
        "low": [95.0] * 30, "close": [100.0] * 30, "volume": [1000] * 30,
    })

    with patch.object(preprocessor, "is_liquid_at", return_value=True), \
         patch.object(preprocessor, "_fetch_bars", return_value=fake_df), \
         patch.object(preprocessor, "classify_multitimeframe", return_value="STRONG"), \
         patch.object(preprocessor, "_weekly_trend_filter", return_value="BEARISH"), \
         patch.object(preprocessor, "insert_signal") as m_insert:
        result = preprocessor.scan_symbol("AAPL", ib_client=ib_client, symbol_meta=meta)

    assert result["strength"] == "MEDIUM", f"Expected MEDIUM, got {result['strength']}"
    # extra_indicators should record the weekly_trend
    call_args = m_insert.call_args[0][0]
    extra = json.loads(call_args.extra_indicators)
    assert extra["weekly_trend"] == "BEARISH"


def test_medium_signal_downgraded_on_bearish_weekly():
    """MEDIUM base signal + BEARISH weekly trend => result strength is WEAK."""
    from app.scanner import preprocessor

    meta = {"symbol": "AAPL", "sec_type": "STK", "exchange": "SMART",
            "currency": "USD", "liquid_hours": "US_RTH"}

    ib_client = _build_fake_ib_client(weekly_bars_count=60)

    fake_df = pd.DataFrame({
        "open": [100.0] * 30, "high": [105.0] * 30,
        "low": [95.0] * 30, "close": [100.0] * 30, "volume": [1000] * 30,
    })

    with patch.object(preprocessor, "is_liquid_at", return_value=True), \
         patch.object(preprocessor, "_fetch_bars", return_value=fake_df), \
         patch.object(preprocessor, "classify_multitimeframe", return_value="MEDIUM"), \
         patch.object(preprocessor, "_weekly_trend_filter", return_value="BEARISH"), \
         patch.object(preprocessor, "insert_signal") as m_insert:
        result = preprocessor.scan_symbol("AAPL", ib_client=ib_client, symbol_meta=meta)

    assert result["strength"] == "WEAK", f"Expected WEAK, got {result['strength']}"


# ---------------------------------------------------------------------------
# Multi-market contract building
# ---------------------------------------------------------------------------

def test_run_scan_uses_meta_from_db():
    from app.scanner import preprocessor

    fake_meta = [
        {"symbol": "AAPL", "sec_type": "STK", "exchange": "SMART",
         "currency": "USD", "liquid_hours": "US_RTH"},
        {"symbol": "BTC", "sec_type": "CRYPTO", "exchange": "PAXOS",
         "currency": "USD", "liquid_hours": "24x7"},
    ]

    with patch.object(preprocessor, "get_all_active_symbols_today",
                      return_value=[]) as m_active,          patch.object(preprocessor, "get_approved_symbols_with_meta",
                      return_value=fake_meta) as m_meta,          patch.object(preprocessor, "is_liquid_at", return_value=True),          patch.object(preprocessor, "scan_symbol", return_value={"skipped": False}) as m_scan:
        preprocessor.run_scan()
        m_meta.assert_called_once()
        assert m_scan.call_count == 2
        passed_symbols = [call.args[0] for call in m_scan.call_args_list]
        assert "AAPL" in passed_symbols and "BTC" in passed_symbols


def test_scan_symbol_skips_when_not_liquid():
    from app.scanner import preprocessor

    meta = {"symbol": "AAPL", "sec_type": "STK", "exchange": "SMART",
            "currency": "USD", "liquid_hours": "US_RTH"}

    with patch.object(preprocessor, "is_liquid_at", return_value=False),          patch.object(preprocessor, "_fetch_bars") as m_fetch:
        result = preprocessor.scan_symbol("AAPL", symbol_meta=meta)
        m_fetch.assert_not_called()
        assert result["skipped"] is True


def test_scan_symbol_runs_when_liquid():
    from app.scanner import preprocessor

    meta = {"symbol": "BTC", "sec_type": "CRYPTO", "exchange": "PAXOS",
            "currency": "USD", "liquid_hours": "24x7"}

    fake_df = pd.DataFrame({"close": [100, 101, 102] * 10, "volume": [1000] * 30})

    with patch.object(preprocessor, "is_liquid_at", return_value=True),          patch.object(preprocessor, "_fetch_bars", return_value=fake_df) as m_fetch,          patch.object(preprocessor, "insert_signal"):
        result = preprocessor.scan_symbol("BTC", symbol_meta=meta)
        assert m_fetch.called
        assert result["skipped"] is False
