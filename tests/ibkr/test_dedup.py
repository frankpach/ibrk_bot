# tests/ibkr/test_dedup.py
import time
from datetime import datetime
from unittest.mock import MagicMock, patch
from app.ibkr.dedup import OrderDeduplicator, PreflightChecker, get_deduplicator


def test_is_duplicate_within_window():
    d = OrderDeduplicator()
    assert not d.is_duplicate("AAPL", "BUY")
    d.record("AAPL", "BUY")
    assert d.is_duplicate("AAPL", "BUY")
    assert not d.is_duplicate("AAPL", "SELL")


def test_is_duplicate_after_window():
    d = OrderDeduplicator()
    d.DEDUP_WINDOW_SECONDS = 0.05
    d.record("AAPL", "BUY")
    time.sleep(0.06)
    assert not d.is_duplicate("AAPL", "BUY")


@patch("app.ibkr.dedup.datetime")
def test_preflight_connection_ok(mock_dt):
    mock_dt.now.return_value = datetime(2026, 5, 5, 10, 0)  # Tuesday 10am
    client = MagicMock()
    client.ib.isConnected.return_value = True
    p = PreflightChecker(client)
    r = p.check("AAPL", "BUY", 10, "MKT")
    assert r.ok


@patch("app.ibkr.dedup.datetime")
def test_preflight_not_connected(mock_dt):
    mock_dt.now.return_value = datetime(2026, 5, 5, 10, 0)
    client = MagicMock()
    client.ib.isConnected.return_value = False
    p = PreflightChecker(client)
    r = p.check("AAPL", "BUY", 10, "MKT")
    assert not r.ok
    assert "connected" in r.reason.lower()


@patch("app.ibkr.dedup.datetime")
def test_preflight_symbol_not_allowed(mock_dt):
    mock_dt.now.return_value = datetime(2026, 5, 5, 10, 0)
    client = MagicMock()
    client.ib.isConnected.return_value = True
    p = PreflightChecker(client)
    r = p.check("FAKE", "BUY", 10, "MKT")
    assert not r.ok
    assert "not in allowed" in r.reason


@patch("app.ibkr.dedup.datetime")
def test_preflight_negative_quantity(mock_dt):
    mock_dt.now.return_value = datetime(2026, 5, 5, 10, 0)
    client = MagicMock()
    client.ib.isConnected.return_value = True
    p = PreflightChecker(client)
    r = p.check("AAPL", "BUY", -1, "MKT")
    assert not r.ok


@patch("app.ibkr.dedup.datetime")
def test_preflight_lmt_without_price(mock_dt):
    mock_dt.now.return_value = datetime(2026, 5, 5, 10, 0)
    client = MagicMock()
    client.ib.isConnected.return_value = True
    p = PreflightChecker(client)
    r = p.check("AAPL", "BUY", 10, "LMT")
    assert not r.ok
    assert "requires limit_price" in r.reason


@patch("app.ibkr.dedup.datetime")
def test_preflight_weekend(mock_dt):
    client = MagicMock()
    client.ib.isConnected.return_value = True
    p = PreflightChecker(client)
    saturday = datetime(2026, 5, 9, 10, 0)
    mock_dt.now.return_value = saturday
    r = p.check("AAPL", "BUY", 10, "MKT")
    assert not r.ok
    assert "weekend" in r.reason


def test_get_deduplicator_singleton():
    d1 = get_deduplicator()
    d2 = get_deduplicator()
    assert d1 is d2
