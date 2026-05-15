# Architecture Backlog: refactor (Hexagonal Architecture)

## Summary

- **Module complexity**: HIGH (175+ Python files, 981 tests, 1447-line compat layer)
- **Maintainability score**: 7/10 — clean skeleton, significant legacy drag
- **Scaling risk**: LOW (single-user trading system on Pi; no scaling pressure)
- **Reuse potential**: HIGH — ports/adapters pattern is directly reusable by all 35+ modules
- **Recommended next step**: Eliminate the 30+ direct `app.notifications.telegram` imports — highest coupling density, lowest effort

---

## Priority 1 — Do Next Sprint (3 improvements)

### Improvement 1: Fix broken test collection in `tests/db/test_symbol_config_migration.py`

**Why**: `from app.db import database` fails because `app/db/database.py` was removed/renamed during refactor. This prevents `pytest tests/` from completing cleanly and blocks CI green state.
**Impact**: Removes the one collection error; `pytest tests/` goes from "1 error" to clean.
**Effort**: XS (15 min) — update import to new module path or delete the test if superseded by Alembic migrations.
**Risk**: NONE
**How**: Check what `database.py` provided → update import to `app.infrastructure.db.compat` or `app.infrastructure.db.engine` as appropriate.

---

### Improvement 2: Wire `ILLMPort` into the Container

**Why**: `ILLMPort` is defined in `app/application/ports/llm_port.py` and `OpenCodeAdapter` implements it, but the container never injects it. Every module that needs LLM analysis either bypasses the port entirely (direct subprocess) or imports `app/llm/agent.py` directly.
**Impact**: Completes the third port in the hexagonal architecture; makes LLM calls testable via mock injection (same pattern as broker and notifier).
**Effort**: S (2–3 hours) — add `self.llm = ILLMPort or OpenCodeAdapter()` to container; update `PlaceOrderUseCase` and `ClosePositionUseCase` to accept `llm: ILLMPort` parameter.
**Risk**: LOW — additive change; existing direct imports still work during migration.
**How**:
```python
# container.py
from app.infrastructure.llm.opencode_adapter import OpenCodeAdapter
self.llm = llm or OpenCodeAdapter()

# place_order.py
class PlaceOrderUseCase:
    def __init__(self, broker, notifier, risk_service, llm: ILLMPort = None):
        self._llm = llm
```

---

### Improvement 3: Eliminate direct `app.notifications.telegram` imports from legacy modules (phased)

**Why**: 30+ files still import `from app.notifications.telegram import notify` directly, bypassing `INotificationPort`. This defeats the abstraction and means notifications can't be swapped, mocked, or throttled uniformly.
**Impact**: Every module using direct imports is untestable without network access; bugs in notification logic are duplicated across callsites.
**Effort**: M per module (1–2 hours total for a first pass covering the top 5 callsites: `alerts/`, `analysis/pipeline.py`, `bootstrap/`, `api/main.py`, `positions/manager.py`).
**Risk**: LOW — additive; direct imports still work, just get replaced one at a time.
**How**: Pass `notifier: INotificationPort` as a parameter from the container into each module's entry point; or expose `get_container().notifier` as a global accessor for legacy callsites.

---

## Priority 2 — Do in Next Quarter (3 improvements)

### Improvement 1: Split `app/infrastructure/db/compat.py` (1447 lines)

**Why**: `compat.py` is doing three unrelated jobs: (1) migration logic, (2) seed data initialization, (3) legacy function wrappers. At 1447 lines it is the largest single file in the project and a magnet for new tech debt.
**Impact**: Clarifies ownership; migration logic moves to Alembic; seed data becomes a fixture; legacy wrappers become deprecated and each gets a new-style replacement.
**Effort**: L (6–8 hours) — requires care to avoid breaking imports across 35+ modules.
**Risk**: MEDIUM — high number of consumers; must be done incrementally with aliases.
**How**:
  1. Extract `init_control_settings()` + seed data → `app/infrastructure/db/seeds.py`
  2. Extract `get_connection()` + raw SQL helpers → `app/infrastructure/db/legacy.py` (clearly marked deprecated)
  3. Convert migration helpers to proper Alembic migration scripts
  4. Add `# deprecated` comments to each function in the remnant `compat.py`

---

### Improvement 2: Inject `ISystemStateRepository` into `RiskService`

**Why**: `RiskService` reads config with hardcoded defaults and cannot react to live changes (`UpdateControlSettingUseCase` explicitly notes this in a comment). If the user changes `max_position_size` via the control plane, `RiskService` won't see the change until restart.
**Impact**: Enables live hot-reload of risk parameters — a core value proposition of the control plane.
**Effort**: M (3–4 hours) — define `ISystemStateRepository` port, implement via `compat.get_control_settings()`, inject into `RiskService` and `Container`.
**Risk**: LOW — purely additive; existing behavior is preserved as default.
**How**:
```python
class ISystemStateRepository(ABC):
    @abstractmethod
    def get_setting(self, key: str, default=None): ...

class RiskService:
    def __init__(self, state_repo: ISystemStateRepository = None):
        self._state = state_repo or DefaultStateRepository()
```

---

### Improvement 3: Abstract IBKR preflight/dedup out of use cases

**Why**: `PlaceOrderUseCase` and `ClosePositionUseCase` import `app.ibkr.client` directly (bypassing `IBrokerPort`) to check for duplicate orders and open connections. This ties use cases to a specific IBKR implementation and breaks mock-based testing.
**Impact**: Use cases become fully testable without an IB Gateway; dedup logic gets a proper home.
**Effort**: M (3–4 hours) — add `check_duplicate(order_id)` and `get_open_orders()` methods to `IBrokerPort`; implement in `IBKRBrokerAdapter`; update use cases.
**Risk**: LOW — extends existing port contract; no external API change.
**How**:
```python
# broker_port.py
@abstractmethod
def get_open_orders(self) -> list[str]: ...  # Returns order IDs

# place_order.py — replace raw client import with:
existing_ids = self._broker.get_open_orders()
if order_id in existing_ids:
    return PlaceOrderResult(success=False, error="duplicate")
```

---

## Priority 3 — Monitor (2 concerns)

### Concern 1: Synchronous EventBus in APScheduler threads

**Why**: `EventBus.publish()` is synchronous. If an event handler is slow (e.g., `AuditLogHandler._write()` waits on a locked SQLite), it blocks the APScheduler thread that published the event. This could delay scanner or position-manager jobs.
**Impact**: Under normal load (single user, Pi hardware) this is fine. At higher event frequency (circuit breaker + position closed + mode switched simultaneously) it could cause scheduler hiccups.
**Effort**: XL (10+ hours) — switching to async bus or thread-pool-based dispatch is a significant change.
**When to act**: If scheduler job latency exceeds 500ms on the Pi, or if we add more event handlers that do I/O.
**Monitor**: Add `time.perf_counter()` around `EventBus.publish()` calls in use cases; log if > 100ms.

---

### Concern 2: `compat.py` datetime.utcnow() deprecation

**Why**: 8 deprecation warnings per test run from `datetime.utcnow()` in `compat.py`. Python 3.12 deprecated it; Python 3.14 will remove it.
**Impact**: Low today (warning only). Will break in ~2 years if left unaddressed.
**Effort**: XS (30 min) — find/replace `datetime.utcnow()` → `datetime.now(timezone.utc)` in compat.py.
**When to act**: Before upgrading Python beyond 3.12, or when noise level becomes irritating.

---

## Deferred From Phase 7 Review

### P2-02: `ChangeTradingModeUseCase` blocks on open positions with no `confirmed` flag
**Status**: Deferred to Phase 8
**Why**: The comment on line 58-60 in `change_mode.py` describes a future `confirmed=True` retry path that was never implemented. Works for now (prevents accidental mode switches) but will frustrate operators with open positions at end of day.
**Action**: Add to Priority 2 backlog when the control plane UI is built — the UI can provide the confirmation dialog, and the use case needs the parameter.

### P2-03: `test_container()` in `app/container.py` imports from `tests/`
**Status**: Deferred to Phase 8
**Why**: `test_container()` is a test helper living in production code. The `app/` → `tests/` import direction is an inversion.
**Action**: Move `test_container()` to `tests/conftest.py` as a pytest fixture. Low priority — does not affect runtime.

---

## Opportunities for Other Modules

### Pattern: Ports/Adapters can be applied immediately to these modules

| Module | Current State | Recommended Port |
|--------|---------------|-----------------|
| `app/alerts/manager.py` | Direct Telegram imports | Use `INotificationPort` from container |
| `app/analysis/pipeline.py` | Direct `httpx` + `notify` calls | Use `ILLMPort` + `INotificationPort` |
| `app/positions/manager.py` | Direct broker + notify imports | Use `IBrokerPort` + `INotificationPort` |
| `app/scanner/` | Direct IBKR client calls | Use `IBrokerPort` for price data |

Applying the existing port abstractions (no new code needed — ports already exist) to these 4 modules would eliminate ~80% of the remaining coupling violations.

### Pattern: EventBus for cross-module notifications

`CircuitBreakerTriggered` is already an event — but the circuit breaker logic still publishes it by calling `AuditLogHandler` directly in some paths. Any module that currently calls `notify()` directly should instead publish a domain event. The notification happens automatically via the registered handler.

---

## Anti-Pattern Assessment (Revisited)

| Pattern | Status | Notes |
|---------|--------|-------|
| Model Blindness | ✓ CLEAR | 23 ORM models are distinct; no duplication between domain events and DB models |
| Island Components | ⚠️ PARTIAL DEBT | `RiskService` and `PositionService` not injected via container in legacy callsites |
| Pub/Sub Bypass | ⚠️ MODERATE DEBT | 30+ direct `notify()` imports bypass `INotificationPort`; `PlaceOrderUseCase` imports raw IBKR client |
| UX Amnesia | ✓ CLEAR | State survives restart; audit log complete; control plane persists all settings |

---

## Architecture Health Score

| Dimension | Score | Notes |
|-----------|-------|-------|
| Cohesion | 8/10 | Layers well-defined; legacy modules still present but clearly marked |
| Coupling | 6/10 | 30+ direct notify imports; ILLMPort unwired; use cases bypass broker port |
| Testability | 8/10 | 981 tests; ports mockable; 1 collection error to fix |
| Maintainability | 7/10 | Clean new code; compat.py is the main drag |
| Scalability | 9/10 | Single-user Pi system; scaling is not a concern |
| Reusability | 8/10 | Ports ready to be used by any module; pattern is consistent |

**Overall: 7.7/10 — Solid hexagonal skeleton; main work is eliminating legacy coupling**

---

## Recommendations for Next Sprint

1. **Do first**: Fix `tests/db/test_symbol_config_migration.py` (15 min, eliminates CI noise)
2. **Do second**: Wire `ILLMPort` into container (2–3 hours, completes the port triad)
3. **Start phased**: Replace direct `notify()` imports in top-5 callsites with container notifier (1–2 hours)
4. **Backlog**: Priority 2 improvements for next quarter
5. **Monitor**: EventBus latency on Pi hardware

## Sign-Off

- **Reviewed**: 2026-05-15
- **Recommended path**: Priority 1 fixes first, then P2 structural cleanup before adding new modules
- **Next review**: After next major module addition or when P2 improvements are complete
