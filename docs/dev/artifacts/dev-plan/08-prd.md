# PRD: dev-plan — Feature-Centric Analysis Pipeline

**Module**: dev-plan
**Phase**: Phase 3 — Requirements
**Status**: ✓ Complete
**Date**: 2026-05-07
**Design ref**: docs/dev/artifacts/dev-plan/06-interface-design.md

---

## 1. Overview

Refactorizar el sistema IBKR AI Trader de arquitectura prompt-centric a feature-centric. El LLM deja de calcular e improvisar; pasa a interpretar un FeatureSet estructurado pre-computado. Se introduce un pipeline unificado (AnalysisPipeline) que sirve tanto para análisis on-demand como para decisiones automáticas de trading.

**Versión actual del sistema**: operacional con 95 tests pasando. Este PRD define la evolución — el sistema existente sigue funcionando durante la migración.

---

## 2. Componentes y Requisitos

---

### REQ-01: settings.py — Centralización de variables de entorno

**Prioridad**: P0 — bloquea todo el desarrollo local

**Requisitos funcionales**:

- RF-01.1: `IB_HOST = os.getenv("IB_HOST", "127.0.0.1")` — no hardcodeado
- RF-01.2: `IB_PORT = int(os.getenv("IB_PORT", "4002"))` — no hardcodeado
- RF-01.3: `OPENCODE_BIN = os.getenv("OPENCODE_BIN", "/home/frankpach/.opencode/bin/opencode")`
- RF-01.4: `API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8088")`
- RF-01.5: `IB_MOCK = os.getenv("IB_MOCK", "false").lower() == "true"` → bool
- RF-01.6: `IB_CLIENT_ID_DATA = int(os.getenv("IB_CLIENT_ID_DATA", "12"))` — para IBDataLayer
- RF-01.7: `OPENCODE_MODEL = os.getenv("OPENCODE_MODEL", "opencode-go/qwen3.5-plus")`
- RF-01.8: Todos los módulos que hoy tienen `API_BASE = "http://127.0.0.1:8088"` hardcodeado deben importar `API_BASE` desde settings (7 archivos: alerts/manager.py, notifications/telegram_bot.py, positions/manager.py, llm/loop.py, llm/agent.py, mcp/server.py, backtest/engine.py cuando aplique)
- RF-01.9: `OPENCODE_BIN` se reemplaza en `llm/agent.py` y `notifications/telegram_bot.py`

**Criterios de aceptación**:

- AC-01.1: Con `.env.local` en Windows con `IB_HOST=100.92.245.100`, el sistema usa esa IP sin cambiar código
- AC-01.2: Con `IB_MOCK=true`, el sistema NO intenta conectar a IB Gateway — usa MockIBClient
- AC-01.3: `from app.config.settings import API_BASE` funciona en todos los módulos sin ImportError
- AC-01.4: Los 95 tests existentes siguen pasando sin cambios

---

### REQ-02: MockIBClient (app/analysis/mock_client.py)

**Prioridad**: P0 — bloquea tests locales

**Requisitos funcionales**:

- RF-02.1: Implementa la misma interfaz pública que IBKRClient: `get_stock_price(symbol)`, `get_account()`, `get_portfolio()`, `place_order(...)`, `disconnect()`
- RF-02.2: Implementa los métodos que necesita IBDataLayer: `ib.reqHistoricalData(...)`, `ib.reqScannerData(...)`, `ib.reqHistoricalNews(...)`, `ib.reqFundamentalData(...)`
- RF-02.3: Retorna datos determinísticos con semilla fija (numpy seed=42) — mismos datos siempre para mismo símbolo
- RF-02.4: `get_stock_price("AAPL")` siempre retorna `{"symbol": "AAPL", "market_price": 287.50, "bid": 287.49, "ask": 287.51}`
- RF-02.5: `reqHistoricalData` retorna 180 barras diarias sintéticas con tendencia alcista moderada + volatilidad realista
- RF-02.6: `isConnected()` siempre retorna `True`
- RF-02.7: `place_order(...)` retorna `{"order_id": "mock_001", "status": "Submitted"}` sin conectar a IB
- RF-02.8: Se activa automáticamente cuando `settings.IB_MOCK is True`

**Criterios de aceptación**:

- AC-02.1: `pytest tests/` completo pasa en Windows sin IB Gateway con `IB_MOCK=true`
- AC-02.2: Los datos mock son idénticos en cada ejecución (determinísticos)
- AC-02.3: MockIBClient no abre ningún socket ni conexión de red

---

### REQ-03: IBDataLayer (app/analysis/data.py)

**Prioridad**: P0

**Requisitos funcionales**:

- RF-03.1: `__init__(ib_client)` — acepta IBKRClient real o MockIBClient
- RF-03.2: `get_ohlcv(symbol, duration, bar_size, context)` → `pd.DataFrame | None`
  - Columnas obligatorias: `open, high, low, close, volume`
  - TTL por context: `trade_entry=0`, `on_demand=120`, `scanner=900`, `backtest=3600`
  - Si IB falla → retorna None con `logger.error(...)`, sin lanzar excepción
- RF-03.3: `get_historical_volatility(symbol, context)` → `pd.DataFrame | None`
  - Usa `reqHistoricalData(whatToShow="HISTORICAL_VOLATILITY")`
  - TTL igual al context
- RF-03.4: `get_implied_volatility(symbol, context)` → `pd.DataFrame | None`
  - Usa `reqHistoricalData(whatToShow="OPTION_IMPLIED_VOLATILITY")`
- RF-03.5: `get_news(symbol)` → `list[dict]`
  - Intenta `reqHistoricalNews` de IB primero
  - Fallback a Yahoo Finance RSS si IB falla o retorna vacío
  - Cada item: `{"title": str, "sentiment": "positive|negative|neutral", "date": str}`
  - TTL: 900s (mismo que scanner)
- RF-03.6: `get_earnings_date(symbol)` → `datetime | None`
  - Intenta `reqFundamentalData("CalendarReport")`
  - Fallback: parseo Yahoo Finance `/quote/{symbol}` para próximos earnings
  - Fallback final: retorna None (no bloquea el pipeline)
  - TTL: 86400s (24 horas)
- RF-03.7: `run_scanner(scan_code, max_results=20)` → `list[str]`
  - scan_codes válidos: `"HOT_BY_VOLUME"`, `"TOP_PERC_GAIN"`, `"MOST_ACTIVE"`
  - Filtra: solo US stocks, precio > $5, volumen > 500k
  - Retorna lista de tickers (símbolos)
  - TTL: 900s
- RF-03.8: `get_spy_price_on(date)` → `float | None`
  - Obtiene precio de cierre de SPY en una fecha específica via `reqHistoricalData`
  - Usado por ReturnEvaluator
- RF-03.9: Cache en memoria (dict Python): key = `f"{symbol}:{context}:{bar_size}"`, value = `(data, expires_at_timestamp)`
- RF-03.10: `IBDataLayer` usa `IB_CLIENT_ID_DATA` (default=12), nunca interfiere con client_id=10 o 11

**Criterios de aceptación**:

- AC-03.1: Dos llamadas consecutivas a `get_ohlcv("AAPL", "30 D", "1 day", "scanner")` dentro de 900s → segunda usa cache (0 calls a IB)
- AC-03.2: `get_ohlcv("AAPL", "30 D", "1 day", "trade_entry")` NUNCA usa cache
- AC-03.3: Si IB Gateway está desconectado → retorna None, no lanza excepción, logea error
- AC-03.4: Con MockIBClient activo → todos los métodos retornan datos sintéticos válidos

---

### REQ-04: IndicatorEngine (app/analysis/indicators.py)

**Prioridad**: P0

**Requisitos funcionales**:

- RF-04.1: `FeatureSet` dataclass con todos los campos definidos en el interface design
- RF-04.2: `compute_features(symbol, df_daily, df_hourly, df_5min, hv_series, iv_series, spy_df, qqq_df)` → `FeatureSet`
  - Si cualquier DataFrame es None → ese indicador queda como None en el resultado, no falla
  - `df_daily` mínimo 15 filas para calcular RSI (14 períodos + 1)
  - Si menos de 15 filas → retorna FeatureSet con todos los indicadores en None
- RF-04.3: Indicadores a calcular:
  - `rsi_14`: RSI de 14 períodos sobre close de `df_daily`
  - `macd_line`, `macd_signal`, `macd_crossover`: EMA12/EMA26/EMA9 sobre close diario. Crossover = True si la línea MACD cruzó la señal en la última barra
  - `atr_pct`: ATR(14) dividido entre el precio de cierre × 100 (como porcentaje)
  - `sma20`, `sma50`, `sma200`: medias móviles simples sobre close diario
  - `bollinger_upper`, `bollinger_lower`: SMA20 ± 2σ. `bollinger_position` = (close - lower) / (upper - lower) en rango [0,1]
  - `vwap`: VWAP sobre `df_daily` del período disponible
  - `volume_ratio_20d`: volumen del último día / media de 20 días
  - `rs_vs_spy_30d`: retorno acumulado del símbolo en 30d / retorno acumulado de SPY en 30d - 1. Positivo = outperform
  - `rs_vs_qqq_30d`: igual vs QQQ
  - `hist_volatility_30d`: último valor de la serie `hv_series` si disponible
  - `impl_volatility`: último valor de la serie `iv_series` si disponible
- RF-04.4: `compute_single_indicator(indicator_name, df)` → `float | bool | None`
  - Permite calcular un solo indicador sin recalcular todo
  - `indicator_name` debe ser una key válida en `INDICATORS` dict
  - Si `indicator_name` no existe → retorna None con warning
- RF-04.5: `INDICATORS` dict es el registro de plugins — agregar un nuevo indicador solo requiere agregar una entry al dict y su función `_compute_X(df) → float`
- RF-04.6: `feature_relevance` en FeatureSet: carga multiplicadores del símbolo desde DB (tabla `symbol_parameters`). Si no existen → `{indicator: 1.0 for indicator in INDICATORS}`
- RF-04.7: `classify_signal(rsi, macd_crossover, volume_ratio)` y `classify_multitimeframe(daily, hourly, minute)` se migran desde `preprocessor.py` a este módulo. Las firmas no cambian.

**Criterios de aceptación**:

- AC-04.1: `compute_features(symbol, df_daily=df30, df_hourly=None, ...)` retorna FeatureSet con `rsi_14` calculado y `rs_vs_spy_30d = None` (sin error)
- AC-04.2: Mismos inputs producen exactamente los mismos outputs (determinístico)
- AC-04.3: `preprocessor.py` después de la migración importa `classify_signal, classify_multitimeframe` desde `app.analysis.indicators` — tests existentes siguen pasando
- AC-04.4: `backtest/engine.py` importa `_calc_indicators` como `compute_indicators_from_df` desde `app.analysis.indicators` — tests siguen pasando
- AC-04.5: `compute_single_indicator("rsi_14", df)` retorna float entre 0 y 100

---

### REQ-05: QuantScorer (app/analysis/scorer.py)

**Prioridad**: P1

**Requisitos funcionales**:

- RF-05.1: `QuantScore` dataclass: `total: float, momentum: float, trend: float, volume: float, volatility: float, portfolio_fit: float, sentiment: float, recommendation: str, weights_used: dict`
- RF-05.2: `compute_score(features: FeatureSet, symbol: str, portfolio: list) → QuantScore`
  - Calcula dimension scores (0.0-1.0) desde el FeatureSet
  - Carga multiplicadores por símbolo desde DB (tabla `symbol_parameters`). Default 1.0 si no existen.
  - `effective_weight = GLOBAL_WEIGHTS[dim] * symbol_multiplier[dim]`
  - Normaliza para que los pesos sumen 1.0
  - `total = sum(dim_score * effective_weight for all dims) * 100`
  - Clampea total a [0, 100]
  - `recommendation`: "REJECTED" si total <= 49, "WATCHLIST" si <= 69, "PROPOSE" si <= 84, "PRIORITY" si > 84
- RF-05.3: Cálculo de dimension scores:
  - `momentum`: RSI en zona extrema (< 30 o > 70) → 0.7+. MACD crossover → +0.3. Sin señal → 0.2-0.4
  - `trend`: precio > SMA50 → +0.3. SMA50 > SMA200 (golden cross) → +0.3. RS_vs_SPY > 0 → +0.2. Bollinger_position en mitad superior → +0.2
  - `volume`: volume_ratio_20d > 1.5 → 0.8+. > 2.0 → 1.0. < 0.8 → 0.2
  - `volatility`: ATR_pct entre 1.5-4% → 0.7 (rango ideal swing). < 1% o > 6% → 0.3
  - `portfolio_fit`: capital disponible para >= 1 unidad → 0.5+. Sin correlación conocida → 0.5. Correlación < 0.7 → 0.8
  - `sentiment`: news_sentiment positivo → 0.7. Neutral → 0.5. Negativo → 0.3. Sin news → 0.5
- RF-05.4: `get_weights(symbol)` → `dict[str, float]` — retorna pesos efectivos para un símbolo (global * multiplicadores)
- RF-05.5: `update_weights_attenuated(symbol, dimension, suggested_multiplier, confidence, learning_rate=0.15, min_trade_count=5)` → `bool`
  - Retorna False (sin actualizar) si `trade_count < min_trade_count` para ese símbolo
  - `new_mult = old_mult + (suggested_multiplier - old_mult) * confidence * learning_rate`
  - Clampea `new_mult` a [0.5, 1.5]
  - Guarda en DB tabla `symbol_parameters`

**Criterios de aceptación**:

- AC-05.1: `compute_score(features_with_rsi28_macd_cross_vol18, "AAPL", [])` retorna `total >= 70`
- AC-05.2: `compute_score(features_neutral, "AAPL", [])` retorna `total` entre 40-60
- AC-05.3: `update_weights_attenuated("AAPL", "momentum", 1.3, 0.8)` con 3 trades → retorna False
- AC-05.4: `update_weights_attenuated("AAPL", "momentum", 1.3, 0.8)` con 6 trades → new_mult = 1.0 + (1.3-1.0)*0.8*0.15 = 1.036. Guardado en DB.
- AC-05.5: Ningún peso multiplicador puede superar 1.5 ni bajar de 0.5 bajo ninguna circunstancia

---

### REQ-06: HardRules (app/analysis/hard_rules.py)

**Prioridad**: P1

**Requisitos funcionales**:

- RF-06.1: `HardRulesResult` dataclass: `passed: bool, failures: list[str], warnings: list[str], earnings_in_days: int | None`
- RF-06.2: `check_all(symbol, features, portfolio, earnings_date, capital)` → `HardRulesResult`
- RF-06.3: Regla de liquidez: si `features.volume_ratio_20d < 0.3` → failure "Volumen insuficiente". Si < 0.7 → warning.
- RF-06.4: Earnings gate: si `earnings_date` y `(earnings_date - now).days < 3` → failure "Earnings en < 3 días". Si < 7 → warning "Earnings en {n} días — considerar reducir TP".
- RF-06.5: Correlación: si hay posición abierta del mismo sector/categoría y correlación > 0.85 → failure. Si > 0.70 → warning. (Implementación inicial: misma categoría ETF/blue_chip/growth es proxy de correlación)
- RF-06.6: Capital: `max_risk = max(500 * 0.02, 1.0)`. `max_pos_usd = min(max_risk / stop_loss_pct_default, 500)`. `units = int(max_pos_usd / features_price)`. Si `units < 1` → failure "Capital insuficiente para 1 unidad".
- RF-06.7: Si `earnings_date is None` → NO failure, solo agrega a warnings: "Fecha de earnings desconocida"
- RF-06.8: `passed = len(failures) == 0`

**Criterios de aceptación**:

- AC-06.1: `check_all(symbol, features, [], earnings_in_2_days, 500)` → `passed=False`, failures incluye "Earnings"
- AC-06.2: `check_all(symbol, features, [], earnings_in_5_days, 500)` → `passed=True`, warnings incluye "Earnings en 5 días"
- AC-06.3: `check_all(symbol, features, [], None, 500)` → `passed=True`, warnings incluye "Fecha de earnings desconocida"
- AC-06.4: Sin LLM involucrado en ninguna decisión de HardRules — función pura determinística

---

### REQ-07: AnalysisPipeline (app/analysis/pipeline.py)

**Prioridad**: P1

**Requisitos funcionales**:

- RF-07.1: Dataclasses: `AnalysisContext(mode: str)`, `ParameterSuggestion(dimension, current_value, suggested_value, confidence, reason)`, `AnalysisResult` (ver interface design)
- RF-07.2: `AnalysisPipeline.__init__(symbol, data_layer, context, notify_fn=None)`
- RF-07.3: `AnalysisPipeline.run()` → `AnalysisResult`
  - Ejecuta en orden: `_fetch_data → _compute_indicators → _score → _check_hard_rules → _llm_interpret (condicional) → _persist`
  - `self.current_step` se actualiza al inicio de cada paso
  - Si `hard_rules.passed is False` → salta `_llm_interpret`, result.recommendation = "REJECTED"
  - Si `context.mode == "daily_discovery"` → salta `_llm_interpret` para candidatos con score < 60 (ahorra LLM calls en batch)
- RF-07.4: Watchdog: `threading.Timer(TOTAL_TIMEOUT=600)` arranca al inicio de `run()`. Si dispara:
  - `self._result.failed_at_step = self.current_step`
  - Si `notify_fn` → llama `notify_fn(f"Análisis {symbol} timeout en paso '{self.current_step}' (10 min)")`
  - Retorna `AnalysisResult` parcial con `recommendation="ERROR"`
- RF-07.5: Timeouts por paso via `threading.Timer` individual: `fetch_data=30s, compute_indicators=10s, hard_rules=5s, llm_interpret=60s`
- RF-07.6: Progress notifications via `notify_fn` si no es None:
  - `_fetch_data`: "Descargando datos {symbol}..."
  - `_compute_indicators`: "Calculando indicadores {symbol}..."
  - `_check_hard_rules`: solo si falla: "Reglas duras fallaron para {symbol}: {failures}"
  - `_llm_interpret`: "Consultando LLM para {symbol} (score: {score:.0f})..."
- RF-07.7: `_llm_interpret` construye el prompt con esta estructura:
  ```
  SYMBOL: {symbol}
  CATEGORY: {category}
  STRATEGY_CONTEXT: {get_strategy_context(category)}
  
  FEATURE_SET:
  {features.to_dict() como JSON}
  
  QUANT_SCORE:
  {score.to_dict() como JSON}
  
  HARD_RULES:
  {hard_rules.to_dict()}
  
  NEWS_SUMMARY:
  {news_items}
  
  HISTORICAL_PATTERNS:
  {patterns del símbolo}
  
  TASK: Interpreta esta evidencia. Responde SOLO con este JSON:
  {"narrative": "...", "confidence": 0.75, "key_risks": ["..."], "suggestions": [...]}
  ```
- RF-07.8: `_persist` guarda en DB:
  - `FeatureSnapshot` → `feature_snapshot_id`
  - `CandidateDecision` con `feature_snapshot_id`, score, recommendation, llm_summary
  - Actualiza `WatchlistScore` para el símbolo

**Criterios de aceptación**:

- AC-07.1: `pipeline.run()` con MockIBClient completa en < 5s (sin LLM)
- AC-07.2: Si `notify_fn` es provided, recibe al menos 2 mensajes de progreso durante un análisis completo
- AC-07.3: Si IB Gateway no responde → `failed_at_step = "fetch_data"` en result, no lanza excepción
- AC-07.4: Si `hard_rules.passed is False` → `llm_interpret` NUNCA se llama (verificable con mock)
- AC-07.5: `result.feature_snapshot_id` es un int válido (guardado en DB) al completarse correctamente
- AC-07.6: Con watchdog forzado → Frank recibe mensaje Telegram con nombre del paso donde se trabó

---

### REQ-08: PostMortem v2 — Fix BUG-001 + Ajustes estructurados

**Prioridad**: P0 (bug activo)

**Requisitos funcionales**:

- RF-08.1: Eliminar `from openai import OpenAI` y el uso de `LLM_API_KEY`
- RF-08.2: Usar `_call_opencode(prompt)` de `app/llm/agent.py` — misma función
- RF-08.3: El prompt incluye el `FeatureSet` al momento de entrada si `feature_snapshot_id` está disponible en el trade
- RF-08.4: LLM retorna JSON estructurado:
  ```json
  {
    "pattern_text": "AAPL + RSI<30 + MACD alcista → BUY confiable",
    "suggestions": [
      {"dimension": "stop_loss_pct", "suggested": 0.028, "confidence": 0.7, "reason": "ATR sugiere SL más amplio"},
      {"dimension": "momentum_weight", "suggested_multiplier": 1.2, "confidence": 0.6, "reason": "RSI fue predictivo"}
    ]
  }
  ```
- RF-08.5: Para cada suggestion con `confidence >= 0.5`: llamar `QuantScorer.update_weights_attenuated()`
- RF-08.6: Si parseo del JSON falla → guarda solo `pattern_text` como texto libre (degradación graceful)
- RF-08.7: Notifica a Frank: "Post-mortem {symbol}: patrón guardado. {n} ajustes aplicados."

**Criterios de aceptación**:

- AC-08.1: `run_postmortem(trade)` no lanza excepción con `LLM_API_KEY=""` (ya no la necesita)
- AC-08.2: Un pattern queda en DB después de ejecutar `run_postmortem`
- AC-08.3: Frank recibe notificación Telegram con resumen del post-mortem
- AC-08.4: Con OpenCode no disponible → retorna gracefully sin crash, logea error

---

### REQ-09: DB — 4 nuevas tablas

**Prioridad**: P1

**Requisitos funcionales**:

- RF-09.1: Tabla `feature_snapshots`:
  ```sql
  CREATE TABLE IF NOT EXISTS feature_snapshots (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      symbol TEXT NOT NULL,
      timestamp TEXT NOT NULL,
      context TEXT NOT NULL,
      rsi_14 REAL, macd_line REAL, macd_signal REAL, macd_crossover INTEGER,
      atr_pct REAL, sma20 REAL, sma50 REAL, sma200 REAL,
      bollinger_upper REAL, bollinger_lower REAL, bollinger_position REAL,
      vwap REAL, volume_ratio_20d REAL,
      hist_volatility_30d REAL, impl_volatility REAL,
      rs_vs_spy_30d REAL, rs_vs_qqq_30d REAL,
      feature_relevance_json TEXT DEFAULT '{}'
  )
  ```
- RF-09.2: Tabla `symbol_parameters`:
  ```sql
  CREATE TABLE IF NOT EXISTS symbol_parameters (
      symbol TEXT PRIMARY KEY,
      stop_loss_pct REAL DEFAULT 0.025,
      take_profit_pct REAL DEFAULT 0.06,
      min_profit_pct REAL DEFAULT 0.01,
      momentum_mult REAL DEFAULT 1.0,
      trend_mult REAL DEFAULT 1.0,
      volume_mult REAL DEFAULT 1.0,
      volatility_mult REAL DEFAULT 1.0,
      portfolio_fit_mult REAL DEFAULT 1.0,
      sentiment_mult REAL DEFAULT 1.0,
      trade_count INTEGER DEFAULT 0,
      version INTEGER DEFAULT 1,
      previous_json TEXT,
      updated_at TEXT NOT NULL
  )
  ```
- RF-09.3: Tabla `candidate_decisions`:
  ```sql
  CREATE TABLE IF NOT EXISTS candidate_decisions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      symbol TEXT NOT NULL,
      decision_date TEXT NOT NULL,
      decision TEXT NOT NULL,
      price_at_decision REAL,
      quant_score REAL,
      feature_snapshot_id INTEGER,
      llm_summary TEXT,
      future_return_7d REAL,
      future_return_30d REAL,
      future_return_90d REAL,
      alpha_vs_spy_7d REAL,
      alpha_vs_spy_30d REAL,
      evaluated_7d_at TEXT,
      evaluated_30d_at TEXT
  )
  ```
- RF-09.4: Tabla `watchlist_scores`:
  ```sql
  CREATE TABLE IF NOT EXISTS watchlist_scores (
      symbol TEXT PRIMARY KEY,
      signal_quality_score REAL DEFAULT 0.5,
      admission_score REAL DEFAULT 0.5,
      trade_history_score REAL DEFAULT 0.5,
      watchlist_score REAL DEFAULT 0.5,
      last_updated TEXT NOT NULL
  )
  ```
- RF-09.5: Todas las tablas se crean en `init_db()` con `CREATE TABLE IF NOT EXISTS` — no breaking changes
- RF-09.6: CRUD functions en `database.py`: `insert_feature_snapshot`, `get_feature_snapshot`, `insert_candidate_decision`, `update_candidate_decision_returns`, `get_candidate_decisions_for_evaluation`, `get_or_create_symbol_parameters`, `update_symbol_parameters`, `get_watchlist_scores`, `update_watchlist_score`

**Criterios de aceptación**:

- AC-09.1: `init_db()` después del cambio crea las 4 nuevas tablas sin errores
- AC-09.2: Las tablas existentes (signals, trades, patterns, etc.) no se modifican
- AC-09.3: `get_or_create_symbol_parameters("AAPL")` retorna defaults si AAPL no tiene registro previo

---

### REQ-10: Migración preprocessor.py

**Prioridad**: P2

**Requisitos funcionales**:

- RF-10.1: `classify_signal` y `classify_multitimeframe` se mueven a `app/analysis/indicators.py`
- RF-10.2: `preprocessor.py` importa estas funciones desde `app.analysis.indicators`
- RF-10.3: `_calc_indicators(df)` en preprocessor se reemplaza por llamada a `IndicatorEngine.compute_features(...)`
- RF-10.4: `scan_symbol()` usa `AnalysisPipeline` con `context=AnalysisContext(mode="scanner")` para símbolos del universo

**Criterios de aceptación**:

- AC-10.1: Tests `test_preprocessor.py` y `test_multitimeframe.py` pasan sin cambios en los tests
- AC-10.2: `from app.scanner.preprocessor import classify_signal` sigue funcionando (reexportado)

---

### REQ-11: Migración backtest/engine.py

**Prioridad**: P2

**Requisitos funcionales**:

- RF-11.1: Reemplaza `from app.scanner.preprocessor import classify_signal, _calc_indicators` con `from app.analysis.indicators import classify_signal, compute_from_df`
- RF-11.2: `apply_signals_to_df(df)` usa `compute_from_df(df)` internamente

**Criterios de aceptación**:

- AC-11.1: Tests `test_backtest_engine.py` pasan sin cambios en los tests

---

### REQ-12: Migración llm/agent.py

**Prioridad**: P2

**Requisitos funcionales**:

- RF-12.1: `OPENCODE_BIN` y `OPENCODE_MODEL` se importan desde `settings`
- RF-12.2: `analyze_signal(symbol, strength, rsi, macd, volume_ratio, signal_id)` → delega a `AnalysisPipeline` creando un `AnalysisContext(mode="auto_signal")`. El FeatureSet ya viene calculado desde el scanner — se reutiliza si el cache está fresco.
- RF-12.3: `_get_context()` se elimina — el contexto llega como FeatureSet desde el pipeline

**Criterios de aceptación**:

- AC-12.1: `analyze_signal(...)` retorna `LLMDecision` sin cambios de interface para `loop.py`
- AC-12.2: `OPENCODE_BIN` hardcodeado desaparece de `agent.py`

---

### REQ-13: DailyDiscovery job + Universe rotation

**Prioridad**: P2

**Requisitos funcionales**:

- RF-13.1: Job APScheduler `daily_discovery`: cron 8am ET, solo días de mercado (lunes-viernes)
- RF-13.2: Llama `data_layer.run_scanner("HOT_BY_VOLUME")` + `run_scanner("TOP_PERC_GAIN")` + `run_scanner("MOST_ACTIVE")`
- RF-13.3: Une los resultados, elimina duplicados y símbolos ya en `ALLOWED_SYMBOLS`, toma top 20 por volumen
- RF-13.4: Para cada candidato: crea `AnalysisPipeline(mode="daily_discovery")` y llama `run()`. Sin notify_fn (batch silencioso).
- RF-13.5: Candidatos con `score >= 70` son "candidatos de watchlist"
- RF-13.6: Universe rotation: si `candidato.score > 75` y `peor_universo.watchlist_score < 40`:
  - Actualiza `symbol_config` (approved=false para el que sale, approved=true para el que entra)
  - Actualiza `ALLOWED_SYMBOLS` en memoria
  - Notifica Frank: "🔄 {nuevo} (score:{s}) entra al universo. {viejo} (watchlist:{w}) sale."
- RF-13.7: SPY y QQQ nunca salen del universo (hardcoded protection)

**Criterios de aceptación**:

- AC-13.1: El job corre una vez a las 8am ET en días de mercado y no en fines de semana
- AC-13.2: Frank recibe notificación solo si hay rotación efectiva, no en cada ejecución
- AC-13.3: Con MockIBClient + `IB_MOCK=true`, el job completa sin errores (útil para tests)
- AC-13.4: SPY y QQQ permanecen en universo aunque su watchlist_score sea bajo

---

### REQ-14: ReturnEvaluator job

**Prioridad**: P2

**Requisitos funcionales**:

- RF-14.1: Job APScheduler `return_evaluator`: cron 6am ET diario
- RF-14.2: `get_candidate_decisions_for_evaluation(days_ago=7)` → decisiones sin `future_return_7d`
- RF-14.3: Para cada decisión: obtiene precio actual del símbolo y precio de SPY en la fecha de la decisión via `data_layer.get_spy_price_on(decision.decision_date)`
- RF-14.4: Calcula `return_7d = (current_price - price_at_decision) / price_at_decision`
- RF-14.5: Calcula `alpha_7d = return_7d - spy_return_7d`
- RF-14.6: Actualiza `candidate_decisions` con los valores calculados
- RF-14.7: Si hay >= 20 decisiones evaluadas con 7d return: calcula accuracy (% de PROPOSE/PRIORITY que superaron SPY). Si accuracy < 50% → loguea warning pero NO ajusta thresholds automáticamente (manual por ahora)

**Criterios de aceptación**:

- AC-14.1: Una decisión creada hace 7 días tiene `future_return_7d` poblado después del job
- AC-14.2: `alpha_vs_spy_7d` es positivo si el símbolo superó a SPY en 7 días

---

### REQ-15: Endpoints FastAPI nuevos

**Prioridad**: P2

**Requisitos funcionales**:

- RF-15.1: `GET /candidate-analysis/{symbol}` — corre `AnalysisPipeline(mode="on_demand")` y retorna `AnalysisResult` como JSON
- RF-15.2: `GET /analysis/indicator/{symbol}/{indicator_name}` — calcula un solo indicador usando cache de IBDataLayer. Retorna `{"symbol": str, "indicator": str, "value": float|bool|null}`
- RF-15.3: `GET /universe/watchlist` — retorna símbolos del universo con sus watchlist_scores
- RF-15.4: `GET /candidate-decisions` — historial de decisiones con retornos calculados
- RF-15.5: `GET /symbol-parameters/{symbol}` — parámetros adaptativos actuales del símbolo

**Criterios de aceptación**:

- AC-15.1: `GET /candidate-analysis/NFLX` con IB conectado retorna JSON con `quant_score` y `recommendation` en < 90s
- AC-15.2: `GET /analysis/indicator/AAPL/rsi_14` retorna float entre 0-100

---

### REQ-16: MCP Server — nuevas tools

**Prioridad**: P2

**Requisitos funcionales**:

- RF-16.1: Tool `candidate_analysis(symbol: str)` — llama `GET /candidate-analysis/{symbol}` y retorna resultado completo
- RF-16.2: Tool `compute_indicator(symbol: str, indicator_name: str)` — llama `GET /analysis/indicator/{symbol}/{indicator_name}`
- RF-16.3: Tool `get_universe_watchlist()` — llama `GET /universe/watchlist`

**Criterios de aceptación**:

- AC-16.1: OpenCode puede llamar `candidate_analysis("NFLX")` via MCP y recibe el AnalysisResult

---

## 3. Edge Cases

| Caso | Comportamiento esperado |
|---|---|
| IB Gateway desconectado durante fetch_data | AnalysisPipeline retorna `failed_at_step="fetch_data"`, Frank notificado |
| Símbolo sin datos históricos suficientes (< 15 barras) | FeatureSet con todos los indicadores en None, score = 0, REJECTED |
| LLM call timeout (> 60s) | Watchdog corta, Frank notificado con paso específico |
| Earnings date desconocida | HardRules pasa con warning, LLM recibe "earnings_unknown: true" |
| Symbol ya en ALLOWED_SYMBOLS → /analizar | Pipeline usa mode="auto_signal", no mode="on_demand" |
| ReturnEvaluator sin datos de SPY para fecha histórica | `alpha_vs_spy_7d = null`, no falla el job |
| IB Scanner retorna 0 resultados | `daily_discovery` loguea warning, no rota universo |
| Sugerencia de ajuste con SL > 8% | `update_weights_attenuated` clampea a 0.08, no aplica el exceso |
| trade_count = 4 (< ventana mínima de 5) | `update_weights_attenuated` retorna False, no ajusta |
| NFLX propuesto pero SPY tiene watchlist_score = 25 | SPY protegido — NVDA sería el siguiente candidato a salir |

---

## 4. Performance

| Operación | Target | Límite absoluto |
|---|---|---|
| IBDataLayer.get_ohlcv (cache hit) | < 5ms | < 50ms |
| IBDataLayer.get_ohlcv (IB call fresco) | < 10s | < 30s |
| IndicatorEngine.compute_features | < 200ms | < 500ms |
| QuantScorer.compute_score | < 5ms | < 20ms |
| HardRules.check_all | < 5ms | < 20ms |
| AnalysisPipeline.run (sin LLM) | < 15s | < 30s |
| AnalysisPipeline.run (con LLM) | < 60s | < 90s (watchdog 10min) |
| DailyDiscovery (20 candidatos, sin LLM) | < 5 min | < 10 min |

---

## 5. Security

- Credenciales IBKR solo en `.env`, nunca en logs ni código
- `IB_MOCK=true` por defecto en `.env.local` — nunca accede a IB real en Windows dev
- `MockIBClient.place_order()` no puede conectarse a IB real bajo ninguna circunstancia
- RiskValidator no se modifica — sigue siendo la última línea de defensa

---

## 6. Testing

| Capa | Tipo | Herramienta |
|---|---|---|
| IBDataLayer, IndicatorEngine, QuantScorer, HardRules | Unit con MockIBClient | pytest |
| AnalysisPipeline | Unit con MockIBClient, integration con IB en Pi | pytest |
| PostMortem v2 | Unit con mock _call_opencode | pytest |
| DB nuevas tablas | Unit | pytest |
| DailyDiscovery, ReturnEvaluator | Unit con MockIBClient | pytest |
| Migraciones (preprocessor, backtest, agent) | Existing tests sin cambios | pytest |

**Cobertura mínima**: todos los nuevos módulos >= 80% de cobertura de líneas.

**Tests de integración** (marcados `@pytest.mark.integration`, solo en Pi):
- `IBDataLayer` con IB Gateway real
- `AnalysisPipeline.run()` completo con LLM

---

## 7. Open Questions Bloqueantes

Ninguna — el diseño está suficientemente especificado para proceder a planning.

## 8. Open Questions No Bloqueantes

| Pregunta | Impact | Resolve when |
|---|---|---|
| ¿reqFundamentalData disponible en IBKR Pro? | Si no → Yahoo fallback permanente | Phase 5 — primer test en Pi |
| ¿IB Scanner con delayed data útil para swing? | Si no → solo universo fijo hasta obtener live data | Phase 5 — primer día de mercado |
| ¿Accuracy del ReturnEvaluator < 50% tras 20 decisiones? | Indica que los thresholds necesitan ajuste manual | Phase 5+ — necesita datos reales |

---

**Document Version**: 1.0
**Created**: 2026-05-07
**Status**: ✓ Ready for Phase 4 — Planning
