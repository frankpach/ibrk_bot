# IBKR AI Swing Trader — Design Spec
**Date:** 2026-05-06  
**Status:** Approved  

---

## Overview

Sistema de swing trading semi-autónomo corriendo en Raspberry Pi. Conecta IB Gateway localmente via ib_insync, usa Kimi K2 como LLM de decisión (llamado solo cuando hay señal), y aprende de cada operación extrayendo patrones explícitos.

---

## Decisiones Clave

| Aspecto | Decisión |
|---|---|
| Estilo | Swing trading 2-10 días + reacción a señales fuertes |
| LLM | Kimi K2 (API, OpenAI-compatible SDK) |
| Aprendizaje | Memoria de decisiones + RAG de noticias/mercado |
| Frecuencia | Preprocesador cada 15 min, LLM solo cuando hay señal |
| Señales | RSI+MACD+volumen base, crece con señales IB, LLM elige por símbolo |
| Stop-loss/TP | LLM define por operación |
| Gestión capital | Máximo 2% del capital en riesgo por operación (mín $2 si capital < $100) |
| Posiciones | Máximo 3 simultáneas (buy, sell, call, put combinados) |
| Símbolos | Lista base, LLM propone nuevos con aprobación humana |
| Aprendizaje | Post-mortem por operación, LLM extrae patrones a DB |
| Paper trading | Auto-ejecuta solo |
| Live trading | Auto-ejecuta + Telegram con ventana de cancelación 5 min |
| Base de datos | SQLite ahora, PostgreSQL cuando madure |

---

## Arquitectura

```
Raspberry Pi
├── IB Gateway (puerto 4002)
├── FastAPI (puerto 8088)
│   ├── app/ibkr/client.py          cliente IB thread-safe
│   ├── app/api/main.py             endpoints REST
│   ├── app/risk/validator.py       motor de riesgo determinístico
│   ├── app/scanner/preprocessor.py scheduler sin LLM
│   ├── app/llm/agent.py            agente Kimi K2
│   ├── app/positions/manager.py    daemon stop-loss/take-profit
│   ├── app/notifications/telegram.py bot Telegram
│   ├── app/db/                     SQLite + modelos
│   └── app/config/settings.py     configuración central
└── systemd services (fase 7)
```

---

## Componentes

### app/ibkr/client.py (ampliar)
Agregar a lo existente:
- get_account() — net_liquidation, buying_power, cash_balance, currency
- get_portfolio() — posiciones con symbol, quantity, avg_cost, market_value, unrealized_pnl
- place_order(symbol, action, quantity, order_type, limit_price, stop_loss, take_profit)
- cancel_order(order_id)

### app/risk/validator.py (nuevo)
Capa determinística, nunca bypasseable por el LLM.

Validaciones en orden:
1. Símbolo en ALLOWED_SYMBOLS
2. Posiciones activas < MAX_POSITIONS (3)
3. Tipo de orden permitido (MKT, LMT)
4. Horario de mercado (09:30-16:00 ET, lunes-viernes)
5. Capital en riesgo: stop_loss_pct x position_size <= 2% del capital
6. PAPER_TRADING_ONLY gate
7. REQUIRE_HUMAN_APPROVAL gate (live: Telegram 5 min)

Devuelve: ValidationResult(approved, reasons, position_size_units, estimated_risk_usd)

### app/scanner/preprocessor.py (nuevo)
Scheduler independiente. No llama al LLM nunca.

- Corre cada 15 min en horario 09:15-16:15 ET
- Calcula RSI, MACD, volumen relativo por símbolo
- Carga indicadores adicionales preferidos por símbolo desde DB
- Clasifica señal:
  - STRONG: RSI<30 o >70 AND MACD cruce AND volumen >150% promedio
  - MEDIUM: cualquier 2 de 3 anteriores
  - WEAK: 1 o ninguno — no actúa
- STRONG o MEDIUM: inserta en tabla signals

### app/llm/agent.py (nuevo)
Solo se instancia cuando hay señal en cola.

Tools disponibles para el LLM:
- get_price(symbol)
- get_portfolio()
- get_account()
- request_additional_indicator(symbol, indicator)

Devuelve: accion (BUY/SELL/IGNORE), stop_loss_pct, take_profit_pct, justificacion
Después de cerrar posición: corre post-mortem, extrae patrones a DB

### app/positions/manager.py (nuevo)
Daemon cada 2 min. No llama al LLM.

- Stop-loss tocado: cierra inmediatamente
- Señal MEDIUM + ganancia >= 1%: cierra
- Señal STRONG: deja correr hasta take-profit o stop-loss
- Registra resultado en DB

### app/db/ (nuevo)
Tablas SQLite:
- signals: cola de señales del preprocesador
- trades: historial completo de operaciones
- patterns: reglas aprendidas por el LLM por símbolo
- symbol_config: universo + indicadores preferidos por símbolo
- decisions: log de cada llamada al LLM

### app/notifications/telegram.py (nuevo)
- Paper: informa, no espera respuesta
- Live: botones Aprobar/Cancelar, timeout 5 min, cancela si no hay respuesta

### app/api/main.py (ampliar)
Endpoints:
- GET  /health
- GET  /price/{symbol}
- GET  /account
- GET  /portfolio
- GET  /allowed-symbols
- POST /symbols/propose
- POST /orders/preview
- POST /orders/place
- DELETE /orders/cancel/{id}
- GET  /signals
- GET  /trades
- GET  /patterns

---

## Flujo Completo de Operación

1. Preprocesador detecta RSI=28 + MACD alcista + volumen 180% en AAPL → STRONG → inserta signal
2. LLM Agent despierta: consulta portfolio (1 activa<3 OK), account ($1000), patrones AAPL
3. LLM decide: BUY, stop-loss 2.5%, take-profit 6%
4. Motor de Riesgo: riesgo max $20, position_size = $800 = 2 acciones. Paper: aprueba directo
5. POST /orders/place → IB Gateway ejecuta → DB registra
6. Position Manager cada 2 min: señal STRONG, deja correr → precio +6% → cierra
7. Post-mortem: LLM extrae patrón → guarda en patterns → activa Bollinger para AAPL

---

## Fases de Implementación

| Fase | Contenido | Estado |
|---|---|---|
| 0 | FastAPI base + IBKRClient + /price | Completado |
| 1 | /account, /portfolio, /orders/preview + risk validator | Siguiente |
| 2 | DB SQLite + Preprocesador + señales | Pendiente |
| 3 | LLM Agent Kimi K2 | Pendiente |
| 4 | Position Manager + cierre automático | Pendiente |
| 5 | Telegram bot | Pendiente |
| 6 | Post-mortem + patrones aprendidos | Pendiente |
| 7 | Live trading + systemd | Pendiente |

---

## Reglas de Seguridad Inamovibles

1. El LLM nunca llama directamente a IB Gateway — solo via FastAPI
2. El motor de riesgo es determinístico — el LLM no puede bypassearlo
3. Stop-loss siempre definido antes de ejecutar cualquier orden
4. Capital en riesgo nunca supera 2% por operación
5. Máximo 3 posiciones simultáneas sin excepción
6. En live: toda orden espera confirmación Telegram 5 min
7. PAPER_TRADING_ONLY bloquea ejecución real en toda la cadena
