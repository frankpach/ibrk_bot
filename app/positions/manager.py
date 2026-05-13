# app/positions/manager.py
import logging
import threading
import httpx
from app.config.settings import MIN_PROFIT_PCT_MEDIUM
from app.db.database import get_open_trades, close_trade, update_trade_status
from app.llm.postmortem import run_postmortem
from app.notifications.telegram import notify
from app.notifications.policy import get_policy
from app.risk.trailing_stop import TrailingStopManager
from app.risk.partial_exit import PartialExitManager
from app.ibkr.fill_tracker import get_fill_price_fallback

logger = logging.getLogger(__name__)
from app.config.settings import API_BASE  # noqa: F401

trailing_mgr = TrailingStopManager()
partial_mgr = PartialExitManager()
_positions_check_lock = threading.Lock()


def _is_trade_open(trade_id: int) -> bool:
    """Verifica si un trade sigue OPEN en la base de datos."""
    from app.db.database import get_connection
    conn = get_connection()
    try:
        row = conn.execute("SELECT status FROM trades WHERE id=?", (trade_id,)).fetchone()
        return row is not None and row["status"] == "OPEN"
    finally:
        conn.close()


def _get_current_price(symbol: str) -> float | None:
    try:
        return httpx.get(f"{API_BASE}/price/{symbol}", timeout=15).json().get("market_price")
    except Exception as e:
        logger.error(f"Could not fetch price for {symbol}: {e}")
        return None


def _close_position(
    trade, exit_reason: str, price: float, pnl_pct: float, pnl_usd: float,
    quantity: float = None,
):
    """Close a position (full or partial) with IBKR order and DB update."""
    qty = quantity if quantity is not None else (trade.remaining_quantity or trade.quantity)
    emoji = "✅" if pnl_usd >= 0 else "❌"
    logger.info(f"Closing trade {trade.id} {trade.symbol} reason={exit_reason} qty={qty} pnl={pnl_pct:.2%} ${pnl_usd:.2f}")

    # Idempotencia: verificar que el trade siga abierto antes de actuar
    if not _is_trade_open(trade.id):
        logger.warning(f"Trade {trade.id} {trade.symbol} already closed or missing — skipping duplicate close")
        return False

    # 1) Enviar orden de cierre REAL a IBKR
    close_action = "SELL" if trade.action == "BUY" else "BUY"
    try:
        from app.ibkr.client import get_client
        from app.ibkr.dedup import get_deduplicator, PreflightChecker
        ib = get_client()
        dedup = get_deduplicator()

        # Deduplicación de órdenes de cierre por trade + razón
        dedup_action = f"{close_action}_{trade.id}_{exit_reason}"
        if dedup.is_duplicate(trade.symbol, dedup_action):
            logger.warning(f"Duplicate close order blocked for {trade.symbol} {dedup_action}")
            return False

        # Pre-flight check
        preflight = PreflightChecker(ib).check(
            trade.symbol, close_action, qty, "MKT",
        )
        if not preflight.ok:
            logger.error(f"Preflight failed for close {trade.symbol}: {preflight.reason}")
            return False

        order_result = ib.place_order(
            symbol=trade.symbol,
            action=close_action,
            quantity=qty,
            order_type="MKT",
        )
        dedup.record(trade.symbol, dedup_action)
        logger.info(f"IBKR close order sent: {close_action} {qty} {trade.symbol}")

        # Confirm fill price
        try:
            fill_price = get_fill_price_fallback(ib, order_result.get("order_id", ""), trade.symbol)
        except Exception:
            fill_price = price

    except Exception as e:
        logger.error(f"Failed to send IBKR close order for {trade.symbol}: {e}")
        fill_price = price

    # 2) Actualizar base de datos local
    if exit_reason.startswith("PARTIAL"):
        # Partial exit: update remaining, keep OPEN
        trade.remaining_quantity = trade.remaining_quantity - qty if trade.remaining_quantity else trade.quantity - qty
        trade.partial_exit_done = True
        # Move SL to breakeven
        trade.stop_loss_price = partial_mgr.get_breakeven_sl(trade)
        update_trade_status(
            trade_id=trade.id,
            trade_status="PARTIAL",
            remaining_quantity=trade.remaining_quantity,
            stop_loss_price=trade.stop_loss_price,
        )
        notify_msg = (
            f"{emoji} Salida parcial: <b>{trade.action} {trade.symbol}</b>\n"
            f"Cerrado: {qty} | Restante: {trade.remaining_quantity}\n"
            f"Nuevo SL: ${trade.stop_loss_price:.2f} (breakeven)\n"
            f"P&L parcial: {pnl_pct:.2%} (${pnl_usd:.2f})"
        )
    else:
        # Full close
        close_trade(
            trade_id=trade.id, exit_price=fill_price or price, exit_reason=exit_reason,
            pnl_usd=round(pnl_usd, 2), pnl_pct=round(pnl_pct, 4),
            exit_fill_price=fill_price,
        )
        trade.exit_price = fill_price or price
        trade.exit_reason = exit_reason
        trade.pnl_usd = round(pnl_usd, 2)
        trade.pnl_pct = round(pnl_pct, 4)
        notify_msg = (
            f"{emoji} Posición cerrada: <b>{trade.action} {trade.symbol}</b>\n"
            f"Razón: {exit_reason}\n"
            f"Entrada: ${trade.entry_price:.2f} → Salida: ${fill_price or price:.2f}\n"
            f"P&L: {pnl_pct:.2%} (${pnl_usd:.2f})"
        )
        try:
            run_postmortem(trade)
        except Exception as e:
            logger.error(f"Postmortem error for trade {trade.id}: {e}")

    policy = get_policy()
    if policy.should_notify("position_closed"):
        notify(notify_msg)
    return True


def check_positions():
    with _positions_check_lock:
        trades = get_open_trades()
        if not trades:
            return

        for trade in trades:
            price = _get_current_price(trade.symbol)
            if price is None:
                continue

            # Calculate P&L
            entry = trade.entry_price
            if trade.action == "BUY":
                pnl_pct = (price - entry) / entry
            else:
                pnl_pct = (entry - price) / entry
            qty = trade.remaining_quantity or trade.quantity
            pnl_usd = pnl_pct * entry * qty

            try:
                from app.db.database import upsert_position_snapshot
                upsert_position_snapshot(
                    trade_id=trade.id,
                    symbol=trade.symbol,
                    current_price=price,
                    pnl_usd=round(pnl_usd, 2),
                    pnl_pct=round(pnl_pct, 4),
                )
            except Exception as _snap_err:
                logger.debug(f"Position snapshot write skipped: {_snap_err}")

            # 1) Check partial exit first (only if profitable)
            partial = partial_mgr.check_exit(trade, price)
            if partial.should_exit:
                _close_position(
                    trade, partial.exit_reason, price, pnl_pct,
                    pnl_pct * entry * partial.exit_quantity,
                    quantity=partial.exit_quantity,
                )
                if partial.close_all:
                    continue
                # After partial, recalculate P&L for remaining
                qty = trade.remaining_quantity or trade.quantity
                pnl_usd = pnl_pct * entry * qty

            # 2) Check trailing stop
            sl_result = trailing_mgr.update_stop_levels(trade, price)
            if sl_result.new_stop_price is not None:
                trade.stop_loss_price = sl_result.new_stop_price
                # Persist to DB
                update_trade_status(
                    trade_id=trade.id,
                    trade_status=trade.trade_status or "OPEN",
                    stop_loss_price=trade.stop_loss_price,
                )
                logger.info(f"Trailing stop updated for {trade.symbol}: ${trade.stop_loss_price:.2f} ({sl_result.reason})")

            # 3) Check exit conditions
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
                _close_position(trade, exit_reason, price, pnl_pct, pnl_usd)
