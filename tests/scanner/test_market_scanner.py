"""Tests for app/scanner/market_scanner.py"""
from unittest.mock import MagicMock, patch, call
import pandas as pd


def test_fetch_and_cache_scanner_handles_empty():
    """data_layer.run_scanner returns [] — no crash, upsert called with empty list."""
    from app.scanner.market_scanner import fetch_and_cache_scanner

    data_layer = MagicMock()
    data_layer.run_scanner.return_value = []

    with patch("app.db.database.upsert_scanner_results") as mock_upsert, \
         patch("app.db.database.get_scanner_results", return_value=[]):
        fetch_and_cache_scanner(data_layer)

    # Should have been called for most_active, gainers, losers, and top_movers
    assert mock_upsert.call_count >= 4


def test_fetch_and_cache_scanner_writes_results():
    """data_layer.run_scanner returns symbols — upsert called with correct scan_type."""
    from app.scanner.market_scanner import fetch_and_cache_scanner

    data_layer = MagicMock()
    data_layer.run_scanner.return_value = ["AAPL", "TSLA", "NVDA"]

    with patch("app.db.database.upsert_scanner_results") as mock_upsert, \
         patch("app.db.database.get_scanner_results", return_value=[]):
        fetch_and_cache_scanner(data_layer)

    # Extract all scan_type args passed to upsert
    scan_types = [c.args[0] for c in mock_upsert.call_args_list]
    assert "most_active" in scan_types
    assert "gainers" in scan_types
    assert "losers" in scan_types
    assert "top_movers" in scan_types

    # For most_active, the results list should have 3 entries
    most_active_call = next(c for c in mock_upsert.call_args_list if c.args[0] == "most_active")
    assert len(most_active_call.args[1]) == 3
    assert most_active_call.args[1][0]["symbol"] == "AAPL"


def test_fetch_and_cache_scanner_enriches_rows_with_change_and_volume_ratio():
    """Scanner rows should include actionable pct move and volume ratio data."""
    from app.scanner.market_scanner import fetch_and_cache_scanner

    data_layer = MagicMock()
    data_layer.run_scanner.return_value = ["AAPL"]
    data_layer.get_ohlcv.return_value = pd.DataFrame({"close": [100.0, 103.0]})
    data_layer.get_indicators.return_value = {"volume_ratio_20d": 2.4}

    with patch("app.db.database.upsert_scanner_results") as mock_upsert, \
         patch("app.db.database.get_scanner_results", return_value=[]):
        fetch_and_cache_scanner(data_layer)

    most_active_call = next(c for c in mock_upsert.call_args_list if c.args[0] == "most_active")
    row = most_active_call.args[1][0]
    assert row["symbol"] == "AAPL"
    assert row["change_pct"] == 3.0
    assert row["volume_ratio"] == 2.4


def test_fetch_and_cache_sectors_handles_empty():
    """data_layer.get_ohlcv returns None — no crash, upsert not called for empty results."""
    from app.scanner.market_scanner import fetch_and_cache_sectors

    data_layer = MagicMock()
    data_layer.get_ohlcv.return_value = None

    with patch("app.db.database.upsert_scanner_results") as mock_upsert:
        fetch_and_cache_sectors(data_layer)

    # No results collected → upsert should not be called
    mock_upsert.assert_not_called()


def test_fetch_and_cache_sectors_writes_etf_data():
    """data_layer.get_ohlcv returns 2-row DataFrame — change_pct computed and stored."""
    from app.scanner.market_scanner import fetch_and_cache_sectors

    data_layer = MagicMock()
    df = pd.DataFrame({"close": [100.0, 102.0]})
    data_layer.get_ohlcv.return_value = df

    with patch("app.db.database.upsert_scanner_results") as mock_upsert:
        fetch_and_cache_sectors(data_layer)

    mock_upsert.assert_called_once()
    scan_type, results = mock_upsert.call_args.args
    assert scan_type == "sector"
    assert len(results) == 6  # 6 sector ETFs
    xlk_result = next(r for r in results if r["symbol"] == "XLK")
    assert xlk_result["change_pct"] == 2.0
    assert xlk_result["name"] == "Tech"


def test_fetch_implied_move_handles_empty():
    """data_layer.get_implied_volatility returns None — no crash, upsert not called."""
    from app.scanner.market_scanner import fetch_implied_move

    data_layer = MagicMock()
    data_layer.get_implied_volatility.return_value = None

    with patch("app.db.database.upsert_scanner_results") as mock_upsert:
        fetch_implied_move(data_layer, ["AAPL", "TSLA"])

    mock_upsert.assert_not_called()


def test_fetch_implied_move_writes_results():
    """data_layer.get_implied_volatility returns IV data — weekly move stored."""
    import math
    from app.scanner.market_scanner import fetch_implied_move

    data_layer = MagicMock()
    df = pd.DataFrame({"close": [0.2600]})  # 26% annual IV
    data_layer.get_implied_volatility.return_value = df

    with patch("app.db.database.upsert_scanner_results") as mock_upsert:
        fetch_implied_move(data_layer, ["AAPL"])

    mock_upsert.assert_called_once()
    scan_type, results = mock_upsert.call_args.args
    assert scan_type == "implied_move"
    assert results[0]["symbol"] == "AAPL"
    expected_weekly = round(0.2600 / math.sqrt(52) * 100, 1)
    assert results[0]["change_pct"] == expected_weekly
