# Architecture Map: dev-plan

**Status**: ✓ Complete  
**Date**: 2026-05-07  
**Phase**: 1 (Architecture Discovery)  
**Module**: dev-plan  

---

## Existing Models

### Signal (app/db/models.py)
- **Purpose**: Señal técnica detectada por el scanner — RSI, MACD, volume_ratio
- **Key fields**: id, symbol, strength (STRONG/MEDIUM/WEAK), rsi, macd, volume_ratio, extra_indicators (JSON str), created_at, processed
- **Used by**: preprocessor (insert), loop.py (consume), main.py (GET /signals)
- **Gap**: Solo guarda 3 indicadores básicos. No guarda ATR, Bollinger, SMA, RS_vs_SPY. El nuevo IndicatorEngine debe enriquecer este modelo o crear FeatureSnapshot paralelo.

### Trade (app/db/models.py)
- **Purpose**: Operación de compra/venta — entrada, SL, TP, resultado
- **Key fields**: id, symbol, action, entry_price, stop_loss_price, take_profit_price, stop_loss_pct, take_profit_pct, signal_strength, llm_justification, status, pnl_usd, pnl_pct, exit_reason
- **Used by**: main.py (insert/close), positions/manager.py (monitor), postmortem.py (analysis)
- **Gap**: No guarda el FeatureVector completo al momento de entrada. Si queremos saber "¿con qué condiciones exactas entramos?", hoy no podemos saberlo. Necesita campo `feature_snapshot_id` FK a nueva tabla.

### Pattern (app/db/models.py)
- **Purpose**: Patrón aprendido por el LLM post-mortem — texto libre
- **Key fields**: id, symbol, pattern_text (free text), win_count, loss_count, created_at, updated_at
- **Used by**: postmortem.py (insert), agent.py (read via get_patterns_for_symbol)
- **Gap crítico**: Texto libre — no se puede hacer estadística sobre él. Necesita estructura. La nueva tabla `symbol_parameters` con valores numéricos reemplaza/complementa esto para el aprendizaje cuantitativo.

### SymbolConfig (app/db/models.py)
- **Purpose**: Símbolos del universo — aprobados o pendientes
- **Key fields**: symbol (PK), extra_indicators (JSON), approved (bool), proposed_by, created_at
- **Used by**: database.py (get_approved_symbols), main.py (/symbols/approve)
- **Extensión necesaria**: Agregar campo `category` (etf/blue_chip/growth), `watchlist_score`, `last_evaluated_at` para el universo dinámico.

### Decision (app/db/models.py)
- **Purpose**: Log de cada llamada al LLM con contexto y resultado
- **Key fields**: id, signal_id, symbol, llm_model, prompt_summary, response (text), action, stop_loss_pct, take_profit_pct, created_at
- **Used by**: agent.py (insert), main.py (/decisions — no existe aún)
- **Gap**: `response` es texto libre. No tiene quant_score ni feature_snapshot. La nueva `CandidateDecision` será el equivalente estructurado para el DecisionMemory.

---

## Existing Components (Python modules)

### IBKRClient (app/ibkr/client.py)
- **Purpose**: Wrapper thread-safe sobre ib_insync. Todos los calls IB van por aquí.
- **Pattern**: Dedicated thread+loop. `_run_sync(coro)` para cualquier operación.
- **Methods**: get_stock_price, get_account, get_portfolio, place_order, disconnect
- **Gap**: No tiene `fetch_historical_bars`, `fetch_historical_volatility`, `run_scanner`. El IBDataLayer los agrega como wrapper encima de IBKRClient sin modificarlo.
- **Anti-pattern detectado**: `client_id=11` hardcodeado en main.py para evitar conflicto con run.py (client_id=10). Esto es frágil — el IBDataLayer debe usar un client_id separado configurable via .env.

### RiskValidator (app/risk/validator.py)
- **Purpose**: Validación determinística de órdenes. Irrompible.
- **Methods**: `validate_order()` → ValidationResult
- **Status**: COMPLETO, NO MODIFICAR. Es la capa de seguridad final.
- **Nota**: Valida `ALLOWED_SYMBOLS` — el CandidateAdmissionFlow opera sobre símbolos NO en esa lista, por eso /price/free/{symbol} existe.

### Preprocessor (app/scanner/preprocessor.py)
- **Purpose**: Scanner multi-timeframe. Calcula RSI+MACD+volume, clasifica señales.
- **Functions**: `_calc_indicators(df)`, `classify_signal()`, `classify_multitimeframe()`, `_fetch_bars()`, `scan_symbol()`, `run_scan()`
- **Gap crítico**: `_calc_indicators` duplicado en backtest/engine.py (importado) y replicado conceptualmente en agent.py (que recibe los valores). La función pública `_calc_indicators` tiene prefijo `_` (privada) pero backtest la importa directamente — violación de encapsulamiento.
- **Migración**: Mover `_calc_indicators`, `classify_signal`, `classify_multitimeframe` a `app/analysis/indicators.py`. Preprocessor importa de ahí.

### BacktestEngine (app/backtest/engine.py)
- **Purpose**: Simulación histórica de la estrategia.
- **Functions**: `apply_signals_to_df()`, `simulate_trades()`, `calculate_metrics()`, `run_backtest()`
- **Gap**: Importa `classify_signal, _calc_indicators` directamente desde preprocessor. Solo usa barras daily — no multi-timeframe. Cuando IndicatorEngine esté listo, el backtest será más rico automáticamente.

### LLMAgent (app/llm/agent.py)
- **Purpose**: Análisis LLM via OpenCode subprocess.
- **Key vars**: `OPENCODE_BIN = "/home/frankpach/.opencode/bin/opencode"` — HARDCODEADO. Necesita ir a .env como `OPENCODE_BIN`.
- **Functions**: `_call_opencode()`, `_get_context()`, `analyze_signal()`, `get_symbol_category()`, `get_strategy_context()`
- **Gap crítico**: `_get_context()` hace 3 calls HTTP a FastAPI (price, portfolio, account) + 1 call DB (patterns) + 1 RSS (news). El LLM recibe texto semiestructurado, no JSON de features. Con IndicatorEngine, recibirá FeatureVector estructurado completo.
- **Gap**: `SYMBOL_CATEGORIES` y `STRATEGY_CONTEXTS` hardcodeados. Con SymbolConfig.category en DB, se vuelve dinámico.

### PostMortem (app/llm/postmortem.py)
- **Gap crítico**: Usa `openai.OpenAI` SDK con `LLM_API_KEY` que está vacío. No usa OpenCode. Esto es un bug — el postmortem nunca ha corrido en producción porque `LLM_API_KEY` no está configurado. Debe migrarse a `_call_opencode()` como el agent.py.
- **Gap**: Solo extrae una frase de texto libre. No sugiere ajustes paramétricos estructurados ni actualiza `symbol_parameters`.

### SignalLoop (app/llm/loop.py)
- **Purpose**: Procesa señales pendientes → LLM → orden.
- **Gap**: No tiene watchdog interno. Si el LLM call se cuelga, el loop queda bloqueado indefinidamente para esa señal.

### MCPServer (app/mcp/server.py)
- **Purpose**: Expone tools MCP para OpenCode/Claude.
- **Gap**: `get_price` solo funciona para ALLOWED_SYMBOLS. La nueva tool `get_price_free` y `candidate_analysis` deben agregarse al MCP para que el LLM pueda llamarlas directamente.

---

## Event Catalog

Este sistema no usa pub/sub — usa APScheduler + llamadas síncronas directas. No hay bus de eventos.

### "Eventos" actuales (jobs en scheduler)
- `scanner` (cada 15 min) → `run_scan(ib_client)` → inserta en `signals` table
- `signal_processor` (cada 15 min) → `process_pending_signals()` → consume `signals` table
- `position_manager` (cada 2 min) → `check_positions()` → cierra trades según SL/TP
- `circuit_breaker` (cada 2 min) → `check_circuit_breaker()` → pausa si pérdida > 5%
- `alert_checker` (cada 2 min) → `check_all_alerts()` → notifica alertas de precio
- `weekly_report` (lunes 8am ET) → `send_weekly_report()`
- `sunday_reminder` (domingo 10pm ET) → notificación re-auth IB
- `gateway_watchdog` (cada 5 min) → reconecta IB si se desconecta

### Nuevos jobs necesarios (gaps)
- `daily_discovery` (8am ET, días de mercado) → IB Scanner → CandidateAdmissionFlow batch
- `return_evaluator` (diario) → evalúa retornos 7/30/90d de candidate_decisions vs SPY
- `universe_rotation` (integrado en daily_discovery) → actualiza watchlist_score, rota top 10

---

## Core Services

### FastAPI (app/api/main.py — 480 líneas)
- **Endpoints**: 23 endpoints actuales
- **Anti-pattern detectado**: main.py tiene 480 líneas — demasiado grande. Mezcla routing, business logic y DB calls directos. La refactorización natural es separar en routers: `api/routers/trading.py`, `api/routers/system.py`, `api/routers/analysis.py`. Pero esto es out of scope para dev-plan — lo anoto como deuda técnica.
- **Gap**: Falta `GET /candidate-analysis/{symbol}`, `GET /analysis/indicator/{symbol}/{name}`, `GET /universe/watchlist`

### Notifications (app/notifications/telegram.py + telegram_bot.py)
- **telegram.py**: `notify(message)` — wrapper simple
- **telegram_bot.py**: 435 líneas, todos los comandos
- **Gap**: No tiene `progress_update(analysis_id, step, message)` para streaming de análisis. Necesita función que edite el mensaje anterior vs enviar nuevo.

### SystemController (app/system/controller.py)
- **Purpose**: pause/resume/mode/circuit_breaker
- **Status**: Completo, funcional
- **Gap**: No tiene método para registrar/desregistrar jobs dinámicamente (necesario para daily_discovery que solo corre en días de mercado).

---

## Gaps (What's Missing)

### New Tables (SQLite)

- [ ] **feature_snapshots**: OHLCV processed + todos los indicadores al momento del análisis. Fields: id, symbol, timestamp, timeframe, rsi_14, macd_line, macd_signal, macd_crossover, atr_pct, sma20, sma50, sma200, bollinger_upper, bollinger_lower, bollinger_position, vwap, volume_ratio_20d, hist_volatility_30d, impl_volatility, rs_vs_spy_30d, rs_vs_qqq_30d, raw_bars_json (opcional, para audit). TTL: 24h para reutilización.

- [ ] **symbol_parameters**: Parámetros adaptativos por símbolo. Fields: symbol (PK), stop_loss_pct, take_profit_pct, min_profit_pct, momentum_weight, trend_weight, volume_weight, volatility_weight, portfolio_fit_weight, version, previous_json, updated_at, trade_count (para ventana mínima).

- [ ] **candidate_decisions**: DecisionMemory para retorno futuro. Fields: id, symbol, date, decision (REJECTED/WATCHLIST/PROPOSE/PRIORITY), price_at_decision, quant_score, feature_snapshot_id, llm_summary, future_return_7d, future_return_30d, future_return_90d, alpha_vs_spy_7d, alpha_vs_spy_30d, evaluated_at.

- [ ] **watchlist_scores**: Score dinámico por símbolo para rotación del universo. Fields: symbol, signal_quality_score, admission_score, trade_history_score, watchlist_score, last_updated.

### New Modules

- [ ] **app/analysis/data.py** — IBDataLayer: descarga OHLCV, HV, IV, noticias IB, scanner. Cache TTL diferenciado. MockIBClient para tests locales.

- [ ] **app/analysis/indicators.py** — IndicatorEngine: RSI14, MACD, ATR%, SMA20/50/200, Bollinger, VWAP, Volume Profile, RS vs SPY/QQQ. Plugin registry. `compute(symbol, ib_client)` → FeatureSnapshot. `compute_from_df(df)` → dict (para backtest).

- [ ] **app/analysis/scorer.py** — QuantScorer: scoring 0-100 ponderado. `score(features, symbol)` → QuantScore. `get_weights(symbol)` → global * symbol_multiplier. `update_weights_attenuated(symbol, suggestion, confidence)`.

- [ ] **app/analysis/hard_rules.py** — HardRules determinísticas: earnings gate, liquidez, correlación, capital disponible. Sin LLM. `check_all(symbol, features, portfolio)` → HardRulesResult.

- [ ] **app/analysis/admission.py** — CandidateAdmissionFlow: orquesta data→indicators→score→hard_rules→LLM. `analyze(symbol, ib_client, notify_progress=False)` → AdmissionResult. Con watchdog interno 10 min.

- [ ] **app/analysis/mock_client.py** — MockIBClient: mismo interface que IBKRClient pero sin conexión IB. Retorna datos sintéticos determinísticos para tests locales.

### Config gaps

- [ ] `settings.py`: `IB_HOST` hardcoded a `127.0.0.1` — debe ser `os.getenv("IB_HOST", "127.0.0.1")` para que desarrollo local apunte a Pi via Tailscale.
- [ ] `settings.py`: `OPENCODE_BIN` no existe como setting — está hardcodeado en agent.py y telegram_bot.py en dos lugares. Debe ser `os.getenv("OPENCODE_BIN", "/home/frankpach/.opencode/bin/opencode")`.
- [ ] `settings.py`: `API_BASE` hardcodeado en 7 archivos diferentes (`http://127.0.0.1:8088`). Debe ser `os.getenv("API_BASE", "http://127.0.0.1:8088")` en settings, importado donde se necesite.
- [ ] `settings.py`: `IB_MOCK = os.getenv("IB_MOCK", "false")` para activar MockIBClient.
- [ ] `.env`: Agregar `IB_HOST`, `OPENCODE_BIN`, `API_BASE`, `IB_MOCK`, `OPENCODE_MODEL`.

---

## Anti-Patterns Detected

### Anti-Pattern 1: Logic Triplication [CLEAR]
**Finding**: `_calc_indicators(df)` calculando RSI+MACD+volume existe en `preprocessor.py` (definido), `backtest/engine.py` (importado como `_calc_indicators` — función privada!), y `agent.py` (recibe los valores via texto). Cualquier mejora a los indicadores debe hacerse 3 veces.
**Resolution**: Mover a `app/analysis/indicators.py` como función pública. Preprocessor y backtest importan desde ahí.

### Anti-Pattern 2: Hardcoded Infrastructure [CLEAR]
**Finding**: `API_BASE = "http://127.0.0.1:8088"` en 7 archivos. `OPENCODE_BIN = "/home/frankpach/.opencode/bin/opencode"` en 2 archivos. `IB_HOST = "127.0.0.1"` en settings (no via env).
**Resolution**: Centralizar en `settings.py` via `os.getenv()`. Desarrollo local usa `.env.local` con valores diferentes.

### Anti-Pattern 3: Dead PostMortem [CLEAR]
**Finding**: `postmortem.py` usa `openai.OpenAI` con `LLM_API_KEY` que está vacío en `.env`. El postmortem nunca ha corrido realmente en producción. El Pattern text en DB viene de tests manuales, no del sistema real.
**Resolution**: Migrar `postmortem.py` a usar `_call_opencode()` como agent.py. Eliminar la dependencia de openai SDK para esta función.

### Anti-Pattern 4: Private Function Cross-Import [CLEAR]
**Finding**: `from app.scanner.preprocessor import classify_signal, _calc_indicators` en `backtest/engine.py`. Importar una función con prefijo `_` desde otro módulo viola encapsulamiento y crea acoplamiento frágil.
**Resolution**: Hacer `_calc_indicators` pública en `IndicatorEngine` y exportarla limpiamente.

### Anti-Pattern 5: Missing Progress Visibility [CLEAR]
**Finding**: `loop.py` llama `analyze_signal()` que puede tardar 30-60s. El usuario recibe "Consultando al LLM..." y luego silencio. Si el LLM call falla, el error solo va a logs — no hay timeout ni notificación de fallo.
**Resolution**: Watchdog interno en `analyze_signal()` y `CandidateAdmissionFlow`. Progress streaming via Telegram. Timeout por paso.

### Anti-Pattern 6: Pub/Sub Bypass [NOT APPLICABLE]
**Finding**: No hay pub/sub en este sistema — todo es llamadas directas y polling via scheduler. Es correcto para un sistema single-process en Pi.

---

## Archaeology Notes

- **IBKRClient usa client_id=10 (run.py) y 11 (main.py)** — esto es un hack para evitar conflicto. El IBDataLayer debe usar client_id=12 (o configurable via .env: `IB_CLIENT_ID_DATA`).
- **SQLite en modo WAL** — correcto para lecturas concurrentes. No necesita cambio.
- **95 tests pasando** — buena base. MockIBClient permitirá agregar tests para todos los nuevos módulos sin IB Gateway.
- **APScheduler BackgroundScheduler** — no es cron nativo, es in-process. Si el proceso muere, los jobs mueren. Systemd como watchdog externo es la solución correcta (ya planificado).
- **OpenCode via subprocess** — correcto para evitar bloqueos asyncio. El timeout de 60s en `_call_opencode()` es el único control de latencia hoy.
- **news.py usa Yahoo RSS** — funcional pero ruidoso. Con `reqHistoricalNews()` de IB disponible, se puede mejorar. Mantener Yahoo RSS como fallback.
- **MCP server** — bien diseñado, el único que tiene un cliente HTTP limpio. El patrón `_get(path)` / `_post(path, data)` con `API_BASE` es el que debería usarse en todos lados.

---

## Decisions for Phase 2

- [ ] ¿Feature_snapshots como tabla separada o como campo JSON en signals/trades?
- [ ] ¿IndicatorEngine como clase singleton o como funciones puras?
- [ ] ¿CandidateAdmissionFlow como endpoint FastAPI o como función interna llamada por el bot?
- [ ] ¿Cómo maneja el MockIBClient la variabilidad de mercado? ¿Datos fijos o generados con semilla?
- [ ] ¿La rotación del universo es automática o requiere confirmación de Frank?

---

**Document Version**: 1.0  
**Created by**: discover-codebase (Phase 1)  
**Reviewed by**: Claude + Frank
