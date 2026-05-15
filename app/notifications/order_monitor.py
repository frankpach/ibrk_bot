# app/notifications/order_monitor.py
"""OrderExecutionMonitor — verifies order fills and tracks execution state."""
import logging
import time
from dataclasses import dataclass
from typing import Optional

from app.db.models import Trade
from app.infrastructure.db.compat import update_trade_status, update_trade_close_fill
from app.ibkr.fill_tracker import get_fill_price_fallback

logger = logging.getLogger(__name__)


@dataclass
class OrderResult:
    success: bool
    order_id: str
    status: str  # FILLED, PARTIAL, REJECTED, TIMEOUT
    fill_price: Optional[float]
    filled_quantity: float
    reason: Optional[str]


class OrderExecutionMonitor:
    """
    Monitors order execution from submission to fill.
    Ensures DB consistency with actual IBKR state.
    """

    FILL_TIMEOUT = 15  # seconds
    POLL_INTERVAL = 2.0  # seconds

    def __init__(self, ib_client):
        self._client = ib_client

    def place_and_monitor(
        self,
        symbol: str,
        action: str,
        quantity: float,
        order_type: str,
        limit_price: float = None,
    ) -> OrderResult:
        """
        Place order and monitor until fill or timeout.
        
        Returns OrderResult with actual fill details.
        """
        try:
            # Place order
            result = self._client.place_order(
                symbol=symbol,
                action=action,
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price,
            )
            order_id = result.get("order_id", "")
            initial_status = result.get("status", "PendingSubmit")
            
            logger.info(f"Order placed: {symbol} {action} {quantity} — status={initial_status}")
            
            # If already filled, return immediately
            if initial_status == "Filled":
                # Try to get fill price
                fill_price = self._get_fill_price(order_id, symbol)
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    status="FILLED",
                    fill_price=fill_price,
                    filled_quantity=quantity,
                    reason="Immediate fill",
                )
            
            # Poll for fill
            fill_price = self._poll_for_fill(order_id, symbol)
            
            if fill_price is not None:
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    status="FILLED",
                    fill_price=fill_price,
                    filled_quantity=quantity,
                    reason="Fill confirmed",
                )
            else:
                return OrderResult(
                    success=False,
                    order_id=order_id,
                    status="TIMEOUT",
                    fill_price=None,
                    filled_quantity=0,
                    reason=f"No fill after {self.FILL_TIMEOUT}s",
                )
                
        except Exception as e:
            logger.error(f"Order placement failed for {symbol}: {e}")
            return OrderResult(
                success=False,
                order_id="",
                status="REJECTED",
                fill_price=None,
                filled_quantity=0,
                reason=str(e),
            )

    def _poll_for_fill(self, order_id: str, symbol: str) -> Optional[float]:
        """Poll IBKR for fill status."""
        elapsed = 0
        while elapsed < self.FILL_TIMEOUT:
            time.sleep(self.POLL_INTERVAL)
            elapsed += self.POLL_INTERVAL
            
            fill_price = self._get_fill_price(order_id, symbol)
            if fill_price is not None:
                return fill_price
        
        return None

    def _get_fill_price(self, order_id: str, symbol: str) -> Optional[float]:
        """Get fill price from IBKR."""
        try:
            return get_fill_price_fallback(self._client, order_id, symbol)
        except Exception:
            return None

    def confirm_entry_fill(self, trade_id: int, order_id: str, symbol: str) -> bool:
        """Confirm entry fill and update DB with real fill price."""
        try:
            fill_price = self._get_fill_price(order_id, symbol)
            if fill_price is not None:
                update_trade_status(
                    trade_id=trade_id,
                    trade_status="FILLED",
                    fill_price=fill_price,
                )
                logger.info(f"Entry fill confirmed for {symbol}: ${fill_price:.2f}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to confirm entry fill: {e}")
            return False

    def confirm_close_fill(self, trade_id: int, close_order_id: str, symbol: str) -> Optional[float]:
        """Confirm close fill and update DB with real exit fill price."""
        try:
            fill_price = self._get_fill_price(close_order_id, symbol)
            if fill_price is not None:
                update_trade_close_fill(trade_id, close_order_id, fill_price)
                logger.info(f"Close fill confirmed for {symbol}: ${fill_price:.2f}")
                return fill_price
            return None
        except Exception as e:
            logger.error(f"Failed to confirm close fill: {e}")
            return None
