# Design Concept: mtf-learning-engine

**Status**: ✓ Complete
**Date**: 2026-05-13
**Module**: mtf-learning-engine

---

## Problem Statement

El sistema IBKR AI Trader tiene infraestructura de aprendizaje diseñada pero no funcional:

1. **El ML global (SignalFilter) nunca ha aprendido nada real** — un bug silencioso hace que `retrain()` produzca siempre un dataset vacío porque busca un campo `features` que no existe en el modelo `Trade`. El sistema lleva operando con el modelo heurístico de fallback desde el inicio.

2. **El análisis multi-timeframe está diseñado pero desconectado** — `compute_features()` acepta `df_hourly` y `df_weekly` como parámetros pero los ignora. `classify_multitimeframe()` existe pero no se llama desde el pipeline. El sistema evalúa señales sin contexto macro ni timing de entrada.

3. **Cada símbolo nuevo arranca ciego** — `symbol_parameters` se inicializa con valores genéricos (SL=2.5%, TP=6%, todos los multiplicadores=1.0) sin importar si ese símbolo históricamente responde bien o mal a esos parámetros.

4. **El QuantScorer tiene errores de diseño de señal** — volatilidad alta se puntúa como buena (invertido), y un precio cayendo 5% y uno subiendo 5% producen el mismo score para un BUY (pierde dirección).

5. **Los datos recopilados no cierran el loop** — `candidate_decisions.future_return_7d/30d` se calculan pero no retroalimentan al SignalFilter. Los patrones en la tabla `patterns` se guardan pero ningún código los consume para mejorar decisiones.

---

## Solution

Implementar el motor de aprendizaje multi-timeframe completo en orden de riesgo:

**Capa 1 — Correcciones (sin riesgo de regresión):**
- Fix SignalFilter.retrain() para cargar features reales desde `feature_snapshots` en DB
- Corregir `_dim_volatility()` (invertir escala: ATR moderado = buena señal)
- Hacer `_dim_price_change()` direccional según acción BUY/SELL
- Agregar `TimeSeriesSplit` al ciclo de reentrenamiento

**Capa 2 — Features multi-timeframe:**
- Conectar datos semanales y horarios a `compute_features()` para todos los asset classes
- Activar `classify_multitimeframe(daily, hourly, weekly_trend)` en el pipeline del scanner
- Agregar dimensión `trend_macro` al QuantScorer como filtro de tendencia semanal
- Manejar horarios extendidos para futuros (23h) y crypto (24/7)

**Capa 3 — Pipeline de aprendizaje completo:**
- Pipeline backtest → `symbol_parameters` que se dispara automáticamente al aprobar un símbolo nuevo
- Loop cerrado: `candidate_decisions.future_return_7d` → `SignalFilter.retrain()`
- Postmortem enriquecido con estadísticas reales antes de llamar al LLM
- Sistema de rollback automático si win_rate últimos 5 trades < 30%

---

## Key Personas

### Persona 1: Frank — Trader/Operador
- **Quién**: Desarrollador-trader que opera el sistema via Telegram desde cualquier lugar
- **Dispositivo**: Mobile (Telegram) + Desktop (logs, DB, código)
- **Entorno**: Remoto — Raspberry Pi corre el sistema autónomamente
- **Goal**: Que el sistema mejore su win rate sin intervención manual constante. Activar nuevos símbolos y que el sistema arranque calibrado.
- **Mayor constraint**: Tiempo — no puede monitorear el sistema hora a hora. Necesita que el aprendizaje sea automático y confiable.

### Persona 2: Frank — Quant Developer
- **Quién**: El mismo Frank en modo desarrollo: revisa métricas, ajusta código, valida que el aprendizaje funciona
- **Dispositivo**: Desktop (VSCode, Python REPL, SQLite browser)
- **Entorno**: Oficina/home — sesiones de desarrollo focalizadas
- **Goal**: Poder medir si el motor de aprendizaje mejora objetivamente. Ver feature importance, evolución de multiplicadores por símbolo, AUC del SignalFilter.
- **Mayor constraint**: Datos escasos — con $500-$2000 de capital, los trades reales son pocos. El sistema debe aprender eficientemente con datos limitados.

### Persona 3: El Motor Autónomo (Sistema)
- **Quién**: El pipeline automatizado que corre 24/7 (futuros/crypto) o en market hours (equities)
- **Dispositivo**: Raspberry Pi — recursos limitados (RAM, CPU)
- **Entorno**: Producción — no puede fallar silenciosamente
- **Goal**: Evaluar señales con contexto multi-timeframe, aprender de cada trade cerrado, ajustar parámetros por símbolo sin intervención humana.
- **Mayor constraint**: Latencia de datos — `reqHistoricalData` tiene rate limits. El análisis multi-TF no puede bloquear el pipeline principal más de 30s por símbolo.

---

## Constraints

### Timeline
- **Deadline**: 1 semana (2026-05-20)
- **Iteración 1 (esta semana)**: Correcciones críticas + multi-timeframe básico (daily + weekly filter + hourly timing)
- **Iteración 2 (siguiente semana)**: Pipeline backtest → symbol_parameters + loop cerrado candidate_decisions → retrain
- **Bloqueado por**: Nada — paper trading continúa durante el desarrollo

### Technical
- **Lenguaje**: Python 3.11+, Raspberry Pi (ARM)
- **DB**: SQLite — migraciones solo con `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ADD COLUMN`
- **ML**: scikit-learn instalado. XGBoost como mejora futura (cuando haya 200+ trades)
- **Datos**: IBKR via ib_insync — rate limit ~50 requests/10min. Caché en IBDataLayer obligatorio.
- **Asset classes**: Equities (RTH 9:30-16:00 ET), Futuros (23h), Forex (24/5), Crypto (24/7)
- **Timeframes**: Weekly (contexto macro), Daily (señal), Hourly (timing) — 5min para futuros/crypto intraday
- **Activación dinámica**: Backtest pre-entrenamiento se dispara automáticamente al aprobar símbolo

### Business
- **Capital**: $500-$2,000 — máx 3 posiciones simultáneas, máx $500 por posición
- **Risk**: Circuit breaker y módulo de riesgo intocables
- **Success metric**: Señales multi-timeframe filtran ≥20% de entradas contra la tendencia macro en paper trading. SignalFilter.retrain() ejecuta exitosamente con AUC medible.
- **Backward compat**: Si datos multi-TF no están disponibles (IBKR falla), el sistema cae back a análisis single-timeframe. Nunca silencia señales por falta de datos adicionales.

---

## Scope: In vs Out

### In Scope
- Fix SignalFilter.retrain() para cargar features reales desde feature_snapshots
- TimeSeriesSplit en el ciclo de reentrenamiento
- Activar df_hourly y df_weekly en compute_features() para todos los asset classes
- Usar classify_multitimeframe() en el pipeline del scanner
- Agregar dimensión trend_macro al QuantScorer (filtro semanal)
- Corregir _dim_volatility() (escala invertida)
- Corregir _dim_price_change() (dirección BUY/SELL)
- Pipeline: aprobar símbolo → run_backtest() → escribir symbol_parameters calibrados
- Loop: candidate_decisions.future_return_7d → SignalFilter.retrain()
- Postmortem con contexto estadístico (estadísticas reales como prompt context al LLM)
- Rollback automático de symbol_parameters si win_rate últimos 5 trades < 30%
- Manejo de market hours por asset class (equities RTH, futuros extended, crypto 24/7)
- Métricas visibles: AUC del SignalFilter, evolución de multiplicadores, win rate por símbolo

### Out of Scope
- Migración a XGBoost (cuando haya 200+ trades — iteración futura)
- LSTM / deep learning (cuando haya 1,000+ trades)
- Reinforcement Learning
- Optimización de hiperparámetros (grid search automático del modelo ML)
- Análisis de opciones o derivados
- Integración con fuentes de datos alternativas (yfinance, Alpha Vantage)
- Dashboard web de métricas (puede usarse SQLite viewer o Telegram)
- Backtesting multi-asset simultáneo

**Por qué fuera de scope**: El objetivo es cerrar los loops existentes y corregir errores de diseño. El upgrade del modelo ML requiere datos que aún no existen.

---

## Open Questions

- [ ] ¿Se necesita persistir el modelo pkl del SignalFilter en un path accesible desde Telegram (para forzar re-entrenamiento remoto)?
  - *Implicación*: Puede requerir un endpoint Telegram `/retrain` o acceso al filesystem desde el bot
- [ ] Para futuros (ES, NQ) que operan 23h, ¿se usa RTH o extended hours para los datos históricos?
  - *Implicación*: `useRTH=True/False` en reqHistoricalData cambia significativamente el comportamiento del ATR y volumen
- [ ] ¿El rollback de symbol_parameters debe notificarse por Telegram?
  - *Implicación*: Frank necesita saber cuando el sistema revierte parámetros automáticamente
- [ ] ¿Cuántos días de histórico usar en el backtest de inicialización? (90, 180, 365 días)
  - *Implicación*: Más días = mejor calibración pero más tiempo de request a IBKR

---

## Assumptions

- [x] Assumption: El sistema tiene acceso a datos horarios históricos de IBKR para todos los asset classes
  - *Verificar*: Confirmar con reqHistoricalData "1 hour" para futuros y forex
- [x] Assumption: feature_snapshots en DB tiene registros con features técnicas reales que corresponden a trades cerrados
  - *Verificar*: Query `SELECT COUNT(*) FROM feature_snapshots` con trades cerrados
- [x] Assumption: El costo computacional del análisis multi-TF (3 requests adicionales por símbolo) es aceptable en Raspberry Pi con el caché de IBDataLayer
  - *Verificar*: Medir tiempo de análisis en paper trading después de implementar
- [x] Assumption: Para crypto (BTC, ETH), se usan los mismos timeframes (weekly/daily/hourly) sin ajuste especial por 24/7
  - *Verificar*: IBKR puede tener limitaciones para crypto

---

## Success Criteria

- [ ] **ML funcional**: SignalFilter.retrain() ejecuta sin errores, produce modelo con AUC > 0.5 (mejor que azar)
- [ ] **Filtro macro**: classify_multitimeframe() descarta ≥20% de señales que van contra la tendencia semanal
- [ ] **Parámetros calibrados**: Cada símbolo nuevo recibe SL/TP desde backtest histórico, no defaults genéricos
- [ ] **Sin regresiones**: El pipeline de paper trading sigue generando señales válidas tras todos los cambios
- [ ] **Fallback funcional**: Si IBKR no devuelve datos horarios/semanales, el sistema opera normalmente con análisis daily solo
- [ ] **Rollback funcional**: Si win_rate últimos 5 trades < 30%, symbol_parameters revierte y notifica por Telegram

---

## Related Components

- **app/ml/signal_filter.py** — SignalFilter (fix retrain + features multi-TF)
- **app/analysis/indicators.py** — compute_features(), classify_multitimeframe() (activar)
- **app/analysis/scorer.py** — QuantScorer (correcciones + dimensión trend_macro)
- **app/analysis/data.py** — IBDataLayer (ya soporta cualquier bar_size)
- **app/backtest/engine.py** — run_backtest() + pipeline → symbol_parameters
- **app/llm/postmortem.py** — postmortem con contexto estadístico
- **app/analysis/evaluator.py** — ReturnEvaluator → loop hacia retrain()
- **app/db/database.py** — feature_snapshots, candidate_decisions, symbol_parameters

---

## Next Steps

1. Verificar assumptions (feature_snapshots con datos, acceso hourly IBKR)
2. Phase 1: `/120-architecture mtf-learning-engine` → mapear dependencias entre componentes
3. Phase 2: `/130-design mtf-learning-engine` → interfaces entre capas
4. Phase 3: `/140-requirements` → issues detallados por componente
5. Phase 4: `/150-planning` → orden de implementación con dependencias

---

## Sign-Off

| Rol | Nombre | Fecha | Aprobado |
|-----|--------|-------|----------|
| Developer/Trader | Frank Pacheco | 2026-05-13 | ✓ |

**Document Version**: 1.0
**Last Updated**: 2026-05-13
**Approved**: ✓ Yes
