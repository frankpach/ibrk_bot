# Issue MTE-002: Fix _dim_price_change() — Dirección sin abs()

**Module**: mtf-learning-engine
**Type**: AFK
**Effort**: S
**Blocked by**: None
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: Una acción que subió 5% hoy y otra que bajó 5% producen el mismo score de "price_change" para una señal BUY. El sistema no distingue entre momentum positivo y caída brusca al evaluar entradas.

**Business impact**: Se abren posiciones BUY en activos en colapso intraday (caída > 3%) con el mismo score que en activos con momentum positivo. Trades abiertos en bear momentum tienen peor win rate.

**Success signal**: Subida del 2% → score alto para BUY. Caída del 4% → score bajo. Los tests pasan con los nuevos valores.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| Motor Autónomo | Sistema | Raspberry Pi | Producción | Score refleja dirección del precio | No romper pipeline |

---

## WHAT — Constraints

- [ ] No agregar parámetros a la firma de `_dim_price_change(features)` — el scorer no conoce la acción en este nivel
- [ ] La nueva lógica asume BUY como caso primario (es la acción más común en el sistema)
- [ ] Actualizar tests simultáneamente en el mismo commit
- [ ] No tocar otras dimensiones del scorer

---

## HOW — Implementation Approach

**`app/analysis/scorer.py` — reemplazar `_dim_price_change()`**:

```python
def _dim_price_change(features) -> float:
    pc = features.price_change_pct
    if pc is None: return 0.0
    if 1.0 <= pc <= 4.0:   return 0.9   # Momentum positivo moderado — ideal BUY
    if 0.0 <= pc < 1.0:    return 0.6   # Neutral-positivo
    if 4.0 < pc:            return 0.7   # Fuerte momentum — cuidado overbought
    if -1.0 <= pc < 0.0:   return 0.4   # Leve corrección — posible pullback
    if -3.0 <= pc < -1.0:  return 0.2   # Caída moderada — señal de alerta
    return 0.1                           # Colapso (< -3%) — posible bear trap
```

**`tests/analysis/test_scorer.py` — actualizar**:
- `test_dim_price_change_high`: pc=6.0 → esperar 0.7 (antes: 1.0)
- `test_dim_price_change_med`: pc=1.5 → esperar 0.9 (antes: 0.5)
- `test_dim_price_change_low`: pc=0.3 → esperar 0.6 (antes: 0.1)
- Agregar: pc=-2.0 → esperar 0.2
- Agregar: pc=-5.0 → esperar 0.1

---

## Code Search

- [x] `app/analysis/scorer.py:140-154` — `_dim_price_change()` actual leído
- [x] `tests/analysis/test_scorer.py:168-186` — tests actuales leídos

**Reuse decision**:
- Reuse as-is: firma, integración en `compute_score()`
- Build new: lógica interna direccional

---

## Reference Documents

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `docs/dev/artifacts/mtf-learning-engine/08-prd.md` | REQ-03, AC-03.1 a AC-03.4 |

---

## Acceptance Criteria

- [ ] AC-03.1: `price_change_pct = 2.0` → score 0.9
- [ ] AC-03.2: `price_change_pct = -4.0` → score 0.1
- [ ] AC-03.3: `price_change_pct = None` → score 0.0
- [ ] AC-03.4: Todos los tests de `_dim_price_change` en test_scorer.py pasan
- [ ] AC-03.5: No hay regresiones en el resto de test_scorer.py

## Definition of Done

- [ ] Todos los ACs verificados
- [ ] `pytest tests/analysis/test_scorer.py` pasa sin errores
- [ ] Issue movido a `done/`
