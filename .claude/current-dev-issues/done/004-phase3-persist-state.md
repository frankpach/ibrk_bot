# Issue 004: Phase 3 — Persistir System State, Auditoría y Event Bus

**Module**: refactor
**Type**: AFK
**Effort**: M
**Blocked by**: 003
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: Cada módulo que necesita notificar algo importa `notify()` directamente — hay 17 módulos haciendo esto. Cuando se quiere añadir auditoría o throttling a una notificación, hay que editar 17 lugares. Además, el modo paper/live aún no tiene un event trail — el operador no puede ver cuándo y por qué cambió el modo.

**Business impact**: Sin event bus, cada side effect (Telegram, auditoría, postmortem) está acoplado directamente al use case. Añadir logging de auditoría para el control plane (Fase 4) requiere modificar cada use case individualmente en lugar de añadir un handler al bus.

**Success signal**: `grep -r "from app.notifications.telegram import notify" app/` devuelve 0 en módulos de dominio. El audit log tiene una entrada por cada cambio de modo con `changed_by` y timestamp.

---

## WHO — The Users

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| Frank | Trader | Desktop/móvil | Mercado | Ver historial de cuándo cambió el modo y quién lo cambió | Acceso solo via Tailscale |
| Frank | Developer | Desktop | Local | Añadir nuevos side effects sin modificar use cases | No puede modificar lógica de trading para añadir auditoría |

**Primary user**: Frank — Developer (el event bus beneficia principalmente la mantenibilidad).

---

## WHAT — Constraints

**Architecture**:
- [ ] El event bus es in-process y síncrono — sin Redis, sin asyncio event loop adicional
- [ ] Un handler que lanza excepción NO interrumpe la publicación a los demás handlers
- [ ] Los errores en handlers se loguean con structlog pero no se propagan al publisher
- [ ] `TelegramNotificationAdapter` wrappea el sistema existente de policy + throttler — sin reescribir
- [ ] `audit_log` es append-only — ningún código hace UPDATE ni DELETE sobre esta tabla

**Module-specific rules**:
- [ ] `PauseSystemUseCase` pausa: `signal_processor`, `scanner`, `scanner_fetch`, `news_fetch`
- [ ] `PauseSystemUseCase` NO pausa: `position_manager`, `circuit_breaker`, `gateway_watchdog`
- [ ] `ChangeTradingModeUseCase` valida que no hay órdenes en vuelo (status=SUBMITTED) antes de reconectar IB
- [ ] Los campos `is_secret=True` en audit_log se registran como `[SECRET_UPDATED]`, nunca el valor

**Module context**:
- Archivos nuevos: `app/application/event_bus.py`, `app/domain/trading/events.py`, `app/infrastructure/notifications/telegram_adapter.py`, `app/infrastructure/system/persisted_state.py`, `app/application/use_cases/change_mode.py`, `app/application/use_cases/pause_system.py`
- DB: tabla `audit_log` (nueva)

---

## HOW — Implementation Approach

**Event Bus** (RF-306):
1. `app/application/event_bus.py`:
   ```python
   class EventBus:
       _handlers: dict[type, list[Callable]] = {}
       def subscribe(self, event_type: type, handler: Callable) -> None: ...
       def publish(self, event: DomainEvent) -> None:
           for h in self._handlers.get(type(event), []):
               try: h(event)
               except Exception as e: log.error("handler_failed", handler=h.__name__, error=str(e))
   ```
2. `app/domain/trading/events.py`: todos los `@dataclass(frozen=True)` de eventos del PRD
3. Registrar handlers en `container.py`:
   - `PositionClosed` → `PostmortemHandler`, `TelegramNotificationHandler`, `AuditLogHandler`
   - `OrderPlaced` → `TelegramNotificationHandler`, `AuditLogHandler`
   - `TradingModeSwitched` → `IBKRReconnectHandler`, `TelegramNotificationHandler`, `AuditLogHandler`
   - `SystemPaused` / `SystemResumed` → `TelegramNotificationHandler`, `AuditLogHandler`
   - `CircuitBreakerTriggered` → `PauseSystemHandler`, `TelegramNotificationHandler`

**TelegramNotificationAdapter** (para reemplazar llamadas directas a `notify()`):
1. Wrappea `app/notifications/policy.py` + `throttler.py` + `telegram.py` — sin cambiar internals
2. Implementa `INotificationPort.notify()` y `request_approval()`
3. Los use cases reciben `INotificationPort` inyectado — no importan `notify()` directamente
4. Migrar los 17 módulos que llaman `notify()` directamente: en Fase 3, migrar al menos los use cases creados en Fase 2 (`PlaceOrderUseCase`, `ClosePositionUseCase`, `ChangeTradingModeUseCase`)

**Tabla audit_log** (RF-303):
1. `CREATE TABLE audit_log (id, event_type, entity_type, entity_id, old_value, new_value, changed_by, ip_address, occurred_at)`
2. Migración en `bootstrap/db_init.py` (formato compatible con Alembic en Fase 6)
3. `AuditLogHandler`: INSERT en audit_log al recibir cualquier evento de dominio

**ChangeTradingModeUseCase** (RF-304):
1. Valida: no hay orders con `trade_status=SUBMITTED`
2. Persiste `trading_mode` e `ib_port` en `control_settings`
3. Llama `IBrokerPort.reconnect(port)` — reconexión automática
4. Publica `TradingModeSwitched`
5. Con posiciones abiertas: devuelve `{ warning: "X posiciones abiertas", confirmed: false }` — el caller decide si confirmar

**PauseSystemUseCase / ResumeSystemUseCase** (RF-305):
1. Pausa/reanuda jobs en APScheduler via `scheduler.pause_job(job_id)` / `scheduler.resume_job(job_id)`
2. Persiste `is_paused` en `control_settings`
3. Publica `SystemPaused` / `SystemResumed`
4. Idempotente: si ya pausado, devuelve OK

**Events**:
- Publishes: `TradingModeSwitched`, `SystemPaused`, `SystemResumed`, `ControlSettingChanged`
- Consumes (nuevos handlers): `PositionClosed` → `PostmortemHandler`; `CircuitBreakerTriggered` → `PauseSystemHandler`

---

## Code Search (MANDATORY)

- [x] `from app.notifications.telegram import notify`: 17 archivos — migrar primero los use cases de Fase 2
- [x] `app/notifications/policy.py`: 108 LOC — wrappear, no reescribir
- [x] `app/notifications/throttler.py`: 100 LOC — wrappear, no reescribir
- [x] `app/notifications/approval.py`: 195 LOC — wrappear en `TelegramNotificationAdapter.request_approval()`
- [x] `app/system/controller.py:set_mode()`: 20 LOC — reemplazar con `ChangeTradingModeUseCase`
- [x] APScheduler jobs para pausar: `signal_processor`, `scanner`, `scanner_fetch`, `news_fetch` — IDs en `scheduler_setup.py`

**Reuse decision**:
- Reuse as-is: `policy.py`, `throttler.py`, `telegram.py`, `approval.py` — wrappear sin tocar internals
- Replace: `SystemController.set_mode()` y `pause()`/`resume()` → use cases
- Build new: `EventBus`, `TelegramNotificationAdapter`, `AuditLogHandler`, todos los use cases de este issue

---

## Reference Documents

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `docs/dev/artifacts/refactor/08-prd.md` | RF-301 a RF-306 con ACs |
| Interface design | `docs/dev/artifacts/refactor/06-interface-design.md` | Workflow 2 (cambio paper→live) |
| Architecture map | `docs/dev/artifacts/refactor/03-architecture-map.md` | Event catalog completo |

---

## Acceptance Criteria

- [x] `EventBus.publish()` con handler que lanza excepción → los demás handlers se ejecutan igualmente
- [x] `ChangeTradingModeUseCase`: paper→live → `ib_port=4001` en `control_settings` → reconexión IB automática
- [x] `ChangeTradingModeUseCase`: con órdenes en vuelo → devuelve warning, no cambia modo
- [x] `ChangeTradingModeUseCase`: audit_log tiene entrada con `changed_by="admin_key"` y `event_type="mode_changed"`
- [x] `PauseSystemUseCase`: `signal_processor` job pausado; `position_manager` job sigue corriendo
- [x] `PauseSystemUseCase`: restart → sistema arranca pausado (valor persiste en `control_settings`)
- [x] `TelegramNotificationAdapter` implementa `INotificationPort` — los use cases de Fase 2 lo usan
- [x] `grep -r "from app.notifications.telegram import notify" app/application/` → 0 resultados
- [x] Todos los tests existentes pasan

## Definition of Done

- [x] Todos los acceptance criteria verificados
- [x] Test: `EventBus` con múltiples handlers, uno lanza excepción → los demás ejecutan
- [x] Test: `ChangeTradingModeUseCase` paper→live → audit_log verificado
- [x] Test: `PauseSystemUseCase` → job específico en scheduler está pausado
- [x] Mypy sin errores nuevos
- [x] Issue movido a `done/`
