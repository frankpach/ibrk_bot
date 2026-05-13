"""Learning cycle coordinator — runs daily post-market."""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class LearningReport:
    date: str
    signal_filter_auc: float | None = None
    samples_used: int = 0
    symbols_rolled_back: list = field(default_factory=list)
    win_rates: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)

    def to_telegram(self) -> str:
        lines = [f"📊 <b>Learning Report — {self.date}</b>"]
        if self.signal_filter_auc is not None:
            lines.append(
                f"🤖 SignalFilter AUC: {self.signal_filter_auc:.3f} "
                f"({self.samples_used} samples)"
            )
        if self.symbols_rolled_back:
            lines.append(f"⚠️ Rollbacks: {', '.join(self.symbols_rolled_back)}")
        if self.win_rates:
            top = sorted(self.win_rates.items(), key=lambda x: -x[1])[:5]
            wr_str = " | ".join(f"{s}:{v:.0%}" for s, v in top)
            lines.append(f"📈 Win rates: {wr_str}")
        if self.errors:
            lines.append(f"❌ Errors: {len(self.errors)}")
        return "\n".join(lines)


def run_learning_cycle(data_layer) -> LearningReport:
    """
    Daily learning cycle: evaluate returns → retrain → rollback check → report.
    Each step is independent; failures are captured in LearningReport.errors.
    """
    report = LearningReport(date=datetime.utcnow().strftime("%Y-%m-%d"))

    # Step 1: evaluate pending returns
    try:
        from app.analysis.evaluator import run_return_evaluator
        run_return_evaluator(data_layer)
    except Exception as e:
        report.errors.append(f"ReturnEvaluator: {e}")
        logger.error(f"ReturnEvaluator failed: {e}")

    # Step 2: retrain SignalFilter if enough data
    try:
        from app.db.database import get_closed_trades_with_snapshots
        from app.ml.signal_filter import get_signal_filter
        trades = get_closed_trades_with_snapshots(limit=200)
        if len(trades) >= 10:
            sf = get_signal_filter()
            result = sf.retrain(trades)
            if isinstance(result, float):
                report.signal_filter_auc = result
                report.samples_used = len(trades)
                logger.info(f"SignalFilter retrained. AUC={result:.3f}, samples={len(trades)}")
    except Exception as e:
        report.errors.append(f"SignalFilter retrain: {e}")
        logger.error(f"SignalFilter retrain failed: {e}")

    # Step 3: rollback check and win rates per symbol
    try:
        from app.db.database import get_approved_symbols
        symbols = get_approved_symbols()
        for symbol in symbols:
            try:
                rolled = maybe_rollback_parameters(symbol)
                if rolled:
                    report.symbols_rolled_back.append(symbol)
                wr = _get_win_rate_last_10(symbol)
                if wr is not None:
                    report.win_rates[symbol] = wr
            except Exception as e:
                report.errors.append(f"{symbol}: {e}")
    except Exception as e:
        report.errors.append(f"Symbol loop: {e}")
        logger.error(f"Symbol loop failed: {e}")

    # Step 4: notify only when there's something worth reporting
    has_news = (
        report.signal_filter_auc is not None
        or report.symbols_rolled_back
        or report.errors
    )
    if has_news:
        try:
            from app.notifications.telegram import notify
            notify(report.to_telegram())
        except Exception as e:
            logger.error(f"Notify failed: {e}")

    return report


def maybe_rollback_parameters(symbol: str) -> bool:
    """
    Revert symbol_parameters to previous version if recent win rate < 30%.
    Returns True if rollback was applied.
    """
    from app.db.database import (
        get_closed_trades_by_symbol,
        get_or_create_symbol_parameters,
        update_symbol_parameters,
    )
    trades = get_closed_trades_by_symbol(symbol, limit=5)
    if len(trades) < 5:
        return False
    wins = sum(1 for t in trades if (t.pnl_pct or 0) > 0)
    if wins / 5 >= 0.30:
        return False
    params = get_or_create_symbol_parameters(symbol)
    if not params.previous_json:
        return False
    try:
        prev = json.loads(params.previous_json)
        update_symbol_parameters(symbol, **prev)
        from app.notifications.telegram import notify
        notify(
            f"⚠️ <b>{symbol}</b>: parameters reverted "
            f"(win rate: {wins}/5 last trades)"
        )
        logger.info(f"Rolled back {symbol} parameters (win rate {wins}/5)")
        return True
    except Exception as e:
        logger.error(f"Rollback failed for {symbol}: {e}")
        return False


def _get_win_rate_last_10(symbol: str) -> float | None:
    """Return win rate for last 10 closed trades, or None if < 3 trades."""
    from app.db.database import get_closed_trades_by_symbol
    trades = get_closed_trades_by_symbol(symbol, limit=10)
    if len(trades) < 3:
        return None
    wins = sum(1 for t in trades if (t.pnl_pct or 0) > 0)
    return wins / len(trades)
