# Issue LD-003: Enrich /dashboard/data Endpoint

**Module**: live-dashboard
**Type**: AFK
**Effort**: S
**Blocked by**: LD-001
**Requires review**: false

---

## WHY

The React dashboard fetches all its data from `GET /dashboard/data`. Currently it returns
6 fields. The new dashboard needs 6 more: position snapshots (live P&L), account history
(equity curve), news, scanner results, symbol universe with calibration, and IB connection status.
Without this endpoint returning the right data, the frontend sections have nothing to render.

**Success signal**: `GET /dashboard/data` returns all 12 fields. The React app can render
every section from this single JSON response.

---

## WHO

| Persona | Role | Goal |
|---------|------|------|
| Motor Autónomo | System | Endpoint serves fresh data every 15-60s |

---

## WHAT — Constraints

- [ ] Endpoint remains `GET /dashboard/data` — no route change
- [ ] All new fields are additive — existing fields unchanged
- [ ] Zero IBKR calls — only SELECT queries from DB
- [ ] If a table is empty (jobs haven't run yet), return empty list/dict gracefully
- [ ] Response must stay under 50KB
- [ ] `ib_connected` comes from `client.ib.isConnected()` — the client is already imported

---

## HOW

In `app/api/main.py`, extend the `dashboard_data()` function to add 6 new sections:

```python
@app.get("/dashboard/data")
def dashboard_data():
    from app.db.database import (
        get_open_trades, get_closed_trades, get_pending_signals,
        get_patterns_for_symbol, get_daily_pnl, get_approved_symbols,
        get_position_snapshots, get_account_history,
        get_news_cache, get_scanner_results,
        get_or_create_symbol_parameters, get_closed_trades_by_symbol,
    )

    # ... existing code for status, open_trades, closed_trades, signals, patterns, learning ...

    # NEW 1: Position snapshots (live P&L per trade)
    pos_snaps = get_position_snapshots()  # {trade_id: {current_price, pnl_usd, pnl_pct, updated_at}}
    # Merge into open_trades
    for t in trades_out:
        snap = pos_snaps.get(t.get("trade_id"))
        if snap:
            t["current_price"] = snap["current_price"]
            t["pnl_usd"] = snap["pnl_usd"]
            t["pnl_pct"] = snap["pnl_pct"]
            t["snapshot_at"] = snap["updated_at"]
        else:
            t["current_price"] = t["entry_price"]
            t["pnl_usd"] = 0.0
            t["pnl_pct"] = 0.0
            t["snapshot_at"] = None

    # NEW 2: Account history for equity curve
    account_history = get_account_history(days=30)

    # NEW 3: Latest account balance for stat cards
    latest_account = account_history[-1] if account_history else {}

    # NEW 4: News cache (default: all approved symbols, limit 20)
    approved = get_approved_symbols()
    news = get_news_cache(symbols=approved[:40], limit=20)

    # NEW 5: Scanner results (all scan types)
    scanner = {
        "most_active":  get_scanner_results("most_active"),
        "top_movers":   get_scanner_results("top_movers"),
        "gainers":      get_scanner_results("gainers"),
        "losers":       get_scanner_results("losers"),
        "sector":       get_scanner_results("sector"),
        "implied_move": get_scanner_results("implied_move"),
    }

    # NEW 6: Symbol universe with calibration data
    symbols_universe = []
    for sym in approved[:40]:
        try:
            params = get_or_create_symbol_parameters(sym)
            trades_sym = get_closed_trades_by_symbol(sym, limit=20)
            wins = sum(1 for t in trades_sym if (t.pnl_pct or 0) > 0)
            win_rate = round(wins / len(trades_sym), 3) if trades_sym else None
            multipliers = {
                k: round(getattr(params, f"{k}_mult", 1.0), 3)
                for k in ["momentum", "trend", "volume", "volatility"]
                if abs(getattr(params, f"{k}_mult", 1.0) - 1.0) > 0.05
            }
            symbols_universe.append({
                "symbol": sym,
                "backtest_calibrated": bool(getattr(params, "backtest_calibrated", 0)),
                "backtest_calibrated_at": getattr(params, "backtest_calibrated_at", None),
                "backtest_profit_factor": getattr(params, "backtest_profit_factor", None),
                "stop_loss_pct": params.stop_loss_pct,
                "take_profit_pct": params.take_profit_pct,
                "trade_count": params.trade_count,
                "win_rate": win_rate,
                "multipliers_drifted": multipliers,
            })
        except Exception:
            pass

    # NEW 7: IB connection status
    ib_connected = False
    ib_last_seen = None
    try:
        ib_connected = bool(client.ib.isConnected())
    except Exception:
        pass

    # NEW 8: Earnings warnings for open positions
    earnings_warnings = {}
    try:
        from datetime import timedelta
        for t in open_trades:
            ed = data_layer.get_earnings_date(t.symbol) if hasattr(data_layer, 'get_earnings_date') else None
            if ed:
                days_until = (ed - datetime.now()).days
                if 0 <= days_until <= 3:
                    earnings_warnings[t.symbol] = days_until
    except Exception:
        pass

    return {
        # Existing fields
        "status": status,
        "open_trades": trades_out,           # now enriched with pnl_usd, pnl_pct, current_price
        "closed_trades": closed_out,
        "signals": signals_out,
        "patterns": patterns_out,
        "learning": learning,
        # New fields
        "account_history": account_history,
        "latest_account": latest_account,
        "news": news,
        "scanner": scanner,
        "symbols_universe": symbols_universe,
        "ib_connected": ib_connected,
        "earnings_warnings": earnings_warnings,
    }
```

Also need `trade_id` in `trades_out` — add it to the existing serialization:
```python
"trade_id": t.id,  # add this field
```

---

## Code Search

- [x] `app/api/main.py:574` — `dashboard_data()` function confirmed
- [x] `app/api/main.py:613` — `trades_out` dict — add `trade_id` and snapshot fields
- [x] `client.ib.isConnected()` — used in other endpoints

**Reuse decision**:
- `get_approved_symbols()` — exists, used in learning cycle
- `get_closed_trades_by_symbol()` — added in MTE-011, exists
- `data_layer.get_earnings_date()` — exists in IBDataLayer

---

## Reference Documents

| Document | Path |
|----------|------|
| Spec | `docs/superpowers/specs/2026-05-13-live-dashboard-design.md` |

---

## Acceptance Criteria

- [ ] AC-01: `GET /dashboard/data` returns 200 with all 13 top-level fields
- [ ] AC-02: `open_trades` items include `pnl_usd`, `pnl_pct`, `current_price`, `trade_id`
- [ ] AC-03: `account_history` is a list of dicts with `date`, `net_liquidation`, `daily_pnl_usd`
- [ ] AC-04: `scanner` has 6 keys (most_active, top_movers, gainers, losers, sector, implied_move)
- [ ] AC-05: `symbols_universe` has one entry per approved symbol with calibration fields
- [ ] AC-06: `ib_connected` is a boolean
- [ ] AC-07: Empty tables return empty lists/dicts, never error
- [ ] AC-08: `pytest tests/api/` passes

## Definition of Done

- [ ] All ACs verified
- [ ] Test: `test_dashboard_data_success()` verifies all 13 fields present
- [ ] Issue moved to `done/`
