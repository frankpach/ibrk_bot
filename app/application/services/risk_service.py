# app/application/services/risk_service.py
from dataclasses import dataclass
from datetime import datetime

from app.config.settings import MAX_RISK_PCT, MIN_RISK_USD, MAX_POSITION_USD, MARKET_TZ
from app.risk.validator import validate_order as _validate_order


@dataclass
class ValidationResult:
    approved: bool
    reasons: list[str]


class ISystemStateRepository:
    """Interface for system state — implemented by control_settings or env for now."""
    def get_max_positions(self) -> int:
        from app.config.settings import MAX_POSITIONS
        return MAX_POSITIONS

    def get_max_risk_pct(self) -> float:
        return MAX_RISK_PCT

    def get_capital_cap(self) -> float:
        from app.config.settings import CAPITAL_CAP
        return CAPITAL_CAP

    def get_max_position_usd(self) -> float:
        return MAX_POSITION_USD

    def get_min_risk_usd(self) -> float:
        return MIN_RISK_USD


class RiskService:
    def __init__(self, system_state_repo: ISystemStateRepository = None):
        self._repo = system_state_repo or ISystemStateRepository()

    def get_max_positions(self) -> int:
        return self._repo.get_max_positions()

    def validate_order(self, symbol: str, action: str, quantity: float, order_type: str,
                       stop_loss_pct: float, capital: float, active_positions: int,
                       now: datetime = None) -> ValidationResult:
        now = now or datetime.now(tz=MARKET_TZ)
        result = _validate_order(
            symbol=symbol, action=action, quantity=quantity,
            order_type=order_type, stop_loss_pct=stop_loss_pct,
            capital=capital, active_positions=active_positions, now=now,
        )
        return ValidationResult(approved=result.approved, reasons=result.reasons)

    def calculate_position_size(self, price: float, stop_loss_pct: float,
                                capital: float = None) -> float:
        cap = capital if capital is not None else self._repo.get_capital_cap()
        max_risk_usd = max(cap * self._repo.get_max_risk_pct(), self._repo.get_min_risk_usd())
        max_position_usd = min(max_risk_usd / stop_loss_pct, self._repo.get_max_position_usd()) if stop_loss_pct > 0 else 0
        units = max_position_usd / price if price > 0 else 0.0
        return round(units, 4)

    def check_circuit_breaker(self, daily_pnl: float, capital: float) -> bool:
        if daily_pnl >= 0:
            return False
        loss_pct = abs(daily_pnl) / capital
        return loss_pct >= 0.05
