# app/risk/partial_exit.py
"""PartialExitManager — scales out of winning trades in tranches."""
import logging
from dataclasses import dataclass
from typing import Optional

from app.db.models import Trade

logger = logging.getLogger(__name__)


@dataclass
class PartialExitResult:
    should_exit: bool
    exit_quantity: float
    remaining_quantity: float
    exit_reason: str | None
    close_all: bool


class PartialExitManager:
    """
    Partial exit rules:
    1. At +1.5× SL: exit 50% of position, move SL to breakeven+0.3%
    2. Remainder: managed by trailing stop
    3. Never reduces remaining below 1 share
    """

    FIRST_EXIT_MULTIPLIER = 1.5
    FIRST_EXIT_PCT = 0.50
    MIN_REMAINING_SHARES = 1.0
    BREAKEVEN_BUFFER = 0.003

    def check_exit(self, trade: Trade, current_price: float) -> PartialExitResult:
        """
        Check if a partial exit should be triggered.
        Only triggers once per trade (partial_exit_done flag).
        """
        if trade.partial_exit_done:
            return PartialExitResult(
                should_exit=False,
                exit_quantity=0,
                remaining_quantity=trade.remaining_quantity or trade.quantity,
                exit_reason=None,
                close_all=False,
            )
        
        entry = trade.entry_price
        sl_pct = trade.stop_loss_pct
        
        if trade.action == "BUY":
            pnl_pct = (current_price - entry) / entry
        else:  # SELL
            pnl_pct = (entry - current_price) / entry
        
        trigger_pct = self.FIRST_EXIT_MULTIPLIER * sl_pct
        
        if pnl_pct >= trigger_pct:
            total_qty = trade.remaining_quantity or trade.quantity
            exit_qty = total_qty * self.FIRST_EXIT_PCT
            remaining = total_qty - exit_qty
            
            # Ensure minimum remaining
            if remaining < self.MIN_REMAINING_SHARES:
                # Close all instead of leaving tiny position
                return PartialExitResult(
                    should_exit=True,
                    exit_quantity=total_qty,
                    remaining_quantity=0,
                    exit_reason="PARTIAL_FULL",
                    close_all=True,
                )
            
            return PartialExitResult(
                should_exit=True,
                exit_quantity=round(exit_qty, 4),
                remaining_quantity=round(remaining, 4),
                exit_reason="PARTIAL_50PCT",
                close_all=False,
            )
        
        return PartialExitResult(
            should_exit=False,
            exit_quantity=0,
            remaining_quantity=trade.remaining_quantity or trade.quantity,
            exit_reason=None,
            close_all=False,
        )

    def get_breakeven_sl(self, trade: Trade) -> float:
        """
        Calculate new stop loss at breakeven + small buffer.
        Called after first partial exit.
        """
        if trade.action == "BUY":
            return round(trade.entry_price * (1 + self.BREAKEVEN_BUFFER), 2)
        else:
            return round(trade.entry_price * (1 - self.BREAKEVEN_BUFFER), 2)

    def update_trade_after_partial(
        self,
        trade: Trade,
        exit_result: PartialExitResult,
    ) -> Trade:
        """
        Update trade object after partial exit (in-memory).
        DB update should be done by caller.
        """
        if not exit_result.should_exit:
            return trade
        
        trade.partial_exit_done = True
        trade.remaining_quantity = exit_result.remaining_quantity
        
        # Move SL to breakeven if partial
        if not exit_result.close_all:
            new_sl = self.get_breakeven_sl(trade)
            trade.stop_loss_price = new_sl
            logger.info(
                f"Partial exit for {trade.symbol}: closed {exit_result.exit_quantity}, "
                f"remaining {exit_result.remaining_quantity}, SL moved to ${new_sl:.2f}"
            )
        
        return trade
