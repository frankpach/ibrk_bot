# app/positions/manager.py
import logging
import httpx
from app.config.settings import MIN_PROFIT_PCT_MEDIUM
from app.db.database import get_open_trades, close_trade

logger = logging.getLogger(__name__)
API_BASE = "http://127.0.0.1:8088"


def _get_current_price(symbol: str) -> float | None:
    try:
        return httpx.get(f"{API_BASE}/price/{symbol}", timeout=15).json().get("market_price")
    except Exception as e:
        logger.error(f"Could not fetch price for {symbol}: {e}")
        return None


def check_positions():
    trades = get_open_trades()
    if not trades:
        return

    for trade in trades:
        price = _get_current_price(trade.symbol)
        if price is None:
            continue

        pnl_pct = (price - trade.entry_price) / trade.entry_price
        if trade.action == "SELL":
            pnl_pct = -pnl_pct
        pnl_usd = pnl_pct * trade.entry_price * trade.quantity

        exit_reason = None

        if trade.action == "BUY":
            if price <= trade.stop_loss_price:
                exit_reason = "STOP_LOSS"
            elif price >= trade.take_profit_price:
                exit_reason = "TAKE_PROFIT"
            elif trade.signal_strength == "MEDIUM" and pnl_pct >= MIN_PROFIT_PCT_MEDIUM:
                exit_reason = "MIN_PROFIT_MEDIUM"
        elif trade.action == "SELL":
            if price >= trade.stop_loss_price:
                exit_reason = "STOP_LOSS"
            elif price <= trade.take_profit_price:
                exit_reason = "TAKE_PROFIT"

        if exit_reason:
            logger.info(f"Closing trade {trade.id} {trade.symbol} reason={exit_reason} pnl={pnl_pct:.2%} ${pnl_usd:.2f}")
            close_trade(
                trade_id=trade.id, exit_price=price, exit_reason=exit_reason,
                pnl_usd=round(pnl_usd, 2), pnl_pct=round(pnl_pct, 4),
            )
