"""Tests for app/scanner/market_open_selector.py"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.scanner.market_open_selector import select_top_symbols, simple_score

TODAY = date.today().isoformat()


def _make_ib_client(position_symbols=None):
    ib_client = MagicMock()
    positions = []
    for sym in (position_symbols or []):
        pos = MagicMock()
        pos.contract.symbol = sym
        pos.position = 1
        positions.append(pos)
    ib_client.ib.positions.return_value = positions
    return ib_client


def _make_data_layer(indicators_map=None):
    data_layer = MagicMock()
    _map = indicators_map or {}

    def _get_indicators(symbol):
        return _map.get(symbol, {"rsi": 50.0, "volume_ratio": 1.0})

    data_layer.get_indicators.side_effect = _get_indicators
    return data_layer


class TestSimpleScore:
    def test_extreme_rsi_gives_high_score(self):
        assert simple_score(rsi=80.0, volume_ratio=3.0) > 70

    def test_neutral_rsi_low_volume_gives_low_score(self):
        assert simple_score(rsi=50.0, volume_ratio=1.0) < 20

    def test_none_inputs_are_handled(self):
        score = simple_score(rsi=None, volume_ratio=None)
        assert 0.0 <= score <= 100.0


class TestSelectTopSymbols:
    def _patch_candidates(self, symbols):
        return patch(
            "app.scanner.market_open_selector._get_candidates",
            return_value=symbols,
        )

    def _patch_upsert(self):
        return patch("app.scanner.market_open_selector.upsert_active_symbols")

    def test_select_top_symbols_respects_n_limit(self):
        candidates = ["SYM" + str(i) for i in range(20)]
        ib_client = _make_ib_client()
        data_layer = _make_data_layer()

        with self._patch_candidates(candidates), self._patch_upsert():
            result = select_top_symbols(
                "STK_US", ib_client, data_layer, session_date=TODAY, n=5
            )

        assert len(result) == 5

    def test_select_top_symbols_includes_open_positions(self):
        candidates = ["SYM" + str(i) for i in range(20)]
        forced_sym = "FORCED_POSITION"
        ib_client = _make_ib_client(position_symbols=[forced_sym])
        indicators = {sym: {"rsi": 70.0, "volume_ratio": 2.0} for sym in candidates}
        data_layer = _make_data_layer(indicators)

        with self._patch_candidates(candidates), self._patch_upsert():
            result = select_top_symbols(
                "STK_US", ib_client, data_layer, session_date=TODAY, n=5
            )

        assert forced_sym in result

    def test_select_top_symbols_saves_to_db(self):
        candidates = ["AAPL", "MSFT", "NVDA"]
        ib_client = _make_ib_client()
        data_layer = _make_data_layer()

        with self._patch_candidates(candidates), self._patch_upsert() as mock_upsert:
            result = select_top_symbols(
                "STK_US", ib_client, data_layer, session_date=TODAY, n=10
            )

        mock_upsert.assert_called_once()
        call_args = mock_upsert.call_args
        assert call_args[0][0] == "STK_US"
        saved_symbols = call_args[0][1]
        for sym in result:
            assert sym in saved_symbols

    def test_select_top_symbols_returns_list(self):
        ib_client = _make_ib_client()
        data_layer = _make_data_layer()

        with self._patch_candidates([]), self._patch_upsert():
            result = select_top_symbols(
                "CRYPTO", ib_client, data_layer, session_date=TODAY, n=10
            )

        assert isinstance(result, list)
