# app/risk/cooldown.py
"""Re-entry cooldown — prevents re-entering a symbol too soon after exit."""
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class _CooldownRecord:
    exit_price: float
    exit_reason: str
    exited_at: float  # timestamp


class ReentryCooldown:
    """
    Manages cooldown periods after exit to prevent 'death by a thousand cuts'.
    """

    def __init__(
        self,
        cooldown_hours: float = 24.0,
        min_move_pct: float = 0.02,
        tp_cooldown_hours: float = 4.0,
    ):
        self.cooldown_hours = cooldown_hours
        self.min_move_pct = min_move_pct
        self.tp_cooldown_hours = tp_cooldown_hours
        self._registry: dict[str, _CooldownRecord] = {}
        self._lock = threading.Lock()

    def record_exit(self, symbol: str, exit_price: float, exit_reason: str) -> None:
        """Record an exit to activate cooldown."""
        with self._lock:
            self._registry[symbol.upper()] = _CooldownRecord(
                exit_price=exit_price,
                exit_reason=exit_reason,
                exited_at=time.time(),
            )
        logger.info(f"Cooldown activated for {symbol}: {exit_reason} @ ${exit_price:.2f}")

    def can_reenter(self, symbol: str, current_price: float) -> tuple[bool, str]:
        """
        Check if re-entry is allowed for a symbol.
        
        Returns:
            (allowed, reason)
        """
        symbol = symbol.upper()
        with self._lock:
            record = self._registry.get(symbol)
        
        if record is None:
            return True, "ok"
        
        elapsed_hours = (time.time() - record.exited_at) / 3600.0
        
        # After take-profit: shorter cooldown
        if record.exit_reason in ("TAKE_PROFIT", "MIN_PROFIT_MEDIUM", "TRAILING_STOP"):
            if elapsed_hours < self.tp_cooldown_hours:
                return False, f"TP cooldown: {elapsed_hours:.1f}h / {self.tp_cooldown_hours}h"
            return True, "ok"
        
        # After stop-loss: longer cooldown
        if elapsed_hours < self.cooldown_hours:
            # Check if price moved enough from exit
            price_move = abs(current_price - record.exit_price) / record.exit_price
            if price_move >= self.min_move_pct:
                return True, f"price moved {price_move:.1%} from SL"
            return False, f"SL cooldown: {elapsed_hours:.1f}h / {self.cooldown_hours}h"
        
        return True, "ok"

    def get_record(self, symbol: str) -> Optional[_CooldownRecord]:
        """Get cooldown record for a symbol (for debugging)."""
        return self._registry.get(symbol.upper())

    def clear(self, symbol: str = None) -> None:
        """Clear cooldown for a symbol, or all if None."""
        with self._lock:
            if symbol:
                self._registry.pop(symbol.upper(), None)
            else:
                self._registry.clear()


# Singleton
_cooldown_instance: Optional[ReentryCooldown] = None


def get_cooldown() -> ReentryCooldown:
    global _cooldown_instance
    if _cooldown_instance is None:
        _cooldown_instance = ReentryCooldown()
    return _cooldown_instance
