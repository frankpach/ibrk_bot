# Issue 002: IBDataLayer + IndicatorEngine

**Module**: dev-plan
**Type**: AFK
**Effort**: L
**Blocked by**: 001
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: Los indicadores técnicos (RSI, MACD, etc.) están duplicados en 3 módulos distintos. El sistema no puede descargar datos de IB para símbolos fuera del universo, ni para el backtest de forma eficiente. No hay cache — cada análisis redescarga todo desde IB.

**Business impact**: Sin IndicatorEngine unificado, el CandidateAdmissionFlow y el AnalysisPipeline no pueden construirse. Sin IBDataLayer con cache, el sistema saturará IB con requests repetidos.

**Success signal**: `IndicatorEngine.compute_features("AAPL", df)` retorna un `FeatureSet` con todos los indicadores calculados. Los tests de preprocessor y backtest siguen pasando sin cambios.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---|---|---|---|---|---|
| Sistema | Bot Pi | Pi | 24/7 | Calcular indicadores una vez, reutilizarlos | Rate limits IB, latencia |
| Frank | Developer | Windows | Local | Testear pipeline sin IB conectado | MockIBClient debe bastar |

**Primary user**: Sistema autónomo.

---

## WHAT — Constraints

- [ ] `IBDataLayer` usa `IB_CLIENT_ID_DATA` (default=12) — nunca interfiere con client_id 10 u 11
- [ ] Cache en memoria: dict Python con `(data, expires_at)` — NO en SQLite
- [ ] Si IB falla → retorna None, loguea error — nunca lanza excepción
- [ ] `compute_features()` retorna FeatureSet con campos None si los datos no están disponibles — no falla
- [ ] `classify_signal()` y `classify_multitimeframe()` se migran a indicators.py, reexportadas desde preprocessor.py para backwards compatibility
- [ ] `_calc_indicators` privada de preprocessor se convierte en `compute_from_df()` pública en indicators.py

**Module-specific rules**:
- [ ] IBDataLayer envuelve IBKRClient SIN modificarlo
- [ ] IndicatorEngine son funciones puras — sin estado global
- [ ] Plugin registry `INDICATORS` dict para fácil extensión

---

## HOW — Implementation Approach

**app/analysis/data.py** — IBDataLayer clase:
- `__init__(ib_client)`: acepta IBKRClient o MockIBClient
- Cache key: `f"{symbol}:{context}:{bar_size}:{duration}"`
- TTL constants: `TTL = {"trade_entry": 0, "on_demand": 120, "scanner": 900, "backtest": 3600, "fundamentals": 86400}`
- `get_ohlcv(symbol, duration, bar_size, context)` → DataFrame con open/high/low/close/volume
- `get_historical_volatility(symbol, context)` → DataFrame, whatToShow="HISTORICAL_VOLATILITY"
- `get_implied_volatility(symbol, context)` → DataFrame, whatToShow="OPTION_IMPLIED_VOLATILITY"
- `get_news(symbol)` → list[dict] con title, sentiment, date. IB first, Yahoo RSS fallback
- `get_earnings_date(symbol)` → datetime | None. reqFundamentalData → Yahoo fallback → None
- `run_scanner(scan_code, max_results=20)` → list[str] tickers filtrados (precio > $5, vol > 500k)
- `get_spy_price_on(date)` → float | None para ReturnEvaluator

**app/analysis/indicators.py** — funciones puras:
- `FeatureSet` dataclass (todos los campos del interface design)
- `INDICATORS` dict con 11 funciones registradas
- `compute_features(symbol, df_daily, df_hourly, df_5min, hv_series, iv_series, spy_df, qqq_df)` → FeatureSet
  - Mínimo 15 filas en df_daily para RSI. Si menos → todos los indicadores = None
  - Indicadores a calcular: rsi_14, macd (line/signal/crossover), atr_pct, sma20/50/200, bollinger (upper/lower/position), vwap, volume_ratio_20d, rs_vs_spy_30d, rs_vs_qqq_30d
  - Si hv_series disponible → hist_volatility_30d = último valor
  - Si iv_series disponible → impl_volatility = último valor
  - feature_relevance cargado de DB o default {k: 1.0}
- `compute_from_df(df)` → dict (compatible con _calc_indicators anterior para backtest)
- `compute_single_indicator(name, df)` → float|bool|None
- `classify_signal(rsi, macd_crossover, volume_ratio)` → str (migrado de preprocessor)
- `classify_multitimeframe(daily, hourly, minute)` → str (migrado de preprocessor)

**Migración preprocessor.py**:
- Importar `classify_signal, classify_multitimeframe` desde `app.analysis.indicators`
- Reexportar para backwards compat: `from app.analysis.indicators import classify_signal, classify_multitimeframe`
- `_calc_indicators` queda como alias de `compute_from_df` para no romper backtest

---

## Code Search

- [ ] `app/scanner/preprocessor.py` — funciones a migrar identificadas: `_calc_indicators`, `classify_signal`, `classify_multitimeframe`
- [ ] `app/backtest/engine.py` — importa `classify_signal, _calc_indicators` desde preprocessor → mantener alias
- [ ] `app/llm/agent.py` — usa RSI/MACD como floats sueltos → issue 005 lo refactoriza
- [ ] Tests existentes: `test_preprocessor.py` y `test_multitimeframe.py` usan `classify_signal` y `classify_multitimeframe` — deben seguir importando desde preprocessor (reexportado)

**Reuse decision**:
- Reuse as-is: IBKRClient thread-safe pattern (referencia), news.py Yahoo RSS fallback
- Extend: settings.py TTL constants
- Build new: IBDataLayer, IndicatorEngine con FeatureSet

---

## Reference Documents

| Document | Path | What to Extract |
|---|---|---|
| PRD | docs/dev/artifacts/dev-plan/08-prd.md | REQ-03 (IBDataLayer), REQ-04 (IndicatorEngine) con todos los ACs |
| Interface design | docs/dev/artifacts/dev-plan/06-interface-design.md | Firmas exactas de métodos |
| Architecture map | docs/dev/artifacts/dev-plan/03-architecture-map.md | Anti-pattern triplication, IBKRClient pattern |

---

## Acceptance Criteria

- [ ] AC-03.1: Dos llamadas `get_ohlcv("AAPL", "30 D", "1 day", "scanner")` en < 900s → segunda usa cache, 0 calls IB
- [ ] AC-03.2: `get_ohlcv(..., "trade_entry")` nunca usa cache
- [ ] AC-03.3: IB Gateway desconectado → retorna None, no lanza excepción
- [ ] AC-03.4: Con MockIBClient → todos los métodos retornan datos sintéticos válidos
- [ ] AC-04.1: `compute_features(symbol, df_daily=df30, df_hourly=None, ...)` → FeatureSet sin error, rs_vs_spy_30d=None
- [ ] AC-04.2: Mismos inputs → mismos outputs (determinístico)
- [ ] AC-04.3: `test_preprocessor.py` (6 tests) y `test_multitimeframe.py` (7 tests) pasan sin modificar los tests
- [ ] AC-04.4: `test_backtest_engine.py` (8 tests) pasan sin modificar los tests
- [ ] AC-04.5: `compute_single_indicator("rsi_14", df)` → float entre 0-100
- [ ] `pytest tests/test_preprocessor.py tests/test_multitimeframe.py tests/test_backtest_engine.py -v` → todos PASS

## Definition of Done

- [ ] Todos los ACs verificados
- [ ] `app/analysis/data.py` y `app/analysis/indicators.py` creados con tests propios >= 80% cobertura
- [ ] preprocessor.py migrado — `classify_signal` y `classify_multitimeframe` importados desde indicators, reexportados
- [ ] Tests de integración marcados `@pytest.mark.integration` para tests que requieren IB Gateway real
- [ ] Issue movido a `done/`
