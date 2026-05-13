# Constraints: mtf-learning-engine

**Module**: mtf-learning-engine
**Phase**: Phase 1 — Architecture
**Status**: complete
**Date**: 2026-05-13

---

## Constraints de Módulo (descubiertos en arqueología)

### C-01: Dos rutas de señal — NO fusionar sin plan
El sistema tiene `preprocessor.py` (scanner) y `pipeline.py` (análisis profundo) como rutas separadas. **No fusionarlas** — tienen propósitos diferentes y ciclos de vida distintos. Las mejoras deben aplicarse a cada una respetando su rol.

### C-02: Tests de scorer deben actualizarse con los bugs corregidos
`tests/analysis/test_scorer.py` tiene tests que verifican el comportamiento ACTUAL incorrecto:
```python
def test_dim_volatility_high():
    f = _make_features(atr_pct=5.0)
    assert _dim_volatility(f) == 1.0  # ← Este test FALLARÁ tras el fix
```
Al corregir `_dim_volatility()`, estos tests deben actualizarse simultáneamente o el CI se romperá.

### C-03: `test_multitimeframe.py` importa desde `scanner.preprocessor`, no desde `analysis.indicators`
```python
from app.scanner.preprocessor import classify_signal, classify_multitimeframe
```
Ambas funciones fueron migradas a `analysis.indicators` pero re-exportadas desde `preprocessor` para backwards compat. No mover la fuente sin actualizar el test.

### C-04: `_fetch_bars()` en preprocessor usa `useRTH=True` hardcodeado
Para futuros y crypto, `useRTH` debe ser `False`. Cambiar a `get_use_rth(sec_type)` del `contract_factory`.

### C-05: Rate limit de IBKR — máx ~50 requests/10min
Con 40 símbolos activos y análisis multi-TF (4 requests por símbolo: daily, hourly, 5min, weekly), el scan completo necesita 160 requests. Si el scan corre cada 15 min, eso es 160/15min = OK. Pero si se solicitan datos adicionales para backtest calibration simultáneamente, puede superar el límite. Los requests de calibración deben encolarse con delay.

### C-06: `feature_snapshots` no tiene columnas para features horarias
Para agregar `rsi_1h` y `volume_ratio_1h`, se necesita migración:
```python
_add_column_if_missing(conn, "feature_snapshots", "rsi_1h", "REAL")
_add_column_if_missing(conn, "feature_snapshots", "volume_ratio_1h", "REAL")
_add_column_if_missing(conn, "feature_snapshots", "weekly_trend", "TEXT")
```
Usar `_add_column_if_missing()` que ya existe — nunca `ALTER TABLE` directo.

### C-07: `trades` no tiene `feature_snapshot_id` — migración requerida
```python
_add_column_if_missing(conn, "trades", "feature_snapshot_id", "INTEGER")
```
Sin este campo, el retrain del SignalFilter no puede cargar features reales. Es el fix más crítico del módulo.

### C-08: El modelo pkl del SignalFilter se guarda en `models/` relativo al CWD
```python
MODEL_PATH = "models/signal_filter.pkl"
```
En Raspberry Pi, el CWD debe ser consistente o el modelo no se encuentra. Verificar que el path es absoluto en producción o usar `Path(__file__).parent.parent / "models"`.

### C-09: `symbol_parameters` no tiene campo `backtest_calibrated`
Para saber si un símbolo ya fue calibrado por backtest (vs usa defaults genéricos), agregar:
```python
_add_column_if_missing(conn, "symbol_parameters", "backtest_calibrated", "INTEGER DEFAULT 0")
_add_column_if_missing(conn, "symbol_parameters", "backtest_calibrated_at", "TEXT")
```

### C-10: Preprocessor ignora `symbol_meta.sec_type` al construir el contrato
```python
# ACTUAL (bug):
contract = Stock(symbol, "SMART", "USD")

# CORRECTO:
contract = build_contract(
    symbol,
    meta.get("sec_type", "STK"),
    meta.get("exchange", "SMART"),
    meta.get("currency", "USD")
)
```
`build_contract()` ya existe en `app/ibkr/contract_factory.py` — solo hay que usarlo.

---

## Constraints Técnicos Globales (del proyecto)

- Python 3.11+, Raspberry Pi ARM — no dependencias pesadas sin verificar compatibilidad ARM
- SQLite — sin ORM, sin migraciones Alembic — solo SQL crudo con `IF NOT EXISTS`
- scikit-learn instalado (confirmado por `import sklearn` en tests)
- XGBoost: no confirmado — cualquier uso debe tener try/except fallback a LogisticRegression
- ib_insync event loop: no hacer requests síncronos desde threads de APScheduler sin usar `run_coroutine_threadsafe`
- paper trading activo: los cambios no deben modificar la lógica de ejecución de órdenes

---

## Constraints de Performance

- Scan de 40 símbolos cada 15min: presupuesto de ~22s por símbolo (15min/40 = 22.5s)
- Pipeline de análisis profundo tiene watchdog de 10min total (`TOTAL_TIMEOUT = 600`)
- Fetch weekly con caché TTL=3600s: solo 1 request por símbolo por hora — aceptable
- SignalFilter.retrain(): debe correr en background thread, no bloquear el scanner
- Backtest calibration: correr en background con delay de 2s entre símbolos para respetar rate limit

---

## Dependencias del Módulo

| Módulo | Tipo | Descripción |
|--------|------|-------------|
| `app/ibkr/contract_factory.py` | Produce para nosotros | `build_contract()`, `get_use_rth()` |
| `app/analysis/data.py` | Produce para nosotros | `IBDataLayer.get_ohlcv()` con caché |
| `app/db/database.py` | Produce para nosotros | Todas las funciones de acceso a datos |
| `app/notifications/telegram.py` | Produce para nosotros | `notify()` para alertas |
| `app/positions/manager.py` | Consume nuestro output | Llama `run_postmortem()` al cerrar trades |
| `app/llm/loop.py` | Consume nuestro output | Usa `SignalFilter.predict()` y `compute_score()` |
| `app/risk/dynamic_sizing.py` | Consume nuestro output | Usa `win_rate` de historial y `symbol_parameters` |
