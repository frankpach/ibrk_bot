# app/api/main.py
from datetime import datetime
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException

from app.config.settings import ALLOWED_SYMBOLS, MARKET_TZ, MAX_RISK_PCT, MIN_RISK_USD, MAX_POSITION_USD
from app.ibkr.client import IBKRClient
from app.risk.validator import validate_order
from app.db.database import get_pending_signals, get_open_trades, get_patterns_for_symbol, init_db

app = FastAPI(title="IBKR AI Trader API")
client = IBKRClient(client_id=11)


class OrderPreviewRequest(BaseModel):
    symbol: str
    action: str
    quantity: int
    order_type: str
    stop_loss_pct: float
    take_profit_pct: float


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
    return {
        "status": "pending_approval",
        "symbol": req.symbol.upper(),
        "reason": req.reason,
        "message": "Symbol proposal logged. Awaiting human approval.",
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
        capital=capital, active_positions=active_positions,
        now=datetime.now(tz=MARKET_TZ),
    )

    max_risk_usd = max(capital * MAX_RISK_PCT, MIN_RISK_USD)
    max_position_usd = min(max_risk_usd / req.stop_loss_pct, MAX_POSITION_USD) if req.stop_loss_pct > 0 else 0
    units = int(max_position_usd / current_price) if current_price > 0 else 0
    estimated_risk = units * current_price * req.stop_loss_pct
    estimated_value = units * current_price

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
        "stop_loss_price": round(current_price * (1 - req.stop_loss_pct), 2),
        "take_profit_price": round(current_price * (1 + req.take_profit_pct), 2),
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
