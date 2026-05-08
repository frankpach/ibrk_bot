# app/api/main.py
"""FastAPI con endpoints de compra-venta, preview y gestión de símbolos."""
from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException

from app.config.settings import (
    ALLOWED_SYMBOLS, MARKET_TZ, MAX_RISK_PCT, MIN_RISK_USD, MAX_POSITION_USD,
    PAPER_TRADING_ONLY, REQUIRE_HUMAN_APPROVAL,
)
from app.ibkr.client import IBKRClient
from app.risk.validator import validate_order
from app.db.database import (
    get_pending_signals, get_open_trades, get_patterns_for_symbol,
    init_db, insert_trade, save_symbol_proposal, approve_symbol,
    get_pending_proposals,
)
from app.db.models import Trade

app = FastAPI(title="IBKR AI Trader API")
client = IBKRClient(client_id=11)


class OrderPreviewRequest(BaseModel):
    symbol: str
    action: str = Field(..., pattern="^(BUY|SELL)$")
    quantity: int = Field(..., ge=1)
    order_type: str = Field(..., pattern="^(MKT|LMT)$")
    stop_loss_pct: float = Field(..., gt=0, le=0.10)
    take_profit_pct: float = Field(..., gt=0)


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
    symbol = req.symbol.upper()
    save_symbol_proposal(symbol, req.reason)
    return {
        "status": "pending_approval",
        "symbol": symbol,
        "reason": req.reason,
        "message": f"Symbol {symbol} saved. Use GET /symbols/proposals to review and POST /symbols/approve/{{symbol}} to activate.",
    }


@app.get("/symbols/proposals")
def get_proposals():
    return get_pending_proposals()


@app.post("/symbols/approve/{symbol}")
def approve_symbol_endpoint(symbol: str):
    symbol = symbol.upper()
    approve_symbol(symbol)
    if symbol not in ALLOWED_SYMBOLS:
        ALLOWED_SYMBOLS.append(symbol)
    return {"status": "approved", "symbol": symbol, "message": f"{symbol} added to active trading universe."}


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
        capital = account["net_liquidation"]
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
        take_profit_pct=req.take_profit_pct, capital=capital,
        active_positions=active_positions,
        now=datetime.now(tz=MARKET_TZ),
    )

    max_risk_usd = max(capital * MAX_RISK_PCT, MIN_RISK_USD)
    max_position_usd = min(max_risk_usd / req.stop_loss_pct, MAX_POSITION_USD) if req.stop_loss_pct > 0 else 0
    units = int(max_position_usd / current_price) if current_price > 0 else 0
    estimated_risk = units * current_price * req.stop_loss_pct
    estimated_value = units * current_price

    # Precios según dirección
    if req.action == "BUY":
        sl_price = round(current_price * (1 - req.stop_loss_pct), 2)
        tp_price = round(current_price * (1 + req.take_profit_pct), 2)
    else:  # SELL
        sl_price = round(current_price * (1 + req.stop_loss_pct), 2)
        tp_price = round(current_price * (1 - req.take_profit_pct), 2)

    return {
        "approved": result.approved,
        "requires_human_approval": REQUIRE_HUMAN_APPROVAL,
        "symbol": symbol,
        "action": req.action,
        "current_price": current_price,
        "recommended_units": units,
        "estimated_value": round(estimated_value, 2),
        "estimated_risk_usd": round(estimated_risk, 2),
        "stop_loss_pct": req.stop_loss_pct,
        "take_profit_pct": req.take_profit_pct,
        "stop_loss_price": sl_price,
        "take_profit_price": tp_price,
        "reasons": result.reasons,
    }


@app.post("/orders/place")
def orders_place(req: OrderPreviewRequest):
    symbol = req.symbol.upper()

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

    result = validate_order(
        symbol=symbol, action=req.action, quantity=req.quantity,
        order_type=req.order_type, stop_loss_pct=req.stop_loss_pct,
        take_profit_pct=req.take_profit_pct, capital=capital,
        active_positions=active_positions,
        now=datetime.now(tz=MARKET_TZ),
    )

    if not result.approved:
        raise HTTPException(status_code=403, detail={"approved": False, "reasons": result.reasons})

    max_risk_usd = max(capital * MAX_RISK_PCT, MIN_RISK_USD)
    max_position_usd = min(max_risk_usd / req.stop_loss_pct, MAX_POSITION_USD) if req.stop_loss_pct > 0 else 0
    units = int(max_position_usd / current_price) if current_price > 0 else 0

    if units < 1:
        raise HTTPException(status_code=400, detail="Calculated position size is 0 units")

    # Precios según dirección
    if req.action == "BUY":
        stop_loss_price = round(current_price * (1 - req.stop_loss_pct), 2)
        take_profit_price = round(current_price * (1 + req.take_profit_pct), 2)
    else:  # SELL
        stop_loss_price = round(current_price * (1 + req.stop_loss_pct), 2)
        take_profit_price = round(current_price * (1 - req.take_profit_pct), 2)

    estimated_risk = round(units * current_price * req.stop_loss_pct, 2)

    if REQUIRE_HUMAN_APPROVAL:
        from app.notifications.telegram import request_approval
        approved = request_approval(
            symbol=symbol, action=req.action, units=units,
            entry_price=current_price, stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price, estimated_risk_usd=estimated_risk,
        )
        if not approved:
            raise HTTPException(status_code=403, detail={
                "approved": False,
                "reasons": ["Order rejected or timed out waiting for human approval"],
            })

    if not PAPER_TRADING_ONLY:
        raise HTTPException(status_code=500, detail="Real trading not enabled. Set PAPER_TRADING_ONLY=true or configure approval.")

    try:
        order_result = client.place_order(
            symbol=symbol, action=req.action, quantity=units, order_type=req.order_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Order placement failed: {exc}")

    insert_trade(Trade(
        id=None, symbol=symbol, action=req.action, quantity=units,
        entry_price=current_price, stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price, stop_loss_pct=req.stop_loss_pct,
        take_profit_pct=req.take_profit_pct, signal_strength="MANUAL",
        llm_justification="Placed via API", status="OPEN",
        exit_price=None, exit_reason=None, pnl_usd=None, pnl_pct=None,
        opened_at=datetime.now(tz=MARKET_TZ), closed_at=None,
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
