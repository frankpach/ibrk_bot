# Module Registry: arch-refactor

**Module**: arch-refactor
**Last Updated**: 2026-05-14

## This Module

**Name**: arch-refactor
**Scope**: Transversal — afecta toda la codebase app/
**Status**: in_development
**Plan**: `C:\Users\be47\.claude\plans\para-el-promp-glowing-quasar.md`

## Estructura Objetivo (post-refactor)

```
app/
├── domain/          # Entidades, eventos, value objects — sin deps externas
├── application/     # Use cases + ports (interfaces)
├── infrastructure/  # Implementaciones: DB repos, IBKR adapter, LLM adapter, Telegram
├── interfaces/      # FastAPI routes (thin); Telegram bot handlers
├── readmodels/      # DTOs para dashboard y reportes
└── scheduler/       # APScheduler setup + job orchestration (sin lógica de negocio)
```

## Módulos Afectados por Fase

| Fase | Módulos principales |
|------|---------------------|
| 0 | database.py, llm/agent.py, llm/postmortem.py, analysis/pipeline.py, api/main.py |
| 1 | llm/loop.py, positions/manager.py, nueva application/trading/execute_order.py |
| 2 | run.py, api/main.py, nueva application/ completo |
| 3 | system/controller.py, database.py → repos, nueva domain/config/events.py |
| 4 | Nueva interfaces/api/control_plane_routes.py, application/config/ |
| 5 | api/dashboard.py → split, nueva infrastructure/db/read_models/ |
| 6–7 | Nueva infrastructure/db/repositories/postgres_*, migration script |
| 8 | Hardening global |

## Nuevos Módulos a Crear

| Módulo | Fase | Propósito |
|--------|------|-----------|
| app/application/ports/ | 2 | Interfaces ITradeRepository, ISignalRepository, etc. |
| app/application/trading/ | 1–2 | ExecuteOrderUseCase, ClosePositionUseCase |
| app/application/config/ | 3–4 | SetTradingModeCommand, UpdateRiskConfigCommand |
| app/infrastructure/llm/opencode_adapter.py | 0 | Unifica 3× _call_opencode() |
| app/infrastructure/db/repositories/ | 2–3 | SQLiteTradeRepo, SQLiteSignalRepo, etc. |
| app/infrastructure/db/read_models/ | 5 | DashboardQueryService, ReportQueryService |
| app/infrastructure/events/in_process_event_bus.py | 3 | IEventBus en proceso único |
| app/interfaces/api/control_plane_routes.py | 4 | /control/* endpoints |
| app/scheduler/runner.py + jobs.py | 2 | Split de run.py |
| app/readmodels/ | 4–5 | DashboardStateDTO, ControlPlaneStateDTO |
