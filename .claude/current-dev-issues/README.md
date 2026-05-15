# Refactor Arquitectónico — Development Issues

**Module**: refactor
**Started**: 2026-05-14
**Status**: Phase 4 — Planning complete, ready for execution

## Issue List

| # | Issue | Effort | Type | Blocked by | Status |
|---|-------|--------|------|-----------|--------|
| 001 | [Phase 0 — Quick Wins](001-phase0-quick-wins.md) | M | AFK | None | pending |
| 002 | [Phase 1 — Eliminar HTTP Interno](002-phase1-eliminate-internal-http.md) | M | AFK | 001 | pending |
| 003 | [Phase 2 — Extraer Servicios y DI](003-phase2-extract-services.md) | L | AFK | 002 | pending |
| 004 | [Phase 3 — Persistir System State y Event Bus](004-phase3-persist-state.md) | M | AFK | 003 | pending |
| 005 | [Phase 4a — Control Plane Backend](005-phase4a-control-plane-backend.md) | M | AFK | 004 | pending |
| 006 | [Phase 4b — Control Plane Frontend](006-phase4b-control-plane-frontend.md) | M | HITL | 005 | pending |
| 007 | [Phase 5 — Dashboard Read Models y Background Jobs](007-phase5-dashboard-jobs.md) | M | AFK | 006 | pending |
| 008 | [Phase 6 — SQLAlchemy Models, Alembic y Repositorios](008-phase6-sqlalchemy-alembic.md) | XL | AFK | 007 | pending |
| 009 | [Phase 7 — Migrar a PostgreSQL](009-phase7-postgresql.md) | M | HITL | 008 | pending |
| 010 | [Phase 8 — Hardening Final](010-phase8-hardening.md) | M | AFK | 009 | pending |

**Total issues**: 10  
**AFK**: 8 | **HITL**: 2 (006 frontend, 009 migración de datos de producción)

## Dependency Graph

```
001 (Phase 0 — Quick Wins)
 └─► 002 (Phase 1 — Eliminar HTTP interno)
      └─► 003 (Phase 2 — Extraer servicios + DI)
           └─► 004 (Phase 3 — Persistir state + Event Bus)
                └─► 005 (Phase 4a — Control plane backend)
                     └─► 006 (Phase 4b — Control plane frontend) [HITL]
                          └─► 007 (Phase 5 — Dashboard + background jobs)
                               └─► 008 (Phase 6 — SQLAlchemy + Alembic) [XL]
                                    └─► 009 (Phase 7 — PostgreSQL) [HITL]
                                         └─► 010 (Phase 8 — Hardening)
```

Todos los issues son secuenciales — no hay paralelismo posible dado que cada fase depende de la arquitectura establecida en la anterior.

## Parallelizable Groups

**Ninguno** — el refactor es estrictamente secuencial. Cada fase desbloquea la siguiente.

La única excepción: la instalación de PostgreSQL (prerequisito de Issue 009) puede hacerse en paralelo mientras se trabaja en Issues 007-008.

## Estimación Total

| Esfuerzo | Issues | Notas |
|---------|--------|-------|
| S | 0 | |
| M | 8 | 001, 002, 004, 005, 006, 007, 009, 010 |
| L | 1 | 003 |
| XL | 1 | 008 — migración de 35 módulos a SQLAlchemy |

## PRD y Artefactos de Referencia

| Artefacto | Path |
|-----------|------|
| PRD | `docs/dev/artifacts/refactor/08-prd.md` |
| Design Concept | `docs/dev/artifacts/refactor/01-design-concept.md` |
| Architecture Map | `docs/dev/artifacts/refactor/03-architecture-map.md` |
| Interface Design | `docs/dev/artifacts/refactor/06-interface-design.md` |
| Why Decisions | `docs/dev/artifacts/refactor/05-why-decisions.md` |
| Plan arquitectónico completo | `C:\Users\be47\.claude\plans\refactor-zesty-axolotl.md` |

## Criterios de Éxito Globales

- [ ] `grep -r "httpx" app/llm/ app/positions/ app/alerts/` → 0
- [ ] `grep -r "from app.db.database import" app/` → 0
- [ ] `grep -r "_call_opencode" app/` → 1 (solo en `opencode_adapter.py`)
- [ ] `grep -r "shell=True" app/` → 0
- [ ] `alembic upgrade head` desde DB vacía → schema completo < 5s
- [ ] `GET /dashboard/data` p95 < 100ms
- [ ] Suite de unit tests corre en < 30s sin IB Gateway ni Telegram
- [ ] Estado operativo (modo, pausa, parámetros) sobrevive restart de la Pi
