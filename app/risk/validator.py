# app/risk/validator.py
"""Validación de órdenes con reglas de riesgo estrictas."""
from dataclasses import dataclass, field
from datetime import datetime

from app.config.settings import (
    ALLOWED_SYMBOLS, MAX_POSITIONS, MAX_RISK_PCT, MIN_RISK_USD,
    MARKET_TZ, MARKET_OPEN_HOUR, MARKET_CLOSE_HOUR,
    MIN_RR_RATIO, MAX_POSITION_USD,
)
from app.db.database import get_open_trades, get_today_pnl

ALLOWED_ORDER_TYPES = {"MKT", "LMT"}
ALLOWED_ACTIONS = {"BUY", "SELL"}


@dataclass
class ValidationResult:
    approved: bool
    reasons: list[str] = field(default_factory=list)
    position_size_units: int = 0
    estimated_risk_usd: float = 0.0


def validate_order(
    symbol: str, action: str, quantity: int, order_type: str,
    stop_loss_pct: float, take_profit_pct: float, capital: float,
    active_positions: int, now: datetime | None = None,
) -> ValidationResult:
    if now is None:
        now = datetime.now(tz=MARKET_TZ)

    reasons: list[str] = []
    symbol = symbol.upper()
    action = action.upper()
    order_type = order_type.upper()

    # ── Validaciones básicas ──
    if symbol not in ALLOWED_SYMBOLS:
        reasons.append(f"Symbol {symbol} is not allowed")

    if action not in ALLOWED_ACTIONS:
        reasons.append(f"Action {action} must be BUY or SELL")

    if active_positions >= MAX_POSITIONS:
        reasons.append(f"Max positions ({MAX_POSITIONS}) already active")

    if order_type not in ALLOWED_ORDER_TYPES:
        reasons.append(f"Invalid order type {order_type}. Allowed: {ALLOWED_ORDER_TYPES}")

    if not _is_market_hours(now):
        reasons.append("Outside market hours (09:30-16:00 ET, Mon-Fri)")

    # ── Validación de porcentajes ──
    if stop_loss_pct <= 0:
        reasons.append("stop_loss_pct must be > 0")
    elif stop_loss_pct > 0.10:
        reasons.append("stop_loss_pct too high (>10%)")

    if take_profit_pct <= 0:
        reasons.append("take_profit_pct must be > 0")

    if stop_loss_pct > 0 and take_profit_pct > 0:
        rr = take_profit_pct / stop_loss_pct
        if rr < MIN_RR_RATIO:
            reasons.append(f"Reward/Risk ratio {rr:.2f} < {MIN_RR_RATIO} (TP must be >= {MIN_RR_RATIO}x SL)")

    # ── Validación de cantidad ──
    if quantity < 1:
        reasons.append("Quantity must be >= 1")

    # ── Sin posición duplicada ──
    open_trades = get_open_trades()
    open_symbols = {t.symbol for t in open_trades}
    if symbol in open_symbols:
        reasons.append(f"Already have an open position in {symbol}")

    # ── Límite de pérdida diaria ──
    today_pnl = get_today_pnl()
    max_risk_usd = max(capital * MAX_RISK_PCT, MIN_RISK_USD)
    daily_loss_limit = capital * 0.03  # 3% hard limit
    if today_pnl is not None and today_pnl < -daily_loss_limit:
        reasons.append(f"Daily loss limit reached: ${today_pnl:.2f}")

    # ── Cálculo de tamaño de posición ──
    if stop_loss_pct > 0:
        max_position_usd = min(max_risk_usd / stop_loss_pct, MAX_POSITION_USD)
        position_size_units = int(max_position_usd)
        estimated_risk_usd = position_size_units * stop_loss_pct
    else:
        position_size_units = 0
        estimated_risk_usd = 0.0

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
    open_t = et.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0, microsecond=0)
    close_t = et.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0, microsecond=0)
    return open_t <= et <= close_t
