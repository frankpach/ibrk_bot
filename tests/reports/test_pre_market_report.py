# tests/reports/test_pre_market_report.py
"""Tests for generate_pre_market_report with market_key parameter and 3-layer symbols_data."""
import pytest
from unittest.mock import MagicMock, patch
from app.reports.generator import generate_pre_market_report


def _make_symbols_data(n=3, layer="market_mover"):
    return [
        {
            "symbol": f"SYM{i}",
            "score": 70.0 + i,
            "recommendation": "WATCHLIST",
            "narrative": f"Symbol {i} narrative.",
            "rsi": 55.0,
            "volume_ratio": 1.5,
            "weekly_trend": "BULLISH",
            "layer": layer,
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# generate_pre_market_report — basic contract
# ---------------------------------------------------------------------------

_DB_PATCH = "app.infrastructure.db.compat"


def test_returns_report_id_on_success():
    data = _make_symbols_data(3)
    with patch(f"{_DB_PATCH}.save_report", return_value=42) as mock_save, \
         patch(f"{_DB_PATCH}.get_news_cache", return_value=[]), \
         patch(f"{_DB_PATCH}.get_scanner_results", return_value=[]), \
         patch(f"{_DB_PATCH}.get_account_history", return_value=[]):
        report_id = generate_pre_market_report(data)
    assert report_id == 42
    mock_save.assert_called_once()


def test_returns_none_on_save_failure():
    data = _make_symbols_data(2)
    with patch(f"{_DB_PATCH}.save_report", side_effect=Exception("db error")), \
         patch(f"{_DB_PATCH}.get_news_cache", return_value=[]), \
         patch(f"{_DB_PATCH}.get_scanner_results", return_value=[]), \
         patch(f"{_DB_PATCH}.get_account_history", return_value=[]):
        result = generate_pre_market_report(data)
    assert result is None


def test_empty_symbols_data_still_generates():
    with patch(f"{_DB_PATCH}.save_report", return_value=1) as mock_save, \
         patch(f"{_DB_PATCH}.get_news_cache", return_value=[]), \
         patch(f"{_DB_PATCH}.get_scanner_results", return_value=[]), \
         patch(f"{_DB_PATCH}.get_account_history", return_value=[]):
        result = generate_pre_market_report([])
    assert result == 1
    args = mock_save.call_args[0]
    assert "0 simbolos" in args[2]  # title


# ---------------------------------------------------------------------------
# market_key propagation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("market_key,expected_label", [
    ("STK_US",  "Acciones US"),
    ("FUT_US",  "Futuros US"),
    ("CASH_FX", "Forex"),
    ("CRYPTO",  "Crypto"),
    ("UNKNOWN", "UNKNOWN"),
])
def test_market_key_reflected_in_title(market_key, expected_label):
    data = _make_symbols_data(1)
    captured = {}

    def fake_save(report_type, date, title, content):
        captured["title"] = title
        captured["content"] = content
        return 99

    with patch(f"{_DB_PATCH}.save_report", side_effect=fake_save), \
         patch(f"{_DB_PATCH}.get_news_cache", return_value=[]), \
         patch(f"{_DB_PATCH}.get_scanner_results", return_value=[]), \
         patch(f"{_DB_PATCH}.get_account_history", return_value=[]):
        generate_pre_market_report(data, market_key=market_key)

    assert expected_label in captured["title"]
    assert expected_label in captured["content"]


# ---------------------------------------------------------------------------
# Layer labels in report content
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("layer,expected_tag", [
    ("open_position", "📌 Posición Abierta"),
    ("market_mover",  "📈 Market Mover"),
    ("universe",      "🔵 Universo"),
])
def test_layer_tag_appears_in_content(layer, expected_tag):
    data = [
        {
            "symbol": "AAPL",
            "score": None,
            "recommendation": "WATCHLIST",
            "narrative": "test",
            "rsi": None,
            "volume_ratio": None,
            "weekly_trend": "NEUTRAL",
            "layer": layer,
        }
    ]
    captured = {}

    def fake_save(report_type, date, title, content):
        captured["content"] = content
        return 1

    with patch(f"{_DB_PATCH}.save_report", side_effect=fake_save), \
         patch(f"{_DB_PATCH}.get_news_cache", return_value=[]), \
         patch(f"{_DB_PATCH}.get_scanner_results", return_value=[]), \
         patch(f"{_DB_PATCH}.get_account_history", return_value=[]):
        generate_pre_market_report(data)

    assert expected_tag in captured["content"]


def test_open_position_recommendation_label():
    data = [
        {
            "symbol": "NVDA",
            "score": None,
            "recommendation": "POSICIÓN ABIERTA",
            "narrative": "Posicion abierta.",
            "rsi": None,
            "volume_ratio": None,
            "weekly_trend": "NEUTRAL",
            "layer": "open_position",
        }
    ]
    captured = {}

    def fake_save(report_type, date, title, content):
        captured["content"] = content
        return 1

    with patch(f"{_DB_PATCH}.save_report", side_effect=fake_save), \
         patch(f"{_DB_PATCH}.get_news_cache", return_value=[]), \
         patch(f"{_DB_PATCH}.get_scanner_results", return_value=[]), \
         patch(f"{_DB_PATCH}.get_account_history", return_value=[]):
        generate_pre_market_report(data)

    assert "ABIERTA" in captured["content"]
    assert "NVDA" in captured["content"]


# ---------------------------------------------------------------------------
# Account snapshot and market context
# ---------------------------------------------------------------------------

def test_account_snapshot_included_when_available():
    captured = {}

    def fake_save(report_type, date, title, content):
        captured["content"] = content
        return 1

    with patch(f"{_DB_PATCH}.save_report", side_effect=fake_save), \
         patch(f"{_DB_PATCH}.get_news_cache", return_value=[]), \
         patch(f"{_DB_PATCH}.get_scanner_results", return_value=[]), \
         patch(f"{_DB_PATCH}.get_account_history", return_value=[
             {"net_liquidation": 12345.0, "buying_power": 8000.0}
         ]):
        generate_pre_market_report([])

    assert "12,345.00" in captured["content"]
    assert "8,000.00" in captured["content"]


def test_gainers_losers_included_in_market_context():
    captured = {}

    def fake_save(report_type, date, title, content):
        captured["content"] = content
        return 1

    def fake_scanner(scan_type):
        if scan_type == "gainers":
            return [{"symbol": "MSTR", "change_pct": 8.5, "volume_ratio": 2.0, "extra_json": "{}"}]
        if scan_type == "losers":
            return [{"symbol": "TSLA", "change_pct": -4.2, "volume_ratio": 1.5, "extra_json": "{}"}]
        return []

    with patch(f"{_DB_PATCH}.save_report", side_effect=fake_save), \
         patch(f"{_DB_PATCH}.get_news_cache", return_value=[]), \
         patch(f"{_DB_PATCH}.get_scanner_results", side_effect=fake_scanner), \
         patch(f"{_DB_PATCH}.get_account_history", return_value=[]):
        generate_pre_market_report([])

    assert "MSTR" in captured["content"]
    assert "TSLA" in captured["content"]
    assert "+8.5%" in captured["content"]
    assert "-4.2%" in captured["content"]
