# Multi-Market Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded STK_US-only architecture with a contract-type-aware foundation that supports STK, FUT, CASH (Forex), and CRYPTO through a single ContractFactory abstraction.

**Architecture:** Three layers: (1) DB schema stores sec_type/exchange/currency per symbol, (2) ContractFactory translates that metadata into ib_insync Contract objects, (3) IBDataLayer/IBKRClient/Scanner consume ContractFactory instead of hardcoding Stock(). All changes are backward compatible — existing STK_US symbols continue working unchanged.

**Tech Stack:** Python 3.13, ib_insync, FastAPI, SQLite (WAL), pytest, APScheduler

---

## Pre-flight checklist

- [ ] Confirm working directory: `cd /home/frankpach/ibkr-bot`
- [ ] Confirm virtualenv active: `source .venv/bin/activate && python --version` → `Python 3.13.x`
- [ ] Confirm baseline tests pass: `pytest -q` → `190 passed` (or current baseline) — record the count before starting
- [ ] Confirm git working tree clean: `git status` → "nothing to commit, working tree clean"
- [ ] Create feature branch: `git checkout -b feature/multi-market-foundation`
- [ ] Verify `app/db/database.py` exposes `get_connection()` and that the SQLite file path is resolvable from tests (the tests must use a temp DB; check existing test fixtures in `tests/conftest.py` before writing new ones)

---

## Task 1 — DB schema migration + symbol universe seed

**Goal:** Add `sec_type`, `exchange`, `currency`, `liquid_hours`, `market_key` columns to `symbol_config` and seed the 40-symbol universe (10 STK + 10 FUT + 10 CASH + 10 CRYPTO).

### Files to create/modify

- Modify: `app/db/database.py` (add migration helper + seeding routine)
- Modify: `app/db/migrations.py` (if it exists — otherwise add the migration code into `app/db/database.py` `init_db()`)
- Create: `tests/db/test_symbol_config_migration.py`

### Step 1.1 — Write failing test first

- [ ] Create `tests/db/test_symbol_config_migration.py`:

```python
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
```

- [ ] Run: `pytest tests/db/test_symbol_config_migration.py -q` → **expect failure** (columns don't exist yet, or seed count mismatches)

### Step 1.2 — Implement migration in `app/db/database.py`

- [ ] Add the symbol universe constants at the top of `app/db/database.py` (after imports):

```python
# ----- Multi-market symbol universe (Plan A seed) ----------------------------
_STK_US_SEED = [
    ("AAPL", "STK", "SMART", "USD", "STK_US"),
    ("MSFT", "STK", "SMART", "USD", "STK_US"),
    ("SPY",  "STK", "SMART", "USD", "STK_US"),
    ("QQQ",  "STK", "SMART", "USD", "STK_US"),
    ("NVDA", "STK", "SMART", "USD", "STK_US"),
    ("TSLA", "STK", "SMART", "USD", "STK_US"),
    ("AMZN", "STK", "SMART", "USD", "STK_US"),
    ("GOOGL","STK", "SMART", "USD", "STK_US"),
    ("META", "STK", "SMART", "USD", "STK_US"),
    ("JPM",  "STK", "SMART", "USD", "STK_US"),
]

_FUT_US_SEED = [
    ("ES",  "FUT", "CME",   "USD", "FUT_US"),
    ("NQ",  "FUT", "CME",   "USD", "FUT_US"),
    ("YM",  "FUT", "CBOT",  "USD", "FUT_US"),
    ("RTY", "FUT", "CME",   "USD", "FUT_US"),
    ("CL",  "FUT", "NYMEX", "USD", "FUT_US"),
    ("GC",  "FUT", "COMEX", "USD", "FUT_US"),
    ("SI",  "FUT", "COMEX", "USD", "FUT_US"),
    ("NG",  "FUT", "NYMEX", "USD", "FUT_US"),
    ("ZB",  "FUT", "CBOT",  "USD", "FUT_US"),
    ("ZN",  "FUT", "CBOT",  "USD", "FUT_US"),
]

_CASH_FX_SEED = [
    ("EURUSD", "CASH", "IDEALPRO", "USD", "CASH_FX"),
    ("GBPUSD", "CASH", "IDEALPRO", "USD", "CASH_FX"),
    ("USDJPY", "CASH", "IDEALPRO", "JPY", "CASH_FX"),
    ("AUDUSD", "CASH", "IDEALPRO", "USD", "CASH_FX"),
    ("USDCAD", "CASH", "IDEALPRO", "CAD", "CASH_FX"),
    ("USDCHF", "CASH", "IDEALPRO", "CHF", "CASH_FX"),
    ("NZDUSD", "CASH", "IDEALPRO", "USD", "CASH_FX"),
    ("EURJPY", "CASH", "IDEALPRO", "JPY", "CASH_FX"),
    ("GBPJPY", "CASH", "IDEALPRO", "JPY", "CASH_FX"),
    ("EURGBP", "CASH", "IDEALPRO", "GBP", "CASH_FX"),
]

_CRYPTO_SEED = [
    ("BTC",  "CRYPTO", "PAXOS", "USD", "CRYPTO"),
    ("ETH",  "CRYPTO", "PAXOS", "USD", "CRYPTO"),
    ("LTC",  "CRYPTO", "PAXOS", "USD", "CRYPTO"),
    ("SOL",  "CRYPTO", "PAXOS", "USD", "CRYPTO"),
    ("ADA",  "CRYPTO", "PAXOS", "USD", "CRYPTO"),
    ("AVAX", "CRYPTO", "PAXOS", "USD", "CRYPTO"),
    ("DOT",  "CRYPTO", "PAXOS", "USD", "CRYPTO"),
    ("LINK", "CRYPTO", "PAXOS", "USD", "CRYPTO"),
    ("XRP",  "CRYPTO", "PAXOS", "USD", "CRYPTO"),
    ("UNI",  "CRYPTO", "PAXOS", "USD", "CRYPTO"),
]

_FULL_SEED = _STK_US_SEED + _FUT_US_SEED + _CASH_FX_SEED + _CRYPTO_SEED


def _add_column_if_missing(conn, table: str, column: str, ddl: str) -> None:
    """SQLite has no IF NOT EXISTS for ADD COLUMN — try/except instead."""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    except sqlite3.OperationalError as exc:
        if "duplicate column name" not in str(exc).lower():
            raise


def _migrate_symbol_config(conn) -> None:
    _add_column_if_missing(conn, "symbol_config", "sec_type",     "TEXT DEFAULT 'STK'")
    _add_column_if_missing(conn, "symbol_config", "exchange",     "TEXT DEFAULT 'SMART'")
    _add_column_if_missing(conn, "symbol_config", "currency",     "TEXT DEFAULT 'USD'")
    _add_column_if_missing(conn, "symbol_config", "liquid_hours", "TEXT")
    _add_column_if_missing(conn, "symbol_config", "market_key",   "TEXT DEFAULT 'STK_US'")


def _seed_symbol_universe(conn) -> None:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    for sym, sec_type, exch, ccy, market_key in _FULL_SEED:
        conn.execute(
            """
            INSERT INTO symbol_config
                (symbol, extra_indicators, approved, proposed_by, created_at,
                 sec_type, exchange, currency, market_key)
            VALUES (?, '[]', 1, 'seed', ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                sec_type   = excluded.sec_type,
                exchange   = excluded.exchange,
                currency   = excluded.currency,
                market_key = excluded.market_key,
                approved   = 1
            """,
            (sym, now, sec_type, exch, ccy, market_key),
        )
    conn.commit()
```

- [ ] Wire the migration + seed into `init_db()`. After the `CREATE TABLE IF NOT EXISTS symbol_config (...)` statement, call:

```python
_migrate_symbol_config(conn)
_seed_symbol_universe(conn)
```

- [ ] Make sure `init_db()` opens a single connection (or uses `get_connection()`), commits, and closes. If the existing `init_db()` already does multi-statement setup, append the two calls just before the final commit/close.

### Step 1.3 — Verify test passes

- [ ] Run: `pytest tests/db/test_symbol_config_migration.py -q`
- [ ] Expected output: `5 passed in <1s`
- [ ] Run full suite: `pytest -q` → expect 190 + 5 = **195 passed** (no regressions)

### Step 1.4 — Migrate the live DB on Pi

- [ ] On `aiutox-pi`, with the bot **stopped**: `python -c "from app.db.database import init_db; init_db()"`
- [ ] Verify: `sqlite3 data/ibkr_bot.db "SELECT sec_type, COUNT(*) FROM symbol_config GROUP BY sec_type;"`
- [ ] Expected: `CASH|10`, `CRYPTO|10`, `FUT|10`, `STK|10`

### Step 1.5 — Commit

- [ ] `git add app/db/database.py tests/db/test_symbol_config_migration.py`
- [ ] `git commit -m "feat(db): add multi-market columns and seed 40-symbol universe"`

---

## Task 2 — `ContractFactory` module

**Goal:** Single source of truth that turns `(symbol, sec_type, exchange, currency)` into the right `ib_insync` Contract.

### Files to create/modify

- Create: `app/ibkr/contract_factory.py`
- Create: `tests/ibkr/test_contract_factory.py`

### Step 2.1 — Write failing test first

- [ ] Create `tests/ibkr/test_contract_factory.py`:

```python
import pytest
from ib_insync import Stock, Future, Forex, Contract

from app.ibkr.contract_factory import (
    build_contract,
    get_what_to_show,
    get_use_rth,
    parse_forex_pair,
    UnsupportedSecTypeError,
    InvalidForexPairError,
)


# ---- build_contract ---------------------------------------------------------

def test_build_stk_returns_stock():
    c = build_contract("AAPL", "STK", "SMART", "USD")
    assert isinstance(c, Stock)
    assert c.symbol == "AAPL"
    assert c.exchange == "SMART"
    assert c.currency == "USD"


def test_build_stk_uppercases_symbol():
    c = build_contract("aapl", "STK", "SMART", "USD")
    assert c.symbol == "AAPL"


def test_build_fut_returns_future_without_expiry():
    c = build_contract("ES", "FUT", "CME", "USD")
    assert isinstance(c, Future)
    assert c.symbol == "ES"
    assert c.exchange == "CME"
    assert c.currency == "USD"
    # Front-month is resolved later via reqContractDetails
    assert c.lastTradeDateOrContractMonth in ("", None)


def test_build_cash_returns_forex_with_pair():
    c = build_contract("EURUSD", "CASH", "IDEALPRO", "USD")
    assert isinstance(c, Forex)
    assert c.symbol == "EUR"      # base
    assert c.currency == "USD"    # quote
    assert c.exchange == "IDEALPRO"


def test_build_cash_jpy_quote():
    c = build_contract("USDJPY", "CASH", "IDEALPRO", "JPY")
    assert c.symbol == "USD"
    assert c.currency == "JPY"


def test_build_crypto_returns_generic_contract():
    c = build_contract("BTC", "CRYPTO", "PAXOS", "USD")
    assert isinstance(c, Contract)
    assert c.secType == "CRYPTO"
    assert c.symbol == "BTC"
    assert c.exchange == "PAXOS"
    assert c.currency == "USD"


def test_build_unsupported_sec_type_raises():
    with pytest.raises(UnsupportedSecTypeError):
        build_contract("XYZ", "BOND", "SMART", "USD")


# ---- parse_forex_pair -------------------------------------------------------

@pytest.mark.parametrize("pair,base,quote", [
    ("EURUSD", "EUR", "USD"),
    ("usdjpy", "USD", "JPY"),
    ("GBPJPY", "GBP", "JPY"),
])
def test_parse_forex_pair_ok(pair, base, quote):
    assert parse_forex_pair(pair) == (base, quote)


@pytest.mark.parametrize("bad", ["EUR", "EURUSDX", "", "12USD"])
def test_parse_forex_pair_invalid(bad):
    with pytest.raises(InvalidForexPairError):
        parse_forex_pair(bad)


# ---- get_what_to_show -------------------------------------------------------

@pytest.mark.parametrize("sec_type,expected", [
    ("STK", "TRADES"),
    ("FUT", "TRADES"),
    ("CRYPTO", "TRADES"),
    ("CASH", "MIDPOINT"),
    ("OPT", "TRADES"),
])
def test_what_to_show(sec_type, expected):
    assert get_what_to_show(sec_type) == expected


# ---- get_use_rth ------------------------------------------------------------

@pytest.mark.parametrize("sec_type,expected", [
    ("STK", True),
    ("OPT", True),
    ("FUT", False),
    ("CASH", False),
    ("CRYPTO", False),
])
def test_use_rth(sec_type, expected):
    assert get_use_rth(sec_type) is expected
```

- [ ] Run: `pytest tests/ibkr/test_contract_factory.py -q` → **expect ImportError / module not found**

### Step 2.2 — Implement `app/ibkr/contract_factory.py`

```python
"""Contract factory: turns (symbol, sec_type, exchange, currency) tuples into
ib_insync Contract objects. Single source of truth for multi-market support.
"""
from __future__ import annotations

import re
from ib_insync import Contract, Forex, Future, Option, Stock


class ContractFactoryError(Exception):
    """Base class for contract-factory errors."""


class UnsupportedSecTypeError(ContractFactoryError):
    """Raised when sec_type is not one of STK / OPT / FUT / CASH / CRYPTO."""


class InvalidForexPairError(ContractFactoryError):
    """Raised when a CASH symbol is not a valid 6-letter currency pair."""


_FOREX_RE = re.compile(r"^[A-Z]{3}[A-Z]{3}$")


def parse_forex_pair(pair: str) -> tuple[str, str]:
    """Split 'EURUSD' → ('EUR', 'USD'). Case-insensitive. Raises on invalid."""
    if not isinstance(pair, str):
        raise InvalidForexPairError(f"Forex pair must be str, got {type(pair)!r}")
    p = pair.upper()
    if not _FOREX_RE.match(p):
        raise InvalidForexPairError(
            f"Invalid forex pair {pair!r}: expected 6 letters like 'EURUSD'"
        )
    return p[:3], p[3:]


def build_contract(
    symbol: str,
    sec_type: str,
    exchange: str,
    currency: str,
) -> Contract:
    """Build the ib_insync Contract for the given metadata.

    For FUT, the returned contract has *no* `lastTradeDateOrContractMonth` set;
    the caller is responsible for resolving the front-month via
    `IB.reqContractDetailsAsync(...)` and using the qualified contract.
    """
    sym = symbol.upper().strip()
    sec = sec_type.upper().strip()

    if sec == "STK":
        return Stock(sym, exchange or "SMART", currency or "USD")

    if sec == "OPT":
        # Generic OPT placeholder — Plan A does not expand options;
        # future plans will add strike/right/expiry resolution.
        return Option(sym, "", 0.0, "C", exchange or "SMART", currency=currency or "USD")

    if sec == "FUT":
        # No expiry: resolved at runtime via reqContractDetails.
        return Future(symbol=sym, exchange=exchange or "CME", currency=currency or "USD")

    if sec == "CASH":
        base, quote = parse_forex_pair(sym)
        c = Forex(pair=f"{base}{quote}")
        # ib_insync Forex() ignores explicit exchange in some versions; force it.
        c.exchange = exchange or "IDEALPRO"
        return c

    if sec == "CRYPTO":
        return Contract(
            secType="CRYPTO",
            symbol=sym,
            exchange=exchange or "PAXOS",
            currency=currency or "USD",
        )

    raise UnsupportedSecTypeError(
        f"sec_type={sec_type!r} is not supported. "
        "Expected one of: STK, OPT, FUT, CASH, CRYPTO"
    )


def get_what_to_show(sec_type: str) -> str:
    """Historical-data `whatToShow` value per asset class.

    Forex has no trade prints — IB requires MIDPOINT (or BID/ASK) for CASH.
    Everything else uses TRADES.
    """
    return "MIDPOINT" if sec_type.upper() == "CASH" else "TRADES"


def get_use_rth(sec_type: str) -> bool:
    """`useRTH=True` only for equities/options. FUT/CASH/CRYPTO trade ~24h."""
    return sec_type.upper() in {"STK", "OPT"}


__all__ = [
    "build_contract",
    "get_what_to_show",
    "get_use_rth",
    "parse_forex_pair",
    "ContractFactoryError",
    "UnsupportedSecTypeError",
    "InvalidForexPairError",
]
```

- [ ] If `tests/ibkr/__init__.py` does not exist, create it as empty.

### Step 2.3 — Verify test passes

- [ ] Run: `pytest tests/ibkr/test_contract_factory.py -q`
- [ ] Expected: `~17 passed`
- [ ] Run full suite: `pytest -q` → no regressions

### Step 2.4 — Commit

- [ ] `git add app/ibkr/contract_factory.py tests/ibkr/test_contract_factory.py tests/ibkr/__init__.py`
- [ ] `git commit -m "feat(ibkr): add ContractFactory with STK/FUT/CASH/CRYPTO support"`

---

## Task 3 — `IBDataLayer.get_ohlcv` parameterized per asset class

**Goal:** `get_ohlcv` accepts `sec_type/exchange/currency`, builds the right contract via the factory, picks the right `whatToShow` and `useRTH`. For FUT, resolves front-month via `reqContractDetailsAsync` before calling `reqHistoricalData`.

### Files to create/modify

- Modify: `app/analysis/data.py`
- Create/extend: `tests/analysis/test_data_multi_market.py`

### Step 3.1 — Write failing test first

- [ ] Create `tests/analysis/test_data_multi_market.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ib_insync import Stock, Forex, Future, Contract

from app.analysis.data import IBDataLayer


class _FakeBar:
    def __init__(self):
        self.date = "2026-05-08"
        self.open = 1.0
        self.high = 1.1
        self.low = 0.9
        self.close = 1.05
        self.volume = 100


@pytest.fixture
def fake_client():
    client = MagicMock()
    client.ib = MagicMock()
    client.ib.reqHistoricalData = MagicMock(return_value=[_FakeBar() for _ in range(5)])
    # async-style for futures resolution
    fake_details = MagicMock()
    fake_details.contract = Future(symbol="ES", exchange="CME", currency="USD")
    fake_details.contract.lastTradeDateOrContractMonth = "20260619"
    client.ib.reqContractDetailsAsync = AsyncMock(return_value=[fake_details])
    return client


def test_stk_uses_stock_trades_rth_true(fake_client):
    layer = IBDataLayer(fake_client)
    layer.get_ohlcv("AAPL", "1 D", "5 mins", context={}, sec_type="STK",
                    exchange="SMART", currency="USD")
    call = fake_client.ib.reqHistoricalData.call_args
    contract = call.args[0] if call.args else call.kwargs["contract"]
    assert isinstance(contract, Stock)
    kwargs = call.kwargs
    assert kwargs["whatToShow"] == "TRADES"
    assert kwargs["useRTH"] is True


def test_cash_uses_forex_midpoint_rth_false(fake_client):
    layer = IBDataLayer(fake_client)
    layer.get_ohlcv("EURUSD", "1 D", "5 mins", context={}, sec_type="CASH",
                    exchange="IDEALPRO", currency="USD")
    call = fake_client.ib.reqHistoricalData.call_args
    contract = call.args[0] if call.args else call.kwargs["contract"]
    assert isinstance(contract, Forex)
    assert call.kwargs["whatToShow"] == "MIDPOINT"
    assert call.kwargs["useRTH"] is False


def test_crypto_uses_contract_trades_rth_false(fake_client):
    layer = IBDataLayer(fake_client)
    layer.get_ohlcv("BTC", "1 D", "5 mins", context={}, sec_type="CRYPTO",
                    exchange="PAXOS", currency="USD")
    call = fake_client.ib.reqHistoricalData.call_args
    contract = call.args[0] if call.args else call.kwargs["contract"]
    assert contract.secType == "CRYPTO"
    assert call.kwargs["whatToShow"] == "TRADES"
    assert call.kwargs["useRTH"] is False


def test_fut_resolves_front_month(fake_client):
    layer = IBDataLayer(fake_client)
    layer.get_ohlcv("ES", "1 D", "5 mins", context={}, sec_type="FUT",
                    exchange="CME", currency="USD")
    # reqContractDetailsAsync was called to resolve expiry
    fake_client.ib.reqContractDetailsAsync.assert_called_once()
    call = fake_client.ib.reqHistoricalData.call_args
    contract = call.args[0] if call.args else call.kwargs["contract"]
    assert isinstance(contract, Future)
    assert contract.lastTradeDateOrContractMonth == "20260619"
    assert call.kwargs["useRTH"] is False


def test_default_sec_type_is_stk_backward_compatible(fake_client):
    layer = IBDataLayer(fake_client)
    layer.get_ohlcv("AAPL", "1 D", "5 mins", context={})
    call = fake_client.ib.reqHistoricalData.call_args
    contract = call.args[0] if call.args else call.kwargs["contract"]
    assert isinstance(contract, Stock)
    assert call.kwargs["whatToShow"] == "TRADES"
    assert call.kwargs["useRTH"] is True
```

- [ ] Run: `pytest tests/analysis/test_data_multi_market.py -q` → **expect failures** (signature doesn't accept new params).

### Step 3.2 — Implement updated `get_ohlcv`

- [ ] In `app/analysis/data.py`, replace the existing `get_ohlcv` with:

```python
import asyncio
from ib_insync import Future

from app.ibkr.contract_factory import (
    build_contract,
    get_what_to_show,
    get_use_rth,
)


def get_ohlcv(
    self,
    symbol: str,
    duration: str,
    bar_size: str,
    context: dict,
    sec_type: str = "STK",
    exchange: str = "SMART",
    currency: str = "USD",
):
    """Fetch historical OHLCV bars. Multi-asset aware.

    For FUT, resolves the front-month expiry via reqContractDetailsAsync
    before calling reqHistoricalData.
    """
    contract = build_contract(symbol, sec_type, exchange, currency)
    what = get_what_to_show(sec_type)
    use_rth = get_use_rth(sec_type)

    if sec_type.upper() == "FUT":
        contract = self._resolve_future_front_month(contract)

    bars = self._client.ib.reqHistoricalData(
        contract,
        endDateTime="",
        durationStr=duration,
        barSizeSetting=bar_size,
        whatToShow=what,
        useRTH=use_rth,
        formatDate=1,
    )
    return self._bars_to_dataframe(bars, context=context)


def _resolve_future_front_month(self, contract: Future) -> Future:
    """Pick the nearest-expiry contract for a generic Future."""
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # Already inside an async context (e.g. APScheduler async job)
        details = asyncio.run_coroutine_threadsafe(
            self._client.ib.reqContractDetailsAsync(contract), loop
        ).result(timeout=10)
    else:
        details = loop.run_until_complete(
            self._client.ib.reqContractDetailsAsync(contract)
        )
    if not details:
        raise RuntimeError(f"No contract details for future {contract.symbol}")
    # Sort by expiry ascending and take the front month
    details_sorted = sorted(
        details,
        key=lambda d: d.contract.lastTradeDateOrContractMonth or "99999999",
    )
    return details_sorted[0].contract
```

- [ ] Keep `_bars_to_dataframe` and any other helpers untouched.

### Step 3.3 — Verify

- [ ] Run: `pytest tests/analysis/test_data_multi_market.py -q` → **expect 5 passed**
- [ ] Run full suite: `pytest -q` → 190 + 5 (Task 1) + 17 (Task 2) + 5 = **217 passed**

### Step 3.4 — Commit

- [ ] `git add app/analysis/data.py tests/analysis/test_data_multi_market.py`
- [ ] `git commit -m "feat(data): get_ohlcv accepts sec_type/exchange/currency and resolves FUT front-month"`

---

## Task 4 — `IBKRClient.get_stock_price` and `place_order` use ContractFactory

**Goal:** `get_stock_price()` (renamed conceptually but kept for backward-compat) and `place_order()` accept `sec_type/exchange/currency` and route through `build_contract()`.

### Files to create/modify

- Modify: `app/ibkr/client.py`
- Create/extend: `tests/ibkr/test_client_multi_market.py`

### Step 4.1 — Write failing test first

- [ ] Create `tests/ibkr/test_client_multi_market.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ib_insync import Stock, Forex, Contract

from app.ibkr.client import IBKRClient


@pytest.fixture
def client():
    c = IBKRClient.__new__(IBKRClient)  # bypass real connect
    c.ib = MagicMock()
    c._connected = True
    return c


# ---- get_stock_price --------------------------------------------------------

def test_get_price_stk_default(client):
    ticker = MagicMock()
    ticker.marketPrice.return_value = 192.5
    client.ib.reqMktData = MagicMock(return_value=ticker)
    client.ib.sleep = MagicMock()

    price = client.get_stock_price("AAPL")
    contract_used = client.ib.reqMktData.call_args.args[0]
    assert isinstance(contract_used, Stock)
    assert price == 192.5


def test_get_price_cash_uses_forex(client):
    ticker = MagicMock()
    ticker.marketPrice.return_value = 1.0834
    client.ib.reqMktData = MagicMock(return_value=ticker)
    client.ib.sleep = MagicMock()

    price = client.get_stock_price("EURUSD", sec_type="CASH",
                                   exchange="IDEALPRO", currency="USD")
    contract_used = client.ib.reqMktData.call_args.args[0]
    assert isinstance(contract_used, Forex)
    assert price == 1.0834


def test_get_price_crypto_uses_paxos(client):
    ticker = MagicMock()
    ticker.marketPrice.return_value = 67000.0
    client.ib.reqMktData = MagicMock(return_value=ticker)
    client.ib.sleep = MagicMock()

    price = client.get_stock_price("BTC", sec_type="CRYPTO",
                                   exchange="PAXOS", currency="USD")
    contract_used = client.ib.reqMktData.call_args.args[0]
    assert contract_used.secType == "CRYPTO"
    assert contract_used.exchange == "PAXOS"


# ---- place_order ------------------------------------------------------------

def test_place_order_stk_default(client):
    trade = MagicMock()
    trade.order.orderId = 42
    client.ib.placeOrder = MagicMock(return_value=trade)

    result = client.place_order("AAPL", "BUY", 1, "MKT")
    contract = client.ib.placeOrder.call_args.args[0]
    assert isinstance(contract, Stock)
    assert result["order_id"] == 42


def test_place_order_crypto(client):
    trade = MagicMock()
    trade.order.orderId = 99
    client.ib.placeOrder = MagicMock(return_value=trade)

    client.place_order("BTC", "BUY", 0.01, "MKT",
                       sec_type="CRYPTO", exchange="PAXOS", currency="USD")
    contract = client.ib.placeOrder.call_args.args[0]
    assert contract.secType == "CRYPTO"
    assert contract.symbol == "BTC"


def test_place_order_cash_uses_forex(client):
    trade = MagicMock()
    trade.order.orderId = 7
    client.ib.placeOrder = MagicMock(return_value=trade)

    client.place_order("EURUSD", "BUY", 25_000, "MKT",
                       sec_type="CASH", exchange="IDEALPRO", currency="USD")
    contract = client.ib.placeOrder.call_args.args[0]
    assert isinstance(contract, Forex)
```

- [ ] Run: `pytest tests/ibkr/test_client_multi_market.py -q` → **expect failures**

### Step 4.2 — Update `app/ibkr/client.py`

- [ ] At the top of `app/ibkr/client.py`:

```python
from app.ibkr.contract_factory import build_contract
```

- [ ] Replace `get_stock_price` (or whatever its current name is — keep the same public name for backward-compat):

```python
def get_stock_price(
    self,
    symbol: str,
    sec_type: str = "STK",
    exchange: str = "SMART",
    currency: str = "USD",
) -> float | None:
    """Return the current market price for any supported sec_type.

    Name retained for backward-compatibility; works for STK/FUT/CASH/CRYPTO.
    """
    contract = build_contract(symbol, sec_type, exchange, currency)
    ticker = self.ib.reqMktData(contract, "", False, False)
    self.ib.sleep(1.0)
    price = ticker.marketPrice()
    if price is None or price != price:  # NaN check
        return None
    return float(price)
```

- [ ] Replace the body of `_place_order_async` (or `place_order`) — keep the existing method signature pattern, add the new kwargs:

```python
def place_order(
    self,
    symbol: str,
    action: str,
    quantity: float,
    order_type: str,
    sec_type: str = "STK",
    exchange: str = "SMART",
    currency: str = "USD",
    limit_price: float | None = None,
) -> dict:
    from ib_insync import Order
    contract = build_contract(symbol, sec_type, exchange, currency)
    order = Order()
    order.action = action.upper()
    order.totalQuantity = quantity
    order.orderType = order_type.upper()
    if limit_price is not None and order.orderType in {"LMT", "STP LMT"}:
        order.lmtPrice = float(limit_price)
    trade = self.ib.placeOrder(contract, order)
    return {"order_id": trade.order.orderId, "symbol": symbol,
            "sec_type": sec_type, "status": "submitted"}
```

- [ ] If the existing `place_order` is the async wrapper, modify whichever inner method actually calls `self.ib.placeOrder`. The key change: replace `Stock(symbol.upper(), "SMART", "USD")` with `build_contract(symbol, sec_type, exchange, currency)`.

### Step 4.3 — Verify

- [ ] `pytest tests/ibkr/test_client_multi_market.py -q` → **expect 6 passed**
- [ ] `pytest -q` → expect previous total + 6 = **223 passed**

### Step 4.4 — Commit

- [ ] `git add app/ibkr/client.py tests/ibkr/test_client_multi_market.py`
- [ ] `git commit -m "feat(ibkr): client.get_stock_price and place_order route through ContractFactory"`

---

## Task 5 — Scanner consumes symbol metadata

**Goal:** `scan_symbol` accepts a `symbol_meta` dict (`sec_type`, `exchange`, `currency`, `liquid_hours`); uses `build_contract` and replaces `_is_market_hours()` with `is_liquid_at(now, liquid_hours)`.

### Files to create/modify

- Modify: `app/scanner/preprocessor.py`
- Create: `app/scanner/liquid_hours.py` (new helper)
- Modify: `app/db/database.py` (add `get_approved_symbols_with_meta`)
- Create/extend: `tests/scanner/test_preprocessor_multi_market.py`
- Create/extend: `tests/scanner/test_liquid_hours.py`

### Step 5.1 — Write failing tests first

- [ ] `tests/scanner/test_liquid_hours.py`:

```python
from datetime import datetime, timezone

import pytest

from app.scanner.liquid_hours import is_liquid_at


def _utc(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


def test_none_means_24x7():
    # No liquid_hours configured → assume 24/7 (CRYPTO behaviour)
    assert is_liquid_at(_utc(2026, 5, 8, 3, 0), None) is True


def test_24x7_string():
    assert is_liquid_at(_utc(2026, 5, 8, 3, 0), "24x7") is True


def test_us_rth_session_open():
    # 14:30 UTC = 09:30 ET (RTH open)
    assert is_liquid_at(_utc(2026, 5, 8, 14, 30), "US_RTH") is True


def test_us_rth_after_close():
    # 22:00 UTC = 17:00 ET (after 16:00 close)
    assert is_liquid_at(_utc(2026, 5, 8, 22, 0), "US_RTH") is False


def test_forex_closed_weekend():
    # Saturday → forex closed
    assert is_liquid_at(_utc(2026, 5, 9, 12, 0), "FX") is False


def test_forex_open_tuesday():
    assert is_liquid_at(_utc(2026, 5, 12, 12, 0), "FX") is True
```

- [ ] `tests/scanner/test_preprocessor_multi_market.py`:

```python
from unittest.mock import MagicMock, patch

import pytest


def test_run_scan_uses_meta_from_db():
    from app.scanner import preprocessor

    fake_meta = [
        {"symbol": "AAPL", "sec_type": "STK", "exchange": "SMART",
         "currency": "USD", "liquid_hours": "US_RTH"},
        {"symbol": "BTC", "sec_type": "CRYPTO", "exchange": "PAXOS",
         "currency": "USD", "liquid_hours": "24x7"},
    ]

    with patch.object(preprocessor, "get_approved_symbols_with_meta",
                      return_value=fake_meta) as m_meta, \
         patch.object(preprocessor, "scan_symbol") as m_scan:
        preprocessor.run_scan()
        m_meta.assert_called_once()
        # scan_symbol called once per symbol, with meta forwarded
        assert m_scan.call_count == 2
        passed_symbols = [call.args[0] for call in m_scan.call_args_list]
        assert "AAPL" in passed_symbols and "BTC" in passed_symbols


def test_scan_symbol_skips_when_not_liquid():
    from app.scanner import preprocessor

    meta = {"symbol": "AAPL", "sec_type": "STK", "exchange": "SMART",
            "currency": "USD", "liquid_hours": "US_RTH"}

    with patch.object(preprocessor, "is_liquid_at", return_value=False) as m_liq, \
         patch.object(preprocessor, "_run_indicators") as m_ind:
        result = preprocessor.scan_symbol("AAPL", symbol_meta=meta)
        m_ind.assert_not_called()
        assert result["skipped"] is True


def test_scan_symbol_runs_when_liquid():
    from app.scanner import preprocessor

    meta = {"symbol": "BTC", "sec_type": "CRYPTO", "exchange": "PAXOS",
            "currency": "USD", "liquid_hours": "24x7"}

    with patch.object(preprocessor, "is_liquid_at", return_value=True), \
         patch.object(preprocessor, "_run_indicators",
                      return_value={"rsi": 50}) as m_ind:
        result = preprocessor.scan_symbol("BTC", symbol_meta=meta)
        m_ind.assert_called_once()
        assert result["skipped"] is False
```

- [ ] Run both → expect failures (modules / functions don't exist).

### Step 5.2 — Create `app/scanner/liquid_hours.py`

```python
"""Schedule/window evaluator for trading sessions.

Supported `liquid_hours` codes:
- None or "24x7"  → always liquid (CRYPTO).
- "US_RTH"        → 09:30–16:00 America/New_York, Mon–Fri.
- "US_EXT"        → 04:00–20:00 America/New_York, Mon–Fri (pre/post market).
- "FX"            → Sun 22:00 UTC – Fri 22:00 UTC (continuous).
- "GLOBEX"        → Sun 23:00 UTC – Fri 22:00 UTC, daily 60-min halt 22–23 UTC.
"""
from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

_NY = ZoneInfo("America/New_York")


def is_liquid_at(now: datetime, liquid_hours: str | None) -> bool:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    code = (liquid_hours or "24x7").upper()

    if code == "24X7":
        return True

    if code in {"US_RTH", "US_EXT"}:
        ny = now.astimezone(_NY)
        if ny.weekday() >= 5:  # Sat/Sun
            return False
        t = ny.time()
        if code == "US_RTH":
            return time(9, 30) <= t < time(16, 0)
        return time(4, 0) <= t < time(20, 0)

    if code == "FX":
        utc = now.astimezone(timezone.utc)
        wd = utc.weekday()  # Mon=0 … Sun=6
        # Closed Sat all day; closed Fri >= 22:00; closed Sun < 22:00
        if wd == 5:
            return False
        if wd == 4 and utc.time() >= time(22, 0):
            return False
        if wd == 6 and utc.time() < time(22, 0):
            return False
        return True

    if code == "GLOBEX":
        utc = now.astimezone(timezone.utc)
        wd = utc.weekday()
        if wd == 5:
            return False
        if wd == 4 and utc.time() >= time(22, 0):
            return False
        if wd == 6 and utc.time() < time(23, 0):
            return False
        # Daily 22:00–23:00 UTC halt
        if time(22, 0) <= utc.time() < time(23, 0):
            return False
        return True

    # Unknown code → conservative: closed
    return False
```

### Step 5.3 — Add `get_approved_symbols_with_meta()` to `app/db/database.py`

```python
def get_approved_symbols_with_meta() -> list[dict]:
    """Return approved symbols with full multi-market metadata."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT symbol, sec_type, exchange, currency, liquid_hours, market_key "
            "FROM symbol_config WHERE approved=1"
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "symbol": r["symbol"],
            "sec_type": r["sec_type"] or "STK",
            "exchange": r["exchange"] or "SMART",
            "currency": r["currency"] or "USD",
            "liquid_hours": r["liquid_hours"],
            "market_key": r["market_key"] or "STK_US",
        }
        for r in rows
    ]
```

### Step 5.4 — Update `app/scanner/preprocessor.py`

- [ ] Imports:

```python
from datetime import datetime, timezone

from app.db.database import get_approved_symbols_with_meta
from app.ibkr.contract_factory import build_contract
from app.scanner.liquid_hours import is_liquid_at
```

- [ ] Replace `scan_symbol` signature and the `_is_market_hours()` check:

```python
def scan_symbol(symbol: str, symbol_meta: dict | None = None) -> dict:
    meta = symbol_meta or {
        "symbol": symbol, "sec_type": "STK", "exchange": "SMART",
        "currency": "USD", "liquid_hours": "US_RTH",
    }

    now = datetime.now(timezone.utc)
    if not is_liquid_at(now, meta.get("liquid_hours")):
        return {"symbol": symbol, "skipped": True, "reason": "not_liquid"}

    contract = build_contract(
        meta["symbol"], meta["sec_type"], meta["exchange"], meta["currency"]
    )
    indicators = _run_indicators(symbol, contract=contract, meta=meta)
    return {"symbol": symbol, "skipped": False, "indicators": indicators}
```

- [ ] Replace `run_scan()` body:

```python
def run_scan() -> list[dict]:
    results = []
    for meta in get_approved_symbols_with_meta():
        results.append(scan_symbol(meta["symbol"], symbol_meta=meta))
    return results
```

- [ ] If `_run_indicators` exists with a different signature, adapt it to accept `contract=` and `meta=` kwargs (the contract is what `IBDataLayer.get_ohlcv` ultimately needs; pass `meta["sec_type"]` etc. through to it).

### Step 5.5 — Verify

- [ ] `pytest tests/scanner/test_liquid_hours.py tests/scanner/test_preprocessor_multi_market.py -q` → expect all green
- [ ] `pytest -q` → no regressions

### Step 5.6 — Commit

- [ ] `git add app/scanner/liquid_hours.py app/scanner/preprocessor.py app/db/database.py tests/scanner/test_liquid_hours.py tests/scanner/test_preprocessor_multi_market.py`
- [ ] `git commit -m "feat(scanner): consume symbol_meta and liquid_hours from DB"`

---

## Task 6 — Validator reads from DB instead of hardcoded `ALLOWED_SYMBOLS`

**Goal:** `validate_order` calls `get_approved_symbols()` from the DB. `ALLOWED_SYMBOLS` in `settings.py` is kept as a deprecation-warning fallback only (to keep any external imports from breaking) but is no longer the source of truth.

### Files to create/modify

- Modify: `app/risk/validator.py`
- Modify: `app/config/settings.py` (annotate deprecation; do not delete)
- Create/extend: `tests/risk/test_validator_db_symbols.py`

### Step 6.1 — Write failing test first

```python
# tests/risk/test_validator_db_symbols.py
from unittest.mock import patch

import pytest

from app.risk import validator


def _make_order(symbol="AAPL"):
    # Adjust constructor args to whatever validator.validate_order expects.
    return {
        "symbol": symbol, "action": "BUY", "quantity": 1,
        "order_type": "MKT", "limit_price": None,
    }


def test_validator_accepts_symbol_present_in_db():
    with patch.object(validator, "get_approved_symbols",
                      return_value=["AAPL", "BTC", "EURUSD"]):
        result = validator.validate_order(_make_order("BTC"))
    assert result.get("approved") is True or result.get("ok") is True


def test_validator_rejects_symbol_not_in_db():
    with patch.object(validator, "get_approved_symbols",
                      return_value=["AAPL"]):
        result = validator.validate_order(_make_order("ZZZZ"))
    reasons = result.get("reasons") or []
    assert any("not allowed" in r.lower() or "unknown" in r.lower()
               for r in reasons)


def test_validator_does_not_use_hardcoded_settings_list():
    """If DB returns empty, no symbol should be allowed even if settings.ALLOWED_SYMBOLS still has them."""
    with patch.object(validator, "get_approved_symbols", return_value=[]):
        result = validator.validate_order(_make_order("AAPL"))
    reasons = result.get("reasons") or []
    assert any("not allowed" in r.lower() or "unknown" in r.lower()
               for r in reasons)
```

- [ ] Run: `pytest tests/risk/test_validator_db_symbols.py -q` → expect failures.

### Step 6.2 — Update `app/risk/validator.py`

- [ ] Replace the `from app.config.settings import ALLOWED_SYMBOLS` import:

```python
from app.db.database import get_approved_symbols
```

- [ ] Replace the membership check inside `validate_order`:

```python
allowed = set(get_approved_symbols())
if symbol.upper() not in allowed:
    reasons.append(f"Symbol {symbol} is not allowed (not in approved DB list)")
```

- [ ] Add a module-level cache only if perf becomes an issue (Plan A: don't cache; the table has 40 rows).

### Step 6.3 — Mark `ALLOWED_SYMBOLS` deprecated in `app/config/settings.py`

```python
# DEPRECATED — kept for backward-compat with any external script.
# The risk validator now reads approved symbols from the DB.
# Will be removed once Plans B and C are in.
ALLOWED_SYMBOLS = ["AAPL", "MSFT", "SPY", "QQQ", "TSLA",
                   "NVDA", "AMZN", "GOOGL", "META", "JPM"]
```

### Step 6.4 — Verify

- [ ] `pytest tests/risk/test_validator_db_symbols.py -q` → expect 3 passed
- [ ] `pytest -q` → full suite green
- [ ] Spot-check there is no remaining `from app.config.settings import ALLOWED_SYMBOLS` outside `settings.py` itself: `grep -rn "ALLOWED_SYMBOLS" app/ tests/` — only `settings.py` should appear.

### Step 6.5 — Commit

- [ ] `git add app/risk/validator.py app/config/settings.py tests/risk/test_validator_db_symbols.py`
- [ ] `git commit -m "feat(risk): validator reads approved symbols from DB; deprecate ALLOWED_SYMBOLS"`

---

## Final integration verification

- [ ] Run the full suite one last time: `pytest -q`
  - Expected: at least **190 + (5 + 17 + 5 + 6 + 6 + 3) = 232 passed**, 0 failed
  - If the count is off, find the regression before proceeding
- [ ] Smoke test against the live (paper) IB Gateway, with the bot stopped and a one-shot script:

```bash
python - <<'PY'
from app.ibkr.client import IBKRClient
c = IBKRClient(); c.connect()
print("STK   AAPL   :", c.get_stock_price("AAPL"))
print("CASH  EURUSD :", c.get_stock_price("EURUSD", sec_type="CASH",
                                          exchange="IDEALPRO", currency="USD"))
print("CRYPTO BTC   :", c.get_stock_price("BTC", sec_type="CRYPTO",
                                          exchange="PAXOS", currency="USD"))
print("FUT   ES     :", c.get_stock_price("ES", sec_type="FUT",
                                          exchange="CME", currency="USD"))
c.disconnect()
PY
```

  - Expected: four non-None floats. If FUT returns None, check that paper account has FUT_US permission and that the front-month resolution succeeded (look at gateway logs).
- [ ] Restart the bot service: `sudo systemctl restart ibkr-bot.service`
- [ ] Watch logs for 60 s: `journalctl -u ibkr-bot.service -f` — no tracebacks expected.

## Branch wrap-up

- [ ] `git log --oneline feature/multi-market-foundation ^main` — expect 6 commits (one per task).
- [ ] Push and open PR: `git push -u origin feature/multi-market-foundation` then `gh pr create --title "Multi-market foundation (Plan A)" --body "Implements ContractFactory, DB schema migration, and routes data/client/scanner/validator through it. Foundation for Plans B and C."`
- [ ] Do **not** merge yet — Plans B and C build on this branch; merge order is A → B → C.

## Rollback procedure (if anything goes wrong on Pi)

1. `sudo systemctl stop ibkr-bot.service`
2. `git checkout main && git reset --hard <pre-feature-sha>`
3. Restore DB from the pre-migration backup (always take one before running `init_db()` against the live file): `cp data/ibkr_bot.db.bak data/ibkr_bot.db`
4. `sudo systemctl start ibkr-bot.service`

The migration is column-additive and seed uses `ON CONFLICT DO UPDATE` — so re-running it on an already-migrated DB is safe and idempotent. The only destructive change is in `validator.py` (now requires DB to be populated); the seed in Task 1 guarantees that.
