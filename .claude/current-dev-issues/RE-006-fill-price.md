# Issue RE-006: Real Fill Price Tracking

**Module**: risk-engine-v2
**Type**: AFK
**Effort**: S
**Blocked by**: RE-005
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: El P&L reportado usa precios estimados (último precio de mercado), no el precio real de fill. En alta volatilidad, la diferencia puede ser 0.5%-1%.

**Business impact**: P&L falso. Post-mortem aprende de datos incorrectos. Win rate calculado es impreciso.

**Success signal**: P&L usa precios reales de IBKR fills. Post-mortem analiza datos exactos.

---

## WHAT — Constraints

- [ ] `Trade.entry_fill_price`: precio real de fill de entrada
- [ ] `Trade.exit_fill_price`: precio real de fill de cierre
- [ ] Obtener de IBKR fills API después de cada orden
- [ ] Fallback: si no disponible, usar estimado + log warning

---

## HOW — Implementation Approach

**app/ibkr/client.py** (extender):
```python
def get_fill_price_for_order(self, order_id: str) -> float | None: ...
```

**app/api/main.py**:
```python
# Después de place_order
fill_price = client.get_fill_price_for_order(order_result["order_id"])
```

---

## Acceptance Criteria

- [ ] AC-01: Orden ejecutada → entry_fill_price es precio real, no estimado
- [ ] AC-02: Cierre ejecutado → exit_fill_price es precio real
- [ ] AC-03: P&L calculado con precios reales

## Definition of Done

- [ ] Todos ACs verificados
- [ ] Issue movido a `done/`
