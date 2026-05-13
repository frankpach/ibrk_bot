# Live Dashboard Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the live dashboard, live/paper runtime mode, symbol approval flow, and LD-005 frontend behavior coherent, accurate, and realistic for end users operating against IBKR.

**Architecture:** Keep the dashboard as a DB-first read model fed by scheduled jobs and reconciliation logic, while moving all operational truth to stable backend sources: DB-approved symbols, runtime mode/config, and persisted snapshots. The implementation closes the gap between visual UI completion and real operational behavior by fixing approval/calibration flow, snapshot freshness, scanner usefulness, and live/paper semantics end-to-end.

**Tech Stack:** FastAPI, APScheduler, SQLite, ib_insync, React via CDN, pytest, Playwright/manual browser verification

---

## File Map

- Modify: `run.py`
  Purpose: runtime config, gateway port selection, scheduler registration, snapshot cadence
- Modify: `app/config/settings.py`
  Purpose: source of truth cleanup for legacy `ALLOWED_SYMBOLS` and live/paper env semantics
- Modify: `app/api/main.py`
  Purpose: dashboard data contract, symbol approval endpoint, runtime status, backtest/universe consistency
- Modify: `app/api/dashboard.py`
  Purpose: dashboard rendering, realistic UI behavior, LD-005 completion
- Modify: `app/db/database.py`
  Purpose: symbol approval persistence, approved-symbol queries, optional helper queries for active/open symbols
- Modify: `app/positions/manager.py`
  Purpose: position snapshot freshness and reconciled-trade monitoring
- Modify: `app/scanner/market_scanner.py`
  Purpose: populate scanner rows with actionable `% move` and `volume_ratio`
- Modify: `app/analysis/data.py`
  Purpose: chart caching TTL alignment for dashboard lazy chart
- Modify: `app/system/controller.py`
  Purpose: scheduler pause/resume consistency and runtime mode visibility
- Modify: `app/notifications/telegram_bot.py`
  Purpose: `/simbolos` and operator-facing flows stay consistent with approved DB symbols
- Test: `tests/api/test_main_extended.py`
- Test: `tests/db/test_database.py`
- Test: `tests/system/test_controller.py`
- Test: `tests/scanner/test_market_scanner.py`
- Test: `tests/positions/test_manager.py`

---

### Task 1: Fix Runtime Mode And Gateway Configuration

**Files:**
- Modify: `run.py`
- Modify: `app/system/controller.py`
- Modify: `app/config/settings.py`
- Test: `tests/system/test_controller.py`
- Test: `tests/api/test_main_extended.py`

- [ ] **Step 1: Write the failing tests for live/paper runtime semantics**

```python
def test_system_status_reflects_live_mode_from_controller():
    ...
    resp = client.get("/dashboard/data")
    assert resp.json()["status"]["mode"] == "live"


def test_run_uses_env_gateway_port_not_hardcoded():
    import run
    assert run.IB_PORT in (4001, 4002)
```

- [ ] **Step 2: Run the targeted tests to verify current failure**

Run: `pytest tests/system/test_controller.py tests/api/test_main_extended.py -k "mode or gateway" -v`
Expected: failures showing inconsistent runtime mode and/or hardcoded assumptions.

- [ ] **Step 3: Make runtime config explicit and environment-driven**

Implement in `run.py`:

```python
import os

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4002"))
```

Implement in `app/system/controller.py`:

```python
    def pause(self):
        for job_id in ("signal_processor", "scanner", "scanner_fetch"):
            try:
                self.scheduler.pause_job(job_id)
            except Exception:
                pass

    def resume(self):
        for job_id in ("signal_processor", "scanner", "scanner_fetch"):
            try:
                self.scheduler.resume_job(job_id)
            except Exception:
                pass
```

Implement in `app/config/settings.py` comments and defaults:

```python
# Legacy list retained for compatibility only; DB-approved symbols are authoritative.
PAPER_TRADING_ONLY = os.getenv("PAPER_TRADING_ONLY", "true").lower() == "true"
```

- [ ] **Step 4: Make dashboard status use controller/runtime consistently**

Update `app/api/main.py` status assembly so dashboard does not infer `"paper"` from stale defaults when controller is initialized:

```python
status = {
    "mode": _mode,
    "paused": False,
    ...
}
try:
    ctrl = get_controller()
    status["mode"] = ctrl.mode
    status["paused"] = ctrl.is_paused
except RuntimeError:
    pass
```

- [ ] **Step 5: Re-run the targeted tests**

Run: `pytest tests/system/test_controller.py tests/api/test_main_extended.py -k "mode or gateway" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add run.py app/system/controller.py app/config/settings.py app/api/main.py tests/system/test_controller.py tests/api/test_main_extended.py
git commit -m "fix: align runtime mode and gateway config with env-driven live/paper behavior"
```

---

### Task 2: Make Approved Symbols A Single Source Of Truth

**Files:**
- Modify: `app/db/database.py`
- Modify: `app/api/main.py`
- Modify: `app/notifications/telegram_bot.py`
- Test: `tests/db/test_database.py`
- Test: `tests/api/test_main_extended.py`

- [ ] **Step 1: Write the failing tests for approval and approved-symbol visibility**

```python
def test_approve_symbol_inserts_missing_symbol_into_symbol_config():
    approve_symbol("AAOI")
    assert "AAOI" in get_approved_symbols()


def test_allowed_symbols_endpoint_uses_db_approved_symbols():
    resp = client.get("/allowed-symbols")
    assert "AAOI" in resp.json()["symbols"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/db/test_database.py tests/api/test_main_extended.py -k "approve_symbol or allowed_symbols" -v`
Expected: FAIL if symbols outside seed or runtime list are not consistently exposed.

- [ ] **Step 3: Finalize symbol approval persistence**

Keep and verify `app/db/database.py` approval flow like:

```python
def approve_symbol(symbol: str, ib_client=None) -> None:
    sym = symbol.upper()
    conn = get_connection()
    conn.execute(
        """INSERT OR IGNORE INTO symbol_config
           (symbol, extra_indicators, approved, proposed_by, created_at,
            sec_type, exchange, currency, market_key)
           VALUES (?, '[]', 0, 'dashboard', ?, 'STK', 'SMART', 'USD', 'STK_US')""",
        (sym, datetime.utcnow().isoformat())
    )
    conn.execute("UPDATE symbol_config SET approved=1 WHERE symbol=?", (sym,))
    conn.commit()
    conn.close()
```

- [ ] **Step 4: Remove endpoint behavior that depends on the legacy static list**

Update `app/api/main.py`:

```python
@app.get("/price/{symbol}")
def get_price(symbol: str):
    symbol = symbol.upper()
    if symbol not in set(get_approved_symbols()):
        raise HTTPException(status_code=403, detail=f"Symbol {symbol} not allowed")
```

Update `/backtest/{symbol}` similarly:

```python
if symbol not in set(get_approved_symbols()):
    raise HTTPException(status_code=403, detail=f"Symbol {symbol} not in approved DB list")
```

Update `/symbols/approve/{symbol}` to stop mutating `ALLOWED_SYMBOLS` as primary behavior:

```python
approve_symbol(symbol, ib_client=client if client and client.ib.isConnected() else None)
return {"status": "approved", "symbol": symbol, "message": f"{symbol} approved in DB universe."}
```

- [ ] **Step 5: Ensure `/simbolos` uses the same DB-backed payload**

Keep `telegram_bot.py` on `/allowed-symbols` and verify formatting remains:

```python
data = _api("get", "/allowed-symbols")
symbols = data.get("symbols", [])
meta = data.get("meta", [])
```

- [ ] **Step 6: Re-run tests**

Run: `pytest tests/db/test_database.py tests/api/test_main_extended.py -k "approve_symbol or allowed_symbols or backtest" -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/db/database.py app/api/main.py app/notifications/telegram_bot.py tests/db/test_database.py tests/api/test_main_extended.py
git commit -m "fix: unify approved symbol flow around DB-backed universe"
```

---

### Task 3: Make Dashboard Data Contract Accurate And DB-First

**Files:**
- Modify: `app/api/main.py`
- Test: `tests/api/test_main_extended.py`

- [ ] **Step 1: Write failing tests for dashboard payload realism**

```python
def test_dashboard_data_includes_position_snapshots_and_open_trade_runtime_fields():
    resp = client.get("/dashboard/data")
    data = resp.json()
    assert "position_snapshots" in data
    assert "current_price" in data["open_trades"][0]
    assert "pnl_usd" in data["open_trades"][0]


def test_dashboard_data_sorts_open_symbols_first_in_universe():
    assert data["symbols_universe"][0]["symbol"] == "AAOI"
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest tests/api/test_main_extended.py -k "dashboard_data" -v`
Expected: FAIL showing missing or inconsistent dashboard contract fields.

- [ ] **Step 3: Ensure `/dashboard/data` returns the fields the frontend actually consumes**

In `app/api/main.py`, enrich `trades_out`:

```python
trades_out = [{
    "id": t.id,
    "trade_id": t.id,
    "symbol": t.symbol,
    "action": t.action,
    "quantity": t.quantity,
    "entry_price": t.entry_fill_price or t.entry_price,
    "stop_loss_price": t.stop_loss_price,
    "take_profit_price": t.take_profit_price,
    "signal_strength": t.signal_strength,
    "opened_at": ...,
} for t in open_trades]
```

After applying snapshots:

```python
position_snapshots_out = list(pos_snaps.values()) if pos_snaps else []
```

Return payload:

```python
return {
    "status": status,
    "open_trades": trades_out,
    "position_snapshots": position_snapshots_out,
    ...
}
```

- [ ] **Step 4: Make dashboard status DB-first where possible**

Keep current live-account fallback only as temporary compatibility, but explicitly prefer snapshots for dashboard display values:

```python
if account_history:
    latest_account = account_history[-1]
else:
    latest_account = {
        "net_liquidation": round(_nl, 2),
        "buying_power": round(_bp, 2),
    }
```

- [ ] **Step 5: Sort `symbols_universe` for operator relevance**

```python
open_symbols = {t.symbol for t in open_trades}
...
symbols_universe.append({
    ...
    "is_open": sym in open_symbols,
})
symbols_universe.sort(key=lambda item: (not item["is_open"], item["symbol"]))
```

- [ ] **Step 6: Re-run tests**

Run: `pytest tests/api/test_main_extended.py -k "dashboard_data" -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/api/main.py tests/api/test_main_extended.py
git commit -m "fix: stabilize dashboard data contract for DB-first live dashboard rendering"
```

---

### Task 4: Ensure Reconciled And Open Positions Produce Fresh Snapshot Data

**Files:**
- Modify: `app/positions/manager.py`
- Modify: `app/api/main.py`
- Test: `tests/positions/test_manager.py`
- Test: `tests/api/test_main_extended.py`

- [ ] **Step 1: Write failing tests for reconciled/open position snapshot coverage**

```python
def test_check_positions_writes_snapshot_for_open_trade():
    check_positions()
    assert get_position_snapshots()[trade_id]["current_price"] == 228.16


def test_dashboard_open_position_uses_snapshot_price_not_entry_price():
    assert data["open_trades"][0]["current_price"] == 228.16
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/positions/test_manager.py tests/api/test_main_extended.py -k "snapshot or current_price" -v`
Expected: FAIL when open trades cannot obtain snapshot-backed prices reliably.

- [ ] **Step 3: Remove approval-list dependency from price resolution path used by position monitoring**

Change `_get_current_price()` in `app/positions/manager.py`:

```python
def _get_current_price(symbol: str) -> float | None:
    try:
        return httpx.get(f"{API_BASE}/price/free/{symbol}", timeout=15).json().get("market_price")
    except Exception as e:
        logger.error(f"Could not fetch price for {symbol}: {e}")
        return None
```

This is necessary so reconciled or newly approved symbols can still be monitored before all caches and UI flows settle.

- [ ] **Step 4: Make trade close callbacks and UI ids consistent**

Confirm `trade_id` is used everywhere:

```python
"trade_id": t.id
```

And any client-facing close request uses the same field.

- [ ] **Step 5: Re-run tests**

Run: `pytest tests/positions/test_manager.py tests/api/test_main_extended.py -k "snapshot or current_price" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/positions/manager.py app/api/main.py tests/positions/test_manager.py tests/api/test_main_extended.py
git commit -m "fix: keep reconciled open positions monitored through snapshot-backed free price path"
```

---

### Task 5: Complete LD-005 Frontend Behavior For Real Users

**Files:**
- Modify: `app/api/dashboard.py`
- Modify: `app/api/main.py`
- Modify: `app/analysis/data.py`
- Test: `tests/api/test_main_extended.py`

- [ ] **Step 1: Write failing tests for LD-005 contract coverage**

```python
def test_dashboard_html_references_position_snapshots_and_open_trade_fields():
    html = render_dashboard_html()
    assert "position_snapshots" in html
    assert "trade_id || t.id" in html or "current_price" in html


def test_dashboard_symbol_endpoint_is_available():
    resp = client.get("/dashboard/symbol/AAPL?period=intraday")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests and verify failure where behavior is inconsistent**

Run: `pytest tests/api/test_main_extended.py -k "dashboard_html or dashboard_symbol" -v`
Expected: FAIL if the frontend still assumes missing payload fields or stale semantics.

- [ ] **Step 3: Fix the P&L and snapshot usage in the React dashboard**

In `app/api/dashboard.py`, update:

```jsx
<div className="ss">{f.pct(pct)} · drawdown</div>
```

And:

```jsx
const snap = snapshots.find(s => s.trade_id === (t.trade_id || t.id)) || {};
const currentPrice = snap.current_price || t.current_price || t.entry_price;
const pnlUsd = parseFloat(snap.pnl_usd != null ? snap.pnl_usd : (t.pnl_usd || 0));
const pnlPct = parseFloat(snap.pnl_pct != null ? snap.pnl_pct : (t.pnl_pct || 0));
```

- [ ] **Step 4: Make `Mi Universo` operationally meaningful**

In `app/api/dashboard.py`, add open badge:

```jsx
{s.is_open && <span ...>OPEN</span>}
```

For recalibration UX, replace false-positive alert with background-state language only after backend supports it:

```jsx
alert(`Recalibración solicitada para ${symbol}. Revisa logs/Telegram para confirmación real.`);
```

- [ ] **Step 5: Align chart cache to the spec**

In `app/analysis/data.py`, reduce scanner/on-demand caching used by dashboard symbol chart to 300 seconds through either:

```python
TTL = {
    ...
    "dashboard_chart": 300,
}
```

and call:

```python
df = data_layer.get_ohlcv(symbol, "1 D", "5 mins", "dashboard_chart")
```

Do the same for the daily chart path.

- [ ] **Step 6: Re-run tests**

Run: `pytest tests/api/test_main_extended.py -k "dashboard_html or dashboard_symbol" -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/api/dashboard.py app/api/main.py app/analysis/data.py tests/api/test_main_extended.py
git commit -m "fix: complete LD-005 dashboard frontend behavior with real snapshot and chart semantics"
```

---

### Task 6: Make Market Trends Actionable Instead Of Placeholder Data

**Files:**
- Modify: `app/scanner/market_scanner.py`
- Modify: `app/api/dashboard.py`
- Test: `tests/scanner/test_market_scanner.py`

- [ ] **Step 1: Write failing tests for scanner row usefulness**

```python
def test_fetch_and_cache_scanner_populates_change_and_volume_fields():
    fetch_and_cache_scanner(data_layer)
    rows = get_scanner_results("gainers")
    assert rows[0]["change_pct"] is not None
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/scanner/test_market_scanner.py -k "scanner" -v`
Expected: FAIL because `change_pct` and `volume_ratio` are currently stored as `None`.

- [ ] **Step 3: Enrich scanner fetch results**

Update `app/scanner/market_scanner.py` so each symbol gets lightweight indicator enrichment:

```python
df = data_layer.get_ohlcv(symbol, "2 D", "1 day", "dashboard_chart")
ind = data_layer.get_indicators(symbol)
change_pct = round((curr - prev) / prev * 100, 2) if prev > 0 else None
volume_ratio = ind.get("volume_ratio")
```

Store:

```python
{
    "symbol": symbol,
    "name": "",
    "change_pct": change_pct,
    "volume_ratio": volume_ratio,
    "extra_json": "{}",
}
```

- [ ] **Step 4: Keep frontend empty states honest**

In `app/api/dashboard.py`, if `change_pct` or `volume_ratio` is missing, render `—` rather than `0.0%` / `0.0×`.

```jsx
const pctText = r.change_pct == null ? '—' : `${pct>=0?'+':''}${pct.toFixed(1)}%`;
const vrText = r.volume_ratio == null ? '—' : `${vr.toFixed(1)}×`;
```

- [ ] **Step 5: Re-run tests**

Run: `pytest tests/scanner/test_market_scanner.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/scanner/market_scanner.py app/api/dashboard.py tests/scanner/test_market_scanner.py
git commit -m "fix: populate market trends with actionable scanner metrics"
```

---

### Task 7: End-To-End Verification And Operational Rollout

**Files:**
- Modify: `.claude/current-dev-issues/LD-005-dashboard-frontend-b.md`
- Modify: `docs/superpowers/specs/2026-05-13-live-dashboard-design.md` if behavior was intentionally changed

- [ ] **Step 1: Run API and focused regression tests**

Run:

```bash
pytest tests/api/ tests/db/ tests/system/ tests/scanner/ tests/positions/ -q
```

Expected: PASS

- [ ] **Step 2: Run syntax safety check**

Run:

```bash
python -m compileall app run.py
```

Expected: no syntax errors

- [ ] **Step 3: Verify live dashboard manually**

Run and check:

```bash
curl http://127.0.0.1:8088/dashboard/data
```

Expected:
- `status.mode` matches runtime
- `open_trades[*].current_price` present when snapshots exist
- `symbols_universe[0].is_open == true` for current open symbol
- `position_snapshots` present

- [ ] **Step 4: Verify browser acceptance criteria**

Manual browser checklist:

```text
1. Open /dashboard
2. Confirm status bar online/offline state
3. Confirm P&L Today percentage is plausible
4. Confirm open-position card ACTUAL != ENTRY when market moved
5. Confirm "Mi Universo" shows current open symbol at top with OPEN badge
6. Click ↻ Recal. and confirm background log/Telegram signal
7. Confirm News defaults to Mi universo
8. Confirm all 6 Market Trends tabs render with meaningful values or honest empty states
9. Turn IB Gateway offline and confirm Close/Pause actions disable cleanly
```

- [ ] **Step 5: Update issue tracking**

Move/mark `LD-005-dashboard-frontend-b.md` only when all of these are true:

```text
- UI behavior matches actual backend behavior
- Recalibration path is real, not just visual
- Scanner tabs carry user-meaningful data
- Approved symbols are consistent across dashboard, bot, and backtest
```

- [ ] **Step 6: Commit**

```bash
git add .claude/current-dev-issues/LD-005-dashboard-frontend-b.md docs/superpowers/specs/2026-05-13-live-dashboard-design.md
git commit -m "docs: close dashboard stabilization plan with verified LD-005 behavior"
```

---

## Spec Coverage Check

- Live/paper port and runtime-mode consistency: covered by Task 1
- DB as symbol source of truth and approval visibility: covered by Task 2
- Dashboard contract, snapshots, realistic status fields: covered by Task 3
- Open-position freshness and reconciled trades: covered by Task 4
- LD-005 frontend B behavior and chart cache alignment: covered by Task 5
- Market Trends usefulness: covered by Task 6
- Verification, rollout, and issue closure: covered by Task 7

## Placeholder Scan

- No `TODO` or `TBD`
- All tasks include concrete files, commands, and expected results
- Behavior changes are tied to specific modules already in this repo

## Type Consistency Check

- `trade_id` is the user-facing identifier for dashboard position actions
- `symbols_universe[*].is_open` is the sorting/display flag
- `position_snapshots` remains a list payload for frontend consumption
- DB-approved symbols are the authoritative universe for dashboard, bot, and backtest checks

---

Plan complete and saved to `docs/superpowers/plans/2026-05-13-live-dashboard-stabilization.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
