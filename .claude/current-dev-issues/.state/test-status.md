# Test Status: arch-refactor

**Module**: arch-refactor
**Last Updated**: 2026-05-14

## Latest Run

No tests run yet. Module in planning phase.
Reference: 764 tests passing at end of live-dashboard module.

## Status

Unit: not run (Fase 0 — run before committing)
Integration: not run
E2E: not run
Mypy: not run
Linting: not run

## Test Strategy por Fase

| Fase | Tests requeridos antes de cerrar |
|------|----------------------------------|
| 0 | pytest tests/ — all green; sistema corre 24h sin errores |
| 1 | pytest tests/integration/test_trade_lifecycle.py sin httpx mocks |
| 2 | pytest tests/ — all green; scheduler jobs corren correctamente |
| 3 | test de persistencia de modo entre reinicios; test de audit log |
| 4 | test de auth; test de audit; test de hot-reload config |
| 5 | /dashboard/data < 500ms; test de consistencia de DTOs |
| 6–7 | pytest --backend=postgres; validar migración de datos |
| 8 | bandit -r app/; no settings.X = Y fuera de config repo |

## Nuevos Tests a Crear (por fase)

- Fase 1: `tests/integration/test_execute_order_direct.py`
- Fase 2: `tests/unit/application/test_execute_order_usecase.py`
- Fase 3: `tests/system/test_mode_persistence.py`, `tests/system/test_audit_log.py`
- Fase 4: `tests/control_plane/test_auth.py`, `tests/control_plane/test_mode_change.py`
- Fase 6: `tests/adapters/test_postgres_trade_repo.py`
