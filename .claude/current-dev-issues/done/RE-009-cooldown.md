# Issue RE-009: Re-entry Rules + Cooldown

**Module**: risk-engine-v2
**Type**: AFK
**Effort**: S
**Blocked by**: —
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: Después de un stop-loss, el scanner puede generar la misma señal 5 minutos después. Frank puede perder 2.5% tres veces seguidas en el mismo día en el mismo símbolo.

**Business impact**: "Death by a thousand cuts". Una mala racha en un símbolo puede destruir el capital.

**Success signal**: Después de un SL en NVDA, el sistema no re-entra en NVDA por 24h o hasta que el precio se mueva > 2% desde el SL.

---

## WHAT — Constraints

- [ ] Cooldown por símbolo después de SL: 24h (configurable)
- [ ] O: requerir que precio se mueva > 2% desde el SL antes de reconsiderar
- [ ] Cooldown por símbolo después de TP: 4h (opcional)
- [ ] Guardar `last_exit_at` y `last_exit_price` en `SymbolParameter` o registry
- [ ] Rechazar señal con razón: "Cooldown activo para NVDA (SL hace 3h)"

---

## HOW — Implementation Approach

**app/risk/cooldown.py**:
```python
class ReentryCooldown:
    def __init__(self, cooldown_hours=24, min_move_pct=0.02): ...
    def can_reenter(self, symbol, current_price) -> tuple[bool, str]: ...
    def record_exit(self, symbol, exit_price, exit_reason): ...
```

---

## Acceptance Criteria

- [ ] AC-01: SL en NVDA hace 2h → señal nueva rechazada
- [ ] AC-02: SL hace 25h → señal permitida
- [ ] AC-03: Precio se movió 3% desde SL → señal permitida aunque < 24h
- [ ] AC-04: TP no activa cooldown (o activa 4h opcional)

## Definition of Done

- [ ] Todos ACs verificados
- [ ] Tests: cooldown, reentry conditions, time-based, price-based
- [ ] Issue movido a `done/`
