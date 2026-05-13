# Architecture Map: mtf-learning-engine

**Module**: mtf-learning-engine
**Phase**: Phase 1 — Architecture
**Status**: complete
**Date**: 2026-05-13
**Previous artifact**: docs/dev/artifacts/mtf-learning-engine/02-persona-journey.md
**Next artifact**: docs/dev/artifacts/mtf-learning-engine/04-constraints.md

---

## Executive Summary

La exploración del codebase revela **dos hallazgos críticos que redefinen el alcance**:

1. **Positivo**: `classify_multitimeframe(daily, hourly, 5min)` YA SE LLAMA en `preprocessor.py`. El multi-TF daily+hourly+5min para equities ya funciona en el scanner.

2. **Problema real**: El preprocessor hardcodea `Stock(symbol, "SMART", "USD")` — no funciona para futuros, forex ni crypto. Y no hay timeframe semanal en ningún lugar.

El sistema tiene **DOS rutas de análisis separadas** con lógica diferente. Este es el problema de arquitectura central.

---

## Las Dos Rutas de Señal (Divergencia Arquitectural)

```
RUTA 1: Scanner (preprocessor.py) — cada 15 min
─────────────────────────────────────────────────
  _fetch_bars(daily) → classify_signal()
  _fetch_bars(hourly) → classify_signal()
  _fetch_bars(5min)  → classify_signal()
  classify_multitimeframe(d, h, 5m) → strength
  insert_signal(strength) → DB
  
  ✅ Multi-TF: SÍ (daily+hourly+5min)
  ❌ Asset classes: Solo STK (hardcodeado a Stock())
  ❌ Weekly filter: NO existe
  ❌ QuantScorer: NO se llama aquí
  ❌ SignalFilter: NO se llama aquí

RUTA 2: Pipeline (pipeline.py) — on demand (cuando hay señal)
──────────────────────────────────────────────────────────────
  get_ohlcv(daily, 180D) → compute_features() → FeatureSet
  get_ohlcv(hourly, 5D)  → compute_features() [IGNORADO]
  compute_score(features, symbol) → QuantScore
  SignalFilter.predict(features) → P(win)
  LLM analysis → LLMDecision
  
  ❌ Multi-TF: NO (hourly se fetcha pero se ignora)
  ❌ Asset classes: Solo STK implícitamente
  ❌ Weekly filter: NO existe
  ✅ QuantScorer: SÍ
  ✅ SignalFilter: SÍ (pero con modelo heurístico por el bug)
```

**Implicación**: El scanner genera señales con multi-TF correcto, pero el pipeline de análisis profundo (QuantScorer + LLM) trabaja solo con features daily. Las dos rutas deben converger.

---

## Modelos y Datos Existentes

### Tablas SQLite — Estado actual

| Tabla | Propósito | Gap identificado |
|-------|-----------|-----------------|
| `trades` | Historial de trades | **NO tiene `feature_snapshot_id`** — falta el link para retrain |
| `feature_snapshots` | Features técnicas al momento del análisis | Existe y se popula ✅ |
| `candidate_decisions` | Decisiones candidatas con `feature_snapshot_id` | Tiene FK a feature_snapshot ✅ pero no a trade |
| `symbol_parameters` | Parámetros por símbolo | Existe, funciona. Le falta columna `backtest_calibrated BOOL` |
| `patterns` | Patrones aprendidos del postmortem | Existe pero **nada la consume** para decisiones |
| `symbol_config` | Símbolos aprobados con `sec_type`, `exchange` | Tiene metadata completa para todos los asset classes ✅ |

### Función crítica ausente

```python
# NO EXISTE en database.py — necesaria para fix del retrain:
def get_feature_snapshot_for_trade(trade_id: int) -> dict | None:
    # Requiere agregar feature_snapshot_id a trades table
```

### Función de migración segura (reutilizable)

```python
# YA EXISTE en database.py:75 — usar para toda migración nueva
def _add_column_if_missing(conn, table: str, column: str, ddl: str) -> None:
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    except Exception as exc:
        if "duplicate column name" not in str(exc).lower():
            raise
```

---

## Componentes Existentes — Inventario Real

### app/scanner/preprocessor.py — `scan_symbol()`
**Estado**: Funcional, pero incompleto.
- ✅ YA llama `classify_multitimeframe(sig_daily, sig_hourly, sig_5min)`
- ✅ YA fetcha daily + hourly + 5min via `_fetch_bars()`
- ❌ Hardcodea `Stock(symbol, "SMART", "USD")` — no multi-market
- ❌ No fetcha weekly para filtro macro
- ❌ `symbol_meta` recibido pero ignorado en la construcción del contrato

### app/analysis/pipeline.py — `AnalysisPipeline`
**Estado**: Funcional, datos parciales.
- ✅ Fetcha `df_daily` (180D) y `df_hourly` (5D/1h)
- ✅ Llama `compute_features(symbol, df_daily, df_hourly, ...)` con hourly
- ❌ `compute_features()` ignora `df_hourly` — el parámetro existe pero no se usa
- ❌ No fetcha `df_weekly`
- ❌ No usa `classify_multitimeframe()`

### app/analysis/indicators.py — `compute_features()`
**Estado**: Parcialmente implementado.
- ✅ Firma acepta `df_hourly`, `df_5min`, `df_weekly` (aunque df_weekly no está declarado)
- ❌ Solo calcula indicadores desde `df_daily` — hourly y 5min ignorados
- ✅ `classify_multitimeframe()` existe y funciona (testado)
- ✅ `classify_signal_v2()` existe (criterio mejorado con más condiciones)

### app/analysis/scorer.py — `compute_score()`
**Estado**: Funcional con 2 bugs de diseño.
- ✅ Pesos adaptativos por símbolo via `_get_multipliers()`
- ✅ `update_weights_attenuated()` funciona correctamente
- ❌ `_dim_volatility()`: ATR alto = score alto (INVERTIDO — confirmed by tests)
- ❌ `_dim_price_change()`: usa `abs()` — pierde dirección

### app/ml/signal_filter.py — `SignalFilter`
**Estado**: Funcional en heurístico. ML nunca entrenó.
- ✅ Arquitectura correcta, singleton, caché de modelo pkl
- ✅ Tests comprensivos en `tests/ml/test_signal_filter.py`
- ❌ `retrain()`: busca `trade.features` — campo no existe en `Trade` dataclass
- ❌ No hay `feature_snapshot_id` en `trades` para cargar features reales
- ❌ Sin `TimeSeriesSplit` — data leakage en entrenamiento futuro

### app/backtest/engine.py — `run_backtest()`
**Estado**: Funcional como simulador. Sin pipeline de calibración.
- ✅ Simula trades con señales diarias, calcula métricas
- ✅ `BacktestResult` contiene win_rate, profit_factor, optimal SL/TP implícito
- ❌ Hardcodea `Stock(symbol, "SMART", "USD")` — solo equities
- ❌ No escribe resultados a `symbol_parameters`
- ❌ No tiene grid search de SL/TP

### app/llm/postmortem.py — `run_postmortem()`
**Estado**: Funcional. Sin contexto estadístico.
- ✅ Llama LLM via OpenCode subprocess
- ✅ Aplica ajustes via `update_weights_attenuated()`
- ❌ No tiene estadísticas reales de win_rate, exit_reasons históricos del símbolo
- ❌ Tabla `patterns` se llena pero nada la consume en decisiones futuras

### app/analysis/evaluator.py — `run_return_evaluator()`
**Estado**: Funcional. Sin loop cerrado.
- ✅ Calcula `future_return_7d/30d` y `alpha_vs_spy` correctamente
- ✅ Actualiza `candidate_decisions` en DB
- ❌ **Nunca llama `SignalFilter.retrain()`** después de evaluar

---

## Tests Existentes (Reutilizables)

| Archivo | Cubre | Estado |
|---------|-------|--------|
| `tests/ml/test_signal_filter.py` | SignalFilter completo | ✅ Comprensivo — 12 tests |
| `tests/test_multitimeframe.py` | classify_multitimeframe | ✅ Existe — importa desde preprocessor |
| `tests/analysis/test_scorer.py` | compute_score, _dim_* | ✅ Comprensivo — confirma bugs actuales |
| `tests/test_backtest_engine.py` | BacktestEngine | ✅ Existe |
| `tests/llm/test_postmortem_extended.py` | Postmortem | ✅ Existe |
| `tests/analysis/test_pipeline.py` | AnalysisPipeline | ✅ Existe |

**Importante**: `test_scorer.py` confirma el comportamiento ACTUAL (incorrecto) de `_dim_volatility`. Al corregir el bug, los tests deben actualizarse para reflejar el nuevo comportamiento correcto.

---

## Gaps Identificados — Qué Construir

### GAP-01: Link trades → feature_snapshots (CRÍTICO para retrain)
`trades` no tiene `feature_snapshot_id`. Sin este link, el retrain no puede cargar features.
- **Acción**: `ALTER TABLE trades ADD COLUMN feature_snapshot_id INTEGER` via `_add_column_if_missing()`
- **Acción**: Agregar `get_feature_snapshot_by_id(snapshot_id)` en database.py
- **Acción**: Corregir `retrain()` para cargar desde DB en lugar de `trade.features`

### GAP-02: Weekly timeframe — ausente en todo el sistema
Ningún componente fetcha datos semanales.
- **Acción**: Agregar `df_weekly = get_ohlcv(symbol, "1 Y", "1 week", "scanner")` en preprocessor y pipeline
- **Acción**: Agregar `_dim_trend_macro(df_weekly)` al QuantScorer
- **Acción**: Usar weekly trend como filtro en preprocessor (no como señal, como veto)

### GAP-03: Preprocessor hardcodeado a STK
`scan_symbol()` usa `Stock(symbol, "SMART", "USD")` ignorando `symbol_meta`.
- **Acción**: Usar `build_contract(symbol, sec_type, exchange, currency)` desde `symbol_meta`
- **Acción**: El `symbol_meta` ya se recibe como parámetro — solo usar su contenido
- **Acción**: Ajustar `useRTH` según asset class (False para futuros/crypto)

### GAP-04: compute_features() ignora df_hourly
El parámetro existe pero el cuerpo de la función no lo usa.
- **Acción**: Calcular `rsi_1h`, `macd_1h`, `volume_ratio_1h` desde `df_hourly`
- **Acción**: Agregar campos a `FeatureSet`: `rsi_1h`, `volume_ratio_1h`
- **Acción**: Agregar campos a `feature_snapshots` tabla

### GAP-05: Pipeline usa classify_signal, debería usar result de preprocessor
El pipeline recalcula la señal de forma independiente al scanner. Redundancia.
- **Acción**: La señal multi-TF del scanner (guardada en `extra_indicators` JSON) debería pasarse al pipeline
- **Acción**: Pipeline usa esa señal como contexto, no recalcula

### GAP-06: Backtest → symbol_parameters no conectado
- **Acción**: `run_backtest_calibration(symbol)` que corre grid de SL/TP y escribe mejor resultado
- **Acción**: Hook en `approve_symbol()` para disparar calibración

### GAP-07: ReturnEvaluator → retrain no conectado
- **Acción**: Al final de `run_return_evaluator()`, si hay N nuevos registros evaluados, llamar `SignalFilter.retrain()`

### GAP-08: Patrones no consumidos
- **Acción**: En el prompt del postmortem y del análisis LLM, incluir patrones previos del símbolo desde `get_patterns_for_symbol()`

---

## Reutilización — No Reinventar

| Necesidad | Usar existente |
|-----------|---------------|
| Migración columna DB | `_add_column_if_missing()` en database.py:75 |
| Construir contrato multi-market | `build_contract()` en app/ibkr/contract_factory.py |
| `useRTH` por asset class | `get_use_rth(sec_type)` en app/ibkr/contract_factory.py |
| Datos históricos cached | `IBDataLayer.get_ohlcv(symbol, duration, bar_size, context)` |
| Clasificar señal single-TF | `classify_signal()` en indicators.py — no duplicar |
| Combinar señales multi-TF | `classify_multitimeframe()` en indicators.py — ya existe y testado |
| Notificaciones Telegram | `notify()` en app/notifications/telegram.py |
| Symbol metadata (sec_type, etc.) | `get_approved_symbols_with_meta()` en database.py |

---

## Mapa de Dependencias

```
DB (SQLite)
  ├── symbol_config (sec_type, exchange, liquid_hours)
  ├── trades [NECESITA: feature_snapshot_id]
  ├── feature_snapshots
  ├── candidate_decisions (→feature_snapshot_id)
  ├── symbol_parameters (stop_loss_pct, *_mult)
  └── patterns

SCANNER (cada 15min)
  preprocessor.scan_symbol()
    ├── build_contract() [FIX: usar symbol_meta completo]
    ├── _fetch_bars(daily, hourly, 5min)
    ├── classify_signal() × 3
    ├── classify_multitimeframe() ✅ ya funciona
    ├── [ADD] _fetch_bars(weekly) → weekly_trend_filter
    └── insert_signal()

PIPELINE (on demand, por señal)
  AnalysisPipeline.run()
    ├── get_ohlcv(daily) ✅
    ├── get_ohlcv(hourly) ✅ [FIX: usar en compute_features]
    ├── [ADD] get_ohlcv(weekly) → trend_macro
    ├── compute_features(daily, hourly) [FIX: activar hourly]
    ├── SignalFilter.predict() [FIX: retrain bug]
    ├── compute_score() [FIX: volatility + price_change + ADD trend_macro]
    └── LLM analysis

LEARNING LOOP (por trade cerrado)
  close_trade()
    └── run_postmortem()
          ├── [ADD] estadísticas históricas del símbolo
          ├── [ADD] patrones previos del símbolo
          └── update_weights_attenuated()

RETURN EVALUATOR (diario)
  run_return_evaluator()
    ├── Calcula future_return_7d/30d ✅
    └── [ADD] → SignalFilter.retrain() si N nuevos registros

BACKTEST PIPELINE (al aprobar símbolo)
  approve_symbol()
    └── [ADD] run_backtest_calibration()
              └── update symbol_parameters(sl, tp)
```
