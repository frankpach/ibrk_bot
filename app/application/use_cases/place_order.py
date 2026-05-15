# app/application/use_cases/place_order.py
"""PlaceOrderUseCase — encapsulates order placement logic."""
from dataclasses import dataclass
from datetime import datetime
from threading import Lock

from app.application.ports.broker_port import IBrokerPort
from app.application.ports.notification_port import INotificationPort
from app.application.services.risk_service import RiskService
from app.domain.trading.value_objects import Order
from app.config.settings import MARKET_TZ, REQUIRE_HUMAN_APPROVAL, ENTRY_SLIPPAGE_BUFFER
from app.risk.lmt_orders import calculate_limit_price
from app.risk.validator import validate_order
from app.ibkr.dedup import PreflightChecker, get_deduplicator
from app.notifications.order_monitor import OrderExecutionMonitor
from app.infrastructure.db.compat import insert_trade
from app.db.models import Trade
from app.api.capital import get_operating_capital


@dataclass
class PlaceOrderCommand:
    symbol: str
    action: str
    quantity: float
    signal_strength: str = "MANUAL"
    requested_by: str = "system"
    order_type: str = "LMT"
    limit_price: float = None
    stop_loss_pct: float = 0.025
    take_profit_pct: float = 0.06


@dataclass
class PlaceOrderResult:
    success: bool
    order_id: str = ""
    trade_id: int = 0
    error: str = None


class PlaceOrderUseCase:
    def __init__(
        self,
        broker: IBrokerPort,
        notifier: INotificationPort,
        risk_service: RiskService = None,
    ):
        self._broker = broker
        self._notifier = notifier
        self._risk = risk_service or RiskService()
        self._symbol_locks: dict[str, Lock] = {}

    def _get_lock(self, symbol: str) -> Lock:
        if symbol not in self._symbol_locks:
            self._symbol_locks[symbol] = Lock()
        return self._symbol_locks[symbol]

    def execute(self, cmd: PlaceOrderCommand) -> PlaceOrderResult:
        symbol = cmd.symbol.upper()
        with self._get_lock(symbol):
            return self._execute(cmd)

    def _execute(self, cmd: PlaceOrderCommand) -> PlaceOrderResult:
        symbol = cmd.symbol.upper()
        try:
            price_data = self._broker.get_price(symbol)
            current_price = float(price_data)
        except Exception as exc:
            return PlaceOrderResult(success=False, error=f"Could not fetch price: {exc}")

        try:
            account = self._broker.get_account()
            capital = get_operating_capital(account.net_liquidation)
        except Exception as exc:
            return PlaceOrderResult(success=False, error=f"Could not fetch account: {exc}")

        try:
            portfolio = self._broker.get_portfolio()
            active_positions = len(portfolio)
        except Exception as exc:
            return PlaceOrderResult(success=False, error=f"Could not fetch portfolio: {exc}")

        result = self._risk.validate_order(
            symbol=symbol, action=cmd.action, quantity=cmd.quantity,
            order_type=cmd.order_type, stop_loss_pct=cmd.stop_loss_pct,
            capital=capital, active_positions=active_positions,
            now=datetime.now(tz=MARKET_TZ),
        )
        if not result.approved:
            return PlaceOrderResult(success=False, error=f"Validation failed: {result.reasons}")

        units = self._risk.calculate_position_size(price=current_price, stop_loss_pct=cmd.stop_loss_pct, capital=capital)
        buying_power = account.buying_power
        estimated_cost = units * current_price
        if units <= 0:
            return PlaceOrderResult(success=False, error="Position size is 0")
        if estimated_cost > buying_power:
            return PlaceOrderResult(success=False, error="Insufficient buying power")

        entry_order_type = cmd.order_type.upper()
        limit_price = cmd.limit_price
        if entry_order_type == "MKT":
            limit_price = calculate_limit_price(current_price, cmd.action)
            entry_order_type = "LMT"
        elif limit_price is None and current_price:
            if cmd.action == "BUY":
                limit_price = round(current_price * (1 + ENTRY_SLIPPAGE_BUFFER), 2)
            else:
                limit_price = round(current_price * (1 - ENTRY_SLIPPAGE_BUFFER), 2)

        # Preflight + dedup + place via raw IB client (legacy bridge)
        from app.ibkr.client import get_client as _get_ib_client
        ib_client = _get_ib_client()
        preflight = PreflightChecker(ib_client).check(symbol, cmd.action, units, entry_order_type, limit_price)
        if not preflight.ok:
            return PlaceOrderResult(success=False, error=f"Preflight failed: {preflight.reason}")

        dedup = get_deduplicator()
        if dedup.is_duplicate(symbol, cmd.action):
            return PlaceOrderResult(success=False, error="Duplicate order blocked")

        if REQUIRE_HUMAN_APPROVAL:
            stop_loss_price_val = round(current_price * (1 - cmd.stop_loss_pct), 2)
            take_profit_price_val = round(current_price * (1 + cmd.take_profit_pct), 2)
            estimated_risk = round(units * current_price * cmd.stop_loss_pct, 2)
            approved = self._notifier.request_approval(
                symbol=symbol, action=cmd.action, units=units,
                entry_price=current_price, stop_loss_price=stop_loss_price_val,
                take_profit_price=take_profit_price_val, estimated_risk_usd=estimated_risk,
            )
            if not approved:
                return PlaceOrderResult(success=False, error="Human approval rejected or timed out")

        monitor = OrderExecutionMonitor(ib_client)
        order_result = monitor.place_and_monitor(
            symbol=symbol, action=cmd.action, quantity=units,
            order_type=entry_order_type, limit_price=limit_price,
        )
        if not order_result.success:
            return PlaceOrderResult(success=False, error=f"Order placement failed: {order_result.reason}")

        dedup.record(symbol, cmd.action)
        fill_price = order_result.fill_price or current_price

        price_for_sl = fill_price or current_price
        if cmd.action == "BUY":
            stop_loss_price = round(price_for_sl * (1 - cmd.stop_loss_pct), 2)
            take_profit_price = round(price_for_sl * (1 + cmd.take_profit_pct), 2)
        else:
            stop_loss_price = round(price_for_sl * (1 + cmd.stop_loss_pct), 2)
            take_profit_price = round(price_for_sl * (1 - cmd.take_profit_pct), 2)

        trade_id = insert_trade(Trade(
            id=None, symbol=symbol, action=cmd.action, quantity=units,
            entry_price=price_for_sl, stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price, stop_loss_pct=cmd.stop_loss_pct,
            take_profit_pct=cmd.take_profit_pct, signal_strength=cmd.signal_strength,
            llm_justification=f"Placed by {cmd.requested_by}", status="OPEN",
            exit_price=None, exit_reason=None, pnl_usd=None, pnl_pct=None,
            opened_at=datetime.now(tz=MARKET_TZ), closed_at=None,
            order_id=order_result.order_id,
            trade_status="FILLED", entry_fill_price=fill_price, remaining_quantity=units,
        ))

        self._notifier.notify(
            f"Orden ejecutada: <b>{cmd.action} {units} {symbol}</b>\n"
            f"Entrada: ${price_for_sl}\nStop-loss: ${stop_loss_price}\n"
            f"Take-profit: ${take_profit_price}\nOrder ID: {order_result.order_id}"
        )
        return PlaceOrderResult(success=True, order_id=order_result.order_id, trade_id=trade_id)
