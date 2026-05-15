# Module: Hexagonal Architecture Refactor

**Status**: Complete (Issues 001–010 + Sprint 1 DI fixes)
**Completed**: 2026-05-15
**Owner**: Frank Pacheco

## What This Module Is

A full architectural refactor of the IBKR AI Trader — a semi-autonomous trading bot running on Raspberry Pi. The system was transformed from a fragile monolith into a clean Hexagonal Architecture (Ports & Adapters) with a Dependency Injection Container, Event Bus, SQLAlchemy ORM, and Alembic migrations.

## Problem Solved

| Before | After |
|--------|-------|
| State lost on every Pi restart (mode, pause) | Persisted in `control_settings` DB table |
| `app/db/database.py` — 1,277-line SQL monolith imported by 35 modules | 23 SQLAlchemy models + `compat.py` wrapper |
| Modules called localhost FastAPI via `httpx` | Direct Python use-case calls |
| `_call_opencode()` duplicated in 3 files | Single `OpenCodeAdapter` |
| No way to adjust params without SSH + restart | React control plane at `/control` |
| Tests impossible without IB Gateway + Telegram | `test_container()` with mocks + in-memory SQLite |
| Thread-unsafe module-level globals (`_broker`, `_notifier`, `_dedup_instance`) | All wired through Container |

## Quick Start for Developers

```bash
# Run all tests (no IB Gateway or Telegram needed)
pytest tests/ --timeout=60 -q

# Run migrations
alembic upgrade head

# Test container (in-memory, fully mocked)
python -c "from app.container import test_container; c = test_container(); print(c.broker, c.alert_manager)"
```

## Key Entry Points

| Entry Point | File | Purpose |
|-------------|------|---------|
| DI Container | `app/container.py` | All dependencies wired here |
| FastAPI app | `app/interfaces/api/app.py` | HTTP interface |
| Scheduler | `app/bootstrap/scheduler_setup.py` | APScheduler jobs |
| DB engine | `app/infrastructure/db/engine.py` | SQLite / PostgreSQL |
| Migrations | `alembic.ini` + `app/infrastructure/db/migrations/` | Schema versioning |

## Module Docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — Layers, components, event catalog
- [API.md](API.md) — HTTP endpoints
- [EXTENDING.md](EXTENDING.md) — How to add a new module/use case
- [DECISIONS.md](DECISIONS.md) — Architecture decision records
- [BACKLOG.md](BACKLOG.md) — Deferred improvements
