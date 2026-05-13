# Why Decisions: live-dashboard

**Module**: live-dashboard
**Date**: 2026-05-13

## WD-01: Jobs write to DB, dashboard reads — zero IBKR calls from endpoint

**Decision**: APScheduler jobs fetch and cache all data. The dashboard endpoint only reads SQLite.

**Why**: IBKR allows only one active session. Opening the mobile app disconnects IB Gateway. If the dashboard called IBKR directly, it would fail immediately when the user opened their phone app. By using SQLite as the intermediary, the dashboard always has data (possibly 10min stale) regardless of connection state.

**Tradeoff**: Data is never "real-time" — it's always N minutes old. Accepted because the bot itself only checks positions every 2 minutes anyway.

---

## WD-02: Position snapshots inside check_positions(), not a separate job

**Decision**: Write `position_snapshots` inside the existing `check_positions()` loop, not as a separate scheduled job.

**Why**: `check_positions()` already calls `_get_current_price()` for every trade. Adding a snapshot write reuses that API call at zero extra cost. A separate job would duplicate the price fetch and use extra IBKR rate limit budget.

---

## WD-03: SVG inline charts, no charting library

**Decision**: All charts rendered as inline SVG generated in React, not via Chart.js, Recharts, or D3.

**Why**: Pi 5 ARM processor. Chart.js alone is ~200KB. With 10+ charts on the page, loading 5+ chart libraries over a slow Tailscale connection on mobile is unacceptable. SVG paths generated from data arrays add zero bundle weight.

**Tradeoff**: SVG charts require manual path calculation. Accepted because the data structures are simple (line, bar, area) and the patterns are reusable.

---

## WD-04: news_cache fetches for full universe (40 symbols), not on-demand per symbol

**Decision**: The news fetcher job fetches news for all 40 approved symbols every 10 minutes and stores in `news_cache`. The "Mi universo" tab is a filter query, not a live fetch.

**Why**: On-demand news fetch on tab click would require IB Gateway to be online at the moment of the click. With cached data, the news tab always works even when the user opens the IBKR app and disconnects the gateway.

**Tradeoff**: 40 news requests per 10-minute cycle. Within the rate limit (50 req/10min from IB Gateway). Implemented with 0.5s delay between symbols to stay safe.

---

## WD-05: run_learning_cycle() receives ib_client as optional parameter

**Decision**: Add `ib_client=None` parameter to `run_learning_cycle()` instead of importing the client globally inside the function.

**Why**: Avoids circular imports and keeps the cycle module testable with mocks. The client is injected from `run.py` which already has the reference. The parameter is optional so existing tests don't break.

---

## WD-06: backtest_profit_factor added to symbol_parameters, not a new table

**Decision**: Add `backtest_profit_factor REAL` column to existing `symbol_parameters` table instead of creating a `backtest_results` table.

**Why**: Each symbol has one current calibration result. There's no use case for querying historical calibration results. The existing `symbol_parameters` table already has `backtest_calibrated` and `backtest_calibrated_at`. Adding one more column keeps the Mi Universo query a simple SELECT from one table.

---

## WD-07: Telegram confirmation for close position, not PIN on web

**Decision**: Critical actions (close position, pause scanner) require Telegram confirmation instead of a web PIN.

**Why**: The Telegram bot already has `@_only_owner` — only Frank can confirm. Adding a web PIN would require storing secrets and managing sessions. Telegram confirmation leverages the existing security model and adds a natural audit trail in the chat history.
