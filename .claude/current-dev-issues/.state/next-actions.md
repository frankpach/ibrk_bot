# Next Actions: arch-refactor

**Module**: arch-refactor
**Last Updated**: 2026-05-14

## ✅ Fase 0 — Completa (2026-05-14)

WAL mode, OPENCODE_CWD, OpenCodeAdapter, X-Control-Key auth. 839/839 tests green.

## Current Focus

**Phase**: Fase 1 — Eliminar HTTP interno
**Goal**: Reemplazar `llm/loop.py → POST /orders/place` (httpx interno) con llamada directa a `ExecuteOrderUseCase`

## Next Action (Do This Now)

1. **Crear `app/application/trading/execute_order.py`** — `ExecuteOrderUseCase`
   - Extrae la lógica actual de `POST /orders/place` en `app/api/main.py`
   - Parámetros: symbol, action, quantity, order_type, stop_loss_pct, take_profit_pct, limit_price (optional)
   - Feature flag: `USE_DIRECT_CALLS=true` en `.env` para rollback sin revert de código (D-06)

2. **Actualizar `app/llm/loop.py`**
   - Reemplazar `httpx.post(f"{API_BASE}/orders/place", ...)` por `ExecuteOrderUseCase().execute(...)`
   - Verificar que `app/positions/manager.py` también usa HTTP interno y migrar si aplica

3. **Mantener `POST /orders/place` en main.py** — ahora solo llama `ExecuteOrderUseCase`; no eliminar el endpoint todavía

## Backlog

- [ ] Fase 1 — Eliminar HTTP interno (loop.py, positions/manager.py) — después de Fase 0
- [ ] Fase 2 — Extraer servicios de aplicación (ports, use cases, scheduler split) — después de Fase 1
- [ ] Fase 3 — Persistir system state en DB — después de Fase 2
- [ ] Fase 4 — Control plane /control — después de Fase 3
- [ ] Fase 5 — Desacoplar dashboard/reportes — después de Fase 4
- [ ] Fase 6 — Doble soporte SQLite/PostgreSQL — después de Fase 5
- [ ] Fase 7 — Migrar a PostgreSQL — después de Fase 6
- [ ] Fase 8 — Endurecimiento final — después de Fase 7
