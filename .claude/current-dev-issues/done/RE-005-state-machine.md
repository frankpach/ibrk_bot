# Issue RE-005: Order Lifecycle State Machine (DB)

**Module**: risk-engine-v2
**Type**: AFK
**Effort**: M
**Blocked by**: —
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: No hay forma de saber si una orden está "pendiente de llenarse", "llenada", "fallida", o "en proceso de cierre". El estado binario OPEN/CLOSED es insuficiente.

**Business impact**: Órdenes parcialmente llenas, reintentos innecesarios, posiciones huérfanas.

**Success signal**: Estado de cada orden es trazable: PENDING → SUBMITTED → PARTIAL → FILLED → OPEN → CLOSE_REQUESTED → CLOSE_FILLED → CLOSED.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---|---|---|---|---|---|
| Sistema | Bot | Pi | 24/7 | Rastrear estado exacto de cada orden | SQLite schema change |

---

## WHAT — Constraints

- [ ] Nuevos estados: `PENDING`, `SUBMITTED`, `PARTIAL`, `FILLED`, `OPEN`, `CLOSE_REQUESTED`, `CLOSE_PARTIAL`, `CLOSE_FILLED`, `CLOSED`, `FAILED`, `CANCELLED`
- [ ] `trade_status` enum en DB (no solo status='OPEN'/'CLOSED')
- [ ] Transiciones válidas definidas (máquina de estados)
- [ ] Fallback: estados antiguos mapean a nuevo enum

**Module-specific rules**:
- [ ] Migration SQLite: ALTER TABLE trades ADD COLUMN trade_status
- [ ] Backward compat: OPEN → 'OPEN', CLOSED → 'CLOSED'

---

## HOW — Implementation Approach

**app/db/models.py**:
```python
TRADE_STATUSES = [
    "PENDING", "SUBMITTED", "PARTIAL", "FILLED", 
    "OPEN", "CLOSE_REQUESTED", "CLOSE_PARTIAL", 
    "CLOSE_FILLED", "CLOSED", "FAILED", "CANCELLED"
]

@dataclass
class Trade:
    # ... existing fields ...
    trade_status: str = "PENDING"
```

**app/db/database.py**:
```python
def update_trade_status(trade_id: int, status: str, order_id: str | None = None, fill_price: float | None = None): ...
```

---

## Acceptance Criteria

- [ ] AC-01: Nueva tabla/estructura soporta todos los estados
- [ ] AC-02: Transición OPEN → CLOSE_REQUESTED → CLOSE_FILLED → CLOSED funciona
- [ ] AC-03: Datos antiguos siguen funcionando

## Definition of Done

- [ ] Todos ACs verificados
- [ ] Migration script tested
- [ ] Issue movido a `done/`
