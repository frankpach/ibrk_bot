# app/db/models.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Signal:
    id: Optional[int]
    symbol: str
    strength: str
    rsi: float
    macd: float
    volume_ratio: float
    extra_indicators: str
    created_at: datetime
    processed: bool = False


@dataclass
class Trade:
    id: Optional[int]
    symbol: str
    action: str
    quantity: int
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    stop_loss_pct: float
    take_profit_pct: float
    signal_strength: str
    llm_justification: str
    status: str
    exit_price: Optional[float]
    exit_reason: Optional[str]
    pnl_usd: Optional[float]
    pnl_pct: Optional[float]
    opened_at: datetime
    closed_at: Optional[datetime]
    order_id: Optional[str]


@dataclass
class Pattern:
    id: Optional[int]
    symbol: str
    pattern_text: str
    win_count: int
    loss_count: int
    created_at: datetime
    updated_at: datetime


@dataclass
class SymbolConfig:
    symbol: str
    extra_indicators: str
    approved: bool
    proposed_by: str
    created_at: datetime


@dataclass
class Decision:
    id: Optional[int]
    signal_id: int
    symbol: str
    llm_model: str
    prompt_summary: str
    response: str
    action: str
    stop_loss_pct: float
    take_profit_pct: float
    created_at: datetime


@dataclass
class FeatureSnapshot:
    id: Optional[int]
    symbol: str
    timestamp: str
    context: str
    rsi_14: Optional[float] = None
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_crossover: Optional[bool] = None
    atr_pct: Optional[float] = None
    sma20: Optional[float] = None
    sma50: Optional[float] = None
    sma200: Optional[float] = None
    bollinger_upper: Optional[float] = None
    bollinger_lower: Optional[float] = None
    bollinger_position: Optional[float] = None
    vwap: Optional[float] = None
    volume_ratio_20d: Optional[float] = None
    hist_volatility_30d: Optional[float] = None
    impl_volatility: Optional[float] = None
    rs_vs_spy_30d: Optional[float] = None
    rs_vs_qqq_30d: Optional[float] = None
    feature_relevance_json: str = "{}"


@dataclass
class SymbolParameter:
    symbol: str
    stop_loss_pct: float = 0.025
    take_profit_pct: float = 0.06
    min_profit_pct: float = 0.01
    momentum_mult: float = 1.0
    trend_mult: float = 1.0
    volume_mult: float = 1.0
    volatility_mult: float = 1.0
    portfolio_fit_mult: float = 1.0
    sentiment_mult: float = 1.0
    trade_count: int = 0
    version: int = 1
    previous_json: Optional[str] = None
    updated_at: str = ""


@dataclass
class CandidateDecision:
    id: Optional[int]
    symbol: str
    decision_date: str
    decision: str
    price_at_decision: Optional[float] = None
    quant_score: Optional[float] = None
    feature_snapshot_id: Optional[int] = None
    llm_summary: Optional[str] = None
    future_return_7d: Optional[float] = None
    future_return_30d: Optional[float] = None
    alpha_vs_spy_7d: Optional[float] = None
    alpha_vs_spy_30d: Optional[float] = None
    evaluated_7d_at: Optional[str] = None
    evaluated_30d_at: Optional[str] = None


@dataclass
class WatchlistScore:
    symbol: str
    signal_quality_score: float = 0.5
    admission_score: float = 0.5
    trade_history_score: float = 0.5
    watchlist_score: float = 0.5
    last_updated: str = ""
