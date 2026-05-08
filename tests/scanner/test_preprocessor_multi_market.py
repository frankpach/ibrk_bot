from unittest.mock import MagicMock, patch

import pytest
import pandas as pd


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
