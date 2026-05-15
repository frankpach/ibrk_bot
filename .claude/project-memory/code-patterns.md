# Code Patterns

## Pattern: Jobs-write, endpoint-reads (live-dashboard)

APScheduler jobs persist data to SQLite; API endpoints only SELECT. Zero IBKR calls from HTTP handlers.

## Pattern: DI Container Access — Always Lazy

Never call `get_container()` at module import time (circular imports). Always inside a function body:

```python
# WRONG — module top level
from app.container import get_container
_c = get_container()

# CORRECT — inside function
def process_pending_signals() -> None:
    from app.container import get_container
    c = get_container()
    LLMSignalProcessor(broker=c.broker, notifier=c.notifier, dedup=c.order_deduplicator).process_pending_signals()
```

## Pattern: Class-Based DI (no module globals)

No `_broker: IBrokerPort | None = None` globals, no `set_broker()` setters. Dependencies via constructor only. Module-level shim lazily accesses container:

```python
class AlertManager:
    def __init__(self, broker: IBrokerPort) -> None:
        self._broker = broker

def check_all_alerts(db_get_alerts, db_mark_triggered) -> None:
    from app.container import get_container
    get_container().alert_manager.check_all(db_get_alerts, db_mark_triggered)
```

## Pattern: test_container() for all tests

```python
from app.container import test_container

def test_something():
    c = test_container()  # MockBrokerAdapter, in-memory SQLite, fresh per call
    result = c.place_order_use_case.execute(...)
```

## Pattern: Domain Events — frozen dataclasses, register once

```python
# All events in app/domain/trading/events.py
@dataclass(frozen=True)
class TradingModeSwitched:
    old_mode: str
    new_mode: str
    changed_by: str
    occurred_at: datetime = field(default_factory=datetime.utcnow)

# Register ONLY in Container._register_event_handlers() — never per-request
self.event_bus.subscribe(TradingModeSwitched, audit_handler.handle)
```

## Pattern: Use Case structure

```python
class MyUseCase:
    def __init__(self, broker: IBrokerPort, notifier: INotificationPort, event_bus: EventBus):
        self._broker = broker
        self._notifier = notifier
        self._event_bus = event_bus

    def execute(self, ...) -> MyResult:
        # validate → call ports → publish event → return result
        self._event_bus.publish(SomethingHappened(...))
        return MyResult(success=True)
```

## Pattern: MockBrokerAdapter for tests

```python
from tests.mocks.mock_broker import MockBrokerAdapter
from decimal import Decimal

broker = MockBrokerAdapter(
    prices={"AAPL": Decimal("200.00")},
    prev_closes={"AAPL": Decimal("195.00")},  # added in Sprint 1
    portfolio=[],
)
```

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
