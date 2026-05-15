# app/interfaces/api/routes/trading_routes.py
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Depends
from app.api.auth import require_control_key
from app.container import get_container
from app.application.use_cases.place_order import PlaceOrderCommand
from app.application.use_cases.close_position import ClosePositionCommand
from app.infrastructure.db.compat import get_open_trades, close_trade

router = APIRouter()


class OrderPreviewRequest(BaseModel):
    symbol: str
    action: str
    quantity: float
    order_type: str
    stop_loss_pct: float
    take_profit_pct: float
    limit_price: float | None = None


@router.post("/orders/preview")
def orders_preview(req: OrderPreviewRequest):
    from app.api.capital import get_operating_capital
    from app.application.services.risk_service import RiskService
    from datetime import datetime
    from app.config.settings import MARKET_TZ

    symbol = req.symbol.upper()
    c = get_container()
    try:
        current_price = float(c.broker.get_price(symbol))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not fetch price: {exc}")
    try:
        account = c.broker.get_account()
        capital = get_operating_capital(account.net_liquidation)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not fetch account: {exc}")
    try:
        portfolio = c.broker.get_portfolio()
        active_positions = len(portfolio)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not fetch portfolio: {exc}")

    risk = RiskService()
    result = risk.validate_order(
        symbol=symbol, action=req.action, quantity=req.quantity,
        order_type=req.order_type, stop_loss_pct=req.stop_loss_pct,
        capital=capital, active_positions=active_positions,
        now=datetime.now(tz=MARKET_TZ),
    )
    units = risk.calculate_position_size(price=current_price, stop_loss_pct=req.stop_loss_pct, capital=capital)
    buying_power = account.buying_power
    estimated_cost = units * current_price
    if req.action == "BUY":
        stop_loss_price = round(current_price * (1 - req.stop_loss_pct), 2)
        take_profit_price = round(current_price * (1 + req.take_profit_pct), 2)
    else:
        stop_loss_price = round(current_price * (1 + req.stop_loss_pct), 2)
        take_profit_price = round(current_price * (1 - req.take_profit_pct), 2)

    return {
        "approved": result.approved,
        "symbol": symbol, "action": req.action,
        "current_price": current_price,
        "recommended_units": units,
        "estimated_value": round(estimated_cost, 2),
        "stop_loss_price": stop_loss_price,
        "take_profit_price": take_profit_price,
        "reasons": result.reasons,
    }


@router.post("/orders/place", dependencies=[Depends(require_control_key)])
def orders_place(req: OrderPreviewRequest):
    c = get_container()
    cmd = PlaceOrderCommand(
        symbol=req.symbol.upper(), action=req.action, quantity=req.quantity,
        order_type=req.order_type, limit_price=req.limit_price,
        stop_loss_pct=req.stop_loss_pct, take_profit_pct=req.take_profit_pct,
        requested_by="api",
    )
    result = c.place_order_use_case.execute(cmd)
    if not result.success:
        raise HTTPException(status_code=403, detail={"approved": False, "reasons": [result.error]})
    return {
        "status": "placed", "symbol": cmd.symbol, "action": cmd.action,
        "order_id": result.order_id, "trade_id": result.trade_id,
    }


@router.post("/orders/close/{symbol}", dependencies=[Depends(require_control_key)])
def close_position(symbol: str):
    symbol = symbol.upper()
    trades = [t for t in get_open_trades() if t.symbol == symbol]
    if not trades:
        raise HTTPException(status_code=404, detail=f"No open position for {symbol}")
    trade = trades[0]
    c = get_container()
    result = c.close_position_use_case.execute(
        ClosePositionCommand(trade_id=trade.id, reason="MANUAL_CLOSE", requested_by="api")
    )
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return {"status": "closed", "symbol": symbol, "pnl_usd": result.pnl_usd, "pnl_pct": result.pnl_pct}


@router.post("/orders/close-all", dependencies=[Depends(require_control_key)])
def close_all_positions():
    trades = get_open_trades()
    if not trades:
        return {"status": "ok", "closed": 0}
    c = get_container()
    closed = []
    failed = []
    for trade in trades:
        result = c.close_position_use_case.execute(
            ClosePositionCommand(trade_id=trade.id, reason="MANUAL_CLOSE_ALL", requested_by="api")
        )
        if result.success:
            closed.append({"symbol": trade.symbol, "pnl_usd": result.pnl_usd})
        else:
            failed.append({"symbol": trade.symbol, "error": result.error})
    return {"status": "ok", "closed": len(closed), "failed": len(failed), "positions": closed}


@router.post("/orders/close/id/{trade_id}", dependencies=[Depends(require_control_key)])
def close_trade_by_id(trade_id: int):
    trades = [t for t in get_open_trades() if t.id == trade_id]
    if not trades:
        raise HTTPException(status_code=404, detail="Trade not found or already closed")
    trade = trades[0]
    c = get_container()
    c.notifier.notify(
        f"Solicitud de cierre desde dashboard:\n<b>{trade.symbol}</b> {trade.action} {trade.quantity}u\n"
        f"Responde /cerrar {trade.symbol} para confirmar."
    )
    return {"message": f"Confirmación enviada por Telegram para {trade.symbol}", "trade_id": trade_id}


@router.get("/trades/closed")
def get_closed_trades(limit: int = 10):
    from app.infrastructure.db.compat import get_closed_trades
    trades = get_closed_trades(limit=limit)
    return [{"id": t.id, "symbol": t.symbol, "action": t.action,
             "pnl_usd": t.pnl_usd, "pnl_pct": t.pnl_pct,
             "exit_reason": t.exit_reason, "closed_at": t.closed_at} for t in trades]
