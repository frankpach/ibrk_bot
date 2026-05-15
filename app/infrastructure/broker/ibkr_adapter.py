# app/infrastructure/broker/ibkr_adapter.py
from decimal import Decimal

from app.application.ports.broker_port import IBrokerPort
from app.domain.trading.value_objects import Order, OrderResult, Position, AccountSummary
from app.ibkr.client import get_client


class IBKRBrokerAdapter(IBrokerPort):
    """Wraps IBKRClient to conform to IBrokerPort interface."""

    def __init__(self, client=None):
        self._client = client or get_client()

    def get_price(self, symbol: str, sec_type: str = "STK", exchange: str = "SMART", currency: str = "USD") -> Decimal:
        data = self._client.get_stock_price(symbol)
        price = data.get("market_price", 0.0) or 0.0
        return Decimal(str(price))

    def get_prev_close(self, symbol: str, sec_type: str = "STK", exchange: str = "SMART", currency: str = "USD") -> Decimal:
        prev_close = self._client.get_prev_close(symbol, sec_type, exchange, currency)
        return Decimal(str(prev_close))

    def place_order(self, order: Order) -> OrderResult:
        result = self._client.place_order(
            symbol=order.symbol,
            action=order.action,
            quantity=order.quantity,
            order_type=order.order_type,
            limit_price=order.limit_price,
        )
        success = bool(result.get("order_id"))
        return OrderResult(
            success=success,
            order_id=result.get("order_id", ""),
            fill_price=result.get("fill_price"),
            reason=result.get("reason"),
        )

    def get_portfolio(self) -> list[Position]:
        raw = self._client.get_portfolio()
        positions = []
        for item in raw:
            positions.append(Position(
                symbol=item.get("symbol", ""),
                quantity=float(item.get("quantity", 0) or 0),
                avg_cost=float(item.get("avg_cost", 0) or 0),
                market_value=float(item.get("market_value", 0) or 0),
                unrealized_pnl=float(item.get("unrealized_pnl", 0) or 0),
            ))
        return positions

    def get_account(self) -> AccountSummary:
        data = self._client.get_account()
        return AccountSummary(
            net_liquidation=float(data.get("net_liquidation", 0) or 0),
            buying_power=float(data.get("buying_power", 0) or 0),
            daily_pnl_usd=float(data.get("daily_pnl_usd", 0) or 0),
            daily_pnl_pct=float(data.get("daily_pnl_pct", 0) or 0),
        )

    def reconnect(self, port: int = 4002) -> None:
        # Delegate to client's internal reconnect if available
        if hasattr(self._client, "_connect_async"):
            self._client._run_sync(self._client._connect_async())
