# Issue LD-005: Dashboard Frontend Part B — Symbol Chart, News, Trends, Mi Universo, Controls

**Module**: live-dashboard
**Type**: AFK
**Effort**: M
**Blocked by**: LD-004
**Requires review**: false

---

## WHY

Part A gave Frank the ability to monitor positions. Part B gives him market intelligence
and control: lazy symbol charts for any active symbol, news filtered to his universe,
market trends scanner with sector performance and implied move, the Mi Universo table
showing calibration status per symbol, and the system control bar.

**Success signal**: Frank selects AAPL from the symbol chips and sees the intraday 5min
chart load. The News card defaults to "Mi universo" tab with the latest articles. Market
Trends shows 6 populated tabs. Mi Universo table lists all approved symbols with
backtest_calibrated badge and win rate.

---

## WHO

| Persona | Role | Device | Goal |
|---------|------|--------|------|
| Frank Trader | Trader | Mobile + Desktop | Market discovery, system control |

---

## WHAT — Constraints

- [ ] Symbol chart is **lazy** — only calls `/price/{symbol}/chart` when user selects a symbol
- [ ] Symbol chart cached for 5 minutes on the server side
- [ ] News tab defaults to "Mi universo" (not "Todas")
- [ ] Market Trends has exactly 6 tabs: Más activos, Top Movers, Gainers, Losers, Sectores, Implied Move
- [ ] Mi Universo table: "Recalibrar" button calls `POST /symbols/approve/{symbol}` (triggers background calibration)
- [ ] Close position button disabled + tooltip when `ib_connected === false`
- [ ] All SVG charts, no external chart libraries

---

## HOW

### New API endpoint for lazy symbol chart

Add to `app/api/main.py`:
```python
@app.get("/dashboard/symbol/{symbol}")
def dashboard_symbol_chart(symbol: str, period: str = "intraday"):
    """Lazy-loaded symbol data for dashboard chart. Cached 5min."""
    try:
        data_layer = get_data_layer()
        result = {"symbol": symbol.upper(), "period": period}
        if period == "intraday":
            df = data_layer.get_ohlcv(symbol, "1 D", "5 mins", "scanner")
        else:  # daily
            df = data_layer.get_ohlcv(symbol, "30 D", "1 day", "scanner")
        if df is not None and len(df) > 0:
            result["bars"] = [
                {"close": float(r["close"]),
                 "volume": int(r.get("volume", 0))}
                for _, r in df.iterrows()
            ]
        else:
            result["bars"] = []
        # Indicators for "indicators" tab
        if period == "indicators":
            from app.analysis.indicators import compute_features
            fs = compute_features(symbol, df) if df is not None else None
            if fs:
                result["rsi_14"] = fs.rsi_14
                result["macd_line"] = fs.macd_line
                result["bollinger_position"] = fs.bollinger_position
                result["volume_ratio_20d"] = fs.volume_ratio_20d
        return result
    except Exception as e:
        return {"symbol": symbol, "bars": [], "error": str(e)}
```

### Frontend sections

**Symbol Chart (lazy)**
```jsx
function SymbolCard({ openTrades, signals, ibConnected }) {
  const [selected, setSelected] = useState(null);
  const [chartData, setChartData] = useState(null);
  const [tab, setTab] = useState('intraday');

  const chips = [
    ...openTrades.map(t => t.symbol),
    ...signals.slice(0,3).map(s => s.symbol)
  ].filter((v,i,a) => a.indexOf(v)===i).slice(0,6);

  async function loadChart(sym, period) {
    const res = await fetch(`/dashboard/symbol/${sym}?period=${period}`);
    setChartData(await res.json());
  }

  function selectSym(sym) {
    setSelected(sym);
    loadChart(sym, tab);
  }
  // ... render chips, tabs, SVG chart
}
```

SVG line chart built from `chartData.bars` array — normalize to SVG viewBox, draw polyline.

**News Card (3 tabs, default: Mi universo)**
```jsx
function NewsCard({ news, approvedSymbols, openTrades }) {
  const [tab, setTab] = useState('universe');  // ← default

  const filtered = {
    all: news,
    universe: news.filter(n => approvedSymbols.includes(n.symbol)),
    positions: news.filter(n => openTrades.some(t => t.symbol === n.symbol)),
  };
  // ... render
}
```

**Market Trends (6 tabs)**
```jsx
function MarketTrendsCard({ scanner }) {
  const [tab, setTab] = useState('most_active');

  // Sector tab: bars from scanner.sector
  // Implied move tab: bars from scanner.implied_move with amber/green color based on value

  async function addSymbol(symbol) {
    await fetch(`/symbols/propose/${symbol}`, {method:'POST',
      body: JSON.stringify({reason: 'Added from Market Trends dashboard'}),
      headers: {'Content-Type':'application/json'}});
    // Show "propuesto ✓" feedback
  }
  // ... render 6 tabs
}
```

**Mi Universo Table**
```jsx
function UniverseTable({ symbolsUniverse }) {
  async function recalibrate(symbol) {
    await fetch(`/symbols/approve/${symbol}`, {method:'POST'});
    // Show "calibrando..." state on that row
  }

  return (
    <table>
      <thead><tr>
        <th>SYM</th><th>CALIBRADO</th><th>SL%</th><th>TP%</th>
        <th>PF</th><th>WIN RATE</th><th>TRADES</th>
        <th>APRENDIZAJE</th><th>ÚLTIMA CAL.</th><th></th>
      </tr></thead>
      <tbody>
        {symbolsUniverse.map(s => (
          <tr key={s.symbol}>
            <td className="sym">{s.symbol}</td>
            <td>{s.backtest_calibrated
              ? <span className="badge-calibrated">✓ backtest</span>
              : <span className="badge-defaults">defaults</span>}
            </td>
            <td>{(s.stop_loss_pct * 100).toFixed(1)}%</td>
            <td>{(s.take_profit_pct * 100).toFixed(1)}%</td>
            <td>{s.backtest_profit_factor?.toFixed(2) || '—'}</td>
            <td style={{color: s.win_rate >= 0.5 ? 'var(--green)' : 'var(--red)'}}>
              {s.win_rate != null ? `${(s.win_rate*100).toFixed(0)}%` : '—'}
            </td>
            <td>{s.trade_count}</td>
            <td>{Object.entries(s.multipliers_drifted || {}).map(([k,v]) =>
              <span key={k} className={v>1?'mult-up':'mult-down'}>
                {k.slice(0,3)} {v>1?'▲':'▼'}{v.toFixed(2)}
              </span>
            )}</td>
            <td>{s.backtest_calibrated_at?.slice(0,10) || '—'}</td>
            <td><button onClick={() => recalibrate(s.symbol)}>↻ Recal.</button></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

**System Control Bar**
- Scanner toggle: `POST /system/pause` or `POST /system/resume` — disabled if `!ibConnected`
- Notification level: `POST /notifications/level/{level}` — no confirmation needed
- Mode badge (read-only)
- Hint about Telegram confirmation

---

## Code Search

- [x] `app/api/main.py` — `GET /price/{symbol}` endpoint pattern to follow for new chart endpoint
- [x] `app/analysis/data.py:77` — `get_ohlcv()` confirmed for intraday/daily
- [x] `app/analysis/indicators.py:176` — `compute_features()` for indicators tab

**Reuse decision**:
- `GET /symbols/propose/{symbol}` — check if exists, create if not (for "+ añadir" button)
- `GET /system/pause` and `/system/resume` — already exist in main.py

---

## Reference Documents

| Document | Path |
|----------|------|
| Spec | `docs/superpowers/specs/2026-05-13-live-dashboard-design.md` — Sections 4-10 |
| Mockup | `.superpowers/brainstorm/*/content/full-dashboard.html` |
| News/Trends mockup | `.superpowers/brainstorm/*/content/news-trends.html` |

---

## Acceptance Criteria

- [ ] AC-01: Selecting AAPL chip loads intraday chart within 2s (IBKR connected)
- [ ] AC-02: Symbol chart shows SL and TP lines when symbol is an open position
- [ ] AC-03: News card defaults to "Mi universo" tab on load
- [ ] AC-04: Market Trends shows 6 populated tabs (uses `scanner` data from endpoint)
- [ ] AC-05: Sector tab shows bars for XLK, XLF, XLE, XLV, XLY, XLI
- [ ] AC-06: Mi Universo table lists all approved symbols; calibrated ones show green ✓ badge
- [ ] AC-07: "Recalibrar" button triggers calibration (confirm in Telegram message or background job log)
- [ ] AC-08: Close position button shows disabled tooltip when `ib_connected === false`
- [ ] AC-09: "+ añadir" in scanner proposes symbol to bot (visible in Telegram or DB)
- [ ] AC-10: `pytest tests/api/` passes

## Definition of Done

- [ ] All ACs verified in browser
- [ ] Tested with IB Gateway offline (all sections show cached data, actions disabled)
- [ ] Tested with no data in DB (new install) — all sections show empty state messages
- [ ] Issue moved to `done/`
