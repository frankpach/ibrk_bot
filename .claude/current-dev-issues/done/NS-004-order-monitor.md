# Issue NS-004: OrderExecutionMonitor + Fill Verification

**Module**: notification-system
**Type**: AFK
**Effort**: M
**Blocked by**: NS-001
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: Frank no sabe si su orden se ejecutó realmente. El sistema dice "Orden ejecutada" basándose en que IBKR aceptó la orden, no en que se llenó. A veces la orden queda pendiente o parcialmente llena.

**Business impact**: Posiciones fantasma (en IB pero no en DB) o DB inconsistente (cerrada en DB pero abierta en IB). El trailing stop no funciona si no hay trade en DB.

**Success signal**: Cada orden pasa por estados verificables: PENDING → SUBMITTED → FILLED. Si no se llena en 15s, Frank recibe alerta y el sistema reintenta o cancela.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---|---|---|---|---|---|
| Sistema | Bot | Pi | Pre/durante orden | Garantizar consistencia DB/IBKR | No bloquear threads |
| Frank | Trader | iPhone | Telegram | Saber el estado real de sus órdenes | Notificación solo si hay problema |

---

## WHAT — Constraints

- [ ] `place_order()` debe retornar estado real, no "PendingSubmit"
- [ ] Implementar `place_order_and_wait_fill()` con polling cada 2s, timeout 15s
- [ ] Estados de orden: PENDING → SUBMITTED → FILLED / PARTIAL / CANCELLED / REJECTED
- [ ] Si FILLED → obtener fill_price real de IBKR para calcular entry/exit exacto
- [ ] Si TIMEOUT → notificar y reintentar (max 3 reintentos)
- [ ] Si REJECTED → notificar con razón de IBKR
- [ ] `Trade` model necesita: `entry_fill_price`, `exit_fill_price`, `close_order_id`

**Module-specific rules**:
- [ ] No modificar IBKRClient.place_order() signature
- [ ] Polling via `ib.fills()` o `trade.orderStatus.status`
- [ ] Fallback: si no se puede obtener fill price, usar last market price + log warning

---

## HOW — Implementation Approach

**app/ibkr/order_monitor.py** (nuevo):
```python
class OrderExecutionMonitor:
    def place_and_monitor(self, symbol, action, quantity, order_type, limit_price=None) -> OrderResult: ...
    def _poll_fill_status(self, trade, timeout=15) -> FillStatus: ...
    def get_fill_price(self, order_id) -> float | None: ...

@dataclass
class OrderResult:
    success: bool
    order_id: str
    status: str  # FILLED, PARTIAL, REJECTED, TIMEOUT
    fill_price: float | None
    filled_quantity: float
    reason: str | None
```

**app/db/models.py**:
```python
@dataclass
class Trade:
    # ... existing fields ...
    entry_fill_price: float | None = None  # Precio real de fill
    exit_fill_price: float | None = None   # Precio real de fill de cierre
    close_order_id: str | None = None      # Order ID de orden de cierre
```

**app/api/main.py** (modificar `orders_place`):
```python
# 1. Insert PENDING
# 2. place_and_monitor()
# 3. If FILLED → update to OPEN with fill_price
# 4. If FAILED → update to FAILED, notify, raise
```

---

## Code Search

- [ ] `app/ibkr/client.py` — `_place_order_async()` — ya retorna trade object
- [ ] `app/api/main.py` — `orders_place()` — orden actual
- [ ] `app/positions/manager.py` — cierre de posiciones
- [ ] `app/db/database.py` — `insert_trade()`, `close_trade()`

**Reuse decision**:
- Reuse as-is: `IBKRClient.place_order()`, `Trade` model
- Build new: `OrderExecutionMonitor`
- Extend: `Trade` model (3 campos nuevos)

---

## Reference Documents

| Document | Path | What to Extract |
|---|---|---|
| Recomendaciones | docs/dev/artifacts/recomendaciones-toma-decisiones.md | Fill verification section |

---

## Acceptance Criteria

- [ ] AC-01: Orden MKT se llena en < 5s → fill_price exacto guardado en DB
- [ ] AC-02: Orden LMT no se llena en 15s → TIMEOUT, notificación, no trade en DB
- [ ] AC-03: Orden rechazada por IBKR → notificación con razón, DB en FAILED
- [ ] AC-04: Cierre de posición obtiene fill_price real, no estimado
- [ ] AC-05: 3 reintentos automáticos en timeout antes de notificar fallo

## Definition of Done

- [ ] Todos ACs verificados
- [ ] Tests nuevos: fill success, timeout, rejection, retry
- [ ] Schema migration para campos nuevos en trades
- [ ] Issue movido a `done/`
