# Why Decisions: mtf-learning-engine

**Module**: mtf-learning-engine
**Phase**: Phase 1 — Architecture
**Status**: complete
**Date**: 2026-05-13

---

## WD-01: Corregir preprocessor para multi-market ANTES de agregar weekly

**Decisión**: El primer fix en el preprocessor es usar `build_contract()` con `symbol_meta`, no agregar weekly primero.

**Por qué**: Sin el fix multi-market, el scan falla silenciosamente para futuros, forex y crypto. Agregar weekly a un preprocessor que solo funciona para equities no sirve. El orden correcto es: fix multi-market → luego agregar weekly.

**Alternativa descartada**: Agregar weekly primero — introduce un timeframe nuevo antes de que el sistema funcione correctamente para todos los asset classes.

---

## WD-02: Agregar `feature_snapshot_id` a `trades` en lugar de buscar por timestamp

**Decisión**: La migración agrega `feature_snapshot_id INTEGER` a la tabla `trades` y se popula al insertar el trade.

**Por qué**: La alternativa (buscar el feature_snapshot más cercano por símbolo y timestamp) es frágil — puede retornar un snapshot de otra señal si el sistema procesó el mismo símbolo dos veces en ventanas cercanas. El FK explícito es la única forma confiable.

**Alternativa descartada**: JOIN por símbolo + timestamp con ventana de ±5min — demasiado propenso a falsos matches en días de alta actividad.

---

## WD-03: Corregir tests de scorer simultáneamente con el fix

**Decisión**: Los tests de `_dim_volatility` y `_dim_price_change` se actualizan en el mismo commit que el fix al código.

**Por qué**: Si se corrige el código sin actualizar los tests, el CI falla inmediatamente y el PR no puede mergearse. Los tests actuales documentan el comportamiento incorrecto — deben reflejar el comportamiento correcto nuevo.

**Riesgo**: Cambiar tests y código al mismo tiempo puede enmascarar regresiones. Mitigación: el test de `compute_score()` de integración (`test_compute_score_priority`) debe seguir pasando — si el score total cambia significativamente, hay un bug en la lógica de normalización.

---

## WD-04: Weekly como filtro de veto, no como dimensión de score

**Decisión**: La tendencia semanal NO se agrega al `QuantScore` como dimensión sumativa. Se implementa como un filtro boolean previo al scoring.

**Por qué**: Si se agrega como dimensión sumativa, una señal contra la tendencia macro puede compensarse con alto volumen o RSI extremo y igual generar un score alto. El propósito del weekly es **vetar** señales que van contra la tendencia, no ponderar. Un trade BUY en downtrend semanal es incorrecto independientemente de otros indicadores.

**Implementación**: En el preprocessor, si `weekly_trend == "BEARISH"` y `action == "BUY"`, reducir `strength` un nivel (STRONG→MEDIUM, MEDIUM→WEAK). En el pipeline, incluir `weekly_trend` como feature del SignalFilter, no como dimensión del QuantScorer.

**Alternativa descartada**: Agregar `trend_macro` como dimensión al QuantScorer con peso 0.15 — mezcla dos conceptos distintos (filtro vs puntuación).

---

## WD-05: retrain() carga features desde DB, no desde objetos Trade en memoria

**Decisión**: La función `retrain()` hace una query a `feature_snapshots` por `feature_snapshot_id` del trade, en lugar de esperar features en el objeto Trade.

**Por qué**: Los objetos Trade que llegan al retrain son dataclasses sin el campo `features`. Agregarlo al dataclass crearía un objeto pesado y cambiaría la firma de todas las funciones que crean Trade objects. La DB es la fuente de verdad.

**Implementación**:
```python
def retrain(self, trades: list) -> bool:
    from app.db.database import get_feature_snapshot_by_id, get_connection
    for trade in trades:
        snapshot_id = getattr(trade, 'feature_snapshot_id', None)
        if not snapshot_id:
            continue
        snapshot = get_feature_snapshot_by_id(snapshot_id)
        if snapshot is None:
            continue
        X.append(self._extract_features(snapshot))
        y.append(1 if (trade.pnl_pct or 0) > 0 else 0)
```

---

## WD-06: Backtest calibration corre en background thread con delay entre símbolos

**Decisión**: `run_backtest_calibration()` se ejecuta en un `threading.Thread` al aprobar un símbolo, con `time.sleep(2)` entre requests para respetar el rate limit de IBKR.

**Por qué**: La calibración puede tomar 5-15 segundos por símbolo (requests históricos + simulación). Bloquear el pipeline de trading durante la aprobación de un símbolo es inaceptable. El rate limit de IBKR (~50 req/10min) se comparte con el scanner.

**Alternativa descartada**: Queue con worker thread dedicado — overkill para la frecuencia de activación de nuevos símbolos (una vez cada días/semanas).

---

## WD-07: SignalFilter retrain usa TimeSeriesSplit con 5 folds, evalúa en fold final

**Decisión**: El retrain usa `TimeSeriesSplit(n_splits=5)` para validación, pero **entrena el modelo final sobre todos los datos** (no solo el último fold).

**Por qué**: En series temporales, no se puede mezclar datos futuros con pasados para entrenamiento. El objetivo del split es medir la calidad del modelo (AUC reportado), no limitar los datos de entrenamiento. Con pocos datos (10-100 trades), usar solo el último fold para entrenar desperdiciaría el 80% de los datos.

**Implementación**:
```python
# Evaluar calidad con CV temporal
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
tscv = TimeSeriesSplit(n_splits=5)
auc_scores = cross_val_score(model, X_scaled, y, cv=tscv, scoring='roc_auc')
logger.info(f"SignalFilter retrained. CV AUC: {auc_scores.mean():.3f} ± {auc_scores.std():.3f}")

# Entrenar modelo final sobre todos los datos
model.fit(X_scaled, y)
```

---

## WD-08: Postmortem estadístico usa historial de la DB, no reanaliza precios

**Decisión**: El contexto estadístico que se inyecta al prompt del postmortem viene de `get_closed_trades_by_symbol()` en DB, no de re-fetch de precios históricos.

**Por qué**: Re-fetchear precios históricos al cierre de cada trade añade latencia (request IBKR), puede fallar si el mercado está cerrado, y duplica datos que ya están en la DB. Los trades cerrados tienen toda la información necesaria: `pnl_pct`, `exit_reason`, `stop_loss_pct`, `signal_strength`.

**Contexto que se inyecta**:
```python
stats = {
    "win_rate_last_10": wins / total,
    "avg_pnl_wins": mean(pnl for wins),
    "avg_pnl_losses": mean(pnl for losses),
    "sl_hit_rate": sl_exits / total,
    "tp_hit_rate": tp_exits / total,
    "most_common_exit_reason": mode(exit_reasons),
}
```

---

## WD-09: No modificar `app/risk/` — integración unidireccional

**Decisión**: Este módulo NO toca ningún archivo en `app/risk/` (circuit_breaker, trailing_stop, partial_exit, dynamic_sizing, validator).

**Por qué**: El módulo de riesgo es el componente más crítico del sistema — una regresión aquí puede resultar en pérdidas reales. El learning engine consume `symbol_parameters` (que el risk module también lee), pero no modifica la lógica de riesgo directamente.

**Integración**: `symbol_parameters.stop_loss_pct` y `take_profit_pct` son leídos por el risk module cuando se abre una orden. Al calibrarlos desde el backtest, el efecto llega al risk module de forma indirecta sin modificar su código.
