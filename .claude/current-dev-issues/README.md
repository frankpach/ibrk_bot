# arch-refactor — Development Issues

**Module**: arch-refactor
**Started**: 2026-05-14
**Status**: planning — Fase 0 pending
**Plan**: `C:\Users\be47\.claude\plans\para-el-promp-glowing-quasar.md`

## Objetivo

Refactor arquitectónico profundo e incremental: desacoplar HTTP interno, extraer ports/adapters/use-cases, persistir system state, control plane /control, SQLite→PostgreSQL.

## Issue List

[To be populated in Phase 4 — /150-planning]

## Dependency Graph

[To be populated in Phase 4]

## Parallelizable Groups

[To be populated in Phase 4]

## Fases del Roadmap

| Fase | Objetivo | Estado |
|------|----------|--------|
| 0 | Quick wins: WAL mode, subprocess unify, auth | pending |
| 1 | Eliminar HTTP interno (loop.py → execute_order direct) | pending |
| 2 | Extraer servicios: ports, use cases, scheduler split | pending |
| 3 | Persistir system state (globals → DB), audit log, events | pending |
| 4 | Control plane /control | pending |
| 5 | Desacoplar dashboard/reportes → read models | pending |
| 6 | Doble soporte SQLite/PostgreSQL | pending |
| 7 | Migrar a PostgreSQL | pending |
| 8 | Endurecimiento final (security, cleanup) | pending |
| 9 | Paralelismo y workers separados (opcional) | future |
