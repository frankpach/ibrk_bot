# app/system/reconciler.py
"""
Reconcilia posiciones abiertas en IB Gateway vs las registradas en la DB.
Se ejecuta al arrancar el sistema para detectar desincronizaciones.
"""
import logging
from app.db.database import get_open_trades, close_trade
from app.notifications.telegram import notify

logger = logging.getLogger(__name__)


def reconcile_positions(ib_client) -> int:
    """
    Compara posiciones en DB vs IB real.
    Si una posicion esta en DB pero no en IB, la marca como cerrada.
    Retorna el numero de posiciones reconciliadas.
    """
    db_trades = get_open_trades()
    if not db_trades:
        return 0

    try:
        ib_portfolio = ib_client.get_portfolio()
        ib_symbols = {p["symbol"] for p in ib_portfolio if abs(p["quantity"]) > 0}
    except Exception as e:
        logger.error(f"Could not fetch IB portfolio for reconciliation: {e}")
        return 0

    reconciled = 0
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
            reconciled += 1

    if reconciled > 0:
        notify(
            f"Reconciliacion: {reconciled} posicion(es) en DB no encontradas en IB.\n"
            f"Marcadas como cerradas automaticamente."
        )
        logger.info(f"Reconciled {reconciled} positions")

    return reconciled
