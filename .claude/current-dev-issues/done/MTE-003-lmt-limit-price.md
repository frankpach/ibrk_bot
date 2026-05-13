# Issue MTE-003: LMT Limit Price en _execute_order()

**Module**: mtf-learning-engine
**Type**: AFK
**Effort**: XS
**Blocked by**: None
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: Todas las órdenes de entrada se ejecutan como MKT efectivo porque `_execute_order()` siempre manda `"limit_price": None`. Con $500 de capital, un slippage de 0.5% por entrada representa $2.50 perdidos innecesariamente en cada trade.

**Business impact**: Pérdida acumulada de slippage evitable. El cliente IBKR y el validator ya soportan LMT — solo falta el cálculo del precio.

**Success signal**: Una orden BUY en AAPL a $215 se coloca como LMT @ $216.08 (buffer 0.5%). Se ejecuta al mejor precio disponible dentro de ese límite.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| Motor Autónomo | Sistema | Raspberry Pi | Producción | Mejores precios de entrada | Fallback a MKT si precio no disponible |
| Frank Trader | Trader | iPhone/Telegram | Remoto | Ver que la orden es LMT en la notificación | Sin cambios en UX |

---

## WHAT — Constraints

- [ ] Solo modificar `_execute_order()` en `app/llm/loop.py` — no tocar `IBKRClient` ni `validate_order()`
- [ ] Cierres de posición (SL/TP) en `_close_position()` siguen usando MKT — no cambiar
- [ ] Si `_get_current_price()` falla o retorna None → fallback a MKT (no bloquear la orden)
- [ ] `ENTRY_SLIPPAGE_BUFFER` en settings.py o default hardcodeado a 0.005

---

## HOW — Implementation Approach

**`app/llm/loop.py` — modificar `_execute_order()`**:

Antes del preview payload, calcular limit_price:
```python
from app.config.settings import ENTRY_SLIPPAGE_BUFFER  # o default 0.005
slippage = getattr(settings, 'ENTRY_SLIPPAGE_BUFFER', 0.005)

# Obtener precio actual (la función ya existe en positions/manager.py o via data_layer)
try:
    price_data = httpx.get(f"{API_BASE}/market/price/{symbol}", timeout=5).json()
    current_price = price_data.get("price")
except Exception:
    current_price = None

if current_price:
    if decision.action == "BUY":
        limit_price = round(current_price * (1 + slippage), 2)
    else:
        limit_price = round(current_price * (1 - slippage), 2)
    order_type = "LMT"
else:
    limit_price = None
    order_type = "MKT"  # fallback

# En ambos payloads (preview y place):
"order_type": order_type,
"limit_price": limit_price,
```

**`app/config/settings.py`** — agregar si no existe:
```python
ENTRY_SLIPPAGE_BUFFER: float = float(os.getenv("ENTRY_SLIPPAGE_BUFFER", "0.005"))
```

---

## Code Search

- [x] `app/llm/loop.py:83-145` — `_execute_order()` leído, `"limit_price": None` confirmado
- [x] `app/ibkr/client.py` — `place_order()` ya acepta `limit_price` y `order_type`
- [x] `app/risk/validator.py` — ya acepta "LMT" en `ALLOWED_ORDER_TYPES`

**Reuse decision**:
- Reuse as-is: `IBKRClient.place_order()`, `validate_order()`, API endpoint `/orders/place`
- Build new: cálculo de limit_price en `_execute_order()`

---

## Reference Documents

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `docs/dev/artifacts/mtf-learning-engine/08-prd.md` | REQ-11, AC-11.1 a AC-11.5 |

---

## Acceptance Criteria

- [ ] AC-11.1: BUY a $215.00, buffer 0.5% → payload contiene `"order_type": "LMT"` y `"limit_price": 216.08`
- [ ] AC-11.2: SELL a $215.00, buffer 0.5% → `"limit_price": 213.92`
- [ ] AC-11.3: Si precio no disponible → `"order_type": "MKT"` y `"limit_price": None` (fallback)
- [ ] AC-11.4: Cierres en `_close_position()` no cambian — siguen con MKT
- [ ] AC-11.5: `pytest tests/test_signal_loop.py` pasa sin regresiones

## Definition of Done

- [ ] Todos los ACs verificados en paper trading
- [ ] Test agregado: verificar cálculo de limit_price BUY y SELL
- [ ] Issue movido a `done/`
