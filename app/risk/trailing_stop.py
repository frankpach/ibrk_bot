# app/risk/trailing_stop.py
"""TrailingStopManager — dynamic stop loss with breakeven and trailing rules."""
import logging
from dataclasses import dataclass

from app.db.models import Trade

logger = logging.getLogger(__name__)


@dataclass
class StopUpdateResult:
    new_stop_price: float | None
    reason: str | None
    should_close: bool


class TrailingStopManager:
    """
    Manages trailing stops for open positions:
    1. Breakeven Rule: If P&L% > 1.5 × original_SL%, move SL to entry ± 0.3%
    2. Trailing Rule: If P&L% > 3.0 × original_SL%, trailing at 50% of max gain
    3. Never moves SL backward
    """

    BREAKEVEN_MULTIPLIER = 1.5
    BREAKEVEN_BUFFER = 0.003
    TRAILING_MULTIPLIER = 3.0
    TRAILING_PCT = 0.5

    def update_stop_levels(self, trade: Trade, current_price: float) -> StopUpdateResult:
        """
        Calculate updated stop levels based on current price and trade state.
        """
        entry = trade.entry_price
        original_sl = trade.stop_loss_pct
        
        if trade.action == "BUY":
            pnl_pct = (current_price - entry) / entry
        else:  # SELL
            pnl_pct = (entry - current_price) / entry
        
        current_sl = trade.stop_loss_price
        new_sl = None
        reason = None
        
        # Breakeven rule
        if pnl_pct > self.BREAKEVEN_MULTIPLIER * original_sl:
            if trade.action == "BUY":
                breakeven_sl = entry * (1 + self.BREAKEVEN_BUFFER)
            else:
                breakeven_sl = entry * (1 - self.BREAKEVEN_BUFFER)
            
            # Only move if better than current
            if (trade.action == "BUY" and breakeven_sl > current_sl) or \
               (trade.action == "SELL" and breakeven_sl < current_sl):
                new_sl = breakeven_sl
                reason = "breakeven"
        
        # Trailing rule
        if pnl_pct > self.TRAILING_MULTIPLIER * original_sl:
            if trade.action == "BUY":
                # Trailing at 50% of max gain from entry
                trailing_sl = entry + (current_price - entry) * self.TRAILING_PCT
            else:
                trailing_sl = entry - (entry - current_price) * self.TRAILING_PCT
            
            # Only move if better than current
            if (trade.action == "BUY" and trailing_sl > current_sl) or \
               (trade.action == "SELL" and trailing_sl < current_sl):
                # Also better than breakeven if already applied
                if new_sl is None or \
                   (trade.action == "BUY" and trailing_sl > new_sl) or \
                   (trade.action == "SELL" and trailing_sl < new_sl):
                    new_sl = trailing_sl
                    reason = "trailing"
        
        # Check if current price hit the new SL
        should_close = False
        if new_sl is not None:
            if trade.action == "BUY" and current_price <= new_sl:
                should_close = True
            elif trade.action == "SELL" and current_price >= new_sl:
                should_close = True
        
        return StopUpdateResult(
            new_stop_price=round(new_sl, 2) if new_sl else None,
            reason=reason,
            should_close=should_close,
        )

    def get_current_sl(self, trade: Trade, current_price: float) -> float:
        """Get effective stop loss (current or updated)."""
        result = self.update_stop_levels(trade, current_price)
        if result.new_stop_price is not None:
            return result.new_stop_price
        return trade.stop_loss_price
