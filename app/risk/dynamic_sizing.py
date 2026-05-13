# app/risk/dynamic_sizing.py
"""PositionSizer — dynamic position sizing with win rate, volatility, and confidence."""
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PositionSizeResult:
    units: float
    estimated_risk_usd: float
    estimated_slippage_usd: float
    base_size: float
    win_rate_adj: float
    volatility_adj: float
    confidence_adj: float
    reasons: list[str]


class PositionSizer:
    """
    Calculates position size based on:
    - Base risk formula
    - Win rate adjustment
    - Volatility (ATR) adjustment
    - Confidence (score) adjustment
    - Slippage buffer
    """

    def __init__(self, max_risk_pct: float = 0.02, max_position_usd: float = 500.0,
                 min_risk_usd: float = 1.0, slippage_buffer: float = 0.005):
        self.max_risk_pct = max_risk_pct
        self.max_position_usd = max_position_usd
        self.min_risk_usd = min_risk_usd
        self.slippage_buffer = slippage_buffer

    def calculate_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss_pct: float,
        capital: float,
        atr_pct: float | None = None,
        win_rate: float | None = None,
        score: float | None = None,
    ) -> PositionSizeResult:
        """
        Calculate position size with adaptive adjustments.
        
        Formula:
        base_size = max_risk_usd / (stop_loss_pct + slippage_buffer)
        win_rate_adj = 0.5 + win_rate
        volatility_adj = 2.0 / atr_pct
        confidence_adj = min(score / 75, 1.5)
        final_size = base_size * win_rate_adj * volatility_adj * confidence_adj
        """
        reasons = []
        
        # 1. Base risk
        max_risk_usd = max(capital * self.max_risk_pct, self.min_risk_usd)
        effective_sl = stop_loss_pct + self.slippage_buffer
        base_size = max_risk_usd / effective_sl
        reasons.append(f"Base risk: ${max_risk_usd:.2f} / {effective_sl:.2%} = ${base_size:.2f}")
        
        # 2. Win rate adjustment (default 0.5 if unknown)
        wr = win_rate if win_rate is not None else 0.5
        if win_rate is None or win_rate < 0:
            reasons.append("Win rate unknown, using default 0.5")
        win_rate_adj = 0.5 + wr
        reasons.append(f"Win rate adj: {wr:.0%} → {win_rate_adj:.2f}x")
        
        # 3. Volatility adjustment
        if atr_pct is not None and atr_pct > 0:
            volatility_adj = 2.0 / atr_pct
            reasons.append(f"Volatility adj: ATR {atr_pct:.1f}% → {volatility_adj:.2f}x")
        else:
            volatility_adj = 1.0
            reasons.append("Volatility adj: ATR unavailable → 1.0x")
        
        # 4. Confidence adjustment
        if score is not None and score > 0:
            confidence_adj = min(score / 75.0, 1.5)
            reasons.append(f"Confidence adj: score {score:.0f} → {confidence_adj:.2f}x")
        else:
            confidence_adj = 1.0
            reasons.append("Confidence adj: no score → 1.0x")
        
        # 5. Final size
        final_size_usd = base_size * win_rate_adj * volatility_adj * confidence_adj
        
        # 6. Cap
        final_size_usd = min(final_size_usd, self.max_position_usd)
        if final_size_usd >= self.max_position_usd:
            reasons.append(f"Capped at MAX_POSITION_USD ${self.max_position_usd:.2f}")
        
        # 7. Calculate units
        units = final_size_usd / entry_price if entry_price > 0 else 0.0
        units = round(units, 4)
        
        # 8. Calculate metrics
        estimated_risk = units * entry_price * stop_loss_pct
        estimated_slippage = units * entry_price * self.slippage_buffer
        
        reasons.append(f"Final: {units} units @ ${entry_price:.2f} = ${final_size_usd:.2f}")
        
        logger.info(f"PositionSizer {symbol}: {units} units, risk=${estimated_risk:.2f}")
        
        return PositionSizeResult(
            units=units,
            estimated_risk_usd=round(estimated_risk, 2),
            estimated_slippage_usd=round(estimated_slippage, 2),
            base_size=round(base_size, 2),
            win_rate_adj=round(win_rate_adj, 2),
            volatility_adj=round(volatility_adj, 2),
            confidence_adj=round(confidence_adj, 2),
            reasons=reasons,
        )
