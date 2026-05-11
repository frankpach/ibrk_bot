# app/positions/manager.py
import logging
import httpx
from app.config.settings import MIN_PROFIT_PCT_MEDIUM
from app.db.database import get_open_trades, close_trade
from app.llm.postmortem import run_postmortem
from app.notifications.telegram import notify

logger = logging.getLogger(__name__)
from app.config.settings import API_BASE  # noqa: F401


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
            emoji = "✅" if pnl_usd >= 0 else "❌"
            logger.info(f"Closing trade {trade.id} {trade.symbol} reason={exit_reason} pnl={pnl_pct:.2%} ${pnl_usd:.2f}")

            # 1) Enviar orden de cierre REAL a IBKR
            close_action = "SELL" if trade.action == "BUY" else "BUY"
            try:
                from app.ibkr.client import get_client
                ib = get_client()
                ib.place_order(
                    symbol=trade.symbol,
                    action=close_action,
                    quantity=trade.quantity,
                    order_type="MKT",
                )
                logger.info(f"IBKR close order sent: {close_action} {trade.quantity} {trade.symbol}")
            except Exception as e:
                logger.error(f"Failed to send IBKR close order for {trade.symbol}: {e}")
                # Continuamos para no dejar la DB inconsistente,
                # pero loggeamos para revision manual.

            # 2) Actualizar base de datos local
            close_trade(
                trade_id=trade.id, exit_price=price, exit_reason=exit_reason,
                pnl_usd=round(pnl_usd, 2), pnl_pct=round(pnl_pct, 4),
            )
            trade.exit_price = price
            trade.exit_reason = exit_reason
            trade.pnl_usd = round(pnl_usd, 2)
            trade.pnl_pct = round(pnl_pct, 4)

            notify(
                f"{emoji} Posición cerrada: <b>{trade.action} {trade.symbol}</b>\n"
                f"Razón: {exit_reason}\n"
                f"Entrada: ${trade.entry_price:.2f} → Salida: ${price:.2f}\n"
                f"P&L: {pnl_pct:.2%} (${pnl_usd:.2f})"
            )

            try:
                run_postmortem(trade)
            except Exception as e:
                logger.error(f"Postmortem error for trade {trade.id}: {e}")
