#!/usr/bin/env python3
# app/mcp/server.py
"""
MCP server para IBKR AI Trader.
Expone las acciones de trading como tools MCP via stdio.
Actua como cliente HTTP de la FastAPI local en puerto 8088.
Nunca accede directamente a IB Gateway — toda seguridad va por FastAPI.
"""
import sys
from pathlib import Path

import httpx
from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config.settings import API_BASE  # noqa: F401
TIMEOUT = 30.0

mcp = FastMCP(
    name="IBKR AI Trader",
    instructions=(
        "Herramienta de trading conectada a Interactive Brokers via la FastAPI local. "
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


@mcp.tool()
def get_price(symbol: str) -> dict:
    """
    Obtiene el precio actual de un simbolo de bolsa.
    Retorna market_price, bid, ask, last.
    Solo funciona para simbolos aprobados en el universo activo del sistema.
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
    """
    return _post("/orders/preview", {
        "symbol": symbol.upper(),
        "action": action.upper(),
        "quantity": 1,
        "order_type": order_type.upper(),
        "stop_loss_pct": stop_loss_pct,
        "take_profit_pct": take_profit_pct,
    })


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
    Limites: max 3 posiciones, max 2% capital en riesgo, max $1000 por posicion,
    solo simbolos permitidos, solo horario de mercado ET Lun-Vie 09:30-16:00.

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


@mcp.tool()
def candidate_analysis(symbol: str) -> dict:
    """
    Full AnalysisPipeline analysis for any symbol — even outside the active universe.
    Returns score, recommendation, LLM narrative, and feature data.
    Args:
        symbol: Ticker symbol (e.g., NFLX, SHOP)
    """
    return _get(f"/candidate-analysis/{symbol.upper()}")


@mcp.tool()
def compute_indicator(symbol: str, indicator_name: str) -> dict:
    """
    Compute a single technical indicator for a symbol.
    Available indicators: rsi_14, macd, atr_pct, sma20, sma50, sma200,
                          bollinger, vwap, volume_ratio_20d
    Args:
        symbol: Ticker symbol
        indicator_name: Name of the indicator to compute
    """
    return _get(f"/analysis/indicator/{symbol.upper()}/{indicator_name}")


@mcp.tool()
def get_universe_watchlist() -> list:
    """
    Returns the active trading universe with watchlist scores.
    Higher score = more likely to be kept in universe.
    """
    return _get("/universe/watchlist")


if __name__ == "__main__":
    mcp.run(transport="stdio")
