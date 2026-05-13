# Live Dashboard — Design Spec

**Date**: 2026-05-13
**Module**: live-dashboard
**Status**: approved by user

---

## Problem

The current dashboard at `/dashboard` reads data exclusively from the local SQLite DB and never reflects live IBKR data. Open positions show no floating P&L, account balance is stale, and there is no market discovery capability (news, scanner, sector performance). The user also needs basic interactive controls accessible from the web without depending on Telegram for every action.

**Key constraint**: IBKR only allows one active session at a time. Opening the IBKR mobile or web app disconnects IB Gateway. The dashboard must degrade gracefully when IB Gateway is offline — showing cached data with timestamps instead of failing.

---

## Architecture: Jobs Write, Dashboard Reads

The dashboard endpoint never calls IBKR directly. The trading bot's existing scheduler jobs fetch data periodically and persist it to SQLite. `/dashboard/data` only does SELECT queries.

```
check_positions()  every 2min  → writes position_snapshots (live P&L per trade)
daily_cycle        17:05 ET    → writes account_snapshots (daily balance)
news_job           every 10min → writes news_cache table
scanner_job        every 5min  → writes scanner_results table
/dashboard/data                → SELECT only, zero IBKR calls
```

When IB Gateway is offline: all tables retain last values. Dashboard shows "last updated X min ago" per section. Critical actions (close position, pause scanner) are blocked with a visual indicator until reconnection.

---

## IB Gateway Status Bar

Persistent bar above the header, always visible:

- **Online**: green dot + "IB Gateway · connected" + "data fresh"
- **Offline**: red dot + "IB Gateway · offline" + "last connection Xmin ago" + amber warning "critical actions blocked"

---

## Smart Refresh

- **15 seconds** when there are open positions (active trading)
- **60 seconds** when no open positions (idle)
- Visual countdown ring in the header

---

## Sections & Features

### 1. Stat Cards (top strip)
Four cards in a responsive grid:
- **Net Liquidation** — from `client.get_account()`, cached in `account_snapshots`
- **P&L Today** — sum of closed trades today + floating P&L of open positions; **drawdown gauge** below the number showing current drawdown vs the 5%/10%/15% mode-change thresholds
- **Buying Power** — from `account_snapshots`
- **Positions** — open count / 3 max

### 2. Open Positions
Per position card with:
- Symbol, action badge (BUY/SELL), signal strength badge, weekly_trend chip
- **Earnings badge** (⚠ Earnings in N days) when `get_earnings_date()` returns a date within 3 days
- **Floating P&L** in $ and % — from `position_snapshots` (updated by `check_positions()`)
- **Risk/Reward visual bar** — horizontal bar between SL and TP showing current price location; R/R ratio displayed
- Entry, current price, SL, TP, quantity, risk $ in a 3-column grid
- **Close button** — triggers `POST /orders/close` → bot sends Telegram confirmation → user confirms → executes

### 3. Mi Cuenta (4 tabs)
- **Equity 30d** (default): combo chart — blue line for balance + green/red daily P&L bars
- **Semanal**: bar chart of P&L per week, last 5 weeks
- **Exits**: horizontal bar chart of exit distribution — Take Profit / Stop Loss / Trailing / Manual
- **Horas**: bar chart of average P&L by hour of day (best entry time pattern)

### 4. Symbol Chart (lazy load, 3 tabs)
- Symbol selector chips: open positions + active signals (chips from DB, no IBKR call)
- Lazy fetch when user selects a symbol; cached for 5 minutes
- **Hoy 5min** (default): intraday 5-min candle/line chart with entry price marker, SL line, TP line
- **30D diario**: daily price chart with SMA20 overlay
- **Indicadores**: RSI gauge, MACD histogram, Bollinger position bar, Volume ratio

### 5. Noticias IBKR (3 tabs)
- Fetched every 10min via `reqHistoricalNews` in APScheduler job, stored in `news_cache`
- **Mi universo** (default): filtered by the 40 active approved symbols
- **Todas**: all market news from BRFG + DJNL providers
- **Posiciones**: only news for currently open position symbols
- Each item: symbol, headline, source, time ago, sentiment chip (positive/negative/neutral)

### 6. Market Trends (6 tabs)
All data from `reqScannerSubscription` + sector ETF prices, fetched every 5min by APScheduler job, stored in `scanner_results`:
- **Más activos** (default): most active by volume
- **Top Movers**: largest % moves regardless of direction
- **Gainers**: top % gainers
- **Losers**: top % losers
- **Sectores**: performance bars for XLK, XLF, XLE, XLV, XLY, XLI (fetched from sector ETF prices)
- **Implied Move**: expected ±% move from implied volatility for each symbol in the user's universe — amber >3%, green ≤3%

Each scanner row has: symbol, name, % change, volume multiplier, **+ añadir button** → calls `POST /symbols/propose` → no IBKR needed, just DB write

### 7. Signals + History (2 columns)
- **Señales**: table with symbol, strength badge, RSI, volume, weekly_trend chip, time; input + "Analizar" and "Aprobar" buttons
- **Historial**: last 8 closed trades with symbol, P&L $, P&L %, exit reason, date

### 8. Learning Engine Widget
Small status card showing:
- SignalFilter AUC with fill bar (from `LearningReport` in `cycle.py`)
- Trades trained, last retrain timestamp, global win rate
- Shows the system is actually learning

### 9. Mi Universo — Símbolos con Entrenamiento y Backtest

Table showing all approved symbols with their learning and calibration status. Accessible as a full section below the main grid.

Columns:
- **Symbol** — ticker
- **Calibrado** — ✓ badge (green, from backtest) or "defaults" (gray, generic params)
- **SL% / TP%** — current calibrated or default values from `symbol_parameters`
- **Profit Factor** — from backtest result (store in `symbol_parameters.backtest_profit_factor`)
- **Win Rate** — calculated from closed `trades` for this symbol (last 20 trades)
- **Trades** — `symbol_parameters.trade_count`
- **Aprendizaje** — compact badges showing which multipliers have drifted from 1.0 (e.g., `momentum ▲1.23`, `trend ▼0.87`)
- **Última calibración** — `symbol_parameters.backtest_calibrated_at` or "nunca"
- **Acciones** — "Recalibrar" button to trigger `on_symbol_approved()` again; "Ver detalle" to open symbol lazy chart

Requires adding `backtest_profit_factor REAL` column to `symbol_parameters` (via `_add_column_if_missing`).

### 10. System Control Bar
- Scanner toggle (▶ ACTIVE / ⏸ PAUSED) — with Telegram confirmation
- Notification level selector (critico / normal / verbose) — no confirmation needed
- Mode badge (PAPER / LIVE)
- Hint: "critical actions → Telegram confirmation"

---

## New DB Tables Required

```sql
CREATE TABLE IF NOT EXISTS account_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,                -- YYYY-MM-DD
    net_liquidation REAL NOT NULL,
    buying_power REAL,
    daily_pnl_usd REAL,
    daily_pnl_pct REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS position_snapshots (
    trade_id INTEGER PRIMARY KEY,      -- FK to trades.id
    symbol TEXT NOT NULL,
    current_price REAL,
    pnl_usd REAL,
    pnl_pct REAL,
    updated_at TEXT NOT NULL
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
    scan_type TEXT NOT NULL,           -- 'most_active', 'top_movers', 'gainers', 'losers', 'sector', 'implied_move'
    symbol TEXT NOT NULL,
    name TEXT,
    change_pct REAL,
    volume_ratio REAL,
    extra_json TEXT DEFAULT '{}',
    fetched_at TEXT NOT NULL
);
```

---

## New APScheduler Jobs (in run.py)

| Job | Frequency | Function |
|-----|-----------|----------|
| `_save_position_snapshots()` | every 2min (with check_positions) | Writes live P&L per open trade |
| `_save_account_snapshot()` | 17:05 ET daily | Saves daily balance from `client.get_account()` |
| `_fetch_news()` | every 10min, market hours | `reqHistoricalNews` → `news_cache` |
| `_fetch_scanner()` | every 5min, market hours | `reqScannerSubscription` → `scanner_results` |
| `_fetch_sectors()` | every 5min, market hours | Sector ETF prices → `scanner_results` |

---

## Modified Files

| File | Change |
|------|--------|
| `app/db/database.py` | 4 new tables + CRUD functions for each |
| `app/positions/manager.py` | After P&L calculation in `check_positions()`, write to `position_snapshots` |
| `app/ml/cycle.py` | After `run_learning_cycle()`, write to `account_snapshots` |
| `app/api/main.py` | Enrich `/dashboard/data` with snapshots, news, scanner, learning metrics |
| `app/api/dashboard.py` | Full dashboard rebuild with all new sections |
| `run.py` | Register 5 new scheduler jobs |

---

## New Files

| File | Purpose |
|------|---------|
| `app/scanner/news_fetcher.py` | `fetch_and_cache_news()` using `reqHistoricalNews` |
| `app/scanner/market_scanner.py` | `fetch_and_cache_scanner()` using `reqScannerSubscription` |

---

## IB Gateway Offline Behavior

| Component | Online | Offline |
|-----------|--------|---------|
| Stats (balance, buying power) | Fresh from snapshots (2min old) | Last cached value + "Xmin ago" |
| Position P&L | Fresh from position_snapshots | Last known P&L + timestamp |
| News | Fresh if <10min | Cached news, shows fetch time |
| Scanner | Fresh if <5min | Cached results, shows fetch time |
| Close position button | Active | Disabled, "IB Gateway offline" tooltip |
| Pause scanner button | Active | Disabled |

---

## Dark / Light Mode

CSS variable tokens for full theme support. Toggle button in header (☀️/🌙). Preference persisted in localStorage.

---

## Earnings Warning

`get_earnings_date(symbol)` already exists in `IBDataLayer`. When a position or signal has earnings within 3 days, show a red `⚠ Earnings in N days` badge on the position card. Fetched from `fundamentals` cache (TTL=86400s already configured).

---

## Interaction Flow: Close Position

```
User clicks "Cerrar" on AAPL position
  → POST /orders/close {trade_id: 42}
  → API validates IB Gateway is connected
  → Bot sends Telegram: "Cerrar AAPL BUY 2.2u @ $184.20? Responde /si o /no"
  → User replies /si in Telegram
  → Bot executes close order
  → Dashboard refreshes on next 15s tick, position disappears
```

---

## Verification Checklist

- [ ] `position_snapshots` populated after `check_positions()` runs
- [ ] `account_snapshots` has 1 row per day after 17:05 ET
- [ ] Equity curve chart shows real balance progression
- [ ] News shows when IB Gateway is online; cached when offline
- [ ] Scanner tabs populate; sector bars show ETF performance
- [ ] Earnings badge appears on position with upcoming report
- [ ] Drawdown gauge reflects current drawdown from `drawdown.py`
- [ ] Close position button disabled when IB offline; Telegram confirmation works when online
- [ ] Dark/light toggle persists across page refreshes
- [ ] "Mi Universo" table shows all approved symbols with calibration status, win rate, profit factor
- [ ] Symbols with `backtest_calibrated=0` show "defaults" badge in gray
- [ ] "Recalibrar" button triggers background calibration job and shows "calibrando..." state
- [ ] 15s refresh when positions open, 60s when none
