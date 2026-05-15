# Known Risks

## IBKR Single-Session Constraint
Opening IBKR mobile/web app disconnects IB Gateway (TCP session limit = 1). Dashboard and all real-time features must degrade gracefully to cached SQLite data.
**Mitigation**: Jobs-write/endpoint-reads pattern; stale data timestamps shown in UI.

## EventBus has no unsubscribe() — handler leak risk
If a handler is registered inside a per-request or per-pipeline scope (e.g., inside `AnalysisPipeline.run()`), it permanently accumulates. Each instance retains the closure in memory.
**Mitigation**: Register handlers ONLY in `Container._register_event_handlers()`. Sprint 2 backlog includes adding `EventBus.unsubscribe()`.
**Detection**: `len(event_bus._handlers[EventType])` growing over time in logs.

## compat.py (1447 lines) — legacy drag
`app/infrastructure/db/compat.py` is the de-facto application layer for 30+ legacy modules. New code should not use it.
**Mitigation**: Sprint 2 replaces it incrementally with `SymbolRepository`, `TradeRepository`, etc.
**Rule**: Do not add new functions to `compat.py`. Use SQLAlchemy models + session directly.

## RiskService reads hardcoded config defaults
`RiskService` does not react to live control plane changes. If operator updates `max_position_size` via `/control`, `RiskService` won't see it until restart.
**Mitigation**: Sprint 2 backlog — inject `ISystemStateRepository` into `RiskService`.

## Synchronous EventBus may block APScheduler threads
`event_bus.publish()` is synchronous. A slow handler (SQLite write under lock) can stall the scheduler thread.
**Current state**: Fine at single-user Pi load.
**Action threshold**: Scheduler latency > 500ms. Add `time.perf_counter()` instrumentation first.

## get_deduplicator() thin delegate — bootstrap risk
`app/ibkr/dedup.py:get_deduplicator()` calls `get_container()`. If called before container initializes (import-time side effect), it bootstraps a production container unexpectedly.
**Mitigation**: Only called from `LLMSignalProcessor._execute_order()` at runtime — safe today. Migrate remaining call sites to `container.order_deduplicator` directly.

## SQLite Write Locks Under Concurrency
APScheduler runs 15+ concurrent jobs. Multiple writers to SQLite can cause "database is locked" errors.
**Mitigation**: WAL mode (`PRAGMA journal_mode=WAL`) and `PRAGMA busy_timeout=5000`. Planned for arch-refactor Fase 0.

## Global Mutation of settings.PAPER_TRADING_ONLY
`SystemController.set_mode()` mutates a module-level variable. If the process restarts, the mode reverts to `.env` default regardless of what was set at runtime.
**Mitigation**: Persist `system_config` to DB (arch-refactor Fase 3).

## HTTP Internal Bus (loop.py → /orders/place)
`llm/loop.py` calls `POST /orders/place` via httpx. If the FastAPI server is slow or restarting, orders can fail silently.
**Mitigation**: Eliminate HTTP internal calls (arch-refactor Fase 1).

## Subprocess LLM Timeout Blocking Scheduler
OpenCode subprocess has a 60s timeout. If it hangs, the APScheduler job thread is blocked for 60s, potentially missing subsequent runs.
**Mitigation**: Unify subprocess handling in opencode_adapter.py with strict timeout + non-blocking background job model (arch-refactor Fases 0, 6).

## Hardcoded Raspberry Pi Paths in Production Code
`cwd="/home/frankpach/ibkr-bot"` appears in 3 modules. Any deployment to a different path or machine breaks LLM calls silently.
**Mitigation**: Move to `settings.py` (arch-refactor Fase 0).
