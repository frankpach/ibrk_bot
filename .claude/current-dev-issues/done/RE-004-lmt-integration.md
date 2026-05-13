# Issue RE-004: LMT Orders + Integration

**Module**: risk-engine-v2
**Type**: AFK
**Effort**: S
**Blocked by**: RE-001, RE-003
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: Las órdenes de entrada siempre son MKT. En acciones con spread amplio (especialmente en apertura), el precio de ejecución es 0.3%-1% peor que el precio mostrado.

**Business impact**: Cada entrada pierde slippage innecesario. En un sistema con $500 de capital y 2% de riesgo por trade, 0.5% de slippage representa un 25% del riesgo esperado.

**Success signal**: Entrada en NVDA se coloca como LMT a $215.00 en vez de MKT a $215.50. Ahorra $0.50 por acción.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---|---|---|---|---|---|
| Sistema | Bot | Pi | Pre-orden | Colocar LMT para mejores fills | Fallback a MKT si es necesario (v2) |
| Frank | Trader | iPhone | Telegram | Ver que la orden es LMT en preview | Claro y transparente |

---

## WHAT — Constraints

- [ ] Entradas (BUY/SELL nuevas posiciones) usan `LMT` por defecto
- [ ] Limit price = current_price ± slippage_buffer_pct (±0.5% default)
- [ ] Salidas (SL, TP, manual close) siguen usando `MKT`
- [ ] Preview muestra: "Order type: LMT @ $215.00 (slippage buffer: 0.5%)"
- [ ] Integration: `validate_order()` acepta LMT y valida limit_price

**Module-specific rules**:
- [ ] No modificar `IBKRClient.place_order()` — ya acepta order_type y limit_price
- [ ] Backward compat: si order_type no especificado, default a LMT para entradas

---

## HOW — Implementation Approach

**app/api/main.py** (modificar):
- `orders_preview()`:
  ```python
  if req.order_type == "LMT" or req.order_type is None:
      limit_price = current_price * (1 + slippage_buffer) if req.action == "BUY" else current_price * (1 - slippage_buffer)
      order_type = "LMT"
  ```
- `orders_place()`:
  - Igual lógica para calcular limit_price si no viene en request
  - Pasar `order_type="LMT"` y `limit_price` a `client.place_order()`

**app/llm/loop.py** (modificar):
- `_execute_order()`: payload usa `"order_type": "LMT"` en vez de `"MKT"`

**app/risk/validator.py** (modificar):
- Validar que `limit_price` esté presente si `order_type == "LMT"`
- Validar que `limit_price` esté dentro de ±5% del current_price (safety check)

---

## Code Search

- [ ] `app/api/main.py` — `orders_preview()`, `orders_place()`
- [ ] `app/llm/loop.py` — `_execute_order()` payload
- [ ] `app/risk/validator.py` — `ALLOWED_ORDER_TYPES` agregar "LMT"
- [ ] `app/ibkr/client.py` — `place_order()` signature (ya acepta limit_price)

**Reuse decision**:
- Reuse as-is: `place_order()`, `SLIPPAGE_BUFFER`
- Build new: LMT logic en preview/place
- Extend: `validate_order()`, `_execute_order()`

---

## Reference Documents

| Document | Path | What to Extract |
|---|---|---|
| PRD | docs/dev/artifacts/risk-engine-v2/08-prd.md | REQ-06, REQ-07 |
| Interface design | docs/dev/artifacts/risk-engine-v2/06-interface-design.md | LMT workflow |

---

## Acceptance Criteria

- [ ] AC-06.1: BUY a $214.91, buffer 0.5% → LMT @ $215.99
- [ ] AC-06.2: SELL a $214.91, buffer 0.5% → LMT @ $213.84
- [ ] AC-06.3: Preview muestra "Order type: LMT @ $215.99"
- [ ] AC-06.4: SL/TP cierre usa MKT (no cambia)
- [ ] AC-07.1: `validate_order()` rechaza LMT sin limit_price
- [ ] AC-07.2: `validate_order()` rechaza limit_price > 5% away from current_price

## Definition of Done

- [ ] Todos ACs verificados
- [ ] Tests nuevos: LMT calculation, validation, preview response
- [ ] Issue movido a `done/`
