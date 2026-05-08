"""Tests for the modified run_scan() in app/scanner/preprocessor.py."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import app.scanner.preprocessor as preprocessor_module


def _make_meta(symbol: str, market_key: str = "STK_US") -> dict:
    return {
        "symbol": symbol,
        "market_key": market_key,
        "liquid_hours": None,  # None = always liquid
        "sec_type": "STK",
        "exchange": "SMART",
        "currency": "USD",
    }


class TestRunScanActiveSymbols:
    def _run_with_patches(
        self,
        active_rows: list[dict],
        approved_rows: list[dict],
    ) -> list[str]:
        ib_client = MagicMock()

        with (
            patch(
                "app.scanner.preprocessor.get_all_active_symbols_today",
                return_value=active_rows,
            ),
            patch(
                "app.scanner.preprocessor.get_approved_symbols_with_meta",
                return_value=approved_rows,
            ),
            patch(
                "app.scanner.preprocessor.is_liquid_at",
                return_value=True,
            ),
            patch(
                "app.scanner.preprocessor.scan_symbol",
            ) as mock_scan,
        ):
            preprocessor_module.run_scan(ib_client)
            return [c.args[0] for c in mock_scan.call_args_list]

    def test_run_scan_uses_active_symbols_when_available(self):
        active = [_make_meta("AAPL"), _make_meta("NVDA")]
        approved = [_make_meta("OLD_SYM")]  # should NOT be used

        scanned = self._run_with_patches(active_rows=active, approved_rows=approved)

        assert set(scanned) == {"AAPL", "NVDA"}
        assert "OLD_SYM" not in scanned

    def test_run_scan_falls_back_to_approved_when_no_active(self):
        approved = [_make_meta("MSFT"), _make_meta("GOOG")]

        scanned = self._run_with_patches(active_rows=[], approved_rows=approved)

        assert set(scanned) == {"MSFT", "GOOG"}

    def test_run_scan_skips_illiquid_symbols(self):
        active = [_make_meta("AAPL"), _make_meta("NVDA")]
        ib_client = MagicMock()

        def _liquid(now, code):
            return code != "ILLIQUID_CODE"

        active[1]["liquid_hours"] = "ILLIQUID_CODE"

        with (
            patch(
                "app.scanner.preprocessor.get_all_active_symbols_today",
                return_value=active,
            ),
            patch(
                "app.scanner.preprocessor.get_approved_symbols_with_meta",
                return_value=[],
            ),
            patch(
                "app.scanner.preprocessor.is_liquid_at",
                side_effect=_liquid,
            ),
            patch("app.scanner.preprocessor.scan_symbol") as mock_scan,
        ):
            preprocessor_module.run_scan(ib_client)
            scanned = [c.args[0] for c in mock_scan.call_args_list]

        assert "AAPL" in scanned
        assert "NVDA" not in scanned
