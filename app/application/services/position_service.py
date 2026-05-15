# app/application/services/position_service.py
from dataclasses import dataclass
from typing import Optional

from app.config.settings import MIN_PROFIT_PCT_MEDIUM
from app.risk.trailing_stop import TrailingStopManager
from app.risk.partial_exit import PartialExitManager


@dataclass
class ExitCondition:
    reason: str
    quantity: Optional[float] = None


class PositionService:
    def __init__(self):
        self._trailing_mgr = TrailingStopManager()
        self._partial_mgr = PartialExitManager()

    def check_exit_conditions(self, trade, current_price: float) -> Optional[ExitCondition]:
        """Check stop-loss, take-profit, and min-profit-medium conditions."""
        if trade.action == "BUY":
            if current_price <= trade.stop_loss_price:
                return ExitCondition(reason="STOP_LOSS")
            if current_price >= trade.take_profit_price:
                return ExitCondition(reason="TAKE_PROFIT")
            if trade.signal_strength == "MEDIUM":
                pnl_pct = (current_price - trade.entry_price) / trade.entry_price
                if pnl_pct >= MIN_PROFIT_PCT_MEDIUM:
                    return ExitCondition(reason="MIN_PROFIT_MEDIUM")
        elif trade.action == "SELL":
            if current_price >= trade.stop_loss_price:
                return ExitCondition(reason="STOP_LOSS")
            if current_price <= trade.take_profit_price:
                return ExitCondition(reason="TAKE_PROFIT")
        return None

    def check_partial_exit(self, trade, current_price: float):
        return self._partial_mgr.check_exit(trade, current_price)

    def apply_trailing_stop(self, trade, current_price: float):
        return self._trailing_mgr.update_stop_levels(trade, current_price)

    def get_breakeven_sl(self, trade):
        return self._partial_mgr.get_breakeven_sl(trade)
