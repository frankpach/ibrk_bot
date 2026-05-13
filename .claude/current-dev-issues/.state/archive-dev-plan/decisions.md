# Decisions Log: dev-plan

**Module**: dev-plan
**Last Updated**: 2026-05-07

## D-001: IndicatorEngine como módulo compartido único
**Decision**: Crear app/analysis/indicators.py como el único lugar donde se calculan indicadores técnicos. Preprocessor, backtest y agent lo importan.
**Reason**: Hoy los indicadores están duplicados en 3 lugares. Cualquier mejora debe hacerse 3 veces.
**Date**: 2026-05-07

## D-002: IB no entrega indicadores precalculados
**Decision**: Siempre calcular RSI/MACD/ATR desde barras OHLCV. IB sí entrega historical_volatility e implied_volatility como series de tiempo.
**Reason**: Investigación confirma que TWS API no tiene endpoint de indicadores.
**Date**: 2026-05-07

## D-003: IB Scanner como capa de descubrimiento diario
**Decision**: Usar reqScannerData(HOT_BY_VOLUME / TOP_PERC_GAIN / MOST_ACTIVE) cada mañana 8am ET para descubrir candidatos fuera del universo base.
**Reason**: Hoy solo se escanean 10 símbolos fijos. El mercado tiene oportunidades que nunca se detectan.
**Date**: 2026-05-07

## D-004: LLM como intérprete, no como calculador
**Decision**: El LLM recibe FeatureVector JSON estructurado con todos los indicadores ya calculados. El LLM narra, contextualiza y sugiere ajustes. NO calcula ni decide numéricamente.
**Reason**: LLM que infiere RSI desde precios comete errores. LLM que interpreta evidencia estructurada es más confiable.
**Date**: 2026-05-07

## D-005: Ajustes paramétricos atenuados por símbolo
**Decision**: PostMortem LLM puede sugerir cambios a SL%, TP%, pesos del scorer por símbolo. Se aplican atenuados: new_param = old_param + (suggestion * confidence * learning_rate). Límites duros irrompibles.
**Reason**: TSLA necesita diferentes parámetros que SPY. El sistema debe aprender esto de la experiencia.
**Date**: 2026-05-07

## D-006: DecisionMemory con retorno realizado vs SPY
**Decision**: Guardar candidate_decisions con precio y score al momento de la decisión. Job en 7/30/90 días calcula retorno real vs SPY. Retroalimenta el scorer.
**Reason**: Sin validación contra retorno real, el sistema puede aprender patrones incorrectos.
**Date**: 2026-05-07

## D-007: CandidateAdmissionFlow ≈ TradeDecisionFlow
**Decision**: El mismo pipeline data→indicators→score→hard_rules→LLM se usa tanto para evaluar admisión de nuevos símbolos como para decisiones de trading en símbolos del universo. Solo cambia el threshold y la acción final.
**Reason**: Unifica la lógica y garantiza consistencia en evaluación.
**Date**: 2026-05-07

## D-008: No usar LangGraph ni múltiples LLM calls en paralelo
**Decision**: Pipeline secuencial liviano. Un solo call LLM al final del pipeline. Sin debate multi-ronda.
**Reason**: Raspberry Pi 5, latencia de usuario en Telegram, simplicidad de mantenimiento.
**Date**: 2026-05-07
