# app/risk/adaptive_sl.py
"""ATR-Based Adaptive Stop Loss — dynamic SL based on symbol volatility."""
import logging

logger = logging.getLogger(__name__)

# Constants
MIN_SL_PCT = 0.015   # 1.5% minimum
MAX_SL_PCT = 0.05    # 5.0% maximum
ATR_MULTIPLIER = 1.5


def calculate_adaptive_sl(atr_pct: float | None) -> float:
    """
    Calculate adaptive stop-loss based on ATR percentage.
    
    Formula: SL = ATR% × 1.5
    Bounds: min 1.5%, max 5.0%
    
    Args:
        atr_pct: ATR as percentage of price (e.g. 2.8 for 2.8%)
    
    Returns:
        Stop-loss percentage (e.g. 0.042 for 4.2%)
    """
    if atr_pct is None or atr_pct <= 0:
        logger.warning("ATR not available, using default SL=2.5%")
        return 0.025
    
    sl = atr_pct * ATR_MULTIPLIER / 100.0  # Convert from percentage to decimal
    sl = max(MIN_SL_PCT, min(MAX_SL_PCT, sl))
    
    logger.info(f"Adaptive SL: ATR={atr_pct:.2f}% → SL={sl:.2%}")
    return sl


def get_sl_for_symbol(atr_pct: float | None, default_sl: float = 0.025) -> float:
    """Get SL for a symbol, falling back to default if ATR unavailable."""
    if atr_pct is None:
        return default_sl
    return calculate_adaptive_sl(atr_pct)
