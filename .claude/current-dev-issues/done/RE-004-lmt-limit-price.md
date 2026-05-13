# Issue RE-004b: LMT Limit Price en loop.py

**Module**: mtf-learning-engine (incorporado desde risk-engine-v2)
**Type**: AFK
**Effort**: XS
**Blocked by**: ninguno
**Requires review**: false

---

## WHY — El Problema

`IBKRClient.place_order()` ya soporta órdenes LMT con `limit_price`. `validate_order()` ya acepta LMT. Pero `_execute_order()` en `loop.py` manda siempre `"limit_price": None` — por eso todas las entradas son efectivamente MKT aunque el código diga LMT.

Con $500 de capital y slippage de 0.5% en cada entrada, se pierde ~$2.50 por trade innecesariamente.

**Success signal**: Una orden BUY en AAPL a precio de mercado $215.00 se coloca como LMT @ $215.00 (precio actual, no más). La orden se llena en el bid/ask sin pagar spread extra.

---

## WHAT — Qué falta exactamente

En `app/llm/loop.py`, función `_execute_order()`:

**ACTUAL** (líneas ~92 y ~118):
```python
"limit_price": None,   # ← siempre None = MKT efectivo
```

**CORRECCIÓN**:
```python
# Obtener precio actual para calcular limit_price
current_price = _get_current_price(symbol)  # ya existe en positions/manager.py
slippage = 0.005  # 0.5% buffer — importar de settings o hardcodear

if decision.action == "BUY":
    limit_price = round(current_price * (1 + slippage), 2)
elif decision.action == "SELL":
    limit_price = round(current_price * (1 - slippage), 2)

# En el payload:
"order_type": "LMT",
"limit_price": limit_price,
```

**NO tocar**: `IBKRClient`, `validate_order()`, `OrderExecutionMonitor` — ya manejan LMT correctamente.

---

## Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `app/llm/loop.py` | Calcular `limit_price` en `_execute_order()` antes de preview y place |
| `app/config/settings.py` | +`ENTRY_SLIPPAGE_BUFFER = 0.005` si no existe |

---

## Acceptance Criteria

- [ ] AC-01: BUY a mercado $215.00, buffer 0.5% → orden LMT @ $216.08
- [ ] AC-02: SELL a mercado $215.00, buffer 0.5% → orden LMT @ $213.93
- [ ] AC-03: Preview en Telegram muestra "Order type: LMT @ $216.08"
- [ ] AC-04: Cierres por SL/TP siguen usando MKT (no cambia `_close_position()`)

## Definition of Done

- [ ] Todos ACs verificados en paper trading
- [ ] Test: cálculo de limit_price BUY y SELL, fallback si precio no disponible
- [ ] Issue movido a `done/`
