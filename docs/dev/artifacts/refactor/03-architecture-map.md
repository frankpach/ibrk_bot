# Architecture Map: Refactor Arquitectónico — IBKR AI Trader

**Status**: ✓ Complete  
**Date**: 2026-05-14  
**Phase**: 1 (Architecture Discovery)  
**Module**: refactor  

---

## Existing Models (raw SQL — sin ORM)

Todos los "modelos" actuales son tablas SQLite definidas como `CREATE TABLE` en `app/db/database.py` (1,277 LOC). No hay ORM. Todo el CRUD está en el mismo archivo. En el refactor, cada tabla se convierte en un SQLAlchemy model + repositorio.

### TradeModel (tabla: `trades`)
- **Purpose**: Ciclo de vida completo de una posición — desde señal hasta cierre
- **Key fields**: `id`, `symbol`, `action` (BUY/SELL), `quantity`, `entry_price`, `stop_loss_price`, `take_profit_price`, `status` (state machine), `trade_status` (PENDING→SUBMITTED→FILLED→OPEN→PARTIAL→CLOSED), `pnl_usd`, `pnl_pct`, `opened_at`, `closed_at`, `order_id`, `entry_fill_price`, `exit_fill_price`, `remaining_quantity`
- **Used by**: `llm/loop.py`, `positions/manager.py`, `api/main.py`, `system/reconciler.py`, `notifications/order_monitor.py` — 20+ módulos
- **Relevance**: Entidad central del dominio. Necesita repositorio SQLAlchemy con transaction support y state machine explícita.

### SignalModel (tabla: `signals`)
- **Purpose**: Señales técnicas pendientes de procesar por el LLM
- **Key fields**: `id`, `symbol`, `strength` (STRONG/MEDIUM/WEAK), `rsi`, `macd`, `volume_ratio`, `extra_indicators` (JSON), `created_at`, `processed` (bool)
- **Used by**: `scanner/preprocessor.py` (write), `llm/loop.py` (read + mark processed)
- **Relevance**: Input del pipeline trading. `processed=False` es la cola de trabajo del signal processor.

### SymbolConfigModel (tabla: `symbol_config`)
- **Purpose**: Universo de símbolos aprobados + metadata de mercado
- **Key fields**: `symbol`, `extra_indicators`, `approved` (bool), `proposed_by`, `created_at`, `sec_type`, `exchange`, `currency`, `liquid_hours`, `market_key`
- **Used by**: `api/main.py`, `scanner/`, `analysis/`, `ibkr/`
- **Relevance**: Gateway del universo tradeable. El control plane necesita poder aprobar/rechazar símbolos desde UI.

### SymbolParametersModel (tabla: `symbol_parameters`)
- **Purpose**: Parámetros adaptativos por símbolo — calibrados por backtesting y ML
- **Key fields**: `symbol`, `stop_loss_pct`, `take_profit_pct`, `momentum_multiplier`, `trend_multiplier`, `volume_multiplier`, `volatility_multiplier`, `calibrated_at`
- **Used by**: `ml/calibration.py`, `risk/sizer.py`, `analysis/`
- **Relevance**: Config por símbolo editable desde `/control` (sección "Parámetros Adaptativos").

### DecisionModel (tabla: `decisions`)
- **Purpose**: Log de decisiones LLM — qué decidió el modelo y con qué resultado
- **Key fields**: `signal_id`, `decision_date`, `action`, `stop_loss_pct`, `take_profit_pct`, `confidence`, `return_pct`, `status`
- **Used by**: `llm/agent.py` (write), `ml/cycle.py` (read para entrenamiento)
- **Relevance**: Append-only. Candidato a PostgreSQL primero (analítico).

### FeatureSnapshotModel (tabla: `feature_snapshots`)
- **Purpose**: Vector de features ML en el momento de cada decisión — para reentrenamiento
- **Key fields**: `signal_id`, `symbol`, `rsi_14`, `macd`, `atr`, `bollinger_pct`, `volume_ratio`, `relative_strength_spy`, `relative_strength_qqq`, múltiples más
- **Used by**: `ml/cycle.py` — input para `RandomForest`
- **Relevance**: Append-only, analítico. Sin relación con lógica operativa.

### AccountSnapshotModel (tabla: `account_snapshots`)
- **Purpose**: Snapshot EOD del account: net liquidation, buying power, daily P&L
- **Key fields**: `date`, `net_liquidation`, `buying_power`, `daily_pnl_usd`, `daily_pnl_pct`
- **Used by**: `api/main.py` (dashboard data), `reports/weekly.py`
- **Relevance**: Read model para performance dashboard.

### NewsCacheModel (tabla: `news_cache`)
- **Purpose**: Caché de noticias fetched cada 30 min
- **Key fields**: `symbol`, `headline`, `source`, `url`, `published_at`, `fetched_at`
- **Used by**: `scanner/news.py` (write), `api/main.py` (read para dashboard)
- **Relevance**: TTL corto; aceptable perder en restart. No necesita transaction.

### ScannerResultModel (tabla: `scanner_results`)
- **Purpose**: Top movers, gainers/losers del mercado — caché del scanner de IB
- **Key fields**: `scan_type`, `symbol`, `pct_change`, `volume`, `sector`, `fetched_at`
- **Used by**: `scanner/preprocessor.py` (write), `api/main.py` (read)
- **Relevance**: Caché de mercado. TTL corto.

### AnalysisReportModel (tabla: `analysis_reports`)
- **Purpose**: Reportes generados (pre-market, weekly) en markdown/HTML
- **Key fields**: `id`, `report_type`, `date`, `content`, `created_at`
- **Used by**: `reports/weekly.py` (write), `api/main.py` (serve)
- **Relevance**: Append-only. El dashboard lo muestra via `/reports`.

### MarketPermissionModel (tabla: `market_permissions`)
- **Purpose**: Exchanges y tipos de contrato con permisos activos en IBKR
- **Key fields**: `exchange`, `sec_type`, `contract_id`, `qualified_at`
- **Used by**: `ibkr/market_permissions.py`, `api/main.py`
- **Relevance**: Config de infraestructura. Actualizado diariamente.

### PatternModel (tabla: `patterns`)
- **Purpose**: Patrones históricos de trading por símbolo con win/loss counts
- **Key fields**: `id`, `symbol`, `pattern_text`, `win_count`, `loss_count`
- **Used by**: `llm/agent.py` (read para contexto), `llm/postmortem.py` (write)
- **Relevance**: Memoria histórica del sistema para el LLM.

### DailyWatchlistModel (tabla: `daily_watchlist`)
- **Purpose**: Símbolos seleccionados para la sesión con scores
- **Key fields**: `symbol`, `score`, `reason`, `session_date`
- **Used by**: `scanner/opportunity_scanner.py`, `api/main.py`
- **Relevance**: Read model para dashboard. Regenerable.

### PositionSnapshotModel (tabla: `position_snapshots`)
- **Purpose**: P&L en tiempo real de posiciones abiertas
- **Key fields**: `symbol`, `current_price`, `unrealized_pnl`, `updated_at`
- **Used by**: `positions/manager.py` (write), `api/main.py` (dashboard)
- **Relevance**: Read model. Actualizado cada 2 min por position_manager job.

### [NUEVO] ControlSettingModel (tabla: `control_settings`) — a crear
- **Purpose**: Store de configuración operativa persistida — reemplaza globals en settings.py
- **Key fields**: `key`, `value` (JSON), `value_type`, `label`, `description`, `is_secret`, `requires_restart`, `updated_at`, `updated_by`
- **Used by**: (nuevo) `PersistedSystemState`, control plane `/control`
- **Relevance**: Core del refactor — toda la configuración que hoy vive en `.env` o en memoria.

### [NUEVO] AuditLogModel (tabla: `audit_log`) — a crear/expandir
- **Purpose**: Registro inmutable de todos los cambios operativos y de configuración
- **Key fields**: `id`, `event_type`, `entity_type`, `entity_id`, `old_value`, `new_value`, `changed_by`, `ip_address`, `occurred_at`
- **Used by**: (nuevo) `AuditLogHandler` (event bus handler)
- **Relevance**: Trazabilidad completa. Append-only.

### [NUEVO] BackgroundJobModel (tabla: `background_jobs`) — a crear
- **Purpose**: Estado de jobs asincrónicos (LLM analysis, backtest, opportunity scan)
- **Key fields**: `id` (UUID), `job_type`, `status` (pending/running/success/failed), `params` (JSON), `result` (JSON), `error`, `progress_pct`, `progress_msg`, `created_at`, `started_at`, `completed_at`
- **Used by**: (nuevo) `BackgroundJobRunner`, `JobStatusEndpoint`
- **Relevance**: Saca análisis LLM del request path.

---

## Existing Components (Frontend — React embebido en Python)

El frontend es una SPA React embebida en `app/api/dashboard.py` (2,700+ LOC). No hay un sistema de diseño separado — todo el HTML/CSS/JS está en strings Python o archivos servidos directamente.

### DashboardApp (componente raíz)
- **Location**: `app/api/dashboard.py` (inline en response HTML)
- **Purpose**: Vista principal — posiciones, señales, P&L, noticias, scanner
- **Relevance**: Necesita separarse en componentes React independientes. La lógica de aggregation de datos (270 líneas en 1 función) debe moverse a `DashboardDataQuery`.

### TradingViewChart (componente)
- **Location**: `app/api/dashboard.py`
- **Purpose**: Gráfico de velas con indicadores (TradingView Lightweight Charts)
- **Relevance**: Componente ya funcional — reutilizar as-is en nueva estructura.

### ReportsViewer
- **Location**: `app/api/dashboard.py` + route `/reports`
- **Purpose**: Lista y renderiza reportes markdown/HTML generados
- **Relevance**: Puede quedar como está; solo separar del monolito.

### [NUEVO] ControlPlaneApp — a crear
- **Purpose**: Página `/control` — toda la configuración operativa
- **Secciones**: Modo operativo, parámetros de riesgo, circuit breaker, universo de símbolos, parámetros adaptativos, notificaciones, feature flags, conectividad IB, jobs/scheduler
- **Relevance**: Componente React nuevo; se sirve desde `control_routes.py`.

---

## Event Catalog

### Eventos actualmente publicados: NINGUNO (anti-patrón detectado)

No existe event bus. Toda comunicación entre módulos es:
- Llamadas directas a funciones Python (dentro del mismo proceso)
- Llamadas HTTP a endpoints FastAPI (entre módulos del mismo proceso)
- Imports directos de `notify()` en 17 módulos

### Eventos de Dominio a Crear

Estos eventos se publicarán en el event bus in-process una vez implementado:

| Evento | Publicado por | Cuándo | Payload |
|--------|-------------|--------|---------|
| `SignalDetected` | `ScanMarketUseCase` | Scanner detecta señal STRONG/MEDIUM | `symbol`, `strength`, `indicators` |
| `OrderPlaced` | `PlaceOrderUseCase` | Orden enviada a IBKR | `symbol`, `action`, `quantity`, `price`, `trade_id` |
| `PositionOpened` | `PlaceOrderUseCase` | Fill confirmado | `trade_id`, `symbol`, `fill_price` |
| `PositionClosed` | `ClosePositionUseCase` | Posición cerrada (SL/TP/manual) | `trade_id`, `symbol`, `pnl_usd`, `reason` |
| `StopLossHit` | `PositionService` | Precio toca SL | `trade_id`, `symbol`, `trigger_price` |
| `TakeProfitHit` | `PositionService` | Precio toca TP | `trade_id`, `symbol`, `trigger_price` |
| `TradingModeSwitched` | `ChangeTradingModeUseCase` | Cambio paper↔live | `old_mode`, `new_mode`, `new_port`, `changed_by` |
| `SystemPaused` | `PauseSystemUseCase` | Sistema pausado | `reason`, `paused_by` |
| `SystemResumed` | `ResumeSystemUseCase` | Sistema reanudado | `resumed_by` |
| `CircuitBreakerTriggered` | `RiskService` | Daily P&L < threshold | `daily_pnl_pct`, `threshold` |
| `ControlSettingChanged` | `UpdateControlSettingUseCase` | Setting modificado en /control | `key`, `old_value`, `new_value`, `changed_by` |
| `SymbolApproved` | `ApproveSymbolUseCase` | Símbolo añadido al universo | `symbol`, `sec_type`, `approved_by` |
| `LLMAnalysisCompleted` | `BackgroundJobRunner` | Job de análisis LLM termina | `job_id`, `symbol`, `decision` |
| `GatewayDisconnected` | `GatewayWatchdog` | IB Gateway caído > 5 min | `last_connected_at`, `duration_minutes` |

### Handlers de Eventos a Registrar

| Evento | Handler | Acción |
|--------|---------|--------|
| `PositionClosed` | `PostmortemHandler` | Ejecuta análisis postmortem LLM |
| `PositionClosed` | `TelegramNotificationHandler` | Notifica con P&L |
| `PositionClosed` | `AuditLogHandler` | Registra en audit_log |
| `OrderPlaced` | `TelegramNotificationHandler` | Notifica orden enviada |
| `OrderPlaced` | `AuditLogHandler` | Registra en audit_log |
| `CircuitBreakerTriggered` | `PauseSystemHandler` | Pausa el scheduler |
| `CircuitBreakerTriggered` | `TelegramNotificationHandler` | Alerta crítica |
| `ControlSettingChanged` | `AuditLogHandler` | Registra cambio con old/new value |
| `ControlSettingChanged` | `HotReloadHandler` | Aplica cambio en caliente si aplica |
| `TradingModeSwitched` | `IBKRReconnectHandler` | Reconecta IBKRClient con nuevo puerto |
| `TradingModeSwitched` | `TelegramNotificationHandler` | Notifica cambio de modo |
| `GatewayDisconnected` | `TelegramNotificationHandler` | Alerta crítica de conectividad |

---

## Core Services (existentes — reutilizar)

### IBKRClient (singleton actual → IBKRBrokerAdapter)
- **Location**: `app/ibkr/client.py` (294 LOC)
- **Purpose**: Conexión a IB Gateway — prices, orders, portfolio, account
- **Methods**: `get_stock_price()`, `place_order()`, `get_account()`, `get_portfolio()`, `get_executions()`
- **Tu módulo puede**: Wrappear en `IBKRBrokerAdapter(IBrokerPort)` — la lógica interna no cambia
- **Nota**: El singleton `_client_instance` se reemplaza con instancia inyectada desde `container.py`

### NotificationPolicy + Throttler (mantener)
- **Location**: `app/notifications/policy.py` + `app/notifications/throttler.py`
- **Purpose**: Filtro por severidad + deduplicación de mensajes Telegram
- **Relevance**: Wrappear en `TelegramNotificationAdapter(INotificationPort)`. La política y el throttling quedan como están.

### NotificationQueue (mantener)
- **Location**: `app/notifications/queue.py` (130 LOC)
- **Purpose**: Queue thread-safe para evitar `asyncio.run()` conflicts con APScheduler
- **Relevance**: Mantener como implementation detail del adapter.

### OrderDedup (mantener)
- **Location**: `app/ibkr/dedup.py` (157 LOC)
- **Purpose**: Ventana de 30s para deduplicar órdenes por símbolo+acción
- **Relevance**: Mover lógica a `PlaceOrderUseCase` o mantener en `IBKRBrokerAdapter`.

### BacktestEngine (mantener as-is)
- **Location**: `app/backtest/engine.py` (235 LOC)
- **Purpose**: Backtest 180 días con métricas: profit factor, Sharpe, max drawdown
- **Relevance**: No necesita cambios arquitectónicos. El endpoint `/backtest/{symbol}` se convierte en async job.

### ApprovalManager (mantener)
- **Location**: `app/notifications/approval.py` (195 LOC)
- **Purpose**: Solicitar aprobación humana vía Telegram con timeout
- **Relevance**: Encapsular en `TelegramNotificationAdapter.request_approval()`.

### TrailingStopManager + PartialExitManager (refactor leve)
- **Location**: `app/risk/trailing_stop.py`, `app/risk/partial_exit.py`
- **Purpose**: Gestión de trailing stops y salidas parciales
- **Relevance**: Mover lógica a `PositionService`. Eliminar module-level instances en `positions/manager.py`.

### OpenCode subprocess (consolidar)
- **Location**: `app/llm/agent.py` (duplicado), `app/analysis/pipeline.py` (duplicado), `app/notifications/telegram_bot.py` (duplicado)
- **Purpose**: Llamada al LLM via subprocess
- **Relevance**: Consolidar en `infrastructure/llm/opencode_adapter.py` (ya existe, no se usa). Eliminar los 3 duplicados.

### SystemController (reemplazar)
- **Location**: `app/system/controller.py` (90 LOC)
- **Purpose**: Modo paper/live + pausa — todo en memoria
- **Relevance**: Reemplazar con `PersistedSystemState(ISystemStateRepository)`. El controlador actual muta `settings.py` — esto desaparece.

---

## Gaps (What's Missing)

### Nuevos SQLAlchemy Models

- [ ] `TradeModel` — SQLAlchemy `DeclarativeBase`, mismo schema actual + `updated_at`
- [ ] `SignalModel` — igual que arriba
- [ ] `SymbolConfigModel` — igual
- [ ] `SymbolParametersModel` — igual
- [ ] `DecisionModel` — igual
- [ ] `FeatureSnapshotModel` — igual
- [ ] `AccountSnapshotModel` — igual
- [ ] `NewsCacheModel` — igual
- [ ] `ScannerResultModel` — igual
- [ ] `AnalysisReportModel` — igual
- [ ] `MarketPermissionModel` — igual
- [ ] `PatternModel` — igual
- [ ] `DailyWatchlistModel` — igual
- [ ] `PositionSnapshotModel` — igual
- [ ] `ControlSettingModel` — **nuevo**, tabla nueva
- [ ] `AuditLogModel` — **nuevo**, tabla nueva
- [ ] `BackgroundJobModel` — **nuevo**, tabla nueva

### Nuevos Repositorios SQLAlchemy

- [ ] `SQLAlchemyTradeRepository(ITradeRepository)` — con `get_open()`, `save()`, `close()`, `get_by_symbol()`
- [ ] `SQLAlchemySignalRepository(ISignalRepository)` — con `get_pending()`, `save()`, `mark_processed()`
- [ ] `SQLAlchemySymbolRepository(ISymbolRepository)` — con `get_approved()`, `approve()`, `get_parameters()`
- [ ] `SQLAlchemySystemStateRepository(ISystemStateRepository)` — con `get_setting()`, `save_setting()`, `get_all()`
- [ ] `SQLAlchemyAuditLogRepository` — append-only, `log(event)`
- [ ] `SQLAlchemyJobRepository(IJobRepository)` — con `save()`, `update_status()`, `get_by_id()`
- [ ] `SQLAlchemyAccountRepository` — snapshots, `save_snapshot()`, `get_daily_pnl()`
- [ ] `SQLAlchemyPatternRepository` — `get_by_symbol()`, `update_counts()`

### Nuevas Migraciones Alembic

- [ ] `001_initial_schema.py` — schema completo actual (estado baseline)
- [ ] `002_add_control_settings.py` — tabla `control_settings`
- [ ] `003_add_audit_log.py` — tabla `audit_log` expandida
- [ ] `004_add_background_jobs.py` — tabla `background_jobs`
- [ ] `005_add_updated_at_to_trades.py` — columna faltante

### Nuevas Interfaces (Ports)

- [ ] `IBrokerPort` — `get_price()`, `place_order()`, `get_portfolio()`, `get_account()`, `reconnect(port)`
- [ ] `ILLMPort` — `analyze_signal()`, `run_postmortem()`, `interpret_analysis()`
- [ ] `INotificationPort` — `notify()`, `request_approval()`
- [ ] `ITradeRepository` — CRUD de trades
- [ ] `ISignalRepository` — CRUD de signals
- [ ] `ISymbolRepository` — universo de símbolos
- [ ] `ISystemStateRepository` — settings persistidos
- [ ] `IJobRepository` — background jobs

### Nuevos Use Cases

- [ ] `PlaceOrderUseCase` — validación risk + dedup + IB order + DB trade + event
- [ ] `ClosePositionUseCase` — IB order + DB update + P&L calc + event
- [ ] `ProcessSignalUseCase` — pending signal → LLM decision → place order
- [ ] `ScanMarketUseCase` — IB data → indicators → signal classification → save
- [ ] `ChangeTradingModeUseCase` — validar posiciones → persistir modo/puerto → reconectar IB → event
- [ ] `PauseSystemUseCase` — persistir is_paused → pause scheduler jobs → event
- [ ] `ResumeSystemUseCase` — persistir is_paused=False → resume scheduler jobs → event
- [ ] `UpdateControlSettingUseCase` — validar → persistir → hot-reload si aplica → event
- [ ] `ApproveSymbolUseCase` — validar → actualizar symbol_config → event
- [ ] `RunLearningCycleUseCase` — wrap del ML retraining existente

### Nuevos Application Services

- [ ] `RiskService` — `validate_order()`, `check_circuit_breaker()`, `calculate_position_size()`
- [ ] `PositionService` — `apply_trailing_stop()`, `check_exit_conditions()`, `apply_partial_exit()`
- [ ] `SymbolService` — `get_watchlist_scores()`, `get_adaptive_params()`
- [ ] `SecretManager` — cifrado/descifrado Fernet para API keys en `control_settings`
- [ ] `SettingValidator` — tipos, rangos, enums por key

### Nuevos Infrastructure Adapters

- [ ] `IBKRBrokerAdapter(IBrokerPort)` — wrappea `IBKRClient` existente
- [ ] `MockBrokerAdapter(IBrokerPort)` — para tests, sin IB Gateway
- [ ] `OpenCodeLLMAdapter(ILLMPort)` — consolida los 3 `_call_opencode()` duplicados
- [ ] `MockLLMAdapter(ILLMPort)` — para tests
- [ ] `TelegramNotificationAdapter(INotificationPort)` — wrappea telegram.py + policy + throttler
- [ ] `MockNotificationAdapter(INotificationPort)` — para tests
- [ ] `PersistedSystemState(ISystemStateRepository)` — lee/escribe `control_settings`

### Nuevos Interface Routes

- [ ] `trading_routes.py` — `/orders/*`, `/trades/*`
- [ ] `market_routes.py` — `/price/*`, `/signals`, `/patterns/*`
- [ ] `system_routes.py` — `/system/*`, `/health`
- [ ] `analysis_routes.py` — `/backtest/*`, `/candidate-analysis/*`
- [ ] `reports_routes.py` — `/reports/*`
- [ ] `control_routes.py` — `/control/*` (nuevo)
- [ ] `jobs_routes.py` — `/jobs/*` (nuevo — async jobs)

### Nuevo DI Container

- [ ] `app/container.py` — `get_container()` con `@lru_cache(maxsize=1)`, instancia todos los adapters y use cases
- [ ] `app/bootstrap/scheduler_setup.py` — thin wrappers de jobs → llaman use cases
- [ ] `app/bootstrap/gateway_watchdog.py` — lógica de reconexión IB extraída de `run.py`
- [ ] `app/bootstrap/db_init.py` — `alembic upgrade head` al startup

### Nuevo Event Bus

- [ ] `app/application/event_bus.py` — pub/sub in-process, sync, handlers registrados en `container.py`

### Nuevo Control Plane Frontend

- [ ] `ControlPlaneApp` — React SPA en `/control`
- [ ] Secciones: modo/pausa, parámetros de riesgo, circuit breaker, universo de símbolos, API keys, puertos IB, DB URL, jobs/scheduler, audit log

### Nuevo Read Model para Dashboard

- [ ] `DashboardDataQuery` — 1-2 queries SQLAlchemy agregadas que reemplazan la función de 270 líneas

---

## Anti-Patterns Detectados

### Anti-Pattern 1: Model Blindness — NO APLICA

El codebase no usa ORM — todos los "modelos" son raw SQL en `database.py`. No hay riesgo de duplicar un modelo SQLAlchemy que no existe aún. La tarea es **crear** los modelos SQLAlchemy a partir de las tablas existentes.

**Oportunidad**: Aprovechar la migración a SQLAlchemy para añadir `updated_at` donde falta y estandarizar el naming.

### Anti-Pattern 2: Island Components — CLARO

**Finding**: El adapter `infrastructure/llm/opencode_adapter.py` **ya existe** en el codebase pero ningún módulo lo usa. En cambio, `_call_opencode()` está implementado idénticamente en 3 archivos distintos:
- `app/llm/agent.py:73-98`
- `app/analysis/pipeline.py:282`
- `app/notifications/telegram_bot.py:37-60`

**Acción**: El adapter existente debe ser **el único** — los 3 duplicados deben eliminarse.

### Anti-Pattern 3: Pub/Sub Bypass — CLARO (sistémico)

**Finding**: No existe event bus. Todo el sistema usa llamadas directas:
- 17 módulos importan `notify()` directamente
- `loop.py` llama FastAPI endpoints via `httpx`
- `positions/manager.py` llama FastAPI endpoints via `httpx`
- El postmortem se llama directamente desde `positions/manager.py` tras cerrar una posición
- `SystemController.set_mode()` muta `settings.py` directamente

**Acción**: Crear event bus in-process. Migrar `notify()` disperso a `TelegramNotificationAdapter` como handler de eventos. Eliminar HTTP interno.

### Anti-Pattern 4: UX Amnesia — NO APLICA

**Finding**: El design concept y los journeys están bien alineados con la realidad operativa. Las dos personas identificadas (Trader y Developer son la misma persona en roles distintos) reflejan el contexto real: sistema personal single-user en Raspberry Pi.

### Anti-Pattern 5: God Module — CLARO (adicional)

**Finding**: 3 archivos superan 1,000 LOC con múltiples responsabilidades mezcladas:
- `database.py` (1,277 LOC): DDL + migraciones + CRUD de 15 entidades
- `api/main.py` (1,311 LOC): 50+ routes + lógica de riesgo + IB calls + DB queries
- `dashboard.py` (2,700 LOC): HTML/CSS/JS embebido + queries de aggregation + React components

**Acción**: Dividir según plan de refactor de cada archivo (ver design concept sección 3.5).

### Anti-Pattern 6: Config Leakage — CLARO (adicional)

**Finding**: `settings.py` importado directamente en 30+ módulos. Las variables son mutadas en runtime (`PAPER_TRADING_ONLY = False` en `controller.py`). Cambios en runtime no se persisten — se pierden en restart.

**Acción**: Toda la configuración operativa pasa a `control_settings` DB. Los módulos leen desde `ISystemStateRepository`, no desde `settings.py`.

---

## Archaeology Notes

- **No hay ORM**: Todo es raw SQL con `sqlite3`. El salto a SQLAlchemy es completo — no hay modelos existentes que reutilizar.
- **No hay event bus**: La comunicación entre módulos es 100% imperativa — imports directos o HTTP.
- **No hay DI**: Los singletons (`IBKRClient`, `SystemController`) se instancian directamente. El container es nuevo.
- **Adapter existente ignorado**: `infrastructure/llm/opencode_adapter.py` ya tiene la implementación correcta — nadie la usa.
- **Tests escasos**: `pytest.ini` existe pero sin fixtures de DB ni mocks de IB. Los tests que existen requieren infra real.
- **APScheduler pattern actual**: Los jobs son lambdas/closures en `run.py` que capturan estado mutable. Deben convertirse en thin wrappers que llaman use cases.
- **Telegram bot 839 LOC**: Mezcla handlers de 24 comandos distintos + análisis LLM + subprocess calls. Dividir en 3 handler files.
- **Frontend embebido en Python**: No hay build system frontend separado. El HTML/React está en strings dentro de `dashboard.py`. El refactor puede mantener esta estructura pero separar los componentes lógicamente.

---

## Decisiones para Phase 2 (Design)

- [ ] **Alembic con SQLite**: ¿Usamos Alembic directamente o un runner propio para las operaciones complejas que SQLite no soporta?
- [ ] **Order de implementación SQLAlchemy**: ¿Migramos tabla por tabla (empezando por `trades`) o creamos todos los modelos en paralelo y cambiamos la capa de acceso de golpe?
- [ ] **Frontend `/control`**: ¿Mismo patrón embebido en Python (como `dashboard.py`) o separar en archivos estáticos servidos por FastAPI?
- [ ] **Event bus sync o async**: ¿Sync (simple, predecible) o asyncio (potencialmente más rápido pero complejo)? Recomendación: sync en Fase 3, con opción a async en Fase 9.
- [ ] **Startup con Alembic**: ¿`alembic upgrade head` automático al arrancar la app o solo con comando manual?

---

## Next Steps

1. ✓ Architecture map completado
2. → Artefacto 04-constraints.md
3. → Artefacto 05-why-decisions.md
4. Actualizar estado fase 1
5. `/clear` de contexto
6. `/130-design refactor`

---

**Document Version**: 1.0  
**Created by**: discover-codebase skill  
**Reviewed by**: Frank Pacheco — 2026-05-14
