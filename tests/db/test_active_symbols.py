"""Tests for active_symbols DB functions in app/db/database.py."""
from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from app.infrastructure.db.compat import (
    get_active_symbols,
    get_all_active_symbols_today,
    init_active_symbols_table,
    upsert_active_symbols,
)

TODAY = date.today().isoformat()


@pytest.fixture()
def mem_db() -> sqlite3.Connection:
    """In-memory SQLite DB with active_symbols and minimal symbol_config."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS symbol_config (
            symbol       TEXT NOT NULL,
            market_key   TEXT NOT NULL,
            sec_type     TEXT,
            exchange     TEXT,
            currency     TEXT,
            liquid_hours TEXT,
            PRIMARY KEY (symbol, market_key)
        )
        """
    )
    conn.commit()
    return conn


class TestInitActiveSymbolsTable:
    def test_table_creation(self, mem_db):
        init_active_symbols_table(mem_db)
        cursor = mem_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='active_symbols'"
        )
        assert cursor.fetchone() is not None

    def test_table_creation_is_idempotent(self, mem_db):
        init_active_symbols_table(mem_db)
        init_active_symbols_table(mem_db)  # should not raise


class TestUpsertActiveSymbols:
    def test_upsert_inserts_symbols(self, mem_db):
        init_active_symbols_table(mem_db)
        upsert_active_symbols("STK_US", ["AAPL", "NVDA"], TODAY, conn=mem_db)
        rows = mem_db.execute(
            "SELECT symbol FROM active_symbols WHERE market_key='STK_US' AND session_date=?",
            (TODAY,),
        ).fetchall()
        symbols = {r[0] for r in rows}
        assert symbols == {"AAPL", "NVDA"}

    def test_upsert_is_idempotent(self, mem_db):
        init_active_symbols_table(mem_db)
        upsert_active_symbols("STK_US", ["AAPL"], TODAY, conn=mem_db)
        upsert_active_symbols("STK_US", ["AAPL"], TODAY, conn=mem_db)
        count = mem_db.execute(
            "SELECT COUNT(*) FROM active_symbols WHERE market_key='STK_US' AND session_date=?",
            (TODAY,),
        ).fetchone()[0]
        assert count == 1

    def test_upsert_stores_scores(self, mem_db):
        init_active_symbols_table(mem_db)
        scores = {"AAPL": 87.5, "NVDA": 92.0}
        upsert_active_symbols("STK_US", ["AAPL", "NVDA"], TODAY, scores=scores, conn=mem_db)
        row = mem_db.execute(
            "SELECT score FROM active_symbols WHERE symbol='NVDA' AND session_date=?",
            (TODAY,),
        ).fetchone()
        assert row[0] == pytest.approx(92.0)

    def test_upsert_updates_existing_score(self, mem_db):
        init_active_symbols_table(mem_db)
        upsert_active_symbols("STK_US", ["AAPL"], TODAY, scores={"AAPL": 50.0}, conn=mem_db)
        upsert_active_symbols("STK_US", ["AAPL"], TODAY, scores={"AAPL": 99.0}, conn=mem_db)
        row = mem_db.execute(
            "SELECT score FROM active_symbols WHERE symbol='AAPL' AND session_date=?",
            (TODAY,),
        ).fetchone()
        assert row[0] == pytest.approx(99.0)


class TestGetActiveSymbols:
    def test_get_returns_correct_symbols(self, mem_db):
        init_active_symbols_table(mem_db)
        upsert_active_symbols("STK_US", ["AAPL", "MSFT"], TODAY, conn=mem_db)
        upsert_active_symbols("CRYPTO", ["BTC", "ETH"], TODAY, conn=mem_db)
        result = get_active_symbols("STK_US", TODAY, conn=mem_db)
        assert set(result) == {"AAPL", "MSFT"}

    def test_get_returns_empty_for_unknown_market(self, mem_db):
        init_active_symbols_table(mem_db)
        result = get_active_symbols("NONEXISTENT", TODAY, conn=mem_db)
        assert result == []

    def test_get_orders_by_score_descending(self, mem_db):
        init_active_symbols_table(mem_db)
        scores = {"LOW": 10.0, "HIGH": 95.0, "MID": 55.0}
        upsert_active_symbols("STK_US", ["LOW", "HIGH", "MID"], TODAY, scores=scores, conn=mem_db)
        result = get_active_symbols("STK_US", TODAY, conn=mem_db)
        assert result == ["HIGH", "MID", "LOW"]


class TestGetAllActiveSymbolsToday:
    def test_get_all_merges_across_markets(self, mem_db):
        init_active_symbols_table(mem_db)
        upsert_active_symbols("STK_US", ["AAPL"], TODAY, conn=mem_db)
        upsert_active_symbols("CRYPTO", ["BTC"], TODAY, conn=mem_db)
        result = get_all_active_symbols_today(TODAY, conn=mem_db)
        symbols = {r["symbol"] for r in result}
        assert "AAPL" in symbols
        assert "BTC" in symbols

    def test_get_all_returns_dicts_with_required_keys(self, mem_db):
        init_active_symbols_table(mem_db)
        upsert_active_symbols("STK_US", ["AAPL"], TODAY, conn=mem_db)
        result = get_all_active_symbols_today(TODAY, conn=mem_db)
        assert len(result) == 1
        row = result[0]
        for key in ("symbol", "market_key", "score"):
            assert key in row, f"Missing key: {key}"

    def test_get_all_returns_empty_when_no_rows(self, mem_db):
        init_active_symbols_table(mem_db)
        result = get_all_active_symbols_today(TODAY, conn=mem_db)
        assert result == []

    def test_get_all_only_returns_todays_rows(self, mem_db):
        init_active_symbols_table(mem_db)
        upsert_active_symbols("STK_US", ["AAPL"], "2026-01-01", conn=mem_db)
        result = get_all_active_symbols_today(TODAY, conn=mem_db)
        assert result == []
