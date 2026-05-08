# app/analysis/hard_rules.py
"""HardRules — deterministic gates before LLM analysis. No LLM involved."""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class HardRulesResult:
    passed: bool
    failures: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    earnings_in_days: Optional[int] = None


def check_all(
    symbol: str,
    features,
    portfolio: list,
    earnings_date: Optional[datetime],
    capital: float = 500.0,
    stop_loss_pct: float = 0.025,
) -> HardRulesResult:
    failures = []
    warnings = []
    earnings_in_days = None

    # 1. Liquidity check
    if features.volume_ratio_20d is not None:
        if features.volume_ratio_20d < 0.3:
            failures.append(f"Insufficient liquidity: volume_ratio={features.volume_ratio_20d:.2f} < 0.3")
        elif features.volume_ratio_20d < 0.7:
            warnings.append(f"Low volume: volume_ratio={features.volume_ratio_20d:.2f}")

    # 2. Earnings gate
    if earnings_date is not None:
        now = datetime.now(tz=earnings_date.tzinfo) if earnings_date.tzinfo else datetime.now()
        delta = (earnings_date.replace(tzinfo=None) - now.replace(tzinfo=None)).days
        earnings_in_days = max(0, delta)
        if delta < 3:
            failures.append(f"Earnings in {delta} days — too close to enter")
        elif delta < 7:
            warnings.append(f"Earnings in {delta} days — consider reducing TP")
    else:
        warnings.append("Earnings date unknown — verify before entry")

    # 3. Capital check
    from app.config.settings import MAX_RISK_PCT, MIN_RISK_USD, MAX_POSITION_USD
    max_risk = max(capital * MAX_RISK_PCT, MIN_RISK_USD)
    max_pos_usd = min(max_risk / stop_loss_pct, MAX_POSITION_USD) if stop_loss_pct > 0 else 0
    price = features.sma20 or 100.0
    units = int(max_pos_usd / price) if price > 0 else 0
    if units < 1:
        failures.append(f"Insufficient capital: max_pos=${max_pos_usd:.2f}, price=${price:.2f}, units=0")

    # 4. Correlation proxy (simplified: warn if same category already held)
    if portfolio:
        try:
            from app.llm.agent import get_symbol_category
            sym_cat = get_symbol_category(symbol)
            held_cats = []
            for pos in portfolio:
                pos_sym = pos.get("symbol", "") if isinstance(pos, dict) else getattr(pos, "symbol", "")
                held_cats.append(get_symbol_category(pos_sym))
            same_cat = sum(1 for c in held_cats if c == sym_cat)
            if same_cat >= 2:
                failures.append(f"Correlation risk: {same_cat} positions in same category '{sym_cat}'")
            elif same_cat == 1:
                warnings.append(f"1 existing position in same category '{sym_cat}'")
        except Exception:
            pass

    return HardRulesResult(
        passed=len(failures) == 0,
        failures=failures,
        warnings=warnings,
        earnings_in_days=earnings_in_days,
    )
