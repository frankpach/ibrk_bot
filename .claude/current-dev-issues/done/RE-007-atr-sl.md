# Issue RE-007: ATR-Based Adaptive Stop Loss

**Module**: risk-engine-v2
**Type**: AFK
**Effort**: S
**Blocked by**: —
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: SL fijo de 2.5% para NVDA (ATR 2.8%) se toca por ruido normal del mercado. Para SPY (ATR 1.2%) el SL es demasiado amplio, desperdiciando potencial de ganancia.

**Business impact**: Stops innecesarios en símbolos volátiles (churn). SL ineficiente en símbolos estables.

**Success signal**: SL = 1.5 × ATR% (mín 1.5%, máx 5%). NVDA SL=4.2%, SPY SL=1.8%.

---

## WHAT — Constraints

- [ ] `SL = 1.5 × ATR_pct`
- [ ] Mínimo: `MIN_SL_PCT = 0.015` (1.5%)
- [ ] Máximo: `MAX_SL_PCT = 0.05` (5.0%)
- [ ] Aplicar en `validate_order()` y `orders_preview()`
- [ ] Guardar SL usado en DB para trailing stop reference

---

## HOW — Implementation Approach

**app/risk/adaptive_sl.py**:
```python
def calculate_adaptive_sl(atr_pct: float) -> float:
    sl = atr_pct * 1.5
    return max(0.015, min(0.05, sl))
```

**app/api/main.py**: Usar en `orders_preview()` y `orders_place()`.

---

## Acceptance Criteria

- [ ] AC-01: ATR=2.8% → SL=4.2%
- [ ] AC-02: ATR=1.2% → SL=1.8%
- [ ] AC-03: ATR=0.8% → SL=1.5% (mínimo)
- [ ] AC-04: ATR=4.0% → SL=5.0% (máximo)

## Definition of Done

- [ ] Todos ACs verificados
- [ ] Tests: edge cases, min/max bounds
- [ ] Issue movido a `done/`
