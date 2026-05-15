# app/domain/trading/events.py
"""Domain events for the trading system."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events."""
    pass


@dataclass(frozen=True)
class TradingModeSwitched(DomainEvent):
    old_mode: str
    new_mode: str
    changed_by: str = "system"


@dataclass(frozen=True)
class SystemPaused(DomainEvent):
    paused_by: str = "system"


@dataclass(frozen=True)
class SystemResumed(DomainEvent):
    resumed_by: str = "system"


@dataclass(frozen=True)
class PositionClosed(DomainEvent):
    trade_id: int
    symbol: str
    pnl_usd: float
    pnl_pct: float
    exit_reason: str


@dataclass(frozen=True)
class OrderPlaced(DomainEvent):
    trade_id: int
    symbol: str
    action: str
    quantity: float
    order_type: str


@dataclass(frozen=True)
class ControlSettingChanged(DomainEvent):
    key: str
    old_value: str
    new_value: str
    changed_by: str = "system"
    is_secret: bool = False


@dataclass(frozen=True)
class CircuitBreakerTriggered(DomainEvent):
    daily_pnl: float
    capital: float
    loss_pct: float
