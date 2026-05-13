# Issue RE-008: Partial Exits (Escalonado de Ganancias)

**Module**: risk-engine-v2
**Type**: AFK
**Effort**: M
**Blocked by**: RE-002, RE-007
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: Cuando una posición sube 5%, el sistema espera el TP fijo de 6% o deja que revierta hasta el SL. No hay forma de "bancar" ganancias parciales.

**Business impact**: Trades ganadores se convierten en perdedores. El profit factor se degrada porque no se protege el upside.

**Success signal**: Cerrar 50% en TP1 (1.5x riesgo), dejar 50% con trailing stop. Mejora R:R efectivo.

---

## WHAT — Constraints

- [ ] Cerrar 50% cuando P&L alcanza 1.5 × SL%
- [ ] Mover SL de los restantes 50% a breakeven + 0.3%
- [ ] Dejar correr restantes con trailing stop (TP2 = 3x riesgo)
- [ ] Notificar: "NVDA: 50% cerrado en +3.75%. Restantes con SL en breakeven."
- [ ] Requiere múltiples órdenes de cierre (o bracket order con partials)

---

## HOW — Implementation Approach

**app/positions/manager.py** (extender `check_positions()`):
```python
# Si P&L > 1.5 * SL
if pnl_pct > 1.5 * trade.stop_loss_pct and not trade.partial_exit_done:
    # Cerrar 50%
    close_quantity = trade.quantity * 0.5
    client.place_order(symbol, close_action, close_quantity, "MKT")
    trade.partial_exit_done = True
    trade.remaining_quantity = close_quantity
    # Mover SL de restantes
    # ...
```

**app/db/models.py**: Agregar `partial_exit_done`, `remaining_quantity`.

---

## Acceptance Criteria

- [ ] AC-01: Posición sube 1.5x SL → 50% cierra automáticamente
- [ ] AC-02: SL de restantes se mueve a breakeven
- [ ] AC-03: Trailing stop aplica solo a restantes 50%
- [ ] AC-04: P&L reportado correctamente para porción cerrada y abierta

## Definition of Done

- [ ] Todos ACs verificados
- [ ] Tests: partial exit, remaining trailing, P&L accuracy
- [ ] Issue movido a `done/`
