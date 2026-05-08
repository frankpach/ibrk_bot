# app/positions/manager.py
"""Gestión de posiciones abiertas: cierre por SL/TP, time-exit y sincronización con IBKR."""
import logging
import httpx
from datetime import datetime, timedelta

from app.config.settings import MIN_PROFIT_PCT_MEDIUM, MARKET_TZ
from app.db.database import get_open_trades, close_trade, get_trade_by_id
from app.ibkr.client import IBKRClient

logger = logging.getLogger(__name__)
API_BASE = "http://127.0.0.1:8088"


def _get_current_price(symbol: str) -> float | None:
    try:
        return httpx.get(f"{API_BASE}/price/{symbol}", timeout=15).json().get("market_price")
    except Exception as e:
        logger.error(f"Could not fetch price for {symbol}: {e}")
        return None


def check_positions():
    """Chequea trades abiertos y cierra los que hayan alcanzado SL, TP o condiciones especiales."""
    trades = get_open_trades()
    if not trades:
        return

    ib_client = IBKRClient()

    for trade in trades:
        price = _get_current_price(trade.symbol)
        if price is None:
            continue

        # Calcular P&L
        if trade.action == "BUY":
            pnl_pct = (price - trade.entry_price) / trade.entry_price
        else:  # SELL
            pnl_pct = (trade.entry_price - price) / trade.entry_price
        pnl_usd = pnl_pct * trade.entry_price * trade.quantity

        exit_reason = None

        # ── Stop Loss / Take Profit ──
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
            elif trade.signal_strength == "MEDIUM" and pnl_pct >= MIN_PROFIT_PCT_MEDIUM:
                exit_reason = "MIN_PROFIT_MEDIUM"

        # ── Time-based exit (más de 5 días abierta) ──
        if exit_reason is None:
            age = datetime.now(tz=MARKET_TZ) - trade.opened_at
            if age > timedelta(days=5):
                exit_reason = "TIME_EXIT"

        if exit_reason:
            logger.info(
                f"Closing trade {trade.id} {trade.symbol} reason={exit_reason} "
                f"pnl={pnl_pct:.2%} ${pnl_usd:.2f}"
            )

            # 1) Enviar orden de cierre real a IBKR
            try:
                close_action = "SELL" if trade.action == "BUY" else "BUY"
                ib_client.close_position(
                    symbol=trade.symbol,
                    quantity=trade.quantity,
                    action=close_action,
                    order_type="MKT",
                )
                logger.info(f"IBKR close order sent for {trade.symbol} {close_action}")
            except Exception as exc:
                logger.error(f"Failed to send close order for {trade.symbol}: {exc}")
                # Continuamos actualizando DB para no quedar en estado inconsistente,
                # pero loggeamos el error para revisión manual.

            # 2) Actualizar base de datos local
            close_trade(
                trade_id=trade.id, exit_price=price, exit_reason=exit_reason,
                pnl_usd=round(pnl_usd, 2), pnl_pct=round(pnl_pct, 4),
            )

            # 3) Postmortem
            try:
                from app.llm.postmortem import run_postmortem
                closed_trade = get_trade_by_id(trade.id)
                if closed_trade:
                    run_postmortem(closed_trade)
            except Exception as e:
                logger.error(f"Postmortem error for trade {trade.id}: {e}")


def sync_positions_with_broker():
    """Sincroniza posiciones abiertas en la DB con las posiciones reales de IBKR.

    Si IBKR no tiene la posición, la marca como cerrada en la DB.
    """
    try:
        ib_client = IBKRClient()
        broker_positions = ib_client.sync_positions()
        broker_symbols = {p["symbol"]: p for p in broker_positions}

        open_trades = get_open_trades()
        for trade in open_trades:
            broker_pos = broker_symbols.get(trade.symbol)
            if broker_pos is None:
                logger.warning(
                    f"Trade {trade.id} {trade.symbol} not found in IBKR – marking as closed externally"
                )
                # No sabemos el precio de cierre exacto, usamos el último conocido o entry
                close_trade(
                    trade_id=trade.id,
                    exit_price=trade.entry_price,
                    exit_reason="EXTERNAL_CLOSE",
                    pnl_usd=0.0,
                    pnl_pct=0.0,
                )
            else:
                # Validar que la cantidad coincida (dirección)
                expected_qty = trade.quantity if trade.action == "BUY" else -trade.quantity
                if int(broker_pos["quantity"]) != expected_qty:
                    logger.warning(
                        f"Trade {trade.id} {trade.symbol} quantity mismatch: "
                        f"DB={expected_qty} IBKR={broker_pos['quantity']}"
                    )
    except Exception as exc:
        logger.error(f"Position sync failed: {exc}")
