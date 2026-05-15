# Project Memory — IBKR AI Trader

Last updated: 2026-05-15

## System Summary

Semi-autonomous IBKR trading bot running on Raspberry Pi (aiutox-pi). Single-user, Python 3.13, FastAPI + APScheduler + SQLite (PostgreSQL path available). Deployed via `scripts/deploy.sh` over SSH.

## Completed Modules

| Module | Date | Key Outcome |
|--------|------|-------------|
| risk-engine-v2 | prior | Trailing stop, partial exit, circuit breaker |
| notification-system | prior | Telegram bot, approval manager, throttler |
| mtf-learning-engine | prior | Multi-timeframe ML signal filter |
| live-dashboard | 2026-05-13 | SQLite read model; SVG charts; zero IBKR calls from HTTP |
| **arch-refactor** | **2026-05-15** | **Full Hexagonal Architecture — see below** |

## arch-refactor — What Changed (2026-05-15)

### Core Architecture
- **DI Container**: `app/container.py` — single wiring point, `get_container()` (cached) + `test_container()` (fresh mocks)
- **Event Bus**: `app/application/event_bus.py` — in-process sync pub/sub; handlers registered once at container init
- **Ports/Adapters**: `IBrokerPort`, `INotificationPort`, `ILLMPort` (defined, not yet wired in Container)
- **Use Cases**: PlaceOrder, ClosePosition, ChangeMode, PauseSystem, UpdateControlSetting, ControlQueries
- **SQLAlchemy + Alembic**: 23 ORM models replacing raw SQL; dual SQLite/PostgreSQL backend
- **Control Plane**: `/control` React SPA — all operational params configurable from browser

### Sprint 1 DI Fixes (same day)
- `AnalysisPipeline._score()` uses `broker.get_portfolio()` (no more `httpx` self-call)
- `AlertManager` class-based DI; `LLMSignalProcessor` class-based DI
- `OrderDeduplicator` in Container; thread-unsafe singleton eliminated
- `IBrokerPort.get_prev_close()` added — alerts now use real previous close

### What's NOT Done Yet (Sprint 2 backlog)
- `ILLMPort` not wired in Container
- 30+ direct `notify()` imports still bypassing `INotificationPort`
- `EventBus.unsubscribe()` not implemented
- `compat.py` (1447 lines) not yet replaced by Repositories
- `RiskService` doesn't hot-reload control plane settings

## Key File Locations

| Concern | Files |
|---------|-------|
| DI wiring | `app/container.py` |
| Domain events | `app/domain/trading/events.py` |
| Ports | `app/application/ports/` |
| Use cases | `app/application/use_cases/` |
| ORM models | `app/infrastructure/db/models/` |
| Migrations | `app/infrastructure/db/migrations/`, `alembic.ini` |
| Legacy bridge | `app/infrastructure/db/compat.py` (not to be extended) |
| Mocks | `tests/mocks/` |
| Wiring tests | `tests/test_container_wiring.py` |
| CI | `.github/workflows/ci.yml` |
| Deploy | `scripts/deploy.sh` |

## Critical Rules

1. **Never** call `get_container()` at module import time — always inside a function body
2. **Never** add new code to `compat.py` — use SQLAlchemy models + session directly
3. **Never** register event handlers per-request or per-pipeline scope — only in `Container._register_event_handlers()`
4. **Always** use `test_container()` in tests, not `get_container()`
5. **Always** run `alembic upgrade head` after schema changes

## Process Lessons (from arch-refactor retro)

1. **Delete stale tests at the same commit as the deleted module.** Do not defer. Stale tests that patch removed symbols cost 3× more to fix later than if fixed immediately.

2. **Trace old data sources before rewriting fetch methods.** Document "old source → new source, equivalent?" in the plan. The `prev_close` regression (alerts silently broken) was caused by this omission.

3. **Architecture review phase (`/230`) is not optional polish.** It caught 4 production correctness bugs that tests missed (mock-patching hid them).

4. **EventBus subscriptions have no cleanup.** Register ALL handlers in `Container._register_event_handlers()`. Never subscribe inside a per-call scope (per-request, per-pipeline).

5. **Two-stage subagent review (spec then quality) catches different things.** Spec reviewer catches missing/extra scope. Quality reviewer catches logic bugs that tests don't cover. Both are needed.

## Cross-References

- Architecture details: `docs/04-modules/refactor/ARCHITECTURE.md`
- API reference: `docs/04-modules/refactor/API.md`
- Extension guide: `docs/04-modules/refactor/EXTENDING.md`
- Decision records: `docs/04-modules/refactor/DECISIONS.md`
- Backlog: `docs/04-modules/refactor/BACKLOG.md`
- Code patterns: `.claude/project-memory/code-patterns.md`
- Known risks: `.claude/project-memory/known-risks.md`
