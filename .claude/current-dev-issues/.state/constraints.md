# Constraints: dev-plan

**Module**: dev-plan
**Last Updated**: 2026-05-07

## Global Rules

- Sistema corre en Raspberry Pi 5 (8GB RAM, ARM64, Debian 13)
- IB Gateway en puerto 4002, paper trading mode
- FastAPI en puerto 8088, accesible via Tailscale (100.92.245.100)
- LLM: OpenCode via subprocess (opencode-go/qwen3.5-plus) — sin API key externa
- Capital simulado: $500 — riesgo máximo 2% por operación
- Máximo 3 posiciones simultáneas
- Motor de riesgo determinístico irrompible (app/risk/validator.py)
- LLM interpreta, NO decide numéricamente
- Reglas duras no bypasseables por ningún agente

## Module-Specific Constraints

- IBDataLayer debe usar el IBKRClient thread-safe existente (app/ibkr/client.py)
- IB Scanner disponible: HOT_BY_VOLUME, TOP_PERC_GAIN, MOST_ACTIVE
- IB entrega OHLCV + historical volatility + implied volatility + news — NO indicadores precalculados
- Indicadores (RSI/MACD/ATR/etc.) siempre calculados desde barras OHLCV
- IndicatorEngine debe ser el único lugar donde se calculan indicadores (hoy están duplicados en preprocessor, backtest/engine, agent)
- Ajustes paramétricos por símbolo: atenuados (learning_rate), con límites duros
- SL nunca < 0.5% ni > 8% sin aprobación humana
- Pesos del scorer no pueden desviarse > 50% del default global

## Module Dependencies

- app/ibkr/client.py — IBKRClient (existente, no modificar)
- app/risk/validator.py — motor de riesgo (existente, no modificar)
- app/db/database.py — capa de datos (extender con nuevas tablas)
- app/scanner/preprocessor.py — migrar para usar IndicatorEngine
- app/backtest/engine.py — migrar para usar IndicatorEngine
- app/llm/agent.py — migrar para recibir FeatureVector estructurado
- app/notifications/telegram_bot.py — /analizar usa CandidateAdmissionFlow
