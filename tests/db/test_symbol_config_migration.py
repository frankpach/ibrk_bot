import sqlite3
import pytest
from app.db import database


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    database.init_db()
    yield str(db_path)


def _columns(db_path: str, table: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    finally:
        conn.close()
    return {row[1] for row in rows}


def test_symbol_config_has_multi_market_columns(fresh_db):
    cols = _columns(fresh_db, "symbol_config")
    assert "sec_type" in cols
    assert "exchange" in cols
    assert "currency" in cols
    assert "liquid_hours" in cols
    assert "market_key" in cols


def test_default_seed_contains_40_symbols(fresh_db):
    conn = sqlite3.connect(fresh_db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT symbol, sec_type, exchange, currency, market_key "
        "FROM symbol_config WHERE approved=1"
    ).fetchall()
    conn.close()

    by_sec = {}
    for r in rows:
        by_sec.setdefault(r["sec_type"], []).append(r["symbol"])

    assert len(by_sec.get("STK", [])) == 10
    assert len(by_sec.get("FUT", [])) == 10
    assert len(by_sec.get("CASH", [])) == 10
    assert len(by_sec.get("CRYPTO", [])) == 10
    assert "AAPL" in by_sec["STK"]
    assert "ES" in by_sec["FUT"]
    assert "EURUSD" in by_sec["CASH"]
    assert "BTC" in by_sec["CRYPTO"]


def test_migration_is_idempotent(fresh_db):
    # Running init_db twice must not raise nor duplicate seed rows
    database.init_db()
    database.init_db()
    conn = sqlite3.connect(fresh_db)
    count = conn.execute("SELECT COUNT(*) FROM symbol_config").fetchone()[0]
    conn.close()
    assert count == 40


def test_seeded_futures_have_correct_exchanges(fresh_db):
    conn = sqlite3.connect(fresh_db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT symbol, exchange FROM symbol_config WHERE sec_type='FUT'"
    ).fetchall()
    conn.close()
    mapping = {r["symbol"]: r["exchange"] for r in rows}
    assert mapping["ES"] == "CME"
    assert mapping["CL"] == "NYMEX"
    assert mapping["GC"] == "COMEX"
    assert mapping["ZB"] == "CBOT"


def test_seeded_forex_uses_idealpro(fresh_db):
    conn = sqlite3.connect(fresh_db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT exchange FROM symbol_config WHERE sec_type='CASH'"
    ).fetchall()
    conn.close()
    assert all(r["exchange"] == "IDEALPRO" for r in rows)


def test_get_approved_symbols_with_meta_returns_correct_structure(fresh_db):
    from app.db.database import get_approved_symbols_with_meta
    rows = get_approved_symbols_with_meta()
    assert len(rows) == 40
    required_keys = {"symbol", "sec_type", "exchange", "currency", "liquid_hours", "market_key"}
    for row in rows:
        assert required_keys <= row.keys(), f"Missing keys in row: {row}"
    # spot-check one known row
    stk_rows = [r for r in rows if r["sec_type"] == "STK"]
    assert len(stk_rows) == 10
