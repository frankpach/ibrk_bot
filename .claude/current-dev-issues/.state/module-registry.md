# Module Registry: dev-plan

**Module**: dev-plan
**Last Updated**: 2026-05-07

## This Module

**Name**: dev-plan
**Path**: ~/ibkr-bot/app/ (Raspberry Pi: aiutox-pi)
**Status**: in_development

## Architecture Layers

| Layer | Path | Status | Role |
|---|---|---|---|
| IBDataLayer | app/analysis/data.py | TO CREATE | Descarga OHLCV + scanner + datos IB para cualquier ticker |
| IndicatorEngine | app/analysis/indicators.py | TO CREATE | RSI/MACD/ATR/SMA/Bollinger/VWAP/RS — único lugar |
| QuantScorer | app/analysis/scorer.py | TO CREATE | Scoring ponderado 0-100, pesos por símbolo en DB |
| HardRules | app/analysis/hard_rules.py | TO CREATE | Earnings gate, liquidez, correlación — sin LLM |
| CandidateAdmissionFlow | app/analysis/admission.py | TO CREATE | Pipeline completo para símbolos fuera del universo |
| ParameterStore | app/db/ (nueva tabla) | TO CREATE | symbol_parameters, symbol_scorer_weights |
| DecisionMemory | app/db/ (nueva tabla) | TO CREATE | candidate_decisions con retorno futuro vs SPY |
| PostMortem (mejorado) | app/llm/postmortem.py | TO REFACTOR | Sugiere ajustes paramétricos atenuados |

## Related Modules (existentes, a migrar)

| Module | Path | Relación |
|---|---|---|
| preprocessor | app/scanner/preprocessor.py | Migrará a usar IndicatorEngine |
| backtest engine | app/backtest/engine.py | Migrará a usar IndicatorEngine |
| agent | app/llm/agent.py | Migrará a recibir FeatureVector |
| telegram_bot | app/notifications/telegram_bot.py | /analizar usará CandidateAdmissionFlow |
| IB Discovery | run.py scheduler | Agregará IB Scanner diario 8am ET |
