# app/risk/lmt_orders.py
"""LMT order calculator for entry orders."""
import logging

logger = logging.getLogger(__name__)


def calculate_limit_price(
    current_price: float,
    action: str,
    slippage_buffer_pct: float = 0.005,
) -> float:
    """
    Calculate limit price for entry orders.
    
    BUY: limit = current_price * (1 + buffer)
    SELL: limit = current_price * (1 - buffer)
    
    This gives slight slippage tolerance while avoiding MKT slippage.
    """
    if action.upper() == "BUY":
        limit = current_price * (1 + slippage_buffer_pct)
    else:  # SELL
        limit = current_price * (1 - slippage_buffer_pct)
    
    return round(limit, 2)


def is_fill_expected(
    current_price: float,
    limit_price: float,
    action: str,
) -> bool:
    """
    Check if current market price would fill a LMT order.
    
    BUY LMT fills if current_price <= limit_price
    SELL LMT fills if current_price >= limit_price
    """
    if action.upper() == "BUY":
        return current_price <= limit_price
    else:
        return current_price >= limit_price
