# Issue 002: Phase 1 — Eliminar HTTP Interno

**Module**: refactor
**Type**: AFK
**Effort**: M
**Blocked by**: 001
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: Si el servidor FastAPI tiene cualquier glitch durante el horario de mercado, el signal processor y el position manager fallan silenciosamente porque llaman a la propia API via `httpx`. El trading se detiene sin error visible, y el operador no lo sabe hasta que revisa logs.

**Business impact**: Una orden no enviada o una posición no monitoreada durante mercado activo tiene impacto financiero directo. El HTTP interno también hace imposible testear `loop.py` y `positions/manager.py` sin levantar el servidor FastAPI completo.

**Success signal**: `grep -r "httpx" app/llm/loop.py app/positions/manager.py app/alerts/manager.py` devuelve 0 resultados. Tests de use cases de trading pasan en < 5s sin servidor HTTP corriendo.

---

## WHO — The Users

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| Frank | Developer | Desktop | Local | Escribir tests de trading sin infraestructura | El sistema está en producción — no puede romper el flujo existente |
| Frank | Trader | Pi via Telegram | Mercado abierto | El sistema siga operando aunque haya un restart parcial | No puede estar mirando el sistema constantemente |

**Primary user**: Frank — Developer (la eliminación del HTTP interno desbloquea la testabilidad completa).

---

## WHAT — Constraints

**Architecture**:
- [ ] `IBrokerPort` es la única interfaz entre el dominio y el broker IBKR — no llamadas directas a `IBKRClient`
- [ ] `ILLMPort` es la única interfaz entre el dominio y OpenCode — no subprocess directo en use cases
- [ ] `INotificationPort` es la única interfaz para notificaciones — no `notify()` directo en use cases
- [ ] `MockBrokerAdapter`, `MockLLMAdapter`, `MockNotificationAdapter` en `tests/mocks/` — sin dependencias de infra real
- [ ] Los ports viven en `application/ports/` — sin imports de `infrastructure/` ni `interfaces/`

**Module-specific rules**:
- [ ] Los métodos del port devuelven tipos de dominio (`Decimal`, `Trade`, `Position`) — no dicts crudos
- [ ] Los adapters wrappean el cliente existente — no reescriben la lógica de IB
- [ ] El `IBKRBrokerAdapter` nunca expone el `ib_insync` API directamente — solo a través del port interface

**Module context**:
- Archivos a modificar: `app/llm/loop.py`, `app/positions/manager.py`, `app/alerts/manager.py`
- Archivos nuevos: `app/application/ports/broker_port.py`, `app/application/ports/llm_port.py`, `app/application/ports/notification_port.py`, `app/infrastructure/broker/ibkr_adapter.py`, `app/infrastructure/broker/mock_adapter.py`

---

## HOW — Implementation Approach

**Backend — IBrokerPort** (RF-101):
1. Crear `app/application/ports/broker_port.py`:
   ```python
   class IBrokerPort(ABC):
       @abstractmethod
       def get_price(self, symbol: str, sec_type: str, exchange: str, currency: str) -> Decimal: ...
       @abstractmethod
       def place_order(self, order: Order) -> OrderResult: ...
       @abstractmethod
       def get_portfolio(self) -> list[Position]: ...
       @abstractmethod
       def get_account(self) -> AccountSummary: ...
       @abstractmethod
       def reconnect(self, port: int) -> None: ...
   ```
2. Crear `app/infrastructure/broker/ibkr_adapter.py` que wrappea `IBKRClient` existente
3. Crear `app/infrastructure/broker/mock_adapter.py` que devuelve valores fijos configurables
4. Crear `app/domain/trading/value_objects.py`: `Order`, `OrderResult`, `Position`, `AccountSummary`

**Backend — ILLMPort y INotificationPort** (RF-103):
1. Crear `app/application/ports/llm_port.py` con `analyze_signal()`, `run_postmortem()`, `interpret_analysis()`
2. Crear `app/application/ports/notification_port.py` con `notify()`, `request_approval()`
3. Crear `tests/mocks/mock_broker.py`, `tests/mocks/mock_llm.py`, `tests/mocks/mock_notifications.py`

**Backend — Eliminar httpx de módulos de trading** (RF-102):
1. `app/llm/loop.py`:
   - Eliminar `httpx.get("/price/{symbol}")` → usar `IBrokerPort.get_price()`
   - Eliminar `httpx.post("/orders/preview")` → usar `RiskService.validate()` (Fase 2 lo formalizará)
   - Eliminar `httpx.post("/orders/place")` → llamar directamente al use case (que se crea en Fase 2)
   - Por ahora: llamar `IBKRBrokerAdapter.place_order()` directamente si el use case no existe aún
2. `app/positions/manager.py`:
   - Eliminar `httpx.get("/price/free/{symbol}")` → usar `IBrokerPort.get_price()`
3. `app/alerts/manager.py`:
   - Eliminar `httpx.get("/price/{symbol}")` → usar `IBrokerPort.get_price()`

**Inyección transitoria** (hasta que container.py exista en Fase 2):
- Los módulos que necesitan `IBrokerPort` reciben una instancia via parámetro de función, o acceden a un módulo-nivel `_broker: IBrokerPort | None = None` con `set_broker(broker)` para inyección manual desde `run.py`

**Events**:
- Publishes: none (event bus en Fase 3)
- Consumes: none

---

## Code Search (MANDATORY)

- [x] `httpx` en trading modules: `loop.py:91,114,138`, `manager.py:35`, `alerts/manager.py:60`
- [x] `IBKRClient.get_stock_price()` — interfaz a wrappear en `IBKRBrokerAdapter`
- [x] `IBKRClient.place_order()` — interfaz a wrappear
- [x] `IBKRClient.get_portfolio()` — interfaz a wrappear
- [x] No existe `application/ports/` — crear directorio

**Reuse decision**:
- Reuse as-is: `IBKRClient` (internamente, sin cambios), `OpenCodeAdapter` (de Issue 001)
- Extend: `loop.py`, `positions/manager.py`, `alerts/manager.py` (eliminar httpx)
- Build new: `IBrokerPort`, `ILLMPort`, `INotificationPort`, `IBKRBrokerAdapter`, todos los mocks

---

## Reference Documents

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `docs/dev/artifacts/refactor/08-prd.md` | RF-101, RF-102, RF-103 y sus AC |
| Architecture map | `docs/dev/artifacts/refactor/03-architecture-map.md` | IBKRClient methods, httpx call sites |
| Constraints | `.claude/current-dev-issues/.state/constraints.md` | Port design rules |

---

## Acceptance Criteria

- [ ] `grep -r "httpx" app/llm/loop.py app/positions/manager.py app/alerts/manager.py` → 0 resultados
- [ ] `IBrokerPort`, `ILLMPort`, `INotificationPort` en `application/ports/`
- [ ] `IBKRBrokerAdapter(IBrokerPort)` pasa todos los métodos al `IBKRClient` subyacente
- [ ] `MockBrokerAdapter.get_price()` devuelve un `Decimal` configurable sin conectar a IB
- [ ] Test: `MockBrokerAdapter` usado en test de `loop.py` — test pasa sin servidor HTTP
- [ ] Test: `MockBrokerAdapter` usado en test de `positions/manager.py` — test pasa sin servidor HTTP
- [ ] El sistema sigue operando en producción (no regression en flujo de trading)
- [ ] Todos los tests existentes pasan

## Definition of Done

- [ ] Todos los acceptance criteria verificados
- [ ] `tests/mocks/` existe con `mock_broker.py`, `mock_llm.py`, `mock_notifications.py`
- [ ] Al menos 1 test por mock adapter
- [ ] Mypy sin errores nuevos
- [ ] Issue movido a `done/`
