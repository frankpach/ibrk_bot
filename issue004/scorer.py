# app/analysis/scorer.py
"""QuantScorer — weighted 0-100 score with per-symbol multipliers."""
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

GLOBAL_WEIGHTS = {
    "momentum": 0.25,
    "trend": 0.20,
    "volume": 0.15,
    "volatility": 0.10,
    "portfolio_fit": 0.15,
    "sentiment": 0.15,
}

THRESHOLDS = {"rejected": 49, "watchlist": 69, "propose": 84, "priority": 100}

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
    recommendation: str
    weights_used: dict

    def to_dict(self) -> dict:
        import dataclasses
        return dataclasses.asdict(self)


def _dim_momentum(features) -> float:
    score = 0.4
    if features.rsi_14 is not None:
        if features.rsi_14 < 30 or features.rsi_14 > 70:
            score += 0.4
        elif features.rsi_14 < 40 or features.rsi_14 > 60:
            score += 0.1
    if features.macd_crossover:
        score += 0.3
    return min(1.0, score)


def _dim_trend(features) -> float:
    score = 0.3
    if features.sma50 and features.sma200:
        close = features.sma20 or features.sma50
        if close > features.sma50:
            score += 0.2
        if features.sma50 > features.sma200:
            score += 0.2
    if features.rs_vs_spy_30d is not None and features.rs_vs_spy_30d > 0:
        score += 0.2
    if features.bollinger_position is not None:
        if features.bollinger_position > 0.5:
            score += 0.1
    return min(1.0, score)


def _dim_volume(features) -> float:
    if features.volume_ratio_20d is None:
        return 0.5
    vr = features.volume_ratio_20d
    if vr >= 2.0:
        return 1.0
    if vr >= 1.5:
        return 0.8
    if vr >= 1.0:
        return 0.6
    if vr >= 0.7:
        return 0.4
    return 0.2


def _dim_volatility(features) -> float:
    if features.atr_pct is None:
        return 0.5
    atr = features.atr_pct
    if 1.5 <= atr <= 4.0:
        return 0.8
    if 1.0 <= atr <= 5.0:
        return 0.6
    return 0.3


def _dim_portfolio_fit(portfolio: list, capital: float = 500.0) -> float:
    score = 0.5
    positions = len(portfolio) if portfolio else 0
    if positions == 0:
        score += 0.3
    elif positions == 1:
        score += 0.1
    elif positions >= 3:
        score -= 0.3
    return max(0.0, min(1.0, score))


def _dim_sentiment(news_items: list) -> float:
    if not news_items:
        return 0.5
    pos = sum(1 for n in news_items if n.get("sentiment") == "positive")
    neg = sum(1 for n in news_items if n.get("sentiment") == "negative")
    total = len(news_items)
    if pos > neg:
        return 0.7 + 0.1 * (pos / total)
    if neg > pos:
        return 0.3 - 0.1 * (neg / total)
    return 0.5


def _get_multipliers(symbol: str) -> dict:
    """Load per-symbol weight multipliers from DB. Returns defaults if not found."""
    try:
        from app.db.database import get_or_create_symbol_parameters
        params = get_or_create_symbol_parameters(symbol)
        if params:
            return {
                "momentum": getattr(params, "momentum_mult", 1.0),
                "trend": getattr(params, "trend_mult", 1.0),
                "volume": getattr(params, "volume_mult", 1.0),
                "volatility": getattr(params, "volatility_mult", 1.0),
                "portfolio_fit": getattr(params, "portfolio_fit_mult", 1.0),
                "sentiment": getattr(params, "sentiment_mult", 1.0),
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
        from app.db.database import get_or_create_symbol_parameters, update_symbol_parameters
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
