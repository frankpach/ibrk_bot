# app/api/main.py
import logging
from datetime import datetime
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException

from app.config.settings import MARKET_TZ, MAX_RISK_PCT, MIN_RISK_USD, MAX_POSITION_USD
from app.api.capital import get_operating_capital
from app.ibkr.client import get_client
from app.risk.validator import validate_order
from app.db.database import (
    get_pending_signals,
    get_open_trades,
    get_patterns_for_symbol,
    init_db,
    get_approved_symbols,
)

logger = logging.getLogger(__name__)
app = FastAPI(title="IBKR AI Trader API")
client = get_client()


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
    from app.db.database import get_approved_symbols_with_meta
    symbols = get_approved_symbols_with_meta()
    return {"symbols": [s["symbol"] for s in symbols], "meta": symbols}


@app.post("/symbols/propose")
def propose_symbol(req: SymbolProposalRequest):
    from app.db.database import save_symbol_proposal
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


@app.post("/orders/place")
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

    from app.db.database import insert_trade
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
    from app.db.database import get_pending_proposals
    return get_pending_proposals()


@app.post("/symbols/approve/{symbol}")
def approve_symbol_endpoint(symbol: str):
    from app.db.database import approve_symbol
    symbol = symbol.upper()
    ib_client = client if client and client.ib.isConnected() else None
    approve_symbol(symbol, ib_client=ib_client)
    return {"status": "approved", "symbol": symbol, "message": f"{symbol} approved in DB universe."}



# --- System endpoints ---

@app.get("/system/status")
def system_status():
    from app.system.controller import get_controller
    from app.db.database import get_daily_pnl, get_open_trades
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
    
    return {
        **status,
        "ib_connected": ib_connected,
        "open_positions": len(open_trades),
        "daily_pnl_usd": round(daily_pnl, 2),
        "daily_pnl_pct": round(daily_pnl / _capital * 100, 2) if _capital else 0.0,
        "operating_capital": _capital,
    }


@app.post("/system/pause")
def system_pause():
    from app.system.controller import get_controller
    get_controller().pause()
    return {"status": "paused"}


@app.post("/system/resume")
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


@app.post("/system/mode/{mode}")
def system_mode(mode: str):
    from app.system.controller import get_controller
    try:
        get_controller().set_mode(mode)
        return {"status": "ok", "mode": mode}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/trades/closed")
def get_closed_trades_endpoint(limit: int = 10):
    from app.db.database import get_closed_trades
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


@app.post("/orders/close/id/{trade_id}")
def close_trade_by_id(trade_id: int):
    """Request to close a position by trade ID — sends Telegram confirmation."""
    from app.db.database import get_open_trades
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


@app.post("/orders/close/{symbol}")
def close_position(symbol: str):
    from app.db.database import get_open_trades, close_trade
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


@app.post("/orders/close-all")
def close_all_positions():
    from app.db.database import get_open_trades, close_trade
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
    """JSON endpoint consumed by the React dashboard every 30s."""
    from pathlib import Path
    from app.db.database import (
        get_open_trades, get_closed_trades, get_pending_signals,
        get_patterns_for_symbol, get_daily_pnl, get_closed_trades_by_symbol,
        get_approved_symbols, get_account_history,
    )

    # ── Status ──
    daily_pnl = get_daily_pnl()
    open_trades = get_open_trades()

    account_history = []
    latest_account = {}
    try:
        account_history = get_account_history(days=30)
        if account_history:
            latest_account = account_history[-1]
    except Exception as e:
        logger.warning(f"Account history failed: {e}")

    _nl = float(latest_account.get("net_liquidation") or 0.0)
    _bp = float(latest_account.get("buying_power") or 0.0)
    _capital = get_operating_capital(_nl) if _nl else None
    if not _capital:
        from app.config.settings import CAPITAL_CAP
        _capital = CAPITAL_CAP
    if not latest_account:
        latest_account = {
            "net_liquidation": round(_nl, 2),
            "buying_power": round(_bp, 2),
        }

    # Detect mode from settings + controller
    from app.config.settings import PAPER_TRADING_ONLY
    _mode = "paper" if PAPER_TRADING_ONLY else "live"
    latest_account_date = str(latest_account.get("date") or "")
    today_utc = datetime.utcnow().strftime("%Y-%m-%d")

    status = {
        "mode": _mode,
        "paused": False,
        "daily_pnl_usd": round(daily_pnl, 2),
        "daily_pnl_pct": round(daily_pnl / _capital * 100, 4) if _capital else 0.0,
        "open_positions": len(open_trades),
        "operating_capital": _capital,
        "simulated_capital": _capital,
        "net_liquidation": round(_nl, 2),
        "buying_power": round(_bp, 2),
        "ib_data_live": bool(latest_account_date and latest_account_date == today_utc),
    }
    try:
        from app.system.controller import get_controller
        ctrl = get_controller()
        status["mode"] = ctrl.mode
        status["paused"] = ctrl.is_paused
    except RuntimeError:
        pass
    status["drawdown_pct"] = 0.0

    # ── Open trades ──
    trades_out = [
        {
            "id": t.id,
            "trade_id": t.id,
            "symbol": t.symbol, "action": t.action,
            "quantity": t.quantity,
            "entry_price": t.entry_fill_price or t.entry_price,
            "stop_loss_price": t.stop_loss_price,
            "take_profit_price": t.take_profit_price,
            "signal_strength": t.signal_strength,
            "opened_at": t.opened_at.isoformat() if hasattr(t.opened_at, 'isoformat') else str(t.opened_at),
        }
        for t in open_trades
    ]

    # ── Closed trades (last 8, with pnl_pct) ──
    closed_out = [
        {
            "symbol": t.symbol, "action": t.action,
            "pnl_usd": t.pnl_usd, "pnl_pct": t.pnl_pct,
            "exit_reason": t.exit_reason,
            "closed_at": t.closed_at.isoformat() if t.closed_at and hasattr(t.closed_at, 'isoformat') else str(t.closed_at or ""),
        }
        for t in get_closed_trades(limit=8)
    ]

    # ── Signals (include extra_indicators for weekly_trend) ──
    signals_out = [
        {
            "symbol": s.symbol, "strength": s.strength,
            "rsi": s.rsi, "volume_ratio": s.volume_ratio,
            "extra_indicators": s.extra_indicators or "{}",
            "created_at": s.created_at.isoformat() if hasattr(s.created_at, 'isoformat') else str(s.created_at),
        }
        for s in get_pending_signals()
    ]

    # ── Patterns (from approved symbols) ──
    patterns_out = []
    try:
        syms = get_approved_symbols()[:8]
        for sym in syms:
            for p in get_patterns_for_symbol(sym, limit=1):
                patterns_out.append({
                    "symbol": p.symbol,
                    "pattern_text": p.pattern_text,
                    "wins": p.win_count, "losses": p.loss_count,
                })
    except Exception:
        pass

    # ── Learning metrics ──
    learning = {"model_trained": False, "win_rates": {}, "total_trades": 0, "pkl_age_hours": None}
    try:
        pkl = Path("models/signal_filter.pkl")
        if pkl.exists():
            import time
            age_h = (time.time() - pkl.stat().st_mtime) / 3600
            learning["model_trained"] = True
            learning["pkl_age_hours"] = round(age_h, 1)
    except Exception:
        pass
    try:
        all_closed = get_closed_trades(limit=150)
        learning["total_trades"] = len(all_closed)
        by_sym: dict = {}
        for t in all_closed:
            by_sym.setdefault(t.symbol, []).append(t)
        for sym, ts in by_sym.items():
            recent = ts[:10]
            if len(recent) >= 3:
                wins = sum(1 for t in recent if (t.pnl_pct or 0) > 0)
                learning["win_rates"][sym] = round(wins / len(recent), 3)
    except Exception:
        pass

    # --- 1. Position snapshots (live P&L per open trade) ---
    try:
        from app.db.database import get_position_snapshots
        pos_snaps = get_position_snapshots()  # {trade_id: {current_price, pnl_usd, pnl_pct, updated_at}}
        for t in trades_out:
            snap = pos_snaps.get(t.get("trade_id"))
            if snap:
                t["current_price"] = snap.get("current_price")
                t["pnl_usd"] = snap.get("pnl_usd", 0.0)
                t["pnl_pct"] = snap.get("pnl_pct", 0.0)
                t["snapshot_at"] = snap.get("updated_at")
            else:
                t["current_price"] = t.get("entry_price")
                t["pnl_usd"] = 0.0
                t["pnl_pct"] = 0.0
                t["snapshot_at"] = None
    except Exception as e:
        logger.warning(f"Position snapshots failed: {e}")
        pos_snaps = {}

    position_snapshots_out = list(pos_snaps.values()) if pos_snaps else []

    # --- 3. News (filtered by approved symbols) ---
    news = []
    try:
        from app.db.database import get_news_cache
        all_syms = get_approved_symbols()
        news = get_news_cache(symbols=all_syms, limit=20)
    except Exception as e:
        logger.warning(f"News cache failed: {e}")

    # --- 4. Scanner results (all scan types) ---
    scanner = {}
    try:
        from app.db.database import get_scanner_results
        for scan_type in ("most_active", "top_movers", "gainers", "losers", "sector", "implied_move"):
            scanner[scan_type] = get_scanner_results(scan_type)
    except Exception as e:
        logger.warning(f"Scanner results failed: {e}")

    # --- 5. Symbol universe with calibration data ---
    symbols_universe = []
    try:
        from app.db.database import get_or_create_symbol_parameters
        open_symbols = {t.symbol for t in open_trades}
        for sym in get_approved_symbols():
            try:
                params = get_or_create_symbol_parameters(sym)
                trades_sym = get_closed_trades_by_symbol(sym, limit=20)
                wins = sum(1 for t in trades_sym if (t.pnl_pct or 0) > 0)
                win_rate = round(wins / len(trades_sym), 3) if trades_sym else None
                multipliers_drifted = {
                    k: round(getattr(params, f"{k}_mult", 1.0), 3)
                    for k in ("momentum", "trend", "volume", "volatility")
                    if abs(getattr(params, f"{k}_mult", 1.0) - 1.0) > 0.05
                }
                symbols_universe.append({
                    "symbol": sym,
                    "backtest_calibrated": bool(getattr(params, "backtest_calibrated", 0)),
                    "backtest_calibrated_at": getattr(params, "backtest_calibrated_at", None),
                    "backtest_profit_factor": getattr(params, "backtest_profit_factor", None),
                    "stop_loss_pct": params.stop_loss_pct,
                    "take_profit_pct": params.take_profit_pct,
                    "trade_count": params.trade_count,
                    "win_rate": win_rate,
                    "multipliers_drifted": multipliers_drifted,
                    "is_open": sym in open_symbols,
                })
            except Exception:
                pass
        symbols_universe.sort(key=lambda item: (not item["is_open"], item["symbol"]))
    except Exception as e:
        logger.warning(f"Symbols universe failed: {e}")

    # --- 6. IB connection status ---
    ib_connected = False
    try:
        ib_connected = bool(client.ib.isConnected())
    except Exception:
        pass

    # --- 7. Earnings warnings for open positions ---
    earnings_warnings = {}
    try:
        from datetime import datetime as _dt
        from app.llm.agent import get_data_layer
        data_layer_inst = get_data_layer()
        for trade in open_trades:
            ed = data_layer_inst.get_earnings_date(trade.symbol)
            if ed:
                days_until = (ed - _dt.now()).days
                if 0 <= days_until <= 3:
                    earnings_warnings[trade.symbol] = days_until
    except Exception as e:
        logger.debug(f"Earnings warnings: {e}")

    return {
        "status": status,
        "open_trades": trades_out,
        "closed_trades": closed_out,
        "signals": signals_out,
        "patterns": patterns_out,
        "position_snapshots": position_snapshots_out,
        "learning": learning,
        "account_history": account_history,
        "latest_account": latest_account,
        "news": news,
        "scanner": scanner,
        "symbols_universe": symbols_universe,
        "ib_connected": ib_connected,
        "earnings_warnings": earnings_warnings,
    }


@app.get("/dashboard/symbol/{symbol}")
def dashboard_symbol_data(symbol: str, period: str = "intraday"):
    """Lazy-loaded symbol data for dashboard chart. Uses IBDataLayer cache."""
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
                {"close": round(float(r["close"]), 4),
                 "volume": int(r.get("volume", 0))}
                for _, r in df.iterrows()
            ]
        if period == "indicators":
            from app.analysis.indicators import compute_features
            if df is not None and len(df) >= 15:
                fs = compute_features(symbol, df)
                result.update({
                    "rsi_14": fs.rsi_14,
                    "macd_line": fs.macd_line,
                    "bollinger_position": fs.bollinger_position,
                    "volume_ratio_20d": fs.volume_ratio_20d,
                })
        return result
    except Exception as e:
        logger.error(f"dashboard_symbol_data({symbol}): {e}")
        return {"symbol": symbol, "bars": [], "error": str(e)}


@app.get("/backtest/{symbol}")
def run_backtest_endpoint(symbol: str, days: int = 180):
    from app.backtest.engine import run_backtest
    from app.backtest.reporter import format_api
    symbol = symbol.upper()
    if symbol not in set(get_approved_symbols()):
        raise HTTPException(status_code=403, detail=f"Symbol {symbol} not in approved DB list")
    try:
        _acct = client.get_account()
        _capital = get_operating_capital(_acct.get("net_liquidation", 0.0))
    except Exception:
        from app.config.settings import CAPITAL_CAP
        _capital = CAPITAL_CAP
    try:
        result = run_backtest(
            symbol=symbol,
            ib_client=client,
            period_days=days,
            capital=_capital,
        )
        return format_api(result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/candidate-analysis/{symbol}")
def candidate_analysis_endpoint(symbol: str):
    """Run full AnalysisPipeline for any symbol."""
    from app.analysis.pipeline import AnalysisPipeline, AnalysisContext
    from app.llm.agent import get_data_layer
    symbol = symbol.upper()
    try:
        data_layer = get_data_layer()
        context = AnalysisContext(mode="on_demand")
        pipeline = AnalysisPipeline(symbol, data_layer, context, notify_fn=None)
        result = pipeline.run()
        return result.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


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
    from app.db.database import get_connection
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
    from app.db.database import get_connection
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM candidate_decisions ORDER BY decision_date DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/symbol-parameters/{symbol}")
def get_symbol_parameters_endpoint(symbol: str):
    """Return adaptive parameters for a symbol."""
    from app.db.database import get_or_create_symbol_parameters, init_analysis_tables
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
