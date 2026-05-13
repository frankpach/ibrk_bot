# Architecture Map: live-dashboard

**Module**: live-dashboard
**Phase**: Phase 1 — Architecture
**Date**: 2026-05-13

---

## What Already Exists (Reuse)

### Dashboard infrastructure
- `app/api/dashboard.py` — `render_dashboard_html()` returns full HTML with React CDN. Will be rewritten with new sections.
- `app/api/main.py:568` — `GET /dashboard` returns HTML
- `app/api/main.py:574` — `GET /dashboard/data` returns JSON. Already has: status, open_trades, closed_trades, signals, patterns, learning. Needs enrichment.

### Data access
- `IBDataLayer.get_news(symbol)` — already calls `reqHistoricalNews` with BRFG+DJNL+BRFUPDN. Returns list of news items per symbol. Needs to be generalized to multi-symbol and persisted.
- `IBDataLayer.run_scanner(scan_code)` — calls `reqScannerData`. Currently returns mock/basic data. Needs `reqScannerSubscription` for proper live scanner.
- `IBDataLayer.get_earnings_date(symbol)` — already exists, TTL=86400s cached.
- `IBDataLayer.get_implied_volatility(symbol)` — already fetches IV series.
- `IBDataLayer.get_ohlcv(symbol, duration, bar_size, context)` — full historical data, any bar size, with cache. Used for symbol charts.

### Bot infrastructure
- `check_positions()` in `app/positions/manager.py:143` — already calculates `current_price`, `pnl_usd`, `pnl_pct` per trade every 2 minutes. **Just needs a write call added at line ~165**.
- `run_learning_cycle(data_layer)` in `app/ml/cycle.py:37` — runs daily at 17:05. Returns `LearningReport` with AUC, win_rates, samples_used. **Needs `ib_client` parameter added to save account snapshot**.
- `client.get_account()` — already called in multiple places. Returns `net_liquidation`, `buying_power`.
- `get_daily_pnl()` — exists in database.py, used in dashboard.

### DB utilities
- `_add_column_if_missing(conn, table, column, ddl)` at `database.py:75` — safe migrations.
- `init_analysis_tables()` at `database.py:724` — where new tables are added.
- `symbol_parameters` table — already has `backtest_calibrated INTEGER DEFAULT 0` and `backtest_calibrated_at TEXT`. **Missing: `backtest_profit_factor REAL`**.
- `SymbolParameter` dataclass at `models.py:118` — has all multipliers. **Missing: `backtest_calibrated`, `backtest_calibrated_at`, `backtest_profit_factor` fields**.

### APScheduler — existing jobs in run.py
19 jobs already registered. Relevant:
- `check_positions` — every 2 min (add position_snapshot write here)
- `learning_cycle` — 17:05 ET (add account_snapshot write here)
- `reconciler` — every 10 min (pattern to follow for new jobs)

---

## What Doesn't Exist (Build)

### New DB tables (4)
None of these exist yet:
- `position_snapshots` — live P&L per open trade, updated every 2min by check_positions
- `account_snapshots` — daily balance history, written at 17:05 by learning_cycle
- `news_cache` — news articles per symbol, fetched every 10min
- `scanner_results` — scanner/sector/implied_move data, fetched every 5min

### New DB column
- `symbol_parameters.backtest_profit_factor REAL` — store backtest result for Mi Universo table

### New APScheduler jobs (5)
- `_save_position_snapshots` — write after check_positions (same 2min interval)
- `_save_account_snapshot` — write after learning_cycle at 17:05
- `_fetch_news` — every 10min, market hours → news_cache
- `_fetch_scanner` — every 5min, market hours → scanner_results
- `_fetch_sectors` — every 5min, market hours → scanner_results (XLK, XLF, XLE, XLV, XLY, XLI)

### New scanner/news fetcher modules
- `app/scanner/news_fetcher.py` — `fetch_and_cache_news(ib_client, data_layer)` — multi-symbol news fetch and persist
- `app/scanner/market_scanner.py` — `fetch_and_cache_scanner(ib_client)` and `fetch_and_cache_sectors(data_layer)` — scanner subscription + sector ETF prices

### New /dashboard/data fields
Current endpoint returns 6 fields. Needs 6 more:
- `position_snapshots` — live P&L per trade from new table
- `account_history` — 30-day balance array for equity chart
- `news` — from news_cache, filtered by symbol subset
- `scanner` — from scanner_results, by scan_type
- `symbols_universe` — symbol_parameters for all approved symbols (Mi Universo table)
- `ib_connected` — boolean for IB Gateway status bar

### Dashboard React sections (10 new vs current 6)
The current dashboard has: StatCards, OpenPositions, Signals, History, Learning, Patterns.
New sections to add: IB status bar, smart refresh, drawdown gauge, R/R bar per position, earnings badge, equity/weekly/exits/hours tabs, lazy symbol chart, news card, market trends card, Mi Universo table, control bar.

---

## Data Flow Diagram

```
IB Gateway (IBKR)
    │
    ├─ check_positions() every 2min
    │      └─ writes → position_snapshots
    │
    ├─ _fetch_news() every 10min
    │      └─ writes → news_cache
    │
    ├─ _fetch_scanner() every 5min
    │      └─ writes → scanner_results
    │
    └─ learning_cycle 17:05 ET
           └─ writes → account_snapshots

SQLite DB
    └─ /dashboard/data (GET, read-only)
           └─ React dashboard (client-side fetch every 15/60s)
```

---

## Reuse Decisions

| Need | Use | File |
|------|-----|------|
| Fetch news | `IBDataLayer.get_news()` extended | data.py:214 |
| Fetch earnings | `IBDataLayer.get_earnings_date()` | data.py:254 |
| Fetch implied vol | `IBDataLayer.get_implied_volatility()` | data.py:192 |
| Fetch OHLCV for charts | `IBDataLayer.get_ohlcv()` | data.py:77 |
| DB migration | `_add_column_if_missing()` | database.py:75 |
| Account balance | `client.get_account()` | already called in dashboard |
| P&L calculation | existing logic in check_positions | manager.py:154-161 |
| Scheduler pattern | existing `scheduler.add_job()` | run.py:302+ |

---

## Anti-Pattern Flags

**Model Blindness**: `SymbolParameter` already has `backtest_calibrated`. Don't create a new table — extend the existing model with `backtest_profit_factor`.

**Island Components**: `IBDataLayer.get_news()` already calls `reqHistoricalNews`. Don't write a new IBKR connection — extend the existing method for multi-symbol batch fetching.

**Pub/Sub Bypass**: `check_positions()` already runs every 2min. Add the snapshot write inside the existing loop rather than creating a separate polling job that duplicates work.
