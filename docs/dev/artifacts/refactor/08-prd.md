# PRD: Refactor Arquitectónico — IBKR AI Trader

**Module**: refactor
**Phase**: Phase 3 — Requirements
**Status**: ✓ Complete
**Date**: 2026-05-14
**Author**: Frank Pacheco
**Previous artifact**: docs/dev/artifacts/refactor/06-interface-design.md
**Next artifact**: docs/dev/artifacts/refactor/09-plan.md

---

## Overview

El IBKR AI Trader es un sistema de trading semi-autónomo en producción (Raspberry Pi + IB Gateway, acceso Tailscale). El sistema funciona pero tiene deuda arquitectónica crítica: estado operativo en memoria volátil, monolito de DB de 1,277 LOC importado por 35 módulos, HTTP interno entre módulos del mismo proceso, y ausencia de UI para configurar parámetros sin SSH + edición de `.env`.

Este PRD especifica los requisitos funcionales, de aceptación, de seguridad y de rendimiento para el refactor completo organizado en 9 fases incrementales (0–8), más la Fase 9 opcional de paralelismo.

---

## Open Questions Resueltas

Las tres preguntas abiertas de Phase 2 se resuelven aquí con decisiones pragmáticas:

| Pregunta | Decisión |
|----------|---------|
| **DB URL bootstrap**: precedencia `.env` vs `control_settings` | `.env` es la fuente de verdad al primer arranque. Una vez que `control_settings` tiene la clave `database_url`, esa tiene precedencia en todos los arranques posteriores. Si la DB es inaccesible al arrancar, el sistema falla rápido con error claro en log. |
| **Secret rotation**: re-cifrado automático o manual al cambiar `SECRET_ENCRYPTION_KEY` | **Manual**: al cambiar la clave, el sistema detecta al arrancar que no puede descifrar los secrets existentes, loguea un error por cada secret que falla, y el control plane muestra un banner "⚠ N secrets no pueden descifrarse — re-ingrésalos". El admin re-introduce cada secret desde `/control/api-keys`. No hay auto re-cifrado. |
| **Cambio a live con posiciones abiertas** | **Advertencia + doble confirmación** (no bloqueo duro). El modal muestra "Tienes X posiciones abiertas. Al cambiar a live, estas posiciones seguirán siendo monitoreadas con el modo live. ¿Confirmar?" con checkbox adicional. El Developer puede hacer bloqueo duro con un feature flag `REQUIRE_NO_POSITIONS_FOR_LIVE_MODE`. |

---

## Goals y Success Metrics

| Goal | Métrica de éxito |
|------|----------------|
| Estado persistente | `trading_mode`, `is_paused`, todos los parámetros de riesgo sobreviven restart de la Pi |
| Tests sin infra | Suite de unit tests de use cases corre en < 30s sin IB Gateway, Telegram ni DB real |
| Sin HTTP interno | `grep -r "httpx" app/llm/ app/positions/ app/alerts/` devuelve 0 resultados |
| Control plane completo | Todo parámetro operativo editable desde `/control` sin tocar código ni SSH |
| Audit trail | Cada cambio en `/control` → fila en `audit_log` con `changed_by`, `old_value`, `new_value`, `occurred_at` |
| SQLAlchemy completo | `grep -r "from app.db.database import" app/` devuelve 0 resultados |
| Alembic | `alembic upgrade head` aplica limpiamente desde schema vacío |
| PostgreSQL ready | Suite completa de tests pasa con `DATABASE_URL=postgresql://...` |
| API keys cifradas | Ninguna API key visible en plain text en DB, logs ni API responses |
| Dashboard rápido | `GET /dashboard/data` p95 < 100ms |
| OpenCode consolidado | 1 sola implementación de `_call_opencode()` — `infrastructure/llm/opencode_adapter.py` |

---

## Personas

Ver [02-persona-journey.md](02-persona-journey.md).

- **Frank — Trader**: opera el sistema en mercado, ajusta parámetros, aprueba órdenes live, monitorea desde browser/Telegram
- **Frank — Developer**: mantiene el código, escribe tests, hace deploys, corre migraciones

---

## Requisitos Funcionales por Fase

### Fase 0 — Quick Wins (RF-0xx)

**RF-001** — Consolidar `_call_opencode()`
- El sistema tiene exactamente 1 implementación de `_call_opencode()`: `infrastructure/llm/opencode_adapter.py`
- Los archivos `llm/agent.py`, `analysis/pipeline.py`, `notifications/telegram_bot.py` eliminan sus implementaciones locales y usan el adapter
- El adapter valida que `OPENCODE_BIN` es un path absoluto existente al instanciarse
- El adapter rechaza símbolos que no pasen `SAFE_SYMBOL_RE = re.compile(r'^[A-Z0-9./=]{1,20}$')` con `ValueError`

**RF-002** — Transaction context manager
- Existe `@contextmanager get_session(engine)` en `infrastructure/db/connection.py` (o equivalente Alembic/SQLAlchemy)
- El context manager hace `session.commit()` al salir sin error y `session.rollback()` al salir con excepción
- `PlaceOrderUseCase` (Fase 2) y `ClosePositionUseCase` (Fase 2) usan este context manager

**RF-003** — Persistir estado operativo desde el primer día
- `trading_mode` y `is_paused` se guardan en la tabla `control_settings` al arrancar
- Si `control_settings` no existe aún, se leen de `.env` y se escriben a la tabla durante `bootstrap/db_init.py`
- Al reiniciar la app, el sistema carga el modo y el estado de pausa desde `control_settings`
- **AC (Acceptance Criteria)**:
  - [ ] Cambiar modo a `paper`, reiniciar app → sistema arranca en `paper`
  - [ ] Pausar sistema, reiniciar app → sistema arranca pausado
  - [ ] Si `control_settings` no existe, bootstrapea desde `.env` correctamente

**RF-004** — Logging estructurado
- Todos los módulos de `application/` y `infrastructure/` usan `structlog`
- Cada línea de log incluye: `event`, `symbol` (si aplica), `trade_id` (si aplica), `job_id` (si aplica)
- Los secrets no aparecen en logs — los valores de campos `is_secret=True` se loguean como `[REDACTED]`

---

### Fase 1 — Eliminar HTTP Interno (RF-1xx)

**RF-101** — Port `IBrokerPort`
- Existe la interface `IBrokerPort` en `application/ports/broker_port.py` con métodos:
  - `get_price(symbol, sec_type, exchange, currency) -> Decimal`
  - `place_order(order: Order) -> OrderResult`
  - `get_portfolio() -> list[Position]`
  - `get_account() -> AccountSummary`
  - `reconnect(port: int) -> None`
- Existe `IBKRBrokerAdapter(IBrokerPort)` en `infrastructure/broker/ibkr_adapter.py` que wrappea el `IBKRClient` existente
- Existe `MockBrokerAdapter(IBrokerPort)` en `infrastructure/broker/mock_adapter.py` para tests

**RF-102** — Eliminar httpx en módulos de trading
- `llm/loop.py` no importa `httpx`
- `positions/manager.py` no importa `httpx`
- `alerts/manager.py` no importa `httpx`
- `mcp/server.py` puede mantener httpx para comunicación externa, no para llamadas internas a la propia API
- **AC**:
  - [ ] `grep -r "httpx" app/llm/loop.py app/positions/ app/alerts/` → 0 resultados
  - [ ] Tests de `ProcessSignalUseCase` (Fase 2) pasan sin servidor HTTP corriendo

**RF-103** — Ports para LLM y Notificaciones
- Existe `ILLMPort` en `application/ports/llm_port.py`:
  - `analyze_signal(signal: Signal) -> LLMDecision`
  - `run_postmortem(trade: Trade, patterns: list[Pattern]) -> PostmortemResult`
  - `interpret_analysis(context: AnalysisContext) -> AnalysisNarrative`
- Existe `INotificationPort` en `application/ports/notification_port.py`:
  - `notify(message: str, severity: Severity) -> None`
  - `request_approval(context: ApprovalRequest) -> ApprovalResult`
- Existen mocks para ambas interfaces en `tests/mocks/`

---

### Fase 2 — Extraer Servicios de Aplicación (RF-2xx)

**RF-201** — `PlaceOrderUseCase`
- Encapsula toda la lógica de `POST /orders/place` (actualmente 140 líneas en el handler)
- Recibe `PlaceOrderCommand(symbol, action, quantity, signal_strength, requested_by)`
- Flujo: validar risk → dedup check → (si live) request approval → IB order → DB insert → emitir `OrderPlaced`
- Lock por símbolo: no pueden correr dos `PlaceOrderUseCase` para el mismo símbolo simultáneamente
- Devuelve `PlaceOrderResult(success, order_id, trade_id, error)`
- **AC**:
  - [ ] Test: signal STRONG → orden placed → `OrderPlaced` event emitido
  - [ ] Test: risk validation falla → no order, no DB insert, no event
  - [ ] Test: dos órdenes simultáneas para el mismo símbolo → solo 1 ejecutada
  - [ ] Test: handler FastAPI delega completamente al use case (< 5 líneas en el handler)

**RF-202** — `ClosePositionUseCase`
- Encapsula lógica de cierre de posición (actualmente dispersa en `positions/manager.py` y `api/main.py`)
- Recibe `ClosePositionCommand(trade_id, reason, requested_by)`
- Flujo: get trade → get current price (broker) → IB sell order → DB update → emitir `PositionClosed`
- Lock por símbolo: no puede ejecutarse mientras hay un `PlaceOrderUseCase` activo para el mismo símbolo
- **AC**:
  - [ ] Test: posición abierta → cierre exitoso → `PositionClosed` event con `pnl_usd` correcto
  - [ ] Test: posición ya cerrada → idempotente, no duplica la operación

**RF-203** — `RiskService`
- Métodos: `validate_order(symbol, quantity, price) -> ValidationResult`, `check_circuit_breaker() -> bool`, `calculate_position_size(symbol, risk_pct, price) -> int`
- Lee parámetros de riesgo desde `ISystemStateRepository` (no desde `settings.py`)
- **AC**:
  - [ ] Test: `max_positions=3` con 3 posiciones abiertas → `validate_order` rechaza
  - [ ] Test: `capital_cap=500` con order value > 500 → rechaza
  - [ ] Test: cambiar `max_risk_pct` en `control_settings` → `RiskService` usa nuevo valor sin restart

**RF-204** — `PositionService`
- Métodos: `apply_trailing_stop(trade, current_price) -> Trade`, `check_exit_conditions(trade, current_price) -> ExitCondition | None`, `apply_partial_exit(trade, current_price) -> PartialExitResult`
- Lógica movida desde `trailing_stop.py`, `partial_exit.py`, `positions/manager.py`
- No tiene module-level instances — todo inyectado

**RF-205** — Dividir `api/main.py`
- El archivo `app/api/main.py` se divide en:
  - `interfaces/api/routes/trading_routes.py` — `/orders/*`, `/trades/*`
  - `interfaces/api/routes/market_routes.py` — `/price/*`, `/signals`, `/patterns/*`
  - `interfaces/api/routes/system_routes.py` — `/system/*`, `/health`
  - `interfaces/api/routes/analysis_routes.py` — `/backtest/*`, `/candidate-analysis/*`
  - `interfaces/api/routes/reports_routes.py` — `/reports/*`
  - `interfaces/api/routes/control_routes.py` — `/control/*` (nuevo)
  - `interfaces/api/app.py` — FastAPI app con `include_router()` para cada uno
- Ningún route handler supera 30 líneas de lógica

**RF-206** — `container.py` (DI)
- Existe `app/container.py` con `get_container() -> Container` decorado con `@lru_cache(maxsize=1)`
- Instancia todos los adapters, repositorios y use cases con sus dependencias
- `run.py` importa y usa el container — no instancia dependencias directamente
- **AC**:
  - [ ] `get_container()` llamado dos veces devuelve la misma instancia
  - [ ] Tests usan `test_container()` que sustituye adapters reales por mocks

**RF-207** — Slim `run.py`
- `run.py` tiene < 60 líneas
- Solo hace: `init_container()` → `apply_migrations()` → `start_scheduler()` → `start_telegram_bot()` → `start_api()`
- Toda lógica de reconexión IB está en `bootstrap/gateway_watchdog.py`
- Toda lógica de registro de jobs está en `bootstrap/scheduler_setup.py`
- Los jobs del scheduler son funciones nombradas en `scheduler/jobs.py` (no lambdas)

---

### Fase 3 — Persistir System State y Auditoría (RF-3xx)

**RF-301** — Tabla `control_settings`
- Schema:
  ```sql
  CREATE TABLE control_settings (
      key              TEXT PRIMARY KEY,
      value            TEXT NOT NULL,       -- JSON serializado
      value_type       TEXT NOT NULL,       -- "bool"|"float"|"int"|"str"|"list"
      label            TEXT,
      description      TEXT,
      is_secret        BOOLEAN DEFAULT FALSE,
      requires_restart BOOLEAN DEFAULT FALSE,
      updated_at       TEXT,
      updated_by       TEXT
  );
  ```
- Settings iniciales populados por Alembic seed o bootstrap desde `.env`
- La tabla existe antes de que arranque el resto de la app (creada en migración 002)

**RF-302** — `PersistedSystemState(ISystemStateRepository)`
- Métodos: `get_setting(key) -> Any`, `save_setting(key, value, updated_by) -> None`, `get_all() -> dict`
- Lee y escribe en `control_settings` via SQLAlchemy
- Campos `is_secret=True`: el valor se almacena cifrado con `SecretManager.encrypt()`; `get_setting()` devuelve el valor descifrado para uso interno; la API devuelve `••••••••`

**RF-303** — Tabla `audit_log`
- Schema:
  ```sql
  CREATE TABLE audit_log (
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      event_type   TEXT NOT NULL,
      entity_type  TEXT,
      entity_id    TEXT,
      old_value    TEXT,
      new_value    TEXT,
      changed_by   TEXT NOT NULL,
      ip_address   TEXT,
      occurred_at  TEXT NOT NULL
  );
  ```
- Append-only: el sistema nunca hace UPDATE ni DELETE sobre esta tabla
- Campos con `is_secret=True`: `old_value` y `new_value` se registran como `[SECRET_UPDATED]`

**RF-304** — `ChangeTradingModeUseCase`
- Flujo:
  1. Verificar Admin Key (lo hace el middleware antes de llamar al use case)
  2. Contar posiciones abiertas → si > 0, devolver advertencia (no bloquear)
  3. Determinar nuevo puerto: `live → 4001`, `paper → 4002`
  4. `ISystemStateRepository.save_setting("trading_mode", mode)`
  5. `ISystemStateRepository.save_setting("ib_port", port)`
  6. `IBrokerPort.reconnect(port=port)` — reconexión automática
  7. Emitir `TradingModeSwitched(old_mode, new_mode, new_port, changed_by)`
- **AC**:
  - [ ] Paper → live: `ib_port` cambia a 4001 en `control_settings`
  - [ ] Reconexión IB ocurre automáticamente sin restart
  - [ ] Con posiciones abiertas: advertencia devuelta en response, pero no bloqueo
  - [ ] Audit log tiene entrada con `changed_by="admin_key"`
  - [ ] Telegram recibe notificación del cambio

**RF-305** — `PauseSystemUseCase` / `ResumeSystemUseCase`
- Pausa: pausa los jobs `signal_processor`, `scanner`, `scanner_fetch`, `news_fetch` en APScheduler
- Pausa: NO pausa `position_manager`, `circuit_breaker`, `gateway_watchdog` (safety-critical)
- Persiste `is_paused` en `control_settings`
- Emite `SystemPaused` / `SystemResumed`
- **AC**:
  - [ ] Sistema pausado: `signal_processor` no corre en los próximos 15 min
  - [ ] Sistema pausado: `position_manager` sigue corriendo cada 2 min
  - [ ] Restart con sistema pausado → arranca pausado
  - [ ] Barra de estado muestra `⏸ Pausado`

**RF-306** — Event Bus in-process
- Existe `EventBus` en `application/event_bus.py` con `subscribe(event_type, handler)` y `publish(event)`
- `publish()` itera handlers síncronamente; cada handler está en try/except — un handler que falla no interrumpe los demás
- Los errores en handlers se loguean con `structlog.error()` pero no se propagan al use case
- Handlers registrados en `container.py`
- **AC**:
  - [ ] Test: handler que lanza excepción no interrumpe la publicación a los demás handlers
  - [ ] Test: `PositionClosed` → `PostmortemHandler` + `TelegramNotificationHandler` + `AuditLogHandler` se ejecutan los tres

---

### Fase 4 — Control Plane `/control` (RF-4xx)

**RF-401** — Barra de estado (`SystemStatusBar`)
- Componente React presente en el layout del dashboard (`dashboard.py` o layout compartido)
- Hace `GET /control/status` cada 30s sin autenticación
- Muestra: modo (PAPER/LIVE), puerto IB, estado (Activo/Pausado), P&L hoy, conectividad IB
- Clickable → navega a `/control`
- **AC**:
  - [ ] La barra muestra estado correcto tras restart sin recarga manual
  - [ ] Si IB Gateway cae, la barra muestra `IB: ✗` en el próximo ciclo de 30s

**RF-402** — Página `/control` con sidebar de 7 secciones
- Secciones: Operativo, Riesgo, Símbolos, Infraestructura, Jobs, API Keys, Audit Log
- Cada sección es un componente React independiente (`OperationalPanel.jsx`, etc.)
- La URL refleja la sección activa: `/control?section=risk`

**RF-403** — Sección "Operativo"
- Controles: modo paper/live (radio buttons), pausar/reanudar (botones), reset circuit breaker (botón)
- Cambio a live: modal con confirmación, campo Admin Key, advertencia si hay posiciones abiertas
- Pausa/reanuda: Control Key — feedback inmediato en UI
- Circuit breaker: muestra estado (activo/activado), threshold, botón reset (Control Key)

**RF-404** — Sección "Riesgo"
- Settings: `max_positions`, `max_risk_pct`, `min_risk_usd`, `max_position_usd`, `capital_cap`
- Edición inline: campo de texto editable con validación antes de guardar
- Validaciones: tipos numéricos, rangos mínimo/máximo, no negativos
- Hot-reload: ninguno requiere restart → el próximo ciclo del risk service usa el nuevo valor
- **AC**:
  - [ ] Editar `max_risk_pct` a valor inválido (negativo) → error de validación, no se guarda
  - [ ] Editar `max_risk_pct` a valor válido → guardado, audit log, hot-reload

**RF-405** — Sección "Infraestructura"
- Settings: `ib_host`, `ib_port`, `database_url`, `opencode_bin`, `opencode_model`, `opencode_cwd`
- Requiere Admin Key para escritura
- `database_url` y `telegram_bot_token` muestran banner `⚠ Requiere restart`
- Al guardar cualquier setting con `requires_restart=True`: banner persistente en UI "Cambios pendientes de restart"
- `ib_port` no se edita directamente — se cambia vía Cambio de Modo (que determina el puerto automáticamente)

**RF-406** — Sección "API Keys"
- Lista de secrets: `LLM_API_KEY`, `TELEGRAM_BOT_TOKEN`, `API_CONTROL_KEY`, `API_ADMIN_KEY`, cualquier key añadida
- Muestra: `KEY_NAME: ••••••••  [Actualizar]`
- Al hacer click "Actualizar": campo tipo `password`, botón guardar con Admin Key
- El valor nunca aparece en plain text en ninguna respuesta de API
- Al cambiar `SECRET_ENCRYPTION_KEY`: banner "N secrets no pueden descifrarse — re-ingrésalos"

**RF-407** — Sección "Jobs"
- Lista todos los jobs de APScheduler con: nombre, `last_run` (timestamp + duración), `next_run`, `status` (ok/error/running)
- Botón `[▶ Ejecutar ahora]` para trigger manual (Control Key)
- **AC**:
  - [ ] Trigger manual de `signal_processor` → job corre + timestamp `last_run` actualiza
  - [ ] Job que fallará en el próximo run muestra `status: error` con mensaje del último error

**RF-408** — Sección "Audit Log"
- Tabla paginada (últimas 50 entradas por defecto)
- Columnas: `occurred_at`, `event_type`, `entity`, `changed_by`, `old_value`, `new_value`
- Los secrets muestran `[SECRET_UPDATED]` en old/new value
- Requiere Control Key para ver
- **AC**:
  - [ ] Cada cambio en cualquier sección de `/control` → entrada nueva en audit log
  - [ ] Secrets nunca visibles en plain text en la tabla

**RF-409** — `UpdateControlSettingUseCase`
- Valida: tipo del valor (int/float/bool/str), rango si aplica, enum si aplica
- Si `is_secret=True`: cifra antes de persistir
- Persiste en `control_settings`
- Emite `ControlSettingChanged(key, old_value, new_value, changed_by)`
- Si `requires_restart=False`: `HotReloadHandler` aplica el valor en caliente
- **AC**:
  - [ ] `max_risk_pct = -0.5` → ValidationError, no persistido, no evento
  - [ ] `max_risk_pct = 0.015` → persistido, evento emitido, audit log, hot-reload
  - [ ] `telegram_bot_token` (secret) → cifrado en DB, `[REDACTED]` en evento y log

---

### Fase 5 — Dashboard Solo Lectura y Background Jobs (RF-5xx)

**RF-501** — `DashboardDataQuery`
- Reemplaza la función de 270 líneas del handler `/dashboard/data`
- Ejecuta máximo 3 queries SQLAlchemy optimizadas (joins en lugar de N+1)
- Devuelve `DashboardView` dataclass con todos los datos del dashboard
- **AC**:
  - [ ] `GET /dashboard/data` p95 < 100ms en producción (Pi con SQLite)
  - [ ] `DashboardDataQuery` no importa ningún use case de escritura

**RF-502** — Background job system
- Tabla `background_jobs` con campos: `id` (UUID), `job_type`, `status`, `params` (JSON), `result` (JSON), `error`, `progress_pct`, `progress_msg`, `created_at`, `started_at`, `completed_at`
- `BackgroundJobRunner` usa `ThreadPoolExecutor(max_workers=3)`
- Jobs LLM analysis, backtest, opportunity scan se ejecutan en background
- **API**:
  - `POST /jobs/llm-analysis { symbol }` → `{ job_id }` (respuesta inmediata < 100ms)
  - `POST /jobs/backtest { symbol }` → `{ job_id }`
  - `GET /jobs/{job_id}` → `{ status, progress_pct, result?, error? }`
- **AC**:
  - [ ] `POST /jobs/llm-analysis` responde en < 100ms mientras el análisis corre en background
  - [ ] `GET /jobs/{job_id}` refleja el status actualizado durante la ejecución
  - [ ] Job que tarda > 60s es marcado como `failed` con error `timeout`
  - [ ] `GET /health` responde < 100ms mientras hay jobs corriendo

**RF-503** — Read models para reportes
- `GET /reports` y `GET /reports/{id}` leen únicamente de `analysis_reports` SQLAlchemy
- No tocan tablas operativas (`trades`, `signals`) para renderizar reportes
- **AC**:
  - [ ] Reportes cargados sin depender del estado de posiciones abiertas

---

### Fase 6 — Doble Soporte SQLite/PostgreSQL (RF-6xx)

**RF-601** — SQLAlchemy models para las 17 tablas
- Cada tabla tiene su `DeclarativeBase` model en `infrastructure/db/models/`
- Los campos JSON usan `sqlalchemy.types.JSON` (compatible con ambos backends)
- Los campos booleanos usan `Boolean` (no `INTEGER` de SQLite)
- Todos los modelos incluyen `updated_at` con `onupdate=func.now()`

**RF-602** — Alembic setup y migraciones
- `alembic.ini` apunta a `DATABASE_URL` desde `control_settings` (con fallback a `.env`)
- `env.py` importa `Base.metadata` de todos los modelos
- Migración `001_initial_schema`: estado actual completo de la DB
- Migraciones `002` a `005`: añadir las tablas nuevas (`control_settings`, `audit_log`, `background_jobs`, columna `updated_at`)
- Cada migración incluye `upgrade()` y `downgrade()`
- **AC**:
  - [ ] `alembic upgrade head` desde DB vacía → schema completo en < 5s
  - [ ] `alembic downgrade base` → DB vacía sin error
  - [ ] `alembic upgrade head` aplicado dos veces → idempotente

**RF-603** — Repositorios SQLAlchemy (8)
- `SQLAlchemyTradeRepository`, `SQLAlchemySignalRepository`, `SQLAlchemySymbolRepository`, `SQLAlchemySystemStateRepository`, `SQLAlchemyAuditLogRepository`, `SQLAlchemyJobRepository`, `SQLAlchemyAccountRepository`, `SQLAlchemyPatternRepository`
- Cada repositorio implementa su interface de `application/ports/`
- **AC**:
  - [ ] `grep -r "from app.db.database import" app/` → 0 resultados
  - [ ] Trade lifecycle completo (insert → update → close) via repositorio en test de integración

**RF-604** — Tests parametrizados por backend
- `@pytest.fixture(params=["sqlite", "postgres"])` en `conftest.py`
- Los tests de repositorio corren contra ambos backends
- El backend PostgreSQL se salta si `TEST_PG_URL` no está definida
- **AC**:
  - [ ] `pytest -k sqlite tests/integration/` → todos pasan
  - [ ] `pytest -k postgres tests/integration/` → todos pasan (si TEST_PG_URL disponible)

**RF-605** — `DatabaseConfig` paramétrica
- `DATABASE_URL` se lee de `control_settings` (si existe) o de `.env`
- Bootstrap: al primer arranque sin `control_settings`, lee `.env` → crea la tabla → guarda la URL en ella
- El engine SQLAlchemy se crea con esta URL
- Si la DB es inaccesible al arrancar → error claro en log, app no arranca

---

### Fase 7 — Migrar a PostgreSQL (RF-7xx)

**RF-701** — Script de migración de datos
- Existe `scripts/migrate_to_postgres.py` que:
  1. Lee todas las filas de SQLite
  2. Las inserta en PostgreSQL via SQLAlchemy
  3. Verifica row counts + checksums por tabla
  4. Imprime reporte: `trades: 142 rows OK, signals: 8 rows OK, ...`
- **Modo dry-run**: `--dry-run` imprime el reporte sin escribir a PostgreSQL
- **AC**:
  - [ ] Dry-run completa sin errores sobre la DB de producción
  - [ ] Migración completa con checksums coincidentes para todas las tablas

**RF-702** — Cambio de `database_url` en producción
- El operador cambia `database_url` desde `/control/infrastructure` (Admin Key)
- El sistema muestra banner "Requiere restart"
- Tras restart, `alembic upgrade head` verifica que PostgreSQL está al día
- **AC**:
  - [ ] Cambio de URL + restart → app conecta a PostgreSQL en el próximo arranque
  - [ ] Los datos migrados previamente están disponibles desde el dashboard

---

### Fase 8 — Hardening Final (RF-8xx)

**RF-801** — systemd hardening
- `/etc/systemd/system/ibkr-trader.service` incluye:
  - `NoNewPrivileges=true`
  - `PrivateTmp=true`
  - `ProtectSystem=strict`
  - `ReadWritePaths=/home/frankpach/ibkr-bot`
  - `EnvironmentFile=/home/frankpach/ibkr-bot/.env.secret`
- `.env.secret` tiene `chmod 600` y no está en el repositorio git
- **AC**:
  - [ ] `systemctl show ibkr-trader | grep NoNewPrivileges` → `yes`

**RF-802** — Security headers FastAPI
- `CORSMiddleware` configurado solo para el host Tailscale (no `*`)
- Respuestas incluyen `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`
- **AC**:
  - [ ] `curl -I http://pi:8088/health | grep X-Frame-Options` → `DENY`

**RF-803** — Subprocess hardening completo
- `OpenCodeLLMAdapter._call()` valida path del binario con `Path.resolve().exists()`
- No usa `shell=True` en ningún subprocess
- El symbol se valida con `SAFE_SYMBOL_RE` antes de incluir en el prompt
- El output de OpenCode se parsea con `json.loads()` en try/except — nunca con `eval()`
- **AC**:
  - [ ] Symbol con caracteres especiales (`;`, `"`, `\n`) → `ValueError` antes de llegar a subprocess
  - [ ] Binario en path no existente → `RuntimeError` con mensaje claro

**RF-804** — Eliminar code paths SQLite (post-Fase 7)
- `SQLiteXxxRepository` clases eliminadas del codebase
- Solo quedan `SQLAlchemy*Repository` genéricos que funcionan con cualquier backend soportado por SQLAlchemy
- `PRAGMA` específicos de SQLite eliminados del código de aplicación
- **AC**:
  - [ ] `grep -r "sqlite3\|PRAGMA\|AUTOINCREMENT" app/` → 0 resultados

---

## Requisitos No Funcionales

### Performance

| Endpoint / Operación | Target p95 | Condición |
|---------------------|-----------|-----------|
| `GET /dashboard/data` | < 100ms | Con SQLite WAL en Pi |
| `GET /control/status` | < 50ms | Sin auth, cacheado 30s en frontend |
| `POST /orders/place` | < 5s | Incluye validación + IB + DB |
| `POST /jobs/llm-analysis` | < 100ms | Solo crea job, no ejecuta |
| `GET /jobs/{id}` | < 50ms | Lectura de tabla background_jobs |
| `alembic upgrade head` | < 5s | Startup sin bloquear la app |
| Startup completo | < 30s | Incluyendo migraciones + IB connection |

### Disponibilidad

- El sistema debe arrancar aunque `control_settings` esté vacío (bootstrap desde `.env`)
- El sistema debe arrancar aunque OpenCode no esté disponible (jobs LLM fallaran, el resto funciona)
- El sistema NO arranca si la DB es inaccesible — falla rápido con error claro

### Escalabilidad

- Diseñado para proceso único; sin cambios de arquitectura para soportar hasta 50 símbolos en el universo

---

## Seguridad

### Autenticación y Autorización

| Recurso | Control Key | Admin Key | Sin auth |
|---------|------------|-----------|----------|
| `GET /control/status` | | | ✓ |
| `GET /control/settings` | | | ✓ (secrets ocultos) |
| `PUT /control/settings/*` (no-secret) | ✓ | ✓ | |
| `PUT /control/settings/*` (secret/infra) | | ✓ | |
| `POST /control/mode/live` | | ✓ | |
| `POST /control/pause`, `/resume` | ✓ | ✓ | |
| `POST /control/circuit-breaker/reset` | ✓ | ✓ | |
| `POST /control/jobs/*/trigger` | ✓ | ✓ | |
| `GET /control/audit` | ✓ | ✓ | |
| `POST /control/symbols/approve` | | ✓ | |
| `POST /orders/place`, `/orders/close/*` | ✓ | ✓ | |
| `GET /dashboard`, `/dashboard/data` | | | ✓ |

### Secrets

- `SECRET_ENCRYPTION_KEY` nunca está en el repositorio git ni en `control_settings`
- Solo en `.env.secret` con `chmod 600` (local) o en `systemd` credentials (Pi)
- Los campos `is_secret=True` en `control_settings` almacenan el valor cifrado con Fernet
- `GET /control/settings` devuelve `"value": "••••••••"` para campos secret — nunca el valor real
- Los eventos de dominio con old/new value de secrets usan `[REDACTED]`

### Subprocess

- El binary `OPENCODE_BIN` se valida al arrancar: path absoluto, existe, es ejecutable
- `shell=False` en todos los subprocess
- El símbolo se valida contra `SAFE_SYMBOL_RE` antes de incluirlo en cualquier prompt
- Timeout hard de 60s para analysis y postmortem; 150s para comandos Telegram

### Auditoría

- Toda escritura en `/control` genera una fila en `audit_log`
- El `changed_by` refleja el nivel de auth usado: `"control_key"` o `"admin_key"`
- El `ip_address` se extrae del header `X-Forwarded-For` o la IP directa del request

---

## Edge Cases

| Caso | Comportamiento esperado |
|------|------------------------|
| `SECRET_ENCRYPTION_KEY` rotada sin re-cifrar | Al arrancar: error por secret en `get_setting()`, banner en `/control/api-keys`: "N secrets no pueden descifrarse" |
| DB inaccesible al arrancar | App no arranca, log: `FATAL: cannot connect to database: <URL>` |
| IB Gateway caído al arrancar | App arranca, scheduler pausa jobs de trading, `gateway_watchdog` intenta reconectar cada 5 min |
| OpenCode binario no encontrado | App arranca, jobs LLM fallan con error claro, trading técnico continúa |
| Job lleva > 60s | `BackgroundJobRunner` cancela el thread, marca job como `failed` con `error: "timeout after 60s"` |
| Dos `/orders/place` para el mismo símbolo simultáneamente | Lock por símbolo: el segundo espera a que termine el primero |
| Migración Alembic falla a mitad | `alembic downgrade -1` disponible; log indica qué migración falló |
| Cambio de `database_url` apunta a DB vacía | Al restart: `alembic upgrade head` crea el schema; datos de producción no migrados (operador debe migrar primero) |
| `max_positions` cambiado a 0 | `SettingValidator` rechaza: mínimo 1 |
| Barra de estado no puede alcanzar `/control/status` | Muestra indicador de error sin interrumpir el dashboard principal |
| `ChangeTradingModeUseCase` con posiciones abiertas | Devuelve `{ warning: "X open positions", requires_confirmation: true }` — el frontend muestra el warning, permite continuar |
| `PauseSystemUseCase` llamado dos veces | Idempotente: segunda llamada devuelve OK sin cambiar el estado |

---

## Testing Requirements

### Unit Tests (sin infra)

Deben correr en < 30s en CI:

| Test file | Cubre |
|-----------|-------|
| `tests/domain/test_risk_rules.py` | pure functions de `domain/trading/rules.py` |
| `tests/domain/test_trade_state_machine.py` | transiciones de estado válidas e inválidas |
| `tests/application/test_place_order_use_case.py` | mock broker, mock repo, mock notifications |
| `tests/application/test_close_position_use_case.py` | mock broker, mock repo, mock notifications |
| `tests/application/test_change_mode_use_case.py` | mock broker, mock state repo |
| `tests/application/test_update_setting_use_case.py` | validaciones, cifrado, eventos |
| `tests/application/test_risk_service.py` | validaciones de riesgo, circuit breaker |
| `tests/application/test_event_bus.py` | pub/sub, handler error isolation |

### Integration Tests (SQLite :memory:)

| Test file | Cubre |
|-----------|-------|
| `tests/integration/test_trade_repository.py` | CRUD completo + state machine |
| `tests/integration/test_signal_repository.py` | insert, get_pending, mark_processed |
| `tests/integration/test_system_state_repository.py` | get/set settings, secret cifrado |
| `tests/integration/test_full_order_flow.py` | signal → LLM → order → trade → close |
| `tests/integration/test_migration_runner.py` | alembic upgrade head desde vacío |
| `tests/integration/test_control_plane_api.py` | todos los endpoints de /control |

### Regression Tests

| Test file | Cubre |
|-----------|-------|
| `tests/regression/test_trading_scenarios.py` | STRONG signal → order; circuit breaker; paper mode no envía a IB real |
| `tests/regression/test_mode_switch.py` | paper→live→paper, reconexión IB, audit log |
| `tests/regression/test_state_persistence.py` | restart preserva modo y parámetros |

### Contract Tests

| Test file | Cubre |
|-----------|-------|
| `tests/contracts/test_broker_port_contract.py` | `MockBrokerAdapter` y `IBKRBrokerAdapter` (si IB disponible) |
| `tests/contracts/test_llm_port_contract.py` | `MockLLMAdapter` y `OpenCodeLLMAdapter` (si binario disponible) |

---

## Dependencias entre Requisitos

```
RF-001 (OpenCode adapter) → RF-103 (ILLMPort) → RF-201 (PlaceOrderUseCase)
RF-002 (transaction CM) → RF-201, RF-202
RF-003 (persistir estado) → RF-301 (control_settings tabla)
RF-101 (IBrokerPort) → RF-102 (eliminar httpx) → RF-201, RF-202
RF-201, RF-202, RF-203 → RF-205 (dividir api/main.py)
RF-205, RF-206 (container) → RF-207 (slim run.py)
RF-301 (control_settings) → RF-302 (PersistedSystemState) → RF-304 (ChangeTradingModeUseCase)
RF-306 (EventBus) → RF-401-409 (control plane events)
RF-601 (SQLAlchemy models) → RF-602 (Alembic) → RF-603 (repositorios) → RF-604 (tests parametrizados)
RF-603 → RF-701 (script migración)
```

---

## Out of Scope (confirmado)

- Exposición pública a internet
- Multi-usuario / multi-tenant
- Workers separados en procesos distintos (Fase 9 opcional, futuro)
- Mobile app nativa
- UI de backtesting avanzada
- Nuevas capacidades de trading o nuevos modelos ML
- SMS notifications
- Integración con brokers distintos a IBKR

---

**Document Version**: 1.0
**Status**: ✓ Approved
**Reviewed by**: Frank Pacheco — 2026-05-14
