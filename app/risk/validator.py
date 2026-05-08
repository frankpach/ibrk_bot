# app/risk/validator.py
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config.settings import (
    MAX_POSITIONS, MAX_RISK_PCT, MIN_RISK_USD,
    MARKET_TZ, MARKET_OPEN_HOUR, MARKET_CLOSE_HOUR,
)
from app.db.database import get_approved_symbols

ALLOWED_ORDER_TYPES = {"MKT", "LMT"}


@dataclass
class ValidationResult:
    approved: bool
    reasons: list[str] = field(default_factory=list)
    position_size_units: int = 0
    estimated_risk_usd: float = 0.0


def validate_order(
    symbol: str, action: str, quantity: float, order_type: str,
    stop_loss_pct: float, capital: float, active_positions: int,
    now: datetime | None = None,
    liquid_hours: str | None = None,
    price: float = 1.0,
) -> ValidationResult:
    if now is None:
        now = datetime.now(tz=MARKET_TZ)

    reasons = []

    allowed = set(get_approved_symbols())
    if symbol.upper() not in allowed:
        reasons.append(f"Symbol {symbol} is not allowed (not in approved DB list)")

    if active_positions >= MAX_POSITIONS:
        reasons.append(f"Max positions ({MAX_POSITIONS}) already active")

    if order_type.upper() not in ALLOWED_ORDER_TYPES:
        reasons.append(f"Invalid order type {order_type}. Allowed: {ALLOWED_ORDER_TYPES}")

    # Horario: usa liquidHours de IB si se provee, sino fallback hardcodeado US stocks
    if liquid_hours:
        from app.ibkr.market_hours import is_liquid_at
        if not is_liquid_at(liquid_hours, now):
            reasons.append("Outside liquid hours for this instrument")
    else:
        if not _is_market_hours(now):
            reasons.append("Outside market hours (09:30-16:00 ET, Mon-Fri)")

    max_risk_usd = max(capital * MAX_RISK_PCT, MIN_RISK_USD)
    max_position_usd = max_risk_usd / stop_loss_pct if stop_loss_pct > 0 else 0
    position_size_units = max_position_usd / price if price > 0 else 0.0
    estimated_risk_usd = position_size_units * stop_loss_pct

    if reasons:
        return ValidationResult(approved=False, reasons=reasons)

    return ValidationResult(
        approved=True,
        reasons=["Order validated. Execution requires /orders/place"],
        position_size_units=position_size_units,
        estimated_risk_usd=round(estimated_risk_usd, 2),
    )


def _is_market_hours(now: datetime) -> bool:
    et = now.astimezone(MARKET_TZ)
    if et.weekday() >= 5:
        return False
    open_t = et.replace(hour=9, minute=30, second=0, microsecond=0)
    close_t = et.replace(hour=16, minute=0, second=0, microsecond=0)
    return open_t <= et <= close_t
