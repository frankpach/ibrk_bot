# app/analysis/scorer.py
"""QuantScorer — weighted 0-100 score with per-symbol multipliers."""
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

GLOBAL_WEIGHTS = {
    "momentum": 0.20,
    "trend": 0.15,
    "volume": 0.15,
    "volatility": 0.10,
    "portfolio_fit": 0.10,
    "sentiment": 0.10,
    "price_change": 0.20,
}

THRESHOLDS = {"rejected": 35, "watchlist": 55, "propose": 75, "priority": 100}

LEARNING_RATE = 0.15
MIN_TRADE_COUNT = 5
MULT_MIN, MULT_MAX = 0.5, 1.5


@dataclass
class QuantScore:
    symbol: str
    total: float
    momentum: float
    trend: float
    volume: float
    volatility: float
    portfolio_fit: float
    sentiment: float
    price_change: float
    recommendation: str
    weights_used: dict

    def to_dict(self) -> dict:
        import dataclasses
        return dataclasses.asdict(self)


def _dim_momentum(features) -> float:
    score = 0.0
    if features.rsi_14 is not None:
        if features.rsi_14 < 25 or features.rsi_14 > 75:
            score += 0.5
        elif features.rsi_14 < 35 or features.rsi_14 > 65:
            score += 0.3
        elif features.rsi_14 < 45 or features.rsi_14 > 55:
            score += 0.1
    if features.macd_crossover:
        score += 0.4
    return min(1.0, score)


def _dim_trend(features) -> float:
    score = 0.0
    if features.sma50 and features.sma200:
        close = features.sma20 or features.sma50
        if close > features.sma50:
            score += 0.25
        if features.sma50 > features.sma200:
            score += 0.25
    if features.rs_vs_spy_30d is not None:
        if features.rs_vs_spy_30d > 0.05:
            score += 0.3
        elif features.rs_vs_spy_30d > 0:
            score += 0.15
    if features.bollinger_position is not None:
        if features.bollinger_position > 0.6:
            score += 0.2
        elif features.bollinger_position > 0.4:
            score += 0.1
    return min(1.0, score)


def _dim_volume(features) -> float:
    if features.volume_ratio_20d is None:
        return 0.0
    vr = features.volume_ratio_20d
    if vr >= 3.0:
        return 1.0
    if vr >= 2.0:
        return 0.85
    if vr >= 1.5:
        return 0.7
    if vr >= 1.0:
        return 0.5
    if vr >= 0.7:
        return 0.3
    return 0.1


def _dim_volatility(features) -> float:
    if features.atr_pct is None:
        return 0.0
    atr = features.atr_pct
    if 1.0 <= atr <= 2.5: return 1.0   # Optimal zone for fixed SL
    if 0.5 <= atr < 1.0:  return 0.6   # Too low: little expected movement
    if 2.5 < atr <= 4.0:  return 0.5   # High: SL noise risk
    if atr > 4.0:          return 0.2   # Very high: weak signal
    return 0.3


def _dim_portfolio_fit(portfolio: list, capital: float = 500.0) -> float:
    score = 0.0
    positions = len(portfolio) if portfolio else 0
    if positions == 0:
        score += 1.0
    elif positions == 1:
        score += 0.7
    elif positions == 2:
        score += 0.4
    else:
        score += 0.0
    return max(0.0, min(1.0, score))


def _dim_sentiment(news_items: list) -> float:
    if not news_items:
        return 0.0
    pos = sum(1 for n in news_items if n.get("sentiment") == "positive")
    neg = sum(1 for n in news_items if n.get("sentiment") == "negative")
    total = len(news_items)
    if pos > neg:
        return 0.6 + 0.4 * (pos / total)
    if neg > pos:
        return max(0.0, 0.4 - 0.4 * (neg / total))
    return 0.5


def _dim_price_change(features) -> float:
    pc = features.price_change_pct
    if pc is None: return 0.0
    if 1.0 <= pc <= 4.0:   return 0.9   # Positive moderate momentum — ideal BUY
    if 0.0 <= pc < 1.0:    return 0.6   # Neutral-positive
    if 4.0 < pc:            return 0.7   # Strong momentum — watch overbought
    if -1.0 <= pc < 0.0:   return 0.4   # Slight pullback — possible entry
    if -3.0 <= pc < -1.0:  return 0.2   # Moderate drop — caution
    return 0.1                           # Collapse (< -3%) — possible bear trap


def _get_multipliers(symbol: str) -> dict:
    """Load per-symbol weight multipliers from DB. Returns defaults if not found."""
    try:
        from app.infrastructure.db.compat import get_or_create_symbol_parameters
        params = get_or_create_symbol_parameters(symbol)
        if params:
            return {
                "momentum": getattr(params, "momentum_mult", 1.0),
                "trend": getattr(params, "trend_mult", 1.0),
                "volume": getattr(params, "volume_mult", 1.0),
                "volatility": getattr(params, "volatility_mult", 1.0),
                "portfolio_fit": getattr(params, "portfolio_fit_mult", 1.0),
                "sentiment": getattr(params, "sentiment_mult", 1.0),
                "price_change": 1.0,
            }
    except Exception:
        pass
    return {k: 1.0 for k in GLOBAL_WEIGHTS}


def compute_score(features, symbol: str, portfolio: list, news_items: list = None) -> QuantScore:
    multipliers = _get_multipliers(symbol)
    dims = {
        "momentum": _dim_momentum(features),
        "trend": _dim_trend(features),
        "volume": _dim_volume(features),
        "volatility": _dim_volatility(features),
        "portfolio_fit": _dim_portfolio_fit(portfolio),
        "sentiment": _dim_sentiment(news_items or []),
        "price_change": _dim_price_change(features),
    }
    effective = {k: GLOBAL_WEIGHTS[k] * multipliers.get(k, 1.0) for k in GLOBAL_WEIGHTS}
    total_weight = sum(effective.values())
    if total_weight == 0:
        total_weight = 1.0
    normalized = {k: v / total_weight for k, v in effective.items()}
    total = sum(dims[k] * normalized[k] for k in dims) * 100
    total = max(0.0, min(100.0, total))

    if total <= THRESHOLDS["rejected"]:
        rec = "REJECTED"
    elif total <= THRESHOLDS["watchlist"]:
        rec = "WATCHLIST"
    elif total <= THRESHOLDS["propose"]:
        rec = "PROPOSE"
    else:
        rec = "PRIORITY"

    return QuantScore(
        symbol=symbol, total=round(total, 2),
        momentum=round(dims["momentum"], 3),
        trend=round(dims["trend"], 3),
        volume=round(dims["volume"], 3),
        volatility=round(dims["volatility"], 3),
        portfolio_fit=round(dims["portfolio_fit"], 3),
        sentiment=round(dims["sentiment"], 3),
        price_change=round(dims["price_change"], 3),
        recommendation=rec,
        weights_used={k: round(normalized[k], 4) for k in normalized},
    )


def update_weights_attenuated(
    symbol: str,
    dimension: str,
    suggested_multiplier: float,
    confidence: float,
    learning_rate: float = LEARNING_RATE,
    min_trade_count: int = MIN_TRADE_COUNT,
) -> bool:
    """Update per-symbol weight multiplier with attenuation. Returns False if trade count < min."""
    try:
        from app.infrastructure.db.compat import get_or_create_symbol_parameters, update_symbol_parameters
        params = get_or_create_symbol_parameters(symbol)
        if params is None:
            return False
        if getattr(params, "trade_count", 0) < min_trade_count:
            return False
        field = f"{dimension}_mult"
        old_mult = getattr(params, field, 1.0)
        new_mult = old_mult + (suggested_multiplier - old_mult) * confidence * learning_rate
        new_mult = max(MULT_MIN, min(MULT_MAX, new_mult))
        update_symbol_parameters(symbol, **{field: round(new_mult, 4)})
        logger.info(f"Updated {symbol} {dimension}_mult: {old_mult:.4f} -> {new_mult:.4f}")
        return True
    except Exception as e:
        logger.error(f"update_weights_attenuated failed: {e}")
        return False
