# Architecture Decision Records: IBKR AI Trader Refactor

## DEC-001: SQLAlchemy ORM

**Status**: Committed
**Replaces**: Raw SQL in `app/db/database.py` (1,277 LOC)
**Rationale**: Portable across SQLite→PostgreSQL without rewriting data layer. Type-safe queries. Strong ecosystem.
**Trade-off**: Slight abstraction overhead; compat.py bridge needed during migration.

## DEC-002: Alembic for Migrations

**Status**: Committed
**Replaces**: `ALTER TABLE` embedded in `try/except` blocks
**Rationale**: Versioned, reversible, reproducible schema changes. `alembic upgrade head` at startup.
**Constraint**: Every schema change needs a numbered migration with `upgrade()` and `downgrade()`.

## DEC-003: Ports & Adapters (Hexagonal Architecture)

**Status**: Committed
**Layer order**: `domain/` → `application/ports/` + `use_cases/` → `infrastructure/` → `interfaces/`
**Rationale**: Use cases testable without IB Gateway, Telegram, or real DB. Adapters swappable.
**Trade-off**: More files; abstraction overhead for a single-developer project.

## DEC-004: Eliminate Internal HTTP

**Status**: Committed
**Removed**: `httpx.get("http://localhost:8088/...")` calls in `llm/loop.py`, `positions/manager.py`, `analysis/pipeline.py`
**Replaced with**: Direct Python use-case calls or port method calls
**Rationale**: Circular self-calls coupled components to the FastAPI server being up.

## DEC-005: Event Bus — In-Process Synchronous

**Status**: Committed
**Rejected alternatives**: Redis pub/sub, asyncio event loop
**Rationale**: No external dependencies; predictable execution order; Pi hardware doesn't need distributed messaging.
**Trade-off**: Slow synchronous handlers block the publishing thread. Monitor if scheduler latency > 500ms.
**Known gap**: No `unsubscribe()`. Handlers must be registered once at container init — never inside per-request or per-pipeline scope.

## DEC-006: Persist System State in DB

**Status**: Committed
**Table**: `control_settings` (key-value store)
**Replaces**: In-memory globals in `settings.py`, `system/controller.py`
**Rationale**: Pi restart preserves mode (paper/live) and pause state.

## DEC-007: Control Plane at `/control`

**Status**: Committed
**Format**: React SPA embedded in FastAPI (same pattern as dashboard)
**Sections**: Mode/pause, risk params, circuit breaker, symbol universe, API keys, IB ports, DB URL, scheduler, audit log
**Rationale**: Operator can configure everything from browser — no SSH, no `.env` edits.

## DEC-008: Two-Tier Auth (Control-Key + Admin-Key)

**Status**: Committed
**Control-Key** (`X-Control-Key`): Standard operations
**Admin-Key** (`X-Admin-Key`): High-impact changes (live mode, API keys, IB ports, symbol approval)
**Rationale**: Prevents accidental live trading activation from dashboard interactions.

## DEC-009: ThreadPoolExecutor for Slow Jobs

**Status**: Committed
**max_workers**: 3
**Pattern**: `POST /jobs/{type}` → `{job_id}`, `GET /jobs/{id}` → `{status, result}`
**Rationale**: LLM analysis (150s+), backtest, opportunity scan must not block HTTP request.
**Trade-off**: No distributed job queue; if Pi crashes, in-flight jobs are lost (acceptable for single-user).

## DEC-010: Fernet Encryption for Secrets

**Status**: Committed
**Library**: `cryptography.Fernet` with `SECRET_ENCRYPTION_KEY` env var
**Applies to**: API keys, passwords in `control_settings` where `is_secret=True`
**Rationale**: Keys never stored or returned in plain text.
**Constraint**: Key rotation requires restart; store `SECRET_ENCRYPTION_KEY` in `.env.secret` (gitignored).

## DEC-011: Dual-Backend SQLite/PostgreSQL

**Status**: Committed
**Default**: SQLite (Pi, local dev)
**Production path**: PostgreSQL when data volume demands it
**How**: Same SQLAlchemy models; `DATABASE_URL` env var controls which backend.
**Trade-off**: Schema conservatism — can't use DB-specific features (e.g., JSONB, array columns).

## DEC-012: Container as Single Wiring Point

**Status**: Committed
**Pattern**: `get_container()` (cached singleton) + `test_container()` (fresh, all mocks)
**Rule**: Never instantiate adapters or use cases outside the Container.
**Rule**: Never call `get_container()` at module import time — only inside function bodies.

## DEC-013: `compat.py` as Migration Bridge

**Status**: Committed (temporary)
**Scope**: 75 functions wrapping the old raw SQL API
**Intent**: Legacy modules continue working while incrementally migrated. Not to be extended.
**Exit criterion**: Replaced by `SymbolRepository`, `TradeRepository`, etc. (Sprint 2 backlog).

## DEC-014: `get_deduplicator()` kept as thin Container delegate

**Status**: Committed (Sprint 1)
**Context**: `app/ibkr/dedup.py` originally had a thread-unsafe `_dedup_instance` singleton.
**Decision**: Keep the `get_deduplicator()` function but have it delegate to `get_container().order_deduplicator` instead of managing its own state. This avoids breaking 4+ call sites while eliminating the thread-unsafe global.
**Exit criterion**: All call sites migrated to use Container directly.
