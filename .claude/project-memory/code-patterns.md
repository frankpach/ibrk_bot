# Code Patterns

## Pattern: Jobs-write, endpoint-reads (live-dashboard)

APScheduler jobs persist data to SQLite; API endpoints only SELECT. Zero IBKR calls from HTTP handlers.

```python
# scheduler job writes:
def _save_position_snapshots(ib_client, trades):
    for trade in trades:
        price = ib_client.get_price(trade.symbol)
        db.insert_position_snapshot(trade.id, price, unrealized_pnl=...)

# endpoint only reads:
@app.get("/dashboard/data")
def dashboard_data():
    return {
        "positions": db.get_position_snapshots(),
        "account": db.get_account_history(days=30),
        ...
    }
```

**Why**: IBKR single-session constraint. Mobile app opens → gateway disconnects → cached data always available.

---

## Pattern: Optional ib_client injection (learning cycle)

Pass `ib_client=None` to modules that optionally need the IB connection, rather than importing the global singleton.

```python
def run_learning_cycle(ib_client=None):
    if ib_client is None:
        return  # skip gracefully
    ...
```

**Why**: Avoids circular imports; testable with `run_learning_cycle(ib_client=mock_client)`.

---

## Pattern: SVG charts generated in React from data arrays (no library)

```jsx
const LineChart = ({ data, width, height }) => {
  const points = data.map((v, i) => `${(i / data.length) * width},${height - (v / max) * height}`).join(' ');
  return <svg width={width} height={height}><polyline points={points} fill="none" stroke="#3b82f6"/></svg>;
};
```

**Why**: Pi 5 ARM + Tailscale mobile. External chart libs (Chart.js ~200KB) cause unacceptable load times.

---

## Pattern: Telegram confirmation for destructive UI actions

Dashboard buttons for close-position and pause-scanner send a Telegram inline keyboard request. Only the owner can confirm (`@_only_owner` decorator).

**Why**: Avoids PIN management on the web; leverages existing security model; creates audit trail in Telegram chat.

---

## Pattern: Smart dashboard refresh interval

```javascript
const refreshInterval = openPositions.length > 0 ? 15000 : 60000;
```

**Why**: Saves Pi CPU and Tailscale bandwidth when no active positions require monitoring.
