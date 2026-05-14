# Current Objective

**Phase**: Phase 1 — Eliminar HTTP interno (Fases del plan: 0–9)
**Fase 0**: ✅ Completa (2026-05-14) — WAL mode, OPENCODE_CWD, OpenCodeAdapter, X-Control-Key auth
**Module**: arch-refactor
**Started**: 2026-05-14

## Goal

Refactor arquitectónico profundo e incremental del sistema de trading IBKR. Desacoplar HTTP interno, extraer ports/adapters/use-cases, persistir system state, crear control plane /control, preparar migración SQLite→PostgreSQL.

Plan completo: `C:\Users\be47\.claude\plans\para-el-promp-glowing-quasar.md`

## Fase 0 — Próxima a ejecutar

**Quick Wins Seguros** (1–2 días):
1. Activar WAL mode + busy_timeout en SQLite (`app/db/database.py`)
2. Mover `cwd="/home/frankpach/ibkr-bot"` y OPENCODE_BIN a `settings.py`
3. Unificar 3× `_call_opencode()` en `infrastructure/llm/opencode_adapter.py`
4. Añadir `X-Control-Key` auth en endpoints de sistema (pause/resume/mode)

## Fases del Roadmap

| Fase | Objetivo | Estado |
|------|----------|--------|
| 0 | Quick wins (WAL, subprocess, auth) | pending |
| 1 | Eliminar HTTP interno (loop.py, positions/manager.py) | pending |
| 2 | Extraer servicios de aplicación (ports, use cases) | pending |
| 3 | Persistir system state en DB (eliminar globals mutables) | pending |
| 4 | Control plane /control | pending |
| 5 | Desacoplar dashboard/reportes | pending |
| 6 | Doble soporte SQLite/PostgreSQL | pending |
| 7 | Migrar a PostgreSQL | pending |
| 8 | Endurecimiento final | pending |
| 9 | Paralelismo y workers (opcional) | future |

## Blockers
None
