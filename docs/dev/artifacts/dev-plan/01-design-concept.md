# Design Concept: dev-plan — IBKR AI Trader Feature-Centric Architecture

**Status**: ✓ Complete  
**Date**: 2026-05-07  
**Module**: dev-plan  

---

## Problem Statement

> "El sistema actual es prompt-centric: el LLM recibe 3 números (RSI, MACD, volumen) y texto libre, y debe simultáneamente calcular, interpretar y decidir. Los indicadores están duplicados en 3 lugares del código. Solo se vigilan 10 símbolos fijos y nunca se descubren oportunidades en el resto del mercado. No hay validación de si las decisiones del sistema fueron correctas en retrospectiva. Cuando el usuario pide un análisis no sabe si está corriendo o si se trabó."

---

## Solution

> Un sistema feature-centric donde los datos se descargan una vez con TTL diferenciado, todos los indicadores se calculan en un único IndicatorEngine compartido, un QuantScorer produce un score numérico antes de llamar al LLM, el IB Scanner descubre candidatos diariamente en todo el mercado, y el aprendizaje retroalimenta los parámetros por símbolo de forma atenuada. El LLM solo interpreta evidencia estructurada — nunca calcula ni decide numéricamente.

---

## Key Personas

### Persona 1: Frank — Trader / Operator
- **Who**: Dueño y operador del sistema. Conoce trading, quiere supervisión sin microgestión.
- **Device**: iPhone (Telegram), PC Windows (desarrollo local), Raspberry Pi (producción)
- **Environment**: Móvil principalmente, PC para desarrollo
- **Goal**: Ver qué está pasando, recibir análisis cuando hay oportunidad, confiar en que el sistema no tomará malas decisiones solo
- **Biggest constraint**: Tiempo — quiere respuestas rápidas con progreso visible, no silencio

### Persona 2: Sistema Autónomo — El Bot
- **Who**: El proceso corriendo en la Pi que escanea, analiza y opera
- **Device**: Raspberry Pi 5, 8GB RAM, Debian 13
- **Environment**: 24/7, conectado a IB Gateway y Telegram
- **Goal**: Detectar oportunidades reales, operar con disciplina, aprender de cada trade
- **Biggest constraint**: Latencia de OpenCode (~30-60s por call LLM), rate limits de IB API

### Persona 3: LLM — Analista Interpretativo
- **Who**: OpenCode qwen3.5-plus actuando como analista narrativo
- **Device**: subprocess en la Pi
- **Environment**: Llamado solo cuando hay evidencia estructurada pre-procesada
- **Goal**: Explicar el score, identificar riesgos no cuantificables, sugerir ajustes paramétricos atenuados
- **Biggest constraint**: No debe calcular ni decidir — solo interpreta JSON de features

---

## Constraints

### Timeline
- **Due date**: Sin restricción
- **Estimated effort**: 4-6 semanas (implementación completa en iteración única)
- **Blocking issues**: Ninguno — sistema actual sigue funcionando durante el desarrollo

### Technical
- **Plataforma**: Raspberry Pi 5, ARM64, Debian 13, Python 3.13
- **IB Gateway**: Puerto 4002 paper trading, suscripción US stocks activa
- **LLM**: OpenCode via subprocess, modelo opencode-go/qwen3.5-plus
- **DB**: SQLite (existente) — nuevas tablas: feature_snapshots, symbol_parameters, candidate_decisions
- **Desarrollo**: Local en Windows, IB Gateway en Pi via Tailscale (IB_HOST en .env)
- **Config**: Todo via .env — IB_HOST, IB_PORT, IB_MOCK para desarrollo local
- **Cache**: TTL diferenciado — 2 min análisis on-demand, 15 min scanner, 0 trade entry, 24h fundamentals
- **MockIBClient**: Para desarrollo local sin necesidad de IB Gateway conectado

### Business
- **Capital simulado**: $500, regla del 2% de riesgo por operación
- **Límites duros irrompibles**: SL 0.5%-8%, pesos scorer ±50% del global, max 3 posiciones
- **Success metrics**:
  - Win rate sistema > 55% después de 50 trades
  - Score promedio de trades ganadores > score de trades perdedores
  - Tiempo de análisis on-demand < 90 segundos con progreso visible
  - Cero fallos silenciosos — todo error notificado por Telegram

---

## Scope: In vs Out

### In Scope

**IBDataLayer**
- Descarga OHLCV (daily 180d, hourly 5d) para cualquier ticker via IB
- TTL diferenciado por contexto de uso
- `HISTORICAL_VOLATILITY` e `OPTION_IMPLIED_VOLATILITY` como series de tiempo via IB
- IB Scanner: HOT_BY_VOLUME, TOP_PERC_GAIN, MOST_ACTIVE — 8am ET días de mercado
- Noticias via `reqHistoricalNews()` de IB (más confiable que Yahoo RSS)
- Earnings gate: `reqFundamentalData("CalendarReport")` → fallback Yahoo Finance → fallback "unknown"
- MockIBClient para desarrollo local

**IndicatorEngine**
- RSI 14, MACD, ATR%, SMA20/50/200, Bollinger Bands, VWAP, Volume Profile
- Relative Strength vs SPY y QQQ (30d)
- Historical Volatility (de IB), Implied Volatility (de IB)
- Registro dinámico: cada indicador es un plugin, fácil de agregar
- Solicitud on-demand de indicador individual usando cache de barras existente
- Feature relevance por símbolo: sistema aprende qué indicadores importan para cada uno

**QuantScorer**
- Scoring 0-100 con dimensiones: momentum, trend, volume, volatility, portfolio_fit, sentiment
- Pesos globales como hipótesis inicial — ajustables por símbolo via multiplicadores (0.5x-1.5x)
- Ventana mínima de 5 trades antes de activar ajuste de pesos por símbolo
- Thresholds: 0-49 RECHAZADO, 50-69 WATCHLIST, 70-84 PROPONER, 85-100 PRIORIDAD ALTA

**HardRules (determinísticas, sin LLM)**
- Earnings en < 3 días → bloqueo
- Liquidez mínima (volumen > 500k acciones/día)
- Correlación con posiciones actuales < 0.85
- Capital disponible suficiente para position size mínimo (1 acción)

**CandidateAdmissionFlow** (= AnalysisFlow = TradeDecisionFlow)
- Mismo pipeline para: análisis on-demand, scan automático, evaluación de admisión
- Solo cambia el threshold y la acción final
- Watchdog interno: timeout 10 minutos total, notifica paso donde se trabó
- Progress streaming: cada paso envía update a Telegram

**Universo Dinámico (Top 10)**
- watchlist_score por símbolo (signal_quality 0.4, admission_score 0.3, trade_history 0.3)
- IB Scanner diario alimenta rotación: si candidato score > 75 y peor del universo < 40 → rota
- Notificación Telegram cuando hay rotación del universo

**DecisionMemory**
- Guarda: symbol, date, decision, price, quant_score, llm_summary
- Job diario evalúa retorno real vs SPY a 7/30/90 días
- ReturnEvaluator ajusta thresholds del scorer (determinístico, sin LLM)

**ParameterStore + Adaptive Learning**
- symbol_parameters: SL%, TP%, min_profit%, pesos scorer por símbolo
- PostMortem LLM sugiere ajustes, sistema aplica atenuados: `new = old + (suggestion * confidence * 0.15)`
- Versionado: guarda versión anterior para poder revertir
- Notificación Telegram en cada ajuste aplicado
- Límites duros irrompibles

**Heartbeat externo**
- Uptime Kuma en Pi monitoreando health endpoint y puerto 4002
- Alertas Telegram si cualquier servicio cae
- Dashboard en http://100.92.245.100:3001 via Tailscale
- Fallback: cron en Pi como backup si Uptime Kuma cae

### Out of Scope

- LangGraph ni múltiples LLM calls en paralelo
- Debate multi-ronda entre agentes
- ML ranking model (fase futura después de acumular datos suficientes)
- Opciones trading (puts/calls) — solo stocks por ahora
- Live trading — solo paper trading en esta versión
- Mobile app nativa

**Por qué out of scope:**
> El sistema actual funciona y genera datos de aprendizaje. El objetivo es hacerlo feature-centric y robusto primero, antes de agregar ML o opciones. LangGraph agrega complejidad de infraestructura que no se justifica en la Pi con el LLM actual.

---

## Open Questions

- [ ] ¿El IB Scanner con datos delayed retorna candidatos útiles o muy rezagados para swing trading?
  - *Implication*: Determina si el scanner diario es viable o necesitamos fuente alternativa
- [ ] ¿reqFundamentalData("CalendarReport") está disponible con IBKR Pro sin suscripción adicional?
  - *Implication*: Si no → fallback Yahoo Finance become primary
- [ ] ¿Cuántos trades necesita acumular el sistema antes de que el adaptive learning sea estadísticamente significativo?
  - *Implication*: Define cuándo cambiar de "aprendizaje activo" a "producción confiable"
- [ ] ¿El MockIBClient debe generar datos sintéticos determinísticos o aleatorios con semilla?
  - *Implication*: Tests reproducibles vs tests más realistas

---

## Assumptions

- [x] IB Gateway siempre corre en la Pi — IBDataLayer asume conexión disponible (con retry)
- [x] OpenCode qwen3.5-plus es suficiente para interpretación narrativa — no se necesita modelo más potente
- [x] SQLite es suficiente para el volumen de datos esperado (< 10k trades/año)
- [x] Tailscale garantiza conectividad Windows ↔ Pi para desarrollo local
- [x] learning_rate=0.15 es moderado y apropiado — ajustable via .env si se necesita cambiar
- [x] Top 10 símbolos en universo es el límite operativo correcto con $500 capital simulado
- [ ] IB Scanner retorna resultados con delayed data — por confirmar con datos reales

---

## Success Criteria

- [ ] **Pipeline unificado**: preprocessor, backtest y agent usan el mismo IndicatorEngine — cero duplicación
- [ ] **Análisis completo en < 90s**: con progress visible en Telegram, watchdog de 10 min
- [ ] **Universo dinámico**: IB Scanner rota símbolos automáticamente, notifica cambios
- [ ] **Decisiones auditables**: cada decisión tiene FeatureVector completo guardado en DB
- [ ] **Aprendizaje verificable**: DecisionMemory muestra retorno real vs SPY para decisiones pasadas
- [ ] **Parámetros adaptativos**: symbol_parameters muestran divergencia del global después de 20+ trades
- [ ] **Heartbeat activo**: Uptime Kuma alertando en < 5 min si algún servicio cae
- [ ] **Desarrollo local funciona**: MockIBClient permite correr toda la suite de tests sin Pi conectada

---

## Related Modules (existentes)

- **app/scanner/preprocessor.py** — migrará a usar IndicatorEngine
- **app/backtest/engine.py** — migrará a usar IndicatorEngine
- **app/llm/agent.py** — migrará a recibir FeatureVector JSON
- **app/llm/postmortem.py** — extender con sugerencias de ajuste paramétrico
- **app/risk/validator.py** — sin cambios, límites duros irrompibles
- **app/ibkr/client.py** — IBDataLayer lo envuelve, sin modificar
- **app/notifications/telegram_bot.py** — /analizar usa CandidateAdmissionFlow con progress

---

## Architecture Overview

```
IBDataLayer (cache TTL diferenciado)
    ↓
IndicatorEngine (plugin registry, feature relevance por símbolo)
    ↓
QuantScorer (pesos globales + multiplicadores por símbolo)
    ↓
HardRules (determinístico, sin LLM)
    ↓ solo si pasa
LLM Interpretation (OpenCode — narra, contextualiza, sugiere ajustes)
    ↓
Decision + DecisionMemory
    ↓
ReturnEvaluator (7/30/90d vs SPY → ajusta thresholds)
    ↓
ParameterStore (ajustes atenuados por símbolo, versionados)
```

---

## Next Steps

1. Verificar open questions con datos reales de IB
2. `/clear` contexto
3. Phase 1: `/120-architecture dev-plan`

---

## Sign-Off

| Role | Name | Date | Sign-Off |
|------|------|------|----------|
| Trader / Owner | Frank | 2026-05-07 | ✓ |
| Engineering | Claude | 2026-05-07 | ✓ |

---

**Document Version**: 1.0  
**Last Updated**: 2026-05-07  
**Approved**: ✓ Yes
