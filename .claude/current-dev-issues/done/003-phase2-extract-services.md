# Issue 003: Phase 2 — Extraer Servicios, Use Cases y DI

**Module**: refactor
**Type**: AFK
**Effort**: L
**Blocked by**: 002
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: `api/main.py` (1,311 LOC) tiene handlers de 140 líneas con lógica de riesgo, llamadas a IB, escrituras a DB y notificaciones — todo mezclado. `run.py` (627 LOC) tiene lógica de negocio dentro de lambdas de scheduler. Cuando algo falla, el stack trace no indica qué parte del negocio falló — solo que falló una lambda en el scheduler.

**Business impact**: Cada nueva feature requiere entender 1,300 líneas de contexto. Cada bug de producción requiere SSH + leer logs de funciones anónimas. El developer no puede progresar sin riesgo de regresión.

**Success signal**: Ningún route handler supera 30 líneas. Los jobs del scheduler son funciones nombradas. `PlaceOrderUseCase` tiene un test que corre en < 1s sin servidor ni IB Gateway.

---

## WHO — The Users

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| Frank | Developer | Desktop | Local | Modificar lógica de trading sin entender todo api/main.py | No puede parar el sistema en producción para refactorizar |
| Frank | Trader | Pi via Telegram | Mercado | Las órdenes sigan ejecutándose correctamente | Cero tolerancia a regresiones en trading |

**Primary user**: Frank — Developer.

---

## WHAT — Constraints

**Architecture**:
- [x] Ningún route handler importa `sqlite3`, `IBKRClient`, ni `subprocess` directamente
- [x] Los use cases reciben dependencias inyectadas — sin `get_client()` ni singletons directos dentro del use case
- [x] `container.py` usa `@lru_cache(maxsize=1)` — una sola instancia por proceso
- [x] `run.py` < 60 líneas tras este issue
- [x] Los jobs del scheduler son funciones nombradas en `bootstrap/scheduler_setup.py`

**Module-specific rules**:
- [ ] `PlaceOrderUseCase`: lock por símbolo con `threading.Lock` — dos órdenes simultáneas para el mismo símbolo no pueden ejecutarse en paralelo
- [ ] `RiskService` lee parámetros de `ISystemStateRepository` — no de `settings.py` directamente
- [ ] `ClosePositionUseCase` es idempotente — si el trade ya está cerrado, devuelve OK sin error

**Module context**:
- Archivos a dividir: `app/api/main.py` → 6 route files, `run.py` → `run.py` (60 LOC) + `bootstrap/`
- Archivos nuevos: `app/application/use_cases/`, `app/application/services/`, `app/container.py`

---

## HOW — Implementation Approach

**PlaceOrderUseCase** (RF-201):
1. Extraer de `POST /orders/place` handler (140 líneas) a `app/application/use_cases/place_order.py`
2. Input: `PlaceOrderCommand(symbol, action, quantity, signal_strength, requested_by)`
3. Flujo: validate risk → dedup check → (si live) request_approval → broker.place_order → repo.save_trade → publish OrderPlaced
4. Lock `_symbol_locks: dict[str, Lock]` — instanciado en `container.py`
5. Devuelve `PlaceOrderResult(success, order_id, trade_id, error)`

**ClosePositionUseCase** (RF-202):
1. Extraer de `POST /orders/close/{symbol}` handler y de `positions/manager.py`
2. Input: `ClosePositionCommand(trade_id, reason, requested_by)`
3. Flujo: get_trade → get_price → broker.place_order (sell) → repo.close_trade → publish PositionClosed
4. Idempotente: si trade.status ya es CLOSED, devuelve OK

**RiskService** (RF-203):
1. `validate_order(symbol, action, quantity, price) -> ValidationResult`
2. `check_circuit_breaker() -> bool`
3. `calculate_position_size(symbol, risk_pct, price) -> int`
4. Lee `max_positions`, `max_risk_pct`, `capital_cap`, `max_position_usd` de `ISystemStateRepository`

**PositionService** (RF-204):
1. Mover lógica de `trailing_stop.py` + `partial_exit.py` + lógica de exit de `positions/manager.py`
2. `apply_trailing_stop(trade, current_price) -> Trade`
3. `check_exit_conditions(trade, current_price) -> ExitCondition | None`
4. Eliminar module-level `trailing_mgr` y `partial_mgr` de `positions/manager.py`

**Dividir api/main.py** (RF-205):
1. Crear `app/interfaces/api/routes/`:
   - `trading_routes.py` — `/orders/*`, `/trades/*`
   - `market_routes.py` — `/price/*`, `/signals`, `/patterns/*`
   - `system_routes.py` — `/system/*`, `/health`
   - `analysis_routes.py` — `/backtest/*`, `/candidate-analysis/*`
   - `reports_routes.py` — `/reports/*`
2. Crear `app/interfaces/api/app.py` con `include_router()` para cada uno
3. `trading_routes.py` delega a `PlaceOrderUseCase` y `ClosePositionUseCase`
4. Ningún handler supera 30 líneas

**container.py** (RF-206):
1. `app/container.py` con `get_container() -> Container`
2. Instancia: `IBKRBrokerAdapter`, `OpenCodeLLMAdapter`, `TelegramNotificationAdapter`
3. Instancia: repos (por ahora usando funciones de `database.py` — migración a repos SQLAlchemy en Fase 6)
4. Instancia: `RiskService`, `PositionService`, `PlaceOrderUseCase`, `ClosePositionUseCase`
5. Función `test_container()` que sustituye adapters reales por mocks

**Slim run.py** (RF-207):
1. Extraer lógica de reconexión IB a `app/bootstrap/gateway_watchdog.py`
2. Extraer registro de jobs a `app/bootstrap/scheduler_setup.py` con funciones nombradas
3. `run.py` queda: init container → apply migrations → start scheduler → start telegram → start uvicorn

**Events**:
- Publishes: `OrderPlaced`, `PositionClosed` (via event bus — implementación real en Fase 3; por ahora llamar handlers directamente)
- Consumes: none en este issue

---

## Code Search (MANDATORY)

- [x] Handler `/orders/place`: `api/main.py:245-387` (142 líneas) — extraer a use case
- [x] Handler `/orders/close/{symbol}`: `api/main.py:535-588` — extraer a use case
- [x] `trailing_mgr` en `positions/manager.py:17` — module-level instance a eliminar
- [x] Jobs registrados en `run.py`: 21 lambdas/funciones anónimas — convertir a named functions
- [x] `_ib_client_ref` dict en `run.py` — mover a `gateway_watchdog.py`

**Reuse decision**:
- Reuse as-is: lógica de trading de `loop.py`, `positions/manager.py` (solo reorganizar)
- Extend: `IBKRBrokerAdapter` (añadir métodos que falten)
- Build new: `PlaceOrderUseCase`, `ClosePositionUseCase`, `RiskService`, `PositionService`, `container.py`, 6 route files, `bootstrap/`

---

## Reference Documents

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `docs/dev/artifacts/refactor/08-prd.md` | RF-201 a RF-207 con ACs |
| Architecture map | `docs/dev/artifacts/refactor/03-architecture-map.md` | Servicios a crear, anti-patrones |
| Interface design | `docs/dev/artifacts/refactor/06-interface-design.md` | API structure, components to build |
| Constraints | `.claude/current-dev-issues/.state/constraints.md` | Lock por símbolo, idempotencia |

---

## Acceptance Criteria

- [x] `PlaceOrderUseCase` en `application/use_cases/place_order.py` < 80 LOC
- [x] Test: `PlaceOrderUseCase` con `MockBrokerAdapter` y `MockNotificationAdapter` — pasa en < 1s
- [x] Test: dos llamadas simultáneas a `PlaceOrderUseCase` para el mismo símbolo → solo 1 ejecutada
- [x] Test: `ClosePositionUseCase` con trade ya cerrado → devuelve OK (idempotente)
- [x] `RiskService.validate_order()` lee `max_positions` de `ISystemStateRepository`, no de `settings.py`
- [x] Ningún handler en los 6 route files supera 30 líneas
- [x] `run.py` < 60 líneas
- [x] Los jobs del scheduler son funciones nombradas (no lambdas) en `scheduler_setup.py`
- [x] `get_container()` llamado 3 veces → devuelve la misma instancia
- [x] `test_container()` devuelve instancia con todos los mocks — sin IB Gateway, sin Telegram
- [x] Todos los tests existentes pasan

## Definition of Done

- [x] Todos los acceptance criteria verificados
- [x] Tests unitarios de `PlaceOrderUseCase`, `ClosePositionUseCase`, `RiskService`
- [x] Test de integración: `POST /orders/place` → llama `PlaceOrderUseCase` → persiste en DB
- [x] Mypy sin errores nuevos
- [x] Issue movido a `done/`
