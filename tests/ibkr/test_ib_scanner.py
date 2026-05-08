"""
Tests for app/ibkr/ib_scanner.py
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.ibkr.ib_scanner import get_stk_us_candidates, run_ib_scanner


def _make_scan_item(symbol: str, rank: int) -> MagicMock:
    """Build a fake ib_insync ScanData item."""
    item = MagicMock()
    item.rank = rank
    item.contractDetails.contract.symbol = symbol
    return item


def _make_ib_client(scan_items: list[MagicMock]) -> MagicMock:
    """Build a fake IBKRClient whose reqScannerData returns scan_items."""
    ib_client = MagicMock()
    ib_client.ib.reqScannerData.return_value = scan_items
    return ib_client


class TestRunIbScanner:
    def test_run_ib_scanner_returns_symbol_list(self):
        items = [_make_scan_item("AAPL", 0), _make_scan_item("NVDA", 1)]
        ib_client = _make_ib_client(items)

        result = run_ib_scanner(
            ib_client,
            scan_code="MOST_ACTIVE",
            location="STK.US.MAJOR",
            instrument="STK",
            limit=50,
        )

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == {"symbol": "AAPL", "rank": 0}
        assert result[1] == {"symbol": "NVDA", "rank": 1}

    def test_run_ib_scanner_respects_limit(self):
        items = [_make_scan_item(f"SYM{i}", i) for i in range(20)]
        ib_client = _make_ib_client(items)

        result = run_ib_scanner(
            ib_client,
            scan_code="MOST_ACTIVE",
            location="STK.US.MAJOR",
            instrument="STK",
            limit=5,
        )

        assert len(result) == 5
        assert result[0]["symbol"] == "SYM0"
        assert result[4]["symbol"] == "SYM4"

    def test_run_ib_scanner_returns_empty_on_exception(self):
        ib_client = MagicMock()
        ib_client.ib.reqScannerData.side_effect = RuntimeError("IB connection lost")

        result = run_ib_scanner(
            ib_client,
            scan_code="MOST_ACTIVE",
            location="STK.US.MAJOR",
            instrument="STK",
        )

        assert result == []

    def test_run_ib_scanner_skips_items_without_symbol(self):
        good = _make_scan_item("TSLA", 0)
        bad = MagicMock()
        bad.rank = 1
        bad.contractDetails.contract.symbol = None

        ib_client = _make_ib_client([good, bad])

        result = run_ib_scanner(
            ib_client,
            scan_code="HOT_BY_PRICE",
            location="STK.US.MAJOR",
            instrument="STK",
            limit=50,
        )

        assert len(result) == 1
        assert result[0]["symbol"] == "TSLA"


class TestGetStkUsCandidates:
    def _mock_run_scanner(self, per_scan_results: dict[str, list[MagicMock]]):
        def _fake_run(ib_client, scan_code, location, instrument, limit=50):
            items = per_scan_results.get(scan_code, [])
            return [
                {"symbol": it.contractDetails.contract.symbol, "rank": it.rank}
                for it in items
                if it.contractDetails.contract.symbol
            ]
        return patch("app.ibkr.ib_scanner.run_ib_scanner", side_effect=_fake_run)

    def test_get_stk_us_candidates_returns_symbols_list(self):
        items = [_make_scan_item("AAPL", 0), _make_scan_item("MSFT", 1)]
        ib_client = _make_ib_client(items)
        per_scan = {
            "MOST_ACTIVE": items,
            "TOP_VOLUME_RATE": items,
            "HOT_BY_PRICE": items,
        }
        with self._mock_run_scanner(per_scan):
            result = get_stk_us_candidates(ib_client, limit=50)

        assert isinstance(result, list)
        assert len(result) > 0
        assert all("symbol" in r and "rank" in r for r in result)

    def test_get_stk_us_candidates_deduplicates(self):
        most_active = [_make_scan_item("AAPL", 0), _make_scan_item("NVDA", 1)]
        top_vol = [_make_scan_item("AAPL", 0), _make_scan_item("TSLA", 1)]
        hot_price = [_make_scan_item("NVDA", 0), _make_scan_item("AAPL", 1)]

        per_scan = {
            "MOST_ACTIVE": most_active,
            "TOP_VOLUME_RATE": top_vol,
            "HOT_BY_PRICE": hot_price,
        }
        ib_client = MagicMock()
        with self._mock_run_scanner(per_scan):
            result = get_stk_us_candidates(ib_client, limit=50)

        symbols = [r["symbol"] for r in result]
        assert len(symbols) == len(set(symbols)), "Duplicate symbols in output"
        assert set(symbols) == {"AAPL", "NVDA", "TSLA"}

    def test_get_stk_us_candidates_ranks_by_first_appearance(self):
        most_active = [_make_scan_item("EARLY", 0)]
        top_vol = [_make_scan_item("EARLY", 0), _make_scan_item("LATE", 1)]
        hot_price = []

        per_scan = {
            "MOST_ACTIVE": most_active,
            "TOP_VOLUME_RATE": top_vol,
            "HOT_BY_PRICE": hot_price,
        }
        ib_client = MagicMock()
        with self._mock_run_scanner(per_scan):
            result = get_stk_us_candidates(ib_client, limit=50)

        symbols = [r["symbol"] for r in result]
        assert symbols.index("EARLY") < symbols.index("LATE")

    def test_get_stk_us_candidates_respects_limit(self):
        items = [_make_scan_item(f"S{i}", i) for i in range(30)]
        per_scan = {
            "MOST_ACTIVE": items[:10],
            "TOP_VOLUME_RATE": items[10:20],
            "HOT_BY_PRICE": items[20:30],
        }
        ib_client = MagicMock()
        with self._mock_run_scanner(per_scan):
            result = get_stk_us_candidates(ib_client, limit=15)

        assert len(result) <= 15
