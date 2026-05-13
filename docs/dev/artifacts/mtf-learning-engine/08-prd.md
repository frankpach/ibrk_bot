# PRD: mtf-learning-engine

**Module**: mtf-learning-engine
**Phase**: Phase 3 — Requirements
**Status**: complete
**Date**: 2026-05-13
**Design**: Alternative B — Observable Learning Pipeline
**Timeline**: Iteración 1 (2026-05-20) + Iteración 2 (siguiente semana)

---

## Objetivo

Hacer funcional el motor de aprendizaje del IBKR AI Trader. El sistema tiene la infraestructura diseñada pero con bugs críticos, componentes desconectados y errores de diseño de señal. Este PRD define exactamente qué debe quedar funcionando al final del módulo.

---

## REQ-01: Fix retrain del SignalFilter (BUG CRÍTICO)

**Prioridad**: P0 — bloquea todo el aprendizaje ML  
**Iteración**: 1

### Problema
`SignalFilter.retrain()` busca `trade.features` — campo que no existe en el dataclass `Trade`. El dataset siempre está vacío. El sistema opera con el fallback heurístico desde su inicio.

### Solución
1. Agregar columna `feature_snapshot_id INTEGER` a la tabla `trades` vía `_add_column_if_missing()`
2. Al insertar un trade, vincular el `feature_snapshot_id` correspondiente
3. Agregar `get_feature_snapshot_by_id(snapshot_id: int) -> dict | None` en `database.py`
4. Reescribir `retrain()` para cargar features desde DB vía `trade.feature_snapshot_id`
5. Agregar `TimeSeriesSplit(n_splits=5)` para calcular AUC antes de entrenar el modelo final
6. Retornar el AUC del último fold (float) o None si hay < 10 muestras

### Acceptance Criteria
- [ ] **AC-01.1**: Con 10+ trades que tienen `feature_snapshot_id`, `retrain()` retorna un float AUC > 0
- [ ] **AC-01.2**: Con < 10 muestras, `retrain()` retorna `False` y logea warning
- [ ] **AC-01.3**: El modelo `.pkl` se actualiza en `models/signal_filter.pkl` tras retrain exitoso
- [ ] **AC-01.4**: `retrain()` usa `TimeSeriesSplit` — nunca mezcla datos futuros con pasados
- [ ] **AC-01.5**: Si `get_feature_snapshot_by_id()` falla, el trade se omite silenciosamente (no crashea retrain)

### Edge Cases
- Trade sin `feature_snapshot_id` (trades previos al fix): omitir sin error
- `feature_snapshots` con campos None: usar el default del `_extract_features()`
- Todos los trades son de la misma clase (todos wins o todos losses): loggear warning, no entrenar

---

## REQ-02: Corrección de _dim_volatility() (BUG de diseño)

**Prioridad**: P0 — produce señales incorrectas  
**Iteración**: 1

### Problema
`_dim_volatility()` retorna 1.0 para ATR >= 4% (alta volatilidad = señal máxima). Esto es incorrecto para una estrategia con SL fijo: alta volatilidad aumenta la probabilidad de activar el SL por ruido, no por tendencia real.

### Solución
Invertir la escala: ATR moderado (1.0-2.5%) = zona óptima. ATR extremo penaliza.

```python
def _dim_volatility(features) -> float:
    atr = features.atr_pct
    if atr is None: return 0.0
    if 1.0 <= atr <= 2.5: return 1.0   # Zona óptima
    if 0.5 <= atr < 1.0:  return 0.6   # Muy baja: poco movimiento
    if 2.5 < atr <= 4.0:  return 0.5   # Alta: riesgo de SL por ruido
    if atr > 4.0:          return 0.2   # Muy alta: señal débil
    return 0.3
```

**Actualizar tests simultáneamente**: `test_dim_volatility_high` (ATR=5.0) debe esperar 0.2, no 1.0.

### Acceptance Criteria
- [ ] **AC-02.1**: ATR = 1.5% → `_dim_volatility()` retorna 1.0
- [ ] **AC-02.2**: ATR = 5.0% → `_dim_volatility()` retorna 0.2
- [ ] **AC-02.3**: ATR = None → retorna 0.0
- [ ] **AC-02.4**: `compute_score()` con features de alta volatilidad produce score más bajo que con ATR moderado (ceteris paribus)
- [ ] **AC-02.5**: Tests en `test_scorer.py` pasan con los nuevos valores esperados

---

## REQ-03: Corrección de _dim_price_change() — dirección BUY/SELL

**Prioridad**: P1 — señales imprecisas  
**Iteración**: 1

### Problema
`_dim_price_change()` usa `abs(price_change_pct)` — un precio cayendo 5% y uno subiendo 5% producen el mismo score para un BUY. Un BUY en un activo con caída fuerte del día puede ser oportunidad o trampa, pero no es lo mismo que momentum positivo.

### Solución
La función necesita contexto de acción. Si la acción no se conoce en scoring (el scorer no sabe si va a ser BUY o SELL), usar una heurística conservadora: premio al momentum positivo leve, penalización a caídas fuertes (indicador de bear momentum).

```python
def _dim_price_change(features) -> float:
    pc = features.price_change_pct
    if pc is None: return 0.0
    # Momentum positivo moderado es ideal para entry
    if 1.0 <= pc <= 4.0:   return 0.9   # Upward momentum — bueno para BUY
    if 0.0 <= pc < 1.0:    return 0.6   # Neutral-positivo
    if -1.0 <= pc < 0.0:   return 0.4   # Leve corrección — puede ser pullback
    if -3.0 <= pc < -1.0:  return 0.2   # Caída moderada — señal de alerta
    if pc < -3.0:           return 0.1   # Colapso — posible bear trap
    if pc > 4.0:            return 0.7   # Fuerte momentum — atención overbought
    return 0.0
```

**Actualizar tests**: `test_dim_price_change_high` (pc=6.0) debe esperar 0.7, no 1.0.

### Acceptance Criteria
- [ ] **AC-03.1**: `price_change_pct = 2.0` → score 0.9
- [ ] **AC-03.2**: `price_change_pct = -4.0` → score 0.1
- [ ] **AC-03.3**: `price_change_pct = None` → score 0.0
- [ ] **AC-03.4**: Tests en `test_scorer.py` pasan

---

## REQ-04: Activar df_hourly en compute_features()

**Prioridad**: P1 — multi-TF parcialmente implementado  
**Iteración**: 1

### Problema
`compute_features()` acepta `df_hourly` como parámetro pero solo usa `df_daily`. El pipeline ya fetcha datos horarios y los descarta.

### Solución
Calcular `rsi_1h` y `volume_ratio_1h` desde `df_hourly` cuando está disponible. Agregar esos campos a `FeatureSet`.

Nuevos campos en `FeatureSet`:
```python
rsi_1h: Optional[float] = None
volume_ratio_1h: Optional[float] = None
weekly_trend: Optional[str] = None  # "BULLISH" | "BEARISH" | "NEUTRAL"
```

Nuevas columnas en `feature_snapshots` (via `_add_column_if_missing`):
```sql
rsi_1h REAL
volume_ratio_1h REAL
weekly_trend TEXT
```

### Acceptance Criteria
- [ ] **AC-04.1**: Con `df_hourly` válido, `features.rsi_1h` es un float entre 0 y 100
- [ ] **AC-04.2**: Con `df_hourly = None`, `features.rsi_1h` es None (no crashea)
- [ ] **AC-04.3**: `insert_feature_snapshot()` persiste `rsi_1h` y `volume_ratio_1h` en DB
- [ ] **AC-04.4**: `_extract_features()` del SignalFilter incluye `rsi_1h` y `volume_ratio_1h` (con defaults si None)

---

## REQ-05: Weekly trend filter en el scanner

**Prioridad**: P1 — mayor impacto en calidad de señales  
**Iteración**: 1

### Problema
El preprocessor no fetcha datos semanales. No hay filtro de tendencia macro. El scanner puede generar señales STRONG en activos en downtrend semanal claro.

### Solución

**`_weekly_trend_filter(df_weekly) -> str`** (nueva función en preprocessor.py):
- `"BULLISH"`: close > SMA20_semanal AND SMA20_semanal > SMA50_semanal
- `"BEARISH"`: close < SMA20_semanal AND SMA20_semanal < SMA50_semanal
- `"NEUTRAL"`: caso intermedio
- Si `df_weekly` es None o < 20 barras: retorna `"NEUTRAL"` (fallback graceful)

**Veto parcial en scan_symbol()**:
- Si `weekly_trend == "BEARISH"` y `strength == "STRONG"` → degradar a `"MEDIUM"`
- Si `weekly_trend == "BEARISH"` y `strength == "MEDIUM"` → degradar a `"WEAK"`
- Si `weekly_trend == "BULLISH"`: no modificar strength

**Fix multi-market**: usar `build_contract(symbol, sec_type, exchange, currency)` desde `symbol_meta` en lugar de `Stock(symbol, "SMART", "USD")` hardcodeado.

**useRTH por asset class**: usar `get_use_rth(sec_type)` del contract_factory.

### Acceptance Criteria
- [ ] **AC-05.1**: Con SMA20w > SMA50w y close > SMA20w → `_weekly_trend_filter()` retorna "BULLISH"
- [ ] **AC-05.2**: En downtrend semanal, una señal STRONG se degrada a MEDIUM
- [ ] **AC-05.3**: En downtrend semanal, una señal MEDIUM se degrada a WEAK
- [ ] **AC-05.4**: Si IBKR no devuelve datos semanales → el scan continúa con strength original (fallback graceful)
- [ ] **AC-05.5**: Futuros (ES, NQ) usan `useRTH=False` y `build_contract()` correcto
- [ ] **AC-05.6**: `extra_indicators` del Signal incluye `"weekly_trend"` como campo

### Edge Cases
- Rate limit de IBKR durante fetch semanal: timeout de 10s, fallback a "NEUTRAL"
- Símbolo sin suficiente historia semanal (crypto nuevo): fallback a "NEUTRAL"
- Crypto (24/7): fetch semanal sin useRTH

---

## REQ-06: Loop cerrado ReturnEvaluator → SignalFilter.retrain()

**Prioridad**: P1 — sin esto el ML nunca mejora  
**Iteración**: 1

### Problema
`run_return_evaluator()` calcula `future_return_7d/30d` y los guarda en `candidate_decisions` pero nunca dispara el reentrenamiento del SignalFilter.

### Solución
En `app/ml/cycle.py`, `run_learning_cycle()` encadena:
1. Llamar `run_return_evaluator(data_layer)` 
2. Obtener trades con feature_snapshot_id: `get_closed_trades_with_snapshots()`
3. Si len >= 10: llamar `SignalFilter.retrain(trades)` → loggear AUC
4. Para cada símbolo activo: verificar win_rate y rollback si < 30%
5. Construir y retornar `LearningReport`

`get_closed_trades_with_snapshots()` (nueva función en database.py):
```sql
SELECT t.*, fs.rsi_14, fs.macd_line, fs.atr_pct, fs.volume_ratio_20d,
       fs.bollinger_position, fs.rs_vs_spy_30d, fs.rsi_1h, fs.volume_ratio_1h
FROM trades t
JOIN feature_snapshots fs ON t.feature_snapshot_id = fs.id
WHERE t.status = 'CLOSED'
ORDER BY t.closed_at DESC
LIMIT 200
```

### Acceptance Criteria
- [ ] **AC-06.1**: `run_learning_cycle()` ejecuta sin excepción cuando hay 0 trades cerrados
- [ ] **AC-06.2**: Con 10+ trades con snapshots, `LearningReport.signal_filter_auc` es un float > 0
- [ ] **AC-06.3**: `LearningReport.win_rates` contiene un entry por cada símbolo con trades recientes
- [ ] **AC-06.4**: Si retrain falla, `LearningReport.errors` contiene la descripción — el ciclo no crashea
- [ ] **AC-06.5**: `run_learning_cycle()` se registra en el APScheduler con frecuencia diaria (17:00 ET)

---

## REQ-07: Rollback automático de symbol_parameters

**Prioridad**: P2  
**Iteración**: 1

### Problema
Si el postmortem LLM sugiere ajustes incorrectos y los últimos 5 trades de un símbolo son todos pérdidas, los parámetros se deterioran sin mecanismo de corrección automática.

### Solución
`maybe_rollback_parameters(symbol: str) -> bool` (en `cycle.py`):
1. Obtener últimos 5 trades cerrados del símbolo
2. Calcular win_rate_last_5
3. Si < 0.30 (menos de 2 wins en 5 trades) Y `previous_json` no es None:
   - Cargar `previous_json` y restaurar parámetros
   - Notificar por Telegram
   - Retornar True

### Acceptance Criteria
- [ ] **AC-07.1**: Win_rate últimos 5 trades < 30% + `previous_json` existe → parámetros revertidos
- [ ] **AC-07.2**: Rollback genera notificación Telegram: "AAPL revertió parámetros (win_rate: 20%)"
- [ ] **AC-07.3**: Con < 5 trades del símbolo → no hacer rollback (no hay suficientes datos)
- [ ] **AC-07.4**: Sin `previous_json` → no hacer rollback (no hay versión anterior)

---

## REQ-08: Backtest → symbol_parameters al aprobar símbolo

**Prioridad**: P2  
**Iteración**: 2

### Problema
Todo símbolo nuevo arranca con SL=2.5%, TP=6% genéricos. El backtest existe pero no alimenta los parámetros.

### Solución
`on_symbol_approved(symbol, ib_client)` en `app/ml/calibration.py`:
1. Lanzar thread background (daemon=True)
2. Grid search: SL en [0.02, 0.025, 0.03, 0.035], TP en [0.04, 0.05, 0.06, 0.07, 0.08]
3. Para cada combinación: `run_backtest(symbol, ib_client, sl, tp, period_days=180)`
4. Solo considerar resultados con `total_trades >= 5`
5. Elegir combinación con mayor `profit_factor`
6. Escribir a `symbol_parameters` con `backtest_calibrated=1`
7. Notificar por Telegram

### Acceptance Criteria
- [ ] **AC-08.1**: Al llamar `approve_symbol()`, `on_symbol_approved()` se dispara sin bloquear
- [ ] **AC-08.2**: Grid search prueba 4×5=20 combinaciones (con delay 2s entre requests)
- [ ] **AC-08.3**: Si ninguna combinación tiene >= 5 trades → usar defaults y loggear
- [ ] **AC-08.4**: `symbol_parameters.backtest_calibrated = 1` tras calibración exitosa
- [ ] **AC-08.5**: Notificación Telegram: "ES calibrado: SL=3.0%, TP=7.0% (profit_factor=1.8, 23 trades)"
- [ ] **AC-08.6**: Thread no bloquea el scanner ni el pipeline de trading

### Edge Cases
- IBKR no tiene historia suficiente para el símbolo (< 30 barras): usar defaults, notificar
- Rate limit durante grid search: sleep(2) entre requests, reintentar una vez
- Símbolo crypto sin datos históricos en IBKR: usar defaults silenciosamente

---

## REQ-09: Postmortem con contexto estadístico

**Prioridad**: P2  
**Iteración**: 2

### Problema
El LLM en el postmortem recibe solo el resultado del trade individual, sin contexto de si ese símbolo históricamente gana o pierde, ni en qué condiciones.

### Solución
`enrich_postmortem_context(symbol) -> PostmortemContext | None` en `app/ml/postmortem_stats.py`:
- Retorna None si hay < 3 trades cerrados del símbolo
- Calcula desde `trades` en DB: win_rate_last_10, avg_pnl_wins, avg_pnl_losses, sl_hit_rate, tp_hit_rate, most_common_exit
- Incluye últimos 3 patrones de la tabla `patterns` para ese símbolo

El prompt del postmortem incluye este contexto antes de pedir sugerencias al LLM.

### Acceptance Criteria
- [ ] **AC-09.1**: Con 5 trades de AAPL, `enrich_postmortem_context("AAPL")` retorna `PostmortemContext` con campos válidos
- [ ] **AC-09.2**: Con < 3 trades de AAPL → retorna None (no crashea `run_postmortem()`)
- [ ] **AC-09.3**: El prompt del LLM incluye las estadísticas del contexto cuando `PostmortemContext` no es None
- [ ] **AC-09.4**: `patterns_last_3` contiene máx 3 entradas; lista vacía si no hay patrones

---

## REQ-10: NS-003b — Telegram Commands + Digest Scheduler

**Prioridad**: P1  
**Iteración**: 1

### Problema
`NotificationPolicy` y `DigestGenerator` ya existen en `policy.py` pero los comandos `/notificaciones` y `/silencio` no están registrados en el bot Telegram, y el digest no tiene job en el scheduler.

### Solución
En `app/notifications/telegram_bot.py`:
- `cmd_notificaciones(update, context)`: parsea arg (critico/normal/verbose), llama `get_notification_policy().set_level(nivel)`
- `cmd_silencio(update, context)`: parsea horas (ej: `/silencio 2`), activa supresión por N horas
- Registrar ambos con `CommandHandler`

En `run.py`:
- Agregar job: `scheduler.add_job(_send_digest, "cron", hour="10,14", minute=0, timezone=MARKET_TZ)`
- `_send_digest()` llama `get_digest_generator().generate_digest(...)` y envía via `notify()`

### Acceptance Criteria
- [ ] **AC-10.1**: `/notificaciones critico` → bot responde confirmando el cambio de nivel
- [ ] **AC-10.2**: `/notificaciones verbose` → señales ignoradas SÍ generan notificación
- [ ] **AC-10.3**: `/silencio 2` → no-críticos suprimidos por 2h, luego restaurados
- [ ] **AC-10.4**: Digest enviado automáticamente a las 10:00 y 14:00 ET en días de mercado
- [ ] **AC-10.5**: Digest incluye: posiciones abiertas, P&L del día, señales procesadas en últimas 4h

---

## REQ-11: RE-004b — LMT Limit Price en _execute_order()

**Prioridad**: P1  
**Iteración**: 1

### Problema
`_execute_order()` en `loop.py` manda siempre `"limit_price": None`. Todas las entradas son efectivamente MKT aunque el cliente IBKR soporte LMT.

### Solución
En `_execute_order()`, calcular `limit_price` antes del preview:
```python
slippage = getattr(settings, 'ENTRY_SLIPPAGE_BUFFER', 0.005)
current_price = _get_current_price(symbol)
if decision.action == "BUY":
    limit_price = round(current_price * (1 + slippage), 2)
else:
    limit_price = round(current_price * (1 - slippage), 2)
```
Cierres (SL/TP) no cambian — siguen en MKT desde `_close_position()`.

### Acceptance Criteria
- [ ] **AC-11.1**: BUY a $215.00, buffer 0.5% → payload con `"order_type": "LMT"` y `"limit_price": 216.08`
- [ ] **AC-11.2**: SELL a $215.00, buffer 0.5% → `"limit_price": 213.92`
- [ ] **AC-11.3**: Preview en Telegram muestra "Order type: LMT @ $216.08"
- [ ] **AC-11.4**: Si `_get_current_price()` falla → fallback a MKT (no bloquear la orden)
- [ ] **AC-11.5**: Cierres de posición (SL/TP) siguen usando MKT sin cambios

---

## Migraciones de DB requeridas

Todas usando `_add_column_if_missing()` existente en `database.py`:

| Tabla | Columna | Tipo | Default | REQ |
|-------|---------|------|---------|-----|
| `trades` | `feature_snapshot_id` | INTEGER | NULL | REQ-01 |
| `symbol_parameters` | `backtest_calibrated` | INTEGER | 0 | REQ-08 |
| `symbol_parameters` | `backtest_calibrated_at` | TEXT | NULL | REQ-08 |
| `feature_snapshots` | `rsi_1h` | REAL | NULL | REQ-04 |
| `feature_snapshots` | `volume_ratio_1h` | REAL | NULL | REQ-04 |
| `feature_snapshots` | `weekly_trend` | TEXT | NULL | REQ-05 |

---

## Nuevos archivos

| Archivo | Propósito | REQ |
|---------|-----------|-----|
| `app/ml/cycle.py` | `run_learning_cycle()` + `LearningReport` | REQ-06, REQ-07 |
| `app/ml/calibration.py` | `on_symbol_approved()` + grid search | REQ-08 |
| `app/ml/postmortem_stats.py` | `enrich_postmortem_context()` + `PostmortemContext` | REQ-09 |

---

## Performance

| Operación | Límite | Medición |
|-----------|--------|----------|
| `scan_symbol()` con weekly fetch | < 30s por símbolo | Incluye caché TTL=3600s para weekly |
| `SignalFilter.predict()` | < 100ms | Sin cambio vs actual |
| `SignalFilter.retrain()` | < 10s | Con hasta 200 trades |
| `_run_calibration_safe()` grid search | < 5min total | 20 combos × 15s max cada uno |
| `run_learning_cycle()` | < 60s | Correr daily post-market |

---

## Seguridad y Confiabilidad

- **Fallback graceful obligatorio**: cada nuevo componente debe funcionar si falla (weekly, hourly, retrain, calibración)
- **No modificar módulo de riesgo**: `app/risk/` es intocable
- **Thread safety**: calibración en daemon thread, nunca bloquear el scanner
- **Rate limit IBKR**: delay de 2s entre requests en grid search, máx 40 requests en calibración
- **Modelo ML**: si el pkl está corrupto, `SignalFilter` cae al heurístico sin crashear
- **DB**: todas las migraciones son idempotentes via `_add_column_if_missing()`

---

## Orden de implementación (por riesgo)

### Iteración 1 — Esta semana (2026-05-20)

| Orden | REQ | Archivo principal | Riesgo |
|-------|-----|------------------|--------|
| 1 | REQ-02 | scorer.py | Mínimo — fix puntual + test update |
| 2 | REQ-03 | scorer.py | Mínimo — fix puntual + test update |
| 3 | REQ-11 | loop.py | Bajo — cálculo de limit_price |
| 4 | REQ-10 | telegram_bot.py, run.py | Bajo — solo UI/scheduler |
| 5 | REQ-01 | database.py, signal_filter.py | Medio — migración DB + retrain fix |
| 6 | REQ-04 | indicators.py, database.py | Medio — nuevos campos FeatureSet |
| 7 | REQ-05 | preprocessor.py | Medio — fetch weekly + veto |
| 8 | REQ-06 | cycle.py (nuevo), database.py | Medio — coordinador + scheduler |
| 9 | REQ-07 | cycle.py | Bajo — rollback en cycle |

### Iteración 2 — Siguiente semana

| Orden | REQ | Archivo principal | Riesgo |
|-------|-----|------------------|--------|
| 10 | REQ-09 | postmortem_stats.py (nuevo), postmortem.py | Bajo |
| 11 | REQ-08 | calibration.py (nuevo), database.py | Medio — grid search backtest |

---

## Preguntas Abiertas

- [ ] **PQ-01**: ¿RTH o extended hours para futuros (ES, NQ) en fetch semanal? → Usar `get_use_rth(sec_type)` del contract_factory como decisión por defecto
- [ ] **PQ-02**: ¿Threshold de rollback en 30% o diferente? → 30% confirmado por diseño (D-005 en decisions.md)
- [ ] **PQ-03**: ¿El digest de las 14:00 ET se envía también cuando no hay posiciones abiertas? → Sí, siempre (muestra "Sin posiciones activas")
- [ ] **PQ-04**: ¿Frecuencia del learning cycle — diario o cada N trades? → Diario a las 17:00 ET post-market

---

## Criterio de Éxito del Módulo

El módulo se considera completo cuando:

1. `SignalFilter.retrain()` ejecuta sin errores y el `LearningReport` reporta AUC medible
2. El scanner descarta al menos 1 señal STRONG por semana por filtro semanal bearish (verificable en logs)
3. Cada símbolo nuevo aprobado recibe `backtest_calibrated=1` en `symbol_parameters` dentro de 5 minutos
4. `run_learning_cycle()` corre diariamente sin errores y Frank recibe el reporte en Telegram
5. Los tests de scorer pasan con los valores corregidos de volatilidad y price_change
