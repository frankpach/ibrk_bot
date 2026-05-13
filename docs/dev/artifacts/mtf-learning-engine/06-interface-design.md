# Interface Design: mtf-learning-engine

**Module**: mtf-learning-engine
**Phase**: Phase 2 — Design
**Status**: complete
**Date**: 2026-05-13
**Chosen Alternative**: B — User-First: Observable Learning Pipeline

---

## Alternativa Elegida: B — Observable Learning Pipeline

**Por qué B**: Los fixes quirúrgicos de A son correctos, pero sin observabilidad Frank no sabe si el sistema está aprendiendo. La alternativa C es prematura — DI injection en todo el codebase para un sistema que hoy tiene un solo desarrollador y una sola instancia. B da el punto de coordinación central y las métricas sin agregar complejidad innecesaria.

---

## Interfaz Primaria

El módulo expone **tres puntos de entrada principales** que los callers existentes pueden invocar sin cambiar sus firmas:

### 1. `run_learning_cycle(data_layer)` — `app/ml/cycle.py`
El coordinador del aprendizaje. Se llama una vez al día desde el scheduler. Encadena: evaluación de returns → retrain del SignalFilter → rollback de parámetros deteriorados → reporte de métricas.

```python
@dataclass
class LearningReport:
    date: str
    signal_filter_auc: float | None      # AUC del modelo reentrenado. None si sin cambios.
    samples_used: int                     # Trades usados en retrain
    symbols_rolled_back: list[str]        # Símbolos que revirtieron parámetros
    win_rates: dict[str, float]           # {symbol: win_rate_last_10}
    params_changed: dict[str, list[str]]  # {symbol: [dimensiones cambiadas]}
    errors: list[str]                     # Errores no fatales durante el ciclo

def run_learning_cycle(data_layer) -> LearningReport:
    ...
```

### 2. `on_symbol_approved(symbol, ib_client)` — `app/ml/calibration.py`
Disparado desde `approve_symbol()` en database.py. Corre backtest en background y escribe SL/TP óptimos a `symbol_parameters`. No bloquea.

```python
def on_symbol_approved(symbol: str, ib_client) -> None:
    """Lanza calibración de backtest en thread background."""
    threading.Thread(
        target=_run_calibration_safe,
        args=(symbol, ib_client),
        daemon=True
    ).start()

def _run_calibration_safe(symbol: str, ib_client) -> None:
    """Grid search SL/TP + escribe a symbol_parameters."""
    ...
```

### 3. `enrich_postmortem_context(symbol)` — `app/ml/postmortem_stats.py`
Llamado desde `run_postmortem()` en postmortem.py antes del LLM. Retorna estadísticas reales del símbolo desde DB.

```python
@dataclass
class PostmortemContext:
    win_rate_last_10: float
    avg_pnl_wins_pct: float
    avg_pnl_losses_pct: float
    sl_hit_rate: float
    tp_hit_rate: float
    most_common_exit: str
    patterns_last_3: list[str]     # Últimos 3 patrones de la tabla patterns

def enrich_postmortem_context(symbol: str) -> PostmortemContext | None:
    """None si hay < 3 trades cerrados del símbolo."""
    ...
```

---

## Flujos Clave

### Flujo 1: Señal multi-timeframe con filtro macro (Scanner — cada 15min)

```
preprocessor.scan_symbol(symbol, ib_client, symbol_meta)
  │
  ├── build_contract(symbol, sec_type, exchange, currency)  ← FIX: usa symbol_meta
  │
  ├── _fetch_bars(daily, "30 D", "1 day")
  ├── _fetch_bars(hourly, "5 D", "1 hour")
  ├── _fetch_bars(5min, "1 D", "5 mins")
  ├── _fetch_bars(weekly, "1 Y", "1 week")  ← NUEVO
  │
  ├── classify_signal(daily) → sig_daily
  ├── classify_signal(hourly) → sig_hourly
  ├── classify_signal(5min) → sig_5min
  ├── _weekly_trend_filter(weekly_df) → weekly_trend  ← NUEVO: "BULLISH"/"BEARISH"/"NEUTRAL"
  │
  ├── strength = classify_multitimeframe(sig_daily, sig_hourly, sig_5min)  ← ya existe
  │
  ├── [NUEVO] si weekly_trend == "BEARISH" y strength == "STRONG":
  │     strength = "MEDIUM"   # veto parcial de tendencia macro
  │
  └── insert_signal(strength, extra_indicators={"weekly_trend": weekly_trend, ...})
```

**Contrato de `_weekly_trend_filter(df_weekly)`**:
- Retorna `"BULLISH"` si close > SMA20 semanal y SMA20w > SMA50w
- Retorna `"BEARISH"` si close < SMA20 semanal y SMA20w < SMA50w
- Retorna `"NEUTRAL"` en caso intermedio
- Si `df_weekly` es None o vacío → retorna `"NEUTRAL"` (fallback graceful)

---

### Flujo 2: Análisis profundo con features multi-TF (Pipeline — on demand)

```
AnalysisPipeline.run()
  │
  ├── get_ohlcv(daily, "180 D", "1 day")    ← ya existe
  ├── get_ohlcv(hourly, "5 D", "1 hour")    ← ya se fetcha, FIX: ahora se USA
  ├── get_ohlcv(weekly, "1 Y", "1 week")    ← NUEVO
  │
  ├── compute_features(symbol, df_daily, df_hourly)  ← FIX: df_hourly ya no se ignora
  │     → FeatureSet con:
  │         rsi_14 (daily)     ← ya existe
  │         macd_line (daily)  ← ya existe
  │         rsi_1h             ← NUEVO: desde df_hourly
  │         volume_ratio_1h    ← NUEVO: desde df_hourly
  │         weekly_trend       ← NUEVO: "BULLISH"/"BEARISH"/"NEUTRAL"
  │
  ├── SignalFilter.predict(features) → P(win)  ← FIX: modelo real, no heurístico
  │
  ├── compute_score(features, symbol, portfolio)
  │     → QuantScore con:
  │         _dim_volatility()    ← FIX: ATR moderado = score alto
  │         _dim_price_change()  ← FIX: BUY quiere precio positivo reciente
  │         weekly_trend_veto    ← NUEVO: si BEARISH, recommendation no puede ser PRIORITY
  │
  └── LLM analysis con contexto enriquecido
```

**Contrato de cambios en `compute_features()`**:
```python
def compute_features(
    symbol: str,
    df_daily: pd.DataFrame,
    df_hourly: pd.DataFrame | None = None,   # ACTIVADO: antes ignorado
    df_5min: pd.DataFrame | None = None,
    df_weekly: pd.DataFrame | None = None,   # NUEVO parámetro
    hv_series=None, iv_series=None,
    spy_df=None, qqq_df=None,
) -> FeatureSet:
```

Nuevos campos en `FeatureSet`:
```python
rsi_1h: Optional[float] = None           # RSI 14 en timeframe horario
volume_ratio_1h: Optional[float] = None  # Volumen última hora vs media
weekly_trend: Optional[str] = None       # "BULLISH" | "BEARISH" | "NEUTRAL"
```

---

### Flujo 3: Retrain del SignalFilter (ciclo de aprendizaje diario)

```
run_learning_cycle(data_layer)  ← llamado desde APScheduler diario
  │
  ├── run_return_evaluator(data_layer)    ← ya existe, calcula future_return_7d/30d
  │
  ├── trades = get_closed_trades_with_snapshots()  ← NUEVO: JOIN trades + feature_snapshots
  │
  ├── if len(trades) >= 10:
  │     auc = SignalFilter.retrain(trades)   ← FIX: carga features desde DB, no trade.features
  │     log + notify Telegram
  │
  ├── for symbol in get_active_symbols():
  │     maybe_rollback_parameters(symbol)   ← NUEVO: revierte si win_rate < 30%
  │
  ├── report = LearningReport(auc, win_rates, params_changed, ...)
  │
  └── notify Telegram(reporte_semanal)  ← solo los lunes o cuando AUC cambia >0.05
```

**Contrato del fix en `SignalFilter.retrain()`**:
```python
def retrain(self, trades: list[Trade]) -> float | None:
    """
    Retorna AUC del modelo en TimeSeriesSplit, o None si hay < 10 muestras.
    Carga features desde feature_snapshots en DB vía trade.feature_snapshot_id.
    """
    from app.db.database import get_feature_snapshot_by_id
    X, y = [], []
    for trade in trades:
        if not trade.feature_snapshot_id:
            continue
        snapshot = get_feature_snapshot_by_id(trade.feature_snapshot_id)
        if snapshot is None:
            continue
        X.append(self._extract_features(snapshot))
        y.append(1 if (trade.pnl_pct or 0) > 0 else 0)
    ...
    # TimeSeriesSplit para AUC
    # Entrenar modelo final sobre todos los datos
    # Retornar AUC del último fold
```

---

### Flujo 4: Calibración de símbolo nuevo (backtest → parámetros)

```
approve_symbol(symbol)   ← en database.py (ya existe)
  │
  └── on_symbol_approved(symbol, ib_client)   ← NUEVO hook post-aprobación
        │
        └── thread: _run_calibration_safe(symbol, ib_client)
              │
              ├── for sl_pct in [0.02, 0.025, 0.03, 0.035]:
              │   for tp_pct in [0.04, 0.05, 0.06, 0.07, 0.08]:
              │     result = run_backtest(symbol, ib_client, sl_pct, tp_pct, 180D)
              │
              ├── best = max(results, key=lambda r: r.profit_factor)
              │          if r.total_trades >= 5  # Mínimo para ser válido
              │
              ├── update_symbol_parameters(symbol,
              │     stop_loss_pct=best.sl_pct,
              │     take_profit_pct=best.tp_pct,
              │     backtest_calibrated=1,
              │     backtest_calibrated_at=now)
              │
              └── notify Telegram(f"{symbol} calibrado: SL={best.sl_pct} TP={best.tp_pct}")
```

---

### Flujo 5: Postmortem enriquecido

```
run_postmortem(trade)   ← en postmortem.py, llamado desde positions/manager.py
  │
  ├── ctx = enrich_postmortem_context(trade.symbol)   ← NUEVO: estadísticas reales
  │
  ├── prompt = build_prompt(trade, ctx)
  │     → incluye: win_rate_last_10, sl_hit_rate, patrones previos del símbolo
  │
  ├── response = _call_opencode(prompt)
  │
  ├── insert_pattern(pattern_text)   ← ya existe
  │
  └── update_weights_attenuated(...)  ← ya existe
```

---

## Componentes a Construir

| Componente | Archivo | Tipo | Tamaño estimado |
|-----------|---------|------|-----------------|
| `run_learning_cycle()` + `LearningReport` | `app/ml/cycle.py` | Nuevo | ~100 líneas |
| `on_symbol_approved()` + `_run_calibration_safe()` | `app/ml/calibration.py` | Nuevo | ~80 líneas |
| `enrich_postmortem_context()` + `PostmortemContext` | `app/ml/postmortem_stats.py` | Nuevo | ~60 líneas |
| `_weekly_trend_filter()` | `app/scanner/preprocessor.py` | Nuevo en existente | ~20 líneas |
| `get_feature_snapshot_by_id()` | `app/db/database.py` | Nuevo en existente | ~10 líneas |
| `get_closed_trades_with_snapshots()` | `app/db/database.py` | Nuevo en existente | ~15 líneas |

---

## Componentes a Modificar (Fixes)

| Componente | Archivo | Cambio |
|-----------|---------|--------|
| `SignalFilter.retrain()` | `app/ml/signal_filter.py` | Cargar features desde DB vía snapshot_id |
| `compute_features()` | `app/analysis/indicators.py` | Activar df_hourly + agregar df_weekly |
| `FeatureSet` | `app/analysis/indicators.py` | +rsi_1h, +volume_ratio_1h, +weekly_trend |
| `_dim_volatility()` | `app/analysis/scorer.py` | Invertir escala: ATR moderado = score alto |
| `_dim_price_change()` | `app/analysis/scorer.py` | Agregar dirección BUY/SELL |
| `scan_symbol()` | `app/scanner/preprocessor.py` | Usar build_contract() + weekly filter |
| `run_postmortem()` | `app/llm/postmortem.py` | Llamar enrich_postmortem_context() antes del LLM |
| `init_analysis_tables()` | `app/db/database.py` | Migrar: feature_snapshot_id en trades, backtest_calibrated en symbol_parameters, rsi_1h en feature_snapshots |
| `run_backtest()` | `app/backtest/engine.py` | Parametrizar sl_pct y tp_pct para grid search |
| Tests de scorer | `tests/analysis/test_scorer.py` | Actualizar tests de volatility y price_change |

---

## Migración de DB requerida

```python
# En init_analysis_tables() — usar _add_column_if_missing() existente:
_add_column_if_missing(conn, "trades", "feature_snapshot_id", "INTEGER")
_add_column_if_missing(conn, "symbol_parameters", "backtest_calibrated", "INTEGER DEFAULT 0")
_add_column_if_missing(conn, "symbol_parameters", "backtest_calibrated_at", "TEXT")
_add_column_if_missing(conn, "feature_snapshots", "rsi_1h", "REAL")
_add_column_if_missing(conn, "feature_snapshots", "volume_ratio_1h", "REAL")
_add_column_if_missing(conn, "feature_snapshots", "weekly_trend", "TEXT")
```

---

## Trade-offs de esta Alternativa

**Optimizamos por**:
- Mínima superficie de cambio en callers existentes — ninguno cambia su firma
- Observabilidad real para Frank (AUC, win rates, rollbacks) sin UI web
- Fallback graceful en cada punto — si weekly falla, la señal usa solo daily+hourly+5min

**Sacrificamos**:
- DI injection limpia (la alternativa C sería más testeable con mocks)
- `run_learning_cycle()` en `cycle.py` llama funciones importadas directamente, no inyectadas

**Por qué es el trade-off correcto**:
Un sistema con un desarrollador y una instancia en producción no necesita DI. Lo que necesita es no romper nada y poder ver si funciona. B da ambas cosas con el mínimo de complejidad nueva.

---

## Preguntas Abiertas Resueltas por este Diseño

| Pregunta | Resolución |
|----------|-----------|
| ¿Weekly como dimensión o como veto? | Veto parcial en preprocessor (STRONG→MEDIUM) + feature en SignalFilter |
| ¿Retrain cada vez o batched? | Batched en `run_learning_cycle()` diario. No en cada postmortem individual. |
| ¿Calibración bloquea aprobación? | No. Thread background con notify Telegram al terminar. |
| ¿Rollback notifica por Telegram? | Sí — `maybe_rollback_parameters()` llama `notify()` siempre que revierte. |
| ¿Cuántos días de histórico para backtest? | 180 días (ya en el engine). Grid 4×5 = 20 combinaciones por símbolo. |
