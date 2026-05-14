# Known Risks

## IBKR Single-Session Constraint
Opening IBKR mobile/web app disconnects IB Gateway (TCP session limit = 1). Dashboard and all real-time features must degrade gracefully to cached SQLite data.
**Mitigation**: Jobs-write/endpoint-reads pattern; stale data timestamps shown in UI.

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
