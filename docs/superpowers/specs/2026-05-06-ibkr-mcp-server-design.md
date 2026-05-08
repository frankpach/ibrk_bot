# IBKR MCP Server — Design Spec
**Date:** 2026-05-06
**Status:** Approved

---

## Overview

MCP server en Python que expone las acciones del IBKR AI Trader como tools consumibles desde OpenCode, Claude Code, o cualquier cliente MCP compatible. Actúa como cliente de la FastAPI existente (puerto 8088) — no duplica lógica, no accede directamente a IB Gateway.

---

## Arquitectura

```
OpenCode / Claude Code (cliente MCP)
        ↓ MCP protocol (stdio)
app/mcp/server.py  — FastMCP server
        ↓ HTTP a localhost:8088
app/api/main.py    — FastAPI (ya existe)
        ↓
Risk Validator + IBKRClient + SQLite
        ↓
IB Gateway (puerto 4002)
```

El MCP server es un proceso independiente que corre en stdio. OpenCode lo lanza automáticamente al arrancar según la configuración en opencode.json.

---

## Archivo único: app/mcp/server.py

Una sola responsabilidad: mapear tools MCP a endpoints FastAPI.

---

## Tools expuestas

### Lectura (sin riesgo)

| Tool | Endpoint FastAPI | Descripción |
|---|---|---|
| `get_price(symbol)` | GET /price/{symbol} | Precio actual con bid/ask |
| `get_account()` | GET /account | Balance, buying power, cash |
| `get_portfolio()` | GET /portfolio | Posiciones abiertas con P&L |
| `get_signals()` | GET /signals | Señales técnicas pendientes (STRONG/MEDIUM) |
| `get_trades()` | GET /trades | Trades abiertos |
| `get_patterns(symbol)` | GET /patterns/{symbol} | Patrones aprendidos por símbolo |
| `get_allowed_symbols()` | GET /allowed-symbols | Universo de símbolos activo |

### Simulación (sin ejecución)

| Tool | Endpoint FastAPI | Descripción |
|---|---|---|
| `preview_order(symbol, action, order_type, stop_loss_pct, take_profit_pct)` | POST /orders/preview | Simula orden, calcula riesgo, nunca ejecuta |

### Ejecución controlada

| Tool | Endpoint FastAPI | Descripción |
|---|---|---|
| `place_order(symbol, action, order_type, stop_loss_pct, take_profit_pct)` | POST /orders/place | Ejecuta orden — pasa por risk validator, paper gate, Telegram en live |
| `propose_symbol(symbol, reason)` | POST /symbols/propose | Propone nuevo símbolo para aprobación humana |

---

## Seguridad inamovible

- `place_order` llama a `/orders/place` en FastAPI, que pasa OBLIGATORIAMENTE por el Risk Validator
- El MCP server nunca llama directamente a IBKRClient ni a IB Gateway
- Si FastAPI no está corriendo → todas las tools fallan con error claro
- El motor de riesgo (MAX_POSITIONS=3, MAX_RISK_PCT=2%, MAX_POSITION_USD=$1000) no es bypasseable desde el MCP
- En live (REQUIRE_HUMAN_APPROVAL=True): la orden espera confirmación Telegram 5 min antes de ejecutarse

---

## Configuración OpenCode

Archivo: `~/.config/opencode/opencode.json` (global) o en el proyecto.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "ibkr-trader": {
      "type": "local",
      "command": [
        "/home/frankpach/ibkr-bot/.venv/bin/python3",
        "/home/frankpach/ibkr-bot/app/mcp/server.py"
      ],
      "enabled": true
    }
  }
}
```

---

## Transport

**stdio** — estándar para MCPs locales. OpenCode lanza el proceso y se comunica via stdin/stdout. No requiere puerto adicional.

---

## Dependencias nuevas

- `fastmcp` — SDK Python oficial de MCP
- `httpx` — ya instalado

---

## Archivos a crear/modificar

```
~/ibkr-bot/
├── app/
│   └── mcp/
│       ├── __init__.py       CREAR (vacío)
│       └── server.py         CREAR — MCP server completo
└── docs/superpowers/specs/
    └── 2026-05-06-ibkr-mcp-server-design.md  CREAR (este doc)

~/.config/opencode/
    └── opencode.json         CREAR/MODIFICAR — registrar MCP
```

---

## Ejemplo de uso desde OpenCode

```
Usuario: "¿Qué señales hay ahora?"
OpenCode → tool: get_signals()
→ [{"symbol": "AAPL", "strength": "STRONG", "rsi": 28.5, ...}]

Usuario: "Simula comprar AAPL con stop 2.5% y take profit 6%"
OpenCode → tool: preview_order("AAPL", "BUY", "MKT", 0.025, 0.06)
→ {"approved": true, "recommended_units": 3, "estimated_risk_usd": 21.57, ...}

Usuario: "Ejecuta esa orden"
OpenCode → tool: place_order("AAPL", "BUY", "MKT", 0.025, 0.06)
→ (paper) {"status": "placed", "order_id": "...", ...}
→ (live) Telegram: "BUY 3 AAPL — Aprobar/Cancelar (5 min)"
```
