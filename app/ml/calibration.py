"""Backtest calibration for newly approved symbols."""
import logging
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SL_GRID = [0.020, 0.025, 0.030, 0.035]
TP_GRID = [0.040, 0.050, 0.060, 0.070, 0.080]
MIN_TRADES = 5
PERIOD_DAYS = 180
REQUEST_DELAY = 2.0  # seconds between IBKR requests


def on_symbol_approved(symbol: str, ib_client) -> None:
    """Launch background calibration thread (non-blocking)."""
    t = threading.Thread(
        target=_run_calibration_safe,
        args=(symbol, ib_client),
        daemon=True,
        name=f"calibration-{symbol}",
    )
    t.start()
    logger.info(f"Calibration started for {symbol} in background thread")


def _run_calibration_safe(symbol: str, ib_client) -> None:
    """Grid search SL/TP, write best result to symbol_parameters."""
    try:
        from app.backtest.engine import run_backtest
        from app.infrastructure.db.compat import update_symbol_parameters
        from app.notifications.telegram import notify

        best_result = None
        best_sl = 0.025
        best_tp = 0.060

        for sl in SL_GRID:
            for tp in TP_GRID:
                time.sleep(REQUEST_DELAY)
                try:
                    result = run_backtest(
                        symbol=symbol,
                        ib_client=ib_client,
                        period_days=PERIOD_DAYS,
                        stop_loss_pct=sl,
                        take_profit_pct=tp,
                        capital=500.0,
                    )
                    if result.total_trades >= MIN_TRADES:
                        if (best_result is None
                                or result.profit_factor > best_result.profit_factor):
                            best_result = result
                            best_sl = sl
                            best_tp = tp
                except Exception as e:
                    logger.warning(
                        f"Backtest {symbol} SL={sl:.1%} TP={tp:.1%} failed: {e}"
                    )

        update_symbol_parameters(
            symbol,
            stop_loss_pct=best_sl,
            take_profit_pct=best_tp,
            backtest_calibrated=1,
            backtest_calibrated_at=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        )

        if best_result:
            notify(
                f"📊 <b>{symbol}</b> calibrated:\n"
                f"SL={best_sl:.1%}  TP={best_tp:.1%}\n"
                f"Profit factor: {best_result.profit_factor:.2f} "
                f"({best_result.total_trades} trades, {PERIOD_DAYS}d)"
            )
            logger.info(
                f"Calibration done for {symbol}: SL={best_sl:.1%} TP={best_tp:.1%} "
                f"PF={best_result.profit_factor:.2f}"
            )
        else:
            notify(
                f"⚠️ <b>{symbol}</b>: no valid backtest results "
                f"(< {MIN_TRADES} trades). Using defaults."
            )
            logger.warning(f"No valid backtest results for {symbol} — defaults kept")

    except Exception as e:
        logger.error(f"Calibration failed for {symbol}: {e}")
