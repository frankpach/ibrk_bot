# Issue LD-001: DB Foundation — 4 New Tables + SymbolParameter Fields

**Module**: live-dashboard
**Type**: AFK
**Effort**: S
**Blocked by**: None
**Requires review**: false

---

## WHY

The live dashboard needs persistent storage for 4 categories of data that don't exist yet:
position P&L snapshots (updated every 2min), daily account balance history (for equity curve),
news articles per symbol (for the news card), and scanner/sector results (for Market Trends).
Without these tables, every other dashboard issue is blocked.

**Success signal**: All 4 tables exist in SQLite after `init_db()`. SymbolParameter dataclass
has the 3 new fields. All existing tests still pass.

---

## WHO

| Persona | Role | Goal |
|---------|------|------|
| Motor Autónomo | System | Write live data to DB every 2-10min |
| Frank Developer | Quant | Tables available for subsequent issues |

---

## WHAT — Constraints

- [ ] All migrations via `_add_column_if_missing()` — idempotent, never breaks existing data
- [ ] All 4 tables created in `init_analysis_tables()` with `CREATE TABLE IF NOT EXISTS`
- [ ] `SymbolParameter` dataclass in `models.py` gets 3 new fields with defaults
- [ ] Do NOT touch `app/risk/` or `app/llm/`

---

## HOW

### A) 4 new tables in `app/db/database.py` — inside `init_analysis_tables()`

Add to the `conn.executescript("""...""")` block:

```sql
CREATE TABLE IF NOT EXISTS position_snapshots (
    trade_id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    current_price REAL,
    pnl_usd REAL,
    pnl_pct REAL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    net_liquidation REAL,
    buying_power REAL,
    daily_pnl_usd REAL,
    daily_pnl_pct REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS news_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT,
    headline TEXT NOT NULL,
    provider TEXT,
    sentiment TEXT,
    article_id TEXT,
    published_at TEXT,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scanner_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT,
    change_pct REAL,
    volume_ratio REAL,
    extra_json TEXT DEFAULT '{}',
    fetched_at TEXT NOT NULL
);
```

Also add column migration for `symbol_parameters`:
```python
_add_column_if_missing(conn, "symbol_parameters", "backtest_profit_factor", "REAL")
```

### B) CRUD functions in `app/db/database.py`

```python
def upsert_position_snapshot(trade_id, symbol, current_price, pnl_usd, pnl_pct):
    conn = get_connection()
    conn.execute("""INSERT OR REPLACE INTO position_snapshots
        (trade_id, symbol, current_price, pnl_usd, pnl_pct, updated_at)
        VALUES (?,?,?,?,?,?)""",
        (trade_id, symbol, current_price, pnl_usd, pnl_pct, datetime.utcnow().isoformat()))
    conn.commit(); conn.close()

def get_position_snapshots() -> dict:
    """Returns {trade_id: {current_price, pnl_usd, pnl_pct, updated_at}}"""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM position_snapshots").fetchall()
    conn.close()
    return {r["trade_id"]: dict(r) for r in rows}

def upsert_account_snapshot(date, net_liquidation, buying_power, daily_pnl_usd, daily_pnl_pct):
    conn = get_connection()
    conn.execute("""INSERT OR REPLACE INTO account_snapshots
        (date, net_liquidation, buying_power, daily_pnl_usd, daily_pnl_pct, created_at)
        VALUES (?,?,?,?,?,?)""",
        (date, net_liquidation, buying_power, daily_pnl_usd, daily_pnl_pct,
         datetime.utcnow().isoformat()))
    conn.commit(); conn.close()

def get_account_history(days: int = 30) -> list:
    """Returns last N days of account snapshots, oldest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM account_snapshots ORDER BY date DESC LIMIT ?", (days,)
    ).fetchall()
    conn.close()
    return list(reversed([dict(r) for r in rows]))

def insert_news_cache(symbol, headline, provider, sentiment, article_id, published_at):
    conn = get_connection()
    conn.execute("""INSERT INTO news_cache
        (symbol, headline, provider, sentiment, article_id, published_at, fetched_at)
        VALUES (?,?,?,?,?,?,?)""",
        (symbol, headline, provider, sentiment, article_id, published_at,
         datetime.utcnow().isoformat()))
    conn.commit(); conn.close()

def get_news_cache(symbols: list = None, limit: int = 20) -> list:
    conn = get_connection()
    if symbols:
        placeholders = ",".join("?" * len(symbols))
        rows = conn.execute(
            f"SELECT * FROM news_cache WHERE symbol IN ({placeholders}) "
            f"ORDER BY fetched_at DESC LIMIT ?",
            symbols + [limit]
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM news_cache ORDER BY fetched_at DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def clear_news_cache_older_than(hours: int = 24):
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    conn = get_connection()
    conn.execute("DELETE FROM news_cache WHERE fetched_at < ?", (cutoff,))
    conn.commit(); conn.close()

def upsert_scanner_results(scan_type: str, results: list):
    """Replace all results for a scan_type with fresh data."""
    conn = get_connection()
    conn.execute("DELETE FROM scanner_results WHERE scan_type=?", (scan_type,))
    now = datetime.utcnow().isoformat()
    for r in results:
        conn.execute("""INSERT INTO scanner_results
            (scan_type, symbol, name, change_pct, volume_ratio, extra_json, fetched_at)
            VALUES (?,?,?,?,?,?,?)""",
            (scan_type, r.get("symbol"), r.get("name"), r.get("change_pct"),
             r.get("volume_ratio"), r.get("extra_json", "{}"), now))
    conn.commit(); conn.close()

def get_scanner_results(scan_type: str) -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM scanner_results WHERE scan_type=? ORDER BY rowid",
        (scan_type,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
```

### C) `app/db/models.py` — SymbolParameter dataclass

Add 3 fields after `updated_at`:
```python
backtest_calibrated: int = 0
backtest_calibrated_at: Optional[str] = None
backtest_profit_factor: Optional[float] = None
```

Also update `get_or_create_symbol_parameters()` to include these fields when building the object from DB rows.

---

## Code Search

- [x] `app/db/database.py:75` — `_add_column_if_missing()` confirmed
- [x] `app/db/database.py:724` — `init_analysis_tables()` location confirmed
- [x] `app/db/models.py:118` — SymbolParameter fields confirmed; `backtest_calibrated` and `backtest_calibrated_at` already exist in DB schema but NOT in the dataclass
- [x] `app/db/database.py:775` — `get_or_create_symbol_parameters()` confirmed

**Reuse decision**:
- Pattern from `insert_feature_snapshot()` and `get_closed_trades_with_snapshots()` for new CRUD functions

---

## Reference Documents

| Document | Path |
|----------|------|
| Spec | `docs/superpowers/specs/2026-05-13-live-dashboard-design.md` |
| Architecture map | `docs/dev/artifacts/live-dashboard/03-architecture-map.md` |

---

## Acceptance Criteria

- [ ] AC-01: `init_db()` creates all 4 new tables without error on fresh DB
- [ ] AC-02: `init_db()` is idempotent — running twice doesn't fail or duplicate
- [ ] AC-03: `upsert_position_snapshot(1, "AAPL", 184.20, 4.21, 0.0104)` inserts and re-inserting updates
- [ ] AC-04: `get_account_history(30)` returns list oldest-first
- [ ] AC-05: `upsert_scanner_results("gainers", [...])` replaces previous gainers data
- [ ] AC-06: `SymbolParameter` dataclass has `backtest_calibrated`, `backtest_calibrated_at`, `backtest_profit_factor`
- [ ] AC-07: `pytest tests/db/test_database.py` passes
- [ ] AC-08: `pytest tests/` — no regressions (764 tests passing)

## Definition of Done

- [ ] All ACs verified
- [ ] Tests for new CRUD functions
- [ ] Issue moved to `done/`
