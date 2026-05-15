# app/api/main.py
import logging
import os
from datetime import datetime
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from app.api.auth import require_control_key
from app.interfaces.api.routes.control_routes import router as control_router
from app.interfaces.api.routes.jobs_routes import router as jobs_router

from app.config.settings import MARKET_TZ, MAX_RISK_PCT, MIN_RISK_USD, MAX_POSITION_USD
from app.api.capital import get_operating_capital
from app.ibkr.client import get_client
from app.risk.validator import validate_order
from app.infrastructure.db.compat import (
    get_pending_signals,
    get_open_trades,
    get_patterns_for_symbol,
    init_db,
    get_approved_symbols,
)

logger = logging.getLogger(__name__)
app = FastAPI(title="IBKR AI Trader API")

# CORS — restrict to configured origin(s); default is restrictive (no public access)
_ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "")
allow_origins = [o.strip() for o in _ALLOWED_ORIGINS.split(",") if o.strip()] or ["*"]
if os.getenv("RESTRICT_CORS", "false").lower() == "true":
    allow_origins = [o.strip() for o in _ALLOWED_ORIGINS.split(",") if o.strip()]
    if not allow_origins:
        allow_origins = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["X-Control-Key", "X-Admin-Key", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Add security headers to every response."""
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


app.include_router(control_router)
app.include_router(jobs_router)
client = get_client()


def _get_universe_symbols(auto_approve_open: bool = False) -> list[str]:
    approved = list(get_approved_symbols())
    open_symbols = [t.symbol.upper() for t in get_open_trades()]
    if auto_approve_open:
        from app.infrastructure.db.compat import approve_symbol
        approved_set = set(approved)
        for sym in open_symbols:
            if sym not in approved_set:
                try:
                    approve_symbol(sym)
                    approved.append(sym)
                    approved_set.add(sym)
                except Exception as exc:
                    logger.warning(f"Could not auto-approve open symbol {sym}: {exc}")
    return list(dict.fromkeys(open_symbols + approved))


class OrderPreviewRequest(BaseModel):
    symbol: str
    action: str
    quantity: float
    order_type: str
    stop_loss_pct: float
    take_profit_pct: float
    limit_price: float | None = None


class SymbolProposalRequest(BaseModel):
    symbol: str
    reason: str


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok", "connected": client.ib.isConnected()}


@app.get("/price/{symbol}")
def get_price(symbol: str):
    symbol = symbol.upper()
    if symbol not in set(get_approved_symbols()):
        raise HTTPException(status_code=403, detail=f"Symbol {symbol} not allowed")
    try:
        return client.get_stock_price(symbol)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/price/free/{symbol}")
def get_price_free(symbol: str):
    """Obtiene precio de cualquier simbolo sin restriccion del universo aprobado.
    Solo para analisis — no para operar."""
    symbol = symbol.upper()
    try:
        return client.get_stock_price(symbol)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/account")
def get_account():
    try:
        return client.get_account()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/portfolio")
def get_portfolio():
    try:
        return client.get_portfolio()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/allowed-symbols")
def get_allowed_symbols():
    from app.infrastructure.db.compat import get_approved_symbols_with_meta
    approved_meta = get_approved_symbols_with_meta()
    meta_by_symbol = {row["symbol"]: row for row in approved_meta}
    symbols = []
    for sym in _get_universe_symbols(auto_approve_open=True):
        symbols.append(meta_by_symbol.get(sym, {
            "symbol": sym,
            "sec_type": "STK",
            "exchange": "SMART",
            "currency": "USD",
            "liquid_hours": None,
            "market_key": "STK_US",
        }))
    return {"symbols": [s["symbol"] for s in symbols], "meta": symbols}


@app.post("/symbols/propose")
def propose_symbol(req: SymbolProposalRequest):
    from app.infrastructure.db.compat import save_symbol_proposal
    symbol = req.symbol.upper()
    save_symbol_proposal(symbol, req.reason)
    return {
        "status": "pending_approval",
        "symbol": symbol,
        "reason": req.reason,
        "message": f"Symbol {symbol} saved. Use GET /symbols/proposals to review and POST /symbols/approve/{{symbol}} to activate.",
    }


@app.post("/orders/preview")
def orders_preview(req: OrderPreviewRequest):
    symbol = req.symbol.upper()
    try:
        price_data = client.get_stock_price(symbol)
        current_price = price_data["market_price"]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not fetch price: {exc}")
    try:
        account = client.get_account()
        capital = get_operating_capital(account.get("net_liquidation", 0.0))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not fetch account: {exc}")
    try:
        portfolio = client.get_portfolio()
        active_positions = len(portfolio)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not fetch portfolio: {exc}")

    result = validate_order(
        symbol=symbol, action=req.action, quantity=req.quantity,
        order_type=req.order_type, stop_loss_pct=req.stop_loss_pct,
        capital=capital, active_positions=active_positions,
        now=datetime.now(tz=MARKET_TZ),
    )

    max_risk_usd = max(capital * MAX_RISK_PCT, MIN_RISK_USD)
    max_position_usd = min(max_risk_usd / req.stop_loss_pct, MAX_POSITION_USD) if req.stop_loss_pct > 0 else 0
    units = max_position_usd / current_price if current_price > 0 else 0.0
    units = round(units, 4)  # Soporta fraccionales (e.g., 1.7034 shares)
    buying_power = account.get("buying_power", 0.0)
    estimated_cost = units * current_price
    if units <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Position size is 0 units at ${current_price:.2f} — price too high for available capital",
        )
    if estimated_cost > buying_power:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient buying power: need ${estimated_cost:.2f}, available ${buying_power:.2f}",
        )
    estimated_risk = units * current_price * req.stop_loss_pct
    estimated_value = units * current_price

    if req.action == "BUY":
        stop_loss_price = round(current_price * (1 - req.stop_loss_pct), 2)
        take_profit_price = round(current_price * (1 + req.take_profit_pct), 2)
    else:  # SELL
        stop_loss_price = round(current_price * (1 + req.stop_loss_pct), 2)
        take_profit_price = round(current_price * (1 - req.take_profit_pct), 2)

    return {
        "approved": result.approved,
        "requires_human_approval": False,
        "symbol": symbol,
        "action": req.action,
        "current_price": current_price,
        "recommended_units": units,
        "estimated_value": round(estimated_value, 2),
        "estimated_risk_usd": round(estimated_risk, 2),
        "stop_loss_pct": req.stop_loss_pct,
        "take_profit_pct": req.take_profit_pct,
        "stop_loss_price": stop_loss_price,
        "take_profit_price": take_profit_price,
        "reasons": result.reasons,
    }


@app.get("/signals")
def get_signals(since_hours: int = 24):
    return [{"id": s.id, "symbol": s.symbol, "strength": s.strength,
             "rsi": s.rsi, "macd": s.macd, "volume_ratio": s.volume_ratio,
             "created_at": s.created_at.isoformat()} for s in get_pending_signals(since_hours=since_hours)]


@app.get("/trades")
def get_trades():
    return [{"id": t.id, "symbol": t.symbol, "action": t.action,
             "quantity": t.quantity, "entry_price": t.entry_price,
             "stop_loss_price": t.stop_loss_price, "take_profit_price": t.take_profit_price,
             "signal_strength": t.signal_strength, "status": t.status,
             "opened_at": t.opened_at.isoformat()} for t in get_open_trades()]


@app.get("/executions")
def get_executions(limit: int = 10):
    try:
        fills = client.get_executions(since_days=7)
        return {"source": "ibkr", "count": len(fills), "executions": fills[:limit]}
    except Exception as exc:
        return {"source": "ibkr", "error": str(exc), "count": 0, "executions": []}


@app.get("/account/commission-report")
def get_commission_report():
    """Retorna historial real de comisiones y P&L de IBKR."""
    try:
        return client.get_commissions(since_days=30)
    except Exception as exc:
        return {"error": str(exc), "fills": [], "total_commission": 0, "total_realized_pnl": 0, "fill_count": 0}


@app.get("/patterns/{symbol}")
def get_patterns(symbol: str):
    return [{"id": p.id, "pattern": p.pattern_text, "wins": p.win_count,
             "losses": p.loss_count} for p in get_patterns_for_symbol(symbol.upper())]


@app.post("/orders/place", dependencies=[Depends(require_control_key)])
def orders_place(req: OrderPreviewRequest):
    from app.config.settings import REQUIRE_HUMAN_APPROVAL, PAPER_TRADING_ONLY
    symbol = req.symbol.upper()

    try:
        price_data = client.get_stock_price(symbol)
        current_price = price_data["market_price"]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not fetch price: {exc}")
    try:
        account = client.get_account()
        capital = get_operating_capital(account.get("net_liquidation", 0.0))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not fetch account: {exc}")
    try:
        portfolio = client.get_portfolio()
        active_positions = len(portfolio)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not fetch portfolio: {exc}")

    result = validate_order(
        symbol=symbol, action=req.action, quantity=req.quantity,
        order_type=req.order_type, stop_loss_pct=req.stop_loss_pct,
        capital=capital, active_positions=active_positions,
        now=datetime.now(tz=MARKET_TZ),
    )

    if not result.approved:
        raise HTTPException(status_code=403, detail={"approved": False, "reasons": result.reasons})

    max_risk_usd = max(capital * MAX_RISK_PCT, MIN_RISK_USD)
    max_position_usd = min(max_risk_usd / req.stop_loss_pct, MAX_POSITION_USD) if req.stop_loss_pct > 0 else 0
    units = max_position_usd / current_price if current_price > 0 else 0.0
    units = round(units, 4)
    buying_power = account.get("buying_power", 0.0)
    estimated_cost = units * current_price
    if units <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Position size is 0 units at ${current_price:.2f} — price too high for available capital",
        )
    if estimated_cost > buying_power:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient buying power: need ${estimated_cost:.2f}, available ${buying_power:.2f}",
        )

    if REQUIRE_HUMAN_APPROVAL:
        from app.notifications.telegram import request_approval
        stop_loss_price_val = round(current_price * (1 - req.stop_loss_pct), 2)
        take_profit_price_val = round(current_price * (1 + req.take_profit_pct), 2)
        estimated_risk = round(units * current_price * req.stop_loss_pct, 2)

        approved = request_approval(
            symbol=symbol,
            action=req.action,
            units=units,
            entry_price=current_price,
            stop_loss_price=stop_loss_price_val,
            take_profit_price=take_profit_price_val,
            estimated_risk_usd=estimated_risk,
        )
        if not approved:
            raise HTTPException(status_code=403, detail={
                "approved": False,
                "reasons": ["Order rejected or timed out waiting for human approval"],
            })

    # Use LMT for entries to avoid slippage
    entry_order_type = req.order_type.upper()
    limit_price = req.limit_price
    if entry_order_type == "MKT":
        from app.risk.lmt_orders import calculate_limit_price
        limit_price = calculate_limit_price(current_price, req.action)
        entry_order_type = "LMT"

    # Pre-flight checks
    from app.ibkr.dedup import PreflightChecker, get_deduplicator
    preflight = PreflightChecker(client).check(symbol, req.action, units, entry_order_type, limit_price)
    if not preflight.ok:
        raise HTTPException(status_code=403, detail={"approved": False, "reasons": [preflight.reason]})

    # Deduplication
    dedup = get_deduplicator()
    if dedup.is_duplicate(symbol, req.action):
        raise HTTPException(status_code=429, detail={"approved": False, "reasons": ["Duplicate order blocked (within 30s window)"]})

    # Place and monitor order
    from app.notifications.order_monitor import OrderExecutionMonitor
    monitor = OrderExecutionMonitor(client)
    order_result = monitor.place_and_monitor(
        symbol=symbol,
        action=req.action,
        quantity=units,
        order_type=entry_order_type,
        limit_price=limit_price,
    )

    if not order_result.success:
        raise HTTPException(status_code=500, detail=f"Order placement failed: {order_result.reason}")

    dedup.record(symbol, req.action)

    # Use real fill price if available
    fill_price = order_result.fill_price or current_price

    from app.infrastructure.db.compat import insert_trade
    from app.db.models import Trade
    from datetime import datetime as dt
    price_for_sl = fill_price or current_price
    if req.action == "BUY":
        stop_loss_price = round(price_for_sl * (1 - req.stop_loss_pct), 2)
        take_profit_price = round(price_for_sl * (1 + req.take_profit_pct), 2)
    else:  # SELL
        stop_loss_price = round(price_for_sl * (1 + req.stop_loss_pct), 2)
        take_profit_price = round(price_for_sl * (1 - req.take_profit_pct), 2)
    insert_trade(Trade(
        id=None, symbol=symbol, action=req.action, quantity=units,
        entry_price=price_for_sl, stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price, stop_loss_pct=req.stop_loss_pct,
        take_profit_pct=req.take_profit_pct, signal_strength="MANUAL",
        llm_justification="Placed via MCP", status="OPEN",
        exit_price=None, exit_reason=None, pnl_usd=None, pnl_pct=None,
        opened_at=dt.utcnow(), closed_at=None,
        order_id=order_result.order_id,
        trade_status="FILLED",
        entry_fill_price=fill_price,
        remaining_quantity=units,
    ))

    return {
        "status": "placed",
        "mode": "paper" if PAPER_TRADING_ONLY else "live",
        "symbol": symbol,
        "action": req.action,
        "units": units,
        "entry_price": price_for_sl,
        "fill_price": fill_price,
        "stop_loss_price": stop_loss_price,
        "take_profit_price": take_profit_price,
        "order_id": order_result.order_id,
    }


@app.get("/symbols/proposals")
def get_proposals():
    from app.infrastructure.db.compat import get_pending_proposals
    return get_pending_proposals()


@app.post("/symbols/approve/{symbol}", dependencies=[Depends(require_control_key)])
def approve_symbol_endpoint(symbol: str):
    from app.infrastructure.db.compat import approve_symbol
    symbol = symbol.upper()
    ib_client = client if client and client.ib.isConnected() else None
    approve_symbol(symbol, ib_client=ib_client)
    return {"status": "approved", "symbol": symbol, "message": f"{symbol} approved in DB universe."}



# --- System endpoints ---

@app.get("/system/status")
def system_status():
    from app.system.controller import get_controller
    from app.infrastructure.db.compat import get_daily_pnl, get_open_trades
    from app.config.settings import PAPER_TRADING_ONLY
    try:
        ctrl = get_controller()
        status = ctrl.status()
    except RuntimeError:
        status = {
            "paused": False,
            "mode": "paper" if PAPER_TRADING_ONLY else "live",
            "circuit_breaker_threshold": "5%",
        }
    open_trades = get_open_trades()
    daily_pnl = get_daily_pnl()
    try:
        _acct = client.get_account()
        _capital = get_operating_capital(_acct.get("net_liquidation", 0.0))
    except Exception:
        from app.config.settings import CAPITAL_CAP
        _capital = CAPITAL_CAP
    
    # Estado de conexion IB Gateway
    ib_connected = False
    try:
        ib_connected = client.ib.isConnected()
    except Exception:
        pass
    
    payload = {
        **status,
        "ib_connected": ib_connected,
        "open_positions": len(open_trades),
        "daily_pnl_usd": round(daily_pnl, 2),
        "daily_pnl_pct": round(daily_pnl / _capital * 100, 2) if _capital else 0.0,
        "operating_capital": _capital,
    }
    if payload["mode"] == "live":
        try:
            portfolio = client.get_portfolio()
            floating_live_pnl = sum(float(p.get("unrealized_pnl") or 0.0) for p in portfolio)
            payload["daily_pnl_usd"] = round(floating_live_pnl, 2)
            payload["daily_pnl_pct"] = round(floating_live_pnl / _capital * 100, 2) if _capital else 0.0
        except Exception as exc:
            logger.warning(f"system_status live pnl fallback failed: {exc}")
    return payload


@app.post("/system/pause", dependencies=[Depends(require_control_key)])
def system_pause():
    from app.system.controller import get_controller
    get_controller().pause()
    return {"status": "paused"}


@app.post("/system/resume", dependencies=[Depends(require_control_key)])
def system_resume():
    from app.system.controller import get_controller
    get_controller().resume()
    return {"status": "resumed"}


@app.post("/notifications/level/{level}")
def set_notification_level(level: str):
    """Set notification level: critico, normal, verbose."""
    from app.notifications.policy import NotificationPolicy
    level_map = {"critico": "critical_only", "normal": "normal", "verbose": "verbose"}
    mapped = level_map.get(level.lower())
    if mapped is None:
        raise HTTPException(status_code=400, detail=f"Invalid level '{level}'. Use: critico, normal, verbose")
    try:
        policy = NotificationPolicy()
        policy.set_level(mapped)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "ok", "level": level, "mapped": mapped}


@app.post("/system/mode/{mode}", dependencies=[Depends(require_control_key)])
def system_mode(mode: str):
    from app.system.controller import get_controller
    try:
        get_controller().set_mode(mode)
        return {"status": "ok", "mode": mode}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/trades/closed")
def get_closed_trades_endpoint(limit: int = 10):
    from app.infrastructure.db.compat import get_closed_trades
    trades = get_closed_trades(limit)
    return [
        {
            "id": t.id, "symbol": t.symbol, "action": t.action,
            "quantity": t.quantity, "entry_price": t.entry_price,
            "exit_price": t.exit_price, "exit_reason": t.exit_reason,
            "pnl_usd": t.pnl_usd, "pnl_pct": t.pnl_pct,
            "opened_at": t.opened_at.isoformat(),
            "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        }
        for t in trades
    ]


@app.post("/orders/close/id/{trade_id}", dependencies=[Depends(require_control_key)])
def close_trade_by_id(trade_id: int):
    """Request to close a position by trade ID — sends Telegram confirmation."""
    from app.infrastructure.db.compat import get_open_trades
    trades = [t for t in get_open_trades() if t.id == trade_id]
    if not trades:
        raise HTTPException(status_code=404, detail="Trade not found or already closed")
    trade = trades[0]
    try:
        from app.notifications.telegram import notify
        notify(
            f"\U0001f514 Solicitud de cierre desde dashboard:\n"
            f"<b>{trade.symbol}</b> {trade.action} {trade.quantity}u\n"
            f"Responde /cerrar {trade.symbol} para confirmar."
        )
        return {"message": f"Confirmación enviada por Telegram para {trade.symbol}",
                "trade_id": trade_id, "symbol": trade.symbol}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/orders/close/{symbol}", dependencies=[Depends(require_control_key)])
def close_position(symbol: str):
    from app.infrastructure.db.compat import get_open_trades, close_trade
    symbol = symbol.upper()
    trades = [t for t in get_open_trades() if t.symbol == symbol]
    if not trades:
        raise HTTPException(status_code=404, detail=f"No open position for {symbol}")
    trade = trades[0]
    try:
        price_data = client.get_stock_price(symbol)
        current_price = price_data["market_price"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not fetch price: {e}")
    
    # 1) Enviar orden de cierre REAL a IBKR
    close_action = "SELL" if trade.action == "BUY" else "BUY"
    from app.ibkr.dedup import get_deduplicator, PreflightChecker
    dedup = get_deduplicator()
    if dedup.is_duplicate(trade.symbol, close_action):
        raise HTTPException(status_code=429, detail="Duplicate close order blocked")
    preflight = PreflightChecker(client).check(trade.symbol, close_action, trade.quantity, "MKT")
    if not preflight.ok:
        raise HTTPException(status_code=403, detail=preflight.reason)

    try:
        from app.ibkr.fill_tracker import get_fill_price_fallback
        order_result = client.place_order(
            symbol=trade.symbol,
            action=close_action,
            quantity=trade.quantity,
            order_type="MKT",
        )
        logger.info(f"IBKR close order sent: {close_action} {trade.quantity} {trade.symbol}")
        dedup.record(trade.symbol, close_action)
        try:
            fill_price = get_fill_price_fallback(client, order_result.get("order_id", ""), trade.symbol)
        except Exception:
            fill_price = current_price
    except Exception as e:
        logger.error(f"Failed to send IBKR close order for {trade.symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"IBKR close order failed: {e}")

    # 2) Actualizar base de datos local
    pnl_pct = (fill_price - trade.entry_price) / trade.entry_price
    if trade.action == "SELL":
        pnl_pct = -pnl_pct
    pnl_usd = pnl_pct * trade.entry_price * trade.quantity
    close_trade(trade.id, fill_price, "MANUAL_CLOSE", round(pnl_usd, 2), round(pnl_pct, 4), exit_fill_price=fill_price)
    return {
        "status": "closed", "symbol": symbol,
        "exit_price": fill_price,
        "pnl_usd": round(pnl_usd, 2),
        "pnl_pct": round(pnl_pct * 100, 2),
    }


@app.post("/orders/close-all", dependencies=[Depends(require_control_key)])
def close_all_positions():
    from app.infrastructure.db.compat import get_open_trades, close_trade
    trades = get_open_trades()
    if not trades:
        return {"status": "ok", "closed": 0}
    closed = []
    failed = []
    from app.ibkr.dedup import get_deduplicator, PreflightChecker
    from app.ibkr.fill_tracker import get_fill_price_fallback
    dedup = get_deduplicator()
    for trade in trades:
        try:
            price_data = client.get_stock_price(trade.symbol)
            current_price = price_data["market_price"]
            
            # Enviar orden de cierre REAL a IBKR
            close_action = "SELL" if trade.action == "BUY" else "BUY"
            if dedup.is_duplicate(trade.symbol, close_action):
                failed.append({"symbol": trade.symbol, "error": "Duplicate close blocked"})
                continue
            preflight = PreflightChecker(client).check(trade.symbol, close_action, trade.quantity, "MKT")
            if not preflight.ok:
                failed.append({"symbol": trade.symbol, "error": preflight.reason})
                continue
            try:
                order_result = client.place_order(
                    symbol=trade.symbol,
                    action=close_action,
                    quantity=trade.quantity,
                    order_type="MKT",
                )
                logger.info(f"IBKR close order sent: {close_action} {trade.quantity} {trade.symbol}")
                dedup.record(trade.symbol, close_action)
                try:
                    fill_price = get_fill_price_fallback(client, order_result.get("order_id", ""), trade.symbol)
                except Exception:
                    fill_price = current_price
            except Exception as e:
                logger.error(f"Failed to send IBKR close order for {trade.symbol}: {e}")
                failed.append({"symbol": trade.symbol, "error": str(e)})
                continue
            
            pnl_pct = (fill_price - trade.entry_price) / trade.entry_price
            if trade.action == "SELL":
                pnl_pct = -pnl_pct
            pnl_usd = pnl_pct * trade.entry_price * trade.quantity
            close_trade(trade.id, fill_price, "MANUAL_CLOSE_ALL", round(pnl_usd, 2), round(pnl_pct, 4), exit_fill_price=fill_price)
            closed.append({"symbol": trade.symbol, "pnl_usd": round(pnl_usd, 2)})
        except Exception as e:
            logger.error(f"Could not close {trade.symbol}: {e}")
            failed.append({"symbol": trade.symbol, "error": str(e)})
    
    return {"status": "ok", "closed": len(closed), "failed": len(failed), "positions": closed}


from fastapi.responses import HTMLResponse


@app.get("/logs")
def get_logs(lines: int = 100):
    """Return last N lines of bot.log for dashboard log viewer."""
    import os
    log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "bot.log")
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        last_lines = all_lines[-lines:]
        return {"lines": lines, "count": len(last_lines), "log": "".join(last_lines)}
    except Exception as e:
        return {"lines": lines, "count": 0, "log": f"Error reading log: {e}"}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    from app.api.dashboard import render_dashboard_html
    return HTMLResponse(content=render_dashboard_html())


@app.get("/dashboard/data")
def dashboard_data():
    """JSON endpoint consumed by the React dashboard every 30s.

    Uses DashboardDataQuery read model for fast aggregation.
    """
    from app.infrastructure.db.read_models.dashboard_query import DashboardDataQuery
    return DashboardDataQuery().execute()


@app.get("/dashboard/symbol/{symbol}")
def dashboard_symbol_data(symbol: str, period: str = "intraday"):
    """Lazy-loaded symbol data for dashboard chart. Uses IBDataLayer cache."""
    import pandas as pd
    try:
        from app.llm.agent import get_data_layer
        data_layer = get_data_layer()
        result: dict = {"symbol": symbol.upper(), "period": period, "bars": []}
        if period == "intraday":
            df = data_layer.get_ohlcv(symbol, "1 D", "5 mins", "dashboard_chart")
        else:
            df = data_layer.get_ohlcv(symbol, "30 D", "1 day", "dashboard_chart")
        if df is not None and len(df) > 0:
            result["bars"] = [
                {
                    "time": i,
                    "open": round(float(r.get("open", r["close"])), 4),
                    "high": round(float(r.get("high", r["close"])), 4),
                    "low": round(float(r.get("low", r["close"])), 4),
                    "close": round(float(r["close"]), 4),
                    "volume": int(r.get("volume", 0)),
                }
                for i, (_, r) in enumerate(df.iterrows())
            ]
        if period in ("intraday", "daily", "indicators") and df is not None and len(df) >= 15:
            from app.analysis.indicators import _compute_rsi
            # RSI series
            rsi_series = []
            for i in range(14, len(df)):
                slice_df = df.iloc[:i + 1]
                rsi = _compute_rsi(slice_df)
                if rsi is not None:
                    rsi_series.append({"time": i, "value": round(rsi, 2)})
            result["rsi_series"] = rsi_series

            # MACD series
            ema12 = df["close"].ewm(span=12).mean()
            ema26 = df["close"].ewm(span=26).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9).mean()
            macd_series = []
            for i in range(26, len(df)):
                macd_series.append({
                    "time": i,
                    "macd": round(float(macd_line.iloc[i]), 4),
                    "signal": round(float(signal_line.iloc[i]), 4),
                    "histogram": round(float(macd_line.iloc[i] - signal_line.iloc[i]), 4),
                })
            result["macd_series"] = macd_series

            # Bollinger Bands
            sma20 = df["close"].rolling(20).mean()
            std20 = df["close"].rolling(20).std()
            boll_series = []
            for i in range(20, len(df)):
                if not pd.isna(sma20.iloc[i]):
                    boll_series.append({
                        "time": i,
                        "upper": round(float(sma20.iloc[i] + 2 * std20.iloc[i]), 4),
                        "middle": round(float(sma20.iloc[i]), 4),
                        "lower": round(float(sma20.iloc[i] - 2 * std20.iloc[i]), 4),
                    })
            result["boll_series"] = boll_series
        return result
    except Exception as e:
        logger.error(f"dashboard_symbol_data({symbol}): {e}")
        return {"symbol": symbol, "bars": [], "error": str(e)}


@app.get("/backtest/{symbol}")
def run_backtest_endpoint(symbol: str, days: int = 180):
    """Queue a backtest job. Returns immediately with job_id."""
    from app.application.services.job_runner import get_global_runner
    from app.interfaces.api.routes.jobs_routes import _run_backtest
    symbol = symbol.upper()
    if symbol not in set(_get_universe_symbols(auto_approve_open=True)):
        raise HTTPException(status_code=403, detail=f"Symbol {symbol} not in approved DB list")
    runner = get_global_runner()
    job_id = runner.submit(
        job_type="backtest",
        fn=_run_backtest,
        timeout_seconds=60,
        symbol=symbol,
        days=days,
    )
    return {"job_id": job_id}


@app.get("/candidate-analysis/{symbol}")
def candidate_analysis_endpoint(symbol: str):
    """Queue an LLM analysis job. Returns immediately with job_id."""
    from app.application.services.job_runner import get_global_runner
    from app.interfaces.api.routes.jobs_routes import _run_llm_analysis
    runner = get_global_runner()
    job_id = runner.submit(
        job_type="llm-analysis",
        fn=_run_llm_analysis,
        timeout_seconds=60,
        symbol=symbol.upper(),
    )
    return {"job_id": job_id}


@app.get("/analysis/indicator/{symbol}/{indicator_name}")
def single_indicator_endpoint(symbol: str, indicator_name: str):
    """Compute a single indicator for a symbol."""
    from app.analysis.indicators import compute_single_indicator
    from app.llm.agent import get_data_layer
    symbol = symbol.upper()
    try:
        data_layer = get_data_layer()
        df = data_layer.get_ohlcv(symbol, "30 D", "1 day", "on_demand")
        if df is None:
            raise HTTPException(status_code=404, detail=f"No data for {symbol}")
        value = compute_single_indicator(indicator_name, df)
        return {"symbol": symbol, "indicator": indicator_name, "value": value}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/universe/watchlist")
def universe_watchlist():
    """Return universe symbols with their watchlist scores."""
    from app.infrastructure.db.compat import get_connection
    conn = get_connection()
    rows = conn.execute("SELECT * FROM watchlist_scores ORDER BY watchlist_score DESC").fetchall()
    conn.close()
    scores = {r["symbol"]: r["watchlist_score"] for r in rows}
    return [
        {"symbol": s, "watchlist_score": scores.get(s, 0.5), "active": True}
        for s in get_approved_symbols()
    ]


@app.get("/candidate-decisions")
def get_candidate_decisions_endpoint(limit: int = 20):
    """Return candidate decisions with return metrics."""
    from app.infrastructure.db.compat import get_connection
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM candidate_decisions ORDER BY decision_date DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/symbol-parameters/{symbol}")
def get_symbol_parameters_endpoint(symbol: str):
    """Return adaptive parameters for a symbol."""
    from app.infrastructure.db.compat import get_or_create_symbol_parameters, init_analysis_tables
    init_analysis_tables()
    import dataclasses
    params = get_or_create_symbol_parameters(symbol.upper())
    return dataclasses.asdict(params)


@app.get("/market-permissions")
def get_market_permissions_endpoint(refresh: bool = False):
    """Retorna exchanges y product types operables via IB Gateway."""
    from app.ibkr.market_permissions import get_permissions_report
    try:
        report = get_permissions_report(force_refresh=refresh)
        return report
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=str(e))


# --- Reports endpoints ---

@app.get("/reports/list")
def list_reports_json(limit: int = 20):
    """JSON list of recent reports."""
    from app.infrastructure.db.compat import get_reports
    return {"reports": get_reports(limit=limit)}


@app.get("/reports", response_class=HTMLResponse)
def reports_page():
    """HTML reports index page."""
    from app.infrastructure.db.compat import get_reports
    reports = get_reports(limit=30)
    rows = ""
    for r in reports:
        type_badge = "Pre-mercado" if r["report_type"] == "pre_market" else "Operaciones"
        rows += f"""
        <tr>
          <td>{type_badge}</td>
          <td>{r['report_date']}</td>
          <td><a href="/reports/{r['id']}">{r['title']}</a></td>
          <td>{r['created_at'][:16]}</td>
          <td><button onclick="delReport({r['id']})" style="background:rgba(244,63,94,.15);color:#F43F5E;border:1px solid rgba(244,63,94,.3);padding:2px 8px;border-radius:3px;cursor:pointer;font-size:.75rem">Borrar</button></td>
        </tr>"""
    return HTMLResponse(content=f"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reportes — IBKR AI Trader</title>
<link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500&family=Barlow+Condensed:wght@400;600&display=swap" rel="stylesheet">
<style>
body{{background:#06090F;color:#E2E8F0;font-family:"Barlow Condensed",sans-serif;max-width:1000px;margin:0 auto;padding:20px}}
h1{{color:#38BDF8;font-size:1.6rem;border-bottom:1px solid #1E2D42;padding-bottom:8px}}
table{{width:100%;border-collapse:collapse;font-family:"Fira Code",monospace;font-size:.82rem;margin-top:16px}}
th{{color:#64748B;text-align:left;padding:6px 10px;border-bottom:1px solid #1E2D42;font-size:.7rem;letter-spacing:.1em;text-transform:uppercase}}
td{{padding:8px 10px;border-bottom:1px solid rgba(30,45,66,.5)}}
a{{color:#38BDF8;text-decoration:none}}a:hover{{text-decoration:underline}}
.nav{{display:flex;gap:12px;margin-bottom:20px;font-family:"Fira Code",monospace;font-size:.8rem}}
.nav a{{color:#38BDF8}}
.empty{{color:#334155;font-family:"Fira Code",monospace;padding:40px;text-align:center}}
</style>
</head><body>
<div class="nav"><a href="/dashboard">&larr; Dashboard</a></div>
<h1>Reportes de Analisis</h1>
{'<table><thead><tr><th>Tipo</th><th>Fecha</th><th>Titulo</th><th>Creado</th><th></th></tr></thead><tbody>' + rows + '</tbody></table>' if reports else '<div class="empty">// Sin reportes aun — se generan automaticamente antes de apertura de mercado</div>'}
<script>
async function delReport(id){{
  if(!confirm('Borrar este reporte?'))return;
  await fetch('/reports/'+id,{{method:'DELETE'}});
  location.reload();
}}
</script>
</body></html>""")


@app.get("/reports/{report_id}", response_class=HTMLResponse)
def view_report(report_id: int):
    """Render a single report as HTML."""
    from app.infrastructure.db.compat import get_report_by_id
    report = get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    import re
    html_content = report["content_md"]
    # Headers (process largest first to avoid partial replacement)
    for i in range(6, 0, -1):
        html_content = re.sub(
            rf'^{"#" * i}\s+(.+)$', rf'<h{i}>\1</h{i}>', html_content, flags=re.MULTILINE
        )
    # Bold / italic
    html_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_content)
    html_content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html_content)
    # Inline code
    html_content = re.sub(r'`(.+?)`', r'<code>\1</code>', html_content)
    # Blockquote
    html_content = re.sub(r'^> (.+)$', r'<blockquote>\1</blockquote>', html_content, flags=re.MULTILINE)
    # Tables
    lines = html_content.split('\n')
    out_lines = []
    in_table = False
    for line in lines:
        if '|' in line and line.strip().startswith('|'):
            if not in_table:
                out_lines.append('<table>')
                in_table = True
            if re.match(r'^\|[-|\s]+\|$', line.strip()):
                continue  # skip separator row
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            row = ''.join(f'<td>{c}</td>' for c in cells)
            out_lines.append(f'<tr>{row}</tr>')
        else:
            if in_table:
                out_lines.append('</table>')
                in_table = False
            out_lines.append(line)
    if in_table:
        out_lines.append('</table>')
    html_content = '\n'.join(out_lines)
    # Lists
    html_content = re.sub(r'^- (.+)$', r'<li>\1</li>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'(<li>.*</li>\n?)+', r'<ul>\g<0></ul>', html_content, flags=re.DOTALL)
    # HR
    html_content = html_content.replace('---', '<hr>')
    # Paragraphs
    html_content = re.sub(r'\n\n', '</p><p>', html_content)

    return HTMLResponse(content=f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{report['title']}</title>
<link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500&family=Barlow+Condensed:wght@400;600&display=swap" rel="stylesheet">
<style>
body{{background:#06090F;color:#E2E8F0;font-family:"Barlow Condensed",sans-serif;max-width:900px;margin:0 auto;padding:20px;line-height:1.6}}
h1{{font-size:1.8rem;color:#38BDF8;border-bottom:1px solid #1E2D42;padding-bottom:8px}}
h2{{font-size:1.3rem;color:#94A3B8;margin-top:24px}}
h3{{font-size:1.1rem;color:#E2E8F0}}
code{{font-family:"Fira Code",monospace;background:#111D2E;padding:2px 6px;border-radius:3px;color:#38BDF8}}
blockquote{{border-left:3px solid #38BDF8;margin:0;padding:8px 16px;background:#0C1421;color:#94A3B8;font-style:italic}}
table{{width:100%;border-collapse:collapse;margin:12px 0;font-family:"Fira Code",monospace;font-size:.82rem}}
td{{padding:6px 10px;border:1px solid #1E2D42}}
tr:nth-child(even){{background:#0C1421}}
ul{{padding-left:20px}}
li{{margin:4px 0}}
hr{{border:none;border-top:1px solid #1E2D42;margin:20px 0}}
em{{color:#94A3B8}}
strong{{color:#FBBF24}}
.nav{{display:flex;gap:12px;margin-bottom:20px;font-family:"Fira Code",monospace;font-size:.8rem}}
.nav a{{color:#38BDF8;text-decoration:none}}
</style>
</head>
<body>
<div class="nav">
  <a href="/reports">&larr; Todos los reportes</a>
  <a href="/dashboard">Dashboard</a>
</div>
<p><em>Tipo: {report['report_type']} | Fecha: {report['report_date']} | Creado: {report['created_at'][:16]}</em></p>
<div>{html_content}</div>
</body>
</html>""")


@app.delete("/reports/{report_id}")
def delete_report_endpoint(report_id: int):
    from app.infrastructure.db.compat import delete_report
    if not delete_report(report_id):
        raise HTTPException(status_code=404, detail="Report not found")
    return {"deleted": True, "id": report_id}


@app.post("/analyze/{symbol}")
def trigger_analysis(symbol: str):
    """Trigger on-demand LLM analysis for any symbol (including market trend candidates)."""
    from app.notifications.telegram import notify
    sym = symbol.upper()
    try:
        notify(f"📊 Análisis solicitado desde dashboard: <b>{sym}</b>\nUsa /analizar {sym} para ver el resultado.")
        return {"message": f"Análisis de {sym} en cola. Recibirás el resultado en Telegram.", "symbol": sym}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/refresh")
def manual_refresh():
    """Manually trigger news and scanner refresh (for dashboard button)."""
    results = {}
    try:
        from app.scanner.news_fetcher import fetch_and_cache_news
        dl = get_data_layer()
        fetch_and_cache_news(dl)
        results["news"] = "ok"
    except Exception as e:
        results["news"] = str(e)
    try:
        from app.scanner.market_scanner import fetch_and_cache_scanner, fetch_and_cache_sectors
        dl = get_data_layer()
        fetch_and_cache_scanner(dl)
        fetch_and_cache_sectors(dl)
        results["scanner"] = "ok"
    except Exception as e:
        results["scanner"] = str(e)
    return {"refreshed": True, "results": results}


def get_data_layer():
    """Helper to retrieve the shared IBDataLayer instance."""
    try:
        from app.llm.agent import get_data_layer as _get_dl
        return _get_dl()
    except Exception:
        return None
