# app/interfaces/api/routes/market_routes.py
from fastapi import APIRouter, HTTPException
from app.container import get_container
from app.infrastructure.db.compat import get_approved_symbols, get_pending_signals, get_patterns_for_symbol

router = APIRouter()


@router.get("/price/{symbol}")
def get_price(symbol: str):
    symbol = symbol.upper()
    if symbol not in set(get_approved_symbols()):
        raise HTTPException(status_code=403, detail=f"Symbol {symbol} not allowed")
    try:
        c = get_container()
        price = c.broker.get_price(symbol)
        return {"market_price": float(price)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/price/free/{symbol}")
def get_price_free(symbol: str):
    symbol = symbol.upper()
    try:
        c = get_container()
        price = c.broker.get_price(symbol)
        return {"market_price": float(price)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/account")
def get_account():
    c = get_container()
    try:
        acct = c.broker.get_account()
        return {
            "net_liquidation": acct.net_liquidation,
            "buying_power": acct.buying_power,
            "daily_pnl_usd": acct.daily_pnl_usd,
            "daily_pnl_pct": acct.daily_pnl_pct,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/portfolio")
def get_portfolio():
    c = get_container()
    try:
        positions = c.broker.get_portfolio()
        return [
            {"symbol": p.symbol, "quantity": p.quantity, "avg_cost": p.avg_cost,
             "market_value": p.market_value, "unrealized_pnl": p.unrealized_pnl}
            for p in positions
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/allowed-symbols")
def allowed_symbols():
    symbols = get_approved_symbols()
    from app.infrastructure.db.compat import get_approved_symbols_with_meta
    meta = get_approved_symbols_with_meta()
    return {"symbols": symbols, "meta": meta}


@router.get("/signals")
def get_signals(since_hours: int = 24):
    return [{"id": s.id, "symbol": s.symbol, "strength": s.strength,
             "rsi": s.rsi, "macd": s.macd, "volume_ratio": s.volume_ratio,
             "created_at": s.created_at.isoformat()} for s in get_pending_signals(since_hours=since_hours)]


@router.get("/trades")
def get_trades():
    from app.infrastructure.db.compat import get_open_trades
    trades = get_open_trades()
    return [{"id": t.id, "symbol": t.symbol, "action": t.action, "quantity": t.quantity,
             "entry_price": t.entry_price, "status": t.status} for t in trades]


@router.get("/patterns/{symbol}")
def get_patterns(symbol: str):
    return [{"id": p.id, "pattern": p.pattern_text, "wins": p.win_count,
             "losses": p.loss_count} for p in get_patterns_for_symbol(symbol.upper())]
