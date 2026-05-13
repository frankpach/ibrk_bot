# app/risk/market_regime.py
"""MarketRegimeDetector — detect market regime using VIX levels."""
import logging
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass
class MarketRegime:
    vix_level: float
    regime: Literal["low_vol", "normal", "high_vol", "crisis"]


@dataclass
class RegimeAdjustments:
    position_size_multiplier: float
    sl_widening_multiplier: float
    entry_blocked: bool


class MarketRegimeDetector:
    """
    Detects market regime based on VIX level:
    - low_vol: VIX < 15
    - normal: 15 <= VIX < 25
    - high_vol: 25 <= VIX < 35
    - crisis: VIX >= 35
    """

    THRESHOLDS = [15.0, 25.0, 35.0]
    
    ADJUSTMENTS = {
        "low_vol": RegimeAdjustments(1.2, 0.9, False),
        "normal": RegimeAdjustments(1.0, 1.0, False),
        "high_vol": RegimeAdjustments(0.5, 1.3, False),
        "crisis": RegimeAdjustments(0.0, 1.5, True),
    }

    def get_regime(self, vix_level: float) -> MarketRegime:
        """Determine regime from VIX level."""
        if vix_level < self.THRESHOLDS[0]:
            regime = "low_vol"
        elif vix_level < self.THRESHOLDS[1]:
            regime = "normal"
        elif vix_level < self.THRESHOLDS[2]:
            regime = "high_vol"
        else:
            regime = "crisis"
        
        return MarketRegime(vix_level=vix_level, regime=regime)

    def get_adjustments(self, regime: str | MarketRegime) -> RegimeAdjustments:
        """Get adjustments for a regime."""
        if isinstance(regime, MarketRegime):
            regime = regime.regime
        return self.ADJUSTMENTS.get(regime, self.ADJUSTMENTS["normal"])

    def get_regime_from_data(self, data_layer) -> MarketRegime:
        """Fetch VIX and determine current regime."""
        try:
            df = data_layer.get_ohlcv("VIX", "5 D", "1 day", "on_demand")
            if df is not None and len(df) > 0:
                vix = float(df["close"].iloc[-1])
                return self.get_regime(vix)
        except Exception as e:
            logger.warning(f"Could not fetch VIX: {e}")
        
        # Fallback to normal if VIX unavailable
        return MarketRegime(vix_level=0.0, regime="normal")
