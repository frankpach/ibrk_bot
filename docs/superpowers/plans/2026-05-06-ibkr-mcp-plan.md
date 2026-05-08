# IBKR MCP Server — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exponer las acciones del IBKR AI Trader como tools MCP consumibles desde OpenCode y cualquier cliente MCP, con seguridad total a través del Risk Validator existente.

**Architecture:** MCP server en stdio usando fastmcp que actúa como cliente HTTP de la FastAPI local (puerto 8088). Primero se añade el endpoint /orders/place a FastAPI, luego se crea el MCP server, finalmente se registra en OpenCode.

**Tech Stack:** Python 3.13, fastmcp 3.2.4, httpx, FastAPI (ya existe), IB Gateway paper trading

---

## Mapa de Archivos

```
~/ibkr-bot/
├── app/
│   ├── api/main.py              MODIFICAR — agregar POST /orders/place
│   └── mcp/
│       ├── __init__.py          CREAR (vacío)
│       └── server.py            CREAR — MCP server con 10 tools
├── tests/
│   └── test_mcp_server.py       CREAR — tests de tools MCP
└── docs/superpowers/plans/
    └── 2026-05-06-ibkr-mcp-plan.md

~/.config/opencode/
    └── opencode.json            CREAR/MODIFICAR — registrar MCP
```

---

## Task 1: Agregar POST /orders/place a FastAPI

**Files:**
- Modify: `~/ibkr-bot/app/api/main.py`

El endpoint /orders/place ejecuta órdenes reales en paper trading. Pasa OBLIGATORIAMENTE por el risk validator. En paper mode ejecuta directo; en live mode (REQUIRE_HUMAN_APPROVAL=True) bloquea hasta confirmación Telegram (implementada en Fase 5 futura — por ahora retorna "pending_approval").

- [ ] **Step 1: Agregar place_order al IBKRClient**

Leer client.py actual:
```bash
ssh aiutox-pi "cat ~/ibkr-bot/app/ibkr/client.py"
```

Agregar al final de la clase IBKRClient en `~/ibkr-bot/app/ibkr/client.py`:

```python
    async def _place_order_async(
        self,
        symbol: str,
        action: str,
        quantity: int,
        order_type: str,
        limit_price: float | None = None,
    ) -> dict:
        await self._connect_async()
        from ib_insync import Stock, Order
        contract = Stock(symbol.upper(), "SMART", "USD")
        await self.ib.qualifyContractsAsync(contract)
        order = Order(
            action=action.upper(),
            totalQuantity=quantity,
            orderType=order_type.upper(),
        )
        if order_type.upper() == "LMT" and limit_price:
            order.lmtPrice = limit_price
        trade = self.ib.placeOrder(contract, order)
        await asyncio.sleep(1)
        return {
            "order_id": str(trade.order.orderId),
            "symbol": symbol.upper(),
            "action": action.upper(),
            "quantity": quantity,
            "order_type": order_type.upper(),
            "status": trade.orderStatus.status,
        }

    def place_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
        order_type: str,
        limit_price: float | None = None,
    ) -> dict:
        with self._lock:
            return self._run_sync(
                self._place_order_async(symbol, action, quantity, order_type, limit_price)
            )
```

- [ ] **Step 2: Agregar POST /orders/place al final de main.py**

```python
@app.post("/orders/place")
def orders_place(req: OrderPreviewRequest):
    from app.config.settings import REQUIRE_HUMAN_APPROVAL, PAPER_TRADING_ONLY
    symbol = req.symbol.upper()

    # Obtener precio y cuenta para el validator
    try:
        price_data = client.get_stock_price(symbol)
        current_price = price_data["market_price"]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not fetch price: {exc}")
    try:
        account = client.get_account()
        capital = account["net_liquidation"]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not fetch account: {exc}")
    try:
        portfolio = client.get_portfolio()
        active_positions = len(portfolio)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not fetch portfolio: {exc}")

    # Validar siempre — no bypasseable
    result = validate_order(
        symbol=symbol, action=req.action, quantity=req.quantity,
        order_type=req.order_type, stop_loss_pct=req.stop_loss_pct,
        capital=capital, active_positions=active_positions,
        now=datetime.now(tz=MARKET_TZ),
    )

    if not result.approved:
        raise HTTPException(status_code=403, detail={"approved": False, "reasons": result.reasons})

    # Calcular units reales
    max_risk_usd = max(capital * MAX_RISK_PCT, MIN_RISK_USD)
    max_position_usd = min(max_risk_usd / req.stop_loss_pct, MAX_POSITION_USD) if req.stop_loss_pct > 0 else 0
    units = int(max_position_usd / current_price) if current_price > 0 else 0

    if units < 1:
        raise HTTPException(status_code=400, detail="Calculated position size is 0 units")

    # Live mode: requiere aprobación humana (Telegram — implementado en Fase 5)
    if REQUIRE_HUMAN_APPROVAL:
        return {
            "status": "pending_approval",
            "symbol": symbol,
            "action": req.action,
            "units": units,
            "message": "Order queued for human approval via Telegram.",
        }

    # Paper mode: ejecutar directamente
    if not PAPER_TRADING_ONLY:
        raise HTTPException(status_code=500, detail="Neither paper nor approval mode configured")

    try:
        order_result = client.place_order(
            symbol=symbol,
            action=req.action,
            quantity=units,
            order_type=req.order_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Order placement failed: {exc}")

    # Registrar en DB
    from app.db.database import insert_trade
    from app.db.models import Trade
    stop_loss_price = round(current_price * (1 - req.stop_loss_pct), 2)
    take_profit_price = round(current_price * (1 + req.take_profit_pct), 2)
    from datetime import datetime as dt
    insert_trade(Trade(
        id=None, symbol=symbol, action=req.action, quantity=units,
        entry_price=current_price, stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price, stop_loss_pct=req.stop_loss_pct,
        take_profit_pct=req.take_profit_pct, signal_strength="MANUAL",
        llm_justification="Placed via MCP", status="OPEN",
        exit_price=None, exit_reason=None, pnl_usd=None, pnl_pct=None,
        opened_at=dt.utcnow(), closed_at=None,
        order_id=order_result.get("order_id"),
    ))

    return {
        "status": "placed",
        "symbol": symbol,
        "action": req.action,
        "units": units,
        "entry_price": current_price,
        "stop_loss_price": stop_loss_price,
        "take_profit_price": take_profit_price,
        "order_id": order_result.get("order_id"),
    }
```

- [ ] **Step 3: Reiniciar run.py y probar /orders/place (preview primero)**

```bash
ssh aiutox-pi "kill \$(ps aux | grep 'run.py' | grep -v grep | awk '{print \$2}') 2>/dev/null; sleep 2"
ssh aiutox-pi "cd ~/ibkr-bot && source .venv/bin/activate && nohup python3 run.py > /tmp/run.log 2>&1 & sleep 10 && curl -s http://127.0.0.1:8088/health"
```

Probar que el endpoint existe y el risk validator lo protege:
```bash
# Debe rechazar símbolo inválido
ssh aiutox-pi "curl -s -X POST http://127.0.0.1:8088/orders/place -H 'Content-Type: application/json' -d '{\"symbol\":\"FAKE\",\"action\":\"BUY\",\"quantity\":1,\"order_type\":\"MKT\",\"stop_loss_pct\":0.025,\"take_profit_pct\":0.06}'"
```
Esperado: `{"detail":{"approved":false,"reasons":["Symbol FAKE is not allowed"]}}`

```bash
# Debe aceptar orden válida en paper mode
ssh aiutox-pi "curl -s -X POST http://127.0.0.1:8088/orders/place -H 'Content-Type: application/json' -d '{\"symbol\":\"AAPL\",\"action\":\"BUY\",\"quantity\":1,\"order_type\":\"MKT\",\"stop_loss_pct\":0.025,\"take_profit_pct\":0.06}'"
```
Esperado: `{"status":"placed","symbol":"AAPL",...}` o rechazo de market hours si es fin de semana.

- [ ] **Step 4: Commit**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && git add app/api/main.py app/ibkr/client.py && git commit -m 'feat: add POST /orders/place with risk validation and trade recording'"
```

---

## Task 2: Instalar fastmcp y crear MCP server

**Files:**
- Create: `~/ibkr-bot/app/mcp/__init__.py`
- Create: `~/ibkr-bot/app/mcp/server.py`

- [ ] **Step 1: Instalar fastmcp**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && source .venv/bin/activate && pip install fastmcp && pip freeze | grep fastmcp"
```
Esperado: `fastmcp==3.2.4` (o versión similar)

- [ ] **Step 2: Crear app/mcp/__init__.py**

```bash
ssh aiutox-pi "mkdir -p ~/ibkr-bot/app/mcp && touch ~/ibkr-bot/app/mcp/__init__.py"
```

- [ ] **Step 3: Crear app/mcp/server.py**

Escribir el archivo completo:

```python
#!/usr/bin/env python3
# app/mcp/server.py
"""
MCP server para IBKR AI Trader.
Expone las acciones de trading como tools MCP via stdio.
Actua como cliente HTTP de la FastAPI local en puerto 8088.
Nunca accede directamente a IB Gateway — toda seguridad va por FastAPI.
"""
import json
import sys
from pathlib import Path

import httpx
from fastmcp import FastMCP

# Asegurar que el proyecto sea importable cuando se lanza desde opencode
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

API_BASE = "http://127.0.0.1:8088"
TIMEOUT = 30.0

mcp = FastMCP(
    name="IBKR AI Trader",
    instructions=(
        "Herramienta de trading conectada a Interactive Brokers via paper trading. "
        "Usa preview_order antes de place_order. "
        "El motor de riesgo bloquea ordenes que superen limites de capital o posiciones. "
        "Maximo 3 posiciones activas simultaneas. Maximo $1000 por operacion."
    ),
)


def _get(path: str) -> dict | list:
    try:
        r = httpx.get(f"{API_BASE}{path}", timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        return {"error": "FastAPI server not running. Start with: python3 run.py"}
    except Exception as e:
        return {"error": str(e)}


def _post(path: str, data: dict) -> dict:
    try:
        r = httpx.post(f"{API_BASE}{path}", json=data, timeout=TIMEOUT)
        if r.status_code == 403:
            return r.json()
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        return {"error": "FastAPI server not running. Start with: python3 run.py"}
    except Exception as e:
        return {"error": str(e)}


# --- Tools de solo lectura ---

@mcp.tool()
def get_price(symbol: str) -> dict:
    """
    Obtiene el precio actual de un simbolo de bolsa.
    Retorna market_price, bid, ask, last.
    Simbolos permitidos: AAPL, MSFT, SPY, QQQ, TSLA, NVDA, AMZN, GOOGL, META, JPM.
    """
    return _get(f"/price/{symbol.upper()}")


@mcp.tool()
def get_account() -> dict:
    """
    Retorna el estado actual de la cuenta de trading.
    Incluye net_liquidation (valor total), buying_power, cash_balance y currency.
    """
    return _get("/account")


@mcp.tool()
def get_portfolio() -> list:
    """
    Retorna las posiciones abiertas actuales.
    Cada posicion incluye symbol, quantity, avg_cost, market_value, unrealized_pnl.
    Maximo 3 posiciones activas simultaneas segun reglas del sistema.
    """
    return _get("/portfolio")


@mcp.tool()
def get_signals() -> list:
    """
    Retorna las senales tecnicas pendientes detectadas por el preprocesador.
    Cada senal incluye symbol, strength (STRONG/MEDIUM), rsi, macd, volume_ratio.
    Solo aparecen senales STRONG y MEDIUM — las WEAK son descartadas automaticamente.
    """
    return _get("/signals")


@mcp.tool()
def get_trades() -> list:
    """
    Retorna los trades actualmente abiertos en el sistema.
    Incluye symbol, action, quantity, entry_price, stop_loss_price, take_profit_price.
    """
    return _get("/trades")


@mcp.tool()
def get_patterns(symbol: str) -> list:
    """
    Retorna los patrones de trading aprendidos para un simbolo especifico.
    Cada patron incluye el texto del patron, numero de wins y losses historicos.
    Usar esto antes de decidir una operacion para aprovechar el historial.
    """
    return _get(f"/patterns/{symbol.upper()}")


@mcp.tool()
def get_allowed_symbols() -> dict:
    """
    Retorna la lista de simbolos permitidos para operar.
    Solo estos simbolos pueden usarse en preview_order y place_order.
    """
    return _get("/allowed-symbols")


# --- Tool de simulacion ---

@mcp.tool()
def preview_order(
    symbol: str,
    action: str,
    order_type: str,
    stop_loss_pct: float,
    take_profit_pct: float,
) -> dict:
    """
    Simula una orden de trading sin ejecutarla. Siempre seguro de llamar.
    Calcula el tamano de posicion, riesgo estimado, precios de stop-loss y take-profit.

    Args:
        symbol: Ticker (ej: AAPL, MSFT)
        action: BUY o SELL
        order_type: MKT (mercado) o LMT (limite)
        stop_loss_pct: Porcentaje de stop-loss como decimal (ej: 0.025 = 2.5%)
        take_profit_pct: Porcentaje de take-profit como decimal (ej: 0.06 = 6%)
                         Debe ser al menos 2x el stop_loss_pct.
    """
    return _post("/orders/preview", {
        "symbol": symbol.upper(),
        "action": action.upper(),
        "quantity": 1,
        "order_type": order_type.upper(),
        "stop_loss_pct": stop_loss_pct,
        "take_profit_pct": take_profit_pct,
    })


# --- Tool de ejecucion controlada ---

@mcp.tool()
def place_order(
    symbol: str,
    action: str,
    order_type: str,
    stop_loss_pct: float,
    take_profit_pct: float,
) -> dict:
    """
    Ejecuta una orden de trading real en paper trading.
    SIEMPRE pasa por el motor de riesgo — no bypasseable.
    Limites aplicados automaticamente:
      - Maximo 3 posiciones activas simultaneas
      - Maximo 2% del capital en riesgo por operacion
      - Maximo $1000 por posicion
      - Solo simbolos permitidos
      - Solo en horario de mercado (09:30-16:00 ET, Lun-Vie)
    En modo live (cuando este habilitado): envia notificacion Telegram y espera aprobacion 5 min.

    Args:
        symbol: Ticker (ej: AAPL, MSFT)
        action: BUY o SELL
        order_type: MKT (mercado) o LMT (limite)
        stop_loss_pct: Porcentaje de stop-loss como decimal (ej: 0.025 = 2.5%)
        take_profit_pct: Porcentaje de take-profit como decimal (ej: 0.06 = 6%)
    """
    return _post("/orders/place", {
        "symbol": symbol.upper(),
        "action": action.upper(),
        "quantity": 1,
        "order_type": order_type.upper(),
        "stop_loss_pct": stop_loss_pct,
        "take_profit_pct": take_profit_pct,
    })


@mcp.tool()
def propose_symbol(symbol: str, reason: str) -> dict:
    """
    Propone agregar un nuevo simbolo al universo de trading.
    El simbolo no se activa inmediatamente — queda pendiente de aprobacion humana.

    Args:
        symbol: Ticker a proponer (ej: NFLX, BABA)
        reason: Justificacion para agregar este simbolo
    """
    return _post("/symbols/propose", {
        "symbol": symbol.upper(),
        "reason": reason,
    })


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

- [ ] **Step 4: Verificar que el server arranca sin errores**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && source .venv/bin/activate && echo '{}' | timeout 3 python3 app/mcp/server.py 2>&1 || true"
```
Esperado: salida de inicializacion MCP sin errores de importacion (puede dar timeout — es normal en stdio).

- [ ] **Step 5: Commit**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && git add app/mcp/ && git commit -m 'feat: add MCP server with 10 trading tools via fastmcp'"
```

---

## Task 3: Tests del MCP server

**Files:**
- Create: `~/ibkr-bot/tests/test_mcp_server.py`

Los tests verifican la logica de las tools sin necesitar FastAPI corriendo — mockean las llamadas HTTP.

- [ ] **Step 1: Crear tests/test_mcp_server.py**

```python
# tests/test_mcp_server.py
"""
Tests del MCP server. Mockean httpx para no requerir FastAPI corriendo.
"""
from unittest.mock import patch, MagicMock
import pytest


def make_response(data, status_code=200):
    mock = MagicMock()
    mock.json.return_value = data
    mock.status_code = status_code
    mock.raise_for_status = MagicMock()
    return mock


def make_error_response(data, status_code=403):
    mock = MagicMock()
    mock.json.return_value = data
    mock.status_code = status_code
    mock.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return mock


@patch("httpx.get")
def test_get_price_calls_correct_endpoint(mock_get):
    mock_get.return_value = make_response({"symbol": "AAPL", "market_price": 287.64})
    from app.mcp.server import get_price
    result = get_price("aapl")
    mock_get.assert_called_once_with("http://127.0.0.1:8088/price/AAPL", timeout=30.0)
    assert result["market_price"] == 287.64


@patch("httpx.get")
def test_get_price_uppercases_symbol(mock_get):
    mock_get.return_value = make_response({"symbol": "MSFT", "market_price": 420.0})
    from app.mcp.server import get_price
    get_price("msft")
    mock_get.assert_called_once_with("http://127.0.0.1:8088/price/MSFT", timeout=30.0)


@patch("httpx.get")
def test_get_account_returns_data(mock_get):
    mock_get.return_value = make_response({"net_liquidation": 1000000.0, "buying_power": 500000.0})
    from app.mcp.server import get_account
    result = get_account()
    assert result["net_liquidation"] == 1000000.0


@patch("httpx.get")
def test_get_portfolio_returns_list(mock_get):
    mock_get.return_value = make_response([])
    from app.mcp.server import get_portfolio
    result = get_portfolio()
    assert isinstance(result, list)


@patch("httpx.get")
def test_get_signals_returns_list(mock_get):
    mock_get.return_value = make_response([{"symbol": "AAPL", "strength": "STRONG"}])
    from app.mcp.server import get_signals
    result = get_signals()
    assert result[0]["strength"] == "STRONG"


@patch("httpx.get")
def test_get_patterns_uppercases_symbol(mock_get):
    mock_get.return_value = make_response([])
    from app.mcp.server import get_patterns
    get_patterns("aapl")
    mock_get.assert_called_once_with("http://127.0.0.1:8088/patterns/AAPL", timeout=30.0)


@patch("httpx.post")
def test_preview_order_sends_correct_payload(mock_post):
    mock_post.return_value = make_response({"approved": True, "recommended_units": 3})
    from app.mcp.server import preview_order
    result = preview_order("aapl", "buy", "mkt", 0.025, 0.06)
    call_args = mock_post.call_args
    payload = call_args[1]["json"]
    assert payload["symbol"] == "AAPL"
    assert payload["action"] == "BUY"
    assert payload["order_type"] == "MKT"
    assert payload["stop_loss_pct"] == 0.025


@patch("httpx.post")
def test_place_order_sends_correct_payload(mock_post):
    mock_post.return_value = make_response({"status": "placed", "order_id": "123"})
    from app.mcp.server import place_order
    result = place_order("AAPL", "BUY", "MKT", 0.025, 0.06)
    call_args = mock_post.call_args
    payload = call_args[1]["json"]
    assert payload["symbol"] == "AAPL"
    assert payload["stop_loss_pct"] == 0.025
    assert result["status"] == "placed"


@patch("httpx.post")
def test_place_order_returns_rejection_when_403(mock_post):
    rejection = {"approved": False, "reasons": ["Symbol FAKE is not allowed"]}
    mock_post.return_value = make_response(rejection, status_code=403)
    from app.mcp.server import place_order
    result = place_order("FAKE", "BUY", "MKT", 0.025, 0.06)
    assert result["approved"] is False


@patch("httpx.get")
def test_get_error_when_server_not_running(mock_get):
    import httpx
    mock_get.side_effect = httpx.ConnectError("Connection refused")
    from app.mcp.server import get_price
    result = get_price("AAPL")
    assert "error" in result
    assert "not running" in result["error"]
```

- [ ] **Step 2: Correr tests para verificar que fallan primero**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && source .venv/bin/activate && pytest tests/test_mcp_server.py -v 2>&1 | tail -15"
```
Esperado: `ModuleNotFoundError` o `ImportError` — server.py existe pero tests no habian corrido aun.

- [ ] **Step 3: Correr tests con server.py ya creado**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && source .venv/bin/activate && pytest tests/test_mcp_server.py -v 2>&1"
```
Esperado: 10 tests PASS

- [ ] **Step 4: Correr todos los tests del proyecto**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && source .venv/bin/activate && pytest tests/test_mcp_server.py tests/test_risk_validator.py tests/test_preprocessor.py -v 2>&1 | tail -20"
```
Esperado: 23 tests PASS (10 + 7 + 6)

- [ ] **Step 5: Commit**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && git add tests/test_mcp_server.py && git commit -m 'test: add MCP server tool tests'"
```

---

## Task 4: Registrar MCP en OpenCode

**Files:**
- Create/Modify: `~/.config/opencode/opencode.json`

- [ ] **Step 1: Verificar donde vive opencode.json global**

```bash
ssh aiutox-pi "ls ~/.config/opencode/ 2>/dev/null && cat ~/.config/opencode/opencode.json 2>/dev/null || echo 'not found'"
```

- [ ] **Step 2: Crear o actualizar ~/.config/opencode/opencode.json**

Si no existe el directorio:
```bash
ssh aiutox-pi "mkdir -p ~/.config/opencode"
```

Escribir el config completo:
```bash
ssh aiutox-pi "cat > ~/.config/opencode/opencode.json << 'EOF'
{
  \"\$schema\": \"https://opencode.ai/config.json\",
  \"mcp\": {
    \"ibkr-trader\": {
      \"type\": \"local\",
      \"command\": [
        \"/home/frankpach/ibkr-bot/.venv/bin/python3\",
        \"/home/frankpach/ibkr-bot/app/mcp/server.py\"
      ],
      \"enabled\": true,
      \"timeout\": 30000
    }
  }
}
EOF"
```

- [ ] **Step 3: Verificar que el JSON es válido**

```bash
ssh aiutox-pi "python3 -m json.tool ~/.config/opencode/opencode.json"
```
Esperado: JSON formateado sin errores.

- [ ] **Step 4: Probar el MCP server manualmente via stdio**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && source .venv/bin/activate && echo '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\",\"params\":{}}' | python3 app/mcp/server.py 2>/dev/null | python3 -m json.tool 2>/dev/null | head -40"
```
Esperado: JSON con lista de tools incluyendo get_price, get_account, preview_order, place_order, etc.

- [ ] **Step 5: Commit**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && git add . && git commit -m 'feat: register MCP server in opencode.json'"
```

---

## Task 5: Smoke test end-to-end

Verifica que el flujo completo funciona: FastAPI corriendo → MCP server llama FastAPI → devuelve datos reales.

- [ ] **Step 1: Asegurar que run.py está corriendo**

```bash
ssh aiutox-pi "curl -s http://127.0.0.1:8088/health"
```
Si no responde:
```bash
ssh aiutox-pi "cd ~/ibkr-bot && source .venv/bin/activate && nohup python3 run.py > /tmp/run.log 2>&1 & sleep 10 && curl -s http://127.0.0.1:8088/health"
```
Esperado: `{"status":"ok","connected":true}`

- [ ] **Step 2: Llamar tools via MCP protocol directamente**

Probar get_price via MCP stdio:
```bash
ssh aiutox-pi "cd ~/ibkr-bot && source .venv/bin/activate && python3 -c \"
import json, subprocess, sys

proc = subprocess.Popen(
    ['python3', 'app/mcp/server.py'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
)

# Enviar initialize
init = json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'test','version':'1.0'}}})
proc.stdin.write((init + '\n').encode())
proc.stdin.flush()

# Enviar tool call get_price
call = json.dumps({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'get_price','arguments':{'symbol':'AAPL'}}})
proc.stdin.write((call + '\n').encode())
proc.stdin.flush()

import time; time.sleep(8)
proc.terminate()

# Leer respuestas
output = proc.stdout.read().decode()
for line in output.strip().split('\n'):
    if line.strip():
        try:
            d = json.loads(line)
            if d.get('id') == 2:
                print(json.dumps(d, indent=2))
        except:
            pass
\""
```
Esperado: JSON con `result.content` conteniendo el precio de AAPL.

- [ ] **Step 3: Probar preview_order via MCP**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && source .venv/bin/activate && python3 -c \"
import json, subprocess, time

proc = subprocess.Popen(
    ['python3', 'app/mcp/server.py'],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
)

msgs = [
    json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'test','version':'1.0'}}}),
    json.dumps({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'preview_order','arguments':{'symbol':'AAPL','action':'BUY','order_type':'MKT','stop_loss_pct':0.025,'take_profit_pct':0.06}}}),
]
for m in msgs:
    proc.stdin.write((m + '\n').encode())
    proc.stdin.flush()

time.sleep(10)
proc.terminate()
out = proc.stdout.read().decode()
for line in out.strip().split('\n'):
    if line.strip():
        try:
            d = json.loads(line)
            if d.get('id') == 2:
                print(json.dumps(d, indent=2))
        except: pass
\""
```
Esperado: JSON con `approved: true`, `recommended_units`, `estimated_risk_usd`.

- [ ] **Step 4: Verificar lista completa de tools**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && source .venv/bin/activate && python3 -c \"
import json, subprocess, time

proc = subprocess.Popen(
    ['python3', 'app/mcp/server.py'],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
)

msgs = [
    json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'test','version':'1.0'}}}),
    json.dumps({'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}}),
]
for m in msgs:
    proc.stdin.write((m + '\n').encode())
    proc.stdin.flush()

time.sleep(3)
proc.terminate()
out = proc.stdout.read().decode()
for line in out.strip().split('\n'):
    if line.strip():
        try:
            d = json.loads(line)
            if d.get('id') == 2:
                tools = [t['name'] for t in d['result']['tools']]
                print('Tools:', tools)
                print('Count:', len(tools))
        except: pass
\""
```
Esperado: 10 tools listadas: get_price, get_account, get_portfolio, get_signals, get_trades, get_patterns, get_allowed_symbols, preview_order, place_order, propose_symbol.

---

## Self-Review

**Cobertura del spec:**
- ✅ app/mcp/server.py con 10 tools — Task 2
- ✅ Transport stdio — Task 2 (`mcp.run(transport="stdio")`)
- ✅ Seguridad: place_order pasa por FastAPI → risk validator — Task 1
- ✅ Registro en opencode.json — Task 4
- ✅ Tests de tools — Task 3
- ✅ /orders/place en FastAPI (prerequisito) — Task 1
- ✅ Smoke test end-to-end — Task 5

**Sin placeholders:** Plan completo con código en cada step ✅

**Consistencia de tipos:**
- `_get()` retorna `dict | list` — usado en tools de lectura ✅
- `_post()` retorna `dict` — usado en preview_order, place_order, propose_symbol ✅
- Todos los símbolos se uppercasean en el MCP antes de llamar FastAPI ✅
- `place_order` en IBKRClient retorna dict con `order_id` — usado en main.py ✅
