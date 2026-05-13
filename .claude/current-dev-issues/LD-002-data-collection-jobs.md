# Issue LD-002: Data Collection Jobs — Position Snapshots, Account, News, Scanner

**Module**: live-dashboard
**Type**: AFK
**Effort**: M
**Blocked by**: LD-001
**Requires review**: false

---

## WHY

The dashboard shows "last updated X min ago" for every section. That freshness depends on
background jobs writing to the 4 new DB tables. Without these jobs running, the dashboard
has no live data to display — stat cards stay empty, news stays blank, scanner never populates.

**Success signal**: After a 2-minute wait with IB Gateway connected, `position_snapshots`
has one row per open trade with a current price. After 5 minutes, `scanner_results` has
rows for "most_active". After 10 minutes, `news_cache` has articles for approved symbols.

---

## WHO

| Persona | Role | Goal |
|---------|------|------|
| Motor Autónomo | System | Data written periodically, available for dashboard |
| Frank Trader | Trader | News and scanner always visible even if IB goes offline |

---

## WHAT — Constraints

- [ ] News fetch: max 40 symbols, 0.5s delay between requests (rate limit safety)
- [ ] Scanner and news jobs only run during liquid hours for their market type
- [ ] Position snapshot write goes INSIDE `check_positions()` loop — not a separate job
- [ ] `run_learning_cycle()` signature change to `(data_layer, ib_client=None)` — backwards compatible
- [ ] All job functions wrapped in try/except — never crash the scheduler
- [ ] Do NOT touch `app/risk/`

---

## HOW

### A) Position snapshots — inside `app/positions/manager.py`

In `check_positions()`, after calculating `pnl_usd` (approximately line 161), add:
```python
try:
    from app.db.database import upsert_position_snapshot
    upsert_position_snapshot(
        trade_id=trade.id,
        symbol=trade.symbol,
        current_price=price,
        pnl_usd=round(pnl_usd, 2),
        pnl_pct=round(pnl_pct, 4),
    )
except Exception as snap_err:
    logger.debug(f"Position snapshot write failed for {trade.symbol}: {snap_err}")
```

### B) Account snapshot — in `app/ml/cycle.py`

Change signature: `def run_learning_cycle(data_layer, ib_client=None) -> LearningReport:`

At end of `run_learning_cycle()`, before `return report`:
```python
# Save daily account snapshot
if ib_client is not None:
    try:
        from app.db.database import upsert_account_snapshot, get_daily_pnl
        account = ib_client.get_account()
        daily_pnl = get_daily_pnl()
        capital = account.get("net_liquidation", 0.0)
        upsert_account_snapshot(
            date=datetime.utcnow().strftime("%Y-%m-%d"),
            net_liquidation=round(capital, 2),
            buying_power=round(account.get("buying_power", 0.0), 2),
            daily_pnl_usd=round(daily_pnl, 2),
            daily_pnl_pct=round(daily_pnl / capital * 100, 4) if capital else 0.0,
        )
    except Exception as e:
        report.errors.append(f"Account snapshot: {e}")
        logger.error(f"Account snapshot failed: {e}")
```

In `run.py` where learning_cycle is called, pass the client:
```python
def _run_learning_cycle():
    try:
        ib_client = _ib_client_ref.get("client")
        run_learning_cycle(_ib_client_ref["data_layer"], ib_client=ib_client)
    except Exception as e:
        logger.error(f"Learning cycle error: {e}")
```

### C) News fetcher — new file `app/scanner/news_fetcher.py`

```python
"""Fetch news from IBKR for all approved symbols and cache in news_cache."""
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)

def fetch_and_cache_news(data_layer) -> int:
    """Fetch news for approved symbols. Returns count of articles saved."""
    from app.db.database import get_approved_symbols_with_meta, insert_news_cache, clear_news_cache_older_than
    from app.analysis.indicators import _extract_sentiment  # reuse if available

    try:
        clear_news_cache_older_than(hours=24)
    except Exception:
        pass

    symbols = get_approved_symbols_with_meta()[:40]
    count = 0
    for sym_meta in symbols:
        symbol = sym_meta.get("symbol", "")
        try:
            news_items = data_layer.get_news(symbol)
            for item in news_items:
                headline = item.get("title", "")
                if not headline:
                    continue
                insert_news_cache(
                    symbol=symbol,
                    headline=headline,
                    provider=item.get("provider", ""),
                    sentiment=item.get("sentiment", "neutral"),
                    article_id=item.get("article_id", ""),
                    published_at=str(item.get("date", "")),
                )
                count += 1
            time.sleep(0.5)  # rate limit safety
        except Exception as e:
            logger.warning(f"News fetch failed for {symbol}: {e}")

    logger.info(f"News cache updated: {count} articles for {len(symbols)} symbols")
    return count
```

### D) Market scanner — new file `app/scanner/market_scanner.py`

```python
"""Fetch scanner data (most active, gainers, losers, sectors, implied move) from IBKR."""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

SCAN_CODES = {
    "most_active": "MOST_ACTIVE",
    "top_movers":  "TOP_PERC_GAIN",   # will also run TOP_PERC_LOSE and combine
    "gainers":     "TOP_PERC_GAIN",
    "losers":      "TOP_PERC_LOSE",
}

SECTOR_ETFS = {
    "XLK": "Tech", "XLF": "Finance", "XLE": "Energy",
    "XLV": "Health", "XLY": "Consumer", "XLI": "Industrial",
}

def fetch_and_cache_scanner(data_layer) -> None:
    from app.db.database import upsert_scanner_results
    for scan_type, scan_code in SCAN_CODES.items():
        try:
            raw = data_layer.run_scanner(scan_code)
            results = [
                {"symbol": s, "name": "", "change_pct": None, "volume_ratio": None}
                for s in (raw or [])[:10]
            ]
            upsert_scanner_results(scan_type, results)
        except Exception as e:
            logger.warning(f"Scanner {scan_type} failed: {e}")

def fetch_and_cache_sectors(data_layer) -> None:
    from app.db.database import upsert_scanner_results
    results = []
    for etf, name in SECTOR_ETFS.items():
        try:
            df = data_layer.get_ohlcv(etf, "2 D", "1 day", "scanner")
            if df is not None and len(df) >= 2:
                prev = float(df["close"].iloc[-2])
                curr = float(df["close"].iloc[-1])
                change_pct = round((curr - prev) / prev * 100, 2) if prev > 0 else 0.0
                results.append({
                    "symbol": etf, "name": name,
                    "change_pct": change_pct, "volume_ratio": None,
                })
        except Exception as e:
            logger.warning(f"Sector ETF {etf} failed: {e}")
    upsert_scanner_results("sector", results)

def fetch_implied_move(data_layer, symbols: list) -> None:
    """Fetch implied volatility as proxy for expected move."""
    from app.db.database import upsert_scanner_results
    results = []
    for symbol in symbols[:10]:
        try:
            iv_df = data_layer.get_implied_volatility(symbol, "scanner")
            if iv_df is not None and len(iv_df) > 0:
                iv = float(iv_df["close"].iloc[-1])
                # Weekly implied move ≈ IV / sqrt(52)
                import math
                weekly_move = round(iv / math.sqrt(52) * 100, 1)
                results.append({
                    "symbol": symbol, "name": "",
                    "change_pct": weekly_move, "volume_ratio": None,
                    "extra_json": f'{{"iv": {iv:.4f}}}'
                })
        except Exception as e:
            logger.debug(f"Implied move {symbol}: {e}")
    upsert_scanner_results("implied_move", results)
```

### E) Register 3 new jobs in `run.py`

```python
from app.scanner.news_fetcher import fetch_and_cache_news
from app.scanner.market_scanner import fetch_and_cache_scanner, fetch_and_cache_sectors, fetch_implied_move

def _run_news_fetch():
    try:
        if _ib_client_ref.get("data_layer"):
            fetch_and_cache_news(_ib_client_ref["data_layer"])
    except Exception as e:
        logger.error(f"News fetch error: {e}")

def _run_scanner_fetch():
    try:
        if _ib_client_ref.get("data_layer"):
            dl = _ib_client_ref["data_layer"]
            fetch_and_cache_scanner(dl)
            fetch_and_cache_sectors(dl)
            from app.db.database import get_approved_symbols
            syms = get_approved_symbols()[:10]
            fetch_implied_move(dl, syms)
    except Exception as e:
        logger.error(f"Scanner fetch error: {e}")

# Add jobs:
scheduler.add_job(_run_news_fetch, "interval", minutes=10,
                  id="news_fetch", replace_existing=True)
scheduler.add_job(_run_scanner_fetch, "interval", minutes=5,
                  id="scanner_fetch", replace_existing=True)
```

---

## Code Search

- [x] `app/positions/manager.py:143-161` — P&L calculation confirmed, insert point at ~line 165
- [x] `app/ml/cycle.py:37` — current signature `run_learning_cycle(data_layer)` confirmed
- [x] `run.py:390-406` — learning cycle job calls `_ib_client_ref["data_layer"]`
- [x] `app/analysis/data.py:214-252` — `get_news()` confirmed, already calls `reqHistoricalNews`
- [x] `app/analysis/data.py:276-295` — `run_scanner()` confirmed

**Reuse decision**:
- `data_layer.get_news(symbol)` — reuse as-is, called per symbol
- `data_layer.run_scanner(scan_code)` — reuse, extend with proper scan codes
- `data_layer.get_ohlcv()` — reuse for sector ETF daily prices
- `data_layer.get_implied_volatility()` — reuse for implied move tab

---

## Reference Documents

| Document | Path |
|----------|------|
| Spec | `docs/superpowers/specs/2026-05-13-live-dashboard-design.md` — New APScheduler Jobs section |
| Architecture map | `docs/dev/artifacts/live-dashboard/03-architecture-map.md` |

---

## Acceptance Criteria

- [ ] AC-01: After `check_positions()` runs with open trades, `position_snapshots` has one row per trade
- [ ] AC-02: After `_run_learning_cycle()` with connected IB client, `account_snapshots` has today's date row
- [ ] AC-03: `run_learning_cycle(data_layer)` (old signature, no ib_client) still works without error
- [ ] AC-04: After `_run_news_fetch()`, `news_cache` has rows for approved symbols
- [ ] AC-05: After `_run_scanner_fetch()`, `scanner_results` has rows for scan_types: most_active, gainers, losers, sector, implied_move
- [ ] AC-06: Jobs registered in scheduler at startup (visible in run.py logs)
- [ ] AC-07: `pytest tests/` — no regressions

## Definition of Done

- [ ] All ACs verified with IB Gateway connected in paper mode
- [ ] Tests for `fetch_and_cache_news()` and `fetch_and_cache_scanner()` with mocks
- [ ] Issue moved to `done/`
