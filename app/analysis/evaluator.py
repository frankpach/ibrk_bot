# app/analysis/evaluator.py
"""ReturnEvaluator — computes actual returns vs SPY for past candidate decisions."""
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def run_return_evaluator(data_layer):
    """Evaluate past decisions at 7d and 30d marks."""
    for days_ago in (7, 30):
        try:
            _evaluate_at(data_layer, days_ago)
        except Exception as e:
            logger.error(f"ReturnEvaluator failed for {days_ago}d: {e}")


def _evaluate_at(data_layer, days_ago: int):
    from app.infrastructure.db.compat import get_candidate_decisions_for_evaluation, get_connection
    decisions = get_candidate_decisions_for_evaluation(days_ago)
    if not decisions:
        return

    logger.info(f"Evaluating {len(decisions)} decisions from ~{days_ago} days ago")

    for dec in decisions:
        try:
            # Get current price of the symbol
            df = data_layer.get_ohlcv(dec.symbol, "5 D", "1 day", "backtest")
            if df is None or len(df) == 0:
                continue
            current_price = float(df["close"].iloc[-1])
            price_then = dec.price_at_decision or current_price

            return_pct = (current_price - price_then) / price_then if price_then > 0 else 0.0

            # Get SPY return over same period
            spy_df = data_layer.get_ohlcv("SPY", "40 D", "1 day", "backtest")
            alpha = None
            if spy_df is not None and len(spy_df) >= days_ago:
                spy_now = float(spy_df["close"].iloc[-1])
                spy_then = float(spy_df["close"].iloc[-min(days_ago, len(spy_df)-1)])
                spy_return = (spy_now - spy_then) / spy_then if spy_then > 0 else 0.0
                alpha = return_pct - spy_return

            # Update DB
            conn = get_connection()
            if days_ago <= 10:
                conn.execute(
                    "UPDATE candidate_decisions SET future_return_7d=?, alpha_vs_spy_7d=?, evaluated_7d_at=? WHERE id=?",
                    (round(return_pct, 4), round(alpha, 4) if alpha is not None else None,
                     datetime.now(timezone.utc).replace(tzinfo=None).isoformat(), dec.id)
                )
            else:
                conn.execute(
                    "UPDATE candidate_decisions SET future_return_30d=?, alpha_vs_spy_30d=?, evaluated_30d_at=? WHERE id=?",
                    (round(return_pct, 4), round(alpha, 4) if alpha is not None else None,
                     datetime.now(timezone.utc).replace(tzinfo=None).isoformat(), dec.id)
                )
            conn.commit()
            conn.close()
            if alpha is not None:
                logger.info(f"  {dec.symbol}: return={return_pct:.2%} alpha={alpha:.2%}")
            else:
                logger.info(f"  {dec.symbol}: return={return_pct:.2%}")

        except Exception as e:
            logger.error(f"Evaluation failed for {dec.symbol}: {e}")
