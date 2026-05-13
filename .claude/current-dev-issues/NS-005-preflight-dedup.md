# Issue NS-005: Order Deduplication + Pre-flight Checks

**Module**: notification-system
**Type**: AFK
**Effort**: S
**Blocked by**: NS-004
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: Si `check_positions()` corre cada 2 min y el precio está en el límite del SL, puede enviar múltiples órdenes de cierre. O si el scanner detecta la misma señal 2 veces, puede generar 2 órdenes de entrada para el mismo símbolo.

**Business impact**: Órdenes duplicadas = exposición doble al riesgo. Comisiones dobles. P&L imposible de rastrear.

**Success signal**: Nunca hay 2 órdenes de entrada para el mismo símbolo. Nunca hay 2 órdenes de cierre para la misma posición.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---|---|---|---|---|---|
| Sistema | Bot | Pi | Pre-orden | Evitar duplicados | < 1ms de overhead |

---

## WHAT — Constraints

- [ ] `PendingOrders` registry en memoria: `{symbol: order_id}`
- [ ] Pre-flight checklist antes de cada orden:
  1. IB Gateway conectado
  2. Precio reciente (< 30s)
  3. Buying power suficiente
  4. No hay orden pendiente para este símbolo
  5. validate_order() pasa
- [ ] Auto-limpieza de registry cuando orden se llena o falla
- [ ] Timeout de seguridad: orden pendiente > 60s se considera stale

**Module-specific rules**:
- [ ] No DB writes (in-memory)
- [ ] Thread-safe (APScheduler + bot pueden colisionar)

---

## HOW — Implementation Approach

**app/risk/preflight.py** (nuevo):
```python
class PreFlightChecker:
    def check(self, symbol, action, estimated_cost) -> tuple[bool, str]: ...
    def _is_ib_connected(self) -> bool: ...
    def _has_price_data(self, symbol) -> bool: ...
    def _has_buying_power(self, cost) -> bool: ...
    def _no_pending_order(self, symbol) -> bool: ...

class PendingOrderRegistry:
    def add(self, symbol, order_id): ...
    def remove(self, symbol): ...
    def has(self, symbol) -> bool: ...
    def clear_stale(self, max_age_seconds=60): ...
```

---

## Code Search

- [ ] `app/api/main.py` — `orders_place()`
- [ ] `app/positions/manager.py` — `check_positions()` cierre
- [ ] `app/llm/loop.py` — `_execute_order()`

---

## Acceptance Criteria

- [ ] AC-01: Orden pendiente para AAPL → segunda orden rechazada con "pending order exists"
- [ ] AC-02: IB desconectado → orden rechazada antes de enviar a IBKR
- [ ] AC-03: Buying power insuficiente → rechazada antes de enviar
- [ ] AC-04: Orden stale (>60s) → auto-limpieza, siguiente orden permitida

## Definition of Done

- [ ] Todos ACs verificados
- [ ] Tests: duplicación, preflight failure, stale cleanup
- [ ] Issue movido a `done/`
