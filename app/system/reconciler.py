# app/system/reconciler.py
"""
Reconcilia posiciones abiertas en IB Gateway vs las registradas en la DB.
Se ejecuta al arrancar el sistema para detectar desincronizaciones.
"""
import logging
from datetime import datetime
from app.db.database import get_open_trades, close_trade, insert_trade
from app.db.models import Trade
from app.notifications.telegram import notify

logger = logging.getLogger(__name__)


def reconcile_positions(ib_client) -> dict:
    """
    Reconciliacion BIDIRECCIONAL entre DB local e IBKR real.

    1. Si una posicion esta en DB pero no en IB -> la marca como cerrada.
    2. Si una posicion esta en IB pero no en DB -> la crea como trade local
       (captura operaciones manuales o de otra plataforma).

    Retorna dict con 'closed' y 'created'.
    """
    db_trades = get_open_trades()
    try:
        ib_portfolio = ib_client.get_portfolio()
        ib_positions = {p["symbol"]: p for p in ib_portfolio if abs(p.get("quantity", 0)) > 0}
    except Exception as e:
        logger.error(f"Could not fetch IB portfolio for reconciliation: {e}")
        return {"closed": 0, "created": 0}

    db_symbols = {t.symbol for t in db_trades}
    ib_symbols = set(ib_positions.keys())

    # 1) DB -> IB: cerrar trades locales que ya no existen en IB
    closed_count = 0
    for trade in db_trades:
        if trade.symbol not in ib_symbols:
            logger.warning(
                f"Trade {trade.id} {trade.symbol} in DB but not in IB — marking as closed"
            )
            close_trade(
                trade_id=trade.id,
                exit_price=trade.entry_price,
                exit_reason="RECONCILED_NOT_IN_IB",
                pnl_usd=0.0,
                pnl_pct=0.0,
            )
            closed_count += 1

    # 2) IB -> DB: crear trades locales para posiciones nuevas en IB
    created_count = 0
    for symbol, pos in ib_positions.items():
        if symbol not in db_symbols:
            quantity = abs(pos.get("quantity", 0))
            avg_cost = pos.get("avg_cost", 0)
            action = "BUY" if pos.get("quantity", 0) > 0 else "SELL"
            logger.warning(
                f"Position {symbol} found in IB but not in DB — creating local trade"
            )
            now = datetime.utcnow()
            new_trade = Trade(
                id=None,
                symbol=symbol,
                action=action,
                quantity=quantity,
                entry_price=avg_cost,
                stop_loss_price=round(avg_cost * 0.97, 2),
                take_profit_price=round(avg_cost * 1.06, 2),
                stop_loss_pct=0.03,
                take_profit_pct=0.06,
                signal_strength="MANUAL_RECONCILED",
                llm_justification="Created from IBKR reconciliation — likely manual trade",
                status="OPEN",
                exit_price=None,
                exit_reason=None,
                pnl_usd=None,
                pnl_pct=None,
                opened_at=now,
                closed_at=None,
                order_id=None,
            )
            insert_trade(new_trade)
            created_count += 1

    if closed_count or created_count:
        notify(
            f"Reconciliacion IB <-> DB:\n"
            f"  Cerradas (DB huérfanas): {closed_count}\n"
            f"  Creadas (manuales IB): {created_count}\n"
            f"Usa /posiciones para ver estado actual."
        )
        logger.info(f"Reconciled: closed={closed_count}, created={created_count}")

    return {"closed": closed_count, "created": created_count}
