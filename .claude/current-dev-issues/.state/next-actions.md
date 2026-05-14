# Next Actions: arch-refactor

**Module**: arch-refactor
**Last Updated**: 2026-05-14

## Current Focus

**Phase**: Fase 0 — Quick Wins Seguros
**Goal**: Reducir deuda sin tocar lógica de negocio; cambios seguros y reversibles

## Next Action (Do This Now)

Ejecutar Fase 0 del plan. Los 4 cambios son independientes y pueden hacerse en cualquier orden:

1. **WAL mode + busy_timeout** en `app/db/database.py`
   - Añadir `PRAGMA journal_mode=WAL` y `PRAGMA busy_timeout=5000` en `init_db()` o `get_connection()`

2. **Mover paths hardcodeados a settings.py**
   - `cwd="/home/frankpach/ibkr-bot"` → `settings.OPENCODE_CWD`
   - En: `app/llm/agent.py`, `app/llm/postmortem.py`, `app/analysis/pipeline.py`

3. **Unificar `_call_opencode()`** en `app/infrastructure/llm/opencode_adapter.py`
   - Crear módulo con `OpenCodeAdapter` que implementará `ILLMService` (Fase 2)
   - Los 3 módulos actuales importan de ahí

4. **Auth `X-Control-Key`** en endpoints de sistema
   - `POST /system/pause`, `POST /system/resume`, `POST /system/mode/{mode}`
   - `POST /orders/place`, `POST /orders/close*`, `POST /orders/close-all`
   - `POST /symbols/approve/{symbol}`

## Backlog

- [ ] Fase 1 — Eliminar HTTP interno (loop.py, positions/manager.py) — después de Fase 0
- [ ] Fase 2 — Extraer servicios de aplicación (ports, use cases, scheduler split) — después de Fase 1
- [ ] Fase 3 — Persistir system state en DB — después de Fase 2
- [ ] Fase 4 — Control plane /control — después de Fase 3
- [ ] Fase 5 — Desacoplar dashboard/reportes — después de Fase 4
- [ ] Fase 6 — Doble soporte SQLite/PostgreSQL — después de Fase 5
- [ ] Fase 7 — Migrar a PostgreSQL — después de Fase 6
- [ ] Fase 8 — Endurecimiento final — después de Fase 7
