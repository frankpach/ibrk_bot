# Issue RE-010: ML Ligero como Filtro Previo

**Module**: risk-engine-v2
**Type**: AFK
**Effort**: L
**Blocked by**: RE-001
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: El LLM es lento (30-60s) y caro (tokens). Muchas señales terminan en IGNORE después de todo ese esfuerzo.

**Business impact**: Latencia alta. Costo de tokens innecesario. Frank espera 60s para saber que la señal era mala.

**Success signal**: Un filtro rápido (< 100ms) rechaza el 40% de señales débiles antes de llamar al LLM. Solo las mejores pasan al LLM.

---

## WHAT — Constraints

- [ ] Modelo: Logistic Regression (scikit-learn)
- [ ] Features: RSI, MACD, ATR, vol_ratio, bollinger_pos, RS_vs_SPY, day_of_week, hour
- [ ] Entrenamiento: datos históricos de trades (wins/losses)
- [ ] Predicción: P(win) ∈ [0,1]
- [ ] Umbral: P(win) < 0.45 → IGNORE automático
- [ ] P(win) >= 0.45 → pasar al LLM
- [ ] Re-entrenar semanalmente con nuevos trades

---

## HOW — Implementation Approach

**app/ml/filter.py**:
```python
class SignalFilter:
    def __init__(self, model_path="models/signal_filter.pkl"): ...
    def predict(self, features: FeatureSet) -> float: ...  # P(win)
    def should_ignore(self, features: FeatureSet) -> bool: ...
    def retrain(self, trades: list[Trade]): ...
```

**app/llm/loop.py**:
```python
def process_pending_signals():
    for signal in signals:
        # Filtro rápido primero
        if signal_filter.should_ignore(features):
            mark_signal_processed(signal.id)
            continue
        # Solo si pasa el filtro → LLM
        decision = analyze_signal(...)
```

---

## Acceptance Criteria

- [ ] AC-01: Filtro rechaza señal en < 100ms
- [ ] AC-02: P(win) < 0.45 → IGNORE sin LLM
- [ ] AC-03: P(win) >= 0.45 → LLM llamado
- [ ] AC-04: Retraining semanal actualiza modelo

## Definition of Done

- [ ] Todos ACs verificados
- [ ] Tests: accuracy, speed, threshold behavior
- [ ] Issue movido a `done/`
