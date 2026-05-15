# Architecture Backlog: IBKR AI Trader

**Last Updated**: 2026-05-15
**Module Health**: 7.7/10 — solid hexagonal skeleton; main work is eliminating legacy coupling

---

## Sprint 2 — Do Next (High Value)

### S2-01: Wire `ILLMPort` into the Container

**Why**: `ILLMPort` is defined and `OpenCodeAdapter` implements it, but the container never injects it. Every LLM-dependent module either bypasses the port or imports `llm/agent.py` directly — untestable without subprocess.
**Effort**: S (2–3 hours)
**Risk**: LOW — additive
**How**:
```python
# container.py
from app.infrastructure.llm.opencode_adapter import OpenCodeAdapter
self.llm = OpenCodeAdapter()
```
Then update `PlaceOrderUseCase` and `ClosePositionUseCase` to accept `llm: ILLMPort` parameter.

### S2-02: Replace top-5 direct `notify()` imports with container notifier

**Why**: 30+ files still import `from app.notifications.telegram import notify` directly. Bypasses `INotificationPort`, defeats the abstraction, makes modules untestable.
**Top-5 callsites**: `alerts/manager.py` (done ✓), `analysis/admission.py`, `bootstrap/runner.py`, `api/main.py`, `positions/manager.py`
**Effort**: M (1–2 hours for top 5)
**How**: Pass `notifier: INotificationPort` from container into each module's entry point.

### S2-03: Add analysis lifecycle domain events

**Why**: `AnalysisPipeline` runs 5 steps and publishes 0 events. No audit trail, no graceful pause.
**Events to add** (in `app/domain/trading/events.py`):
- `AnalysisStarted(symbol, mode)`
- `AnalysisStepCompleted(symbol, step, elapsed_ms)`
- `AnalysisCompleted(symbol, recommendation, elapsed_seconds)`
- `AnalysisFailed(symbol, step, error)`
**Note**: Requires `EventBus.unsubscribe()` before subscribing per-pipeline handlers.

### S2-04: Tests for EventBus and use cases

**Why**: New EventBus, `ChangeTradingModeUseCase`, `PauseSystemUseCase`, `PlaceOrderUseCase`, `ClosePositionUseCase` — none have dedicated tests.
**Files to create**: `tests/test_event_bus.py`, `tests/test_use_cases.py`
**Edge cases for EventBus**: handler throws, multiple handlers for same event, handler order.

### S2-05: Add `EventBus.unsubscribe()` support

**Why**: Without unsubscribe, handlers registered inside per-request or per-pipeline scopes leak indefinitely (memory + slow publishes). See `DECISIONS.md DEC-005`.
**Effort**: XS (30 min)
**How**: `handlers[event_type].remove(handler)` with `ValueError` guard.

---

## Quarter Backlog — Structural Cleanup

### Q1-01: Split `app/infrastructure/db/compat.py` (1447 lines)

**Why**: Doing three unrelated jobs — migration logic, seed data, legacy wrappers.
**How**:
1. Extract seed data → `app/infrastructure/db/seeds.py`
2. Mark each function `# deprecated — use XRepository instead`
3. Extract to `SymbolRepository`, `TradeRepository`, `PatternRepository` incrementally
**Effort**: L (6–8 hours) — many consumers, must be incremental

### Q1-02: Inject `ISystemStateRepository` into `RiskService`

**Why**: `RiskService` reads config with hardcoded defaults and cannot react to live control plane changes.
**Impact**: Makes control plane risk parameter changes take effect without restart.
**Effort**: M (3–4 hours)

### Q1-03: Abstract IBKR preflight/dedup out of use cases

**Why**: `PlaceOrderUseCase` imports `app.ibkr.client` directly for dedup — bypasses `IBrokerPort`.
**How**: Add `get_open_orders() -> list[str]` to `IBrokerPort`, implement in adapter.
**Effort**: M (3–4 hours)

### Q1-04: `ChangeTradingModeUseCase` — add `confirmed` parameter

**Why**: Use case blocks if open positions exist, with no UI path to override (comment in `change_mode.py:58-60`).
**When**: Build after control plane UI adds a confirmation dialog.
**Effort**: S (1–2 hours)

### Q1-05: Move `test_container()` out of `app/container.py`

**Why**: Test helper living in production code; `app/` → `tests/` import inversion.
**How**: Move to `tests/conftest.py` as a pytest fixture.
**Effort**: XS (30 min)

---

## Monitor — No Action Needed Now

### M-01: Synchronous EventBus in APScheduler threads

**Risk**: Slow event handler (e.g., SQLite write) blocks the scheduler thread that published the event.
**Current state**: Fine at single-user Pi load. Will degrade if multiple events fire simultaneously during market open.
**Action threshold**: Scheduler job latency > 500ms on Pi, or > 5 event handlers registered.
**How to monitor**: Add `time.perf_counter()` around `event_bus.publish()` calls; log if > 100ms.

### M-02: `compat.py` datetime.utcnow() deprecation

**Risk**: Python 3.14 will remove `datetime.utcnow()`. Currently 8 deprecation warnings per test run.
**Action threshold**: Before upgrading Python beyond 3.13.
**Fix**: Find-replace `datetime.utcnow()` → `datetime.now(timezone.utc)` in `compat.py`.

### M-03: `get_deduplicator()` thin delegate

**Risk**: If `get_container()` is called before container is initialized (e.g., import-time), it will bootstrap a production container unexpectedly.
**Current state**: Not a problem — only called from `LLMSignalProcessor._execute_order()` at runtime.
**Action**: Migrate all 4+ call sites to use `container.order_deduplicator` directly, then delete `get_deduplicator()`.

---

## Completed Improvements (Sprint 1)

| Item | Done | What |
|------|------|------|
| Fix `test_symbol_config_migration.py` stale import | ✓ | Deleted — superseded by Alembic |
| Remove `httpx` self-call in `pipeline._score()` | ✓ | Now uses `broker.get_portfolio()` |
| `AlertManager` class-based DI | ✓ | `alerts/manager.py` fully refactored |
| `LLMSignalProcessor` class-based DI | ✓ | `llm/loop.py` fully refactored |
| `OrderDeduplicator` into Container | ✓ | Thread-unsafe singleton eliminated |
| `IBrokerPort.get_prev_close()` | ✓ | Added to fix alert pct_change regression |
| 9 Container wiring tests | ✓ | `tests/test_container_wiring.py` |
