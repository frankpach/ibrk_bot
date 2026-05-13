# app/ibkr/fill_tracker.py
"""FillTracker — tracks real fill prices from IBKR for accurate P&L."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class FillTracker:
    """
    Retrieves actual fill prices from IBKR after order execution.
    Uses ib.fills() to find the fill for a given order_id.
    """

    def __init__(self, ib_client):
        self._client = ib_client

    def get_fill_price(self, order_id: str) -> Optional[float]:
        """
        Get the fill price for a given order ID.
        Returns None if not found.
        """
        try:
            # Get all fills and find matching order
            fills = self._client.get_executions(since_days=1)
            if isinstance(fills, list):
                for fill in fills:
                    # IBKR execution ID may contain order ID
                    fill_order_id = str(fill.get("order_id", ""))
                    if fill_order_id == str(order_id):
                        return float(fill.get("price", 0))
            
            # Alternative: check trade fills directly
            # This requires access to ib.trades() which isn't exposed in our client
            # Fallback: return None and caller uses last known price
            return None
        except Exception as e:
            logger.error(f"Failed to get fill price for order {order_id}: {e}")
            return None

    def get_last_fill_for_symbol(self, symbol: str, since_days: int = 1) -> Optional[float]:
        """
        Get the most recent fill price for a symbol.
        """
        try:
            fills = self._client.get_executions(since_days=since_days)
            if isinstance(fills, list):
                for fill in fills:
                    if fill.get("symbol") == symbol.upper():
                        return float(fill.get("price", 0))
            return None
        except Exception as e:
            logger.error(f"Failed to get fills for {symbol}: {e}")
            return None


def get_fill_price_fallback(ib_client, order_id: str, symbol: str) -> float:
    """
    Get fill price with fallback to current market price.
    
    Priority:
    1. Actual fill price from IBKR
    2. Current market price (with warning)
    """
    tracker = FillTracker(ib_client)
    
    # Try order-specific fill
    fill_price = tracker.get_fill_price(order_id)
    if fill_price is not None:
        return fill_price
    
    # Fallback: current market price
    try:
        price_data = ib_client.get_stock_price(symbol)
        market_price = price_data.get("market_price")
        if market_price:
            logger.warning(
                f"Using market price ${market_price} as fill price for {symbol} "
                f"(order {order_id}) — actual fill not found"
            )
            return market_price
    except Exception as e:
        logger.error(f"Could not get fallback price for {symbol}: {e}")
    
    raise ValueError(f"Could not determine fill price for {symbol} order {order_id}")
