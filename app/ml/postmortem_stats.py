"""Statistical context for postmortem analysis."""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PostmortemContext:
    win_rate_last_10: float
    avg_pnl_wins_pct: float
    avg_pnl_losses_pct: float
    sl_hit_rate: float
    tp_hit_rate: float
    most_common_exit: str
    patterns_last_3: list = field(default_factory=list)

    def to_prompt_str(self) -> str:
        parts = [
            f"Historical context for this symbol:",
            f"- Win rate (last 10 trades): {self.win_rate_last_10:.0%}",
            f"- Stop-loss hit rate: {self.sl_hit_rate:.0%}",
            f"- Take-profit hit rate: {self.tp_hit_rate:.0%}",
            f"- Avg winning trade: {self.avg_pnl_wins_pct:.1%}",
            f"- Avg losing trade: {self.avg_pnl_losses_pct:.1%}",
            f"- Most common exit: {self.most_common_exit}",
        ]
        if self.patterns_last_3:
            parts.append(
                "- Recent patterns: "
                + "; ".join(p[:60] for p in self.patterns_last_3)
            )
        return "\n".join(parts)


def enrich_postmortem_context(symbol: str) -> "PostmortemContext | None":
    """
    Build statistical context for postmortem prompt.
    Returns None if fewer than 3 closed trades exist for the symbol.
    """
    try:
        from app.db.database import get_closed_trades_by_symbol, get_patterns_for_symbol
        trades = get_closed_trades_by_symbol(symbol, limit=10)
        if len(trades) < 3:
            return None

        wins = [t for t in trades if (t.pnl_pct or 0) > 0]
        losses = [t for t in trades if (t.pnl_pct or 0) <= 0]
        sl_exits = [t for t in trades if t.exit_reason == "STOP_LOSS"]
        tp_exits = [t for t in trades if t.exit_reason == "TAKE_PROFIT"]

        from collections import Counter
        exit_counts = Counter(
            t.exit_reason for t in trades if t.exit_reason
        )
        most_common = exit_counts.most_common(1)

        patterns = get_patterns_for_symbol(symbol, limit=3)

        return PostmortemContext(
            win_rate_last_10=len(wins) / len(trades),
            avg_pnl_wins_pct=(
                sum(t.pnl_pct for t in wins) / len(wins) if wins else 0.0
            ),
            avg_pnl_losses_pct=(
                sum(t.pnl_pct for t in losses) / len(losses) if losses else 0.0
            ),
            sl_hit_rate=len(sl_exits) / len(trades),
            tp_hit_rate=len(tp_exits) / len(trades),
            most_common_exit=most_common[0][0] if most_common else "UNKNOWN",
            patterns_last_3=[p.pattern_text[:80] for p in patterns],
        )
    except Exception as e:
        logger.error(f"enrich_postmortem_context({symbol}) failed: {e}")
        return None
