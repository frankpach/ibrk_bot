# app/api/main.py
from datetime import datetime
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException

from app.config.settings import ALLOWED_SYMBOLS, MARKET_TZ, MAX_RISK_PCT, MIN_RISK_USD, MAX_POSITION_USD
from app.api.capital import get_operating_capital
from app.ibkr.client import IBKRClient
from app.risk.validator import validate_order
from app.db.database import get_pending_signals, get_open_trades, get_patterns_for_symbol, init_db

app = FastAPI(title="IBKR AI Trader API")
client = IBKRClient(client_id=11)


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
    if symbol not in ALLOWED_SYMBOLS:
        raise HTTPException(status_code=403, detail=f"Symbol {symbol} not allowed")
    try:
        return client.get_stock_price(symbol)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/price/free/{symbol}")
def get_price_free(symbol: str):
    """Obtiene precio de cualquier simbolo sin restriccion de ALLOWED_SYMBOLS.
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
    return {"symbols": ALLOWED_SYMBOLS}


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
def get_signals():
    return [{"id": s.id, "symbol": s.symbol, "strength": s.strength,
             "rsi": s.rsi, "macd": s.macd, "volume_ratio": s.volume_ratio,
             "created_at": s.created_at.isoformat()} for s in get_pending_signals()]


@app.get("/trades")
def get_trades():
    return [{"id": t.id, "symbol": t.symbol, "action": t.action,
             "quantity": t.quantity, "entry_price": t.entry_price,
             "stop_loss_price": t.stop_loss_price, "take_profit_price": t.take_profit_price,
             "signal_strength": t.signal_strength, "status": t.status,
             "opened_at": t.opened_at.isoformat()} for t in get_open_trades()]


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

    if not PAPER_TRADING_ONLY:
        raise HTTPException(status_code=500, detail="Neither paper nor approval mode configured")

    try:
        order_result = client.place_order(
            symbol=symbol,
            action=req.action,
            quantity=units,
            order_type=req.order_type,
            limit_price=req.limit_price,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Order placement failed: {exc}")

    from app.db.database import insert_trade
    from app.db.models import Trade
    from datetime import datetime as dt
    if req.action == "BUY":
        stop_loss_price = round(current_price * (1 - req.stop_loss_pct), 2)
        take_profit_price = round(current_price * (1 + req.take_profit_pct), 2)
    else:  # SELL
        stop_loss_price = round(current_price * (1 + req.stop_loss_pct), 2)
        take_profit_price = round(current_price * (1 - req.take_profit_pct), 2)
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


@app.get("/symbols/proposals")
def get_proposals():
    from app.db.database import get_pending_proposals
    return get_pending_proposals()


@app.post("/symbols/approve/{symbol}")
def approve_symbol_endpoint(symbol: str):
    from app.db.database import approve_symbol
    from app.config.settings import ALLOWED_SYMBOLS
    symbol = symbol.upper()
    approve_symbol(symbol)
    if symbol not in ALLOWED_SYMBOLS:
        ALLOWED_SYMBOLS.append(symbol)
    return {"status": "approved", "symbol": symbol, "message": f"{symbol} added to active trading universe."}



# --- System endpoints ---

@app.get("/system/status")
def system_status():
    from app.system.controller import get_controller
    from app.db.database import get_daily_pnl, get_open_trades
    try:
        ctrl = get_controller()
        status = ctrl.status()
    except RuntimeError:
        status = {"paused": False, "mode": "paper", "circuit_breaker_threshold": "5%"}
    open_trades = get_open_trades()
    daily_pnl = get_daily_pnl()
    try:
        _acct = client.get_account()
        _capital = get_operating_capital(_acct.get("net_liquidation", 0.0))
    except Exception:
        from app.config.settings import CAPITAL_CAP
        _capital = CAPITAL_CAP
    return {
        **status,
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
    try:
        client.place_order(
            symbol=trade.symbol,
            action=close_action,
            quantity=trade.quantity,
            order_type="MKT",
        )
        logger.info(f"IBKR close order sent: {close_action} {trade.quantity} {trade.symbol}")
    except Exception as e:
        logger.error(f"Failed to send IBKR close order for {trade.symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"IBKR close order failed: {e}")
    
    # 2) Actualizar base de datos local
    pnl_pct = (current_price - trade.entry_price) / trade.entry_price
    if trade.action == "SELL":
        pnl_pct = -pnl_pct
    pnl_usd = pnl_pct * trade.entry_price * trade.quantity
    close_trade(trade.id, current_price, "MANUAL_CLOSE", round(pnl_usd, 2), round(pnl_pct, 4))
    return {
        "status": "closed", "symbol": symbol,
        "exit_price": current_price,
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
    for trade in trades:
        try:
            price_data = client.get_stock_price(trade.symbol)
            current_price = price_data["market_price"]
            
            # Enviar orden de cierre REAL a IBKR
            close_action = "SELL" if trade.action == "BUY" else "BUY"
            try:
                client.place_order(
                    symbol=trade.symbol,
                    action=close_action,
                    quantity=trade.quantity,
                    order_type="MKT",
                )
                logger.info(f"IBKR close order sent: {close_action} {trade.quantity} {trade.symbol}")
            except Exception as e:
                logger.error(f"Failed to send IBKR close order for {trade.symbol}: {e}")
                failed.append({"symbol": trade.symbol, "error": str(e)})
                continue
            
            pnl_pct = (current_price - trade.entry_price) / trade.entry_price
            if trade.action == "SELL":
                pnl_pct = -pnl_pct
            pnl_usd = pnl_pct * trade.entry_price * trade.quantity
            close_trade(trade.id, current_price, "MANUAL_CLOSE_ALL", round(pnl_usd, 2), round(pnl_pct, 4))
            closed.append({"symbol": trade.symbol, "pnl_usd": round(pnl_usd, 2)})
        except Exception as e:
            logger.error(f"Could not close {trade.symbol}: {e}")
            failed.append({"symbol": trade.symbol, "error": str(e)})
    
    return {"status": "ok", "closed": len(closed), "failed": len(failed), "positions": closed}
    return {"status": "ok", "closed": len(closed), "positions": closed}


from fastapi.responses import HTMLResponse


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    from app.api.dashboard import render_dashboard
    from app.db.database import (
        get_open_trades, get_closed_trades, get_pending_signals,
        get_patterns_for_symbol, get_daily_pnl,
    )
    from app.config.settings import ALLOWED_SYMBOLS

    daily_pnl = get_daily_pnl()
    open_trades = get_open_trades()
    try:
        _acct = client.get_account()
        _capital = get_operating_capital(_acct.get("net_liquidation", 0.0))
    except Exception:
        from app.config.settings import CAPITAL_CAP
        _capital = CAPITAL_CAP

    status_data = {
        "mode": "paper",
        "paused": False,
        "daily_pnl_usd": round(daily_pnl, 2),
        "daily_pnl_pct": round(daily_pnl / _capital * 100, 2) if _capital else 0.0,
        "open_positions": len(open_trades),
        "operating_capital": _capital,
    }
    try:
        from app.system.controller import get_controller
        ctrl = get_controller()
        status_data["mode"] = ctrl.mode
        status_data["paused"] = ctrl.is_paused
    except RuntimeError:
        pass

    trades = [
        {
            "symbol": t.symbol, "action": t.action, "quantity": t.quantity,
            "entry_price": t.entry_price, "stop_loss_price": t.stop_loss_price,
            "take_profit_price": t.take_profit_price, "signal_strength": t.signal_strength,
            "status": t.status, "opened_at": t.opened_at.isoformat(),
        }
        for t in open_trades
    ]
    closed = [
        {
            "symbol": t.symbol, "action": t.action, "pnl_usd": t.pnl_usd,
            "exit_reason": t.exit_reason,
            "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        }
        for t in get_closed_trades(limit=5)
    ]
    signals = [
        {
            "symbol": s.symbol, "strength": s.strength, "rsi": s.rsi,
            "volume_ratio": s.volume_ratio, "created_at": s.created_at.isoformat(),
        }
        for s in get_pending_signals()
    ]
    all_patterns = []
    for sym in ALLOWED_SYMBOLS[:5]:
        for p in get_patterns_for_symbol(sym)[:1]:
            all_patterns.append({
                "symbol": p.symbol, "pattern": p.pattern_text,
                "wins": p.win_count, "losses": p.loss_count,
            })

    html = render_dashboard(status_data, trades, closed, signals, all_patterns)
    return HTMLResponse(content=html)


@app.get("/backtest/{symbol}")
def run_backtest_endpoint(symbol: str, days: int = 180):
    from app.backtest.engine import run_backtest
    from app.backtest.reporter import format_api
    symbol = symbol.upper()
    if symbol not in ALLOWED_SYMBOLS:
        raise HTTPException(status_code=403, detail=f"Symbol {symbol} not in allowed list")
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
    from app.config.settings import ALLOWED_SYMBOLS
    conn = get_connection()
    rows = conn.execute("SELECT * FROM watchlist_scores ORDER BY watchlist_score DESC").fetchall()
    conn.close()
    scores = {r["symbol"]: r["watchlist_score"] for r in rows}
    return [
        {"symbol": s, "watchlist_score": scores.get(s, 0.5), "active": True}
        for s in ALLOWED_SYMBOLS
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

