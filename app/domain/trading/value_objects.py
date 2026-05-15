# app/domain/trading/value_objects.py
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class Order:
    symbol: str
    action: str
    quantity: float
    order_type: str
    limit_price: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None


@dataclass
class OrderResult:
    success: bool
    order_id: str
    fill_price: Optional[float] = None
    reason: Optional[str] = None


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_cost: float
    market_value: float
    unrealized_pnl: float


@dataclass
class AccountSummary:
    net_liquidation: float
    buying_power: float
    daily_pnl_usd: float
    daily_pnl_pct: float
