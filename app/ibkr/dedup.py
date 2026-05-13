# app/ibkr/dedup.py
"""OrderDeduplicator + PreflightChecker — prevent duplicate orders and validate before sending."""
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PreflightResult:
    ok: bool
    reason: Optional[str]


class OrderDeduplicator:
    """
    Prevents duplicate orders within a time window.
    Keyed by (symbol, action) with 30-second dedup window.
    """

    DEDUP_WINDOW_SECONDS = 30

    def __init__(self):
        self._recent: dict[tuple[str, str], float] = {}

    def is_duplicate(self, symbol: str, action: str) -> bool:
        """Check if an identical order was recently placed."""
        key = (symbol.upper(), action.upper())
        last_time = self._recent.get(key)
        if last_time and (time.time() - last_time) < self.DEDUP_WINDOW_SECONDS:
            logger.warning(f"Duplicate order blocked: {symbol} {action} (within {self.DEDUP_WINDOW_SECONDS}s)")
            return True
        return False

    def record(self, symbol: str, action: str) -> None:
        """Record an order as placed."""
        self._recent[(symbol.upper(), action.upper())] = time.time()
        # Cleanup old entries
        cutoff = time.time() - self.DEDUP_WINDOW_SECONDS * 2
        self._recent = {k: v for k, v in self._recent.items() if v > cutoff}


class PreflightChecker:
    """
    Validates all preconditions before sending an order to IBKR.
    """

    def __init__(self, ib_client):
        self._client = ib_client

    def check(
        self,
        symbol: str,
        action: str,
        quantity: float,
        order_type: str,
        limit_price: float = None,
    ) -> PreflightResult:
        """
        Run all pre-flight checks.
        Returns PreflightResult(ok=True) if all pass.
        """
        checks = [
            self._check_connection,
            self._check_symbol_tradable,
            self._check_quantity_positive,
            self._check_buying_power,
            self._check_limit_price,
            self._check_market_hours,
        ]
        
        for check_fn in checks:
            result = check_fn(symbol, action, quantity, order_type, limit_price)
            if not result.ok:
                return result
        
        return PreflightResult(ok=True, reason=None)

    def _check_connection(self, symbol, action, quantity, order_type, limit_price):
        try:
            if not self._client.ib.isConnected():
                return PreflightResult(ok=False, reason="IB Gateway not connected")
        except Exception:
            return PreflightResult(ok=False, reason="IB Gateway connection check failed")
        return PreflightResult(ok=True, reason=None)

    def _check_symbol_tradable(self, symbol, action, quantity, order_type, limit_price):
        # Basic check — symbol must be in allowed list
        from app.config.settings import ALLOWED_SYMBOLS
        if symbol.upper() not in ALLOWED_SYMBOLS:
            return PreflightResult(ok=False, reason=f"Symbol {symbol} not in allowed universe")
        return PreflightResult(ok=True, reason=None)

    def _check_quantity_positive(self, symbol, action, quantity, order_type, limit_price):
        if quantity <= 0:
            return PreflightResult(ok=False, reason="Quantity must be positive")
        return PreflightResult(ok=True, reason=None)

    def _check_buying_power(self, symbol, action, quantity, order_type, limit_price):
        if action.upper() != "BUY":
            # SELL orders don't require buying power check
            return PreflightResult(ok=True, reason=None)
        
        try:
            account = self._client.get_account()
            buying_power = account.get("buying_power", 0)
            price = limit_price or self._client.get_stock_price(symbol).get("market_price", 0)
            estimated_cost = quantity * price
            if estimated_cost > buying_power:
                return PreflightResult(
                    ok=False,
                    reason=f"Insufficient buying power: need ${estimated_cost:.2f}, have ${buying_power:.2f}",
                )
        except Exception as e:
            logger.warning(f"Could not check buying power: {e}")
            # Don't block on API failure, but log
        return PreflightResult(ok=True, reason=None)

    def _check_limit_price(self, symbol, action, quantity, order_type, limit_price):
        if order_type.upper() == "LMT" and limit_price is None:
            return PreflightResult(ok=False, reason="LMT order requires limit_price")
        return PreflightResult(ok=True, reason=None)

    def _check_market_hours(self, symbol, action, quantity, order_type, limit_price):
        # Allow orders 30 min before/after market hours
        import pytz
        try:
            now = datetime.now(pytz.timezone("America/New_York"))
            market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
            market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
            
            if now.weekday() >= 5:  # Weekend
                return PreflightResult(ok=False, reason="Markets closed (weekend)")
            
            # Allow 30 min buffer
            buffer = 30 * 60  # seconds
            seconds_from_open = (now - market_open).total_seconds()
            seconds_to_close = (market_close - now).total_seconds()
            
            if seconds_from_open < -buffer or seconds_to_close < -buffer:
                return PreflightResult(ok=False, reason="Markets closed (outside trading hours)")
        except Exception:
            pass
        return PreflightResult(ok=True, reason=None)


# Singletons
_dedup_instance = None

def get_deduplicator() -> OrderDeduplicator:
    global _dedup_instance
    if _dedup_instance is None:
        _dedup_instance = OrderDeduplicator()
    return _dedup_instance
