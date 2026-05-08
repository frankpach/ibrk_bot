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
