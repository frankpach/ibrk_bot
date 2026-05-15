# app/infrastructure/broker/mock_adapter.py
from decimal import Decimal

from app.application.ports.broker_port import IBrokerPort
from app.domain.trading.value_objects import Order, OrderResult, Position, AccountSummary


class MockBrokerAdapter(IBrokerPort):
    """Test-only broker adapter with configurable responses."""

    def __init__(self, prices: dict[str, Decimal] = None, prev_closes: dict[str, Decimal] = None,
                 portfolio: list[Position] = None, account: AccountSummary = None):
        self.prices = prices or {}
        self.prev_closes = prev_closes or {}
        self._portfolio = portfolio or []
        self._account = account or AccountSummary(
            net_liquidation=10000.0,
            buying_power=10000.0,
            daily_pnl_usd=0.0,
            daily_pnl_pct=0.0,
        )
        self.orders_placed: list[Order] = []
        self._order_counter = 0

    def get_price(self, symbol: str, sec_type: str = "STK", exchange: str = "SMART", currency: str = "USD") -> Decimal:
        return self.prices.get(symbol.upper(), Decimal("0"))

    def get_prev_close(self, symbol: str, sec_type: str = "STK", exchange: str = "SMART", currency: str = "USD") -> Decimal:
        return self.prev_closes.get(symbol.upper(), Decimal("0"))

    def place_order(self, order: Order) -> OrderResult:
        self.orders_placed.append(order)
        self._order_counter += 1
        return OrderResult(
            success=True,
            order_id=f"mock-{self._order_counter}",
            fill_price=self.prices.get(order.symbol.upper(), Decimal("0")),
        )

    def get_portfolio(self) -> list[Position]:
        return list(self._portfolio)

    def get_account(self) -> AccountSummary:
        return self._account

    def reconnect(self, port: int = 4002) -> None:
        pass
