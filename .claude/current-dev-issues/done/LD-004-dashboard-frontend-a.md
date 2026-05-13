# Issue LD-004: Dashboard Frontend Part A — Header, Stats, Positions, Account Charts

**Module**: live-dashboard
**Type**: AFK
**Effort**: M
**Blocked by**: LD-003
**Requires review**: false

---

## WHY

The current dashboard is a minimal dark-theme table. After LD-003 the endpoint returns
rich data — now the frontend needs to display it. Part A covers the top half of the
dashboard: the IB status bar, header with controls, stat cards, open positions with live
P&L and R/R visualization, and the Mi Cuenta 4-tab chart card. These are the sections
Frank checks first during market hours.

**Success signal**: Dashboard loads, shows IB Gateway status, displays live P&L per
position with color-coded R/R bar, and the equity curve chart renders from account_history data.

---

## WHO

| Persona | Role | Device | Goal |
|---------|------|--------|------|
| Frank Trader | Trader | Mobile (Tailscale) | Quick status check, position monitoring |

---

## WHAT — Constraints

- [ ] Full rewrite of `app/api/dashboard.py` — only `render_dashboard_html()` signature kept
- [ ] React via CDN — no build step, no npm
- [ ] All charts as inline SVG generated from data arrays — no Chart.js/D3
- [ ] Dark/light mode via CSS variables, toggled with localStorage persistence
- [ ] Smart refresh: 15s if `open_trades.length > 0`, else 60s
- [ ] Responsive: single column on mobile (<640px), 2-column grid on desktop

---

## HOW

Rewrite `app/api/dashboard.py` keeping `render_dashboard_html()` signature.

**Sections in Part A:**

### IB Status Bar
```jsx
function IbStatusBar({ connected }) {
  return (
    <div className={`ib-bar ${connected ? 'online' : 'offline'}`}>
      <span className="ib-dot" />
      <span className="ib-status">
        {connected ? 'IB Gateway · connected' : 'IB Gateway · offline'}
      </span>
      {!connected && (
        <span className="ib-warn">⚡ critical actions blocked</span>
      )}
      <span className="ib-cache" id="last-refresh">—</span>
    </div>
  );
}
```

### Header
- Logo "IBKR AI TRADER" (Bebas Neue)
- PAPER/LIVE badge
- Pause/Resume button (disabled when IB offline)
- Dark/light toggle (saves to localStorage)
- Countdown ring SVG that counts down 15s or 60s

### Stat Cards (4)
- Net Liquidation from `latest_account.net_liquidation` (or status.operating_capital fallback)
- P&L Today from `status.daily_pnl_usd` + **drawdown gauge**: mini bar showing current drawdown % vs 5%/10%/15% thresholds (from `status` — need to add `drawdown_pct` to endpoint)
- Buying Power from `latest_account.buying_power`
- Positions count

### Open Positions Card
Per position:
```jsx
// R/R visual bar between SL and TP
function RRBar({ entry, current, sl, tp, action }) {
  const range = Math.abs(tp - sl);
  if (range === 0) return null;
  const pos = action === 'BUY'
    ? (current - sl) / range
    : (sl - current) / range;
  const pct = Math.max(0, Math.min(100, pos * 100));
  return (
    <div style={{position:'relative', height:8, borderRadius:4,
      background:'linear-gradient(to right, rgba(244,63,94,.3), rgba(16,185,129,.3))'}}>
      <div style={{position:'absolute', left:`${pct}%`, top:-2,
        width:4, height:12, background:'var(--text)', borderRadius:2}} />
    </div>
  );
}
```

Earnings badge:
```jsx
{earnings_warnings[t.symbol] !== undefined && (
  <span className="earn-chip">⚠ Earnings in {earnings_warnings[t.symbol]}d</span>
)}
```

### Mi Cuenta — 4 tab card

**Tab 1: Equity 30d** (default)
SVG combo chart: blue line for `net_liquidation` over dates + green/red daily P&L bars.
Data source: `account_history` array from endpoint.

```jsx
function EquityChart({ history }) {
  if (!history?.length) return <Empty msg="// sin historial de cuenta aún" />;
  const vals = history.map(h => h.net_liquidation);
  const min = Math.min(...vals), max = Math.max(...vals);
  const range = max - min || 1;
  const w = 420, h = 130;
  const points = history.map((h, i) => {
    const x = (i / (history.length - 1)) * w;
    const y = h - ((h.net_liquidation - min) / range) * (h - 20) + 10;
    return `${x},${y}`;
  }).join(' ');
  // ... render polyline + bars
}
```

**Tab 2: Semanal** — group `account_history` by ISO week, sum daily_pnl_usd per week, render bars

**Tab 3: Exits** — aggregate `closed_trades` by exit_reason, render horizontal bars

**Tab 4: Horas** — aggregate `closed_trades` by `opened_at` hour, avg pnl per hour, render bars

---

## Code Search

- [x] `app/api/dashboard.py:1-519` — current React dashboard structure confirmed
- [x] Existing components to port: `Badge`, `TrendChip`, `Card`, `StatCard`, `Empty` — keep patterns
- [x] Existing `f` formatters and CSS variables — keep as-is

**Reuse decision**:
- Port existing `Badge`, `Card`, `Empty`, `f` formatters unchanged
- Reuse CSS variable token system for dark/light mode
- Reuse `render_dashboard_html()` function signature (returns str)

---

## Reference Documents

| Document | Path |
|----------|------|
| Spec | `docs/superpowers/specs/2026-05-13-live-dashboard-design.md` — Sections 1, 2, 3 |
| Mockup | `.superpowers/brainstorm/*/content/full-dashboard.html` |

---

## Acceptance Criteria

- [ ] AC-01: IB status bar shows green/red based on `ib_connected` field
- [ ] AC-02: Positions card shows `pnl_usd` and `pnl_pct` from snapshot data
- [ ] AC-03: R/R bar renders for each open position (position between SL and TP)
- [ ] AC-04: Earnings badge appears when `earnings_warnings[symbol]` exists
- [ ] AC-05: Equity chart renders when `account_history` has ≥2 entries
- [ ] AC-06: Smart refresh: 15s with open positions, 60s without (verify by watching countdown)
- [ ] AC-07: Dark/light toggle works and persists across refresh (localStorage)
- [ ] AC-08: Layout is single-column on 390px viewport
- [ ] AC-09: `pytest tests/api/` passes (no regressions)

## Definition of Done

- [ ] All ACs verified visually in browser on paper trading session
- [ ] Tested on mobile viewport (390px) and desktop (1200px)
- [ ] Issue moved to `done/`
