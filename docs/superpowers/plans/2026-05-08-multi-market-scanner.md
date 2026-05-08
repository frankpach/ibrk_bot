# Multi-Market Pre-Open Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 15 minutes before each market opens, use IB Scanner (for STK_US) or curated seed lists (FUT/FX/CRYPTO) to select top-10 symbols for that session, scored with QuantScorer, replacing the static ALLOWED_SYMBOLS universe.

**Architecture:** A new `active_symbols` DB table stores the day's selected symbols per market. A pre-open scheduler job runs before each market session, scores candidates, and fills the table. `run_scan()` reads from `active_symbols` instead of the full approved list. Open positions always stay in the active set regardless of score.

**Tech Stack:** Python 3.13, ib_insync, FastAPI, SQLite (WAL), pytest, APScheduler

**Depends on:** Plan A (2026-05-08-multi-market-foundation.md) must be merged first.

---

## Context the implementer needs

### What Plan A provides (already implemented when this plan runs)
- `symbol_config` table has `sec_type`, `exchange`, `currency`, `liquid_hours`, `market_key` columns, seeded with 40 symbols (10 each: STK_US, FUT_US, CASH_FX, CRYPTO)
- `app/ibkr/contract_factory.py` — `build_contract()`, `get_what_to_show()`, `get_use_rth()`
- `app/scanner/liquid_hours.py` — `is_liquid_at(now, code)`
- `app/db/database.py` — `get_approved_symbols_with_meta()`
- `app/scanner/preprocessor.py` — `run_scan()` loops over metadata from DB

### IB Scanner facts (verified live on paper account)
- `reqScannerDataAsync(ScannerSubscription(instrument="STK", locationCode="STK.US.MAJOR", scanCode="MOST_ACTIVE"))` → returns 50 results in under 2s
- Scan codes that work: `MOST_ACTIVE`, `TOP_VOLUME_RATE`, `HOT_BY_PRICE`
- FUT scanner returns 0 results in paper (market closed or not supported) → fall back to full seed list
- No FX or CRYPTO locationCode exists in IB Scanner → use full seed list for those
- clientId=77 is free for scanner use

### QuantScorer location
Check if `app/analysis/scorer.py` exists. If it does, use `QuantScorer`. If not, use this simplified score:
```python
def simple_score(rsi: float | None, volume_ratio: float | None) -> float:
    rsi_score = abs((rsi or 50) - 50) / 50  # 0.0 to 1.0, higher = more extreme
    vol_score = min((volume_ratio or 1.0) / 3.0, 1.0)  # capped at 3x avg
    return (rsi_score * 0.6 + vol_score * 0.4) * 100
```

### Market session times (for pre-open jobs)
| Market | Opens | Pre-open job time | Days |
|---|---|---|---|
| STK_US | 09:30 ET | 09:15 ET | Mon-Fri |
| FUT_US | 18:00 ET | 17:45 ET | Sun-Thu |
| CASH_FX | 17:00 ET | 16:45 ET | Sun-Thu |
| CRYPTO | 00:00 UTC | 23:45 UTC prev day | Daily |

### `run.py` scheduler pattern (existing)
```python
scheduler.add_job(
    lambda: run_scan(ib_client),
    trigger="interval",
    minutes=SCAN_INTERVAL_MINUTES,
    id="scanner",
)
```
Cron jobs use: `trigger="cron", hour=9, minute=15, day_of_week="mon-fri", timezone=MARKET_TZ`

---

## Tasks

### Task B1: `app/ibkr/ib_scanner.py` + tests

- [ ] Create `app/ibkr/ib_scanner.py` with `run_ib_scanner()` and `get_stk_us_candidates()`
- [ ] Create `tests/ibkr/test_ib_scanner.py` with 4 tests
- [ ] Verify: `pytest tests/ibkr/test_ib_scanner.py -q` passes

#### Implementation: `app/ibkr/ib_scanner.py`

```python
"""
IB Scanner integration for pre-open symbol selection.

Only STK_US uses the live IB Scanner. FUT, FX, and CRYPTO fall back to
their full seed lists because IB Scanner does not reliably return results
for those instrument types on paper accounts.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ib_insync import ScannerSubscription

if TYPE_CHECKING:
    from app.ibkr.ib_client import IBClient

logger = logging.getLogger(__name__)

# Scan codes run in order; union is ranked by first appearance
STK_US_SCAN_CODES = ["MOST_ACTIVE", "TOP_VOLUME_RATE", "HOT_BY_PRICE"]
STK_US_LOCATION = "STK.US.MAJOR"
STK_US_INSTRUMENT = "STK"


def run_ib_scanner(
    ib_client: "IBClient",
    scan_code: str,
    location: str,
    instrument: str,
    limit: int = 50,
) -> list[dict]:
    """
    Run one IB scanner subscription synchronously.

    Args:
        ib_client: Connected IBClient instance (uses ib_client.ib internally).
        scan_code: IB scan code, e.g. "MOST_ACTIVE".
        location: IB location code, e.g. "STK.US.MAJOR".
        instrument: IB instrument type, e.g. "STK".
        limit: Maximum number of results to return.

    Returns:
        List of dicts [{"symbol": str, "rank": int}, ...], ordered by IB rank.
        Returns empty list on any error.
    """
    sub = ScannerSubscription(
        instrument=instrument,
        locationCode=location,
        scanCode=scan_code,
        numberOfRows=limit,
    )
    try:
        scan_data = ib_client.ib.reqScannerData(sub)
    except Exception as exc:
        logger.warning(
            "IB scanner %s/%s failed: %s", location, scan_code, exc
        )
        return []

    results: list[dict] = []
    for item in scan_data[:limit]:
        symbol = getattr(item.contractDetails.contract, "symbol", None)
        if symbol:
            results.append({"symbol": symbol, "rank": item.rank})

    logger.info(
        "IB scanner %s/%s returned %d results", location, scan_code, len(results)
    )
    return results


def get_stk_us_candidates(
    ib_client: "IBClient",
    limit: int = 50,
) -> list[dict]:
    """
    Union MOST_ACTIVE + TOP_VOLUME_RATE + HOT_BY_PRICE from STK.US.MAJOR.

    Deduplicates by symbol. Ranking is determined by earliest appearance
    across the three scans (lower rank = appears first = better).

    Args:
        ib_client: Connected IBClient instance.
        limit: Maximum symbols to return after union.

    Returns:
        List of dicts [{"symbol": str, "rank": int}, ...], deduplicated
        and sorted by composite rank (ascending = best first).
    """
    seen: dict[str, int] = {}   # symbol -> best (lowest) composite rank
    composite_rank = 0

    for scan_code in STK_US_SCAN_CODES:
        results = run_ib_scanner(
            ib_client,
            scan_code=scan_code,
            location=STK_US_LOCATION,
            instrument=STK_US_INSTRUMENT,
            limit=limit,
        )
        for item in results:
            symbol = item["symbol"]
            if symbol not in seen:
                seen[symbol] = composite_rank
                composite_rank += 1
            # Already seen: keep original (earlier) rank

    sorted_symbols = sorted(seen.items(), key=lambda kv: kv[1])
    candidates = [
        {"symbol": sym, "rank": rank} for sym, rank in sorted_symbols[:limit]
    ]
    logger.info(
        "get_stk_us_candidates: %d unique symbols from union of %d scans",
        len(candidates),
        len(STK_US_SCAN_CODES),
    )
    return candidates
```

#### Test file: `tests/ibkr/test_ib_scanner.py`

```python
"""
Tests for app/ibkr/ib_scanner.py

Uses synchronous mocks for ib_client.ib.reqScannerData because ib_insync's
async scanner API is difficult to drive in unit tests.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.ibkr.ib_scanner import get_stk_us_candidates, run_ib_scanner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scan_item(symbol: str, rank: int) -> MagicMock:
    """Build a fake ib_insync ScanData item."""
    item = MagicMock()
    item.rank = rank
    item.contractDetails.contract.symbol = symbol
    return item


def _make_ib_client(scan_items: list[MagicMock]) -> MagicMock:
    """Build a fake IBClient whose reqScannerData returns scan_items."""
    ib_client = MagicMock()
    ib_client.ib.reqScannerData.return_value = scan_items
    return ib_client


# ---------------------------------------------------------------------------
# Tests for run_ib_scanner
# ---------------------------------------------------------------------------

class TestRunIbScanner:
    def test_run_ib_scanner_returns_symbol_list(self):
        """run_ib_scanner returns a list of dicts with 'symbol' and 'rank' keys."""
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
        """run_ib_scanner truncates results to the given limit."""
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
        """run_ib_scanner returns [] instead of raising when IB throws."""
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
        """Items whose contract has no symbol are silently dropped."""
        good = _make_scan_item("TSLA", 0)
        bad = MagicMock()
        bad.rank = 1
        bad.contractDetails.contract.symbol = None  # missing symbol

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


# ---------------------------------------------------------------------------
# Tests for get_stk_us_candidates
# ---------------------------------------------------------------------------

class TestGetStkUsCandidates:
    def _mock_run_scanner(self, per_scan_results: dict[str, list[MagicMock]]):
        """
        Return a patched run_ib_scanner that yields different results per
        scan_code. Keys in per_scan_results map scan_code -> list of items.
        """
        def _fake_run(ib_client, scan_code, location, instrument, limit=50):
            items = per_scan_results.get(scan_code, [])
            return [
                {"symbol": it.contractDetails.contract.symbol, "rank": it.rank}
                for it in items
                if it.contractDetails.contract.symbol
            ]

        return patch("app.ibkr.ib_scanner.run_ib_scanner", side_effect=_fake_run)

    def test_get_stk_us_candidates_returns_symbols_list(self):
        """get_stk_us_candidates returns a non-empty list of dicts."""
        items = [_make_scan_item("AAPL", 0), _make_scan_item("MSFT", 1)]
        ib_client = _make_ib_client(items)
        # All three scan codes return the same two symbols
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
        """Symbols appearing in multiple scans appear only once in output."""
        # AAPL appears in all 3 scans; NVDA appears in 2; TSLA only in 1
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
        """Symbol seen first in MOST_ACTIVE gets lower (better) rank than one
        seen only in later scans."""
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
        """Output is capped at the given limit."""
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
```

---

### Task B2: DB `active_symbols` table

- [ ] Add `init_active_symbols_table()` to `app/db/database.py` and call it from `init_db()`
- [ ] Add `upsert_active_symbols()`, `get_active_symbols()`, `get_all_active_symbols_today()` to `app/db/database.py`
- [ ] Create `tests/db/test_active_symbols.py` with 4 tests
- [ ] Verify: `pytest tests/db/test_active_symbols.py -q` passes

#### Implementation additions to `app/db/database.py`

Add these functions after the existing `init_db()` and related helpers. The SQL DDL goes into `init_active_symbols_table()`, which must be called inside the existing `init_db()` function.

```python
# -- active_symbols table ----------------------------------------------------

ACTIVE_SYMBOLS_DDL = """
CREATE TABLE IF NOT EXISTS active_symbols (
    symbol       TEXT NOT NULL,
    market_key   TEXT NOT NULL,
    score        REAL DEFAULT 0.0,
    selected_at  TEXT NOT NULL,
    session_date TEXT NOT NULL,
    PRIMARY KEY (symbol, market_key, session_date)
);
"""


def init_active_symbols_table(conn=None) -> None:
    """Create active_symbols table if it does not exist.

    Called automatically from init_db(). May also be called directly in
    tests that use an in-memory DB.
    """
    _conn = conn or get_connection()
    _conn.execute(ACTIVE_SYMBOLS_DDL)
    _conn.commit()


def upsert_active_symbols(
    market_key: str,
    symbols: list[str],
    session_date: str,
    scores: dict[str, float] | None = None,
    conn=None,
) -> None:
    """Insert or replace the active symbol set for a market and date.

    Args:
        market_key:   Market identifier, e.g. "STK_US".
        symbols:      Ordered list of symbol strings to persist.
        session_date: ISO date string, e.g. "2026-05-08".
        scores:       Optional mapping symbol -> score. Missing symbols get 0.0.
        conn:         Optional existing DB connection (for testing).
    """
    from datetime import datetime, timezone

    _conn = conn or get_connection()
    selected_at = datetime.now(timezone.utc).isoformat()
    _scores = scores or {}

    _conn.executemany(
        """
        INSERT OR REPLACE INTO active_symbols
            (symbol, market_key, score, selected_at, session_date)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (sym, market_key, _scores.get(sym, 0.0), selected_at, session_date)
            for sym in symbols
        ],
    )
    _conn.commit()


def get_active_symbols(
    market_key: str,
    session_date: str,
    conn=None,
) -> list[str]:
    """Return active symbols for a market on a given session date.

    Args:
        market_key:   Market identifier, e.g. "STK_US".
        session_date: ISO date string, e.g. "2026-05-08".
        conn:         Optional existing DB connection (for testing).

    Returns:
        List of symbol strings, ordered by descending score.
    """
    _conn = conn or get_connection()
    cursor = _conn.execute(
        """
        SELECT symbol FROM active_symbols
        WHERE market_key = ? AND session_date = ?
        ORDER BY score DESC
        """,
        (market_key, session_date),
    )
    return [row[0] for row in cursor.fetchall()]


def get_all_active_symbols_today(
    session_date: str,
    conn=None,
) -> list[dict]:
    """Return all active symbols across all markets for today.

    Joins with symbol_config to provide metadata required by run_scan().

    Args:
        session_date: ISO date string, e.g. "2026-05-08".
        conn:         Optional existing DB connection (for testing).

    Returns:
        List of dicts with keys: symbol, market_key, score, sec_type,
        exchange, currency, liquid_hours. Empty list if no rows found.
    """
    _conn = conn or get_connection()
    cursor = _conn.execute(
        """
        SELECT
            a.symbol,
            a.market_key,
            a.score,
            s.sec_type,
            s.exchange,
            s.currency,
            s.liquid_hours
        FROM active_symbols a
        LEFT JOIN symbol_config s
            ON a.symbol = s.symbol AND a.market_key = s.market_key
        WHERE a.session_date = ?
        ORDER BY a.market_key, a.score DESC
        """,
        (session_date,),
    )
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
```

**In `init_db()`, add the call:**

```python
def init_db(conn=None) -> None:
    """Initialise all application tables."""
    _conn = conn or get_connection()
    # ... existing table initialisations ...
    init_active_symbols_table(_conn)   # <-- add this line
    _conn.commit()
```

#### Test file: `tests/db/test_active_symbols.py`

```python
"""
Tests for active_symbols DB functions in app/db/database.py.

All tests use an in-memory SQLite database to avoid touching the real DB.
"""
from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from app.db.database import (
    get_active_symbols,
    get_all_active_symbols_today,
    init_active_symbols_table,
    upsert_active_symbols,
)

TODAY = date.today().isoformat()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mem_db() -> sqlite3.Connection:
    """In-memory SQLite DB with active_symbols (and minimal symbol_config)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Minimal symbol_config so JOIN in get_all_active_symbols_today works
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInitActiveSymbolsTable:
    def test_table_creation(self, mem_db):
        """init_active_symbols_table creates the table without errors."""
        init_active_symbols_table(mem_db)

        cursor = mem_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='active_symbols'"
        )
        assert cursor.fetchone() is not None, "active_symbols table was not created"

    def test_table_creation_is_idempotent(self, mem_db):
        """Calling init_active_symbols_table twice does not raise."""
        init_active_symbols_table(mem_db)
        init_active_symbols_table(mem_db)  # should not raise


class TestUpsertActiveSymbols:
    def test_upsert_inserts_symbols(self, mem_db):
        """upsert_active_symbols persists symbols to the DB."""
        init_active_symbols_table(mem_db)
        upsert_active_symbols("STK_US", ["AAPL", "NVDA"], TODAY, conn=mem_db)

        rows = mem_db.execute(
            "SELECT symbol FROM active_symbols WHERE market_key='STK_US' AND session_date=?",
            (TODAY,),
        ).fetchall()
        symbols = {r[0] for r in rows}
        assert symbols == {"AAPL", "NVDA"}

    def test_upsert_is_idempotent(self, mem_db):
        """Upserting the same symbols twice does not duplicate rows."""
        init_active_symbols_table(mem_db)
        upsert_active_symbols("STK_US", ["AAPL"], TODAY, conn=mem_db)
        upsert_active_symbols("STK_US", ["AAPL"], TODAY, conn=mem_db)

        count = mem_db.execute(
            "SELECT COUNT(*) FROM active_symbols WHERE market_key='STK_US' AND session_date=?",
            (TODAY,),
        ).fetchone()[0]
        assert count == 1

    def test_upsert_stores_scores(self, mem_db):
        """upsert_active_symbols persists per-symbol scores."""
        init_active_symbols_table(mem_db)
        scores = {"AAPL": 87.5, "NVDA": 92.0}
        upsert_active_symbols("STK_US", ["AAPL", "NVDA"], TODAY, scores=scores, conn=mem_db)

        row = mem_db.execute(
            "SELECT score FROM active_symbols WHERE symbol='NVDA' AND session_date=?",
            (TODAY,),
        ).fetchone()
        assert row[0] == pytest.approx(92.0)

    def test_upsert_updates_existing_score(self, mem_db):
        """Re-upserting a symbol with a new score replaces the old score."""
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
        """get_active_symbols returns only symbols for the requested market+date."""
        init_active_symbols_table(mem_db)
        upsert_active_symbols("STK_US", ["AAPL", "MSFT"], TODAY, conn=mem_db)
        upsert_active_symbols("CRYPTO", ["BTC", "ETH"], TODAY, conn=mem_db)

        result = get_active_symbols("STK_US", TODAY, conn=mem_db)
        assert set(result) == {"AAPL", "MSFT"}

    def test_get_returns_empty_for_unknown_market(self, mem_db):
        """get_active_symbols returns [] for a market that has no rows."""
        init_active_symbols_table(mem_db)
        result = get_active_symbols("NONEXISTENT", TODAY, conn=mem_db)
        assert result == []

    def test_get_orders_by_score_descending(self, mem_db):
        """get_active_symbols returns symbols sorted by score, highest first."""
        init_active_symbols_table(mem_db)
        scores = {"LOW": 10.0, "HIGH": 95.0, "MID": 55.0}
        upsert_active_symbols(
            "STK_US", ["LOW", "HIGH", "MID"], TODAY, scores=scores, conn=mem_db
        )

        result = get_active_symbols("STK_US", TODAY, conn=mem_db)
        assert result == ["HIGH", "MID", "LOW"]


class TestGetAllActiveSymbolsToday:
    def test_get_all_merges_across_markets(self, mem_db):
        """get_all_active_symbols_today returns symbols from all markets."""
        init_active_symbols_table(mem_db)
        upsert_active_symbols("STK_US", ["AAPL"], TODAY, conn=mem_db)
        upsert_active_symbols("CRYPTO", ["BTC"], TODAY, conn=mem_db)

        result = get_all_active_symbols_today(TODAY, conn=mem_db)
        symbols = {r["symbol"] for r in result}
        assert "AAPL" in symbols
        assert "BTC" in symbols

    def test_get_all_returns_dicts_with_required_keys(self, mem_db):
        """Each row has the keys required by run_scan()."""
        init_active_symbols_table(mem_db)
        upsert_active_symbols("STK_US", ["AAPL"], TODAY, conn=mem_db)

        result = get_all_active_symbols_today(TODAY, conn=mem_db)
        assert len(result) == 1
        row = result[0]
        for key in ("symbol", "market_key", "score"):
            assert key in row, f"Missing key: {key}"

    def test_get_all_returns_empty_when_no_rows(self, mem_db):
        """get_all_active_symbols_today returns [] when table is empty."""
        init_active_symbols_table(mem_db)
        result = get_all_active_symbols_today(TODAY, conn=mem_db)
        assert result == []

    def test_get_all_only_returns_todays_rows(self, mem_db):
        """Symbols from a different date are not returned."""
        init_active_symbols_table(mem_db)
        upsert_active_symbols("STK_US", ["AAPL"], "2026-01-01", conn=mem_db)

        result = get_all_active_symbols_today(TODAY, conn=mem_db)
        assert result == []
```

---

### Task B3: `app/scanner/market_open_selector.py` + tests

- [ ] Create `app/scanner/market_open_selector.py` with `simple_score()` and `select_top_symbols()`
- [ ] Create `tests/scanner/test_market_open_selector.py` with 3 tests
- [ ] Verify: `pytest tests/scanner/test_market_open_selector.py -q` passes

#### Implementation: `app/scanner/market_open_selector.py`

```python
"""
Pre-open symbol selector.

15 minutes before each market session, `select_top_symbols()` is called by the
APScheduler cron job. It:
  1. Fetches candidate symbols (IB Scanner for STK_US, seed list otherwise).
  2. Scores each candidate with simple_score() (or QuantScorer if available).
  3. Always includes open positions regardless of score.
  4. Saves top-N to the active_symbols DB table.
  5. Returns the selected symbol list for logging.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.ibkr.ib_client import IBClient

logger = logging.getLogger(__name__)

# Market keys that use IB Scanner for candidate generation
IB_SCANNER_MARKETS = {"STK_US"}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _get_scorer():
    """Return QuantScorer if available, else None (use simple_score)."""
    try:
        from app.analysis.scorer import QuantScorer  # noqa: PLC0415
        return QuantScorer()
    except ImportError:
        return None


def simple_score(rsi: float | None, volume_ratio: float | None) -> float:
    """Score a symbol using RSI extremeness and volume ratio.

    Args:
        rsi:          14-period RSI, or None if unavailable.
        volume_ratio: Today's volume / 20-day average, or None if unavailable.

    Returns:
        Score in [0, 100]. Higher = more tradeable.
    """
    rsi_score = abs((rsi or 50) - 50) / 50       # 0.0-1.0, higher = more extreme
    vol_score = min((volume_ratio or 1.0) / 3.0, 1.0)  # capped at 3x avg
    return (rsi_score * 0.6 + vol_score * 0.4) * 100


def _score_symbol(scorer, symbol: str, indicators: dict) -> float:
    """Route scoring through QuantScorer or simple_score."""
    rsi = indicators.get("rsi")
    volume_ratio = indicators.get("volume_ratio")
    if scorer is not None:
        try:
            return scorer.score(symbol, rsi=rsi, volume_ratio=volume_ratio)
        except Exception as exc:
            logger.warning("QuantScorer failed for %s: %s", symbol, exc)
    return simple_score(rsi, volume_ratio)


# ---------------------------------------------------------------------------
# Candidate source
# ---------------------------------------------------------------------------

def _get_candidates(market_key: str, ib_client: "IBClient") -> list[str]:
    """Return raw candidate symbols for the given market.

    STK_US: union of three IB Scanner scans.
    Others:  full seed list from symbol_config (fallback).
    """
    if market_key in IB_SCANNER_MARKETS:
        from app.ibkr.ib_scanner import get_stk_us_candidates  # noqa: PLC0415

        results = get_stk_us_candidates(ib_client)
        if results:
            return [r["symbol"] for r in results]
        logger.warning(
            "IB Scanner returned no results for %s, falling back to seed list",
            market_key,
        )

    # Fallback: seed list from DB
    from app.db.database import get_approved_symbols_with_meta  # noqa: PLC0415

    meta = get_approved_symbols_with_meta()
    return [m["symbol"] for m in meta if m.get("market_key") == market_key]


# ---------------------------------------------------------------------------
# Open positions
# ---------------------------------------------------------------------------

def _get_open_position_symbols(ib_client: "IBClient") -> set[str]:
    """Return symbols that currently have open positions in IB."""
    try:
        positions = ib_client.ib.positions()
        return {pos.contract.symbol for pos in positions if pos.position != 0}
    except Exception as exc:
        logger.warning("Could not fetch open positions: %s", exc)
        return set()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def select_top_symbols(
    market_key: str,
    ib_client: "IBClient",
    ib_data_layer,
    session_date: str | None = None,
    n: int = 10,
) -> list[str]:
    """Select the top N symbols for a market session and persist them.

    Steps:
      1. Get candidates: IB Scanner (STK_US) or full seed list (others).
      2. Fetch daily RSI + volume_ratio for each via ib_data_layer.
      3. Score with simple_score() (or QuantScorer if available).
      4. Always include open positions (prepend, not counted against N limit).
      5. Save top N to active_symbols table for today.
      6. Return the final symbol list.

    Args:
        market_key:    Market identifier, e.g. "STK_US".
        ib_client:     Connected IBClient instance.
        ib_data_layer: Data layer with .get_indicators(symbol) -> dict.
        session_date:  ISO date string; defaults to today.
        n:             Maximum symbols to select (excluding forced open positions).

    Returns:
        List of selected symbol strings (open positions first, then top-N by score).
    """
    from app.db.database import upsert_active_symbols  # noqa: PLC0415

    today = session_date or date.today().isoformat()
    scorer = _get_scorer()

    # 1. Candidate symbols
    candidates = _get_candidates(market_key, ib_client)
    logger.info(
        "Pre-open %s: %d raw candidates", market_key, len(candidates)
    )

    # 2 & 3. Score each candidate
    scores: dict[str, float] = {}
    for symbol in candidates:
        try:
            indicators = ib_data_layer.get_indicators(symbol)
        except Exception as exc:
            logger.warning("Could not fetch indicators for %s: %s", symbol, exc)
            indicators = {}
        scores[symbol] = _score_symbol(scorer, symbol, indicators)

    # Sort by score descending, take top N
    ranked = sorted(scores, key=lambda s: scores[s], reverse=True)
    top_n = ranked[:n]

    # 4. Always include open positions (may push total above N)
    open_positions = _get_open_position_symbols(ib_client)
    forced = [sym for sym in open_positions if sym not in set(top_n)]
    selected = forced + top_n   # open positions prepended

    # 5. Persist
    all_scores = {sym: scores.get(sym, 0.0) for sym in selected}
    upsert_active_symbols(market_key, selected, today, scores=all_scores)

    logger.info("Pre-open %s: selected %s", market_key, selected)
    return selected
```

#### Test file: `tests/scanner/test_market_open_selector.py`

```python
"""
Tests for app/scanner/market_open_selector.py
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.scanner.market_open_selector import select_top_symbols, simple_score

TODAY = date.today().isoformat()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ib_client(position_symbols: list[str] | None = None) -> MagicMock:
    """Build a minimal fake IBClient."""
    ib_client = MagicMock()
    positions = []
    for sym in (position_symbols or []):
        pos = MagicMock()
        pos.contract.symbol = sym
        pos.position = 1
        positions.append(pos)
    ib_client.ib.positions.return_value = positions
    return ib_client


def _make_data_layer(indicators_map: dict[str, dict] | None = None) -> MagicMock:
    """Build a fake ib_data_layer."""
    data_layer = MagicMock()
    _map = indicators_map or {}

    def _get_indicators(symbol):
        return _map.get(symbol, {"rsi": 50.0, "volume_ratio": 1.0})

    data_layer.get_indicators.side_effect = _get_indicators
    return data_layer


# ---------------------------------------------------------------------------
# Tests for simple_score
# ---------------------------------------------------------------------------

class TestSimpleScore:
    def test_extreme_rsi_gives_high_score(self):
        assert simple_score(rsi=80.0, volume_ratio=3.0) > 70

    def test_neutral_rsi_low_volume_gives_low_score(self):
        assert simple_score(rsi=50.0, volume_ratio=1.0) < 20

    def test_none_inputs_are_handled(self):
        score = simple_score(rsi=None, volume_ratio=None)
        assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# Tests for select_top_symbols
# ---------------------------------------------------------------------------

class TestSelectTopSymbols:
    """All DB and IB calls are mocked so tests are hermetic."""

    def _patch_candidates(self, symbols: list[str]):
        return patch(
            "app.scanner.market_open_selector._get_candidates",
            return_value=symbols,
        )

    def _patch_upsert(self):
        return patch("app.scanner.market_open_selector.upsert_active_symbols")

    def test_select_top_symbols_respects_n_limit(self):
        """select_top_symbols returns at most n symbols (excluding open positions)."""
        candidates = [f"SYM{i}" for i in range(20)]
        ib_client = _make_ib_client()  # no open positions
        data_layer = _make_data_layer()

        with self._patch_candidates(candidates), self._patch_upsert():
            result = select_top_symbols(
                "STK_US", ib_client, data_layer, session_date=TODAY, n=5
            )

        # No open positions -> exactly 5
        assert len(result) == 5

    def test_select_top_symbols_includes_open_positions(self):
        """Open positions are always included, even if not in the top-N scored set."""
        # 20 candidates, open position is not a candidate at all
        candidates = [f"SYM{i}" for i in range(20)]
        forced_sym = "FORCED_POSITION"

        ib_client = _make_ib_client(position_symbols=[forced_sym])
        # Give candidates high scores; forced_sym not in candidates so score=0
        indicators = {sym: {"rsi": 70.0, "volume_ratio": 2.0} for sym in candidates}
        data_layer = _make_data_layer(indicators)

        with self._patch_candidates(candidates), self._patch_upsert():
            result = select_top_symbols(
                "STK_US", ib_client, data_layer, session_date=TODAY, n=5
            )

        assert forced_sym in result, (
            f"Open position {forced_sym} must always be in result; got {result}"
        )

    def test_select_top_symbols_saves_to_db(self):
        """select_top_symbols calls upsert_active_symbols with the selected symbols."""
        candidates = ["AAPL", "MSFT", "NVDA"]
        ib_client = _make_ib_client()
        data_layer = _make_data_layer()

        with self._patch_candidates(candidates), self._patch_upsert() as mock_upsert:
            result = select_top_symbols(
                "STK_US", ib_client, data_layer, session_date=TODAY, n=10
            )

        mock_upsert.assert_called_once()
        call_args = mock_upsert.call_args
        # First positional arg = market_key, second = symbols list
        assert call_args[0][0] == "STK_US"
        saved_symbols = call_args[0][1]
        for sym in result:
            assert sym in saved_symbols

    def test_select_top_symbols_returns_list(self):
        """Return type is always a list."""
        ib_client = _make_ib_client()
        data_layer = _make_data_layer()

        with self._patch_candidates([]), self._patch_upsert():
            result = select_top_symbols(
                "CRYPTO", ib_client, data_layer, session_date=TODAY, n=10
            )

        assert isinstance(result, list)
```

---

### Task B4: Pre-open scheduler jobs in `run.py` + scan filter

- [ ] Add 4 cron jobs to `run.py`
- [ ] Modify `run_scan()` in `app/scanner/preprocessor.py` to read from `active_symbols`
- [ ] Create `tests/scanner/test_run_scan_active.py` with 2 tests
- [ ] Verify: `pytest tests/scanner/test_run_scan_active.py -q` passes

#### Changes to `run.py`

Locate the block where `scheduler.add_job` is called for `"scanner"`. Add the 4 cron jobs immediately after:

```python
from app.scanner.market_open_selector import select_top_symbols

MARKET_TZ = "America/New_York"

# --- existing scanner interval job (do not remove) ---
scheduler.add_job(
    lambda: run_scan(ib_client),
    trigger="interval",
    minutes=SCAN_INTERVAL_MINUTES,
    id="scanner",
)

# --- pre-open symbol selection jobs ---

# STK_US: 09:15 ET, Mon-Fri
scheduler.add_job(
    lambda: select_top_symbols("STK_US", ib_client, data_layer),
    trigger="cron",
    hour=9,
    minute=15,
    day_of_week="mon-fri",
    timezone=MARKET_TZ,
    id="preopen_stk_us",
)

# FUT_US: 17:45 ET, Sun-Thu
scheduler.add_job(
    lambda: select_top_symbols("FUT_US", ib_client, data_layer),
    trigger="cron",
    hour=17,
    minute=45,
    day_of_week="sun-thu",
    timezone=MARKET_TZ,
    id="preopen_fut_us",
)

# CASH_FX: 16:45 ET, Sun-Thu
scheduler.add_job(
    lambda: select_top_symbols("CASH_FX", ib_client, data_layer),
    trigger="cron",
    hour=16,
    minute=45,
    day_of_week="sun-thu",
    timezone=MARKET_TZ,
    id="preopen_cash_fx",
)

# CRYPTO: 23:45 UTC, daily
scheduler.add_job(
    lambda: select_top_symbols("CRYPTO", ib_client, data_layer),
    trigger="cron",
    hour=23,
    minute=45,
    timezone="UTC",
    id="preopen_crypto",
)
```

#### Changes to `app/scanner/preprocessor.py`

Replace the body of `run_scan()` with:

```python
def run_scan(ib_client) -> None:
    """Scan active symbols for the current moment.

    Reads today's active_symbols table. Falls back to the full approved list
    if no pre-open job has run yet (e.g., first startup of the day).
    """
    from datetime import date, datetime, timezone  # noqa: PLC0415

    from app.db.database import (  # noqa: PLC0415
        get_all_active_symbols_today,
        get_approved_symbols_with_meta,
    )
    from app.scanner.liquid_hours import is_liquid_at  # noqa: PLC0415

    today = date.today().isoformat()
    now = datetime.now(timezone.utc)

    active = get_all_active_symbols_today(today)
    if not active:
        logger.info("run_scan: no active_symbols for %s -- using full approved list", today)
        active = get_approved_symbols_with_meta()
    else:
        logger.info("run_scan: %d active symbols for %s", len(active), today)

    for meta in active:
        liquid_hours = meta.get("liquid_hours")
        if liquid_hours and not is_liquid_at(now, liquid_hours):
            continue
        try:
            scan_symbol(meta["symbol"], symbol_meta=meta, ib_client=ib_client)
        except Exception as exc:
            logger.error("scan_symbol failed for %s: %s", meta["symbol"], exc)
```

#### Test file: `tests/scanner/test_run_scan_active.py`

```python
"""
Tests for the modified run_scan() in app/scanner/preprocessor.py.

Verifies that run_scan() reads from active_symbols when rows exist,
and falls back to get_approved_symbols_with_meta() when the table is empty.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import app.scanner.preprocessor as preprocessor_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_meta(symbol: str, market_key: str = "STK_US") -> dict:
    return {
        "symbol": symbol,
        "market_key": market_key,
        "liquid_hours": None,  # None = always liquid (is_liquid_at skipped)
        "sec_type": "STK",
        "exchange": "SMART",
        "currency": "USD",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRunScanActiveSymbols:
    """Patch all external I/O so run_scan is a pure unit test."""

    def _run_with_patches(
        self,
        active_rows: list[dict],
        approved_rows: list[dict],
    ) -> list[str]:
        """
        Execute run_scan() with controlled DB responses.

        Returns the list of symbols passed to scan_symbol(), in call order.
        """
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
        """When active_symbols has rows, run_scan scans those symbols."""
        active = [_make_meta("AAPL"), _make_meta("NVDA")]
        approved = [_make_meta("OLD_SYM")]  # should NOT be used

        scanned = self._run_with_patches(active_rows=active, approved_rows=approved)

        assert set(scanned) == {"AAPL", "NVDA"}
        assert "OLD_SYM" not in scanned

    def test_run_scan_falls_back_to_approved_when_no_active(self):
        """When active_symbols is empty, run_scan falls back to approved list."""
        approved = [_make_meta("MSFT"), _make_meta("GOOG")]

        scanned = self._run_with_patches(active_rows=[], approved_rows=approved)

        assert set(scanned) == {"MSFT", "GOOG"}

    def test_run_scan_skips_illiquid_symbols(self):
        """Symbols that is_liquid_at returns False for are skipped."""
        active = [_make_meta("AAPL"), _make_meta("NVDA")]
        ib_client = MagicMock()

        def _liquid(now, code):
            return code != "ILLIQUID_CODE"

        active[1]["liquid_hours"] = "ILLIQUID_CODE"  # NVDA marked illiquid

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
```

---

## Acceptance criteria

- `pytest tests/ibkr/test_ib_scanner.py tests/db/test_active_symbols.py tests/scanner/test_market_open_selector.py tests/scanner/test_run_scan_active.py -q` passes with no regressions
- Full test suite (`pytest -q`) passes
- Logs show `"Pre-open STK_US: selected [NVDA, AAPL, ...]"` before 09:30 ET
- `run_scan()` logs include symbols from all 4 markets when their sessions overlap
- IB Scanner failure for FUT/FX/CRYPTO markets degrades gracefully to seed list
- Open positions are never excluded from the active set regardless of their score
