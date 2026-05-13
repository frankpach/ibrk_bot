# Issue MTE-001: Fix _dim_volatility() — Invertir escala ATR

**Module**: mtf-learning-engine
**Type**: AFK
**Effort**: S
**Blocked by**: None
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: El sistema premia señales en activos con alta volatilidad (ATR > 4%), cuando en realidad alta volatilidad aumenta la probabilidad de que el SL se active por ruido antes de que la señal se confirme. El resultado es una tasa de stop-loss activados por ruido más alta de lo necesario.

**Business impact**: Trades en activos con ATR > 4% pierden por SL activado por ruido, no por tendencia real. El win rate se degrada sistemáticamente.

**Success signal**: Con ATR = 1.5% el score de volatilidad es máximo. Con ATR = 5% el score es bajo. Los tests de scorer pasan con los nuevos valores.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| Motor Autónomo | Sistema | Raspberry Pi | Producción | Señales de calidad en activos con volatilidad apropiada | No romper pipeline |
| Frank Developer | Quant | Desktop | Home office | Scorer produce señales estadísticamente correctas | Tests deben pasar |

**Primary user**: Motor Autónomo — recibe el score en cada ciclo de evaluación.

---

## WHAT — Constraints

- [ ] No modificar la firma de `_dim_volatility(features)` — mismo input/output
- [ ] Actualizar `tests/analysis/test_scorer.py` en el mismo commit — si los tests fallan, el commit se rechaza
- [ ] No tocar ninguna otra dimensión del scorer en este issue
- [ ] Fallback: si `features.atr_pct is None` → retornar 0.0 (ya existe, mantener)

---

## HOW — Implementation Approach

**`app/analysis/scorer.py` — reemplazar `_dim_volatility()`**:

```python
def _dim_volatility(features) -> float:
    if features.atr_pct is None:
        return 0.0
    atr = features.atr_pct
    if 1.0 <= atr <= 2.5: return 1.0   # Zona óptima para SL fijo
    if 0.5 <= atr < 1.0:  return 0.6   # Muy baja: poco movimiento esperado
    if 2.5 < atr <= 4.0:  return 0.5   # Alta: riesgo de SL por ruido
    if atr > 4.0:          return 0.2   # Muy alta: señal débil
    return 0.3
```

**`tests/analysis/test_scorer.py` — actualizar valores esperados**:
- `test_dim_volatility_high`: ATR=5.0 → esperar 0.2 (antes: 1.0)
- `test_dim_volatility_med`: ATR=1.2 → esperar 1.0 (antes: 0.5)
- `test_dim_volatility_low`: ATR=0.3 → esperar 0.3 (antes: 0.1)
- Agregar test: ATR=2.0 → esperar 1.0
- Agregar test: ATR=3.0 → esperar 0.5

---

## Code Search

- [x] `app/analysis/scorer.py:96-110` — `_dim_volatility()` actual leído
- [x] `tests/analysis/test_scorer.py:110-128` — tests actuales leídos
- [x] `compute_score()` en scorer.py:177 — no cambia, llama `_dim_volatility(features)`

**Reuse decision**:
- Reuse as-is: firma de función, integración en `compute_score()`
- Build new: lógica interna de `_dim_volatility()`
- Update: tests de `_dim_volatility` en test_scorer.py

---

## Reference Documents

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `docs/dev/artifacts/mtf-learning-engine/08-prd.md` | REQ-02, AC-02.1 a AC-02.5 |
| Architecture map | `docs/dev/artifacts/mtf-learning-engine/03-architecture-map.md` | GAP identificado en scorer |
| Constraints | `.claude/current-dev-issues/.state/constraints.md` | No tocar app/risk/ |

---

## Acceptance Criteria

- [ ] AC-02.1: ATR = 1.5% → `_dim_volatility()` retorna 1.0
- [ ] AC-02.2: ATR = 5.0% → `_dim_volatility()` retorna 0.2
- [ ] AC-02.3: ATR = None → retorna 0.0
- [ ] AC-02.4: `compute_score()` con ATR=5% produce score total más bajo que con ATR=1.5% (ceteris paribus)
- [ ] AC-02.5: Todos los tests en `tests/analysis/test_scorer.py` pasan (incluyendo los actualizados)
- [ ] AC-02.6: No hay regresiones en `tests/analysis/test_pipeline.py`

## Definition of Done

- [ ] Todos los ACs verificados
- [ ] `pytest tests/analysis/test_scorer.py` pasa sin errores
- [ ] `pytest tests/analysis/test_pipeline.py` pasa sin errores
- [ ] Issue movido a `done/`
