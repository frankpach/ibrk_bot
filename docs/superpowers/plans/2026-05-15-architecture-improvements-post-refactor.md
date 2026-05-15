# Architecture Improvements — Post-Refactor Sprint Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the four remaining DI anti-patterns left after the 10-phase refactor so every component receives its dependencies through the Container and the `SystemPaused` event can abort in-flight analysis runs.

**Architecture:** Sprint 1 targets the P0 and P1 gaps: (1) `pipeline.py` makes an `httpx` self-call that bypasses the DI container; (2) `alerts/manager.py` and `llm/loop.py` use thread-unsafe module-level globals with `set_broker()` setters; (3) `ibkr/dedup.py` has a thread-unsafe singleton factory. All four are converted to class-based DI and wired through the Container. No DB migrations, no API surface changes.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, APScheduler, pytest, `test_container()` with in-memory SQLite.

---

## Context

The 10-phase refactor (Issues 001–010, completed 2026-05-15) established the hexagonal skeleton: `Container`, `EventBus`, domain events, ports, and use cases. However, three modules still use the pre-refactor "transient injection" pattern (module-level globals + setter functions) and the `AnalysisPipeline` still calls `httpx.get(f"{API_BASE}/portfolio")` at runtime — a circular self-call that couples the pipeline to the FastAPI server being up. Sprint 1 closes these four gaps so the architecture is complete and consistent.

---

## File Map

| Change | File | Action |
|--------|------|--------|
| 1 | `app/analysis/pipeline.py` | Remove `httpx` call from `_score()`; add `broker`/`event_bus` kwargs to `__init__`; subscribe to `SystemPaused` |
| 2 | `app/alerts/manager.py` | Replace module-global `_broker` + `set_broker()` with `AlertManager` class; add lazy shim |
| 3 | `app/llm/loop.py` | Replace module-global `_broker`/`_notifier` + setters with `LLMSignalProcessor` class; add lazy shim; inject `dedup` as arg |
| 4 | `app/ibkr/dedup.py` | Delete `_dedup_instance` singleton + `get_deduplicator()` function |
| 5 | `app/container.py` | Add `self.order_deduplicator` and `self.alert_manager` |
| 6 | `tests/test_container_wiring.py` | New — wiring tests for Sprint 1 changes |

---

## Task 1: Remove `httpx` self-call from `pipeline._score()`

**Files:**
- Modify: `app/analysis/pipeline.py:69-84` (`__init__`), `app/analysis/pipeline.py:97-171` (`run`), `app/analysis/pipeline.py:199-214` (`_score`)

- [ ] **Step 1.1: Read the current file to confirm line numbers**

  ```bash
  # Read-only search — verify before editing
  grep -n "httpx\|notify_fn\|def __init__\|def run\|def _score" app/analysis/pipeline.py
  ```

- [ ] **Step 1.2: Update `__init__` — add `broker` and `event_bus` kwargs**

  In `app/analysis/pipeline.py`, change the `AnalysisPipeline.__init__` signature and body.

  Old:
  ```python
  class AnalysisPipeline:
      def __init__(
          self,
          symbol: str,
          data_layer,
          context: AnalysisContext,
          notify_fn: Optional[Callable] = None,
      ):
          self.symbol = symbol.upper()
          self._data_layer = data_layer
          self._context = context
          self._notify_fn = notify_fn
          self.current_step = "init"
          self._result = AnalysisResult(symbol=self.symbol)
          self._start_time = 0.0
          self._aborted = threading.Event()
  ```

  New:
  ```python
  class AnalysisPipeline:
      def __init__(
          self,
          symbol: str,
          data_layer,
          context: AnalysisContext,
          notify_fn: Optional[Callable] = None,
          broker=None,     # IBrokerPort | None — injected for portfolio fetch
          event_bus=None,  # EventBus | None — injected for SystemPaused subscription
      ):
          self.symbol = symbol.upper()
          self._data_layer = data_layer
          self._context = context
          self._notify_fn = notify_fn
          self._broker = broker
          self._event_bus = event_bus
          self.current_step = "init"
          self._result = AnalysisResult(symbol=self.symbol)
          self._start_time = 0.0
          self._aborted = threading.Event()
  ```

- [ ] **Step 1.3: Subscribe to `SystemPaused` at the top of `run()`**

  Add these lines at the start of `run()`, before the watchdog timer:
  ```python
  def run(self) -> AnalysisResult:
      import time
      self._start_time = time.time()

      # Subscribe to SystemPaused for graceful abort
      if self._event_bus is not None:
          from app.domain.trading.events import SystemPaused
          def _on_system_paused(event: SystemPaused) -> None:
              self._aborted.set()
          self._event_bus.subscribe(SystemPaused, _on_system_paused)

      # Global watchdog (existing code continues here...)
  ```

- [ ] **Step 1.4: Replace `httpx` block in `_score()` with broker call**

  Old (`app/analysis/pipeline.py:199-212`):
  ```python
  def _score(self):
      self.current_step = "score"
      from app.analysis.scorer import compute_score
      portfolio = []
      try:
          import httpx
          from app.config.settings import API_BASE
          r = httpx.get(f"{API_BASE}/portfolio", timeout=5)
          portfolio = r.json() if r.status_code == 200 else []
      except Exception:
          pass
      self._result.score = compute_score(
          self._result.features, self.symbol, portfolio, self._news
      )
  ```

  New:
  ```python
  def _score(self):
      self.current_step = "score"
      from app.analysis.scorer import compute_score
      portfolio: list = []
      if self._broker is not None:
          try:
              portfolio = self._broker.get_portfolio()
          except Exception:
              pass
      self._result.score = compute_score(
          self._result.features, self.symbol, portfolio, self._news
      )
  ```

- [ ] **Step 1.5: Update call sites of `AnalysisPipeline(...)` to pass `broker`/`event_bus`**

  Search for all instantiations:
  ```bash
  grep -rn "AnalysisPipeline(" app/
  ```

  For each found call site (likely in `app/analysis/admission.py` and Telegram bot handlers), add:
  ```python
  from app.container import get_container
  _c = get_container()
  pipe = AnalysisPipeline(symbol, data_layer, context, notify_fn=notify,
                          broker=_c.broker, event_bus=_c.event_bus)
  ```

- [ ] **Step 1.6: Run existing pipeline tests to verify nothing broke**

  ```bash
  cd d:/Documents/Mis_proyectos/Proyectos_Actuales/llm_ibr
  python -m pytest tests/analysis/test_pipeline.py -v 2>&1 | tail -20
  ```
  Expected: all existing tests pass (no broker → portfolio stays `[]`, same as before).

- [ ] **Step 1.7: Commit**

  ```bash
  git add app/analysis/pipeline.py app/analysis/admission.py
  git commit -m "fix(pipeline): inject IBrokerPort, remove httpx self-call, subscribe to SystemPaused"
  ```

---

## Task 2: Convert `alerts/manager.py` to class-based DI

**Files:**
- Modify: `app/alerts/manager.py`
- Modify: `app/container.py`

- [ ] **Step 2.1: Read current file to confirm the global pattern**

  ```bash
  grep -n "_broker\|set_broker\|_get_broker\|def check_all" app/alerts/manager.py
  ```

- [ ] **Step 2.2: Rewrite `app/alerts/manager.py`**

  Replace the module-level `_broker` global and `set_broker()` / `_get_broker()` block with an `AlertManager` class. Keep `parse_alert_command()` and `check_alert_triggered()` as pure functions (no broker dependency). Add a module-level shim `check_all_alerts()` that lazily calls `get_container()`.

  ```python
  # app/alerts/manager.py
  """
  Gestiona alertas de precio configuradas por el usuario via Telegram.
  Verifica cada 2 minutos si el precio se movio mas del umbral.
  """
  import structlog
  from dataclasses import dataclass
  from typing import Optional

  from app.notifications.telegram import notify
  from app.application.ports.broker_port import IBrokerPort

  logger = structlog.get_logger(__name__)


  @dataclass
  class AlertConfig:
      id: Optional[int]
      symbol: str
      threshold_pct: float  # ej: 0.05 = 5%


  class AlertManager:
      """Stateless alert checker. Broker injected via constructor."""

      def __init__(self, broker: IBrokerPort) -> None:
          self._broker = broker

      def get_price_and_prev_close(self, symbol: str) -> tuple[float, float]:
          try:
              price = float(self._broker.get_price(symbol))
              return price, price  # prev_close fallback: same as current
          except Exception as e:
              logger.error(f"Could not fetch price for {symbol}: {e}")
              return 0.0, 0.0

      def check_all(self, db_get_alerts, db_mark_triggered) -> None:
          alerts = db_get_alerts()
          if not alerts:
              return
          for alert in alerts:
              current_price, prev_close = self.get_price_and_prev_close(alert.symbol)
              if current_price <= 0:
                  continue
              triggered, pct_change = check_alert_triggered(alert, current_price, prev_close)
              if triggered:
                  direction = "subio" if pct_change > 0 else "bajo"
                  notify(
                      f"ALERTA: <b>{alert.symbol}</b> {direction} {abs(pct_change):.1%}\n"
                      f"Precio: ${current_price:.2f}\n"
                      f"Umbral configurado: {alert.threshold_pct:.0%}"
                  )
                  db_mark_triggered(alert.id)
                  logger.info(f"Alert triggered for {alert.symbol}: {pct_change:.1%}")


  # --- Pure functions (no broker dependency) ---

  def parse_alert_command(symbol: str, threshold_str: str) -> Optional[AlertConfig]:
      try:
          pct_str = threshold_str.strip().rstrip("%")
          pct = float(pct_str) / 100.0
          if pct <= 0 or pct > 1.0:
              return None
          return AlertConfig(id=None, symbol=symbol.upper(), threshold_pct=pct)
      except (ValueError, AttributeError):
          return None


  def check_alert_triggered(
      alert: AlertConfig,
      current_price: float,
      prev_close: float,
  ) -> tuple[bool, float]:
      if prev_close <= 0:
          return False, 0.0
      pct_change = (current_price - prev_close) / prev_close
      triggered = abs(pct_change) >= alert.threshold_pct
      return triggered, round(pct_change, 4)


  # --- APScheduler entry point shim ---

  def check_all_alerts(db_get_alerts, db_mark_triggered) -> None:
      """Called by APScheduler. Uses Container's broker — lazy import avoids circular deps."""
      from app.container import get_container
      get_container().alert_manager.check_all(db_get_alerts, db_mark_triggered)
  ```

- [ ] **Step 2.3: Add `alert_manager` to `app/container.py`**

  In `Container.__init__`, after `self.position_service = PositionService()`, add:
  ```python
  from app.alerts.manager import AlertManager
  self.alert_manager = AlertManager(broker=self.broker)
  ```

- [ ] **Step 2.4: Find and verify all call sites of the old `set_broker()` setter**

  ```bash
  grep -rn "set_broker\|from app.alerts.manager import" app/ --include="*.py"
  ```

  Remove any `alerts_manager.set_broker(...)` calls found (they are no longer needed — Container wires at startup).

- [ ] **Step 2.5: Run alert tests**

  ```bash
  python -m pytest tests/test_alerts.py -v 2>&1 | tail -20
  ```

  If tests patch `_get_broker`, update the patch target to `app.alerts.manager.AlertManager.get_price_and_prev_close` or `app.infrastructure.broker.ibkr_adapter.IBKRBrokerAdapter.get_price`.

- [ ] **Step 2.6: Commit**

  ```bash
  git add app/alerts/manager.py app/container.py
  git commit -m "fix(alerts): convert AlertManager to class-based DI, remove global _broker"
  ```

---

## Task 3: Convert `llm/loop.py` to class-based DI

**Files:**
- Modify: `app/llm/loop.py`

- [ ] **Step 3.1: Read current file — find globals and all usages**

  ```bash
  grep -n "_broker\|_notifier\|set_broker\|set_notifier\|_get_broker\|_get_notifier\|get_deduplicator\|def process_pending" app/llm/loop.py
  ```

- [ ] **Step 3.2: Identify the boundary — what should become class methods**

  The function `process_pending_signals()` and its helpers (`_execute_order`, etc.) reference `_get_broker()` and `_get_notifier()`. Trace every such call in `loop.py`:
  ```bash
  grep -n "_get_broker\|_get_notifier\|get_deduplicator\|notify(" app/llm/loop.py
  ```

- [ ] **Step 3.3: Add `LLMSignalProcessor` class above the module-level shim**

  Before the current `process_pending_signals()` function, add:
  ```python
  class LLMSignalProcessor:
      """Processes pending LLM signals. All dependencies injected via constructor."""

      def __init__(self, broker, notifier, dedup) -> None:
          self._broker = broker
          self._notifier = notifier
          self._dedup = dedup

      def process_pending_signals(self) -> None:
          # Move the body of the current process_pending_signals() here.
          # Replace every _get_broker() with self._broker
          # Replace every _get_notifier() with self._notifier
          # Replace every get_deduplicator() with self._dedup
          # Replace every notify(...) call with self._notifier.notify(...)
          ...  # (full current body here)

      def _execute_order(self, symbol, decision, ...) -> bool:
          # Move the body of the current _execute_order() here.
          # Same replacements as above.
          ...
  ```

- [ ] **Step 3.4: Replace the module-level `process_pending_signals` function with a shim**

  ```python
  def process_pending_signals() -> None:
      """APScheduler entry point. Delegates to Container-wired processor."""
      from app.container import get_container
      c = get_container()
      LLMSignalProcessor(
          broker=c.broker,
          notifier=c.notifier,
          dedup=c.order_deduplicator,
      ).process_pending_signals()
  ```

- [ ] **Step 3.5: Delete the old globals and setter functions**

  Remove from `loop.py`:
  - `_broker: IBrokerPort | None = None`
  - `_notifier: INotificationPort | None = None`
  - `def set_broker(broker: IBrokerPort) -> None: ...`
  - `def set_notifier(notifier: INotificationPort) -> None: ...`
  - `def _get_broker() -> IBrokerPort: ...`
  - `def _get_notifier() -> INotificationPort: ...`

- [ ] **Step 3.6: Verify no remaining calls to `set_broker` / `set_notifier` in the codebase**

  ```bash
  grep -rn "set_broker\|set_notifier\|from app.llm.loop import" app/ --include="*.py"
  ```

  Any remaining `set_broker` call must be removed.

- [ ] **Step 3.7: Run signal loop tests**

  ```bash
  python -m pytest tests/ -k "signal or loop" -v 2>&1 | tail -30
  ```
  Expected: all existing tests pass or are updated to match new class-based structure.

- [ ] **Step 3.8: Commit**

  ```bash
  git add app/llm/loop.py
  git commit -m "fix(llm-loop): extract LLMSignalProcessor class, remove module-level broker/notifier globals"
  ```

---

## Task 4: Move `OrderDeduplicator` singleton into the Container

**Files:**
- Modify: `app/ibkr/dedup.py`
- Modify: `app/container.py`

- [ ] **Step 4.1: Read dedup.py to confirm singleton lines**

  ```bash
  grep -n "_dedup_instance\|get_deduplicator\|class OrderDeduplicator" app/ibkr/dedup.py
  ```
  Expected: singleton at lines ~150–157.

- [ ] **Step 4.2: Delete singleton from `app/ibkr/dedup.py`**

  Remove these lines entirely (lines 150–157):
  ```python
  # Singletons
  _dedup_instance = None

  def get_deduplicator() -> OrderDeduplicator:
      global _dedup_instance
      if _dedup_instance is None:
          _dedup_instance = OrderDeduplicator()
      return _dedup_instance
  ```

- [ ] **Step 4.3: Add `order_deduplicator` to `app/container.py`**

  In `Container.__init__`, after the alert_manager line (from Task 2), add:
  ```python
  from app.ibkr.dedup import OrderDeduplicator
  self.order_deduplicator = OrderDeduplicator()
  ```

- [ ] **Step 4.4: Verify no remaining calls to `get_deduplicator()` outside of the class**

  After Task 3, `loop.py` no longer calls `get_deduplicator()` — the dedup instance comes via `LLMSignalProcessor.__init__`. Confirm:
  ```bash
  grep -rn "get_deduplicator" app/ --include="*.py"
  ```
  Expected: 0 results.

- [ ] **Step 4.5: Run dedup-related tests**

  ```bash
  python -m pytest tests/ibkr/ -v 2>&1 | tail -20
  python -m pytest tests/ -k "dedup" -v 2>&1 | tail -20
  ```

- [ ] **Step 4.6: Commit**

  ```bash
  git add app/ibkr/dedup.py app/container.py
  git commit -m "fix(dedup): move OrderDeduplicator into Container, remove thread-unsafe module singleton"
  ```

---

## Task 5: Add wiring tests

**Files:**
- Create: `tests/test_container_wiring.py`

- [ ] **Step 5.1: Create the test file**

  ```python
  # tests/test_container_wiring.py
  """Verify the DI Container wires all Sprint 1 components correctly."""
  import pytest
  from unittest.mock import MagicMock, patch

  from app.container import test_container
  from app.alerts.manager import AlertConfig, AlertManager, check_alert_triggered
  from app.ibkr.dedup import OrderDeduplicator


  def test_container_has_alert_manager():
      c = test_container()
      assert isinstance(c.alert_manager, AlertManager)
      assert c.alert_manager._broker is c.broker


  def test_container_has_order_deduplicator():
      c = test_container()
      assert isinstance(c.order_deduplicator, OrderDeduplicator)


  def test_deduplicator_is_same_instance():
      c = test_container()
      assert c.order_deduplicator is c.order_deduplicator


  def test_alert_manager_with_mock_broker():
      """AlertManager delegates price fetch to injected broker."""
      mock_broker = MagicMock()
      mock_broker.get_price.return_value = 200.0
      manager = AlertManager(broker=mock_broker)
      current, _ = manager.get_price_and_prev_close("AAPL")
      assert current == 200.0
      mock_broker.get_price.assert_called_once_with("AAPL")


  def test_alert_manager_handles_broker_error_gracefully():
      mock_broker = MagicMock()
      mock_broker.get_price.side_effect = RuntimeError("IB Gateway disconnected")
      manager = AlertManager(broker=mock_broker)
      current, prev = manager.get_price_and_prev_close("AAPL")
      assert current == 0.0
      assert prev == 0.0


  def test_check_alert_triggered_above_threshold():
      alert = AlertConfig(id=1, symbol="AAPL", threshold_pct=0.05)
      triggered, pct = check_alert_triggered(alert, current_price=210.0, prev_close=200.0)
      assert triggered is True
      assert abs(pct - 0.05) < 0.001


  def test_check_alert_not_triggered_below_threshold():
      alert = AlertConfig(id=2, symbol="TSLA", threshold_pct=0.05)
      triggered, pct = check_alert_triggered(alert, current_price=203.0, prev_close=200.0)
      assert triggered is False


  def test_pipeline_accepts_broker_kwarg_without_breaking():
      """Pipeline still works when broker kwarg is omitted (backward compat)."""
      from app.analysis.pipeline import AnalysisPipeline, AnalysisContext
      dl = MagicMock()
      dl.get_ohlcv.return_value = None
      dl.get_historical_volatility.return_value = None
      dl.get_news.return_value = []
      dl.get_earnings_date.return_value = None
      pipe = AnalysisPipeline("AAPL", dl, AnalysisContext(mode="on_demand"))
      result = pipe.run()
      # No broker → portfolio=[] → pipeline completes (with error due to no data)
      assert result.symbol == "AAPL"


  def test_pipeline_calls_broker_get_portfolio_when_injected():
      """When broker is provided, portfolio is fetched from broker not httpx."""
      from app.analysis.pipeline import AnalysisPipeline, AnalysisContext

      mock_broker = MagicMock()
      mock_broker.get_portfolio.return_value = [{"symbol": "TSLA", "qty": 10}]

      dl = MagicMock()
      dl.get_ohlcv.return_value = None
      dl.get_historical_volatility.return_value = None
      dl.get_news.return_value = []
      dl.get_earnings_date.return_value = None

      pipe = AnalysisPipeline("AAPL", dl, AnalysisContext(mode="on_demand"),
                              broker=mock_broker)
      pipe.run()
      mock_broker.get_portfolio.assert_called_once()
  ```

- [ ] **Step 5.2: Run the new tests**

  ```bash
  python -m pytest tests/test_container_wiring.py -v 2>&1 | tail -30
  ```
  Expected: all 9 tests pass.

- [ ] **Step 5.3: Run the full test suite to check for regressions**

  ```bash
  python -m pytest tests/ -x --tb=short 2>&1 | tail -40
  ```
  Expected: no new failures introduced by Sprint 1 changes.

- [ ] **Step 5.4: Commit**

  ```bash
  git add tests/test_container_wiring.py
  git commit -m "test(container): add wiring tests for Sprint 1 DI fixes"
  ```

---

## Verification

End-to-end verification after all 5 tasks are complete:

```bash
# 1. No httpx calls remain in analysis pipeline
grep -rn "httpx" app/analysis/ --include="*.py"
# Expected: 0 results

# 2. No set_broker / set_notifier / get_deduplicator calls remain
grep -rn "set_broker\|set_notifier\|get_deduplicator" app/ --include="*.py"
# Expected: 0 results

# 3. Container wires all Sprint 1 components
python -c "from app.container import test_container; c = test_container(); print('alert_manager:', c.alert_manager); print('dedup:', c.order_deduplicator)"
# Expected: both objects instantiated without error

# 4. Full test suite green
python -m pytest tests/ --tb=short -q 2>&1 | tail -10
```

---

## Sprint 2 — Backlog (Next Quarter, Do Not Implement Now)

Document these for the issue tracker. Start only after Sprint 1 is deployed and stable on the Pi.

1. **Add analysis lifecycle domain events** — Add `AnalysisStarted`, `AnalysisStepCompleted`, `AnalysisCompleted`, `AnalysisFailed` to `app/domain/trading/events.py`. Pipeline publishes them at each step boundary. Dashboard can display live analysis progress.

2. **Tests for EventBus, use cases, and Container** — Create `tests/test_event_bus.py` (edge cases: handler throws, multiple handlers for same event, unsubscribe), and `tests/test_use_cases.py` covering `ChangeTradingModeUseCase`, `PauseSystemUseCase`, `PlaceOrderUseCase`, `ClosePositionUseCase`.

3. **Begin `compat.py` → Repository migration** — Extract `SymbolRepository` wrapping `get_approved_symbols()` / `approve_symbol()`. Target: `compat.py` under 1000 lines (from 1447) by end of quarter. Use `ISymbolRepositoryPort` interface.

---

## Sprint 3 — Monitor (Deferred)

1. **Full `compat.py` decomposition** — `TradeRepository`, `SignalRepository`, `AccountRepository`, `DecisionRepository`, `PatternRepository`.

2. **`admission.py` event integration** — Pass `event_bus` to `run_daily_discovery`; publish `DiscoveryCandidateFound(symbol, score)` events.

3. **Concurrency safety audit** — Audit all `threading.Event`, `dict` accesses in `dedup.py` and `pipeline.py` under APScheduler's thread pool; add `threading.Lock()` where needed.

---

## Common Pitfalls

**Circular imports.** Shims call `get_container()` inside the function body — never at module import time. `app/container.py` imports from many submodules; importing it at the top of `alerts/manager.py` or `llm/loop.py` creates circular imports. The lazy `from app.container import get_container` inside a function is the established pattern here.

**`test_container()` vs `get_container()`.** `get_container()` is `@lru_cache(maxsize=1)` — it returns the same instance every call. Tests that call `test_container()` bypass the cache and get a fresh instance with `MockBrokerAdapter`. Shim-level unit tests that need the mock must patch `app.container.get_container` to return a `test_container()` instance.

**Existing pipeline test patch targets.** Tests in `tests/analysis/test_pipeline.py` may patch `app.db.database.insert_feature_snapshot` — the old import path. The pipeline actually imports from `app.infrastructure.db.compat`. Verify patch targets intercept the right module before running; update to `app.infrastructure.db.compat.insert_feature_snapshot` if needed.

**Pi deployment.** After merging Sprint 1: `sudo systemctl restart ibkr-trader`. No DB migrations, no config changes required.
