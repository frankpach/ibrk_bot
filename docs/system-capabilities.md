# IBKR AI Trader — Capacidades del Sistema

> Estado: Paper Trading activo | Capital: ~$1,031,314 | IB Gateway: puerto 4002

---

## 1. Qué entrega IB Gateway preprocesado

### 1.1 Datos de mercado en tiempo real (via `reqMktData`)

| Campo | Descripción | Usado en |
|---|---|---|
| `last` | Último precio ejecutado | Precio de entrada/salida |
| `bid` / `ask` | Mejor oferta y demanda | Spread estimado |
| `marketPrice()` | Precio calculado por ib_insync (last o mid) | Señales, sizing |
| `close` | Cierre del día anterior | Referencia overnight |

**Latencia real:** ~200ms con datos delayed (MARKET_DATA_TYPE=3). Con cuenta live + suscripción: tiempo real.

### 1.2 Datos históricos OHLCV (via `reqHistoricalData`)

IB entrega barras históricas listas para calcular indicadores:

| Timeframe | Duración | Uso en el sistema |
|---|---|---|
| 1 day | 30 D | RSI diario, MACD, tendencia largo plazo |
| 1 hour | 5 D | Confirmación de tendencia intermedia |
| 5 mins | 1 D | Señal de entrada precisa |
| 1 day | 200+ D | SMA200, volatilidad histórica 30d |

**Caching:** IBDataLayer cachea resultados con TTL por contexto:
- `trade_entry`: 0s (siempre fresco)
- `on_demand`: 120s
- `scanner`: 900s (15 min)
- `backtest`: 3600s
- `fundamentals`: 86400s

### 1.3 Datos de contrato (via `reqContractDetails`)

Por cada instrumento IB entrega:

| Campo | Descripción | Cómo se usa |
|---|---|---|
| `tradingHours` | Horario total del exchange (incluyendo pre/post) | Scheduler sabe cuándo puede operar |
| `liquidHours` | Horario de mercado líquido oficial | Fuente de verdad para señales |
| `minTick` | Mínimo movimiento de precio | Sizing de órdenes precisas |
| `multiplier` | Valor por punto del contrato (futuros) | Cálculo de P&L en USD |
| `validExchanges` | Lista de exchanges donde se puede ejecutar | Routing de órdenes |
| `currency` | Divisa base del contrato | Conversión a USD para risk manager |

**Formato `liquidHours` que parsea el sistema:**
```
20260507:0930-20260507:1600;20260508:0930-20260508:1600;20260509:CLOSED
```

### 1.4 Datos de cuenta (via `accountSummaryAsync`)

| Tag IB | Descripción | Endpoint |
|---|---|---|
| `NetLiquidation` | Valor total de la cuenta en USD | `/account` |
| `BuyingPower` | Poder de compra disponible | `/account` |
| `TotalCashValue` | Cash disponible | `/account` |
| `AvailableFunds` | Fondos disponibles para margen | No expuesto aún |

### 1.5 Portfolio en tiempo real (via `ib.portfolio()`)

IB mantiene sync automático del portafolio:

```json
{
  "symbol": "AAPL",
  "quantity": 5,
  "avg_cost": 185.20,
  "market_value": 1438.75,
  "unrealized_pnl": 13.75
}
```

---

## 2. Qué preprocesa el sistema antes de llegar al LLM

### 2.1 IndicatorEngine (`app/analysis/indicators.py`)

Corre sobre DataFrames de IB y produce un `FeatureSet` completo:

| Indicador | Cómo se calcula | Interpretación |
|---|---|---|
| `rsi_14` | EMA de ganancias/pérdidas 14 periodos | <30 oversold, >70 overbought |
| `macd_line` / `macd_signal` | EMA12 - EMA26 / EMA9 del MACD | Momentum |
| `macd_crossover` | Bool: cruce en la última barra | Señal de cambio de tendencia |
| `atr_pct` | ATR14 / precio × 100 | Volatilidad en % para sizing |
| `sma20` / `sma50` / `sma200` | Medias móviles simples | Tendencia multi-plazo |
| `bollinger_upper/lower/position` | SMA20 ± 2σ, posición relativa | Rango de precio normalizado |
| `vwap` | Precio ponderado por volumen intraday | Referencia institucional |
| `volume_ratio_20d` | Volumen actual / media 20d | Confirmación de señal |
| `hist_volatility_30d` | Desviación estándar retornos 30d | Risk sizing |
| `impl_volatility` | IV de IB (si disponible) | Costo de opciones / riesgo |
| `rs_vs_spy_30d` | Retorno relativo vs SPY | Fortaleza relativa |
| `rs_vs_qqq_30d` | Retorno relativo vs QQQ | Fortaleza relativa tech |

### 2.2 QuantScorer (`app/analysis/scorer.py`)

Produce un **score 0-100** combinando 6 dimensiones con pesos configurables:

| Dimensión | Peso | Señales que usa |
|---|---|---|
| Momentum | 25% | RSI extremo, MACD crossover |
| Trend | 20% | SMA20 > SMA50 > SMA200, posición en Bollinger |
| Volume | 15% | volume_ratio_20d, VWAP |
| Volatility | 10% | ATR%, hist_volatility, impl_volatility |
| Portfolio fit | 15% | Correlación con posiciones actuales, diversificación |
| Sentiment | 15% | Noticias (via NewsAPI), contexto macro |

**Umbrales de recomendación:**
- 0-49 → `REJECTED`
- 50-69 → `WATCHLIST`
- 70-84 → `PROPOSE`
- 85-100 → `PRIORITY`

**Los multiplicadores se adaptan por símbolo** con cada trade cerrado (`SymbolParameter`), aprendiendo qué dimensiones predicen mejor para ese activo.

### 2.3 HardRules (`app/analysis/hard_rules.py`)

Gates deterministas que bloquean la entrada al LLM si se cumplen:

| Regla | Condición de bloqueo | Condición de warning |
|---|---|---|
| Liquidez | volume_ratio < 0.3 | volume_ratio < 0.7 |
| Earnings gate | Earnings en < 3 días | Earnings en < 7 días |
| Capital suficiente | units calculados = 0 | — |
| Correlación | Misma categoría ya en portfolio | — |

### 2.4 Preprocessor multi-timeframe (`app/scanner/preprocessor.py`)

Corre cada 15 min en horario de mercado. Para cada símbolo:

1. Descarga barras daily (30D) → clasifica señal diaria
2. Descarga barras hourly (5D) → clasifica señal horaria
3. Descarga barras 5min (1D) → clasifica señal de corto plazo
4. `classify_multitimeframe()` combina las 3:
   - Daily STRONG + cualquiera MEDIUM → `STRONG`
   - Daily MEDIUM + al menos una confirmación → `MEDIUM`
   - Solo daily → `WEAK` (ignorado)

Solo inserta en DB las señales STRONG o MEDIUM para procesamiento LLM.

---

## 3. Herramientas del sistema (lo que puede hacer)

### 3.1 API REST (`http://aiutox-pi:8088`)

#### Información
| Endpoint | Descripción | Output clave |
|---|---|---|
| `GET /health` | Estado de conexión a IB | `connected: true/false` |
| `GET /account` | Balance de cuenta | `net_liquidation`, `buying_power`, `cash_balance` |
| `GET /system/status` | Estado del sistema | `paused`, `mode`, `open_positions`, `daily_pnl_usd` |
| `GET /portfolio` | Posiciones abiertas en IB | `symbol`, `quantity`, `unrealized_pnl` |
| `GET /trades` | Trades abiertos en DB | `entry_price`, `stop_loss`, `take_profit` |
| `GET /trades/closed?limit=N` | Historial de trades | `pnl_usd`, `pnl_pct`, `exit_reason` |
| `GET /signals` | Señales técnicas pendientes | `symbol`, `strength`, `rsi`, `macd`, `volume_ratio` |
| `GET /price/{symbol}` | Precio en tiempo real via IB | `market_price`, `bid`, `ask` |
| `GET /price/free/{symbol}` | Precio sin IB (fallback) | Precio de fuente alternativa |
| `GET /allowed-symbols` | Universo activo | Lista de símbolos aprobados |
| `GET /universe/watchlist` | Watchlist con scores | `symbol`, `watchlist_score` |
| `GET /patterns/{symbol}` | Patrones aprendidos | Texto de patrón, win/loss count |
| `GET /candidate-decisions` | Historial de decisiones | Score, LLM summary, retornos futuros |
| `GET /symbol-parameters/{symbol}` | Parámetros adaptativos | SL/TP, multiplicadores por dimensión |
| `GET /backtest/{symbol}?days=N` | Backtest histórico | Win rate, P&L, profit factor, drawdown |
| `GET /analysis/indicator/{symbol}/{name}` | Indicador específico | Valor del indicador |
| `GET /market-permissions` | Exchanges/productos disponibles | Cache de discovery IB |

#### Ejecución
| Endpoint | Descripción | Validaciones |
|---|---|---|
| `POST /orders/preview` | Preview sin ejecutar | Risk validator completo |
| `POST /orders/place` | Ejecutar orden | Risk + horario + capital + max posiciones |
| `POST /orders/close/{symbol}` | Cerrar posición específica | — |
| `POST /orders/close-all` | Cerrar todas las posiciones | — |

#### Control del sistema
| Endpoint | Descripción |
|---|---|
| `POST /system/pause` | Detiene scanner y procesamiento |
| `POST /system/resume` | Reactiva el sistema |
| `POST /system/mode/paper\|live` | Cambia modo de operación |
| `POST /symbols/propose` | Propone nuevo símbolo |
| `POST /symbols/approve/{symbol}` | Aprueba símbolo propuesto |

### 3.2 MCP Tools (para Claude / LLM externo)

El servidor MCP en `app/mcp/server.py` expone el sistema como tools:

| Tool | Descripción |
|---|---|
| `get_price(symbol)` | Precio actual |
| `get_account()` | Estado de cuenta |
| `get_portfolio()` | Posiciones abiertas |
| `get_signals()` | Señales pendientes |
| `get_trades()` | Trades abiertos |
| `get_patterns(symbol)` | Patrones aprendidos |
| `get_allowed_symbols()` | Universo activo |
| `preview_order(symbol, action, qty, order_type, sl_pct, tp_pct)` | Preview con validación |
| `place_order(symbol, action, qty, order_type, sl_pct, tp_pct)` | Ejecutar orden |
| `propose_symbol(symbol, reason)` | Proponer símbolo |
| `candidate_analysis(symbol)` | Análisis completo AnalysisPipeline |
| `compute_indicator(symbol, indicator_name)` | Calcular indicador específico |
| `get_universe_watchlist()` | Universo con scores |

### 3.3 Telegram Bot (comandos disponibles)

| Comando | Función |
|---|---|
| `/estado` | Resumen completo: modo, P&L, posiciones |
| `/posiciones` | Posiciones abiertas con SL/TP |
| `/historial` | Últimas 5 operaciones con P&L |
| `/senales` | Señales técnicas pendientes |
| `/simbolos` | Universo activo |
| `/analizar SYMBOL` | Pipeline completo con LLM (score + narrativa) |
| `/proponer SYMBOL razon` | Agregar símbolo al universo |
| `/aprobar SYMBOL` | Confirmar símbolo propuesto |
| `/backtest SYMBOL [dias]` | Backtest histórico |
| `/mercados` | Exchanges y productos operables (cache IB) |
| `/mercados refresh` | Forzar redescubrimiento en IB |
| `/alerta SYMBOL 5%` | Alerta de precio por umbral |
| `/alertas` | Ver alertas activas |
| `/cerrar SYMBOL` | Cerrar posición |
| `/cerrar todo` | Cerrar todas las posiciones |
| `/pausar` / `/reanudar` | Control del scanner |
| `/modo paper\|live` | Cambiar modo |
| Mensaje libre | Consulta al LLM con contexto del sistema |

---

## 4. Jobs automáticos (scheduler APScheduler)

| Job | Frecuencia | Función |
|---|---|---|
| `scanner` | Cada 15 min (horario mercado US) | Escanea todos los símbolos del universo en 3 timeframes |
| `signal_processor` | Cada 15 min | Lee señales pendientes → LLM → orden |
| `position_manager` | Cada 2 min | Verifica SL/TP de trades abiertos |
| `circuit_breaker` | Cada 2 min | Para el sistema si P&L diario < -5% |
| `alert_checker` | Cada 2 min | Verifica alertas de precio activas |
| `gateway_watchdog` | Cada 5 min | Reconecta a IB si se cae |
| `daily_discovery` | Lu-Vi 8:00am ET | Descubrimiento y scoring de candidatos |
| `return_evaluator` | Diario 6:00am ET | Evalúa retornos reales vs decisiones pasadas |
| `market_permissions_daily` | Lu-Vi 7:50am ET | Redescubre exchanges/productos vía IB |
| `weekly_report` | Lunes 8:00am ET | Reporte semanal vía Telegram |
| `sunday_reminder` | Domingo 10:00pm ET | Recordatorio de re-autenticación IB |

---

## 5. Base de datos (SQLite `ibkr_trader.db`)

| Tabla | Qué almacena | Crece con |
|---|---|---|
| `signals` | Señales técnicas detectadas | Cada ciclo del scanner |
| `trades` | Trades abiertos y cerrados | Cada orden ejecutada |
| `decisions` | Decisiones LLM por señal | Cada análisis LLM |
| `patterns` | Patrones aprendidos por símbolo | Cada trade cerrado con resultado |
| `symbol_config` | Universo de símbolos aprobados | Aprobaciones manuales |
| `feature_snapshots` | Indicadores calculados por símbolo | Cada análisis del pipeline |
| `candidate_decisions` | Decisiones con retornos futuros | Daily discovery |
| `watchlist_scores` | Score compuesto por símbolo | Cada ciclo de evaluación |
| `symbol_parameters` | Parámetros SL/TP adaptativos | Cada trade cerrado |
| `alerts` | Alertas de precio activas | Comandos Telegram |
| `market_permissions` | Exchanges/productos disponibles | Job diario 7:50am |

---

## 6. Límites actuales del sistema

| Límite | Valor | Dónde se configura |
|---|---|---|
| Max posiciones simultáneas | 3 | `settings.py → MAX_POSITIONS` |
| Max riesgo por operación | 2% del capital | `settings.py → MAX_RISK_PCT` |
| Max USD por posición | $500 | `settings.py → MAX_POSITION_USD` |
| Capital simulado (risk calc) | $500 | `settings.py → SIMULATED_CAPITAL` |
| Circuit breaker | -5% P&L diario | `system/controller.py` |
| Market data | Delayed 15-20 min | `settings.py → MARKET_DATA_TYPE=3` |
| Universo activo | 10 símbolos US stocks | `settings.py → ALLOWED_SYMBOLS` |
| Horario de scanner | 09:15-16:15 ET Lu-Vi | `settings.py → MARKET_OPEN/CLOSE` |
| Modo actual | Paper (no dinero real) | `settings.py → PAPER_TRADING_ONLY` |

---

## 7. Lo que falta / no existe aún

| Capacidad | Estado | Bloqueante |
|---|---|---|
| Futuros (ES, NQ) | ❌ No implementado | IBDataLayer solo usa `Stock()` |
| Forex en scanner | ❌ No implementado | Preprocessor asume STK |
| Crypto en scanner | ❌ No implementado | Preprocessor asume STK |
| Market data tiempo real | ❌ Solo delayed | Requiere suscripción IB ~$10/mes |
| Horarios IB dinámicos | ❌ Hardcodeado US 9:30-16:00 | Pendiente parsear `liquidHours` |
| Opciones | ❌ No implementado | Greeks complejos |
| Multi-divisa P&L | ❌ Solo USD | Pendiente para EU/JP/AU stocks |
| `tzdata` en Pi | ❌ No instalado | Error al parsear zonas horarias IB |
| Read-Only en live | ⚠️ Activo | IB Gateway live tiene Read-Only mode activado |
